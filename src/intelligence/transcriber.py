"""Transcripcion con faster-whisper + cache en R2. Autocontenido."""
import logging
from functools import lru_cache

log = logging.getLogger("VideoFactory.Intelligence")


@lru_cache(maxsize=1)
def _load_model(model_name, device):
    from faster_whisper import WhisperModel
    compute = "int8" if device == "cpu" else "float16"
    log.info(f"Cargando faster-whisper '{model_name}' en {device}...")
    return WhisperModel(model_name, device=device, compute_type=compute)


def _transcribir_archivo(audio_path, video, model_name, device):
    try:
        model = _load_model(model_name, device)
        segments, info = model.transcribe(str(audio_path), language="es", beam_size=5)
        texto = " ".join(s.text.strip() for s in segments)
        return {
            "video_id": video.get("id") or video.get("shortcode"),
            "texto": texto,
            "duracion_segundos": round(info.duration, 1),
            "palabras": len(texto.split()),
        }
    except Exception as e:
        log.error(f"Error transcribiendo: {e}")
        return None


def transcribir_top(videos, top_n=15, model_name="base", device="cpu"):
    from src import state_store

    def score(v):
        return (v.get("likesCount") or 0) + (v.get("commentsCount") or 0) * 3 \
               + (v.get("viewsCount") or 0) * 0.1

    videos.sort(key=score, reverse=True)
    for i, v in enumerate(videos):
        if i >= top_n:
            v["transcripcion"] = None
            continue
        vid = v.get("id") or v.get("shortcode")
        cached = state_store.pull_transcript(vid) if vid else None
        if cached:
            v["transcripcion"] = cached
            continue
        from src.intelligence.downloader import descargar_audio
        audio = descargar_audio(v)
        if not audio:
            v["transcripcion"] = None
            continue
        t = _transcribir_archivo(audio, v, model_name, device)
        v["transcripcion"] = t
        if t and vid:
            state_store.push_transcript(vid, t)

    transcritos = sum(1 for v in videos if v.get("transcripcion"))
    log.info(f"Transcritos {transcritos}/{top_n} videos top")
    return videos
