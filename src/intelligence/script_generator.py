"""Guionista de COMEDIA financiera: beats tipados (punch/dato) + expansion + rewrite."""
import csv
import re
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from src.llm import chat_json
from .matrix_generator import cargar_matrix

log = logging.getLogger("VideoFactory.Intelligence")

PROHIBIDAS = [
    "ganar dinero rápido", "hazte rico", "inversión garantizada",
    "rendimiento asegurado", "duplica tu dinero", "sin riesgo",
    "libertad financiera en", "secreto que los bancos",
]
LECTURA_PROHIBIDA = [
    "en este video", "a continuacion", "en conclusion", "es importante mencionar",
    "como hemos visto", "por lo tanto", "en primer lugar", "estimados",
    "hoy vamos a hablar", "vamos a analizar", "de manera adecuada",
    "herramienta util", "queridos amigos", "sin mas preambulos",
    "como sabemos", "cabe destacar",
]

SYSTEM_PROMPT = """Eres guionista de COMEDIA financiera viral en español.
Haces reir Y ensenas: el espectador se rie y se lleva una leccion real de dinero.
FORMATO: lineas (beats) de 5-12 palabras, MAXIMO 14. Cada beat es un objeto {"t": texto, "k": tipo}.
Tipos k: "normal" | "punch" (momento de risa) | "dato" (numero que ensena).
TECNICAS DE COMEDIA OBLIGATORIAS:
- Regla de 3: dos lineas serias + tercera exagerada/absurda (k=punch).
- Autodesprecio o situacion cotidiana exagerada.
- Callback: al final, referencia al hook.
- Un dato real de finanzas cada 3-4 lineas (k=dato).
ESCALADA OBLIGATORIA (regla MrBeast): el video no puede mantener el mismo
nivel toda la pieza. Cada bloque sube la apuesta respecto al anterior: mas
incomodo, mas concreto o mas absurdo. El ultimo tercio es el mas fuerte.
REGLA DEL EXTRANO: por cada linea preguntate si a alguien que no te conoce le
importaria lo que se dice ahi. Si la respuesta es no, esa linea no se escribe.
PROHIBIDO tono de ensayo: "en este video", "a continuacion", "por lo tanto", "es importante".
PROHIBIDO escribir acotaciones: nada de "(SFX: ...)", "[musica]", "*sonido*", "PLANO:", "CAMARA:".
Cada beat es SOLO lo que se dice en voz alta. Nunca repitas un beat.
HOOK (primeros 3s): TIENE QUE ROMPER EL SCROLL. Nada de tibio ni amable.
FAMILIAS DE HOOK (se te indicara cual usar; respetala):
- dolor: nombra la herida con una cifra o un plazo concreto.
    "Llevas cinco años cobrando puntual y sigues sin un mes de colchon."
- advertencia: intercepta algo que el espectador iba a hacer.
    "Si vas a pedir un prestamo este mes, mira esto antes."
- comparacion: enfrenta dos opciones REALES que el espectador esta sopesando
  de verdad, ambas defendibles. Si las dos son malas no hay dilema y nadie
  opina; eso NO es una comparacion.
    BIEN: "Que es mejor: pagar la deuda o ahorrar primero. La respuesta incomoda."
    MAL:  "Que es mejor: gastar en cafe caro o llorar viendo tu cuenta."
- diferencia: abre un hueco de conocimiento que da verguenza no tener.
    "La diferencia entre ahorrar e invertir. Casi nadie la sabe y por eso sigue igual."
- prohibicion: el miedo a estar cometiendo el error ahora mismo.
    "Nunca metas ahi tus ahorros. Es lo peor que puedes hacer con tu dinero."
Reglas del hook:
- Habla de TU, directo, acusador. Nunca "muchas personas" ni "todos alguna vez".
- Nombra la herida con precision incomoda: la cifra, el numero de años, el
  detalle que el espectador reconoce y le arde. Ataca la SITUACION, nunca a la
  persona: si insultas al espectador se va; si le nombras su realidad, se queda.
- Cero introduccion, cero saludo, cero contexto. Empieza en el golpe.
- Prohibido suavizar con "quiza", "tal vez", "puede que".
EJEMPLOS del nivel que se pide:
  "Llevas seis años trabajando y no aguantas un mes sin sueldo."
  "Tu jefe sabe que no puedes renunciar. Por eso te trata asi."
  "Vas a llegar a los cuarenta con la misma cuenta que a los veinte."
  "Ganas mas que hace tres años y estas igual de quebrado."
NIVEL PROHIBIDO (demasiado blando, no usar):
  "Cobras tu quincena y desaparece."   <- es una observacion, no duele
  "El dinero se va volando."           <- topico sin filo
PROHIBIDO repetir el hook en los primeros beats. El hook ya se dijo: los beats
siguientes AVANZAN la historia, no la vuelven a contar troceada.
ESTRUCTURA: hook → setup (2-3) → 3 bloques comicos con dato → callback → CTA.
TOTAL: 20-24 beats, 190-215 palabras. Minimo 4 beats k=punch y 3 k=dato.
EJEMPLO DEL TONO EXACTO:
  {"t": "Llegas al 15.", "k": "normal"}
  {"t": "Tu cartera: vacia.", "k": "normal"}
  {"t": "Tu corazon: lleno de esperanza.", "k": "punch"}
  {"t": "La esperanza no paga la renta.", "k": "punch"}
  {"t": "La mitad de tu quincena se va en lo fijo.", "k": "dato"}
  {"t": "Renta, luz, super.", "k": "normal"}
  {"t": "El 30 en antojos que ni recuerdas.", "k": "dato"}
  {"t": "Cafe de 60, taxi, la app de comida.", "k": "normal"}
  {"t": "Tu cafe ya tiene su propio credito.", "k": "punch"}
Responde UNICAMENTE JSON valido:
{
  "titulo": "maximo 8 palabras",
  "tipo_hook": "dolor | advertencia | comparacion | diferencia | prohibicion",
  "estructura_usada": "comedia-regla3",
  "hook": "8-15 palabras",
  "beats": [{"t": "linea 5-12 palabras", "k": "normal|punch|dato"}, "..."],
  "cta": "maximo 20 palabras",
  "escenas": [{"keyword": "stock search words english", "accion": "que hace el personaje en este escenario", "prompt_imagen": "english description"}],
  "hashtags": ["maximo 5"]
}"""

