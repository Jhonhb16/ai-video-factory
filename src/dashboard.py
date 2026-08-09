"""Panel publico en R2: ver videos y resultados sin usar GitHub."""
import os
import json
import logging
import boto3
from pathlib import Path
from src.utils import today, notify

log = logging.getLogger("VideoFactory.Dashboard")

HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dinero Inteligente - Panel</title>
<style>
body{background:#0b1220;color:#e5e7eb;font-family:system-ui,sans-serif;margin:0;padding:16px}
.card{background:#111a2e;border:1px solid #1f2a44;border-radius:14px;padding:16px;margin:12px auto;max-width:560px}
h1{font-size:20px;text-align:center}
video{width:100%;border-radius:10px;background:#000;margin-top:10px}
.score{display:inline-block;background:#16a34a;color:#fff;border-radius:999px;padding:4px 12px;font-weight:700}
.row{display:flex;justify-content:space-between;gap:8px;padding:10px;border-bottom:1px solid #1f2a44;font-size:14px}
a{color:#60a5fa;text-decoration:none}
.btn{display:block;text-align:center;background:#2563eb;color:#fff;border-radius:10px;padding:12px;margin:10px 0;font-weight:700}
small{color:#94a3b8}
</style>
</head>
<body>
<h1>🎬 Dinero Inteligente — Panel</h1>
<div class="card" id="latest"></div>
<div class="card"><h2 style="font-size:16px">📚 Historial</h2><div id="hist"></div></div>
<div class="card">
<a class="btn" href="https://github.com/Jhonhb16/ai-video-factory/actions" target="_blank">⚙️ Operar sistema (GitHub Actions)</a>
<small id="upd"></small>
</div>
<script>
fetch('data.json').then(function(r){return r.json()}).then(function(d){
d.sort(function(a,b){return b.fecha.localeCompare(a.fecha)});
var u=d[0];
if(u){
document.getElementById('latest').innerHTML='<h2 style="font-size:16px">'+(u.titulo||'Video')+'</h2>'+
'<span class="score">Score '+(u.score!=null?u.score:'-')+'</span> <small>'+u.fecha+' · modo '+u.modo+'</small>'+
(u.url?'<video controls src="'+u.url+'"></video>':'<p><small>Sin video aun</small></p>');
}
document.getElementById('hist').innerHTML=d.map(function(v){
return '<div class="row"><span>'+v.fecha+' · '+(v.titulo||'')+'</span><span><small>score '+(v.score!=null?v.score:'-')+'</small> '+(v.url?'<a href="'+v.url+'" target="_blank">Ver</a>':'')+'</span></div>';
}).join('');
document.getElementById('upd').textContent='Actualizado: '+new Date().toLocaleString();
});
</script>
</body>
</html>"""


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{(os.getenv('R2_ACCOUNT_ID') or '').strip()}.r2.cloudflarestorage.com",
        aws_access_key_id=(os.getenv("R2_ACCESS_KEY_ID") or "").strip(),
        aws_secret_access_key=(os.getenv("R2_SECRET_ACCESS_KEY") or "").strip(),
        region_name="auto",
    )


def publicar_dashboard(info=None):
    base = (os.getenv("R2_PUBLIC_BASE") or "").strip()
    bucket = (os.getenv("R2_BUCKET") or "").strip()
    if not (base and bucket):
        log.warning("R2 publico sin configurar; salto dashboard.")
        return None
    c = _client()
    fecha = today()

    data = []
    try:
        local = Path("output/web/data.json")
        local.parent.mkdir(parents=True, exist_ok=True)
        c.download_file(bucket, "web/data.json", str(local))
        data = json.loads(local.read_text())
    except Exception:
        data = []

    url = None
    final = Path("output/final/video_final.mp4")
    if final.exists():
        key = f"web/videos/{fecha}.mp4"
        c.upload_file(str(final), bucket, key, ExtraArgs={"ContentType": "video/mp4"})
        url = f"{base.rstrip('/')}/{key}"

    titulo, score, modo = "", -1, "prueba"
    if info:
        titulo = info.get("titulo", "")
        score = info.get("score", -1)
        modo = info.get("modo", "prueba")
    else:
        sf = Path(f"output/scripts/video_{fecha}.json")
        if sf.exists():
            titulo = json.loads(sf.read_text(encoding="utf-8")).get("titulo", "")

    data = [d for d in data if d.get("fecha") != fecha]
    data.append({"fecha": fecha, "titulo": titulo, "score": score, "url": url, "modo": modo})
    data.sort(key=lambda d: d.get("fecha", ""), reverse=True)
    data = data[:60]

    local = Path("output/web/data.json")
    local.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    c.upload_file(str(local), bucket, "web/data.json",
                  ExtraArgs={"ContentType": "application/json"})

    html = Path("output/web/index.html")
    html.write_text(HTML, encoding="utf-8")
    c.upload_file(str(html), bucket, "web/index.html",
                  ExtraArgs={"ContentType": "text/html"})

    dash_url = f"{base.rstrip('/')}/web/index.html"
    log.info(f"DASHBOARD LISTO: {dash_url}")
    return dash_url
