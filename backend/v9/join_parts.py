"""Join validated hour exports, with optional bounded-memory smooth transitions."""
import json,re,shutil,subprocess,sys,tempfile
from pathlib import Path


def smooth_filter(count,overlap=12):
    """Pairwise constant-sum crossfades; avoid overshoot on correlated audio."""
    if not 2<=count<=12 or not 1<=overlap<=30:raise ValueError("Invalid transition plan")
    filters=[]
    last="[0:a]"
    for i in range(1,count):
        out=f"[mix{i}]"
        filters.append(f"{last}[{i}:a]acrossfade=d={overlap}:c1=tri:c2=tri{out}")
        last=out
    return ";".join(filters),last

def smooth_join(sources,target,fmt,bitrate,overlap):
    graph,last=smooth_filter(len(sources),overlap)
    args=["ffmpeg","-y","-v","error","-xerror"]
    for p in sources:args+=["-i",str(p)]
    # Decode and encode once; keep the original rate and stereo. Constant-sum
    # fades and a conservative limiter protect overlapping mastered material.
    args+=["-filter_complex",graph+";"+last+"alimiter=limit=0.794328:level=false:latency=true[out]","-map","[out]","-ar","48000","-ac","2","-c:a","aac" if fmt=="m4a" else "libmp3lame","-b:a",bitrate]
    if fmt=="m4a":args+=["-movflags","+faststart"]
    subprocess.run(args+[str(target)],check=True)

def main(request):
    parts=request["parts"];fmt=request["format"];mode=request.get("mode","copy");bitrate=request.get("bitrate","320k" if fmt=="mp3" else "256k");overlap=12
    if mode not in ("copy","smooth") or bitrate not in ("192k","256k","320k") or (fmt=="mp3" and bitrate!="320k") or (fmt=="m4a" and bitrate=="320k"):raise ValueError("Invalid join mode or bitrate")
    if fmt not in ("mp3","m4a") or not isinstance(parts,list) or not 2<=len(parts)<=12 or len(set(parts))!=len(parts) or any(not re.fullmatch(r"auraluna-[a-f0-9]{32}",p) for p in parts):raise ValueError("Invalid join plan")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        subprocess.run(["apt-get","update","-qq"],check=True)
        subprocess.run(["apt-get","install","-y","-qq","ffmpeg"],check=True)
    def probe(path):
        data=json.loads(subprocess.check_output(["ffprobe","-v","error","-select_streams","a:0","-show_streams","-show_format","-of","json",str(path)]))
        s=data["streams"][0]
        return (s["codec_name"],s.get("profile"),s["sample_rate"],s["channels"],s.get("channel_layout")),float(data["format"]["duration"])
    inputs=Path("/kaggle/input")
    output=Path("/kaggle/working/results");output.mkdir(parents=True,exist_ok=True)
    sources=[];licences=[];signature=None;total=0.
    for slug in parts:
        matches=[p for p in inputs.rglob("variation_1_music."+fmt) if slug in p.parts]
        if len(matches)!=1:raise RuntimeError("Missing or ambiguous source output: "+slug)
        p=matches[0]
        report=json.loads(p.with_name("variation_1_completed.json").read_text())
        if report.get("seconds")!=3600 or report.get("quality",{}).get("status")!="technical_checks_passed":raise RuntimeError("Part is not a validated one-hour export: "+slug)
        sig,duration=probe(p)
        if sig[0]!=("mp3" if fmt=="mp3" else "aac") or sig[2:4]!=("48000",2) or abs(duration-3600)>1:raise RuntimeError("Unexpected stream format or duration")
        if signature is not None and sig!=signature:raise RuntimeError("Incompatible audio streams; use the same export settings for every part")
        signature=sig;total+=duration;sources.append(p)
        records=json.loads(p.with_name("variation_1_licences.json").read_text())
        if not isinstance(records,list):raise RuntimeError("Invalid licence records")
        for record in records:
            if record not in licences:licences.append(record)
    if shutil.disk_usage(output).free<sum(p.stat().st_size for p in sources)*1.15+128*1024**2:raise RuntimeError("Insufficient disk space for joined export")
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i,p in enumerate(sources):(root/f"part{i:02}.{fmt}").symlink_to(p)
        manifest=root/"concat.txt";manifest.write_text("".join(f"file part{i:02}.{fmt}\n" for i in range(len(sources))))
        target=output/("joined.part."+fmt)
        if mode=="smooth":smooth_join(sources,target,fmt,bitrate,overlap)
        else:subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","1","-i",str(manifest),"-map","0:a:0","-c:a","copy",*(["-movflags","+faststart"] if fmt=="m4a" else []),str(target)],check=True)
        sig,duration=probe(target)
        expected=len(parts)*3600-(len(parts)-1)*overlap if mode=="smooth" else len(parts)*3600
        if sig[0]!=signature[0] or sig[2:4]!=signature[2:4] or abs(duration-expected)>len(parts)+1:raise RuntimeError("Joined stream validation failed")
        subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(target),"-f","null","-"],check=True)
        target.replace(output/("variation_1_music."+fmt))
    (output/"variation_1_licences.json").write_text(json.dumps(licences,indent=2))
    (output/"variation_1_completed.json").write_text(json.dumps({"engine":"smooth_join" if mode=="smooth" else "packet_join","seconds":expected,"sample_rate":48000,"file":"music."+fmt,"quality":{"status":"joined_decode_verified","decoded_seconds":duration,"sample_rate":48000,"channels":2,"warnings":["12-second overlapping fades reduce total duration; source fades may still cause quiet transitions. One additional lossy encode; no claim of seamlessness until listening review."] if mode=="smooth" else ["Existing fades retained; transitions may be quiet. No new mastering or lossy encode. Duration includes possible codec padding."]},"join":{"parts":parts,"method":"12-second constant-sum crossfade" if mode=="smooth" else "FFmpeg packet copy","overlap_seconds":overlap if mode=="smooth" else 0,"source_duration_seconds":total}},indent=2))
if __name__=="__main__":main(json.loads(Path(sys.argv[1]).read_text()))
