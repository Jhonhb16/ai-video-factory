"""Feedback semanal: metricas de NUESTROS videos via Meta Graph API."""
import os
import json
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("VideoFactory.Intelligence")
OWN_METRICS_FILE = Path("output/intelligence/metricas_propias.json")


def obtener_metricas_propias():
    token = os.getenv("META_ACCESS_TOKEN")
    page_id = os.getenv("META_PAGE_ID")
    if not (token and page_id):
        log.warning("META no configurado. Sin feedback propio.")
        return []

    results = []
    try:
        r = requests.get(
            f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION','v23.0')}/{page_id}/videos",
            params={"access_token": token,
                    "fields": "id,title,created_time", "limit": 20}, timeout=30)
        videos = r.json().get("data", [])
        limite = datetime.now() - timedelta(days=7)

        for v in videos:
            try:
                creado = datetime.fromisoformat(v["created_time"].replace("+0000", "+00:00")).replace(tzinfo=None)
                if creado < limite:
                    continue
                results.append({"video_id": v["id"], "titulo": v.get("title", ""),
                                "created_time": v["created_time"], **_metricas_video(v["id"], token)})
            except Exception as e:
                log.debug(f"Error con video {v.get('id')}: {e}")
    except Exception as e:
        log.error(f"Error consultando Meta Graph API: {e}")

    if results:
        OWN_METRICS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        log.info(f"{len(results)} videos propios con metricas")
    return results


def _metricas_video(video_id, token):
    out = {"views": 0, "likes": 0, "comments": 0, "shares": 0}
    graph = f"https://graph.facebook.com/{os.getenv('META_GRAPH_VERSION','v23.0')}"
    try:
        r = requests.get(f"{graph}/{video_id}",
                         params={"access_token": token,
                                 "fields": "likes.summary(true),comments.summary(true),shares"}, timeout=30)
        d = r.json()
        out["likes"] = d.get("likes", {}).get("summary", {}).get("total_count", 0)
        out["comments"] = d.get("comments", {}).get("summary", {}).get("total_count", 0)
        out["shares"] = d.get("shares", {}).get("count", 0)
        r2 = requests.get(f"{graph}/{video_id}/video_insights",
                          params={"access_token": token, "metric": "total_video_views"}, timeout=30)
        insights = r2.json().get("data", [])
        if insights:
            vals = insights[0].get("values", [])
            out["views"] = vals[-1].get("value", 0) if vals else 0
    except Exception:
        pass
    return out
