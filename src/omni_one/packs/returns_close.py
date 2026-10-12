"""
Returns & Refunds Close — the weekly money-leak ritual refund teams actually run.
===============================================================================
Sellers close the day; support closes the week. Every Monday the ops lead asks
three questions:

  1. How much did refunds bleed this week? (refund total + count + rate, cited)
  2. Which reason leaks the most dollars, and what restocks today?
     (reason breakdown + restock sheet with cited actions)
  3. What do we copy-paste to customers RIGHT NOW? (grounded reply drafts)

One call, offline, $0, deterministic (seeded), no network, no LLM:

  from omni_one.packs.returns_close import build_returns_close
  close = build_returns_close(seed=42)
  # -> headline + kpis + reason_breakdown + restock_sheet + drafts[3]
  #    + do_today[3] + prevented_today[2]

  write_close_bundle(close, "./returns_close_2026-10-11")
  # -> close.json + close.csv + returns.csv + drafts.txt (print / send / file)

Design rules (mirrors revops_close.py / micro_close.py):
- Deterministic: same (records, seed) -> same close (minus date stamp).
  No LLM/network/wall-clock in math. Only `date` uses today, never scoring.
- Every dollar cites a signal: [shopify:orders#N] per return record.
- Idempotent, private, offline, $0.
- Refund rate is returns vs assumed sales (ASSUMED_SALES = 60 / week).
- Restockable = resellable as-new: changed_mind / wrong_item always;
  late only when days_since_purchase <= 14; damaged / quality never.

Record schema (from DEMO_RETURNS): order_id, product, reason
(damaged|late|wrong_item|changed_mind|quality), amount, days_since_purchase,
restockable bool, citation like "[shopify:orders#1001]".

Reason math: group by reason -> {count, amount_usd}; top_reason = max
amount_usd (ties broken alphabetically for determinism).
Restock math: restock_value = sum(amount where restockable);
restock_sheet = restockable rows sorted amount desc with inspect+relist action.
Drafts: top-3 refunds by amount, each a template with apology +
reship/refund choice + verbatim citation.
do_today[3]: concrete actions each carrying a $ amount.
prevented_today[2]: template guardrails that stop next week's leak.
"""
from __future__ import annotations

import csv
import io
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ASSUMED_SALES = 60  # assumed orders / week; refund_rate = count / 60 * 100

REASONS = ("damaged", "late", "wrong_item", "changed_mind", "quality")

_PRODUCTS = [
    "Aero Hoodie",
    "Trail Sneakers",
    "Canvas Tote",
    "Wool Socks",
    "Denim Jacket",
    "Ceramic Mug",
    "Yoga Mat",
    "Leather Wallet",
    "Linen Shirt",
    "Steel Bottle",
    "Cotton Cap",
    "Silk Scarf",
]

CITATIONS_NOTE = (
    "every dollar cites a return: [shopify:orders#N] per record; "
    "audit via returns.csv citation column"
)

__all__ = [
    "ASSUMED_SALES",
    "REASONS",
    "DEMO_RETURNS",
    "demo_returns",
    "build_returns_close",
    "close_to_csv",
    "returns_to_csv",
    "drafts_to_txt",
    "write_close_bundle",
]


# ---------------------------------------------------------------------------
# Demo generator — deterministic seeded records
# ---------------------------------------------------------------------------

def DEMO_RETURNS(seed: int = 42) -> list[dict[str, Any]]:
    """Deterministic list of ~12 return/refund records for the given seed."""
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    for i in range(12):
        product = rng.choice(_PRODUCTS)
        reason = rng.choice(REASONS)
        amount = round(rng.uniform(19.99, 189.99), 2)
        days = rng.randint(1, 30)
        if reason in ("changed_mind", "wrong_item"):
            restockable = True
        elif reason == "late" and days <= 14:
            restockable = True
        else:
            restockable = False
        order_id = f"#{1001 + i}"
        citation = f"[shopify:orders#{1001 + i}]"
        records.append(
            {
                "order_id": order_id,
                "product": product,
                "reason": reason,
                "amount": amount,
                "days_since_purchase": days,
                "restockable": restockable,
                "citation": citation,
            }
        )
    return records


# lowercase alias (same function, same determinism)
def demo_returns(seed: int = 42) -> list[dict[str, Any]]:
    """Lowercase alias for DEMO_RETURNS (same seeded demo)."""
    return DEMO_RETURNS(seed=seed)


def _restock_action(rec: dict[str, Any]) -> str:
    return (
        f"Inspect {rec['product']} ({rec['order_id']}) + relist in 24h "
        f"— ${float(rec['amount']):,.2f} recoverable {rec['citation']}"
    )


