"""Consolida data scrapeada + transcripciones en contexto-viral.md."""
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger("VideoFactory.Intelligence")
OUTPUT_FILE = Path("output/intelligence/contexto-viral.md")


def construir_contexto(videos_data):
    for item in videos_data:
        v = item["video"]
        views = v.get("viewsCount", 0) or 0
        likes = v.get("likesCount", 0) or 0
        comments = v.get("commentsCount", 0) or 0
        shares = v.get("sharesCount", 0) or 0
        item["engagement_score"] = views + (likes * 5) + (comments * 10) + (shares * 8)

    videos_data.sort(key=lambda x: x["engagement_score"], reverse=True)

    lines = ["# CONTEXTO VIRAL - Finanzas Personales (ES)",
             f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"Total videos analizados: {len(videos_data)}",
             f"Videos con transcripcion: {sum(1 for x in videos_data if x.get('transcripcion'))}",
             "", "---", ""]

    for i, item in enumerate(videos_data, 1):
        v = item["video"]
        t = item.get("transcripcion") or {}
        lines.append(f"## Video {i} - {item['referente']}")
        lines.append(f"- **Views:** {v.get('viewsCount', 0)}")
        lines.append(f"- **Likes:** {v.get('likesCount', 0)}")
        lines.append(f"- **Comentarios:** {v.get('commentsCount', 0)}")
        lines.append(f"- **Compartidos:** {v.get('sharesCount', 0)}")
        lines.append(f"- **Engagement score:** {item['engagement_score']}")
        caption = v.get("caption", "") or ""
        if caption:
            lines.append(f"- **Caption:** {caption[:500]}")
        if t.get("texto"):
            lines.append(f"- **Transcripcion ({t.get('duracion_segundos', 0)}s, {t.get('palabras', 0)} palabras):**")
            lines.append(f"  > {t['texto']}")
        lines.append(f"- **URL:** {v.get('url', 'N/A')}")
        lines.append("")

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Contexto viral generado: {OUTPUT_FILE} ({len(videos_data)} videos)")
    return OUTPUT_FILE
