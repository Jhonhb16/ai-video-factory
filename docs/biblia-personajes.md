# Biblia de personajes — Dinero Inteligente

Elenco fijo del canal. La identidad del canal se construye con personajes
recurrentes: el espectador vuelve porque ya los conoce.

**Regla de oro: el BLOQUE DE ESTILO se copia LITERAL en todos los prompts.**
Si cambia una sola palabra, cambia el estilo y los personajes dejan de
pertenecer al mismo mundo.

---

## BLOQUE DE ESTILO (copiar siempre, sin tocar)

```
flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, simple modern character design, vibrant but slightly muted
palette, plain white background, full body visible, centered, no text
```

---

## PASO 1 — Generar el elenco JUNTO (esto fija el estilo)

Genera PRIMERO esta imagen. Al salir los cinco en el mismo dibujo, el estilo
queda unificado. Esta imagen es la referencia maestra de todo lo demás.

```
Character lineup of five characters standing side by side, full body, front view.

1. MARIO: young latin man, 25, short black hair, black baseball cap worn
   forward, green hoodie, black jogger pants, white sneakers. Friendly,
   curious expression.
2. GASTON: young latin man, 27, slightly chubby, messy hair, loud orange
   shirt with palm trees, shorts, expensive flashy sneakers, gold chain,
   sunglasses on head, holding shopping bags. Carefree grin.
3. CATA: young latin woman, 26, dark hair in a practical ponytail, glasses,
   mustard cardigan over white shirt, dark jeans, flat shoes, holding a
   small notebook. Calm, confident expression.
4. TIO NEGOCIO: latin man, 45, slicked back hair, thin moustache, shiny
   cheap purple suit, open shirt, too many rings, wide salesman smile,
   holding a briefcase.
5. DONA FANNY: latin woman, 60, grey hair in a bun, floral house dress,
   apron, slippers, arms crossed, skeptical raised eyebrow.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, simple modern character design, vibrant but slightly muted
palette, plain white background, full body visible, centered, no text
```

---

## PASO 2 — Hoja individual de cada personaje

Una por personaje. Usa la imagen del PASO 1 como referencia adjunta y pide
que mantenga el diseño exacto.

Plantilla (sustituye `<DESCRIPCION>` por la del personaje del paso 1):

```
Character sheet of the same character, keep the exact same design, colors and
proportions as the reference.
<DESCRIPCION>

Show in one image: full body front view, full body side view, full body back
view, and four face closeups with these expressions: neutral, laughing hard,
worried, surprised.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, simple modern character design, vibrant but slightly muted
palette, plain white background, full body visible, centered, no text
```

---

## PASO 3 — Escenarios recurrentes

Los mismos lugares en todos los videos = mundo reconocible. Sin personajes,
solo el fondo (los personajes se componen encima).

```
Empty interior background, no people. <LUGAR>

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no text
```

Lugares a generar:
- `small modest latin american apartment kitchen with a table covered in bills`
- `neighborhood corner store (tienda de barrio) with shelves and a counter`
- `busy city street with buses and street vendors at golden hour`
- `plain office cubicle with an old computer`
- `living room with an old sofa and a TV`

---

## Consejos de consistencia

- Genera SIEMPRE con la imagen del elenco adjunta como referencia.
- Si un personaje sale distinto, no lo aceptes: regenera. Un personaje
  inconsistente rompe la ilusion de serie (el error que ya tiene la mascota
  actual, que son cinco niños distintos).
- Guarda los PNG en `assets/personajes/<nombre>/`.
- Fondo blanco liso siempre: facilita recortar al personaje despues.
