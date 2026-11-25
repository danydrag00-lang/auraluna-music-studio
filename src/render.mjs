export async function render(project,catalog){
 const rate=44100, ctx=new OfflineAudioContext(2,Math.ceil(project.seconds*rate),rate);
 const master=ctx.createGain();master.gain.value=.55;const compressor=ctx.createDynamicsCompressor();master.connect(compressor);compressor.connect(ctx.destination);
 const assets=catalog.filter(a=>a.kind==='note'&&['CC0-1.0','CC-BY-4.0'].includes(a.license)&&a.reviewed===true);
 const cache=new Map();const used=new Map();
 for(const e of project.events){
 const a=assets.filter(x=>x.instrument===e.instrument&&Math.abs(x.pitch-e.pitch)<=3).sort((x,y)=>Math.abs(x.pitch-e.pitch)-Math.abs(y.pitch-e.pitch))[0];
 if(!a)throw Error('Missing verified sample for '+e.instrument+' MIDI '+e.pitch);
 if(!cache.has(a.id)){const res=await fetch(a.path);if(!res.ok)throw Error('Missing local audio '+a.id);cache.set(a.id,await ctx.decodeAudioData(await res.arrayBuffer()));}
 used.set(a.id,a);const s=ctx.createBufferSource(),g=ctx.createGain();s.buffer=cache.get(a.id);s.playbackRate.value=2**((e.pitch-a.pitch)/12);s.connect(g);g.connect(master);
 const end=Math.min(project.seconds,e.time+e.duration,s.buffer.duration/s.playbackRate.value+e.time);if(end<=e.time)continue;const attack=Math.min(.05,(end-e.time)/3),release=Math.min(.35,(end-e.time)/3);g.gain.setValueAtTime(0,e.time);g.gain.linearRampToValueAtTime(e.velocity,e.time+attack);g.gain.setValueAtTime(e.velocity,end-release);g.gain.linearRampToValueAtTime(0,end);s.start(e.time);s.stop(end);
 }
 const audio=await ctx.startRendering();let peak=0;for(let c=0;c<2;c++)for(const x of audio.getChannelData(c))peak=Math.max(peak,Math.abs(x));if(!Number.isFinite(peak)||peak<.0001)throw Error('Silent or invalid render');
 return {blob:wav(audio),peak,licenses:[...used.values()]};
}
function wav(b){const n=b.length*4,ab=new ArrayBuffer(44+n),v=new DataView(ab);const str=(p,s)=>{for(let i=0;i<s.length;i++)v.setUint8(p+i,s.charCodeAt(i))};str(0,'RIFF');v.setUint32(4,36+n,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,2,true);v.setUint32(24,b.sampleRate,true);v.setUint32(28,b.sampleRate*4,true);v.setUint16(32,4,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,n,true);const l=b.getChannelData(0),r=b.getChannelData(1);for(let i=0;i<b.length;i++){v.setInt16(44+i*4,Math.max(-1,Math.min(1,l[i]))*32767,true);v.setInt16(46+i*4,Math.max(-1,Math.min(1,r[i]))*32767,true)}return new Blob([ab],{type:'audio/wav'})}
