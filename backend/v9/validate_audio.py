"""Streaming quality audit for a decoded production. Does not substitute for listening."""
import argparse, json, math, subprocess
from pathlib import Path
import numpy as np

def inspect(path, expected=None):
    meta=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","a:0","-show_streams","-of","json",str(path)]))
    stream=meta["streams"][0]
    rate=int(stream["sample_rate"]);channels=int(stream["channels"])
    if channels!=2 or rate!=48000:raise ValueError("Expected native stereo 48 kHz")
    proc=subprocess.Popen(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(path),"-map","0:a:0","-f","f32le","-acodec","pcm_f32le","-"],stdout=subprocess.PIPE)
    frames=0;peak=0.;energy=0.;clipped=0;quiet=0;longest=0
    try:
        while True:
            raw=proc.stdout.read(rate*channels*4)
            if not raw:break
            x=np.frombuffer(raw,dtype="<f4").reshape(-1,channels).astype(np.float64)
            if not np.isfinite(x).all():raise ValueError("Non-finite audio")
            frames+=len(x);peak=max(peak,float(np.abs(x).max()));energy+=float(np.sum(x*x))
            clipped+=int(np.sum(np.abs(x)>=1))
            if np.sqrt(np.mean(x*x))<.0001:quiet+=len(x)
            else:quiet=0
            longest=max(longest,quiet)
        if proc.wait()!=0:raise RuntimeError("Audio decode failed")
    finally:
        if proc.poll() is None:proc.kill();proc.wait()
        proc.stdout.close()
    if not frames:raise ValueError("Empty audio")
    duration=frames/rate;rms=math.sqrt(energy/(frames*channels))
    db=lambda x:20*math.log10(max(x,1e-12))
    issues=[]
    if expected is not None and abs(duration-expected)>.2:issues.append("Duration mismatch")
    if clipped:issues.append("Decoded full-scale samples")
    if rms<.0005:issues.append("Very low overall audio level")
    if longest/rate>30:issues.append("More than 30 seconds near silence")
    # EBU R128 measures integrated loudness and true peak, including codec overshoot.
    p=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",str(path),"-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True,check=True)
    import re
    summary=p.stderr.rsplit("Summary:",1)[-1]
    loudness=re.findall(r"I:\s*(-?[\d.]+)\s*LUFS",summary)
    tp=re.findall(r"Peak:\s*(-?[\d.]+)\s*dBFS",summary)
    integrated=float(loudness[-1]) if loudness else None
    true_peak=float(tp[-1]) if tp else None
    if true_peak is None:issues.append("True peak unavailable")
    elif true_peak>0:issues.append("True peak above full scale")
    return dict(seconds=duration,sample_rate=rate,channels=channels,codec=stream["codec_name"],rms_dbfs=db(rms),sample_peak_dbfs=db(peak),integrated_lufs=integrated,true_peak_dbtp=true_peak,clipped_samples=clipped,longest_near_silence_seconds=longest/rate,issues=issues,technical_pass=not issues,listening_review="pending")
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("audio",type=Path);p.add_argument("--seconds",type=float);p.add_argument("--report",type=Path,required=True);a=p.parse_args()
    report=inspect(a.audio,a.seconds);a.report.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(not report["technical_pass"])
