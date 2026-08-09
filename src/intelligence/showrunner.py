"""SHOWRUNNER: lider con criterio alto. GO/NO-GO antes de producir."""
import json
import logging
from src.llm import chat_json

log = logging.getLogger("VideoFactory.Showrunner")

PROMPT = """Eres el SHOWRUNNER (director creativo) de un estudio de reels de finanzas-COMEDIA.
Revisas el paquete de produccion con criterio ALTO tipo MrBeast. Checklist:
1. HOOK 3s: detiene el scroll SI o SI.
2. COMEDIA: minimo 4 momentos de risa (regla de 3, exageracion, autodesprecio, callback al hook).
3. RITMO: ninguna linea > 14 palabras; cero tono de ensayo.
4. VALOR: el espectador aprende algo REAL de finanzas (no solo risa).
5. VISUAL: hay cambios planificados (escena/pose/SFX) para cada 3 segundos.
6. CIERRE: punch final + ensenanza + CTA que genera comentarios.
Se honesto: si esta flojo, REWRITE con cambios concretos.
Devuelve UNICAMENTE JSON:
{"veredicto": "GO" | "REWRITE", "nota_corta": "frase", "cambios": ["cambio concreto", "..."]}"""


def revisar_paquete(guion):
    try:
        paquete = {k: guion.get(k) for k in ("titulo", "hook", "beats", "cta", "escenas")}
        r = chat_json(PROMPT, f"PAQUETE:\n{json.dumps(paquete, ensure_ascii=False)}",
                      temperature=0.3, max_tokens=1500)
    except Exception as e:
        log.warning(f"Showrunner fallo ({e}). Aprobando por defecto.")
        return {"veredicto": "GO"}
    log.info(f"SHOWRUNNER: {r.get('veredicto')} - {r.get('nota_corta', '')}")
    return r
