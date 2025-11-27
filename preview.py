import os
import subprocess
import tempfile
import shutil
import sys

def _has_executable(name: str) -> bool:
    from shutil import which
    return which(name) is not None

def preview_file(path: str, duration: int = 5):
    """
    Play a short preview of a media file. Prefers ffplay; falls back to extracting a short clip and opening it.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    # try ffplay first
    if _has_executable("ffplay"):
        cmd = ["ffplay", "-autoexit", "-nodisp", "-t", str(duration), "-hide_banner", "-loglevel", "warning", path]
        # ffplay prints to stdout/stderr — run and wait
        subprocess.run(cmd)
        return
    # fallback: use ffmpeg to make a short clipped file and open with system default
    if not _has_executable("ffmpeg"):
        raise EnvironmentError("ffplay or ffmpeg not found on PATH; cannot preview.")
    tmpdir = tempfile.mkdtemp(prefix="freepoop_preview_")
    out = os.path.join(tmpdir, "preview.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "0", "-t", str(duration),
        "-i", path,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        out
    ]
    subprocess.run(cmd, check=True)
    # open with platform default
    if sys.platform.startswith("win"):
        os.startfile(out)
    elif sys.platform == "darwin":
        subprocess.run(["open", out])
    else:
        subprocess.run(["xdg-open", out])
    # note: tmpdir not removed automatically so OS can play file; user can clean temp dirs later.