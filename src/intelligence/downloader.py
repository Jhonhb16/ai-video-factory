"""Descarga de audio con yt-dlp + fallback directo."""
import logging
import subprocess
from pathlib import Path
import requests

log = logging.getLogger("VideoFactory.Intelligence")
AUDIO_CACHE = Path("output/intelligence/audio_cache")
AUDIO_CACHE.mkdir(parents=True, exist_ok=True)


def descargar_audio(video):
    vid = video.get("id") or video.get("shortcode")
    if not vid:
        return None
    out = AUDIO_CACHE / f"{vid}.mp3"
    if out.exists() and out.stat().st_size > 1000:
        return out

    url = video.get("url") or video.get("videoUrl")
    if not url:
        return None
    if not url.startswith("http"):
        url = f"https://www.instagram.com/reel/{vid}/"

    try:
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "--no-playlist", "-o", str(out), url],
            capture_output=True, check=True, timeout=120)
        if out.exists() and out.stat().st_size > 1000:
            return out
    except Exception as e:
        log.debug(f"yt-dlp fallo para {vid}: {e}")

    video_url = video.get("videoUrl")
    if video_url:
        try:
            tmp = AUDIO_CACHE / f"{vid}.mp4"
            with requests.get(video_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(tmp), "-vn", "-acodec", "libmp3lame",
                 "-q:a", "4", str(out)],
                capture_output=True, check=True, timeout=120)
            tmp.unlink(missing_ok=True)
            if out.exists():
                return out
        except Exception as e:
            log.debug(f"Descarga directa fallo para {vid}: {e}")
    return None
