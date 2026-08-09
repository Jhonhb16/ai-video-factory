"""Genera guiones DESDE la matrix (uno por llamada) + registro."""
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
ESCRIBES COMO SE HABLA: coloquial, directo, como contándoselo a un amigo en una junta.
CERO TECNICISMOS: si una palabra es compleja, la explicas con cosas de la vida diaria
(cafe, super, renta, la quincena, el cel).
Recibes una MATRIX DE VIRALIDAD con patrones reales. Escribe UN guion que los aplique.
El HOOK (primeros 3 segundos) debe disparar UNO de estos 3 gatillos:
- Curiosidad: "hay un agujero en tu quincena y ni lo notas"
- Identificacion: "si llegas al 15 sin un peso, esto es para ti"
- Experiencia vivida: "yo hice esto por años y me costo carisimo"
Reglas estrictas:
- Guion entre 280 y 340 palabras (video de 120 segundos)
- Frases cortas. Ritmo. Habla de "tu", nunca de "usted"
- NUNCA promesas de riqueza o rendimientos
- 20 escenas visuales
- Escapa correctamente las comillas dobles dentro de los textos
Responde UNICAMENTE JSON valido (un solo objeto):
{
  "titulo": "maximo 8 palabras",
  "tipo_hook": "curiosidad / identificacion / experiencia_vivida / negacion_mito",
  "estructura_usada": "nombre de estructura de la matrix",
  "hook": "maximo 15 palabras",
  "guion": "texto completo 280-340 palabras, coloquial, sin tecnicismos",
  "cta": "maximo 20 palabras",
  "escenas": [{"prompt_imagen": "descripcion en ingles, estilo cinematografico financiero"}],
  "hashtags": ["maximo 5"]
}"""


def generar_guiones_desde_matrix(n=5, tema_semana=None):
    matrix = cargar_matrix()
    matrix_txt = json.dumps(matrix, ensure_ascii=False)
    tema_txt = f"Tema sugerido: {tema_semana}" if tema_semana else "Elige tu un tema de finanzas personales"

    validos = []
    for i in range(n):
        try:
            g = chat_json(
                SYSTEM_PROMPT,
                f"MATRIX DE VIRALIDAD:\n{matrix_txt}\n{tema_txt}\n\nEscribe el guion #{i+1} de hoy. Usa una combinacion de hook y estructura distinta a la de un video tipico. JSON de UN solo guion:",
                temperature=0.85, max_tokens=8000)
        except Exception as e:
            log.warning(f"Guion #{i+1} fallo al generar/parsear: {e}")
            continue

        texto = (g.get("hook", "") + " " + g.get("guion", "") + " " + g.get("titulo", "")).lower()
        if any(p.lower() in texto for p in PROHIBIDAS):
            log.warning(f"Guion '{g.get('titulo')}' descartado: frase prohibida")
            continue
        palabras = len(g.get("guion", "").split())
        if not (250 <= palabras <= 370):
            log.warning(f"Guion '{g.get('titulo')}' con {palabras} palabras fuera de rango")
            continue
        g["_palabras"] = palabras
        validos.append(g)

    log.info(f"{len(validos)}/{n} guiones validos generados desde la matrix")
    return validos


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
