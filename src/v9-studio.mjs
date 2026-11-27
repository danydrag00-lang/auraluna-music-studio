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
 const data={engine:$('composition-engine').value,composition:$('composition-style').value,job:$('job').value.trim(),prompt,variations:Number($('variations').value),format:$('format').value};
 if(!/^[A-Za-z0-9]{1,48}$/.test(data.job))throw Error('Use a job ID containing only letters and numbers.');
 {data.seconds=Math.round(Number($('duration').value)*60);if(!Number.isInteger(data.seconds)||data.seconds<15||data.seconds>3600)throw Error('Choose a duration between 15 seconds and 60 minutes.');}
 if(infer){if(!prompt)throw Error('Describe your music first.');}
 else{data.preset=$('preset').value;data.instruments=Object.keys(controls).filter(k=>controls[k].check.checked);data.nature=$('nature').value;data.gains=Object.fromEntries(data.instruments.map(k=>[k,Number(controls[k].slider.value)]));if(!data.instruments.length&&data.nature==='none')throw Error('Select at least one instrument or nature sound.');}
 const natureOnly=!infer&&data.instruments.length===0&&data.nature!=='none';
 const limit=natureOnly||data.engine==='fast'?3600:900;
 if(data.seconds>limit)throw Error('Choose up to '+limit/60+' minutes for this mode.');
 if(![1,2,3].includes(data.variations)||natureOnly&&data.variations!==1)throw Error('Choose a valid variation count.');
 if(data.seconds*data.variations>limit)throw Error('Combined duration must not exceed '+limit/60+' minutes.');
 if(data.seconds>900&&data.format!=='mp3')throw Error('Choose MP3 for tracks longer than 15 minutes.');
 if(data.format==='wav'&&data.seconds&&data.seconds*288000>=2**32-65536)throw Error('This duration exceeds the standard WAV size limit. Choose MP3 or FLAC.');
 return data;
}
function estimate(r){
 const natureOnly=Array.isArray(r.instruments)&&!r.instruments.length&&r.nature!=="none";
 const mode=natureOnly?"nature":r.engine;
 const count=Array.isArray(r.instruments)?r.instruments.length:null;
 const signature=[mode,mode==="fast"?r.composition||"independent":"",count===null?"prompt":r.instruments.slice().sort().join(","),r.format,r.nature||"inferred"].join("|");
 const minutes=r.seconds*r.variations/60;
 // Broad planning assumptions, not measured CPU benchmarks.
 const base=mode==="nature"?[2,.12,6,.7]:mode==="fast"?[2,.6,8,2.5]:[4,3,10,7];
 let low=base[0]+base[1]*minutes,high=base[2]+base[3]*minutes;
 const compute=mode==="aria"?"GPU":"CPU";
 const rows=history().filter(x=>x.estimateSignature===signature&&x.compute===compute&&x.timingReliable===true&&x.measuredSeconds>0&&x.seconds>0&&x.variations>0&&Math.abs(Math.log((x.seconds*x.variations/60)/minutes))<=Math.log(2));
 const rates=rows.map(x=>x.measuredSeconds/(x.seconds*x.variations)).sort((a,b)=>a-b);
 if(rates.length>=3){
  const median=rates[Math.floor(rates.length/2)]*minutes;
  low=Math.max(1,Math.min(median*.7,rates[0]*minutes*.8));high=Math.max(low+1,median*1.5,rates[rates.length-1]*minutes*1.2);
 }
 return {low:Math.max(1,Math.floor(low)),high:Math.max(2,Math.ceil(high)),signature,source:rates.length>=3?"Based on "+rates.length+" comparable completed jobs":"Initial planning estimate"};
}
function estimateLabel(e){return e?e.low+"–"+e.high+" min":"—"}
function refresh(){
 const infer=$('mode').value==='prompt';$('mix-section').hidden=infer;$('preset').disabled=infer;$('infer-duration-row').hidden=true;$('duration').disabled=false;
 const natureOnly=!infer&&!Object.values(controls).some(c=>c.check.checked)&&$('nature').value!=='none';const fast=$('composition-engine').value==='fast';
 $('composition-style-row').hidden=natureOnly||!fast;$('composition-style').disabled=natureOnly||!fast;
 $('duration').max=natureOnly||fast?60:15;
 $('compute-plan').textContent=natureOnly||fast?'CPU · no GPU requested':'GPU · Aria neural composition';
 $('variations').disabled=natureOnly;
 if(natureOnly)$('variations').value='1';
 $('duration-limit').textContent=natureOnly?'Nature-only: up to 60 minutes.':fast?'Fast acoustic: up to 60 minutes combined across variations.':'Aria: up to 15 minutes combined across variations.';
 for(const c of Object.values(controls)){c.slider.disabled=!c.check.checked;c.value.textContent=(Number(c.slider.value)>0?'+':'')+c.slider.value+' dB'}
 try{const r=buildRequest();const e=estimate(r);$('estimate-time').textContent=estimateLabel(e);$('estimate-basis').textContent=e.source+' · Includes typical setup allowance; queue delays can extend it.';$('summary').textContent=(r.preset?presets[r.preset][0]:'Prompt-based configuration')+' · '+(r.seconds?r.seconds/60+' min':'duration inferred')+' · '+(r.engine==='fast'?'Fast acoustic · '+(r.composition==='thematic'?'Recurring theme':'Independent sections'):'Aria AI')+' · '+r.variations+' variation(s) · '+r.format.toUpperCase()+(r.instruments?' · '+r.instruments.map(k=>instruments[k]).join(', ')+' · '+r.nature:'');}
 catch(e){$('summary').textContent=e.message;$('estimate-time').textContent='—';$('estimate-basis').textContent='Choose valid production settings.'}
}

