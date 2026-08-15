"""Ensamblador v5 (ESTUDIO COMEDIA): b-roll + mascota que ACTUA por beat +
subtitulos con enfasis en punchlines + SFX sincronizados + musica."""
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from src.utils import load_config, load_script, audio_path, get_duration, run_cmd, today

log = logging.getLogger("VideoFactory.Assembler")
IMG_DIR = Path("output/images")
MEDIA_DIR = Path("output/media")
MASCOT_DIR = MEDIA_DIR / "mascot"
FINAL_DIR = Path("output/final")

CAMARAS = [(0.5, 0.5, "in"), (0.3, 0.3, "out"), (0.7, 0.7, "in"),
           (0.5, 0.25, "out"), (0.25, 0.6, "in"), (0.75, 0.4, "out")]


def _beat_timeline(guion, audio_dur):
    seq = []
    if guion.get("hook"):
        seq.append((guion["hook"], "hook"))
    for b in (guion.get("beats") or []):
        if isinstance(b, dict) and (b.get("t") or "").strip():
            seq.append((b["t"].strip(), b.get("k", "normal")))
        elif isinstance(b, str) and b.strip():
            seq.append((b.strip(), "normal"))
    if guion.get("cta"):
        seq.append((guion["cta"], "cta"))
    pesos = [max(1, len(t.split())) for t, k in seq]
    total = sum(pesos) or 1
    items, t0 = [], 0.0
    for (txt, k), w in zip(seq, pesos):
        d = audio_dur * w / total
        items.append({"txt": txt, "k": k, "start": t0, "end": t0 + d})
        t0 += d
    return items


def _pose_en(ts, items, s):
    for it in items:
        if it["start"] <= ts < it["end"]:
            k = it["k"]
            if k == "punch":
                return "celebrate"
            if k == "dato":
                return "point"
            if k == "hook":
                return "talk"
            if k == "cta":
                return "celebrate"
            return ["talk", "explain", "think"][s % 3]
    return "talk"


def assemble_video():
    cfg = load_config().get("contenido", {})
    fps = int(cfg.get("fps", 30))
    music_vol = float(cfg.get("volumen_musica", 0.15))
    audio = audio_path()
    if not audio.exists():
        raise FileNotFoundError(f"No existe {audio}.")
    audio_dur = get_duration(audio)

    try:
        guion = load_script()
    except Exception:
        guion = {}
    items = _beat_timeline(guion, audio_dur)

    clips = sorted(MEDIA_DIR.glob("clip_*.mp4")) if MEDIA_DIR.exists() else []
    images = sorted(IMG_DIR.glob("img_*.png")) if IMG_DIR.exists() else []
    if not clips and not images:
        raise FileNotFoundError("No hay clips ni imagenes.")

    total_shots = max(8, round(audio_dur / 3.0))
    shot_dur = audio_dur / total_shots

    seg_dir = Path(f"output/segments_{today()}")
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    log.info(f"{total_shots} planos de ~{shot_dur:.1f}s + mascota actuando por beat...")

    jobs = []
    if clips:
        durs = {c: get_duration(c) for c in clips}
        for s in range(total_shots):
            clip = clips[s % len(clips)]
            cd = durs[clip]
            off = min((s // len(clips)) * shot_dur, max(0.0, cd - shot_dur - 0.3))
            jobs.append(("clip", clip, off, s, _pose_en(s * shot_dur, items, s)))
    else:
        for s in range(total_shots):
            jobs.append(("img", images[s % len(images)], 0, s, _pose_en(s * shot_dur, items, s)))

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: _render(j, shot_dur, fps, seg_dir), jobs))

    segments = [seg_dir / f"seg_{s:03d}.mp4" for s in range(total_shots)]
    for sgm in segments:
        if not sgm.exists():
            raise RuntimeError(f"Falta segmento {sgm}")

    music = None
    tracks = sorted(Path("assets/music").glob("*.mp3")) if Path("assets/music").exists() else []
    if tracks:
        music = tracks[0]
    elif MEDIA_DIR.exists() and (MEDIA_DIR / "musica.mp3").exists():
        music = MEDIA_DIR / "musica.mp3"

    _generar_subtitulos(items)

    sfx_cues = [(it["start"], "sfx_pop.mp3") for it in items if it["k"] == "punch"]
    if len(items) > 1:
        sfx_cues.append((items[1]["start"], "sfx_whoosh.mp3"))

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    raw = FINAL_DIR / "video_raw.mp4"
    _final_encode(segments, audio, music, music_vol, raw, sfx_cues)
    log.info(f"Video ensamblado: {raw} ({audio_dur:.1f}s, {total_shots} cortes, "
             f"{len(sfx_cues)} SFX)")
    shutil.rmtree(seg_dir, ignore_errors=True)
    return raw


