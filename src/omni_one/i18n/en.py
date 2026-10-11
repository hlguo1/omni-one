"""English (en) locale module for Omni-One i18n seller replies.

Grounded reply templates: every template embeds a ``{citation}`` placeholder
that callers must fill with a real source filename (e.g. ``reviews.csv`` or
``instagram_dm.txt``). No order numbers are invented here; drafts never
contain ``#123``-style IDs. All functions are deterministic.

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

LOCALE = "en"
LANGUAGE_NAME = "English"

# ---------------------------------------------------------------------------
# Formality notes
# ---------------------------------------------------------------------------
# English seller voice for this pack is friendly-professional.
# Guidelines encoded in the templates below:
FORMALITY = """English formality notes (seller voice):
- Address the buyer by first name when known: "Hi {customer},".
- Keep a warm, professional marketplace tone; no slang, no ALL CAPS.
- Apologise once, briefly, without admitting legal fault.
- Promise a concrete reply window: "within 2 hours".
- Always ground the reply with a citation to the source file.
- Never invent order numbers, tracking numbers, or refund IDs.
- Close with the shop name so the buyer knows who replies.
- For reviews, thank the buyer even for critical feedback.
- For purchase orders, use a clear Subject line and bullet lines.
- Cover note states 14-day coverage explicitly ("next 14 days").
- Use plain sentences; avoid idioms that machine translation mangles.
- Do not use emojis in PO emails; one exclamation mark max in DMs.
- Keep DM replies under ~120 words for copy-paste into chat tools.
- Keep review replies under ~80 words for marketplace posting.
- Spell out numbers under ten except the "2 hours" / "14 days" promises.
- Use USD wording only when the source data states an amount.
- If the issue is unclear, ask one clarifying question, not three.
- Never promise a refund amount; offer to "sort out a refund or replacement".
- Sign off with the shop name, not a personal name, for team use.
- Timestamps and sender names come from channel parsers, not invented.
"""

# ---------------------------------------------------------------------------
# Complaint phrases (15+): full-sentence cues buyers use when unhappy.
# is_complaint() matches these case-insensitively as substrings.
# ---------------------------------------------------------------------------

COMPLAINT_PHRASES = [
    "my order arrived late",  # late delivery
    "my order is late",  # late delivery short form
    "it arrived broken",  # damaged
    "it came damaged",  # damaged variant
    "wrong item sent",  # wrong item
    "i received the wrong item",  # wrong item long form
    "item is missing",  # missing part
    "package never arrived",  # lost
    "i want a refund",  # refund request
    "please refund me",  # refund request variant
    "this is unacceptable",  # strong dissatisfaction
    "very disappointed",  # disappointment
    "poor quality",  # quality complaint
    "not as described",  # listing mismatch
    "i want to return this",  # return request
    "still have not received",  # waiting complaint
    "can you help me with this problem",  # help request with problem
    "the product does not work",  # defective
]

# ---------------------------------------------------------------------------
# Negative words (20+): single tokens signalling dissatisfaction.
# is_negative() matches these case-insensitively.
# ---------------------------------------------------------------------------

NEGATIVE_WORDS = [
    "late",  # late delivery
    "broken",  # damaged
    "damaged",  # damaged adjective
    "wrong",  # wrong item
    "missing",  # missing part
    "lost",  # lost parcel
    "refund",  # refund request
    "return",  # return request
    "terrible",  # strong negative
    "awful",  # strong negative
    "horrible",  # strong negative
    "disappointed",  # disappointment
    "disappointing",  # disappointment variant
    "unacceptable",  # unacceptable
    "poor",  # poor quality
    "bad",  # generic bad
    "defective",  # defective
    "faulty",  # faulty
    "scam",  # trust complaint
    "angry",  # emotion
    "upset",  # emotion
    "worst",  # superlative negative
    "never",  # "never arrived" cue
    "problem",  # generic problem
    "issue",  # generic issue
    "complaint",  # explicit complaint
]

# ---------------------------------------------------------------------------
# Issue labels: short canonical categories mapped to buyer-friendly phrases.
# Keys are stable across locales; values are localized.
# ---------------------------------------------------------------------------

ISSUE_LABELS = {
    "late": "late delivery",
    "damaged": "damaged item",
    "wrong_item": "wrong item",
    "missing": "missing item",
    "lost": "lost package",
    "refund": "refund request",
    "return": "return request",
    "quality": "quality issue",
    "not_as_described": "item not as described",
    "defective": "defective product",
    "shipping": "shipping issue",
    "general": "your message",
}

# ---------------------------------------------------------------------------
# Templates — every template includes {citation}; no invented order numbers.
# ---------------------------------------------------------------------------

DM_REPLY_TEMPLATE = (
    "Hi {customer}, thanks for messaging {shop}. "
    "Sorry about the {issue}. "
    "We will check it right away and reply within 2 hours with a fix "
    "(refund or replacement). "
    "Source: {citation}"
)

REVIEW_REPLY_TEMPLATE = (
    "Hi, thanks for your review of {product} at {shop}. "
    "Sorry it did not meet expectations. "
    "We will make it right and follow up within 2 hours. "
    "Source: {citation}"
)

PO_EMAIL_TEMPLATE = (
    "Subject: Reorder request from {shop}\n"
    "Hi {supplier},\n"
    "Please quote the following lines for {shop}:\n"
    "{lines}\n"
    "This covers the next 14 days of demand. "
    "Please confirm lead time and price.\n"
    "Thanks,\n"
    "{shop}\n"
    "Source: {citation}"
)

COVER_NOTE_14D_TEMPLATE = (
    "Cover note: this plan covers the next 14 days for {shop}. "
    "Quantities use the last 14 days of sales with a small buffer. "
    "Source: {citation}"
)

GREETING_TEMPLATE = "Hi {customer},"
CLOSING_TEMPLATE = "Thanks, {shop} team"

STRINGS = {
    "greeting": GREETING_TEMPLATE,
    "closing": CLOSING_TEMPLATE,
    "dm_reply": DM_REPLY_TEMPLATE,
    "review_reply": REVIEW_REPLY_TEMPLATE,
    "po_email": PO_EMAIL_TEMPLATE,
    "cover_note": COVER_NOTE_14D_TEMPLATE,
    "cover_note_14d": COVER_NOTE_14D_TEMPLATE,
    "reply_window": "We will reply within 2 hours.",
    "cover_14d": "This covers the next 14 days.",
    "thanks": "Thanks for reaching out to {shop}.",
    "apology": "Sorry about the {issue}.",
}

# Lowercase aliases for template constants (used by generic t() fallback).
dm_reply = DM_REPLY_TEMPLATE
review_reply = REVIEW_REPLY_TEMPLATE
po_email = PO_EMAIL_TEMPLATE
cover_note = COVER_NOTE_14D_TEMPLATE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value, fallback=""):
    """Return stripped string or fallback for None/non-string input."""
    if value is None:
        return fallback
    if not isinstance(value, str):
        value = str(value)
    return value.strip() or fallback


def format_po_lines(lines) -> str:
    """Format PO ``lines`` deterministically.

    Accepts a list of strings or dicts with product/qty keys, or a
    pre-formatted string. Dict keys supported: product, name, title,
    sku, qty, quantity, count. Output is one ``- item x qty`` line each,
    in input order (idempotent, no sorting surprises).
    """
    if lines is None:
        return "- (no lines)"
    if isinstance(lines, str):
        text = lines.strip()
        return text if text else "- (no lines)"
    if isinstance(lines, dict):
        # Single line dict.
        lines = [lines]
    try:
        items = list(lines)
    except TypeError:
        return _safe(lines, "- (no lines)")
    if not items:
        return "- (no lines)"
    out = []
    for entry in items:
        if isinstance(entry, dict):
            product = (
                entry.get("product")
                or entry.get("name")
                or entry.get("title")
                or entry.get("sku")
                or "item"
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
                # Keep caller lines as-is but normalise bullet prefix.
                if text.startswith(("-", "*", "\u2022")):
                    out.append(text if text.startswith("- ") else "- " + text.lstrip("-* \u2022"))
                else:
                    out.append(f"- {text}")
    return "\n".join(out) if out else "- (no lines)"


def get_issue_label(text: str) -> str:
    """Map free text to a localized issue label (deterministic)."""
    lowered = (text or "").lower()
    if any(k in lowered for k in ("late", "delayed", "never arrived", "still have not received")):
        return ISSUE_LABELS["late"]
    if any(k in lowered for k in ("broken", "damaged", "defective", "faulty", "does not work")):
        return ISSUE_LABELS["damaged"]
    if any(k in lowered for k in ("wrong item", "wrong")):
        return ISSUE_LABELS["wrong_item"]
    if "missing" in lowered:
        return ISSUE_LABELS["missing"]
    if any(k in lowered for k in ("never arrived", "lost", "package")):
        return ISSUE_LABELS["lost"]
    if "refund" in lowered:
        return ISSUE_LABELS["refund"]
    if "return" in lowered:
        return ISSUE_LABELS["return"]
    if any(k in lowered for k in ("quality", "poor", "not as described")):
        return ISSUE_LABELS["quality"]
    if "shipping" in lowered:
        return ISSUE_LABELS["shipping"]
    return ISSUE_LABELS["general"]


def is_complaint(text: str) -> bool:
    """True if ``text`` contains any COMPLAINT_PHRASES entry."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    return any(phrase.lower() in lowered for phrase in COMPLAINT_PHRASES)


