const {chromium}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
// Exercise the canonical cloud studio without spending Kaggle quota or using real secrets.
function fixtureWav(seconds=60){
 const rate=8000,n=rate*seconds,b=Buffer.alloc(44+n*2);
 b.write('RIFF',0);b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*2,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(n*2,40);
 for(let i=0;i<n;i++)b.writeInt16LE(Math.round(3000*Math.sin(2*Math.PI*220*i/rate)),44+2*i);
 return b;
}
(async()=>{
 const root=process.cwd();
 const server=http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const file=path.resolve(root,'.'+(pathname==='/'?'/index.html':pathname));
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);res.end();return}
  const types={'.html':'text/html','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.wav':'audio/wav'};
  res.setHeader('Content-Type',types[path.extname(file)]||'application/octet-stream');fs.createReadStream(file).pipe(res)
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 let browser;
 try{
  browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message)});
  const slug='auraluna-'+'a'.repeat(32),wave=fixtureWav();
  const files=[1,2,3].flatMap(v=>['music.wav','completed.json','licences.json'].map(name=>({name:'variation_'+v+'/'+name})));
  await page.route('https://auraluna-api.dhanushmanoharan1996.workers.dev/**',async route=>{
   const req=route.request(),u=new URL(req.url());
   const headers={'access-control-allow-origin':'*','access-control-allow-headers':'authorization, content-type','access-control-allow-methods':'GET, POST, OPTIONS'};
   const json=data=>route.fulfill({status:200,headers,contentType:'application/json',body:JSON.stringify(data)});
   if(req.method()==='OPTIONS')return route.fulfill({status:204,headers});
   if(u.pathname==='/health')return json({version:'V25-studio-premium',configured:true,cpuRouting:true});
   assert.equal(req.headers().authorization,'Bearer smoke-test-only');
   if(u.pathname==='/test-kaggle')return json({ok:true});
   if(u.pathname==='/generate'){requests.push(req.postDataJSON());return json({slug,compute:'CPU',seed:'SmokeSeed',seedVariation:1,composition:'thematic',aacMode:'premium',tuning:'standard'});}
   if(u.pathname==='/status')return json({status:'COMPLETE'});
   if(u.pathname==='/outputs')return json({files});
   if(u.pathname==='/file'&&u.searchParams.get('file')?.endsWith('.wav'))return route.fulfill({status:200,headers,contentType:'audio/wav',body:wave});
   return route.fulfill({status:404,headers,body:'Unexpected mocked endpoint: '+u.pathname});
  });
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  assert.match(await page.title(),/Auraluna Music Studio/);
  assert.equal(await page.locator('#generate').isDisabled(),true);
  await page.fill('#access-key','smoke-test-only');await page.click('#connect');
  await page.locator('#generate:enabled').waitFor();
  await page.selectOption('#composition-engine','studio');
  await page.selectOption('#composition-style','thematic');
  await page.selectOption('#format','wav');
  await page.fill('#duration','1');
  await page.click('#preview');
  await page.waitForFunction(()=>document.querySelectorAll('#players audio').length===3,{},{timeout:30000});
  await page.locator('#generate:enabled').waitFor();
  assert.equal(requests.length,1);
  assert.equal(requests[0].engine,'studio');assert.equal(requests[0].seconds,60);assert.equal(requests[0].variations,3);assert.equal(requests[0].composition,'thematic');
  await page.getByRole('button',{name:'Load audio',exact:true}).first().click();
  await page.waitForFunction(()=>{const a=document.querySelector('#players audio');return a&&!a.hidden&&a.readyState>=1});
  const metrics=await page.locator('#players audio').first().evaluate(async a=>{const ctx=new AudioContext();try{const b=await ctx.decodeAudioData(await(await fetch(a.src)).arrayBuffer());let peak=0,sum=0,n=0;for(const x of b.getChannelData(0)){peak=Math.max(peak,Math.abs(x));sum+=x*x;n++;}return {duration:b.duration,peak,rms:Math.sqrt(sum/n)}}finally{await ctx.close()}});
  assert.ok(Math.abs(metrics.duration-60)<.01);assert.ok(metrics.peak>.001&&metrics.peak<.99);assert.ok(metrics.rms>.0001);
  await page.waitForFunction(()=>document.querySelector('#players .v9-waveform input:not(:disabled)'));
  assert.equal(errors.length,0,errors.join('; '));
  console.log('Cloud studio smoke test passed with mocked API and deterministic WAV fixture',metrics);
 }finally{await browser?.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
