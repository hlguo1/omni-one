"""
Multi-Shop Rollup Close — the portfolio-owner Sunday ritual (flagship pack).
==============================================================================
One owner, four shops, one page. Every Sunday night the portfolio owner asks
three questions:

  1. Did the portfolio actually make money? (blended profit + margin, cited)
  2. Which shop carries the week and which one drags it? (ranked sheet)
  3. What three moves fix the most dollars before Monday? (cross-shop plays)

One call, offline, $0, deterministic (seeded), no network, no LLM:

  from omni_one.packs.rollup_close import build_rollup_close
  close = build_rollup_close(seed=42)
  # -> headline + kpis + shops[4 ranked] + plays[3] + do_today[3]

  write_close_bundle(close, "./rollup_close_2026-10-12")
  # -> close.json + close.csv + shops.csv + actions.txt (print / send / file)

Design rules (mirrors revops_close.py, micro_close.py):
- Deterministic: same (shops, seed) -> same close (minus date stamp).
  No LLM/network/wall-clock in math. Only `date` uses today, never scoring.
- Every dollar cites a shop: [<channel>:shop:<name>].
- Idempotent, private, offline, $0.
- Profit math is exact integers: profit = gmv - fees - ship_cost - cogs;
  margin_pct = profit / gmv * 100 (rounded to 1 decimal in display,
  2 decimals stored per row); blended = total_profit / total_gmv * 100.

Shop schema (DEMO_SHOPS output, also the explicit-input contract):
  name, channel, gmv, fees, ship_cost, cogs, orders, stockout_count,
  angry_count. Enriched rows add: profit, margin_pct, citation, rank.

Play assignment (exactly 3, fixed order):
  1. FEE-AUDIT  -> worst margin_pct shop (fees eat the take).
  2. REPLY-SPRINT -> highest angry_count shop (reviews kill next week).
     Tie-break: lower profit first, then name asc (deterministic).
  3. PO-SPRINT   -> highest stockout_count shop (empty shelf = lost GMV).
     Tie-break: lower profit first, then name asc (deterministic).
  A shop may own two plays; plays always reference real shop names.

Golden demo (seed=42) — asserted in tests, do not drift:
  computed at runtime; headline/kpis hardcoded in
  tests/unit/test_rollup_close.py. Regenerate via:
    PYTHONPATH=src python3 -c "
      from omni_one.packs.rollup_close import build_rollup_close;
      c = build_rollup_close(seed=42, date_str='2026-10-12');
      print(c['headline']); print(c['kpis'])"
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
# Constants — the four demo shops (fixed identities, seeded numbers)
# ---------------------------------------------------------------------------

# Fixed (name, channel) pairs: identities never change, only numbers reseed.
_DEMO_IDENTITIES: list[tuple[str, str]] = [
    ("Harbor Goods", "shopify"),
    ("Pixel Pantry", "amazon"),
    ("Northwind Home", "etsy"),
    ("Velvet Vinyl", "tiktok"),
]

DO_TODAY_N = 3

CITATIONS_NOTE = (
    "every dollar cites a shop: [<channel>:shop:<name>]; "
    "audit via shops.csv citation column; profit = gmv - fees - ship_cost - cogs"
)

__all__ = [
    "DEMO_SHOPS",
    "demo_shops",
    "CITATIONS_NOTE",
    "build_rollup_close",
    "close_to_csv",
    "actions_to_txt",
    "write_close_bundle",
]


# ---------------------------------------------------------------------------
# Demo generator — deterministic 4 shops
# ---------------------------------------------------------------------------

def DEMO_SHOPS(seed: int = 42) -> list[dict[str, Any]]:
    """Deterministic 4-shop demo book. Same seed -> same shops, always."""
    rng = random.Random(seed)
    shops: list[dict[str, Any]] = []
    for name, channel in _DEMO_IDENTITIES:
        gmv = rng.randint(8000, 30000)
        fees = int(gmv * rng.uniform(0.08, 0.18))
        ship_cost = rng.randint(800, 3500)
        cogs = int(gmv * rng.uniform(0.35, 0.55))
        orders = rng.randint(150, 900)
        stockout_count = rng.randint(0, 6)
        angry_count = rng.randint(0, 9)
        shops.append({
            "name": name,
            "channel": channel,
            "gmv": gmv,
            "fees": fees,
            "ship_cost": ship_cost,
            "cogs": cogs,
            "orders": orders,
            "stockout_count": stockout_count,
            "angry_count": angry_count,
        })
    return shops


# Lowercase alias (same object contract, friendlier import).
def demo_shops(seed: int = 42) -> list[dict[str, Any]]:
    """Alias of DEMO_SHOPS (same deterministic book)."""
    return DEMO_SHOPS(seed=seed)


def _citation_for(shop: dict[str, Any]) -> str:
    return f"[{shop.get('channel', '?')}:shop:{shop.get('name', '?')}]"


def _enrich(shop: dict[str, Any]) -> dict[str, Any]:
    """Add profit + margin_pct + citation (pure math, no I/O)."""
    gmv = int(shop.get("gmv", 0) or 0)
    fees = int(shop.get("fees", 0) or 0)
    ship = int(shop.get("ship_cost", 0) or 0)
    cogs = int(shop.get("cogs", 0) or 0)
    profit = gmv - fees - ship - cogs
    margin = round(profit / gmv * 100.0, 2) if gmv else 0.0
    return {
        "name": str(shop.get("name", "")),
        "channel": str(shop.get("channel", "")),
        "gmv": gmv,
        "fees": fees,
        "ship_cost": ship,
        "cogs": cogs,
        "orders": int(shop.get("orders", 0) or 0),
        "stockout_count": int(shop.get("stockout_count", 0) or 0),
        "angry_count": int(shop.get("angry_count", 0) or 0),
        "profit": profit,
        "margin_pct": margin,
        "citation": _citation_for(shop),
    }


# ---------------------------------------------------------------------------
# Main builder — shops -> portfolio close
# ---------------------------------------------------------------------------

def build_rollup_close(
    shops: list[dict[str, Any]] | None = None,
    seed: int = 42,
    date_str: str | None = None,
) -> dict[str, Any]:
    """Build the Sunday Rollup Close. None -> DEMO_SHOPS(seed). Date stamp only.

    Returns dict with date, headline, kpis, shops (profit desc, ranked),
    plays (3 cross-shop), do_today (3), citations, free, offline, seed.
    Deterministic, no LLM/network. $0 offline.
    """
    raw = list(shops) if shops is not None else DEMO_SHOPS(seed=seed)
    enriched = [_enrich(s) for s in raw]
    enriched.sort(key=lambda r: (-r["profit"], r["name"]))
    for i, row in enumerate(enriched, 1):
        row["rank"] = i

    total_gmv = sum(r["gmv"] for r in enriched)
    total_profit = sum(r["profit"] for r in enriched)
    total_orders = sum(r["orders"] for r in enriched)
    total_stockouts = sum(r["stockout_count"] for r in enriched)
    total_angry = sum(r["angry_count"] for r in enriched)
    blended = round(total_profit / total_gmv * 100.0, 1) if total_gmv else 0.0

    n = len(enriched)
    best = enriched[0] if enriched else None
    worst = enriched[-1] if enriched else None
    best_name = best["name"] if best else "—"
    worst_name = worst["name"] if worst else "—"

    # Cross-shop plays (fixed order, deterministic tie-breaks).
    plays: list[dict[str, Any]] = []
    if enriched:
        worst_margin = min(enriched, key=lambda r: (r["margin_pct"], -r["profit"], r["name"]))
        # Highest angry / stockout leaders; ties break to lower profit then name.
        angry_sorted = sorted(enriched, key=lambda r: (-r["angry_count"], r["profit"], r["name"]))
        angry_top = angry_sorted[0]
        stock_sorted = sorted(enriched, key=lambda r: (-r["stockout_count"], r["profit"], r["name"]))
        stock_top = stock_sorted[0]
        plays = [
            {
                "play_id": "FEE-AUDIT",
                "play": "Fee Audit",
                "shop": worst_margin["name"],
                "channel": worst_margin["channel"],
                "reason": (
                    f"Thinnest margin {worst_margin['margin_pct']:.2f}% "
                    f"(${worst_margin['profit']:,} on ${worst_margin['gmv']:,} GMV)"
                ),
                "evidence": worst_margin["citation"],
                "citation": worst_margin["citation"],
                "next_step": (
                    f"Pull the {worst_margin['channel']} fee schedule for "
                    f"{worst_margin['name']} and dispute one fee class Monday"
                ),
            },
            {
                "play_id": "REPLY-SPRINT",
                "play": "Reply Sprint",
                "shop": angry_top["name"],
                "channel": angry_top["channel"],
                "reason": f"{angry_top['angry_count']} angry message(s) open",
                "evidence": angry_top["citation"],
                "citation": angry_top["citation"],
                "next_step": (
                    f"Reply to every angry thread at {angry_top['name']} "
                    f"inside 2 hours with refund-or-reship choice"
                ),
            },
            {
                "play_id": "PO-SPRINT",
                "play": "PO Sprint",
                "shop": stock_top["name"],
                "channel": stock_top["channel"],
                "reason": f"{stock_top['stockout_count']} stockout(s) killing GMV",
                "evidence": stock_top["citation"],
                "citation": stock_top["citation"],
                "next_step": (
                    f"Raise the PO for {stock_top['name']} Monday AM "
                    f"covering 14 days of velocity"
                ),
            },
        ]

    # do_today: exactly 3 strings, each names a shop and carries a $ amount.
    do_today: list[str] = []
    if enriched:
        wm = plays[0]
        wm_row = next(r for r in enriched if r["name"] == wm["shop"])
        do_today.append(
            f"Audit fees at {wm['shop']} — {wm_row['margin_pct']:.2f}% margin, "
            f"${wm_row['profit']:,} profit on ${wm_row['gmv']:,} GMV "
            f"{wm_row['citation']} -> dispute one fee class Monday"
        )
        at = plays[1]
        at_row = next(r for r in enriched if r["name"] == at["shop"])
        do_today.append(
            f"Reply sprint at {at['shop']} — {at_row['angry_count']} angry open, "
            f"${at_row['gmv']:,} GMV at stake {at_row['citation']} -> "
            f"answer every thread inside 2h"
        )
        st = plays[2]
        st_row = next(r for r in enriched if r["name"] == st["shop"])
        do_today.append(
            f"PO sprint at {st['shop']} — {st_row['stockout_count']} stockout(s), "
            f"${st_row['gmv']:,} GMV shelf {st_row['citation']} -> raise the PO Monday AM"
        )
    do_today = do_today[:DO_TODAY_N]
    while len(do_today) < DO_TODAY_N:
        do_today.append("Book clear — review the ranked sheet and confirm Monday POs.")

    if n:
        headline = (
            f"ROLLUP CLOSE: {n} shops · ${total_gmv:,} GMV · "
            f"${total_profit:,} profit ({blended:.1f}%) · "
            f"★ {best_name} / ⚠ {worst_name}"
        )
    else:
        headline = "ROLLUP CLOSE: 0 shops · $0 GMV · $0 profit (0.0%) · no shops yet"

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "seed": seed,
        "headline": headline,
        "kpis": {
            "shops": n,
            "gmv": total_gmv,
            "profit": total_profit,
            "blended_margin_pct": blended,
            "best_shop": best_name,
            "worst_shop": worst_name,
            "orders": total_orders,
            "stockouts": total_stockouts,
            "angry": total_angry,
        },
        "shops": enriched,
        "plays": plays,
        "do_today": do_today,
        "citations": CITATIONS_NOTE,
        "free": True,
        "offline": True,
    }


# ---------------------------------------------------------------------------
# Exporters — CSV + actions text (mirror flagship shapes)
# ---------------------------------------------------------------------------

def close_to_csv(close: dict[str, Any]) -> str:
    """Render the close as CSV (one row per shop, profit-desc rank order)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([
        "rank", "shop", "channel", "gmv", "fees", "ship_cost", "cogs",
        "profit", "margin_pct", "orders", "stockout_count", "angry_count",
        "citation",
    ])
    for r in close.get("shops", []):
        w.writerow([
            r.get("rank", ""),
            r.get("name", ""),
            r.get("channel", ""),
            r.get("gmv", ""),
            r.get("fees", ""),
            r.get("ship_cost", ""),
            r.get("cogs", ""),
            r.get("profit", ""),
            r.get("margin_pct", ""),
            r.get("orders", ""),
            r.get("stockout_count", ""),
            r.get("angry_count", ""),
            r.get("citation", ""),
        ])
    return buf.getvalue()


