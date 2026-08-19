"""Doblaje de un video de cliente, de principio a fin.

    python -m src.doblaje.runner "input/cliente/video.mp4"
    python -m src.doblaje.runner video.mp4 --musica assets/music/energia-alta.mp3

Cada fase deja su resultado en disco y se salta si ya esta hecho, asi que se
puede parar y retomar. Un doblaje de 16 minutos son ~40 minutos de proceso;
perder eso por un corte de luz seria absurdo.

Lo que este modulo NO hace y hay que hacer a mano:
  - los textos de las tarjetas de titulo (hay que leerlas y traducirlas)
  - las franjas de datos (hay que decidir que cifras merecen grafico)
Son decisiones de contenido, no de proceso.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from src.doblaje import montaje, planos, transcribir, voz
from src.doblaje.adaptar import adaptar
from src.utils import get_duration

log = logging.getLogger("VideoFactory.Doblaje")


def _cargar(ruta):
    p = Path(ruta)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _guardar(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def doblar(video, salida="output/doblaje", musica=None, idioma_destino="es"):
    video = Path(video)
    if not video.exists():
        raise FileNotFoundError(video)
    O = Path(salida)
    O.mkdir(parents=True, exist_ok=True)
    duracion = get_duration(video)
    log.info(f"Doblando {video.name} ({duracion/60:.1f} min)")

    # 1. transcribir --------------------------------------------------------
    trans = _cargar(O / "transcripcion.json")
    if not trans:
        frases, idioma = transcribir.transcribir(video, destino=O / "transcripcion.json")
        trans = {"frases": frases, "idioma": idioma}
    log.info(f"1/6 transcrito: {len(trans['frases'])} frases ({trans['idioma']})")

    # 2. adaptar ------------------------------------------------------------
    datos = _cargar(O / "bloques.json")
    if not datos:
        bloques = transcribir.agrupar(trans["frases"])
        textos = adaptar([(g["ini"], g["fin"], g["ru"]) for g in bloques])
        for g, es in zip(bloques, textos):
            g["es"] = es or g["ru"]
        datos = {"bloques": bloques}
        _guardar(O / "bloques.json", datos)
    bloques = datos["bloques"]
    log.info(f"2/6 adaptado: {len(bloques)} bloques")

    # 3. voz ----------------------------------------------------------------
    voz.generar(bloques, O / "voz")
    voz.arreglar_solapes(bloques, O / "voz")
    _guardar(O / "bloques.json", {"bloques": bloques})
    voz.pista(bloques, O / "voz.wav", duracion)
    log.info("3/6 voz lista")

    # 4. planos -------------------------------------------------------------
    detectados = _cargar(O / "planos.json")
    if not detectados:
        carteles = planos.buscar_carteles(video, duracion, O / "_cards")
        lista = planos.detectar(video, duracion, O / "_scan",
                                destino=O / "planos.json", carteles=carteles)
        detectados = {"planos": lista, "carteles": carteles}
        _guardar(O / "planos.json", detectados)
    log.info(f"4/6 planos: {len(detectados['planos'])}")

    # 5. montaje ------------------------------------------------------------
    base = O / "camara.mp4"
    if not base.exists():
        base = montaje.camara(video, detectados["planos"], O / "planos")
    log.info("5/6 camara montada")

    # Las capas necesitan decisiones de contenido; si no hay graficos
    # preparados se sigue sin ellos antes que parar el proceso.
    gfx = O / "gfx"
    rotulos = gfx / "rotulos.png"
    franjas = json.loads((gfx / "franjas.json").read_text(encoding="utf-8")) \
        if (gfx / "franjas.json").exists() else []
    tarjetas = {int(p.stem[1:]): p for p in (gfx / "tarjetas").glob("t*.png")} \
        if (gfx / "tarjetas").exists() else {}

    if rotulos.exists():
        con_capas = montaje.capas(base, detectados["planos"], rotulos,
                                  [(gfx / f[0], f[1], f[2]) for f in franjas],
                                  tarjetas, O / "video_gfx.mp4", duracion)
    else:
        log.warning("Sin graficos preparados: se monta sin capas.")
        con_capas = base

    # 6. audio y union ------------------------------------------------------
    musica = musica or "assets/music/energia-alta.mp3"
    if Path(musica).exists():
        montaje.mezclar(O / "voz.wav", musica, O / "audio.wav", duracion)
        audio = O / "audio.wav"
    else:
        log.warning("Sin musica: se usa solo la voz.")
        audio = O / "voz.wav"

    final = montaje.unir(con_capas, audio, O / "FINAL.mp4",
                         revision=O / "FINAL_revision.mp4")
    log.info(f"6/6 LISTO: {final} ({get_duration(final):.0f}s)")
    return final


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ap = argparse.ArgumentParser(description="Dobla y edita un video de cliente")
    ap.add_argument("video")
    ap.add_argument("--salida", default="output/doblaje")
    ap.add_argument("--musica", default=None)
    a = ap.parse_args()
    try:
        doblar(a.video, a.salida, a.musica)
    except Exception as e:
        log.error(f"El doblaje se detuvo: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
