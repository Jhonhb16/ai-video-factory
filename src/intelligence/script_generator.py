"""Guiones de ALTO IMPACTO (beats cortos) + expansion + registro."""
import csv
import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from src.llm import chat_json
from .matrix_generator import cargar_matrix

log = logging.getLogger("VideoFactory.Intelligence")

PROHIBIDAS = [
    "ganar dinero rápido", "hazte rico", "inversión garantizada",
    "rendimiento asegurado", "duplica tu dinero", "sin riesgo",
    "libertad financiera en", "secreto que los bancos",
]

# Frases que delatan tono de LECTURA/ENSAYO (matan la retencion)
LECTURA_PROHIBIDA = [
    "en este video", "a continuacion", "en conclusion", "es importante mencionar",
    "como hemos visto", "por lo tanto", "en primer lugar", "estimados",
    "hoy vamos a hablar", "vamos a analizar", "de manera adecuada",
    "herramienta util", "queridos amigos", "sin mas preambulos",
    "como sabemos", "cabe destacar",
]

SYSTEM_PROMPT = """Eres guionista de reels VIRALES de finanzas en español.
NO escribes para leer: escribes para VIDEO de alto impacto que ROMPE EL SCROLL.
REGLAS DE ORO DEL RITMO:
- Cada linea (beat) tiene 5-12 palabras. MAXIMO 14.
- Frases cortas. Punto seguido. Cero conectores de ensayo.
- Habla de "tu", como amigo, cero tecnicismos (lo complejo se explica con cafe, super, renta).
- Un dato o numero concreto cada 2-3 lineas.
- Un open loop a la mitad ("y el numero 3 es el que mas dano te hace...").
PROHIBIDO (suena a lectura): "en este video", "a continuacion", "en conclusion",
"es importante mencionar", "por lo tanto", "en primer lugar", "estimados",
"hoy vamos a hablar", "vamos a analizar", "de manera adecuada".
El HOOK (primeros 3s) dispara: curiosidad / identificacion / experiencia vivida.
ESTRUCTURA: hook (1-2 lineas) → tension (2-3 lineas) → 3 puntos (3-4 lineas c/u con numero)
→ cierre (2 lineas) → CTA (1-2 lineas). TOTAL: 24-30 lineas, 260-340 palabras.
EJEMPLO DEL TONO EXACTO QUE QUIERO (copialo como referencia):
  "Llegas al 15 sin un peso."
  "Y no, no es mala suerte."
  "Es esto."
  "La mitad de tu quincena se va en lo fijo."
  "Renta, luz, super."
  "El 30, en antojos que ni recuerdas."
  "Cafe de 60, taxi, la app de comida."
  "Y el 20... ese ni existe."
  "Porque nadie te enseno a apartarlo."
  "Hoy cambias eso."
Responde UNICAMENTE JSON valido:
{
  "titulo": "maximo 8 palabras",
  "tipo_hook": "curiosidad / identificacion / experiencia_vivida / negacion_mito",
  "estructura_usada": "beats-punch",
  "hook": "8-15 palabras que rompen scroll",
  "beats": ["linea de 5-12 palabras con su puntuacion", "..."],
  "cta": "maximo 20 palabras",
  "escenas": [{"keyword": "stock search words english", "prompt_imagen": "english description"}],
  "hashtags": ["maximo 5"]
}"""

SYSTEM_PROMPT_EXPAND = """Eres editor de guiones de reels de finanzas en español.
Recibes un guion en lineas (beats) que quedo CORTO.
Agregale 4-8 lineas NUEVAS de 5-12 palabras con ejemplos cotidianos y numeros.
NO cambies hook, CTA, titulo ni tema. Cero tono de ensayo.
Devuelve el MISMO JSON completo con el arreglo "beats" ampliado.
Responde UNICAMENTE JSON valido."""


