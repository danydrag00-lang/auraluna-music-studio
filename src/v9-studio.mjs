const $=id=>document.getElementById(id);
const instruments={felt_piano:"Felt piano",grand_piano:"Grand piano",flute:"Flute",cello:"Cello",harp:"Harp",handpan:"Handpan",bansuri:"Bansuri",singing_bowls:"Singing bowls",clarinet:"Clarinet (beta)",oboe:"Oboe (beta)",bassoon:"Bassoon (beta)"};
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
const natureControls={};
const natureNames={rain:"Rain",river:"River",ocean:"Ocean",forest:"Forest"};
for(const [name,title] of Object.entries(natureNames)){
 const row=document.createElement("div");row.className="v9-track";
 const label=document.createElement("label"),check=document.createElement("input");check.type="checkbox";label.append(check,document.createTextNode(" "+title));
 const slider=document.createElement("input");slider.type="range";slider.min=-30;slider.max=6;slider.step=1;slider.value=0;slider.setAttribute("aria-label",title+" gain");
 const value=document.createElement("output");value.textContent="0 dB";row.append(label,slider,value);$("nature-mixer").append(row);natureControls[name]={check,slider,value};
}
function chosenNature(){return Object.fromEntries(Object.entries(natureControls).filter(([,c])=>c.check.checked).map(([name,c])=>[name,Number(c.slider.value)]))}
let deployedVersion="";
function newJob(){$('job').value='v9'+Date.now().toString(36)+Math.random().toString(36).slice(2,8)}
function applyPreset(){const [,selected,nature]=presets[$('preset').value];for(const [key,c] of Object.entries(controls)){c.check.checked=selected.includes(key);c.slider.value=0;} for(const [name,c] of Object.entries(natureControls)){c.check.checked=name===nature;c.slider.value=0;}refresh()}
let extensionSelection=null,regenerationSelection=null;
function buildRequest(preview=false){
 const infer=$('mode').value==='prompt', prompt=$('prompt').value.trim();
 const data={mastering:$("mastering").value,aac_mode:$('format').value==='m4a'?$('aac-mode').value:'premium',tuning:$('tuning').value,engine:$('composition-engine').value,composition:$('composition-style').value,job:$('job').value.trim(),prompt,variations:Number($('variations').value),format:$('format').value};
 if(!/^[A-Za-z0-9]{1,48}$/.test(data.job))throw Error('Use a job ID containing only letters and numbers.');
 {data.seconds=preview?60:Math.round(Number($('duration').value)*60);if(!Number.isInteger(data.seconds)||data.seconds<15||data.seconds>43200)throw Error('Choose a duration between 15 seconds and 12 hours.');}
 if(infer){if(!prompt)throw Error('Describe your music first.');}
 else{data.preset=$('preset').value;data.instruments=Object.keys(controls).filter(k=>controls[k].check.checked);data.nature_layers=chosenNature();data.nature=Object.keys(data.nature_layers)[0]||'none';data.gains=Object.fromEntries(data.instruments.map(k=>[k,Number(controls[k].slider.value)]));if(!data.instruments.length&&data.nature==='none')throw Error('Select at least one instrument or nature sound.');}
 const woodwind=(!infer&&data.instruments.some(x=>["clarinet","oboe","bassoon"].includes(x)))||(infer&&/\b(clarinet|oboe|bassoon)\b/i.test(prompt));
 if(woodwind&&(deployedVersion!=="V33-woodwind-beta"||!["fast","studio"].includes(data.engine)||data.seconds*data.variations>180||regenerationSelection||extensionSelection))throw Error("Experimental woodwinds require V33, Fast/Studio, max 3 total minutes, no extension/regeneration.");
 const natureOnly=!infer&&data.instruments.length===0&&data.nature!=='none';
 if(preview){data.seconds=60;data.variations=natureOnly?1:3;}
 if(!infer&&!natureOnly&&["fast","studio"].includes(data.engine)){data.seed=$("composition-seed").value.trim();data.seed_variation=preview?1:Number($("seed-variation").value);if(data.seed_variation!==1&&(!data.seed||data.variations!==1))throw Error("Selected variation requires a fixed seed and one output.");if(data.seed&&!/^[A-Za-z0-9]{1,48}$/.test(data.seed))throw Error("Seed must contain 1–48 ASCII letters or digits.");}
 const limit=natureOnly?43200:['fast','studio'].includes(data.engine)?3600:900;
 if(data.seconds>limit)throw Error('Choose up to '+limit/60+' minutes for this mode.');
 if(![1,2,3].includes(data.variations)||natureOnly&&data.variations!==1)throw Error('Choose a valid variation count.');
 if(data.seconds*data.variations>limit)throw Error('Combined duration must not exceed '+limit/60+' minutes.');
 if(data.seconds>900&&!['mp3','m4a'].includes(data.format))throw Error('Choose MP3 or YouTube Ready AAC for tracks longer than 15 minutes.');
 if(data.format==='wav'&&data.seconds&&data.seconds*288000>=2**32-65536)throw Error('This duration exceeds the standard WAV size limit. Choose MP3 or FLAC.');
 if(regenerationSelection&&!preview){
  const g=regenerationSelection;
  if(data.engine!=="fast"||data.format!=="flac"||data.variations!==1||data.tuning!=="standard"||data.seconds!==g.seconds||data.instruments?.length!==1||data.instruments[0]!==g.instrument||Object.keys(data.nature_layers||{}).length)throw Error("Regeneration settings changed. Restore the selected instrument and original duration or clear the selection.");
  data.regenerate={slug:g.slug,variation:g.variation,instrument:g.instrument};
 }
 if(extensionSelection&&!preview){
  if(data.format!=="flac"||data.variations!==1||data.seconds<75||data.seconds>900)throw Error("Preview extension requires one FLAC output, 1.25–15 minutes total.");
  data.extension={...extensionSelection};
 }
 return data;
}
function estimate(r){
 const natureOnly=Array.isArray(r.instruments)&&!r.instruments.length&&r.nature!=="none";
 const mode=natureOnly?"nature":r.engine;
 const count=Array.isArray(r.instruments)?r.instruments.length:null;
 const signature=[mode,r.aac_mode||'premium',r.tuning||"standard",["fast","studio"].includes(mode)?r.composition||"independent":"",count===null?"prompt":r.instruments.slice().sort().join(","),r.format,r.nature_layers?Object.keys(r.nature_layers).sort().join(","):r.nature||"inferred"].join("|");
 const minutes=r.seconds*r.variations/60;
 // Broad planning assumptions, not measured CPU benchmarks.
 const base=mode==="nature"?[2,.12,6,.7]:mode==="studio"?[3,.8,10,3]:mode==="fast"?[2,.6,8,2.5]:[4,3,10,7];
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
// Local, transparent instruction interpreter. No external AI or paid service.
function directMusic(){
 const t=$("director-prompt").value.trim().toLowerCase(), changes=[];
 if(!t){$("director-status").textContent="Enter an editing instruction.";return}
 if($("mode").value==="prompt"){$("director-status").textContent="Switch to Preset + custom mix to edit individual settings.";return}
 if(busy||submitting||pendingSlug){$("director-status").textContent="Finish the active production before editing.";return}
 const soft=/\b(softer|quieter|reduce|less|lower)\b/, strong=/\b(louder|increase|more|stronger|raise)\b/;
 const aliases={felt_piano:"felt piano|soft piano|piano",grand_piano:"grand piano|piano",flute:"flute",cello:"cello",harp:"harp",handpan:"handpan",bansuri:"bansuri|bamboo flute",singing_bowls:"singing bowls?|tibetan bowls?"};
 const setGain=(c,n)=>{c.slider.value=String(Math.max(-30,Math.min(6,Number(c.slider.value)+n)))};
 for(const clause of t.split(/[,;.!]|\band\b|\bbut\b/)){
  if(/\b(deep sleep|more peaceful|more relaxing|gentler|for sleeping)\b/.test(clause)){$("mastering").value="sleep";changes.push("Deep Sleep mastering")}
  if(/\b(luxury spa|spa mastering)\b/.test(clause)){$("mastering").value="spa";changes.push("Luxury Spa mastering")}
  if(/\b(less repetitive|more variation|independent sections)\b/.test(clause)){$("composition-engine").value="fast";$("composition-style").value="independent";changes.push("Fast Acoustic independent sections")}
  if(/\b(recurring theme|consistent theme|same motif)\b/.test(clause)){$("composition-engine").value="fast";$("composition-style").value="thematic";changes.push("Fast Acoustic recurring theme")}
  for(const [key,c] of Object.entries({...controls,...natureControls})){
   const alias=aliases[key]||key;
   if(!new RegExp("\\b(?:"+alias+")\\b").test(clause))continue;
   if(/\b(remove|without|no|exclude|mute)\b/.test(clause)){if(c.check.checked){c.check.checked=false;changes.push("Removed "+(instruments[key]||natureNames[key]))}}
   else if(/\b(add|include|enable)\b/.test(clause)){c.check.checked=true;changes.push("Added "+(instruments[key]||natureNames[key]))}
   else if(soft.test(clause)||strong.test(clause)){if(c.check.checked){setGain(c,soft.test(clause)?-3:3);changes.push((instruments[key]||natureNames[key])+" "+c.slider.value+" dB")}}
  }
 }
 refresh();$("director-status").textContent=changes.length?changes.join(" · ")+". Review settings before generating.":"No supported changes found. Try ‘reduce river’, ‘remove cello’, ‘add harp’, or ‘more variation’.";
}
function planExport(){
 const mb=Number($("target-mb").value),seconds=Math.round(Number($("duration").value)*60);
 if(!Number.isFinite(mb)||mb<=0||!Number.isFinite(seconds)||seconds<15){$("target-status").textContent="Enter a positive target size and valid duration.";return}
 const choices=[["mp3","premium",320,"Premium MP3"],["m4a","premium",256,"Premium AAC"],["m4a","balanced",192,"Balanced AAC"]];
 const fitting=choices.filter(x=>seconds*x[2]/8000*1.03<=mb);
 const pick=fitting[0];
 if(!pick){$("target-status").textContent="No predictable supported bitrate fits this target. Balanced AAC is approximately "+(seconds*192/8000).toFixed(1)+" MB before overhead. Shorten duration or increase budget; no aggressive compression applied.";return}
 $("target-status").textContent=pick[3]+" fits the planning budget at approximately "+(seconds*pick[2]/8000).toFixed(1)+" MB per track. This is an estimate, not a hard cap.";
 $("format").value=pick[0];$("aac-mode").value=pick[1];refresh();
}
$("director-apply").addEventListener("click",directMusic);
$("target-apply").addEventListener("click",planExport);
function refresh(){
 const infer=$('mode').value==='prompt';$('mix-section').hidden=infer;$('preset').disabled=infer;$('infer-duration-row').hidden=true;$('duration').disabled=false;
 const natureOnly=!infer&&!Object.values(controls).some(c=>c.check.checked)&&Object.keys(chosenNature()).length>0;const fast=['fast','studio'].includes($('composition-engine').value);
 $('aac-mode-row').hidden=$('format').value!=='m4a';$('aac-mode').disabled=$('format').value!=='m4a';
 $('tuning-row').hidden=natureOnly;$('tuning').disabled=natureOnly;if(natureOnly)$('tuning').value='standard';
 $('seed-row').hidden=infer||natureOnly||!fast;$('composition-seed').disabled=infer||natureOnly||!fast;
 $('composition-style-row').hidden=natureOnly||!fast;$('composition-style').disabled=natureOnly||!fast;
 $('duration').max=natureOnly?720:fast?60:15;
 $('compute-plan').textContent=natureOnly||fast?'CPU · no GPU requested':'GPU · Aria neural composition';
 $('variations').disabled=natureOnly;
 if(natureOnly)$('variations').value='1';
 $('duration-limit').textContent=natureOnly?'Nature-only: up to 12 hours (experimental beyond 60 minutes). Long MP3 files require direct download.':fast?'Acoustic engines: up to 60 minutes combined across variations.':'Aria: up to 15 minutes combined across variations.';
 for(const c of Object.values(natureControls)){c.slider.disabled=!c.check.checked;c.value.textContent=(Number(c.slider.value)>0?'+':'')+c.slider.value+' dB'}
 for(const c of Object.values(controls)){c.slider.disabled=!c.check.checked;c.value.textContent=(Number(c.slider.value)>0?'+':'')+c.slider.value+' dB'}
 try{const r=buildRequest();const e=estimate(r);$('file-size-estimate').textContent=r.format==='m4a'&&r.aac_mode==='vbr'?'Quality-driven VBR · illustrative size at 192 kbps: '+(r.seconds*192/8000).toFixed(1)+' MB per variation; actual size varies and may exceed premium.':['mp3','m4a'].includes(r.format)?'Approx. '+(r.seconds*(r.format==='m4a'?(r.aac_mode==='balanced'?192:256):320)/8000).toFixed(1)+' MB per variation · '+(r.format==='m4a'?(r.aac_mode==='balanced'?'AAC-LC 192 kbps':'AAC-LC 256 kbps'):'MP3 320 kbps'):'Lossless size varies with the audio';$('estimate-time').textContent=estimateLabel(e);$('estimate-basis').textContent=e.source+' · Includes typical setup allowance; queue delays can extend it.';$('summary').textContent=(r.preset?presets[r.preset][0]:'Prompt-based configuration')+' · '+(r.seconds?r.seconds/60+' min':'duration inferred')+' · '+(['fast','studio'].includes(r.engine)?(r.engine==='studio'?'Studio Premium · ':'Fast acoustic · ')+(r.composition==='thematic'?'Recurring theme':'Independent sections'):'Aria AI')+' · '+r.variations+' variation(s) · '+r.format.toUpperCase()+(r.instruments?' · '+r.instruments.map(k=>instruments[k]).join(', ')+' · '+(Object.keys(r.nature_layers||{}).map(k=>natureNames[k]).join(' + ')||'No nature ambience'):'');}
 catch(e){$('file-size-estimate').textContent='—';$('summary').textContent=e.message;$('estimate-time').textContent='—';$('estimate-basis').textContent='Choose valid production settings.'}
}

const API="https://auraluna-api.dhanushmanoharan1996.workers.dev";
let key="",busy=false,timer=null,active="",attempt=0;
const historyKey="auraluna-v9-jobs";
function history(){try{return JSON.parse(localStorage.getItem(historyKey)||"[]").filter(x=>/^auraluna-[a-f0-9]{32}$/.test(x.slug))}catch{return []}}
let pendingMeta=null, pendingSlug="", submitting=false;
function lock(){busy=true;$("preview").disabled=true;$("generate").disabled=true;$("generate").textContent=submitting?"Submitting production…":"Production in progress"}
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
const terminalStates=new Set(["COMPLETE","COMPLETED","SUCCESS","ERROR","FAILED","CANCELLED","CANCELED","CANCEL_ACKNOWLEDGED"]);
function updateSaved(slug,patch){try{const rows=history();localStorage.setItem(historyKey,JSON.stringify(rows.map(x=>x.slug===slug?{...x,...patch}:x)))}catch{}renderHistory()}
function showProgress(text,running=false){$("production-status").textContent=text;$("production-panel").hidden=false;$("production-progress").hidden=!running;$("check-status").disabled=pollInFlight||!active||!key;}
function elapsed(){if(!selectedStarted||(!clockRunning&&!selectedEnd))return "—";const n=Math.max(0,Math.floor(((selectedEnd||Date.now())-selectedStarted)/1000));return Math.floor(n/60)+"m "+String(n%60).padStart(2,"0")+"s"}
function updateClock(){const spent=selectedStarted?((selectedEnd||Date.now())-selectedStarted)/60000:0;$("remaining-estimate").textContent=selectedEnd?"Finished / stopped":!clockRunning||!selectedEstimate?"—":spent>=selectedEstimate.high?"Taking longer than estimated":Math.max(0,Math.floor(selectedEstimate.low-spent))+"–"+Math.max(1,Math.ceil(selectedEstimate.high-spent))+" min (approx.)";$("elapsed-time").textContent=elapsed();$("last-check").textContent=lastChecked?new Date(lastChecked).toLocaleTimeString():"—"}
setInterval(updateClock,1000);
function remember(slug){try{localStorage.setItem(historyKey,JSON.stringify([{slug,...(history().find(x=>x.slug===slug)||{}),...(pendingMeta||{})},...history().filter(x=>x.slug!==slug)]))}catch{ $("library-status").textContent="Browser storage unavailable or full. Export your catalogue to preserve it." }renderHistory()}
function restoreSettings(r){
 if(busy||submitting||pendingSlug)return;
 if(!r||typeof r!=="object")return;
 extensionSelection=null;regenerationSelection=null;$("extension-status").textContent="No preview selected.";
 const choose=(id,value)=>{if([...$(id).options].some(o=>o.value===String(value)))$(id).value=String(value)};
 choose("mode",Array.isArray(r.instruments)?"manual":"prompt");
 choose("preset",r.preset);choose("composition-engine",r.engine);choose("composition-style",r.composition);choose("tuning",r.tuning);choose("format",r.format);choose("mastering",r.mastering||"original");choose("aac-mode",r.aac_mode);
 $("prompt").value=typeof r.prompt==="string"?r.prompt.slice(0,2000):"";
 if(Array.isArray(r.instruments)){
  for(const [k,c] of Object.entries(controls)){c.check.checked=r.instruments.includes(k);c.slider.value=Number.isFinite(r.gains?.[k])?Math.max(-30,Math.min(6,r.gains[k])):0;}
  for(const [k,c] of Object.entries(natureControls)){c.check.checked=Object.hasOwn(r.nature_layers||{},k);c.slider.value=Number.isFinite(r.nature_layers?.[k])?Math.max(-30,Math.min(6,r.nature_layers[k])):0;}
 }
 $("composition-seed").value=typeof r.seed==="string"?r.seed:"";$("seed-variation").value=String(r.seed_variation||1);$("variations").value="1";newJob();refresh();
 $("duration").scrollIntoView({behavior:"smooth",block:"center"});$("duration").focus({preventScroll:true});
 $("library-status").textContent="Musical settings restored. Choose your full duration and generate a new composition.";
}
function renderHistory(){
 const el=$("history");el.replaceChildren();
 const query=$("library-search").value.trim().toLowerCase(),filter=$("library-filter").value;
 const all=history(),rows=all.filter(x=>(!query||[x.title,x.slug,x.engine,x.composition,x.format,x.notes].some(v=>String(v||"").toLowerCase().includes(query)))&&(filter==="all"||filter==="ready"&&["COMPLETE","COMPLETED","SUCCESS"].includes(x.state)||filter==="favorites"&&x.favorite));
 $("library-count").textContent=rows.length+" of "+all.length+" productions";
 if(!rows.length){el.textContent=all.length?"No matching productions.":"Your generated music will appear here.";return}
 for(const {slug,title,date,state,seconds,format,compute,favorite,notes,requestSettings} of rows){
  const item=document.createElement("div");item.className="v9-saved";
  const info=document.createElement("div"),name=document.createElement("strong"),meta=document.createElement("p"),button=document.createElement("button");
  name.textContent=title||"Saved track";
  const labels={COMPLETE:"Ready",COMPLETED:"Ready",SUCCESS:"Ready",RUNNING:"Creating",QUEUED:"Queued",ERROR:"Failed",FAILED:"Failed",CANCELED:"Canceled",CANCELLED:"Canceled"};
  meta.textContent=[date?new Date(date).toLocaleString():"",seconds?"Requested: "+durationLabel(seconds):"Requested duration not recorded",format?.toUpperCase(),compute?compute+" requested":"",labels[state]||"Check status"].filter(Boolean).join(" · ");
  info.append(name,meta);button.type="button";button.className="v9-secondary";button.textContent=["COMPLETE","COMPLETED","SUCCESS"].includes(state)?"Listen & download":"Open";button.disabled=submitting||Boolean(pendingSlug&&pendingSlug!==slug);button.onclick=()=>watch(slug);const actions=document.createElement("div");actions.className="v9-actions";
  const star=document.createElement("button"),edit=document.createElement("button");star.type=edit.type="button";star.className=edit.className="v9-secondary";star.textContent=favorite?"★ Saved":"☆ Favourite";star.setAttribute("aria-pressed",String(Boolean(favorite)));star.onclick=()=>updateSaved(slug,{favorite:!favorite});
  edit.textContent="Edit title & notes";edit.onclick=()=>{const titleInput=document.createElement("input"),noteInput=document.createElement("textarea"),save=document.createElement("button"),cancel=document.createElement("button");titleInput.value=title||"Saved track";titleInput.maxLength=160;titleInput.setAttribute("aria-label","Production title");noteInput.value=notes||"";noteInput.maxLength=2000;noteInput.setAttribute("aria-label","Production notes");save.type=cancel.type="button";save.textContent="Save";cancel.textContent="Cancel";save.onclick=()=>updateSaved(slug,{title:titleInput.value.trim()||"Saved track",notes:noteInput.value.trim()});cancel.onclick=renderHistory;info.replaceChildren(titleInput,noteInput,save,cancel);};
  if(notes){const note=document.createElement("p");note.textContent=notes;info.append(note)}
  actions.append(button,star,edit);if(requestSettings){const reuse=document.createElement("button");reuse.type="button";reuse.className="v9-secondary";reuse.textContent="Reuse musical settings";reuse.disabled=busy||submitting||Boolean(pendingSlug);reuse.onclick=()=>restoreSettings(requestSettings);actions.append(reuse);}item.append(info,actions);el.append(item);
 }
}
$("library-search").addEventListener("input",renderHistory);
$("library-filter").addEventListener("change",renderHistory);
$("library-export").onclick=()=>{
 const rows=history();const blob=new Blob([JSON.stringify({schema:"auraluna-catalogue-v1",productions:rows},null,2)],{type:"application/json"});const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="auraluna-music-catalogue.json";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 $("library-status").textContent="Catalogue backup requested. Audio files are not included.";
};
$("library-import").onchange=async()=>{
 const input=$("library-import");try{
 const file=input.files[0];if(!file)return;if(file.size>20*1024*1024)throw Error("Catalogue exceeds 20 MB");
 const data=JSON.parse(await file.text());if(data.schema!=="auraluna-catalogue-v1"||!Array.isArray(data.productions))throw Error("Invalid catalogue backup");
 const clean=data.productions.filter(x=>x&&typeof x.slug==="string"&&/^auraluna-[a-f0-9]{32}$/.test(x.slug)).map(x=>({slug:x.slug,title:typeof x.title==="string"?x.title.slice(0,160):"Saved track",notes:typeof x.notes==="string"?x.notes.slice(0,2000):"",favorite:x.favorite===true,date:typeof x.date==="string"&&Number.isFinite(Date.parse(x.date))?x.date:null,seconds:Number.isFinite(x.seconds)&&x.seconds>0?x.seconds:null,format:["mp3","m4a","wav","flac"].includes(x.format)?x.format:null,engine:["aria","fast","studio"].includes(x.engine)?x.engine:null,composition:["independent","thematic"].includes(x.composition)?x.composition:null,variations:[1,2,3].includes(x.variations)?x.variations:null,state:terminalStates.has(x.state)?x.state:"UNVERIFIED"}));
 const merged=new Map(history().map(x=>[x.slug,x]));let added=0;for(const x of clean)if(!merged.has(x.slug)){merged.set(x.slug,x);added++}
 localStorage.setItem(historyKey,JSON.stringify([...merged.values()]));$("library-status").textContent=added+" productions restored. Remote audio availability must be checked.";renderHistory();
 }catch(e){$("library-status").textContent=e.message}finally{input.value=""}
};
async function api(path,options={}){
 if(!key)throw Error("Enter your Auraluna access key and connect first.");
 const r=await fetch(API+path,{cache:"no-store",...options,headers:{Authorization:"Bearer "+key,...options.headers}});
 const d=await r.json();if(!r.ok){const e=new Error(d.error||"Backend HTTP "+r.status);e.status=r.status;throw e;}return d;
}
function status(s){$("cloud-status").textContent=s}
function unlock(){if(submitting||pendingSlug){lock();return}busy=false;$("preview").disabled=!key;$("generate").disabled=!key;$("generate").textContent="Generate Music"}
function release(slug){if(pendingSlug===slug)pendingSlug="";unlock()}
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
  deployedVersion=backendVersion;
  status(backendVersion==="V21-aac-balanced"?"Connected · V21 AAC balanced":backendVersion==="V20-aac-vbr"?"Connected · V20 AAC VBR":backendVersion==="V19-youtube-ready"?"Connected · V19 YouTube Ready":backendVersion==="V18-long-nature"?"Connected · V18 extended nature":backendVersion==="V17-tuning"?"Connected · V17 custom tuning":backendVersion==="V16-nature-mixer"?"Connected · V16 nature mixer":backendVersion==="V15-composition-styles"?"Connected · V15 composition styles":backendVersion==="V14-cpu-routing"?"Connected · V14 · update Worker for composition styles":backendVersion?"Connected · "+backendVersion+" · CPU routing not confirmed; update Worker if needed.":"Connected · Backend version unavailable");unlock();
  const latest=history().find(x=>x.state&&x.state!=="UNVERIFIED"&&!terminalStates.has(x.state))||history().find(x=>terminalStates.has(x.state));if(latest){if(latest.state&&!terminalStates.has(latest.state)){pendingSlug=latest.slug;lock()}await watch(latest.slug)}
 }catch(e){if(version!==connectionVersion)return;key="";if(e.status===401||e.status===403)forgetKey();$("credentials").hidden=false;status(e.message)}
 finally{if(version===connectionVersion)$("connect").disabled=false}
}
$("connect").onclick=()=>connect($("access-key").value.trim(),$("remember-device").checked);
$("disconnect").onclick=()=>{if(submitting){showProgress("Submission is still being confirmed. Disconnect after the request returns.",true);return}++connectionVersion;forgetKey();key="";clearTimeout(timer);++monitorVersion;active="";clockRunning=false;$("production-panel").hidden=true;$("credentials").hidden=false;$("connect").disabled=false;$("generate").disabled=true;$("generate").textContent="Generate Music";status("Disconnected");pendingSlug="";busy=false;$("players").replaceChildren()};
// Waveforms are measured from decoded output, never fabricated.
// Bound decoding to short preview files to avoid large PCM allocations.
async function previewPeaks(url){
 const AudioCtx=window.AudioContext||window.webkitAudioContext;
 if(!AudioCtx)throw Error("Waveform decoding is unavailable in this browser");
 const context=new AudioCtx();
 try{
  const response=await fetch(url);
  if(!response.ok)throw Error("Preview could not be read");
  const encoded=await response.arrayBuffer();
  if(encoded.byteLength>40*1024*1024)throw Error("Preview is too large for waveform analysis");
  const audio=await context.decodeAudioData(encoded);
  if(audio.duration>95)throw Error("Waveform analysis is limited to short previews");
  const bins=300,peaks=new Float32Array(bins);
  for(let c=0;c<audio.numberOfChannels;c++){
   const samples=audio.getChannelData(c);
   for(let i=0;i<samples.length;i++){
    const bin=Math.min(bins-1,Math.floor(i*bins/samples.length));
    peaks[bin]=Math.max(peaks[bin],Math.abs(samples[i]));
   }
  }
  return peaks;
 }finally{await context.close().catch(()=>{})}
}
function mountPreviewWaveform(row,player){
 const panel=document.createElement("div");panel.className="v9-waveform";
 const canvas=document.createElement("canvas");canvas.width=900;canvas.height=108;canvas.setAttribute("aria-hidden","true");
 const label=document.createElement("p");label.className="hint";label.textContent="Waveform: load preview to analyse actual audio.";
 const seek=document.createElement("input");seek.type="range";seek.min="0";seek.max="1000";seek.step="1";seek.value="0";seek.disabled=true;seek.setAttribute("aria-label","Seek preview position");
 panel.append(canvas,seek,label);player.after(panel);
 let peaks=null;
 function draw(){
  const ctx=canvas.getContext("2d");if(!ctx)return;
  const w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);
  ctx.fillStyle="#22252c";ctx.fillRect(0,0,w,h);
  if(!peaks)return;
  const progress=Number.isFinite(player.duration)&&player.duration>0?player.currentTime/player.duration:0;
  const step=w/peaks.length;
  for(let i=0;i<peaks.length;i++){
   const amp=Math.max(1,Math.min(1,peaks[i])*(h/2-4));
   ctx.fillStyle=i/peaks.length<=progress?"#e16172":"#9ca6b3";
   ctx.fillRect(i*step,(h-2*amp)/2,Math.max(1,step-1),amp*2);
  }
 }
 function jump(value){
  if(Number.isFinite(player.duration)&&player.duration>0)player.currentTime=Math.max(0,Math.min(1,value))*player.duration;
 }
 seek.addEventListener("input",()=>jump(Number(seek.value)/1000));
 canvas.addEventListener("click",e=>{if(peaks){const rect=canvas.getBoundingClientRect();if(rect.width)jump((e.clientX-rect.left)/rect.width)}});
 player.addEventListener("timeupdate",()=>{if(Number.isFinite(player.duration)&&player.duration>0){seek.value=String(Math.round(player.currentTime/player.duration*1000));draw()}});
 draw();
 return async url=>{
  label.textContent="Analysing decoded preview…";
  try{peaks=await previewPeaks(url);if(!row.isConnected)return;seek.disabled=false;label.textContent="Measured peak amplitude · common full-scale reference · click or use the slider to seek.";draw()}
  catch(e){if(row.isConnected)label.textContent="Waveform unavailable: "+e.message}
 };
}
// Short-production premaster mixer; bounded decoded memory, synchronized Web Audio transport.
// Local archive stores original encoded bytes, not credentials or signed URLs.
function archiveDB(){
 return new Promise((resolve,reject)=>{const q=indexedDB.open("auraluna-audio-archive",1);q.onupgradeneeded=()=>q.result.createObjectStore("audio",{keyPath:"id"});q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);q.onblocked=()=>reject(Error("Archive database is blocked by another tab"));});
}
async function archiveOp(mode,action){
 const db=await archiveDB();try{return await new Promise((resolve,reject)=>{const tx=db.transaction("audio",mode),req=action(tx.objectStore("audio"));tx.oncomplete=()=>resolve(req.result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error("Archive transaction aborted"));});}finally{db.close()}
}
function saveBlob(blob,name){
 const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
async function renderArchive(){
 const list=$("archive-list");list.replaceChildren();
 try{
  const entries=await archiveOp("readonly",s=>s.getAllKeys());
  if(!entries.length){list.textContent="No locally archived audio.";return}
  for(const id of entries){
   const row=document.createElement("div");row.className="v9-saved";const label=document.createElement("span");label.textContent=id.replace("/results/"," · ");row.append(label);
   const download=document.createElement("button"),remove=document.createElement("button");
   download.type=remove.type="button";download.textContent="Download";remove.textContent="Remove";
   download.onclick=async()=>{try{const e=await archiveOp("readonly",s=>s.get(id));if(!e)throw Error("Archive entry missing");saveBlob(e.blob,e.name)}catch(e){$("archive-status").textContent=e.message}};
   remove.onclick=async()=>{if(!confirm("Remove this local audio copy?"))return;try{await archiveOp("readwrite",s=>s.delete(id));await renderArchive()}catch(e){$("archive-status").textContent=e.message}};
   row.append(download,remove);list.append(row);
  }
 }catch(e){list.textContent="Local archive unavailable: "+e.message}
}
function stemHeadroom(tracks){return Math.min(1,.85/Math.max(.000001,tracks.reduce((sum,t)=>sum+t.peak,0)))}
async function exportStemMix(tracks,duration,rate){
 const n=Math.floor(duration*rate),ctx=new OfflineAudioContext(2,n,rate),solo=tracks.some(t=>t.solo),master=ctx.createGain();master.gain.value=stemHeadroom(tracks);master.connect(ctx.destination);
 for(const t of tracks){if(t.mute||(solo&&!t.solo))continue;const source=ctx.createBufferSource(),gain=ctx.createGain();source.buffer=t.buffer;gain.gain.value=10**(t.db/20);source.connect(gain);gain.connect(master);source.start(0)}
 const mix=await ctx.startRendering(),bytes=new ArrayBuffer(44+n*6),v=new DataView(bytes);
 const tag=(p,s)=>{for(let i=0;i<s.length;i++)v.setUint8(p+i,s.charCodeAt(i))};
 tag(0,"RIFF");v.setUint32(4,bytes.byteLength-8,true);tag(8,"WAVE");tag(12,"fmt ");v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,2,true);v.setUint32(24,rate,true);v.setUint32(28,rate*6,true);v.setUint16(32,6,true);v.setUint16(34,24,true);tag(36,"data");v.setUint32(40,n*6,true);
 const channels=[mix.getChannelData(0),mix.getChannelData(1)];let p=44,peak=0;
 for(let i=0;i<n;i++)for(let c=0;c<2;c++){const x=channels[c][i];if(!Number.isFinite(x))throw Error("Invalid mix sample");peak=Math.max(peak,Math.abs(x));const q=Math.round(Math.max(-1,Math.min(1-1/8388608,x))*8388608);v.setUint8(p++,q&255);v.setUint8(p++,q>>8&255);v.setUint8(p++,q>>16&255)}
 if(peak>1)throw Error("Mix exceeds available headroom");if(peak<1e-7)throw Error("Mix is silent; unmute a track first");
 return new Blob([bytes],{type:"audio/wav"});
}

