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


def icfg_guiones(config):
    return int(config.get("intelligence", {}).get("guiones_por_dia", 3))


def producir_guion_del_dia(config):
    # El concepto va PRIMERO: escribir bien sobre un tema que el espectador ya
    # ha visto quinientas veces no sirve de nada. Si ningun angulo convence,
    # se cae a la lista de temas de siempre en vez de bloquear la produccion.
    log.info("Buscando el angulo del dia...")
    concepto = None
    try:
        from src.conceptos import elegir_concepto
        concepto = elegir_concepto()
    except Exception as e:
        log.warning(f"Fallo la busqueda de concepto ({str(e)[:90]})")

    if concepto:
        # Se le pasa el ESQUELETO, no solo el titulo: las tres revelaciones en
        # orden son lo que impide que el guion se quede dando vueltas.
        rev = concepto.get("revelaciones") or []
        tema = (f"{concepto['titulo']}\n"
                f"ANGULO: {concepto.get('angulo','')}\n"
                f"ESTRUCTURA OBLIGATORIA — revela estas tres cosas EN ESTE ORDEN, "
                f"cada una mas fuerte que la anterior, y no digas ninguna dos veces:\n"
                + "\n".join(f"  {i+1}. {r}" for i, r in enumerate(rev)))
    else:
        tema = get_next_topic()

    log.info(f"Generando guiones desde la matrix (n={icfg_guiones(config)})...")
    guiones = generar_guiones_desde_matrix(n=icfg_guiones(config), tema_semana=tema)
    if not guiones:
        log.error("No se generaron guiones validos")
        return None

    from .showrunner import revisar_paquete
    from .script_generator import aplicar_cambios
    log.info("SHOWRUNNER revisando el paquete...")
    # Se reescribe hasta N veces mientras el showrunner lo rechace. Antes solo
    # se daba UNA pasada, aunque la configuracion ya preveia varias; con un
    # showrunner exigente una sola no basta para arreglar el hilo.
    # Al agotarse los intentos se produce igual: la regla del proyecto es
    # publicar siempre, la matrix no reemplaza publicar.
    maximo = int(config["intelligence"].get("maximos_reintentos_reescritura", 2))
    aprobados = []
    for g in guiones:
        for intento in range(maximo):
            r = revisar_paquete(g)
            if r.get("veredicto") != "REWRITE" or not r.get("cambios"):
                break
            log.info(f"Reescritura {intento+1}/{maximo}: {r.get('nota_corta','')[:90]}")
            g2 = aplicar_cambios(g, r["cambios"])
            if not g2:
                break
            g = g2
        aprobados.append(g)

    log.info("Simulando guiones contra la matrix...")
    mejor = seleccionar_mejor(aprobados, config)
    if mejor:
        mejor["guion"]["_tema"] = tema or mejor["guion"].get("titulo", "")
        log.info(f"Guion del dia: '{mejor['guion'].get('titulo')}' (score {mejor['score']})")
    return mejor


def es_dia_de_actualizacion(config):
    dia_cfg = config["intelligence"].get("dia_actualizacion_matrix", "lunes")
    dia_esperado = MAPA_DIAS.get(dia_cfg.lower(), "monday")
    return datetime.now().strftime("%A").lower() == dia_esperado