def actions_to_txt(close: dict[str, Any]) -> str:
    """Render the Sunday action sheet (print / send / file)."""
    k = close.get("kpis", {}) or {}
    out = [
        f"ROLLUP CLOSE {close.get('date', '')} — SUNDAY SHEET",
        f"{close.get('headline', '')}",
        "=" * 72,
        "",
        f"Portfolio: {k.get('shops', 0)} shops · ${k.get('gmv', 0):,} GMV · "
        f"${k.get('profit', 0):,} profit ({k.get('blended_margin_pct', 0)}%) · "
        f"{k.get('orders', 0)} orders",
        "",
        "DO TODAY (in this order):",
    ]
    for i, t in enumerate(close.get("do_today", []), 1):
        out.append(f"  [{i}] {t}")
    out += ["", "-" * 72, "CROSS-SHOP PLAYS:", "-" * 72, ""]
    for p in close.get("plays", []) or []:
        out.append(
            f"  - {p.get('play', '')} [{p.get('play_id', '')}] @ {p.get('shop', '')}: "
            f"{p.get('reason', '')} {p.get('evidence', '')} -> {p.get('next_step', '')}"
        )
    out += ["", "-" * 72, "RANKED SHOPS:", "-" * 72, ""]
    for r in close.get("shops", []) or []:
        out.append(
            f"  #{r.get('rank', '')} {r.get('name', '')} [{r.get('channel', '')}]: "
            f"${r.get('profit', 0):,} profit ({r.get('margin_pct', 0)}%) on "
            f"${r.get('gmv', 0):,} GMV {r.get('citation', '')}"
        )
    out += ["", str(close.get("citations", "")), "free: true · offline: true"]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Bundle writer: 4 files
# ---------------------------------------------------------------------------

def write_close_bundle(close: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + shops.csv + actions.txt. Returns paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(json.dumps(close, indent=2, default=str))
    per_shop = close_to_csv(close)
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(per_shop)
    paths["shops.csv"] = str(out / "shops.csv")
    (out / "shops.csv").write_text(per_shop)
    paths["actions.txt"] = str(out / "actions.txt")
    (out / "actions.txt").write_text(actions_to_txt(close))
    return paths
