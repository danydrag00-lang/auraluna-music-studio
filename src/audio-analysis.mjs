// Descriptive audio measurements, not a relaxation score or a LUFS implementation.
const db=x=>20*Math.log10(Math.max(x,1e-8));
export function analyze(buffer){
 const rate=buffer.sampleRate, channels=Array.from({length:buffer.numberOfChannels},(_,i)=>buffer.getChannelData(i));
 if(!channels.length||!buffer.length||!rate)throw Error('Empty audio');
 // Equal-length opening excerpts (up to 120 s); stride bounds analysis costs.
 const length=Math.min(buffer.length,rate*120),stride=Math.max(1,Math.floor(rate/12000)),window=Math.max(1,Math.floor(rate/stride*.5));
 let sum=0,n=0,peak=0,clip=0,quiet=0,ws=0,wn=0,levels=[],lowEnergy=0,totalEnergy=0,low=0;
 const alpha=1-Math.exp(-2*Math.PI*2000*stride/rate);
 for(let i=0;i<length;i+=stride){let mono=0;for(const c of channels){const x=c[i];if(!Number.isFinite(x))throw Error('Invalid PCM');peak=Math.max(peak,Math.abs(x));if(Math.abs(x)>=.999)clip++;sum+=x*x;n++;mono+=x/channels.length;}low+=alpha*(mono-low);lowEnergy+=(mono-low)**2;totalEnergy+=mono**2;ws+=mono**2;wn++;if(wn===window){const rms=Math.sqrt(ws/wn);levels.push(db(rms));if(rms<.00316)quiet++;ws=0;wn=0;}}
 if(wn){const rms=Math.sqrt(ws/wn);levels.push(db(rms));if(rms<.00316)quiet++;}
 const active=levels.filter(x=>x>-50).sort((a,b)=>a-b),pct=(p)=>active[Math.floor((active.length-1)*p)]??-160;
 return {seconds:length/rate,fullDuration:buffer.length/rate,peakDb:db(peak),rmsDb:db(Math.sqrt(sum/n)),variationDb:Math.max(0,pct(.9)-pct(.1)),quietPercent:100*quiet/levels.length,clipPercent:100*clip/n,brightness:totalEnergy>1e-12?100*lowEnergy/totalEnergy:0};
}
export async function analyzeFile(file){if(file.size>80*1024*1024)throw Error('Use a reference excerpt under 80 MB.');const ctx=new AudioContext();try{return analyze(await ctx.decodeAudioData(await file.arrayBuffer()));}finally{await ctx.close();}}
export function brief(m){return {complexity:m.quietPercent>20?15:m.variationDb>12?25:35,mood:'sleep',note:'A starting point only; listen before approving. Brightness and loudness do not identify tempo or genre.'};}
