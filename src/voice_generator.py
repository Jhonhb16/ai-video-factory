"""Voz: ElevenLabs con respaldo edge-tts gratuito."""
import os
import asyncio
import json
import logging
from src.utils import load_config, load_script, script_path, audio_path, get_duration

log = logging.getLogger("VideoFactory.Voice")


def generate_voice(data=None):
    if isinstance(data, dict) and "guion" in data:
        script_path().parent.mkdir(parents=True, exist_ok=True)
        script_path().write_text(json.dumps(data["guion"], ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    script = load_script()
    texto = _build_text(script)
    out = audio_path()
    out.parent.mkdir(parents=True, exist_ok=True)

    cfg = load_config().get("contenido", {})
    voice_id = cfg.get("elevenlabs_voice_id", "21m00Tcm4TlvDq8ikWAM")
    edge_voice = cfg.get("edge_voice", "es-MX-DaliaNeural")

    if os.getenv("ELEVENLABS_API_KEY"):
        try:
            _elevenlabs(texto, out, voice_id)
            log.info("Voz generada con ElevenLabs")
        except Exception as e:
            log.warning(f"ElevenLabs fallo ({e}). Usando edge-tts.")
            _edge_tts(texto, out, edge_voice)
    else:
        log.info("Sin ELEVENLABS_API_KEY: usando edge-tts gratuito.")
        _edge_tts(texto, out, edge_voice)

    dur = get_duration(out)
    log.info(f"Duracion del audio: {dur:.1f}s")
    if dur < 60:
        raise RuntimeError(f"Audio demasiado corto ({dur:.0f}s).")
    if dur > 140:
        log.warning(f"Audio largo ({dur:.0f}s); el video superara los 2 min.")
    return dur


def _build_text(script):
    partes = [script.get("hook", ""), script.get("guion", ""), script.get("cta", "")]
    return ". ".join(p.strip() for p in partes if p.strip())


def _elevenlabs(texto, out, voice_id):
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
    stream = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id="eleven_multilingual_v2",
        output_format="mp3_22050_32",
        text=texto,
        voice_settings={"stability": 0.5, "similarity_boost": 0.75},
    )
    with open(out, "wb") as f:
        for chunk in stream:
            if chunk:
                f.write(chunk)
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("ElevenLabs devolvio audio vacio")


def _edge_tts(texto, out, voice):
    import edge_tts

    async def _run():
        comm = edge_tts.Communicate(texto, voice)
        await comm.save(str(out))

    asyncio.run(_run())
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("edge-tts no genero audio")
