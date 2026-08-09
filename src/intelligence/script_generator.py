"""Genera guiones DESDE la matrix + expansion automatica + registro."""
import csv
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

SYSTEM_PROMPT = """Eres un guionista de contenido viral de finanzas personales en español.
ESCRIBES COMO SE HABLA: coloquial, directo, como contándoselo a un amigo.
CERO TECNICISMOS: lo complejo se explica con cafe, super, renta, la quincena.
Recibes una MATRIX DE VIRALIDAD con patrones reales. Escribe UN guion que los aplique.
El HOOK (primeros 3 segundos) debe disparar UNO de estos gatillos:
- Curiosidad: "hay un agujero en tu quincena y ni lo notas"
- Identificacion: "si llegas al 15 sin un peso, esto es para ti"
- Experiencia vivida: "yo hice esto por años y me costo carisimo"
ESTRUCTURA OBLIGATORIA CON PRESUPUESTO DE PALABRAS:
* Hook: 15-20 palabras
* Planteo del problema: 40-50 palabras
* Punto 1: 60-70 palabras con un numero o ejemplo cotidiano
* Punto 2: 60-70 palabras con un numero o ejemplo cotidiano
* Punto 3: 60-70 palabras con un numero o ejemplo cotidiano
* Cierre + CTA: 40-50 palabras
TOTAL: 300-340 palabras. Cuenta y NO entregues menos de 280.
Reglas: frases cortas, habla de "tu", NUNCA promesas de riqueza,
20 escenas visuales, escapa comillas dobles dentro de textos.
Responde UNICAMENTE JSON valido (un solo objeto):
{
  "titulo": "maximo 8 palabras",
  "tipo_hook": "curiosidad / identificacion / experiencia_vivida / negacion_mito",
  "estructura_usada": "nombre de estructura de la matrix",
  "hook": "maximo 15 palabras",
  "guion": "texto completo 300-340 palabras",
  "cta": "maximo 20 palabras",
  "escenas": [{"prompt_imagen": "descripcion en ingles, estilo cinematografico financiero"}],
  "hashtags": ["maximo 5"]
}"""

SYSTEM_PROMPT_EXPAND = """Eres un editor de guiones de finanzas en español coloquial.
Recibes un guion que quedo CORTO. Reescribelo AMPLIADO a 300-340 palabras.
NO cambies el hook, el CTA, el titulo ni el tema.
Agrega ejemplos cotidianos con numeros reales (cafe, super, renta, la quincena).
Frases cortas, ritmo, cero tecnicismos.
Devuelve el MISMO objeto JSON completo (todos los campos) con el "guion" ampliado.
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
                temperature=0.85, max_tokens=8000)
        except Exception as e:
            log.warning(f"Guion #{i+1} fallo al generar: {e}")
            continue
        g = _validar_y_ajustar(g)
        if g:
            validos.append(g)

    log.info(f"{len(validos)}/{n} guiones validos generados desde la matrix")
    return validos


def _validar_y_ajustar(g):
    if not isinstance(g, dict) or not g.get("guion"):
        return None
    palabras = len(g["guion"].split())

    # Capa 2: si llego corto, pedir expansion UNA vez
    if palabras < 250:
        log.info(f"Guion corto ({palabras} palabras). Pidiendo expansion a 300-340...")
        try:
            g2 = chat_json(
                SYSTEM_PROMPT_EXPAND,
                f"GUION ACTUAL ({palabras} palabras):\n{json.dumps(g, ensure_ascii=False)}",
                temperature=0.7, max_tokens=8000)
            if isinstance(g2, dict) and g2.get("guion"):
                g = {**g, **g2}
        except Exception as e:
            log.warning(f"Expansion fallo: {e}")
        palabras = len(g.get("guion", "").split())

    # Capa 3: filtros finales con rango tolerante
    texto = (g.get("hook", "") + " " + g.get("guion", "") + " " + g.get("titulo", "")).lower()
    if any(p.lower() in texto for p in PROHIBIDAS):
        log.warning(f"Guion '{g.get('titulo')}' descartado: frase prohibida")
        return None
    if not (230 <= palabras <= 370):
        log.warning(f"Guion '{g.get('titulo')}' con {palabras} palabras fuera de rango (230-370)")
        return None
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
