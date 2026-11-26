const $=id=>document.getElementById(id);
const instruments={felt_piano:"Felt piano",grand_piano:"Grand piano",flute:"Flute",cello:"Cello",harp:"Harp",handpan:"Handpan",bansuri:"Bansuri",singing_bowls:"Singing bowls"};
const presets={
luxury_spa:["Luxury spa",["felt_piano","flute","cello","harp"],"river"],
deep_sleep:["Deep sleep",["felt_piano","cello"],"rain"],
meditation:["Meditation",["flute","harp"],"ocean"],
study_focus:["Study focus",["grand_piano","harp"],"forest"],
emotional_relaxation:["Emotional relaxation",["felt_piano","cello"],"ocean"],
peaceful_piano:["Peaceful piano",["felt_piano"],"none"],
yoga_zen:["Yoga Zen",["handpan","singing_bowls"],"forest"],
indian_meditation:["Indian meditation",["bansuri","singing_bowls"],"river"],
rain_sleep:["Rain sleep",[],"rain"],ocean_sleep:["Ocean sleep",[],"ocean"],forest_relaxation:["Forest relaxation",[],"forest"],river_relaxation:["River relaxation",[],"river"]};
for(const [key,[name]] of Object.entries(presets))$('preset').add(new Option(name,key));
const controls={};
for(const [key,name] of Object.entries(instruments)){
 const row=document.createElement('div');row.className='v9-track';
 const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';label.append(check,document.createTextNode(' '+name));
 const slider=document.createElement('input');slider.type='range';slider.min=-30;slider.max=6;slider.step=1;slider.value=0;slider.setAttribute('aria-label',name+' gain');
 const value=document.createElement('output');value.textContent='0 dB';
 row.append(label,slider,value);$('instrument-mixer').append(row);controls[key]={check,slider,value};
}
function newJob(){$('job').value='v9'+Date.now().toString(36)+Math.random().toString(36).slice(2,8)}
function applyPreset(){const [,selected,nature]=presets[$('preset').value];for(const [key,c] of Object.entries(controls)){c.check.checked=selected.includes(key);c.slider.value=0;} $('nature').value=nature;refresh()}
function buildRequest(){
 const infer=$('mode').value==='prompt', prompt=$('prompt').value.trim();
 const data={job:$('job').value.trim(),prompt,variations:Number($('variations').value),format:$('format').value};
 if(!/^[A-Za-z0-9]{1,48}$/.test(data.job))throw Error('Use a job ID containing only letters and numbers.');
 if(!infer||!$('infer-duration').checked){data.seconds=Math.round(Number($('duration').value)*60);if(!Number.isInteger(data.seconds)||data.seconds<15||data.seconds>43200)throw Error('Choose a duration between 15 seconds and 12 hours.');}
 if(infer){if(!prompt)throw Error('Describe your music first.');}
 else{data.preset=$('preset').value;data.instruments=Object.keys(controls).filter(k=>controls[k].check.checked);data.nature=$('nature').value;data.gains=Object.fromEntries(data.instruments.map(k=>[k,Number(controls[k].slider.value)]));if(!data.instruments.length&&data.nature==='none')throw Error('Select at least one instrument or nature sound.');}
 if(data.format==='wav'&&data.seconds&&data.seconds*288000>=2**32-65536)throw Error('This duration exceeds the standard WAV size limit. Choose MP3 or FLAC.');
 return data;
}
function refresh(){
 const infer=$('mode').value==='prompt';$('mix-section').hidden=infer;$('preset').disabled=infer;$('infer-duration-row').hidden=!infer;$('duration').disabled=infer&&$('infer-duration').checked;
 for(const c of Object.values(controls)){c.slider.disabled=!c.check.checked;c.value.textContent=(Number(c.slider.value)>0?'+':'')+c.slider.value+' dB'}
 try{const r=buildRequest();$('summary').textContent=(r.preset?presets[r.preset][0]:'Prompt-based configuration')+' · '+(r.seconds?r.seconds/60+' min':'duration inferred')+' · '+r.variations+' variation(s) · '+r.format.toUpperCase()+(r.instruments?' · '+r.instruments.map(k=>instruments[k]).join(', ')+' · '+r.nature:'');}
 catch(e){$('summary').textContent=e.message}
}
function download(data){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=data.job+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1500)}
function code(data){
 const bytes=new TextEncoder().encode(JSON.stringify(data));const encoded=btoa(Array.from(bytes,x=>String.fromCharCode(x)).join(''));
 return [
 'from pathlib import Path','import base64, subprocess, sys',
 'engine = Path("/kaggle/working/Auraluna-V9/engine")','engine.mkdir(parents=True, exist_ok=True)',
 'base = "https://raw.githubusercontent.com/danydrag00-lang/auraluna-music-studio/main/backend/v9/"',
 'for name in ["compose_preview.py", "arrange.py", "produce.py", "request.py"]:',
 '    subprocess.run(["curl", "-fLsS", base + name, "-o", str(engine / name)], check=True)',
 'request = Path("/kaggle/working/'+data.job+'.json")',
 'request.write_bytes(base64.b64decode("'+encoded+'"))',
 'subprocess.run([sys.executable, str(engine / "request.py"), str(request), "--run", "--max-sections", "3"], check=True)'
 ].join('\n');
}
$('v9-form').addEventListener('input',refresh);$('preset').addEventListener('change',applyPreset);$('new-job').onclick=()=>{newJob();refresh();$('feedback').textContent='New production ID created.'};
$('v9-form').onsubmit=e=>{e.preventDefault();try{download(buildRequest());$('feedback').textContent='Request downloaded. Copy the Kaggle code to execute it.'}catch(e){$('feedback').textContent=e.message}};
$('copy-code').onclick=async()=>{try{const text=code(buildRequest());await navigator.clipboard.writeText(text);$('feedback').textContent='Kaggle code copied. Paste into your installed V9 notebook; run again with the same job settings to resume.'}catch(e){$('feedback').textContent='Unable to copy: '+e.message+'. Download the request instead.'}};
let urls=[];$('tracks').onchange=()=>{urls.forEach(URL.revokeObjectURL);urls=[];$('players').replaceChildren();for(const file of $('tracks').files){const row=document.createElement('article'),name=document.createElement('h3'),player=document.createElement('audio'),link=document.createElement('a');name.textContent=file.name;const url=URL.createObjectURL(file);urls.push(url);player.controls=true;player.preload='metadata';player.src=url;link.href=url;link.download=file.name;link.textContent='Download track';row.append(name,player,link);$('players').append(row)}};
document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true);
newJob();applyPreset();