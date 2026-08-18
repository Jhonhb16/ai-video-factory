"""Montaje final del clip: cámara, gráficos, doblaje y música.

Se hace por partes y no en un solo filtergraph gigante: así cada paso se puede
mirar por separado cuando algo sale mal, que es lo que pasa siempre.

Cámara: los planos del presentador entran MÁS CERRADOS que el general, y el
segundo más que el primero. Un corte a la misma escala no se lee como cambio
de cámara, se lee como un salto.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

E = Path("output/cliente/edicion")
G = E / "gfx"
BASE = E / "base.mp4"
FPS = 25
DUR = 51.42

# (inicio, fin, zoom_inicial, zoom_final, centro_y)  centro_y 0.5 = mitad
PLANOS = [
    (0.00, 21.50, 1.00, 1.06, 0.50),   # comparativa, empuje lento
    (21.50, 24.50, 1.20, 1.23, 0.42),  # presentador, plano medio
    (24.50, 40.50, 1.06, 1.00, 0.50),  # comparativa, retrocede
    (40.50, 45.50, 1.30, 1.34, 0.42),  # presentador, MÁS cerrado que antes
    (45.50, DUR, 1.00, 1.04, 0.50),    # comparativa, cierre
]

# (png, entra, sale) — solo sobre comparativa, nunca sobre el presentador
CAPAS = [
    ("rotulos.png", 0.00, 21.30),
    ("rotulos.png", 24.70, 40.30),
    ("rotulos.png", 45.70, DUR),
    ("spec_tcl.png", 1.60, 9.60),
    ("spec_his.png", 10.60, 20.60),
    ("comp65.png", 25.20, 37.80),
]
FUNDIDO = 0.35


def run(cmd, etiqueta=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FALLO {etiqueta}\n{r.stderr[-1200:]}")
        raise SystemExit(1)


print("1/4  camara: cortes y zooms")
partes = []
for i, (a, b, z0, z1, cy) in enumerate(PLANOS):
    dur = b - a
    n = max(1, int(round(dur * FPS)))
    dest = E / f"seg{i}.mp4"
    # zoompan: 'on' es el fotograma de salida, asi que el zoom avanza solo
    z = f"{z0}+({z1 - z0})*on/{n}"
    vf = (f"zoompan=z='{z}':d=1:fps={FPS}:s=1920x1080"
          f":x='iw/2-(iw/zoom/2)'"
          f":y='ih*{cy}-(ih/zoom/2)'")
    run(["ffmpeg", "-y", "-ss", f"{a:.3f}", "-i", str(BASE), "-t", f"{dur:.3f}",
         "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-pix_fmt", "yuv420p", str(dest)], f"segmento {i}")
    partes.append(dest)
    print(f"     plano {i}: {a:5.2f}-{b:5.2f}s  zoom {z0}->{z1}")

lista = E / "lista.txt"
lista.write_text("".join(f"file '{p.name}'\n" for p in partes), encoding="utf-8")
run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
     "-c", "copy", str(E / "camara.mp4")], "concat")

print("2/4  graficos encima")
entradas, filtros, prev = ["-i", str(E / "camara.mp4")], [], "0:v"
for k, (png, ent, sal) in enumerate(CAPAS):
    # -loop: un PNG suelto es UN fotograma en t=0, asi que el fundido que
    # empieza en el segundo 1.6 no llegaba a ocurrir nunca y la capa salia
    # invisible. Con loop pasa a ser un video de la duracion del clip.
    entradas += ["-loop", "1", "-framerate", str(FPS), "-t", f"{DUR:.2f}",
                 "-i", str(G / png)]
    et = f"c{k}"
    # el fundido va en el alfa de la capa, no en la imagen de debajo
    filtros.append(
        f"[{k+1}:v]format=rgba,"
        f"fade=t=in:st={ent:.2f}:d={FUNDIDO}:alpha=1,"
        f"fade=t=out:st={max(ent, sal - FUNDIDO):.2f}:d={FUNDIDO}:alpha=1[{et}]")
    filtros.append(
        f"[{prev}][{et}]overlay=0:0:enable='between(t,{ent:.2f},{sal:.2f})'[v{k}]")
    prev = f"v{k}"
run(["ffmpeg", "-y"] + entradas + ["-filter_complex", ";".join(filtros),
     "-map", f"[{prev}]", "-t", f"{DUR:.2f}",
     "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
     str(E / "video_gfx.mp4")], "graficos")

print("3/4  audio: doblaje + musica con ducking")
d = json.load(open("output/cliente/clip_bloques.json", encoding="utf-8"))
ent_audio, f_audio, etiquetas = [], [], []
for i, b in enumerate(d["bloques"]):
    ent_audio += ["-i", b["audio"]]
    ms = int(b["ini"] * 1000)
    f_audio.append(f"[{i}:a]adelay={ms}|{ms},aformat=sample_fmts=fltp:"
                   f"sample_rates=48000:channel_layouts=stereo[v{i}]")
    etiquetas.append(f"[v{i}]")
n = len(d["bloques"])
ent_audio += ["-i", "assets/music/energia-alta.mp3"]
f_audio.append("".join(etiquetas) + f"amix=inputs={n}:normalize=0[voz]")
f_audio.append("[voz]volume=1.35,alimiter=limit=0.95[vozf]")
# la musica se aparta sola bajo la voz; sin esto compite y cansa
f_audio.append(f"[{n}:a]aformat=sample_fmts=fltp:sample_rates=48000:"
               f"channel_layouts=stereo,volume=0.16,atrim=0:{DUR:.2f}[mus]")
f_audio.append("[mus][vozf]sidechaincompress=threshold=0.06:ratio=8:"
               "attack=15:release=340[musd]")
# loudnorm a -14 LUFS, que es el objetivo de YouTube. A ojo el nivel salia
# en -29.8 dB de media: se oiria la mitad de bajo que cualquier otro video.
f_audio.append("[vozf][musd]amix=inputs=2:normalize=0,"
               "loudnorm=I=-14:TP=-1.5:LRA=11,"
               "alimiter=limit=0.95[out]")
run(["ffmpeg", "-y"] + ent_audio + ["-filter_complex", ";".join(f_audio),
     "-map", "[out]", "-t", f"{DUR:.2f}", "-c:a", "pcm_s16le",
     str(E / "audio.wav")], "audio")

print("4/4  union final")
run(["ffmpeg", "-y", "-i", str(E / "video_gfx.mp4"), "-i", str(E / "audio.wav"),
     "-map", "0:v", "-map", "1:a", "-c:v", "copy",
     "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart",
     str(E / "clip_final.mp4")], "union")

info = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                       "format=duration,size", "-show_entries",
                       "stream=width,height", "-of", "csv=p=0",
                       str(E / "clip_final.mp4")], capture_output=True, text=True)
print("\nLISTO:", E / "clip_final.mp4")
print(info.stdout.strip())

# Nota: este modulo se escribio para el encargo de doblaje de Colbin Review.
# Los tiempos de PLANOS y CAPAS son de ese clip; para otro video hay que
# volver a detectar los cambios de plano y recolocar las capas.
