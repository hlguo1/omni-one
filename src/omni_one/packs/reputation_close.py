"""
Reviews & Reputation Close — the daily 5-star ritual (flagship pack).
=====================================================================
Shops don't want a "review dashboard". They want to CLOSE the day:

  1. What is my star average right now? (avg_stars, deterministic math)
  2. Who needs a reply NOW before they churn/1-star? (stars<=3, worst-first)
  3. Who loves me and should be asked for a referral/photo review? (5-star ask_list)
  4. What keeps going wrong? (complaint_themes: late/damaged/wrong counts)
  5. File something for tomorrow. (close.json / close.csv / reviews.csv / replies.txt)

One call, offline, $0::

    from omni_one.packs.reputation_close import (
        DEMO_REVIEWS, build_reputation_close, write_close_bundle,
    )

    close = build_reputation_close()          # seeded demo (seed=42)
    write_close_bundle(close, "./reputation_close_today")
    # -> close.json + close.csv + reviews.csv + replies.txt

Design rules (flagship contract, mirrors seller_close / micro_close):
- Deterministic, no LLM. Drafts are string templates grounded in citations.
- Every draft cites [channel:reviews#N]. No phantom reviews.
- Idempotent: same reviews -> same close (minus the date stamp).
- Private: data never leaves the laptop. Works on plane wifi.
- Free: stdlib only (+ repo-local seller_close import with local fallback).

Sibling map vs seller_close / micro_close (read both before editing):

==================  ============================  ==============================
concern             seller/micro_close              reputation_close (this pack)
==================  ============================  ==============================
signal source       briefing + scenarios/events     review list only (no pipeline)
money               GMV/fees or cash revenue        stars (no money math)
reply channel       DM/review/WhatsApp              review replies only
reply promise       "within 2 hours"                make-right offer (no ETA lie)
ask channel         referral nudge (micro only)     5-star referral/photo ask
themes              money leaks / reorder           complaint keywords late/damaged/wrong
bundle file #4      reorder.csv (buy sheet)         reviews.csv (stars + theme)
==================  ============================  ==============================

Golden demo (seed=42) — asserted in tests, do not drift:
- 10 reviews, stars [5,5,5,5,5,5,5,4,2,1] (sum 42, avg 4.2)
- count_1_2 = 2 (Ivan 2★, Judy 1★), count_5 = 7, need_reply = 2
- complaint_themes: late 3 (Heidi, Ivan, Judy), damaged 1 (Ivan), wrong 1 (Judy)
- reply_queue head: Judy 1★ [etsy:reviews#10], then Ivan 2★ [amazon:reviews#9]
- ask_list: Alice, Bob, Cara (first three 5★, max 3)
- headline: "REPUTATION CLOSE: 4.2★ across 10 review(s) · 2 need reply NOW · top gripe 'late' (3)"
- Bundle: close.json + close.csv + reviews.csv + replies.txt.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Any

__all__ = [
    "DEMO_REVIEWS",
    "demo_reviews",
    "draft_reputation_reply",
    "build_reputation_close",
    "close_to_csv",
    "reviews_to_csv",
    "replies_to_txt",
    "write_close_bundle",
]

DEMO_SEED = 42
COMPLAINT_KEYWORDS = ("late", "damaged", "wrong")
MAX_ASK = 3

# Import seller_close draft helper when available so review wording stays
# consistent across packs. Never fatal: local template fallback below.
try:  # pragma: no cover - import probe, fallback tested separately
    from omni_one.packs.seller_close import (  # type: ignore
        draft_review_reply as _seller_draft_review_reply,
    )
except Exception:  # pragma: no cover
    _seller_draft_review_reply = None  # type: ignore


def _first_name(reviewer: str) -> str:
    reviewer = (reviewer or "there").strip().split()[0].strip(",:@")
    return reviewer[:20] or "there"


def _local_review_reply(
    reviewer: str, product: str, text: str, citation: str, shop: str
) -> str:
    """Local review-reply template (seller_close style + first-name greeting)."""
    name = _first_name(reviewer)
    shop_name = (shop or "our shop").strip() or "our shop"
    cite = (citation or "[reviews:1]").strip() or "[reviews:1]"
    prod = (product or "item").strip() or "item"
    return (
        f"Hi {name}! Thank you for flagging this ({cite}) — we're sorry about "
        f"your {prod} experience. We've fixed the packing/quality check that "
        f"caused it. Please DM us for a free replacement or refund — we want "
        f"to make this right. — {shop_name}"
    )


def draft_reputation_reply(
    reviewer: str,
    product: str,
    text: str,
    citation: str,
    shop: str = "our shop",
) -> str:
    """Build a grounded copy-paste reply for one unhappy reviewer.

    Primary path reuses ``seller_close.draft_review_reply`` (same claims,
    same citation) prefixed with a ``Hi <FirstName>!`` greeting so the draft
    is personal. Fallback path uses the local template above. Deterministic,
    mock-LLM-free on both paths.
    """
    name = _first_name(reviewer)
    shop_name = (shop or "our shop").strip() or "our shop"
    if _seller_draft_review_reply is not None:
        try:
            base = _seller_draft_review_reply(product, text, citation, shop_name)
            if name and name not in base:
                return f"Hi {name}! {base}"
            return base
        except Exception:
            pass
    return _local_review_reply(reviewer, product, text, citation, shop_name)


def DEMO_REVIEWS(seed: int = 42) -> list[dict[str, Any]]:  # noqa: N802
    """Deterministic demo reviews (~10, fixed distribution, seeded API).

    Args:
        seed: accepted for flagship API parity. The star distribution is
            FIXED ([5]*7 + [4,2,1]) so the average (4.2) never drifts with
            the seed; the seed is echoed in the close dict for audit.

    Returns:
        List of 10 dicts with reviewer/stars/text/product/channel/citation.
    """
    _ = seed  # fixed distribution by design; seed kept for parity/audit
    return [
        {"reviewer": "Alice", "stars": 5, "text": "Love it! Fast shipping, perfect quality.",
         "product": "Mug", "channel": "etsy", "citation": "[etsy:reviews#1]"},
        {"reviewer": "Bob", "stars": 5, "text": "Excellent, exactly as described, will buy again.",
         "product": "Candle", "channel": "shopify", "citation": "[shopify:reviews#2]"},
        {"reviewer": "Cara", "stars": 5, "text": "Beautiful packaging, my daughter loves the design.",
         "product": "Tote", "channel": "amazon", "citation": "[amazon:reviews#3]"},
        {"reviewer": "Dan", "stars": 5, "text": "Great seller, quick response, five stars.",
         "product": "Mug", "channel": "etsy", "citation": "[etsy:reviews#4]"},
        {"reviewer": "Eve", "stars": 5, "text": "Perfect gift, arrived early and flawless.",
         "product": "Candle", "channel": "shopify", "citation": "[shopify:reviews#5]"},
        {"reviewer": "Frank", "stars": 5, "text": "Superb quality, left a photo review already.",
         "product": "Poster", "channel": "amazon", "citation": "[amazon:reviews#6]"},
        {"reviewer": "Grace", "stars": 5, "text": "Lovely! Will refer friends to this shop.",
         "product": "Tote", "channel": "etsy", "citation": "[etsy:reviews#7]"},
        {"reviewer": "Heidi", "stars": 4, "text": "Good but box arrived late by a day.",
         "product": "Mug", "channel": "shopify", "citation": "[shopify:reviews#8]"},
        {"reviewer": "Ivan", "stars": 2, "text": "Arrived late and box was damaged, very disappointed.",
         "product": "Candle", "channel": "amazon", "citation": "[amazon:reviews#9]"},
        {"reviewer": "Judy", "stars": 1, "text": "Wrong item sent and arrived late, need refund.",
         "product": "Poster", "channel": "etsy", "citation": "[etsy:reviews#10]"},
    ]


# lowercase alias (flagship convenience; same object)
demo_reviews = DEMO_REVIEWS


def _theme_for(text: str) -> str:
    """Primary complaint theme for one snippet (late/damaged/wrong/praise)."""
    low = (text or "").lower()
    hits = []
    if "late" in low:
        hits.append("late")
    if "damag" in low:
        hits.append("damaged")
    if "wrong" in low:
        hits.append("wrong")
    return "+".join(hits) if hits else "praise"


def _complaint_themes(reviews: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"late": 0, "damaged": 0, "wrong": 0}
    for r in reviews or []:
        low = str(r.get("text", "") or "").lower()
        if "late" in low:
            counts["late"] += 1
        if "damag" in low:
            counts["damaged"] += 1
        if "wrong" in low:
            counts["wrong"] += 1
    return counts


def build_reputation_close(
    reviews: list[dict[str, Any]] | None = None,
    seed: int = 42,
    shop: str = "our shop",
    date_str: str | None = None,
) -> dict[str, Any]:
    """Build the Reputation Close (deterministic, no LLM, $0 offline).

    Args:
        reviews: review dicts (reviewer/stars/text/product/channel/citation).
            When None the seeded demo ``DEMO_REVIEWS(seed)`` is used.
        seed: echoed in the output for audit; demo distribution is fixed.
        shop: display name used in drafts and headline context.
        date_str: ``YYYY-MM-DD`` label. Defaults to today. Excluded from
            every idempotency comparison except the ``date`` field itself.

    Returns:
        dict with date, headline, kpis, reply_queue[{reviewer,stars,product,
        draft,citation}], ask_list, complaint_themes, do_today[3],
        citations, reviews, free, offline, seed, shop.
    """
    shop_name = (shop or "our shop").strip() or "our shop"
    items = [dict(r) for r in (reviews if reviews is not None else DEMO_REVIEWS(seed=seed))]
    n = len(items)
    stars = [int(r.get("stars", 0) or 0) for r in items]
    avg = round(sum(stars) / n, 2) if n else 0.0
    count_1_2 = sum(1 for s in stars if s <= 2)
    count_5 = sum(1 for s in stars if s == 5)
    need_reply = sum(1 for s in stars if s <= 3)
    themes = _complaint_themes(items)
    # top gripe: max count, tie-break fixed order late/damaged/wrong
    top, top_n = "none", 0
    for key in ("late", "damaged", "wrong"):
        if themes.get(key, 0) > top_n:
            top, top_n = key, themes[key]

    # reply queue: stars<=3, worst-first (stars asc, then reviewer for stability)
    low = [r for r in items if int(r.get("stars", 0) or 0) <= 3]
    low.sort(key=lambda r: (int(r.get("stars", 0) or 0), str(r.get("reviewer", ""))))
    reply_queue: list[dict[str, Any]] = []
    for r in low:
        reviewer = str(r.get("reviewer", "customer"))
        product = str(r.get("product", "item"))
        text = str(r.get("text", ""))
        citation = str(r.get("citation", ""))
        draft = draft_reputation_reply(reviewer, product, text, citation, shop_name)
        reply_queue.append({
            "reviewer": reviewer,
            "stars": int(r.get("stars", 0) or 0),
            "product": product,
            "draft": draft,
            "citation": citation,
        })

    # ask_list: first MAX_ASK 5-star reviewers (input order, deterministic)
    ask_list: list[dict[str, Any]] = []
    for r in items:
        if int(r.get("stars", 0) or 0) != 5:
            continue
        if len(ask_list) >= MAX_ASK:
            break
        reviewer = str(r.get("reviewer", "customer"))
        first = _first_name(reviewer)
        product = str(r.get("product", "item"))
        citation = str(r.get("citation", ""))
        ask_list.append({
            "reviewer": reviewer,
            "stars": 5,
            "product": product,
            "citation": citation,
            "ask": (
                f"Hi {first}! Thanks for the 5-star review on {product} "
                f"({citation}) — would you share a photo review or refer a "
                f"friend? It helps {shop_name} hugely. — {shop_name}"
            ),
        })

    # do_today: exactly three strings
    if reply_queue:
        worst = reply_queue[0]
        do_reply = (
            f"Reply to {worst['reviewer']} ({worst['stars']} star on "
            f"{worst['product']}) {worst['citation']} — draft ready in replies.txt"
        )
    else:
        do_reply = "No reviews need a reply — thank a 5-star reviewer instead"
    if top_n > 0:
        do_fix = (
            f"Fix recurring gripe '{top}' ({top_n} mention(s)) — "
            f"check packing/shipping checklist before tomorrow's batch"
        )
    else:
        do_fix = "No recurring complaint — keep the packing checklist tight"
    if ask_list:
        happy = ask_list[0]
        do_ask = (
            f"Ask {happy['reviewer']} for a referral/photo review "
            f"({happy['citation']}) — happy customers bring tomorrow's sales"
        )
    else:
        do_ask = "No 5-star reviewers to ask — deliver today's orders flawlessly"
    do_today = [do_reply, do_fix, do_ask]

    headline = (
        f"REPUTATION CLOSE: {avg:.1f}\u2605 across {n} review(s) \u00b7 "
        f"{need_reply} need reply NOW \u00b7 top gripe '{top}' ({top_n})"
    )
    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "shop": shop_name,
        "seed": seed,
        "headline": headline,
        "kpis": {
            "avg_stars": avg,
            "total": n,
            "count": n,
            "count_1_2": count_1_2,
            "count_5": count_5,
            "need_reply": need_reply,
            "top_theme": top,
            "top_theme_n": top_n,
        },
        "reply_queue": reply_queue,
        "ask_list": ask_list,
        "complaint_themes": themes,
        "do_today": do_today,
        "reviews": items,
        "citations": "every reply cites [channel:reviews#N]; audit via reviews.csv",
        "free": True,
        "offline": True,
    }


def close_to_csv(close: dict[str, Any]) -> str:
    """Render the close as CSV (headline + KPIs + actions + reviews table).

    Shape mirrors seller_close.close_to_csv so accountant tooling keeps
    working; the reviews table carries stars + theme per review.
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["REPUTATION CLOSE", close.get("date", ""), close.get("headline", "")])
    w.writerow([])
    w.writerow(["metric", "value"])
    for key, val in (close.get("kpis") or {}).items():
        w.writerow([key, val])
    w.writerow([])
    w.writerow(["do_today_n", "do_today"])
    for i, task in enumerate(close.get("do_today", []), 1):
        w.writerow([i, task])
    w.writerow([])
    w.writerow(["reviewer", "stars", "product", "channel", "theme", "citation", "snippet"])
    for r in close.get("reviews", []) or []:
        w.writerow([
            r.get("reviewer", ""),
            r.get("stars", ""),
            r.get("product", ""),
            r.get("channel", ""),
            _theme_for(str(r.get("text", ""))),
            r.get("citation", ""),
            str(r.get("text", ""))[:120],
        ])
    return buf.getvalue()


