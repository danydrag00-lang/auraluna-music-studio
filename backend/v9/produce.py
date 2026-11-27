"""V9 production controller. Run beside compose_preview.py and arrange.py.
Checkpoints are local; copy the job directory to durable storage before session loss.
"""
import argparse, json, math, os, subprocess, sys, tempfile, uuid, hashlib, time
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

SR=48000
ROOT=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
HERE=Path(__file__).resolve().parent
PRESETS={
 "yoga_zen":("meditation","handpan,singing_bowls","forest"),
 "indian_meditation":("meditation","bansuri,singing_bowls","river"),
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
p.add_argument("--composition",choices=["independent","thematic"],default="independent")
p.add_argument("--engine",choices=["aria","fast"],default="aria")
p.add_argument("--seconds",type=int,default=120)
p.add_argument("--job",default=None)
p.add_argument("--max-sections",type=int,default=2)
p.add_argument("--format",choices=["mp3","flac","wav"],default="mp3")
p.add_argument("--variations",type=int,choices=[1,2,3],default=1)
p.add_argument("--gains",default="{}")
p.add_argument("--instruments",default=None)
p.add_argument("--nature",choices=["none","rain","river","ocean","forest"],default=None)
a=p.parse_args()
gains=json.loads(a.gains)
allowed={"felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls"}
if not isinstance(gains,dict) or any(k not in allowed or not isinstance(v,(int,float)) or not math.isfinite(v) or not -60<=v<=12 for k,v in gains.items()):p.error("Invalid instrument gains")
if a.instruments and not set(a.instruments.split(","))<=allowed:p.error("Invalid instruments")
if not 15<=a.seconds<=43200 or a.max_sections<1: p.error("Duration 15–43200 seconds; positive max-sections")
job_id=a.job or uuid.uuid4().hex[:12]
if not job_id.isalnum():p.error("Job ID must be alphanumeric")
job=ROOT/"jobs"/job_id; job.mkdir(parents=True,exist_ok=True)
manifest=job/"job.json"
config={"quality_revision":8,"composition":a.composition,"engine":a.engine,"preset":a.preset,"seconds":a.seconds,"format":a.format,"variations":a.variations}
if gains or a.instruments is not None or a.nature is not None:config.update(gains=gains,instruments=a.instruments,nature=a.nature)
if manifest.exists():
    state=json.loads(manifest.read_text())
    if state["config"]!=config:raise RuntimeError("Resume with original job settings")
else:state={"config":config,"sections":{}}
def save():
    tmp=manifest.with_suffix(".tmp");tmp.write_text(json.dumps(state,indent=2));os.replace(tmp,manifest)
save()
print("JOB ID:",job_id,flush=True)
mood,instruments,nature=PRESETS[a.preset]
if a.instruments is not None:
    instruments=a.instruments or None
    mood=(mood or "meditation") if instruments else None
if a.nature is not None:nature=a.nature
if not mood and nature=="none":p.error("Select at least one sound source")
import shutil
# Conservative disk budget: uncompressed 24-bit checkpoints plus final output, with 512 MiB scratch allowance.
bytes_per_second={"mp3":40000,"flac":288000,"wav":288000}[a.format]
if a.format=="wav" and a.seconds*288000>=2**32-65536:p.error("WAV exceeds RIFF size limit; choose FLAC or MP3")
existing=sum(x.stat().st_size for x in job.rglob("*") if x.is_file())
required=max(0,a.variations*a.seconds*(bytes_per_second+(310000 if mood else 0))-existing)+512*1024**2
if shutil.disk_usage(job).free<required:raise RuntimeError("Insufficient estimated free disk; choose shorter duration, fewer variations or MP3")
overlap=4*SR
# Equal-size 15–60 second source sections; no final tiny section.
section_limit=120 if a.engine=="fast" else 60
count=max(1,math.ceil((a.seconds-4)/(section_limit-4))) if mood else 0
section_seconds=max(15,math.ceil((a.seconds+4*max(0,count-1))/max(1,count)))
def run(cmd,log,env=None):
    started=time.monotonic()
    try:
        with log.open("a") as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,env=env)
    finally:
        print(f"PERF {Path(cmd[1]).name}: {time.monotonic()-started:.1f}s",flush=True)
def valid(path,frames):
    try:
        info=sf.info(path);return info.frames==frames and info.samplerate==SR and info.channels==2 and info.subtype=="PCM_24"
    except Exception:return False
