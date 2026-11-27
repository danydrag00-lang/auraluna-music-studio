"""First end-to-end V9 smoke test: original Aria MIDI, acoustic piano, optional rain."""
# The same downloaded script also runs as a private, job-local inference service.
# This branch must precede audio imports: the Aria virtualenv is separate.
import sys
if len(sys.argv)>1 and sys.argv[1]=="--serve-aria":
    import json, socket, time, traceback
    from argparse import Namespace
    from functools import lru_cache
    from pathlib import Path
    from aria import run as aria_run
    socket_path,checkpoint=sys.argv[2:4]
    original_loader=aria_run._load_inference_model_torch
    @lru_cache(maxsize=1)
    def cached_loader(checkpoint_path,config_name,strict=True):
        started=time.monotonic()
        model=original_loader(checkpoint_path,config_name,strict)
        print(f"PERF Aria model loaded: {time.monotonic()-started:.1f}s",flush=True)
        return model
    aria_run._load_inference_model_torch=cached_loader
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
        listener.bind(socket_path)
        listener.listen(1)
        print("Aria inference service ready",flush=True)
        while True:
            conn,_=listener.accept()
            with conn,conn.makefile("rwb") as stream:
                try:
                    request=json.loads(stream.readline(65536))
                    output=Path(request["output"])
                    aria_run.generate(Namespace(
                        variations=1,prompt_duration=15,backend="torch_cuda",
                        length=2048,checkpoint_path=checkpoint,
                        prompt_midi_path=request["seed"],save_dir=str(output),
                        temp=.98,min_p=.035,top_p=None,end=False,compile=False))
                    response={"ok":True}
                except Exception as exc:
                    traceback.print_exc()
                    response={"ok":False,"error":str(exc)}
                    cached_loader.cache_clear()
                    import torch
                    torch.cuda.empty_cache()
                try:
                    stream.write((json.dumps(response)+"\n").encode())
                    stream.flush()
                except OSError:
                    pass
    raise SystemExit(0)

import argparse, json, os, subprocess, uuid, hashlib, time, socket, math
from pathlib import Path
import numpy as np
import pretty_midi
import soundfile as sf
from scipy.signal import butter,sosfilt

