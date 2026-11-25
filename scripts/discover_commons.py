"""Discover candidate audio, never publish without manual rights and audio review."""
import urllib.request, urllib.parse, json, pathlib, time, re, html
ROOT=pathlib.Path(__file__).resolve().parents[1]
API='https://commons.wikimedia.org/w/api.php'
UA='AuralunaMusicStudio/0.1 (https://github.com/danydrag00-lang/auraluna-music-studio)'
TERMS=['felt piano note','piano single note','bamboo flute note','bansuri note','harp note','singing bowl','tanpura','rain field recording','river field recording','forest ambience','ocean waves']
def clean(s):return html.unescape(re.sub(r'<[^>]*>',' ',s)).strip()
def get(params):
 req=urllib.request.Request(API+'?'+urllib.parse.urlencode(params),headers={'User-Agent':UA})
 with urllib.request.urlopen(req,timeout=45) as r:return json.load(r)
def discover():
 output=ROOT/'catalog/candidates.json'
 records={x['source']:x for x in json.loads(output.read_text())} if output.exists() else {}
 for term in TERMS:
  try:
   data=get(dict(action='query',format='json',generator='search',gsrsearch=term+' filetype:audio',gsrnamespace=6,gsrlimit=30,prop='imageinfo',iiprop='url|mime|size|extmetadata'))
   for page in data.get('query',{}).get('pages',{}).values():
    info=page.get('imageinfo',[{}])[0]; m=info.get('extmetadata',{})
    field=lambda k:clean(m.get(k,{}).get('value',''))
    lic=field('LicenseUrl').replace('http://','https://').rstrip('/')
    accepted={'https://creativecommons.org/publicdomain/zero/1.0':'CC0-1.0','https://creativecommons.org/licenses/by/4.0':'CC-BY-4.0'}
    if lic not in accepted or not info.get('mime','').startswith('audio/') or not field('Artist') or not info.get('descriptionurl'):continue
    source=info['descriptionurl']
    records.setdefault(source,dict(title=page['title'],creator=field('Artist'),source=source,download=info['url'],license=accepted[lic],license_url=lic,evidence=m,search_term=term,reviewed=False,bytes=info.get('size')))
  except Exception as e:print(term, str(e))
  time.sleep(2)
 output.write_text(json.dumps(list(records.values()),indent=2)+'\n')
 print(len(records),'candidates; none published by discovery')
if __name__=='__main__':discover()
