"""Spanish (es) locale module for Omni-One i18n seller replies.

Respuestas fundamentadas: cada plantilla incluye el marcador ``{citation}``
que debe rellenarse con un nombre de archivo real (por ejemplo
``instagram_dm.txt``). No se inventan n\u00fameros de pedido; los borradores
nunca contienen identificadores tipo ``#123``. Todo es determinista.

Exports:
  LOCALE, LANGUAGE_NAME, FORMALITY,
  COMPLAINT_PHRASES (15+), NEGATIVE_WORDS (20+), ISSUE_LABELS,
  DM_REPLY_TEMPLATE, REVIEW_REPLY_TEMPLATE, PO_EMAIL_TEMPLATE,
  COVER_NOTE_14D_TEMPLATE, STRINGS,
  DM_REPLY(customer, issue, citation, shop),
  REVIEW_REPLY(product, citation, shop),
  PO_EMAIL(supplier, lines, shop, citation),
  cover_note_14d(shop, citation),
  is_complaint(text), is_negative(text), get_issue_label(text),
  format_po_lines(lines), greeting(customer), closing(shop)
"""

from __future__ import annotations

LOCALE = "es"
LANGUAGE_NAME = "Espa\u00f1ol"

# ---------------------------------------------------------------------------
# Notas de formalidad
# ---------------------------------------------------------------------------
# Voz del vendedor en espa\u00f1ol: cordial y profesional, tuteo suave.
# Directrices codificadas en las plantillas:
FORMALITY = """Notas de formalidad en espa\u00f1ol (voz del vendedor):
- Saluda por el nombre cuando se conoce: "Hola {customer},".
- Tono c\u00e1lido y profesional de marketplace; sin jerga ni MAY\u00daSCULAS.
- Pide disculpas una vez, breve, sin admitir culpa legal.
- Promete un plazo concreto: "en menos de 2 horas".
- Fundamenta siempre la respuesta con una cita del archivo fuente.
- Nunca inventes n\u00fameros de pedido, de seguimiento ni de reembolso.
- Cierra con el nombre de la tienda para identificar qui\u00e9n responde.
- En rese\u00f1as, agradece incluso la cr\u00edtica negativa.
- En pedidos de compra, usa asunto claro y l\u00edneas con vi\u00f1etas.
- La nota de cobertura dice 14 d\u00edas expl\u00edcitamente ("pr\u00f3ximos 14 d\u00edas").
- Usa frases sencillas; evita modismos dif\u00edciles de traducir.
- No uses emojis en correos de compra; m\u00e1ximo un signo de exclamaci\u00f3n en DM.
- Mant\u00e9n las respuestas de DM en unas 120 palabras para copiar y pegar.
- Mant\u00e9n las respuestas a rese\u00f1as en unas 80 palabras.
- Escribe los n\u00fameros menores de diez en letra salvo "2 horas" y "14 d\u00edas".
- Menciona importes solo si el archivo fuente indica una cantidad.
- Si el problema no est\u00e1 claro, haz una pregunta concreta, no tres.
- No prometas un importe de reembolso; ofrece "reembolso o reemplazo".
- Firma con el nombre de la tienda, no con un nombre personal.
- Los nombres y horas vienen de los analizadores de canal, no inventados.
- Usa "usted" solo si el cliente lo usa primero; por defecto tuteo cordial.
- Evita anglicismos innecesarios; prefiere "pedido" a "order".
"""

# ---------------------------------------------------------------------------
# Frases de queja (15+): se\u00f1ales de insatisfacci\u00f3n del comprador.
# is_complaint() las detecta sin distinguir may\u00fasculas.
# ---------------------------------------------------------------------------

COMPLAINT_PHRASES = [
    "mi pedido lleg\u00f3 tarde",  # entrega tard\u00eda
    "mi pedido est\u00e1 retrasado",  # retraso
    "lleg\u00f3 roto",  # da\u00f1ado
    "lleg\u00f3 da\u00f1ado",  # da\u00f1ado variante
    "me enviaron el art\u00edculo equivocado",  # art\u00edculo equivocado
    "recib\u00ed el producto equivocado",  # equivocado forma larga
    "falta un art\u00edculo",  # falta pieza
    "el paquete nunca lleg\u00f3",  # perdido
    "quiero un reembolso",  # solicitud de reembolso
    "por favor reemb\u00f3lsame",  # reembolso variante
    "esto es inaceptable",  # insatisfacci\u00f3n fuerte
    "muy decepcionado",  # decepci\u00f3n
    "mala calidad",  # queja de calidad
    "no es como se describ\u00eda",  # diferencia con anuncio
    "quiero devolver esto",  # solicitud de devoluci\u00f3n
    "todav\u00eda no lo he recibido",  # espera
    "puedes ayudarme con este problema",  # petici\u00f3n de ayuda
    "el producto no funciona",  # defectuoso
]