const API="https://auraluna-api.dhanushmanoharan1996.workers.dev";
let key="",busy=false,timer=null,active="",attempt=0;
const historyKey="auraluna-v9-jobs";
function history(){try{return JSON.parse(localStorage.getItem(historyKey)||"[]").filter(x=>/^auraluna-[a-f0-9]{32}$/.test(x.slug))}catch{return []}}
let pendingMeta=null;
document.addEventListener("visibilitychange",()=>{if(document.hidden)continuousObservation=false});
let selectedEnd=0,clockRunning=false,selectedEstimate=null,continuousObservation=false,submittingSlugExpected=false;
function durationLabel(seconds){if(!Number.isFinite(seconds)||seconds<=0)return "Not recorded";const n=Math.round(seconds);return Math.floor(n/60)+"m "+String(n%60).padStart(2,"0")+"s"}
function showRequest(meta){
 selectedEstimate=meta?.estimate||null;
 let retrospective=false;
 // Older jobs may lack request metadata. Never fabricate a historical accelerator or original estimate.
 if(!selectedEstimate&&meta?.seconds&&Number.isFinite(meta.seconds)){
  const preset=Object.entries(presets).find(([,v])=>v[0]===meta.title);
  if(preset&&(meta.engine||preset[1][1].length===0)){
   const [, [title,ins,nature]]=preset;
   if(ins.length===0){
    selectedEstimate=estimate({seconds:meta.seconds,variations:meta.variations||1,format:meta.format||"mp3",instruments:[],nature,engine:meta.engine||"aria"});
    retrospective=true;
   }
  }
 }
 $("estimate-caption").textContent=retrospective?"Planning estimate (inferred; not original)":"Original estimate";
 $("requested-estimate").textContent=selectedEstimate?estimateLabel(selectedEstimate):"Not recorded";$("requested-duration").textContent=durationLabel(meta?.seconds);$("requested-style").textContent=meta?.title||"Saved production";$("requested-format").textContent=meta?.format?.toUpperCase()||"—";$("requested-composition").textContent=meta?.composition==="thematic"?"Recurring theme":meta?.composition==="independent"?"Independent sections":"Not recorded / not applicable";$("requested-compute").textContent=meta?.compute?meta.compute+" requested":"Not recorded";}
