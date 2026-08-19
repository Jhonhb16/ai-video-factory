"""Escenas generadas con IA: protagonista fijo + secundarios nuevos cada video.

Decision de Mario (2026-08-17): el PROTAGONISTA se mantiene en todos los
videos y los SECUNDARIOS cambian en cada uno.

Es la combinacion que usan los formatos que aguantan años: MrBeast rota a los
concursantes pero nunca a Jimmy; una sitcom rota invitados y mantiene el
reparto. El protagonista es lo unico que alguien reconoce mientras desliza;
los secundarios dan la variedad que evita que todo se vea igual.

Flujo por video:
  1. El protagonista sale de una referencia fija (assets/personajes/protagonista).
  2. El LLM inventa 2-3 secundarios acordes al guion del dia.
  3. Cada frase se ilustra pasando la referencia del personaje que toca, asi
     se mantiene consistente dentro del video.
  4. Uno o dos momentos clave se animan como clip.
"""
import json
import logging
from pathlib import Path

from src import kie
from src.llm import chat_json
from src.utils import load_config

log = logging.getLogger("VideoFactory.EscenasIA")

SALIDA = Path("output/images")
ESTILO = ("3D animated movie style, stylized cartoon proportions, soft "
          "cinematic lighting, vertical composition, no text, no logos")

SYS_ELENCO = """Eres director de casting de un canal de finanzas en español latino.
El PROTAGONISTA ya existe y no se toca: joven latino con gorra negra hacia
atras y sudadera verde. Tu inventas solo los SECUNDARIOS de este video.
Cada secundario es un arquetipo reconocible de la vida cotidiana
latinoamericana relacionado con el tema: el casero, la cajera del banco, el
amigo que presume, la vecina, el jefe, el vendedor insistente.
Describelos en INGLES para generar su retrato con IA: edad, ropa, rasgos.
NO uses nombres de personas reales ni marcas.
Responde solo JSON:
{"elenco":[{"id":"casero","papel":"quien es en una frase",
            "descripcion":"english visual description"}]}"""

SYS_ESCENAS = """Eres director de arte de un canal de COMEDIA financiera.
Para cada frase describes UNA escena visual concreta en INGLES y dices que
personaje aparece.

Cada frase viene con su TIPO, y el tipo manda:

[punch] = ES UN CHISTE. La imagen tiene que ser graciosa POR SI SOLA, aunque
  se vea sin sonido. Aqui se exagera: escala absurda (una montaña de recibos
  hasta el techo), reaccion facial extrema, metafora literal (el personaje
  literalmente ahogandose en billetes), objeto fuera de lugar. Si la escena de
  un punch podria ilustrar tambien una frase seria, esta MAL: no es un chiste,
  es una ilustracion.
[dato] = una cifra. Escena sobria y limpia, que la cifra es la protagonista.
[normal] = escena cotidiana concreta, sin exagerar.

Reglas comunes: realidad latinoamericana, concreta y visual (nada abstracto),
una sola accion clara. NO describas al personaje (viene por referencia), solo
que hace y donde. El protagonista aparece en la mayoria de las frases.

Ejemplos de la diferencia, misma idea:
  frase [normal] "pagas la renta cada mes"
     -> "handing cash to a landlord at an apartment door"
  frase [punch] "tu renta se lleva medio sueldo"
     -> "tiny person carrying a giant house on his back, bending under the
         weight, neighbors watching from a balcony"

Responde solo JSON:
{"escenas":[{"i":0,"personaje":"id del elenco","escena":"english scene"}]}"""


PROTAGONISTA_DIR = Path("assets/personajes/protagonista")


def _cfg():
    c = load_config().get("elenco", {}) or {}
    return {
        "activado": bool(c.get("activado", True)),
        "secundarios": int(c.get("secundarios", 2)),
        "clips": int(c.get("clips_por_video", 2)),
        "resolucion_clip": c.get("resolucion_clip", "480p"),
        "max_creditos": int(c.get("max_creditos_por_video", 250)),
    }


def _ref_protagonista():
    """URL publica permanente del protagonista. Se sube una sola vez."""
    guardada = PROTAGONISTA_DIR / "referencia_url.txt"
    if guardada.exists():
        url = guardada.read_text(encoding="utf-8").strip()
        if url.startswith("http"):
            return url
    local = PROTAGONISTA_DIR / "referencia.png"
    if not local.exists():
        return None
    url = kie.subir_publico(local, "ref/protagonista.png")
    if url:
        guardada.write_text(url, encoding="utf-8")
    return url