def _draft_for(rec: dict[str, Any]) -> str:
    amount = float(rec.get("amount", 0) or 0)
    return (
        f"Hi there — sorry your {rec.get('product', 'item')} "
        f"({rec.get('order_id', '')}) arrived {rec.get('reason', 'with an issue')} "
        f"({rec.get('citation', '')}). Quick fix, your choice: "
        f"reply RESHIP for a free replacement in 2 days, or REFUND for "
        f"${amount:,.2f} back in 3-5 days. We will confirm within 2 hours. — Support"
    )


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_returns_close(
    records: list[dict[str, Any]] | None = None,
    seed: int = 42,
    date_str: str | None = None,
) -> dict[str, Any]:
    """Build the weekly Returns & Refunds Close.

    Args:
        records: explicit return records (same keys as DEMO_RETURNS).
            When None, the seeded demo generator is used.
        seed: seed for the demo generator (ignored when records given).
        date_str: YYYY-MM-DD label. Defaults to today. Excluded from every
            idempotency comparison except the `date` field itself.

    Returns:
        dict with date, headline, kpis, reason_breakdown, restock_sheet,
        drafts, do_today, prevented_today, records, citations, free, offline,
        seed.
    """
    recs: list[dict[str, Any]] = (
        DEMO_RETURNS(seed=seed) if records is None else list(records)
    )

    refund_count = len(recs)
    refund_total = round(sum(float(r.get("amount", 0) or 0) for r in recs), 2)
    refund_rate = (
        round(refund_count / ASSUMED_SALES * 100, 1) if ASSUMED_SALES else 0.0
    )
    avg_refund = round(refund_total / refund_count, 2) if refund_count else 0.0

    # reason breakdown: reason -> {count, amount_usd}, sorted amount desc
    grouped: dict[str, dict[str, Any]] = {}
    for r in recs:
        reason = str(r.get("reason", "unknown") or "unknown")
        entry = grouped.setdefault(reason, {"count": 0, "amount_usd": 0.0})
        entry["count"] += 1
        entry["amount_usd"] = round(
            float(entry["amount_usd"]) + float(r.get("amount", 0) or 0), 2
        )
    reason_breakdown: dict[str, dict[str, Any]] = dict(
        sorted(
            grouped.items(),
            key=lambda kv: (-float(kv[1]["amount_usd"]), kv[0]),
        )
    )

    if reason_breakdown:
        top_reason = next(iter(reason_breakdown))
        top_reason_usd = float(reason_breakdown[top_reason]["amount_usd"])
        top_reason_count = int(reason_breakdown[top_reason]["count"])
    else:
        top_reason = "none"
        top_reason_usd = 0.0
        top_reason_count = 0

    restock_rows = [r for r in recs if bool(r.get("restockable"))]
    restock_value = round(
        sum(float(r.get("amount", 0) or 0) for r in restock_rows), 2
    )
    restock_count = len(restock_rows)
    restock_sorted = sorted(
        restock_rows, key=lambda r: (-float(r.get("amount", 0) or 0), str(r.get("order_id", "")))
    )
    restock_sheet: list[dict[str, Any]] = [
        {
            "order_id": r.get("order_id", ""),
            "product": r.get("product", ""),
            "reason": r.get("reason", ""),
            "amount": float(r.get("amount", 0) or 0),
            "citation": r.get("citation", ""),
            "action": _restock_action(r),
        }
        for r in restock_sorted
    ]

    # drafts: top-3 refunds by amount (or fewer when fewer records)
    by_amount = sorted(
        recs, key=lambda r: (-float(r.get("amount", 0) or 0), str(r.get("order_id", "")))
    )
    top3 = by_amount[:3]
    drafts: list[dict[str, Any]] = [
        {
            "order_id": r.get("order_id", ""),
            "product": r.get("product", ""),
            "reason": r.get("reason", ""),
            "amount": float(r.get("amount", 0) or 0),
            "citation": r.get("citation", ""),
            "draft": _draft_for(r),
        }
        for r in top3
    ]

    top3_sum = round(sum(float(r.get("amount", 0) or 0) for r in top3), 2)

    # prevented_today: 2 template guardrails
    if refund_count:
        prevented_today = [
            f"Add {top_reason} guardrail: photo QC + packing checklist before ship "
            f"— prevents ~${top_reason_usd * 0.25:,.2f}/wk of {top_reason} refunds",
            f"Relist {restock_count} restockable item(s) = ${restock_value:,.2f} "
            f"back on shelf today — inspect + relist in 24h",
        ]
    else:
        prevented_today = [
            "No returns this week — keep photo QC + packing checklist in place",
            "No restock queue — shelf is clean, confirm listing counts",
        ]
    prevented_usd = round(top_reason_usd * 0.25 + restock_value * 0.5, 2) if refund_count else 0.0

    # do_today: exactly 3 concrete strings, each with a $ amount
    if refund_count:
        top_cite = str(by_amount[0].get("citation", "")) if by_amount else ""
        top_product = str(by_amount[0].get("product", "")) if by_amount else ""
        if restock_sheet:
            head = restock_sheet[0]
            do_restock = (
                f"Restock ${restock_value:,.2f} today: inspect + relist "
                f"{restock_count} item(s), starting with {head['product']} "
                f"({head['order_id']}) ${float(head['amount']):,.2f} {head['citation']}"
            )
        else:
            do_restock = (
                f"Restock $0.00 today: nothing resellable — write off "
                f"${refund_total:,.2f} and review QC {top_cite}"
            )
        do_fix = (
            f"Fix top leak {top_reason}: audit {top_reason_count} order(s) = "
            f"${top_reason_usd:,.2f} — add photo QC + size guide this week {top_cite}"
        )
        do_reply = (
            f"Reply to {len(top3)} refund(s) totalling ${top3_sum:,.2f}: send drafts "
            f"below, starting with {top_product} {top_cite} (reship/refund choice)"
        )
        do_today = [do_restock, do_fix, do_reply]
    else:
        do_today = [
            "Restock $0.00 today: no returns — confirm shelf counts",
            "Fix top leak none: $0.00 — keep photo QC checklist posted",
            "Reply to 0 refund(s) totalling $0.00: inbox is clean — log today's ships",
        ]

    headline = (
        f"RETURNS CLOSE: ${refund_total:,.2f} refunded in {refund_count} return(s) "
        f"· top leak {top_reason} ${top_reason_usd:,.2f} "
        f"· ${restock_value:,.2f} restockable today"
    )

    citations: list[str] = [str(r.get("citation", "")) for r in recs if r.get("citation")]

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "headline": headline,
        "kpis": {
            "refund_total": refund_total,
            "refund_count": refund_count,
            "refund_rate_pct": refund_rate,
            "assumed_sales": ASSUMED_SALES,
            "avg_refund": avg_refund,
            "top_reason": top_reason,
            "top_reason_usd": top_reason_usd,
            "top_reason_count": top_reason_count,
            "restock_value": restock_value,
            "restock_count": restock_count,
            "top3_sum": top3_sum,
            "prevented_today_usd": prevented_usd,
        },
        "reason_breakdown": reason_breakdown,
        "restock_sheet": restock_sheet,
        "drafts": drafts,
        "do_today": do_today,
        "prevented_today": prevented_today,
        "records": recs,
        "citations": citations,
        "citations_note": CITATIONS_NOTE,
        "free": True,
        "offline": True,
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------

