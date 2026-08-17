"""Pipeline principal v3 (serverless-ready)."""
import argparse
import csv
import json
import sys
import logging
from pathlib import Path
from src.utils import load_config, notify, today

DIRS = ["output/scripts", "output/audio", "output/images",
        "output/final", "output/intelligence", "logs", "data", "assets/music"]
for d in DIRS:
    Path(d).mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/pipeline.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("VideoFactory")

STATE_FILE = Path("output/state.json")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"date": today(), "completed": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def reset_if_new_day(state):
    if state.get("date") != today():
        state = {"date": today(), "completed": []}
        save_state(state)
    return state


def ya_publicado_hoy():
    pub_log = Path("output/published_log.csv")
    if not pub_log.exists():
        return False
    with open(pub_log, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("fecha") == today():
                return True
    return False


def run(draft=False, skip_intelligence=False):
    config = load_config()
    state = reset_if_new_day(load_state())

    if ya_publicado_hoy():
        log.warning("Ya se publico hoy. Saliendo.")
        return

    resultado = {"data": None}

    def paso_inteligencia():
        from src.intelligence.orchestrator import actualizar_inteligencia
        try:
            actualizar_inteligencia(config)
        except Exception as e:
            log.error(f"Inteligencia fallo ({e}). Se continua con matrix existente/respaldo.")
            notify(f"Inteligencia fallo; usando matrix de respaldo: {e}", ok=False)

    def paso_guion():
        from src.intelligence.orchestrator import producir_guion_del_dia
        res = producir_guion_del_dia(config)
        if res is None:
            raise RuntimeError("Ningun guion paso el simulador")
        sf = Path(f"output/scripts/video_{today()}.json")
        sf.parent.mkdir(parents=True, exist_ok=True)
        sf.write_text(json.dumps(res["guion"], ensure_ascii=False, indent=2), encoding="utf-8")
        resultado["data"] = res

    def paso_voz():
        from src.voice_generator import generate_voice
        generate_voice(resultado["data"])

    # ¿se pudieron componer escenas con personajes y escenarios propios?
    propias = {"ok": False}

    def _guion_actual():
        if resultado["data"]:
            return resultado["data"]["guion"]
        from src.utils import load_script
        return load_script()

    def paso_imagenes():
        # Cadena de respaldo, de mejor a peor: escenas generadas con IA
        # (protagonista fijo + secundarios nuevos) -> escenas compuestas en
        # local -> generadores de imagen -> tarjetas de texto.
        g = _guion_actual()
        n = 0

        try:
            from src.escenas_ia import generar_escenas_ia, disponible as ia_ok
            if ia_ok():
                from src.utils import get_duration, audio_path
                from src.video_assembler import _beat_timeline
                from src.alineador import alinear
                dur = get_duration(audio_path())
                items = alinear(_beat_timeline(g, dur), audio_path(), dur)
                n = generar_escenas_ia(g, items, today())
        except Exception as e:
            log.warning(f"Escenas con IA fallaron ({e}); se prueba el sistema local.")
            n = 0

        if n >= 8:
            propias["ok"] = True
            log.info(f"{n} escenas generadas con IA: se omite el b-roll de stock.")
            return

        from src.escenarios_propios import generar_escenas
        try:
            n = generar_escenas(g)
        except Exception as e:
            log.warning(f"Escenas propias fallaron ({e}); se usa el sistema anterior.")
            n = 0
        if n >= 8:
            propias["ok"] = True
            log.info(f"{n} escenas propias: se omite el b-roll de stock.")
            return
        from src.image_generator import generate_images
        generate_images(resultado["data"])

    def paso_media():
        from src.stock_media import download_media, descargar_sfx
        g = _guion_actual()
        if propias["ok"]:
            # con escenas propias no hace falta stock; si acaso, musica y SFX
            descargar_sfx()
        else:
            download_media(g)

        # La mascota sobra si ya salen los personajes del canal: serian dos
        # estilos distintos peleando en el mismo plano.
        mascot_dir = Path("output/media/mascot")
        if propias["ok"]:
            for p in mascot_dir.glob("*.png"):
                p.unlink()
        else:
            from src.mascot import generar_mascotas
            generar_mascotas()

    def paso_video():
        from src.video_assembler import assemble_video
        assemble_video()

    def paso_disclosure():
        from src.ai_disclosure import add_disclosure
        add_disclosure()

    def paso_dashboard():
        from src.dashboard import publicar_dashboard
        info = None
        if resultado["data"]:
            info = {"titulo": resultado["data"]["guion"].get("titulo", ""),
                    "score": resultado["data"].get("score", -1),
                    "modo": "publicado" if config.get("publicacion", {}).get("activada") else "prueba"}
        url = publicar_dashboard(info)
        if url:
            log.info(f"Panel disponible en: {url}")

    steps = []
    from src.intelligence.orchestrator import es_dia_de_actualizacion
    if not skip_intelligence and es_dia_de_actualizacion(config):
        steps.append(("intelligence", "Actualizando matrix de viralidad", paso_inteligencia))
    steps += [
        ("script", "Generando y simulando guiones", paso_guion),
        ("voice", "Generando voz", paso_voz),
        ("images", "Generando imagenes", paso_imagenes),
        ("media", "Descargando b-roll real y musica", paso_media),
        ("video", "Ensamblando video", paso_video),
        ("disclose", "Aplicando etiqueta IA", paso_disclosure),
        ("dashboard", "Publicando dashboard", paso_dashboard),
    ]

    for key, msg, func in steps:
        if key in state["completed"]:
            log.info(f"Paso ya completado: {key}")
            continue
        log.info(f">> {msg}")
        try:
            func()
            state["completed"].append(key)
            save_state(state)
        except Exception as e:
            log.error(f"Fallo en '{key}': {e}")
            notify(f"Fallo en '{key}': {e}", ok=False)
            sys.exit(1)

    if resultado["data"] is None:
        sf = Path(f"output/scripts/video_{today()}.json")
        if sf.exists():
            resultado["data"] = {"guion": json.loads(sf.read_text(encoding="utf-8")), "score": -1}
            log.info("Guion reconstruido desde disco (modo retry).")

    if resultado["data"] is None:
        notify("Sin guion disponible hoy. No se publica.", ok=False)
        return

    final_video = Path("output/final/video_final.mp4")
    if not final_video.exists():
        notify("video_final.mp4 no existe tras el pipeline.", ok=False)
        sys.exit(1)

    if draft:
        notify("MODO DRAFT: video listo, publicacion pausada.", ok=True)
        return

    _publicar(final_video, resultado["data"], state)


def _publicar(final_video, guion_data, state):
    config = load_config()
    if not config.get("publicacion", {}).get("activada", True):
        log.info("MODO PRUEBA: publicacion desactivada. Video listo en output/final/")
        notify("Modo prueba: video generado OK (publicacion desactivada).", ok=True)
        return

    if "publish" in state["completed"]:
        log.info("Ya publicado hoy.")
        return
    try:
        from src.publisher import publish_video
        urls = publish_video(str(final_video), guion_data["guion"])
        from src.intelligence.script_generator import registrar_publicacion
        registrar_publicacion(guion_data["guion"], guion_data.get("score", -1),
                              urls.get("facebook", ""))
        state["completed"].append("publish")
        save_state(state)
        notify(f"Publicado score={guion_data.get('score')} | FB: {urls.get('facebook','s/d')} | IG: {urls.get('instagram','s/d')}", ok=True)
        STATE_FILE.unlink(missing_ok=True)
    except Exception as e:
        notify(f"Fallo al publicar: {e}", ok=False)
        sys.exit(1)


def publish_from_disk():
    final_video = Path("output/final/video_final.mp4")
    sf = Path(f"output/scripts/video_{today()}.json")
    if not sf.exists():
        candidates = sorted(Path("output/scripts").glob("video_*.json"))
        if not candidates:
            log.error("No hay ningun guion generado.")
            sys.exit(1)
        sf = candidates[-1]
        log.info(f"Usando guion mas reciente: {sf.name}")
    if not final_video.exists():
        log.error("Falta video_final.mp4.")
        sys.exit(1)
    state = reset_if_new_day(load_state())
    guion = json.loads(sf.read_text(encoding="utf-8"))
    _publicar(final_video, {"guion": guion, "score": -1}, state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--publish-only", action="store_true")
    parser.add_argument("--skip-intelligence", action="store_true")
    args = parser.parse_args()

    if args.publish_only:
        publish_from_disk()
    elif args.draft:
        run(draft=True)
    else:
        run(skip_intelligence=args.skip_intelligence)
