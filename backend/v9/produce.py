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
p.add_argument("--tuning",choices=["standard","a432","c528"],default="standard")
p.add_argument("--composition",choices=["independent","thematic"],default="independent")
p.add_argument("--engine",choices=["aria","fast","studio"],default="aria")
p.add_argument("--seconds",type=int,default=120)
p.add_argument("--job",default=None)
p.add_argument("--seed",default="")
p.add_argument("--seed-variation",type=int,default=1)
p.add_argument("--max-sections",type=int,default=2)
p.add_argument("--aac-mode",choices=["premium","vbr","balanced"],default="premium")
p.add_argument("--mastering",choices=["original","sleep","spa","youtube"],default="original")
p.add_argument("--format",choices=["mp3","m4a","flac","wav"],default="mp3")
p.add_argument("--variations",type=int,choices=[1,2,3],default=1)
p.add_argument("--gains",default="{}")
p.add_argument("--instruments",default=None)
p.add_argument("--nature-layers",default=None)
p.add_argument("--nature",choices=["none","rain","river","ocean","forest"],default=None)
a=p.parse_args()
gains=json.loads(a.gains)
allowed={"felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls","clarinet","oboe","bassoon"}
if not isinstance(gains,dict) or any(k not in allowed or not isinstance(v,(int,float)) or not math.isfinite(v) or not -60<=v<=12 for k,v in gains.items()):p.error("Invalid instrument gains")
if a.instruments and not set(a.instruments.split(","))<=allowed:p.error("Invalid instruments")
if not 15<=a.seconds<=43200 or a.max_sections<1: p.error("Duration 15–43200 seconds; positive max-sections")
job_id=a.job or uuid.uuid4().hex[:12]
if a.seed and (a.engine not in ("fast","studio") or not a.seed.isascii() or not a.seed.isalnum() or len(a.seed)>48):p.error("Seed requires Fast Acoustic and 1–48 ASCII letters or digits")
if not 1<=a.seed_variation<=3 or (a.seed_variation!=1 and (not a.seed or a.variations!=1)):p.error("Selected seed variation requires a fixed seed and one output")
creative_seed=a.seed or job_id
def seed_for(*parts):return int(hashlib.sha256(":".join(map(str,(creative_seed,*parts))).encode()).hexdigest()[:16],16)
if not job_id.isalnum():p.error("Job ID must be alphanumeric")
job=ROOT/"jobs"/job_id; job.mkdir(parents=True,exist_ok=True)
manifest=job/"job.json"
config={"quality_revision":23,"mastering":a.mastering,"seed_variation":a.seed_variation,"seed":creative_seed,"aac_mode":a.aac_mode,"tuning":a.tuning,"nature_layers":a.nature_layers,"composition":a.composition,"engine":a.engine,"preset":a.preset,"seconds":a.seconds,"format":a.format,"variations":a.variations}
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
layers=json.loads(a.nature_layers) if a.nature_layers is not None else ({nature:0} if nature!="none" else {})
if not isinstance(layers,dict) or any(k not in {"rain","river","ocean","forest"} or type(v) not in (int,float) or not math.isfinite(v) or not -30<=v<=6 for k,v in layers.items()):p.error("Invalid nature mixer")
if not mood and not layers:p.error("Select at least one sound source")
if not mood and a.tuning!="standard":p.error("Tuning requires instruments")
pitch_ratio={"standard":1.0,"a432":432/440,"c528":528/(440*2**(3/12))}[a.tuning]
if pitch_ratio!=1:
    filters=subprocess.run(["ffmpeg","-hide_banner","-filters"],capture_output=True,text=True,check=True).stdout
    if "rubberband" not in filters:raise RuntimeError("High-quality pitch-shifting filter unavailable; no lower-quality fallback used")
