"""Convert a JSON job request into a safe V9 production command.
Rule-based prompt interpretation, no remote service or paid API.
"""
import argparse,json,math,re,sys,subprocess
from pathlib import Path

PRESETS={
"luxury_spa":(["felt_piano","flute","cello","harp"],"river"),
"deep_sleep":(["felt_piano","cello"],"rain"),
"meditation":(["flute","harp"],"ocean"),
"study_focus":(["grand_piano","harp"],"forest"),
"emotional_relaxation":(["felt_piano","cello"],"ocean"),
"peaceful_piano":(["felt_piano"],"none"),
"yoga_zen":(["handpan","singing_bowls"],"forest"),
"indian_meditation":(["bansuri","singing_bowls"],"river"),
"rain_sleep":([],"rain"),"ocean_sleep":([],"ocean"),
"forest_relaxation":([],"forest"),"river_relaxation":([],"river")}
ALIASES={"felt_piano":r"felt piano|soft piano","grand_piano":r"grand piano|acoustic piano","flute":r"\bflute\b","cello":r"\bcello\b","harp":r"\bharp\b","handpan":r"\bhandpan\b","bansuri":r"\bbansuri\b|bamboo flute","singing_bowls":r"singing bowls?|tibetan bowls?"}
NATURE={"rain","river","ocean","forest","none"}
def normalize(r):
    if not isinstance(r,dict):raise ValueError("Expected JSON object")
    prompt=r.get("prompt","")
    if not isinstance(prompt,str) or len(prompt)>2000:raise ValueError("Prompt must be text up to 2000 characters")
    t=prompt.lower()
    preset=r.get("preset")
    if not preset:
        rules=[("indian_meditation",r"bansuri|indian|bamboo flute"),("yoga_zen",r"handpan|yoga|zen"),("deep_sleep",r"sleep|insomnia"),("study_focus",r"study|focus|concentration"),("emotional_relaxation",r"emotional|romantic"),("luxury_spa",r"spa|massage"),("meditation",r"meditat"),("peaceful_piano",r"piano")]
        preset=next((k for k,pat in rules if re.search(pat,t)),"luxury_spa")
    if preset not in PRESETS:raise ValueError("Unknown preset")
    default,ambient=PRESETS[preset]
    mentioned=[k for k,pat in ALIASES.items() if re.search(pat,t)]
    if "bansuri" in mentioned and "bamboo flute" in t:mentioned=[k for k in mentioned if k!="flute"]
    if "piano" in t and not any(k.endswith("piano") for k in mentioned):mentioned.append("felt_piano")
    # Explicit structured selections override prompt inference.
    instruments=r.get("instruments",mentioned or default)
    if "nature only" in t or "no music" in t or "no instruments" in t:
        if "instruments" not in r:instruments=[]
    if not isinstance(instruments,list) or any(not isinstance(k,str) or k not in ALIASES for k in instruments) or len(set(instruments))!=len(instruments):raise ValueError("Invalid instrument list")
    nature=r.get("nature")
    if nature is None:
        nature=next((k for k in ("rain","river","ocean","forest") if re.search(r"\b"+k+r"\b",t)),ambient)
        if re.search(r"no (nature|ambience|ambient sounds)|without (nature|ambience|rain|river|ocean|forest)",t):nature="none"
    if nature not in NATURE:raise ValueError("Invalid nature source")
    layers=r.get("nature_layers",{nature:0} if nature!="none" else {})
    if not isinstance(layers,dict) or any(k not in NATURE-{"none"} or type(v) not in (int,float) or not math.isfinite(v) or not -30<=v<=6 for k,v in layers.items()):raise ValueError("Invalid nature mixer")
    nature=next(iter(layers),"none")
    if not instruments and not layers:raise ValueError("Select a valid sound source")
    seconds=r.get("seconds")
    if seconds is None:
        m=re.search(r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b",t)
        words={"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,"twelve":12}
        seconds=round((words[m[1]] if m[1] in words else float(m[1]))*(3600 if m[2].startswith("h") else 60 if m[2].startswith("m") else 1)) if m else 120
    def integer(k,v,lo,hi):
        if type(v)!=int or not lo<=v<=hi:raise ValueError(f"{k} must be an integer {lo}–{hi}")
        return v
    seconds=integer("seconds",seconds,15,43200)
    variations=integer("variations",r.get("variations",1),1,3)
    fmt=r.get("format","mp3")
    if fmt not in ("mp3","flac","wav"):raise ValueError("Invalid format")
    job=r.get("job")
    if not isinstance(job,str) or not re.fullmatch(r"[A-Za-z0-9]{1,48}",job):raise ValueError("Job ID must be 1–48 ASCII letters or digits")
    gains=r.get("gains",{})
    if not isinstance(gains,dict) or any(k not in instruments or type(v) not in (int,float) or not math.isfinite(v) or not -60<=v<=12 for k,v in gains.items()):raise ValueError("Invalid gain offsets")
    engine=r.get("engine","aria")
    if engine not in ("aria","fast"):raise ValueError("Invalid composition engine")
    composition=r.get("composition","independent")
    if composition not in ("independent","thematic"):raise ValueError("Invalid composition style")
    return dict(composition=composition,engine=engine,preset=preset,instruments=instruments,nature=nature,nature_layers=layers,seconds=seconds,variations=variations,format=fmt,job=job,gains=gains)
def command(r,budget):
    return [sys.executable,str(Path(__file__).with_name("produce.py")),"--preset",r["preset"],"--instruments",",".join(r["instruments"]),"--nature",r["nature"],"--nature-layers",json.dumps(r["nature_layers"],separators=(",",":")),"--seconds",str(r["seconds"]),"--variations",str(r["variations"]),"--format",r["format"],"--job",r["job"],"--gains",json.dumps(r["gains"],separators=(",",":")),"--max-sections",str(budget),"--engine",r.get("engine","aria"),"--composition",r.get("composition","independent")]
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("request",type=Path)
    p.add_argument("--run",action="store_true")
    p.add_argument("--max-sections",type=int,default=3)
    a=p.parse_args()
    if not 1<=a.max_sections<=100:p.error("Section budget must be 1–100")
    r=normalize(json.loads(a.request.read_text()))
    print(json.dumps(r,indent=2),flush=True)
    if a.run:subprocess.run(command(r,a.max_sections),check=True)
