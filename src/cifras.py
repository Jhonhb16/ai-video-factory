"""Encuentra cifras en el guion, incluidas las escritas con letra.

Por que hace falta: el guionista escribe "el cincuenta por ciento" y "diez mil
pesos", no "50%" ni "10000". Buscando solo digitos se detectaban 2 cifras de
25 frases, y en un canal de finanzas la cifra ES el contenido: es lo que se
puede convertir en un grafico y lo que la gente recuerda.
"""
import re

UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuno": 21, "veinticinco": 25,
    "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
    "setenta": 70, "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "quinientos": 500,
}
MULTIPLICADORES = {"mil": 1000, "millon": 1000000, "millón": 1000000,
                   "millones": 1000000}

# "50/30/20": la regla estrella de finanzas personales. Merece grafico propio.
PROPORCION = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\s*/\s*(\d{1,3})\b")
PORCENTAJE_DIGITO = re.compile(r"\b(\d{1,3})\s*(?:%|por\s*ciento)")
NUMERO_DIGITO = re.compile(r"\b(\d[\d.,]*)\b")

CONTRASTE = re.compile(
    r"\b(pero|mientras|en vez de|en lugar de|aunque|sin embargo|no es|y no)\b",
    re.IGNORECASE)


def _normalizar(p):
    return p.lower().strip(".,;:¡!¿?()")


def _valor_en_palabras(texto):
    """Devuelve (valor, expresion) de la primera cifra escrita con letra."""
    palabras = texto.split()
    for i, bruta in enumerate(palabras):
        p = _normalizar(bruta)
        if p not in UNIDADES:
            continue
        valor = UNIDADES[p]
        usadas = [bruta]

        # "cincuenta y cinco"
        if i + 2 < len(palabras) and _normalizar(palabras[i + 1]) == "y":
            sig = _normalizar(palabras[i + 2])
            if sig in UNIDADES and UNIDADES[sig] < 10 and valor >= 20:
                valor += UNIDADES[sig]
                usadas += [palabras[i + 1], palabras[i + 2]]

        # "diez mil", "dos millones"
        j = i + len(usadas)
        if j < len(palabras):
            mult = _normalizar(palabras[j])
            if mult in MULTIPLICADORES:
                valor *= MULTIPLICADORES[mult]
                usadas.append(palabras[j])
                j += 1

        # unidad final: "por ciento" / "pesos"
        unidad = ""
        resto = " ".join(_normalizar(x) for x in palabras[j:j + 2])
        if resto.startswith("por ciento"):
            unidad = "%"
            usadas += palabras[j:j + 2]
        elif resto.startswith("pesos"):
            unidad = "$"
            usadas.append(palabras[j])

        return valor, unidad, " ".join(usadas)
    return None


def analizar(texto):
    """Describe que hay en la frase, para decidir como ilustrarla.

    Devuelve un dict con 'tipo' entre: proporcion | porcentaje | cifra |
    comparacion | texto.
    """
    m = PROPORCION.search(texto)
    if m:
        partes = [int(x) for x in m.groups()]
        if 90 <= sum(partes) <= 110:          # solo si de verdad reparte un total
            return {"tipo": "proporcion", "partes": partes, "expresion": m.group(0)}

    m = PORCENTAJE_DIGITO.search(texto)
    if m:
        return {"tipo": "porcentaje", "valor": int(m.group(1)),
                "unidad": "%", "expresion": m.group(0)}

    palabras = _valor_en_palabras(texto)
    if palabras:
        valor, unidad, expresion = palabras
        if unidad == "%":
            return {"tipo": "porcentaje", "valor": valor, "unidad": "%",
                    "expresion": expresion}
        return {"tipo": "cifra", "valor": valor, "unidad": unidad,
                "expresion": expresion}

    m = NUMERO_DIGITO.search(texto)
    if m:
        crudo = m.group(1).replace(".", "").replace(",", "")
        if crudo.isdigit():
            return {"tipo": "cifra", "valor": int(crudo), "unidad": "",
                    "expresion": m.group(1)}

    if CONTRASTE.search(texto):
        return {"tipo": "comparacion", "expresion": CONTRASTE.search(texto).group(0)}

    return {"tipo": "texto"}


def formatear(valor, unidad):
    """1000 -> '1.000'; 50 con '%' -> '50%'."""
    if valor >= 1000:
        txt = f"{valor:,}".replace(",", ".")
    else:
        txt = str(valor)
    if unidad == "%":
        return txt + "%"
    if unidad == "$":
        return "$" + txt
    return txt
