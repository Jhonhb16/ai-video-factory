"""Imagenes: Replicate -> Pollinations (gratis) -> tarjetas locales."""
import os
import hashlib
import random
import logging
import urllib.parse
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFilter
from src.utils import load_script, load_font

log = logging.getLogger("VideoFactory.Images")

IMG_DIR = Path("output/images")
CACHE_DIR = IMG_DIR / "cache"
SDXL_MODEL = "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b"
GEN_W, GEN_H = 576, 1024
PROC_W, PROC_H = 1620, 2880

NEGATIVE = "text, words, letters, watermark, logo, signature, blurry, low quality, distorted, deformed"
STYLE = "cinematic financial theme, professional, clean, high detail, vertical composition, no text"


def generate_images(data=None):
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for old in IMG_DIR.glob("img_*.png"):
        old.unlink()

    script = data.get("guion") if isinstance(data, dict) and "guion" in data else load_script()
    escenas = script.get("escenas", [])
    prompts = [e.get("prompt_imagen", "").strip() for e in escenas if e.get("prompt_imagen")]
    if not prompts:
        prompts = [_generic_prompt(i) for i in range(10)]
    prompts = prompts[:30]

    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda ip: _generate_one(ip[0], ip[1]), enumerate(prompts)))

    paths = []
    for i, prompt in enumerate(prompts):
        dest = IMG_DIR / f"img_{i+1:03d}.png"
        if not dest.exists():
            _fallback_image(prompt, dest)
        paths.append(dest)
    log.info(f"{len(paths)} imagenes listas")
    return paths


def _generate_one(i, prompt):
    dest = IMG_DIR / f"img_{i+1:03d}.png"
    h = hashlib.md5(prompt.encode()).hexdigest()
    cached = CACHE_DIR / f"{h}.png"

    if not cached.exists():
        ok = False
        if os.getenv("REPLICATE_API_TOKEN"):
            ok = _gen_replicate(prompt, cached)
        if not ok:
            ok = _gen_pollinations(prompt, cached)
        if not ok:
            return False

    try:
        img = Image.open(cached).convert("RGB")
        img = _crop_916(img).resize((PROC_W, PROC_H), Image.LANCZOS)
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
        img.save(dest)
        return True
    except Exception as e:
        log.warning(f"Post-proceso imagen {i+1} fallo: {e}")
        return False


def _gen_replicate(prompt, cached):
    try:
        import replicate
        output = replicate.run(SDXL_MODEL, input={
            "prompt": f"{prompt}, {STYLE}",
            "negative_prompt": NEGATIVE,
            "width": GEN_W, "height": GEN_H,
            "num_outputs": 1, "num_inference_steps": 25,
            "guidance_scale": 7.5, "scheduler": "K_EULER",
        })
        url = output[0] if isinstance(output, (list, tuple)) else str(output)
        r = requests.get(url, timeout=90)
        r.raise_for_status()
        cached.write_bytes(r.content)
        return True
    except Exception as e:
        log.warning(f"Replicate fallo: {e}")
        return False


def _gen_pollinations(prompt, cached):
    try:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(f"{prompt}, {STYLE}")
        r = requests.get(url, params={
            "width": GEN_W, "height": GEN_H, "nologo": "true",
            "seed": random.randint(1, 999999),
        }, timeout=180)
        r.raise_for_status()
        if len(r.content) < 1000:
            raise RuntimeError("respuesta vacia")
        cached.write_bytes(r.content)
        return True
    except Exception as e:
        log.warning(f"Pollinations fallo: {e}")
        return False


def _crop_916(img):
    w, h = img.size
    target = 9 / 16
    if w / h > target:
        nw = int(h * target); left = (w - nw) // 2
        return img.crop((left, 0, left + nw, h))
    elif w / h < target:
        nh = int(w / target); top = (h - nh) // 2
        return img.crop((0, top, w, top + nh))
    return img


def _generic_prompt(i):
    temas = ["monedas y calculadora sobre escritorio", "grafico financiero ascendente",
             "alcancia y billetes", "persona revisando presupuesto en laptop",
             "crecimiento de planta sobre monedas"]
    return temas[i % len(temas)]


def _fallback_image(prompt, out):
    img = Image.new("RGB", (PROC_W, PROC_H))
    d = ImageDraw.Draw(img)
    for y in range(0, PROC_H, 4):
        t = y / PROC_H
        d.rectangle([0, y, PROC_W, y + 4],
                    fill=(int(12 + 20 * t), int(18 + 34 * t), int(45 + 70 * t)))
    font = load_font(64)
    kw = " ".join(prompt.split()[:6])
    bbox = d.textbbox((0, 0), kw, font=font)
    tw = bbox[2] - bbox[0]
    d.text(((PROC_W - tw) // 2, PROC_H // 2), kw, font=font, fill=(255, 255, 255))
    img.save(out)
