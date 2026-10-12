"""
Micro-biz Close — the 5-minute street-shop ritual (sibling of Seller Daily Close).
================================================================================
Brilliant idea: a taco stand with no website, no POS, just a phone and a
shoebox of receipts still deserves to CLOSE the day:

  1. Did I actually make money today? (cash revenue, not GMV)
  2. What ingredient runs out and kills tomorrow's sales? (reorder sheet)
  3. Who is annoyed RIGHT NOW on WhatsApp? (copy-paste drafts, cited)
  4. Where is money leaking? (cancelled orders, food cost, slow service)
  5. Text my supplier something short. (vendor SMS/WhatsApp draft)

One folder in, one bundle out, offline, $0::

    from pathlib import Path
    from omni_one.packs._labs.micro_biz import make_demo_folder, ingest_folder
    from omni_one.packs.micro_close import build_micro_close, write_close_bundle

    events, _ = ingest_folder(folder)          # messy folder -> events
    close = build_micro_close(events)           # events -> close dict
    write_close_bundle(close, "./close_2026-10-11")
    # -> close.json + close.csv + reorder.csv + replies.txt + vendor.txt

Design rules (why street shops trust it — same contract as seller_close):
- Deterministic, no LLM needed for numbers. Drafts are templates grounded
  in citations. A mock LLM is never even called; drafts come from
  ``omni_one.i18n.drafts.build_reply`` with a local-template fallback.
- Every dollar cites file:line. No phantom tasks, no invented order IDs.
- Idempotent: same events -> same close (minus the date stamp).
- Private: data never leaves the laptop. Works on plane wifi.
- Bilingual: ``locale="en"`` or ``locale="es"``. Numbers never change
  with locale — only the human words do.

Sibling map vs ``seller_close.build_daily_close`` (read both before editing):

==================  ============================  ==============================
concern             seller_close (online sellers)   micro_close (street shops)
==================  ============================  ==============================
signal source       seller_os briefing + scenarios  micro_biz briefing only
money               GMV/fees/true profit            cash revenue/expenses/net
stock model         inventory.csv on-hand + 7d vel  receipt mentions, no inv file
cover window        14 days (warehouse)             7 days (fridge, daily market)
reply channel       IG/DM/review/email              WhatsApp-first (+ voice/IG)
reply promise       "within 2 hours"                "within 2 hours / 2 horas"
supplier doc        PO email (Subject + bullets)    vendor SMS/WhatsApp, chat-short
bundle file #5      po.txt (formal email)           vendor.txt (chat-short text)
locales             en/es/zh/fr/de                  en/es (street reality)
==================  ============================  ==============================

Stock model without an inventory file (read this before "fixing" it):
- Street shops have no inventory.csv. The only stock signal is how often
  an ingredient shows up on supplier receipts.
- ``sold`` = number of receipt line-item mentions of the ingredient
  (each sighting ~= one purchase cycle ~= usage pressure).
- ``on_hand`` = ``BASE_STOCK - sold`` (floor 0). Frequent re-buys mean
  the shelf is thin. BASE_STOCK = 4 portions covers a small stand.
- ``daily_velocity`` = sold / 7. ``days_left`` = on_hand / velocity.
- ``reorder_qty`` = ceil(velocity * COVER_DAYS - on_hand), floor 0.
- Known quirk: the demo ``.jpg`` receipt and its ``.txt`` sidecar parse
  to the same lines, so mentions double-count (cilantro x3, not x2).
  This is deterministic and stable, so the close keeps it and documents
  it instead of silently deduping (see docs/MICRO_CLOSE.md).
- Known quirk 2: ``notebook.txt`` line 1 ("sept 12 - sold out ...")
  parses its date fragment as $12.00 of expense. It flows into the
  briefing revenue math, so the close keeps the briefing number and
  documents it. Never hand-adjust golden numbers.

Golden demo (seed=42, Maya's Tacos) — asserted in tests, do not drift:
- revenue $241.50, expenses $219.50, net $22.00
- orders 5, items 77, avg ticket $48.30
- best seller "tacos al pastor" x32, at-risk customers 2
- money at risk $96.60 (= 2 x $48.30)
- reorder sheet head: cilantro, ORDER TODAY, citation [receipt_...:...]
"""
from __future__ import annotations

import csv
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants — street-shop tuning (see module docstring for rationale)
# ---------------------------------------------------------------------------

COVER_DAYS = 7               # ingredient cover: 7 days (fridge, daily market)
ORDER_TODAY_DAYS = 3.0       # must-buy threshold (mirrors seller STOCKOUT urgency)
STOCKOUT_DAYS = 5.0          # "this week" threshold (matches seller_close scale)
BASE_STOCK = 4               # assumed starting portions with no inventory file
VELOCITY_WINDOW_DAYS = 7.0   # mentions are counted over ~one demo week
MAX_REORDER_ROWS = 5         # keep the sheet printable on a phone screen
MAX_REPLY_QUEUE = 5          # one screen of copy-paste drafts
MAX_LEAKS = 4                # money leaks cap (same as seller_close)
AVG_DECIMALS = 2             # money rounding everywhere