def generar_guiones_desde_matrix(n=3, tema_semana=None):
    matrix = cargar_matrix()
    matrix_txt = json.dumps(matrix, ensure_ascii=False)
    tema_txt = f"Tema sugerido: {tema_semana}" if tema_semana else "Elige tu un tema de finanzas personales"

    validos = []
    for i in range(n):
        try:
            g = chat_json(
                SYSTEM_PROMPT,
                f"MATRIX DE VIRALIDAD:\n{matrix_txt}\n{tema_txt}\n\nEscribe el guion #{i+1} de hoy con combinacion distinta de hook/estructura. JSON de UN solo guion:",
                temperature=0.9, max_tokens=8000)
        except Exception as e:
            log.warning(f"Guion #{i+1} fallo al generar: {e}")
            continue
        g = _validar_y_ajustar(g)
        if g:
            validos.append(g)

    log.info(f"{len(validos)}/{n} guiones validos generados desde la matrix")
    return validos


def _extraer_beats(g):
    beats = [b.strip() for b in (g.get("beats") or []) if b and b.strip()]
    if not beats and g.get("guion"):
        beats = [f.strip() for f in re.split(r"(?<=[.!?])\s+", g["guion"]) if f.strip()]
    return beats


def _validar_y_ajustar(g):
    if not isinstance(g, dict):
        return None
    beats = _extraer_beats(g)
    if not beats:
        return None
    palabras = sum(len(b.split()) for b in beats)

    # Capa expansion si quedo corto
    if palabras < 250:
        log.info(f"Guion corto ({palabras} palabras). Pidiendo expansion en beats...")
        try:
            g2 = chat_json(
                SYSTEM_PROMPT_EXPAND,
                f"GUION ACTUAL ({palabras} palabras):\n{json.dumps(g, ensure_ascii=False)}",
                temperature=0.7, max_tokens=8000)
            if isinstance(g2, dict):
                g = {**g, **g2}
                beats = _extraer_beats(g)
        except Exception as e:
            log.warning(f"Expansion fallo: {e}")
        palabras = sum(len(b.split()) for b in beats)

    texto = (g.get("hook", "") + " " + " ".join(beats) + " " + g.get("titulo", "")).lower()
    # normaliza tildes para los filtros
    texto_plano = texto

    if any(p.lower() in texto_plano for p in PROHIBIDAS):
        log.warning(f"Guion '{g.get('titulo')}' descartado: frase prohibida")
        return None
    if any(p.lower() in texto_plano for p in LECTURA_PROHIBIDA):
        log.warning(f"Guion '{g.get('titulo')}' descartado: tono de lectura/ensayo")
        return None
    if not (230 <= palabras <= 370):
        log.warning(f"Guion '{g.get('titulo')}' con {palabras} palabras fuera de rango (230-370)")
        return None
    largos = [b for b in beats if len(b.split()) > 16]
    if len(largos) > 2:
        log.warning(f"Guion '{g.get('titulo')}' con ritmo de lectura ({len(largos)} lineas largas)")
        return None

    g["beats"] = beats
    g["guion"] = "\n".join(beats)
    g["_palabras"] = palabras
    return g


def get_next_topic():
    if not Path("topics.csv").exists():
        return None
    usados = set()
    log_file = Path("output/published_log.csv")
    if log_file.exists():
        with open(log_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                usados.add(row.get("tema_hash", ""))
    with open("topics.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tema = (row.get("tema") or "").strip()
            if tema and hashlib.md5(tema.encode()).hexdigest()[:8] not in usados:
                return tema
    return None


def registrar_publicacion(guion, score, url=""):
    log_file = Path("output/published_log.csv")
    existe = log_file.exists()
    tema = guion.get("_tema") or guion.get("titulo", "")
    tema_hash = hashlib.md5(tema.encode()).hexdigest()[:8]
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not existe:
            w.writerow(["fecha", "titulo", "tema_hash", "score", "url"])
        w.writerow([datetime.now().strftime("%Y%m%d"), guion.get("titulo", ""),
                    tema_hash, score, url])

    scores_file = Path("output/intelligence/scores_log.csv")
    existe2 = scores_file.exists()
    with open(scores_file, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not existe2:
            w.writerow(["fecha", "titulo", "tipo_hook", "estructura", "score_simulado"])
        w.writerow([datetime.now().strftime("%Y%m%d"), guion.get("titulo", ""),
                    guion.get("tipo_hook", ""), guion.get("estructura_usada", ""), score])
