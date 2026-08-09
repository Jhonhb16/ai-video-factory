"""Persistencia de estado en Cloudflare R2 para ejecuciones sin servidor."""
import os
import json
import logging
import boto3
from pathlib import Path
from botocore.exceptions import ClientError

log = logging.getLogger("VideoFactory.StateStore")

STATE_FILES = [
    "output/published_log.csv",
    "output/publish_receipts.json",
    "output/intelligence/scores_log.csv",
    "output/intelligence/referentes.json",
    "output/intelligence/matrix-viralidad.json",
    "output/intelligence/matrix-viralidad.md",
    "output/intelligence/contexto-viral.md",
    "output/intelligence/metricas_propias.json",
]


def _require_r2():
    for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_STATE_BUCKET"):
        if not os.getenv(var):
            raise RuntimeError(f"Falta la variable {var} para usar R2")


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def _not_found(e):
    return e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound")


def pull_state():
    _require_r2()
    c = _client()
    bucket = os.getenv("R2_STATE_BUCKET")
    prefix = os.getenv("R2_STATE_PREFIX", "state")
    for local in STATE_FILES:
        key = f"{prefix}/{local}"
        try:
            Path(local).parent.mkdir(parents=True, exist_ok=True)
            c.download_file(bucket, key, local)
            log.info(f"Estado descargado: {local}")
        except ClientError as e:
            if _not_found(e):
                log.info(f"  (sin estado previo: {local})")
            else:
                log.warning(f"No pude descargar {key}: {e}")
        except Exception as e:
            log.warning(f"Error descargando {key}: {e}")


def push_state():
    _require_r2()
    c = _client()
    bucket = os.getenv("R2_STATE_BUCKET")
    prefix = os.getenv("R2_STATE_PREFIX", "state")
    for local in STATE_FILES:
        if not Path(local).exists():
            continue
        try:
            c.upload_file(local, bucket, f"{prefix}/{local}")
            log.info(f"Estado subido: {local}")
        except Exception as e:
            log.error(f"Error subiendo {local}: {e}")


def pull_transcript(video_id):
    _require_r2()
    try:
        local = Path(f"output/intelligence/transcripts/{video_id}.json")
        local.parent.mkdir(parents=True, exist_ok=True)
        _client().download_file(
            os.getenv("R2_STATE_BUCKET"),
            f"{os.getenv('R2_STATE_PREFIX','state')}/transcripts/{video_id}.json",
            str(local))
        return json.loads(local.read_text())
    except Exception:
        return None


def push_transcript(video_id, data):
    _require_r2()
    try:
        local = Path(f"output/intelligence/transcripts/{video_id}.json")
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        _client().upload_file(
            str(local), os.getenv("R2_STATE_BUCKET"),
            f"{os.getenv('R2_STATE_PREFIX','state')}/transcripts/{video_id}.json")
    except Exception as e:
        log.warning(f"No subi transcript {video_id}: {e}")
