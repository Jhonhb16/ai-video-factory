"""Deteccion de que hay en pantalla en cada momento.

Sin esto no se puede editar: hace falta saber cuando sale el presentador (para
hacerle punch-in) y cuando hay banda negra libre (para poner graficos). Ponerle
un grafico encima al presentador es el fallo mas visible que se puede cometer.

El metodo mide el brillo de una franja del cuadro. Es tosco pero funciona en
material de review, donde el plano de producto es oscuro y el del presentador
tiene su mesa iluminada. Calibrado sobre video real: comparativa ~0.12,
presentador ~0.35.

OJO con los carteles de titulo a pantalla completa: son blancos, asi que el
detector los toma por presentador y les aplicaria zoom. Un cartel es un
cartel: se marca aparte y no se le toca.
"""
import json
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("VideoFactory.Doblaje.Planos")

UMBRAL = 0.18
MIN_PLANO = 1.2
PASO = 0.5


def _muestrear(video, duracion, tmp, paso=PASO, recorte="crop=1920:120:0:890"):
    import numpy as np
    from PIL import Image

    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    muestras = []
    for i in range(int(duracion / paso)):
        t = i * paso
        f = tmp / f"s{i:05d}.png"
        if not f.exists():
            subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf", f"{recorte},scale=192:12",
                            str(f)], capture_output=True)
        if not f.exists():
            continue
        a = np.asarray(Image.open(f).convert("L"), dtype=float)
        muestras.append((t, float((a > 60).mean())))
        if i % 200 == 0:
            log.info(f"  {t:.0f}s de {duracion:.0f}s")
    return muestras


def detectar(video, duracion, tmp="output/cliente/_scan", destino=None,
             carteles=()):
    """Lista de {ini, fin, tipo} con tipo presentador|comparativa|cartel."""
    muestras = _muestrear(video, duracion, tmp)
    if not muestras:
        return []

    tramos, ini, estado = [], 0.0, None
    for t, v in muestras:
        e = "presentador" if v > UMBRAL else "comparativa"
        if estado is None:
            estado = e
        elif e != estado:
            tramos.append({"ini": ini, "fin": t, "tipo": estado})
            ini, estado = t, e
    tramos.append({"ini": ini, "fin": duracion, "tipo": estado})

    # fusionar los demasiado cortos: un plano de medio segundo se ve como un
    # fallo de montaje, no como una decision
    limpios = []
    for tr in tramos:
        if limpios and (tr["fin"] - tr["ini"] < MIN_PLANO
                        or limpios[-1]["tipo"] == tr["tipo"]):
            limpios[-1]["fin"] = tr["fin"]
        else:
            limpios.append(dict(tr))

    # los carteles se marcan aparte para que nadie les aplique zoom
    for p in limpios:
        if any(a < p["fin"] and b > p["ini"] for a, b in carteles):
            p["tipo"] = "cartel"

    pres = sum(p["fin"] - p["ini"] for p in limpios if p["tipo"] == "presentador")
    log.info(f"{len(limpios)} planos | presentador {pres:.0f}s de {duracion:.0f}s")
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(json.dumps({"planos": limpios},
                                            ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    return limpios


def buscar_carteles(video, duracion, tmp="output/cliente/_cards", paso=1.0):
    """Tramos con cartel de titulo a pantalla completa (fondo claro).

    Se distinguen del resto por el brillo medio del cuadro: el video de review
    es oscuro casi siempre y estas tarjetas son fondo blanco.
    """
    import numpy as np
    from PIL import Image

    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    claras = []
    for i in range(int(duracion / paso)):
        t = i * paso
        f = tmp / f"c{i:05d}.png"
        if not f.exists():
            subprocess.run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(video),
                            "-frames:v", "1", "-vf", "scale=64:36", str(f)],
                           capture_output=True)
        if not f.exists():
            continue
        if np.asarray(Image.open(f).convert("L"), dtype=float).mean() > 150:
            claras.append(t)

    tramos, ini, prev = [], None, None
    for t in claras:
        if ini is None:
            ini = t
        elif t - prev > 1.5:
            tramos.append((ini, prev + paso))
            ini = t
        prev = t
    if ini is not None:
        tramos.append((ini, prev + paso))
    log.info(f"{len(tramos)} carteles de titulo encontrados")
    return tramos
