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
archives=list(Path("/kaggle/input").rglob("Auraluna-V9-assets.tar"))
if len(archives)!=1:raise RuntimeError("Attach exactly one Auraluna V9 assets archive")
with tarfile.open(archives[0]) as t:
    t.extractall(root,filter="data")
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