def disponible():
    return _cfg()["activado"] and kie.disponible()


def _lista_de(respuesta, clave):
    """El LLM devuelve unas veces {"clave":[...]} y otras la lista pelada.

    Costo una corrida entera: reventaba con 'list object has no attribute get'
    y el video salio con 25 escenas identicas de relleno.
    """
    if isinstance(respuesta, list):
        return respuesta
    if isinstance(respuesta, dict):
        if isinstance(respuesta.get(clave), list):
            return respuesta[clave]
        # a veces envuelve la lista con otro nombre
        for v in respuesta.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def _inventar_elenco(guion, n):
    texto = guion.get("hook", "") + "\n" + "\n".join(
        b["t"] for b in (guion.get("beats") or [])[:12])
    try:
        r = chat_json(SYS_ELENCO,
                      f"TEMA: {guion.get('titulo','')}\nGUION:\n{texto}\n\n"
                      f"Inventa exactamente {n} secundarios.",
                      temperature=0.9, max_tokens=1500)
        elenco = [e for e in _lista_de(r, "elenco")
                  if isinstance(e, dict) and e.get("descripcion")][:n]
        return elenco or None
    except Exception as e:
        log.warning(f"No se pudo inventar el elenco ({str(e)[:100]})")
        return None


def _retratos(elenco, fecha):
    """Genera y publica el retrato de referencia de cada personaje."""
    refs = {}
    for i, p in enumerate(elenco):
        prompt = (f"full body portrait of {p['descripcion']}, standing, neutral "
                  f"pose, plain light background, {ESTILO}")
        ruta = kie.generar_imagen(prompt, proporcion="9:16",
                                  nombre=f"ref_{fecha}_{i}")
        if not ruta:
            continue
        url = kie.subir_publico(ruta, f"ref/{fecha}/{p.get('id', i)}.png")
        if url:
            refs[p.get("id", str(i))] = url
            log.info(f"Personaje listo: {p.get('id')} — {p.get('papel','')[:50]}")
    return refs


def _plan_escenas(guion, items, elenco):
    ids = [p.get("id", str(i)) for i, p in enumerate(elenco)]
    # El TIPO de cada frase viaja con ella: sin eso el director de arte no
    # sabe cuales son los chistes y los ilustra igual que el resto, asi que el
    # remate se oye pero no se ve.
    lista = "\n".join(f'{i} [{it.get("k", "normal")}]: {it["txt"]}'
                      for i, it in enumerate(items))
    fichas = "\n".join(f'- {p.get("id")}: {p.get("papel","")}' for p in elenco)
    try:
        r = chat_json(SYS_ESCENAS,
                      f"ELENCO:\n{fichas}\n\nFRASES:\n{lista}",
                      temperature=0.7, max_tokens=4000)
        plan = {e["i"]: e for e in _lista_de(r, "escenas")
                if isinstance(e, dict) and "i" in e}
    except Exception as e:
        log.warning(f"No se pudo planificar escenas ({str(e)[:100]})")
        plan = {}
    # relleno por si el LLM se deja alguna
    for i in range(len(items)):
        if i not in plan:
            plan[i] = {"i": i, "personaje": ids[0],
                       "escena": "person at home looking at money worried"}
        if plan[i].get("personaje") not in ids:
            plan[i]["personaje"] = ids[0]
    return plan


# Cuantos planos como mucho pueden ser tarjeta. Sin tope, un guion cargado de
# datos saldria medio video de graficos y perderia al personaje, que es lo que
# da +23% de retencion frente a las imagenes sueltas.
MAX_TARJETAS = 5


def _tarjeta_de_cifra(item, indice, contador=[0]):
    """Dibuja la tarjeta del beat si trae cifra. Devuelve la ruta o None."""
    if indice == 1:
        contador[0] = 0                       # video nuevo, cuenta a cero
    if contador[0] >= MAX_TARJETAS:
        return None
    try:
        from src.cifras import analizar
        from src.graficos import tarjeta
        info = analizar(item.get("txt") or item.get("t") or "")
        if info.get("tipo") not in ("cifra", "porcentaje"):
            return None
        # una cifra de 0 o 1 no merece pantalla completa
        if info.get("valor", 0) < 2:
            return None
        frase = item.get("txt") or item.get("t") or ""
        beat = item.get("k", "dato")
        png = SALIDA / f"img_{indice:03d}.png"
        ruta = tarjeta(frase, info, beat, destino=png)
        if not ruta:
            return None
        contador[0] += 1
        # Ademas de la imagen (que sirve de respaldo y de conteo) se genera la
        # version animada: una cifra que sube de 0 a su valor mientras la voz
        # la dice se recuerda; una que aparece de golpe se lee y se olvida.
        try:
            from src.graficos import tarjeta_animada
            dur = float(item.get("end", 0)) - float(item.get("start", 0))
            tarjeta_animada(frase, info, beat, destino=png.with_suffix(".mp4"),
                            segundos=max(1.6, min(4.0, dur or 2.6)))
        except Exception as e:
            log.warning(f"Tarjeta {indice} sin animar ({str(e)[:70]})")
        return ruta
    except Exception as e:
        log.warning(f"No se pudo dibujar la tarjeta del plano {indice} ({e})")
        return None


