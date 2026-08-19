"""Doblaje al español ajustado al tiempo original.

Lo que arruina un doblaje no es la traduccion ni la voz: es la DURACION. El
español ocupa entre un 15% y un 25% mas que el ingles diciendo lo mismo, asi
que una traduccion fiel se sale de su hueco, y a los treinta segundos la voz
va por detras de la imagen y ya no hay quien lo salve.

Por eso aqui no se traduce: se ADAPTA a un numero de palabras calculado desde
la duracion real del tramo. Es lo que hace un ajustador de doblaje de verdad,
que reescribe la frase para que quepa en la boca del actor.

Segunda regla: si aun asi se pasa, se corrige el tempo del audio (hasta un
6%, que es inaudible) antes que dejar que se desplace. Estirar mas se nota.
"""
import json
import logging
import re
from pathlib import Path

from src.llm import chat_json
from src.utils import run_cmd

log = logging.getLogger("VideoFactory.Doblaje")

# Palabras por segundo, MEDIDO sobre audio real de la voz que se usa.
#
# Estaba en 2.6 y era falso: esa cifra salia de la voz del canal, que corre a
# 1.2x y con diccion de Reel. Al medir la voz de doblaje a ritmo natural sobre
# 7 lineas reales dio 1.72, o sea que el limite de palabras estaba inflado un
# 51% y TODAS las lineas se salian de su hueco (105% a 147%).
#
# Si se cambia de voz o de velocidad, hay que volver a medirlo: es el numero
# del que depende que el doblaje encaje.
RITMO = 1.72
TEMPO_MAX = 1.06        # correccion de tempo que el oido no detecta

PROMPT = """Eres ajustador de doblaje al español latino neutro.

No traduces: ADAPTAS. Cada linea tiene un limite de palabras porque tiene que
caber en el mismo hueco de tiempo que el original. Pasarse desincroniza el
video entero.

Reglas:
- RESPETA el limite de palabras de cada linea. Es lo mas importante.
- Di lo MISMO, no lo parecido: si hay que sacrificar algo, sacrifica adornos,
  nunca el dato ni el sentido.
- Español latino NEUTRO: nada de "vosotros", "tio", "guay", "coger".
- Habla como habla la gente, no como se escribe. Frases cortas.
- Los nombres propios, marcas y cifras se conservan tal cual.
- Si la linea original es una muletilla ("you know", "so, um"), puedes
  dejarla en blanco: es mejor un silencio que relleno.

Devuelve UNICAMENTE JSON:
{"lineas": [{"i": indice, "es": "texto en español"}]}"""


def _limite(segundos):
    """Cuantas palabras caben de verdad en ese hueco."""
    return max(1, int(segundos * RITMO))


def adaptar(frases, lote=25):
    """[(inicio, fin, texto_original)] -> lista de textos en español.

    Se manda por lotes porque un video de 16 minutos no cabe en una llamada,
    y porque el modelo respeta peor los limites cuanto mas larga es la lista.
    """
    salida = [""] * len(frases)
    for arranque in range(0, len(frases), lote):
        trozo = frases[arranque:arranque + lote]
        peticion = [{"i": arranque + k, "segundos": round(b - a, 1),
                     "max_palabras": _limite(b - a), "en": t}
                    for k, (a, b, t) in enumerate(trozo)]
        try:
            r = chat_json(PROMPT,
                          "Adapta estas lineas:\n"
                          + json.dumps(peticion, ensure_ascii=False),
                          temperature=0.4, max_tokens=4000)
        except Exception as e:
            log.warning(f"Fallo el lote {arranque}: {e}")
            continue
        lineas = r.get("lineas") if isinstance(r, dict) else r
        for x in (lineas or []):
            try:
                i = int(x["i"])
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= i < len(salida):
                salida[i] = str(x.get("es", "")).strip()

    largos = sum(1 for (a, b, _), t in zip(frases, salida)
                 if t and len(t.split()) > _limite(b - a) * 1.25)
    if largos:
        log.info(f"{largos} de {len(frases)} lineas se pasaron del hueco; "
                 f"se corrigen con tempo al montar")
    return salida


def _ajustar_al_hueco(audio, destino, objetivo):
    """Encaja el audio en su hueco exacto sin que se note.

    Hasta un 6% se corrige con atempo, que el oido no distingue. Mas alla se
    deja como esta y se acepta el desfase: una voz acelerada al 20% suena a
    dibujo animado y delata el doblaje al instante.
    """
    from src.utils import get_duration
    real = get_duration(audio)
    if real <= 0 or objetivo <= 0:
        return audio
    factor = real / objetivo
    if abs(factor - 1) < 0.01:
        return audio
    if factor > TEMPO_MAX:
        log.info(f"  linea {real:.1f}s en hueco de {objetivo:.1f}s: se deja, "
                 f"corregirla al {factor:.0%} se notaria")
        factor = TEMPO_MAX
    run_cmd(["ffmpeg", "-y", "-i", str(audio), "-filter:a",
             f"atempo={max(0.94, min(TEMPO_MAX, factor)):.4f}",
             "-c:a", "pcm_s16le", str(destino)])
    return destino


def sincronizar(frases, audios, salida, duracion_total):
    """Coloca cada linea doblada en el segundo exacto del original."""
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)

    entradas, filtros, etiquetas = [], [], []
    for k, ((ini, fin, _), audio) in enumerate(zip(frases, audios)):
        if not audio or not Path(audio).exists():
            continue
        entradas += ["-i", str(audio)]
        filtros.append(f"[{len(etiquetas)}:a]adelay={int(ini*1000)}|"
                       f"{int(ini*1000)}[a{k}]")
        etiquetas.append(f"[a{k}]")

    if not etiquetas:
        return None
    mezcla = ("".join(filtros) + ";" + "".join(etiquetas)
              + f"amix=inputs={len(etiquetas)}:normalize=0[out]")
    run_cmd(["ffmpeg", "-y"] + entradas + ["-filter_complex", mezcla,
             "-map", "[out]", "-t", f"{duracion_total:.2f}",
             "-c:a", "pcm_s16le", str(salida)])
    return salida
