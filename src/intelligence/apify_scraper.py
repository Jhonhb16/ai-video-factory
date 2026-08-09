"""Scraper Apify: descubrimiento de referentes + scraping de perfiles."""
import os
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from apify_client import ApifyClient

log = logging.getLogger("VideoFactory.Intelligence")

CACHE_DIR = Path("output/intelligence/scrape_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_IDS_FILE = Path("output/intelligence/processed_ids.json")


class ApifyScraper:
    def __init__(self, config):
        token = os.getenv("APIFY_TOKEN")
        if not token:
            raise ValueError("APIFY_TOKEN no configurado")
        self.token = token
        self.client = ApifyClient(token)
        self.cfg = config["intelligence"]
        self.actor_id = self.cfg.get("apify_actor", "apify/instagram-scraper")

    def credito_suficiente(self, minimo_usd=0.50):
        try:
            r = requests.get("https://api.apify.com/v2/users/me",
                             params={"token": self.token}, timeout=15)
            data = r.json().get("data", {})
            usado = float(data.get("usage", {}).get("total", 0) or 0)
            log.info(f"Apify: uso mensual actual ${usado:.2f}")
            if data.get("plan", {}).get("id") == "FREE" and usado > 4.0:
                log.warning("Credito Apify casi agotado. Usando cache/respaldo.")
                return False
            return True
        except Exception as e:
            log.warning(f"No se pudo verificar credito Apify ({e}). Continuando.")
            return True

    def discover_referentes(self):
        log.info("Descubriendo referentes automaticamente...")
        fecha_limite = datetime.now() - timedelta(days=self.cfg["dias_atras"])
        creadores = {}
        for hashtag in self.cfg["hashtags_descubrimiento"]:
            videos = self._scrapear_hashtag(hashtag)
            for v in videos:
                if not self._video_califica(v, fecha_limite):
                    continue
                owner = v.get("ownerUsername") or ""
                if not owner:
                    continue
                if owner not in creadores:
                    creadores[owner] = {"count": 0, "engagement": 0}
                creadores[owner]["count"] += 1
                creadores[owner]["engagement"] += self._engagement_score(v)

        ranking = [
            {"username": u, "videos_virales": d["count"], "engagement_total": d["engagement"]}
            for u, d in creadores.items() if d["count"] >= 3
        ]
        ranking.sort(key=lambda x: (x["videos_virales"], x["engagement_total"]), reverse=True)
        top = [f"@{r['username']}" for r in ranking[:self.cfg["top_referentes_descubiertos"]]]
        for r in ranking[:5]:
            log.info(f"   @{r['username']}: {r['videos_virales']} virales, engagement {r['engagement_total']:,}")
        if not top:
            log.error("Descubrimiento devolvio 0 referentes. Se usara matrix de respaldo.")
        else:
            log.info(f"Referentes descubiertos: {top}")
        return top

    def _scrapear_hashtag(self, hashtag):
        cache = CACHE_DIR / f"hashtag_{hashtag}.json"
        if self._cache_valido(cache, horas=24):
            return json.loads(cache.read_text())
        input_data = {
            "hashtags": [hashtag],
            "resultsLimit": self.cfg["videos_por_hashtag"],
            "includeStories": False,
        }
        items = self._run_actor(input_data)
        if items:
            cache.write_text(json.dumps(items, ensure_ascii=False, default=str))
        return items

    def scrape_referente(self, username):
        username = username.lstrip("@")
        cache = CACHE_DIR / f"profile_{username}.json"
        if self._cache_valido(cache, horas=12):
            return json.loads(cache.read_text())
        input_data = {
            "directUsernames": [username],
            "resultsLimit": 30,
            "includeStories": False,
        }
        items = self._run_actor(input_data)
        if items:
            cache.write_text(json.dumps(items, ensure_ascii=False, default=str))
        return items

    def _run_actor(self, input_data):
        try:
            run = self.client.actor(self.actor_id).call(run_input=input_data)
            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            items = [i for i in items if i.get("type") in ("video", "reel") or i.get("videoUrl")]
            return self._deduplicar(items)
        except Exception as e:
            log.error(f"Actor Apify fallo ({self.actor_id}): {e}")
            return []

    def _engagement_score(self, v):
        likes = v.get("likesCount") or 0
        comments = v.get("commentsCount") or 0
        views = v.get("viewsCount") or 0
        return int(likes + comments * 3 + views * 0.1)

    def _video_califica(self, v, fecha_limite):
        if self._engagement_score(v) < 500:
            return False
        ts = v.get("timestamp")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    fecha = datetime.fromtimestamp(ts)
                else:
                    fecha = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).replace(tzinfo=None)
                return fecha >= fecha_limite
            except Exception:
                return True
        return True

    def _deduplicar(self, items):
        vistos = self._cargar_ids()
        unicos = []
        for item in items:
            vid = item.get("id") or item.get("shortcode") or item.get("url", "")
            if vid and vid not in vistos:
                vistos.add(vid)
                unicos.append(item)
        self._guardar_ids(vistos)
        return unicos

    def _cargar_ids(self):
        if PROCESSED_IDS_FILE.exists():
            try:
                return set(json.loads(PROCESSED_IDS_FILE.read_text()))
            except Exception:
                return set()
        return set()

    def _guardar_ids(self, ids):
        PROCESSED_IDS_FILE.write_text(json.dumps(list(ids)[-5000:]))

    def _cache_valido(self, path, horas):
        if not path.exists():
            return False
        return (time.time() - path.stat().st_mtime) < horas * 3600
