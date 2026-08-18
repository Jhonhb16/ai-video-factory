"""VERIFICADOR DE DATOS: juzga si las cifras de un guion son ciertas.

Por que existe: el veto de patrones (VETO_DATO) caza la FORMA de una
afirmacion sin respaldo ("segun la CFPB...", "ocho de cada diez..."), pero no
puede distinguir una cifra cierta de una falsa cuando las dos tienen la misma
forma. Ejemplo real de una misma tirada:

  "El 30 por ciento de tu puntaje es la utilizacion."   <- CIERTO (FICO)
  "El 35 por ciento de tu puntaje viene de tu renta."   <- FALSO (ese 35% es
                                                           el historial de pagos)

Las dos son "N% de tu puntaje". Distinguirlas es conocimiento, no patron.

Este canal habla de dinero a gente que decide donde mete sus ahorros, asi que
una cifra falsa con tono de autoridad hace daño de verdad. Ante la duda, el
veredicto es DUDOSO y la linea se reescribe: no publicar un dato bueno cuesta
mucho menos que publicar uno falso.
"""
import json
import re
import logging

from src.llm import chat_json

log = logging.getLogger("VideoFactory.Verificador")

PROMPT = """Eres verificador de datos de un canal de finanzas para migrantes
hispanos en Estados Unidos. Tu unico trabajo es decir si cada afirmacion con
cifra es CIERTA, FALSA o DUDOSA. No juzgas el estilo ni la gracia.

CIERTA: es un hecho comprobable y ampliamente conocido del sistema financiero
  de EE. UU., o una cuenta aritmetica que el propio guion deriva de un precio.
  Ej: "el 30 por ciento de tu puntaje FICO es la utilizacion" (correcto).
  Ej: "quince dolares por semana son setecientos ochenta al año" (la cuenta sale).
FALSA: contradice como funciona el sistema, o se contradice con otra cifra del
  MISMO guion.
  Ej: "el 35 por ciento de tu puntaje viene de reportar la renta" (ese 35 por
      ciento es el historial de pagos, no la renta).
  Ej: decir "ocho por ciento de comision" y luego "llega menos del diez por
      ciento del dinero".
DUDOSA: estadistica sobre personas que no puedes confirmar, cita a un estudio
  o institucion, o cifra que varia mucho segun el caso.
  Ej: "el setenta por ciento de los inquilinos pierde su deposito".

Rangos de tarifas reales (cambian de sitio en sitio, pero el orden de magnitud
sirve): cambiar un cheque 1-5 por ciento; remesa 3-10 por ciento entre comision
y tipo de cambio; sobregiro 25-40 dolares; prestamo de dia de pago 300-500 por
ciento anual; lote de carros que financia 15-30 por ciento. Una cifra dentro de
su rango es CIERTA; muy fuera, FALSA.

Se estricto: ante la duda, DUDOSA. Es preferible perder un dato bueno que
publicar uno falso.

Para cada afirmacion FALSA o DUDOSA propon un ARREGLO concreto: la misma idea
dicha con una cifra que si se sostenga, o sin cifra.

Devuelve UNICAMENTE JSON:
{"revisiones": [{"frase": "copia exacta", "veredicto": "CIERTA|FALSA|DUDOSA",
                 "motivo": "breve", "arreglo": "como decirlo bien"}]}"""


# "X al mes son Y al año" y familia. Estas NO se le preguntan al LLM: se
# calculan. Cuando se le preguntaron, dio por falsa "mil cuatrocientos al mes
# son dieciseis mil ochocientos al año" (que es exacta) y dejo pasar otras.
# Dos de cada diez veredictos suyos sobre aritmetica estaban mal; la
# multiplicacion sale bien el cien por cien de las veces.
PERIODOS = [
    (r"al\s+d[ií]a\b", r"al\s+a[ñn]o\b", 365),
    (r"al\s+d[ií]a\b", r"al\s+mes\b", 30),
    (r"a\s+la\s+semana\b|por\s+semana\b|semanales?\b", r"al\s+a[ñn]o\b", 52),
    (r"a\s+la\s+semana\b|por\s+semana\b|semanales?\b", r"al\s+mes\b", 4),
    (r"al\s+mes\b|mensuales?\b", r"al\s+a[ñn]o\b", 12),
]


