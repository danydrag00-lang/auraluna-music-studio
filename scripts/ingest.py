"""Import a manually reviewed local WAV file; never infer licensing."""
import argparse, hashlib, json, pathlib, shutil, wave, datetime
p=argparse.ArgumentParser()
p.add_argument('file',type=pathlib.Path)
for k in ['title','creator','source','evidence','instrument']:p.add_argument('--'+k,required=True)
p.add_argument('--license',choices=['CC0-1.0','CC-BY-4.0'],required=True)
p.add_argument('--kind',choices=['note','nature'],required=True)
p.add_argument('--pitch',type=int)
p.add_argument('--reviewed',action='store_true',required=True)
a=p.parse_args()
if a.kind=='note' and (a.pitch is None or not 0<=a.pitch<=127):p.error('Valid MIDI pitch required')
if not a.source.startswith('https://') or not a.evidence.strip():p.error('Source and license evidence required')
root=pathlib.Path(__file__).resolve().parents[1]
index=root/'catalog/index.json'; data=json.loads(index.read_text())
digest=hashlib.sha256(a.file.read_bytes()).hexdigest()
if any(x['id']==digest for x in data):p.error('Duplicate audio')
with wave.open(str(a.file),'rb') as w:
 rate=w.getframerate(); frames=w.getnframes(); channels=w.getnchannels(); bits=w.getsampwidth()*8
 raw=w.readframes(frames)
 if not frames or rate<22050 or channels not in (1,2) or bits not in (16,24,32) or not any(raw):p.error('Unsuitable PCM recording')
target=root/'audio'/ (digest+'.wav');target.parent.mkdir(exist_ok=True);shutil.copyfile(a.file,target)
license_url={'CC0-1.0':'https://creativecommons.org/publicdomain/zero/1.0/','CC-BY-4.0':'https://creativecommons.org/licenses/by/4.0/'}[a.license]
data.append(dict(id=digest,title=a.title,creator=a.creator,source=a.source,evidence=a.evidence,instrument=a.instrument,license=a.license,license_url=license_url,reviewed=True,kind=a.kind,pitch=a.pitch,path='audio/'+target.name,duration=frames/rate,sample_rate=rate,channels=channels,bit_depth=bits,verified_date=str(datetime.date.today())))
tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(index)
print('Imported',digest)
