"""Run on Kaggle: python bootstrap.py. No credentials required for setup."""
import os
import sys
import subprocess
from pathlib import Path
import urllib.request

ROOT = Path(os.environ.get("AURALUNA_ROOT", "/kaggle/working/Auraluna-V9"))
ENV = Path("/tmp/aria-env")
REPO = Path("/tmp/aria")
for name in ("engine","instruments","nature","models","licenses","presets","seeds","productions","checkpoints","logs"):
    (ROOT/name).mkdir(parents=True, exist_ok=True)

def run(cmd):
    with (ROOT/"logs/setup.log").open("a") as log:
        subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)

if not (ROOT/"setup-complete").exists():
    run(["apt-get","update","-qq"])
    run(["apt-get","install","-y","-qq","fluidsynth","ffmpeg"])
    run([sys.executable,"-m","pip","install","-q","uv","pretty_midi","pyfluidsynth","soundfile","scipy","requests","beautifulsoup4","huggingface_hub","py7zr"])
    (ROOT/"setup-complete").touch()
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