# ---------------------------------------------------------------------------
# Palabras negativas (20+): tokens que indican insatisfacci\u00f3n.
# is_negative() las detecta sin distinguir may\u00fasculas.
# ---------------------------------------------------------------------------

NEGATIVE_WORDS = [
    "tarde",  # entrega tard\u00eda
    "roto",  # da\u00f1ado
    "rota",  # da\u00f1ado femenino
    "da\u00f1ado",  # adjetivo da\u00f1ado
    "equivocado",  # art\u00edculo equivocado
    "falta",  # falta pieza
    "perdido",  # paquete perdido
    "reembolso",  # solicitud
    "devoluci\u00f3n",  # devoluci\u00f3n
    "terrible",  # muy negativo
    "horrible",  # muy negativo
    "p\u00e9simo",  # muy negativo
    "decepcionado",  # decepci\u00f3n
    "decepcionante",  # variante
    "inaceptable",  # inaceptable
    "malo",  # gen\u00e9rico malo
    "mala",  # gen\u00e9rico mala
    "defectuoso",  # defectuoso
    "estafa",  # confianza
    "enfadado",  # emoci\u00f3n
    "molesto",  # emoci\u00f3n
    "peor",  # superlativo
    "nunca",  # nunca lleg\u00f3
    "problema",  # gen\u00e9rico
    "queja",  # queja expl\u00edcita
    "retraso",  # retraso
]

# ---------------------------------------------------------------------------
# Etiquetas de incidencia: categor\u00edas can\u00f3nicas con texto localizado.
# Las claves son estables entre idiomas; los valores est\u00e1n localizados.
# ---------------------------------------------------------------------------

ISSUE_LABELS = {
    "late": "entrega tard\u00eda",
    "damaged": "art\u00edculo da\u00f1ado",
    "wrong_item": "art\u00edculo equivocado",
    "missing": "art\u00edculo faltante",
    "lost": "paquete perdido",
    "refund": "solicitud de reembolso",
    "return": "solicitud de devoluci\u00f3n",
    "quality": "problema de calidad",
    "not_as_described": "art\u00edculo distinto al anuncio",
    "defective": "producto defectuoso",
    "shipping": "problema de env\u00edo",
    "general": "tu mensaje",
}

# ---------------------------------------------------------------------------
# Plantillas — todas incluyen {citation}; sin n\u00fameros inventados.
# ---------------------------------------------------------------------------

DM_REPLY_TEMPLATE = (
    "Hola {customer}, gracias por escribir a {shop}. "
    "Lamento el problema con {issue}. "
    "Lo revisamos ahora mismo y te respondemos en menos de 2 horas "
    "con una soluci\u00f3n (reembolso o reemplazo). "
    "Fuente: {citation}"
)

REVIEW_REPLY_TEMPLATE = (
    "Hola, gracias por tu rese\u00f1a de {product} en {shop}. "
    "Lamento que no cumpliera tus expectativas. "
    "Lo solucionaremos y te contactaremos en menos de 2 horas. "
    "Fuente: {citation}"
)

PO_EMAIL_TEMPLATE = (
    "Asunto: Solicitud de reposici\u00f3n de {shop}\n"
    "Hola {supplier},\n"
    "Por favor cotiza las siguientes l\u00edneas para {shop}:\n"
    "{lines}\n"
    "Esto cubre la demanda de los pr\u00f3ximos 14 d\u00edas. "
    "Por favor confirma plazo y precio.\n"
    "Gracias,\n"
    "{shop}\n"
    "Fuente: {citation}"
)

COVER_NOTE_14D_TEMPLATE = (
    "Nota de cobertura: este plan cubre los pr\u00f3ximos 14 d\u00edas para {shop}. "
    "Las cantidades usan las ventas de los \u00faltimos 14 d\u00edas con un peque\u00f1o margen. "
    "Fuente: {citation}"
)

GREETING_TEMPLATE = "Hola {customer},"
CLOSING_TEMPLATE = "Gracias, equipo de {shop}"

STRINGS = {
    "greeting": GREETING_TEMPLATE,
    "closing": CLOSING_TEMPLATE,
    "dm_reply": DM_REPLY_TEMPLATE,
    "review_reply": REVIEW_REPLY_TEMPLATE,
    "po_email": PO_EMAIL_TEMPLATE,
    "cover_note": COVER_NOTE_14D_TEMPLATE,
    "cover_note_14d": COVER_NOTE_14D_TEMPLATE,
    "reply_window": "Te respondemos en menos de 2 horas.",
    "cover_14d": "Esto cubre los pr\u00f3ximos 14 d\u00edas.",
    "thanks": "Gracias por escribir a {shop}.",
    "apology": "Lamento el problema con {issue}.",
}

