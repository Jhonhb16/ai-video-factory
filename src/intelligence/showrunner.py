"""SHOWRUNNER: lider con criterio alto. GO/NO-GO antes de producir."""
import json
import logging
from src.llm import chat_json

log = logging.getLogger("VideoFactory.Showrunner")

PROMPT = """Eres el SHOWRUNNER (director creativo) de un estudio de reels de finanzas-COMEDIA.
Revisas el paquete con criterio ALTO tipo MrBeast y eres DURO: tu trabajo es
rechazar lo mediocre, no aprobarlo.

CRITERIO CERO — ¿YA ESTA ESCRITO?
Se te dara la lista de guiones YA APROBADOS para este canal. Si el que
revisas cuenta lo MISMO que uno de ellos, es REWRITE aunque este bien escrito.
No hablamos de repetir el tema —cabe hablar de remesas diez veces— sino de
repetir el ANGULO: la misma herida, el mismo giro y el mismo remate.
Dos guiones que abren con la misma frase son, en la practica, el mismo video,
y publicar el mismo video dos veces es lo que hace que una cuenta deje de
distribuirse. Ningun contador automatico ve esto: lo tienes que ver TU.
En los cambios, di QUE angulo distinto tomar, no solo "hazlo diferente".

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
7. CIERRE EPICO — pesa tanto como el hook: los ultimos beats vuelven a la
   ESCENA EXACTA del hook, la rematan con la consecuencia maxima y una cifra,
   y reencuadran (lo que parecia una cosa era otra). Una moraleja generica
   tipo "si no pagas todo, pagas doble" es REWRITE: el espectador aguanto 70
   segundos y se queda sin la descarga que se le prometio. La ultima linea
   tiene que ser la MAS FUERTE del video.
8. CTA que genera comentarios.

Se honesto: si esta flojo, REWRITE con cambios concretos y accionables.
Devuelve UNICAMENTE JSON:
{"veredicto": "GO" | "REWRITE", "hilo": "avanza" | "se repite",
 "nota_corta": "frase", "cambios": ["cambio concreto", "..."]}"""


def revisar_paquete(guion, previos=None):
    """Revisa un guion. `previos` son los ya aprobados, para cazar repeticiones.

    Sin esa lista el showrunner juzga cada guion en el vacio y no puede saber
    que es el cuarto video seguido sobre lo mismo: en una tirada de 30 salieron
    cuatro con el mismo hook y los aprobo todos, porque cada uno, por separado,
    estaba bien.
    """
    try:
        paquete = {k: guion.get(k) for k in ("titulo", "hook", "beats", "cta", "escenas")}
        contexto = ""
        if previos:
            lista = "\n".join(f'- "{p.get("titulo","")}" abre con: {p.get("hook","")}'
                              for p in previos[-30:])
            contexto = f"\n\nGUIONES YA APROBADOS DE ESTE CANAL:\n{lista}\n"
        r = chat_json(PROMPT,
                      f"PAQUETE:\n{json.dumps(paquete, ensure_ascii=False)}{contexto}",
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