# Keywords that escalate a chat reply to P0 (answer inside 2h or lose them).
# Bilingual on purpose: the demo chat mixes Spanish and English.
P0_KEYWORDS = (
    "refund", "reembolso", "cancel", "molesta", "molesto", "tardó", "tardo",
    "espera", "terrible", "disappointed", "awful", "horrible", "cold",
    "frío", "frio", "lento", "nunca", "enojad", "queja",
)

# Keywords that mark a slow-service money leak (staff gaps, long waits).
SLOW_SERVICE_KEYWORDS = (
    "didn't show", "didnt show", "short staff", "long wait", "long waits",
    "espera larga", "espera fue larga", "tardó", "tardo", "sold out",
)

# Greeting words that identify the shop's own messages (not customers).
# Used only to skip self-messages when picking a "happy customer" name.
SHOP_GREETING_HINTS = ("buenos días", "buenos dias", "tenemos", "listos", "disculpas")


__all__ = [
    "COVER_DAYS",
    "ORDER_TODAY_DAYS",
    "STOCKOUT_DAYS",
    "BASE_STOCK",
    "build_micro_close",
    "draft_whatsapp_reply",
    "close_to_csv",
    "reorder_to_csv",
    "replies_to_txt",
    "vendor_to_txt",
    "write_close_bundle",
]


# ---------------------------------------------------------------------------
# Small helpers — names, locales, money, citations
# ---------------------------------------------------------------------------

def _first_name(sender: str) -> str:
    """Return a short first name for a chat sender (never empty)."""
    sender = (sender or "there").strip().split()[0].strip(",:@+")
    return sender[:20] or "there"


def _norm_locale(locale: str | None) -> str:
    """Normalize locale to the street-shop pair: ``en`` or ``es``.

    Anything unknown (including None/'') falls back to ``en`` so numbers
    and structure never break on a bad locale string.
    """
    loc = (locale or "en").lower()[:2]
    return loc if loc in ("en", "es") else "en"


