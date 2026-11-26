# Auraluna GPU pilot
Use a Kaggle notebook with Internet enabled and GPU accelerator selected, subject to account quota. Upload the request JSON as a notebook input. Follow the official installation instructions at https://github.com/ace-step/ACE-Step-1.5 (Python 3.11–3.12). The initial pilot uses turbo, no optional language model, sequential generation. The website does not automatically submit jobs or access your Kaggle account.
After installing ACE-Step and its dependencies, run:
```sh
python /path/to/auraluna/backend/generate_ace.py --request /path/to/auraluna-request.json --model-root /path/to/ACE-Step-1.5 --output /kaggle/working/auraluna
```
Download WAVs from notebook output and open them in AI music workspace. Check official model weights and terms before commercial use; no guarantee of uniqueness or Content ID clearance. GPU execution and listening validation pending.
