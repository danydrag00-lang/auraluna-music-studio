# Auraluna Music Studio

Browser-local instrumental composition using licensed, locally hosted acoustic samples. No paid generation API.

## Status
Initial implementation; no verified recordings are bundled yet. The application must refuse generation when required samples are absent. The 10,000 asset library is a target, not an inventory claim.

## Architecture
Catalog owns asset provenance and sample coverage. Composer owns seeded symbolic note events. Renderer owns Web Audio playback and WAV encoding. UI coordinates these modules. A local browser approach avoids server compute; a separate offline renderer is a future option for multi-hour exports.

Serve the repository with `python3 -m http.server 8000` and open http://localhost:8000. Import reviewed audio with the ingestion script. Source recording licences remain separate from code rights.
