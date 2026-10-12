"""
Inventory Forecast Close — the Sunday stock-up ritual shops actually run.
========================================================================
Sellers close the day; owners stock the week. Every Sunday the owner asks:

  1. What will stock out first and kill next week's sales? (days_left + date)
  2. How much cash to cover 14 days? (reorder_qty + reorder_cost, cited)
  3. Who do I email right now? (per-supplier PO draft, copy-paste)

One call, offline, $0, deterministic (seeded), no network, no LLM:

  from omni_one.packs.forecast_close import build_forecast_close
  close = build_forecast_close(seed=42)
  # -> headline + kpis + skus[8] + po_drafts + do_today[3]

  write_close_bundle(close, "./forecast_close_2026-10-11")
  # -> close.json + close.csv + forecast.csv + po.txt (print / send / file)

Design rules (mirrors seller_close.py / revops_close.py):
- Deterministic: same (skus, seed, cover_days) -> same close (minus date stamp).
  No LLM/network/wall-clock in math. Only `date`/`stockout_date` use today.
- Every unit cites inventory: [inventory:skus#N].
- Idempotent, private, offline, $0.
- Reuses seller_close.draft_po_email for PO style (same subject/body shape).
- Formula docs (per SKU):
    days_left    = on_hand / daily_velocity  (999.0 when velocity <= 0)
    safety_stock = ceil(daily_velocity * lead_days * 0.5)
    reorder_qty  = max(0, ceil(daily_velocity * cover_days + safety_stock - on_hand))
    reorder_cost = reorder_qty * unit_cost
    stockout_date = date + floor(days_left) days
    status        = critical if days_left <= 5 else low if days_left <= cover_days else ok
"""
from __future__ import annotations

import csv
import io
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

COVER_DAYS = 14  # reorder cover: 14 days of velocity (mirrors seller_close)
STOCKOUT_DAYS = 5.0  # critical threshold in days (mirrors seller_close)

CITATIONS_NOTE = (
    "every SKU cites [inventory:skus#N]; audit via forecast.csv citation column; "
    "formulas: days_left=on_hand/velocity, safety=ceil(velocity*lead*0.5), "
    "reorder=max(0, ceil(velocity*cover+safety-on_hand))"
)

_CANONICAL_SKUS: list[dict[str, Any]] = [
    {"name": "Espresso Beans 1kg", "on_hand": 18, "daily_velocity": 6.0, "unit_cost": 12.50, "supplier": "Andes Coffee Co.", "lead_days": 7, "citation": "[inventory:skus#0]"},
    {"name": "Oat Milk 12-pack", "on_hand": 40, "daily_velocity": 4.0, "unit_cost": 18.00, "supplier": "Andes Coffee Co.", "lead_days": 5, "citation": "[inventory:skus#1]"},
    {"name": "Ceramic Mug 350ml", "on_hand": 120, "daily_velocity": 3.0, "unit_cost": 4.20, "supplier": "Kiln Works", "lead_days": 14, "citation": "[inventory:skus#2]"},
    {"name": "Cold Brew Bottles", "on_hand": 12, "daily_velocity": 5.0, "unit_cost": 3.80, "supplier": "BottlePro", "lead_days": 4, "citation": "[inventory:skus#3]"},
    {"name": "Paper Filters #4", "on_hand": 200, "daily_velocity": 8.0, "unit_cost": 0.35, "supplier": "BottlePro", "lead_days": 3, "citation": "[inventory:skus#4]"},
    {"name": "Vanilla Syrup 750ml", "on_hand": 15, "daily_velocity": 2.5, "unit_cost": 6.75, "supplier": "Syrup House", "lead_days": 10, "citation": "[inventory:skus#5]"},
    {"name": "Croissant Butter Frozen", "on_hand": 8, "daily_velocity": 7.0, "unit_cost": 1.90, "supplier": "FreshBake", "lead_days": 2, "citation": "[inventory:skus#6]"},
    {"name": "Reusable Tote", "on_hand": 60, "daily_velocity": 1.5, "unit_cost": 2.10, "supplier": "Kiln Works", "lead_days": 12, "citation": "[inventory:skus#7]"},
]


def DEMO_SKUS(seed: int = 42) -> list[dict[str, Any]]:
    """Deterministic demo SKUs (~8). seed=42 returns the canonical book exactly.

    Other seeds deterministically jitter on_hand (+/-5, clamped >= 0) so the
    generator is genuinely seeded while the golden seed never drifts.
    """
    base = [dict(s) for s in _CANONICAL_SKUS]
    if seed != 42:
        rng = random.Random(seed)
        for s in base:
            delta = rng.randint(-5, 5)
            s["on_hand"] = max(0, int(s["on_hand"]) + delta)
    return base


# snake_case alias (same callable behaviour)
demo_skus = DEMO_SKUS


def _today(date_str: str | None) -> date:
    if date_str:
        try:
            return date.fromisoformat(date_str[:10])
        except Exception:
            pass
    return datetime.now().date()