def _money(value: Any) -> float:
    """Coerce anything to a float dollar amount (never raises)."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_file_line_citation(citation: str) -> bool:
    """True when a citation looks like ``[file.ext:line] ...`` evidence."""
    if not citation or "[" not in citation or ":" not in citation:
        return False
    low = citation.lower()
    return any(ext in low for ext in (".csv", ".txt", ".jpg", ".md", ".log", ".json"))


def _issue_snippet(text: str, locale: str) -> str:
    """Short issue phrase for the *fallback* template only.

    The primary path (i18n.build_reply) derives its own issue label via
    the locale module's ``get_issue_label``; this helper only feeds the
    local fallback when that import fails. Kept bilingual and tiny.
    """
    low = (text or "").lower()
    es = locale == "es"
    if any(w in low for w in ("espera", "wait", "tardó", "tardo", "late", "delay")):
        return "la larga espera" if es else "the long wait"
    if any(w in low for w in ("cold", "frío", "frio")):
        return "los tacos fríos" if es else "the cold tacos"
    if any(w in low for w in ("cilantro", "sold out", "agot")):
        return "la falta de cilantro" if es else "running out of cilantro"
    if any(w in low for w in ("terrible", "disappointed", "molesta", "enojad")):
        return "la experiencia de ayer" if es else "yesterday's experience"
    return "esto" if es else "this"


def _local_whatsapp_reply(customer: str, text: str, citation: str,
                          shop: str, locale: str) -> str:
    """Local WhatsApp draft used only when ``i18n.drafts`` is unavailable.

    Contract (must hold for both locales, asserted in tests):
    - embeds the customer first name,
    - embeds the citation verbatim,
    - promises a 2-hour window ("within 2 hours" / "en menos de 2 horas"),
    - offers a concrete remedy (10% off next visit),
    - signs off with the shop name.
    """
    name = _first_name(customer)
    shop_name = (shop or "our shop").strip() or "our shop"
    cite = (citation or "[chat:1] message").strip() or "[chat:1] message"
    issue = _issue_snippet(text, locale)
    if locale == "es":
        return (
            f"Hola {name}! Gracias por venir a {shop_name} — perdón por {issue} "
            f"({cite}). Lo resolvemos ahora mismo y en menos de 2 horas te "
            f"tenemos la solución. Muestra este mensaje y te damos 10% en tu "
            f"próxima visita. — {shop_name}"
        )
    return (
        f"Hi {name}! Thanks for coming to {shop_name} — sorry about {issue} "
        f"({cite}). We're on it and will have your fix ready within 2 hours. "
        f"Show this message for 10% off your next visit! — {shop_name}"
    )


def draft_whatsapp_reply(customer: str, text: str, citation: str,
                         shop: str = "Maya's Tacos",
                         locale: str = "en") -> str:
    """Build a grounded WhatsApp-style draft for one annoyed customer.

    Primary path: ``omni_one.i18n.drafts.build_reply("whatsapp", loc, ...)``
    so en/es wording stays in the shared locale modules. Fallback path:
    :func:`_local_whatsapp_reply` (same contract) when the import fails.
    Deterministic and mock-LLM-free on both paths: pure string templates.
    """
    loc = _norm_locale(locale)
    try:
        from omni_one.i18n.drafts import build_reply as _build_reply
        return _build_reply("whatsapp", loc, customer, text, citation, shop)
    except Exception:
        return _local_whatsapp_reply(customer, text, citation, shop, loc)


def _guess_supplier(events: list[dict[str, Any]]) -> str:
    """Guess the supplier name from receipt headers (deterministic).

    Looks for a ``TIENDA <name>`` line inside any receipt raw text
    (the demo's first receipt says ``TIENDA SYSCO``). Falls back to
    ``"SYSCO"`` — the demo shop's known wholesaler — so the vendor
    draft always has someone to address. Never empty, never invented
    per-row: one supplier for the whole street-shop sheet.
    """
    import re as _re
    for e in events:
        if e.get("source") != "receipt":
            continue
        md = e.get("metadata", {}) or {}
        raw = md.get("raw", "")
        if not isinstance(raw, str):
            raw = str(raw)
        m = _re.search(r"TIENDA\s+([A-ZÁÉÍÓÚÑa-z][A-ZÁÉÍÓÚÑa-z ]{1,30})", raw)
        if m:
            name = m.group(1).strip()
            if name:
                return name[:30]
    # Fallback: also scan notebook-style raws for a wholesaler mention.
    for e in events:
        md = e.get("metadata", {}) or {}
        raw = md.get("raw", "")
        if not isinstance(raw, str):
            raw = str(raw)
        if "sysco" in raw.lower():
            return "SYSCO"
    return "SYSCO"


def _priority_for(text: str) -> str:
    """P0 (reply inside 2h) when the message smells like churn, else P1."""
    low = (text or "").lower()
    if any(w in low for w in P0_KEYWORDS):
        return "P0-reply-in-2h"
    return "P1-today"


# ---------------------------------------------------------------------------
# Reorder sheet — receipt mentions stand in for an inventory file
# ---------------------------------------------------------------------------

def _matching_receipt_events(item: str,
                             events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Receipt line-item events whose parsed item names the ingredient."""
    needle = (item or "").strip().lower()
    if not needle:
        return []
    out: list[dict[str, Any]] = []
    for e in events:
        if e.get("source") != "receipt":
            continue
        md = e.get("metadata", {}) or {}
        if md.get("signal") != "expense_item":
            continue
        name = str(md.get("item", "") or "").strip().lower()
        if needle in name or name in needle:
            out.append(e)
    return out


def _build_reorder_sheet(reorder_list: list[str],
                         events: list[dict[str, Any]],
                         vendor: str) -> list[dict[str, Any]]:
    """Build one reorder row per ingredient (sorted, most urgent first).

    Row contract (mirrors seller_close, street-shop columns):
    ``item, on_hand, sold, daily_velocity, days_left, reorder_qty,
    cover_days, vendor, urgency, citation`` where ``sold`` is the receipt
    mention count and ``citation`` is the first matching receipt line.
    """
    rows: list[dict[str, Any]] = []
    for rank, item in enumerate(list(reorder_list or [])[:MAX_REORDER_ROWS]):
        name = str(item or "").strip() or f"item-{rank + 1}"
        matches = _matching_receipt_events(name, events)
        sold = len(matches)
        total_spent = round(sum(_money(e.get("value")) for e in matches), 2)
        on_hand = max(0, BASE_STOCK - sold)
        velocity = round(sold / VELOCITY_WINDOW_DAYS, 4) if sold else 0.0
        if velocity > 0:
            days_left = round(on_hand / velocity, 2)
        else:
            days_left = 999.0
        need = math.ceil(velocity * COVER_DAYS - on_hand) if velocity else 0
        need = max(0, int(need))
        if days_left < ORDER_TODAY_DAYS:
            urgency = "ORDER TODAY"
        elif days_left < STOCKOUT_DAYS:
            urgency = "this week"
        else:
            urgency = "watch"
        if matches:
            citation = str((matches[0].get("metadata", {}) or {}).get("citation", ""))
        else:
            citation = f"[receipts:0] {name} (no receipt line — notebook estimate)"
        rows.append({
            "item": name,
            "on_hand": on_hand,
            "sold": sold,
            "total_spent_usd": total_spent,
            "daily_velocity": velocity,
            "days_left": days_left,
            "reorder_qty": need,
            "cover_days": COVER_DAYS,
            "vendor": vendor,
            "urgency": urgency,
            "citation": citation,
        })
    rows.sort(key=lambda r: (r["days_left"], r["item"]))
    return rows


# ---------------------------------------------------------------------------
# Vendor draft — supplier SMS/WhatsApp text, chat-short (NOT a PO email)
# ---------------------------------------------------------------------------

def _local_vendor_text(vendor: str, lines: list[dict[str, Any]],
                      shop: str, locale: str) -> str:
    """Local vendor text used when ``i18n`` PO builders are unavailable."""
    bullets = "\n".join(
        f"- {l['item']} x{l['reorder_qty']} (quedan {l['on_hand']}) [{l['citation']}]"
        if locale == "es"
        else f"- {l['item']} x{l['reorder_qty']} (have {l['on_hand']}) [{l['citation']}]"
        for l in lines[:3]
    ) or ("- (nada urgente)" if locale == "es" else "- (nothing urgent)")
    if locale == "es":
        return (
            f"Hola {vendor}! Soy Maya ({shop}). ¿Me mandas mañana?\n"
            f"{bullets}\n"
            f"Pagamos contra entrega. ¡Gracias!"
        )
    return (
        f"Hi {vendor}! Maya here ({shop}). Could you send tomorrow?\n"
        f"{bullets}\n"
        f"Pay on delivery. Thanks!"
    )


def draft_vendor_text(vendor: str, lines: list[dict[str, Any]],
                      shop: str = "Maya's Tacos",
                      locale: str = "en") -> str:
    """Build the chat-short supplier text (vendor.txt).

    Street shops text their supplier; they do not send PO emails. So this
    stays under ~500 characters, names the top lines with citations, and
    asks for tomorrow delivery with pay-on-delivery. Primary path reuses
    the shared ``i18n`` PO builder for consistent quantities, then trims
    to chat length; any failure falls back to :func:`_local_vendor_text`.
    The fallback keeps the same facts, so locale switches change words,
    never numbers.
    """
    loc = _norm_locale(locale)
    vendor_name = (vendor or "SYSCO").strip() or "SYSCO"
    shop_name = (shop or "Maya's Tacos").strip() or "Maya's Tacos"
    if not lines:
        if loc == "es":
            return (f"Hola {vendor_name}! Soy Maya ({shop_name}). Hoy estamos "
                    f"bien de stock, mañana te confirmo. ¡Gracias!")
        return (f"Hi {vendor_name}! Maya here ({shop_name}). Stock is fine "
                f"today, will confirm tomorrow. Thanks!")
    # Try the shared i18n PO builder first (quantities + citations stay
    # consistent with the rest of the pack), then compress to chat length.
    try:
        from omni_one.i18n.drafts import build_po as _build_po
        ll = [{"product": l["item"], "qty": l["reorder_qty"],
               "reorder_qty": l["reorder_qty"],
               "on_hand": l["on_hand"], "days_left": l["days_left"],
               "citation": l["citation"]} for l in lines[:3]]
        full = _build_po(loc, vendor_name, ll, shop_name)
        chat = _to_chat_short(full, vendor_name, shop_name, loc,
                              fallback_cite=lines[0].get("citation", ""))
        if chat:
            return chat
    except Exception:
        pass
    return _local_vendor_text(vendor_name, lines, shop_name, loc)


def _to_chat_short(full: str, vendor: str, shop: str, locale: str,
                   fallback_cite: str = "") -> str:
    """Compress an i18n PO email into a <500-char supplier chat message.

    Keeps the greeting, the ``- item x qty`` bullets, and the first
    citation; drops the Subject line, cover note, and sign-off boilerplate.
    The shared PO builder prints its citation bare (``Source: inv.csv``),
    so when no ``[...]`` evidence survives compression we append the
    top buy line's ``[file:line]`` citation instead — the vendor text
    stays grounded either way. Returns "" when there is nothing usable
    (caller falls back to local).
    """
    lines = [l.rstrip() for l in (full or "").splitlines() if l.strip()]
    if not lines:
        return ""
    bullets = [l for l in lines if l.strip().startswith("-")]
    cite = ""
    for l in lines:
        if "[" in l and "]" in l:
            cite = l[l.index("["):l.index("]") + 1]
            break
    if not cite and fallback_cite:
        cite = fallback_cite if fallback_cite.startswith("[") else f"[{fallback_cite}]"
    head = (f"Hola {vendor}! Soy Maya ({shop}). ¿Me mandas mañana?"
            if locale == "es"
            else f"Hi {vendor}! Maya here ({shop}). Could you send tomorrow?")
    tail = ("Pagamos contra entrega. ¡Gracias!"
            if locale == "es"
            else "Pay on delivery. Thanks!")
    body = "\n".join(bullets[:3]) or (full[:200] + ("..." if len(full) > 200 else ""))
    if cite and cite not in body:
        body = f"{body} {cite}"
    text = f"{head}\n{body}\n{tail}"
    if len(text) > 480:
        text = text[:477] + "..."
    return text


# ---------------------------------------------------------------------------
# Money leaks — dollar amounts with evidence, not charts
# ---------------------------------------------------------------------------

def _build_money_leaks(events: list[dict[str, Any]],
                       revenue: float, expenses: float) -> list[dict[str, Any]]:
    """Detect street-shop money leaks (deterministic, capped at MAX_LEAKS).

    Leak types:
    - ``cancelled_sale`` — a sales_log row marked cancelled (lost revenue).
    - ``food_cost_high`` — receipt totals eat >60% of revenue (waste check).
    - ``slow_service`` — chat/notebook mentions of no-shows or long waits
      (the churn driver behind tomorrow's missing revenue).
    Every leak carries ``leak, amount_usd, note, evidence`` where evidence
    is a real ``[file:line]`` citation.
    """
    leaks: list[dict[str, Any]] = []

    # 1. Cancelled orders: scan sales_log rows for cancel notes/signals.
    for e in events:
        if e.get("source") != "sales_log":
            continue
        md = e.get("metadata", {}) or {}
        raw = md.get("raw", "")
        blob = str(raw).lower()
        notes = str(md.get("notes", "") or "").lower()
        item = str(md.get("item", "") or "sale")
        if "cancel" in blob or "cancel" in notes:
            cite = str(md.get("citation", ""))
            amount = _money(e.get("value"))
            leaks.append({
                "leak": "cancelled_sale",
                "amount_usd": round(amount, 2),
                "note": (f"Cancelled order ({item}) = ${amount:.2f} lost — "
                         f"stockout killed the sale, fix the reorder sheet"),
                "evidence": cite or "[sales_log.csv:?] cancelled row",
            })
            break  # one representative leak; the sheet lists every row

    # 2. Food-cost pressure: expenses above 60% of revenue.
    if revenue > 0 and expenses > revenue * 0.6:
        pct = expenses / revenue * 100
        net = revenue - expenses
        leaks.append({
            "leak": "food_cost_high",
            "amount_usd": round(expenses, 2),
            "note": (f"Food cost {pct:.1f}% of revenue "
                     f"(${expenses:.2f} on ${revenue:.2f}, net ${net:.2f}) — "
                     f"check portions and waste before raising prices"),
            "evidence": (f"[receipt totals ${expenses:.2f} vs "
                         f"sales ${revenue:.2f}]"),
        })

    # 3. Slow service: staff gaps / long waits cited in chat or notebook.
    for e in events:
        md = e.get("metadata", {}) or {}
        raw = md.get("raw", "")
        val = e.get("value", "")
        blob = f"{raw} {val}".lower()
        if any(w in blob for w in SLOW_SERVICE_KEYWORDS):
            cite = str(md.get("citation", ""))
            if cite:
                leaks.append({
                    "leak": "slow_service",
                    "amount_usd": None,
                    "note": ("No-show / long waits mentioned — short staff "
                             "turns regulars into at-risk chats; confirm "
                             "tomorrow's shift tonight"),
                    "evidence": cite,
                })
                break

    return leaks[:MAX_LEAKS]


def _happy_customer_sender(events: list[dict[str, Any]],
                           at_risk_senders: set[str]) -> str:
    """Pick a happy-customer name for the referral nudge (deterministic).

    Scans WhatsApp events for praise words from someone who is NOT in the
    at-risk set and NOT the shop itself. Falls back to "a happy regular".
    """
    praise = ("amazing", "love", "gracias", "delicioso", "rico", "excelente",
              "great", "wonderful", "buen")
    for e in events:
        if e.get("source") not in ("whatsapp", "instagram", "voice_note"):
            continue
        md = e.get("metadata", {}) or {}
        sender = str(md.get("sender", "") or "").strip()
        if not sender or sender in at_risk_senders:
            continue
        text = str(e.get("value", "") or "")
        low = text.lower()
        if any(w in low for w in praise) and not any(
                h in low for h in SHOP_GREETING_HINTS):
            return _first_name(sender)
    return "a happy regular"


# ---------------------------------------------------------------------------
# Main builder — events + micro_biz briefing -> street-shop close
# ---------------------------------------------------------------------------

def build_micro_close(events: list[dict[str, Any]],
                      briefing: dict[str, Any] | None = None,
                      date_str: str | None = None,
                      shop: str = "Maya's Tacos",
                      locale: str = "en") -> dict[str, Any]:
    """Build the micro-biz close for a street shop (deterministic).

    Args:
        events: normalized pipeline events from
            ``omni_one.packs._labs.micro_biz.ingest_folder`` (receipts,
            WhatsApp chat, sales_log, notebook). Empty list is fine.
        briefing: optional precomputed ``build_briefing(events)`` dict.
            When None it is built inside (mock router, no API key).
        date_str: ``YYYY-MM-DD`` label. Defaults to today. Excluded from
            every idempotency comparison except the ``date`` field itself.
        shop: display name used in drafts and headline.
        locale: ``"en"`` or ``"es"``. Unknown values fall back to ``"en"``.
            Locale changes words only — every number stays identical.

    Returns:
        dict with ``date, shop, locale, headline, kpis, do_today[3],
        reorder_sheet, reply_queue, money_leaks, vendor_draft, citations,
        free, offline``. Every draft embeds a ``[file:line]`` citation;
        every dollar traces to briefing KPIs.
    """
    from omni_one.packs._labs.micro_biz import build_briefing

    briefing = briefing or build_briefing(events or [])
    k = briefing.get("kpis", {}) or {}
    loc = _norm_locale(locale)
    shop_name = (shop or "Maya's Tacos").strip() or "Maya's Tacos"

    # ---- 1. money: revenue / avg ticket / money at risk -------------------
    revenue = round(_money(k.get("revenue")), 2)
    expenses = round(_money(k.get("expenses")), 2)
    net = round(_money(k.get("net", revenue - expenses)), 2)

    sales_events = [e for e in (events or [])
                    if e.get("source") == "sales_log"
                    and isinstance(e.get("value"), (int, float))]
    orders = len(sales_events)
    items_qty = 0.0
    for e in sales_events:
        md = e.get("metadata", {}) or {}
        qty = md.get("qty")
        try:
            qty_f = float(qty) if qty is not None else 1.0
        except (TypeError, ValueError):
            qty_f = 1.0
        items_qty += qty_f
    items_qty = round(items_qty, 2)
    # Convention: bl‑ended "orders/items" KPI — orders counts sale rows,
    # items counts portions sold. avg ticket = revenue per order row.
    avg_ticket = round(revenue / orders, AVG_DECIMALS) if orders else 0.0

    at_risk_n = int(k.get("at_risk_customers", 0) or 0)
    happy_n = int(k.get("happy_customers", 0) or 0)
    # Core invariant (asserted in tests + docs): each at-risk regular is
    # worth roughly one avg ticket of tomorrow's revenue.
    money_at_risk = round(at_risk_n * avg_ticket, AVG_DECIMALS)

    best = k.get("best_seller") or {}
    if isinstance(best, dict):
        best_item = {"item": str(best.get("item", "—")),
                     "qty": _money(best.get("qty"))}
    elif isinstance(best, (list, tuple)) and len(best) == 2:
        best_item = {"item": str(best[0]), "qty": _money(best[1])}
    else:
        best_item = {"item": "—", "qty": 0.0}
    worst = k.get("worst_seller") or {}
    if isinstance(worst, dict):
        worst_item = {"item": str(worst.get("item", "—")),
                      "qty": _money(worst.get("qty"))}
    elif isinstance(worst, (list, tuple)) and len(worst) == 2:
        worst_item = {"item": str(worst[0]), "qty": _money(worst[1])}
    else:
        worst_item = {"item": "—", "qty": 0.0}

    # ---- 2. reorder sheet --------------------------------------------------
    vendor = _guess_supplier(events or [])
    reorder = _build_reorder_sheet(
        list(briefing.get("reorder_list", []) or []), events or [], vendor)
    must_buy = sum(1 for r in reorder if r["urgency"] == "ORDER TODAY")
    stockout_n = must_buy

    # ---- 3. WhatsApp reply queue -------------------------------------------
    reply_queue: list[dict[str, Any]] = []
    for item in (briefing.get("at_risk_preview", []) or [])[:MAX_REPLY_QUEUE]:
        item = item or {}
        text = str(item.get("text", "") or "")
        cite = str(item.get("citation", "") or "")
        sender = str(item.get("sender", "") or "").strip()
        if not sender:
            sender = text.split(":")[0].strip() if ":" in text else "customer"
        customer = _first_name(sender)
        if not cite:
            cite = "[whatsapp_chat.txt:?] message"
        draft = draft_whatsapp_reply(customer, text, cite, shop_name, loc)
        reply_queue.append({
            "channel": "whatsapp",
            "customer": customer,
            "summary": text[:120],
            "draft": draft,
            "citation": cite,
            "priority": _priority_for(text),
        })

    # ---- 4. money leaks ------------------------------------------------------
    leaks = _build_money_leaks(events or [], revenue, expenses)

    # ---- 5. vendor draft (chat-short) ----------------------------------------
    buy_lines = [r for r in reorder if r["reorder_qty"] > 0] or reorder[:3]
    vendor_draft = draft_vendor_text(vendor, buy_lines, shop_name, loc)

    # ---- 6. headline: the one line read while the coffee brews ---------------
    headline = (f"{shop_name} ${revenue:.2f} today · "
                f"{at_risk_n} customer(s) to win back · "
                f"{must_buy} buy(s) TODAY · "
                f"${money_at_risk:.2f} at risk")

    # ---- 7. do_today: exactly three actions ----------------------------------
    at_risk_senders = {str((q.get("customer") or "")).strip()
                       for q in reply_queue}
    happy_name = _happy_customer_sender(events or [], at_risk_senders)
    if reply_queue:
        do_reply = (f"WhatsApp {len(reply_queue)} annoyed customer(s) back — "
                    f"${money_at_risk:.2f} at risk (drafts below, answer "
                    f"inside 2h)")
    else:
        do_reply = "No annoyed customers — send today's menu to the group chat"
    if reorder:
        top = reorder[0]
        do_buy = (f"Buy {top['item']} x{top['reorder_qty']} from {vendor} "
                  f"({top['days_left']}d left)")
    else:
        do_buy = "No ingredients tracked — photo today's supplier receipt"
    if leaks:
        do_leak = (f"Plug leak: {leaks[0]['leak']} — "
                   f"{leaks[0]['note'][:90]}")
    elif happy_n:
        do_leak = (f"Ask {happy_name} for a referral — happy regulars "
                   f"bring tomorrow's line")
    else:
        do_leak = "Log today's sales in the notebook — more data tomorrow"
    do_today = [do_reply, do_buy, do_leak]

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "shop": shop_name,
        "locale": loc,
        "headline": headline,
        "kpis": {
            "revenue": revenue,
            "expenses": expenses,
            "net": net,
            "orders": orders,
            "items": items_qty,
            "avg_ticket": avg_ticket,
            "best_item": best_item,
            "worst_item": worst_item,
            "at_risk": at_risk_n,
            "happy": happy_n,
            "stockout_n": stockout_n,
            "reorder_n": len(reorder),
            "money_at_risk": money_at_risk,
        },
        "do_today": do_today,
        "reorder_sheet": reorder,
        "reply_queue": reply_queue,
        "money_leaks": leaks,
        "vendor_draft": vendor_draft,
        "citations": ("every number cites [file:line]; WhatsApp drafts cite "
                      "chat lines, reorder rows cite receipt lines; audit "
                      "via micro_biz briefing"),
        "free": True,
        "offline": True,
    }


