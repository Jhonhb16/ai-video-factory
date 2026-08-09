"""Publicador: Facebook (subida resumible) + Instagram Reel via R2. Idempotente."""
import os
import json
import time
import logging
import requests
from pathlib import Path
from src.utils import load_config, notify, get_duration, today

log = logging.getLogger("VideoFactory.Publisher")

RECEIPTS_FILE = Path("output/publish_receipts.json")


def _graph():
    ver = os.getenv("META_GRAPH_VERSION", "v23.0")
    return f"https://graph.facebook.com/{ver}"


def _load_receipts():
    if RECEIPTS_FILE.exists():
        try:
            return json.loads(RECEIPTS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_receipt(day, platform, url):
    receipts = _load_receipts()
    receipts.setdefault(day, {})[platform] = url
    RECEIPTS_FILE.write_text(json.dumps(receipts, indent=2))


def publish_video(video_path, guion):
    day = today()
    receipts = _load_receipts().get(day, {})
    urls = {}
    dur = get_duration(video_path)
    if not (30 <= dur <= 200):
        log.warning(f"Duracion inusual: {dur:.0f}s")
    caption = _build_caption(guion)
    title = guion.get("titulo", "Video")[:100]

    if receipts.get("facebook"):
        urls["facebook"] = receipts["facebook"]
    else:
        fb = _publish_facebook(video_path, title, caption)
        if fb:
            urls["facebook"] = fb
            _save_receipt(day, "facebook", fb)

    if receipts.get("instagram"):
        urls["instagram"] = receipts["instagram"]
    else:
        ig = _publish_instagram_reel(video_path, caption)
        if ig:
            urls["instagram"] = ig
            _save_receipt(day, "instagram", ig)

    if not urls:
        raise RuntimeError("No se pudo publicar en ninguna plataforma")
    return urls


def _build_caption(guion):
    parts = [guion.get("titulo", ""), "", guion.get("cta", "")]
    tags = " ".join(guion.get("hashtags", []))
    if tags:
        parts.append(tags)
    return "\n".join(p for p in parts if p)[:2000]


def _upload_to_r2(video_path):
    import boto3
    account_id = os.getenv("R2_ACCOUNT_ID")
    bucket = os.getenv("R2_BUCKET")
    base = os.getenv("R2_PUBLIC_BASE")
    if not (account_id and bucket and base):
        raise RuntimeError("Faltan R2_ACCOUNT_ID / R2_BUCKET / R2_PUBLIC_BASE")
    s3 = boto3.client("s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto")
    key = f"reels/reel_{int(time.time())}.mp4"
    s3.upload_file(video_path, bucket, key, ExtraArgs={"ContentType": "video/mp4"})
    url = f"{base.rstrip('/')}/{key}"
    log.info(f"Video subido a R2: {url}")
    return url


def _publish_facebook(video_path, title, caption):
    token = os.getenv("META_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")
    if not (token and page_id):
        log.warning("Faltan credenciales META; salto Facebook.")
        return None
    size = Path(video_path).stat().st_size
    graph = _graph()
    try:
        r = requests.post(f"{graph}/{page_id}/videos",
            data={"upload_phase": "start", "file_size": size, "access_token": token}, timeout=60)
        r.raise_for_status()
        d = r.json()
        session = d.get("upload_session_id")
        video_id = d.get("video_id")
        if not session:
            raise RuntimeError(f"Respuesta start inesperada: {d}")
        start = int(d.get("start_offset", 0))
        end = int(d.get("end_offset", size))
        iters = 0
        with open(video_path, "rb") as f:
            while start < size:
                iters += 1
                if iters > 500:
                    raise RuntimeError("Demasiadas iteraciones de chunk")
                f.seek(start)
                chunk = f.read(max(1, end - start))
                d = _upload_chunk(graph, page_id, token, session, start, chunk)
                ns = int(d.get("start_offset", size))
                if ns <= start:
                    raise RuntimeError("El offset no avanza")
                start = ns
                end = int(d.get("end_offset", size))
        r = requests.post(f"{graph}/{page_id}/videos",
            data={"upload_phase": "finish", "upload_session_id": session,
                  "title": title, "description": caption, "access_token": token}, timeout=120)
        r.raise_for_status()
        r2 = requests.get(f"{graph}/{video_id}",
            params={"fields": "permalink_url", "access_token": token}, timeout=30)
        url = r2.json().get("permalink_url", "")
        log.info(f"Facebook publicado: {url}")
        return url or f"video_id:{video_id}"
    except Exception as e:
        log.error(f"Fallo Facebook: {e}")
        notify(f"Fallo publicacion Facebook: {e}", ok=False)
        return None


def _upload_chunk(graph, page_id, token, session, start, chunk, intentos=3):
    last = None
    for i in range(intentos):
        try:
            r = requests.post(f"{graph}/{page_id}/videos",
                data={"upload_phase": "transfer", "upload_session_id": session,
                      "start_offset": start, "access_token": token},
                files={"video_file": ("chunk.mp4", chunk, "video/mp4")}, timeout=300)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"Chunk fallo tras {intentos} intentos: {last}")


def _publish_instagram_reel(video_path, caption):
    token = os.getenv("META_ACCESS_TOKEN")
    ig_id = os.getenv("META_IG_USER_ID")
    graph = _graph()
    if not (token and ig_id):
        log.warning("Falta META_IG_USER_ID; salto Instagram.")
        return None
    try:
        video_url = _upload_to_r2(video_path)
        head = requests.head(video_url, timeout=15)
        if head.status_code != 200:
            raise RuntimeError(f"URL R2 devuelve HTTP {head.status_code}")
        r = requests.post(f"{graph}/{ig_id}/media",
            data={"media_type": "REELS", "video_url": video_url, "caption": caption,
                  "share_to_feed": "true", "access_token": token}, timeout=120)
        r.raise_for_status()
        creation_id = r.json()["id"]
        status = None
        for _ in range(30):
            time.sleep(10)
            r2 = requests.get(f"{graph}/{creation_id}",
                params={"fields": "status_code", "access_token": token}, timeout=30)
            status = r2.json().get("status_code")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError("Instagram rechazo el video")
        if status != "FINISHED":
            raise RuntimeError(f"Instagram no termino de procesar (status={status})")
        r3 = requests.post(f"{graph}/{ig_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token}, timeout=60)
        r3.raise_for_status()
        media_id = r3.json()["id"]
        r4 = requests.get(f"{graph}/{media_id}",
            params={"fields": "permalink", "access_token": token}, timeout=30)
        url = r4.json().get("permalink", "")
        log.info(f"Instagram Reel publicado: {url}")
        return url or f"media_id:{media_id}"
    except Exception as e:
        log.error(f"Fallo Instagram: {e}")
        notify(f"Fallo publicacion Instagram: {e}", ok=False)
        return None
