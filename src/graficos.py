"""Tarjetas graficas dibujadas por codigo, sin pasar por la IA.

Por que existe: los beats con cifra ("te cobran quince dolares", "veintinueve
por ciento de interes") no necesitan una escena generada. Una cifra gigante
bien puesta se entiende mejor que un personaje señalando algo, cuesta CERO en
API y ademas rompe el ritmo visual, que es lo que sostiene la retencion.

Cada tarjeta que se dibuja aqui es una imagen que no se le pide a kie.ai.

El aspecto sigue la misma paleta que el resto del canal para que no parezca
pegado de otro video.
"""
import logging
import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.cifras import CENTENAS, DECENAS, MULTIPLICADORES, UNIDADES, formatear

# Cualquier palabra que sea un numero escrito con letra: no puede acabar de
# etiqueta debajo de la cifra que ella misma forma.
_NUMERO_PALABRA = re.compile(
    "|".join(sorted((set(UNIDADES) | set(DECENAS) | set(CENTENAS)
                     | set(MULTIPLICADORES)), key=len, reverse=True)))

log = logging.getLogger("VideoFactory.Graficos")

W, H = 1080, 1920

FONDO = (7, 11, 18)
VERDE = (34, 227, 154)
ROJO = (255, 77, 109)
AMBAR = (255, 200, 87)
TEXTO = (242, 246, 255)
TENUE = (95, 113, 145)

# El color dice de que se habla antes de leer nada: verde lo que ganas o
# ahorras, rojo lo que se te va, ambar la advertencia.
COLOR_BEAT = {"punch": ROJO, "dato": VERDE, "hook": AMBAR, "cta": VERDE}