def _comprobar_aritmetica(frase):
    """Si la frase dice 'X al mes son Y al año', comprueba la cuenta.

    Devuelve None si no aplica o si cuadra; si no, el error concreto.
    """
    from src.cifras import _valor_en_palabras

    numeros = []
    for m in re.finditer(r"\d[\d.,]*", frase):
        try:
            numeros.append(float(m.group(0).replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    if len(numeros) < 2:                       # probar con numeros en letra
        trozos, resto = [], frase
        while len(trozos) < 2:
            r = _valor_en_palabras(resto)
            if not r:
                break
            # "un"/"una" casi siempre son articulo, no cantidad: en "cuarenta
            # dolares por UN sobregiro al mes son cuatrocientos ochenta" el 1
            # se colaba como segundo numero y acusaba de mala una cuenta exacta
            if not (r[0] == 1 and r[2].strip().lower() in ("un", "una", "uno")):
                trozos.append(r[0])
            resto = resto.split(r[2], 1)[-1] if r[2] in resto else ""
        numeros = trozos if len(trozos) >= 2 else numeros
    if len(numeros) < 2:
        return None

    base, total = numeros[0], numeros[1]
    if base <= 0 or total <= 0:
        return None
    for pat_a, pat_b, factor in PERIODOS:
        if re.search(pat_a, frase, re.I) and re.search(pat_b, frase, re.I):
            esperado = base * factor
            # 4% de margen: el guionista redondea a proposito y esta bien
            if abs(total - esperado) / esperado > 0.04:
                return (f"la cuenta no sale: {base:.0f} x {factor} = "
                        f"{esperado:.0f}, no {total:.0f}")
            return None
    return None


def verificar(guion):
    """Devuelve la lista de afirmaciones problematicas del guion.

    Si el LLM falla se devuelve lista vacia: el verificador no puede tumbar la
    produccion del dia. Lo que no puede pasar es lo contrario, dar por buena
    una cifra que nadie miro, y por eso se registra en el log.
    """
    frases = [b["t"] for b in (guion.get("beats") or [])
              if any(c.isdigit() for c in b["t"])
              or any(p in b["t"].lower() for p in
                     ("por ciento", "de cada", "segun", "según", "mil", "cientos"))]
    if not frases:
        return []
    try:
        r = chat_json(PROMPT,
                      "TITULO: " + str(guion.get("titulo", "")) + "\n"
                      "AFIRMACIONES:\n" + json.dumps(frases, ensure_ascii=False),
                      temperature=0.1, max_tokens=2000)
    except Exception as e:
        log.warning(f"Verificador no disponible ({e}); las cifras de "
                    f"'{guion.get('titulo')}' NO se han comprobado")
        return []

    revisiones = r.get("revisiones") if isinstance(r, dict) else r
    if not isinstance(revisiones, list):
        return []
    malas = [x for x in revisiones if isinstance(x, dict)
             and str(x.get("veredicto", "")).upper() in ("FALSA", "DUDOSA")]

    # La aritmetica manda sobre el LLM: si la cuenta sale, se le retira la
    # acusacion; si no sale, se acusa aunque el la haya aprobado.
    por_frase = {str(x.get("frase", "")): x for x in malas}
    for f in frases:
        error = _comprobar_aritmetica(f)
        if error and f not in por_frase:
            por_frase[f] = {"frase": f, "veredicto": "FALSA",
                            "motivo": error, "arreglo": "corregir la cifra"}
        elif not error and f in por_frase and "cuenta" in \
                str(por_frase[f].get("motivo", "")).lower():
            del por_frase[f]                   # el LLM se equivoco, la cuenta sale
    malas = list(por_frase.values())
    if malas:
        log.info(f"'{guion.get('titulo')}': {len(malas)} cifras a revisar")
    return malas
