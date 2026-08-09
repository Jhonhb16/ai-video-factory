"""Ensambla el video: Ken Burns + concat + mezcla de audio. FFmpeg puro."""
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.utils import load_config, audio_path, get_duration, run_cmd, today

log = logging.getLogger("VideoFactory.Assembler")

IMG_DIR = Path("output/images")
FINAL_DIR = Path("output/final")


def assemble_video():
    cfg = load_config().get("contenido", {})
    fps = int(cfg.get("fps", 30))
    music_on = bool(cfg.get("musica_fondo", True))
    music_vol = float(cfg.get("volumen_musica", 0.15))

    audio = audio_path()
    if not audio.exists():
        raise FileNotFoundError(f"No existe {audio}. Ejecuta el paso de voz.")
    audio_dur = get_duration(audio)

    images = sorted(IMG_DIR.glob("img_*.png"))
    if not images:
        raise FileNotFoundError("No hay imagenes en output/images/.")
    n = len(images)

    base = audio_dur / n
    durations = [base] * n
    durations[-1] = audio_dur - base * (n - 1)

    music = None
    if music_on:
        tracks = sorted(Path("assets/music").glob("*.mp3")) if Path("assets/music").exists() else []
        if tracks:
            music = tracks[0]
        else:
            log.warning("Sin musica en assets/music/; se omite la pista musical.")

    seg_dir = Path(f"output/segments_{today()}")
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    log.info(f"Renderizando {n} segmentos en paralelo (fps={fps})...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(
            lambda i: _render_segment(images[i], durations[i], fps, seg_dir / f"seg_{i:03d}.mp4", i),
            range(n)
        ))

    segments = [seg_dir / f"seg_{i:03d}.mp4" for i in range(n)]
    for s in segments:
        if not s.exists():
            raise RuntimeError(f"Falta segmento {s}")

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    raw = FINAL_DIR / "video_raw.mp4"
    _final_encode(segments, audio, music, music_vol, fps, raw)
    log.info(f"Video ensamblado: {raw} ({audio_dur:.1f}s)")

    shutil.rmtree(seg_dir, ignore_errors=True)
    return raw


def _render_segment(img, dur, fps, out, idx):
    frames = max(1, round(dur * fps))
    zoom_inc = 0.15 / frames
    anchors = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.7), (0.5, 0.3), (0.3, 0.7)]
    ax, ay = anchors[idx % len(anchors)]

    vf = (f"zoompan=z='min(zoom+{zoom_inc:.6f},1.15)'"
          f":x='(iw-iw/zoom)*{ax:.2f}':y='(ih-ih/zoom)*{ay:.2f}'"
          f":d={frames}:s=1080x1920:fps={fps}")

    cmd = ["ffmpeg", "-y", "-i", str(img),
           "-vf", vf,
           "-frames:v", str(frames),
           "-r", str(fps),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
           "-pix_fmt", "yuv420p",
           str(out)]
    run_cmd(cmd, timeout=300)


def _final_encode(segments, audio, music, music_vol, fps, out):
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
