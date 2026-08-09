"""Incrusta etiqueta visible 'Contenido generado con IA' (cumplimiento Meta)."""
import logging
from pathlib import Path
from PIL import Image, ImageDraw
from src.utils import load_config, run_cmd, load_font

log = logging.getLogger("VideoFactory.Disclosure")

FINAL_DIR = Path("output/final")
BADGE_PATH = FINAL_DIR / "badge_ia.png"


def add_disclosure():
    cfg = load_config().get("contenido", {})
    texto = cfg.get("disclosure_texto", "Contenido generado con IA")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    raw = FINAL_DIR / "video_raw.mp4"
    if not raw.exists():
        raise FileNotFoundError(f"No existe {raw}. Ejecuta el ensamblador primero.")

    _make_badge(texto, BADGE_PATH)
    final = FINAL_DIR / "video_final.mp4"

    cmd = ["ffmpeg", "-y",
           "-i", str(raw), "-i", str(BADGE_PATH),
           "-filter_complex", "[0:v][1:v]overlay=x=W-w-24:y=24[v]",
           "-map", "[v]", "-map", "0:a",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-c:a", "copy",
           str(final)]
    run_cmd(cmd, timeout=900)
    log.info(f"Etiqueta IA aplicada: {final}")
    return final


def _make_badge(texto, out):
    font = load_font(30)
    pad = 18
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), texto, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bw, bh = tw + pad * 2, th + pad * 2

    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2, fill=(0, 0, 0, 165))
    d.text((pad, pad - bbox[1]), texto, font=font, fill=(255, 255, 255, 255))
    img.save(out)