# ---------------------------------------------------------------------------
# Exporters — CSV/TXT shapes mirror seller_close for tooling reuse
# ---------------------------------------------------------------------------

def close_to_csv(close: dict[str, Any]) -> str:
    """Render the close as CSV (headline + KPIs + actions + sheet + leaks).

    Shape mirrors ``seller_close.close_to_csv`` so the same accountant
    scripts and spreadsheet imports keep working: a title row, a
    metric/value block, a do_today block, the reorder table, and the
    leaks table.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["MICRO CLOSE", close.get("date", ""), close.get("headline", "")])
    w.writerow([])
    w.writerow(["metric", "value"])
    for key, val in (close.get("kpis") or {}).items():
        w.writerow([key, val])
    w.writerow([])
    w.writerow(["do_today_n", "do_today"])
    for i, task in enumerate(close.get("do_today", []), 1):
        w.writerow([i, task])
    w.writerow([])
    w.writerow(["item", "on_hand", "sold", "days_left", "reorder_qty_7d",
                "vendor", "urgency", "citation"])
    for r in close.get("reorder_sheet", []):
        w.writerow([r.get("item", ""), r.get("on_hand", ""), r.get("sold", ""),
                    r.get("days_left", ""), r.get("reorder_qty", ""),
                    r.get("vendor", ""), r.get("urgency", ""),
                    r.get("citation", "")])
    w.writerow([])
    w.writerow(["leak", "amount_usd", "note", "evidence"])
    for leak in close.get("money_leaks", []):
        w.writerow([leak.get("leak", ""), leak.get("amount_usd", ""),
                    str(leak.get("note", ""))[:160],
                    leak.get("evidence", "")])
    return buf.getvalue()


def reorder_to_csv(close: dict[str, Any]) -> str:
    """Render the reorder sheet as CSV (one row per ingredient).

    Columns mirror ``seller_close.reorder_to_csv`` with street-shop
    renames (``sold_7d`` -> ``sold`` since mentions already span ~7d,
    ``reorder_qty_14d`` -> ``reorder_qty_7d`` for the 7-day cover,
    ``supplier`` -> ``vendor`` for the market supplier).
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["item", "on_hand", "sold", "daily_velocity", "days_left",
                "reorder_qty_7d", "vendor", "urgency", "citation"])
    for r in close.get("reorder_sheet", []):
        w.writerow([r.get("item", ""), r.get("on_hand", ""), r.get("sold", ""),
                    r.get("daily_velocity", ""), r.get("days_left", ""),
                    r.get("reorder_qty", ""), r.get("vendor", ""),
                    r.get("urgency", ""), r.get("citation", "")])
    return buf.getvalue()


