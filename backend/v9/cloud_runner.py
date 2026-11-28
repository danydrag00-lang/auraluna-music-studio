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
raw=json.loads(a.request.read_text())
r=normalize(raw)
regen=raw.get("regenerate")
regen_score=None
if regen is not None:
    import re
    allowed={"felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls"}
    if not isinstance(regen,dict) or not re.fullmatch(r"auraluna-[a-f0-9]{32}",str(regen.get("slug",""))) or type(regen.get("variation")) is not int or regen["variation"] not in (1,2,3) or regen.get("instrument") not in allowed or r["instruments"]!=[regen["instrument"]] or r["format"]!="flac" or r["variations"]!=1 or r["seconds"]>60 or r["tuning"]!="standard" or r["nature_layers"] or raw.get("extension") is not None:
        raise ValueError("Invalid individual instrument regeneration request")
    prefix=f"variation_{regen['variation']}_"
    matches=[p for p in Path("/kaggle/input").rglob(prefix+"score.mid") if regen["slug"] in p.parts and p.is_file()]
    if len(matches)!=1:raise RuntimeError("Original score unavailable; generate a new short production first")
    regen_score=matches[0]
    original_report=json.loads(regen_score.with_name(prefix+"completed.json").read_text())
    original_licences=json.loads(regen_score.with_name(prefix+"licences.json").read_text())
    if original_report.get("seconds")!=r["seconds"] or original_report.get("quality",{}).get("status") not in ("technical_checks_passed","stem_regeneration_verified"):raise RuntimeError("Original score duration or validation mismatch")
    originals={name:regen_score.with_name(prefix+"stem_"+name+".flac") for name in allowed}
    originals={k:v for k,v in originals.items() if v.is_file()}
    if regen["instrument"] not in originals:raise RuntimeError("Selected original stem missing")
    r["engine"]="fast"
extension=raw.get("extension")
extension_source=None
if extension is not None:
    import re
    if not isinstance(extension,dict) or not re.fullmatch(r"auraluna-[a-f0-9]{32}",str(extension.get("slug",""))) or type(extension.get("variation")) is not int or extension["variation"] not in (1,2,3) or extension.get("format") not in ("wav","flac") or r["format"]!="flac" or r["variations"]!=1 or not 75<=r["seconds"]<=900:
        raise ValueError("Invalid lossless preview extension")
    prefix=f"variation_{extension['variation']}_"
    candidates=[p for p in Path("/kaggle/input").rglob(prefix+"music."+extension["format"]) if extension["slug"] in p.parts and p.is_file()]
    if len(candidates)!=1:raise RuntimeError("Expected exactly one attached preview output; check source notebook permissions and retention")
    extension_source=candidates[0]
    preview_report=json.loads(extension_source.with_name(prefix+"completed.json").read_text())
    preview_licences=json.loads(extension_source.with_name(prefix+"licences.json").read_text())
    if preview_report.get("seconds")!=60 or preview_report.get("sample_rate")!=48000 or preview_report.get("quality",{}).get("status")!="technical_checks_passed":raise RuntimeError("Source must be a validated 60-second preview")
    requested_total=r["seconds"]
    r["seconds"]-=60
    # A new identity prevents restarting the identical opening motif.
    if r["seed"]:r["seed"]=(r["seed"][:35]+"Continuation")
    print("EXTENSION: preserving the source audio; generating",r["seconds"],"new seconds",flush=True)

nature_only=not r["instruments"]
fast=r["engine"] in ("fast","studio")
started_job=time.monotonic()
print("AURALUNA STAGE: restoring acoustic assets",flush=True)
inputs=Path("/kaggle/input")
# Restore only assets needed by this request. Keep all attribution records.
woodwinds=set(r["instruments"])&{"clarinet","oboe","bassoon"}
categories=["licenses"]
if r["instruments"]:categories.extend("instruments/"+name for name in r["instruments"] if name not in woodwinds)
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
        if woodwinds and name in ("instruments","licenses"):
            target.mkdir(parents=True,exist_ok=True)
            if (source/name).exists():
                for child in (source/name).iterdir():(target/child.name).symlink_to(child,target_is_directory=child.is_dir())
        elif (source/name).exists():target.symlink_to(source/name,target_is_directory=True)
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
if woodwinds:
    from woodwind_bank import install
    install(root,woodwinds)