def build_forecast_close(
    skus: list[dict[str, Any]] | None = None,
    seed: int = 42,
    cover_days: int = COVER_DAYS,
    date_str: str | None = None,
    shop: str = "our shop",
) -> dict[str, Any]:
    """Build the Sunday Forecast Close. None -> DEMO_SKUS(seed). Date stamp only."""
    from omni_one.packs.seller_close import draft_po_email

    raw = list(skus) if skus is not None else DEMO_SKUS(seed)
    cover_days = int(cover_days)
    today = _today(date_str)
    day_str = today.isoformat()

    computed: list[dict[str, Any]] = []
    for i, s in enumerate(raw):
        name = str(s.get("name", f"SKU-{i}"))
        on_hand = int(s.get("on_hand", 0) or 0)
        velocity = float(s.get("daily_velocity", 0) or 0)
        unit_cost = float(s.get("unit_cost", 0) or 0)
        supplier = str(s.get("supplier", "") or "see inventory.csv supplier column")
        lead_days = int(s.get("lead_days", 0) or 0)
        citation = str(s.get("citation", f"[inventory:skus#{i}]"))
        if velocity > 0:
            days_left = on_hand / velocity
            safety_stock = math.ceil(velocity * lead_days * 0.5)
            reorder_qty = max(0, math.ceil(velocity * cover_days + safety_stock - on_hand))
        else:
            days_left = 999.0
            safety_stock = 0
            reorder_qty = 0
        if days_left <= STOCKOUT_DAYS:
            status = "critical"
        elif days_left <= cover_days:
            status = "low"
        else:
            status = "ok"
        if days_left < 900:
            stockout_date = (today + timedelta(days=int(math.floor(days_left)))).isoformat()
        else:
            stockout_date = (today + timedelta(days=999)).isoformat()
        reorder_cost = round(reorder_qty * unit_cost, 2)
        computed.append({
            "name": name,
            "on_hand": on_hand,
            "daily_velocity": velocity,
            "unit_cost": unit_cost,
            "supplier": supplier,
            "lead_days": lead_days,
            "citation": citation,
            "days_left": round(float(days_left), 2),
            "safety_stock": int(safety_stock),
            "reorder_qty": int(reorder_qty),
            "reorder_cost": reorder_cost,
            "stockout_date": stockout_date,
            "status": status,
            "cover_days": cover_days,
        })

    computed.sort(key=lambda r: (r["days_left"], -r["reorder_qty"]))

    sku_count = len(computed)
    critical = [r for r in computed if r["status"] == "critical"]
    critical_count = len(critical)
    reorder_lines = sum(1 for r in computed if r["reorder_qty"] > 0)
    reorder_cost_total = round(sum(r["reorder_cost"] for r in computed), 2)
    stockout_soon = [r["name"] for r in critical]

    # ---- PO drafts per supplier (reuse seller_close style) ----
    by_supplier: dict[str, list[dict[str, Any]]] = {}
    for r in computed:
        by_supplier.setdefault(r["supplier"], []).append(r)
    po_drafts: dict[str, str] = {}
    for supplier in sorted(by_supplier):
        rows = [r for r in by_supplier[supplier] if r["reorder_qty"] > 0]
        lines = [{
            "product": r["name"],
            "reorder_qty": r["reorder_qty"],
            "on_hand": r["on_hand"],
            "days_left": r["days_left"],
            "citation": r["citation"],
        } for r in sorted(rows, key=lambda x: x["days_left"])]
        try:
            po_drafts[supplier] = draft_po_email(supplier, lines, shop)
        except Exception:
            po_drafts[supplier] = f"Subject: Reorder request — {supplier}\n\n" + "\n".join(
                f"  - {l['product']}: {l['reorder_qty']} units" for l in lines
            )

    # ---- headline ----
    if sku_count:
        first = computed[0]
        first_days_int = int(math.floor(float(first["days_left"]))) if first["days_left"] < 900 else 999
        headline = (
            f"FORECAST CLOSE: {critical_count}/{sku_count} SKUs critical · "
            f"${reorder_cost_total:,.2f} to cover {cover_days}d · "
            f"first stockout {first['name']} in {first_days_int}d"
        )
    else:
        headline = (
            f"FORECAST CLOSE: 0/0 SKUs critical · $0.00 to cover {cover_days}d · no stockouts"
        )

    # ---- do_today[3]: each string carries $ and days ----
    do_today: list[str] = []
    if sku_count:
        first = computed[0]
        do_today.append(
            f"Order {first['name']} x{first['reorder_qty']} from {first['supplier']} "
            f"(${first['reorder_cost']:,.2f}) — only {first['days_left']:.1f}d left, "
            f"stocks out {first['stockout_date']} [{first['citation']}]"
        )
        # top supplier by reorder cost
        cost_by_sup: dict[str, float] = {}
        for sup, rows in by_supplier.items():
            cost_by_sup[sup] = round(sum(r["reorder_cost"] for r in rows if r["reorder_qty"] > 0), 2)
        reorder_sups = {k: v for k, v in cost_by_sup.items() if v > 0}
        if reorder_sups:
            top_sup = sorted(reorder_sups, key=lambda k: (-reorder_sups[k], k))[0]
            top_rows = [r for r in by_supplier[top_sup] if r["reorder_qty"] > 0]
            worst = sorted(top_rows, key=lambda r: r["days_left"])[0]
            do_today.append(
                f"Send PO to {top_sup} ({len(top_rows)} line(s), ${reorder_sups[top_sup]:,.2f}) — "
                f"covers {cover_days}d demand, worst {worst['name']} at {worst['days_left']:.1f}d left"
            )
        else:
            do_today.append(
                f"Stock healthy — no PO needed for {cover_days}d ($0.00) — recheck in 7d"
            )
        lows = [r for r in computed if r["status"] == "low"]
        if lows:
            low_names = ", ".join(r["name"] for r in lows[:2])
            low_min = min(r["days_left"] for r in lows)
            do_today.append(
                f"Cover {reorder_lines} reorder line(s) for {cover_days}d "
                f"(${reorder_cost_total:,.2f}) — next low: {low_names} from {low_min:.1f}d left"
            )
        else:
            do_today.append(
                f"Cover {reorder_lines} reorder line(s) for {cover_days}d "
                f"(${reorder_cost_total:,.2f}) — no low SKUs, watch critical restock dates"
            )
    else:
        do_today = [
            f"Stock book empty — no reorder for {cover_days}d ($0.00) — add SKUs",
            f"No suppliers to email for {cover_days}d ($0.00) — import inventory.csv",
            f"Nothing to cover for {cover_days}d ($0.00) — recheck in 7d",
        ]
    do_today = do_today[:3]

    return {
        "date": day_str,
        "headline": headline,
        "kpis": {
            "sku_count": sku_count,
            "critical_count": critical_count,
            "reorder_lines": reorder_lines,
            "reorder_cost": reorder_cost_total,
            "stockout_soon": stockout_soon,
        },
        "skus": computed,
        "po_drafts": po_drafts,
        "do_today": do_today,
        "citations": CITATIONS_NOTE,
        "free": True,
        "offline": True,
        "seed": seed,
        "cover_days": cover_days,
    }


