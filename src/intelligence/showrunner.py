"""SHOWRUNNER: lider con criterio alto. GO/NO-GO antes de producir."""
import json
import logging
from src.llm import chat_json

log = logging.getLogger("VideoFactory.Showrunner")

PROMPT = """Eres el SHOWRUNNER (director creativo) de un estudio de reels de finanzas-COMEDIA.
Revisas el paquete con criterio ALTO tipo MrBeast y eres DURO: tu trabajo es
rechazar lo mediocre, no aprobarlo.

EL CRITERIO NUMERO UNO — EL HILO:
El guion tiene que AVANZAR. Cada beat aporta algo que el anterior no dijo.
El fallo mas comun y mas grave es decir la misma idea de varias formas con
palabras distintas. Ejemplo real de guion RECHAZADO:
  "Llevas cinco años cobrando y sigues sin colchon."
  "Vives esperando el deposito como si fuera un milagro."
  "Llega el dinero, respiras y a los tres dias vuela."
  "Tu cuenta parece zona de guerra."
Las cuatro dicen "no te alcanza". Usan palabras distintas, asi que ningun
contador automatico lo detecta: por eso lo tienes que juzgar TU. Si el guion
hace esto, es REWRITE aunque cada frase suelta sea ingeniosa.

Resto del checklist:
1. HOOK 3s: detiene el scroll SI o SI, con cifra o plazo concreto.
2. MICRO-HOOKS: minimo 2 promesas sembradas ("la tercera es la que mas te
   cuesta", "el dato que no te dicen viene al final") Y todas se pagan.
3. DATO EXTRAORDINARIO: al menos una cifra que sorprenda de verdad. "La mitad
   se va en lo basico" no sorprende a nadie.
4. ESCALADA: el ultimo tercio es mas fuerte que el primero.
5. COMEDIA: minimo 4 momentos de risa, con callback al hook.
6. RITMO: ninguna linea > 14 palabras; cero tono de ensayo.
7. CIERRE: punch final + ensenanza + CTA que genera comentarios.

Se honesto: si esta flojo, REWRITE con cambios concretos y accionables.
Devuelve UNICAMENTE JSON:
{"veredicto": "GO" | "REWRITE", "hilo": "avanza" | "se repite",
 "nota_corta": "frase", "cambios": ["cambio concreto", "..."]}"""


def revisar_paquete(guion):
    try:
        paquete = {k: guion.get(k) for k in ("titulo", "hook", "beats", "cta", "escenas")}
        r = chat_json(PROMPT, f"PAQUETE:\n{json.dumps(paquete, ensure_ascii=False)}",
                      temperature=0.3, max_tokens=1500)
    except Exception as e:
        log.warning(f"Showrunner fallo ({e}). Aprobando por defecto.")
        return {"veredicto": "GO"}
    # el hilo manda: un guion que se repite se rechaza aunque el LLM lo apruebe
    if str(r.get("hilo", "")).lower().startswith("se repite"):
        r["veredicto"] = "REWRITE"
        r.setdefault("cambios", []).insert(
            0, "El guion no avanza: hay beats que dicen la misma idea con "
               "otras palabras. Reescribe para que cada uno aporte algo nuevo.")
    log.info(f"SHOWRUNNER: {r.get('veredicto')} (hilo: {r.get('hilo', '?')}) "
             f"- {r.get('nota_corta', '')}")
    return r
