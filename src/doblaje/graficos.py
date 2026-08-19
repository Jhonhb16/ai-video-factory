"""Gráficos para el doblaje de reviews: acompañan la imagen, no la tapan.

Regla de oro de este encargo: el video COMPARA calidad de imagen, asi que
ningun grafico puede pisar los televisores. La primera version ponia tarjetas
flotando encima y tapaba justo lo que el espectador tiene que juzgar.

El material esta en buzon (letterbox): medido sobre el video real, hay 208 px
de banda negra arriba y unos 250 abajo. Todo se dibuja AHI, y las cifras se
colocan sobre el televisor al que pertenecen para que no haga falta explicar
cual es cual.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
BANDA_SUP = 208          # medido: el contenido empieza en y=208
BANDA_INF = 838          # y el televisor acaba por aqui
CENTRO_IZQ, CENTRO_DER = 480, 1440   # centro de cada televisor

TCL = (0, 176, 255)
HIS = (255, 92, 61)
BLANCO = (245, 248, 252)
TENUE = (150, 165, 185)
PANEL = (10, 14, 20)

FUERTE = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FINA = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _f(tam, fina=False):
    for r in (FINA if fina else FUERTE):
        if Path(r).exists():
            try:
                return ImageFont.truetype(r, tam)
            except Exception:
                pass
    return ImageFont.load_default()


def _txt(d, xy, s, fuente, color, centro=False, derecha=False):
    caja = d.textbbox((0, 0), s, font=fuente)
    an = caja[2] - caja[0]
    x, y = xy
    if centro:
        x -= an / 2
    elif derecha:
        x -= an
    d.text((x - caja[0], y - caja[1]), s, font=fuente, fill=color)
    return an


def _lienzo():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def rotulos(destino):
    """Barra inferior: tapa los rotulos rusos y pone los nuestros."""
    img = _lienzo()
    d = ImageDraw.Draw(img)
    y0, y1 = 866, 1006
    d.rectangle([0, y0, W, y1], fill=PANEL + (255,))
    for cx, nombre, modelo, color in ((CENTRO_IZQ, "TCL", "55 C7L", TCL),
                                      (CENTRO_DER, "HiSense", "55 U7S PRO", HIS)):
        d.rounded_rectangle([cx - 250, y0 + 32, cx - 237, y1 - 32], radius=7,
                            fill=color)
        _txt(d, (cx - 212, y0 + 32), nombre, _f(42), BLANCO)
        _txt(d, (cx - 212, y0 + 82), modelo, _f(28, fina=True), TENUE)
    img.save(destino)
    return destino


def franja(titulo, izq, der, destino, resalta=None):
    """Dato comparado en la BANDA SUPERIOR, cada cifra sobre su televisor.

    `resalta`: "izq" o "der" para marcar cual gana ese dato. Sin eso el
    espectador tiene que comparar mentalmente dos numeros; con eso lo ve.
    """
    img = _lienzo()
    d = ImageDraw.Draw(img)
    alto = 168
    y = (BANDA_SUP - alto) // 2

    sombra = _lienzo()
    ImageDraw.Draw(sombra).rounded_rectangle([60, y + 6, W - 60, y + alto + 6],
                                             radius=20, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, y, W - 60, y + alto], radius=20, fill=PANEL + (225,))

    _txt(d, (W // 2, y + 24), titulo.upper(), _f(28), TENUE, centro=True)
    d.line([(W // 2, y + 76), (W // 2, y + alto - 24)], fill=(40, 52, 68), width=2)

    for cx, valor, color, lado in ((CENTRO_IZQ, izq, TCL, "izq"),
                                   (CENTRO_DER, der, HIS, "der")):
        gana = resalta == lado
        _txt(d, (cx, y + 74), str(valor), _f(62 if gana else 54), color, centro=True)
        if gana:
            an = d.textlength(str(valor), font=_f(62))
            d.rounded_rectangle([cx - an / 2 - 16, y + 142, cx + an / 2 + 16, y + 148],
                                radius=3, fill=color)
    img.save(destino)
    return destino


def barras(titulo, izq, der, destino):
    """Comparativa con barras, tambien en la banda superior."""
    img = _lienzo()
    d = ImageDraw.Draw(img)
    alto = 176
    y = (BANDA_SUP - alto) // 2

    sombra = _lienzo()
    ImageDraw.Draw(sombra).rounded_rectangle([60, y + 6, W - 60, y + alto + 6],
                                             radius=20, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([60, y, W - 60, y + alto], radius=20, fill=PANEL + (225,))
    _txt(d, (W // 2, y + 18), titulo.upper(), _f(26), TENUE, centro=True)

    tope = max(izq, der) or 1
    bx0, bx1 = 360, W - 360
    for i, (nombre, valor, color) in enumerate((("TCL", izq, TCL),
                                                ("HiSense", der, HIS))):
        yy = y + 62 + i * 54
        _txt(d, (110, yy + 6), nombre, _f(30), BLANCO)
        d.rounded_rectangle([bx0, yy, bx1, yy + 36], radius=18, fill=(26, 34, 46, 255))
        an = int((bx1 - bx0) * valor / tope)
        d.rounded_rectangle([bx0, yy, bx0 + max(36, an), yy + 36], radius=18, fill=color)
        _txt(d, (W - 110, yy + 2), str(valor), _f(34), color, derecha=True)
    img.save(destino)
    return destino


if __name__ == "__main__":
    D = Path("output/cliente/edicion/gfx")
    D.mkdir(parents=True, exist_ok=True)
    rotulos(D / "rotulos.png")
    franja("Zonas de atenuación local", "800", "512", D / "f_zonas.png", "izq")
    franja("Brillo máximo", "2700 nits", "2000 nits", D / "f_brillo.png", "izq")
    franja("Frecuencia de refresco", "144 Hz", "165 Hz", D / "f_hz.png", "der")
    barras("Zonas de atenuación · 65 pulgadas", 1152, 960, D / "f_65.png")
    print("graficos en", D)