print(f"PERF total bootstrap: {time.monotonic()-started:.1f}s",flush=True)
print("Starting",r["job"],flush=True)
job=root/"jobs"/r["job"]
# Keep one model process alive across all production batches, not across users or jobs.
# Private socket directory, with explicit cleanup even on a failed production.
if regen_score is not None:
    import numpy as np
    import soundfile as sf
    import hashlib
    folder=job/"variation_1"
    folder.mkdir(parents=True,exist_ok=True)
    midi=folder/"section_0000.mid"
    shutil.copy2(regen_score,midi)
    target=regen["instrument"]
    mood={"deep_sleep":"deep_sleep","peaceful_piano":"deep_sleep","luxury_spa":"luxury_spa"}.get(r["preset"],"meditation")
    env=dict(os.environ,AURALUNA_STEMS="1",AURALUNA_PERFORMANCE_SEED=str(int.from_bytes(os.urandom(8),"big")),AURALUNA_REGENERATE="1")
    subprocess.run([sys.executable,str(engine/"arrange.py"),"--root",str(root),"--midi",str(midi),"--mood",mood,"--seconds",str(r["seconds"]),"--instruments",target,"--nature","none","--section","--gains",json.dumps(r["gains"])],env=env,check=True)
    new=folder/"ensemble"/("stem_"+target+".flac")
    frames=r["seconds"]*48000
    def validate_stem(p):
        info=sf.info(p)
        if info.frames!=frames or info.samplerate!=48000 or info.channels!=2 or info.subtype!="PCM_24":raise RuntimeError("Invalid stem: "+p.name)
    def digest(p):
        h=hashlib.sha256()
        with p.open("rb") as reader:
            for block in iter(lambda:reader.read(1024*1024),b""):h.update(block)
        return h.hexdigest()
    for name,src in originals.items():
        dst=folder/("stem_"+name+".flac")
        validate_stem(new if name==target else src)
        shutil.copy2(new if name==target else src,dst)
        if name!=target and digest(src)!=digest(dst):raise RuntimeError("Preserved stem changed")
    if digest(new)==digest(originals[target]):raise RuntimeError("Regeneration produced identical stem; retry")
    # Conservative dry audition mix. Original mastered production remains untouched.
    mix=np.zeros((frames,2),np.float32)
    for stem in sorted(folder.glob("stem_*.flac")):
        samples,_=sf.read(stem,dtype="float32",always_2d=True)
        if not np.isfinite(samples).all():raise RuntimeError("Invalid stem samples")
        mix+=samples
    peak=float(np.max(np.abs(mix)))
    if peak<1e-5:raise RuntimeError("Silent regenerated mix")
    mix*=min(1.,10**(-3/20)/peak)
    sf.write(folder/"music.flac",mix,48000,subtype="PCM_24")
    (folder/"licences.json").write_text(json.dumps(original_licences,indent=2))
    (folder/"completed.json").write_text(json.dumps({"engine":"stem_regeneration","seconds":r["seconds"],"sample_rate":48000,"file":"music.flac","quality":{"status":"stem_regeneration_verified","decoded_seconds":r["seconds"],"sample_rate":48000,"channels":2,"warnings":["Dry audition mix; nature, shared room effects and original mastering are not included."]},"regeneration":{"instrument":target,"source_slug":regen["slug"],"source_variation":regen["variation"],"preserved_stems":sorted(k for k in originals if k!=target),"unchanged_stems_sha256_verified":True}},indent=2))
elif nature_only:
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
if extension_source is not None:
    import soundfile as sf
    import numpy as np
    source=job/"variation_1"
    continuation=source/"music.flac"
    joined=source/"extended.part.flac"
    # Copy the decoded original PCM24 samples exactly; no gain, crossfade
    # or EQ is applied to the approved prefix. Join at the mastered fade.
    for audio,seconds in [(extension_source,60),(continuation,r["seconds"])]:
        info=sf.info(audio)
        if info.samplerate!=48000 or info.channels!=2 or info.frames!=seconds*48000 or info.subtype!="PCM_24":
            raise RuntimeError("Extension requires exact 48 kHz stereo PCM24 input")
    if shutil.disk_usage(source).free<requested_total*288000+128*1024**2:raise RuntimeError("Not enough space for lossless extension")
    with sf.SoundFile(joined,"w",samplerate=48000,channels=2,format="FLAC",subtype="PCM_24") as writer:
        for audio in (extension_source,continuation):
            with sf.SoundFile(audio) as reader:
                for block in reader.blocks(blocksize=48000,dtype="int32",always_2d=True):writer.write(block)
    # Verify the prefix bit for bit after decoding, and the full duration.
    with sf.SoundFile(extension_source) as original,sf.SoundFile(joined) as result:
        if result.frames!=requested_total*48000:raise RuntimeError("Incorrect extended duration")
        for block in original.blocks(blocksize=48000,dtype="int32",always_2d=True):
            if not np.array_equal(block,result.read(len(block),dtype="int32",always_2d=True)):raise RuntimeError("Preview PCM changed")
    report=json.loads((source/"completed.json").read_text())
    report["continuation_quality"]=report.pop("quality")
    report["quality"]={"status":"extension_pcm_verified","sample_rate":48000,"channels":2,"decoded_seconds":requested_total,"warnings":["Original preview and continuation each retain their own mastering and fades. Join may have a quiet transition. Full joined loudness has not been measured."]}
    report["seconds"]=requested_total
    report["extension"]={"source_slug":extension["slug"],"source_variation":extension["variation"],"preserved_seconds":60,"pcm_prefix_verified":True,"join":"lossless concatenation at existing fades"}
    licences=json.loads((source/"licences.json").read_text())
    for record in preview_licences:
        if record not in licences:licences.append(record)
    os.replace(joined,continuation)
    (source/"licences.json").write_text(json.dumps(licences,indent=2))
    (source/"completed.json").write_text(json.dumps(report,indent=2))
output=Path("/kaggle/working/results")
output.mkdir(exist_ok=True)
for i in range(1,r["variations"]+1):
    source=job/f"variation_{i}"
    for name in ("music."+r["format"],"licences.json","completed.json"):
        if not (source/name).is_file():raise RuntimeError("Missing production output: "+name)
        shutil.copy2(source/name,output/f"variation_{i}_{name}")
    if extension_source is None:
        for stem in source.glob("stem_*.flac"):
            shutil.copy2(stem,output/f"variation_{i}_{stem.name}")
        if any(source.glob("stem_*.flac")) and (source/"section_0000.mid").is_file():
            shutil.copy2(source/"section_0000.mid",output/f"variation_{i}_score.mid")
print(f"PERF total engine execution: {time.monotonic()-started_job:.1f}s",flush=True)
print("AURALUNA COMPLETE",flush=True)
