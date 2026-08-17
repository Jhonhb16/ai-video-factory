"""Cliente de kie.ai: imagenes y clips con personaje consistente.

Reglas duras del proyecto que este modulo respeta:
- Nunca hard-fail: si no hay clave, se acaban los creditos o falla la red,
  devuelve None y el pipeline sigue con los escenarios locales.
- Control de ritmo: la cuenta admite 20 peticiones cada 10s y el exceso
  devuelve 429 SIN encolarse.
- Cache por huella del prompt: no se paga dos veces por lo mismo.

Precios medidos (2026-08-17): imagen ~4 creditos ($0.02); clip de 4s a 480p
~47 creditos ($0.23). Un credito = $0.005.
"""
import hashlib
import json
import logging
import os
import time
from collections import deque
from pathlib import Path

import requests

log = logging.getLogger("VideoFactory.Kie")

BASE = "https://api.kie.ai"
MODELO_IMAGEN = "google/nano-banana"
MODELO_CLIP = "bytedance/seedance-2-fast"
CACHE = Path("output/cache/kie")

_ultimas = deque(maxlen=20)      # marcas de tiempo para el limite de ritmo


def _clave():
    return (os.getenv("KIE_API_KEY") or "").strip()


def disponible():
    return bool(_clave())


def _cab():
    return {"Authorization": f"Bearer {_clave()}", "Content-Type": "application/json"}


def creditos():
    """Creditos restantes, o None si no se puede consultar."""
    try:
        r = requests.get(f"{BASE}/api/v1/chat/credit", headers=_cab(), timeout=20)
        return (r.json() or {}).get("data")
    except Exception as e:
        log.warning(f"No se pudieron consultar los creditos: {str(e)[:90]}")
        return None


def _esperar_turno():
    """20 peticiones cada 10s: el exceso da 429 y no se encola."""
    ahora = time.time()
    if len(_ultimas) == _ultimas.maxlen:
        antiguedad = ahora - _ultimas[0]
        if antiguedad < 10.5:
            espera = 10.5 - antiguedad
            log.info(f"Limite de ritmo: esperando {espera:.1f}s")
            time.sleep(espera)
    _ultimas.append(time.time())


def _crear(modelo, entrada):
    _esperar_turno()
    r = requests.post(f"{BASE}/api/v1/playground/createTask", headers=_cab(),
                      json={"model": modelo, "input": entrada}, timeout=60)
    d = r.json()
    if d.get("code") != 200:
        log.warning(f"kie rechazo la tarea: {str(d.get('msg'))[:130]}")
        return None
    return (d.get("data") or {}).get("taskId")


def _esperar(task, limite_s=420):
    """Sondea hasta que la tarea acabe. Devuelve la URL del resultado."""
    t0 = time.time()
    while time.time() - t0 < limite_s:
        try:
            r = requests.get(f"{BASE}/api/v1/playground/recordInfo", headers=_cab(),
                             params={"taskId": task}, timeout=30)
            d = (r.json() or {}).get("data") or {}
        except Exception:
            time.sleep(4)
            continue
        estado = str(d.get("state") or d.get("status") or "").lower()
        if estado in ("success", "completed", "succeeded"):
            res = d.get("resultJson")
            if isinstance(res, str):
                try:
                    res = json.loads(res)
                except Exception:
                    res = {}
            urls = (res or {}).get("resultUrls") or []
            return urls[0] if urls else None
        if estado in ("fail", "failed", "error"):
            log.warning(f"kie fallo la tarea: {str(d.get('failMsg'))[:130]}")
            return None
        time.sleep(4)
    log.warning("kie: la tarea supero el tiempo limite")
    return None


def _descargar(url, destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    datos = requests.get(url, timeout=400).content
    if len(datos) < 5000:
        return None
    destino.write_bytes(datos)
    return destino


def _huella(*partes):
    h = hashlib.sha256()
    for p in partes:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:16]


def generar_imagen(prompt, referencia=None, proporcion="9:16", nombre=None):
    """Imagen 9:16. 'referencia' es una URL publica para mantener el personaje.

    Devuelve la ruta local, o None. Nunca lanza.
    """
    if not disponible():
        return None
    try:
        clave = _huella(MODELO_IMAGEN, prompt, referencia, proporcion)
        destino = CACHE / f"{nombre or 'img'}_{clave}.png"
        if destino.exists() and destino.stat().st_size > 5000:
            log.info(f"kie: imagen en cache ({destino.name})")
            return destino

        entrada = {"prompt": prompt, "aspect_ratio": proporcion}
        if referencia:
            # OJO: en imagen el parametro es image_urls (array). En video es
            # first_frame_url; usar el equivocado se acepta y se IGNORA.
            entrada["image_urls"] = [referencia]

        task = _crear(MODELO_IMAGEN, entrada)
        if not task:
            return None
        url = _esperar(task, 240)
        return _descargar(url, destino) if url else None
    except Exception as e:
        log.warning(f"kie imagen fallo ({str(e)[:110]}); se sigue sin ella.")
        return None


def generar_clip(prompt, primer_fotograma, segundos=4, resolucion="480p", nombre=None):
    """Clip animado a partir de una imagen. Devuelve ruta local o None.

    Los valores por defecto de la API son 720p, 16:9 y audio activado; si no
    se fijan, el coste se multiplica por siete y sale horizontal.
    """
    if not disponible() or not primer_fotograma:
        return None
    try:
        clave = _huella(MODELO_CLIP, prompt, primer_fotograma, segundos, resolucion)
        destino = CACHE / f"{nombre or 'clip'}_{clave}.mp4"
        if destino.exists() and destino.stat().st_size > 20000:
            log.info(f"kie: clip en cache ({destino.name})")
            return destino

        task = _crear(MODELO_CLIP, {
            "prompt": prompt,
            "first_frame_url": primer_fotograma,
            "resolution": resolucion,
            "aspect_ratio": "9:16",
            "duration": int(segundos),
            "generate_audio": False,
        })
        if not task:
            return None
        url = _esperar(task, 420)
        return _descargar(url, destino) if url else None
    except Exception as e:
        log.warning(f"kie clip fallo ({str(e)[:110]}); se sigue sin el.")
        return None


def subir_publico(ruta, clave_remota):
    """Sube a R2 publico y devuelve la URL. kie necesita URLs accesibles."""
    try:
        from src.dashboard import _client
        bucket = (os.getenv("R2_BUCKET") or "").strip()
        base = (os.getenv("R2_PUBLIC_BASE") or "").strip().rstrip("/")
        if not (bucket and base):
            log.warning("Sin R2 publico: kie no puede recibir referencias.")
            return None
        tipo = "video/mp4" if str(ruta).endswith(".mp4") else "image/png"
        _client().upload_file(str(ruta), bucket, clave_remota,
                              ExtraArgs={"ContentType": tipo})
        return f"{base}/{clave_remota}"
    except Exception as e:
        log.warning(f"No se pudo subir a R2 ({str(e)[:110]})")
        return None