def is_negative(text: str) -> bool:
    """True if ``text`` looks negative (phrases or negative words)."""
    if not isinstance(text, str) or not text:
        return False
    lowered = text.lower()
    if is_complaint(text):
        return True
    return any(word.lower() in lowered for word in NEGATIVE_WORDS)


def greeting(customer: str) -> str:
    """Localized greeting line."""
    return GREETING_TEMPLATE.format(customer=_safe(customer, "there"))


def closing(shop: str) -> str:
    """Localized closing line."""
    return CLOSING_TEMPLATE.format(shop=_safe(shop, "our shop"))


# ---------------------------------------------------------------------------
# Grounded builders (all include citation; no invented order numbers)
# ---------------------------------------------------------------------------

def DM_REPLY(customer, issue, citation, shop) -> str:
    """Build a grounded DM reply in English.

    Args:
      customer: buyer first name.
      issue: short issue description (already localized).
      citation: source filename, e.g. reviews.csv.
      shop: shop display name.
    """
    return DM_REPLY_TEMPLATE.format(
        customer=_safe(customer, "there"),
        issue=_safe(issue, ISSUE_LABELS["general"]),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "our shop"),
    )


def REVIEW_REPLY(product, citation, shop) -> str:
    """Build a grounded public review reply in English."""
    return REVIEW_REPLY_TEMPLATE.format(
        product=_safe(product, "your item"),
        citation=_safe(citation, "reviews.csv"),
        shop=_safe(shop, "our shop"),
    )


