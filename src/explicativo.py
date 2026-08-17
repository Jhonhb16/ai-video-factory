"""Genera la composicion HyperFrames de un video explicativo.

Cada frase se ilustra segun lo que CONTIENE, no todas igual:
  proporcion  -> barra que se reparte en tres tramos (la regla 50/30/20)
  porcentaje  -> barra que se llena hasta el valor + cifra grande
  cifra       -> numero grande que entra con golpe
  comparacion -> dos paneles enfrentados
  texto       -> tipografia con la palabra clave resaltada

Variar la tecnica es lo que evita que el video se sienta previsible, que es
el problema real de retencion. El render lo hace HyperFrames (HTML -> MP4).
"""
import html
import json
import logging
from pathlib import Path

from src.cifras import analizar, formatear

log = logging.getLogger("VideoFactory.Explicativo")

W, H = 1080, 1920

# Paleta dark-tech. El verde es "tu dinero", el rojo "lo que se va".
FONDO = "#070b12"
VERDE = "#22e39a"
ROJO = "#ff4d6d"
AMBAR = "#ffc857"
TEXTO = "#f2f6ff"
TENUE = "#5f7191"

COLOR_BEAT = {"punch": ROJO, "dato": VERDE, "hook": AMBAR, "cta": VERDE}


def _color(beat):
    return COLOR_BEAT.get(beat, VERDE)


def _visual(i, frase, info, color):
    """HTML del elemento grafico de la escena (la mitad superior)."""
    t = info["tipo"]

    if t == "proporcion":
        partes = info["partes"]
        tonos = [VERDE, AMBAR, ROJO]
        etiquetas = ["necesidades", "gustos", "ahorro"]
        tramos = "".join(
            f'<div class="tramo" id="tr-{i}-{j}" '
            f'style="width:{p}%;background:{tonos[j % 3]}">'
            f'<span class="tramo-num">{p}%</span>'
            f'<span class="tramo-tag">{etiquetas[j % 3]}</span></div>'
            for j, p in enumerate(partes))
        return f'<div class="barra-total" id="vis-{i}">{tramos}</div>'

    if t == "porcentaje":
        v = info["valor"]
        return (f'<div class="pct-wrap" id="vis-{i}">'
                f'<div class="pct-num" style="color:{color}">{v}<span>%</span></div>'
                f'<div class="pct-riel"><div class="pct-fill" id="fill-{i}" '
                f'style="width:{v}%;background:{color}"></div></div></div>')

    if t == "cifra":
        return (f'<div class="cifra-wrap" id="vis-{i}">'
                f'<div class="cifra-num" style="color:{color}">'
                f'{html.escape(formatear(info["valor"], info["unidad"]))}</div>'
                f'<div class="cifra-linea" style="background:{color}"></div></div>')

    if t == "comparacion":
        return (f'<div class="comp" id="vis-{i}">'
                f'<div class="comp-lado" id="comp-a-{i}" style="border-color:{VERDE}"></div>'
                f'<div class="comp-vs">vs</div>'
                f'<div class="comp-lado" id="comp-b-{i}" style="border-color:{ROJO}"></div>'
                f'</div>')

    # texto: un simple pulso de acento que da presencia al vacio
    return (f'<div class="marca" id="vis-{i}">'
            f'<div class="marca-punto" style="background:{color}"></div></div>')


def _frase_html(i, frase, info, color):
    """Texto con la expresion clave resaltada."""
    seguro = html.escape(frase)
    clave = info.get("expresion")
    if clave:
        seguro_clave = html.escape(clave)
        if seguro_clave in seguro:
            seguro = seguro.replace(
                seguro_clave,
                f'<span class="clave" style="color:{color}">{seguro_clave}</span>', 1)
    return f'<div class="frase" id="frase-{i}">{seguro}</div>'


