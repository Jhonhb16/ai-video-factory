"""Voz del doblaje: se genera, se MIDE y se corrige lo que no cabe.

La leccion mas cara de este modulo: el ritmo de habla NO es constante. Medido
sobre audio real, un bloque corto sale a 1.4-1.9 palabras por segundo y uno de
13 segundos a 2.4-2.5. Cualquier constante unica falla en los dos sentidos.

Asi que aqui no se predice: se genera, se mide contra el hueco y se actua.
  - hasta un 6% de exceso -> se corrige el tempo, que a ese nivel no se oye
  - por encima            -> se manda recortar el texto y se vuelve a generar

Y la voz va acelerada a 1.2x: a velocidad natural sonaba lenta y sin caracter.
Pero acelerar SOLO no basta, porque los bloques se acortan y el silencio entre
frases crece. Por eso el texto se adapta con presupuesto para 1.2x (ver
adaptar.py): mas palabras, dichas mas rapido, llenan el hueco.
"""
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

from src.llm import chat_json
from src.utils import get_duration

log = logging.getLogger("VideoFactory.Doblaje.Voz")

VELOCIDAD = 1.2
TOPE_TEMPO = 1.06      # correccion que el oido no detecta
VOZ = "ash"
INSTRUCCION = (
    "Locutor de review de tecnologia, hombre joven con personalidad. Tono "
    "seguro, cercano y con chispa, como quien domina el tema y se lo cuenta a "
    "un amigo. Ritmo agil. Nada de euforia de anuncio. Las cifras con enfasis.")


def _hablar(texto, destino, voz=VOZ, instruccion=INSTRUCCION):
    """Una llamada a la TTS. Devuelve True si escribio el archivo."""
    clave = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not clave:
        log.warning("Sin OPENAI_API_KEY: no se puede generar voz.")
        return False
    for intento in range(4):
        try:
            r = requests.post("https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {clave}"},
                json={"model": "gpt-4o-mini-tts", "voice": voz, "input": texto,
                      "instructions": instruccion, "response_format": "mp3"},
                timeout=180)
        except Exception as e:
            log.warning(f"TTS fallo ({str(e)[:60]})")
            time.sleep(3 * (intento + 1))
            continue
        if r.status_code == 200:
            Path(destino).write_bytes(r.content)
            return True
        time.sleep(3 * (intento + 1))
    return False


def _recortar(texto, exceso):
    """Pide una version mas corta diciendo cuantas palabras deben quedar."""
    objetivo = max(5, int(len(texto.split()) / exceso) - 1)
    try:
        r = chat_json(
            "Acortas doblaje sin perder el dato ni el sentido: fuera adornos, "
            "repeticiones y muletillas. Español latino neutro con "
            'personalidad. Devuelve JSON {"es": "..."}',
            f"Acorta a {objetivo} palabras o menos:\n\n{texto}",
            temperature=0.3, max_tokens=600)
        return (r.get("es") or "").strip() or texto
    except Exception:
        return texto


def generar(bloques, carpeta, velocidad=VELOCIDAD, voz=VOZ):
    """Genera la voz de cada bloque, ajustada a su hueco.

    Escribe `audio` y `dur` en cada bloque. Devuelve cuantos se recortaron.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    recortes = 0

    for i, g in enumerate(bloques):
        wav = carpeta / f"b{i:03d}.wav"
        if wav.exists() and get_duration(wav) > 0.4:
            g["audio"], g["dur"] = str(wav), round(get_duration(wav), 2)
            continue

        hueco = g["fin"] - g["ini"]
        texto = g.get("es") or g.get("ru", "")
        mp3 = carpeta / f"b{i:03d}.mp3"
        if not _hablar(texto, mp3, voz):
            log.warning(f"Bloque {i} sin voz")
            continue

        # lo que importa es la duracion DESPUES de acelerar
        if get_duration(mp3) / velocidad > hueco * 1.04:
            nuevo = _recortar(texto, (get_duration(mp3) / velocidad) / hueco)
            if nuevo != texto and _hablar(nuevo, mp3, voz):
                g["es"] = nuevo
                recortes += 1

        factor = min(velocidad * 1.15, max(velocidad, get_duration(mp3) / hueco))
        subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-filter:a",
                        f"atempo={factor:.4f}", "-ar", "48000", "-ac", "1",
                        str(wav)], capture_output=True)
        mp3.unlink(missing_ok=True)
        g["audio"], g["dur"] = str(wav), round(get_duration(wav), 2)

    con = [g for g in bloques if g.get("dur")]
    if con:
        relleno = sum(g["dur"] for g in con) / (bloques[-1]["fin"] or 1)
        log.info(f"{len(con)}/{len(bloques)} bloques con voz | {recortes} "
                 f"recortados | relleno {relleno:.0%}")
    return recortes


def arreglar_solapes(bloques, carpeta, velocidad=VELOCIDAD, voz=VOZ):
    """Recorta los bloques cuya voz invade al siguiente.

    Un bloque que dura mas que su hueco pisa al siguiente y se oyen dos voces
    a la vez: es el fallo mas evidente de un doblaje y hay que dejarlo en cero.
    """
    arreglados = 0
    for i in range(len(bloques) - 1):
        g, sig = bloques[i], bloques[i + 1]
        if not g.get("dur"):
            continue
        hueco = sig["ini"] - g["ini"]
        for _ in range(3):
            if g["dur"] <= hueco + 0.05:
                break
            nuevo = _recortar(g["es"], g["dur"] / hueco)
            mp3 = Path(carpeta) / f"b{i:03d}.mp3"
            if nuevo == g["es"] or not _hablar(nuevo, mp3, voz):
                break
            factor = min(velocidad * 1.15,
                         max(velocidad, get_duration(mp3) / hueco))
            wav = Path(carpeta) / f"b{i:03d}.wav"
            subprocess.run(["ffmpeg", "-y", "-i", str(mp3), "-filter:a",
                            f"atempo={factor:.4f}", "-ar", "48000", "-ac", "1",
                            str(wav)], capture_output=True)
            mp3.unlink(missing_ok=True)
            g["es"], g["dur"] = nuevo, round(get_duration(wav), 2)
            arreglados += 1

    quedan = sum(1 for i in range(len(bloques) - 1)
                 if bloques[i].get("dur")
                 and bloques[i]["ini"] + bloques[i]["dur"] > bloques[i+1]["ini"] + 0.05)
    log.info(f"solapes arreglados: {arreglados} | quedan: {quedan}")
    return quedan


def pista(bloques, destino, duracion, sr=48000):
    """Monta la pista de voz completa colocando cada bloque en su segundo.

    Se arma en Python y no con N entradas de ffmpeg: con 77 bloques la linea
    de comandos se pasa de largo en Windows, y asi el silencio entre bloques
    es exacto.
    """
    import wave

    import numpy as np

    salida = np.zeros(int(duracion * sr), dtype=np.float32)
    for g in bloques:
        if not g.get("audio") or not Path(g["audio"]).exists():
            continue
        with wave.open(g["audio"], "rb") as w:
            datos = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            if w.getnchannels() == 2:
                datos = datos.reshape(-1, 2).mean(axis=1)
        i0 = int(g["ini"] * sr)
        i1 = min(len(salida), i0 + len(datos))
        salida[i0:i1] += datos[:i1 - i0].astype(np.float32) / 32768.0

    pico = float(np.abs(salida).max()) or 1.0
    salida = (salida / pico * 0.89 * 32767).astype(np.int16)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(salida.tobytes())
    return destino