# Alias en min\u00fasculas para b\u00fasqueda gen\u00e9rica con t().
dm_reply = DM_REPLY_TEMPLATE
review_reply = REVIEW_REPLY_TEMPLATE
po_email = PO_EMAIL_TEMPLATE
cover_note = COVER_NOTE_14D_TEMPLATE


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------

def _safe(value, fallback=""):
    """Devuelve texto sin espacios o el valor alternativo."""
    if value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    return value.strip() or fallback


def format_po_lines(lines) -> str:
    """Da formato determinista a las l\u00edneas de compra.

    Acepta lista de textos o diccionarios con claves product/qty, o un
    texto ya formateado. Las claves admitidas: product, name, title,
    sku, qty, quantity, count. Salida con vi\u00f1etas en orden de entrada.
    """
    if lines is None:
        return "- (sin l\u00edneas)"
    if isinstance(lines, str):
        text = lines.strip()
        return text if text else "- (sin l\u00edneas)"
    if isinstance(lines, dict):
        lines = [lines]
    try:
        items = list(lines)
    except TypeError:
        return _safe(lines, "- (sin l\u00edneas)")
    if not items:
        return "- (sin l\u00edneas)"
    out = []
    for entry in items:
        if isinstance(entry, dict):
            product = (
                entry.get("product")
                or entry.get("name")
                or entry.get("title")
                or entry.get("sku")
                or "art\u00edculo"
            )
            qty = (
                entry.get("qty")
                if entry.get("qty") is not None
                else entry.get("quantity", entry.get("count", 1))
            )
            out.append(f"- {product} x {qty}")
        else:
            text = _safe(entry, "")
            if text:
                if text.startswith(("-", "*", "\u2022")):
                    out.append(text if text.startswith("- ") else "- " + text.lstrip("-* \u2022"))
                else:
                    out.append(f"- {text}")
    return "\n".join(out) if out else "- (sin l\u00edneas)"


def get_issue_label(text: str) -> str:
    """Asigna un texto libre a una etiqueta localizada (determinista)."""
    lowered = (text or "").lower()
    if any(k in lowered for k in ("tarde", "retrasado", "retraso", "nunca lleg\u00f3", "todav\u00eda no")):
        return ISSUE_LABELS["late"]
    if any(k in lowered for k in ("roto", "da\u00f1ado", "defectuoso", "no funciona")):
        return ISSUE_LABELS["damaged"]
    if "equivocado" in lowered:
        return ISSUE_LABELS["wrong_item"]
    if "falta" in lowered:
        return ISSUE_LABELS["missing"]
    if any(k in lowered for k in ("perdido", "paquete")):
        return ISSUE_LABELS["lost"]
    if "reembolso" in lowered:
        return ISSUE_LABELS["refund"]
    if "devolver" in lowered or "devoluci\u00f3n" in lowered:
        return ISSUE_LABELS["return"]
    if any(k in lowered for k in ("calidad", "mala", "distinto")):
        return ISSUE_LABELS["quality"]
    if "env\u00edo" in lowered or "envio" in lowered:
        return ISSUE_LABELS["shipping"]
    return ISSUE_LABELS["general"]


def is_complaint(text: str) -> bool:
    """True si el texto contiene alguna frase de COMPLAINT_PHRASES."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in COMPLAINT_PHRASES)


def is_negative(text: str) -> bool:
    """True si el texto parece negativo (frases o palabras)."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    if is_complaint(text):
        return True
    return any(word.lower() in lowered for word in NEGATIVE_WORDS)


def greeting(customer: str) -> str:
    """Saludo localizado."""
    return GREETING_TEMPLATE.format(customer=_safe(customer, "gracias"))


def closing(shop: str) -> str:
    """Despedida localizada."""
    return CLOSING_TEMPLATE.format(shop=_safe(shop, "nuestra tienda"))


# ---------------------------------------------------------------------------
# Constructores fundamentados (todos incluyen cita; sin pedidos inventados)
# ---------------------------------------------------------------------------

def DM_REPLY(customer, issue, citation, shop) -> str:
    """Crea una respuesta de DM fundamentada en espa\u00f1ol.

    Args:
      customer: nombre del comprador.
      issue: descripci\u00f3n breve ya localizada.
      citation: archivo fuente, p. ej. instagram_dm.txt.
      shop: nombre visible de la tienda.
    """
    return DM_REPLY_TEMPLATE.format(
        customer=_safe(customer, "gracias"),
        issue=_safe(issue, ISSUE_LABELS["general"]),
        citation=_safe(citation, "instagram_dm.txt"),
        shop=_safe(shop, "nuestra tienda"),
    )


