"""Utilidades compartidas."""
import os
import json
import subprocess
import logging
import yaml
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path("config/.env"))

log = logging.getLogger("VideoFactory.Utils")
CONFIG_PATH = Path("config/settings.yaml")


def today():
    return datetime.now().strftime("%Y%m%d")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def script_path():
    return Path(f"output/scripts/video_{today()}.json")


def load_script():
    p = script_path()
    if not p.exists():
        raise FileNotFoundError(f"No existe {p}. Ejecuta el paso de guion primero.")
    return json.loads(p.read_text(encoding="utf-8"))


def audio_path():
    return Path(f"output/audio/narration_{today()}.mp3")


def get_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"ffprobe fallo en {path}: {r.stderr[-300:]}")
    return float(r.stdout.strip())


def run_cmd(cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"Comando fallo: {' '.join(cmd[:4])}...\nSTDERR: {r.stderr[-900:]}")
    return r


def load_font(size):
    from PIL import ImageFont
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "assets/fonts/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def notify(msg, ok=True):
    import requests
    prefix = "OK" if ok else "ALERTA"
    log.info(f"{prefix}: {msg}")
    webhook = os.getenv("TELEGRAM_WEBHOOK_URL")
    if webhook:
        try:
            requests.post(webhook, json={"text": f"{prefix} VideoFactory: {msg}"}, timeout=10)
        except Exception:
            pass
