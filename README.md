# FreePoop Light — Super Deluxe (Tkinter Deluxe)

What this is
------------

A deluxe GUI to create YouTube Poop–style videos (YTP, YTP tennis, YTPMV).
Source browsers for local video/audio/images/gifs/transition clips and a list to register online URLs.
Preview (uses FFplay if installed, otherwise FFmpeg).
Effects toggles (stutter, scramble, reverse, ear-rape, overlays, etc.) implemented as pipeline flags.
Export using ffmpeg. Robust write routines to support ffmpeg.

Files in this scaffold
- main.py — entry point
- gui.py — main Tkinter UI and wiring
- preview.py — preview helper using ffplay/ffmpeg
- renderer.py — generation pipeline implementing many Poopisms (scaffold/hook-based)
- utils.py — helpers including a downloader that prefers yt-dlp and falls back to requests
- README.md — this file

Requirements
------------
- Python 3.8+
- ffmpeg and/or ffplay on PATH (preview and rendering use ffmpeg binaries)
- Optional but recommended: yt-dlp for robust URL downloads
- Python packages: requests (and optionally yt-dlp). Example:
  python -m pip install requests

Running
-------
Create a virtualenv and install requirements, then run:

python main.py

Notes
-----
- This is a scaffold designed to be extended. The renderer implements simple versions of effects:
  - scramble: randomizes clip order
  - stutter: duplicates clips to produce repetition
  - reverse: re-encodes reversed clips
  - earrape: boosts audio volume (beware loudness)
  - overlay: applies a simple tint overlay post-concatenation
- Downloads use yt-dlp if available; otherwise the code will attempt a streaming HTTP download with requests.
- For robustness in production, integrate more advanced handling: progress reporting in GUI, more robust ffmpeg filter graphs, VapourSynth/AviSynth hooks, remuxing and safe codec parametrization, and safer temp file cleanup.

If you'd like, I can:
- Open a PR that wires this into an existing repository,
- Add GUI progress bars for downloads and render,
- Integrate a proper yt-dlp options UI (format selection, audio-only),
- Add VapourSynth preprocessing hooks or a Pygame preview mode.