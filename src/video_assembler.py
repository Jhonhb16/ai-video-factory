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

# Un plano por beat, pero sin bajar de este minimo: un beat de dos palabras
# daria medio segundo y no da tiempo ni a leer.
MIN_PLANO = 1.4
MAX_PLANO = 4.0

# Efecto de sonido segun el tipo de beat. Antes no habia NINGUNO: cada corte
# era un silencio, y un corte sin sonido no se "siente".
SFX_POR_BEAT = {"punch": "impacto", "dato": "ding", "hook": "whoosh",
                "cta": "impacto", "normal": "whoosh"}

# Maqueta "panel": la imagen ocupa el 60% superior y debajo queda una banda
# oscura donde vive el texto. Asi el subtitulo NUNCA tapa la imagen, y esa
# banda es la misma zona donde se dibujan los graficos de cifras: imagenes y
# datos comparten una sola reticula y el video se lee como un solo producto.
ALTO_IMAGEN = 0.60
COLOR_PANEL = "0x070b12"
COLOR_ACENTO = {"punch": "0xff4d6d", "dato": "0x22e39a", "hook": "0xffc857",
                "cta": "0x22e39a", "normal": "0x22e39a"}


def _agrupar_en_planos(items):
    """Convierte beats en planos, uniendo los demasiado cortos.

    Asi el ritmo lo marca el guion (frase corta = plano corto) en vez de un
    corte cada 3 segundos exactos, que es previsible y aburre.
    """
    planos = []
    for it in items:
        dur = it["end"] - it["start"]
        if planos and (planos[-1]["end"] - planos[-1]["start"]) < MIN_PLANO:
            # el anterior se quedo corto: se estira hasta absorber este beat
            planos[-1]["end"] = it["end"]
            # manda el tipo mas fuerte de los dos
            if it["k"] in ("punch", "dato") and planos[-1]["k"] == "normal":
                planos[-1]["k"] = it["k"]
            continue
        planos.append({"start": it["start"], "end": it["end"],
                       "k": it["k"], "idx": it.get("idx", len(planos))})

    # trocear los que se pasen de largo: mas de 4s sin corte es tiempo muerto
    finales = []
    for p in planos:
        dur = p["end"] - p["start"]
        if dur <= MAX_PLANO:
            finales.append(p)
            continue
        trozos = int(dur / MAX_PLANO) + 1
        paso = dur / trozos
        for j in range(trozos):
            finales.append({"start": p["start"] + j * paso,
                            "end": p["start"] + (j + 1) * paso,
                            "k": p["k"], "idx": p["idx"]})
    return finales


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
    for i, ((txt, k), w) in enumerate(zip(seq, pesos)):
        d = audio_dur * w / total
        items.append({"txt": txt, "k": k, "start": t0, "end": t0 + d, "idx": i})
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

    # Anclar los tiempos a la voz REAL antes de decidir nada. El reparto
    # proporcional acumulaba hasta 4.76s de error, asi que tanto los
    # subtitulos como los cortes iban por delante de lo que se oye.
    from src.alineador import alinear
    items = alinear(items, audio, audio_dur)

    # Un plano por beat en vez de un corte cada 3s exactos: el ritmo lo marca
    # el guion. Frase corta, plano corto; remate, plano con punch-in.
    planos = _agrupar_en_planos(items) if items else []
    if not planos:
        n = max(8, round(audio_dur / 3.0))
        paso = audio_dur / n
        planos = [{"start": i * paso, "end": (i + 1) * paso, "k": "normal", "idx": i}
                  for i in range(n)]

    seg_dir = Path(f"output/segments_{today()}")
    if seg_dir.exists():
        shutil.rmtree(seg_dir)
    seg_dir.mkdir(parents=True)

    duraciones = [p["end"] - p["start"] for p in planos]
    log.info(f"{len(planos)} planos sincronizados con los beats "
             f"({min(duraciones):.1f}s a {max(duraciones):.1f}s, "
             f"media {sum(duraciones)/len(duraciones):.1f}s)")

    maqueta = (load_config().get("contenido", {}) or {}).get("maqueta", "panel")
    jobs = []
    clip_durs = {c: get_duration(c) for c in clips} if clips else {}
    for s, p in enumerate(planos):
        dur = p["end"] - p["start"]
        pose = _pose_en(p["start"], items, s)
        if clips:
            clip = clips[s % len(clips)]
            cd = clip_durs[clip]
            off = min((s // len(clips)) * dur, max(0.0, cd - dur - 0.3))
            jobs.append(("clip", clip, off, s, pose, dur, p["k"]))
        else:
            modo = "img_panel" if maqueta == "panel" else "img"
            jobs.append((modo, images[p["idx"] % len(images)], 0, s, pose, dur, p["k"]))

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda j: _render(j, fps, seg_dir), jobs))

    segments = [seg_dir / f"seg_{s:03d}.mp4" for s in range(len(planos))]

    # Apertura hablada (solo local, con GPU). Si falla o no esta disponible,
    # los segmentos se quedan como estan y el video sale igual.
    segments = _aplicar_hook_hablado(segments, planos, audio, images, fps, seg_dir)
    for sgm in segments:
        if not sgm.exists():
            raise RuntimeError(f"Falta segmento {sgm}")

    # Rotar la pista por fecha: con tracks[0] todos los videos sonaban igual.
    music = None
    tracks = sorted(Path("assets/music").glob("*.mp3")) if Path("assets/music").exists() else []
    if tracks:
        music = tracks[int(today()) % len(tracks)]
    elif MEDIA_DIR.exists() and (MEDIA_DIR / "musica.mp3").exists():
        music = MEDIA_DIR / "musica.mp3"

    _generar_subtitulos(items)

    # Un efecto por corte, elegido por el tipo de beat. Antes eran cero:
    # las señales existian pero los archivos nunca se descargaron.
    from src.sfx import asegurar_sfx, ruta as ruta_sfx
    asegurar_sfx()
    sfx_cues = []
    for p in planos:
        nombre = SFX_POR_BEAT.get(p["k"], "whoosh")
        camino = ruta_sfx(nombre)
        if camino:
            # 60 ms antes del corte: el sonido debe anticipar la imagen
            sfx_cues.append((max(0.0, p["start"] - 0.06), camino))

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    raw = FINAL_DIR / "video_raw.mp4"
    _final_encode(segments, audio, music, music_vol, raw, sfx_cues)
    # el conteo de SFX cuenta senales, no archivos: solo se mezclan los que existen
    sfx_reales = sum(1 for (_, p) in sfx_cues if Path(p).exists())
    log.info(f"Video ensamblado: {raw} ({audio_dur:.1f}s, {len(planos)} cortes, "
             f"musica={music.name if music else 'NINGUNA'}, {sfx_reales} SFX)")
    shutil.rmtree(seg_dir, ignore_errors=True)
    return raw


