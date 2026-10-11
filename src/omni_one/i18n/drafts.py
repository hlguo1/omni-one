"""Draft builders for Omni-One i18n seller pack.

Deterministic, no network, no LLM. All drafts are grounded: every draft
embeds the caller-provided ``citation`` (a real source filename) and never
invents order numbers. Same inputs always produce same outputs.

Public API:
  build_reply(channel, locale, customer, text, citation, shop) -> str
  build_review_reply(locale, product, citation, shop) -> str
  build_po(locale, supplier, lines, shop, citation) -> str
  cover_note_14d(locale, shop, citation) -> str
  list_locales() re-export helper
"""

from __future__ import annotations

from . import SUPPORTED, get_locale_module

DEFAULT_CITATIONS = {
    "instagram": "instagram_dm.txt",
    "tiktok": "tiktok_dm.json",
    "etsy": "etsy_convo.csv",
    "amazon": "amazon_messages.csv",
    "whatsapp": "whatsapp.txt",
    "email": "email.mbox",
}

DEFAULT_SHOP = "Solmar"


def _safe(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return fallback
    text = value.strip()
    return text if text else fallback


def _locale_mod(locale: str):
    loc = _safe(locale, "en").lower()
    if loc not in SUPPORTED:
        loc = "en"
    return get_locale_module(loc), loc


def _default_citation(channel: str, fallback: str = "reviews.csv") -> str:
    ch = _safe(channel, "").lower()
    return DEFAULT_CITATIONS.get(ch, fallback)


def build_reply(channel, locale, customer, text, citation, shop) -> str:
    """Build a grounded DM draft for ``channel`` + ``locale``.

    Uses the locale module's DM_REPLY(customer, issue, citation, shop)
    where ``issue`` is derived deterministically from ``text`` via the
    locale's get_issue_label(). The customer name and citation always
    appear verbatim in the output. No order numbers are invented.

    Idempotent: pure function of its inputs.
    """
    mod, _ = _locale_mod(locale)
    shop_name = _safe(shop, DEFAULT_SHOP) or DEFAULT_SHOP
    cust = _safe(customer, "there") or "there"
    cite = _safe(citation, "") or _default_citation(channel, "reviews.csv")
    issue_fn = getattr(mod, "get_issue_label", None)
    try:
        issue = issue_fn(text) if callable(issue_fn) else _safe(text, "")
    except Exception:
        issue = _safe(text, "")
    if not issue:
        try:
            issue = mod.ISSUE_LABELS.get("general", "your message")
        except Exception:
            issue = "your message"
    builder = getattr(mod, "DM_REPLY", None)
    if callable(builder):
        return builder(cust, issue, cite, shop_name)
    # Fallback: English module (should never trigger).
    en_mod = get_locale_module("en")
    return en_mod.DM_REPLY(cust, issue, cite, shop_name)


def build_review_reply(locale, product, citation, shop) -> str:
    """Build a grounded public review reply for ``locale``.

    Wraps the locale module's REVIEW_REPLY(product, citation, shop).
    Product name and citation appear verbatim. Idempotent.
    """
    mod, _ = _locale_mod(locale)
    shop_name = _safe(shop, DEFAULT_SHOP) or DEFAULT_SHOP
    prod = _safe(product, "your item") or "your item"
    cite = _safe(citation, "reviews.csv") or "reviews.csv"
    builder = getattr(mod, "REVIEW_REPLY", None)
    if callable(builder):
        return builder(prod, cite, shop_name)
    en_mod = get_locale_module("en")
    return en_mod.REVIEW_REPLY(prod, cite, shop_name)


def cover_note_14d(locale, shop, citation="inventory.csv") -> str:
    """Localized 14-day cover note for ``locale``.

    Each locale renders its own 14-day phrase:
      en "next 14 days", es "pr\u00f3ximos 14 d\u00edas", zh "14 \u5929",
      fr "prochains 14 jours", de "n\u00e4chsten 14 Tage".
    Always includes shop and citation. Idempotent.
    """
    mod, _ = _locale_mod(locale)
    shop_name = _safe(shop, DEFAULT_SHOP) or DEFAULT_SHOP
    cite = _safe(citation, "inventory.csv") or "inventory.csv"
    fn = getattr(mod, "cover_note_14d", None)
    if callable(fn):
        try:
            return fn(shop_name, cite)
        except TypeError:
            return fn(shop_name)
    en_mod = get_locale_module("en")
    return en_mod.cover_note_14d(shop_name, cite)


def build_po(locale, supplier, lines, shop, citation="inventory.csv") -> str:
    """Build a grounded reorder email plus localized 14-day cover note.

    Combines locale PO_EMAIL(supplier, lines, shop, citation) with the
    locale cover_note_14d(shop, citation), joined by a blank line. Both
    parts embed the citation. Idempotent and deterministic.
    """
    mod, _ = _locale_mod(locale)
    shop_name = _safe(shop, DEFAULT_SHOP) or DEFAULT_SHOP
    supp = _safe(supplier, "supplier") or "supplier"
    cite = _safe(citation, "inventory.csv") or "inventory.csv"
    po_fn = getattr(mod, "PO_EMAIL", None)
    if callable(po_fn):
        try:
            email = po_fn(supp, lines, shop_name, cite)
        except TypeError:
            email = po_fn(supp, lines, shop_name)
    else:
        en_mod = get_locale_module("en")
        email = en_mod.PO_EMAIL(supp, lines, shop_name, cite)
    note = cover_note_14d(locale, shop_name, cite)
    return f"{email}\n\n{note}"


__all__ = [
    "build_reply",
    "build_review_reply",
    "build_po",
    "cover_note_14d",
    "DEFAULT_CITATIONS",
]