import shutil
# Conservative disk budget: uncompressed 24-bit checkpoints plus final output, with 512 MiB scratch allowance.
bytes_per_second={"mp3":40000,"m4a":50000 if a.aac_mode=="vbr" else 25000 if a.aac_mode=="balanced" else 33000,"flac":288000,"wav":288000}[a.format]
if a.format=="wav" and a.seconds*288000>=2**32-65536:p.error("WAV exceeds RIFF size limit; choose FLAC or MP3")
existing=sum(x.stat().st_size for x in job.rglob("*") if x.is_file())
required=max(0,a.variations*a.seconds*(bytes_per_second+(310000 if mood else 0))-existing)+512*1024**2
if shutil.disk_usage(job).free<required:raise RuntimeError("Insufficient estimated free disk; choose shorter duration, fewer variations or MP3")
overlap=4*SR
# Equal-size 15–60 second source sections; no final tiny section.
section_limit=120 if a.engine in ("fast","studio") else 60
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
def get_loop(nature):
    candidates=sorted((ROOT/"nature"/nature).rglob("*.wav"))
    if not candidates:raise RuntimeError("Missing nature recording: "+nature)
    path=candidates[int(hashlib.sha256((creative_seed+":"+str(musical_v)+":"+nature).encode()).hexdigest(),16)%len(candidates)]
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
    return np.roll(x,int(hashlib.sha256((creative_seed+":"+str(musical_v)).encode()).hexdigest(),16)%len(x),axis=0)
