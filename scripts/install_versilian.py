"""Install a bounded CC0 pilot from the official Versilian repositories.
Run with Python 3 and network access. Downloads real source WAVs, never synthesizes replacements.
"""
import pathlib,json,urllib.request,urllib.parse,re,hashlib,wave,datetime,io
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCES=[('sgossner/VCSL','Chordophones/Zithers/Grand Piano, Kawai/Sustains/','acoustic grand piano','GPiano_sus_'),('sgossner/VSCO-2-CE','Woodwinds/Flute/susvib/','concert flute','LDFlute_susvib_'),('sgossner/VSCO-2-CE','Strings/Harp/','harp','KSHarp_'),('sgossner/VSCO-2-CE','Strings/Cello Section/susvib/','cello section','susvib_'),('sgossner/VSCO-2-CE','Woodwinds/Clarinet/susLong/','clarinet','DCClar_susLong_')]
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'AuralunaMusicStudio/1.0'})
 with urllib.request.urlopen(req,timeout=60) as r:
  data=r.read(25*1024*1024+1)
  if len(data)>25*1024*1024:raise ValueError('File exceeds pilot limit')
  return data
def api(path):return json.loads(get('https://api.github.com/repos/'+path))
def pitch(name,prefix):
 m=re.match(re.escape(prefix)+r'([A-G])([#b]?)(-?\d+)(?:_|\.)',name)
 if not m:return None
 return 12*(int(m[3])+1)+dict(C=0,D=2,E=4,F=5,G=7,A=9,B=11)[m[1]]+({'#':1,'b':-1,'':0}[m[2]])
def run():
 index=ROOT/'catalog/index.json'; rows=json.loads(index.read_text()); ids={x['id'] for x in rows}; out=ROOT/'audio';out.mkdir(exist_ok=True)
 for repo,folder,instrument,prefix in SOURCES:
  meta=api(repo)
  if (meta.get('license') or {}).get('spdx_id')!='CC0-1.0':raise ValueError('Unexpected repository license: '+repo)
  commit=api(repo+'/commits/'+meta['default_branch'])['sha']
  tree=api(repo+'/git/trees/'+commit+'?recursive=1')
  if tree.get('truncated'):raise ValueError('Incomplete tree')
  notes={}
  for item in tree['tree']:
   path=item['path'];name=path.rsplit('/',1)[-1]
   if not path.startswith(folder) or not name.lower().endswith('.wav'):continue
   midi=pitch(name,prefix)
   if midi is None or not (36 if instrument=='cello section' else 42)<=midi<=81:continue
   rank=(0 if '_v2_' in name else 1,0 if 'rr1' in name else 1,name)
   if midi not in notes or rank<notes[midi][0]:notes[midi]=(rank,path)
  if len(notes)<4:raise ValueError('Insufficient sample matches: '+instrument)
  for midi,(_,path) in sorted(notes.items()):
   source='https://github.com/'+repo+'/blob/'+commit+'/'+urllib.parse.quote(path,safe='/')
   if any(x.get('source')==source for x in rows):continue
   raw=get('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+urllib.parse.quote(path,safe='/'))
   digest=hashlib.sha256(raw).hexdigest()
   if digest in ids:continue
   with wave.open(io.BytesIO(raw),'rb') as w:
    rate=w.getframerate(); frames=w.getnframes();channels=w.getnchannels();bits=w.getsampwidth()*8; samples=w.readframes(frames)
    if rate<22050 or frames<rate/4 or channels not in (1,2) or bits not in (16,24,32) or not any(samples):raise ValueError('Invalid WAV '+path)
   target=out/(digest+'.wav');target.write_bytes(raw)
   rows.append(dict(id=digest,title=path.rsplit('/',1)[-1],creator='Versilian Studios and contributors',source=source,evidence='Official repository CC0-1.0 license at '+commit,license='CC0-1.0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',reviewed=True,review_scope='Source-level license and basic PCM validation; listening review pending',instrument=instrument,kind='note',pitch=midi,path='audio/'+target.name,duration=frames/rate,sample_rate=rate,channels=channels,bit_depth=bits,verified_date=str(datetime.date.today())))
   ids.add(digest)
  index.write_text(json.dumps(rows,indent=2)+'\n')
  print(instrument,len(notes),'source pitches')
 print('Catalog assets:',len(rows))
if __name__=='__main__':run()
