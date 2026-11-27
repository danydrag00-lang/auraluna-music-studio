"""Kaggle entry point; expects request JSON and attached private assets dataset."""
import argparse, json, os, shutil, subprocess, sys, tarfile
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("request",type=Path)
a=p.parse_args()
root=Path("/kaggle/working/Auraluna-V9")
# Keep scratch outside saved notebook output where possible.
scratch=Path("/kaggle/temp/auraluna-v9")
scratch.mkdir(parents=True,exist_ok=True)
root=scratch
os.environ["AURALUNA_ROOT"]=str(root)
root.mkdir(parents=True,exist_ok=True)
inputs=Path("/kaggle/input")
required=("instruments","nature","licenses","models/model.safetensors")
def complete(p):
    return all((p/name).exists() for name in required)
def locate(base):
    return sorted({p.parent.parent for p in base.rglob("model.safetensors") if p.parent.name=="models" and complete(p.parent.parent)})
print("Dataset mount entries:",[str(p) for p in inputs.iterdir()] if inputs.exists() else [],flush=True)
sources=locate(inputs)
if len(sources)>1:raise RuntimeError("Multiple complete asset roots: "+str(sources))
if not sources:
    archives=sorted(p for p in inputs.rglob("*") if p.is_file() and p.name.lower().endswith((".tar",".tar.gz",".tgz",".tar.xz",".tar.bz2")) and "auraluna" in p.name.lower())
    print("Asset archive candidates:",[str(p) for p in archives],flush=True)
    if len(archives)!=1:
        import itertools
        print("Input sample:",[str(p) for p in itertools.islice(inputs.rglob("*"),40)],flush=True)
        raise RuntimeError("No unique Auraluna archive or complete extracted asset root; verify dataset attachment and contents")
    unpack=scratch/"unpacked"
    unpack.mkdir(exist_ok=True)
    with tarfile.open(archives[0],"r:*") as t:
        t.extractall(unpack,filter="data")
    sources=locate(unpack)
    if len(sources)!=1:raise RuntimeError("Archive does not contain one complete asset root: "+str(sources))
source=sources[0]
print("Using asset root:",source,flush=True)
for name in ("instruments","nature","licenses","models"):
    target=root/name
    if not target.exists():target.symlink_to(source/name,target_is_directory=True)

for name in ("instruments","nature","licenses","models/model.safetensors"):
    if not (root/name).exists():raise RuntimeError("Asset missing: "+name)
engine=Path(__file__).resolve().parent
subprocess.run([sys.executable,str(engine/"bootstrap.py")],check=True)
from request import normalize,command
r=normalize(json.loads(a.request.read_text()))
print("Starting",r["job"],flush=True)
# Run bounded batches inside this single remote notebook.
for _ in range(1000):
    subprocess.run(command(r,12),check=True)
    job=root/"jobs"/r["job"]
    if all((job/f"variation_{i}"/"completed.json").exists() for i in range(1,r["variations"]+1)):break
else:raise RuntimeError("Production did not finish within batch limit")
output=Path("/kaggle/working/results")
output.mkdir(exist_ok=True)
for i in range(1,r["variations"]+1):
    source=job/f"variation_{i}"
    for name in ("music."+r["format"],"licences.json","completed.json"):
        if not (source/name).is_file():raise RuntimeError("Missing production output: "+name)
        shutil.copy2(source/name,output/f"variation_{i}_{name}")
print("AURALUNA COMPLETE",flush=True)
