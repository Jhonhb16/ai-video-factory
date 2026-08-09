"""Simulador: rúbrica fija de 100 puntos + calibración + reescritura."""
import json
import logging
from src.llm import chat_json, chat_text
from .matrix_generator import cargar_matrix

log = logging.getLogger("VideoFactory.Intelligence")

SYSTEM_PROMPT_SIMULADOR = """Eres un juez estricto de contenido viral de finanzas personales en español.
Evalúas con RÚBRICA FIJA de 100 puntos. Tu score DEBE ser la suma exacta de los items.
RÚBRICA:
- hook (0-30): dispara curiosidad, identificacion o experiencia vivida? es coloquial? detiene el scroll en 3s?
- estructura (0-25): sigue una estructura ganadora? abre, desarrolla con puntos, cierra?
- tema (0-20): esta en los temas populares con angulo ganador?
- cta (0-15): usa un tipo de CTA efectivo?
- formato (0-10): longitud en rango? numeros concretos? cero tecnicismos?
PENALIZACION: frases que prometen riqueza o rendimientos: resta 20. Tecnicismos o lenguaje formal: resta 15.
CALIBRACION (referencia obligatoria):
- ~85: hook de dato impactante con numero, 3 puntos con ejemplos numericos, CTA de pregunta abierta, 300 palabras.
- ~55: hook generico, desarrollo sin numeros, CTA debil.
- ~30: saludo largo, tema tecnico sin aterrizar, sin CTA, promesas de dinero facil.
Responde UNICAMENTE JSON valido:
{
  "analisis": {
    "hook": {"puntos": 0-30, "comentario": "..."},
    "estructura": {"puntos": 0-25, "comentario": "..."},
    "tema": {"puntos": 0-20, "comentario": "..."},
    "cta": {"puntos": 0-15, "comentario": "..."},
    "formato": {"puntos": 0-10, "comentario": "..."}
  },
  "penalizacion": 0,
  "score": 0-100,
  "probabilidad": "alta/media/baja",
  "fortalezas": ["..."],
  "debilidades": ["..."],
  "cambios_concretos": ["..."],
  "guion_reescrito": "version mejorada completa o null si score >= 80"
}"""


def evaluar_guion(guion_data):
    matrix = cargar_matrix()
    texto = (f"TITULO: {guion_data.get('titulo','')}\n"
             f"TIPO HOOK: {guion_data.get('tipo_hook','')}\n"
             f"HOOK: {guion_data.get('hook','')}\n"
             f"GUION ({guion_data.get('_palabras', len(guion_data.get('guion','').split()))} palabras): {guion_data.get('guion','')}\n"
             f"CTA: {guion_data.get('cta','')}")

    r = chat_json(SYSTEM_PROMPT_SIMULADOR,
                  f"MATRIX:\n{json.dumps(matrix, ensure_ascii=False)}\n\nGUION:\n{texto}\n\nJSON:",
                  temperature=0.15, max_tokens=2500)

    suma = sum(v.get("puntos", 0) for v in r.get("analisis", {}).values())
    suma -= r.get("penalizacion", 0)
    if abs(suma - r.get("score", -1)) > 3:
        log.warning(f"Score reportado ({r.get('score')}) != suma rubrica ({suma}). Corrigiendo.")
        r["score"] = max(0, min(100, suma))
    r["probabilidad"] = "alta" if r["score"] >= 75 else "media" if r["score"] >= 60 else "baja"
    return r


def seleccionar_mejor(guiones, config):
    score_min = config["intelligence"]["score_minimo_publicar"]
    resultados = []
    for g in guiones:
        try:
            ev = evaluar_guion(g)
            resultados.append((g, ev))
            log.info(f"   '{g.get('titulo','')}' -> {ev['score']}/100 ({ev['probabilidad']})")
        except Exception as e:
            log.error(f"Error evaluando guion: {e}")

    if not resultados:
        return None

    resultados.sort(key=lambda x: x[1]["score"], reverse=True)
    mejor, evaluacion = resultados[0]

    if evaluacion["score"] < score_min and evaluacion.get("guion_reescrito"):
        log.info(f"Mejor guion bajo umbral ({evaluacion['score']}). Reescribiendo...")
        mejor["guion"] = evaluacion["guion_reescrito"]
        mejor["_palabras"] = len(mejor["guion"].split())
        evaluacion = evaluar_guion(mejor)
        log.info(f"   Re-evaluado -> {evaluacion['score']}/100")

    if evaluacion["score"] >= score_min:
        return {"guion": mejor, "score": evaluacion["score"], "evaluacion": evaluacion,
                "todos_los_scores": [(g.get("titulo"), e["score"]) for g, e in resultados]}

    log.error(f"Ningun guion paso el umbral de {score_min}. Mejor: {evaluacion['score']}")
    return None