def generar_escenas_ia(guion, items, fecha):
    """Crea output/images/img_XXX.png con elenco nuevo. Devuelve cuantas hizo."""
    if not disponible():
        return 0
    cfg = _cfg()

    saldo = kie.creditos()
    if saldo is not None:
        log.info(f"Creditos kie disponibles: {saldo:.0f}")
        if saldo < 60:
            log.warning("Creditos insuficientes; se usan los escenarios locales.")
            return 0

    url_prota = _ref_protagonista()
    if not url_prota:
        log.warning("Sin referencia del protagonista; se usan escenarios locales.")
        return 0

    secundarios = _inventar_elenco(guion, cfg["secundarios"]) or []
    log.info("Secundarios de hoy: " + (", ".join(
        f"{p.get('id')} ({p.get('papel','')[:32]})" for p in secundarios) or "ninguno"))

    # el protagonista NO se regenera: es la cara fija del canal
    refs = {"protagonista": url_prota}
    refs.update(_retratos(secundarios, fecha))
    elenco = [{"id": "protagonista", "papel": "el protagonista del canal"}] + secundarios

    plan = _plan_escenas(guion, items, elenco)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo in SALIDA.glob("img_*.png"):
        viejo.unlink()

    # los momentos que merecen clip: los punch mas separados entre si
    candidatos = [i for i, it in enumerate(items) if it.get("k") in ("punch", "hook")]
    con_clip = set(candidatos[:: max(1, len(candidatos) // max(1, cfg["clips"]))][:cfg["clips"]])

    hechas = 0
    clips = {}
    graficas = 0
    for i, it in enumerate(items):
        # Los beats con cifra se resuelven con una tarjeta dibujada por
        # codigo: cuesta CERO, la cifra se lee mejor que en una escena, y
        # corta el ritmo visual. Cada una es una imagen que no se paga.
        tarjeta = _tarjeta_de_cifra(it, hechas + 1)
        if tarjeta:
            hechas += 1
            graficas += 1
            continue

        p = plan[i]
        ref = refs.get(p["personaje"]) or next(iter(refs.values()))
        prompt = (f"the same character from the reference image, {p['escena']}, {ESTILO}")
        ruta = kie.generar_imagen(prompt, referencia=ref,
                                  nombre=f"esc_{fecha}_{i:03d}")
        if not ruta:
            continue
        destino = SALIDA / f"img_{hechas+1:03d}.png"
        destino.write_bytes(ruta.read_bytes())
        hechas += 1

        if i in con_clip:
            url = kie.subir_publico(ruta, f"ref/{fecha}/plano_{i:03d}.png")
            if url:
                clip = kie.generar_clip(
                    f"{p['escena']}, subtle natural movement, static camera",
                    url, segundos=4, resolucion=cfg["resolucion_clip"],
                    nombre=f"clip_{fecha}_{i:03d}")
                if clip:
                    clips[hechas] = clip

    if clips:
        destino_clips = Path("output/media/clips_ia")
        destino_clips.mkdir(parents=True, exist_ok=True)
        for idx, ruta in clips.items():
            (destino_clips / f"clip_{idx:03d}.mp4").write_bytes(ruta.read_bytes())
        log.info(f"{len(clips)} clips animados generados")

    # el gasto puede salir negativo si se recargan creditos a mitad de la
    # corrida; en ese caso no se informa en vez de mostrar un numero absurdo
    gastado = (saldo - (kie.creditos() or saldo)) if saldo else 0
    coste = f", ~{gastado:.0f} creditos = ${gastado*0.005:.2f}" if gastado > 0 else ""
    ahorro = (f", {graficas} tarjetas dibujadas por codigo "
              f"(~${graficas*4*0.005:.2f} no gastados)") if graficas else ""
    log.info(f"{hechas} escenas con elenco nuevo "
             f"({len(refs)} personajes, {len(clips)} clips{coste}{ahorro})")
    return hechas