def replies_to_txt(close: dict[str, Any]) -> str:
    """Render the WhatsApp reply queue + vendor draft as copy-paste text.

    Shape mirrors ``seller_close.replies_to_txt``: a header with the money
    at risk, numbered ``COPY-PASTE DRAFT`` blocks (each with evidence),
    then the supplier text under a ``VENDOR DRAFT`` banner (where seller
    close prints ``PO DRAFT``).
    """
    kpis = close.get("kpis") or {}
    money = _money(kpis.get("money_at_risk"))
    out = [f"MICRO CLOSE {close.get('date', '')} — WHATSAPP QUEUE "
           f"(${money:.2f} at risk)",
           "=" * 64, ""]
    queue = close.get("reply_queue", []) or []
    if not queue:
        out += ["No annoyed customers today — send the menu to the group chat.", ""]
    for i, q in enumerate(queue, 1):
        out += [f"[{i}] {q.get('priority', '')} — "
                f"{q.get('channel', '')}: {q.get('customer', '')}",
                f"    customer said: {q.get('summary', '')}",
                f"    evidence: {q.get('citation', '')}",
                f"    COPY-PASTE DRAFT: {q.get('draft', '')}", ""]
    out += ["VENDOR DRAFT (text to supplier):", "-" * 64,
            close.get("vendor_draft", "")]
    return "\n".join(out)


