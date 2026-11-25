// A thematic acoustic score, not independently randomized note loops.
export function compose({seed,mood='spa',seconds=30,instruments=['piano'],complexity=35,natureIntensity=0,tonalRoot=null,mix=null}){
 if(!Number.isFinite(seconds)||seconds<15||seconds>600)throw Error('Duration must be 15–600 seconds');
 if(!instruments.length)throw Error('Select an available instrument');
 complexity=Math.max(0,Math.min(100,Number(complexity)||0));natureIntensity=Math.max(0,Math.min(100,Number(natureIntensity)||0));
 let state=seed>>>0;const random=()=>{state=(state+0x6D2B79F5)>>>0;let t=state;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296};
 const pick=a=>a[Math.floor(random()*a.length)];
 const initialRoot=pick([48,50,53,55,57]),root=Number.isInteger(tonalRoot)?tonalRoot:initialRoot;
 const bpm={sleep:48,spa:56,zen:48,indian:52,cinematic:56,focus:62}[mood]||56,beat=60/bpm;
 const modal=mood==='zen'||mood==='indian',minor=mood==='cinematic';
 const scale=modal?[0,2,4,7,9]:minor?[0,2,3,5,7,8,10]:[0,2,4,5,7,9,11];
 const degree=d=>scale[((d%scale.length)+scale.length)%scale.length]+12*Math.floor(d/scale.length);
 // Eight-bar antecedent and consequent, with a genuine return to tonic.
 const harmony=modal?[0,0,3,0,0,4,3,0]:pick([[0,0,5,3,0,3,4,0],[0,3,0,4,5,3,4,0]]);
 const themes=modal?[[0,1,2,1,0,2,3,2],[2,3,4,3,2,1,2,0]]:[[0,1,2,4,2,1,0,2],[2,1,0,4,3,2,1,0],[4,2,1,2,3,2,1,0]];
 const theme=pick(themes),variation=pick([0,1]);const events=[];
 const wind=n=>/flute|clarinet|bansuri|saxophone|duduk|ney/i.test(n),bow=n=>/cello/i.test(n);
 const keys=instruments.find(n=>!wind(n)&&!bow(n));const lead=instruments.find(wind)||keys||instruments[0];
 const bass=instruments.find(n=>bow(n)&&n!==lead);
 const put=(instrument,pitch,time,duration,velocity,role)=>{if(time>=seconds)return;events.push({instrument,pitch,time,duration:Math.min(duration,seconds-time),velocity,role});};
 const fit=(pitch,lo,hi)=>{while(pitch<lo)pitch+=12;while(pitch>hi)pitch-=12;return pitch};
 for(let bar=0;bar*4*beat<seconds;bar++){
  const t=bar*4*beat,k=bar%8,section=Math.floor(bar/8),h=harmony[k],cadence=k===7,shape=.85+.15*Math.sin(Math.PI*(k+1)/9);
  const chord=modal?[degree(h),degree(h+2),degree(h+3)]:[degree(h),degree(h+2),degree(h+4)];
  if(keys&&keys!==lead){put(keys,fit(root+chord[0],43,57),t,beat*3.8,.105*shape,'bass');put(keys,fit(root+chord[1]+12,55,69),t+beat*.15,beat*3.5,.075*shape,'harmony');if(complexity>=35)put(keys,fit(root+chord[2]+12,55,69),t+beat*1.1,beat*2.7,.06*shape,'harmony');}
  if(bass)put(bass,fit(root+chord[0],45,60),t+.1,beat*3.7,.07*shape,'bass');
  const sparse=mood==='sleep'&&complexity<25;
  // Motif is repeated deliberately with altered contour in the B phrase, then resolved.
  const d=cadence?0:theme[(k+(section%3===1?variation:0))%8];
  const melodic=fit(root+12+degree(d),60,76);
  const pitch=bow(lead)?fit(melodic,48,65):melodic;
  const count=sparse?1:(complexity>=25&&!cadence&&k%4!==3?2:1);
  const offset=.13+random()*.06;
  put(lead,pitch,t+offset,beat*(count===1?3.35:1.65),(.14+random()*.025)*shape,'melody');
  if(count===2){const next=fit(root+12+degree(theme[(k+1)%8]),60,76);put(lead,bow(lead)?fit(next,48,65):next,t+beat*2+.04,beat*1.65,.11*shape,'melody');}
  if(keys===lead&&(!sparse||k%2===0))put(keys,fit(root+chord[0],43,55),t,beat*3.8,.085*shape,'bass');
  for(const n of instruments){if(n===lead||n===keys||n===bass)continue;if(k%4===1&&section%2===0)put(n,fit(root+chord[2]+12,55,69),t+beat*.6,beat*2.8,.045,'texture');}
 }
 events.sort((a,b)=>a.time-b.time);
 return {seed,mood,seconds,tonalRoot:root,instruments:[...instruments],complexity,natureIntensity,mix,events};
}
export function fingerprint(project){return JSON.stringify(project.events.map(e=>[e.instrument,e.pitch,Math.round(e.time*4),Math.round(e.duration*4)]))}
