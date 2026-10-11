"""German (de) locale module for Omni-One i18n seller replies.

Geerdete Vorlagen: Jede Vorlage enth\u00e4lt einen ``{citation}``-Platzhalter,
der mit einem echten Quelldateinamen zu f\u00fcllen ist (z. B. ``reviews.csv``
oder ``amazon_messages.csv``). Keine Bestellnummern werden erfunden;
Entw\u00fcrfe enthalten niemals IDs wie ``#123``. Alle Funktionen deterministisch.

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

LOCALE = "de"
LANGUAGE_NAME = "Deutsch"

# ---------------------------------------------------------------------------
# Formalit\u00e4tshinweise
# ---------------------------------------------------------------------------
# Deutsche Verk\u00e4uferstimme: h\u00f6flich, sachlich, Sie-Form.
# In den Vorlagen kodierte Regeln:
FORMALITY = """Formal\u00e4tshinweise Deutsch (Verk\u00e4uferstimme):
- Mit Vornamen begr\u00fc\u00dfen, wenn bekannt: "Hallo {customer},".
- H\u00f6flicher, professioneller Marktplatz-Ton; kein Slang, keine GROSSBUCHSTABEN.
- Einmal kurz entschuldigen, ohne rechtliches Schuldeingest\u00e4ndnis.
- Konkretes Antwortfenster versprechen: "innerhalb von 2 Stunden".
- Antwort immer mit Zitat der Quelldatei erden.
- Niemals Bestell-, Tracking- oder Erstattungsnummern erfinden.
- Mit Shopnamen schlie\u00dfen, damit klar ist, wer antwortet.
- Bei Bewertungen auch f\u00fcr kritisches Feedback danken.
- Bei Lieferantenbestellungen klare Betreffzeile und Stichpunktzeilen.
- Deckungsnotiz nennt 14 Tage explizit ("n\u00e4chsten 14 Tage").
- Einfache S\u00e4tze; schwer \u00fcbersetzbare Idiome vermeiden.
- Keine Emojis in Bestellmails; max. ein Ausrufezeichen in DMs.
- DM-Antworten ca. 120 W\u00f6rter f\u00fcr Copy-Paste in Chattools.
- Bewertungsantworten ca. 80 W\u00f6rter f\u00fcr Marktplatz-Posts.
- Zahlen unter zehn ausschreiben au\u00dfer "2 Stunden" / "14 Tage".
- Betr\u00e4ge nur nennen, wenn die Quelldaten einen Betrag nennen.
- Bei unklarer Sache genau eine Kl\u00e4rungsfrage stellen, nicht drei.
- Keinen Erstattungsbetrag versprechen; "Erstattung oder Ersatz" anbieten.
- Mit Shopnamen signieren, nicht mit Personennamen, f\u00fcr Teamnutzung.
- Zeitstempel und Absender kommen aus Kanalparsern, nicht erfunden.
- Standardm\u00e4\u00dfig Sie-Form; Du nur, wenn der Kunde es vormacht.
- Anglizismen meiden; lieber "Bestellung" als "order".
"""

# ---------------------------------------------------------------------------
# Beschwerdephrasen (15+): typische Unzufriedenheits\u00e4u\u00dferungen.
# is_complaint() erkennt sie case-insensitiv als Teilstrings.
# ---------------------------------------------------------------------------

COMPLAINT_PHRASES = [
    "meine bestellung kam zu sp\u00e4t an",  # sp\u00e4te Lieferung
    "meine bestellung ist versp\u00e4tet",  # Versp\u00e4tung kurz
    "kaputt angekommen",  # besch\u00e4digt
    "besch\u00e4digt angekommen",  # besch\u00e4digt Variante
    "falscher artikel gesendet",  # falscher Artikel
    "ich habe den falschen artikel erhalten",  # langform
    "ein artikel fehlt",  # fehlendes Teil
    "das paket ist nie angekommen",  # verloren
    "ich m\u00f6chte eine erstattung",  # Erstattungswunsch
    "bitte erstatten sie mir den betrag",  # Erstattung Variante
    "das ist inakzeptabel",  # starke Unzufriedenheit
    "sehr entt\u00e4uscht",  # Entt\u00e4uschung
    "schlechte qualit\u00e4t",  # Qualit\u00e4tsbeschwerde
    "nicht wie beschrieben",  # Angebotsabweichung
    "ich m\u00f6chte das zur\u00fccksenden",  # R\u00fccksendungswunsch
    "ich habe es immer noch nicht erhalten",  # Warten
    "k\u00f6nnen sie mir bei diesem problem helfen",  # Hilfebitte
    "das produkt funktioniert nicht",  # defekt
]

# ---------------------------------------------------------------------------
# Negativw\u00f6rter (20+): Tokens f\u00fcr Unzufriedenheit.
# is_negative() erkennt sie case-insensitiv.
# ---------------------------------------------------------------------------

NEGATIVE_WORDS = [
    "versp\u00e4tet",  # sp\u00e4te Lieferung
    "kaputt",  # besch\u00e4digt
    "besch\u00e4digt",  # Adjektiv
    "falsch",  # falscher Artikel
    "fehlt",  # fehlt
    "fehlend",  # fehlend
    "verloren",  # verlorenes Paket
    "erstattung",  # Wunsch
    "r\u00fccksendung",  # R\u00fccksendung
    "zur\u00fcck",  # zur\u00fcck-Variante
    "schrecklich",  # stark negativ
    "furchtbar",  # stark negativ
    "schlimm",  # stark negativ
    "entt\u00e4uscht",  # Entt\u00e4uschung
    "entt\u00e4uschend",  # Variante
    "inakzeptabel",  # inakzeptabel
    "schlecht",  # schlechte Qualit\u00e4t
    "schlechte",  # flektiert
    "defekt",  # defekt
    "betrug",  # Vertrauen
    "w\u00fctend",  # Emotion
    "ver\u00e4rgert",  # Emotion
    "schlimmste",  # Superlativ
    "nie",  # nie angekommen
    "beschwerde",  # explizite Beschwerde
    "reklamation",  # Reklamation
    "mangel",  # Mangel
]

# ---------------------------------------------------------------------------
# Anliegenslabels: stabile Keys, lokalisierte Werte.
# ---------------------------------------------------------------------------

ISSUE_LABELS = {
    "late": "versp\u00e4tete Lieferung",
    "damaged": "besch\u00e4digter Artikel",
    "wrong_item": "falscher Artikel",
    "missing": "fehlender Artikel",
    "lost": "verlorenes Paket",
    "refund": "Erstattungswunsch",
    "return": "R\u00fccksendungswunsch",
    "quality": "Qualit\u00e4tsproblem",
    "not_as_described": "Artikel abweichend vom Angebot",
    "defective": "defektes Produkt",
    "shipping": "Versandproblem",
    "general": "Ihre Nachricht",
}

# ---------------------------------------------------------------------------
# Vorlagen \u2014 jede enth\u00e4lt {citation}; keine erfundenen Nummern.
# ---------------------------------------------------------------------------

DM_REPLY_TEMPLATE = (
    "Hallo {customer}, danke f\u00fcr Ihre Nachricht an {shop}. "
    "Es tut uns leid wegen {issue}. "
    "Wir pr\u00fcfen das sofort und antworten innerhalb von 2 Stunden "
    "mit einer L\u00f6sung (Erstattung oder Ersatz). "
    "Quelle: {citation}"
)

REVIEW_REPLY_TEMPLATE = (
    "Hallo, danke f\u00fcr Ihre Bewertung zu {product} bei {shop}. "
    "Es tut uns leid, dass sie nicht Ihren Erwartungen entsprach. "
    "Wir bringen das in Ordnung und melden uns innerhalb von 2 Stunden. "
    "Quelle: {citation}"
)

PO_EMAIL_TEMPLATE = (
    "Betreff: Nachbestellanfrage von {shop}\n"
    "Hallo {supplier},\n"
    "Bitte erstellen Sie ein Angebot f\u00fcr folgende Positionen f\u00fcr {shop}:\n"
    "{lines}\n"
    "Dies deckt den Bedarf der n\u00e4chsten 14 Tage ab. "
    "Bitte best\u00e4tigen Sie Lieferzeit und Preis.\n"
    "Danke,\n"
    "{shop}\n"
    "Quelle: {citation}"
)

COVER_NOTE_14D_TEMPLATE = (
    "Deckungshinweis: Dieser Plan deckt die n\u00e4chsten 14 Tage f\u00fcr {shop} ab. "
    "Mengen basieren auf den Verk\u00e4ufen der letzten 14 Tage plus kleinem Puffer. "
    "Quelle: {citation}"
)

GREETING_TEMPLATE = "Hallo {customer},"
CLOSING_TEMPLATE = "Danke, Ihr {shop}-Team"

STRINGS = {
    "greeting": GREETING_TEMPLATE,
    "closing": CLOSING_TEMPLATE,
    "dm_reply": DM_REPLY_TEMPLATE,
    "review_reply": REVIEW_REPLY_TEMPLATE,
    "po_email": PO_EMAIL_TEMPLATE,
    "cover_note": COVER_NOTE_14D_TEMPLATE,
    "cover_note_14d": COVER_NOTE_14D_TEMPLATE,
    "reply_window": "Wir antworten innerhalb von 2 Stunden.",
    "cover_14d": "Dies deckt die n\u00e4chsten 14 Tage ab.",
    "thanks": "Danke f\u00fcr Ihre Nachricht an {shop}.",
    "apology": "Es tut uns leid wegen {issue}.",
}

dm_reply = DM_REPLY_TEMPLATE
review_reply = REVIEW_REPLY_TEMPLATE
po_email = PO_EMAIL_TEMPLATE
cover_note = COVER_NOTE_14D_TEMPLATE


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _safe(value, fallback=""):
    """Gibt getrimmten Text oder Fallback zur\u00fcck."""
    if value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    return value.strip() or fallback


def format_po_lines(lines) -> str:
    """Formatiert Bestellzeilen deterministisch.

    Akzeptiert Liste aus Strings oder Dicts mit product/qty-Keys oder einen
    bereits formatierten String. Unterst\u00fctzte Keys: product, name, title,
    sku, qty, quantity, count. Ausgabe mit Spiegelstrichen in Eingabereihenfolge.
    """
    if lines is None:
        return "- (keine Positionen)"
    if isinstance(lines, str):
        text = lines.strip()
        return text if text else "- (keine Positionen)"
    if isinstance(lines, dict):
        lines = [lines]
    try:
        items = list(lines)
    except TypeError:
        return _safe(lines, "- (keine Positionen)")
    if not items:
        return "- (keine Positionen)"
    out = []
    for entry in items:
        if isinstance(entry, dict):
            product = (
                entry.get("product")
                or entry.get("name")
                or entry.get("title")
                or entry.get("sku")
                or "Artikel"
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
    return "\n".join(out) if out else "- (keine Positionen)"


def get_issue_label(text: str) -> str:
    """Ordnet Freitext einem lokalisierten Label zu (deterministisch)."""
    lowered = (text or "").lower()
    if any(k in lowered for k in ("versp\u00e4tet", "zu sp\u00e4t", "nie angekommen", "immer noch nicht")):
        return ISSUE_LABELS["late"]
    if any(k in lowered for k in ("kaputt", "besch\u00e4digt", "defekt", "funktioniert nicht")):
        return ISSUE_LABELS["damaged"]
    if "falsch" in lowered:
        return ISSUE_LABELS["wrong_item"]
    if "fehlt" in lowered or "fehlend" in lowered:
        return ISSUE_LABELS["missing"]
    if any(k in lowered for k in ("verloren", "paket")):
        return ISSUE_LABELS["lost"]
    if "erstattung" in lowered:
        return ISSUE_LABELS["refund"]
    if any(k in lowered for k in ("r\u00fccksend", "zur\u00fcck")):
        return ISSUE_LABELS["return"]
    if any(k in lowered for k in ("qualit\u00e4t", "schlecht", "nicht wie beschrieben")):
        return ISSUE_LABELS["quality"]
    if any(k in lowered for k in ("versand", "lieferung", "sendung")):
        return ISSUE_LABELS["shipping"]
    return ISSUE_LABELS["general"]


def is_complaint(text: str) -> bool:
    """True, wenn Text einen Eintrag aus COMPLAINT_PHRASES enth\u00e4lt."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in COMPLAINT_PHRASES)


