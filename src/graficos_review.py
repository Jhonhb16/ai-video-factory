"""Gráficos del clip: rótulos en español y tarjetas de especificaciones.

Los rótulos rusos van quemados sobre negro puro en la franja inferior, así que
se tapan con una barra propia y no se nota el parche. Se aprovecha para poner
algo mejor que un texto suelto: barra con acento de color por marca.

Las tarjetas de especificaciones aparecen sobre el televisor del que se habla,
en el momento en que la voz dice la cifra.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
D = Path("output/cliente/edicion/gfx")
D.mkdir(parents=True, exist_ok=True)

TCL = (0, 176, 255)          # azul frío
HIS = (255, 92, 61)          # naranja
BLANCO = (245, 248, 252)
TENUE = (150, 165, 185)
PANEL = (10, 14, 20)

FUENTES = ["C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/arialbd.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FINA = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _f(tam, fina=False):
    for r in (FINA if fina else FUENTES):
        if Path(r).exists():
            try:
                return ImageFont.truetype(r, tam)
            except Exception:
                pass
    return ImageFont.load_default()


def _texto(d, xy, txt, fuente, color, centro=False, derecha=False):
    """Dibuja texto. `derecha` alinea el BORDE DERECHO en x, que es lo que
    hace falta para que una cifra no se salga del panel."""
    caja = d.textbbox((0, 0), txt, font=fuente)
    ancho = caja[2] - caja[0]
    x, y = xy
    if centro:
        x -= ancho / 2
    elif derecha:
        x -= ancho
    d.text((x - caja[0], y - caja[1]), txt, font=fuente, fill=color)
    return ancho


def rotulos():
    """Barra inferior que tapa los rotulos rusos y pone los nuestros."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # La franja rusa vive entre y=885 y y=940. Se cubre de 872 a 1010 para
    # que quede holgado y el borde no coincida con el del texto tapado.
    y0, y1 = 872, 1010
    d.rectangle([0, y0, W, y1], fill=PANEL + (255,))

    for x_centro, nombre, marca, color in (
            (480, "TCL", "55 C7L", TCL),
            (1440, "HiSense", "55 U7S PRO", HIS)):
        # pastilla de acento
        d.rounded_rectangle([x_centro - 250, y0 + 34, x_centro - 236, y1 - 34],
                            radius=7, fill=color)
        _texto(d, (x_centro - 210, y0 + 34), nombre, _f(44), BLANCO)
        _texto(d, (x_centro - 210, y0 + 86), marca, _f(30, fina=True), TENUE)
    img.save(D / "rotulos.png")
    return D / "rotulos.png"


def _tarjeta(nombre, color, filas, archivo, lado="izq"):
    """Tarjeta de especificaciones sobre el televisor del que se habla."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    an, al = 560, 322
    x = 120 if lado == "izq" else W - 120 - an
    y = 150

    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([x + 8, y + 10, x + an + 8, y + al + 10],
                                             radius=24, fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(18)))
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([x, y, x + an, y + al], radius=24, fill=PANEL + (232,))
    d.rounded_rectangle([x, y, x + 10, y + al], radius=5, fill=color)
    _texto(d, (x + 40, y + 30), nombre, _f(46), BLANCO)

    yy = y + 110
    for etiqueta, valor in filas:
        _texto(d, (x + 40, yy + 14), etiqueta, _f(26, fina=True), TENUE)
        _texto(d, (x + an - 40, yy), valor, _f(50), color, derecha=True)
        yy += 68
    img.save(D / archivo)
    return D / archivo


def tarjeta_tcl():
    return _tarjeta("TCL 55 C7L", TCL,
                    [("Zonas de atenuación", "800"), ("Brillo", "2700 nits"),
                     ("Refresco", "144 Hz")], "spec_tcl.png", "izq")


def tarjeta_hisense():
    return _tarjeta("HiSense 55 U7S PRO", HIS,
                    [("Zonas de atenuación", "512"), ("Brillo", "2000 nits"),
                     ("Refresco", "165 Hz")], "spec_his.png", "der")


def comparativa_65():
    """Barras comparando las dos marcas en 65 pulgadas."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    an, al = 900, 330
    x, y = (W - an) // 2, 120

    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([x + 8, y + 10, x + an + 8, y + al + 10],
                                             radius=26, fill=(0, 0, 0, 175))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(20)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x, y, x + an, y + al], radius=26, fill=PANEL + (234,))
    _texto(d, (x + an // 2, y + 26), "ZONAS DE ATENUACIÓN · 65\"", _f(32),
           TENUE, centro=True)

    maxv = 1152
    for i, (nombre, valor, color) in enumerate(
            (("TCL", 1152, TCL), ("HiSense", 960, HIS))):
        yy = y + 108 + i * 96
        _texto(d, (x + 44, yy + 12), nombre, _f(38), BLANCO)
        bx0, bx1 = x + 250, x + an - 200
        d.rounded_rectangle([bx0, yy, bx1, yy + 54], radius=27, fill=(26, 34, 46, 255))
        ancho = int((bx1 - bx0) * valor / maxv)
        d.rounded_rectangle([bx0, yy, bx0 + ancho, yy + 54], radius=27, fill=color)
        _texto(d, (x + an - 44, yy + 6), str(valor), _f(46), color, derecha=True)
    img.save(D / "comp65.png")
    return D / "comp65.png"


if __name__ == "__main__":
    for f in (rotulos(), tarjeta_tcl(), tarjeta_hisense(), comparativa_65()):
        print("  ", f)
