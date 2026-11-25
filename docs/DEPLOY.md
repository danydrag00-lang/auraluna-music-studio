# Pilot setup
For personal/noncommercial hosting, open Settings > Pages, choose Deploy from a branch, main, / (root), Save. GitHub Pages is not intended for commercial SaaS and has a 1 GB site limit. Use alternative hosting if your intended use exceeds its policies.
Run python3 scripts/discover_commons.py to build the review queue. Review each source page, underlying rights, listen to the original and verify pitch for notes. Run python3 scripts/import_candidate.py --help for approved imports. FFmpeg must be installed. Commit the small pilot audio files and catalog together. Do not use normal Git history for a 10,000-recording library. Candidate counts are not verified asset counts.
Run node --test tests/composer.test.mjs before publishing.
