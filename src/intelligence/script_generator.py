"""Guionista de COMEDIA financiera: beats tipados (punch/dato) + expansion + rewrite."""
import csv
import re
import unicodedata
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
# Ejemplos tan usados en contenido de finanzas que ya no dicen nada. El
# concepto los penaliza, pero se colaban DENTRO de los guiones igualmente.
EJEMPLOS_QUEMADOS = [
    "cafe diario", "café diario", "el cafe de cada", "el café de cada",
    "gasto hormiga", "gastos hormiga", "regla 50/30/20", "regla 50 30 20",
    "metodo de sobres", "método de sobres", "pagate a ti mismo primero",
    "págate a ti mismo primero",
]
# Dos lineas rojas del nicho de migrantes. La primera son metaforas de
# autolesion, que las plataformas penalizan y que ademas se burlan de una
# situacion real. La segunda es insultar al espectador por mandarle dinero a
# su familia: el LLM lo hizo solo ("el altruismo estupido destruye tu futuro")
# pese a que el prompt ya pedia atacar la situacion y no a la persona. Una
# instruccion que se puede ignorar no es una regla; esto si se comprueba.
VETO_TONO = [
    "suicid", "matarte", "matandote", "morirte de hambre", "muriendote de hambre",
    "altruismo estupido", "altruismo tonto", "eres tonto", "eres estupido",
    "eres un ingenuo", "por pendejo", "por tonto", "por estupido",
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

=== LO MAS IMPORTANTE: EL HILO ===
El guion NO es una lista de frases ingeniosas sobre un tema. Es UNA historia
o UN argumento que AVANZA. Cada beat tiene que aportar informacion nueva.
PROHIBIDO decir lo mismo de cuatro formas distintas. Ejemplo de lo que NO se
puede hacer, todo seguido:
  "Llevas cinco años cobrando y sigues sin colchon."
  "Vives esperando el deposito como si fuera un milagro."
  "Llega el dinero, respiras y a los tres dias vuela."
  "Tu cuenta parece zona de guerra."
Son cuatro maneras de decir "no te alcanza". El espectador ya lo entendio en
la primera y se va, porque nada le promete algo que todavia no sabe.

MICRO-HOOKS OBLIGATORIOS (minimo 2): promesas sembradas que solo se pagan mas
adelante, para dar una razon concreta de seguir viendo.
  "Son tres fugas. La tercera es la que te esta costando el sueldo entero."
  "Y hay un numero que no te van a decir en el banco. Va al final."
  "Lo peor no es eso. Lo peor viene en diez segundos."
Cada micro-hook sembrado SE PAGA despues, sin excepcion. Prometer y no
cumplir quema al espectador para siempre.
Los ejemplos de arriba son PATRONES, no frases para copiar. PROHIBIDO usar
literalmente "lo peor viene ahora mismo", "hay un numero que no te van a
decir" o cualquier otra formula de este prompt: se repetirian video tras
video y el canal sonaria a plantilla, que es justo lo que las plataformas
penalizan. Escribe la promesa con las palabras de ESTE guion y de su tema.

=== A QUIEN LE HABLAS: FINANZAS PARA MIGRANTES ===
El publico es hispano viviendo en ESTADOS UNIDOS. Trabaja, manda dinero a su
pais y navega un sistema financiero que no le explicaron nunca. Se le habla
en español, en DOLARES, y de SU realidad diaria:
- Remesas: lo que le cobran por mandar dinero y el tipo de cambio escondido.
- Credito: llegar sin historial, que le nieguen todo, construirlo desde cero.
- Impuestos: declarar con ITIN, el W-2 contra el 1099, el reembolso.
- Banca: por que cambiar el cheque en el supermercado le cuesta una fortuna,
  abrir cuenta sin numero de seguro social.
- Renta: que le pidan historial crediticio que no tiene, el deposito doble.
- Carro: los lotes de "aqui te financiamos" y su interes de usura.
- Estafas dirigidas a el: el "notario" que no es abogado, el que cobra por
  formularios gratis.
- La tension de fondo: mandar todo a casa y no construir nada aqui.

PROHIBIDO el marco de Latinoamerica: la quincena, el 15 y el 30, el arriendo,
el Icetex, el salario minimo colombiano. Ese publico es otro. Aqui se dice
renta y no arriendo, cheque y no quincena, y las cifras van en dolares
creibles para quien gana por hora: una renta de 1.400, un cheque de 800 a la
semana, 15 dolares por cambiar un cheque, 8 por ciento de comision en una
remesa.
NO se asume estatus migratorio ni se dan consejos legales. Se habla de dinero.
El publico NO es solo mexicano: evita modismos de un solo pais.

=== QUIEN ES EL ENEMIGO (regla que no se rompe) ===
El hook es agresivo con el SISTEMA, jamas con el espectador. El villano son
las comisiones, el tipo de cambio escondido, el lote que cobra 29 por ciento,
el banco que le niega todo. NUNCA su decision de mandarle dinero a su madre.
PROHIBIDO llamarle tonto, ingenuo o estupido, y PROHIBIDO tratar el sacrificio
por la familia como un error: para este publico eso no es un gasto, es la
razon de estar aqui. Se le dice que le estan COBRANDO de mas por ayudar, no
que ayudar este mal.
  MAL:  "El altruismo estupido destruye tu futuro."
  MAL:  "No es generosidad, te estas suicidando financieramente."
  BIEN: "Mandas para que ellos esten bien. Ocho por ciento se queda en el camino."
  BIEN: "El problema no es lo que mandas. Es lo que te cobran por mandarlo."
PROHIBIDO el lenguaje de autolesion o muerte como metafora ("suicidarte",
"matarte", "morirte de hambre"): las plataformas lo penalizan y ademas suena
a burla de una situacion real.

DATO EXTRAORDINARIO (minimo 1): una cifra que haga levantar la ceja, concreta
y sorprendente. No sirve "la mitad se va en lo basico", que ya lo sabe todo
el mundo. Sirve el tipo de dato que uno le cuenta a otro:
  "Quince dolares por cambiar el cheque son setecientos veinte al año."
  "Ocho por ciento de comision en cada remesa: mil dolares que nunca llegan."
ESTRUCTURA DEL HILO: hook -> promesa de lo que se va a revelar -> desarrollo
que avanza -> el dato que sorprende -> pago de las promesas -> CIERRE EPICO.

=== EL CIERRE TIENE QUE RESOLVER EL HOOK ===
El hook abre una herida; el final la cierra. Los DOS O TRES ULTIMOS BEATS
deben volver a la ESCENA EXACTA del hook y rematarla. No vale una moraleja
generica: "la regla es simple, si no pagas todo pagas doble" no resuelve
nada, es un consejo de manual y el espectador se queda sin la descarga que
se le prometio.

El cierre epico hace TRES cosas:
1. VUELVE a la misma escena o premisa con la que abriste, con sus palabras.
2. LA REMATA con la consecuencia maxima y una CIFRA concreta.
3. REENCUADRA: lo que parecia una cosa resulta ser otra.

Ejemplo. Hook: "Si vas a pagar el minimo este mes, mira esto antes."
  MAL:  "La regla es simple: si no pagas todo, pagas doble."
  BIEN: "Ese minimo que ibas a pagar hoy son treinta dolares."
        "En tres años habras pagado mil cien por unos tenis de doscientos."
        "El minimo no es una ayuda del banco. Es el negocio del banco."

La ultima linea del guion es la MAS FUERTE de todo el video. Si no lo es,
esta mal colocada.
PROHIBIDO tono de ensayo: "en este video", "a continuacion", "por lo tanto", "es importante".
PROHIBIDO escribir acotaciones: nada de "(SFX: ...)", "[musica]", "*sonido*", "PLANO:", "CAMARA:".
Cada beat es SOLO lo que se dice en voz alta. Nunca repitas un beat.
HOOK (primeros 3s): TIENE QUE ROMPER EL SCROLL. Nada de tibio ni amable.
FAMILIAS DE HOOK (se te indicara cual usar; respetala):
- dolor: nombra la herida con una cifra o un plazo concreto.
    "Llevas cinco años trabajando aqui y no tienes ni un mes guardado."
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
  "Llevas seis años trabajando aqui y el banco te sigue tratando como recien llegado."
  "Mandaste veinte mil dolares a casa y aqui no tienes ni para un mes."
  "Tu jefe sabe que no puedes renunciar. Por eso te trata asi."
  "Pagas renta puntual hace cinco años y no te sirve de nada para comprar."
  "Te cobran quince dolares por darte TU propio dinero."
NIVEL PROHIBIDO (demasiado blando, no usar):
  "Cobras tu cheque y desaparece."     <- es una observacion, no duele
  "El dinero se va volando."           <- topico sin filo
PROHIBIDO repetir el hook en los primeros beats. El hook ya se dijo: los beats
siguientes AVANZAN la historia, no la vuelven a contar troceada.
ESTRUCTURA: hook → setup (2-3) → 3 bloques comicos con dato → callback → CTA.
TOTAL: 20-24 beats, 190-215 palabras. Minimo 4 beats k=punch y 3 k=dato.
EJEMPLO DEL TONO EXACTO:
  {"t": "Viernes. Llega el cheque.", "k": "normal"}
  {"t": "Y antes de tocarlo, ya tiene dueño.", "k": "punch"}
  {"t": "Quince dolares por cambiarlo en el supermercado.", "k": "dato"}
  {"t": "Pagaste por sacar TU dinero.", "k": "punch"}
  {"t": "Cuarenta a la semana son dos mil al año.", "k": "dato"}
  {"t": "Dos mil dolares por no tener una cuenta.", "k": "punch"}
  {"t": "Y si, se puede abrir con ITIN.", "k": "normal"}
  {"t": "Nadie te lo dijo porque nadie gana con que lo sepas.", "k": "punch"}
Responde UNICAMENTE JSON valido:
{
  "titulo": "maximo 8 palabras",
  "tipo_hook": "dolor | advertencia | comparacion | diferencia | prohibicion",
  "estructura_usada": "comedia-regla3",
  "hook": "8-15 palabras",
  "beats": [{"t": "linea 5-12 palabras", "k": "normal|punch|dato"}, "..."],
  "siembras": ["copia EXACTA de los beats que siembran una promesa (minimo 2)"],
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

    validos, crudos = [], []
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
        crudos.append(json.loads(json.dumps(g)))   # copia: validar muta el dict
        g = _validar_y_ajustar(g)
        if g:
            validos.append(g)

    # Red de seguridad: se piden 2 micro-hooks, pero un canal diario no puede
    # quedarse mudo porque hoy ninguno llego. Si no sobrevivio ninguno, se
    # repesca con el liston en 1 antes que no publicar.
    if not validos and crudos:
        rescatados = [x for x in (_validar_y_ajustar(c, min_ganchos=1)
                                  for c in crudos) if x]
        if rescatados:
            log.warning(f"Ningun guion llego a 2 micro-hooks; se repescan "
                        f"{len(rescatados)} con 1. Revisar el prompt si se repite.")
            validos = rescatados

    log.info(f"{len(validos)}/{n} guiones validos generados"
             + (f" (micro-hooks: {[v.get('_microhooks') for v in validos]})"
                if validos else ""))
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


# Marcas de promesa sembrada: dan al espectador una razon concreta de seguir.
#
# OJO con las tildes: los patrones van SIN ellas y el texto del guion viene
# CON ellas, asi que hay que normalizar antes de buscar. Mientras no se hizo,
# "lo peor viene mas adelante" o "el ultimo te va a doler" no contaban como
# micro-hook y los guiones salian con la mitad de los que en realidad tenian.
MICRO_HOOK = re.compile(
    r"\b(el|la)\s+(tercer|tercera|segundo|segunda|ultimo|ultima|peor)\b"
    r"|\bviene\s+(ahora|en|al|lo)\b|\baqui\s+viene\b"
    r"|\bal\s+final\b|\bmas\s+adelante\b|\ben\s+\w+\s+segundos\b"
    r"|\bespera\b|\bpero\s+lo\s+(peor|bueno)\b|\bno\s+te\s+(lo\s+)?(van a |)dicen?\b"
    r"|\bhay\s+(un|una|tres|dos|cuatro)\b.*\b(que|y)\b"
    # promesa explicita de que falta algo
    r"|\b(todavia|aun)\s+(hay|falta|no)\b|\b(y\s+)?eso\s+no\s+es\s+(lo\s+)?(peor|todo)\b"
    r"|\bhay\s+algo\s+(mas|peor)\b|\bfalta\s+lo\s+(peor|mejor)\b"
    r"|\blo\s+que\s+(sigue|viene)\b|\bya\s+vas\s+a\s+ver\b"
    # instruccion directa de quedarse
    r"|\bquedate\b|\bno\s+te\s+vayas\b|\bantes\s+de\s+que\s+te\s+vayas\b"
    r"|\bguarda\s+(este|ese)\s+dato\b|\bpresta\s+atencion\b|\bapunta\b"
    # cuenta atras / enumeracion pendiente
    r"|\bnumero\s+(dos|tres|cuatro|cinco)\b|\bel\s+truco\s+esta\b"
    r"|\ben\s+un\s+momento\b|\bya\s+casi\b",
    re.IGNORECASE)


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto))
                   if unicodedata.category(c) != "Mn")


