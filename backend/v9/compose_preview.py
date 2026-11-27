"""First end-to-end V9 smoke test: original Aria MIDI, acoustic piano, optional rain."""
import argparse, json, os, subprocess, uuid, hashlib, time
from pathlib import Path
import numpy as np
import pretty_midi
import soundfile as sf
from scipy.signal import butter,sosfilt

p=argparse.ArgumentParser()
p.add_argument("--mood",choices=["deep_sleep","luxury_spa","meditation","peaceful_piano"],default="luxury_spa")
p.add_argument("--seconds",type=int,default=30,choices=range(15,61))
p.add_argument("--midi-only",action="store_true",help="Skip unused preview rendering during production")
p.add_argument("--rain",action="store_true")
a=p.parse_args()
root=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
out=root/"productions"/uuid.uuid4().hex[:12]
out.mkdir(parents=True)
rng=np.random.default_rng()
sr=48000
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
