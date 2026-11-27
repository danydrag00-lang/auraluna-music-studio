"""Render an existing Aria arrangement with acoustic samples; no synthetic fallback."""
import argparse, json, re, subprocess, tempfile, math
from pathlib import Path
from functools import lru_cache
import numpy as np
import pretty_midi as pm
import soundfile as sf
from scipy.signal import resample_poly, butter, sosfilt, fftconvolve
from scipy.ndimage import map_coordinates

SR=48000
P=argparse.ArgumentParser()
P.add_argument("--root",default="/kaggle/working/Auraluna-V9")
P.add_argument("--midi",default=None)
P.add_argument("--instruments",default="felt_piano,flute,cello,harp")
P.add_argument("--nature",choices=["none","rain","river","ocean","forest"],default="river")
P.add_argument("--mood",choices=["luxury_spa","deep_sleep","meditation"],default="luxury_spa")
P.add_argument("--seconds",type=int,default=30)
P.add_argument("--section",action="store_true")
P.add_argument("--gains",default="{}")
a=P.parse_args()
gains=json.loads(a.gains)
if not isinstance(gains,dict) or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not -60<=v<=12 for v in gains.values()):raise ValueError("Gains must be dB offsets between -60 and +12")
root=Path(a.root)
assert 15<=a.seconds<=300
names=a.instruments.split(",")
assert names and len(set(names))==len(names) and set(names)<=set(["felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls"])
src=Path(a.midi) if a.midi else max((root/"productions").rglob("arrangement.mid"),key=lambda p:p.stat().st_mtime)
out=src.parent/"ensemble"
out.mkdir(exist_ok=True)
rng=np.random.default_rng()
original=pm.PrettyMIDI(str(src))
notes=sorted([n for i in original.instruments if not i.is_drum for n in i.notes if n.start<a.seconds],key=lambda n:n.start)
if not notes or max(n.end for n in notes)<a.seconds*.8: raise RuntimeError("Source MIDI too short")
frames=a.seconds*SR
def note(p,s,e,v):
    return pm.Note(int(v),int(p),float(s),float(min(e,a.seconds)))
parts={n:[] for n in names}
for name in ("felt_piano","grand_piano"):
    if name in parts: parts[name]=[note(n.pitch,n.start,n.end,n.velocity) for n in notes]
last=69
if "handpan" in parts:
    import fluidsynth
    synth=fluidsynth.Synth(gain=.8,samplerate=SR)
    sfid=synth.sfload(str(next((root/"instruments/handpan").rglob("*.sf2"))))
    synth.program_select(0,sfid,0,0)
    playable=[]
    for pitch in range(36,89):
        synth.all_sounds_off(0); synth.noteon(0,pitch,65)
        x=np.asarray(synth.get_samples(12000),dtype=np.float32)
        if np.sqrt(np.mean(x*x))>15:playable.append(pitch)
    synth.delete()
    if not playable:raise RuntimeError("No playable handpan keys")
    for t in np.cumsum(rng.uniform(2.8,4.5,size=int(a.seconds/2)+1)):
        if t>=a.seconds-1:break
        active=[n for n in notes if n.start<t+1 and n.end>t]
        compatible=[p for p in playable if any(p%12==n.pitch%12 for n in active)]
        if not compatible:continue
        pitch=int(rng.choice(compatible))
        parts["handpan"].append(note(pitch,t,t+float(rng.uniform(2.0,3.0)),rng.integers(38,49)))
for t in np.arange(0,a.seconds-1,4):
    active=[n for n in notes if n.start<t+1.2 and n.end>t]
    if not active: continue
    bass=min(n.pitch for n in active)
    pcs=set(n.pitch%12 for n in active)
    if "cello" in parts:
        pitch=next(p for p in range(40,52) if p%12==bass%12)
        parts["cello"].append(note(pitch,t+.15,t+3.5,rng.integers(35,45)))
    if "flute" in parts and (not parts["flute"] or rng.random()<(.60 if a.mood=="deep_sleep" else .78)):
        choices=[p for p in range(65,82) if p%12 in pcs]
        pitch=min(choices,key=lambda p:abs(p-last)+rng.uniform(0,4))
        parts["flute"].append(note(pitch,t+.6,t+float(rng.uniform(2.5,3.4)),rng.integers(39,49))); last=pitch
    if "harp" in parts and (not parts["harp"] or rng.random()<.70):
        choices=sorted({next(p for p in range(60,72) if p%12==pc) for pc in pcs})
        for j,p in enumerate(choices[:3]):
            parts["harp"].append(note(p,t+.25+j*.45,t+2.5+j*.45,rng.integers(33,43)))
