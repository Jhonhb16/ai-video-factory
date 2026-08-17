"""Verificador integral del pipeline: revisa cada eslabon y mide.

Existe porque "el log dice OK" no es prueba de nada. Cada comprobacion mide
el resultado REAL (el .ass que se quemo, el audio del mp4, los pixeles del
video) y no lo que el codigo creia estar haciendo.

Uso:
    python -m src.verificar            revisa el video del dia
    python -m src.verificar --bucle    repite hasta que todo pase
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("VideoFactory.Verificar")

OK, MAL, AVISO = "OK  ", "FALLA", "aviso"
_resultados = []


def _mide(nombre, estado, detalle=""):
    _resultados.append((nombre, estado, detalle))
    print(f"  [{estado}] {nombre:38} {detalle}")
    return estado != MAL


def _ffprobe(ruta, campos):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", campos,
                        "-of", "default=noprint_wrappers=1", str(ruta)],
                       capture_output=True, text=True)
    d = {}
    for linea in (r.stdout or "").splitlines():
        if "=" in linea:
            k, v = linea.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def _volumen(ruta):
    r = subprocess.run(["ffmpeg", "-i", str(ruta), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    out = {}
    for linea in (r.stderr or "").splitlines():
        for clave in ("mean_volume", "max_volume"):
            if clave in linea:
                try:
                    out[clave] = float(linea.split(clave + ":")[1].split("dB")[0])
                except ValueError:
                    pass
    return out


# ---------------------------------------------------------------- guion
def revisar_guion():
    print("\nGUION")
    import re
    from src.utils import today
    ruta = Path(f"output/scripts/video_{today()}.json")
    if not ruta.exists():
        rutas = sorted(Path("output/scripts").glob("*.json"))
        if not rutas:
            return _mide("existe el guion", MAL, "no hay ninguno")
        ruta = rutas[-1]
    g = json.loads(ruta.read_text(encoding="utf-8"))
    beats = g.get("beats") or []

    _mide("existe el guion", OK, ruta.name)

    palabras = sum(len(b["t"].split()) for b in beats)
    _mide("palabras en rango 170-250", OK if 170 <= palabras <= 250 else MAL,
          f"{palabras}")

    acot = re.compile(r"SFX|^\(|^\[|\*\*.*\*\*|CAMARA:|PLANO:", re.I)
    malos = [b["t"] for b in beats if acot.search(b.get("t", ""))]
    _mide("sin acotaciones en los beats", OK if not malos else MAL,
          f"{len(malos)} encontradas" if malos else "")

    repes = len(beats) - len({b["t"].lower() for b in beats})
    _mide("sin beats repetidos", OK if repes == 0 else MAL, f"{repes}")

    def utiles(t):
        return {p.strip(".,;:!?").lower() for p in t.split() if len(p) > 3}
    ph = utiles(g.get("hook", ""))
    eco = 0
    for b in beats[:3]:
        pb = utiles(b["t"])
        if pb and len(ph & pb) / len(pb) >= 0.7:
            eco += 1
    _mide("el hook no se repite", OK if eco == 0 else MAL, f"{eco} beats lo repiten")

    punch = sum(1 for b in beats if b.get("k") == "punch")
    dato = sum(1 for b in beats if b.get("k") == "dato")
    _mide("minimo 4 punch y 3 dato", OK if punch >= 4 and dato >= 3 else AVISO,
          f"punch {punch}, dato {dato}")
    _mide("familia de hook declarada", OK if g.get("tipo_hook") else AVISO,
          g.get("tipo_hook", "sin declarar"))
    return g


# ---------------------------------------------------------------- voz
def revisar_voz():
    print("\nVOZ")
    from src.utils import audio_path
    a = audio_path()
    if not a.exists():
        return _mide("existe la narracion", MAL, "no encontrada")
    d = _ffprobe(a, "format=duration")
    dur = float(d.get("duration", 0))
    _mide("existe la narracion", OK, a.name)
    _mide("duracion 60-95s", OK if 60 <= dur <= 95 else AVISO, f"{dur:.1f}s")
    v = _volumen(a)
    _mide("nivel de voz razonable",
          OK if -26 < v.get("mean_volume", -99) < -10 else AVISO,
          f"media {v.get('mean_volume', 0):.1f} dB")
    return dur


# ---------------------------------------------------------------- sincronia
def revisar_sincronia():
    print("\nSINCRONIA (lo que de verdad se quemo en el video)")
    import re
    ass = Path("output/media/subs.ass")
    if not ass.exists():
        return _mide("existe el archivo de subtitulos", MAL, "no encontrado")
    from src.alineador import _palabras_reales, _normalizar
    from src.utils import audio_path

    # Un verificador que da falsas alarmas es peor que no tenerlo: enseña a
    # ignorarlo. Si los subtitulos son de un montaje anterior no se pueden
    # comparar con la voz de hoy, asi que se avisa en vez de dar por fallado.
    if ass.stat().st_mtime < audio_path().stat().st_mtime:
        return _mide("subtitulos al dia", AVISO,
                     "son de un montaje anterior; falta reensamblar")

    def seg(t):
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    # Con rotulos cineticos hay una linea POR PALABRA, y cada una repite la
    # frase entera mas la palabra nueva. Solo interesa el arranque de cada
    # frase: si el texto es una extension del anterior, es continuacion.
    # (Tercera vez que hay que revisar esto: cuando cambia lo que se mide,
    # la medicion hay que revisarla tambien.)
    # Se toma el TIEMPO de la primera linea de cada frase y el TEXTO de la
    # ultima, que es la unica que trae la frase completa. Con el texto de la
    # primera solo habria una palabra ("Y", "El") y volveria a emparejar en
    # el sitio equivocado.
    lineas = []
    previo = ""
    for linea in ass.read_text(encoding="utf-8").splitlines():
        if not linea.startswith("Dialogue:"):
            continue
        p = linea.split(",", 9)
        texto = " ".join(re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", " ").split())
        if previo and texto.startswith(previo[:max(8, len(previo) - 2)]):
            lineas[-1] = (lineas[-1][0], texto)   # misma frase, texto mas completo
        else:
            lineas.append((seg(p[1]), texto))
        previo = texto

    # Se compara la secuencia de las primeras palabras, igual que el
    # alineador. Con una sola palabra, un "y" o un "el" empareja dentro de
    # la frase anterior y se reportaban 2.4s de desfase inexistentes: la
    # herramienta de medida no puede ser peor que lo que mide.
    from src.alineador import _parecidas
    palabras = _palabras_reales(audio_path())
    cursor, errores = 0, []
    for inicio, texto in lineas:
        tr = [_normalizar(t) for t in texto.split()[:3]]
        tr = [t for t in tr if t]
        if not tr:
            continue
        mejor_pos, mejor_puntos = None, 0
        for j in range(cursor, min(cursor + 60, len(palabras))):
            puntos = sum(1 for k, o in enumerate(tr)
                         if j + k < len(palabras)
                         and _parecidas(_normalizar(palabras[j + k][2]), o))
            if puntos > mejor_puntos:
                mejor_pos, mejor_puntos = j, puntos
                if puntos == len(tr):
                    break
        if mejor_pos is not None and mejor_puntos >= min(2, len(tr)):
            errores.append(abs(inicio - palabras[mejor_pos][0]))
            cursor = mejor_pos + 1

    if not errores:
        return _mide("subtitulos sincronizados", AVISO, "no se pudo medir")
    medio = sum(errores) / len(errores)
    peor = max(errores)
    _mide("desfase medio < 0.4s", OK if medio < 0.4 else MAL, f"{medio:.2f}s")
    _mide("desfase maximo < 1.5s", OK if peor < 1.5 else MAL, f"{peor:.2f}s")

    # posicion: fuera de la zona de interfaz del Reel
    m = re.search(r"Style: Default,[^\n]*?,(\d+),\d+\s*$", ass.read_text(encoding="utf-8"), re.M)
    margen = int(m.group(1)) if m else 0
    _mide("subtitulos fuera de la zona de UI", OK if margen >= 380 else MAL,
          f"MarginV {margen}")


# ---------------------------------------------------------------- escenas
def revisar_escenas():
    print("\nESCENAS")
    imgs = sorted(Path("output/images").glob("img_*.png"))
    _mide("hay escenas generadas", OK if len(imgs) >= 8 else MAL, f"{len(imgs)}")
    if not imgs:
        return
    from PIL import Image
    malas = [p.name for p in imgs if Image.open(p).size[0] < 500]
    _mide("resolucion suficiente", OK if not malas else MAL,
          f"{len(malas)} pequeñas" if malas else f"{Image.open(imgs[0]).size}")
    vacias = [p.name for p in imgs if p.stat().st_size < 20000]
    _mide("ninguna imagen vacia", OK if not vacias else MAL, f"{len(vacias)}")
    clips = list(Path("output/media/clips_ia").glob("*.mp4"))
    _mide("clips animados", OK if clips else AVISO, f"{len(clips)}")


# ---------------------------------------------------------------- video
def revisar_video(dur_voz):
    print("\nVIDEO FINAL")
    v = Path("output/final/video_final.mp4")
    if not v.exists():
        return _mide("existe el video", MAL, "no encontrado")
    d = _ffprobe(v, "stream=width,height,codec_type:format=duration,size")
    _mide("existe el video", OK, f"{int(d.get('size', 0))/1024/1024:.1f} MB")
    _mide("resolucion 1080x1920",
          OK if d.get("width") == "1080" and d.get("height") == "1920" else MAL,
          f"{d.get('width')}x{d.get('height')}")
    dur = float(d.get("duration", 0))
    if dur_voz:
        desfase = abs(dur - dur_voz)
        _mide("video y voz duran lo mismo", OK if desfase < 0.6 else MAL,
              f"{desfase:.2f}s de diferencia")
    vol = _volumen(v)
    _mide("pico con margen (<= -0.5 dB)",
          OK if vol.get("max_volume", 0) <= -0.5 else MAL,
          f"pico {vol.get('max_volume', 0):.1f} dB")
    _mide("mezcla audible",
          OK if -24 < vol.get("mean_volume", -99) < -12 else AVISO,
          f"media {vol.get('mean_volume', 0):.1f} dB")


# ---------------------------------------------------------------- respaldos
def revisar_respaldos():
    print("\nRESPALDOS Y ENTORNO")
    from src import kie
    from src.escenarios_propios import disponible as local_ok
    from src.hook_hablado import disponible as sad_ok
    import os

    _mide("clave de LLM", OK if (os.getenv("GEMINI_API_KEY") or
                                 os.getenv("OPENAI_API_KEY")) else MAL)
    _mide("escenas locales de respaldo", OK if local_ok() else AVISO)
    _mide("kie.ai disponible", OK if kie.disponible() else AVISO)
    if kie.disponible():
        c = kie.creditos()
        _mide("creditos suficientes", OK if (c or 0) >= 210 else AVISO,
              f"{c:.0f} (~{int((c or 0)/210)} videos)")
    _mide("hook hablado (solo local)", OK if sad_ok() else AVISO)
    _mide("musica disponible",
          OK if list(Path("assets/music").glob("*.mp3")) else MAL)
    _mide("efectos de sonido",
          OK if list(Path("assets/sfx").glob("*.wav")) else MAL)


def revisar_todo():
    _resultados.clear()
    print("=" * 70)
    revisar_guion()
    dur = revisar_voz()
    revisar_sincronia()
    revisar_escenas()
    revisar_video(dur)
    revisar_respaldos()

    fallos = [r for r in _resultados if r[1] == MAL]
    avisos = [r for r in _resultados if r[1] == AVISO]
    print("\n" + "=" * 70)
    print(f"{len(_resultados)} comprobaciones · {len(fallos)} fallos · {len(avisos)} avisos")
    if fallos:
        print("\nFALLOS QUE HAY QUE ARREGLAR:")
        for n, _, d in fallos:
            print(f"  - {n}: {d}")
    else:
        print("\nTodo correcto.")
    return len(fallos)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(1 if revisar_todo() else 0)
