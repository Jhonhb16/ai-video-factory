"""Genera y filtra CONCEPTOS antes de escribir el guion.

Por que existe: el canal escribia guiones sobre lo que tocara en topics.csv,
una lista de 91 temas de manual — "como hacer un presupuesto en 10 minutos",
"5 gastos hormiga", "la regla 50/30/20". Ninguna estructura salva un tema que
el espectador ha visto quinientas veces. Se estaba puliendo la escritura de
ideas que ya nacian muertas.

Es la regla de MrBeast que faltaba: el concepto va PRIMERO y si no se sostiene
en un titulo, el video no se hace. Aqui se generan angulos, se puntuan y solo
pasa el mejor.

Un TEMA es "como hacer un presupuesto". Un ANGULO es "el presupuesto es la
razon por la que sigues quebrado".
"""
import json
import logging
import re
from pathlib import Path

from src.llm import chat_json
from src.utils import load_config

log = logging.getLogger("VideoFactory.Conceptos")

HISTORIAL = Path("output/intelligence/conceptos_usados.json")
MAX_TITULO = 50

# Angulos tan repetidos que ya no enganchan a nadie
QUEMADOS = [
    "50/30/20", "50 30 20", "gasto hormiga", "gastos hormiga", "cafe diario",
    "metodo de sobres", "metodo del sobre", "paguese a usted primero",
    "pagate a ti primero", "interes compuesto", "regla de las 48 horas",
]

SYS = """Eres editor jefe de un canal de finanzas personales para Latinoamerica.
Tu trabajo NO es elegir temas: es encontrar ANGULOS que hagan parar el scroll.

Un tema es "como hacer un presupuesto". Eso no lo ve nadie.
Un angulo es "el presupuesto es la razon por la que sigues quebrado". Eso si.

Un concepto sirve si cumple AL MENOS DOS de estas:
1. CONTRAINTUITIVO: contradice el consejo que todo el mundo repite.
2. DE ADENTRO: revela como funciona algo por dentro, lo que no te cuentan.
3. INCOMODO Y PERSONAL: apunta a la situacion real del espectador y escuece.
4. CONSECUENCIA CONCRETA: dice que le va a pasar, con cifra o plazo.
5. LOCAL Y ESPECIFICO: precios, sueldos y realidades de Latinoamerica, nunca
   ejemplos gringos de mil dolares.

PROHIBIDO por quemado: la regla 50/30/20, los gastos hormiga, el cafe diario,
el metodo de sobres, "paguese a usted primero", el interes compuesto explicado
como en el colegio.

EL CONCEPTO TIENE QUE TENER RECORRIDO. Un buen titular no basta: si la idea
se agota en una frase, el guionista la reformula cinco veces para llenar 75
segundos y el video se vuelve repetitivo. Por eso cada concepto trae TRES
revelaciones que se pagan en orden y ESCALAN — cada una mas incomoda o mas
cara que la anterior. Si no puedes partirlo en tres cosas distintas que el
espectador no sabe, es buen titulo y mal video: descartalo.

Ejemplo de concepto SIN recorrido (rechazar): "tu dinero pierde valor bajo el
colchon" — es una sola idea, no hay tres revelaciones, solo sinonimos.
Ejemplo CON recorrido: "por que sigues pagando el arriendo de otro":
  1. cuanto llevas pagado en arriendo sin tener nada
  2. el banco te presta menos por ser informal, no por ser pobre
  3. la cuota que si podrias pagar y nadie te la ofrece

El titulo debe tener MENOS de 50 caracteres.
Responde solo JSON:
{"conceptos":[{"titulo":"...","angulo":"una frase","por_que_para":"una frase",
               "revelaciones":["primera","segunda mas fuerte","tercera la peor"],
               "cumple":["contraintuitivo","local_y_especifico"]}]}"""


