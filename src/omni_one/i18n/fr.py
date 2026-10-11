"""French (fr) locale module for Omni-One i18n seller replies.

Mod\u00e8les ancr\u00e9s : chaque mod\u00e8le inclut un espace ``{citation}`` \u00e0 remplir
avec un vrai nom de fichier source (par exemple ``reviews.csv`` ou
``etsy_convo.csv``). Aucun num\u00e9ro de commande invent\u00e9 ; les brouillons ne
contiennent jamais d'identifiants de type ``#123``. Fonctions d\u00e9terministes.

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

LOCALE = "fr"
LANGUAGE_NAME = "Fran\u00e7ais"

# ---------------------------------------------------------------------------
# Notes de formalit\u00e9
# ---------------------------------------------------------------------------
# Voix vendeur en fran\u00e7ais : polie, sobre, vouvoiement.
# R\u00e8gles encod\u00e9es dans les mod\u00e8les ci-dessous :
FORMALITY = """Notes de formalit\u00e9 en fran\u00e7ais (voix vendeur) :
- Saluez par le pr\u00e9nom quand il est connu : "Bonjour {customer},".
- Ton poli et professionnel de marketplace ; sans argot ni MAJUSCULES.
- Excusez-vous une fois, bri\u00e8vement, sans reconna\u00eetre de faute juridique.
- Promettez un d\u00e9lai concret : "en moins de 2 heures".
- Ancrez toujours la r\u00e9ponse avec une citation du fichier source.
- N'inventez jamais de num\u00e9ro de commande, de suivi ou de remboursement.
- Terminez avec le nom de la boutique pour identifier l'exp\u00e9diteur.
- Pour les avis, remerciez m\u00eame en cas de critique n\u00e9gative.
- Pour les commandes fournisseur, objet clair et lignes \u00e0 puces.
- La note de couverture mentionne 14 jours ("prochains 14 jours").
- Phrases simples ; \u00e9vitez les idiotismes difficiles \u00e0 traduire.
- Pas d'emojis dans les emails d'achat ; un point d'exclamation max en DM.
- R\u00e9ponses DM d'environ 120 mots pour copier-coller en messagerie.
- R\u00e9ponses aux avis d'environ 80 mots pour publication marketplace.
- Nombres inf\u00e9rieurs \u00e0 dix en lettres sauf "2 heures" et "14 jours".
- Montants uniquement si le fichier source indique un montant.
- Si le probl\u00e8me est flou, posez une seule question pr\u00e9cise, pas trois.
- Ne promettez aucun montant de remboursement ; proposez "remboursement ou remplacement".
- Signez avec le nom de la boutique, pas un pr\u00e9nom, pour usage en \u00e9quipe.
- Horodatages et exp\u00e9diteurs viennent des analyseurs de canal, non invent\u00e9s.
- Vouvoyez par d\u00e9faut en fran\u00e7ais ; tutoyer seulement si le client le fait.
- \u00c9vitez les anglicismes ; pr\u00e9f\u00e9rez "commande" \u00e0 "order".
"""

# ---------------------------------------------------------------------------
# Phrases de plainte (15+) : signaux d'insatisfaction des acheteurs.
# is_complaint() les d\u00e9tecte sans tenir compte de la casse.
# ---------------------------------------------------------------------------

COMPLAINT_PHRASES = [
    "ma commande est arriv\u00e9e en retard",  # livraison tardive
    "ma commande est en retard",  # retard forme courte
    "arriv\u00e9 cass\u00e9",  # endommag\u00e9
    "arriv\u00e9 endommag\u00e9",  # endommag\u00e9 variante
    "mauvais article envoy\u00e9",  # mauvais article
    "j'ai re\u00e7u le mauvais article",  # mauvais article long
    "il manque un article",  # pi\u00e8ce manquante
    "le colis n'est jamais arriv\u00e9",  # perdu
    "je veux un remboursement",  # demande de remboursement
    "remboursez-moi s'il vous pla\u00eet",  # remboursement variante
    "c'est inacceptable",  # m\u00e9contentement fort
    "tr\u00e8s d\u00e9\u00e7u",  # d\u00e9ception
    "mauvaise qualit\u00e9",  # plainte qualit\u00e9
    "non conforme \u00e0 la description",  # \u00e9cart annonce
    "je veux retourner cet article",  # demande de retour
    "je ne l'ai toujours pas re\u00e7u",  # attente
    "pouvez-vous m'aider avec ce probl\u00e8me",  # demande d'aide
    "le produit ne fonctionne pas",  # d\u00e9fectueux
]

# ---------------------------------------------------------------------------
# Mots n\u00e9gatifs (20+) : tokens signalant le m\u00e9contentement.
# is_negative() les d\u00e9tecte sans tenir compte de la casse.
# ---------------------------------------------------------------------------

NEGATIVE_WORDS = [
    "retard",  # livraison tardive
    "cass\u00e9",  # endommag\u00e9
    "endommag\u00e9",  # adjectif
    "mauvais",  # mauvais article
    "manquant",  # pi\u00e8ce manquante
    "perdu",  # colis perdu
    "remboursement",  # demande
    "retour",  # demande de retour
    "terrible",  # tr\u00e8s n\u00e9gatif
    "horrible",  # tr\u00e8s n\u00e9gatif
    "affreux",  # tr\u00e8s n\u00e9gatif
    "d\u00e9\u00e7u",  # d\u00e9ception
    "d\u00e9cevant",  # variante
    "inacceptable",  # inacceptable
    "mauvaise",  # mauvaise qualit\u00e9
    "mauvaises",  # pluriel
    "d\u00e9fectueux",  # d\u00e9fectueux
    "arnaque",  # confiance
    "en col\u00e8re",  # \u00e9motion
    "contrari\u00e9",  # \u00e9motion
    "pire",  # superlatif
    "jamais",  # jamais arriv\u00e9
    "probl\u00e8me",  # g\u00e9n\u00e9rique
    "plainte",  # plainte explicite
    "litige",  # litige
    "en retard",  # locution retard
]

# ---------------------------------------------------------------------------
# Libell\u00e9s d'incident : cl\u00e9s stables, valeurs localis\u00e9es.
# ---------------------------------------------------------------------------

ISSUE_LABELS = {
    "late": "livraison en retard",
    "damaged": "article endommag\u00e9",
    "wrong_item": "mauvais article",
    "missing": "article manquant",
    "lost": "colis perdu",
    "refund": "demande de remboursement",
    "return": "demande de retour",
    "quality": "probl\u00e8me de qualit\u00e9",
    "not_as_described": "article non conforme \u00e0 l'annonce",
    "defective": "produit d\u00e9fectueux",
    "shipping": "probl\u00e8me de livraison",
    "general": "votre message",
}

# ---------------------------------------------------------------------------
# Mod\u00e8les \u2014 chacun inclut {citation} ; aucun num\u00e9ro invent\u00e9.
# ---------------------------------------------------------------------------

DM_REPLY_TEMPLATE = (
    "Bonjour {customer}, merci d'avoir \u00e9crit \u00e0 {shop}. "
    "D\u00e9sol\u00e9 pour le {issue}. "
    "Nous v\u00e9rifions cela aussit\u00f4t et revenons vers vous en moins de 2 heures "
    "avec une solution (remboursement ou remplacement). "
    "Source : {citation}"
)

REVIEW_REPLY_TEMPLATE = (
    "Bonjour, merci pour votre avis sur {product} chez {shop}. "
    "D\u00e9sol\u00e9 qu'il n'ait pas \u00e9t\u00e9 \u00e0 la hauteur. "
    "Nous allons r\u00e9gler cela et revenir vers vous en moins de 2 heures. "
    "Source : {citation}"
)

PO_EMAIL_TEMPLATE = (
    "Objet : Demande de r\u00e9assort de {shop}\n"
    "Bonjour {supplier},\n"
    "Merci de chiffrer les lignes suivantes pour {shop} :\n"
    "{lines}\n"
    "Cela couvre la demande des prochains 14 jours. "
    "Merci de confirmer d\u00e9lai et prix.\n"
    "Merci,\n"
    "{shop}\n"
    "Source : {citation}"
)

COVER_NOTE_14D_TEMPLATE = (
    "Note de couverture : ce plan couvre les prochains 14 jours pour {shop}. "
    "Les quantit\u00e9s utilisent les ventes des 14 derniers jours avec une petite marge. "
    "Source : {citation}"
)

GREETING_TEMPLATE = "Bonjour {customer},"
CLOSING_TEMPLATE = "Merci, l'\u00e9quipe {shop}"

STRINGS = {
    "greeting": GREETING_TEMPLATE,
    "closing": CLOSING_TEMPLATE,
    "dm_reply": DM_REPLY_TEMPLATE,
    "review_reply": REVIEW_REPLY_TEMPLATE,
    "po_email": PO_EMAIL_TEMPLATE,
    "cover_note": COVER_NOTE_14D_TEMPLATE,
    "cover_note_14d": COVER_NOTE_14D_TEMPLATE,
    "reply_window": "Nous revenons vers vous en moins de 2 heures.",
    "cover_14d": "Cela couvre les prochains 14 jours.",
    "thanks": "Merci d'avoir \u00e9crit \u00e0 {shop}.",
    "apology": "D\u00e9sol\u00e9 pour le {issue}.",
}

dm_reply = DM_REPLY_TEMPLATE
review_reply = REVIEW_REPLY_TEMPLATE
po_email = PO_EMAIL_TEMPLATE
cover_note = COVER_NOTE_14D_TEMPLATE


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _safe(value, fallback=""):
    """Renvoie le texte \u00e9lagu\u00e9 ou la valeur de repli."""
    if value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    return value.strip() or fallback


def format_po_lines(lines) -> str:
    """Met en forme les lignes d'achat de fa\u00e7on d\u00e9terministe.

    Accepte une liste de textes ou de dicts avec cl\u00e9s product/qty, ou un
    texte d\u00e9j\u00e0 format\u00e9. Cl\u00e9s prises en charge : product, name, title,
    sku, qty, quantity, count. Sortie en puces dans l'ordre d'entr\u00e9e.
    """
    if lines is None:
        return "- (aucune ligne)"
    if isinstance(lines, str):
        text = lines.strip()
        return text if text else "- (aucune ligne)"
    if isinstance(lines, dict):
        lines = [lines]
    try:
        items = list(lines)
    except TypeError:
        return _safe(lines, "- (aucune ligne)")
    if not items:
        return "- (aucune ligne)"
    out = []
    for entry in items:
        if isinstance(entry, dict):
            product = (
                entry.get("product")
                or entry.get("name")
                or entry.get("title")
                or entry.get("sku")
                or "article"
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
    return "\n".join(out) if out else "- (aucune ligne)"


def get_issue_label(text: str) -> str:
    """Mappe un texte libre vers un libell\u00e9 localis\u00e9 (d\u00e9terministe)."""
    lowered = (text or "").lower()
    if any(k in lowered for k in ("retard", "en retard", "jamais arriv\u00e9", "toujours pas")):
        return ISSUE_LABELS["late"]
    if any(k in lowered for k in ("cass\u00e9", "endommag\u00e9", "d\u00e9fectueux", "ne fonctionne pas")):
        return ISSUE_LABELS["damaged"]
    if "mauvais article" in lowered or "mauvais" in lowered:
        return ISSUE_LABELS["wrong_item"]
    if "manque" in lowered or "manquant" in lowered:
        return ISSUE_LABELS["missing"]
    if any(k in lowered for k in ("perdu", "colis")):
        return ISSUE_LABELS["lost"]
    if "remboursement" in lowered:
        return ISSUE_LABELS["refund"]
    if "retour" in lowered:
        return ISSUE_LABELS["return"]
    if any(k in lowered for k in ("qualit\u00e9", "mauvaise", "non conforme")):
        return ISSUE_LABELS["quality"]
    if "livraison" in lowered:
        return ISSUE_LABELS["shipping"]
    return ISSUE_LABELS["general"]


def is_complaint(text: str) -> bool:
    """True si le texte contient une entr\u00e9e de COMPLAINT_PHRASES."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in COMPLAINT_PHRASES)