SYSTEM_PROMPT_EXPAND = """Eres editor de guiones de comedia financiera en español.
El total final DEBE quedar entre 200 y 250 palabras.
Agrega los beats NUEVOS necesarios (8-12 objetos {"t","k"} de 5-12 palabras)
con regla de 3 y datos reales, hasta alcanzar el total.
NO cambies hook, CTA, titulo ni tema.
Devuelve el MISMO JSON completo con "beats" ampliado.
Responde UNICAMENTE JSON valido."""


FAMILIAS_HOOK = ["dolor", "advertencia", "comparacion", "diferencia", "prohibicion"]


def _familias_recientes(n=6):
    """Familias de hook usadas ultimamente, para no repetir siempre la misma.

    Publicando a diario, si todos los videos abren igual la audiencia aprende
    a reconocer el patron y desliza antes del segundo uno. La variedad del
    hook no es estetica: es supervivencia.
    """
    ruta = Path("output/intelligence/scores_log.csv")
    if not ruta.exists():
        return []
    try:
        with open(ruta, newline="", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
        return [(r.get("tipo_hook") or "").strip().lower() for r in filas[-n:]]
    except Exception:
        return []


def _siguiente_familia():
    usadas = _familias_recientes()
    libres = [f for f in FAMILIAS_HOOK if f not in usadas]
    if libres:
        return libres[0]
    # todas usadas hace poco: la menos reciente
    for f in FAMILIAS_HOOK:
        if f not in usadas[-3:]:
            return f
    return FAMILIAS_HOOK[0]


def generar_guiones_desde_matrix(n=3, tema_semana=None):
    matrix = cargar_matrix()
    matrix_txt = json.dumps(matrix, ensure_ascii=False)
    tema_txt = f"Tema sugerido: {tema_semana}" if tema_semana else "Elige tu un tema de finanzas personales"

    base = _siguiente_familia()
    orden = FAMILIAS_HOOK[FAMILIAS_HOOK.index(base):] + FAMILIAS_HOOK[:FAMILIAS_HOOK.index(base)]
    log.info(f"Familias de hook para hoy: {orden[:n]} (recientes: {_familias_recientes()})")

    validos = []
    for i in range(n):
        familia = orden[i % len(orden)]
        try:
            g = chat_json(
                SYSTEM_PROMPT,
                f"MATRIX DE VIRALIDAD:\n{matrix_txt}\n{tema_txt}\n\n"
                f"FAMILIA DE HOOK OBLIGATORIA PARA ESTE GUION: {familia}\n"
                f"Escribe el guion COMICO #{i+1} de hoy. JSON de UN solo guion:",
                temperature=0.9, max_tokens=8000)
        except Exception as e:
            log.warning(f"Guion #{i+1} fallo al generar: {e}")
            continue
        g = _validar_y_ajustar(g)
        if g:
            validos.append(g)

    log.info(f"{len(validos)}/{n} guiones validos generados")
    return validos


def aplicar_cambios(g, cambios):
    try:
        g2 = chat_json(
            SYSTEM_PROMPT,
            "REESCRIBE este guion aplicando ESTOS cambios del showrunner:\n"
            + "\n".join(f"- {c}" for c in cambios)
            + f"\n\nGUION ACTUAL:\n{json.dumps(g, ensure_ascii=False)}\nDevuelve el JSON completo corregido.",
            temperature=0.8, max_tokens=8000)
        return _validar_y_ajustar(g2)
    except Exception as e:
        log.warning(f"Rewrite del showrunner fallo: {e}")
        return None


# Acotaciones de guion que el LLM cuela dentro de los beats. Si no se
# filtran, se NARRAN en voz alta y aparecen en los subtitulos: llego a salir
# "*(SFX: Caja registradora cayendo y llanto)*" cinco veces en un video.
# OJO al orden: primero se limpia el formato y DESPUES se evalua. Si se hace
# al reves, "**Y el resto en antojos.**" (negrita de markdown) se confunde con
# una acotacion y se pierde un chiste bueno.
ACOTACION = re.compile(
    r"^\((?![^)]*\b(que|de|la|el|y|a)\b\s).*\)$"   # frase entera entre parentesis
    r"|^\[.*\]$"                                    # frase entera entre corchetes
    r"|\b(sfx|efecto de sonido|voz en off|plano|c[aá]mara|escena)\s*:"
    # los dos puntos deben ir PEGADOS: "Musica:" es acotacion, pero
    # "Musica para tus oidos: ya no debes nada" es una frase legitima.
    r"|^\s*(m[uú]sica|sonido)\s*:",
    re.IGNORECASE)


def _limpiar_texto(t):
    """Quita marcas de formato sueltas que el LLM añade (asteriscos, guiones)."""
    return re.sub(r"^[\*\-–\s]+|[\*\s]+$", "", t).strip()


def _normalizar_beats(g):
    out = []
    vistos = set()
    for b in (g.get("beats") or []):
        if isinstance(b, dict):
            t = (b.get("t") or "").strip()
            k = b.get("k") if b.get("k") in ("normal", "punch", "dato") else "normal"
        else:
            t = str(b).strip()
            k = "normal"
        t = _limpiar_texto(t)
        if not t or ACOTACION.search(t):
            continue
        clave = t.lower()
        if not t or clave in vistos:      # sin repetidos: aburren y gastan segundos
            continue
        vistos.add(clave)
        out.append({"t": t, "k": k})
    if not out and g.get("guion"):
        out = [{"t": f.strip(), "k": "normal"}
               for f in re.split(r"(?<=[.!?])\s+", g["guion"]) if f.strip()]
    return out


def _palabras_utiles(texto):
    return {p.strip(".,;:¡!¿?\"'").lower() for p in texto.split() if len(p) > 3}


def _quitar_eco_del_hook(hook, beats, umbral=0.7, ventana=4):
    """Elimina los primeros beats que solo repiten el hook troceado.

    Caso real detectado escuchando el video: hook "Cobras tu quincena, pagas
    deudas y te quedan diez pesos", y a continuacion los beats "Cobras tu
    quincena." / "Pagas deudas." / "Te quedan diez pesos...". Los primeros 10
    segundos decian lo mismo dos veces, justo donde se decide la retencion.

    El umbral es 0.7 y no 0.6 a proposito: "Te quedan diez pesos y mucha
    dignidad" comparte el 60% con el hook pero aporta el remate comico, y a
    0.6 se perdia el chiste. Mejor dejar pasar un eco leve que borrar un
    punchline.
    """
    if not hook:
        return beats
    ph = _palabras_utiles(hook)
    if not ph:
        return beats
    limpios = list(beats)
    quitados = 0
    while limpios and quitados < ventana:
        pb = _palabras_utiles(limpios[0]["t"])
        if pb and len(ph & pb) / len(pb) >= umbral:
            log.info(f"Beat que repite el hook, fuera: {limpios[0]['t']!r}")
            limpios.pop(0)
            quitados += 1
        else:
            break
    return limpios


def _validar_y_ajustar(g):
    if not isinstance(g, dict):
        return None
    beats = _normalizar_beats(g)
    if not beats:
        return None
    beats = _quitar_eco_del_hook(g.get("hook", ""), beats)
    if not beats:
        return None
    palabras = sum(len(b["t"].split()) for b in beats)

    # ~3,2 palabras/segundo a 1.5x => 70s ≈ 225 palabras
    intentos = 0
    while palabras < 190 and intentos < 3:
        intentos += 1
        log.info(f"Guion corto ({palabras} palabras). Expansion {intentos}/3...")
        try:
            g2 = chat_json(
                SYSTEM_PROMPT_EXPAND,
                f"TOTAL OBJETIVO: 200-250 palabras. ACTUAL: {palabras}.\nGUION:\n{json.dumps(g, ensure_ascii=False)}",
                temperature=0.7, max_tokens=8000)
            if isinstance(g2, dict):
                g = {**g, **g2}
                beats = _normalizar_beats(g)
        except Exception as e:
            log.warning(f"Expansion fallo: {e}")
        palabras = sum(len(b["t"].split()) for b in beats)

    texto = (g.get("hook", "") + " " + " ".join(b["t"] for b in beats) + " " + g.get("titulo", "")).lower()
    if any(p in texto for p in PROHIBIDAS):
        log.warning(f"Guion '{g.get('titulo')}' descartado: frase prohibida")
        return None
    if any(p in texto for p in LECTURA_PROHIBIDA):
        log.warning(f"Guion '{g.get('titulo')}' descartado: tono de lectura")
        return None
    # medido: 251 palabras dieron 84.7s. ~2,96 palabras/segundo => 70s ≈ 207.
    # El techo se sube a 250 porque los guiones agresivos salen mas densos y
    # se rechazaban 2 de cada 3 por pasarse cinco palabras: tirar buen
    # material sale mas caro que un video de 82s en vez de 75s.
    if not (170 <= palabras <= 250):
        log.warning(f"Guion '{g.get('titulo')}' con {palabras} palabras fuera de rango (170-250)")
        return None
    largos = [b for b in beats if len(b["t"].split()) > 16]
    if len(largos) > 2:
        log.warning(f"Guion '{g.get('titulo')}' con ritmo de lectura")
        return None
    if sum(1 for b in beats if b["k"] == "punch") < 2:
        log.warning(f"Guion '{g.get('titulo')}' sin suficientes punchlines")
        return None

    g["beats"] = beats
    g["guion"] = "\n".join(b["t"] for b in beats)
    g["_palabras"] = palabras
    return g


def get_next_topic():
    if not Path("topics.csv").exists():
        return None
    usados = set()
    log_file = Path("output/published_log.csv")
    if log_file.exists():
        with open(log_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                usados.add(row.get("tema_hash", ""))
    with open("topics.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tema = (row.get("tema") or "").strip()
            if tema and hashlib.md5(tema.encode()).hexdigest()[:8] not in usados:
                return tema
    return None


def registrar_publicacion(guion, score, url=""):
    log_file = Path("output/published_log.csv")
    existe = log_file.exists()
    tema = guion.get("_tema") or guion.get("titulo", "")
    tema_hash = hashlib.md5(tema.encode()).hexdigest()[:8]
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not existe:
            w.writerow(["fecha", "titulo", "tema_hash", "score", "url"])
        w.writerow([datetime.now().strftime("%Y%m%d"), guion.get("titulo", ""),
                    tema_hash, score, url])

    scores_file = Path("output/intelligence/scores_log.csv")
    existe2 = scores_file.exists()
    with open(scores_file, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not existe2:
            w.writerow(["fecha", "titulo", "tipo_hook", "estructura", "score_simulado"])
        w.writerow([datetime.now().strftime("%Y%m%d"), guion.get("titulo", ""),
                    guion.get("tipo_hook", ""), guion.get("estructura_usada", ""), score])
