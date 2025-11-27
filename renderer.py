import os
import subprocess
import tempfile
import shutil
import random
import math
from typing import Dict, Callable, List, Optional

from utils import download_url, safe_filename

# Helper to run subprocess and surface useful errors
def _run(cmd: List[str], cwd: Optional[str] = None):
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        # include the command in the raised exception for debugging
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{e}") from e

def _ffmpeg_safe_path(p: str) -> str:
    """
    Make a path safe for ffmpeg concat demuxer on Windows:
    - absolute path
    - forward slashes
    - escape single quotes
    """
    ap = os.path.abspath(p)
    ap = ap.replace("\\", "/")
    ap = ap.replace("'", "\\'")
    return ap

def _semitone_ratio(semitones: int) -> float:
    """Return frequency ratio for semitone shift."""
    return 2 ** (semitones / 12.0)

def _build_audio_pitch_filters(semitones: int, preserve_speed: bool):
    """
    Build ffmpeg audio filter string to shift pitch by semitones.
    If preserve_speed=True, apply a correction atempo filter to keep tempo constant.
    Uses asetrate -> aresample -> atempo chain.
    """
    if semitones == 0:
        return None
    ratio = _semitone_ratio(semitones)
    # asetrate multiplies sample rate; then aresample back to original
    filters = []
    filters.append(f"asetrate=sample_rate*{ratio:.6f}")
    if preserve_speed:
        # atempo supports 0.5-2.0 steps; for ratios outside range, chain them (but we will keep semitone shifts moderate)
        atempo = 1.0 / ratio
        # if atempo outside 0.5-2.0, split into chained atempo filters:
        if atempo < 0.5 or atempo > 2.0:
            # split into factors of 2 or 0.5 as needed
            factors = []
            v = atempo
            while v < 0.5:
                factors.append(0.5)
                v /= 0.5
            while v > 2.0:
                factors.append(2.0)
                v /= 2.0
            factors.append(round(v, 6))
            filters.append("aresample=async=1")  # ensure sample rate restored before atempo
            for f in factors:
                filters.append(f"atempo={f}")
        else:
            filters.append("aresample=async=1")
            filters.append(f"atempo={atempo:.6f}")
    else:
        # do not correct tempo; just resample back to normal rate so pitch changes speed
        filters.append("aresample=44100")
    return ",".join(filters)

def _build_tremolo_filter(depth: float = 0.5, freq: float = 8.0):
    # tremolo is available in recent ffmpeg: tremolo=f=<freq>:d=<depth>
    return f"tremolo=f={freq}:d={depth}"

def _normalize_video(src: str, dest: str, video_filters: Optional[str], audio_filters: Optional[str], target_size: str = "1280x720"):
    """
    Re-encode a clip to a normalized mp4 for safe concatenation.
    Apply video_filters (ffmpeg -vf string) and audio_filters (ffmpeg -af string) if provided.
    """
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
    ]
    if video_filters:
        cmd += ["-vf", video_filters]
    else:
        # ensure scaling to target size while preserving aspect
        cmd += ["-vf", f"scale={target_size}:force_original_aspect_ratio=decrease"]
    if audio_filters:
        cmd += ["-af", audio_filters]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        dest
    ]
    _run(cmd)

def _reverse_clip(src: str, dest: str):
    """Create a reversed video+audio clip."""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src,
        "-vf", "reverse",
        "-af", "areverse",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k",
        dest
    ]
    _run(cmd)