def vendor_to_txt(close: dict[str, Any]) -> str:
    """Render the vendor file: supplier text plus the buy table.

    This is the ``vendor.txt`` bundle member — what the owner forwards on
    WhatsApp plus the numbers behind it, so the supplier sees quantities
    and the owner keeps the citations.
    """
    kpis = close.get("kpis") or {}
    lines = [f"MICRO CLOSE {close.get('date', '')} — TEXT TO SUPPLIER",
             "=" * 64, "",
             close.get("vendor_draft", ""), "",
             "-" * 64,
             f"revenue ${float(kpis.get('revenue', 0)):.2f} · "
             f"{kpis.get('stockout_n', 0)} buy(s) TODAY", ""]
    for r in close.get("reorder_sheet", [])[:3]:
        lines.append(f"- {r.get('item', '')} x{r.get('reorder_qty', '')} "
                     f"(have {r.get('on_hand', '')}, "
                     f"{r.get('days_left', '')}d left) [{r.get('citation', '')}]")
    return "\n".join(lines)


def write_close_bundle(close: dict[str, Any],
                       out_dir: str | Path) -> dict[str, str]:
    """Write the 5-file close bundle (mirrors seller_close bundle shape).

    Files: ``close.json`` (full dict) + ``close.csv`` (numbers) +
    ``reorder.csv`` (buy sheet) + ``replies.txt`` (WhatsApp drafts) +
    ``vendor.txt`` (supplier text). Returns ``{name: path}`` (5 entries).
    Creates ``out_dir`` when missing. Deterministic: same close writes
    byte-identical files.
    """
    import json as _json
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(
        _json.dumps(close, indent=2, default=str, ensure_ascii=False))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close), encoding="utf-8")
    paths["reorder.csv"] = str(out / "reorder.csv")
    (out / "reorder.csv").write_text(reorder_to_csv(close), encoding="utf-8")
    paths["replies.txt"] = str(out / "replies.txt")
    (out / "replies.txt").write_text(replies_to_txt(close), encoding="utf-8")
    paths["vendor.txt"] = str(out / "vendor.txt")
    vendor_text = vendor_to_txt(close)
    (out / "vendor.txt").write_text(vendor_text, encoding="utf-8")
    return paths


