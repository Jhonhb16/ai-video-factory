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

Los mismos lugares en todos los videos = mundo reconocible. Se generan
**vacíos, sin personajes**: los personajes se componen encima despues.

Tres reglas:
- **Sin gente.** Si el fondo trae personas, no se puede reutilizar.
- **Vertical.** El formato final es 9:16.
- **Varios ángulos por lugar.** Un solo encuadre repetido 20 veces es
  justo el problema que tiene el canal hoy.

### 1. LA SALA (escenario principal — donde ocurre el piloto)

```
Empty living room interior background, no people. Modest latin american
apartment: worn brown fabric sofa with a crocheted blanket over the back,
small wooden coffee table, old CRT-style TV on a low cabinet, framed family
photos and a religious picture on the wall, ceiling fan, beige tiled floor,
window with metal security bars and thin curtains, warm afternoon light
coming in. Lived-in and humble but tidy.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

Genera además estas variantes del MISMO cuarto (añade la frase al final):
- `wide shot from the doorway, whole room visible`
- `closer view of the sofa area, shallow depth`
- `view toward the kitchen doorway`
- `low angle from near the coffee table`

### 2. LA COCINA

```
Empty kitchen interior background, no people. Small latin american home
kitchen: tiled wall with faded pattern, old gas stove, dish rack, a small
table with a plastic tablecloth covered in unpaid bills and receipts, a
calculator on top, hanging pots, fridge with magnets and notes, window
above the sink, warm morning light.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

### 3. LA TIENDA DE BARRIO

```
Empty neighborhood corner store interior, no people. Latin american tienda
de barrio: wooden counter, shelves packed with snacks, canned goods and
sodas, hanging bags of chips, a glass drinks cooler humming in the corner,
handwritten price signs, single fluorescent light, worn floor.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

### 4. LA CALLE DEL BARRIO

```
Empty street exterior background, no people. Latin american neighborhood
street: red brick low buildings, tangled power lines overhead, small shops
with colorful awnings, parked motorcycle, uneven sidewalk, distant hills,
golden hour light with long shadows.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

### 5. LA OFICINA (día de pago)

```
Empty office interior background, no people. Plain modest office: grey
cubicle divider, old desktop computer, stacked paper trays, a wall clock,
a small dying potted plant, cheap office chair, fluorescent ceiling light,
window with grey city view.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

### 6. EL CAJERO AUTOMÁTICO

```
Empty ATM vestibule background, no people. Small bank ATM area at night:
lit ATM machine set in a tiled wall, glass door reflecting street lights,
worn floor tiles, a trash bin, harsh cold overhead light contrasting with
warm street light outside.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

### 7. EL CUARTO DE MARIO (reflexión, noche)

```
Empty small bedroom interior background, no people. Young man's modest
bedroom at night: unmade single bed, desk with a laptop and a lamp, posters
on the wall, clothes on a chair, window showing city lights, only the lamp
and the laptop glow lighting the room, blue night tones.

flat 2D anime style, clean bold black outlines, solid flat colors, cel shading
with hard shadows, vibrant but slightly muted palette, vertical composition,
no people, no text
```

---

## Prioridad de generación

No los generes todos de golpe. Para el guion piloto **solo hacen falta los
4 ángulos de LA SALA** (escenario 1). Con eso se produce el video entero.

Orden recomendado: **Sala → Cocina → Calle → Tienda → Cuarto → Oficina →
Cajero.** Los tres primeros cubren la mayoría de guiones de finanzas
domésticas.

---

## Consejos de consistencia

- Genera SIEMPRE con la imagen del elenco adjunta como referencia.
- Si un personaje sale distinto, no lo aceptes: regenera. Un personaje
  inconsistente rompe la ilusion de serie (el error que ya tiene la mascota
  actual, que son cinco niños distintos).
- Guarda los PNG en `assets/personajes/<nombre>/`.
- Fondo blanco liso siempre: facilita recortar al personaje despues.
