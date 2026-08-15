"""Voz: ElevenLabs -> Gemini TTS (gratis, actuado) -> edge-tts (gratis, plano).

Gemini TTS acepta DIRECCION ACTORAL en el propio texto ("dilo con energia
comica"), asi que da entonacion de verdad. edge-tts a +50% suena a robot
leyendo y es justo lo que aplanaba los videos.
"""
import os
import asyncio
import base64
import json
import logging
import struct
import subprocess
import tempfile

import requests

from src.utils import load_config, load_script, script_path, audio_path, get_duration

log = logging.getLogger("VideoFactory.Voice")

GEMINI_TTS_MODELO = "gemini-2.5-flash-preview-tts"
DIRECCION = ("Narra esto como un comediante latino contando algo a un amigo: "
             "energia alta, ritmo agil, cambia el tono en los remates y haz "
             "pausas cortas antes de los golpes. Nunca suenes a locutor.\n\n")


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

    voz_gemini = cfg.get("gemini_voz", "Puck")
    velocidad = float(cfg.get("velocidad_voz", 1.2))

    if os.getenv("ELEVENLABS_API_KEY"):
        try:
            _elevenlabs(texto, out, voice_id)
            log.info("Voz generada con ElevenLabs")
        except Exception as e:
            log.warning(f"ElevenLabs fallo ({e}). Probando Gemini TTS.")
            _voz_gratis(texto, out, voz_gemini, velocidad, edge_voice)
    else:
        _voz_gratis(texto, out, voz_gemini, velocidad, edge_voice)

    dur = get_duration(out)
    log.info(f"Duracion del audio: {dur:.1f}s")
    if dur < 45:
        raise RuntimeError(f"Audio demasiado corto ({dur:.0f}s).")
    if dur > 100:
        log.warning(f"Audio largo ({dur:.0f}s); el objetivo son ~70s.")
    return dur


def _voz_gratis(texto, out, voz_gemini, velocidad, edge_voice):
    """Gemini TTS si hay clave; si falla, edge-tts. Nunca deja al pipeline sin voz."""
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        try:
            _gemini_tts(texto, out, voz_gemini, velocidad)
            log.info(f"Voz generada con Gemini TTS (voz {voz_gemini}, x{velocidad})")
            return
        except Exception as e:
            log.warning(f"Gemini TTS fallo ({str(e)[:140]}). Usando edge-tts.")
    else:
        log.info("Sin GEMINI_API_KEY: usando edge-tts.")
    _edge_tts(texto, out, edge_voice)


def _build_text(script):
    partes = [script.get("hook", ""), script.get("guion", ""), script.get("cta", "")]
    return "\n".join(p.strip() for p in partes if p.strip())


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


def _gemini_tts(texto, out, voz, velocidad):
    """Gemini devuelve PCM crudo: hay que ponerle cabecera WAV y pasarlo a mp3."""
    key = os.getenv("GEMINI_API_KEY").strip()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_TTS_MODELO}:generateContent?key={key}")
    payload = {
        "contents": [{"parts": [{"text": DIRECCION + texto}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}},
        },
    }
    r = requests.post(url, json=payload, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

    datos = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(datos["data"])
    if len(pcm) < 10000:
        raise RuntimeError("audio vacio")

    tasa = 24000
    for trozo in (datos.get("mimeType") or "").split(";"):
        if trozo.strip().startswith("rate="):
            tasa = int(trozo.split("=")[1])

    cabecera = (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
                + struct.pack("<IHHIIHH", 16, 1, 1, tasa, tasa * 2, 2, 16)
                + b"data" + struct.pack("<I", len(pcm)))

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(cabecera + pcm)
        wav = tmp.name
    try:
        # atempo respeta el tono: acelera sin volver la voz de ardilla
        filtro = f"atempo={max(0.5, min(2.0, velocidad)):.2f}"
        subprocess.run(["ffmpeg", "-y", "-i", wav, "-filter:a", filtro,
                        "-codec:a", "libmp3lame", "-b:a", "128k", str(out)],
                       capture_output=True, check=True)
    finally:
        os.unlink(wav)

    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("conversion a mp3 vacia")


def _edge_tts(texto, out, voice):
    import edge_tts

    async def _run():
        comm = edge_tts.Communicate(texto, voice, rate="+50%")
        await comm.save(str(out))

    asyncio.run(_run())
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError("edge-tts no genero audio")
