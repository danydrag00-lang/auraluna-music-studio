import {audibleTrack} from './mix.mjs';
import {analyze} from './audio-analysis.mjs';
export async function render(project,catalog,{measure=false}={}){
 const rate=44100, ctx=new OfflineAudioContext(2,Math.ceil(project.seconds*rate),rate);
 const master=ctx.createGain();master.gain.value=.55;const compressor=ctx.createDynamicsCompressor();const tone=ctx.createBiquadFilter();tone.type='lowpass';tone.frequency.value=project.mix?.tone??(project.mood==='sleep'?3400:5200);tone.Q.value=.25;
 const warmth=ctx.createBiquadFilter();warmth.type='highpass';warmth.frequency.value=45;warmth.Q.value=.5;
 master.connect(warmth);warmth.connect(tone);tone.connect(compressor);compressor.threshold.value=-14;compressor.ratio.value=1.5;compressor.attack.value=.08;compressor.release.value=.7;compressor.connect(ctx.destination);
 // Quiet early reflections from the original recording only; no generated noise or synth layers.
 for(const [delay,gain,pan] of [[.077,.13,-.55],[.131,.095,.55],[.223,.065,-.3],[.347,.035,.3]]){const d=ctx.createDelay(1),g=ctx.createGain(),p=ctx.createStereoPanner();d.delayTime.value=delay;g.gain.value=gain*(project.mix?.space??1);p.pan.value=pan;tone.connect(d);d.connect(g);g.connect(p);p.connect(compressor);}
 const assets=catalog.filter(a=>a.kind==='note'&&['CC0-1.0','CC-BY-4.0'].includes(a.license)&&a.reviewed===true);
 const cache=new Map();const used=new Map();const calibration=new Map();
 for(const e of project.events){
 if(!audibleTrack(project.mix,e.instrument))continue;
 const a=assets.filter(x=>x.instrument===e.instrument&&Math.abs(x.pitch-e.pitch)<=3).sort((x,y)=>Math.abs(x.pitch-e.pitch)-Math.abs(y.pitch-e.pitch)||Number(/_v1_/i.test(y.title))-Number(/_v1_/i.test(x.title)))[0];
 if(!a)throw Error('Missing verified sample for '+e.instrument+' MIDI '+e.pitch);
 if(!cache.has(a.id)){const res=await fetch(a.path);if(!res.ok)throw Error('Missing local audio '+a.id);cache.set(a.id,await ctx.decodeAudioData(await res.arrayBuffer()));}
 if(!calibration.has(a.id)){const b=cache.get(a.id);let peak=0;for(let c=0;c<b.numberOfChannels;c++){const x=b.getChannelData(c);for(let j=0;j<x.length;j+=4)peak=Math.max(peak,Math.abs(x[j]));}if(peak<.001)throw Error('Inaudible source sample '+a.title);calibration.set(a.id,Math.min(4,.65/peak));}
 used.set(a.id,a);const s=ctx.createBufferSource(),g=ctx.createGain();s.buffer=cache.get(a.id);s.playbackRate.value=2**((e.pitch-a.pitch-(a.tuning_cents??0)/100)/12);s.connect(g);const pan=ctx.createStereoPanner();pan.pan.value=(project.mix?.tracks?.[e.instrument]?.pan??(/flute|clarinet/i.test(e.instrument)?.18:/cello/i.test(e.instrument)?-.16:/harp/i.test(e.instrument)?-.22:0));g.connect(pan);const eq=ctx.createBiquadFilter();eq.type='highshelf';eq.frequency.value=2200;eq.gain.value=project.mix?.tracks?.[e.instrument]?.eq??0;pan.connect(eq);eq.connect(master);
 const end=Math.min(project.seconds,e.time+e.duration,s.buffer.duration/s.playbackRate.value+e.time);if(end<=e.time)continue;const wind=/flute|clarinet|cello|bansuri/i.test(e.instrument);const attack=Math.min(wind?.18:.012,(end-e.time)/3),release=Math.min(wind?.65:1.15,(end-e.time)/2);g.gain.setValueAtTime(0,e.time);const level=e.velocity*calibration.get(a.id)*(project.mix?.tracks?.[e.instrument]?.gain??1);g.gain.linearRampToValueAtTime(level,e.time+attack);g.gain.setValueAtTime(level,end-release);g.gain.linearRampToValueAtTime(0,end);s.start(e.time);s.stop(end);
 }
 if(project.natureIntensity>0){
 const candidates=catalog.filter(a=>a.kind==='nature'&&a.reviewed===true&&['CC0-1.0','CC-BY-4.0'].includes(a.license));
 if(!candidates.length)throw Error('No verified nature recording available');
 const a=candidates[project.seed%candidates.length],res=await fetch(a.path);if(!res.ok)throw Error('Nature recording missing');
 const buffer=await ctx.decodeAudioData(await res.arrayBuffer());if(buffer.duration<2)throw Error('Nature recording too short');
 used.set(a.id,a);const overlap=Math.min(2,buffer.duration/4),step=buffer.duration-overlap,level=project.natureIntensity/100*.24;
 for(let start=0;start<project.seconds;start+=step){const source=ctx.createBufferSource(),gain=ctx.createGain();source.buffer=buffer;source.connect(gain);gain.connect(master);const end=Math.min(project.seconds,start+buffer.duration),fade=Math.min(overlap,(end-start)/2);gain.gain.setValueAtTime(0,start);gain.gain.linearRampToValueAtTime(level,start+fade);gain.gain.setValueAtTime(level,end-fade);gain.gain.linearRampToValueAtTime(0,end);source.start(start);source.stop(end);}
 }
 const masterLevel=.55*(project.mix?.master??.75)/.75;const fade= Math.min(1.5,project.seconds/4);master.gain.setValueAtTime(0,0);master.gain.linearRampToValueAtTime(masterLevel,fade);master.gain.setValueAtTime(masterLevel,project.seconds-fade);master.gain.linearRampToValueAtTime(0,project.seconds);const audio=await ctx.startRendering();let peak=0;for(let c=0;c<2;c++)for(const x of audio.getChannelData(c))peak=Math.max(peak,Math.abs(x));if(!Number.isFinite(peak)||peak<.0001)throw Error('Silent or invalid render');
 if(peak>.85){const factor=.85/peak;for(let c=0;c<2;c++){const data=audio.getChannelData(c);for(let i=0;i<data.length;i++)data[i]*=factor;}peak*=factor;}return {blob:wav(audio),peak,metrics:measure?analyze(audio):null,licenses:[...used.values()]};
}
function wav(b){const n=b.length*4,ab=new ArrayBuffer(44+n),v=new DataView(ab);const str=(p,s)=>{for(let i=0;i<s.length;i++)v.setUint8(p+i,s.charCodeAt(i))};str(0,'RIFF');v.setUint32(4,36+n,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,2,true);v.setUint32(24,b.sampleRate,true);v.setUint32(28,b.sampleRate*4,true);v.setUint16(32,4,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,n,true);const l=b.getChannelData(0),r=b.getChannelData(1);for(let i=0;i<b.length;i++){v.setInt16(44+i*4,Math.max(-1,Math.min(1,l[i]))*32767,true);v.setInt16(46+i*4,Math.max(-1,Math.min(1,r[i]))*32767,true)}return new Blob([ab],{type:'audio/wav'})}
