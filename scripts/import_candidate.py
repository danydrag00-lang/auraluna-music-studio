"""Download and convert one explicitly approved candidate to local PCM."""
import argparse, json, pathlib, tempfile, urllib.request, subprocess, sys
from urllib.parse import urlparse
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('source');p.add_argument('--instrument',required=True);p.add_argument('--kind',choices=['note','nature'],required=True);p.add_argument('--pitch',type=int);p.add_argument('--approve-rights-and-audio',action='store_true',required=True)
a=p.parse_args()
rows=json.loads((root/'catalog/candidates.json').read_text())
r=next((x for x in rows if x['source']==a.source),None)
if not r:p.error('Candidate not found')
u=urlparse(r['download'])
if u.scheme!='https' or u.hostname!='upload.wikimedia.org':p.error('Unexpected download host')
if r['license'] not in ('CC0-1.0','CC-BY-4.0'):p.error('Unsupported rights')
if a.kind=='note' and (a.pitch is None or not 0<=a.pitch<=127):p.error('MIDI pitch required')
with tempfile.TemporaryDirectory() as d:
 src=pathlib.Path(d)/'original';wav=pathlib.Path(d)/'sample.wav'
 req=urllib.request.Request(r['download'],headers={'User-Agent':'AuralunaMusicStudio/0.1 (https://github.com/danydrag00-lang/auraluna-music-studio)'})
 with urllib.request.urlopen(req,timeout=60) as response,src.open('wb') as out:
  if urlparse(response.geturl()).hostname!='upload.wikimedia.org':raise ValueError('Unexpected redirect')
  total=0
  while chunk:=response.read(65536):
   total+=len(chunk)
   if total>20*1024*1024:raise ValueError('Source exceeds pilot limit')
   out.write(chunk)
 subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(src),'-map','0:a:0','-t','120','-c:a','pcm_s16le',str(wav)],check=True)
 if wav.stat().st_size>25*1024*1024:raise ValueError('PCM exceeds pilot limit')
 cmd=[sys.executable,str(root/'scripts/ingest.py'),str(wav),'--title',r['title'],'--creator',r['creator'],'--source',r['source'],'--evidence',json.dumps(r['evidence'])+'; converted to PCM, capped at 120 seconds','--license',r['license'],'--kind',a.kind,'--instrument',a.instrument,'--reviewed']
 if a.pitch is not None:cmd+=['--pitch',str(a.pitch)]
 subprocess.run(cmd,check=True)