@lru_cache(maxsize=48)
def load(path):
    x,s=sf.read(path,dtype="float32",always_2d=True)
    if s!=SR:
        g=math.gcd(s,SR); x=resample_poly(x,SR//g,s//g,axis=0).astype(np.float32)
    return x
def stereo(x):
    return np.repeat(x,2,axis=1) if x.shape[1]==1 else x[:,:2]
def mix_note(bus,x,n,attack,release):
    start=round(n.start*SR)
    length=min(len(x),round((n.end-n.start+release)*SR),len(bus)-start)
    if length<=0:return
    x=stereo(x[:length]).copy()
    k=min(length//2,max(1,round(attack*SR)))
    r=min(length//2,max(1,round(release*SR)))
    if k:x[:k]*=np.linspace(0,1,k)[:,None]
    if r:x[-r:]*=np.linspace(1,0,r)[:,None]**2
    bus[start:start+length]+=x*(n.velocity/127)**.8
def felt(ns):
    sfz=next((root/"instruments/felt_piano").rglob("*.sfz"))
    text=sfz.read_text(errors="replace")
    regions=[]
    for block in text.split("<region>")[1:]:
        d=dict(re.findall(r"(\w+)=([^\s<>]+)",block.split("<")[0]))
        if "sample" not in d:continue
        key=int(d.get("pitch_keycenter",d.get("key",d.get("lokey","-1"))))
        regions.append((key,int(d.get("lovel",0)),int(d.get("hivel",127)),sfz.parent/d["sample"].replace("\\","/")))
    if not regions:raise RuntimeError("No SFZ regions")
    bus=np.zeros((frames,2),np.float32)
    for n in ns:
        candidates=[r for r in regions if r[1]<=n.velocity<=r[2]]
        if not candidates:raise RuntimeError("Missing velocity layer")
        key,lo,hi,path=min(candidates,key=lambda r:abs(r[0]-n.pitch))
        if key!=n.pitch:raise RuntimeError("Missing exact felt piano key "+str(n.pitch))
        mix_note(bus,load(str(path)),n,.005,.35)
    return bus
def acoustic(name,ns):
    files=[]
    for path in (root/"instruments"/name).rglob("*.wav"):
        stem=path.stem
        if name=="flute" and "susnv" not in stem.lower():continue
        if name=="cello" and "susvib" not in stem.lower():continue
        m=re.search(r"_([A-G][#b]?-?\d+)_",stem)
        if m:files.append((pm.note_name_to_number(m.group(1))+12,path))
    if not files:raise RuntimeError("No sustained samples for "+name)
    bus=np.zeros((frames,2),np.float32)
    for n in ns:
        pitch,path=min(files,key=lambda r:(abs(r[0]-n.pitch),"v1" not in r[1].stem))
        x=load(str(path)).mean(axis=1)
        ratio=2**((n.pitch-pitch)/12)
        size=min(int((n.end-n.start+.65)*SR),int((len(x)-1)/ratio))
        if size<1:continue
        y=map_coordinates(x,[np.arange(size)*ratio],order=3,mode="nearest")[:,None]
        attack=float(rng.uniform(.08,.18)) if name=="flute" else float(rng.uniform(.14,.26))
        release=float(rng.uniform(.40,.65)) if name=="flute" else float(rng.uniform(.55,.85))
        mix_note(bus,y,n,attack,release)
    return bus
def font_render(name,ns):
    font=next((root/"instruments"/name).rglob("*.sf2"))
    with tempfile.TemporaryDirectory() as tmp:
        mid=Path(tmp)/"part.mid"; wav=Path(tmp)/"part.wav"
        m=pm.PrettyMIDI(); i=pm.Instrument(0);i.notes=ns;m.instruments.append(i);m.write(str(mid))
        with (out/(name+".log")).open("w") as log:
            subprocess.run(["fluidsynth","-ni","-g","0.8","-r",str(SR),"-F",str(wav),str(font),str(mid)],stdout=log,stderr=subprocess.STDOUT,check=True)
        x,s=sf.read(wav,dtype="float32",always_2d=True)
        assert s==SR
        return np.pad(stereo(x[:frames]),((0,max(0,frames-len(x))),(0,0)))
def balance(x,db,cap=8):
    rms=float(np.sqrt(np.mean(x*x)))
    if not np.isfinite(rms) or rms<1e-8:raise RuntimeError("Silent or invalid track")
    return x*min(cap,10**(db/20)/rms)
mix=np.zeros((frames,2),np.float32)
levels={"felt_piano":-30,"grand_piano":-30,"flute":-36,"cello":-38,"harp":-37,"handpan":-31,"bansuri":-31,"singing_bowls":-39}
report={}
for name,ns in parts.items():
    if name in ("bansuri","singing_bowls"):
        path=next((root/"instruments"/name).rglob("*.wav"))
        recording=stereo(load(str(path)))
        x=np.zeros((frames,2),np.float32)
        if name=="bansuri":
            # Recorded phrase, not a chromatic instrument. Keep original pitch.
            offset=int(rng.integers(0,max(1,len(recording)-frames+1)))
            segment=recording[offset:offset+frames]
            segment=segment.copy()
            fade=min(SR//2,len(segment)//4)
            if fade:
                segment[:fade]*=np.linspace(0,1,fade,dtype=np.float32)[:,None]
                segment[-fade:]*=np.linspace(1,0,fade,dtype=np.float32)[:,None]
            x[:len(segment)]=segment
            report[name]=1
        else:
            starts=[0]
            while starts[-1]+SR*22<frames:
                starts.append(starts[-1]+int(SR*rng.uniform(15,22)))
            for start in starts:
                segment=recording[:min(len(recording),frames-start)].copy()
                fade=min(SR,len(segment)//2)
                if fade:segment[-fade:]*=np.linspace(1,0,fade)[:,None]
                x[start:start+len(segment)]+=segment
            report[name]=len(starts)
        mix+=balance(x,levels[name])*10**(gains.get(name,0)/20)
        continue
    if not ns:raise RuntimeError("No playable notes for selected instrument: "+name)
    x=felt(ns) if name=="felt_piano" else acoustic(name,ns) if name in ("flute","cello") else font_render(name,ns)
    x=balance(x,levels[name])*10**(gains.get(name,0)/20)
    pan={"flute":.18,"cello":-.18,"harp":.12}.get(name,0)
    x[:,0]*=1-pan;x[:,1]*=1+pan
    mix+=x
    report[name]=len(ns)
# Light synthetic room impulse, applied only as an effect to real samples.
ir_t=np.arange(SR*2)/SR
ir=rng.normal(size=(len(ir_t),2))*np.exp(-ir_t/0.35)[:,None]
ir=sosfilt(butter(2,4200,fs=SR,output="sos"),ir,axis=0)
ir/=np.sqrt(np.sum(ir*ir,axis=0))
for c in range(2):mix[:,c]+=.12*fftconvolve(mix[:,c],ir[:,c],mode="full")[:frames]
mix=sosfilt(butter(2,25,fs=SR,btype="highpass",output="sos"),mix,axis=0).astype(np.float32)
mix=balance(mix,-30 if a.mood=="deep_sleep" else -28,4)
if a.nature!="none":
    path=next((root/"nature"/a.nature).rglob("*.wav"))
    x=stereo(load(str(path)))
    n=min(SR*3,len(x)//4)
    assert n>0
    w=np.linspace(0,1,n)[:,None]
    loop=np.concatenate([x[-n:]*(1-w)+x[:n]*w,x[n:-n]])
    mix+=balance(loop[np.arange(frames)%len(loop)],-39)
if not a.section:
    fade=min(SR*4,frames//4)
    mix[:fade]*=np.linspace(0,1,fade)[:,None]
    mix[-fade:]*=np.linspace(1,0,fade)[:,None]
ceiling=10**(-8/20)
threshold=.7*ceiling
absx=np.abs(mix)
mix=np.sign(mix)*np.where(absx>threshold,threshold+(ceiling-threshold)*np.tanh((absx-threshold)/(ceiling-threshold)),absx)
if not np.isfinite(mix).all():raise RuntimeError("Non-finite samples in ensemble")
sf.write(out/"ensemble.flac",mix,SR,subtype="PCM_24")
if not a.section:
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(out/"ensemble.flac"),"-b:a","320k",str(out/"ensemble.mp3")],check=True)
arr=pm.PrettyMIDI()
for name,ns in parts.items():
    if not ns:continue
    i=pm.Instrument({"felt_piano":0,"grand_piano":0,"harp":46,"cello":42,"flute":73,"handpan":114}[name],name=name);i.notes=ns;arr.instruments.append(i)
arr.write(str(out/"ensemble.mid"))
licences=[]
for p in (root/"licenses").glob("*.json"):
    d=json.loads(p.read_text())
    if p.stem in report or d.get("category","").removeprefix("instruments/") in report or (a.nature!="none" and d.get("category")=="nature/"+a.nature):licences.append(d)
(out/"licences.json").write_text(json.dumps(licences,indent=2))
(out/"report.json").write_text(json.dumps({"source":str(src),"seconds":a.seconds,"notes":report,"nature":a.nature,"rms_dbfs":20*np.log10(max(1e-12,float(np.sqrt(np.mean(mix*mix))))),"peak_dbfs":20*np.log10(max(1e-12,float(np.max(np.abs(mix))))),"tuning":"VSCO sustained samples assumed +12 semitones from prior audit; verify current library","licence_note":"Source records only; review attribution and model output rights."},indent=2))
print("ENSEMBLE READY:",out/("ensemble.flac" if a.section else "ensemble.mp3"))
print((out/"report.json").read_text())
