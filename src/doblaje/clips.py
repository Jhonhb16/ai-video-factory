"""Saca clips verticales de un video largo de cliente.

El trabajo dificil no es cortar: es ELEGIR. Un video de una hora tiene tres o
cuatro momentos que funcionan solos, y el resto es contexto que sin el video
entero no se entiende. Cortar cada cinco minutos da clips que empiezan a
media frase y no los ve nadie.

Por eso aqui se transcribe con tiempos reales, se le pide al LLM que busque
momentos que se sostengan SOLOS, y se lleva cada corte al borde de frase mas
cercano para no partir palabras por la mitad.
"""
import json
import logging
from pathlib import Path

from src.llm import chat_json
from src.utils import run_cmd

log = logging.getLogger("VideoFactory.Clips")

SALIDA = Path("output/clips")
MIN_SEG, MAX_SEG = 20, 90

PROMPT = """Eres editor de clips virales. Te doy la transcripcion CON TIEMPOS
de un video largo y eliges los momentos que funcionan SOLOS en vertical.

Un buen clip:
- Se entiende sin haber visto el resto. Si necesita contexto previo, NO sirve.
- Empieza en el golpe: una afirmacion fuerte, una cifra, una pregunta
  incomoda o el arranque de una historia. NUNCA en "y entonces" o "como decia".
- Tiene un remate al final. Si se corta en seco a mitad de idea, no sirve.
- Dura entre 20 y 90 segundos.

PREFIERE: opiniones que se mojan, cifras concretas, historias con giro,
contradecir algo que todo el mundo cree, un error propio contado sin adorno.
DESCARTA: presentaciones, saludos, agradecimientos, transiciones, "en el video
de hoy vamos a", y cualquier tramo que solo tenga sentido dentro del largo.

Ordena por cual te parece MEJOR, no por orden de aparicion.
Devuelve UNICAMENTE JSON:
{"clips": [{"inicio": segundos, "fin": segundos, "titulo": "5-8 palabras",
            "gancho": "la frase exacta con la que arranca",
            "por_que": "por que este funciona solo"}]}"""


def transcribir(video, modelo="base"):
    """[(inicio, fin, texto)] por frase. Detecta el idioma solo."""
    from faster_whisper import WhisperModel
    try:
        import torch
        gpu = torch.cuda.is_available()
    except Exception:
        gpu = False
    wm = WhisperModel(modelo, device="cuda" if gpu else "cpu",
                      compute_type="float16" if gpu else "int8")
    segs, info = wm.transcribe(str(video), vad_filter=True)
    frases = [(s.start, s.end, s.text.strip()) for s in segs]
    log.info(f"Transcrito: {len(frases)} frases, idioma detectado "
             f"'{info.language}' ({info.language_probability:.0%})")
    return frases, info.language


def _cuadrar(ini, fin, frases):
    """Lleva el corte al borde de frase mas cercano.

    El LLM da tiempos aproximados y cortar donde el dice parte palabras por
    la mitad. Los limites de frase de whisper caen en silencios reales, asi
    que se usan esos.
    """
    inicios = [a for a, _, _ in frases]
    finales = [b for _, b, _ in frases]
    if inicios:
        ini = min(inicios, key=lambda x: abs(x - ini))
    if finales:
        fin = min(finales, key=lambda x: abs(x - fin))
    return max(0.0, ini - 0.15), fin + 0.25


def elegir(frases, n=5):
    """Los n mejores momentos, segun el LLM."""
    guion = "\n".join(f"[{a:.0f}-{b:.0f}] {t}" for a, b, t in frases)
    r = chat_json(PROMPT,
                  f"Elige los {n} mejores clips.\n\nTRANSCRIPCION:\n{guion}",
                  temperature=0.4, max_tokens=3000)
    clips = r.get("clips") if isinstance(r, dict) else r
    if not isinstance(clips, list):
        return []

    limpios = []
    for c in clips:
        if not isinstance(c, dict):
            continue
        try:
            ini, fin = float(c["inicio"]), float(c["fin"])
        except (KeyError, TypeError, ValueError):
            continue
        ini, fin = _cuadrar(ini, fin, frases)
        if not (MIN_SEG <= fin - ini <= MAX_SEG):
            log.info(f"Descartado '{c.get('titulo', '')}': dura {fin - ini:.0f}s")
            continue
        c["inicio"], c["fin"] = ini, fin
        limpios.append(c)
    return limpios[:n]


def cortar(video, clip, indice, vertical=True):
    """Corta el trozo y lo deja en 9:16."""
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"clip_{indice:02d}.mp4"
    dur = clip["fin"] - clip["inicio"]

    vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,setsar=1") if vertical else "scale=-2:1080"

    run_cmd(["ffmpeg", "-y", "-ss", f"{clip['inicio']:.2f}", "-i", str(video),
             "-t", f"{dur:.2f}", "-vf", vf,
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
             str(destino)])
    return destino


def procesar(video, n=5, vertical=True):
    """De video largo a n clips verticales. Devuelve la lista de clips."""
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(video)

    frases, idioma = transcribir(video)
    if not frases:
        log.warning("No se detecto voz en el video.")
        return []

    clips = elegir(frases, n)
    if not clips:
        log.warning("El LLM no encontro momentos que funcionen solos.")
        return []

    hechos = []
    for i, c in enumerate(clips, 1):
        ruta = cortar(video, c, i, vertical)
        c["archivo"] = str(ruta)
        c["duracion"] = round(c["fin"] - c["inicio"], 1)
        hechos.append(c)
        log.info(f"  clip {i}: {c['duracion']:.0f}s  {c.get('titulo', '')}")

    (SALIDA / "clips.json").write_text(
        json.dumps({"origen": str(video), "idioma": idioma, "clips": hechos},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return hechos
