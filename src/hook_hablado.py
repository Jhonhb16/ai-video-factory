"""Hook hablado: el personaje abre el video moviendo los labios de verdad.

Alcance v1: SOLO la apertura. El resto del video sigue con planos fijos y
movimiento de camara. Un hook con la cara viva es lo que hace que el
espectador se quede; a partir de ahi manda el ritmo de corte.

Reglas duras:
- Nunca hard-fail: si SadTalker falla, tarda de mas o no esta instalado,
  se devuelve None y el video sale con la apertura normal.
- Solo local: SadTalker necesita GPU, asi que en GitHub Actions esto no
  se activa nunca y la nube sigue produciendo igual.
- Con cache: el hook solo se re-renderiza si cambia el audio.
"""
import hashlib
import logging
import subprocess
import time
from pathlib import Path

from src.utils import load_config, get_duration

log = logging.getLogger("VideoFactory.HookHablado")

SADTALKER = Path("D:/LipSyncTools/SadTalker")
CACHE = Path("output/cache/hook")


def _cfg():
    c = load_config().get("hook_hablado", {}) or {}
    return {
        "activado": bool(c.get("activado", False)),
        "segundos": float(c.get("segundos", 12)),
        "tamano": int(c.get("tamano", 256)),
        "timeout": int(c.get("timeout_segundos", 900)),
        "ruta": Path(c.get("ruta_sadtalker") or SADTALKER),
    }


def disponible():
    """SadTalker instalado y utilizable en esta maquina."""
    cfg = _cfg()
    if not cfg["activado"]:
        return False
    py = cfg["ruta"] / "venv/Scripts/python.exe"
    return py.exists() and (cfg["ruta"] / "inference.py").exists()


def _huella(wav, tamano):
    h = hashlib.sha256()
    h.update(wav.read_bytes())
    h.update(str(tamano).encode())
    return h.hexdigest()[:16]


def _extraer_audio(audio, segundos, destino):
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(audio), "-t", f"{segundos:.3f}",
         "-ar", "16000", "-ac", "1", str(destino)],
        capture_output=True, check=True)


def generar_hook(audio, imagen, segundos=None):
    """Devuelve el mp4 del hook hablado, o None si no se pudo (nunca lanza).

    'segundos' lo manda el ensamblador ya cuadrado con los planos que va a
    sustituir. Si se pide 12s "a ojo" y los planos suman 12.9s, el video
    resultante no encaja y hay que tirarlo.
    """
    cfg = _cfg()
    if not cfg["activado"]:
        return None
    if not disponible():
        log.info("SadTalker no disponible aqui; el hook sale con la apertura normal.")
        return None

    imagen = Path(imagen)
    audio = Path(audio)
    if not imagen.exists() or not audio.exists():
        log.warning("Falta la imagen o el audio del hook.")
        return None

    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        pedido = segundos if segundos and segundos > 0 else cfg["segundos"]
        segundos = min(pedido, get_duration(audio))
        wav = CACHE / "hook.wav"
        _extraer_audio(audio, segundos, wav)

        # La cache depende del audio Y del tamano de render: cambiar a 512
        # debe re-renderizar, no reutilizar el de 256.
        clave = _huella(wav, cfg["tamano"])
        final = CACHE / f"hook_{clave}.mp4"
        if final.exists() and final.stat().st_size > 10000:
            log.info(f"Hook hablado en cache ({final.name}); no se re-renderiza.")
            return final

        trabajo = CACHE / "render"
        trabajo.mkdir(parents=True, exist_ok=True)
        py = cfg["ruta"] / "venv/Scripts/python.exe"

        log.info(f"Generando hook hablado ({segundos:.1f}s, tamano {cfg['tamano']}). "
                 f"Puede tardar unos minutos...")
        t0 = time.time()
        r = subprocess.run(
            [str(py), "inference.py",
             "--driven_audio", str(wav.resolve()),
             "--source_image", str(imagen.resolve()),
             "--result_dir", str(trabajo.resolve()),
             "--preprocess", "full",     # conserva el plano completo, no solo la cara
             "--still",                  # sin cabeceo exagerado
             "--size", str(cfg["tamano"]),
             "--batch_size", "2"],
            cwd=str(cfg["ruta"]),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",   # su salida rompe cp1252 en Windows
            timeout=cfg["timeout"])
        tardo = time.time() - t0

        if r.returncode != 0:
            log.warning(f"SadTalker fallo (codigo {r.returncode}): "
                        f"{(r.stderr or '')[-200:]}")
            return None

        videos = sorted(trabajo.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not videos:
            log.warning("SadTalker termino sin producir video.")
            return None

        videos[-1].replace(final)
        for sobra in trabajo.rglob("*"):
            if sobra.is_file():
                sobra.unlink(missing_ok=True)

        log.info(f"Hook hablado listo en {tardo:.0f}s "
                 f"({tardo/max(segundos,0.1):.0f}x tiempo real): {final.name}")
        return final

    except subprocess.TimeoutExpired:
        log.warning(f"SadTalker supero el limite de {cfg['timeout']}s; "
                    f"se usa la apertura normal.")
        return None
    except Exception as e:
        log.warning(f"Hook hablado fallo ({e}); se usa la apertura normal.")
        return None
