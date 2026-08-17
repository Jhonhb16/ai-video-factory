"""Alinea los subtitulos y los cortes con la voz REAL.

El problema que resuelve: el reparto de tiempos se hacia proporcional al
numero de palabras de cada frase. Suena razonable, pero la voz hace pausas
entre frases y el acelerado amplifica el desajuste, asi que el error se
ACUMULA. Medido en un video real: 2.87s de error medio y 4.76s el peor,
con 24 de 25 frases desfasadas mas de 0.3s. Los subtitulos iban segundos
por delante de la voz, y los cortes de plano con ellos.

La solucion es preguntarle al audio: faster-whisper devuelve el momento
exacto de cada palabra. Local, gratis y ~12s en GPU.
"""
import hashlib
import json
import logging
from pathlib import Path

log = logging.getLogger("VideoFactory.Alineador")

CACHE = Path("output/cache/alineado")


# Whisper escribe los numeros con DIGITOS y el guion con letra: "cinco años"
# se transcribe "5 años". Sin esta equivalencia la frase no empareja.
NUMEROS = {
    "cero": "0", "uno": "1", "un": "1", "una": "1", "dos": "2", "tres": "3",
    "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7", "ocho": "8",
    "nueve": "9", "diez": "10", "once": "11", "doce": "12", "quince": "15",
    "veinte": "20", "treinta": "30", "cuarenta": "40", "cincuenta": "50",
    "sesenta": "60", "setenta": "70", "ochenta": "80", "noventa": "90",
    "cien": "100", "mil": "1000",
}


def _normalizar(texto):
    limpio = "".join(c for c in texto.lower() if c.isalnum())
    return NUMEROS.get(limpio, limpio)


def _parecidas(a, b):
    """Tolera diferencias menores de transcripcion: 'llevas' vs 'lleva'."""
    if a == b:
        return True
    if not a or not b:
        return False
    corta, larga = (a, b) if len(a) < len(b) else (b, a)
    return len(corta) >= 4 and larga.startswith(corta) and len(larga) - len(corta) <= 2


def _huella(audio):
    h = hashlib.sha256()
    h.update(Path(audio).read_bytes())
    return h.hexdigest()[:16]


def _palabras_reales(audio, modelo="base"):
    """[(inicio, fin, palabra)] segun la voz. Cachea por huella del audio."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"{_huella(audio)}.json"
    if cache.exists():
        try:
            return [tuple(p) for p in json.loads(cache.read_text(encoding="utf-8"))]
        except Exception:
            pass

    from faster_whisper import WhisperModel
    try:
        import torch
        gpu = torch.cuda.is_available()
    except Exception:
        gpu = False

    wm = WhisperModel(modelo,
                      device="cuda" if gpu else "cpu",
                      compute_type="float16" if gpu else "int8")
    segmentos, _ = wm.transcribe(str(audio), language="es",
                                 word_timestamps=True, vad_filter=False)
    palabras = [(w.start, w.end, w.word.strip())
                for s in segmentos for w in (s.words or [])]
    cache.write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
    return palabras


def alinear(items, audio, duracion):
    """Devuelve los items con start/end corregidos contra la voz real.

    Si algo falla se devuelven los originales: esto nunca puede tumbar el
    montaje, solo mejorarlo.
    """
    if not items:
        return items
    try:
        palabras = _palabras_reales(audio)
        if len(palabras) < len(items):
            log.warning(f"Solo {len(palabras)} palabras reconocidas para "
                        f"{len(items)} frases; se deja el reparto estimado.")
            return items

        # Se avanza por el flujo de palabras sin retroceder, comparando las
        # PRIMERAS PALABRAS de la frase (no solo una): con una sola, un
        # "el" o un "tu" empareja en cualquier sitio.
        #
        # Y muy importante: si una frase no se encuentra, el cursor avanza
        # igualmente de forma proporcional. Antes se quedaba clavado y una
        # sola frase perdida hacia fallar TODAS las siguientes en cascada:
        # se paso de 25/25 aciertos a 6/23 por ese motivo.
        cursor = 0
        anclas = []
        for n, it in enumerate(items):
            trozos = [_normalizar(t) for t in it["txt"].split()[:3]]
            trozos = [t for t in trozos if t]
            restantes = max(1, len(items) - n)
            ventana = max(40, int((len(palabras) - cursor) / restantes * 3))

            mejor_pos, mejor_puntos = None, 0
            for j in range(cursor, min(cursor + ventana, len(palabras))):
                puntos = 0
                for k, objetivo in enumerate(trozos):
                    if j + k < len(palabras) and _parecidas(
                            _normalizar(palabras[j + k][2]), objetivo):
                        puntos += 1
                if puntos > mejor_puntos:
                    mejor_pos, mejor_puntos = j, puntos
                    if puntos == len(trozos):
                        break

            # una sola palabra coincidente no basta si la frase tiene varias
            minimo = 2 if len(trozos) >= 2 else 1
            if mejor_pos is not None and mejor_puntos >= minimo:
                anclas.append(palabras[mejor_pos][0])
                cursor = mejor_pos + 1
            else:
                anclas.append(None)
                # avance proporcional para no envenenar las frases siguientes
                cursor = min(len(palabras) - 1,
                             cursor + max(1, int((len(palabras) - cursor) / restantes)))

        emparejadas = sum(1 for a in anclas if a is not None)
        if emparejadas < len(items) * 0.6:
            log.warning(f"Solo se ubicaron {emparejadas}/{len(items)} frases; "
                        f"se deja el reparto estimado.")
            return items

        # Las que no se encontraron se interpolan entre sus vecinas
        for i, a in enumerate(anclas):
            if a is not None:
                continue
            prev = next((anclas[j] for j in range(i - 1, -1, -1) if anclas[j] is not None), 0.0)
            sig = next((anclas[j] for j in range(i + 1, len(anclas)) if anclas[j] is not None), duracion)
            anclas[i] = prev + (sig - prev) / 2

        # start = donde empieza a hablar; end = donde empieza la frase siguiente
        alineados = []
        for i, it in enumerate(items):
            ini = max(0.0, anclas[i])
            fin = anclas[i + 1] if i + 1 < len(anclas) else min(duracion, palabras[-1][1] + 0.25)
            if fin - ini < 0.25:                 # nunca una frase invisible
                fin = min(duracion, ini + 0.25)
            nuevo = dict(it)
            nuevo["start"], nuevo["end"] = ini, fin
            alineados.append(nuevo)

        desvios = [abs(a["start"] - o["start"]) for a, o in zip(alineados, items)]
        log.info(f"Subtitulos y cortes alineados con la voz real "
                 f"({emparejadas}/{len(items)} frases ancladas, "
                 f"correccion media {sum(desvios)/len(desvios):.2f}s, "
                 f"maxima {max(desvios):.2f}s)")
        return alineados

    except Exception as e:
        log.warning(f"No se pudo alinear con la voz ({e}); se usa el reparto estimado.")
        return items
