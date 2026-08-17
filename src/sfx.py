"""Efectos de sonido sintetizados con ffmpeg.

Por que sintetizados y no descargados: stock_media.py los pedia a
pixabay.com/api/audio/, que devuelve 403 porque esa API no existe. Nunca
hubo SFX en ningun video. Generandolos con ffmpeg funcionan igual en local
y en GitHub Actions, sin red, sin cuotas y sin licencias que revisar.

Se crean una sola vez y se reutilizan: si ya existen, no se regeneran.
"""
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("VideoFactory.SFX")

SFX_DIR = Path("assets/sfx")

# Cada efecto es una cadena de filtros de ffmpeg sobre generadores basicos.
# anoisesrc = ruido, sine = tono puro. El sobre de volumen hace el resto.
RECETAS = {
    # transicion: barrido de ruido filtrado, de agudo a grave
    "whoosh": (
        "anoisesrc=d=0.45:c=pink:r=48000:a=0.5,"
        "highpass=f=300,lowpass=f=6000,"
        "afade=t=in:st=0:d=0.12:curve=exp,"
        "afade=t=out:st=0.18:d=0.27:curve=exp,"
        "volume=0.55"
    ),
    # remate comico: dos tonos cortos ascendentes
    "pop": (
        "sine=frequency=520:duration=0.16:sample_rate=48000,"
        "afade=t=out:st=0.02:d=0.14:curve=exp,"
        "volume=0.42"
    ),
    # golpe: tono grave corto, para los punchlines fuertes
    "impacto": (
        "sine=frequency=80:duration=0.5:sample_rate=48000,"
        "afade=t=out:st=0.03:d=0.47:curve=exp,"
        "volume=0.75"
    ),
    # revelacion de dato: campanita
    "ding": (
        "sine=frequency=1180:duration=0.5:sample_rate=48000,"
        "afade=t=out:st=0.04:d=0.46:curve=exp,"
        "volume=0.30"
    ),
}


# Pico objetivo de cada efecto. Ajustar volumenes a mano no funciona: los
# filtros cambian la energia y salian a -20/-28 dB, inaudibles junto a una
# voz que pica a -1.7 dB. Se mide el resultado y se corrige.
PICO_OBJETIVO_DB = -8.0


def _pico_db(ruta_wav):
    r = subprocess.run(["ffmpeg", "-i", str(ruta_wav), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    for linea in r.stderr.splitlines():
        if "max_volume" in linea:
            try:
                return float(linea.split("max_volume:")[1].split("dB")[0])
            except ValueError:
                return None
    return None


def asegurar_sfx():
    """Crea los efectos que falten, normalizados. Devuelve cuantos hay."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    listos = 0
    for nombre, filtro in RECETAS.items():
        destino = SFX_DIR / f"{nombre}.wav"
        if destino.exists() and destino.stat().st_size > 1000:
            listos += 1
            continue

        crudo = SFX_DIR / f"_{nombre}_crudo.wav"
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", filtro,
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(crudo)],
            capture_output=True, text=True)
        if r.returncode != 0 or not crudo.exists():
            log.warning(f"No se pudo crear {nombre}: {r.stderr.strip()[-160:]}")
            crudo.unlink(missing_ok=True)
            continue

        pico = _pico_db(crudo)
        ganancia = 0.0 if pico is None else (PICO_OBJETIVO_DB - pico)
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", str(crudo), "-af", f"volume={ganancia:.2f}dB",
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(destino)],
            capture_output=True, text=True)
        crudo.unlink(missing_ok=True)

        if r.returncode == 0 and destino.exists() and destino.stat().st_size > 1000:
            listos += 1
            log.info(f"SFX creado: {nombre}.wav ({pico:.1f} dB -> {PICO_OBJETIVO_DB:.0f} dB)")
        else:
            log.warning(f"No se pudo normalizar {nombre}: {r.stderr.strip()[-160:]}")
    return listos


def ruta(nombre):
    p = SFX_DIR / f"{nombre}.wav"
    return p if p.exists() else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(asegurar_sfx(), "efectos listos en", SFX_DIR)
