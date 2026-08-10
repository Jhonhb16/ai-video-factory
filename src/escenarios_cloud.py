"""Escenarios PROPIOS en la nube: FLUX gratis via HuggingFace (sin GPU local).
Personaje consistente con misma semilla + descripcion fija."""
import os
import time
import logging
from pathlib import Path
from PIL import Image
from src.utils import load_config

log = logging.getLogger("VideoFactory.EscenariosCloud")
IMG_DIR = Path("output/images")
PROC_W, PROC_H = 1620, 2880

PERSONAJE = ("cartoon flat illustration of a friendly young latino man with black cap "
             "and green hoodie, simple clean shapes, same consistent character, ")


def _token():
    return (os.getenv("HF_TOKEN") or "").strip()


def activo():
    return bool(_token())


def _a_916(img):
    w, h = img.size
    target = 9 / 16
    if w / h > target:
        nw = int(h * target); left = (w - nw) // 2
        img = img.crop((left, 0, left + nw, h))
    elif w / h < target:
        nh = int(w / target); top = (h - nh) // 2
        img = img.crop((0, top, w, top + nh))
    return img.resize((PROC_W, PROC_H), Image.LANCZOS)


def generar_escenarios_cloud(guion):
    if not activo():
        return False
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        log.warning("huggingface_hub no instalado; salto cloud.")
        return False

    client = InferenceClient(token=_token())
    modelo = load_config().get("estudio_local", {}).get(
        "modelo_cloud", "black-forest-labs/FLUX.1-schnell")
    escenas = [e for e in guion.get("escenas", []) if isinstance(e, dict)][:20]
    ok = 0

    for i, e in enumerate(escenas):
        dest = IMG_DIR / f"img_{i+1:03d}.png"
        if dest.exists():
            ok += 1
            continue
        accion = (e.get("accion") or e.get("keyword") or "talking about money").strip()
        prompt = PERSONAJE + accion + ", cinematic financial scene"
        seed = 777 + (i // 3)   # misma semilla cada 3 escenas = personaje consistente

        for intento in range(3):
            try:
                try:
                    img = client.text_to_image(prompt, model=modelo, seed=seed,
                                               width=768, height=1152,
                                               num_inference_steps=8)
                except TypeError:
                    img = client.text_to_image(prompt, model=modelo, width=768,
                                               height=1152, num_inference_steps=8)
                _a_916(img).save(dest)
                ok += 1
                log.info(f"Escenario cloud {i+1}: {accion}")
                break
            except Exception as ex:
                log.warning(f"HF intento {intento+1} fallo: {str(ex)[:120]}")
                time.sleep(5 * (intento + 1))
        time.sleep(2)   # respeto al limite del tier gratis

    log.info(f"{ok} escenarios propios generados en la nube")
    return ok >= max(3, len(escenas) // 2)