def is_negative(text: str) -> bool:
    """True si le texte semble n\u00e9gatif (phrases ou mots)."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    if is_complaint(text):
        return True
    return any(word.lower() in lowered for word in NEGATIVE_WORDS)


def greeting(customer: str) -> str:
    """Formule de salutation localis\u00e9e."""
    return GREETING_TEMPLATE.format(customer=_safe(customer, "merci"))


def closing(shop: str) -> str:
    """Formule de cl\u00f4ture localis\u00e9e."""
    return CLOSING_TEMPLATE.format(shop=_safe(shop, "notre boutique"))


# ---------------------------------------------------------------------------
# Constructeurs ancr\u00e9s (tous incluent la citation ; z\u00e9ro invention)
# ---------------------------------------------------------------------------

def DM_REPLY(customer, issue, citation, shop) -> str:
    """Construit une r\u00e9ponse DM ancr\u00e9e en fran\u00e7ais.

    Args:
      customer: pr\u00e9nom de l'acheteur.
      issue: description courte d\u00e9j\u00e0 localis\u00e9e.
      citation: fichier source, p. ex. etsy_convo.csv.
      shop: nom visible de la boutique.
    """
    return DM_REPLY_TEMPLATE.format(
        customer=_safe(customer, "merci"),
        issue=_safe(issue, ISSUE_LABELS["general"]),
        citation=_safe(citation, "etsy_convo.csv"),
        shop=_safe(shop, "notre boutique"),
    )


def REVIEW_REPLY(product, citation, shop) -> str:
    """Construit une r\u00e9ponse publique \u00e0 un avis en fran\u00e7ais."""
    return REVIEW_REPLY_TEMPLATE.format(
        product=_safe(product, "votre article"),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "notre boutique"),
    )


def PO_EMAIL(supplier, lines, shop, citation="inventory.csv") -> str:
    """Construit un email de r\u00e9assort ancr\u00e9 en fran\u00e7ais.

    ``citation`` vaut inventory.csv par d\u00e9faut pour que l'espace r\u00e9serv\u00e9
    soit toujours rempli m\u00eame avec (supplier, lines, shop) seuls.
    """
    return PO_EMAIL_TEMPLATE.format(
        supplier=_safe(supplier, "fournisseur"),
        lines=format_po_lines(lines),
        shop=_safe(shop, "notre boutique"),
        citation=_safe(citation, "inventory.csv"),
    )


def cover_note_14d(shop, citation="inventory.csv") -> str:
    """Note de couverture localis\u00e9e \u00e0 14 jours en fran\u00e7ais."""
    return COVER_NOTE_14D_TEMPLATE.format(
        shop=_safe(shop, "notre boutique"),
        citation=_safe(citation, "inventory.csv"),
    )


def dm_reply(customer, issue, citation, shop) -> str:
    """Alias minuscule de DM_REPLY."""
    return DM_REPLY(customer, issue, citation, shop)


def review_reply(product, citation, shop) -> str:
    """Alias minuscule de REVIEW_REPLY."""
    return REVIEW_REPLY(product, citation, shop)


def po_email(supplier, lines, shop, citation="inventory.csv") -> str:
    """Alias minuscule de PO_EMAIL."""
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
# Annexe : exemples d'usage et garanties d'ancrage (doc r\u00e9elle).
# ---------------------------------------------------------------------------
# Exemple DM :
#   DM_REPLY("Camille", "livraison en retard", "etsy_convo.csv", "Solmar")
#   -> "Bonjour Camille, merci d'avoir \u00e9crit \u00e0 Solmar. D\u00e9sol\u00e9 pour le
#       livraison en retard. Nous v\u00e9rifions cela aussit\u00f4t et revenons vers
#       vous en moins de 2 heures avec une solution (remboursement ou
#       remplacement). Source : etsy_convo.csv"
# Exemple avis :
#   REVIEW_REPLY("Tote en toile", "reviews.csv", "Solmar")
#   -> remerciement + excuse + promesse 2 heures + "Source : reviews.csv".
# Exemple achat :
#   PO_EMAIL("Acme", [{"product": "Tote en toile", "qty": 20}], "Solmar")
#   -> Objet + puce "- Tote en toile x 20" + couverture 14 jours
#      + "Source : inventory.csv".
# Ancrage :
#   - Chaque mod\u00e8le rendu contient sa citation verbatim.
#   - Aucun mod\u00e8le ne contient "#" suivi de chiffres (z\u00e9ro invention).
#   - Constructeurs avec d\u00e9fauts s\u00fbrs ; jamais d'erreur sur None.
#   - Fonctions pures : m\u00eames entr\u00e9es -> m\u00eames sorties.
# D\u00e9terminisme :
#   - Ni horloge, ni hasard, ni r\u00e9seau, ni IO dans ce module.
#   - format_po_lines pr\u00e9serve l'ordre d'entr\u00e9e pour des diffs stables.
#   - get_issue_label teste retard/endommag\u00e9 d'abord pour stabilit\u00e9.
# Voir aussi : drafts.build_reply, drafts.build_po, channels.normalize_dm.
# Fin du module de langue fr.