def _escena(i, it, total, info):
    ini = it["start"]
    dur = max(0.4, it["end"] - it["start"])
    color = _color(it.get("k", "normal"))
    return f'''    <section id="esc-{i}" class="clip" data-start="{ini:.3f}"
             data-duration="{dur:.3f}" data-track-index="1">
      <div class="fondo"></div>
      <div class="rejilla"></div>
      <div class="hud">{i + 1:02d}<span>/{total:02d}</span></div>
      <div class="zona-visual">{_visual(i, it["txt"], info, color)}</div>
      {_frase_html(i, it["txt"], info, color)}
      <div class="progreso" id="prog-{i}" style="background:{color}"></div>
    </section>
'''


def _tweens(i, it, info):
    """Animaciones de la escena. fromTo siempre: nunca transform en CSS."""
    ini = it["start"]
    dur = max(0.4, it["end"] - it["start"])
    entra = min(0.5, dur * 0.4)
    t = [
        f'tl.fromTo("#frase-{i}",{{y:70,autoAlpha:0}},'
        f'{{y:0,autoAlpha:1,duration:{entra:.2f},ease:"power3.out"}},{ini:.3f});',
        f'tl.fromTo("#prog-{i}",{{scaleX:0}},'
        f'{{scaleX:1,duration:{dur:.2f},ease:"none"}},{ini:.3f});',
    ]
    tipo = info["tipo"]

    if tipo == "proporcion":
        for j in range(len(info["partes"])):
            t.append(f'tl.fromTo("#tr-{i}-{j}",{{scaleX:0}},'
                     f'{{scaleX:1,duration:0.5,ease:"power2.out"}},'
                     f'{ini + 0.12 + j * 0.16:.3f});')
    elif tipo == "porcentaje":
        t.append(f'tl.fromTo("#fill-{i}",{{scaleX:0}},'
                 f'{{scaleX:1,duration:0.8,ease:"power2.out"}},{ini + 0.1:.3f});')
        t.append(f'tl.fromTo("#vis-{i}",{{autoAlpha:0,y:30}},'
                 f'{{autoAlpha:1,y:0,duration:0.4,ease:"power2.out"}},{ini:.3f});')
    elif tipo == "cifra":
        t.append(f'tl.fromTo("#vis-{i}",{{scale:0.55,autoAlpha:0}},'
                 f'{{scale:1,autoAlpha:1,duration:0.45,ease:"back.out(2.2)"}},{ini + 0.05:.3f});')
    elif tipo == "comparacion":
        t.append(f'tl.fromTo("#comp-a-{i}",{{x:-90,autoAlpha:0}},'
                 f'{{x:0,autoAlpha:1,duration:0.45,ease:"power3.out"}},{ini + 0.08:.3f});')
        t.append(f'tl.fromTo("#comp-b-{i}",{{x:90,autoAlpha:0}},'
                 f'{{x:0,autoAlpha:1,duration:0.45,ease:"power3.out"}},{ini + 0.16:.3f});')
    else:
        t.append(f'tl.fromTo("#vis-{i}",{{scale:0.8,autoAlpha:0}},'
                 f'{{scale:1,autoAlpha:0.9,duration:0.5,ease:"power2.out"}},{ini:.3f});')
    return "\n      ".join(t)


