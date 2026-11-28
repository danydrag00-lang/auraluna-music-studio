"""Measure sustained woodwind pitches and render a real-sample audition pack.
No automatic listening approval or activation in the production engine.
"""
import json, math, re, sys, hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly, correlate, find_peaks

SR=48000
RANGES={"clarinet":(55,76),"oboe":(60,79),"bassoon":(40,64)}
def pitch_measure(x,sr,expected):
    # Search three plausible octave conventions around the filename.
    x=np.asarray(x,dtype=np.float64)
    if x.ndim==2:x=x[:,int(np.argmax(np.mean(x*x,axis=0)))]
    x=x[int(len(x)*.2):int(len(x)*.8)]
    if len(x)<sr*.3:return None
    x=x[:sr*3];x-=x.mean()
    if np.sqrt(np.mean(x*x))<.0005:return None
    ac=correlate(x,x,mode="full",method="fft")[len(x)-1:]
    ac/=max(ac[0],1e-12)
    lo=max(2,int(sr/1400));hi=min(len(ac)-1,int(sr/45))
    peaks=find_peaks(ac[lo:hi])[0]+lo
    candidates=[]
    for p in peaks:
        if ac[p]<.60:continue
        d=ac[p-1]-2*ac[p]+ac[p+1]
        lag=p+(.5*(ac[p-1]-ac[p+1])/d if abs(d)>1e-12 else 0)
        midi=69+12*math.log2(sr/lag/440)
        # Prefer the earliest strong recurrence to avoid subharmonics.
        candidates.append((p,midi,float(ac[p])))
    if not candidates:return None
    best=max(c[2] for c in candidates)
    p,midi,confidence=next(c for c in candidates if c[2]>=max(.60,best*.87))
    options=[expected-12,expected,expected+12]
    key=min(options,key=lambda k:abs(midi-k))
    cents=100*(midi-key)
    if abs(cents)>45:return None
    return dict(midi=key,measured_midi=midi,cents=cents,periodicity=confidence)
def filename_note(title):
    m=re.search(r"_([A-G])([#b]?)(-?\d+)_v(\d+)",title)
    if not m:return None
    pc={"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[m[1]]+{"":0,"#":1,"b":-1}[m[2]]
    return 12*(int(m[3])+1)+pc,int(m[4])
def main(root):
    rows=json.loads((root/"candidate-index.json").read_text())
    mapped=[];rejected=[]
    for row in rows:
        instrument=row["instrument"]
        source=row["source"].lower()
        if instrument not in RANGES or not re.search(r"/(?:sus|suslong|vib)/",source):continue
        label=filename_note(row["title"])
        path=root/row["path"]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row["id"]:raise ValueError("Sample checksum mismatch")
        x,sr=sf.read(path,dtype="float32",always_2d=True)
        measured=pitch_measure(x,sr,label[0]) if label else None
        if measured is None:
            rejected.append(row["title"]);continue
        mapped.append({**row,**measured,"velocity_layer":label[1],"pitch_verified":True})
    (root/"pitch-map.json").write_text(json.dumps(mapped,indent=2))
    report={"accepted":{},"rejected":rejected,"listening_review":"pending"}
    for instrument,(lo,hi) in RANGES.items():
        bank=[r for r in mapped if r["instrument"]==instrument]
        if not bank:raise ValueError("No measured sustained pitches for "+instrument)
        keys=sorted({r["midi"] for r in bank})
        report["accepted"][instrument]={"samples":len(bank),"keys":keys,"largest_shift":max(min(abs(p-k) for k in keys) for p in range(lo,hi+1))}
        # Audition only notes within 3 semitones of a verified original.
        melody=[p for p in range(lo,hi+1) if p%12 in (0,2,4,7,9) and min(abs(p-k) for k in keys)<=3][:8]
        if len(melody)<3:raise ValueError("Insufficient playable audition range")
        bus=np.zeros((SR*(len(melody)*3+2),2),np.float32)
        for i,p in enumerate(melody):
            row=min(bank,key=lambda r:(abs(p-r["midi"]),r["velocity_layer"]))
            x,sr=sf.read(root/row["path"],dtype="float32",always_2d=True)
            g=math.gcd(sr,SR);x=resample_poly(x,SR//g,sr//g,axis=0)
            ratio=2**((p-row["measured_midi"])/12)
            n=min(int(2.5*SR),int((len(x)-1)/ratio))
            if n<SR//4:continue
            ix=np.arange(n)*ratio
            y=np.stack([np.interp(ix,np.arange(len(x)),x[:,c]) for c in range(x.shape[1])],axis=1)
            if y.shape[1]==1:y=np.repeat(y,2,axis=1)
            fade=min(n//3,SR//5)
            y[:fade]*=np.linspace(0,1,fade)[:,None];y[-fade:]*=np.linspace(1,0,fade)[:,None]
            y*=min(4,.12/max(np.abs(y).max(),1e-8))
            bus[i*3*SR:i*3*SR+n]+=y
        if np.sqrt(np.mean(bus*bus))<.001:raise ValueError("Silent audition")
        sf.write(root/(instrument+"-audition.wav"),bus,SR,subtype="PCM_24")
    (root/"pitch-review.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main(Path(sys.argv[1]))