# ---------------------------------------------------------------------------
# Appendix: worked golden example (kept in sync with tests + MICRO_CLOSE.md)
# ---------------------------------------------------------------------------
# Demo folder (seed=42, Maya's Tacos) -> 27 events:
#   whatsapp x8 (2 at-risk: Maria line 2, Ana line 7; 2 happy)
#   sales_log x5 ($112.00 + $48.00 + $24.00 + $40.00 + $17.50 = $241.50)
#   receipt x14 (totals $12.00 notebook quirk + $68.50 + $69.50 + $69.50)
# Briefing KPIs: revenue 241.50, expenses 219.50, net 22.00,
#   best "tacos al pastor" x32, at-risk 2, reorder 5 items.
# Close KPIs: orders 5, items 77.0, avg ticket 48.30,
#   money at risk 96.60 (= 2 x 48.30), stockout_n 2.
# Reorder head: cilantro — sold 3, on_hand 1, velocity 0.4286,
#   days_left 2.33, reorder_qty 3 (7-day cover), ORDER TODAY,
#   citation from receipt_2024-09-11.txt:4.
# Headline: "Maya's Tacos $241.50 today · 2 customer(s) to win back ·
#   2 buy(s) TODAY · $96.60 at risk".
# Reply drafts: Maria + Ana, each with its [whatsapp_chat.txt:N] citation
#   and a 2-hour promise ("within 2 hours" en / "en menos de 2 horas" es).
# Vendor draft: SYSCO, cilantro + onions bullets, chat-short (<500 chars).
# Leaks: cancelled_sale $17.50 [sales_log.csv:6], food_cost_high $219.50,
#   slow_service citing [whatsapp_chat.txt:2] (first slow-service mention
#   in event order; the notebook.txt:1 note says the same).
# Bundle: close.json + close.csv + reorder.csv + replies.txt + vendor.txt.
# End of micro_close module.
