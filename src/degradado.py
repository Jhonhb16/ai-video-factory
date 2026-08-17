"""Genera el degradado inferior de la maqueta B.

La imagen ocupa todo el cuadro y el texto se apoya sobre una caida a oscuro
en el tercio inferior. Se crea una sola vez y se reutiliza: hacerlo con
filtros de ffmpeg en cada segmento seria mas lento y menos controlable.
"""
import logging
from pathlib import Path

log = logging.getLogger("VideoFactory.Degradado")

RUTA = Path("assets/overlay/degradado.png")
W, H = 1080, 1920
INICIO = 0.58     # donde empieza a oscurecer
PLENO = 0.90      # donde alcanza su maximo
# Nunca opaco del todo: a 255 el tercio inferior se veia negro solido y
# parecia que la imagen se cortaba, en vez de fundirse. Con 232 el fondo
# sigue intuyendose detras del texto y el corte desaparece.
ALFA_MAX = 232
COLOR = (7, 11, 18)


def asegurar(alto_extra=0):
    """Devuelve la ruta del degradado, creandolo si no existe."""
    if RUTA.exists() and RUTA.stat().st_size > 1000:
        return RUTA
    try:
        from PIL import Image
        capa = Image.new("RGBA", (W, H), COLOR + (0,))
        pix = capa.load()
        y0, y1 = int(H * INICIO), int(H * PLENO)
        for y in range(H):
            if y < y0:
                a = 0
            elif y >= y1:
                a = ALFA_MAX
            else:
                t = (y - y0) / max(1, (y1 - y0))
                a = int(ALFA_MAX * (t * t))   # cuadratico: arranca suave
            if a:
                for x in range(W):
                    pix[x, y] = COLOR + (a,)
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        capa.save(RUTA)
        log.info(f"Degradado creado: {RUTA}")
        return RUTA
    except Exception as e:
        log.warning(f"No se pudo crear el degradado ({e})")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(asegurar())
