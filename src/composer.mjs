export function compose({seed, mood='spa', seconds=30, instruments=['piano'], complexity=35, natureIntensity=0}) {
 if(!Number.isFinite(seconds)||seconds<15||seconds>120) throw Error('Preview duration must be 15–120 seconds');
 if(!instruments.length) throw Error('Select an available instrument');
 complexity=Math.max(0,Math.min(100,Number(complexity)||0)); natureIntensity=Math.max(0,Math.min(100,Number(natureIntensity)||0));
 let state=seed>>>0; const random=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296};
 const pick=a=>a[Math.floor(random()*a.length)];
 const root=pick([48,50,53,55,57]); const beat=60/(mood==='sleep'?48:mood==='focus'?72:mood==='cinematic'?66:60);
 const modal=mood==='zen'||mood==='indian'; const scale=modal?[0,2,4,7,9]:[0,2,4,5,7,9,11];
 const progression=pick([[0,5,3,4],[0,3,5,4],[0,4,5,3]]); const events=[];
 const motif=Array.from({length:4},()=>Math.floor(random()*scale.length));
 const note=(instrument,pitch,time,duration,velocity)=>events.push({instrument,pitch,time,duration:Math.min(duration,seconds-time),velocity});
 for(let bar=0;bar*4*beat<seconds;bar++){
 const t=bar*4*beat, degree=progression[bar%4]%scale.length;
 const chord=[0,2,4].map(i=>root+scale[(degree+i)%scale.length]+12*Math.floor((degree+i)/scale.length));
 for(let i=0;i<instruments.length;i++){
 const instrument=instruments[i]; if(i>0&&bar%8===7)continue;
 if(i===0&&!modal){for(let j=0;j<(complexity<25?1:complexity<55?2:3);j++){const start=t+j*beat*.7;if(start<seconds)note(instrument,chord[j],start,beat*2.5,.22+random()*.08);}}
 else {const count=complexity<25?1:complexity<65?2:3; for(let j=0;j<count;j++){const start=t+j*beat*(count===3?1.1:1.7)+random()*.07;if(start>=seconds)continue;const d=(motif[(bar+j)%4]+(bar%4===3?1:0))%scale.length;note(instrument,root+12+scale[d],start,beat*(1.1+random()),.24+random()*.12);}}
 }
 }
 return {seed,mood,seconds,complexity,natureIntensity,events};
}
export function fingerprint(project){return JSON.stringify(project.events.map(e=>[e.instrument,e.pitch,Math.round(e.time*4),Math.round(e.duration*4)]))}
