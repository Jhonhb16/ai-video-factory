"""B-roll real + musica desde Pixabay (gratis, sin tarjeta)."""
import os
import logging
import requests
from pathlib import Path

log = logging.getLogger("VideoFactory.Stock")
MEDIA_DIR = Path("output/media")


def _key():
    return (os.getenv("PIXABAY_API_KEY") or "").strip()


def buscar_clip(keyword, dest):
    r = requests.get("https://pixabay.com/api/videos/", params={
        "key": _key(), "q": keyword, "per_page": 5,
        "orientation": "horizontal", "safesearch": "true"}, timeout=30)
    r.raise_for_status()
    for h in r.json().get("hits", []):
        for q in ("hd", "sd", "tiny"):
            f = (h.get("videos") or {}).get(q)
            if f and f.get("size", 0) < 25_000_000:
                d = requests.get(f["url"], timeout=180)
                if d.status_code == 200 and len(d.content) > 10000:
                    dest.write_bytes(d.content)
                    return True
    return False


def descargar_musica(dest):
    r = requests.get("https://pixabay.com/api/audio/", params={
        "key": _key(), "q": "upbeat corporate", "per_page": 3}, timeout=30)
    r.raise_for_status()
    for h in r.json().get("hits", []):
        url = h.get("audio")
        if url:
            d = requests.get(url, timeout=180)
            if d.status_code == 200 and len(d.content) > 50000:
                dest.write_bytes(d.content)
                return True
    return False


def download_media(guion):
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if not _key():
        log.warning("Sin PIXABAY_API_KEY: se usara el sistema anterior de imagenes.")
        return False

    keywords = []
    for e in guion.get("escenas", []):
        k = (e.get("keyword") or "").strip()
        if k and k not in keywords:
            keywords.append(k)
    keywords = (keywords or ["money cash", "city people walking", "counting money"])[:8]

    ok_clips = 0
    for i, kw in enumerate(keywords):
        dest = MEDIA_DIR / f"clip_{i:02d}.mp4"
        if dest.exists():
            ok_clips += 1
            continue
        try:
            if buscar_clip(kw, dest):
                log.info(f"Clip {i} listo: {kw}")
                ok_clips += 1
            else:
                log.warning(f"Sin resultados de clip para: {kw}")
        except Exception as e:
            log.warning(f"Clip {i} fallo: {e}")

    mus = MEDIA_DIR / "musica.mp3"
    if not mus.exists() and not list(Path("assets/music").glob("*.mp3")):
        try:
            if descargar_musica(mus):
                log.info("Musica de fondo descargada de Pixabay.")
        except Exception as e:
            log.warning(f"Musica fallo: {e}")

    descargar_sfx()
    log.info(f"{ok_clips} clips de b-roll listos")
    return ok_clips > 0


def descargar_sfx():
    for name, q in (("sfx_pop.mp3", "pop sound effect"), ("sfx_whoosh.mp3", "whoosh transition")):
        dest = MEDIA_DIR / name
        if dest.exists():
            continue
        try:
            r = requests.get("https://pixabay.com/api/audio/", params={
                "key": _key(), "q": q, "per_page": 2}, timeout=30)
            for h in r.json().get("hits", []):
                url = h.get("audio")
                if url:
                    d = requests.get(url, timeout=120)
                    if d.status_code == 200 and len(d.content) > 5000:
                        dest.write_bytes(d.content)
                        log.info(f"SFX listo: {name}")
                        break
        except Exception as e:
            log.warning(f"SFX {name} fallo: {e}")
