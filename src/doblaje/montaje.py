"""Montaje final: camara, capas, mezcla y union.

Decisiones que costaron un video entero descubrir:

CAMARA. Solo se mueve en los planos del presentador. En una comparativa de
imagen el espectador esta juzgando calidad, y un zoom se la altera. Ademas 16
minutos de zooms constantes cansan. Los planos del presentador alternan escala
para que dos seguidos no se lean como el mismo.

CAPAS. Un PNG suelto es UN fotograma en t=0: si se le pone un fundido que
empieza en el segundo 2, ese fundido no ocurre nunca y la capa sale invisible
sin que ffmpeg avise. Hay que pasarlo con -loop.

GRAFICOS. Solo sobre planos donde hay banda negra libre. Encima del presentador
quedan flotando sobre imagen viva. Y si la ventana en que se menciona el dato
queda partida por un corte, se usa solo el tramo continuo mas largo: una franja
que parpadea se ve como error de render.

AUDIO. loudnorm a -14 LUFS, que es el objetivo de las plataformas. Sin eso
salia a -30 dB, la mitad de bajo que cualquier otro video.
"""
import logging
import subprocess
from pathlib import Path

log = logging.getLogger("VideoFactory.Doblaje.Montaje")

FPS = 25
MIN_VISIBLE = 4.0      # una franja que dura menos no da tiempo a leerse


def _run(cmd, etq):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.error(f"FALLO en {etq}:\n{r.stderr[-800:]}")
        raise RuntimeError(etq)


def camara(video, planos, carpeta, fps=FPS):
    """Corta los planos aplicando punch-in solo donde toca."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    partes, n_pres = [], 0

    for i, p in enumerate(planos):
        dur = p["fin"] - p["ini"]
        if dur < 0.4:
            continue
        dest = carpeta / f"s{i:03d}.mp4"
        if p["tipo"] == "presentador":
            # se alterna la escala: dos planos seguidos a la misma distancia
            # se leen como un salto, no como un cambio de camara
            z0 = 1.18 if n_pres % 2 == 0 else 1.28
            n_pres += 1
            nf = max(1, int(dur * fps))
            vf = (f"zoompan=z='{z0}+0.03*on/{nf}':d=1:fps={fps}:s=1920x1080"
                  f":x='iw/2-(iw/zoom/2)':y='ih*0.42-(ih/zoom/2)'")
        else:
            vf = f"fps={fps}"      # comparativa y carteles: sin tocar
        if not dest.exists():
            _run(["ffmpeg", "-y", "-ss", f"{p['ini']:.3f}", "-i", str(video),
                  "-t", f"{dur:.3f}", "-vf", vf, "-an", "-c:v", "libx264",
                  "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                  str(dest)], f"plano {i}")
        partes.append(dest)

    lista = carpeta / "lista.txt"
    lista.write_text("".join(f"file '{p.name}'\n" for p in partes),
                     encoding="utf-8")
    salida = carpeta / "camara.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
          "-c", "copy", str(salida)], "concat")
    log.info(f"{len(partes)} planos montados ({n_pres} con punch-in)")
    return salida


def ventana_visible(a, b, planos, minimo=MIN_VISIBLE):
    """El tramo continuo mas largo de [a,b] que cae sobre banda libre."""
    libres = [p for p in planos if p["tipo"] == "comparativa"]
    trozos = [(max(a, p["ini"]), min(b, p["fin"])) for p in libres]
    trozos = [(x, y) for x, y in trozos if y - x > 0.1]
    if not trozos:
        return None
    mejor = max(trozos, key=lambda t: t[1] - t[0])
    return mejor if mejor[1] - mejor[0] >= minimo else None


def capas(base, planos, rotulos, franjas, tarjetas, destino, duracion, fps=FPS):
    """Superpone rotulos, franjas de datos y tarjetas de titulo.

    `franjas` es [(png, ini, fin)] y se recorta sola a donde hay banda libre.
    `tarjetas` es {segundo: png} y va sin fundido: aparece y desaparece con el
    corte, como el original. Un fundido ahi delataria el parche.
    """
    libres = [p for p in planos if p["tipo"] == "comparativa"]
    cond = "+".join(f"between(t,{p['ini']:.2f},{p['fin']:.2f})" for p in libres)

    ent = ["-i", str(base),
           "-loop", "1", "-framerate", str(fps), "-t", f"{duracion:.2f}",
           "-i", str(rotulos)]
    fil = [f"[0:v][1:v]overlay=0:0:enable='{cond}'[v0]"]
    prev, n = "v0", 2

    for png, a, b in franjas:
        v = ventana_visible(a, b, planos)
        if not v:
            log.info(f"  {Path(png).name}: sin hueco de banda libre, se omite")
            continue
        a, b = v
        ent += ["-loop", "1", "-framerate", str(fps), "-t", f"{duracion:.2f}",
                "-i", str(png)]
        fil.append(f"[{n}:v]format=rgba,fade=t=in:st={a:.2f}:d=0.3:alpha=1,"
                   f"fade=t=out:st={b-0.3:.2f}:d=0.3:alpha=1[x{n}]")
        fil.append(f"[{prev}][x{n}]overlay=0:0:"
                   f"enable='between(t,{a:.2f},{b:.2f})'[v{n}]")
        prev = f"v{n}"
        n += 1

    for seg, png in sorted(tarjetas.items()):
        ent += ["-loop", "1", "-framerate", str(fps), "-t", f"{duracion:.2f}",
                "-i", str(png)]
        fil.append(f"[{prev}][{n}:v]overlay=0:0:"
                   f"enable='between(t,{seg-0.3:.2f},{seg+3.4:.2f})'[v{n}]")
        prev = f"v{n}"
        n += 1

    _run(["ffmpeg", "-y"] + ent + ["-filter_complex", ";".join(fil),
          "-map", f"[{prev}]", "-t", f"{duracion:.2f}", "-c:v", "libx264",
          "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
          str(destino)], "capas")
    return destino


def mezclar(voz, musica, destino, duracion, volumen_musica=0.11):
    """Voz + musica con ducking y nivel de plataforma.

    OJO con las etiquetas del filtergraph: [v] no vale como nombre porque
    ffmpeg lo lee como "el flujo de video" de una entrada. Costo un render.
    """
    _run(["ffmpeg", "-y", "-i", str(voz), "-stream_loop", "-1", "-i", str(musica),
          "-filter_complex",
          "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:"
          "channel_layouts=stereo[vz];"
          "[1:a]aformat=sample_fmts=fltp:sample_rates=48000:"
          f"channel_layouts=stereo,volume={volumen_musica},"
          f"atrim=0:{duracion:.2f}[ms];"
          "[ms][vz]sidechaincompress=threshold=0.05:ratio=9:attack=15:"
          "release=380[msd];"
          "[vz][msd]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,"
          "alimiter=limit=0.95[out]",
          "-map", "[out]", "-t", f"{duracion:.2f}", "-c:a", "pcm_s16le",
          str(destino)], "mezcla")
    return destino


def unir(video, audio, destino, revision=None):
    """Une video y audio, y saca una copia ligera para revisar."""
    _run(["ffmpeg", "-y", "-i", str(video), "-i", str(audio),
          "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
          "-b:a", "256k", "-movflags", "+faststart", str(destino)], "union")
    if revision:
        _run(["ffmpeg", "-y", "-i", str(destino), "-c:v", "libx264",
              "-preset", "medium", "-crf", "24", "-maxrate", "3M",
              "-bufsize", "6M", "-c:a", "aac", "-b:a", "160k",
              "-movflags", "+faststart", str(revision)], "revision")
    return destino
