"""Import explicitly selected Commons audio into a quarantined local audition library.
No automatic listening approval. Verify file-level license, creator, source and original checksum.
"""
import json,pathlib,urllib.request,urllib.parse,hashlib,subprocess,tempfile,datetime,wave,math,struct,html,re
root=pathlib.Path(__file__).resolve().parents[1]
manifest=json.loads((root/'catalog/recording-sources.json').read_text())
index=root/'catalog/index.json'
rows=json.loads(index.read_text())
out=root/'audio';out.mkdir(exist_ok=True)
headers={'User-Agent':'AuralunaMusicStudio/1.0 (https://github.com/danydrag00-lang/auraluna-music-studio)'}
def get(url,limit):
 with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=90) as r:
  if urllib.parse.urlparse(r.geturl()).hostname not in ('commons.wikimedia.org','upload.wikimedia.org'):raise ValueError('Unexpected host')
  data=r.read(limit+1)
  if len(data)>limit:raise ValueError('Size limit')
  return data
def plain(s):return html.unescape(re.sub('<[^>]+>',' ',s)).strip()
def one(c):
 q=urllib.parse.urlencode(dict(action='query',format='json',titles=c['file'],prop='imageinfo',iiprop='url|sha1|mime|extmetadata',iiextmetadatafilter='LicenseUrl|Artist|LicenseShortName'))
 page=next(iter(json.loads(get('https://commons.wikimedia.org/w/api.php?'+q,2**20))['query']['pages'].values()))
 info=page['imageinfo'][0];m=info['extmetadata'];license_url=m['LicenseUrl']['value']
 u=urllib.parse.urlparse(license_url)
 if u.hostname not in ('creativecommons.org','www.creativecommons.org'):raise ValueError('Unrecognized license authority')
 license={'/publicdomain/zero/1.0':'CC0-1.0','/licenses/by/4.0':'CC-BY-4.0'}.get(u.path.rstrip('/').removesuffix('/deed.en'))
 if license!=c['license']:raise ValueError('License mismatch: '+license_url)
 artist=plain(m['Artist']['value'])
 if not artist:raise ValueError('Missing creator')
 source=info['descriptionurl']
 if any(a.get('source')==source for a in rows):return
 raw=get(info['url'],30*1024*1024)
 digest=int(hashlib.sha1(raw).hexdigest(),16)
 # MediaWiki returns hexadecimal SHA1 for imageinfo (also tolerate base36).
 sha=info['sha1']
 if digest!=int(sha,16 if re.fullmatch('[a-f0-9]{40}',sha) else 36):raise ValueError('Source checksum mismatch')
 with tempfile.TemporaryDirectory() as tmp:
  p=pathlib.Path(tmp)/'original';w=pathlib.Path(tmp)/'recording.wav';p.write_bytes(raw)
  subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(p),'-map','0:a:0','-t','300','-ar','44100','-ac','2','-c:a','pcm_s16le',str(w)],check=True,timeout=120)
  with wave.open(str(w)) as a:
   duration=a.getnframes()/a.getframerate();pcm=a.readframes(a.getnframes())
  if duration<5:raise ValueError('Recording too short')
  samples=memoryview(pcm).cast('h')
  peak=max(abs(x) for x in samples)/32768
  rms=math.sqrt(sum((x/32768)**2 for x in samples[::8])/len(samples[::8]))
  clip=sum(abs(x)>=32760 for x in samples)/len(samples)
  if peak<.005 or rms<.0005 or clip>.001:raise ValueError('Technical quality check failed')
  data=w.read_bytes();id=hashlib.sha256(data).hexdigest()
  if any(a['id']==id for a in rows):return
  (out/(id+'.wav')).write_bytes(data)
  rows.append(dict(id=id,title=c['title'],creator=artist,source=source,license=license,license_url=license_url,evidence={'source_sha1':sha,'source_url':info['url'],'license_label':m.get('LicenseShortName',{}).get('value'),'conversion':'PCM stereo 44.1 kHz, max 300 seconds'},kind=c['kind'],instrument=c['instrument'],path='audio/'+id+'.wav',duration=duration,sample_rate=44100,channels=2,bit_depth=16,reviewed=False,rights_verified=True,technical_verified=True,review_scope='File-level license and checksum verified; PCM peak/RMS/clipping screened; listening approval pending',quality={'peak':peak,'rms':rms,'clipped_fraction':clip},verified_date=str(datetime.date.today())))
  print('Imported for audition:',c['title'],duration,peak,rms)
  index.write_text(json.dumps(rows,indent=2)+'\n')
errors=[]
for c in manifest:
 try:one(c)
 except Exception as e:errors.append({'file':c['file'],'error':str(e)});print('Rejected:',c['file'],e)
(root/'catalog/recording-import-report.json').write_text(json.dumps({'errors':errors,'catalog_count':len(rows)},indent=2)+'\n')
