"""Experimental real-sample woodwinds; pinned public source, private job-local install."""
import hashlib, json, math, tempfile, shutil
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from stage_orchestra_expansion import stage
from pitch_woodwinds import main as measure

REVISION="440300901dfe9275fd84e0b7763af1f8443ae62e"
SR=48000
def install(root,names):
    with tempfile.TemporaryDirectory(prefix="woodwind-") as tmp:
        staged=Path(tmp);stage(staged,REVISION);measure(staged)
        rows=json.loads((staged/"pitch-map.json").read_text())
        for name in sorted(names):
            dest=root/"instruments"/name
            if dest.is_symlink() or dest.exists():raise RuntimeError("Unexpected existing experimental bank")
            dest.mkdir(parents=True)
            bank=[]
            for r in rows:
                if r["instrument"]!=name:continue
                src=staged/r["path"]
                if hashlib.sha256(src.read_bytes()).hexdigest()!=r["id"]:raise RuntimeError("Sample checksum mismatch")
                shutil.copy2(src,dest/(r["id"]+".wav"))
                bank.append(r)
            if not bank:raise RuntimeError("No verified samples for "+name)
            (dest/"pitch-map.json").write_text(json.dumps(bank))
            (root/"licenses"/(name+".json")).write_text(json.dumps(dict(category="instruments/"+name,creator="Versilian Studios LLC / source contributors",license="CC0-1.0",license_url="https://creativecommons.org/publicdomain/zero/1.0/",source="https://github.com/sgossner/VSCO-2-CE/tree/"+REVISION,commercial_use=True,experimental=True,listening_review="pending",recordings=[r["source"] for r in bank]),indent=2))
def render(root,name,notes,frames,rng):
    dest=root/"instruments"/name
    bank=json.loads((dest/"pitch-map.json").read_text())
    bus=np.zeros((frames,2),np.float32)
    cache={}
    for n in notes:
        candidates=[r for r in bank if r["pitch_verified"] and abs(r["midi"]-n.pitch)<=3]
        if not candidates:raise RuntimeError("Uncovered woodwind note")
        nearest=min(abs(r["midi"]-n.pitch) for r in candidates)
        candidates=[r for r in candidates if abs(r["midi"]-n.pitch)==nearest]
        layer=min(r["velocity_layer"] for r in candidates)
        options=[r for r in candidates if r["velocity_layer"]==layer]
        row=options[int(rng.integers(len(options)))]
        id=row["id"]
        if id not in cache:
            x,sr=sf.read(dest/(id+".wav"),dtype="float32",always_2d=True)
            g=math.gcd(sr,SR);x=resample_poly(x,SR//g,sr//g,axis=0).astype(np.float32)
            cache[id]=x
        x=cache[id]
        ratio=2**((n.pitch-row["measured_midi"])/12)
        start=round(n.start*SR)
        length=min(int((n.end-n.start+.6)*SR),int((len(x)-1)/ratio),frames-start)
        if length<SR//10:continue
        ix=np.arange(length)*ratio
        y=np.stack([np.interp(ix,np.arange(len(x)),x[:,c]) for c in range(x.shape[1])],axis=1)
        if y.shape[1]==1:y=np.repeat(y,2,axis=1)
        attack=min(length//3,int(SR*.14));release=min(length//3,int(SR*.55))
        y[:attack]*=np.linspace(0,1,attack)[:,None]
        y[-release:]*=np.linspace(1,0,release)[:,None]**2
        bus[start:start+length]+=y*(n.velocity/127)**.8
    if not np.isfinite(bus).all() or np.sqrt(np.mean(bus*bus))<1e-8:raise RuntimeError("Invalid woodwind output")
    return bus
