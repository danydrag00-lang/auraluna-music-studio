const ORIGIN="https://danydrag00-lang.github.io";
const API="https://api.kaggle.com/v1/kernels.KernelsApiService/";
const BASE="https://raw.githubusercontent.com/danydrag00-lang/auraluna-music-studio/main/backend/v9/";
const presets=["luxury_spa","deep_sleep","meditation","study_focus","emotional_relaxation","peaceful_piano","yoga_zen","indian_meditation","rain_sleep","ocean_sleep","forest_relaxation","river_relaxation"];
const instruments=["felt_piano","grand_piano","flute","cello","harp","handpan","bansuri","singing_bowls"];
const nature=["none","rain","river","ocean","forest"];
function validate(r){
 if(!r||typeof r!=="object"||Array.isArray(r))throw Error("Invalid request");
 const out={job:crypto.randomUUID().replaceAll("-",""),seconds:r.seconds??120,variations:r.variations??1,format:r.format??"mp3",prompt:r.prompt??"",engine:r.engine??"aria",composition:r.composition??"independent"};
 if(!Number.isInteger(out.seconds)||out.seconds<15||out.seconds>3600)throw Error("Choose 15 seconds to 60 minutes.");
 if(!Number.isInteger(out.variations)||out.variations<1||out.variations>3)throw Error("Choose one to three variations.");
 if(!["mp3","flac","wav"].includes(out.format)||typeof out.prompt!=="string"||out.prompt.length>2000)throw Error("Invalid format or prompt");
 if(r.preset!==undefined){if(!presets.includes(r.preset))throw Error("Invalid preset");out.preset=r.preset}
 if(r.instruments!==undefined){if(!Array.isArray(r.instruments)||r.instruments.some(x=>!instruments.includes(x))||new Set(r.instruments).size!==r.instruments.length)throw Error("Invalid instruments");out.instruments=r.instruments}
 if(r.nature!==undefined){if(!nature.includes(r.nature))throw Error("Invalid ambience");out.nature=r.nature}
 if(r.gains!==undefined){if(!r.gains||typeof r.gains!=="object"||Array.isArray(r.gains)||Object.entries(r.gains).some(([k,v])=>!out.instruments?.includes(k)||typeof v!=="number"||!Number.isFinite(v)||v< -60||v>12))throw Error("Invalid gains");out.gains=r.gains}
 if(out.instruments?.length===0&&out.nature==="none")throw Error("Choose a sound source");
 if(!["independent","thematic"].includes(out.composition))throw Error("Invalid composition style");
 if(!["aria","fast"].includes(out.engine))throw Error("Invalid composition engine");
 const natureOnly=Array.isArray(out.instruments)&&out.instruments.length===0&&nature.includes(out.nature)&&out.nature!=="none";
 if(out.seconds>900&&!natureOnly&&out.engine==="aria")throw Error("Aria supports up to 15 minutes.");
 if(natureOnly&&out.variations!==1)throw Error("Nature-only mode supports one variation.");
 if(out.seconds*out.variations>(out.engine==="aria"&&!natureOnly?900:3600))throw Error("Combined duration exceeds the per-job limit.");
 if(out.seconds>900&&out.format!=="mp3")throw Error("For tracks longer than 15 minutes, choose MP3.");
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
 if(url.pathname==="/"||url.pathname==="/health")return reply({service:"Auraluna",version:"V15-composition-styles",configured,datasetConfigured:Boolean(env.KAGGLE_DATASET),cpuRouting:true});
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
    const result=await call("SaveKernel",{slug:env.KAGGLE_USERNAME+"/"+slug,newTitle:title,text:source,language:"python",kernelType:"script",isPrivate:true,enableGpu:needsGpu,enableTpu:false,...(needsGpu?{machineShape:"NvidiaTeslaT4"}:{}),enableInternet:true,datasetDataSources:[env.KAGGLE_DATASET],kernelDataSources:[],competitionDataSources:[],modelDataSources:[]});
    if(!result.ref&&!result.kernelId)throw Error("Kaggle did not confirm notebook creation");
    return reply({job:r.job,slug,version:result.versionNumber??null,status:"submitted",compute:needsGpu?"GPU":"CPU",composition:r.engine==="fast"&&!natureOnly?r.composition:null},202);
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
    const files=(result.files||[]).filter(f=>/^results\/variation_[1-3]_(music\.(mp3|wav|flac)|licences\.json|completed\.json)$/.test(f.fileName||""));
    // Return names only; signed output URLs must be requested separately.
    return reply({files:files.map(f=>({name:f.fileName}))});
  }
  if(["/download","/file"].includes(url.pathname)&&req.method==="GET"){
    const name=url.searchParams.get("file")||"";
    if(!/^results\/variation_[1-3]_(music\.(mp3|wav|flac)|licences\.json|completed\.json)$/.test(name))return reply({error:"Invalid output file"},400);
    const result=await call("ListKernelSessionOutput",{...query,pageSize:100});
    const file=(result.files||[]).find(f=>f.fileName===name);
    if(!file?.url)return reply({error:"Output not available"},404);
    const signed=trustedOutput(file.url);
    const filename=name.split("/").pop();
    if(url.pathname==="/file"){
     const r=await fetchOutput(signed);
     const type=filename.endsWith(".mp3")?"audio/mpeg":filename.endsWith(".wav")?"audio/wav":filename.endsWith(".flac")?"audio/flac":"application/json";
     const outHeaders={...headers,"Content-Type":type,"Content-Disposition":'attachment; filename="'+filename+'"',"X-Content-Type-Options":"nosniff"};
     return new Response(r.body,{status:200,headers:outHeaders});
    }
    return reply({url:signed.href,name:filename});
  }
  return reply({error:"Endpoint not found"},404);
 }catch(e){return reply({error:e.message},502)}
}};
