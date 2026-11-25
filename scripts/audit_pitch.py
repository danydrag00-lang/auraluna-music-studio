"""Audit the real WAVs independently of filename octave conventions.
Use autocorrelation and the first strong period to estimate fundamental frequency.
Only change octave labels on strong, consistent instrument-group evidence.
"""
import json,pathlib,math,collections
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate,resample_poly,find_peaks
root=pathlib.Path(__file__).resolve().parents[1]
index=root/'catalog/index.json'
rows=json.loads(index.read_text())
results=[]
for a in rows:
 if a.get('kind')!='note':continue
 rate,x=wavfile.read(root/a['path'])
 x=x.astype(np.float64)
 if x.ndim>1:x=x.mean(axis=1)
 if not np.isfinite(x).all() or np.max(np.abs(x))==0:raise ValueError(a['title'])
 x=x/np.max(np.abs(x))
 x=resample_poly(x,1, max(1,round(rate/8000)))
 sr=rate/max(1,round(rate/8000))
 # Analyze three sustained windows and require agreement.
 estimates=[]
 for offset in [.2,.55,.9]:
  y=x[int(offset*sr):int((offset+.6)*sr)]
  if len(y)<sr*.4:continue
  y=y-y.mean()
  ac=correlate(y,y,mode='full',method='fft')[len(y)-1:]
  if ac[0]<1e-8:continue
  ac=ac/ac[0]
  expected=440*2**((a['pitch']-69)/12)
  lo=max(2,int(sr/(expected*2.25)));hi=min(len(ac)-2,int(sr/(expected*.44)))
  peaks=find_peaks(ac)[0]
  valid=[p for p in peaks if lo<=p<=hi and ac[p]>.65]
  if not valid:continue
  top=max(ac[p] for p in valid)
  p=min(p for p in valid if ac[p]>=top*.9)
  delta=.5*(ac[p-1]-ac[p+1])/(ac[p-1]-2*ac[p]+ac[p+1]) if ac[p-1]-2*ac[p]+ac[p+1]!=0 else 0
  midi=69+12*math.log2(sr/(p+delta)/440)
  estimates.append(midi)
 measured=float(np.median(estimates)) if len(estimates)>=2 and max(estimates)-min(estimates)<.6 else None
 shift=round((measured-a['pitch'])/12)*12 if measured is not None else None
 if measured is not None and (abs(measured-a['pitch']-shift)>.65 or abs(shift)>12):shift=None
 results.append(dict(id=a['id'],instrument=a['instrument'],title=a['title'],label=a['pitch'],measured=measured,octave_shift=shift))
groups=collections.defaultdict(list)
for r in results:groups[r['instrument']].append(r)
for name,group in groups.items():
 votes=collections.Counter(r['octave_shift'] for r in group if r['octave_shift'] is not None)
 print(name,dict(votes), 'total',len(group))
 # Never modify a catalogue without reviewing the per-file results.
(root/'catalog/pitch-audit.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