# Windows primero, Linux despues: el cron corre en ubuntu y alli no existe
# ninguna de las de Windows. Sin esto la nube caia a la fuente por defecto de
# PIL, que es un bitmap diminuto y arruinaba la tarjeta.
FUENTES = [
    "C:/Windows/Fonts/seguibl.ttf",      # Segoe UI Black
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _fuente(tam):
    for ruta in FUENTES:
        if Path(ruta).exists():
            try:
                return ImageFont.truetype(ruta, tam)
            except Exception:
                continue
    return ImageFont.load_default()


def _centrar(d, texto, fuente, y, color, w=W):
    caja = d.textbbox((0, 0), texto, font=fuente)
    d.text(((w - (caja[2] - caja[0])) / 2 - caja[0], y), texto,
           font=fuente, fill=color)
    return caja[3] - caja[1]


def _fondo():
    """Fondo oscuro con una rejilla tenue y un halo, para que no sea un
    rectangulo plano: en video un fondo liso se ve como un error de render."""
    img = Image.new("RGB", (W, H), FONDO)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 90):
        d.line([(x, 0), (x, H)], fill=(13, 19, 30), width=1)
    for y in range(0, H, 90):
        d.line([(0, y), (W, y)], fill=(13, 19, 30), width=1)

    halo = Image.new("RGB", (W, H), FONDO)
    ImageDraw.Draw(halo).ellipse([W // 2 - 460, H // 2 - 560,
                                  W // 2 + 460, H // 2 + 560], fill=(18, 30, 48))
    img = Image.blend(img, halo.filter(ImageFilter.GaussianBlur(150)), 0.55)
    return img


# ---------------------------------------------------------------- iconos
# Dibujados con primitivas: sin descargas, sin licencias y nitidos a
# cualquier tamaño. Cada uno se pinta dentro de un cuadrado de lado `s`.

def _icono_billete(d, x, y, s, color):
    d.rounded_rectangle([x, y + s * .22, x + s, y + s * .78], radius=s * .06,
                        outline=color, width=max(3, int(s * .05)))
    d.ellipse([x + s * .38, y + s * .38, x + s * .62, y + s * .62],
              outline=color, width=max(3, int(s * .05)))


def _icono_moneda(d, x, y, s, color):
    # El dolar va como glifo de la fuente y no con arcos: dibujado a mano
    # salia un ancla, porque los dos arcos enfrentados no leen como una S a
    # este tamaño.
    g = max(3, int(s * .06))
    d.ellipse([x + s * .08, y + s * .08, x + s * .92, y + s * .92],
              outline=color, width=g)
    f = _fuente(int(s * .62))
    caja = d.textbbox((0, 0), "$", font=f)
    d.text((x + (s - (caja[2] - caja[0])) / 2 - caja[0],
            y + (s - (caja[3] - caja[1])) / 2 - caja[1]), "$", font=f, fill=color)


def _icono_tarjeta(d, x, y, s, color):
    g = max(3, int(s * .05))
    d.rounded_rectangle([x, y + s * .25, x + s, y + s * .75], radius=s * .07,
                        outline=color, width=g)
    d.rectangle([x, y + s * .38, x + s, y + s * .48], fill=color)


def _icono_sobre(d, x, y, s, color):
    g = max(3, int(s * .05))
    d.rounded_rectangle([x, y + s * .25, x + s, y + s * .75], radius=s * .05,
                        outline=color, width=g)
    d.line([(x, y + s * .27), (x + s * .5, y + s * .55)], fill=color, width=g)
    d.line([(x + s, y + s * .27), (x + s * .5, y + s * .55)], fill=color, width=g)


def _icono_casa(d, x, y, s, color):
    g = max(3, int(s * .05))
    d.line([(x + s * .06, y + s * .5), (x + s * .5, y + s * .16)], fill=color, width=g)
    d.line([(x + s * .94, y + s * .5), (x + s * .5, y + s * .16)], fill=color, width=g)
    d.rectangle([x + s * .18, y + s * .5, x + s * .82, y + s * .84],
                outline=color, width=g)


def _icono_carro(d, x, y, s, color):
    g = max(3, int(s * .05))
    d.rounded_rectangle([x + s * .04, y + s * .46, x + s * .96, y + s * .68],
                        radius=s * .07, outline=color, width=g)
    d.arc([x + s * .22, y + s * .26, x + s * .78, y + s * .58], 180, 360,
          fill=color, width=g)
    for cx in (x + s * .28, x + s * .72):
        d.ellipse([cx - s * .1, y + s * .62, cx + s * .1, y + s * .82],
                  outline=color, width=g)


def _icono_reloj(d, x, y, s, color):
    g = max(3, int(s * .06))
    d.ellipse([x + s * .08, y + s * .08, x + s * .92, y + s * .92],
              outline=color, width=g)
    d.line([(x + s * .5, y + s * .5), (x + s * .5, y + s * .26)], fill=color, width=g)
    d.line([(x + s * .5, y + s * .5), (x + s * .68, y + s * .6)], fill=color, width=g)


def _icono_alerta(d, x, y, s, color):
    g = max(3, int(s * .06))
    d.polygon([(x + s * .5, y + s * .1), (x + s * .96, y + s * .88),
               (x + s * .04, y + s * .88)], outline=color, width=g)
    d.line([(x + s * .5, y + s * .38), (x + s * .5, y + s * .64)], fill=color, width=g)
    d.ellipse([x + s * .46, y + s * .7, x + s * .54, y + s * .78], fill=color)


ICONOS = {
    "billete": _icono_billete, "moneda": _icono_moneda, "tarjeta": _icono_tarjeta,
    "sobre": _icono_sobre, "casa": _icono_casa, "carro": _icono_carro,
    "reloj": _icono_reloj, "alerta": _icono_alerta,
}

# Que icono pide cada tema. Se mira la frase, no el beat: es lo unico que
# sabemos con certeza de que se esta hablando.
PISTAS = [
    (r"remesa|envi|mandar dinero|western|giro", "sobre"),
    (r"carro|auto|vehiculo|lote|llanta", "carro"),
    (r"renta|casa|apartamento|hipoteca|deposito|landlord", "casa"),
    (r"tarjeta|credito|puntaje|score|banco", "tarjeta"),
    (r"cheque|efectivo|cash|billete|sueldo|paga", "billete"),
    (r"año|mes|semana|tiempo|plazo|tarde", "reloj"),
    (r"estafa|trampa|cuidado|peligro|ojo|nunca", "alerta"),
]


def _icono_para(frase):
    f = frase.lower()
    for patron, nombre in PISTAS:
        if re.search(patron, f):
            return nombre
    return "moneda"


# ---------------------------------------------------------------- tarjetas

def _barra(d, y, pct, color, ancho=760):
    x0 = (W - ancho) // 2
    alto = 46
    d.rounded_rectangle([x0, y, x0 + ancho, y + alto], radius=alto // 2,
                        fill=(23, 33, 50))
    lleno = max(alto, int(ancho * min(100, max(0, pct)) / 100))
    d.rounded_rectangle([x0, y, x0 + lleno, y + alto], radius=alto // 2, fill=color)


def tarjeta(frase, info, beat="dato", destino=None):
    """Dibuja la tarjeta que ilustra una frase con cifra.

    Devuelve la ruta, o None si la frase no lleva cifra: en ese caso la escena
    se resuelve como siempre y no se fuerza un grafico sin nada que enseñar.
    """
    tipo = (info or {}).get("tipo", "texto")
    if tipo not in ("cifra", "porcentaje"):
        return None

    color = COLOR_BEAT.get(beat, VERDE)
    img = _fondo()
    d = ImageDraw.Draw(img)

    valor = info.get("valor", 0)
    unidad = info.get("unidad", "")
    texto = formatear(valor, unidad)

    # el icono arriba, como entrada visual
    s = 200
    ICONOS[_icono_para(frase)](d, (W - s) // 2, 470, s, color)

    # la cifra, tan grande como quepa: es el motivo de la tarjeta
    tam = 340 if len(texto) <= 3 else 280 if len(texto) <= 5 else 210
    fuente = _fuente(tam)
    while d.textbbox((0, 0), texto, font=fuente)[2] > W - 120 and tam > 90:
        tam -= 20
        fuente = _fuente(tam)
    _centrar(d, texto, fuente, 800, color)

    if tipo == "porcentaje":
        _barra(d, 1210, valor, color)

    # una palabra de contexto, corta, para que la cifra signifique algo
    clave = _contexto(frase, info.get("expresion", ""))
    if clave:
        _centrar(d, clave.upper(), _fuente(64), 1330 if tipo != "porcentaje" else 1310,
                 TENUE)

    destino = Path(destino) if destino else Path("output/images/grafico.png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


# Palabras que no aportan contexto: si la clave sale una de estas, mejor
# ninguna que una de relleno debajo de una cifra gigante.
VACIAS = {"para", "porque", "cuando", "sobre", "entre", "desde", "hasta",
          "entonces", "tambien", "también", "entrar", "sigue", "siendo",
          "termina", "cuesta", "cobran", "pagas", "tienes", "puedes",
          "llega", "queda", "estas", "estás", "entre"}


def _contexto(frase, expresion=""):
    """La palabra que da sentido a la cifra, para ponerla debajo.

    Excluye las palabras que FORMAN el propio numero. Sin esto salia
    "SETECIENTOS" bajo un 720 y "CIENTO" bajo un 8%: la etiqueta repetia la
    cifra en letra, o peor, la contradecia.
    """
    del_numero = {w.lower().strip(".,;:") for w in str(expresion).split()}
    del_numero |= {"ciento", "por", "mil", "millon", "millones"}

    for p in re.findall(r"[a-zA-ZñÑáéíóúÁÉÍÓÚ]{5,}", frase):
        bajo = p.lower()
        if bajo in VACIAS or bajo in del_numero:
            continue
        if _NUMERO_PALABRA.fullmatch(bajo):
            continue
        return p
    return ""


# ------------------------------------------------------- tarjeta animada
#
# La version estatica ya funcionaba, pero una cifra que APARECE y una cifra
# que CUENTA no producen el mismo efecto. En un canal donde el dato ES el
# contenido, verlo subir de 0 a 800 mientras la voz lo dice hace que se
# recuerde; verlo aparecer de golpe se lee y se olvida.
#
# Se genera fotograma a fotograma con PIL y se encodea. No hace falta un motor
# de animacion para esto: son tres valores interpolados.

def _suave(t):
    """Curva de salida: arranca rapido y frena al final.

    Lineal se ve mecanico, como un contador de gasolinera. Esta curva imita
    como se detiene algo con inercia, que es lo que el ojo espera.
    """
    return 1 - (1 - t) ** 3


def tarjeta_animada(frase, info, beat="dato", destino=None, segundos=2.6,
                    fps=25):
    """Version en movimiento de `tarjeta`. Devuelve la ruta del mp4 o None."""
    import subprocess
    import tempfile

    tipo = (info or {}).get("tipo", "texto")
    if tipo not in ("cifra", "porcentaje"):
        return None

    color = COLOR_BEAT.get(beat, VERDE)
    valor = info.get("valor", 0)
    unidad = info.get("unidad", "")
    clave = _contexto(frase, info.get("expresion", ""))
    icono = _icono_para(frase)
    fondo = _fondo()                      # se calcula una vez, no por fotograma

    n = max(2, int(segundos * fps))
    tmp = Path(tempfile.mkdtemp(prefix="tarjeta_"))
    for k in range(n):
        t = _suave(min(1.0, k / (n * 0.62)))     # la cuenta acaba antes del final
        img = fondo.copy()
        d = ImageDraw.Draw(img)

        # el icono entra creciendo en los primeros fotogramas
        s = int(200 * min(1.0, (k / max(1, n * 0.18)) ** 0.5))
        if s > 8:
            ICONOS[icono](d, (W - s) // 2, 470 + (200 - s) // 2, s, color)

        # la cifra sube hasta su valor
        actual = valor * t
        texto = formatear(int(round(actual)), unidad)
        tam = 340 if len(texto) <= 3 else 280 if len(texto) <= 5 else 210
        fuente = _fuente(tam)
        while d.textbbox((0, 0), texto, font=fuente)[2] > W - 120 and tam > 90:
            tam -= 20
            fuente = _fuente(tam)
        _centrar(d, texto, fuente, 800, color)

        if tipo == "porcentaje":
            _barra(d, 1210, valor * t, color)

        # la palabra de contexto entra despues, cuando la cifra ya casi esta
        if clave and k > n * 0.45:
            _centrar(d, clave.upper(), _fuente(64),
                     1330 if tipo != "porcentaje" else 1310, TENUE)

        img.save(tmp / f"f{k:04d}.png")

    destino = Path(destino) if destino else Path("output/images/tarjeta.mp4")
    destino.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(fps), "-i", str(tmp / "f%04d.png"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", str(destino)], capture_output=True, text=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    if r.returncode != 0:
        log.warning(f"No se pudo encodear la tarjeta animada: {r.stderr[-200:]}")
        return None
    return destino
