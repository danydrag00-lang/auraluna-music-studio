"""Run genuine ACE-Step inference on a CUDA worker, not GitHub Pages."""
import argparse,json,pathlib,sys,random
p=argparse.ArgumentParser()
p.add_argument('--request',required=True);p.add_argument('--model-root',required=True);p.add_argument('--output',required=True)
a=p.parse_args()
req=json.loads(pathlib.Path(a.request).read_text())
duration=int(req['duration']);caption=str(req['caption']).strip()
if not 15<=duration<=120 or not caption or len(caption)>2000:raise ValueError('Invalid request')
root=pathlib.Path(a.model_root).resolve();sys.path.insert(0,str(root))
import torch
if not torch.cuda.is_available():raise RuntimeError('Enable a CUDA GPU accelerator before running')
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams,GenerationConfig,generate_music
handler=AceStepHandler();lm=LLMHandler()
handler.initialize_service(project_root=str(root),config_path='acestep-v15-turbo',device='cuda')
output=pathlib.Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
results=[]
for i in range(int(req.get('variations',3))):
 seed=random.SystemRandom().randrange(1,2**31)
 params=GenerationParams(task_type='text2music',caption=caption,lyrics='[Instrumental]',instrumental=True,thinking=False,duration=duration,bpm=int(req['bpm']),seed=seed,inference_steps=8)
 config=GenerationConfig(batch_size=1,audio_format='wav')
 result=generate_music(handler,lm,params,config,save_dir=str(output))
 if not result.success:raise RuntimeError(str(result.error))
 for audio in result.audios:results.append({'path':str(audio['path']),'seed':seed})
(output/'generation-report.json').write_text(json.dumps({'model':'acestep-v15-turbo','request':req,'tracks':results},indent=2))
