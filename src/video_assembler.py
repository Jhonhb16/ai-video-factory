"""Ensambla el video: corte cada 3s + camaras alternadas + musica. FFmpeg puro."""
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.utils import load_config, audio_path, get_duration, run_cmd, today

log = logging.getLogger("VideoFactory.Assembler")

IMG_DIR = Path("output/images")
FINAL_DIR = Path("output/final")

# Camaras alternadas: (ancla_x, ancla_y, direccion)
CAMARAS = [
    (0.5, 0.5, "in"), (0.3, 0.3, "out"), (0.7, 0.7, "in"),
    (0.5, 0.25, "out"), (0.25, 0.6, "in"), (0.75, 0.4, "out"),
]


def assemble_video():
    cfg = load_config().get("contenido", {})
    fps = int(cfg.get("fps", 30))
    music_on = bool(cfg.get("musica_fondo", True))
    music_vol = float(cfg.get("volumen_musica", 0.15))

    audio = audio_path()
    if not audio.exists():
        raise FileNotFoundError(f"No existe {audio}.")
    audio_dur = get_duration(audio)

    images = sorted(IMG_DIR.glob("img_*.png"))
    if not images:
        raise FileNotFoundError("No hay imagenes en output/images/.")
    n = len(images)

    total_shots = max(8, round(audio_dur / 3.0))
    shot_dur = audio_dur / total_shots

    seg_dir = Path(f"output/segments_{today()}")
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    log.info(f"Renderizando {total_shots} planos de ~{shot_dur:.1f}s (corte cada 3s)...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(
            lambda s: _render_shot(
                images[s % n], shot_dur, fps,
                seg_dir / f"seg_{s:03d}.mp4", CAMARAS[s % len(CAMARAS)]),
            range(total_shots)
        ))

    segments = [seg_dir / f"seg_{s:03d}.mp4" for s in range(total_shots)]
    for sgm in segments:
        if not sgm.exists():
            raise RuntimeError(f"Falta segmento {sgm}")

    music = None
    if music_on:
        tracks = sorted(Path("assets/music").glob("*.mp3")) if Path("assets/music").exists() else []
        if tracks:
            music = tracks[0]
            log.info(f"Musica de fondo: {music.name}")
        else:
            log.warning("Sin musica en assets/music/. Sube un mp3 para edicion profesional.")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    raw = FINAL_DIR / "video_raw.mp4"
    _final_encode(segments, audio, music, music_vol, raw)
    log.info(f"Video ensamblado: {raw} ({audio_dur:.1f}s, {total_shots} cortes)")
    shutil.rmtree(seg_dir, ignore_errors=True)
    return raw


def _render_shot(img, dur, fps, out, cam):
    frames = max(1, round(dur * fps))
    ax, ay, direction = cam
    if direction == "in":
        z = f"min(zoom+{0.15 / frames:.6f},1.15)"
    else:
        z = f"if(eq(on,1),1.2,max(zoom-{0.2 / frames:.6f},1.0))"
    vf = (f"zoompan=z='{z}'"
          f":x='(iw-iw/zoom)*{ax:.2f}':y='(ih-ih/zoom)*{ay:.2f}'"
          f":d={frames}:s=1080x1920:fps={fps}")
    cmd = ["ffmpeg", "-y", "-i", str(img), "-vf", vf,
           "-frames:v", str(frames), "-r", str(fps),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
           "-pix_fmt", "yuv420p", str(out)]
    run_cmd(cmd, timeout=300)


def _final_encode(segments, audio, music, music_vol, out):
    n = len(segments)
    inputs = []
    for s in segments:
        inputs += ["-i", str(s)]
    inputs += ["-i", str(audio)]
    if music:
        inputs += ["-i", str(music)]

    concat_in = "".join(f"[{i}:v]" for i in range(n))
    fc = f"{concat_in}concat=n={n}:v=1:a=0[vcat]"

    if music:
        fc += (f";[{n}:a]volume=1.8[narr]"
               f";[{n+1}:a]volume={music_vol*2:.3f}[mus]"
               f";[narr][mus]amix=inputs=2:duration=first:dropout_transition=0[aout]")
        amap = "[aout]"
    else:
        amap = f"{n}:a"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", fc,
        "-map", "[vcat]", "-map", amap,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(out)
    ]
    run_cmd(cmd, timeout=1200)
