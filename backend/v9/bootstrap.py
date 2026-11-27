"""Run on Kaggle: python bootstrap.py. No credentials required for setup."""
import os
import sys
import subprocess
import shutil
import importlib.util
import time
from pathlib import Path
import urllib.request

ROOT = Path(os.environ.get("AURALUNA_ROOT", "/kaggle/working/Auraluna-V9"))
ENV = Path("/tmp/aria-env")
REPO = Path("/tmp/aria")
for name in ("engine","instruments","nature","models","licenses","presets","seeds","productions","checkpoints","logs"):
    (ROOT/name).mkdir(parents=True, exist_ok=True)

def run(cmd):
    started=time.monotonic()
    try:
        with (ROOT/"logs/setup.log").open("a") as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
    finally:
        print(f"PERF setup {Path(cmd[0]).name} {cmd[1]}: {time.monotonic()-started:.1f}s",flush=True)

if not (ROOT/"setup-complete").exists():
    missing_tools=[name for name in ("fluidsynth","ffmpeg") if not shutil.which(name)]
    if missing_tools:
        run(["apt-get","update","-qq"])
        run(["apt-get","install","-y","-qq",*missing_tools])
    packages={"pretty_midi":"pretty_midi","fluidsynth":"pyfluidsynth","soundfile":"soundfile","scipy":"scipy","requests":"requests","bs4":"beautifulsoup4","huggingface_hub":"huggingface_hub","py7zr":"py7zr"}
    missing=[pkg for module,pkg in packages.items() if importlib.util.find_spec(module) is None]
    if not shutil.which("uv"):missing.append("uv")
    if missing:run([sys.executable,"-m","pip","install","-q",*missing])
    print("PERF reused preinstalled tools and packages where available",flush=True)
    (ROOT/"setup-complete").touch()
if "--acoustic-only" in sys.argv:
    print("Acoustic rendering tools ready; skipping Aria setup.",flush=True)
    raise SystemExit(0)
if not (REPO/".git").exists():
    run(["git","clone","--depth","1","https://github.com/EleutherAI/aria.git",str(REPO)])
if not (ENV/"bin/aria").exists():
    run(["uv","python","install","3.12"])
    run(["uv","venv",str(ENV),"--python","3.12"])
    run(["uv","pip","install","--python",str(ENV/"bin/python"),"-e",str(REPO)+"[all]"])
model=ROOT/"models/model.safetensors"
if not model.exists():
    part=model.with_suffix(".part")
    urllib.request.urlretrieve("https://huggingface.co/loubb/aria-medium-base/resolve/main/model-gen.safetensors",str(part))
    os.replace(part,model)
print("Aria environment and model present. See logs/setup.log for installation details.")
print("Instrument restoration is a separate step.")
