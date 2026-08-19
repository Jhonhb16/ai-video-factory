"""Sustituye las tarjetas de titulo en ruso por su version en español.

El video trae 10 tarjetas de seccion a pantalla completa (fondo blanco con
adornos de colores y el titulo en gris con un sol amarillo detras). Dejarlas
en ruso arruina el doblaje: es lo primero que delata que el video es una
traduccion.

No se rehace la tarjeta entera: se tapa SOLO la caja del texto ruso y se
vuelve a dibujar encima, con los mismos colores y el mismo sol. Asi los
adornos de alrededor siguen siendo los suyos y la tarjeta no canta.

Colores medidos del original:
  fondo   (253, 253, 253)
  texto   ( 85,  81,  81)
  sol     (252, 227, 114)
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONDO = (253, 253, 253)
TEXTO = (85, 81, 81)
SOL = (252, 227, 114)

# banda donde vive el titulo, medida sobre el video
BANDA = (330, 700)

FUENTES = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

# segundo -> texto en español. El nombre del canal se queda como esta.
TARJETAS = {
    123: "PRECIO",
    176: "PANEL",
    262: "COLOR DE FÁBRICA",
    308: "BRILLO Y ESCENAS OSCURAS",
    430: "HDR",
    512: "ESCALADO Y PANTALLA MATE",
    605: "JUEGOS Y SONIDO",
    665: "SOFTWARE",
    759: "CONCLUSIÓN",
}


def _f(tam):
    for r in FUENTES:
        if Path(r).exists():
            try:
                return ImageFont.truetype(r, tam)
            except Exception:
                pass
    return ImageFont.load_default()


def _sol(d, cx, cy, radio, puntas=16):
    """El sol de rayos que llevan sus tarjetas detras del titulo."""
    pts = []
    for i in range(puntas * 2):
        ang = math.pi * i / puntas - math.pi / 2
        r = radio if i % 2 == 0 else radio * 0.76
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(pts, fill=SOL)


def generar(segundo, texto, destino, caja=None):
    """Capa que tapa el texto ruso y escribe el español encima.

    `caja` es (x0, y0, x1, y1) del texto ruso detectado en ese fotograma. Si
    no se da, se usa una caja centrada generosa.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    x0, y0, x1, y1 = caja or (300, 430, 1620, 610)
    # margen: el texto ruso tiene bordes suaves y sin holgura quedan restos
    d.rectangle([x0 - 40, y0 - 30, x1 + 40, y1 + 30], fill=FONDO + (255,))

    cy = (y0 + y1) // 2
    # el titulo se ajusta al ancho disponible en vez de usar tamaño fijo:
    # "BRILLO Y ESCENAS OSCURAS" y "HDR" no caben igual
    tam = 118
    fuente = _f(tam)
    limite = 1500
    while d.textbbox((0, 0), texto, font=fuente)[2] > limite and tam > 40:
        tam -= 4
        fuente = _f(tam)

    caja_txt = d.textbbox((0, 0), texto, font=fuente)
    an = caja_txt[2] - caja_txt[0]
    # el sol va detras del final del texto, como en el original
    _sol(d, W // 2 + an * 0.30, cy, max(96, an * 0.16))
    d.text((W // 2 - an / 2 - caja_txt[0], cy - (caja_txt[3] - caja_txt[1]) / 2
            - caja_txt[1]), texto, font=fuente, fill=TEXTO)

    img.save(destino)
    return destino


def caja_del_texto(imagen):
    """Encuentra el rectangulo del texto ruso en la banda del titulo."""
    import numpy as np
    a = np.asarray(Image.open(imagen).convert("RGB"), dtype=int)
    banda = a[BANDA[0]:BANDA[1]]
    oscuro = banda.sum(axis=2) < 350
    filas = np.where(oscuro.sum(axis=1) > 30)[0]
    if len(filas) == 0:
        return None
    sub = oscuro[filas.min():filas.max() + 1]
    cols = np.where(sub.sum(axis=0) > 1)[0]
    if len(cols) == 0:
        return None
    return (int(cols.min()), int(BANDA[0] + filas.min()),
            int(cols.max()), int(BANDA[0] + filas.max()))
