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
    if malas:
        log.info(f"'{guion.get('titulo')}': {len(malas)} cifras a revisar")
    return malas
