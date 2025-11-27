import os
import re
import tempfile
import shutil
from typing import Optional

# Optional dependencies
try:
    import requests
except Exception:
    requests = None

_filename_sanitize_re = re.compile(r'[^A-Za-z0-9._\-\s]+')

def safe_filename(name: str) -> str:
    """Return a filesystem-safe filename based on name."""
    name = name.strip().replace('/', '_').replace('\\', '_')
    name = _filename_sanitize_re.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return 'file'
    return name


def _filename_from_content_disposition(cd: Optional[str]) -> Optional[str]:
    """
    Parse a Content-Disposition header and return a filename if present.

    This accepts both `filename=` and `filename*=UTF-8''...` forms and handles
    single or double quotes around the filename.
    """
    if not cd:
        return None
    # Match filename= or filename*= with optional UTF-8'' prefix, and capture up to ; or end
    m = re.search(r"filename\*?=(?:UTF-8'')?['\"]?([^'\";]+)", cd, flags=re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def download_url(url: str, dest_dir: Optional[str] = None, prefer_yt_dlp: bool = True) -> str:
    """
    Download a URL to a local file and return the local file path.

    Behavior:
    - If prefer_yt_dlp is True and yt_dlp (or yt-dlp) is installed, attempt to use it
      (best for YouTube/InternetArchive/etc).
    - Otherwise, attempt a streaming download via requests (suitable for direct file URLs).
    - dest_dir: directory to place downloaded file. If None, a temporary directory is created.
    - The caller is responsible for removing temporary files if desired.

    Raises:
      Exception on failure with descriptive message.
    """
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix='freepoop_dl_')
    os.makedirs(dest_dir, exist_ok=True)

    yt_err = None
    if prefer_yt_dlp:
        try:
            # try the commonly installed package name
            import yt_dlp  # type: ignore
            ydl_opts = {
                'outtmpl': os.path.join(dest_dir, '%(title)s.%(ext)s'),
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                # don't postprocess by default; leave raw file for ffmpeg processing
                'postprocessors': [],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                try:
                    path = ydl.prepare_filename(info)
                except Exception:
                    title = info.get('title') or info.get('id') or 'download'
                    ext = info.get('ext') or 'mkv'
                    fname = safe_filename(f"{title}.{ext}")
                    path = os.path.join(dest_dir, fname)
                if os.path.exists(path):
                    return path
                # if the expected path doesn't exist, return the most recent file
                files = sorted(
                    (os.path.join(dest_dir, p) for p in os.listdir(dest_dir)),
                    key=lambda p: os.path.getmtime(p),
                    reverse=True
                )
                if files:
                    return files[0]
                raise Exception("yt-dlp did not produce any output file")
        except Exception as e:
            # remember the error and fall back to requests
            yt_err = e

    # Fallback: basic streamed download using requests
    if requests is None:
        raise RuntimeError(f"requests not installed and yt-dlp failed: {yt_err!r}")

    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        # try to determine filename
        filename = None
        cd = resp.headers.get('content-disposition')
        filename = _filename_from_content_disposition(cd)
        if not filename:
            # try path part
            path_part = os.path.basename(resp.url.split('?', 1)[0])
            filename = path_part or 'download'
        filename = safe_filename(filename)
        # ensure we have an extension; if none, try content-type
        if '.' not in filename:
            ctype = resp.headers.get('content-type', '')
            if '/' in ctype:
                ext = ctype.split('/')[-1].split(';')[0]
                if ext and len(ext) <= 8:
                    filename = f"{filename}.{ext}"
        out_path = os.path.join(dest_dir, filename)
        # stream to file
        with open(out_path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    fh.write(chunk)
        if os.path.exists(out_path):
            return out_path
        raise Exception("Streamed download finished but file not found")
    except Exception as e:
        # if we had an earlier yt-dlp error, include both messages to help debugging
        if yt_err:
            raise Exception(f"yt-dlp error: {yt_err!r}; requests fallback error: {e!r}")
        raise


# Backwards-compatible placeholder kept for projects relying on the old function name
def download_url_placeholder(url: str, dest_dir: Optional[str] = None) -> str:
    """
    Legacy compatibility wrapper. Calls download_url with prefer_yt_dlp=True.
    """
    return download_url(url, dest_dir=dest_dir, prefer_yt_dlp=True)