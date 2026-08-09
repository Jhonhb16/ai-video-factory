"""Adaptador LLM: Gemini con salto de modelos + respaldo OpenAI. Solo REST."""
import os
import json
import time
import logging
import requests

log = logging.getLogger("VideoFactory.LLM")

# Orden por cuota gratuita: 2.0 flash suele tener mas cuota diaria que 2.5
GEMINI_MODELS = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]


def _gemini_key():
    return (os.getenv("GEMINI_API_KEY") or "").strip()


def _openai_key():
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def chat_json(system, user, temperature=0.7, max_tokens=4000):
    text = chat_text(system, user, temperature, max_tokens, force_json=True)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _repair_json(text)


def _repair_json(text):
    """Salva JSON truncado: cierra comillas/corchetes o corta en el ultimo objeto completo."""
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
                    if "429" in str(e) and _openai_key():
                        log.warning("Gemini sin cuota (429). Usando OpenAI como respaldo.")
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
    key = _gemini_key()
    last_err = None
    for model in GEMINI_MODELS:
        gen_cfg = {"temperature": temperature, "maxOutputTokens": max_tokens}
        if force_json:
            gen_cfg["response_mime_type"] = "application/json"
        if model.startswith("gemini-2.5"):
            gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        r = requests.post(url, json=payload, timeout=120)
        if r.status_code == 400 and "thinkingConfig" in r.text:
            payload["generationConfig"].pop("thinkingConfig", None)
            r = requests.post(url, json=payload, timeout=120)
        if r.status_code == 404:
            last_err = RuntimeError(f"modelo {model} no disponible")
            continue
        if r.status_code == 429:
            last_err = RuntimeError(f"Gemini {model} 429 cuota agotada")
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Gemini {model} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Gemini {model} respuesta vacia: {json.dumps(data)[:300]}")
        log.info(f"LLM: gemini/{model}")
        return _clean(text, force_json)
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