def _render(job, dur, fps, seg_dir):
    kind, src, off, idx, pose = job
    out = seg_dir / f"seg_{idx:03d}.mp4"
    mascot = MASCOT_DIR / f"{pose}.png"
    has_m = mascot.exists()

    if kind == "clip":
        base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
        inputs = ["-stream_loop", "1", "-ss", f"{off:.2f}", "-i", str(src)]
        tflag = ["-t", f"{dur:.2f}"]
    else:
        frames = max(1, round(dur * fps))
        ax, ay, direction = CAMARAS[idx % len(CAMARAS)]
        z = (f"min(zoom+{0.15 / frames:.6f},1.15)" if direction == "in"
             else f"if(eq(on,1),1.2,max(zoom-{0.2 / frames:.6f},1.0))")
        base = (f"zoompan=z='{z}':x='(iw-iw/zoom)*{ax:.2f}':y='(ih-ih/zoom)*{ay:.2f}'"
                f":d={frames}:s=1080x1920:fps={fps}")
        inputs = ["-i", str(src)]
        tflag = ["-frames:v", str(frames)]

    if has_m:
        inputs += ["-i", str(mascot)]
        fc = (f"[0:v]{base}[b];[1:v]scale=-2:620[m];"
              f"[b][m]overlay=x=W-w-30:y=H-h-170+8*sin(2*PI*t/1.2)[v]")
        vmap = "[v]"
    else:
        fc = f"[0:v]{base}[v]"
        vmap = "[v]"

    cmd = ["ffmpeg", "-y"] + inputs + tflag + [
        "-filter_complex", fc, "-map", vmap,
        "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(out)]
    run_cmd(cmd, timeout=300)


def _ts(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def _generar_subtitulos(items):
    if not items:
        return
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "[Script Info]", "ScriptType: v4.00+",
        "PlayResX: 1080", "PlayResY: 1920",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # MarginV=560: los ~600px inferiores de un Reel los tapa la interfaz
        # (caption, botones de like/comentar/compartir). Con el valor
        # anterior (160) los subtitulos quedaban debajo de los botones.
        "Style: Default,DejaVu Sans,62,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,60,60,560,1",
        "Style: Hook,DejaVu Sans,70,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,0,2,60,60,560,1",
        "Style: Punch,DejaVu Sans,70,&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,0,2,60,60,560,1",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for it in items:
        style = {"hook": "Hook", "punch": "Punch", "cta": "Punch"}.get(it["k"], "Default")
        lines.append(f"Dialogue: 0,{_ts(it['start'])},{_ts(it['end'])},{style},,0,0,0,,{it['txt']}")
    (MEDIA_DIR / "subs.ass").write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Subtitulos con enfasis: {len(items)} lineas")


def _final_encode(segments, audio, music, music_vol, out, sfx_cues):
    n = len(segments)
    inputs = []
    for sgm in segments:
        inputs += ["-i", str(sgm)]
    inputs += ["-i", str(audio)]
    aidx = n
    midx = None
    if music:
        inputs += ["-i", str(music)]
        midx = n + 1

    next_idx = n + 1 + (1 if music else 0)
    sfx_list = []
    for (t, name) in sfx_cues:
        p = MEDIA_DIR / name
        if p.exists():
            inputs += ["-i", str(p)]
            sfx_list.append((t, next_idx))
            next_idx += 1

    concat_in = "".join(f"[{i}:v]" for i in range(n))
    fc = f"{concat_in}concat=n={n}:v=1:a=0[vcat]"

    sub = MEDIA_DIR / "subs.ass"
    if sub.exists():
        # FIX Windows: en el filtergraph de ffmpeg el backslash es un escape, asi
        # que "output\media\subs.ass" se convertia en "outputmediasubs.ass".
        # La ruta es siempre relativa, asi que con barras normales basta y en
        # Linux el replace no cambia nada.
        fc += f";[vcat]ass={str(sub).replace(chr(92), '/')}[vsub]"
        vmap = "[vsub]"
    else:
        vmap = "[vcat]"

    fc += f";[{aidx}:a]volume=1.0[a0]"
    maps = ["[a0]"]
    if music:
        fc += f";[{midx}:a]volume={music_vol:.3f}[a1]"
        maps.append("[a1]")
    for j, (t, idx) in enumerate(sfx_list):
        ms = int(t * 1000)
        fc += f";[{idx}:a]adelay={ms}|{ms},volume=0.9[s{j}]"
        maps.append(f"[s{j}]")
    fc += f";{''.join(maps)}amix=inputs={len(maps)}:normalize=0:duration=first[aout]"

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", fc,
        "-map", vmap, "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(out)
    ]
    run_cmd(cmd, timeout=1200)
