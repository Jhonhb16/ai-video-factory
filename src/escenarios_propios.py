"""Escenas propias: personajes del canal compuestos sobre escenarios propios.

Sustituye al b-roll de stock. No necesita GPU ni red: solo compone imagenes
que ya estan en el repo, asi que funciona igual en local y en GitHub Actions.

Idea clave: como cada plano es una imagen fija, NO hay parpadeo. El
movimiento lo pone despues el ensamblador con el zoom lento.
"""
import json
import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

log = logging.getLogger("VideoFactory.EscenariosPropios")

PERSONAJES_DIR = Path("assets/personajes")
ESCENARIOS_DIR = Path("assets/escenarios")
SALIDA = Path("output/images")
W, H = 1080, 1920

# Encuadre segun el tipo de beat. Es lenguaje de cine: el primer plano se
# reserva para el golpe comico, que es donde debe ir la atencion.
ENCUADRE_POR_BEAT = {
    "hook":   "medio",
    "normal": "general",
    "dato":   "medio",
    "punch":  "rostro",
    "cta":    "general",
}

# Quien protagoniza cada tipo de beat. Mario es el protagonista y debe
# dominar; Cata da los datos pero NO puede acaparar el video (con
# ["cata"] a secas salia en 11 de 24 planos, porque hay muchos beats dato).
REPARTO = {
    "hook":   ["mario"],
    "normal": ["mario", "gaston", "mario", "tio-negocio", "mario", "dona-fanny"],
    "dato":   ["cata", "mario", "cata", "gaston"],
    "punch":  ["dona-fanny", "gaston", "tio-negocio", "mario", "cata"],
    "cta":    ["mario"],
}

ALTURA_RELATIVA = {"general": 0.62, "medio": 0.95, "rostro": 0.80}


def _cargar_meta():
    ruta = ESCENARIOS_DIR / "escenarios.json"
    if not ruta.exists():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return {k: v for k, v in datos.items() if not k.startswith("_")}
    except Exception as e:
        log.warning(f"escenarios.json ilegible ({e}); se usan valores por defecto.")
        return {}


def disponible():
    """Hay material suficiente para componer escenas propias?"""
    if not PERSONAJES_DIR.exists() or not ESCENARIOS_DIR.exists():
        return False
    cuerpos = list(PERSONAJES_DIR.glob("*/cuerpo.png"))
    fondos = list(ESCENARIOS_DIR.glob("*.png"))
    return len(cuerpos) >= 1 and len(fondos) >= 1


def _personaje(slug, encuadre):
    """Devuelve el PNG con alfa del personaje segun el encuadre pedido."""
    base = PERSONAJES_DIR / slug
    archivo = "rostro.png" if encuadre == "rostro" else "cuerpo.png"
    ruta = base / archivo
    if not ruta.exists():
        ruta = base / "cuerpo.png"
    if not ruta.exists():
        return None
    img = Image.open(ruta).convert("RGBA")

    if encuadre == "medio" and archivo == "cuerpo.png":
        # recorte a medio cuerpo: nos quedamos con el 58% superior
        img = img.crop((0, 0, img.width, int(img.height * 0.58)))
    return img


def _componer(fondo_path, per, meta, x_rel, encuadre, espejo):
    fondo = Image.open(fondo_path).convert("RGBA")
    if fondo.size != (W, H):
        fondo = fondo.resize((W, H), Image.LANCZOS)

    if espejo:
        per = per.transpose(Image.FLIP_LEFT_RIGHT)

    alto = int(H * ALTURA_RELATIVA[encuadre])
    ancho = max(1, int(per.width * alto / per.height))
    if ancho > W * 1.15:                       # no desbordar de lado
        ancho = int(W * 1.15)
        alto = max(1, int(per.height * ancho / per.width))
    per = per.resize((ancho, alto), Image.LANCZOS)

    suelo = float(meta.get("suelo", 0.90))
    pies_y = int(H * suelo)
    x = int(W * x_rel - ancho / 2)
    x = max(-int(ancho * 0.12), min(x, W - int(ancho * 0.88)))
    y = pies_y - alto

    lienzo = fondo
    # La sombra de contacto solo tiene sentido si se ven los pies.
    if encuadre == "general":
        sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(sombra)
        sw, sh = int(ancho * 0.70), max(6, int(alto * 0.045))
        d.ellipse([x + (ancho - sw) / 2, pies_y - sh / 2,
                   x + (ancho + sw) / 2, pies_y + sh / 2], fill=(0, 0, 0, 105))
        lienzo = Image.alpha_composite(fondo, sombra.filter(ImageFilter.GaussianBlur(20)))

    lienzo = lienzo.copy()
    lienzo.alpha_composite(per, (x, y))
    return lienzo.convert("RGB")


