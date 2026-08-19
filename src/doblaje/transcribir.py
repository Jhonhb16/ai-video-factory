"""Transcripcion del video original con tiempos reales.

De esto depende TODO lo demas: la seleccion de tramos, la traduccion y la
sincronia. Un error aqui se arrastra hasta el video final.

Por eso el modelo por defecto es 'small' y no 'base': con base el ruso pierde
bastante, y el ahorro de tiempo no compensa que el guion salga mal.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger("VideoFactory.Doblaje.Transcribir")

MAX_BLOQUE = 14.0     # un bloque no deberia pasar de esto
HUECO = 0.45          # a partir de aqui se considera pausa del presentador


def transcribir(video, modelo="small", destino=None):
    """[(ini, fin, texto)] por frase, mas el idioma detectado."""
    from faster_whisper import WhisperModel
    try:
        import torch
        gpu = torch.cuda.is_available()
    except Exception:
        gpu = False

    wm = WhisperModel(modelo, device="cuda" if gpu else "cpu",
                      compute_type="float16" if gpu else "int8")
    segs, info = wm.transcribe(str(video), vad_filter=True)
    frases = [{"ini": round(s.start, 2), "fin": round(s.end, 2),
               "txt": s.text.strip()} for s in segs]

    log.info(f"{len(frases)} frases, idioma '{info.language}' "
             f"({info.language_probability:.0%})")
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(json.dumps(
            {"idioma": info.language, "prob": info.language_probability,
             "frases": frases}, ensure_ascii=False, indent=2), encoding="utf-8")
    return frases, info.language


def agrupar(frases, max_bloque=MAX_BLOQUE, hueco=HUECO):
    """Junta frases en bloques que se doblan de una pieza.

    Trocear en frases de 1-5s da un doblaje picado: la voz arranca y para sin
    parar. Agrupando por idea completa suena a persona hablando, y ademas
    caben mas palabras porque se aprovechan las pausas internas.

    Los cortes caen donde hay SILENCIO real, que es donde el presentador
    respira: asi el doblaje respira en el mismo sitio que el original.
    """
    bloques, actual = [], []
    for f in frases:
        if actual:
            dur = f["fin"] - actual[0]["ini"]
            pausa = f["ini"] - actual[-1]["fin"]
            if dur > max_bloque or pausa >= hueco:
                bloques.append(actual)
                actual = []
        actual.append(f)
    if actual:
        bloques.append(actual)

    salida = [{"ini": b[0]["ini"], "fin": b[-1]["fin"],
               "ru": " ".join(x["txt"] for x in b)} for b in bloques]
    dur = [g["fin"] - g["ini"] for g in salida]
    log.info(f"{len(frases)} frases -> {len(salida)} bloques "
             f"(media {sum(dur)/len(dur):.1f}s)" if salida else "sin bloques")
    return salida
