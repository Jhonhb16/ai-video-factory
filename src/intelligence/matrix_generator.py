"""Genera matrix-viralidad con LLM + validacion + respaldo."""
import json
import logging
from pathlib import Path
from src.llm import chat_json
from .matrix_validator import validar_matrix

log = logging.getLogger("VideoFactory.Intelligence")

CONTEXT_FILE = Path("output/intelligence/contexto-viral.md")
MATRIX_FILE = Path("output/intelligence/matrix-viralidad.md")
MATRIX_JSON = Path("output/intelligence/matrix-viralidad.json")
RESPALDO = Path("data/matrix_respaldo.json")

SYSTEM_PROMPT_MATRIX = """Eres un analista experto en contenido viral de finanzas personales en español.
Analiza el contexto con videos virales y detecta patrones REALES con evidencia. Sé específico y cuantitativo.
Responde ÚNICAMENTE con un objeto JSON válido con esta estructura:
{
  "patrones": {
    "hooks": [{"tipo": "...", "descripcion": "...", "ejemplos_reales": ["..."], "frecuencia": "alta/media/baja"}],
    "temas_populares": [{"tema": "...", "engagement_promedio": "alto/medio/bajo", "angulo_ganador": "..."}],
    "estructuras": [{"nombre": "...", "abertura": "...", "desarrollo": "...", "cierre": "...", "duracion_tipica_segundos": 60}],
    "frases_ganadoras": ["..."],
    "palabras_clave": ["..."],
    "duracion_optima_rango": [30, 75],
    "ctas_efectivos": [{"tipo": "...", "ejemplo": "..."}]
  },
  "anti_patrones": {
    "hooks_a_evitar": ["..."],
    "temas_muertos": ["..."],
    "errores_comunes": ["..."]
  },
  "resumen_ejecutivo": "2-3 frases con la fórmula ganadora del nicho"
}"""


def cargar_matrix():
    if MATRIX_JSON.exists():
        try:
            data = json.loads(MATRIX_JSON.read_text(encoding="utf-8"))
            valida, razon = validar_matrix(data)
            if valida:
                return data
            log.warning(f"Matrix existente invalida ({razon}). Usando respaldo.")
        except Exception as e:
            log.warning(f"Matrix corrupta ({e}). Usando respaldo.")
    else:
        log.info("Matrix no existe aun. Usando respaldo generico.")
    return json.loads(RESPALDO.read_text(encoding="utf-8"))


def generar_matrix():
    if not CONTEXT_FILE.exists():
        log.warning("Sin contexto-viral.md. Se usara matrix de respaldo.")
        return RESPALDO

    contexto = CONTEXT_FILE.read_text(encoding="utf-8")
    if len(contexto.split("## Video ")) < 20:
        log.warning("Menos de 20 videos en contexto. Usando respaldo.")
        return RESPALDO

    if len(contexto) > 50000:
        contexto = _truncar_contexto(contexto, max_videos=50)

    try:
        data = chat_json(SYSTEM_PROMPT_MATRIX,
                         f"Analiza este contexto viral y genera la matrix en JSON:\n\n{contexto}\n\nJSON:",
                         temperature=0.3, max_tokens=4000)
    except Exception as e:
        log.error(f"Generacion de matrix fallo: {e}. Usando respaldo.")
        return RESPALDO

    valida, razon = validar_matrix(data)
    if not valida:
        log.error(f"Matrix generada invalida ({razon}). Usando respaldo.")
        return RESPALDO

    MATRIX_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    MATRIX_FILE.write_text(_json_a_markdown(data), encoding="utf-8")
    log.info(f"Matrix validada y guardada: {MATRIX_JSON}")
    return MATRIX_JSON


def _truncar_contexto(texto, max_videos):
    partes = texto.split("\n## Video ")
    header = partes[0]
    videos = partes[1:max_videos + 1]
    return header + "\n## Video " + "\n## Video ".join(videos)


def _json_a_markdown(data):
    from datetime import datetime
    lines = ["# MATRIX DE VIRALIDAD",
             f"Generada: {datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
             f"## Resumen Ejecutivo\n{data.get('resumen_ejecutivo', '')}\n"]
    p = data.get("patrones", {})
    lines.append("## Hooks Ganadores")
    for h in p.get("hooks", []):
        lines.append(f"### {h['tipo']} (frecuencia: {h['frecuencia']})")
        lines.append(h.get("descripcion", ""))
        for ej in h.get("ejemplos_reales", []):
            lines.append(f'- "{ej}"')
        lines.append("")
    lines.append("## Temas Populares")
    for t in p.get("temas_populares", []):
        lines.append(f"- **{t['tema']}** (engagement {t['engagement_promedio']}): {t.get('angulo_ganador', '')}")
    lines.append("")
    lines.append("## Estructuras")
    for e in p.get("estructuras", []):
        lines.append(f"### {e['nombre']} (~{e.get('duracion_tipica_segundos', '?')}s)")
        lines.append(f"- Abre: {e['abertura']}\n- Desarrolla: {e['desarrollo']}\n- Cierra: {e['cierre']}")
        lines.append("")
    r = p.get("duracion_optima_rango", [0, 0])
    lines.append(f"## Duracion optima: {r[0]}-{r[1]}s")
    lines.append(f"**Palabras clave:** {', '.join(p.get('palabras_clave', []))}")
    return "\n".join(lines)