def _estilos():
    return f'''
  body {{ margin:0; background:{FONDO}; color:{TEXTO};
         font-family:"Segoe UI",Inter,system-ui,sans-serif; }}
  #root {{ position:relative; width:{W}px; height:{H}px; overflow:hidden; }}
  .clip {{ position:absolute; inset:0; }}
  .fondo {{ position:absolute; inset:0;
    background:radial-gradient(125% 75% at 50% 20%, #13233f 0%, {FONDO} 64%); }}
  .rejilla {{ position:absolute; inset:0; opacity:.10;
    background-image:linear-gradient(rgba(120,160,255,.5) 1px,transparent 1px),
                     linear-gradient(90deg,rgba(120,160,255,.5) 1px,transparent 1px);
    background-size:90px 90px; }}
  .hud {{ position:absolute; top:92px; right:70px; font-size:38px; font-weight:700;
    letter-spacing:.14em; color:{TENUE}; font-variant-numeric:tabular-nums; }}
  .hud span {{ font-size:26px; opacity:.65; }}

  .zona-visual {{ position:absolute; top:300px; left:0; width:{W}px; height:760px;
    display:flex; align-items:center; justify-content:center; }}

  .barra-total {{ display:flex; width:{W - 160}px; height:230px;
    border-radius:26px; overflow:hidden; }}
  .tramo {{ position:relative; height:100%; transform-origin:left center;
    display:flex; flex-direction:column; align-items:center; justify-content:center; }}
  .tramo-num {{ font-size:78px; font-weight:800; color:#07121d; line-height:1; }}
  .tramo-tag {{ font-size:26px; font-weight:600; color:#07121d; opacity:.72;
    margin-top:10px; }}

  .pct-wrap {{ width:{W - 160}px; text-align:center; }}
  .pct-num {{ font-size:300px; font-weight:800; line-height:.95;
    font-variant-numeric:tabular-nums; }}
  .pct-num span {{ font-size:150px; opacity:.8; }}
  .pct-riel {{ margin-top:46px; height:34px; border-radius:17px;
    background:rgba(255,255,255,.09); overflow:hidden; }}
  .pct-fill {{ height:100%; transform-origin:left center; }}

  .cifra-wrap {{ text-align:center; }}
  .cifra-num {{ font-size:250px; font-weight:800; line-height:1;
    font-variant-numeric:tabular-nums; }}
  .cifra-linea {{ height:12px; width:340px; margin:40px auto 0; border-radius:6px; }}

  .comp {{ display:flex; align-items:center; gap:52px; }}
  .comp-lado {{ width:330px; height:330px; border:9px solid; border-radius:34px;
    background:rgba(255,255,255,.045); }}
  .comp-vs {{ font-size:62px; font-weight:800; color:{TENUE}; }}

  .marca {{ display:flex; align-items:center; justify-content:center; }}
  .marca-punto {{ width:190px; height:190px; border-radius:50%; opacity:.85; }}

  .frase {{ position:absolute; top:1210px; left:80px; width:{W - 160}px;
    font-size:88px; font-weight:700; line-height:1.16; }}
  .clave {{ font-weight:800; }}
  .progreso {{ position:absolute; left:0; bottom:0; width:{W}px; height:12px;
    transform-origin:left center; }}
'''


def generar_composicion(guion, items, duracion, destino):
    """Escribe index.html + package.json. Devuelve la carpeta del proyecto."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    infos = [analizar(it["txt"]) for it in items]
    escenas = "\n".join(_escena(i, it, len(items), infos[i])
                        for i, it in enumerate(items))
    animaciones = "\n      ".join(_tweens(i, it, infos[i])
                                  for i, it in enumerate(items))

    doc = f'''<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<title>Dinero Inteligente</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>{_estilos()}</style>
</head>
<body>
  <div id="root" data-composition-id="main" data-start="0"
       data-width="{W}" data-height="{H}" data-duration="{duracion:.3f}">
{escenas}  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true }});
      {animaciones}
    window.__timelines["main"] = tl;
  </script>
</body>
</html>
'''
    (destino / "index.html").write_text(doc, encoding="utf-8")
    (destino / "package.json").write_text(json.dumps({
        "name": "explicativo", "private": True, "type": "module",
        "scripts": {"check": "npx --yes hyperframes@latest check",
                    "render": "npx --yes hyperframes@latest render"},
    }, indent=2), encoding="utf-8")

    from collections import Counter
    reparto = Counter(x["tipo"] for x in infos)
    log.info(f"Composicion: {len(items)} escenas -> " +
             ", ".join(f"{k} {v}" for k, v in reparto.most_common()))
    return destino
