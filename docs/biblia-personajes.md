# Biblia de personajes — Dinero Inteligente

Elenco fijo del canal. La identidad se construye con personajes recurrentes:
el espectador vuelve porque ya los conoce.

**Estilo definitivo: 3D animado (cartoon estilizado), NO 2D plano.**
Decidido 2026-08-14 tras ver la calidad conseguida en AI Studio.

**Consecuencia técnica importante:** personajes y fondos se GENERAN, no se
estilizan desde video. Por eso el pipeline diario **no necesita GPU** y
sigue funcionando en GitHub Actions.

---

## BLOQUE DE ESTILO (copiar literal, siempre)

```
3D animated character render, stylized cartoon proportions, soft even studio
lighting, plain white background, subtle contact shadow, high quality
family animation film look, sharp focus, no text, no watermark
```

**Regla de oro:** en cada generación, **adjunta la imagen del personaje** y
escribe `same character, keep the exact same design, colors, proportions and
style as the reference`. Sin la referencia adjunta, el personaje deriva.

---

## El elenco (ya generado — `assets/rodaje/`)

| Personaje | Diseño | Función narrativa |
|---|---|---|
| **Mario** | 25, gorra negra, hoodie verde, joggers negros, tenis blancos | Protagonista. Aprende. Por sus ojos entra el espectador |
| **Gastón** | 27, camisa naranja de palmeras, cadena de oro, gafas en la cabeza, bolsas de compras | Comete el error que el video explica |
| **Cata** | 26, coleta, gafas, cárdigan mostaza, libreta | Entrega los **datos** sin sonar a profesora |
| **Tío Negocio** | 45, pelo engominado, bigote, traje morado brillante, anillos, maletín | Villano cómico: enseña qué **no** hacer |
| **Doña Fanny** | 60, moño gris, vestido floreado, delantal, brazos cruzados | Remata con la verdad brutal y simple |

---

## PASO SIGUIENTE — Banco de poses

Cada pose se compone después sobre un fondo. Genera **vertical y grande**:
las primeras salieron con el cuerpo a solo ~170 px de ancho y hay que
ampliarlas 1,7x, lo que se nota.

### Plantilla de pose

```
same character, keep the exact same design, colors, proportions and style
as the reference image. Full body, <POSE>, <EXPRESION>.

vertical portrait composition, full body filling the frame, feet visible,
3D animated character render, stylized cartoon proportions, soft even studio
lighting, plain white background, subtle contact shadow, high quality
family animation film look, sharp focus, no text, no watermark
```

### Poses por tipo de beat

El ensamblador elige la pose según el tipo de beat del guion:

| Beat | Pose a generar | `<POSE>`, `<EXPRESION>` |
|---|---|---|
| `normal` | Hablando | `standing relaxed, one hand gesturing while talking`, `neutral friendly expression` |
| `dato` | Explicando | `standing, index finger raised making a point`, `confident explaining expression` |
| `punch` | Riendo | `laughing hard, head back, hand on stomach`, `big laugh` |
| `punch` | Facepalm | `palm covering face, shoulders slumped`, `exasperated` |
| `punch` | Sorpresa | `both hands on cheeks, leaning back`, `shocked wide eyes` |
| `cta` | Celebrando | `both arms raised in celebration`, `joyful` |
| — | Escéptico | `arms crossed, weight on one leg`, `raised eyebrow, skeptical` |
| — | Preocupado | `hands together, looking down`, `worried` |

### Prioridad (no generes todo de golpe)

1. **Mario: las 8 poses.** Es quien más aparece.
2. **Cata: explicando, escéptica, hablando.** Es la que da los datos.
3. **Gastón: riendo, sorpresa, preocupado.**
4. **Tío Negocio: hablando (vendiendo), sudando/nervioso.**
5. **Doña Fanny: brazos cruzados, señalando.**

Guardar en `assets/personajes/<nombre>/<pose>.png`.

---

## Escenarios (fondos)

Se generan **vacíos, sin personajes**: los personajes se componen encima.

Tres reglas:
- **Sin gente.** Si el fondo trae personas, no se puede reutilizar.
- **Vertical**, formato 9:16.
- **Varios ángulos por lugar.** Un solo encuadre repetido 20 veces es justo
  el problema que tiene el canal hoy.

Bloque de estilo para fondos (ojo: distinto al de personajes, sin "character"):

```
3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 1. LA SALA (escenario principal — donde ocurre el piloto)

```
Empty living room interior, no people. Modest latin american apartment:
worn brown fabric sofa with a crocheted blanket over the back, small wooden
coffee table, old TV on a low cabinet, framed family photos and a religious
picture on the wall, ceiling fan, beige tiled floor, window with metal
security bars and thin curtains, warm afternoon light coming in.
Lived-in and humble but tidy.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

Variantes del MISMO cuarto (añadir al final):
- `wide shot from the doorway, whole room visible`
- `closer view of the sofa area`
- `view toward the kitchen doorway`
- `low angle from near the coffee table`

### 2. LA COCINA

```
Empty kitchen interior, no people. Small latin american home kitchen: tiled
wall with faded pattern, old gas stove, dish rack, a small table with a
plastic tablecloth covered in unpaid bills and receipts, a calculator on top,
hanging pots, fridge with magnets and notes, window above the sink, warm
morning light.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 3. LA TIENDA DE BARRIO

```
Empty neighborhood corner store interior, no people. Latin american tienda
de barrio: wooden counter, shelves packed with snacks, canned goods and
sodas, hanging bags of chips, a glass drinks cooler in the corner,
handwritten price signs, single fluorescent light, worn floor.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 4. LA CALLE DEL BARRIO

```
Empty street exterior, no people. Latin american neighborhood street: red
brick low buildings, tangled power lines overhead, small shops with colorful
awnings, parked motorcycle, uneven sidewalk, distant hills, golden hour
light with long shadows.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 5. LA OFICINA (día de pago)

```
Empty office interior, no people. Plain modest office: grey cubicle divider,
old desktop computer, stacked paper trays, a wall clock, a small dying
potted plant, cheap office chair, fluorescent ceiling light, window with
grey city view.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 6. EL CAJERO AUTOMÁTICO

```
Empty ATM vestibule, no people. Small bank ATM area at night: lit ATM
machine set in a tiled wall, glass door reflecting street lights, worn
floor tiles, a trash bin, harsh cold overhead light contrasting with warm
street light outside.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### 7. EL CUARTO DE MARIO (reflexión, noche)

```
Empty small bedroom interior, no people. Young man's modest bedroom at
night: unmade single bed, desk with a laptop and a lamp, posters on the
wall, clothes on a chair, window showing city lights, only the lamp and the
laptop glow lighting the room, blue night tones.

3D animated film background, stylized cartoon environment, soft natural
lighting, vertical 9:16 composition, no people, no text, no watermark
```

### Prioridad de escenarios

Para el guion piloto **solo hacen falta los 4 ángulos de LA SALA**.
Después: Cocina → Calle → Tienda → Cuarto → Oficina → Cajero.

---

## Consistencia: qué vigilar

- Adjunta SIEMPRE la imagen de referencia del personaje.
- Si un personaje sale distinto, **no lo aceptes: regenera**. Un personaje
  inconsistente rompe la ilusión de serie. Ese es exactamente el fallo de la
  mascota vieja, que eran cinco niños distintos con ropa y proporciones
  diferentes.
- Fondo blanco liso en personajes: facilita recortarlos con `rembg`, que ya
  está instalado en el proyecto.