def _aplicar_hook_hablado(segments, planos, audio, images, fps, seg_dir):
    """Sustituye los primeros planos por un unico plano hablado.

    Devuelve la lista de segmentos tal cual si algo falla: esta funcion
    nunca puede tumbar el montaje.
    """
    try:
        from src.hook_hablado import generar_hook, disponible
        if not disponible() or not images:
            return segments

        objetivo = float(load_config().get("hook_hablado", {}).get("segundos", 12))

        # Cuantos planos cubre la apertura: se corta donde la suma se acerque
        # mas al objetivo, para que la duracion cuadre exacta y el audio no
        # se desplace respecto al resto del video.
        acumulado, corte, mejor, dur_hook = 0.0, 0, float("inf"), 0.0
        for i, p in enumerate(planos):
            acumulado += p["end"] - p["start"]
            dif = abs(acumulado - objetivo)
            if dif < mejor:
                mejor, corte, dur_hook = dif, i + 1, acumulado
        if corte < 2 or dur_hook <= 0:
            log.info("La apertura cubriria menos de dos planos; se deja normal.")
            return segments

        # se le pide la duracion YA cuadrada con los planos, no un valor
        # redondo: si no, el video vuelve con otra duracion y hay que tirarlo
        hook = generar_hook(audio, images[0], segundos=dur_hook)
        if not hook:
            return segments

        # Reencodear a los mismos parametros que los demas segmentos y
        # recortar a la duracion EXACTA de los planos que sustituye.
        destino = seg_dir / "seg_hook.mp4"
        run_cmd(["ffmpeg", "-y", "-i", str(hook), "-t", f"{dur_hook:.3f}",
                 "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,"
                        f"crop=1080:1920,setsar=1,fps={fps}",
                 "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-pix_fmt", "yuv420p", str(destino)])

        real = get_duration(destino)
        if abs(real - dur_hook) > 0.25:
            log.warning(f"El hook hablado quedo en {real:.2f}s en vez de "
                        f"{dur_hook:.2f}s; se descarta para no desincronizar.")
            return segments

        log.info(f"Apertura hablada: sustituye {corte} planos ({dur_hook:.1f}s)")
        return [destino] + segments[corte:]

    except Exception as e:
        log.warning(f"No se pudo aplicar la apertura hablada ({e}); sigue normal.")
        return segments