def close_to_csv(close: dict[str, Any]) -> str:
    """Render reason_breakdown as CSV (one row per reason, amount desc)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["reason", "count", "amount_usd"])
    breakdown = close.get("reason_breakdown", {}) or {}
    for reason, vals in breakdown.items():
        vals = vals or {}
        w.writerow([reason, vals.get("count", 0), vals.get("amount_usd", 0.0)])
    return buf.getvalue()


def returns_to_csv(close: dict[str, Any]) -> str:
    """Render record-level returns as CSV (one row per return)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(
        ["order_id", "product", "reason", "amount", "days_since_purchase", "restockable", "citation"]
    )
    for r in close.get("records", []) or []:
        w.writerow(
            [
                r.get("order_id", ""),
                r.get("product", ""),
                r.get("reason", ""),
                r.get("amount", ""),
                r.get("days_since_purchase", ""),
                r.get("restockable", ""),
                r.get("citation", ""),
            ]
        )
    return buf.getvalue()


def drafts_to_txt(close: dict[str, Any]) -> str:
    """Render copy-paste drafts + actions as text (phone / inbox screen)."""
    k = close.get("kpis", {}) or {}
    out = [
        f"RETURNS CLOSE {close.get('date', '')} — REPLY QUEUE "
        f"(${float(k.get('refund_total', 0)):,.2f} refunded)",
        f"{close.get('headline', '')}",
        "=" * 72,
        "",
        "DO TODAY:",
    ]
    for i, t in enumerate(close.get("do_today", []), 1):
        out.append(f"  [{i}] {t}")
    out += ["", "-" * 72, "COPY-PASTE DRAFTS (reship/refund choice, cited):", "-" * 72, ""]
    drafts = close.get("drafts", []) or []
    if not drafts:
        out.append("(no refunds — inbox is clean)")
        out.append("")
    for i, d in enumerate(drafts, 1):
        out += [
            f"[{i}] {d.get('product', '')} ({d.get('order_id', '')}) — "
            f"${float(d.get('amount', 0)):,.2f} — {d.get('reason', '')}",
            f"    evidence: {d.get('citation', '')}",
            f"    COPY-PASTE DRAFT: {d.get('draft', '')}",
            "",
        ]
    out += ["-" * 72, "PREVENTED TODAY (guardrails):", "-" * 72]
    for p in close.get("prevented_today", []) or []:
        out.append(f"  - {p}")
    out += ["", str(close.get("citations_note", "")), "free: true · offline: true"]
    return "\n".join(out)


def write_close_bundle(close: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + returns.csv + drafts.txt. Returns paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(json.dumps(close, indent=2, default=str))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close))
    paths["returns.csv"] = str(out / "returns.csv")
    (out / "returns.csv").write_text(returns_to_csv(close))
    paths["drafts.txt"] = str(out / "drafts.txt")
    (out / "drafts.txt").write_text(drafts_to_txt(close))
    return paths
