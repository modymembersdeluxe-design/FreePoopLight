import os
import subprocess
import tempfile
import shutil
import random
from typing import Dict, Callable, List, Optional

from utils import download_url, safe_filename

def _run(cmd: List[str], cwd: Optional[str] = None):
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{e}") from e

def _ffmpeg_path_safe(p: str) -> str:
    """Return absolute path (no quoting) for ffmpeg input ordering. We won't rely on concat demuxer parsing."""
    return os.path.abspath(p)

def _probe_has_stream(path: str, stream: str) -> bool:
    """
    Use ffprobe to check whether a media file has a given stream type ('v' or 'a').
    Returns True if at least one stream of that type exists.
    """
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", stream,
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            path
        ], stderr=subprocess.DEVNULL)
        return bool(out.strip())
    except Exception:
        return False

def _normalize_clip_for_concat(src: str, dest: str, target_size: str = "1280x720", video_filters: Optional[str] = None, audio_filters: Optional[str] = None):
    """
    Normalize input to a MP4 with both video and audio tracks, consistent codec, and optional filters.
    Handles:
      - video+audio (normal case)
      - video only -> add silent audio
      - audio only -> render simple color video + audio
    This avoids ffmpeg concat "reader failed" errors by ensuring consistent streams.
    """
    has_v = _probe_has_stream(src, "v")
    has_a = _probe_has_stream(src, "a")

    # Build ffmpeg command depending on stream presence
    if has_v and has_a:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
        vf = video_filters or f"scale={target_size}:force_original_aspect_ratio=decrease"
        if vf:
            cmd += ["-vf", vf]
        if audio_filters:
            cmd += ["-af", audio_filters]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            dest
        ]
        _run(cmd)
        return

    if has_v and not has_a:
        # add silent audio stream
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]
        vf = video_filters or f"scale={target_size}:force_original_aspect_ratio=decrease"
        if vf:
            cmd += ["-vf", vf]
        if audio_filters:
            # apply any audio filters to the generated silent audio (probably no-op) -> append -af after mapping
            cmd += ["-map", "0:v", "-map", "1:a", "-af", audio_filters]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            dest
        ]
        _run(cmd)
        return

    if not has_v and has_a:
        # create a simple color video to pair with audio
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=size={target_size}:color=black",
            "-i", src,
            "-shortest"
        ]
        if audio_filters:
            cmd += ["-af", audio_filters]
        # apply optional video filters after color input if provided
        if video_filters:
            cmd += ["-vf", video_filters]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            dest
        ]
        _run(cmd)
        return

    # fallback: treat as generic input (shouldn't reach here)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-c:a", "aac", "-b:a", "192k", dest]
    _run(cmd)

def _reverse_clip(src: str, dest: str):
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

def _semitone_ratio(semitones: int) -> float:
    return 2 ** (semitones / 12.0)

def _build_audio_pitch_filters(semitones: int, preserve_speed: bool):
    if semitones == 0:
        return None
    ratio = _semitone_ratio(semitones)
    filters = [f"asetrate=sample_rate*{ratio:.6f}", "aresample=44100"]
    if preserve_speed:
        atempo = 1.0 / ratio
        # chain atempo factors into acceptable 0.5-2.0 ranges
        if atempo < 0.5 or atempo > 2.0:
            factors = []
            v = atempo
            while v < 0.5:
                factors.append(0.5)
                v /= 0.5
            while v > 2.0:
                factors.append(2.0)
                v /= 2.0
            factors.append(round(v, 6))
            for f in factors:
                filters.append(f"atempo={f}")
        else:
            filters.append(f"atempo={atempo:.6f}")
    return ",".join(filters)

def _build_tremolo_filter(depth: float = 0.5, freq: float = 8.0):
    return f"tremolo=f={freq}:d={depth}"

