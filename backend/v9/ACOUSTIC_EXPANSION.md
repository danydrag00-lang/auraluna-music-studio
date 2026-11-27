# Acoustic expansion candidates

The active Kaggle asset dataset is unchanged. Stage new recordings separately and review each source licence and audible quality before publishing or integrating with the renderer.

| Instrument | Source | Declared licence |
|---|---|---|
| Clarinet, oboe, bassoon | https://github.com/sgossner/VSCO-2-CE | CC0 |
| Classical guitar | https://freepats.zenvoid.org/Guitar/acoustic-guitar.html | CC0 |
| Ocarina | https://freepats.zenvoid.org/Wind/ocarina.html | CC0 |
| Tubular bells | https://freepats.zenvoid.org/ChromaticPercussion/tubular-bells.html | CC0 |

The staging script accepts an exact reviewed VSCO commit, checks WAV metadata, copies original bytes, deduplicates by SHA-256, and stores licence evidence. It does not enable the samples, claim independent rights clearance, or change the private production dataset. The FreePats entries are candidates only.

Before production integration: review recording-specific exclusions and attribution, audition each articulation, map playable pitches and velocities, verify sustain and release, render representative passages, inspect clipping and silence, then update the private dataset and renderer together.
