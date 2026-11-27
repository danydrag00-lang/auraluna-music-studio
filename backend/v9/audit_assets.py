"""Audit candidate acoustic recordings before adding them to the private asset dataset.
No downloads, licence inference, or publication: a human must verify source evidence.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path
from urllib.parse import urlsplit

ALLOWED={"CC0-1.0","CC-BY-4.0","CC-BY-3.0"}
CATEGORIES={"felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls","rain","river","ocean","forest"}
def audit(root, records):
    accepted=[]; rejected=[]; seen=set()
    root=root.resolve()
    for i,record in enumerate(records):
        try:
            if not isinstance(record,dict):raise ValueError("Expected object")
            for field in ("path","title","creator","source_url","license","license_url","evidence","reviewed_by","reviewed_on","category"):
                if not isinstance(record.get(field),str) or not record[field].strip():raise ValueError("Missing "+field)
            if record["license"] not in ALLOWED:raise ValueError("Licence requires separate review")
            if record["category"] not in CATEGORIES:raise ValueError("Unknown acoustic category")
            for field in ("source_url","license_url"):
                u=urlsplit(record[field])
                if u.scheme!="https" or not u.hostname or u.username or u.password:raise ValueError("Invalid source URL")
            from datetime import date
            date.fromisoformat(record["reviewed_on"])
            expected={"CC0-1.0":"/publicdomain/zero/1.0/","CC-BY-4.0":"/licenses/by/4.0/","CC-BY-3.0":"/licenses/by/3.0/"}[record["license"]]
            u=urlsplit(record["license_url"])
            if u.hostname!="creativecommons.org" or not u.path.startswith(expected):raise ValueError("Licence URL mismatch")
            path=(root/record["path"]).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in (".wav",".flac"):raise ValueError("Missing or unsupported recording")
            h=hashlib.sha256()
            with path.open("rb") as f:
                for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
            digest=h.hexdigest()
            if digest in seen:raise ValueError("Duplicate recording SHA256")
            if record.get("sha256") and record["sha256"]!=digest:raise ValueError("Recording checksum mismatch")
            import soundfile as sf
            info=sf.info(path)
            if info.frames<=0 or info.channels not in (1,2) or info.samplerate<22050:raise ValueError("Unsupported audio properties")
            seen.add(digest)
            accepted.append({**record,"sha256":digest,"seconds":info.duration,"sample_rate":info.samplerate,"channels":info.channels,"subtype":info.subtype})
        except Exception as e:rejected.append({"index":i,"reason":str(e)})
    return {"accepted_count":len(accepted),"rejected_count":len(rejected),"accepted":accepted,"rejected":rejected,"scope":"Metadata, declared licence evidence, file integrity and exact duplicate checks only; not independent legal clearance."}
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("root",type=Path)
    p.add_argument("manifest",type=Path)
    p.add_argument("report",type=Path)
    a=p.parse_args()
    records=json.loads(a.manifest.read_text())
    if not isinstance(records,list):raise ValueError("Manifest must be a JSON array")
    report=audit(a.root,records)
    a.report.write_text(json.dumps(report,indent=2))
    print(report["accepted_count"],"accepted;",report["rejected_count"],"rejected")
    sys.exit(bool(report["rejected_count"]))
