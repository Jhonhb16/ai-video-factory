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

# En ASS el color va en BGR, al reves que en HTML. Resaltado de la palabra
# que suena en ese instante, segun el tipo de beat.
COLOR_ASS = {"punch": "&H00FFFF&", "dato": "&H9AE322&", "hook": "&H57C8FF&",
             "cta": "&H9AE322&", "normal": "&H9AE322&"}


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
            imagen = images[p["idx"] % len(images)]
            # Las tarjetas de cifra se generan animadas (la cifra CUENTA hasta
            # su valor). Si existe el mp4 hermano de la imagen, ese plano entra
            # por la via de video en vez de por la de imagen fija.
            animada = imagen.with_suffix(".mp4")
            if animada.exists():
                jobs.append(("clip", animada, 0, s, pose, dur, p["k"]))
            else:
                modo = "img_panel" if maqueta == "panel" else "img"
                jobs.append((modo, imagen, 0, s, pose, dur, p["k"]))

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

    try:
        from src.alineador import palabras_por_frase
        reparto = palabras_por_frase(items, audio)
    except Exception as e:
        log.warning(f"Sin timing por palabra ({str(e)[:80]}); rotulos por frase.")
        reparto = None
    _generar_subtitulos(items, reparto)

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
        # La apertura hablada se trocea en varios encuadres del MISMO render:
        # general, medio y primer plano. Mario lo detecto viendo el video —
        # 11 segundos sin un solo corte, y justo al inicio, que es donde se
        # decide si alguien se queda. Es el "zoom cut" de toda la vida: un
        # salto de escala despierta al cerebro y no cuesta ni un centavo,
        # porque sale del mismo material.
        ENCUADRES_HOOK = [
            (1.00, 0.50),   # general
            (1.32, 0.42),   # medio, ligeramente arriba
            (1.62, 0.36),   # primer plano
            (1.18, 0.46),   # vuelta a medio
        ]
        # La apertura obedece la MISMA maqueta que el resto: si no, los
        # primeros segundos llevan otra reticula y el video se contradice a si
        # mismo a los diez segundos. Aqui se quedo la version vieja (imagen
        # recortada + panel solido) cuando el resto ya pintaba a sangre.
        vf = (f"scale=1080:1920:force_original_aspect_ratio=increase,"
              f"crop=1080:1920,setsar=1,fps={fps}")
        maqueta = (load_config().get("contenido", {}) or {}).get("maqueta", "panel")
        capa_hook = None
        if maqueta == "panel":
            from src.degradado import asegurar as asegurar_degradado
            capa_hook = asegurar_degradado()
        # ALTERNAR con planos de recurso. Antes se troceaba el mismo render en
        # tres encuadres, pero seguia siendo LA MISMA IMAGEN 11 segundos:
        # cambiaba la escala, no lo que se ve. Ahora la cabeza parlante se
        # intercala con las escenas que esos planos iban a mostrar, que es lo
        # que hace cualquier montaje real: el presentador habla y se corta a
        # imagen de apoyo mientras su voz sigue.
        n_trozos = max(2, min(5, int(dur_hook / 2.4)))
        paso = dur_hook / n_trozos

        # Los planos de recurso se cogen de LEJOS en la secuencia, no de los
        # inmediatamente siguientes: el planificador suele dar escenas muy
        # parecidas a beats consecutivos, asi que cortar al de al lado cambia
        # el plano pero no lo que se ve. Al final vuelven a aparecer en su
        # sitio, y verlos antes funciona como adelanto de lo que viene.
        lejanos = [segments[i] for i in
                   (corte + 4, corte + 9, corte + 14, corte + 6)
                   if i < len(segments)]
        recursos = lejanos or [segments[i] for i in range(1, min(corte, len(segments)))]
        trozos = []
        for t in range(n_trozos):
            # impares = plano de recurso, si hay; pares = cabeza parlante
            if t % 2 == 1 and recursos:
                origen = recursos[(t // 2) % len(recursos)]
                parte = seg_dir / f"seg_hook_{t}.mp4"
                run_cmd(["ffmpeg", "-y", "-stream_loop", "1", "-i", str(origen),
                         "-t", f"{paso:.3f}", "-an",
                         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                         "-pix_fmt", "yuv420p", str(parte)])
                trozos.append(parte)
                continue
            zoom, centro_y = ENCUADRES_HOOK[t % len(ENCUADRES_HOOK)]
            recorte = ("" if zoom <= 1.001 else
                       f"crop=iw/{zoom:.2f}:ih/{zoom:.2f}:"
                       f"(iw-iw/{zoom:.2f})/2:(ih-ih/{zoom:.2f})*{centro_y:.2f},")

            # WHIP: el plano entra sobredimensionado y se clava en 4 fotogramas.
            # tmix mezcla fotogramas consecutivos: sobre un plano quieto no
            # cambia nada, pero sobre este movimiento brusco genera el motion
            # blur de verdad. Asi el corte se SIENTE, en vez de ser un salto seco.
            if t > 0:
                frames_totales = max(2, int(paso * fps))
                golpe = (f"zoompan=z='if(lt(on,4),1.5-on*0.125,1.0)'"
                         f":x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
                         f":d={frames_totales}:s=1080x1920:fps={fps},"
                         f"tmix=frames=3:weights='1 1 1',")
            else:
                golpe = ""

            parte = seg_dir / f"seg_hook_{t}.mp4"
            cadena = recorte + vf + ("," + golpe.rstrip(",") if golpe else "")
            cmd = ["ffmpeg", "-y", "-ss", f"{t*paso:.3f}", "-i", str(hook)]
            if capa_hook:
                # El degradado entra como input aparte y se superpone al final.
                # eof_action=repeat: es un PNG de un solo fotograma y tiene que
                # aguantar todo el trozo.
                cmd += ["-i", str(capa_hook), "-filter_complex",
                        f"[0:v]{cadena}[b];[b][1:v]overlay=0:0:eof_action=repeat[v]",
                        "-map", "[v]"]
            else:
                cmd += ["-vf", cadena]
            cmd += ["-t", f"{paso:.3f}",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(parte)]
            run_cmd(cmd)
            trozos.append(parte)

        real = sum(get_duration(p) for p in trozos)
        if abs(real - dur_hook) > 0.35:
            log.warning(f"El hook hablado quedo en {real:.2f}s en vez de "
                        f"{dur_hook:.2f}s; se descarta para no desincronizar.")
            return segments

        hablados = sum(1 for t in range(n_trozos) if t % 2 == 0 or not recursos)
        log.info(f"Apertura: {n_trozos} planos de ~{paso:.1f}s "
                 f"({hablados} hablando, {n_trozos-hablados} de recurso)")
        return trozos + segments[corte:]

    except Exception as e:
        log.warning(f"No se pudo aplicar la apertura hablada ({e}); sigue normal.")
        return segments


def _render(job, fps, seg_dir):
    kind, src, off, idx, pose, dur, tipo = job
    out = seg_dir / f"seg_{idx:03d}.mp4"
    mascot = MASCOT_DIR / f"{pose}.png"
    has_m = mascot.exists()
    degradado = None

    if kind == "clip":
        base = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
        inputs = ["-stream_loop", "1", "-ss", f"{off:.2f}", "-i", str(src)]
        tflag = ["-t", f"{dur:.2f}"]
    elif kind == "img_panel":
        # Maqueta B: la imagen ocupa TODO el cuadro y el texto se apoya sobre
        # una caida a oscuro en el tercio inferior. Asi no se pierde imagen
        # (la A recortaba el 40% del alto) y queda sitio arriba para los
        # golpes tipograficos.
        from src.degradado import asegurar as asegurar_degradado
        frames = max(1, round(dur * fps))
        ax, ay, direction = CAMARAS[idx % len(CAMARAS)]
        ay = min(ay, 0.35)
        avance = 0.22 if tipo in ("punch", "cta") else 0.12
        z = f"min(zoom+{avance/frames:.6f},{1.0+avance:.2f})"
        capa = asegurar_degradado()

        base = (f"scale={1080*2}:{1920*2}:force_original_aspect_ratio=increase,"
                f"crop={1080*2}:{1920*2},"
                f"zoompan=z='{z}':x='(iw-iw/zoom)*{ax:.2f}':y='(ih-ih/zoom)*{ay:.2f}'"
                f":d={frames}:s=1080x1920:fps={fps}")
        inputs = ["-i", str(src)]
        tflag = ["-frames:v", str(frames)]
        degradado = capa

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
    elif degradado:
        # el degradado va como entrada aparte, no dentro de base: aqui es
        # donde se arma el filtergraph completo
        n_capa = len([a for a in inputs if a == "-i"])
        inputs += ["-i", str(degradado)]
        fc = f"[0:v]{base}[b];[b][{n_capa}:v]overlay=0:0[v]"
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


def _ass_ts(s):
    s = max(0.0, s)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}:{m:02d}:{s % 60:05.2f}"


def _palabra_golpe(texto):
    """La palabra que se muestra en gigante. La cifra manda; si no, la mas
    larga, que suele ser la que carga el significado."""
    try:
        from src.cifras import analizar
        info = analizar(texto)
        if info.get("expresion"):
            return info["expresion"].strip()
    except Exception:
        pass
    palabras = [p.strip(".,;:¡!¿?\"'") for p in texto.split()]
    utiles = [p for p in palabras if len(p) > 4]
    return max(utiles, key=len) if utiles else (palabras[-1] if palabras else "")


def _golpes_tipograficos(items):
    """Palabra clave GIGANTE sobre la imagen, solo en los remates.

    Va en la zona alta del cuadro, que es donde suele haber fondo y no cara.
    No sustituye al panel: convive con el. Abajo se lee la frase entera —
    importante para quien ve sin sonido— y arriba entra el golpe grafico.
    """
    eventos = []
    posiciones = [(300, 330), (760, 300), (400, 300), (700, 350)]
    n = 0
    for it in items:
        if it.get("k") not in ("punch", "cta"):
            continue
        palabra = _palabra_golpe(it["txt"]).upper()
        if not palabra or len(palabra) > 16:
            continue
        x, y = posiciones[n % len(posiciones)]
        n += 1
        ini = it["start"] + 0.06
        fin = min(it["end"] - 0.05, ini + 1.25)
        if fin <= ini:
            continue
        eventos.append(
            f"Dialogue: 0,{_ass_ts(ini)},{_ass_ts(fin)},Golpe,,0,0,0,,"
            f"{{\\pos({x},{y})\\fscx55\\fscy55\\alpha&H60&\\frz{-4 + (n % 3) * 4}"
            f"\\t(0,140,\\fscx100\\fscy100\\alpha&H00&)"
            f"\\t({int((fin-ini)*1000)-160},{int((fin-ini)*1000)},\\alpha&HFF&)}}"
            f"{palabra}")
    return eventos


def _generar_subtitulos_cineticos(items, reparto):
    """Rotulos que aparecen PALABRA A PALABRA, cada una a su tiempo real.

    No es un subtitulo: es motion graphics. Cada palabra entra con un golpe
    de escala en el instante exacto en que se pronuncia, y la que suena se
    resalta. Esto solo es posible porque el alineador da el timing por
    palabra; con tiempos estimados habria que inventarse el ritmo y se notaria.

    Se emite una linea por palabra con la frase entera, resaltando la actual.
    Son muchas lineas pero libass las gestiona sin problema.
    """
    eventos = []
    for n, (it, palabras) in enumerate(zip(items, reparto)):
        if not palabras:
            continue
        # tope duro: la frase no puede seguir en pantalla cuando entra la
        # siguiente, o se pisan dos textos a la vez
        tope = items[n + 1]["start"] if n + 1 < len(items) else it["end"]
        tipo = it.get("k", "normal")
        estilo = "Punch" if tipo == "punch" else ("Hook" if tipo == "hook" else "Default")
        realce = COLOR_ASS.get(tipo, COLOR_ASS["normal"])
        textos = [p[2] for p in palabras]

        for i, (ini, fin, _) in enumerate(palabras):
            sig = palabras[i + 1][0] if i + 1 < len(palabras) else min(it["end"], tope)
            sig = min(sig, tope)
            # Nada de duracion minima: estirar una palabra corta la hacia
            # solaparse con la siguiente y se veian los dos textos encima.
            # Si la palabra dura un parpadeo, no se dibuja: la linea siguiente
            # ya la lleva escrita, solo sin el realce.
            if sig - ini < 0.05:
                continue
            partes = []
            for j, w in enumerate(textos):
                if j > i:
                    break                      # aun no se ha dicho
                if j == i:
                    # golpe de escala en la palabra que suena ahora
                    partes.append(
                        f"{{\\c{realce}\\fscx118\\fscy118"
                        f"\\t(0,110,\\fscx100\\fscy100)}}{w}{{\\r{estilo}}}")
                else:
                    partes.append(w)
            eventos.append(
                f"Dialogue: 0,{_ass_ts(ini)},{_ass_ts(sig)},"
                f"{estilo},,0,0,0,,{' '.join(partes)}")
    return eventos


def _generar_subtitulos(items, reparto=None):
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
        # Golpe: palabra clave gigante sobre la imagen, en los remates.
        # Alineacion 5 (centrado) porque se posiciona a mano con \pos.
        "Style: Golpe,DejaVu Sans,150,&H00FFFFFF,&H000000FF,&H00202020,&HA0000000,1,0,0,0,100,100,2,0,1,7,3,5,0,0,0,1",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    # Con timing por palabra se animan; sin el, se cae al subtitulo por frase.
    cineticos = _generar_subtitulos_cineticos(items, reparto) if reparto else []
    if cineticos:
        lines += cineticos
        golpes = _golpes_tipograficos(items)
        lines += golpes
        log.info(f"Rotulos cineticos: {len(cineticos)} palabras animadas "
                 f"en {sum(1 for r in reparto if r)} frases, "
                 f"{len(golpes)} golpes tipograficos")
    else:
        for it in items:
            style = {"hook": "Hook", "punch": "Punch",
                     "cta": "Punch"}.get(it["k"], "Default")
            lines.append(f"Dialogue: 0,{_ts(it['start'])},{_ts(it['end'])},"
                         f"{style},,0,0,0,,{it['txt']}")
        log.info(f"Subtitulos con enfasis: {len(items)} lineas")
    (MEDIA_DIR / "subs.ass").write_text("\n".join(lines), encoding="utf-8")


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