budget=a.max_sections
for v in range(1,a.variations+1):
    musical_v=v+a.seed_variation-1
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
            env=dict(os.environ,AURALUNA_ROOT=str(isolated),AURALUNA_TONIC=str([48,50,53,55,57][int(hashlib.sha256((creative_seed+str(musical_v)).encode()).hexdigest(),16)%5]))
            if a.engine in ("fast","studio"):env["AURALUNA_PERFORMANCE_SEED"]=str(seed_for(musical_v,i,"performance"))
            env.update(AURALUNA_SECTION=str(i),AURALUNA_SECTIONS=str(count),AURALUNA_MOTIF_SEED=str(int(hashlib.sha256((creative_seed+":"+str(musical_v)+(":"+str(i) if a.composition=="independent" else "")).encode()).hexdigest()[:16],16)),AURALUNA_COMPOSITION=a.composition)
            if a.seconds<=60 and count==1 and a.tuning=="standard":env["AURALUNA_STEMS"]="1"
            for attempt in range(3):
                if a.engine in ("fast","studio"):
                    env["AURALUNA_PERFORMANCE_SEED"]=str(seed_for(musical_v,i,attempt,"performance"))
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
                    if a.engine in ("fast","studio") and a.composition=="independent" and maximum is not None and maximum>.85 and attempt<2:
                        print(f"Variation {v}: retrying similar section ({maximum:.2f})",flush=True)
                        env["AURALUNA_MOTIF_SEED"]=str(seed_for(musical_v,i,attempt+1,"motif"))
                        continue
                    run([sys.executable,str(HERE/"arrange.py"),"--root",str(isolated),"--midi",str(midi),"--mood",mood,"--seconds",str(section_seconds),"--instruments",instruments,"--nature","none","--section","--gains",json.dumps(gains)],folder/"arrange.log",env)
                    ensemble=midi.parent/"ensemble"
                    section_report=json.loads((ensemble/"report.json").read_text())
                    expected=set(instruments.split(","))
                    rendered=section_report.get("notes",{})
                    if any(not rendered.get(name,0) for name in expected):raise RuntimeError("Missing instrument in rendered section")
                    source=ensemble/"ensemble.flac"
                    if not valid(source,section_seconds*SR):raise RuntimeError("Invalid section")
                    if pitch_ratio!=1:
                        shifted=ensemble/"tuned.flac"
                        frames=section_seconds*SR
                        filter_spec=f"rubberband=pitch={pitch_ratio:.12f}:tempo=1:pitchq=quality:channels=together,apad=whole_len={frames},atrim=end_sample={frames}"
                        run(["ffmpeg","-y","-loglevel","error","-i",str(source),"-af",filter_spec,"-c:a","flac","-sample_fmt","s32","-bits_per_raw_sample","24",str(shifted)],folder/"tuning.log")
                        if not valid(shifted,frames):raise RuntimeError("Invalid tuned section")
                        source=shifted
                    import shutil
                    temp=dest.with_suffix(".part")
                    # Section renderer already writes lossless PCM24 checkpoints.
                    shutil.move(str(source),str(temp));os.replace(temp,dest)
                    shutil.copy2(midi,folder/f"section_{i:04d}.mid")
                    for stem in ensemble.glob("stem_*.flac"):
                        if not valid(stem,section_seconds*SR):raise RuntimeError("Invalid acoustic stem")
                        shutil.copy2(stem,folder/stem.name)
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
    loops={name:get_loop(name) for name in layers}
    layer_scale=max(1,math.sqrt(sum(10**(gain/10) for gain in layers.values())))
    total=a.seconds*SR
    pos=0
    intermediate=folder/"master.part.flac"
    temp=folder/("music.part."+a.format)
    # Stream straight to final encoder instead of retaining a full extra master.
    codec=["-b:a","320k"] if a.format=="mp3" else (["-c:a","aac","-profile:a","aac_low","-aac_coder","twoloop"]+(["-q:a","1.5"] if a.aac_mode=="vbr" else ["-b:a","192k" if a.aac_mode=="balanced" else "256k"])+["-movflags","+faststart"]) if a.format=="m4a" else ["-c:a","pcm_s24le"] if a.format=="wav" else ["-c:a","flac","-sample_fmt","s32","-bits_per_raw_sample","24"]
    from contextlib import contextmanager
    @contextmanager
    def encoder():
        with (folder/"export.log").open("ab") as log:
            proc=subprocess.Popen(["ffmpeg","-y","-loglevel","error","-f","f32le","-ar",str(SR),"-ac","2","-i","pipe:0",*(["-c:a","flac","-sample_fmt","s32","-bits_per_raw_sample","24",str(intermediate)] if a.mastering=="youtube" else [*codec,str(temp)])],stdin=subprocess.PIPE,stdout=log,stderr=log)
            class Writer:
                def write(self,x):proc.stdin.write(np.asarray(x,dtype="<f4").tobytes())
            try:
                yield Writer()
                proc.stdin.close()
                if proc.wait()!=0:raise RuntimeError("Encoding failed; inspect export.log")
            except BaseException:
                proc.kill();proc.wait();raise
    master_gain,peak_ceiling,fade_in,fade_out={"original":(0,-8,6,8),"sleep":(-3,-10,10,15),"spa":(0,-8,8,12),"youtube":(3,-4,6,8)}[a.mastering]
    stats={"sum_squares":0.0,"samples":0,"peak":0.0,"limited_samples":0}
    if a.mastering=="youtube" and shutil.disk_usage(folder).free<total*6+128*1024**2:raise RuntimeError("Insufficient space for lossless normalization master; choose Original mastering or a shorter duration")
    # Adaptive subtractive EQ: gentle band attenuation only when excessive energy
    # is measured. Continuous filter state and smoothed gain across blocks.
    # Original mastering is deliberately untouched.
    eq_enabled=a.mastering in ("sleep","spa","youtube")
    eq_report={"enabled":eq_enabled,"method":"adaptive subtractive band EQ","bands":[]}
    if eq_enabled:
        from scipy.signal import butter,sosfilt
        eq_bands=[]
        for name,lo,hi,threshold,max_cut in [
            ("sub_bass",20,80,.45,2.0),
            ("low_mid",180,420,.55,2.0),
            ("presence",2500,5500,.23,2.5 if a.mastering=="sleep" else 1.5),
            ("high",6500,14000,.18,1.5)]:
            sos=butter(2,[lo,hi],btype="bandpass",fs=SR,output="sos")
            eq_bands.append({"name":name,"hz":[lo,hi],"threshold":threshold,"max_cut_db":max_cut,"sos":sos,"zi":np.zeros((len(sos),2,2)),"gain":0.,"max_applied_cut_db":0.})
        def adaptive_eq(x):
            y=x.copy()
            # Analyse short blocks, not a whole hour in memory.
            for start in range(0,len(x),SR):
                stop=min(start+SR,len(x));block=x[start:stop]
                energy=float(np.mean(block*block,dtype=np.float64))
                for band in eq_bands:
                    filtered,band["zi"]=sosfilt(band["sos"],block,axis=0,zi=band["zi"])
                    ratio=float(np.mean(filtered*filtered))/max(energy,1e-12)
                    target=0. if energy<1e-9 else min(band["max_cut_db"],max(0.,10*math.log10(max(ratio,1e-12)/band["threshold"])))
                    old=band["gain"]
                    new=target+(old-target)*math.exp(-(stop-start)/(SR*2.0))
                    gain=np.linspace(old,new,stop-start,endpoint=False)
                    y[start:stop]-=(1-10**(-gain/20))[:,None]*filtered
                    band["gain"]=new
                    band["max_applied_cut_db"]=max(band["max_applied_cut_db"],new)
            return y
    with encoder() as writer:
        def write(x):
            global pos
            x=x[:max(0,total-pos)].copy()
            if not len(x):return
            ix=np.arange(pos,pos+len(x))
            for index,(name,loop) in enumerate(loops.items()):
                modulation=(1+.035*np.sin(2*np.pi*ix/(SR*(97+index*23)))).astype(np.float32)
                x+=loop[ix%len(loop)]*modulation[:,None]*(10**(layers[name]/20)/layer_scale)
            if eq_enabled:x=adaptive_eq(x)
            fade=np.minimum(np.minimum(ix/(fade_in*SR),(total-1-ix)/(fade_out*SR)),1).clip(0,1)
            x*=fade[:,None]*(10**(master_gain/20))
            limit=10**(peak_ceiling/20)
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
    normalization=None
    if a.mastering=="youtube":
        # Measure a lossless intermediate, then apply constant gain before the only lossy encode.
        # Reserve extra peak headroom for codec overshoot. Never compress dynamics to hit a target.
        import re
        measured=subprocess.run(["ffmpeg","-hide_banner","-nostats","-v","info","-i",str(intermediate),"-af","ebur128=peak=true:framelog=verbose","-f","null","-"],capture_output=True,text=True,check=True)
        summary=measured.stderr.rsplit("Summary:",1)[-1]
        loud=re.search(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS",summary)
        peak=re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS",summary)
        if not loud or not peak:raise RuntimeError("Cannot measure lossless master for normalization")
        source_lufs=float(loud.group(1));source_peak=float(peak.group(1))
        gain=min(12.0,-16.0-source_lufs,-2.0-source_peak)
        normalization={"target_lufs":-16.0,"input_lufs":source_lufs,"input_true_peak_dbtp":source_peak,"applied_gain_db":gain,"pre_encode_true_peak_budget_dbtp":-2.0,"peak_constrained":gain<(-16.0-source_lufs)-0.05}
        run(["ffmpeg","-y","-loglevel","error","-i",str(intermediate),"-af",f"volume={gain:.6f}dB,aresample=192000,alimiter=limit=0.794328:attack=5:release=100:level=false:latency=true,aresample=48000",*codec,str(temp)],folder/"export.log")
        # Keep lossless source until decoded true-peak validation passes.
    # For YouTube, verify codec overshoot and retry from lossless source if necessary.
    if normalization is not None:
        for attempt in range(3):
            check=subprocess.run(["ffmpeg","-hide_banner","-nostats","-v","info","-i",str(temp),"-af","ebur128=peak=true:framelog=verbose","-f","null","-"],capture_output=True,text=True,check=True)
            match=re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS",check.stderr.rsplit("Summary:",1)[-1])
            if not match:raise RuntimeError("Cannot verify true peak")
            tp=float(match.group(1))
            if tp<=-1.0:break
            if attempt==2:raise RuntimeError("Encoded audio exceeds true-peak ceiling after retries")
            gain-=tp+1.5
            run(["ffmpeg","-y","-loglevel","error","-i",str(intermediate),"-af",f"volume={gain:.6f}dB,aresample=192000,alimiter=limit=0.794328:attack=5:release=100:level=false:latency=true,aresample=48000",*codec,str(temp)],folder/"export.log")
        normalization.update(applied_gain_db=gain,peak_constrained=gain<(-16.0-source_lufs)-0.05,verified_true_peak_dbtp=tp,limiter_oversampling=4,encoding_attempts=attempt+1)
        intermediate.unlink()
    # Verify the encoded audio by decoding it in bounded blocks; never load an hour into RAM.
    decoded_frames=0; decoded_peak=0.0; decoded_energy=0.0; quiet_run=0; longest_quiet=0
    # Compact one-second spectral fingerprints, for screening repeated rendered passages.
    # Use only analysis copies; never resample or alter the master audio.
    fingerprints=[]
    bands=np.geomspace(60,16000,33)
    frequencies=np.fft.rfftfreq(SR,1/SR)
    band_edges=np.searchsorted(frequencies,bands)
    window=np.hanning(SR).astype(np.float32)
    # Stream AAC decoding directly into validation to avoid a huge PCM scratch file.
    @contextmanager
    def decoded_audio():
        if a.format!="m4a":
            with sf.SoundFile(temp) as check:
                if check.samplerate!=SR or check.channels!=2:raise RuntimeError("Incorrect export sample rate or channels")
                if a.format in ("flac","wav") and check.subtype!="PCM_24":raise RuntimeError("Incorrect lossless export precision")
                yield check.blocks(blocksize=SR,dtype="float32",always_2d=True)
            return
        info=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=codec_name,sample_rate,channels","-of","json",str(temp)]))["streams"][0]
        if info["codec_name"]!="aac" or int(info["sample_rate"])!=SR or info["channels"]!=2:raise RuntimeError("Incorrect AAC export format")
        with (folder/"export.log").open("ab") as log:
            proc=subprocess.Popen(["ffmpeg","-v","error","-i",str(temp),"-map","0:a:0","-f","f32le","-c:a","pcm_f32le","pipe:1"],stdout=subprocess.PIPE,stderr=log)
            def blocks():
                while True:
                    raw=proc.stdout.read(SR*8)
                    if not raw:break
                    if len(raw)%8:raise RuntimeError("Truncated PCM frame")
                    yield np.frombuffer(raw,dtype="<f4").reshape(-1,2)
            try:
                yield blocks()
                if proc.wait()!=0:raise RuntimeError("AAC decoding failed")
            finally:
                if proc.poll() is None:proc.kill();proc.wait()
                proc.stdout.close()
    with decoded_audio() as blocks:
        for block in blocks:
            if not np.isfinite(block).all():raise RuntimeError("Non-finite decoded samples")
            decoded_frames+=len(block)
            energy=float(np.sum(block*block,dtype=np.float64))
            decoded_energy+=energy
            if len(block)==SR:
                mono=block.mean(axis=1)
                spectrum=np.abs(np.fft.rfft(mono*window))**2
                features=np.array([np.log1p(spectrum[l:r].sum()) for l,r in zip(band_edges[:-1],band_edges[1:])],dtype=np.float32)
                fingerprints.append(features)
            decoded_peak=max(decoded_peak,float(np.max(np.abs(block))))
            if energy/max(1,block.size)<1e-8:
                quiet_run+=len(block);longest_quiet=max(longest_quiet,quiet_run)
            else:quiet_run=0
    tolerance=SR//10 if a.format in ("mp3","m4a") else 0
    if abs(decoded_frames-total)>tolerance:raise RuntimeError("Encoded duration does not match request")
    rms=math.sqrt(decoded_energy/max(1,decoded_frames*2))
    if rms<1e-5 or decoded_peak<1e-5:raise RuntimeError("Export is effectively silent")
    if decoded_peak>=.999:raise RuntimeError("Export reaches digital clipping threshold")
    quality={"status":"technical_checks_passed","decoded_seconds":decoded_frames/SR,"sample_rate":SR,"channels":2,"checkpoint_bits":24 if mood else None,"rms_dbfs":20*math.log10(max(rms,1e-12)),"sample_peak_dbfs":20*math.log10(max(decoded_peak,1e-12)),"longest_very_quiet_seconds":longest_quiet/SR,"warnings":[]}
    # Measure the actual encoded output with FFmpeg's EBU R128 implementation.
    # No gain changes or additional lossy encoding are applied in this pass.
    measurement=subprocess.run(["ffmpeg","-hide_banner","-nostats","-v","info","-i",str(temp),"-af","ebur128=peak=true:framelog=verbose","-f","null","-"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    import re
    summary=measurement.stderr.rsplit("Summary:",1)[-1]
    def metric(pattern):
        match=re.search(pattern,summary)
        if not match:return None
        value=float(match.group(1))
        return value if math.isfinite(value) else None
    quality["loudness"]={"method":"FFmpeg EBU R128 decoded output","integrated_lufs":metric(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS"),"range_lu":metric(r"LRA:\s*(-?\d+(?:\.\d+)?)\s*LU"),"true_peak_dbtp":metric(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS"),"status":"measured" if measurement.returncode==0 else "unavailable"}
    if measurement.returncode!=0 or quality["loudness"]["integrated_lufs"] is None or quality["loudness"]["true_peak_dbtp"] is None:
        quality["loudness"]["status"]="unavailable"
        quality["warnings"].append("Integrated loudness or true peak could not be measured.")
    elif quality["loudness"]["true_peak_dbtp"]>-1:
        quality["warnings"].append("Decoded true peak exceeds -1 dBTP; review before publishing.")
    # Compare 12-second spectral-change sequences at least 24 seconds apart.
    # Centring each band reduces false matches from constant instrumentation.
    # Report a heuristic signal only; repeating nature, chords and timbre can be intentional.
    matches=[]; comparisons=0; max_similarity=None; stride=6
    if len(fingerprints)>=36:
        features=np.asarray(fingerprints,dtype=np.float32)
        changes=np.diff(features,axis=0)
        windows=[]; times=[]
        stride=max(6,6*math.ceil(len(changes)/3600))
        for start in range(0,len(changes)-11,stride):
            vector=changes[start:start+12].reshape(-1)
            norm=float(np.linalg.norm(vector))
            if norm>.1:
                windows.append(vector/norm);times.append(start)
        if windows:
            matrix=np.asarray(windows,dtype=np.float32)
            times=np.asarray(times)
            for start in range(0,len(matrix),128):
                scores=matrix[start:start+128]@matrix.T
                eligible=times[None,:]>=times[start:start+128,None]+24
                comparisons+=int(eligible.sum())
                if not eligible.any():continue
                scores[~eligible]=-2
                best=np.argmax(scores,axis=1)
                for i,j in enumerate(best):
                    score=float(scores[i,j])
                    if score< -1:continue
                    max_similarity=score if max_similarity is None else max(max_similarity,score)
                    if score>=.92:matches.append((score,int(times[start+i]),int(times[j])))
    matches.sort(reverse=True)
    quality["audio_repetition"]={"method":"12-second log-spectral change cosine similarity","scan_stride_seconds":stride,"comparisons":comparisons,"max_similarity":max_similarity,"candidate_matches":len(matches),"examples":[{"first_seconds":a,"second_seconds":b,"similarity":round(score,4)} for score,a,b in matches[:5]],"scope":"Heuristic on final decoded audio; longer tracks use wider scan intervals, which can miss repetitions. Not proof of duplicate passages or artistic quality."}
    if matches and mood and a.composition=="independent":quality["warnings"].append("Audio analysis found similar spectral-change passages; listen at the reported timestamps.")
    quality["instrument_coverage"]={name:sum(int(x.get("instrument_events",{}).get(name,0)>0) for k,x in state["sections"].items() if k.startswith(f"{v}:")) for name in (instruments.split(",") if instruments else [])}
    quality["recorded_layers"]={"bansuri":"original-pitch recorded excerpts; repetition possible" if instruments and "bansuri" in instruments.split(",") else None,"nature":"crossfaded recordings with varied starting phase and gentle level variation" if layers else None}
    quality["tuning"]={"mode":a.tuning,"pitch_ratio":pitch_ratio,"nominal_a4_hz":440*pitch_ratio if mood else None,"nominal_c5_hz":440*2**(3/12)*pitch_ratio if mood else None,"scope":"Instrument mix only; recorded sources may deviate from concert pitch. Nature sounds unchanged."}
    quality["export"]={"format":a.format,"codec":"AAC-LC" if a.format=="m4a" else a.format.upper(),"encoding_mode":("vbr" if a.aac_mode=="vbr" else "target_bitrate") if a.format=="m4a" else "standard","vbr_quality":1.5 if a.format=="m4a" and a.aac_mode=="vbr" else None,"target_kbps":(192 if a.aac_mode=="balanced" else 256) if a.format=="m4a" and a.aac_mode!="vbr" else 320 if a.format=="mp3" else None,"file_bytes":temp.stat().st_size,"average_file_kbps":temp.stat().st_size*8/(a.seconds*1000)}
    if eq_enabled:
        eq_report["bands"]=[{k:b[k] for k in ("name","hz","max_cut_db","max_applied_cut_db")} for b in eq_bands]
    quality["equalisation"]=eq_report
    quality["mastering"]={"profile":a.mastering,"gain_db":master_gain,"sample_ceiling_dbfs":peak_ceiling,"fade_in_seconds":fade_in,"fade_out_seconds":fade_out,"scope":"Gain, soft sample peak shaping and fades; YouTube additionally uses peak-constrained constant-gain normalization; YouTube uses 4x oversampled limiting and decoded peak verification."}
    if normalization is not None:
        quality["normalization"]=normalization
        if normalization["peak_constrained"]:quality["warnings"].append("Loudness target limited by peak headroom or maximum gain; dynamics preserved.")
    quality["seed_variation"]=musical_v
    quality["composition_seed"]=creative_seed if a.engine in ("fast","studio") else None
    quality["stems"]={"available":[p.name for p in sorted(folder.glob("stem_*.flac"))],"scope":"Instrument stems before shared room effect, ensemble normalization, nature mix and final mastering; not an exact reconstruction of the mastered track."}
    quality["nature_layers_db"]=layers
    quality["nature_mix_normalization"]=layer_scale
    if longest_quiet>20*SR:quality["warnings"].append("Extended quiet passage; listen to verify it is intentional.")
    if stats["limited_samples"]>stats["samples"]*.01:quality["warnings"].append("Frequent peak limiting; review dynamics.")
    similarities=[x["similarity"] for k,x in state["sections"].items() if k.startswith(f"{v}:") and x.get("similarity") is not None]
    quality["composition_analysis"]={"method":"MIDI upper-voice interval 4-gram weighted Jaccard (heuristic)","sections":count,"max_similarity":max(similarities,default=None),"comparisons_available":len(similarities),"scope":"MIDI only; does not measure recorded phrases, nature loops or perceived audio repetition"}
    if a.engine in ("fast","studio") and a.composition=="independent" and any(x>.85 for x in similarities):quality["warnings"].append("Some MIDI sections remain highly similar; audition for repetition.")
    os.replace(temp,final)
    records=[]
    for f in (ROOT/"licenses").glob("*.json"):
        d=json.loads(f.read_text())
        if (instruments and f.stem in instruments.split(",")) or (instruments and d.get("category","").removeprefix("instruments/") in instruments.split(",")) or d.get("category") in {"nature/"+name for name in layers}:records.append(d)
    (folder/"licences.json").write_text(json.dumps(records,indent=2))
    done.write_text(json.dumps({"engine":a.engine if mood else "nature","composition":a.composition if mood and a.engine in ("fast","studio") else None,"seconds":a.seconds,"sample_rate":SR,"file":final.name,"quality":quality,"licence_note":"Review source attribution and model output rights; no legal clearance guarantee."},indent=2))
    for section in folder.glob("section_*.flac"):section.unlink()
    print(f"PERF final mix and export: {time.monotonic()-export_started:.1f}s",flush=True)
    print("COMPLETE:",final,flush=True)
print("ALL VARIATIONS COMPLETE",flush=True)
