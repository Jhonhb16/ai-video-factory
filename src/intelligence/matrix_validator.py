"""Valida que una matrix tenga contenido minimo util."""
import logging

log = logging.getLogger("VideoFactory.Intelligence")


def validar_matrix(data):
    if not isinstance(data, dict):
        return False, "no es dict"
    if not data.get("resumen_ejecutivo"):
        return False, "sin resumen ejecutivo"
    p = data.get("patrones", {})
    if len(p.get("hooks", [])) < 2:
        return False, f"solo {len(p.get('hooks', []))} hooks (minimo 2)"
    if len(p.get("temas_populares", [])) < 2:
        return False, "menos de 2 temas"
    if len(p.get("estructuras", [])) < 1:
        return False, "sin estructuras"
    if not p.get("duracion_optima_rango"):
        return False, "sin duracion optima"
    hooks_con_ejemplo = [h for h in p["hooks"] if h.get("ejemplos_reales")]
    if len(hooks_con_ejemplo) < 1:
        return False, "ningun hook tiene ejemplos reales"
    return True, "ok"