async function renderCloudArchive(){
 const list=$("cloud-archive-list"),status=$("cloud-archive-status");list.replaceChildren();
 if(!key){status.textContent="Connect to access the private cloud archive.";return}
 try{
  const usage=await api("/archive/usage");const gb=n=>(n/1e9).toFixed(2)+" GB";const meter=$("cloud-archive-meter");meter.value=Math.min(usage.bytes,usage.limit);meter.max=usage.limit;$("cloud-archive-usage").textContent=gb(usage.bytes)+" used of "+gb(usage.limit)+" safety limit · "+gb(usage.remaining)+" available"+(usage.bytes>=usage.warning?" · Storage warning: download and remove unneeded tracks.":"");
  let cursor=null,count=0;
  do{
   const page=await api("/archive/list"+(cursor?"?cursor="+encodeURIComponent(cursor):""));
   for(const e of page.entries||[]){
    if(!e.slug||!e.name)continue;count++;
    const row=document.createElement("div");row.className="v9-saved";const label=document.createElement("span");label.textContent=e.slug+" · "+e.name.split("/").pop()+" · "+Math.round(Number(e.size)/1048576)+" MiB";row.append(label);
    for(const [kind,title] of [["audio","Download audio"],["completed","Quality report"],["licences","Licences"]]){
     const b=document.createElement("button");b.type="button";b.textContent=title;
     b.onclick=async()=>{b.disabled=true;try{
      const url=API+"/archive/file?slug="+encodeURIComponent(e.slug)+"&file="+encodeURIComponent(e.name)+"&kind="+kind;
      const response=await fetch(url,{headers:{Authorization:"Bearer "+key}});if(!response.ok)throw Error("Archive HTTP "+response.status);
      const filename=kind==="audio"?e.name.split("/").pop():kind+".json";
      if(kind==="audio"&&Number(e.size)>250*1024*1024){
       if(!window.showSaveFilePicker){await response.body?.cancel();throw Error("Large archive downloads require a browser supporting streaming file saves (Chrome/Edge).")}
       // The file picker must be invoked before the first await in a user gesture.
       await response.body?.cancel();throw Error("Use the Stream large audio button.")
      }
      saveBlob(await response.blob(),filename);
     }catch(err){status.textContent=err.message}finally{b.disabled=false}};
     if(kind==="audio"&&Number(e.size)>250*1024*1024){b.textContent="Stream large audio";b.onclick=async()=>{let writer;try{
      if(!window.showSaveFilePicker)throw Error("Large downloads require Chrome or Edge streaming file support.");
      const handle=await window.showSaveFilePicker({suggestedName:e.name.split("/").pop()});
      const response=await fetch(API+"/archive/file?slug="+encodeURIComponent(e.slug)+"&file="+encodeURIComponent(e.name),{headers:{Authorization:"Bearer "+key}});
      if(!response.ok)throw Error("Archive HTTP "+response.status);writer=await handle.createWritable();await response.body.pipeTo(writer);status.textContent="Archived audio downloaded.";
     }catch(err){await writer?.abort().catch(()=>{});status.textContent=err.message}}}
     row.append(b)
    }
    const remove=document.createElement("button");remove.type="button";remove.textContent="Delete cloud copy";remove.onclick=async()=>{if(!confirm("Permanently delete this cloud copy and its reports? Ensure you have downloaded a backup. Local copies and Kaggle outputs are unaffected."))return;remove.disabled=true;try{await api("/archive/delete?slug="+encodeURIComponent(e.slug)+"&file="+encodeURIComponent(e.name),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({confirm:e.name})});await renderCloudArchive()}catch(err){status.textContent=err.message;remove.disabled=false}};row.append(remove);
    list.append(row)
   }
   cursor=page.cursor;
  }while(cursor&&count<500);
  status.textContent=count?count+" archived productions listed.":"No cloud-archived audio.";
 }catch(e){status.textContent=e.message}
}

