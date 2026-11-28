"""Stage pinned CC0 orchestral recordings for review; never alter active engine assets."""
import argparse, hashlib, json, re, shutil, subprocess, tempfile
from pathlib import Path
import soundfile as sf
import numpy as np

SOURCE="https://github.com/sgossner/VSCO-2-CE"
CATEGORIES={"clarinet":"Woodwinds/Clarinet","oboe":"Woodwinds/Oboe","bassoon":"Woodwinds/Bassoon"}
def stage(root, revision):
    if not re.fullmatch(r"[0-9a-f]{40}",revision):raise ValueError("Use an exact reviewed source commit")
    root.mkdir(parents=True,exist_ok=True)
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/"source"
        subprocess.run(["git","init",str(source)],check=True)
        subprocess.run(["git","-C",str(source),"remote","add","origin",SOURCE+".git"],check=True)
        subprocess.run(["git","-C",str(source),"fetch","--depth=1","origin",revision],check=True)
        subprocess.run(["git","-C",str(source),"checkout","--detach","FETCH_HEAD"],check=True)
        if subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True).strip()!=revision:raise RuntimeError("Source revision mismatch")
        licence=(source/"LICENSE").read_text()
        if not licence.startswith("CC0 1.0 Universal"):raise RuntimeError("Licence evidence needs review")
        (root/"VSCO-LICENSE.txt").write_text(licence)
        seen=set()
        for instrument,category in CATEGORIES.items():
            files=sorted((source/category).rglob("*.wav"))
            if not files:raise RuntimeError("Missing category: "+category)
            for p in files:
                if p.is_symlink():continue
                digest=hashlib.sha256(p.read_bytes()).hexdigest()
                if digest in seen:continue
                info=sf.info(p)
                if info.frames<=0 or info.channels not in (1,2) or info.samplerate<22050:continue
                peak=0.;energy=0.;count=0;clipped=0
                with sf.SoundFile(p) as audio:
                    for block in audio.blocks(blocksize=65536,dtype="float64",always_2d=True):
                        if not np.isfinite(block).all():raise ValueError("Nonfinite sample: "+str(p))
                        peak=max(peak,float(np.abs(block).max()));energy+=float(np.sum(block*block));count+=block.size;clipped+=int(np.sum(np.abs(block)>=.9999))
                if peak<.005 or (energy/max(count,1))**.5<.0005 or clipped/max(count,1)>.001:continue
                seen.add(digest)
                dest=root/"audio"/(digest+".wav");dest.parent.mkdir(exist_ok=True)
                shutil.copy2(p,dest)
                rows.append(dict(id=digest,path=str(dest.relative_to(root)),title=p.stem,instrument=instrument,kind="instrument",creator="Versilian Studios LLC / see source licence",source=SOURCE+"/blob/"+revision+"/"+p.relative_to(source).as_posix(),license="CC0-1.0",license_url="https://creativecommons.org/publicdomain/zero/1.0/",duration=info.duration,sample_rate=info.samplerate,subtype=info.subtype,channels=info.channels,quality=dict(peak=peak,rms=(energy/count)**.5,clipped_fraction=clipped/count),technical_verified=True,rights_verified=False,reviewed=False,review_scope="Staged from pinned CC0 repository; per-recording rights and listening review pending"))
    (root/"candidate-index.json").write_text(json.dumps(rows,indent=2))
    return len(rows)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("destination",type=Path)
    p.add_argument("revision")
    a=p.parse_args()
    print("Unique candidate samples staged:",stage(a.destination,a.revision))
