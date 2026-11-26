"""V9 production controller. Run beside compose_preview.py and arrange.py.
Checkpoints are local; copy the job directory to durable storage before session loss.
"""
import argparse, json, math, os, subprocess, sys, tempfile, uuid, hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR=48000
ROOT=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
HERE=Path(__file__).resolve().parent
PRESETS={
 "luxury_spa":("luxury_spa","felt_piano,flute,cello,harp","river"),
 "deep_sleep":("deep_sleep","felt_piano,cello","rain"),
 "meditation":("meditation","flute,harp","ocean"),
 "study_focus":("luxury_spa","grand_piano,harp","forest"),
 "emotional_relaxation":("meditation","felt_piano,cello","ocean"),
 "peaceful_piano":("deep_sleep","felt_piano","none"),
 "rain_sleep":(None,None,"rain"),
 "ocean_sleep":(None,None,"ocean"),
 "forest_relaxation":(None,None,"forest"),
 "river_relaxation":(None,None,"river"),
}
p=argparse.ArgumentParser()
p.add_argument("--preset",choices=PRESETS,default="luxury_spa")
p.add_argument("--seconds",type=int,default=120)
p.add_argument("--job",default=None)
p.add_argument("--max-sections",type=int,default=2)
p.add_argument("--format",choices=["mp3","flac","wav"],default="mp3")
p.add_argument("--variations",type=int,choices=[1,2,3],default=1)
a=p.parse_args()
if not 15<=a.seconds<=43200 or a.max_sections<1: p.error("Duration 15–43200 seconds; positive max-sections")
job_id=a.job or uuid.uuid4().hex[:12]
if not job_id.isalnum():p.error("Job ID must be alphanumeric")
job=ROOT/"jobs"/job_id; job.mkdir(parents=True,exist_ok=True)
manifest=job/"job.json"
config={"preset":a.preset,"seconds":a.seconds,"format":a.format,"variations":a.variations}
if manifest.exists():
    state=json.loads(manifest.read_text())
    if state["config"]!=config:raise RuntimeError("Resume with original job settings")
else:state={"config":config,"sections":{}}
def save():
    tmp=manifest.with_suffix(".tmp");tmp.write_text(json.dumps(state,indent=2));os.replace(tmp,manifest)
save()
print("JOB ID:",job_id,flush=True)
mood,instruments,nature=PRESETS[a.preset]
overlap=4*SR
# Equal-size 15–60 second source sections; no final tiny section.
count=max(1,math.ceil((a.seconds-4)/56)) if mood else 0
section_seconds=max(15,math.ceil((a.seconds+4*max(0,count-1))/max(1,count)))
def run(cmd,log,env=None):
    with log.open("a") as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
def valid(path,frames):
    try:
        info=sf.info(path);return info.frames==frames and info.samplerate==SR and info.channels==2
    except Exception:return False
