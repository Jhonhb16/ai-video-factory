"""Utilidad de tokens Meta: check / refresh (manual, nunca en cron)."""
import os
import time
import requests

GRAPH = "https://graph.facebook.com/v23.0"


def check():
    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        print("META_ACCESS_TOKEN no configurado")
        return
    r = requests.get(f"{GRAPH}/debug_token",
                     params={"input_token": token, "access_token": token}, timeout=30)
    d = r.json().get("data", {})
    exp = d.get("expires_at")
    print(f"valido={d.get('is_valid')} expires_at={exp}")
    if exp and exp - time.time() < 7 * 86400:
        print("Expira en menos de 7 dias. Ejecuta: python -m src.meta_token refresh")


def refresh():
    app_id = os.getenv("META_APP_ID")
    secret = os.getenv("META_APP_SECRET")
    token = os.getenv("META_ACCESS_TOKEN")
    if not (app_id and secret and token):
        print("Faltan META_APP_ID / META_APP_SECRET / META_ACCESS_TOKEN")
        return
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": secret,
        "fb_exchange_token": token,
    }, timeout=30)
    d = r.json()
    if d.get("access_token"):
        print("Nuevo token (pegalo en tu secret META_ACCESS_TOKEN):")
        print(d["access_token"])
    else:
        print("Error:", d)


if __name__ == "__main__":
    import sys
    {"check": check, "refresh": refresh}.get(
        sys.argv[1] if len(sys.argv) > 1 else "check", check)()