def generar_escenas(guion, n_planos=None, semilla=None):
    """Crea output/images/img_XXX.png, una por plano. Devuelve cuantas hizo."""
    if not disponible():
        log.info("Sin personajes o escenarios propios; se usara el sistema anterior.")
        return 0

    rnd = random.Random(semilla if semilla is not None else 777)
    meta_todos = _cargar_meta()
    fondos = sorted(p for p in ESCENARIOS_DIR.glob("*.png"))
    # slug = nombre de la carpeta que contiene cuerpo.png
    disponibles = {p.parent.name for p in PERSONAJES_DIR.glob("*/cuerpo.png")}
    if not disponibles:
        log.warning("No hay ningun personaje con cuerpo.png.")
        return 0

    # secuencia de beats: hook + beats + cta
    secuencia = []
    if guion.get("hook"):
        secuencia.append("hook")
    for b in (guion.get("beats") or []):
        k = b.get("k", "normal") if isinstance(b, dict) else "normal"
        secuencia.append(k if k in ENCUADRE_POR_BEAT else "normal")
    if guion.get("cta"):
        secuencia.append("cta")
    if not secuencia:
        secuencia = ["normal"] * 12
    if n_planos:
        secuencia = secuencia[:n_planos]

    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA.glob("img_*.png"):
        viejo.unlink()

    ultimo_fondo = None
    ultimo_pers = None
    hechas = 0
    turno = {}          # rotacion propia por tipo de beat, no por indice global

    for i, tipo in enumerate(secuencia):
        encuadre = ENCUADRE_POR_BEAT.get(tipo, "general")

        # personaje: rota dentro del tipo y evita repetir el del plano anterior
        candidatos = [s for s in REPARTO.get(tipo, ["mario"]) if s in disponibles] or ["mario"]
        opciones = [s for s in candidatos if s != ultimo_pers] or candidatos
        turno[tipo] = turno.get(tipo, 0)
        slug = opciones[turno[tipo] % len(opciones)]
        turno[tipo] += 1

        # fondo: nunca dos iguales seguidos, y respetando el encuadre.
        # Los fondos con mueble en primer plano (cocina) no admiten cuerpo
        # entero: el personaje acaba de pie sobre la mesa.
        libres = [f for f in fondos if f != ultimo_fondo] or fondos
        if encuadre == "general":
            aptos = [f for f in libres
                     if not meta_todos.get(f.name, {}).get("solo_cerca")]
            libres = aptos or libres
        fondo = libres[(i * 3 + 1) % len(libres)]

        per = _personaje(slug, encuadre)
        if per is None:
            continue

        meta = meta_todos.get(fondo.name, {})
        zona = meta.get("zona", [0.30, 0.70])
        x_rel = zona[0] + (zona[1] - zona[0]) * ((i % 3) / 2.0)
        espejo = (i % 4 == 3)

        try:
            img = _componer(fondo, per, meta, x_rel, encuadre, espejo)
        except Exception as e:
            log.warning(f"Plano {i+1} fallo ({e}); se salta.")
            continue

        img.save(SALIDA / f"img_{hechas+1:03d}.png")
        hechas += 1
        ultimo_fondo, ultimo_pers = fondo, slug

    log.info(f"{hechas} escenas propias compuestas "
             f"({len(set(f.name for f in fondos))} escenarios, {len(disponibles)} personajes)")
    return hechas