def close_to_csv(close: dict[str, Any]) -> str:
    """Per-SKU forecast rows: sku,on_hand,velocity,days_left,safety,reorder,..."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["sku", "on_hand", "daily_velocity", "days_left", "safety_stock",
                "reorder_qty", "unit_cost", "reorder_cost", "supplier",
                "lead_days", "stockout_date", "status", "citation"])
    for r in close.get("skus", []):
        w.writerow([r.get("name", ""), r.get("on_hand", ""), r.get("daily_velocity", ""),
                    r.get("days_left", ""), r.get("safety_stock", ""), r.get("reorder_qty", ""),
                    r.get("unit_cost", ""), r.get("reorder_cost", ""), r.get("supplier", ""),
                    r.get("lead_days", ""), r.get("stockout_date", ""), r.get("status", ""),
                    r.get("citation", "")])
    return buf.getvalue()


def forecast_to_csv(close: dict[str, Any]) -> str:
    """Alias: forecast sheet is the per-SKU close sheet."""
    return close_to_csv(close)


def po_to_txt(close: dict[str, Any]) -> str:
    """Combined PO file: per-supplier drafts separated by rules."""
    k = close.get("kpis", {}) or {}
    out = [
        f"FORECAST CLOSE {close.get('date', '')} — PURCHASE ORDERS",
        f"{close.get('headline', '')}",
        f"Lines: {k.get('reorder_lines', 0)} · Cost: ${k.get('reorder_cost', 0):,.2f}",
        "=" * 64,
        "",
    ]
    drafts = close.get("po_drafts", {}) or {}
    if not drafts:
        out.append("(no suppliers — book empty)")
    for supplier in sorted(drafts):
        out += [f"--- PO: {supplier} ---", drafts[supplier], ""]
    out += [str(close.get("citations", "")), "free: true · offline: true"]
    return "\n".join(out)


def write_close_bundle(close: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + forecast.csv + po.txt. Returns paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(json.dumps(close, indent=2, default=str))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close))
    paths["forecast.csv"] = str(out / "forecast.csv")
    (out / "forecast.csv").write_text(forecast_to_csv(close))
    paths["po.txt"] = str(out / "po.txt")
    (out / "po.txt").write_text(po_to_txt(close))
    return paths


__all__ = [
    "COVER_DAYS",
    "STOCKOUT_DAYS",
    "CITATIONS_NOTE",
    "DEMO_SKUS",
    "demo_skus",
    "build_forecast_close",
    "close_to_csv",
    "forecast_to_csv",
    "po_to_txt",
    "write_close_bundle",
]
