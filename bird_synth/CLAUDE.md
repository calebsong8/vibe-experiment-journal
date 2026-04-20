# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page browser app ("Manus ad Avem") that uses MediaPipe Hands to track two hands via webcam:
- **Hand 1** generates a 5-point waveform from fingertip Y positions, matched via Euclidean distance to the closest of 25 hard-coded birds, driving an oscillator.
- **Hand 2** controls volume via thumb-pinky distance and renders a bird image hologram between those points.
- A second mode ("Bird Calls") plays pre-fetched real audio clips instead of synthesizing them.

## Running the app

Serve the repo root — `index.html` must be loaded over HTTP (camera/audio require a secure or local context):

```bash
python -m http.server
```

Then open `http://localhost:8000` in Chrome or Edge (best MediaPipe performance).

## Python tooling — audio downloader

`download_birds.py` fetches bird call clips from Wikimedia Commons (with xeno-canto fallback) into `audio/birds/<slug>/`. No dependencies beyond stdlib.

```bash
# run the downloader
python download_birds.py

# run pytest tests
pytest tests/test_download_birds.py

# run a single test
pytest tests/test_download_birds.py::test_slug_spaces_to_underscores

# lint
ruff check download_birds.py tests/
ruff format download_birds.py tests/
```

## Browser tests

`tests/test.html` is a self-contained in-browser test runner (no build step). Open it via the local server: `http://localhost:8000/tests/test.html`.

It re-implements the pure JS functions from `index.html` (bird database generation, `findClosestBird`, `getBirdSlug`, `calcPitchMultiplier`, etc.) and runs sync + async test suites. All 25 bird names and the wave-generation algorithm must stay in sync between `index.html` and `tests/test.html`.

## Key invariants

- The `birdDatabase` array is generated deterministically: `index = (i * 17) % 243`, wave values decoded from base-3 digits → `[0.2, 0.5, 0.8]`. Changing the algorithm or bird list order breaks wave matching and the browser test suite.
- Audio slugs: spaces and hyphens both become `_`, all lowercase — same logic in `download_birds.py::slug()` and `index.html::getBirdSlug()`. These must stay identical.
- Audio files live at `audio/birds/<slug>/<n>.mp3` or `.ogg`, numbered from 1. The app tries `.mp3` first, then `.ogg`, and stops at the first missing index.
- `MAX_CLIPS = 2` in `download_birds.py`; the browser uses `MAX_CLIPS_PER_BIRD = 3`. The browser gracefully handles fewer files.