def _usados():
    if not HISTORIAL.exists():
        return []
    try:
        return json.loads(HISTORIAL.read_text(encoding="utf-8"))
    except Exception:
        return []


def _registrar(concepto):
    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    hist = _usados()
    hist.append({"titulo": concepto.get("titulo"), "angulo": concepto.get("angulo")})
    HISTORIAL.write_text(json.dumps(hist[-120:], ensure_ascii=False, indent=2),
                         encoding="utf-8")


def _quemado(texto):
    t = texto.lower()
    return any(q in t for q in QUEMADOS)


def puntuar(c, titulos_previos):
    """0-100. Mide lo que se puede medir; el resto lo juzga el showrunner."""
    titulo = (c.get("titulo") or "").strip()
    angulo = (c.get("angulo") or "").strip()
    if not titulo or not angulo:
        return 0

    # SIN RECORRIDO NO HAY VIDEO: si la idea no se parte en tres revelaciones
    # distintas, el guionista la reformulara cinco veces para llenar 75s.
    revelaciones = [r for r in (c.get("revelaciones") or []) if str(r).strip()]
    if len(revelaciones) < 3:
        return 0

    puntos = 0
    # el titulo tiene que caber: si no se lee de un vistazo, no hay clic
    if len(titulo) <= MAX_TITULO:
        puntos += 25
    elif len(titulo) <= MAX_TITULO + 12:
        puntos += 10

    # cuantos criterios dice cumplir (dos es el minimo exigido)
    cumple = [x for x in (c.get("cumple") or []) if x]
    puntos += min(30, len(cumple) * 15)

    # concrecion: cifras, plazos o lugares reales
    if re.search(r"\d", titulo + " " + angulo):
        puntos += 15
    if re.search(r"colombia|bogota|medellin|cali|peso|quincena|icetex|arriendo"
                 r"|salario minimo|el 15|el 30", (titulo + " " + angulo).lower()):
        puntos += 15

    # segunda persona: habla contigo, no de un tema
    if re.search(r"\btu\b|\btus\b|\bte\b|\bsigues\b|\bestas\b", titulo.lower()):
        puntos += 15

    if _quemado(titulo + " " + angulo):
        puntos -= 45
    if any(t and t.lower() in titulo.lower() for t in titulos_previos):
        puntos -= 60           # ya se publico algo asi

    return max(0, min(100, puntos))


def elegir_concepto(n=6, minimo=55):
    """Devuelve el mejor concepto del dia, o None para caer a topics.csv."""
    cfg = load_config().get("proyecto", {})
    publico = cfg.get("publico", "22 a 35 años, vive al dia, Latinoamerica")
    previos = [c.get("titulo", "") for c in _usados()[-25:]]

    try:
        r = chat_json(SYS,
                      f"Genera {n} conceptos para un canal de finanzas "
                      f"personales. Publico: {publico}.\n"
                      f"NO repitas estos angulos ya usados:\n" +
                      "\n".join(f"- {t}" for t in previos[-12:]),
                      temperature=1.0, max_tokens=2500)
    except Exception as e:
        log.warning(f"No se pudieron generar conceptos ({str(e)[:90]})")
        return None

    lista = r.get("conceptos") if isinstance(r, dict) else r
    if not isinstance(lista, list):
        return None

    puntuados = sorted(
        ((puntuar(c, previos), c) for c in lista if isinstance(c, dict)),
        key=lambda x: x[0], reverse=True)
    if not puntuados:
        return None

    for p, c in puntuados[:4]:
        log.info(f"  concepto {p:3}/100 · {c.get('titulo','')[:48]}")

    mejor_p, mejor = puntuados[0]
    if mejor_p < minimo:
        log.warning(f"Ningun concepto llega a {minimo} (mejor {mejor_p}); "
                    f"se usa la lista de temas de siempre.")
        return None

    _registrar(mejor)
    log.info(f"Concepto del dia ({mejor_p}/100): {mejor.get('titulo')}")
    return mejor
