"""Adaptador LLM: Gemini (3 modelos) + respaldo OpenAI. Solo REST."""
import os
import json
import time
import logging
import requests

log = logging.getLogger("VideoFactory.LLM")

# Los gemini-2.0-* fueron retirados (404), igual que paso antes con 1.5-flash.
# Los alias "-latest" NO caducan: Google los reapunta solo. Eso corta de raiz
# el bug recurrente de "modelo muerto".
GEMINI_MODELS = ["gemini-3.5-flash",            # preferido
                 "gemini-flash-lite-latest",    # alias, cuota gratis mas alta
                 "gemini-flash-latest",         # alias
                 "gemini-2.5-flash"]            # ancla verificada


def _gemini_keys():
    """Todas las claves de Gemini configuradas, en orden.

    El tier gratuito se agota rapido (una sesion larga de guiones lo vacia),
    y cuando pasa el pipeline entero cae a OpenAI, que cuesta. Con varias
    claves se rota: la cuota es POR PROYECTO, asi que claves de proyectos
    distintos suman cuota de verdad. Dos claves del mismo proyecto no sirven
    de nada, comparten el mismo limite.

    Se leen GEMINI_API_KEY, GEMINI_API_KEY_2 ... GEMINI_API_KEY_5.
    """
    claves = []
    for nombre in ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 6)]:
        v = (os.getenv(nombre) or "").strip()
        if v and v not in claves:          # repetir una clave no da mas cuota
            claves.append(v)
    return claves


def _gemini_key():
    claves = _gemini_keys()
    return claves[0] if claves else ""


def _openai_key():
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def chat_json(system, user, temperature=0.7, max_tokens=4000):
    text = chat_text(system, user, temperature, max_tokens, force_json=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _repair_json(text)


def _repair_json(text):
    t = text.rstrip()
    for extra in ('"', '"}', '"}]', '"}]}', '}', ']}', ']]'):
        try:
            return json.loads(t + extra)
        except Exception:
            pass
    idx = t.rfind('}')
    while idx > 0:
        cand = t[:idx + 1]
        cand += ']' * max(0, cand.count('[') - cand.count(']'))
        cand += '}' * max(0, cand.count('{') - cand.count('}'))
        try:
            return json.loads(cand)
        except Exception:
            idx = t.rfind('}', 0, idx)
    raise json.JSONDecodeError("JSON irrecuperable", text, 0)


def chat_text(system, user, temperature=0.7, max_tokens=4000, force_json=False):
    last_err = None
    for attempt in range(3):
        try:
            if _gemini_key():
                try:
                    return _gemini(system, user, temperature, max_tokens, force_json)
                except Exception as e:
                    # FIX: antes solo bajaba a OpenAI en 429. Si Gemini caia por
                    # 503/404/red, el pipeline moria teniendo respaldo disponible.
                    if _openai_key():
                        log.warning(f"Gemini fallo ({str(e)[:120]}). Usando OpenAI como respaldo.")
                        return _openai(system, user, temperature, max_tokens, force_json)
                    raise
            return _openai(system, user, temperature, max_tokens, force_json)
        except Exception as e:
            last_err = e
            wait = 2 ** (attempt + 1)
            log.warning(f"LLM fallo (intento {attempt+1}/3): {e}. Retry en {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"LLM fallo tras 3 intentos: {last_err}")


def _gemini(system, user, temperature, max_tokens, force_json):
    claves = _gemini_keys()
    if not claves:
        raise RuntimeError("Sin GEMINI_API_KEY")
    last_err = None
    saw_429 = False
    # El bucle exterior son las CLAVES y el interior los modelos: si una clave
    # agota su cuota, se prueba la siguiente con todos los modelos otra vez.
    for n_clave, key in enumerate(claves, 1):
      agotada = False
      for model in GEMINI_MODELS:
          gen_cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
          if force_json:
              gen_cfg["response_mime_type"] = "application/json"
          # Sin presupuesto de "pensamiento": si el modelo lo gasta, se queda sin
          # tokens para la respuesta y devuelve parts vacio.
          if model.startswith(("gemini-2.5", "gemini-3")):
              gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
          url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
          payload = {
              "system_instruction": {"parts": [{"text": system}]},
              "contents": [{"parts": [{"text": user}]}],
              "generationConfig": gen_cfg,
          }
          r = requests.post(url, json=payload, timeout=120)
          if r.status_code == 400 and "think" in r.text.lower():
              payload["generationConfig"].pop("thinkingConfig", None)
              r = requests.post(url, json=payload, timeout=120)
          if r.status_code == 404:
              log.warning(f"Modelo {model} no disponible; probando siguiente.")
              last_err = last_err or RuntimeError(f"modelo {model} no disponible")
              continue
          if r.status_code == 429:
              saw_429 = True
              agotada = True
              last_err = RuntimeError(f"Gemini {model} 429 cuota agotada")
              continue
          # FIX: 503 = modelo saturado (pasa a diario en el tier gratis) y 5xx en
          # general son temporales. Antes reventaban el pipeline entero.
          if r.status_code >= 500:
              log.warning(f"Modelo {model} HTTP {r.status_code} (saturado); probando siguiente.")
              last_err = RuntimeError(f"Gemini {model} HTTP {r.status_code}")
              continue
          # Clave mal pegada o sin permisos: no tiene arreglo reintentando con
          # otro modelo, pero SI probando la clave siguiente. Antes esto
          # abandonaba Gemini entero y se caia a OpenAI, que cuesta, teniendo
          # dos claves buenas sin tocar.
          if r.status_code in (400, 403) and "api key" in r.text.lower():
              log.warning(f"Clave {n_clave} de Gemini no es valida.")
              agotada = True
              last_err = RuntimeError(f"Gemini clave {n_clave} invalida")
              break
          if r.status_code != 200:
              raise RuntimeError(f"Gemini {model} HTTP {r.status_code}: {r.text[:300]}")
          data = r.json()
          try:
              text = data["candidates"][0]["content"]["parts"][0]["text"]
          except (KeyError, IndexError):
              raise RuntimeError(f"Gemini {model} respuesta vacia: {json.dumps(data)[:300]}")
          etq = f"gemini/{model}" + (f" (clave {n_clave})" if n_clave > 1 else "")
          log.info(f"LLM: {etq}")
          return _clean(text, force_json)
      if agotada and n_clave < len(claves):
          log.warning(f"Clave {n_clave} de Gemini agotada; probando la {n_clave+1}.")
    # FIX: si algun modelo dio 429, el error final debe decirlo para activar OpenAI
    if saw_429:
        raise RuntimeError(f"Gemini 429: cuota agotada en las {len(claves)} "
                           f"clave(s) configurada(s)")
    raise last_err


def _openai(system, user, temperature, max_tokens, force_json):
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}
        if "JSON" not in system and "JSON" not in user:
            payload["messages"][0]["content"] += "\nResponde en JSON."
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {_openai_key()}"},
        json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:300]}")
    text = r.json()["choices"][0]["message"]["content"]
    log.info("LLM: openai")
    return _clean(text, force_json)


def _clean(text, force_json):
    text = text.strip()
    if force_json and text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return text.strip()