def render_project(config: Dict, out_path: str, progress_callback: Callable[[str], None] = None):
    """
    Robust renderer that avoids concat demuxer parsing problems by using ffmpeg filter_complex concat.
    Normalizes every clip to ensure consistent streams. Handles audio-only and video-only sources.
    """
    if progress_callback is None:
        progress_callback = lambda s: None

    tmp_root = tempfile.mkdtemp(prefix="freepoop_render_")
    try:
        progress_callback("Gathering sources...")
        sources: List[str] = []
        for v in config.get("videos", []):
            sources.append(v)
        for g in config.get("gifs", []):
            sources.append(g)
        for u in config.get("urls", []):
            if os.path.exists(u):
                sources.append(u)
            else:
                progress_callback(f"Downloading: {u}")
                try:
                    fpath = download_url(u, dest_dir=tmp_root)
                    sources.append(fpath)
                except Exception as e:
                    progress_callback(f"Download failed: {e}")

        if not sources:
            raise RuntimeError("No source clips available for render.")

        if config.get("scramble"):
            progress_callback("Shuffling sources...")
            random.shuffle(sources)

        clip_count = int(config.get("clip_count", 6) or 6)
        if len(sources) > clip_count:
            sources = sources[:clip_count]

        if config.get("stutter"):
            progress_callback("Applying stutter...")
            dup = []
            for s in sources:
                dup.append(s)
                dup.append(s)
            sources = dup

        progress_callback("Normalizing clips (this may take a while)...")
        normalized = []
        semitones = int(config.get("pitch_semitones", 0) or 0)
        preserve_speed = bool(config.get("pitch_preserve", True))
        earrape = bool(config.get("earrape", False))
        overlay = bool(config.get("overlay", False))

        for idx, src in enumerate(sources):
            progress_callback(f"Processing clip {idx+1}/{len(sources)}: {os.path.basename(src)}")
            cur = src
            # Optionally reverse clip-level if requested globally
            if config.get("reverse"):
                rev_tmp = os.path.join(tmp_root, f"rev_{idx}.mp4")
                _reverse_clip(cur, rev_tmp)
                cur = rev_tmp

            # Build per-clip audio filters
            audio_filters_parts = []
            pitch_filter = _build_audio_pitch_filters(semitones, preserve_speed)
            if pitch_filter:
                audio_filters_parts.append(pitch_filter)
            # occasional tremolo for variety
            if random.random() < 0.12:
                audio_filters_parts.append(_build_tremolo_filter(depth=0.6, freq=8.0))
            if earrape:
                audio_filters_parts.append("volume=6")
            audio_filters = ",".join(audio_filters_parts) if audio_filters_parts else None

            # For this pass we don't apply many per-clip video fancy filters; keep it stable for concat.
            # You can enhance video_filters here (pixelate/etc) carefully ensuring output streams remain compatible.
            video_filters = None

            norm_path = os.path.join(tmp_root, f"norm_{idx}.mp4")
            _normalize_clip_for_concat(cur, norm_path, target_size="1280x720", video_filters=video_filters, audio_filters=audio_filters)
            normalized.append(norm_path)

        progress_callback("Building ffmpeg inputs for filter_complex concat...")
        # Build ffmpeg command with one -i per normalized file
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for p in normalized:
            cmd += ["-i", p]

        # Build filter_complex: for each input we expect a video and audio stream: [0:v][0:a][1:v][1:a]...concat=n=X:v=1:a=1[outv][outa]
        parts = []
        for i in range(len(normalized)):
            parts.append(f"[{i}:v]")
            parts.append(f"[{i}:a]")
        concat_count = len(normalized)
        filter_complex = "".join(parts) + f"concat=n={concat_count}:v=1:a=1[outv][outa]"

        cmd += ["-filter_complex", filter_complex, "-map", "[outv]", "-map", "[outa]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k", os.path.join(tmp_root, "concat_out.mp4")]

        progress_callback("Running ffmpeg concat (filter_complex)...")
        _run(cmd)

        tmp_out = os.path.join(tmp_root, "concat_out.mp4")
        if overlay:
            progress_callback("Applying overlay tint...")
            final_cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", tmp_out,
                "-f", "lavfi", "-i", "color=blue@0.18:size=1280x720",
                "-filter_complex", "[0:v]scale=1280:720:force_original_aspect_ratio=decrease[p];[p][1:v]overlay=(W-w)/2:(H-h)/2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "copy",
                out_path
            ]
            _run(final_cmd)
        else:
            shutil.move(tmp_out, out_path)

        progress_callback("Render finished.")
    finally:
        try:
            shutil.rmtree(tmp_root)
        except Exception:
            pass