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
let pendingMeta=null;
function remember(slug){try{localStorage.setItem(historyKey,JSON.stringify([{slug,...(history().find(x=>x.slug===slug)||{}),...(pendingMeta||{})},...history().filter(x=>x.slug!==slug)].slice(0,30)))}catch{}renderHistory()}
function renderHistory(){const el=$("history");el.replaceChildren();for(const {slug,title,date} of history()){const b=document.createElement("button");b.type="button";b.className="v9-secondary";b.textContent=(title||"Saved track")+(date?" · "+new Date(date).toLocaleString():"");b.onclick=()=>watch(slug);el.append(b)}}
async function api(path,options={}){
 if(!key)throw Error("Enter your Auraluna access key and connect first.");
 const r=await fetch(API+path,{cache:"no-store",...options,headers:{Authorization:"Bearer "+key,...options.headers}});
 const d=await r.json();if(!r.ok){const e=new Error(d.error||"Backend HTTP "+r.status);e.status=r.status;throw e;}return d;
}
function status(s){$("cloud-status").textContent=s}
function unlock(){busy=false;$("generate").disabled=!key;$("generate").textContent="Generate Music"}
const keyStorage="auraluna-v9-device-access";
function forgetKey(){try{localStorage.removeItem(keyStorage)}catch{}}
let connectionVersion=0;
async function connect(value,remember){
 if(!value){status("Enter your access key.");return}
 const version=++connectionVersion;
 key=value;$("connect").disabled=true;$("generate").disabled=true;
 status("Connecting…");
 try{
  await api("/test-kaggle");
  if(version!==connectionVersion)return;
  if(remember){try{localStorage.setItem(keyStorage,value)}catch{status("Connected for this visit only: browser storage unavailable.");}}
  else forgetKey();
  $("access-key").value="";$("credentials").hidden=true;
  status("Connected");unlock();
  const latest=history()[0];if(latest)await watch(latest.slug);
 }catch(e){if(version!==connectionVersion)return;key="";if(e.status===401||e.status===403)forgetKey();$("credentials").hidden=false;status(e.message)}
 finally{if(version===connectionVersion)$("connect").disabled=false}
}
$("connect").onclick=()=>connect($("access-key").value.trim(),$("remember-device").checked);
$("disconnect").onclick=()=>{++connectionVersion;forgetKey();key="";clearTimeout(timer);active="";$("credentials").hidden=false;$("connect").disabled=false;$("generate").disabled=true;$("generate").textContent="Generate Music";status("Disconnected");busy=false;$("players").replaceChildren()};
async function addFile(slug,name){
 const row=document.createElement("article");row.className="v9-result";
 const h=document.createElement("h3"),meta=document.createElement("p"),player=document.createElement("audio"),download=document.createElement("button"),message=document.createElement("p"),retry=document.createElement("button");
 h.textContent=history().find(x=>x.slug===slug)?.title||"Your generated music";
 meta.textContent=name.split(".").pop().toUpperCase()+" · Original production";
 player.controls=true;player.preload="metadata";player.style.width="100%";player.hidden=true;
 download.type="button";download.textContent="Download music";download.className="v9-download";download.hidden=false;
 message.textContent="Preparing your music…";message.setAttribute("role","status");
 retry.type="button";retry.className="v9-secondary";retry.textContent="Retry audio";retry.hidden=true;
 row.append(h,meta,message,player,download,retry);$("players").append(row);
 async function load(){retry.hidden=true;message.textContent="Preparing your music…";try{
  const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));
  if(active!==slug)return;
  const u=new URL(d.url);if(u.protocol!=="https:")throw Error("Invalid output URL");
  player.src=u.href;player.hidden=false;message.textContent="";
 }catch(e){message.textContent=e.message;retry.hidden=false}}
 download.onclick=async()=>{
  download.disabled=true;download.textContent="Preparing download…";
  row.querySelector(".v9-direct-link")?.remove();
  try{
   const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));
   const u=new URL(d.url);if(u.protocol!=="https:")throw Error("Invalid output URL");
   try{
    const response=await fetch(u.href,{cache:"no-store",credentials:"omit"});
    if(!response.ok)throw Error("Storage HTTP "+response.status);
    const blob=await response.blob();if(!blob.size)throw Error("Empty music file");
    const object=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=object;a.download=d.name||name.split("/").pop();document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(object),60000);message.textContent="Download requested.";
   }catch(e){
    const a=document.createElement("a");a.className="v9-direct-link";a.href=u.href;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open fresh download link";a.download=d.name||name.split("/").pop();
    row.append(a);message.textContent="Browser could not fetch the file directly. Use the fresh link below to open or save your music.";
   }
  }catch(e){message.textContent="Download unavailable: "+e.message;retry.hidden=false}
  finally{download.disabled=false;download.textContent="Download music"}
 };
 retry.onclick=load;player.onerror=()=>{message.textContent="Audio unavailable. Refresh the audio link.";retry.hidden=false};
 await load();
}
function addReports(slug,files){
 const details=document.createElement("details"),summary=document.createElement("summary");summary.textContent="Licence & production details";details.append(summary);
 for(const {name} of files.filter(f=>f.name.endsWith(".json"))){const b=document.createElement("button");b.type="button";b.className="v9-secondary";b.textContent=name.includes("licences")?"Licence information":"Production information";b.onclick=async()=>{try{const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));const a=document.createElement("a");a.href=d.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open report";b.after(a)}catch(e){status(e.message)}};details.append(b)}$("players").append(details);
}
async function watch(slug){if(!key){status("Connect first.");return}clearTimeout(timer);active=slug;remember(slug);pendingMeta=null;$("players").replaceChildren();attempt=0;await poll(slug)}
async function poll(slug){if(active!==slug||!key)return;try{const d=await api("/status?slug="+encodeURIComponent(slug));if(active!==slug)return;const state=String(d.status).toUpperCase();status((state==="RUNNING"?"Creating your music":state==="QUEUED"?"Waiting for a GPU":state)+(d.failureMessage?" — "+d.failureMessage:""));if(["COMPLETE","COMPLETED","SUCCESS"].includes(state)){const out=await api("/outputs?slug="+encodeURIComponent(slug));if(active!==slug)return;const files=out.files||[],audio=files.filter(f=>/\.(mp3|wav|flac)$/i.test(f.name));for(const f of audio)await addFile(slug,f.name);if(active!==slug)return;if(files.some(f=>f.name.endsWith(".json")))addReports(slug,files);status(audio.length?"Production completed.":"Complete; no audio listed yet.");unlock();return}if(["ERROR","FAILED","CANCELLED","CANCELED"].includes(state)){unlock();return}attempt=0;timer=setTimeout(()=>poll(slug),15000)}catch(e){status(e.message);if(++attempt<3)timer=setTimeout(()=>poll(slug),20000);else unlock()}}
$("v9-form").addEventListener("input",refresh);$("preset").addEventListener("change",applyPreset);
$("v9-form").onsubmit=async e=>{e.preventDefault();if(busy)return;try{const data=buildRequest();if(!key)throw Error("Connect first.");busy=true;$("generate").disabled=true;$("generate").textContent="Generating music…";status("Submitting private Kaggle production…");const d=await api("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});pendingMeta={title:data.preset?presets[data.preset][0]:"Custom music",date:new Date().toISOString()};await watch(d.slug)}catch(e){status(e.message);unlock()}};
$("check-job").onclick=()=>{const slug=$("existing-slug").value.trim();if(!/^auraluna-[a-f0-9]{32}$/.test(slug)){status("Invalid production slug");return}watch(slug)};
newJob();applyPreset();renderHistory();
try{const saved=localStorage.getItem(keyStorage);if(saved){$("remember-device").checked=true;connect(saved,true)}}catch{}