def _contar_microhooks(beats, siembras=None):
    """Cuantas promesas sembradas hay, por las buenas o por las declaradas.

    La regex sola no vale: solo reconoce las formulas que trae este prompt.
    En cuanto se prohibio copiarlas literalmente (sonaban a plantilla video
    tras video), el LLM siguio sembrando promesas con otras palabras y el
    contador se quedo ciego, tumbando guiones perfectamente buenos.

    Por eso el guionista DECLARA cuales son sus siembras y aqui solo se
    comprueba que existan de verdad entre los beats. Declarar una frase que
    no esta escrita no cuenta, asi que no se puede inflar el numero.
    """
    por_regex = {b["t"] for b in beats if MICRO_HOOK.search(_sin_tildes(b["t"]))}

    textos = {" ".join(_sin_tildes(b["t"]).lower().split()) for b in beats}
    declaradas = set()
    for s in (siembras or []):
        clave = " ".join(_sin_tildes(str(s)).lower().split())
        if clave and clave in textos:
            declaradas.add(clave)

    # se unen sin contar dos veces el mismo beat
    por_regex_norm = {" ".join(_sin_tildes(t).lower().split()) for t in por_regex}
    return len(por_regex_norm | declaradas)


def _redundancia(beats, ventana=4, umbral=0.55):
    """Cuenta beats que repiten LITERALMENTE palabras de otro cercano.

    LIMITE IMPORTANTE: solo detecta repeticion de vocabulario. La repeticion
    que de verdad mata la retencion es la de SIGNIFICADO — decir "sigues sin
    colchon", "esperas el deposito como un milagro", "a los tres dias vuela"
    y "tu cuenta parece zona de guerra" son cuatro formas de decir "no te
    alcanza" sin compartir una sola palabra. Eso no lo puede ver un contador:
    lo juzga el showrunner, que entiende el sentido.
    """
    def utiles(t):
        return {p.strip(".,;:¡!¿?").lower() for p in t.split() if len(p) > 4}

    repetidos = 0
    for i, b in enumerate(beats):
        pa = utiles(b["t"])
        if len(pa) < 3:
            continue
        for j in range(max(0, i - ventana), i):
            pb = utiles(beats[j]["t"])
            if not pb:
                continue
            solape = len(pa & pb) / min(len(pa), len(pb))
            if solape >= umbral:
                repetidos += 1
                break
    return repetidos