p=argparse.ArgumentParser()
p.add_argument("--mood",choices=["deep_sleep","luxury_spa","meditation","peaceful_piano"],default="luxury_spa")
p.add_argument("--seconds",type=int,default=30)
p.add_argument("--engine",choices=["aria","fast","studio"],default="aria")
p.add_argument("--midi-only",action="store_true",help="Skip unused preview rendering during production")
p.add_argument("--rain",action="store_true")
a=p.parse_args()
if not 15<=a.seconds<=(120 if a.engine in ("fast","studio") else 60):p.error("Unsupported composition section duration")
root=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
out=root/"productions"/uuid.uuid4().hex[:12]
out.mkdir(parents=True)
rng=np.random.default_rng(int(os.environ["AURALUNA_PERFORMANCE_SEED"]) if "AURALUNA_PERFORMANCE_SEED" in os.environ else None)
sr=48000
if a.engine=="studio":
    # Original rule-based composer: long phrases, seventh/add9 harmony,
    # close-position voice leading, sparse melody, and section-level development.
    key=int(os.environ.get("AURALUNA_TONIC","50"))
    section=int(os.environ.get("AURALUNA_SECTION","0"))
    sections=max(1,int(os.environ.get("AURALUNA_SECTIONS","1")))
    thematic=os.environ.get("AURALUNA_COMPOSITION","independent")=="thematic"
    theme=np.random.default_rng(int(os.environ.get("AURALUNA_MOTIF_SEED","1")))
    minor=a.mood=="deep_sleep"
    scale=[0,2,3,5,7,8,10] if minor else [0,2,4,5,7,9,11]
    progressions=[(0,5,3,0,2,3,4,0),(0,2,5,3,0,5,4,0),(0,3,5,2,3,1,4,0),(0,5,0,3,2,5,4,0)]
    progression=progressions[int(theme.integers(len(progressions)))]
    motif=theme.choice([0,1,2,3,4],size=5,replace=True)
    beat=float(theme.uniform(1.55,1.95) if minor else theme.uniform(1.13,1.55))
    bars=max(2,round(a.seconds/(beat*4)))
    weights=np.array([1+.045*math.sin(i*.7)+float(rng.uniform(-.025,.025)) for i in range(bars)])
    edges=np.concatenate(([0.],np.cumsum(weights/weights.sum()*a.seconds)))
    midi=pretty_midi.PrettyMIDI()
    track=pretty_midi.Instrument(0)
    track.name="Studio Premium harmonic score"
    previous=[key+12,key+16,key+19];last=key+19
    def note(p,t,d,v):
        t=max(0.,float(t));end=min(float(a.seconds),t+float(d))
        if end>t:track.notes.append(pretty_midi.Note(int(np.clip(v,28,65)),int(p),t,end))
    def pc(d):return (key+scale[d%7])%12
    for i in range(bars):
        t=float(edges[i]);length=float(edges[i+1]-t)
        arc=math.sin(math.pi*(section+(i+.5)/bars)/sections)
        degree=progression[(i+(section//2 if thematic else 0))%8]
        if i==0 or i==bars-1:degree=0
        elif i==bars-2 and bars>3:degree=4
        chord=[degree,degree+2,degree+4,degree+(6 if i%4 in (1,2) else 8)]
        bass=next(p for p in range(38,50) if p%12==pc(degree))
        note(bass,t,length*.93,38+4*arc+rng.uniform(-2,2))
        # Search inversions for minimum total motion across three inner voices.
        import itertools
        options=[[p for p in range(50,73) if p%12==pc(d)] for d in chord[1:]]
        voicings=[sorted(v) for v in itertools.product(*options) if len(set(v))==3 and max(v)-min(v)<=19]
        voices=min(voicings,key=lambda v:sum(abs(x-y) for x,y in zip(v,previous))+.3*abs(sum(v)-sum(previous))) if voicings else sorted(o[0] for o in options)
        previous=voices
        for j,pitch in enumerate(voices):
            offset=length*(.08+j*(.11 if i%4<2 else .045))
            note(pitch,t+offset,length*(.78-j*.06),35+5*arc+rng.uniform(-3,3))
        # Answer a melodic question in the second half of each four-bar phrase.
        density=2 if minor else 3
        if i%4==3:density=1
        if i==bars-1:density=1
        for j,slot in enumerate([.20,.49,.73][:density]):
            if j and rng.random()<(0.35 if minor else .15):continue
            motion=int(motif[(i+j)%len(motif)])
            target=chord[motion%len(chord)] if i%4!=3 else degree
            if i==bars-1:target=0
            candidates=[p for p in range(64,82) if p%12==pc(target)]
            pitch=min(candidates,key=lambda p:abs(p-last)+float(rng.uniform(0,2)))
            last=pitch
            note(pitch,t+length*slot,length*(.27 if density>1 else .65),45+6*arc+rng.uniform(-3,3))
    midi.instruments.append(track)
    midi.write(str(out/"arrangement.mid"))
    print("STUDIO PREMIUM MIDI READY:",out/"arrangement.mid",flush=True)
    raise SystemExit(0)
if a.engine=="fast":
    # Section-aware composition: recurring motifs, gentle breathing space, stable tonal centre.
    key=int(os.environ.get("AURALUNA_TONIC","50"))
    section=int(os.environ.get("AURALUNA_SECTION","0"))
    sections=max(1,int(os.environ.get("AURALUNA_SECTIONS","1")))
    shared=int(os.environ.get("AURALUNA_MOTIF_SEED","0")) or int(rng.integers(1,2**31))
    thematic=os.environ.get("AURALUNA_COMPOSITION","independent")=="thematic"
    theme=np.random.default_rng(shared)
    scale=[0,2,3,5,7,8,10] if a.mood=="deep_sleep" else [0,2,4,5,7,9,11]
    progressions=[[0,5,3,0],[0,3,1,0],[0,2,3,5],[0,3,4,0],[5,3,0,2]]
    roots=progressions[(int(theme.integers(len(progressions)))+(section//2 if thematic else 0))%len(progressions)]
    beat=float(theme.uniform(1.05,1.28) if a.mood=="luxury_spa" else theme.uniform(1.35,1.75))
    motif=theme.integers(0,3,size=6)
    midi=pretty_midi.PrettyMIDI()
    track=pretty_midi.Instrument(0)
    previous=key+12
    def note(p,t,d,v):
        t=max(0,t);end=min(a.seconds,t+d)
        if end>t:track.notes.append(pretty_midi.Note(int(np.clip(v,25,68)),int(p),float(t),float(end)))
    t=0.;i=0
    while t<a.seconds:
        breath=1+.055*math.sin(i*.72)+float(rng.uniform(-.025,.025))
        b=beat*breath;phrase=b*4
        degree=roots[i%len(roots)]
        if i==0 or t+phrase>=a.seconds:degree=0
        degrees=[(degree+j)%7 for j in (0,2,4)]
        pitches=[key+scale[d] for d in degrees]
        root=pitches[0]
        contour=math.sin(math.pi*min(1,(section+t/a.seconds)/sections))
        swell=3*contour+2*math.sin(i*.55)
        note(root-12,t,phrase*.90,39+swell+rng.uniform(-3,3))
        for j,pitch in enumerate(pitches):
            note(pitch,t+b*(.15+j*(.48 if i%4<2 else .18)),phrase*(.65-.06*j),37+swell+rng.uniform(-4,4))
        slots=[.65,1.8,2.95] if i%4!=3 else [.85,2.4]
        for j,slot in enumerate(slots):
            if j and rng.random()<( .36 if a.mood=="deep_sleep" else .19):continue
            d=degrees[int(motif[(j+i)%len(motif)])] if rng.random()<(.88 if thematic else .65) else int(rng.choice(degrees))
            candidates=[key+scale[d]+o for o in (0,12,24) if 60<=key+scale[d]+o<=84]
            pitch=min(candidates,key=lambda n:abs(n-previous)+float(rng.uniform(0,3)))
            previous=pitch
            note(pitch,t+b*slot+float(rng.uniform(-.035,.035)),b*float(rng.uniform(.75,1.25)),48+swell+rng.uniform(-5,5))
        t+=phrase;i+=1
    midi.instruments.append(track)
    midi.write(str(out/"arrangement.mid"))
    print("FAST MIDI READY:",out/"arrangement.mid",flush=True)
    raise SystemExit(0)
# Quiet, spacious harmonic prompt; transpose within safe piano register.
offset=int(rng.choice([-2,0,2,5]))
speed={"deep_sleep":1.3,"luxury_spa":1.0,"meditation":1.2,"peaceful_piano":1.1}[a.mood]
seed=pretty_midi.PrettyMIDI()
track=pretty_midi.Instrument(0)
for pitch,start,dur,vel in [(50,0,3.8,48),(57,.8,2.8,44),(66,1.3,1.6,58),(69,3.1,1.8,54),(47,4.2,3.8,46),(54,5,2.8,42),(64,5.4,1.8,55),(62,7.5,2,49),(43,8.4,3.5,44),(59,9.1,2.7,43),(66,10.2,2,52),(64,12.5,2.5,47)]:
    track.notes.append(pretty_midi.Note(int(vel),pitch+offset,start*speed,(start+dur)*speed))
seed.instruments.append(track)
seed.write(str(out/"seed.mid"))
started=time.monotonic()
service=os.environ.get("AURALUNA_ARIA_SOCKET")
if service:
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
        deadline=time.monotonic()+90
        while True:
            try:
                conn.connect(service)
                break
            except (FileNotFoundError,ConnectionRefusedError):
                if time.monotonic()>=deadline:raise RuntimeError("Aria service did not start; inspect aria-service.log")
                time.sleep(.5)
        conn.settimeout(1800)
        with conn.makefile("rwb") as stream:
            stream.write((json.dumps({"seed":str(out/"seed.mid"),"output":str(out)})+"\n").encode())
            stream.flush()
            reply=json.loads(stream.readline(65536))
            if not reply.get("ok"):raise RuntimeError("Aria service: "+reply.get("error","unknown error"))
else:
    with (out/"aria.log").open("w") as log:
        subprocess.run(["/tmp/aria-env/bin/aria","generate","--backend","torch_cuda","--checkpoint_path",str(root/"models/model.safetensors"),"--prompt_midi_path",str(out/"seed.mid"),"--prompt_duration","15","--variations","1","--temp","0.98","--min_p","0.035","--length","2048","--save_dir",str(out)],stdout=log,stderr=subprocess.STDOUT,check=True)
print(f"Aria generation: {time.monotonic()-started:.1f}s",flush=True)
files=sorted(out.glob("res*.mid"))
if not files: raise RuntimeError("Aria produced no MIDI; inspect "+str(out/"aria.log"))
generated=pretty_midi.PrettyMIDI(str(files[0]))
midi=pretty_midi.PrettyMIDI()
piano=pretty_midi.Instrument(0)
for inst in generated.instruments:
    if inst.is_drum: continue
    for n in inst.notes:
        start=n.start*speed
        end=min(n.end*speed,a.seconds)
        if start<end:
            piano.notes.append(pretty_midi.Note(max(1,min(75,round(n.velocity*.7))),n.pitch,start,end))
if len(piano.notes)<8 or max(n.end for n in piano.notes)<a.seconds*.8:
    raise RuntimeError("Generated phrase too short; retry with a new seed")
midi.instruments.append(piano)
midi.write(str(out/"arrangement.mid"))
if a.midi_only:
    print("MIDI READY:",out/"arrangement.mid",flush=True)
    raise SystemExit(0)
font=next(iter(sorted((root/"instruments/grand_piano").rglob("*.sf2"))))
with (out/"render.log").open("w") as log:
    subprocess.run(["fluidsynth","-ni","-g","0.8","-r",str(sr),"-F",str(out/"raw.wav"),str(font),str(out/"arrangement.mid")],stdout=log,stderr=subprocess.STDOUT,check=True)
audio,rate=sf.read(out/"raw.wav",dtype="float32",always_2d=True)
assert rate==sr
frames=sr*a.seconds
audio=np.pad(audio[:frames],((0,max(0,frames-len(audio))),(0,0)))
audio=sosfilt(butter(2,25,fs=sr,btype="highpass",output="sos"),audio,axis=0).astype(np.float32)
def balance(x,db):
    rms=float(np.sqrt(np.mean(x*x)))
    if not np.isfinite(rms) or rms<1e-7: raise RuntimeError("Silent or invalid track")
    return x*min(10**(db/20)/rms,8)
audio=balance(audio,-30 if a.mood=="deep_sleep" else -28)
if a.rain:
    rain=next(iter(sorted((root/"nature/rain").rglob("*.wav"))))
    x,rate=sf.read(rain,dtype="float32",always_2d=True)
    if rate!=sr: raise RuntimeError("Unexpected rain sample rate")
    if x.shape[1]==1: x=np.repeat(x,2,axis=1)
    x=x[:,:2]
    n=min(sr*3,len(x)//4)
    if n<1: raise RuntimeError("Empty rain recording")
    w=np.linspace(0,1,n,dtype=np.float32)[:,None]
    loop=np.concatenate([x[-n:]*(1-w)+x[:n]*w,x[n:-n]])
    audio+=balance(loop[np.arange(frames)%len(loop)],-39)
fade=min(sr*3,frames//4)
audio[:fade]*=np.linspace(0,1,fade)[:,None]
audio[-fade:]*=np.linspace(1,0,fade)[:,None]
peak=float(np.max(np.abs(audio)))
if not np.isfinite(peak) or peak<1e-6: raise RuntimeError("Invalid final audio")
audio*=min(1,10**(-8/20)/peak)
sf.write(out/"preview.flac",audio,sr,subtype="PCM_24")
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(out/"preview.flac"),"-b:a","320k",str(out/"preview.mp3")],check=True)
records=[]
for f in (root/"licenses").glob("*.json"):
    record=json.loads(f.read_text())
    if f.stem=="grand_piano" or (a.rain and record.get("category")=="nature/rain"): records.append(record)
(out/"licences.json").write_text(json.dumps(records,indent=2))
(out/"generation.json").write_text(json.dumps({"mood":a.mood,"seconds":a.seconds,"sample_rate":sr,"notes":len(piano.notes),"midi_sha256":hashlib.sha256(files[0].read_bytes()).hexdigest(),"instruments":["grand_piano"],"rain":a.rain,"licence_note":"Source records only; model output rights and attribution require review."},indent=2))
(out/"raw.wav").unlink()
print("PREVIEW READY:",out/"preview.mp3")