let monitorVersion=0, pollInFlight=false, selectedStarted=0, lastChecked=0, unknownChecks=0;
const terminalStates=new Set(["COMPLETE","COMPLETED","SUCCESS","ERROR","FAILED","CANCELLED","CANCELED","CANCEL_ACKNOWLEDGED","CANCEL_REQUESTED"]);
function updateSaved(slug,patch){try{const rows=history();localStorage.setItem(historyKey,JSON.stringify(rows.map(x=>x.slug===slug?{...x,...patch}:x)))}catch{}renderHistory()}
function showProgress(text,running=false){$("production-status").textContent=text;$("production-panel").hidden=false;$("production-progress").hidden=!running;$("check-status").disabled=pollInFlight||!active||!key;}
function elapsed(){if(!selectedStarted||(!clockRunning&&!selectedEnd))return "—";const n=Math.max(0,Math.floor(((selectedEnd||Date.now())-selectedStarted)/1000));return Math.floor(n/60)+"m "+String(n%60).padStart(2,"0")+"s"}
function updateClock(){const spent=selectedStarted?((selectedEnd||Date.now())-selectedStarted)/60000:0;$("remaining-estimate").textContent=selectedEnd?"Finished / stopped":!clockRunning||!selectedEstimate?"—":spent>=selectedEstimate.high?"Taking longer than estimated":Math.max(0,Math.floor(selectedEstimate.low-spent))+"–"+Math.max(1,Math.ceil(selectedEstimate.high-spent))+" min (approx.)";$("elapsed-time").textContent=elapsed();$("last-check").textContent=lastChecked?new Date(lastChecked).toLocaleTimeString():"—"}
setInterval(updateClock,1000);
function remember(slug){try{localStorage.setItem(historyKey,JSON.stringify([{slug,...(history().find(x=>x.slug===slug)||{}),...(pendingMeta||{})},...history().filter(x=>x.slug!==slug)].slice(0,30)))}catch{}renderHistory()}
function renderHistory(){
 const el=$("history");el.replaceChildren();
 const rows=history();
 if(!rows.length){el.textContent="Your generated music will appear here.";return}
 for(const {slug,title,date,state,seconds,format,compute} of rows){
  const item=document.createElement("div");item.className="v9-saved";
  const info=document.createElement("div"),name=document.createElement("strong"),meta=document.createElement("p"),button=document.createElement("button");
  name.textContent=title||"Saved track";
  const labels={COMPLETE:"Ready",COMPLETED:"Ready",SUCCESS:"Ready",RUNNING:"Creating",QUEUED:"Queued",ERROR:"Failed",FAILED:"Failed",CANCELED:"Canceled",CANCELLED:"Canceled"};
  meta.textContent=[date?new Date(date).toLocaleString():"",seconds?"Requested: "+durationLabel(seconds):"Requested duration not recorded",format?.toUpperCase(),compute?compute+" requested":"",labels[state]||"Check status"].filter(Boolean).join(" · ");
  info.append(name,meta);button.type="button";button.className="v9-secondary";button.textContent=["COMPLETE","COMPLETED","SUCCESS"].includes(state)?"Listen & download":"Open";button.onclick=()=>watch(slug);item.append(info,button);el.append(item);
 }
}
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
  let backendVersion="";try{const health=await fetch(API+"/health",{cache:"no-store"});if(health.ok)backendVersion=(await health.json()).version||""}catch{}
  if(version!==connectionVersion)return;
  status(backendVersion==="V15-composition-styles"?"Connected · V15 composition styles":backendVersion==="V14-cpu-routing"?"Connected · V14 · update Worker for composition styles":backendVersion?"Connected · "+backendVersion+" · CPU routing not confirmed; update Worker if needed.":"Connected · Backend version unavailable");unlock();
  const latest=history()[0];if(latest)await watch(latest.slug);
 }catch(e){if(version!==connectionVersion)return;key="";if(e.status===401||e.status===403)forgetKey();$("credentials").hidden=false;status(e.message)}
 finally{if(version===connectionVersion)$("connect").disabled=false}
}
$("connect").onclick=()=>connect($("access-key").value.trim(),$("remember-device").checked);
$("disconnect").onclick=()=>{++connectionVersion;forgetKey();key="";clearTimeout(timer);++monitorVersion;active="";clockRunning=false;$("production-panel").hidden=true;$("credentials").hidden=false;$("connect").disabled=false;$("generate").disabled=true;$("generate").textContent="Generate Music";status("Disconnected");busy=false;$("players").replaceChildren()};
async function addFile(slug,name){
 const row=document.createElement("article");row.className="v9-result";
 const h=document.createElement("h3"),meta=document.createElement("p"),player=document.createElement("audio"),download=document.createElement("button"),message=document.createElement("p"),retry=document.createElement("button");
 h.textContent=(history().find(x=>x.slug===slug)?.title||"Your generated music")+" · Variation "+(name.match(/variation_(\d+)/)?.[1]||"1");
 const saved=history().find(x=>x.slug===slug);
 const requested=saved?.seconds?" · Requested: "+durationLabel(saved.seconds):"";
 meta.textContent=name.split(".").pop().toUpperCase()+requested;
 player.addEventListener("loadedmetadata",()=>{if(Number.isFinite(player.duration)&&player.duration>0)meta.textContent=name.split(".").pop().toUpperCase()+requested+" · Audio length: "+durationLabel(player.duration)});
 player.controls=true;player.preload="metadata";player.style.width="100%";player.hidden=true;
 download.type="button";download.textContent="Download music";download.className="v9-download";
 message.textContent="Preparing your music…";message.setAttribute("role","status");
 retry.type="button";retry.className="v9-secondary";retry.textContent="Retry audio";retry.hidden=true;
 row.append(h,meta,message,player,download,retry);$("players").append(row);
 let objectURL="",loading=null;
 const query="?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name);
 async function getAudio(){
  if(objectURL)return objectURL;
  if(!loading)loading=(async()=>{
   const r=await fetch(API+"/file"+query,{cache:"no-store",headers:{Authorization:"Bearer "+key}});
   if(!r.ok){let detail;try{detail=(await r.json()).error}catch{}throw Error(detail||"Download HTTP "+r.status)}
   if(!(r.headers.get("content-type")||"").startsWith("audio/"))throw Error("Server did not return audio");
   const blob=await r.blob();if(!blob.size)throw Error("Empty music file");
   if(!row.isConnected)throw Error("Track selection changed");
   objectURL=URL.createObjectURL(blob);
   const observer=new MutationObserver(()=>{if(!row.isConnected){URL.revokeObjectURL(objectURL);objectURL="";observer.disconnect()}});
   observer.observe($("players"),{childList:true,subtree:true});
   return objectURL;
  })().finally(()=>loading=null);
  return loading;
 }
 async function load(){
  retry.hidden=true;message.textContent="Preparing your music…";
  try{const u=await getAudio();if(!row.isConnected)return;player.src=u;player.hidden=false;message.textContent=""}
  catch(e){message.textContent=e.message;retry.hidden=false}
 }
 download.onclick=async()=>{
  download.disabled=true;download.textContent="Preparing download…";
  try{const u=await getAudio();const a=document.createElement("a");a.href=u;a.download=name.split("/").pop();document.body.append(a);a.click();a.remove();message.textContent="Download requested."}
  catch(e){message.textContent="Download unavailable: "+e.message;retry.hidden=false}
  finally{download.disabled=false;download.textContent="Download music"}
 };
 retry.onclick=load;player.onerror=()=>{message.textContent="Audio could not play. Try downloading it.";retry.hidden=false};
 if((saved?.seconds||0)<=900&&(saved?.variations||1)===1){await load()}else{message.textContent="Select Load audio or Download music.";retry.textContent="Load audio";retry.hidden=false}
}
function addReports(slug,files){
 const details=document.createElement("details"),summary=document.createElement("summary");summary.textContent="Licence & production details";details.append(summary);
 for(const {name} of files.filter(f=>f.name.endsWith(".json"))){const b=document.createElement("button");b.type="button";b.className="v9-secondary";b.textContent=name.includes("licences")?"Licence information":"Production information";b.onclick=async()=>{try{const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));const a=document.createElement("a");a.href=d.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open report";b.after(a)}catch(e){status(e.message)}};details.append(b)}$("players").append(details);
}
async function watch(slug){
 continuousObservation=Boolean(submittingSlugExpected);submittingSlugExpected=false;
 if(!key){status("Connect first.");return}
 clearTimeout(timer);const version=++monitorVersion;active=slug;remember(slug);pendingMeta=null;
 const saved=history().find(x=>x.slug===slug);
 showRequest(saved);clockRunning=false;selectedEnd=saved?.observedEnd||0;selectedStarted=saved?.date?Date.parse(saved.date):0;lastChecked=0;attempt=0;unknownChecks=0;pollInFlight=false;
 $("players").replaceChildren();updateClock();
 showProgress("Checking production…",true);await poll(slug,version);
}
async function poll(slug,version=monitorVersion){
 if(active!==slug||!key||version!==monitorVersion||pollInFlight)return;
 clearTimeout(timer);pollInFlight=true;$("check-status").disabled=true;
 let next=0;
 try{
  const d=await api("/status?slug="+encodeURIComponent(slug));
  if(version!==monitorVersion)return;
  const state=String(d.status).toUpperCase();
  lastChecked=Date.now();
  const done=["COMPLETE","COMPLETED","SUCCESS","ERROR","FAILED","CANCELLED","CANCELED","CANCEL_ACKNOWLEDGED"].includes(state);
  clockRunning=!done&&!selectedEnd&&["RUNNING","QUEUED","SUBMITTED","PENDING"].includes(state);
  if(done)selectedEnd=selectedEnd||lastChecked;
  updateSaved(slug,{state,observedEnd:selectedEnd});
  updateClock();attempt=0;
  const uncertain=["UNKNOWN","UNSPECIFIED","UNDEFINED","NULL","0","STATUS_UNSPECIFIED"].includes(state);
  if(["COMPLETE","COMPLETED","SUCCESS"].includes(state)||uncertain||state==="RUNNING"){
   if(state!=="RUNNING")showProgress(uncertain?"Checking for saved audio…":"Production complete. Preparing audio…",true);
   const out=await api("/outputs?slug="+encodeURIComponent(slug));
   if(version!==monitorVersion)return;
   const files=out.files||[],audio=files.filter(f=>/\.(mp3|wav|flac)$/i.test(f.name));
   if(state==="RUNNING"&&audio.length<(history().find(x=>x.slug===slug)?.variations||1)){showProgress("Creating your music…",true);next=15000;return}
   $("players").replaceChildren();
   const expected=history().find(x=>x.slug===slug)?.variations||1;
   if(audio.length<expected){
    if(uncertain){unknownChecks++;showProgress("Kaggle has not confirmed the production status. No audio found."+(unknownChecks<4?" Checking again automatically.":" Open Production details to verify the job; do not submit a duplicate."),false);if(unknownChecks<4)next=30000;return}
    showProgress("Completed, but no audio is available yet.");next=20000;return
   }
   clockRunning=false;selectedEnd=selectedEnd||Date.now();const saved=history().find(x=>x.slug===slug);const measuredSeconds=(selectedEnd-selectedStarted)/1000;updateSaved(slug,{state:"COMPLETE",observedEnd:selectedEnd,...(continuousObservation&&saved?.estimateSignature&&measuredSeconds>0?{measuredSeconds,timingReliable:true}:{})});updateClock();refresh();
   for(const f of audio){if(version!==monitorVersion)return;await addFile(slug,f.name)}
   if(version!==monitorVersion)return;
   if(files.some(f=>f.name.endsWith(".json")))addReports(slug,files);
   showProgress("Production completed. Your audio is below.");unlock();return
  }
  unknownChecks=0;
  if(["ERROR","FAILED","CANCELLED","CANCELED","CANCEL_ACKNOWLEDGED"].includes(state)){
   showProgress((state.includes("CANCEL")?"Production canceled.":"Production failed.")+(d.failureMessage?" "+d.failureMessage:" No further details supplied by Kaggle."));
   unlock();return
  }
  const label=state==="RUNNING"?"Creating your music…":state==="QUEUED"?"Waiting for Kaggle compute…":state==="CANCEL_REQUESTED"?"Cancellation requested…":"Kaggle status: "+state;
  showProgress(label+(selectedStarted&&Date.now()-selectedStarted>20*60000?" This is taking longer than usual; check status or review the notebook.":""),true);
  next=15000;
 }catch(e){
  if(version!==monitorVersion)return;
  continuousObservation=false;attempt++;showProgress("Status check failed: "+e.message+(attempt<4?" · Reconnecting automatically.":" · Use Check status to retry."));
  if(attempt<4)next=Math.min(60000,15000*attempt);else unlock();
 }finally{
  if(version===monitorVersion){
   pollInFlight=false;$("check-status").disabled=!active||!key;
   if(next)timer=setTimeout(()=>poll(slug,version),next);
  }
 }
}
$("check-status").onclick=()=>{if(active){attempt=0;unknownChecks=0;poll(active,monitorVersion)}};
$("production-details").onclick=()=>{if(active)window.open("https://www.kaggle.com/code/dhanushdrag/"+active,"_blank","noopener,noreferrer")};
$("v9-form").addEventListener("input",refresh);$("preset").addEventListener("change",applyPreset);
$("v9-form").onsubmit=async e=>{e.preventDefault();if(busy)return;try{const data=buildRequest();if(!key)throw Error("Connect first.");busy=true;$("generate").disabled=true;$("generate").textContent="Generating music…";const prediction=estimate(data);const submittedAt=Date.now();selectedStarted=submittedAt;selectedEnd=0;clockRunning=true;lastChecked=0;showRequest({title:data.preset?presets[data.preset][0]:"Custom music",seconds:data.seconds,format:data.format,estimate:prediction});updateClock();showProgress("Submitting production…",true);const d=await api("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});pendingMeta={title:data.preset?presets[data.preset][0]:"Custom music",date:new Date(submittedAt).toISOString(),estimate:prediction,estimateSignature:prediction.signature,seconds:data.seconds,format:data.format,engine:data.engine,composition:d.composition||null,compute:d.compute||null,variations:data.variations,state:"QUEUED"};submittingSlugExpected=true;await watch(d.slug)}catch(e){clockRunning=false;selectedEnd=Date.now();updateClock();showProgress(e.message);unlock()}};
$("check-job").onclick=()=>{const slug=$("existing-slug").value.trim();if(!/^auraluna-[a-f0-9]{32}$/.test(slug)){status("Invalid production slug");return}watch(slug)};
newJob();applyPreset();renderHistory();
try{const saved=localStorage.getItem(keyStorage);if(saved){$("remember-device").checked=true;connect(saved,true)}}catch{}