def REVIEW_REPLY(product, citation, shop) -> str:
    """Crea una respuesta p\u00fablica a rese\u00f1a en espa\u00f1ol."""
    return REVIEW_REPLY_TEMPLATE.format(
        product=_safe(product, "tu art\u00edculo"),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "nuestra tienda"),
    )


def PO_EMAIL(supplier, lines, shop, citation="inventory.csv") -> str:
    """Crea un correo de reposici\u00f3n fundamentado en espa\u00f1ol.

    ``citation`` vale inventory.csv por defecto para que el marcador
    siempre quede satisfecho aunque solo se pasen (supplier, lines, shop).
    """
    return PO_EMAIL_TEMPLATE.format(
        supplier=_safe(supplier, "proveedor"),
        lines=format_po_lines(lines),
        shop=_safe(shop, "nuestra tienda"),
        citation=_safe(citation, "inventory.csv"),
    )


def cover_note_14d(shop, citation="inventory.csv") -> str:
    """Nota de cobertura localizada de 14 d\u00edas en espa\u00f1ol."""
    return COVER_NOTE_14D_TEMPLATE.format(
        shop=_safe(shop, "nuestra tienda"),
        citation=_safe(citation, "inventory.csv"),
    )


def dm_reply(customer, issue, citation, shop) -> str:
    """Alias en min\u00fasculas de DM_REPLY."""
    return DM_REPLY(customer, issue, citation, shop)


def review_reply(product, citation, shop) -> str:
    """Alias en min\u00fasculas de REVIEW_REPLY."""
    return REVIEW_REPLY(product, citation, shop)


def po_email(supplier, lines, shop, citation="inventory.csv") -> str:
    """Alias en min\u00fasculas de PO_EMAIL."""
    return PO_EMAIL(supplier, lines, shop, citation)


# Alias compatibles con siglas internas de negatividad.
dm_reply_fn = DM_REPLY
review_reply_fn = REVIEW_REPLY
po_email_fn = PO_EMAIL

__all__ = [
    "LOCALE",
    "LANGUAGE_NAME",
    "FORMALITY",
    "COMPLAINT_PHRASES",
    "NEGATIVE_WORDS",
    "ISSUE_LABELS",
    "DM_REPLY_TEMPLATE",
    "REVIEW_REPLY_TEMPLATE",
    "PO_EMAIL_TEMPLATE",
    "COVER_NOTE_14D_TEMPLATE",
    "STRINGS",
    "DM_REPLY",
    "REVIEW_REPLY",
    "PO_EMAIL",
    "cover_note_14d",
    "is_complaint",
    "is_negative",
    "get_issue_label",
    "format_po_lines",
    "greeting",
    "closing",
]


# ---------------------------------------------------------------------------
# Ap\u00e9ndice: ejemplos de uso y garant\u00edas de fundamento (documentaci\u00f3n real).
# ---------------------------------------------------------------------------
# Ejemplo DM:
#   DM_REPLY("Mar\u00eda", "entrega tard\u00eda", "instagram_dm.txt", "Solmar")
#   -> "Hola Mar\u00eda, gracias por escribir a Solmar. Lamento el problema con
#       entrega tard\u00eda. Lo revisamos ahora mismo y te respondemos en menos
#       de 2 horas con una soluci\u00f3n (reembolso o reemplazo).
#       Fuente: instagram_dm.txt"
# Ejemplo rese\u00f1a:
#   REVIEW_REPLY("Tote de lona", "reviews.csv", "Solmar")
#   -> agradecimiento + disculpa + promesa 2 horas + "Fuente: reviews.csv".
# Ejemplo compra:
#   PO_EMAIL("Acme", [{"product": "Tote de lona", "qty": 20}], "Solmar")
#   -> Asunto + vi\u00f1eta "- Tote de lona x 20" + cobertura 14 d\u00edas
#      + "Fuente: inventory.csv".
# Fundamento:
#   - Cada plantilla renderizada contiene su cita literalmente.
#   - Ninguna plantilla contiene "#" seguido de d\u00edgitos (sin pedidos inventados).
#   - Constructores con valores seguros; nunca fallan con None.
#   - Funciones puras: mismos inputs -> mismos outputs.
# Determinismo:
#   - Sin relojes, sin azar, sin red, sin IO en este m\u00f3dulo.
#   - format_po_lines preserva el orden de entrada para diffs estables.
#   - get_issue_label prioriza tarde/da\u00f1ado para categorizaci\u00f3n estable.
# Ver tambi\u00e9n: drafts.build_reply, drafts.build_po, channels.normalize_dm.
# Fin del m\u00f3dulo de idioma es.

