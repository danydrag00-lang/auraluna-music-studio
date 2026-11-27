"""Kaggle entry point; expects request JSON and attached private assets dataset."""
import argparse, json, os, shutil, subprocess, sys, tarfile, tempfile, time
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
from request import normalize,command
r=normalize(json.loads(a.request.read_text()))
nature_only=not r["instruments"]
fast=r["engine"] in ("fast","studio")
started_job=time.monotonic()
print("AURALUNA STAGE: restoring acoustic assets",flush=True)
inputs=Path("/kaggle/input")
# Restore only assets needed by this request. Keep all attribution records.
categories=["licenses"]
if r["instruments"]:categories.extend("instruments/"+name for name in r["instruments"])
categories.extend("nature/"+name for name in r.get("nature_layers",{}))
if not nature_only and not fast:categories.append("models/model.safetensors")
required=tuple(categories)
def complete(p):
    return all((p/name).exists() for name in required)
def locate(base):
    return sorted({p.parent for p in base.rglob("licenses") if p.is_dir() and complete(p.parent)})
print("Dataset mount entries:",[str(p) for p in inputs.iterdir()] if inputs.exists() else [],flush=True)
sources=locate(inputs)
if len(sources)>1:raise RuntimeError("Multiple complete asset roots: "+str(sources))
if not sources:
    archives=sorted(p for p in inputs.rglob("*") if p.is_file() and p.name.lower().endswith((".tar",".tar.gz",".tgz",".tar.xz",".tar.bz2")))
    print("Asset archive candidates:",[str(p) for p in archives],flush=True)
    # Inspect archive manifests, rather than relying on the uploaded filename.
    # Only accept archives that actually contain all the required assets under one root.
    matches=[]
    for archive in archives:
        try:
            with tarfile.open(archive,"r:*") as t:
                roots={}
                for m in t:
                    parts=Path(m.name).parts
                    if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in parts:continue
                    for target in required:
                        wanted=Path(target).parts
                        for i in range(len(parts)-len(wanted)+1):
                            if parts[i:i+len(wanted)]==wanted and m.isfile():
                                roots.setdefault(parts[:i],set()).add(target)
                for prefix,found in roots.items():
                    if found==set(required):matches.append((archive,prefix))
        except (tarfile.TarError,OSError) as exc:
            print("Could not inspect archive:",archive.name,str(exc),flush=True)
    if len(matches)!=1:
        import itertools
        print("Matching asset roots:",[(str(p),prefix) for p,prefix in matches],flush=True)
        print("Required assets:",required,flush=True)
        print("Input sample:",[str(p) for p in itertools.islice(inputs.rglob("*"),40)],flush=True)
        raise RuntimeError("No unique archive containing requested assets. Verify KAGGLE_DATASET attachment and listed missing asset categories.")
    archive,prefix=matches[0]
    unpack=scratch/"unpacked"
    unpack.mkdir(exist_ok=True)
    with tarfile.open(archive,"r:*") as t:
        def selected(member):
            parts=Path(member.name).parts
            if not (member.isfile() or member.isdir()) or member.name.startswith("/") or ".." in parts:return False
            if parts[:len(prefix)]!=prefix:return False
            relative=parts[len(prefix):]
            return any(relative[:len(Path(target).parts)]==Path(target).parts for target in required)
        t.extractall(unpack,members=(m for m in t if selected(m)),filter="data")
    print("Restored required asset categories:",", ".join(required),flush=True)
    sources=locate(unpack)
    if len(sources)!=1:raise RuntimeError("Archive does not contain one complete extracted asset root: "+str(sources))
source=sources[0]
print("Using asset root:",source,flush=True)
for name in ("instruments","nature","licenses","models"):
    target=root/name
    if not target.exists():
        if (source/name).exists():target.symlink_to(source/name,target_is_directory=True)
        else:target.mkdir(parents=True,exist_ok=True)

for name in required:
    if not (root/name).exists():raise RuntimeError("Asset missing: "+name)
