const ORIGIN="https://danydrag00-lang.github.io";
const API="https://api.kaggle.com/v1/kernels.KernelsApiService/";
const BASE="https://raw.githubusercontent.com/danydrag00-lang/auraluna-music-studio/main/backend/v9/";
const presets=["luxury_spa","deep_sleep","meditation","study_focus","emotional_relaxation","peaceful_piano","yoga_zen","indian_meditation","rain_sleep","ocean_sleep","forest_relaxation","river_relaxation"];
const instruments=["felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls"];
const nature=["none","rain","river","ocean","forest"];
function validate(r){
 if(!r||typeof r!=="object"||Array.isArray(r))throw Error("Invalid request");
 const out={job:crypto.randomUUID().replaceAll("-",""),seconds:r.seconds??120,variations:r.variations??1,format:r.format??"mp3",prompt:r.prompt??"",engine:r.engine??"aria",composition:r.composition??"independent",tuning:r.tuning??"standard",aac_mode:r.aac_mode??"premium",seed:r.seed??"",seed_variation:r.seed_variation??1,mastering:r.mastering??"original"};
 if(!Number.isInteger(out.seconds)||out.seconds<15||out.seconds>43200)throw Error("Choose 15 seconds to 12 hours.");
 if(!Number.isInteger(out.variations)||out.variations<1||out.variations>3)throw Error("Choose one to three variations.");
 if(!["mp3","m4a","flac","wav"].includes(out.format)||typeof out.prompt!=="string"||out.prompt.length>2000)throw Error("Invalid format or prompt");
 if(r.preset!==undefined){if(!presets.includes(r.preset))throw Error("Invalid preset");out.preset=r.preset}
 if(r.instruments!==undefined){if(!Array.isArray(r.instruments)||r.instruments.some(x=>!instruments.includes(x))||new Set(r.instruments).size!==r.instruments.length)throw Error("Invalid instruments");out.instruments=r.instruments}
 if(r.nature!==undefined){if(!nature.includes(r.nature))throw Error("Invalid ambience");out.nature=r.nature}
 if(r.gains!==undefined){if(!r.gains||typeof r.gains!=="object"||Array.isArray(r.gains)||Object.entries(r.gains).some(([k,v])=>!out.instruments?.includes(k)||typeof v!=="number"||!Number.isFinite(v)||v< -60||v>12))throw Error("Invalid gains");out.gains=r.gains}
 if(r.nature_layers!==undefined){const l=r.nature_layers;if(!l||typeof l!=="object"||Array.isArray(l)||Object.entries(l).some(([k,v])=>!nature.includes(k)||k==="none"||typeof v!=="number"||!Number.isFinite(v)||v< -30||v>6))throw Error("Invalid nature mixer");out.nature_layers=l;out.nature=Object.keys(l)[0]||"none"}
 if(out.instruments?.length===0&&out.nature==="none")throw Error("Choose a sound source");
 if(!["original","sleep","spa","youtube"].includes(out.mastering))throw Error("Invalid mastering profile");
 if(!["premium","vbr","balanced"].includes(out.aac_mode))throw Error("Invalid AAC mode");
 if(out.format!=="m4a")out.aac_mode="premium";
 if(!["standard","a432","c528"].includes(out.tuning))throw Error("Invalid tuning");
 if(!["independent","thematic"].includes(out.composition))throw Error("Invalid composition style");
 if(!["aria","fast","studio"].includes(out.engine))throw Error("Invalid composition engine");
 const natureOnly=Array.isArray(out.instruments)&&out.instruments.length===0&&nature.includes(out.nature)&&out.nature!=="none";
 if(out.seconds>900&&!natureOnly&&out.engine==="aria")throw Error("Aria supports up to 15 minutes.");
 if(typeof out.seed!=="string"||(out.seed&&(!["fast","studio"].includes(out.engine)||natureOnly||!Array.isArray(out.instruments)||!out.instruments.length||!/^[A-Za-z0-9]{1,48}$/.test(out.seed))))throw Error("Seed requires manual Fast Acoustic instruments and 1–48 ASCII letters or digits");
 if(!Number.isInteger(out.seed_variation)||out.seed_variation<1||out.seed_variation>3||(out.seed_variation!==1&&(!out.seed||out.variations!==1)))throw Error("Selected seed variation requires one output and a fixed seed");
 if(natureOnly&&out.tuning!=="standard")throw Error("Tuning requires instruments");
 if(natureOnly&&out.variations!==1)throw Error("Nature-only mode supports one variation.");
 if(out.seconds*out.variations>(natureOnly?43200:out.engine==="aria"?900:3600))throw Error("Combined duration exceeds the per-job limit.");
 if(out.seconds>900&&!["mp3","m4a"].includes(out.format))throw Error("For tracks longer than 15 minutes, choose MP3 or YouTube Ready AAC.");
 if(r.extension!==undefined){
  const e=r.extension;
  if(!e||typeof e!=="object"||!/^auraluna-[a-f0-9]{32}$/.test(e.slug)||![1,2,3].includes(e.variation)||!["wav","flac"].includes(e.format)||out.format!=="flac"||out.variations!==1||out.seconds<75||out.seconds>900)throw Error("Extension requires a 60-second lossless preview, one FLAC output and total duration 75–900 seconds.");
  out.extension={slug:e.slug,variation:e.variation,format:e.format};
 }
 if(r.regenerate!==undefined){
  const g=r.regenerate;
  if(!g||typeof g!=="object"||!/^auraluna-[a-f0-9]{32}$/.test(g.slug)||![1,2,3].includes(g.variation)||!instruments.includes(g.instrument)||out.instruments?.length!==1||out.instruments[0]!==g.instrument||out.format!=="flac"||out.seconds>60||out.variations!==1||out.tuning!=="standard"||out.engine!=="fast"||out.nature!=="none"||Object.keys(out.nature_layers||{}).length||out.extension)throw Error("Invalid single instrument regeneration");
  out.regenerate={slug:g.slug,variation:g.variation,instrument:g.instrument};
 }
 return out;
}
// Kaggle output links can use Kaggle download gateways or Google storage.
function trustedOutput(value){
 const u=new URL(value);
 const h=u.hostname.toLowerCase();
 const allowed=h==="storage.googleapis.com"||h.endsWith(".storage.googleapis.com")||
   h==="storage.cloud.google.com"||h==="kaggle.com"||h==="www.kaggle.com"||h==="api.kaggle.com"||
   h==="kaggleusercontent.com"||h.endsWith(".kaggleusercontent.com");
 if(u.protocol!=="https:"||u.username||u.password||u.port||!allowed)
   throw Error("Unsupported output storage host: "+h);
 return u;
}
async function fetchOutput(u){
 // Follow only validated redirects, never forwarding API credentials.
 for(let i=0;i<6;i++){
  const r=await fetch(u.href,{method:"GET",redirect:"manual"});
  if([301,302,303,307,308].includes(r.status)){
   const next=r.headers.get("Location");
   if(!next)throw Error("Storage redirect missing destination");
   if(r.body)await r.body.cancel();
   u=trustedOutput(new URL(next,u).href);
   continue;
  }
  if(!r.ok)throw Error("Output storage HTTP "+r.status);
  if((r.headers.get("content-type")||"").includes("text/html")){
   if(r.body)await r.body.cancel();
   throw Error("Storage returned a web page instead of a file");
  }
  return r;
 }
 throw Error("Too many output redirects");
}
export default {async fetch(req,env){
 const headers={"Access-Control-Allow-Origin":ORIGIN,"Access-Control-Allow-Methods":"GET, POST, OPTIONS","Access-Control-Allow-Headers":"Authorization, Content-Type","Cache-Control":"no-store","Content-Type":"application/json"};
 const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers});
 if(req.method==="OPTIONS")return new Response(null,{status:204,headers});
 const url=new URL(req.url);
 const configured=Boolean(env.KAGGLE_USERNAME&&env.KAGGLE_API_TOKEN&&env.AURALUNA_ACCESS_KEY);
 if(url.pathname==="/"||url.pathname==="/health")return reply({service:"Auraluna",version:"V32-smooth-join",archiveConfigured:Boolean(env.AURALUNA_ARCHIVE),configured,datasetConfigured:Boolean(env.KAGGLE_DATASET),cpuRouting:true});
 if(!configured)return reply({error:"Credentials missing"},503);
 if(req.headers.get("Authorization")!=="Bearer "+env.AURALUNA_ACCESS_KEY)return reply({error:"Unauthorised"},401);
 async function call(method,data){
   const response=await fetch(API+method,{method:"POST",redirect:"manual",headers:{Authorization:"Bearer "+env.KAGGLE_API_TOKEN,"Content-Type":"application/json",Accept:"application/json"},body:JSON.stringify(data)});
   if(!response.ok)throw Error("Kaggle "+method+" HTTP "+response.status);
   if(!(response.headers.get("content-type")||"").includes("json"))throw Error("Kaggle returned unexpected content");
   const result=await response.json();if(result.error)throw Error("Kaggle "+method+" rejected request");return result;
 }
 try{
  if(url.pathname==="/test-kaggle"&&req.method==="GET"){await call("ListKernels",{pageSize:1});return reply({connected:true})}
  if(url.pathname==="/join"&&req.method==="POST"){
    const body=await req.json(),parts=body?.parts,format=body?.format,mode=body?.mode??"copy",bitrate=body?.bitrate??(format==="mp3"?"320k":"256k");
    if(!["copy","smooth"].includes(mode)||!(format==="mp3"?["320k"]:["192k","256k"]).includes(bitrate))return reply({error:"Invalid assembly mode or quality"},400);
    if(!["mp3","m4a"].includes(format)||!Array.isArray(parts)||parts.length<2||parts.length>12||new Set(parts).size!==parts.length||parts.some(p=>typeof p!=="string"||!/^auraluna-[a-f0-9]{32}$/.test(p)))return reply({error:"Invalid join plan"},400);
    const job=crypto.randomUUID().replaceAll("-",""),slug="auraluna-"+job;
    const source=[
      "import subprocess,sys,urllib.request",
      "from pathlib import Path",
      "engine=Path('/kaggle/temp/join_parts.py')",
      "engine.parent.mkdir(parents=True,exist_ok=True)",
      "urllib.request.urlretrieve("+JSON.stringify(BASE+"join_parts.py")+",engine)",
      "request=engine.with_name('join.json')",
      "request.write_text("+JSON.stringify(JSON.stringify({parts,format,mode,bitrate})) +")",
      "subprocess.run([sys.executable,str(engine),str(request)],check=True)"
    ].join("\n");
    const result=await call("SaveKernel",{slug:env.KAGGLE_USERNAME+"/"+slug,newTitle:slug.replaceAll("-"," "),text:source,language:"python",kernelType:"script",isPrivate:true,enableGpu:false,enableTpu:false,enableInternet:true,datasetDataSources:[],kernelDataSources:parts.map(p=>env.KAGGLE_USERNAME+"/"+p),competitionDataSources:[],modelDataSources:[]});
    if(!result.ref&&!result.kernelId)throw Error("Kaggle did not confirm join notebook");
    return reply({job,slug,status:"submitted",compute:"CPU"},202);
  }
  if(url.pathname==="/generate"&&req.method==="POST"){
    if(!env.KAGGLE_DATASET||!/^[-a-zA-Z0-9_]+\/[-a-zA-Z0-9_]+$/.test(env.KAGGLE_DATASET))return reply({error:"Configure KAGGLE_DATASET first"},503);
    let r;try{r=validate(await req.json())}catch(e){return reply({error:e.message},400)}
    const slug="auraluna-"+r.job,title=slug.replaceAll("-"," ");
    const natureOnly=Array.isArray(r.instruments)&&r.instruments.length===0&&nature.includes(r.nature)&&r.nature!=="none";
    const needsGpu=r.engine==="aria"&&!natureOnly;
    const payload=JSON.stringify(JSON.stringify(r));
    const source=[
      "import json, sys, subprocess, urllib.request",
      "from pathlib import Path",
      "engine = Path('/kaggle/temp/v9-engine')",
      "engine.mkdir(parents=True, exist_ok=True)",
      "for name in ['bootstrap.py','compose_preview.py','arrange.py','produce.py','request.py','cloud_runner.py']:",
      "    urllib.request.urlretrieve("+JSON.stringify(BASE)+" + name, engine / name)",
      "request = engine / 'job.json'",
      "request.write_text("+payload+")",
      "subprocess.run([sys.executable, str(engine / 'cloud_runner.py'), str(request)], check=True)"
    ].join("\n");
    // A script kernel keeps submitted source small; no credentials in notebook source.
    const result=await call("SaveKernel",{slug:env.KAGGLE_USERNAME+"/"+slug,newTitle:title,text:source,language:"python",kernelType:"script",isPrivate:true,enableGpu:needsGpu,enableTpu:false,...(needsGpu?{machineShape:"NvidiaTeslaT4"}:{}),enableInternet:true,datasetDataSources:[env.KAGGLE_DATASET],kernelDataSources:r.extension||r.regenerate?[env.KAGGLE_USERNAME+"/"+(r.extension||r.regenerate).slug]:[],competitionDataSources:[],modelDataSources:[]});
    if(!result.ref&&!result.kernelId)throw Error("Kaggle did not confirm notebook creation");
    return reply({job:r.job,slug,version:result.versionNumber??null,status:"submitted",compute:needsGpu?"GPU":"CPU",natureLayers:r.nature_layers??null,aacMode:r.aac_mode,seed:["fast","studio"].includes(r.engine)?(r.seed||r.job):null,seedVariation:r.seed_variation,mastering:r.mastering,tuning:r.tuning,composition:["fast","studio"].includes(r.engine)&&!natureOnly?r.composition:null},202);
  }

  if(url.pathname.startsWith("/archive")){
   const bucket=env.AURALUNA_ARCHIVE;
   if(!bucket)return reply({error:"Private R2 archive is not configured"},503);
   const prefix="auraluna/v1/",limit=9000000000,warning=8000000000,lockKey="auraluna/system/archive-write-lock";
   async function usage(){
    let cursor,bytes=0,objects=0;
    do{const page=await bucket.list({limit:1000,...(cursor?{cursor}:{})});for(const o of page.objects){bytes+=o.size;objects++}cursor=page.truncated?page.cursor:undefined;}while(cursor);
    return {bytes,objects,limit,warning,remaining:Math.max(0,limit-bytes),scope:"This R2 bucket only"};
   }
   if(url.pathname==="/archive/usage"&&req.method==="GET")return reply(await usage());
   // Atomic conditional create: never expire or steal a lock while a writer may still be active.
   async function withArchiveLock(action){
    const token=crypto.randomUUID();
    const held=await bucket.put(lockKey,token,{onlyIf:new Headers({"If-None-Match":"*"})});
    if(!held)return reply({error:"Archive write in progress or interrupted. Verify active requests before clearing the lock in the R2 dashboard."},409);
    try{return await action()}finally{await bucket.delete(lockKey)}
   }
   if(url.pathname==="/archive/list"&&req.method==="GET"){
    const cursor=url.searchParams.get("cursor")||undefined;
    const page=await bucket.list({prefix,limit:100,include:["customMetadata"],...(cursor?{cursor}:{})});
    return reply({entries:page.objects.filter(o=>o.key.endsWith("/manifest.json")).map(o=>({id:o.key.slice(prefix.length,-"/manifest.json".length),...o.customMetadata})),cursor:page.truncated?page.cursor:null});
   }
   const slug=url.searchParams.get("slug")||"",name=url.searchParams.get("file")||"";
   const match=/^results\/variation_([1-3])_music\.(mp3|m4a|wav|flac)$/.exec(name);
   if(!/^auraluna-[a-f0-9]{32}$/.test(slug)||!match)return reply({error:"Invalid archive identity"},400);
   const base=prefix+slug+"/variation_"+match[1]+"_"+match[2]+"/",manifestKey=base+"manifest.json";
   const type={mp3:"audio/mpeg",m4a:"audio/mp4",wav:"audio/wav",flac:"audio/flac"}[match[2]];
   if(url.pathname==="/archive/save"&&req.method==="POST")return await withArchiveLock(async()=>{
    const prior=await bucket.head(manifestKey);
    if(prior)return reply({saved:true,alreadySaved:true,...prior.customMetadata});
    const result=await call("ListKernelSessionOutput",{userName:env.KAGGLE_USERNAME,kernelSlug:slug,pageSize:100});
    const names=[name,"results/variation_"+match[1]+"_completed.json","results/variation_"+match[1]+"_licences.json"];
    const files=names.map(n=>(result.files||[]).find(f=>f.fileName===n&&f.url));
    if(files.some(f=>!f))return reply({error:"Complete audio and both reports must be available"},409);
    const reports=[];
    for(let i=1;i<3;i++){
     const response=await fetchOutput(trustedOutput(files[i].url));
     const length=Number(response.headers.get("content-length")||0);
     if(length>1024*1024)throw Error("Report too large");
     const reader=response.body.getReader();let total=0;const parts=[];
     try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.byteLength;if(total>1024*1024)throw Error("Report too large");parts.push(value)}}finally{await reader.cancel().catch(()=>{})}
     const bytes=new Uint8Array(total);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.byteLength}
     reports.push(JSON.parse(new TextDecoder().decode(bytes)));
    }
    if(!reports[0]?.quality?.status||!Number.isFinite(reports[0]?.seconds)||reports[0].seconds<=0||!Array.isArray(reports[1]))throw Error("Missing production validation or licence report");
    const audio=await fetchOutput(trustedOutput(files[0].url));
    const size=Number(audio.headers.get("content-length")||0);
    if(!Number.isSafeInteger(size)||size<=0||size>2*1024**3){await audio.body?.cancel();return reply({error:"Archive requires a known file length up to 2 GiB"},413)}
    const current=await usage();
    // Include the old incomplete objects in the usage total and reserve space for reports.
    const required=size+3*1024*1024;
    if(current.bytes+required>limit){await audio.body?.cancel();return reply({error:"9 GB archive safeguard: insufficient storage. Download and remove old audio first.",...current},409)}
    const stream=new FixedLengthStream(size);
    const pumping=audio.body.pipeTo(stream.writable);
    try{await Promise.all([bucket.put(base+"audio."+match[2],stream.readable,{httpMetadata:{contentType:type}}),pumping])}catch(e){await pumping.catch(()=>{});throw e}
    const stored=await bucket.head(base+"audio."+match[2]);if(!stored||stored.size!==size)throw Error("Archived file size mismatch");
    await bucket.put(base+"completed.json",JSON.stringify(reports[0]),{httpMetadata:{contentType:"application/json"}});
    await bucket.put(base+"licences.json",JSON.stringify(reports[1]),{httpMetadata:{contentType:"application/json"}});
    const meta={slug,name,size:String(size),seconds:String(reports[0].seconds),savedAt:new Date().toISOString()};
    await bucket.put(manifestKey,JSON.stringify(meta),{customMetadata:meta,httpMetadata:{contentType:"application/json"}});
    return reply({saved:true,...meta});
   });
   if(url.pathname==="/archive/delete"&&req.method==="POST")return withArchiveLock(async()=>{
    const body=await req.json();if(body?.confirm!==name)return reply({error:"Explicit matching file confirmation required"},400);
    // Remove manifest first so no incomplete entry is presented as available.
    await bucket.delete(manifestKey);
    await bucket.delete([base+"audio."+match[2],base+"completed.json",base+"licences.json"]);
    return reply({deleted:true,...await usage()});
   });
   if(url.pathname==="/archive/file"&&req.method==="GET"){
    if(!await bucket.head(manifestKey))return reply({error:"Archive entry not found"},404);
    const kind=url.searchParams.get("kind")||"audio";
    if(!["audio","completed","licences"].includes(kind))return reply({error:"Invalid archive file kind"},400);
    const filename=kind==="audio"?"audio."+match[2]:kind+".json";
    const obj=await bucket.get(base+filename);
    if(!obj)return reply({error:"Archived object unavailable"},404);
    return new Response(obj.body,{headers:{...headers,"Content-Type":kind==="audio"?type:"application/json","Content-Length":String(obj.size),"Content-Disposition":'attachment; filename="'+(kind==="audio"?name.split("/").pop():filename)+'"',"X-Content-Type-Options":"nosniff"}});
   }
   return reply({error:"Unknown archive operation"},404);
  }

  const slug=url.searchParams.get("slug")||"";
  if(!/^auraluna-[a-f0-9]{32}$/.test(slug))return reply({error:"Invalid production slug"},400);
  const query={userName:env.KAGGLE_USERNAME,kernelSlug:slug};
  if(url.pathname==="/status"&&req.method==="GET"){
    const result=await call("GetKernelSessionStatus",query);
    return reply({status:result.status??"unknown",failureMessage:result.failureMessage??""});
  }
  if(url.pathname==="/outputs"&&req.method==="GET"){
    const result=await call("ListKernelSessionOutput",{...query,pageSize:100});
    const files=(result.files||[]).filter(f=>/^results\/variation_[1-3]_(music\.(mp3|m4a|wav|flac)|licences\.json|completed\.json|score\.mid|stem_(felt_piano|grand_piano|flute|cello|harp|handpan|bansuri|singing_bowls)\.flac)$/.test(f.fileName||""));
    // Return names only; signed output URLs must be requested separately.
    return reply({files:files.map(f=>({name:f.fileName}))});
  }
  if(["/download","/file"].includes(url.pathname)&&req.method==="GET"){
    const name=url.searchParams.get("file")||"";
    if(!/^results\/variation_[1-3]_(music\.(mp3|m4a|wav|flac)|licences\.json|completed\.json|score\.mid|stem_(felt_piano|grand_piano|flute|cello|harp|handpan|bansuri|singing_bowls)\.flac)$/.test(name))return reply({error:"Invalid output file"},400);
    const result=await call("ListKernelSessionOutput",{...query,pageSize:100});
    const file=(result.files||[]).find(f=>f.fileName===name);
    if(!file?.url)return reply({error:"Output not available"},404);
    const signed=trustedOutput(file.url);
    const filename=name.split("/").pop();
    if(url.pathname==="/file"){
     const r=await fetchOutput(signed);
     const type=filename.endsWith(".mp3")?"audio/mpeg":filename.endsWith(".m4a")?"audio/mp4":filename.endsWith(".wav")?"audio/wav":filename.endsWith(".flac")?"audio/flac":filename.endsWith(".mid")?"audio/midi":"application/json";
     const outHeaders={...headers,"Content-Type":type,"Content-Disposition":'attachment; filename="'+filename+'"',"X-Content-Type-Options":"nosniff"};
     return new Response(r.body,{status:200,headers:outHeaders});
    }
    return reply({url:signed.href,name:filename});
  }
  return reply({error:"Endpoint not found"},404);
 }catch(e){return reply({error:e.message},502)}
}};
