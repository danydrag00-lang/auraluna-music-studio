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

import argparse, json, os, subprocess, uuid, hashlib, time, socket
from pathlib import Path
import numpy as np
import pretty_midi
import soundfile as sf
from scipy.signal import butter,sosfilt

p=argparse.ArgumentParser()
p.add_argument("--mood",choices=["deep_sleep","luxury_spa","meditation","peaceful_piano"],default="luxury_spa")
p.add_argument("--seconds",type=int,default=30)
p.add_argument("--engine",choices=["aria","fast"],default="aria")
p.add_argument("--midi-only",action="store_true",help="Skip unused preview rendering during production")
p.add_argument("--rain",action="store_true")
a=p.parse_args()
if not 15<=a.seconds<=(120 if a.engine=="fast" else 60):p.error("Unsupported composition section duration")
root=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
out=root/"productions"/uuid.uuid4().hex[:12]
out.mkdir(parents=True)
rng=np.random.default_rng()
sr=48000
if a.engine=="fast":
    # Original stochastic tonal phrases; acoustic rendering is handled by arrange.py.
    # Choose one key per production when supplied, to keep section transitions coherent.
    key=int(os.environ.get("AURALUNA_TONIC",str(int(rng.choice([48,50,53,55,57])))))
    scale=[0,2,3,5,7,8,10] if a.mood=="deep_sleep" else [0,2,4,5,7,9,11]
    # Diatonic progressions selected independently per section; one stable key per variation.
    progressions=[[0,5,3,0],[0,3,1,0],[0,2,3,5],[0,3,4,0],[5,3,0,2]]
    roots=progressions[int(rng.integers(len(progressions)))]
    chords=[[(d+j)%7 for j in (0,2,4)] for d in roots]
    beat=float(rng.uniform(1.0,1.25)) if a.mood=="luxury_spa" else float(rng.uniform(1.3,1.65))
    phrase=beat*4
    midi=pretty_midi.PrettyMIDI()
    track=pretty_midi.Instrument(0)
    def note(p,t,d,v):
        t=max(0,t);end=min(a.seconds,t+d)
        if end>t:track.notes.append(pretty_midi.Note(int(v),int(p),float(t),float(end)))
    motif=rng.integers(0,3,size=4)
    previous=key+12
    for i,t in enumerate(np.arange(0,a.seconds,phrase)):
        degrees=chords[i%len(chords)]
        pitches=[key+scale[d] for d in degrees]
        root=pitches[0]
        note(root-12,t,phrase*.87, rng.integers(34,44))
        note(pitches[2],t+beat*.35,phrase*.70,rng.integers(30,40))
        for j,pitch in enumerate(pitches):
            note(pitch,t+beat*(.15+j*.65),phrase*.72,rng.integers(34,46))
        for j in range(3):
            if j>0 and rng.random()<.22:continue
            degree=degrees[int(motif[(j+i)%4])] if rng.random()<.8 else int(rng.choice(degrees))
            candidates=[key+scale[degree]+o for o in (0,12,24) if 55<=key+scale[degree]+o<=84]
            pitch=min(candidates,key=lambda n:abs(n-previous)+float(rng.uniform(0,5)))
            previous=pitch
            note(pitch,t+beat*(.65+j*1.05)+float(rng.uniform(-.04,.04)),beat*float(rng.uniform(.9,1.6)),rng.integers(43,58))
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