function mountStemEditor(row,slug,files,canRegenerate=false){
 const panel=document.createElement("details"),heading=document.createElement("summary");heading.textContent="Multitrack instrument editor (beta)";panel.append(heading);
 const note=document.createElement("p");note.className="hint";note.textContent="Dry acoustic stems before shared mastering. Nature and room effects are not included. Up to 60 seconds.";panel.append(note);
 const load=document.createElement("button");load.type="button";load.textContent="Load instrument tracks";panel.append(load);
 const status=document.createElement("p");status.setAttribute("role","status");panel.append(status);
 row.append(panel);let ctx,tracks=[],sources=[],start=0,offset=0,playing=false,duration=0,raf=0,starting=false;
 const stop=()=>{if(playing){offset=Math.max(0,Math.min(duration,offset+ctx.currentTime-start));playing=false}for(const s of sources){try{s.stop();s.disconnect()}catch{}}sources=[];for(const t of tracks){t.gain?.disconnect();t.gain=null}cancelAnimationFrame(raf)};
 const observer=new MutationObserver(()=>{if(!row.isConnected){stop();ctx?.close().catch(()=>{});observer.disconnect()}});observer.observe($("players"),{childList:true,subtree:true});
 load.onclick=async()=>{
  load.disabled=true;status.textContent="Loading lossless tracks…";
  try{
   ctx=new AudioContext({sampleRate:48000});await ctx.resume();
   for(const file of files){
    const r=await fetch(API+"/file?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(file.name),{headers:{Authorization:"Bearer "+key}});
    if(!r.ok)throw Error("Track HTTP "+r.status);
    const length=Number(r.headers.get("content-length")||0);if(length>30*1024*1024)throw Error("Track exceeds editor limit");
    const blob=await r.blob();if(blob.size>30*1024*1024)throw Error("Track exceeds editor limit");
    let b;try{b=await ctx.decodeAudioData(await blob.arrayBuffer())}catch{throw Error("This browser cannot decode the lossless FLAC stem. Try current Chrome or Edge.")}
    if(b.duration>61||b.numberOfChannels!==2)throw Error("Invalid editor track");
    if(!row.isConnected)throw Error("Track selection changed");
    let peak=0;for(let c=0;c<b.numberOfChannels;c++)for(const x of b.getChannelData(c))peak=Math.max(peak,Math.abs(x));
    tracks.push({name:file.name.match(/stem_(.+)\.flac$/)[1],buffer:b,peak,db:0,mute:false,solo:false,gain:null});
   }
   duration=Math.min(...tracks.map(t=>t.buffer.duration));if(!Number.isFinite(duration)||duration<=0||tracks.some(t=>Math.abs(t.buffer.duration-duration)>.05))throw Error("Stem durations do not match");const master=ctx.createGain();master.gain.value=stemHeadroom(tracks);master.connect(ctx.destination);
   const update=()=>{const solo=tracks.some(t=>t.solo);for(const t of tracks)if(t.gain)t.gain.gain.setTargetAtTime(t.mute||(solo&&!t.solo)?0:10**(t.db/20),ctx.currentTime,.02)};
   const transport=document.createElement("div");transport.className="v9-actions";
   const play=document.createElement("button"),pause=document.createElement("button"),reset=document.createElement("button"),seek=document.createElement("input");
   for(const b of [play,pause,reset])b.type="button";
   play.textContent="Play mix";pause.textContent="Pause";reset.textContent="Restart";seek.type="range";seek.min=0;seek.max=duration;seek.step=.1;seek.value=0;seek.setAttribute("aria-label","Timeline position");
   const tick=()=>{if(!playing)return;const p=offset+ctx.currentTime-start;seek.value=Math.min(duration,p);if(p>=duration){stop();offset=0;seek.value=0;return}raf=requestAnimationFrame(tick)};
   const begin=async()=>{if(playing||starting)return;starting=true;try{if(offset>=duration)offset=0;await ctx.resume();if(!row.isConnected)return;for(const a of $("players").querySelectorAll("audio"))a.pause();start=ctx.currentTime+.03;for(const t of tracks){const s=ctx.createBufferSource();s.buffer=t.buffer;t.gain=ctx.createGain();s.connect(t.gain);t.gain.connect(master);s.start(start,offset);sources.push(s)}playing=true;update();tick()}catch(e){stop();status.textContent="Playback failed: "+e.message}finally{starting=false}};
   play.onclick=()=>void begin();pause.onclick=stop;reset.onclick=()=>{stop();offset=0;seek.value=0};seek.oninput=()=>{const resume=playing;stop();offset=Number(seek.value);if(resume)void begin()};
   const exportMix=document.createElement("button");exportMix.type="button";exportMix.textContent="Export edited mix · 24-bit WAV";exportMix.onclick=async()=>{exportMix.disabled=true;try{const blob=await exportStemMix(tracks,duration,ctx.sampleRate);saveBlob(blob,slug+"-edited-mix.wav");status.textContent="Edited dry mix exported at "+ctx.sampleRate+" Hz."}catch(e){status.textContent=e.message}finally{exportMix.disabled=false}};
   transport.append(play,pause,reset,exportMix);panel.append(transport,seek);
   for(const t of tracks){const lane=document.createElement("div");lane.className="v9-track";const label=document.createElement("strong");label.textContent=t.name.replaceAll("_"," ");const vol=document.createElement("input");vol.type="range";vol.min=-30;vol.max=0;vol.step=1;vol.value=0;vol.setAttribute("aria-label",t.name+" volume");const mute=document.createElement("button"),solo=document.createElement("button");for(const b of [mute,solo]){b.type="button";b.setAttribute("aria-pressed","false")}mute.textContent="Mute";solo.textContent="Solo";vol.oninput=()=>{t.db=Number(vol.value);update()};mute.onclick=()=>{t.mute=!t.mute;mute.setAttribute("aria-pressed",String(t.mute));update()};solo.onclick=()=>{t.solo=!t.solo;solo.setAttribute("aria-pressed",String(t.solo));update()};lane.append(label,vol,mute,solo);if(canRegenerate&&!["clarinet","oboe","bassoon"].includes(t.name)){const regen=document.createElement("button");regen.type="button";regen.textContent="Regenerate";regen.onclick=()=>{if(busy||submitting||pendingSlug){status.textContent="Finish the active production first.";return}const saved=history().find(x=>x.slug===slug);if(!saved?.seconds||saved.seconds>60){status.textContent="Original duration not available.";return}stop();const settings=saved.requestSettings||{};restoreSettings({...settings,engine:"fast",instruments:[t.name],nature_layers:{},gains:{[t.name]:settings.gains?.[t.name]||0},format:"flac",variations:1,tuning:"standard",seed:"",seed_variation:1,mastering:"original"});$("duration").value=String(saved.seconds/60);regenerationSelection={slug,variation:Number(files[0].name.match(/variation_(\d+)/)?.[1]||1),instrument:t.name,seconds:saved.seconds};$("extension-status").textContent="Regenerate "+t.name+" only. Other dry stems preserved. Press Generate Music to submit.";refresh()};lane.append(regen)}panel.append(lane)}
   status.textContent=tracks.length+" tracks loaded. Preview and exported dry mix use matching peak-based headroom.";
   load.hidden=true;
  }catch(e){stop();await ctx?.close().catch(()=>{});tracks=[];status.textContent=e.message;load.disabled=false}
 };
}
async function addFile(slug,name,files=[]){
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
 row.append(h,meta,message,player,download,retry);
 if(saved?.preview&&["fast","studio"].includes(saved.requestSettings?.engine)&&saved.requestSettings?.seed&&saved.requestSettings?.instruments?.length){const select=document.createElement("button");select.type="button";select.className="v9-secondary";select.textContent="Use this preview’s musical identity";select.onclick=()=>{if(busy||submitting||pendingSlug){message.textContent="Finish the active production first.";return}restoreSettings({...saved.requestSettings,seed_variation:Number(name.match(/variation_(\d+)/)?.[1]||1)});message.textContent="Selected variation restored. Choose a longer duration; the arrangement will evolve, not reproduce the exact preview audio.";};row.append(select);}

 if(saved?.preview&&saved.seconds===60&&saved.requestSettings&&/\.(wav|flac)$/i.test(name)){
  const extend=document.createElement("button");extend.type="button";extend.className="v9-secondary";extend.textContent="Extend this exact lossless preview";
  extend.onclick=()=>{
   if(busy||submitting||pendingSlug){message.textContent="Finish the active production first.";return}
   const variation=Number(name.match(/variation_(\d+)/)?.[1]||1);
   const settings=saved.requestSettings;
   restoreSettings({...settings,seed_variation:settings.seed?variation:1,format:"flac",variations:1});
   extensionSelection={slug,variation,format:name.split(".").pop().toLowerCase()};
   $("duration").value="5";$("format").value="flac";$("variations").value="1";
   $("extension-status").textContent="Selected variation "+variation+" · first 60 seconds retained exactly in PCM; new music follows at the existing fade. Choose 1.25–15 minutes total.";
   refresh();
  };row.append(extend);
 }
 $("players").append(row);
 const stemFiles=files.filter(f=>f.name.startsWith(name.replace(/music\.[^.]+$/,"stem_"))&&f.name.endsWith(".flac"));
 if(stemFiles.length)mountStemEditor(row,slug,stemFiles,files.some(f=>f.name===name.replace(/music\.[^.]+$/,"score.mid")));else{const hint=document.createElement("p");hint.className="hint";hint.textContent="Multitrack editor unavailable for this output. Generate one instrumental variation, 15–60 seconds, standard tuning (use Generate Music, not three-variation Preview). Nature-only tracks and cloud archive audio do not include editable stems.";row.append(hint)}
 const analyse=saved?.preview&&saved.seconds<=90?mountPreviewWaveform(row,player):null;
 let analysedURL="";
 let objectURL="",loading=null;
 const query="?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name);
 const cloud=document.createElement("button");cloud.type="button";cloud.className="v9-secondary";cloud.textContent="Save to private cloud";row.append(cloud);
 cloud.onclick=async()=>{if(!["V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion)){message.textContent="Deploy V31 and configure the private R2 archive first (includes storage safeguard).";return}if(!confirm("Save this audio and its licence and quality reports to private cloud storage? Storage charges may apply."))return;cloud.disabled=true;try{const result=await api("/archive/save"+query,{method:"POST"});message.textContent=result.alreadySaved?"Already archived.":"Saved to private cloud. Original encoded audio retained.";await renderCloudArchive()}catch(e){message.textContent=e.message}finally{cloud.disabled=false}};
 const archive=document.createElement("button");archive.type="button";archive.className="v9-secondary";archive.textContent="Save audio locally";row.append(archive);
 archive.onclick=async()=>{archive.disabled=true;try{if((saved?.seconds||0)>3600)throw Error("Download extended audio directly instead.");const u=await getAudio();const blob=await (await fetch(u)).blob();if(blob.size>250*1024*1024)throw Error("Local archive limit is 250 MiB per track; download instead.");await archiveOp("readwrite",s=>s.put({id:slug+"/"+name,name:name.split("/").pop(),blob,savedAt:Date.now()}));message.textContent="Saved in this browser. Download a backup for permanent retention.";await renderArchive()}catch(e){message.textContent="Local save failed: "+e.message}finally{archive.disabled=false}};
 async function getAudio(){
  if((saved?.seconds||0)>3600)throw Error("For extended tracks, use Download music to avoid loading the entire file into browser memory.");
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
  try{const u=await getAudio();if(!row.isConnected)return;player.src=u;player.hidden=false;message.textContent="";if(analyse&&analysedURL!==u){analysedURL=u;void analyse(u)}}
  catch(e){message.textContent=e.message;retry.hidden=false}
 }
 download.onclick=async()=>{
  download.disabled=true;download.textContent="Preparing download…";
  try{if((saved?.seconds||0)>3600){const d=await api("/download"+query);const link=document.createElement("a");link.href=d.url;link.target="_blank";link.rel="noopener noreferrer";link.textContent="Open fresh direct download link";message.replaceChildren(link);return}const u=await getAudio();const a=document.createElement("a");a.href=u;a.download=name.split("/").pop();document.body.append(a);a.click();a.remove();message.textContent="Download requested."}
  catch(e){message.textContent="Download unavailable: "+e.message;retry.hidden=false}
  finally{download.disabled=false;download.textContent="Download music"}
 };
 player.addEventListener("play",()=>{for(const other of $("players").querySelectorAll("audio"))if(other!==player)other.pause()});
 retry.onclick=load;player.onerror=()=>{message.textContent="Audio could not play. Try downloading it.";retry.hidden=false};
 if((saved?.seconds||0)<=900&&(saved?.variations||1)===1){await load()}else{message.textContent=(saved?.seconds||0)>3600?"Extended track: choose Download music for a direct link.":"Select Load audio or Download music.";retry.textContent="Load audio";retry.hidden=(saved?.seconds||0)>3600}
}
function addReports(slug,files){
 const details=document.createElement("details"),summary=document.createElement("summary");summary.textContent="Audio quality, licences & production details";details.append(summary);
 for(const {name} of files.filter(f=>f.name.endsWith("completed.json"))){
  const panel=document.createElement("article"),heading=document.createElement("h3"),button=document.createElement("button"),result=document.createElement("div");
  panel.className="v9-result";heading.textContent="Variation "+(name.match(/variation_(\d+)/)?.[1]||"1")+" · Quality report";
  button.type="button";button.className="v9-secondary";button.textContent="Review audio quality";
  result.setAttribute("aria-live","polite");panel.append(heading,button,result);details.append(panel);
  button.onclick=async()=>{
   button.disabled=true;result.textContent="Loading validated production report…";
   try{
    const response=await fetch(API+"/file?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name),{cache:"no-store",headers:{Authorization:"Bearer "+key}});
    if(!response.ok)throw Error("Report unavailable (HTTP "+response.status+")");
    const report=await response.json();if(!panel.isConnected)return;
    result.replaceChildren();
    const q=report.quality, list=document.createElement("dl");list.className="v9-timing";
    const field=(label,value)=>{const dt=document.createElement("dt"),dd=document.createElement("dd");dt.textContent=label;dd.textContent=String(value??"Not recorded");list.append(dt,dd)};
    const number=(n,suffix="")=>Number.isFinite(n)?n.toFixed(2)+suffix:"Not recorded";
    field("Engine",report.engine==="studio"?"Studio Premium":report.engine==="fast"?"Fast Acoustic":report.engine==="aria"?"Aria AI":report.engine==="nature"?"Nature recordings":report.engine);
    field("Composition",report.composition==="thematic"?"Recurring theme":report.composition==="independent"?"Independent sections":"Not recorded / not applicable");
    field("Duration",durationLabel(q?.decoded_seconds??report.seconds));
    field("Sample rate",Number.isFinite(report.sample_rate)?report.sample_rate+" Hz":"Not recorded");
    if(q){
     field("Technical validation",q.status==="technical_checks_passed"?"Passed":q.status);
     field("Audio channels",q.channels);field("Intermediate precision",q.checkpoint_bits?q.checkpoint_bits+"-bit":"Not applicable / not recorded");
     field("Average level (RMS)",number(q.rms_dbfs," dBFS"));field("Sample peak",number(q.sample_peak_dbfs," dBFS"));
     field("Longest very quiet passage",number(q.longest_very_quiet_seconds," s"));
     if(q.composition_analysis){field("Musical sections",q.composition_analysis.sections);field("Highest MIDI similarity",Number.isFinite(q.composition_analysis.max_similarity)?(100*q.composition_analysis.max_similarity).toFixed(1)+"%":"Insufficient comparison data");}
     if(q.export){field("Export codec",q.export.codec);field("Encoding mode",q.export.encoding_mode==="vbr"?"Quality-driven VBR":q.export.encoding_mode||"Not recorded");field("Target bitrate",q.export.target_kbps?q.export.target_kbps+" kbps":q.export.encoding_mode==="vbr"?"Variable, no fixed target":"Lossless / not recorded");field("Actual average file bitrate",number(q.export.average_file_kbps," kbps"));field("File size",Number.isFinite(q.export.file_bytes)?(q.export.file_bytes/1e6).toFixed(1)+" MB":"Not recorded");}
     if(q.loudness){field("Integrated loudness",number(q.loudness.integrated_lufs," LUFS"));field("Loudness range",number(q.loudness.range_lu," LU"));field("Measured true peak",number(q.loudness.true_peak_dbtp," dBTP"));field("Loudness analysis",q.loudness.status);}
     if(report.regeneration){field("Regenerated instrument",report.regeneration.instrument);field("Preserved stems",report.regeneration.preserved_stems.join(", "));field("Unchanged stems verified",report.regeneration.unchanged_stems_sha256_verified?"Yes":"No");}
     if(report.extension){field("Preserved preview",report.extension.preserved_seconds+" seconds");field("PCM prefix verified",report.extension.pcm_prefix_verified?"Yes":"No");field("Join",report.extension.join);}
     if(q.equalisation?.enabled){field("Adaptive EQ",q.equalisation.bands.map(b=>b.name.replaceAll("_"," ")+": −"+Number(b.max_applied_cut_db).toFixed(2)+" dB max").join(" · "));}
     if(q.normalization){field("Target loudness",number(q.normalization.target_lufs," LUFS"));field("Normalization gain",number(q.normalization.applied_gain_db," dB"));field("Peak-constrained",q.normalization.peak_constrained?"Yes":"No");}
     if(q.mastering){field("Mastering profile",q.mastering.profile);field("Master gain",number(q.mastering.gain_db," dB"));field("Pre-encoding sample ceiling",number(q.mastering.sample_ceiling_dbfs," dBFS"));field("Fade in / out",q.mastering.fade_in_seconds+" / "+q.mastering.fade_out_seconds+" s");}
     if(q.composition_seed)field("Composition seed",q.composition_seed);
     if(q.tuning){field("Tuning",q.tuning.mode==="a432"?"A4 = 432 Hz":q.tuning.mode==="c528"?"C5 = 528 Hz":"Standard pitch");field("Nominal A4",number(q.tuning.nominal_a4_hz," Hz"));field("Nominal C5",number(q.tuning.nominal_c5_hz," Hz"));}
     for(const [name,gain] of Object.entries(q.nature_layers_db||{}))field((natureNames[name]||name)+" · relative gain",gain+" dB");
     if(q.audio_repetition){const ar=q.audio_repetition;field("Audio repetition candidates",ar.comparisons?ar.candidate_matches:"Insufficient comparison data");field("Highest audio pattern similarity",Number.isFinite(ar.max_similarity)?(100*ar.max_similarity).toFixed(1)+"%":"Not recorded");for(const match of (ar.examples||[]).slice(0,5))field("Listen and compare",durationLabel(match.first_seconds===0?0.001:match.first_seconds)+" / "+durationLabel(match.second_seconds)+" · "+(100*match.similarity).toFixed(1)+"% similarity");}
     for(const [instrument,count] of Object.entries(q.instrument_coverage||{}))field((instruments[instrument]||instrument)+" · sections rendered",count);
    }
    result.append(list);
    const note=document.createElement("p");note.className="hint";note.textContent=q?"Technical checks do not certify artistic quality. MIDI and audio similarity are heuristic indicators, not proof of repetition. Listen before publishing.":"Older production: detailed quality measurements were not recorded.";result.append(note);
    if(Array.isArray(q?.warnings)&&q.warnings.length){const h=document.createElement("strong"),ul=document.createElement("ul");h.textContent="Listening review warnings";for(const warning of q.warnings){const li=document.createElement("li");li.textContent=String(warning);ul.append(li)}result.append(h,ul)}
    button.textContent="Refresh quality report";
   }catch(e){result.textContent=e.message;button.textContent="Retry quality report"}finally{button.disabled=false}
  };
 }
 for(const {name} of files.filter(f=>f.name.endsWith(".json"))){const b=document.createElement("button");b.type="button";b.className="v9-secondary";b.textContent=(name.includes("licences")?"Licence information":"Raw production report")+" · Variation "+(name.match(/variation_(\d+)/)?.[1]||"1");b.onclick=async()=>{try{const d=await api("/download?slug="+encodeURIComponent(slug)+"&file="+encodeURIComponent(name));const a=document.createElement("a");a.href=d.url;a.target="_blank";a.rel="noopener noreferrer";a.textContent="Open report";b.after(a)}catch(e){status(e.message)}};details.append(b)}$("players").append(details);
}
async function watch(slug){
 if(submitting||pendingSlug&&pendingSlug!==slug){showProgress("A production is in progress. Check its status before opening another track.",true);return}
 continuousObservation=Boolean(submittingSlugExpected);submittingSlugExpected=false;
 if(!key){status("Connect first.");return}
 clearTimeout(timer);const version=++monitorVersion;active=slug;remember(slug);pendingMeta=null;
 const saved=history().find(x=>x.slug===slug);
 if(!saved?.state||!terminalStates.has(saved.state)){pendingSlug=slug;lock();renderHistory()}
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
  const success=["COMPLETE","COMPLETED","SUCCESS"].includes(state);
  if(!done||success){pendingSlug=slug;lock()}
  updateSaved(slug,{state:success?"VERIFYING":state,observedEnd:selectedEnd});
  updateClock();
  const uncertain=["UNKNOWN","UNSPECIFIED","UNDEFINED","NULL","0","STATUS_UNSPECIFIED"].includes(state);
  if(["COMPLETE","COMPLETED","SUCCESS"].includes(state)||uncertain||state==="RUNNING"){
   if(state!=="RUNNING")showProgress(uncertain?"Checking for saved audio…":"Production complete. Preparing audio…",true);
   let out;
   try{out=await api("/outputs?slug="+encodeURIComponent(slug))}catch(e){if(state==="RUNNING"){showProgress("Creating your music… Waiting for validated outputs.",true);next=15000;return}throw e}
   if(version!==monitorVersion)return;
   const files=out.files||[],names=new Set(files.map(f=>f.name)),audio=files.filter(f=>/music\.(mp3|m4a|wav|flac)$/i.test(f.name)&&names.has(f.name.replace(/music\.(mp3|m4a|wav|flac)$/i,"completed.json"))&&names.has(f.name.replace(/music\.(mp3|m4a|wav|flac)$/i,"licences.json")));
   attempt=0;
   if(state==="RUNNING"&&audio.length<(history().find(x=>x.slug===slug)?.variations||1)){showProgress("Creating your music…",true);next=15000;return}
   $("players").replaceChildren();
   const expected=history().find(x=>x.slug===slug)?.variations||1;
   if(audio.length<expected){
    if(uncertain){unknownChecks++;showProgress("Kaggle has not confirmed the production status. No complete audio and report set found."+(unknownChecks<4?" Checking again automatically.":" Open Production details to verify the job; do not submit a duplicate."),false);if(unknownChecks<4)next=30000;else if(autoLongPlan)pauseLongQueue("Kaggle status is uncertain. Verify the active part before resuming.");return}
    showProgress("Waiting for all audio files and completion reports.");next=20000;return
   }
   clockRunning=false;selectedEnd=selectedEnd||Date.now();const saved=history().find(x=>x.slug===slug);const measuredSeconds=(selectedEnd-selectedStarted)/1000;updateSaved(slug,{state:"COMPLETE",observedEnd:selectedEnd,...(continuousObservation&&saved?.estimateSignature&&measuredSeconds>0?{measuredSeconds,timingReliable:true}:{})});updateClock();refresh();
   for(const f of audio){if(version!==monitorVersion)return;await addFile(slug,f.name,files)}
   if(version!==monitorVersion)return;
   if(files.some(f=>f.name.endsWith(".json")))addReports(slug,files);
   showProgress(saved?.preview?"Preview completed. Audition the variations below. Full production will create a new composition, not extend this exact preview.":"Production completed. Your audio is below.");release(slug);renderHistory();renderLongPlan();queueNextLongPart();return
  }
  unknownChecks=0;
  if(["ERROR","FAILED","CANCELLED","CANCELED","CANCEL_ACKNOWLEDGED"].includes(state)){
   showProgress((state.includes("CANCEL")?"Production canceled.":"Production failed.")+(d.failureMessage?" "+d.failureMessage:" No further details supplied by Kaggle."));
   release(slug);renderHistory();renderLongPlan();if(autoLongPlan)pauseLongQueue("A part failed or was cancelled. Verify the job before continuing.");return
  }
  attempt=0;
  const label=state==="RUNNING"?"Creating your music…":state==="QUEUED"?"Waiting for Kaggle compute…":state==="CANCEL_REQUESTED"?"Cancellation requested…":"Kaggle status: "+state;
  showProgress(label+(selectedStarted&&Date.now()-selectedStarted>20*60000?" This is taking longer than usual; check status or review the notebook.":""),true);
  next=15000;
 }catch(e){
  if(version!==monitorVersion)return;
  continuousObservation=false;attempt++;showProgress("Status check failed: "+e.message+(attempt<4?" · Reconnecting automatically.":" · Use Check status to retry."));
  if(attempt<4)next=Math.min(60000,15000*attempt);else {lock();renderHistory();if(autoLongPlan)pauseLongQueue("Status could not be verified. Check the active job before resuming.")}
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
$("v9-form").onsubmit=async e=>{e.preventDefault();if(busy||submitting||pendingSlug)return;try{const preview=e.submitter?.id==="preview";const data=buildRequest(preview);if(!key)throw Error("Connect first.");if(data.nature_layers&&!["V16-nature-mixer","V17-tuning","V18-long-nature","V19-youtube-ready","V20-aac-vbr","V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion)&&(Object.keys(data.nature_layers).length>1||Object.values(data.nature_layers).some(v=>v!==0)))throw Error("Deploy V16 Worker to use multiple nature layers or adjust their gains.");if(data.tuning!=="standard"&&!["V17-tuning","V18-long-nature","V19-youtube-ready","V20-aac-vbr","V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V17 Worker to enable custom instrument tuning.");if(data.seconds>3600&&!["V18-long-nature","V19-youtube-ready","V20-aac-vbr","V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V18 Worker to enable extended nature duration.");if(data.format==="m4a"&&!["V19-youtube-ready","V20-aac-vbr","V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V19 Worker to enable YouTube Ready AAC.");if(data.aac_mode==="vbr"&&!["V20-aac-vbr","V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V20 Worker to enable AAC VBR.");if(data.aac_mode==="balanced"&&!["V21-aac-balanced","V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V21 Worker to enable balanced AAC.");if(data.seed&&!["V22-seeded-acoustic","V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V22 Worker to use fixed seeds.");if(data.seed_variation>1&&!["V23-preview-selection","V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V23 Worker to select a preview variation.");if(data.mastering!=="original"&&!["V24-mastering","V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V24 Worker to use mastering presets.");if(data.regenerate&&!["V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V28 Worker for instrument regeneration.");if(data.extension&&!["V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V26 Worker for lossless preview extension.");if(data.engine==="studio"&&!["V25-studio-premium","V26-preview-extension","V27-multitrack","V28-instrument-regeneration","V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion))throw Error("Deploy V25 Worker to use Studio Premium.");if(preparedLongPart&&!preview){
 const selection=preparedLongPart;
 const reserve=()=>{
  const plan=readLongPlan(),part=plan?.parts[selection.index];
  if(plan?.id!==selection.id||!part||part.slug||part.pending||data.seconds!==part.seconds||data.variations!==1||data.extension||data.regenerate||!["fast","studio"].includes(data.engine)||!data.instruments?.length||!["mp3","m4a"].includes(data.format))throw Error("Long plan selection changed; prepare the part again.");
  const expected={...plan.settings,seed:plan.settings.seed.slice(0,40)+"Part"+(selection.index+1),seed_variation:1,variations:1,seconds:part.seconds};
  const comparable=x=>JSON.stringify([x.engine,x.format,x.aac_mode,x.tuning,x.mastering,x.composition,x.preset,x.seed,x.seed_variation,[...(x.instruments||[])].sort(),Object.entries(x.gains||{}).sort(),Object.entries(x.nature_layers||{}).sort()]);
  if(comparable(data)!==comparable(expected))throw Error("Part settings differ from the saved plan. Prepare the part again.");
  part.pending=true;part.reservedAt=new Date().toISOString();writeLongPlan(plan);renderLongPlan();
 };
 if(!navigator.locks)throw Error("This browser does not support safe cross-tab production reservations.");
 await navigator.locks.request("auraluna-long-reserve",{ifAvailable:true},lock=>{if(!lock)throw Error("Another tab is reserving a part");reserve()});
 if(busy||submitting||pendingSlug)throw Error("A production started during reservation; verify the reserved part before retrying.");
}
submitting=true;lock();renderHistory();const prediction=estimate(data);const submittedAt=Date.now();selectedStarted=submittedAt;selectedEnd=0;clockRunning=true;lastChecked=0;showRequest({title:data.preset?presets[data.preset][0]:"Custom music",seconds:data.seconds,format:data.format,estimate:prediction});updateClock();showProgress("Submitting production…",true);const d=await api("/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});if(preparedLongPart&&!preview){const plan=readLongPlan();if(plan?.id===preparedLongPart.id){const part=plan.parts[preparedLongPart.index];part.slug=d.slug;part.pending=false;writeLongPlan(plan)}preparedLongPart=null;renderLongPlan()}pendingMeta={title:(preview?"Preview · ":"")+(data.preset?presets[data.preset][0]:"Custom music"),date:new Date(submittedAt).toISOString(),estimate:prediction,estimateSignature:prediction.signature,seconds:data.seconds,format:data.format,engine:data.engine,composition:d.composition||null,natureLayers:d.natureLayers||null,aacMode:d.aacMode||null,tuning:d.tuning||null,compute:d.compute||null,variations:data.variations,preview,requestSettings:{...data,seed:d.seed||data.seed||"",seed_variation:d.seedVariation||data.seed_variation||1},state:"QUEUED"};submitting=false;pendingSlug=d.slug;submittingSlugExpected=true;await watch(d.slug)}catch(e){submitting=false;clockRunning=false;selectedEnd=Date.now();updateClock();showProgress(e.message+" · If submission was interrupted, verify Kaggle before retrying.");unlock();renderHistory();if(autoLongPlan)pauseLongQueue("Submission interrupted. Verify the existing job before resuming.")}};
$("check-job").onclick=()=>{const slug=$("existing-slug").value.trim();if(!/^auraluna-[a-f0-9]{32}$/.test(slug)){status("Invalid production slug");return}watch(slug)};
$("extension-clear").onclick=()=>{extensionSelection=null;regenerationSelection=null;$("extension-status").textContent="No preview selected.";refresh()};
$("cloud-archive-refresh").onclick=()=>void renderCloudArchive();$("archive-refresh").onclick=()=>void renderArchive();$("archive-persist").onclick=async()=>{try{const ok=await navigator.storage?.persist?.();$("archive-status").textContent=ok?"Persistent storage granted; keep a downloaded backup.":"Persistent storage not granted. Browser data may be evicted."}catch(e){$("archive-status").textContent=e.message}};

const longPlanKey="auraluna-long-plan-v1";
function readLongPlan(){try{return JSON.parse(localStorage.getItem(longPlanKey)||"null")}catch{return null}}
function writeLongPlan(p){localStorage.setItem(longPlanKey,JSON.stringify(p))}
function renderLongPlan(){
 const p=readLongPlan(),list=$("long-plan-list");list.replaceChildren();
 if(!p){list.textContent="No long production plan.";return}
 const rows=history();
 for(let i=0;i<p.parts.length;i++){
  const part=p.parts[i],saved=rows.find(x=>x.slug===part.slug),row=document.createElement("div");row.className="v9-saved";
  const label=document.createElement("span");label.textContent="Part "+(i+1)+" · "+durationLabel(part.seconds)+" · "+(saved?.state|| (part.slug?"Check existing production":part.pending?"Submission needs verification":"Not submitted"));row.append(label);
  if(part.slug){const open=document.createElement("button");open.type="button";open.textContent="Open production";open.onclick=()=>watch(part.slug);row.append(open)}
  else if(!part.pending){const select=document.createElement("button");select.type="button";select.textContent="Prepare part";select.onclick=()=>prepareLongPart(i);row.append(select)}
  else{const recover=document.createElement("button");recover.type="button";recover.textContent="Link existing production";recover.onclick=()=>{const slug=prompt("Enter the confirmed Kaggle production ID");if(!slug)return;if(!/^auraluna-[a-f0-9]{32}$/.test(slug)){ $("long-plan-status").textContent="Invalid production ID.";return}const current=readLongPlan();if(current?.id!==p.id)return;if(current.parts.some((part,index)=>index!==i&&part.slug===slug)){ $("long-plan-status").textContent="This production is already linked to another part.";return}current.parts[i].slug=slug;current.parts[i].pending=false;writeLongPlan(current);renderLongPlan()};row.append(recover)}
  list.append(row)
 }
}
let preparedLongPart=null;
function prepareLongPart(i){
 if(busy||submitting||pendingSlug){$("long-plan-status").textContent="Finish the current production first.";return}
 const p=readLongPlan(),part=p?.parts[i];if(!part||part.slug||part.pending)return;
 restoreSettings({...p.settings,seed:p.settings.seed.slice(0,40)+"Part"+(i+1),seed_variation:1,variations:1});
 $("duration").value=String(part.seconds/60);preparedLongPart={id:p.id,index:i};refresh();
 $("long-plan-status").textContent="Part "+(i+1)+" prepared. Review settings and press Generate Music. No automatic submission.";
}
$("long-plan-create").onclick=()=>{
 try{
  if(busy||submitting||pendingSlug)throw Error("Finish the current production first");
  const hours=Number($("long-plan-hours").value);if(!Number.isInteger(hours)||hours<2||hours>12)throw Error("Choose 2–12 whole hours");
  const data=buildRequest(false);if(!["fast","studio"].includes(data.engine)||!data.instruments?.length||!["mp3","m4a"].includes(data.format))throw Error("Choose manual instruments, Fast or Studio Premium, and MP3 or AAC");
  if(data.extension||data.regenerate)throw Error("Clear extension or regeneration selection first");
  if(autoLongPlan)throw Error("Pause the sequential queue before replacing the plan");
  if(readLongPlan()&&!confirm("Replace the saved plan? Existing productions will remain in the catalogue."))return;
  const id=crypto.randomUUID().replaceAll("-","");
  writeLongPlan({id,settings:{...data,seed:data.seed||id,variations:1,seed_variation:1},parts:Array.from({length:hours},()=>({seconds:3600,slug:null,pending:false}))});
  preparedLongPart=null;renderLongPlan();$("long-plan-status").textContent="Plan saved. Generate each hour separately; outputs have their own fades and are not automatically joined.";
 }catch(e){$("long-plan-status").textContent=e.message}
};
$("long-plan-refresh").onclick=renderLongPlan;

let autoLongPlan=null,autoLongTimer=0;
function pauseLongQueue(message="Sequential queue paused. The active Kaggle job is not cancelled."){
 autoLongPlan=null;clearTimeout(autoLongTimer);autoLongTimer=0;
 $("long-plan-auto").disabled=false;$("long-plan-pause").disabled=true;
 $("long-plan-status").textContent=message;
}
function queueNextLongPart(){
 if(!autoLongPlan)return;
 clearTimeout(autoLongTimer);
 autoLongTimer=setTimeout(async()=>{
  if(!autoLongPlan)return;
  if(!key){pauseLongQueue("Connection lost. Reconnect and resume the queue.");return}
  if(busy||submitting||pendingSlug){pauseLongQueue("Another production is active; finish it and resume.");return}
  const p=readLongPlan();if(p?.id!==autoLongPlan){pauseLongQueue("Plan changed; queue paused.");return}
  const rows=history();
  if(p.parts.some(x=>x.pending||x.slug&&rows.find(y=>y.slug===x.slug)?.state!=="COMPLETE")){pauseLongQueue("An existing part needs verification. Open it before resuming.");return}
  const i=p.parts.findIndex(x=>!x.slug);
  if(i<0){pauseLongQueue("All parts complete. Use Join completed parts to assemble the final audio.");return}
  // A browser-wide lock prevents two auto queues submitting the same plan part.
  if(!navigator.locks){pauseLongQueue("This browser lacks cross-tab locking. Use manual part submission.");return}
  try{await navigator.locks.request("auraluna-long-submit",{ifAvailable:true},async lock=>{
   if(!lock||!autoLongPlan){pauseLongQueue("Another tab is submitting or the queue was paused.");return}
   const latest=readLongPlan();if(latest?.id!==p.id||latest.parts[i].slug||latest.parts[i].pending){pauseLongQueue("Part changed in another tab. Refresh the plan.");return}
   prepareLongPart(i);
   if(preparedLongPart?.id!==p.id||preparedLongPart?.index!==i){pauseLongQueue("Could not prepare part.");return}
   $("long-plan-status").textContent="Sequential queue: submitting part "+(i+1)+" of "+p.parts.length+".";
   await $("v9-form").onsubmit({preventDefault(){},submitter:$("generate")});
  })}catch(e){pauseLongQueue("Queue paused: "+e.message)}
 },500);
}
$("long-plan-auto").onclick=()=>{
 const p=readLongPlan();
 if(!p||!key||busy||submitting||pendingSlug){$("long-plan-status").textContent="Connect and finish the active job before starting the queue.";return}
 if(!navigator.locks){$("long-plan-status").textContent="Cross-tab locking unavailable; submit parts manually.";return}
 if(!confirm("Automatically submit remaining one-hour parts, one at a time, while this tab stays open? Each part consumes Kaggle quota. You can pause between jobs."))return;
 autoLongPlan=p.id;$("long-plan-auto").disabled=true;$("long-plan-pause").disabled=false;queueNextLongPart();
};
$("long-plan-pause").onclick=()=>pauseLongQueue();
window.addEventListener("storage",e=>{if(e.key===longPlanKey){renderLongPlan();if(autoLongPlan&&!submitting)pauseLongQueue("Plan changed in another tab; verify progress before resuming.")}});

$("long-plan-join").onclick=async()=>{
 const statusEl=$("long-plan-status"),p=readLongPlan();
 if(busy||submitting||pendingSlug){statusEl.textContent="Finish the active production first.";return}
 if(!["V29-long-join","V30-cloud-archive","V31-archive-guard","V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion)){statusEl.textContent="Deploy V29 Worker to assemble completed parts.";return}
 if(!p||new Set(p.parts.map(part=>part.slug)).size!==p.parts.length||p.parts.some(part=>!part.slug||history().find(x=>x.slug===part.slug)?.state!=="COMPLETE")){statusEl.textContent="Complete every part and verify its status before joining.";return}
 if(p.joinSlug){await watch(p.joinSlug);return}
 if(p.joinPending){statusEl.textContent="Previous join submission needs verification. Recover its production ID before retrying.";return}
 const mode=$("long-join-mode").value;
 if(mode==="smooth"&&!["V32-smooth-join","V33-woodwind-beta"].includes(deployedVersion)){statusEl.textContent="Deploy V32 for smooth transitions.";return}
 const bitrate=p.settings.format==="mp3"?"320k":p.settings.aac_mode==="balanced"?"192k":"256k";
 if(!confirm(mode==="smooth"?"Join with 12-second crossfades? This adds one lossy encode and shortens the final track by 12 seconds per join.":"Submit a CPU-only assembly job? No new musical rendering or lossy re-encoding."))return;
 if(!navigator.locks){statusEl.textContent="This browser does not support safe assembly reservations.";return;}
 try{
  await navigator.locks.request("auraluna-long-reserve",{ifAvailable:true},lock=>{if(!lock)throw Error("Another tab is reserving a production");const latest=readLongPlan();if(latest?.id!==p.id||latest.joinPending||latest.joinSlug||JSON.stringify(latest.parts)!==JSON.stringify(p.parts))throw Error("Assembly state changed in another tab");latest.joinPending=true;writeLongPlan(latest);p.joinPending=true;});submitting=true;lock();
  statusEl.textContent="Submitting assembly…";
  const d=await api("/join",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({parts:p.parts.map(x=>x.slug),format:p.settings.format,mode,bitrate})});
  p.joinSlug=d.slug;p.joinPending=false;writeLongPlan(p);
  pendingMeta={title:"Extended production · "+p.parts.length+" hours",date:new Date().toISOString(),seconds:p.parts.length*3600-(mode==="smooth"?(p.parts.length-1)*12:0),format:p.settings.format,engine:mode==="smooth"?"smooth_join":"packet_join",compute:"CPU",variations:1,state:"QUEUED"};
  submitting=false;pendingSlug=d.slug;submittingSlugExpected=true;statusEl.textContent="Assembly submitted. Open the completed production to download the joined file.";await watch(d.slug);
 }catch(e){submitting=false;unlock();statusEl.textContent=e.message+" · Verify Kaggle before submitting again."}
};
$("long-plan-recover-join").onclick=()=>{
 try{const p=readLongPlan();if(!p?.joinPending||p.joinSlug)throw Error("No uncertain assembly submission.");const slug=prompt("Enter the confirmed assembly production ID");if(!slug)return;if(!/^auraluna-[a-f0-9]{32}$/.test(slug))throw Error("Invalid production ID");p.joinSlug=slug;p.joinPending=false;writeLongPlan(p);pendingMeta={title:"Extended production · "+p.parts.length+" hours",date:new Date().toISOString(),seconds:p.parts.length*3600,format:p.settings.format,engine:"packet_join",compute:"CPU",variations:1,state:"QUEUED"};remember(slug);pendingMeta=null;$("long-plan-status").textContent="Assembly linked. Press Join completed parts to open it."}catch(e){$("long-plan-status").textContent=e.message}
};


newJob();applyPreset();renderHistory();void renderArchive();renderLongPlan();
try{const saved=localStorage.getItem(keyStorage);if(saved){$("remember-device").checked=true;connect(saved,true)}}catch{}