def get_loop():
    if nature=="none":return None
    path=next((ROOT/"nature"/nature).rglob("*.wav"))
    x,s=sf.read(path,dtype="float32",always_2d=True)
    if s!=SR:
        g=math.gcd(s,SR);x=resample_poly(x,SR//g,s//g,axis=0)
    if x.shape[1]==1:x=np.repeat(x,2,axis=1)
    x=x[:,:2];x-=x.mean(axis=0)
    n=min(3*SR,len(x)//4)
    if n<1:raise RuntimeError("Invalid ambience")
    w=np.linspace(0,1,n,dtype=np.float32)[:,None]
    x=np.concatenate([x[-n:]*(1-w)+x[:n]*w,x[n:-n]])
    rms=float(np.sqrt(np.mean(x*x)))
    if rms<1e-8 or not np.isfinite(rms):raise RuntimeError("Silent ambience")
    return x*min(8,10**((-39 if mood else -28)/20)/rms)
budget=a.max_sections
for v in range(1,a.variations+1):
    folder=job/f"variation_{v}";folder.mkdir(exist_ok=True)
    for i in range(count):
        key=f"{v}:{i}"
        dest=folder/f"section_{i:04d}.flac"
        if key in state["sections"] and valid(dest,section_seconds*SR):continue
        if budget==0:
            print("CHECKPOINT SAVED. Repeat with --job",job_id,flush=True);sys.exit(0)
        # Isolated production directory prevents selecting an old MIDI from another job.
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            isolated=Path(tmp)
            for d in ("models","instruments","nature","licenses"):
                (isolated/d).symlink_to(ROOT/d,target_is_directory=True)
            env=dict(os.environ,AURALUNA_ROOT=str(isolated))
            for attempt in range(3):
                try:
                    run([sys.executable,str(HERE/"compose_preview.py"),"--mood",mood,"--seconds",str(section_seconds)],folder/"compose.log",env)
                    midi=max((isolated/"productions").rglob("arrangement.mid"),key=lambda p:p.stat().st_mtime)
                    # Hash note content, not MIDI file metadata.
                    import pretty_midi
                    m=pretty_midi.PrettyMIDI(str(midi))
                    signature=hashlib.sha256(json.dumps(sorted((n.pitch,round(n.start,2),round(n.end,2)) for t in m.instruments for n in t.notes)).encode()).hexdigest()
                    if any(x.get("signature")==signature for k,x in state["sections"].items() if k!=key):continue
                    run([sys.executable,str(HERE/"arrange.py"),"--root",str(isolated),"--midi",str(midi),"--mood",mood,"--seconds",str(section_seconds),"--instruments",instruments,"--nature","none"],folder/"arrange.log",env)
                    source=midi.parent/"ensemble/ensemble.flac"
                    if not valid(source,section_seconds*SR):raise RuntimeError("Invalid section")
                    import shutil
                    temp=dest.with_suffix(".part")
                    shutil.copy2(source,temp);os.replace(temp,dest)
                    shutil.copy2(midi,folder/f"section_{i:04d}.mid")
                    state["sections"][key]={"signature":signature,"file":str(dest.relative_to(job))}
                    save();break
                except (subprocess.CalledProcessError,RuntimeError,ValueError):
                    if attempt==2:raise
            else:raise RuntimeError("Repeated composition; retry job")
        budget-=1
        print(f"Variation {v}: section {i+1}/{count} saved",flush=True)
    final=folder/("music."+a.format)
    done=folder/"completed.json"
    if done.exists() and final.exists():continue
    loop=get_loop()
    total=a.seconds*SR
    pos=0
    intermediate=folder/"master.part.flac"
    with sf.SoundFile(intermediate,"w",samplerate=SR,channels=2,format="FLAC",subtype="PCM_24") as writer:
        def write(x):
            global pos
            x=x[:max(0,total-pos)].copy()
            if not len(x):return
            ix=np.arange(pos,pos+len(x))
            if loop is not None:x+=loop[ix%len(loop)]
            fade=np.minimum(np.minimum(ix/(6*SR),(total-1-ix)/(8*SR)),1).clip(0,1)
            x*=fade[:,None]
            limit=10**(-8/20)
            x=np.clip(x,-limit,limit)
            writer.write(x);pos+=len(x)
        if mood:
            pending=None
            w=np.linspace(0,1,overlap,dtype=np.float32)[:,None]
            for i in range(count):
                x,_=sf.read(folder/f"section_{i:04d}.flac",dtype="float32",always_2d=True)
                if pending is not None:
                    write(pending*np.cos(w*np.pi/2)+x[:overlap]*np.sin(w*np.pi/2))
                    x=x[overlap:]
                if i<count-1:write(x[:-overlap]);pending=x[-overlap:]
                else:write(x)
        else:
            while pos<total:write(np.zeros((min(10*SR,total-pos),2),np.float32))
    if pos!=total:raise RuntimeError(f"Wrong frame count {pos} != {total}")
    temp=folder/("music.part."+a.format)
    if a.format=="flac":os.replace(intermediate,temp)
    else:
        codec=["-b:a","320k"] if a.format=="mp3" else ["-c:a","pcm_s24le"]
        run(["ffmpeg","-y","-loglevel","error","-i",str(intermediate),*codec,str(temp)],folder/"export.log")
        intermediate.unlink()
    os.replace(temp,final)
    records=[]
    for f in (ROOT/"licenses").glob("*.json"):
        d=json.loads(f.read_text())
        if (instruments and f.stem in instruments.split(",")) or d.get("category")=="nature/"+nature:records.append(d)
    (folder/"licences.json").write_text(json.dumps(records,indent=2))
    done.write_text(json.dumps({"seconds":a.seconds,"sample_rate":SR,"file":final.name,"licence_note":"Review source attribution and model output rights; no legal clearance guarantee."},indent=2))
    print("COMPLETE:",final,flush=True)
print("ALL VARIATIONS COMPLETE",flush=True)