def render_project(config: Dict, out_path: str, progress_callback: Callable[[str], None] = None):
    """
    Extended renderer with many effects requested:
    - Uses categorized materials: videos, overlays, audios, sounds, gifs, urls
    - Respects clip_count limit and scramble/stutter options
    - New audio effects: pitch shift, tremolo, earrape (volume), high/low pitch (with/without speed)
    - New video effects: pixelate, bad quality, emboss, mirror symmetry, forward-reverse / reverse-forward
    - Overlay tint support
    Notes: This is still a scaffold. The generated ffmpeg filter_complex strings aim to be compatible with modern ffmpeg.
    """
    if progress_callback is None:
        progress_callback = lambda s: None

    tmp_root = tempfile.mkdtemp(prefix="freepoop_render_")
    try:
        progress_callback("Collecting source list...")
        # Gather sources from config
        sources = []
        # videos and gifs preferred as primary clips
        for v in config.get("videos", []):
            sources.append(v)
        for g in config.get("gifs", []):
            sources.append(g)
        # urls and local sounds/audios may also be used; include them as secondary
        for u in config.get("urls", []):
            # treat local file paths (from add_random_sounds) as already-local; download remote otherwise
            if os.path.exists(u):
                sources.append(u)
            else:
                progress_callback(f"Downloading: {u}")
                try:
                    fpath = download_url(u, dest_dir=tmp_root)
                    sources.append(fpath)
                except Exception as e:
                    progress_callback(f"Download failed: {e}")

        # Apply scramble (shuffle)
        if config.get("scramble"):
            progress_callback("Shuffling sources...")
            random.shuffle(sources)

        # Limit to clip_count
        clip_count = int(config.get("clip_count", 6) or 6)
        if len(sources) > clip_count:
            sources = sources[:clip_count]

        if not sources:
            raise RuntimeError("No source clips available for render.")

        # If stutter: duplicate each
        if config.get("stutter"):
            progress_callback("Applying stutter duplication...")
            dup = []
            for s in sources:
                dup.append(s)
                dup.append(s)
            sources = dup

        progress_callback("Processing individual clips (normalize/reverse/video effects)...")
        normalized = []
        # Predefine requested global audio filters from config
        semitones = int(config.get("pitch_semitones", 0) or 0)
        preserve_pitch_speed = bool(config.get("pitch_preserve", True))
        earrape = bool(config.get("earrape", False))
        overlay = bool(config.get("overlay", False))

        # Additional example effects toggles could be added to config dict; here's a basic set derived from request:
        # For demonstration we'll randomly apply some video effects per clip to create Poop-like variety.
        video_effects_pool = [
            None,
            "pixelate",
            "bad_quality",
            "emboss",
            "mirror_h",
            "mirror_v",
            "forward_reverse",
            "reverse_forward",
        ]

        for idx, src in enumerate(sources):
            progress_callback(f"Clip {idx+1}/{len(sources)}: {os.path.basename(src)}")
            # Decide per-clip video effect (you could expose controls in UI to be deterministic)
            vfx = random.choice(video_effects_pool)

            # Apply reverse-first transformations if needed
            cur = src
            # Build audio filter string for this clip
            audio_filters_list = []

            # Apply pitch shift if requested
            pf = _build_audio_pitch_filters(semitones, preserve_pitch_speed)
            if pf:
                audio_filters_list.append(pf)

            # Tremolo example: apply sometimes if pitch is zero but earrape not requested
            if random.random() < 0.12:
                audio_filters_list.append(_build_tremolo_filter(depth=0.6, freq=8.0))

            # Earrape: strong gain
            if earrape:
                audio_filters_list.append("volume=6")

            audio_filters = ",".join(audio_filters_list) if audio_filters_list else None

            # Video filter selection
            video_filters = None
            # forward_reverse: produce a temporary file with clip forward then reversed appended
            if vfx == "forward_reverse":
                # create reversed version and concat forward+reverse into a single clip file
                rev_tmp = os.path.join(tmp_root, f"rev_{idx}.mp4")
                _reverse_clip(cur, rev_tmp)
                forward_then_rev = os.path.join(tmp_root, f"fwd_rev_{idx}.mp4")
                with open(os.path.join(tmp_root, f"concat_{idx}.txt"), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(f"file '{_ffmpeg_safe_path(cur)}'\n")
                    fh.write(f"file '{_ffmpeg_safe_path(rev_tmp)}'\n")
                _run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", os.path.join(tmp_root, f"concat_{idx}.txt"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                    "-c:a", "aac", "-b:a", "128k",
                    forward_then_rev
                ])
                cur = forward_then_rev

            elif vfx == "reverse_forward":
                # reverse first then append forward
                rev_tmp = os.path.join(tmp_root, f"rev_{idx}.mp4")
                _reverse_clip(cur, rev_tmp)
                rev_then_fwd = os.path.join(tmp_root, f"rev_fwd_{idx}.mp4")
                with open(os.path.join(tmp_root, f"concat_{idx}.txt"), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(f"file '{_ffmpeg_safe_path(rev_tmp)}'\n")
                    fh.write(f"file '{_ffmpeg_safe_path(cur)}'\n")
                _run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", os.path.join(tmp_root, f"concat_{idx}.txt"),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                    "-c:a", "aac", "-b:a", "128k",
                    rev_then_fwd
                ])
                cur = rev_then_fwd

            elif vfx == "pixelate":
                # pixelate by downscaling and upscaling using neighbor sampling
                video_filters = "scale=iw/12:ih/12:flags=neighbor,scale=iw:ih:flags=neighbor"

            elif vfx == "bad_quality":
                # degrade by high CRF and adding noise
                video_filters = "noise=alls=20:allf=u,eq=brightness=0:saturation=0.8"  # heavy noise + slight desat

            elif vfx == "emboss":
                # convolution emboss kernel (approx)
                # kernel:  -2 -1 0 / -1 1 1 / 0 1 2  (rough emboss effect)
                video_filters = "convolution='-2 -1 0 -1 1 1 0 1 2':1:0"

            elif vfx == "mirror_h":
                # horizontal mirror side-by-side
                # split, hflip second, hstack
                video_filters = "split=2[a][b];[b]hflip[b];[a][b]hstack=inputs=2"

            elif vfx == "mirror_v":
                # vertical mirror stack
                video_filters = "split=2[a][b];[b]vflip[b];[a][b]vstack=inputs=2"

            # Normalize the clip (apply audio/video filters) to a temp file to ensure consistent streams
            norm_path = os.path.join(tmp_root, f"norm_{idx}.mp4")
            _normalize_video(cur, norm_path, video_filters=video_filters, audio_filters=audio_filters, target_size="1280x720")
            normalized.append(norm_path)

        # Build concat file
        progress_callback("Building concat list...")
        filelist = os.path.join(tmp_root, "files.txt")
        with open(filelist, "w", encoding="utf-8", newline="\n") as fh:
            for p in normalized:
                fh.write("file '{}'\n".format(_ffmpeg_safe_path(p)))

        # Final concat + optional global overlay tint
        progress_callback("Concatenating clips and encoding final output...")
        tmp_out = os.path.join(tmp_root, "concat_out.mp4")
        concat_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", filelist,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            tmp_out
        ]
        _run(concat_cmd)

        final_out = out_path
        if overlay:
            progress_callback("Applying overlay tint...")
            # tint using color overlay blended with center placement
            # We assume 1280x720 sizing; for production you'd detect resolution
            cmd_overlay = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", tmp_out,
                "-f", "lavfi", "-i", "color=blue@0.18:size=1280x720",
                "-filter_complex", "[0:v]scale=1280:720:force_original_aspect_ratio=decrease[p];[p][1:v]overlay=(W-w)/2:(H-h)/2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "copy",
                final_out
            ]
            _run(cmd_overlay)
        else:
            shutil.move(tmp_out, final_out)

        progress_callback("Render finished.")
    finally:
        # cleanup tmp files
        try:
            shutil.rmtree(tmp_root)
        except Exception:
            pass