engine=Path(__file__).resolve().parent
started=time.monotonic()
print("AURALUNA STAGE: preparing audio engine",flush=True)
if nature_only:
    # Nature export only needs numpy/scipy/soundfile and FFmpeg.
    import importlib.util
    missing=[name for name in ("numpy","scipy","soundfile") if importlib.util.find_spec(name) is None]
    if missing:subprocess.run([sys.executable,"-m","pip","install","-q",*missing],check=True)
    if not shutil.which("ffmpeg"):
        subprocess.run(["apt-get","update","-qq"],check=True)
        subprocess.run(["apt-get","install","-y","-qq","ffmpeg"],check=True)
    print("PERF nature-only: skipped Aria, model setup and FluidSynth",flush=True)
else:
    subprocess.run([sys.executable,str(engine/"bootstrap.py")]+(["--acoustic-only"] if fast else []),check=True)
print(f"PERF total bootstrap: {time.monotonic()-started:.1f}s",flush=True)
print("Starting",r["job"],flush=True)
job=root/"jobs"/r["job"]
# Keep one model process alive across all production batches, not across users or jobs.
# Private socket directory, with explicit cleanup even on a failed production.
if nature_only:
    print("AURALUNA STAGE: mixing nature and encoding audio",flush=True)
    subprocess.run(command(r,12),check=True)
elif fast:
    print("AURALUNA STAGE: fast tonal composition and acoustic rendering",flush=True)
    for _ in range(1000):
        subprocess.run(command(r,12),check=True)
        if all((job/f"variation_{i}"/"completed.json").exists() for i in range(1,r["variations"]+1)):break
    else:raise RuntimeError("Production did not finish within batch limit")
else:
    with tempfile.TemporaryDirectory(prefix="auraluna-aria-",dir="/tmp") as service_dir:
        socket_path=str(Path(service_dir)/"inference.sock")
        env=dict(os.environ,AURALUNA_ARIA_SOCKET=socket_path)
        with (root/"logs/aria-service.log").open("a") as service_log:
            service=subprocess.Popen(
                ["/tmp/aria-env/bin/python",str(engine/"compose_preview.py"),"--serve-aria",socket_path,str(root/"models/model.safetensors")],
                stdout=service_log,stderr=subprocess.STDOUT)
            try:
                print("AURALUNA STAGE: composing and arranging",flush=True)
                # Run bounded batches inside this single remote notebook.
                for _ in range(1000):
                    if service.poll() is not None:raise RuntimeError("Aria service exited; inspect diagnostic log below")
                    subprocess.run(command(r,12),check=True,env=env)
                    job=root/"jobs"/r["job"]
                    if all((job/f"variation_{i}"/"completed.json").exists() for i in range(1,r["variations"]+1)):break
                else:raise RuntimeError("Production did not finish within batch limit")
            finally:
                if service.poll() is None:service.terminate()
                try:service.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    service.kill()
                    service.wait()
                # Show useful performance timings and final diagnostic context in Kaggle logs.
                service_log.flush()
                with (root/"logs/aria-service.log").open() as log:
                    from collections import deque
                    recent=deque(maxlen=60)
                    for line in log:
                        recent.append(line)
                        if line.startswith("PERF ") or line.startswith("Aria inference service ready"):print(line.strip(),flush=True)
                    if sys.exc_info()[0] is not None:
                        print("Aria diagnostic log tail:",flush=True)
                        for line in recent:print(line.rstrip(),flush=True)
                        for logpath in sorted(job.glob("variation_*/*.log")):
                            with logpath.open(errors="replace") as details:
                                print(str(logpath.name),flush=True)
                                for line in deque(details,maxlen=30):print(line.rstrip(),flush=True)
output=Path("/kaggle/working/results")
output.mkdir(exist_ok=True)
for i in range(1,r["variations"]+1):
    source=job/f"variation_{i}"
    for name in ("music."+r["format"],"licences.json","completed.json"):
        if not (source/name).is_file():raise RuntimeError("Missing production output: "+name)
        shutil.copy2(source/name,output/f"variation_{i}_{name}")
print(f"PERF total engine execution: {time.monotonic()-started_job:.1f}s",flush=True)
print("AURALUNA COMPLETE",flush=True)
