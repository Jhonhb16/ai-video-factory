"""Orquestador del Modulo 0: flujo semanal + guion del dia."""
import json
import logging
from datetime import datetime
from pathlib import Path
from .apify_scraper import ApifyScraper
from .transcriber import transcribir_top
from .context_builder import construir_contexto
from .matrix_generator import generar_matrix
from .script_generator import generar_guiones_desde_matrix, get_next_topic
from .script_simulator import seleccionar_mejor

log = logging.getLogger("VideoFactory.Intelligence")

REFERENTES_FILE = Path("output/intelligence/referentes.json")
MAPA_DIAS = {"lunes": "monday", "martes": "tuesday", "miercoles": "wednesday",
             "jueves": "thursday", "viernes": "friday", "sabado": "saturday",
             "domingo": "sunday"}


def _cargar_referentes(config):
    if REFERENTES_FILE.exists():
        try:
            refs = json.loads(REFERENTES_FILE.read_text())
            if refs:
                return refs
        except Exception:
            pass
    return config["intelligence"].get("referentes_instagram") or []


def _guardar_referentes(refs):
    REFERENTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFERENTES_FILE.write_text(json.dumps(refs, ensure_ascii=False))


def actualizar_inteligencia(config):
    log.info("Actualizando inteligencia viral...")
    icfg = config["intelligence"]
    scraper = ApifyScraper(config)

    refs = _cargar_referentes(config)
    if not refs:
        if not scraper.credito_suficiente():
            log.warning("Sin credito Apify. Matrix existente/respaldo sigue activa.")
            return
        refs = scraper.discover_referentes()
        if refs:
            _guardar_referentes(refs)

    if not refs:
        log.warning("Sin referentes. Matrix de respaldo activa.")
        return

    videos_data = []
    for ref in refs:
        reels = scraper.scrape_referente(ref)
        if not reels:
            continue
        reels = transcribir_top(reels, top_n=15,
                                model_name=icfg["whisper_model"],
                                device=icfg["whisper_device"])
        for r in reels:
            videos_data.append({"referente": ref, "video": r,
                                "transcripcion": r.get("transcripcion")})

    if videos_data:
        construir_contexto(videos_data)
        generar_matrix()
    else:
        log.warning("No se obtuvieron videos. Matrix existente/respaldo sigue activa.")

    try:
        from .feedback_loop import obtener_metricas_propias
        obtener_metricas_propias()
    except Exception as e:
        log.warning(f"Feedback propio fallo (normal al inicio): {e}")


def producir_guion_del_dia(config):
    log.info("Generando 5 guiones desde la matrix...")
    tema = get_next_topic()
    guiones = generar_guiones_desde_matrix(n=5, tema_semana=tema)
    if not guiones:
        log.error("No se generaron guiones validos")
        return None

    log.info("Simulando guiones contra la matrix...")
    mejor = seleccionar_mejor(guiones, config)
    if mejor:
        mejor["guion"]["_tema"] = tema or mejor["guion"].get("titulo", "")
        log.info(f"Guion del dia: '{mejor['guion'].get('titulo')}' (score {mejor['score']})")
    return mejor


def es_dia_de_actualizacion(config):
    dia_cfg = config["intelligence"].get("dia_actualizacion_matrix", "lunes")
    dia_esperado = MAPA_DIAS.get(dia_cfg.lower(), "monday")
    return datetime.now().strftime("%A").lower() == dia_esperado