def reviews_to_csv(close: dict[str, Any]) -> str:
    """Render the reviews table as CSV (one row per review, stars + theme)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["reviewer", "stars", "product", "channel", "theme", "citation", "snippet"])
    for r in close.get("reviews", []) or []:
        w.writerow([
            r.get("reviewer", ""),
            r.get("stars", ""),
            r.get("product", ""),
            r.get("channel", ""),
            _theme_for(str(r.get("text", ""))),
            r.get("citation", ""),
            str(r.get("text", ""))[:120],
        ])
    return buf.getvalue()


def replies_to_txt(close: dict[str, Any]) -> str:
    """Render reply_queue + ask_list as copy-paste text (the phone screen)."""
    kpis = close.get("kpis") or {}
    out = [
        f"REPUTATION CLOSE {close.get('date', '')} — REPLY QUEUE "
        f"({kpis.get('need_reply', 0)} need reply NOW, "
        f"{kpis.get('avg_stars', 0):.1f} stars avg)",
        "=" * 64,
        "",
    ]
    queue = close.get("reply_queue", []) or []
    if not queue:
        out += ["No reviews need a reply today — thank a happy customer!", ""]
    for i, q in enumerate(queue, 1):
        out += [
            f"[{i}] {q.get('stars', '')} star — {q.get('reviewer', '')} on {q.get('product', '')}",
            f"    evidence: {q.get('citation', '')}",
            f"    COPY-PASTE DRAFT: {q.get('draft', '')}",
            "",
        ]
    out += ["ASK LIST (5-star referral/photo asks):", "-" * 64]
    asks = close.get("ask_list", []) or []
    if not asks:
        out += ["(no 5-star reviewers to ask today)"]
    for a in asks:
        out += [f"- {a.get('reviewer', '')} on {a.get('product', '')} {a.get('citation', '')}: {a.get('ask', '')}"]
    return "\n".join(out)


def write_close_bundle(close: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + reviews.csv + replies.txt. Returns paths."""
    import json as _json

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(_json.dumps(close, indent=2, default=str, ensure_ascii=False))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close), encoding="utf-8")
    paths["reviews.csv"] = str(out / "reviews.csv")
    (out / "reviews.csv").write_text(reviews_to_csv(close), encoding="utf-8")
    paths["replies.txt"] = str(out / "replies.txt")
    (out / "replies.txt").write_text(replies_to_txt(close), encoding="utf-8")
    return paths
