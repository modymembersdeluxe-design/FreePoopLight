import os
import subprocess
import tempfile
import shutil
import random
from typing import Dict, Callable, List

from utils import download_url, safe_filename

def _run(cmd: List[str], cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, check=True)

def render_project(config: Dict, out_path: str, progress_callback: Callable[[str], None] = None):
    """
    Render a project configuration into out_path.

    config keys:
      - local_sources: list of local file paths
      - url_sources: list of URLs
      - stutter, reverse, scramble, earrape, overlay: booleans to enable effects

    This is a scaffolded renderer:
      - Downloads URLs to a temp dir
      - Optionally shuffles (scramble) source order
      - Optionally duplicates entries (stutter)
      - Optionally reverses clips (re-encodes reversed temp files)
      - Concatenates with ffmpeg and re-encodes to produce output
      - Applies a simple loudness filter for "earrape" and a tint overlay if requested
    """
    if progress_callback is None:
        progress_callback = lambda s: None

    tmp_root = tempfile.mkdtemp(prefix="freepoop_render_")
    try:
        progress_callback("Preparing sources...")
        sources = list(config.get("local_sources", []))
        # download URLs
        url_sources = config.get("url_sources", [])
        for url in url_sources:
            progress_callback(f"Downloading: {url}")
            try:
                fpath = download_url(url, dest_dir=tmp_root)
                sources.append(fpath)
            except Exception as e:
                # skip failed downloads but notify
                progress_callback(f"Download failed: {e}")

        if not sources:
            raise RuntimeError("No sources available for render.")

        # Apply scramble: randomize order
        if config.get("scramble"):
            progress_callback("Scrambling sources...")
            random.shuffle(sources)

        # Apply stutter: duplicate each clip once (simple)
        if config.get("stutter"):
            progress_callback("Applying stutter...")
            duplicated = []
            for s in sources:
                duplicated.append(s)
                duplicated.append(s)  # naive duplication
            sources = duplicated

        # If reverse: create reversed versions as temp files
        processed = []
        for idx, src in enumerate(sources):
            cur = src
            if config.get("reverse"):
                progress_callback(f"Reversing clip {idx+1}/{len(sources)}...")
                rev = os.path.join(tmp_root, f"rev_{idx}_{safe_filename(os.path.basename(src))}.mp4")
                # reverse video and audio
                cmd = [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", src,
                    "-vf", "reverse",
                    "-af", "areverse",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                    "-c:a", "aac", "-b:a", "128k",
                    rev
                ]
                _run(cmd)
                cur = rev
            processed.append(cur)

        # Build ffmpeg concat list
        filelist = os.path.join(tmp_root, "files.txt")
        with open(filelist, "w", encoding="utf-8") as fh:
            for p in processed:
                # Use double-quoted filenames in the concat file and escape any double quotes in the path.
                escaped = p.replace('"', '\\"')
                fh.write('file "{}"\n'.format(escaped))

        # Build filter_complex if overlay or earrape requested
        filters = []
        afilters = []

        if config.get("earrape"):
            # raise audio volume significantly (user beware)
            afilters.append("volume=6")

        vf_extra = ""
        if config.get("overlay"):
            # add a simple color tint overlay using color source and blend
            # We'll add that as a -filter_complex applied after concat by using overlay on the merged stream.
            # For simplicity, we encode the concatenated video and then overlay by running ffmpeg again.
            progress_callback("Will apply overlay after concat step.")

        progress_callback("Concatenating and encoding final output...")
        # Concatenate and encode (safer than copy)
        cmd_concat = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", filelist,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k"
        ]
        # If there are audio filters
        if afilters:
            cmd_concat += ["-af", ",".join(afilters)]
        tmp_out = os.path.join(tmp_root, "concat_out.mp4")
        cmd_concat += [tmp_out]
        _run(cmd_concat)

        final_out = out_path
        if config.get("overlay"):
            progress_callback("Applying overlay tint...")
            # overlay: create a semi-transparent color and blend over video
            # Generate a color source sized to the video using ffmpeg's color filter; center overlay
            # Note: we scale to 1280x720 as a simple default; for production, detect source resolution.
            cmd_overlay = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", tmp_out,
                "-f", "lavfi", "-i", "color=green@0.14:size=1280x720",
                "-filter_complex", "[0:v]scale=1280:720:force_original_aspect_ratio=decrease[p];[p][1:v]overlay=(W-w)/2:(H-h)/2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "copy",
                final_out
            ]
            _run(cmd_overlay)
        else:
            # move/rename tmp_out to final out (or copy)
            shutil.move(tmp_out, final_out)

        progress_callback("Render finished.")
    finally:
        # cleanup temporary files
        try:
            shutil.rmtree(tmp_root)
        except Exception:
            pass