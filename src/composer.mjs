// Acoustic relaxation composer: slow harmonic rhythm, intentional silence and melodic voice leading.
export function compose({seed,mood='spa',seconds=30,instruments=['piano'],complexity=35,natureIntensity=0,tonalRoot=null}){
 if(!Number.isFinite(seconds)||seconds<15||seconds>600)throw Error('Duration must be 15–600 seconds');
 if(!instruments.length)throw Error('Select an available instrument');
 complexity=Math.max(0,Math.min(100,Number(complexity)||0));natureIntensity=Math.max(0,Math.min(100,Number(natureIntensity)||0));
 let state=seed>>>0;const random=()=>{state=(state+0x6D2B79F5)>>>0;let t=state;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296};
 const pick=a=>a[Math.floor(random()*a.length)];
 const initialRoot=pick([48,50,53,55,57]),root=Number.isInteger(tonalRoot)?tonalRoot:initialRoot;
 const bpm={sleep:42,spa:48,zen:44,indian:46,cinematic:56,focus:62}[mood]||48,beat=60/bpm,barLength=8*beat;
 const pentatonic=mood==='zen'||mood==='indian',minor=mood==='cinematic';
 const chords=pentatonic?[[0,7,12,14],[0,7,12,16],[0,7,12,19],[0,7,12,14]]:minor?[[0,7,12,15],[0,7,10,15],[-4,3,8,12],[-2,5,10,14]]:[[0,7,12,16],[-3,4,9,12],[-5,2,7,12],[-5,2,7,14]];
 const order=pick([[0,1,2,3],[0,2,1,3],[0,1,3,2]]);
 const events=[];const roles=instruments.map((instrument,i)=>({instrument,i,wind:/flute|bansuri|clarinet|saxophone|duduk|ney/i.test(instrument),cello:/cello/i.test(instrument)}));
 const keyboard=roles.find(r=>!r.wind&&!r.cello);
 const lead=roles.find(r=>r.wind)||roles.find(r=>r!==keyboard&&!r.cello);
 const note=(instrument,pitch,time,duration,velocity)=>{if(time>=seconds)return;events.push({instrument,pitch,time,duration:Math.min(duration,seconds-time),velocity});};
 const shift=pick([0,1,2]);let lastMelody=root+12;
 for(let bar=0;bar*barLength<seconds;bar++){
  const t=bar*barLength, chord=chords[order[bar%4]], rest=bar%4===3;
  if(keyboard){
   const n=complexity<25?2:complexity<70?3:4;
   const tones=[chord[0],chord[1],chord[2],chord[3]];
   for(let j=0;j<n;j++){const start=t+(j===0?.12:1.2+j*1.25+random()*.22)*beat;note(keyboard.instrument,root+tones[j],start,beat*(j===0?6:4.3),(.14+random()*.045)*(mood==='sleep'?.8:1));}
  }
  for(const r of roles){
   if(r===keyboard)continue;
   if(r.cello){if(bar%4!==3||!keyboard&&!lead)note(r.instrument,root+chord[0],t+.55*beat,beat*5.8,.11+random()*.025);continue;}
   if(r!==lead&&roles.length>2&&bar%3!==r.i%3)continue;
   if(rest&&bar>0&&keyboard)continue;
   const count=complexity<35?1:2;
   for(let j=0;j<count;j++){
    const choices=chord.slice(1).map(p=>root+p).filter(p=>p>=55&&p<=76);
    const ranked=choices.sort((a,b)=>Math.abs(a-lastMelody)-Math.abs(b-lastMelody));
    const pitch=ranked[(shift+bar+j)%Math.min(2,ranked.length)]??root+12;
    const start=t+(1.7+j*3+random()*.17)*beat;
    note(r.instrument,pitch,start,beat*(r.wind?2.25:3.2),.105+random()*.035);lastMelody=pitch;
   }
  }
 }
 events.sort((a,b)=>a.time-b.time);
 return {seed,mood,seconds,tonalRoot:root,instruments:[...instruments],complexity,natureIntensity,events};
}
export function fingerprint(project){return JSON.stringify(project.events.map(e=>[e.instrument,e.pitch,Math.round(e.time*4),Math.round(e.duration*4)]))}