def is_negative(text: str) -> bool:
    """True, wenn Text negativ wirkt (Phrasen oder W\u00f6rter)."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    if is_complaint(text):
        return True
    return any(word.lower() in lowered for word in NEGATIVE_WORDS)


def greeting(customer: str) -> str:
    """Lokalisierte Begr\u00fc\u00dfung."""
    return GREETING_TEMPLATE.format(customer=_safe(customer, "danke"))


def closing(shop: str) -> str:
    """Lokalisierte Verabschiedung."""
    return CLOSING_TEMPLATE.format(shop=_safe(shop, "unserem Shop"))


# ---------------------------------------------------------------------------
# Geerdete Builder (alle mit Zitat; keine erfundenen Nummern)
# ---------------------------------------------------------------------------

def DM_REPLY(customer, issue, citation, shop) -> str:
    """Erstellt eine geerdete DM-Antwort auf Deutsch.

    Args:
      customer: Vorname des K\u00e4ufers.
      issue: kurze, bereits lokalisierte Problembeschreibung.
      citation: Quelldatei, z. B. amazon_messages.csv.
      shop: sichtbarer Shopname.
    """
    return DM_REPLY_TEMPLATE.format(
        customer=_safe(customer, "danke"),
        issue=_safe(issue, ISSUE_LABELS["general"]),
        citation=_safe(citation, "amazon_messages.csv"),
        shop=_safe(shop, "unserem Shop"),
    )


def REVIEW_REPLY(product, citation, shop) -> str:
    """Erstellt eine geerdete \u00f6ffentliche Bewertungsantwort."""
    return REVIEW_REPLY_TEMPLATE.format(
        product=_safe(product, "Ihrem Artikel"),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "unserem Shop"),
    )


def PO_EMAIL(supplier, lines, shop, citation="inventory.csv") -> str:
    """Erstellt eine geerdete Nachbestellmail auf Deutsch.

    ``citation`` defaultet auf inventory.csv, damit der Platzhalter auch bei
    nur (supplier, lines, shop) erf\u00fcllt ist.
    """
    return PO_EMAIL_TEMPLATE.format(
        supplier=_safe(supplier, "Lieferant"),
        lines=format_po_lines(lines),
        shop=_safe(shop, "unserem Shop"),
        citation=_safe(citation, "inventory.csv"),
    )


def cover_note_14d(shop, citation="inventory.csv") -> str:
    """Lokalisierte 14-Tage-Deckungsnotiz auf Deutsch."""
    return COVER_NOTE_14D_TEMPLATE.format(
        shop=_safe(shop, "unserem Shop"),
        citation=_safe(citation, "inventory.csv"),
    )


def dm_reply(customer, issue, citation, shop) -> str:
    """Kleinbuchstaben-Alias f\u00fcr DM_REPLY."""
    return DM_REPLY(customer, issue, citation, shop)


def review_reply(product, citation, shop) -> str:
    """Kleinbuchstaben-Alias f\u00fcr REVIEW_REPLY."""
    return REVIEW_REPLY(product, citation, shop)


def po_email(supplier, lines, shop, citation="inventory.csv") -> str:
    """Kleinbuchstaben-Alias f\u00fcr PO_EMAIL."""
    return PO_EMAIL(supplier, lines, shop, citation)


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
# Anhang: Nutzungsbeispiele + Erdungsgarantien (echte Doku).
# ---------------------------------------------------------------------------
# Beispiel DM:
#   DM_REPLY("Lena", "versp\u00e4tete Lieferung", "amazon_messages.csv", "Solmar")
#   -> "Hallo Lena, danke f\u00fcr Ihre Nachricht an Solmar. Es tut uns leid
#       wegen versp\u00e4tete Lieferung. Wir pr\u00fcfen das sofort und antworten
#       innerhalb von 2 Stunden mit einer L\u00f6sung (Erstattung oder Ersatz).
#       Quelle: amazon_messages.csv"
# Beispiel Bewertung:
#   REVIEW_REPLY("Canvas-Tasche", "reviews.csv", "Solmar")
#   -> Dank + Entschuldigung + 2-Stunden-Versprechen + "Quelle: reviews.csv".
# Beispiel Bestellung:
#   PO_EMAIL("Acme", [{"product": "Canvas-Tasche", "qty": 20}], "Solmar")
#   -> Betreff + "- Canvas-Tasche x 20" + 14-Tage-Abdeckung
#      + "Quelle: inventory.csv".
# Erdung:
#   - Jede gerenderte Vorlage enth\u00e4lt ihr Zitat wortw\u00f6rtlich.
#   - Keine Vorlage enth\u00e4lt "#" + Ziffern (keine erfundenen Nummern).
#   - Builder mit sicheren Defaults; kein Fehler bei None.
#   - Pure Funktionen: gleiche Inputs -> gleiche Outputs.
# Determinismus:
#   - Keine Uhr, kein Zufall, kein Netz, keine IO in diesem Modul.
#   - format_po_lines erh\u00e4lt Eingabereihenfolge f\u00fcr stabile Diffs.
#   - get_issue_label pr\u00fcft versp\u00e4tet/kaputt zuerst f\u00fcr Stabilit\u00e4t.
# Siehe auch: drafts.build_reply, drafts.build_po, channels.normalize_dm.
# Ende des de-Sprachmoduls.