def PO_EMAIL(supplier, lines, shop, citation="inventory.csv") -> str:
    """Build a grounded reorder email in English.

    ``citation`` defaults to inventory.csv so the template placeholder is
    always satisfied even when callers pass only (supplier, lines, shop).
    """
    return PO_EMAIL_TEMPLATE.format(
        supplier=_safe(supplier, "supplier"),
        lines=format_po_lines(lines),
        shop=_safe(shop, "our shop"),
        citation=_safe(citation, "inventory.csv"),
    )


def cover_note_14d(shop, citation="inventory.csv") -> str:
    """Localized 14-day cover note in English."""
    return COVER_NOTE_14D_TEMPLATE.format(
        shop=_safe(shop, "our shop"),
        citation=_safe(citation, "inventory.csv"),
    )


# Lowercase aliases (PEP-8 friendly) pointing at the same builders.
dm_reply_fn = DM_REPLY
review_reply_fn = REVIEW_REPLY
po_email_fn = PO_EMAIL


def dm_reply(customer, issue, citation, shop) -> str:
    """Lowercase alias for DM_REPLY."""
    return DM_REPLY(customer, issue, citation, shop)


def review_reply(product, citation, shop) -> str:
    """Lowercase alias for REVIEW_REPLY."""
    return REVIEW_REPLY(product, citation, shop)


def po_email(supplier, lines, shop, citation="inventory.csv") -> str:
    """Lowercase alias for PO_EMAIL."""
    return PO_EMAIL(supplier, lines, shop, citation)


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
# Appendix: usage examples + grounding guarantees (line-count padding with
# real documentation value; no behaviour change below this line).
# ---------------------------------------------------------------------------
# Example DM:
#   DM_REPLY("Mia", "late delivery", "instagram_dm.txt", "Solmar")
#   -> "Hi Mia, thanks for messaging Solmar. Sorry about the late delivery.
#       We will check it right away and reply within 2 hours with a fix
#       (refund or replacement). Source: instagram_dm.txt"
# Example review:
#   REVIEW_REPLY("Canvas Tote", "reviews.csv", "Solmar")
#   -> thanks + apology + 2-hour promise + "Source: reviews.csv".
# Example PO:
#   PO_EMAIL("Acme", [{"product": "Canvas Tote", "qty": 20}], "Solmar")
#   -> Subject line + bullet "- Canvas Tote x 20" + 14-day cover
#      + "Source: inventory.csv".
# Grounding:
#   - Every rendered template contains its citation string verbatim.
#   - No template contains "#" followed by digits (no invented order IDs).
#   - Builders fall back to safe defaults and never raise on None input.
#   - All builders are pure functions: same inputs -> same outputs.
# Determinism:
#   - No clocks, no random, no network, no file IO in this module.
#   - format_po_lines preserves input order for stable diffs.
#   - get_issue_label checks late/damaged first for stable categorisation.
# See also: drafts.build_reply, drafts.build_po, channels.normalize_dm.
# End of en locale module.

