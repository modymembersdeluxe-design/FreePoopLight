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

# Try to import yt_dlp optionally inside functions when used.

_filename_sanitize_re = re.compile(r'[^A-Za-z0-9._\-\s]+')

def safe_filename(name: str) -> str:
    name = name.strip().replace('/', '_').replace('\\', '_')
    name = _filename_sanitize_re.sub('', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return 'file'
    return name

def _filename_from_content_disposition(cd: Optional[str]) -> Optional[str]:
    if not cd:
        return None
    m = re.search(r'filename\\*?=(?:UTF-8\\'\\')?[\"\\']?([^\"\\';]+)', cd)
    if m:
        return m.group(1)
    return None

def download_url(url: str, dest_dir: Optional[str] = None, prefer_yt_dlp: bool = True) -> str:
    """
    Download a URL to a local file and return the path to the downloaded file.

    Prefers yt-dlp if available and prefer_yt_dlp=True. Falls back to requests streaming download for direct links.
    """
    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix='freepoop_dl_')
    os.makedirs(dest_dir, exist_ok=True)

    yt_err = None
    if prefer_yt_dlp:
        try:
            import yt_dlp  # type: ignore
            ydl_opts = {
                'outtmpl': os.path.join(dest_dir, '%(title)s.%(ext)s'),
                'nocheckcertificate': True,
                'quiet': True,
                'no_warnings': True,
                # don't postprocess by default
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
                files = sorted(
                    (os.path.join(dest_dir, p) for p in os.listdir(dest_dir)),
                    key=lambda p: os.path.getmtime(p),
                    reverse=True
                )
                if files:
                    return files[0]
                raise Exception("yt-dlp did not produce any output file")
        except Exception as e:
            yt_err = e

    # Fallback to requests
    if requests is None:
        raise RuntimeError(f"requests not installed and yt-dlp failed: {yt_err!r}")
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        cd = resp.headers.get('content-disposition')
        filename = _filename_from_content_disposition(cd)
        if not filename:
            path_part = os.path.basename(resp.url.split('?', 1)[0])
            filename = path_part or 'download'
        filename = safe_filename(filename)
        if '.' not in filename:
            ctype = resp.headers.get('content-type', '')
            if '/' in ctype:
                ext = ctype.split('/')[-1].split(';')[0]
                if ext and len(ext) <= 5:
                    filename = f"{filename}.{ext}"
        out_path = os.path.join(dest_dir, filename)
        with open(out_path, 'wb') as fh:
            for chunk in resp.iter_content(chunk_size=64*1024):
                if chunk:
                    fh.write(chunk)
        if os.path.exists(out_path):
            return out_path
        raise Exception("Streamed download completed but file missing")
    except Exception as e:
        if yt_err:
            raise Exception(f"yt-dlp error: {yt_err!r}; requests fallback error: {e!r}")
        raise

def download_url_placeholder(url: str, dest_dir: Optional[str] = None) -> str:
    return download_url(url, dest_dir=dest_dir, prefer_yt_dlp=True)