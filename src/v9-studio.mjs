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
 {data.seconds=Math.round(Number($('duration').value)*60);if(!Number.isInteger(data.seconds)||data.seconds<15||data.seconds>300)throw Error('Choose a duration between 15 seconds and 5 minutes.');}
 if(infer){if(!prompt)throw Error('Describe your music first.');}
 else{data.preset=$('preset').value;data.instruments=Object.keys(controls).filter(k=>controls[k].check.checked);data.nature=$('nature').value;data.gains=Object.fromEntries(data.instruments.map(k=>[k,Number(controls[k].slider.value)]));if(!data.instruments.length&&data.nature==='none')throw Error('Select at least one instrument or nature sound.');}
 if(data.format==='wav'&&data.seconds&&data.seconds*288000>=2**32-65536)throw Error('This duration exceeds the standard WAV size limit. Choose MP3 or FLAC.');
 return data;
}
function refresh(){
 const infer=$('mode').value==='prompt';$('mix-section').hidden=infer;$('preset').disabled=infer;$('infer-duration-row').hidden=true;$('duration').disabled=false;
 for(const c of Object.values(controls)){c.slider.disabled=!c.check.checked;c.value.textContent=(Number(c.slider.value)>0?'+':'')+c.slider.value+' dB'}
 try{const r=buildRequest();$('summary').textContent=(r.preset?presets[r.preset][0]:'Prompt-based configuration')+' · '+(r.seconds?r.seconds/60+' min':'duration inferred')+' · '+r.variations+' variation(s) · '+r.format.toUpperCase()+(r.instruments?' · '+r.instruments.map(k=>instruments[k]).join(', ')+' · '+r.nature:'');}
 catch(e){$('summary').textContent=e.message}
}

const API="https://auraluna-api.dhanushmanoharan1996.workers.dev";
let key="",busy=false,timer=null,active="",attempt=0;
const historyKey="auraluna-v9-jobs";
function history(){try{return JSON.parse(localStorage.getItem(historyKey)||"[]").filter(x=>/^auraluna-[a-f0-9]{32}$/.test(x.slug))}catch{return []}}
function remember(slug){try{localStorage.setItem(historyKey,JSON.stringify([{slug},...history().filter(x=>x.slug!==slug)].slice(0,30)))}catch{}renderHistory()}
function renderHistory(){const el=$("history");el.replaceChildren();for(const {slug} of history()){const b=document.createElement("button");b.type="button";b.className="v9-secondary";b.textContent=slug.slice(0,20)+"…";b.onclick=()=>watch(slug);el.append(b)}}
async function api(path,options={}){
 if(!key)throw Error("Enter your Auraluna access key and connect first.");
 const r=await fetch(API+path,{...options,headers:{Authorization:"Bearer "+key,...options.headers}});
 const d=await r.json();if(!r.ok)throw Error(d.error||"Backend HTTP "+r.status);return d;
}
function status(s){$("cloud-status").textContent=s}
function unlock(){busy=false;$("generate").disabled=false}
$("connect").onclick=async()=>{key=$("access-key").value.trim();$("access-key").value="";try{await api("/test-kaggle");status("Connected to Kaggle");$("generate").disabled=false}catch(e){key="";status(e.message)}};
$("disconnect").onclick=()=>{key="";clearTimeout(timer);active="";$("generate").disabled=true;status("Disconnected");busy=false;$("players").replaceChildren()};
function addFile(slug,name){const row=document.createElement("article"),h=document.createElement("h3"),b=document.createElement("button");h.textContent=name.split("/").pop();b.type="button";b.textContent=name.endsWith(".json")?"Open report":"Load audio";row.append(h,b);$("players").append(row);
 b.onclick=async()=>{b.disabled=true;try{const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));const u=new URL(d.url);if(u.protocol!=="https:")throw Error("Invalid output URL");const link=document.createElement("a");link.href=u.href;link.target="_blank";link.rel="noopener noreferrer";link.textContent="Download / open file";if(!name.endsWith(".json")){const player=document.createElement("audio");player.controls=true;player.preload="none";player.src=u.href;row.append(player)}row.append(link);b.textContent="Refresh link"}catch(e){status(e.message)}finally{b.disabled=false}};
}
async function watch(slug){if(!key){status("Connect first.");return}clearTimeout(timer);active=slug;remember(slug);$("players").replaceChildren();attempt=0;await poll(slug)}
async function poll(slug){if(active!==slug||!key)return;try{const d=await api("/status?slug="+encodeURIComponent(slug));if(active!==slug)return;const state=String(d.status).toUpperCase();status("Kaggle: "+state+(d.failureMessage?" — "+d.failureMessage:""));if(["COMPLETE","COMPLETED","SUCCESS"].includes(state)){const out=await api("/outputs?slug="+encodeURIComponent(slug));if(active!==slug)return;for(const f of out.files||[])addFile(slug,f.name);status(out.files?.length?"Production complete. Load audio below.":"Complete; no outputs listed yet.");unlock();return}if(["ERROR","FAILED","CANCELLED","CANCELED"].includes(state)){unlock();return}attempt=0;timer=setTimeout(()=>poll(slug),15000)}catch(e){status(e.message);if(++attempt<3)timer=setTimeout(()=>poll(slug),20000);else unlock()}}
$("v9-form").addEventListener("input",refresh);$("preset").addEventListener("change",applyPreset);
$("v9-form").onsubmit=async e=>{e.preventDefault();if(busy)return;try{const data=buildRequest();if(!key)throw Error("Connect first.");busy=true;$("generate").disabled=true;status("Submitting private Kaggle production…");const d=await api("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});await watch(d.slug)}catch(e){status(e.message);unlock()}};
$("check-job").onclick=()=>{const slug=$("existing-slug").value.trim();if(!/^auraluna-[a-f0-9]{32}$/.test(slug)){status("Invalid production slug");return}watch(slug)};
newJob();applyPreset();renderHistory();