def _render(job, fps, seg_dir):
    kind, src, off, idx, pose, dur, tipo = job
    out = seg_dir / f"seg_{idx:03d}.mp4"
    mascot = MASCOT_DIR / f"{pose}.png"
    has_m = mascot.exists()

    if kind == "clip":
        base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
        inputs = ["-stream_loop", "1", "-ss", f"{off:.2f}", "-i", str(src)]
        tflag = ["-t", f"{dur:.2f}"]
    elif kind == "img_panel":
        # Maqueta A: imagen arriba, panel de texto abajo. El texto no la tapa.
        frames = max(1, round(dur * fps))
        alto = int(1920 * ALTO_IMAGEN) // 2 * 2      # par, lo exige el codec
        ax, ay, direction = CAMARAS[idx % len(CAMARAS)]
        # Las imagenes son 9:16 y la zona es casi cuadrada (1080x1152): al
        # recortar se pierde casi el 40% del alto. Con el recorte centrado
        # salian planos de torso sin cabeza. Se sesga fuerte hacia ARRIBA,
        # que es donde esta la cara en un plano de cuerpo entero.
        ay = min(ay, 0.12)
        avance = 0.22 if tipo in ("punch", "cta") else 0.12
        tope = 1.0 + avance
        z = f"min(zoom+{avance/frames:.6f},{tope:.2f})"
        acento = COLOR_ACENTO.get(tipo, "0x22e39a")
        base = (f"scale={1080*2}:{alto*2}:force_original_aspect_ratio=increase,"
                f"crop={1080*2}:{alto*2},"
                f"zoompan=z='{z}':x='(iw-iw/zoom)*{ax:.2f}':y='(ih-ih/zoom)*{ay:.2f}'"
                f":d={frames}:s=1080x{alto}:fps={fps},"
                f"pad=1080:1920:0:0:color={COLOR_PANEL},"
                f"drawbox=x=0:y={alto}:w=1080:h=8:color={acento}@1:t=fill")
        inputs = ["-i", str(src)]
        tflag = ["-frames:v", str(frames)]

    else:
        frames = max(1, round(dur * fps))
        ax, ay, direction = CAMARAS[idx % len(CAMARAS)]
        if tipo in ("punch", "cta"):
            # PUNCH-IN: entra ya cerrado y sigue apretando rapido. El salto
            # brusco de escala en el remate es el golpe de dopamina mas
            # barato que existe en edicion.
            z = f"min(zoom+{0.30 / frames:.6f},1.45)"
            ax = ay = 0.5
            inicio = 1.18
            z = f"max({inicio},{z})"
        elif direction == "in":
            z = f"min(zoom+{0.15 / frames:.6f},1.15)"
        else:
            z = f"if(eq(on,1),1.2,max(zoom-{0.2 / frames:.6f},1.0))"
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
        # MarginV=420: centra el texto dentro del panel oscuro (que va de
        # y=1152 a y=1920). A 560 quedaba pegado al borde de la imagen y
        # dejaba un vacio negro enorme debajo. Los ~600px inferiores de un
        # Reel los tapa la interfaz, y este valor sigue por encima de eso.
        "Style: Default,DejaVu Sans,64,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,70,70,420,1",
        "Style: Hook,DejaVu Sans,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,0,2,70,70,420,1",
        "Style: Punch,DejaVu Sans,72,&H0000FFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,0,2,70,70,420,1",
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
    for (t, p) in sfx_cues:
        p = Path(p)
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

    # sidechaincompress exige MISMO formato en sus dos entradas. La voz de
    # Gemini llega a 24 kHz y la musica de MusicGen a 32 kHz.
    # OJO: no forzar channel_layouts=stereo. Ambas fuentes son mono y el
    # upmix a estereo reparte la potencia entre canales: le quitaba 3 dB a
    # la voz y el video acababa sonando MAS BAJO que la narracion sola.
    FMT = "aformat=sample_fmts=fltp:sample_rates=48000"

    if music:
        # Ducking: la musica baja sola mientras hay voz y vuelve a subir en
        # las pausas. Es lo que separa un video producido de uno amateur.
        # La voz se duplica: una copia se mezcla y otra dispara el compresor.
        fc += f";[{aidx}:a]{FMT},volume=1.0,asplit=2[a0][vref]"
        # threshold alto y ratio moderado: con threshold=0.02 y ratio=6 la
        # musica quedaba comprimida SIEMPRE, no solo bajo la voz, y
        # desaparecia de la mezcla.
        fc += (f";[{midx}:a]{FMT},volume={music_vol:.3f}[mus]"
               f";[mus][vref]sidechaincompress="
               f"threshold=0.1:ratio=4:attack=20:release=500:makeup=1[a1]")
        maps = ["[a0]", "[a1]"]
    else:
        fc += f";[{aidx}:a]{FMT},volume=1.0[a0]"
        maps = ["[a0]"]
    for j, (t, idx) in enumerate(sfx_list):
        ms = int(t * 1000)
        fc += f";[{idx}:a]adelay={ms}|{ms},volume=0.9[s{j}]"
        maps.append(f"[s{j}]")
    # alimiter deja 1 dB de margen: al sumar voz + musica + SFX el pico
    # llegaba a 0.0 dB, que es saturacion. Las plataformas piden headroom.
    fc += (f";{''.join(maps)}amix=inputs={len(maps)}:normalize=0:duration=first"
           f",alimiter=limit=0.89:level=disabled[aout]")

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