def melodic_fingerprint(midi):
    # Compare transposition-independent contours, not only byte-identical MIDI.
    from collections import Counter
    notes=sorted((n for track in midi.instruments if not track.is_drum for n in track.notes),key=lambda n:(n.start,-n.pitch))
    # Extract the upper voice in short onset groups, reducing chord doubling.
    tops={}
    for n in notes:
        tick=round(n.start*5)
        tops[tick]=max(tops.get(tick,0),n.pitch)
    pitches=[tops[t] for t in sorted(tops)]
    intervals=[max(-12,min(12,b-a)) for a,b in zip(pitches,pitches[1:])]
    return dict(Counter(",".join(map(str,intervals[i:i+4])) for i in range(max(0,len(intervals)-3))))
def melodic_similarity(a,b):
    if sum(a.values())<8 or sum(b.values())<8:return None
    keys=a.keys()|b.keys()
    return sum(min(a.get(k,0),b.get(k,0)) for k in keys)/sum(max(a.get(k,0),b.get(k,0)) for k in keys)
def get_loop():
    if nature=="none":return None
    candidates=sorted((ROOT/"nature"/nature).rglob("*.wav"))
    if not candidates:raise RuntimeError("Missing nature recording: "+nature)
    path=candidates[int(hashlib.sha256((job_id+":"+str(v)+":"+nature).encode()).hexdigest(),16)%len(candidates)]
    x,s=sf.read(path,dtype="float32",always_2d=True)
    if s!=SR:
        g=math.gcd(s,SR);x=resample_poly(x,SR//g,s//g,axis=0)
    if x.shape[1]==1:x=np.repeat(x,2,axis=1)
    x=x[:,:2].copy();x-=x.mean(axis=0)
    n=min(3*SR,len(x)//4)
    if n<1:raise RuntimeError("Invalid ambience")
    w=(.5-.5*np.cos(np.linspace(0,np.pi,n,dtype=np.float32)))[:,None]
    x=np.concatenate([x[-n:]*(1-w)+x[:n]*w,x[n:-n]])
    rms=float(np.sqrt(np.mean(x*x)))
    if rms<1e-8 or not np.isfinite(rms):raise RuntimeError("Silent ambience")
    x*=min(8,10**((-39 if mood else -28)/20)/rms)
    return np.roll(x,int(hashlib.sha256((job_id+":"+str(v)).encode()).hexdigest(),16)%len(x),axis=0)
budget=a.max_sections
for v in range(1,a.variations+1):
    folder=job/f"variation_{v}";folder.mkdir(exist_ok=True)
    if (folder/"completed.json").exists() and (folder/("music."+a.format)).exists():continue
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
            env=dict(os.environ,AURALUNA_ROOT=str(isolated),AURALUNA_TONIC=str([48,50,53,55,57][int(hashlib.sha256((job_id+str(v)).encode()).hexdigest(),16)%5]))
            env.update(AURALUNA_SECTION=str(i),AURALUNA_SECTIONS=str(count),AURALUNA_MOTIF_SEED=str(int(hashlib.sha256((job_id+":"+str(v)+(":"+str(i) if a.composition=="independent" else "")).encode()).hexdigest()[:16],16)),AURALUNA_COMPOSITION=a.composition)
            for attempt in range(3):
                try:
                    run([sys.executable,str(HERE/"compose_preview.py"),"--mood",mood,"--seconds",str(section_seconds),"--midi-only","--engine",a.engine],folder/"compose.log",env)
                    midi=max((isolated/"productions").rglob("arrangement.mid"),key=lambda p:p.stat().st_mtime)
                    # Hash note content, not MIDI file metadata.
                    import pretty_midi
                    m=pretty_midi.PrettyMIDI(str(midi))
                    signature=hashlib.sha256(json.dumps(sorted((n.pitch,round(n.start,2),round(n.end,2)) for t in m.instruments for n in t.notes)).encode()).hexdigest()
                    if any(x.get("signature")==signature for k,x in state["sections"].items() if k!=key):continue
                    fingerprint=melodic_fingerprint(m)
                    similarities=[melodic_similarity(fingerprint,x.get("fingerprint",{})) for k,x in state["sections"].items() if k!=key]
                    maximum=max((x for x in similarities if x is not None),default=None)
                    # Retry highly similar independent sections, but never reject legitimate recurring themes.
                    if a.engine=="fast" and a.composition=="independent" and maximum is not None and maximum>.85 and attempt<2:
                        print(f"Variation {v}: retrying similar section ({maximum:.2f})",flush=True)
                        env["AURALUNA_MOTIF_SEED"]=str(int.from_bytes(os.urandom(8),"big"))
                        continue
                    run([sys.executable,str(HERE/"arrange.py"),"--root",str(isolated),"--midi",str(midi),"--mood",mood,"--seconds",str(section_seconds),"--instruments",instruments,"--nature","none","--section","--gains",json.dumps(gains)],folder/"arrange.log",env)
                    ensemble=midi.parent/"ensemble"
                    section_report=json.loads((ensemble/"report.json").read_text())
                    expected=set(instruments.split(","))
                    rendered=section_report.get("notes",{})
                    if any(not rendered.get(name,0) for name in expected):raise RuntimeError("Missing instrument in rendered section")
                    source=ensemble/"ensemble.flac"
                    if not valid(source,section_seconds*SR):raise RuntimeError("Invalid section")
                    import shutil
                    temp=dest.with_suffix(".part")
                    # Section renderer already writes lossless PCM24 checkpoints.
                    shutil.move(str(source),str(temp));os.replace(temp,dest)
                    shutil.copy2(midi,folder/f"section_{i:04d}.mid")
                    state["sections"][key]={"signature":signature,"fingerprint":fingerprint,"similarity":maximum,"instrument_events":rendered,"file":str(dest.relative_to(job))}
                    save();break
                except (subprocess.CalledProcessError,RuntimeError,ValueError):
                    if attempt==2:raise
            else:raise RuntimeError("Repeated composition; retry job")
        budget-=1
        print(f"Variation {v}: section {i+1}/{count} saved",flush=True)
    export_started=time.monotonic()
    final=folder/("music."+a.format)
    done=folder/"completed.json"
    if done.exists() and final.exists():continue
    loop=get_loop()
    total=a.seconds*SR
    pos=0
    intermediate=folder/"master.part.flac"
    temp=folder/("music.part."+a.format)
    # Stream straight to final encoder instead of retaining a full extra master.
    codec=["-b:a","320k"] if a.format=="mp3" else ["-c:a","pcm_s24le"] if a.format=="wav" else ["-c:a","flac","-sample_fmt","s32","-bits_per_raw_sample","24"]
    from contextlib import contextmanager
    @contextmanager
    def encoder():
        with (folder/"export.log").open("ab") as log:
            proc=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","f32le","-ar",str(SR),"-ac","2","-i","pipe:0",*codec,str(temp)],stdin=subprocess.PIPE,stdout=log,stderr=log)
            class Writer:
                def write(self,x):proc.stdin.write(np.asarray(x,dtype="<f4").tobytes())
            try:
                yield Writer()
                proc.stdin.close()
                if proc.wait()!=0:raise RuntimeError("Encoding failed; inspect export.log")
            except BaseException:
                proc.kill();proc.wait();raise
    stats={"sum_squares":0.0,"samples":0,"peak":0.0,"limited_samples":0}
    with encoder() as writer:
        def write(x):
            global pos
            x=x[:max(0,total-pos)].copy()
            if not len(x):return
            ix=np.arange(pos,pos+len(x))
            if loop is not None:
                # Very gentle continuous ambience level evolution, not synthetic sound generation.
                modulation=(1+.035*np.sin(2*np.pi*ix/(SR*97))).astype(np.float32)
                x+=loop[ix%len(loop)]*modulation[:,None]
            fade=np.minimum(np.minimum(ix/(6*SR),(total-1-ix)/(8*SR)),1).clip(0,1)
            x*=fade[:,None]
            limit=10**(-8/20)
            if not np.isfinite(x).all():raise RuntimeError("Invalid samples in master")
            stats["limited_samples"]+=int(np.count_nonzero(np.abs(x)>limit))
            # Smooth peak limiting instead of hard clipping.
            mag=np.abs(x); knee=.8*limit
            x=np.sign(x)*np.where(mag>knee,knee+(limit-knee)*np.tanh((mag-knee)/(limit-knee)),mag)
            stats["sum_squares"]+=float(np.sum(x*x,dtype=np.float64));stats["samples"]+=x.size
            stats["peak"]=max(stats["peak"],float(np.max(np.abs(x))))
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
    # Verify the encoded audio by decoding it in bounded blocks; never load an hour into RAM.
    decoded_frames=0; decoded_peak=0.0; decoded_energy=0.0; quiet_run=0; longest_quiet=0
    with sf.SoundFile(temp) as check:
        if check.samplerate!=SR or check.channels!=2:raise RuntimeError("Incorrect export sample rate or channels")
        if a.format!="mp3" and check.subtype!="PCM_24":raise RuntimeError("Incorrect lossless export precision")
        for block in check.blocks(blocksize=SR,dtype="float32",always_2d=True):
            if not np.isfinite(block).all():raise RuntimeError("Non-finite decoded samples")
            decoded_frames+=len(block)
            energy=float(np.sum(block*block,dtype=np.float64))
            decoded_energy+=energy
            decoded_peak=max(decoded_peak,float(np.max(np.abs(block))))
            if energy/max(1,block.size)<1e-8:
                quiet_run+=len(block);longest_quiet=max(longest_quiet,quiet_run)
            else:quiet_run=0
    tolerance=SR//10 if a.format=="mp3" else 0
    if abs(decoded_frames-total)>tolerance:raise RuntimeError("Encoded duration does not match request")
    rms=math.sqrt(decoded_energy/max(1,decoded_frames*2))
    if rms<1e-5 or decoded_peak<1e-5:raise RuntimeError("Export is effectively silent")
    if decoded_peak>=.999:raise RuntimeError("Export reaches digital clipping threshold")
    quality={"status":"technical_checks_passed","decoded_seconds":decoded_frames/SR,"sample_rate":SR,"channels":2,"checkpoint_bits":24 if mood else None,"rms_dbfs":20*math.log10(max(rms,1e-12)),"sample_peak_dbfs":20*math.log10(max(decoded_peak,1e-12)),"longest_very_quiet_seconds":longest_quiet/SR,"warnings":[]}
    quality["instrument_coverage"]={name:sum(int(x.get("instrument_events",{}).get(name,0)>0) for k,x in state["sections"].items() if k.startswith(f"{v}:")) for name in (instruments.split(",") if instruments else [])}
    quality["recorded_layers"]={"bansuri":"original-pitch recorded excerpts; repetition possible" if instruments and "bansuri" in instruments.split(",") else None,"nature":"crossfaded recording with varied starting phase and gentle level variation" if nature!="none" else None}
    if longest_quiet>20*SR:quality["warnings"].append("Extended quiet passage; listen to verify it is intentional.")
    if stats["limited_samples"]>stats["samples"]*.01:quality["warnings"].append("Frequent peak limiting; review dynamics.")
    similarities=[x["similarity"] for k,x in state["sections"].items() if k.startswith(f"{v}:") and x.get("similarity") is not None]
    quality["composition_analysis"]={"method":"MIDI upper-voice interval 4-gram weighted Jaccard (heuristic)","sections":count,"max_similarity":max(similarities,default=None),"comparisons_available":len(similarities),"scope":"MIDI only; does not measure recorded phrases, nature loops or perceived audio repetition"}
    if a.engine=="fast" and a.composition=="independent" and any(x>.85 for x in similarities):quality["warnings"].append("Some MIDI sections remain highly similar; audition for repetition.")
    os.replace(temp,final)
    records=[]
    for f in (ROOT/"licenses").glob("*.json"):
        d=json.loads(f.read_text())
        if (instruments and f.stem in instruments.split(",")) or (instruments and d.get("category","").removeprefix("instruments/") in instruments.split(",")) or d.get("category")=="nature/"+nature:records.append(d)
    (folder/"licences.json").write_text(json.dumps(records,indent=2))
    done.write_text(json.dumps({"engine":a.engine if mood else "nature","composition":a.composition if mood and a.engine=="fast" else None,"seconds":a.seconds,"sample_rate":SR,"file":final.name,"quality":quality,"licence_note":"Review source attribution and model output rights; no legal clearance guarantee."},indent=2))
    for section in folder.glob("section_*.flac"):section.unlink()
    print(f"PERF final mix and export: {time.monotonic()-export_started:.1f}s",flush=True)
    print("COMPLETE:",final,flush=True)
print("ALL VARIATIONS COMPLETE",flush=True)