def _callback_al_hook(hook, beats, ultimos=4):
    """¿Los ultimos beats vuelven a la escena del hook?

    Se mide por vocabulario compartido con el hook. No es perfecto —un
    callback puede reformular sin repetir palabras— pero pilla el caso
    frecuente: terminar con una moraleja generica que no tiene nada que ver
    con la escena con la que se abrio.
    """
    if not hook or not beats:
        return 0
    def utiles(t):
        return {p.strip(".,;:¡!¿?").lower() for p in t.split() if len(p) > 3}
    ph = utiles(hook)
    if not ph:
        return 0
    coincidencias = 0
    for b in beats[-ultimos:]:
        if ph & utiles(b["t"]):
            coincidencias += 1
    return coincidencias


def _validar_y_ajustar(g, min_ganchos=2):
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
    quemados = [q for q in EJEMPLOS_QUEMADOS if q in texto]
    if quemados:
        log.warning(f"Guion '{g.get('titulo')}' descartado: ejemplo quemado "
                    f"({quemados[0]})")
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

    # Sin hilo no hay retencion: un guion que repite la misma idea se abandona
    repes = _redundancia(beats)
    if repes > max(2, len(beats) * 0.15):
        log.warning(f"Guion '{g.get('titulo')}' descartado: {repes} beats "
                    f"repiten ideas ya dichas (no avanza)")
        return None

    # Dos promesas sembradas es el minimo para que la curva no se hunda a la
    # mitad: una sola se paga pronto y a partir de ahi no queda razon de
    # seguir. Con min_ganchos=1 se acepta lo que haya, para no dejar al canal
    # sin video el dia que ninguno llegue a dos.
    texto_todo = _sin_tildes(" ".join(
        [g.get("hook", ""), g.get("cta", "")] + [b["t"] for b in beats])).lower()
    for veto in VETO_TONO:
        if veto in texto_todo:
            log.warning(f"Guion '{g.get('titulo')}' descartado: tono vetado "
                        f"('{veto}'): o insulta al espectador o usa metafora "
                        f"de autolesion")
            return None

    ganchos = _contar_microhooks(beats, g.get("siembras"))
    if ganchos < min_ganchos:
        log.warning(f"Guion '{g.get('titulo')}' descartado: {ganchos} "
                    f"micro-hook(s), se piden {min_ganchos} "
                    f"(poco que prometa al espectador seguir viendo)")
        return None

    # El cierre debe volver a la escena del hook. Sin callback, el video
    # termina en una moraleja de manual y el espectador se queda sin la
    # descarga que el hook le prometio.
    cierre = _callback_al_hook(g.get("hook", ""), beats)
    if not cierre:
        log.warning(f"Guion '{g.get('titulo')}' descartado: el final no "
                    f"resuelve el hook (sin callback en los ultimos beats)")
        return None

    g["_redundancia"] = repes
    g["_microhooks"] = ganchos
    g["_callback"] = cierre

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
