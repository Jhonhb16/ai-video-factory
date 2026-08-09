"""Monitor de salud y costos. Envía reporte a Telegram."""
import csv
import os
import time
from pathlib import Path
from datetime import datetime
from src.utils import notify

COSTO_POR_VIDEO = {"llm": 0.10, "voz": 0.30, "imagenes": 0.10, "apify": 0.05}


def leer_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resumen():
    pub = leer_csv("output/published_log.csv")
    scores = leer_csv("output/intelligence/scores_log.csv")
    hoy = datetime.now()
    mes = hoy.strftime("%Y%m")

    pub_mes = [r for r in pub if r.get("fecha", "").startswith(mes)]
    costo_mes = len(pub_mes) * sum(COSTO_POR_VIDEO.values())

    vals = []
    for r in scores:
        try:
            vals.append(float(r.get("score_simulado", "")))
        except ValueError:
            pass
    avg = sum(vals) / len(vals) if vals else 0

    lineas = [
        f"Videos publicados este mes: {len(pub_mes)}",
        f"Costo estimado del mes: ${costo_mes:.2f} USD",
        f"Score simulador promedio: {avg:.1f}/100",
        f"Total historico publicado: {len(pub)}",
    ]

    total = sum(p.stat().st_size for p in Path("output").rglob("*") if p.is_file())
    lineas.append(f"Uso de disco output/: {total/1e6:.1f} MB")
    lineas.append(_check_token())

    reporte = "\n".join(lineas)
    print(reporte)
    notify("Reporte semanal VideoFactory\n" + reporte, ok=True)


def _check_token():
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        return "META_ACCESS_TOKEN no configurado (publicacion pendiente)"
    import requests
    ver = os.getenv("META_GRAPH_VERSION", "v23.0")
    try:
        r = requests.get(f"https://graph.facebook.com/{ver}/debug_token",
                         params={"input_token": token, "access_token": token}, timeout=15)
        d = r.json().get("data", {})
        exp = d.get("expires_at")
        if exp:
            dias = (exp - time.time()) / 86400
            return f"Token Meta expira en {dias:.0f} dias"
        return "Token Meta sin expiracion"
    except Exception as e:
        return f"No se pudo verificar token: {e}"


if __name__ == "__main__":
    resumen()
