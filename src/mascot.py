"""Mascota consistente (seed fijo) en 5 poses + fondo transparente.
Si el usuario sube sus propias imagenes a assets/mascot/, se usan esas."""
import io
import logging
import urllib.parse
import shutil
import requests
from pathlib import Path
from PIL import Image

log = logging.getLogger("VideoFactory.Mascot")
MASCOT_DIR = Path("output/media/mascot")
USER_DIR = Path("assets/mascot")

BASE_DESC = ("friendly cartoon mascot character, young latino man with black cap "
             "and green hoodie, flat 2D illustration style, simple clean shapes, "
             "full body, centered, white background")

POSES = {
    "talk": "talking with hand gesturing, mouth open",
    "point": "pointing up with one finger, excited face",
    "think": "hand on chin, thinking face",
    "explain": "both hands open explaining",
    "celebrate": "arms up celebrating, happy face",
}


def generar_mascotas():
    MASCOT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Prioridad: imagenes propias del usuario
    if USER_DIR.exists():
        for name in POSES:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                src = USER_DIR / f"{name}{ext}"
                if src.exists():
                    img = Image.open(src).convert("RGBA")
                    img = _remove_bg(img)
                    img.save(MASCOT_DIR / f"{name}.png")
                    log.info(f"Mascota propia cargada: {name}")

    # 2) Generar las que falten (seed fijo = mismo personaje)
    ok = 0
    for name, pose in POSES.items():
        dest = MASCOT_DIR / f"{name}.png"
        if dest.exists():
            ok += 1
            continue
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(f"{BASE_DESC}, {pose}")
        try:
            r = requests.get(url, params={"width": 768, "height": 1024,
                                          "seed": 777, "nologo": "true"}, timeout=180)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            img = _remove_bg(img)
            img.save(dest)
            ok += 1
            log.info(f"Mascota generada: {name}")
        except Exception as e:
            log.warning(f"Mascota {name} fallo: {e}")
    log.info(f"{ok}/{len(POSES)} poses de mascota listas")
    return ok


def _remove_bg(img):
    try:
        from rembg import remove
        return remove(img)
    except Exception as e:
        log.warning(f"rembg fallo ({e}); recorte simple de fondo blanco")
        data = img.convert("RGBA")
        px = data.load()
        w, h = data.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if r > 235 and g > 235 and b > 235:
                    px[x, y] = (r, g, b, 0)
        return data
