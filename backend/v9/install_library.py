"""Restore acoustic assets independently of the Aria environment."""
import os, json, shutil, subprocess, tempfile, tarfile
from pathlib import Path
from urllib.parse import urljoin
import requests
import py7zr
import soundfile as sf
from bs4 import BeautifulSoup
from huggingface_hub import snapshot_download

ROOT=Path(os.environ.get("AURALUNA_ROOT","/kaggle/working/Auraluna-V9"))
for d in ("instruments","nature","licenses","logs"):
    (ROOT/d).mkdir(parents=True,exist_ok=True)
session=requests.Session()
session.headers["User-Agent"]="AuralunaMusicStudio/9.0 (personal acoustic library)"
status={}
def save(name,record):
    (ROOT/"licenses"/(name+".json")).write_text(json.dumps(record,indent=2))
def fetch(url,path):
    with session.get(url,stream=True,timeout=(30,180)) as r:
        r.raise_for_status()
        with path.open("wb") as f:
            for chunk in r.iter_content(1024*1024): f.write(chunk)
def font(name,url,source,creator,license):
    folder=ROOT/"instruments"/name
    folder.mkdir(parents=True,exist_ok=True)
    if not list(folder.rglob("*.sf2")):
        with tempfile.TemporaryDirectory() as tmp:
            archive=Path(tmp)/"download"
            fetch(url,archive)
            if py7zr.is_7zfile(archive):
                with py7zr.SevenZipFile(archive) as z: z.extractall(folder)
            elif tarfile.is_tarfile(archive):
                with tarfile.open(archive) as t: t.extractall(folder,filter="data")
            else: raise RuntimeError("Invalid archive")
    assert list(folder.rglob("*.sf2"))
    save(name,dict(creator=creator,license=license,source=source,commercial_use=True,attribution_required=license.startswith("CC BY")))
def grand():
    font("grand_piano","https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPiano-SF2-V3%2B20200602.tar.xz","https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html","Alexander Holm","CC BY 3.0")
def harp():
    page="https://freepats.zenvoid.org/OrchestralStrings/harp.html"
    if list((ROOT/"instruments/harp").rglob("*.sf2")): url=page
    else:
        r=session.get(page,timeout=60); r.raise_for_status()
        soup=BeautifulSoup(r.text,"html.parser")
        urls=[urljoin(page,a["href"]) for row in soup.select("tr") if "SF2" in row.get_text() for a in row.find_all("a",href=True) if a["href"].lower().endswith((".7z",".tar.xz",".tar.gz",".tgz"))]
        if not urls: raise RuntimeError("No SF2 archive found")
        url=urls[0]
    font("harp",url,page,"FreePats / Versilian Studios","CC0-1.0")
def handpan():
    font("handpan","https://github.com/freepats/hang-D-minor/releases/download/2022-03-30/Hang-D-minor-SF2-20220330.7z","https://freepats.zenvoid.org/ChromaticPercussion/hang.html","FreePats Hang D minor contributors","CC0-1.0")
def felt():
    folder=ROOT/"instruments/felt_piano"
    if len(list(folder.rglob("*.wav")))<264 or not list(folder.rglob("*.sfz")):
        snapshot_download(repo_id="cueharbor/starter-instruments",repo_type="dataset",allow_patterns=["felt-piano/*","felt-piano/**/*"],local_dir=str(folder))
    assert len(list(folder.rglob("*.wav")))>=264 and list(folder.rglob("*.sfz"))
    save("felt_piano",dict(creator="Tom Guder",license="Public domain",source="https://huggingface.co/datasets/cueharbor/starter-instruments",commercial_use=True))
def orchestra():
    folders={"flute":("Woodwinds/Flute",94),"cello":("Strings/Cello Section",156)}
    missing={k:v[0] for k,v in folders.items() if len(list((ROOT/"instruments"/k).rglob("*.wav")))<v[1]}
    if missing:
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)/"vsco"
            subprocess.run(["git","clone","--depth","1","--filter=blob:none","--sparse","https://github.com/sgossner/VSCO-2-CE.git",str(repo)],check=True)
            subprocess.run(["git","-C",str(repo),"sparse-checkout","set",*missing.values()],check=True)
            for k,v in missing.items(): shutil.copytree(repo/v,ROOT/"instruments"/k,dirs_exist_ok=True)
    for k,(_,count) in folders.items():
        assert len(list((ROOT/"instruments"/k).rglob("*.wav")))>=count
        save(k,dict(creator="Versilian Studios LLC",license="CC0-1.0",source="https://github.com/sgossner/VSCO-2-CE",commercial_use=True))
def report():
    (ROOT/"library-status.json").write_text(json.dumps(status,indent=2))
for name,fn in [("grand_piano",grand),("felt_piano",felt),("harp",harp),("handpan",handpan),("flute_cello",orchestra)]:
    try: fn(); status[name]="ready"
    except Exception as e: status[name]=str(e)
    report()
sources={"instruments/bansuri":"Bansuri sample E bass.ogg","instruments/singing_bowls":"SingingBowl2.ogg","nature/rain":"Light Rain Distant Thunder July 5th 2016.wav","nature/river":"Swale.ogg","nature/ocean":"Ocean Waves on a Tropical Beach.ogg","nature/forest":"Walk in the rainforest.ogg"}
for category,title in sources.items():
    folder=ROOT/category
    folder.mkdir(parents=True,exist_ok=True)
    name=Path(title).stem
    dest=folder/(name+".wav")
    try:
        if dest.exists() and (ROOT/"licenses"/(name+".json")).exists() and sf.info(dest).frames>0:
            status[category]="ready"; report(); continue
        r=session.get("https://commons.wikimedia.org/w/api.php",params={"action":"query","titles":"File:"+title,"prop":"imageinfo","iiprop":"url|extmetadata","format":"json"},timeout=60)
        r.raise_for_status()
        info=next(iter(r.json()["query"]["pages"].values()))["imageinfo"][0]
        m=info["extmetadata"]
        license=m.get("LicenseShortName",{}).get("value","")
        if not (license in ("CC0","CC0 1.0","Public domain") or license.startswith("CC BY ")):
            raise ValueError("Licence review required: "+license)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/title; converted=Path(tmp)/"converted.wav"
            fetch(info["url"],raw)
            subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(raw),"-vn","-ar","48000","-c:a","pcm_s24le",str(converted)],check=True)
            assert sf.info(converted).frames>0
            shutil.copy2(converted,dest)
        save(name,dict(category=category,file=str(dest.relative_to(ROOT)),creator=BeautifulSoup(m.get("Artist",{}).get("value",""),"html.parser").get_text(" ",strip=True),license=license,license_url=m.get("LicenseUrl",{}).get("value",""),source=info["descriptionurl"],commercial_use=True,modifications="Converted to 48 kHz PCM WAV"))
        status[category]="ready"
    except requests.HTTPError as e:
        status[category]=str(e)
        if e.response is not None and e.response.status_code==429:
            status[category]="Rate limited; retry after "+e.response.headers.get("Retry-After","server cooldown")
            report(); break
    except Exception as e: status[category]=str(e)
    report()
print(json.dumps(status,indent=2))
