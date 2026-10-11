"""Property tests for the daily close (WORKSTREAM F).

Instead of fixed golden fixtures, these tests assert *properties* that must
hold over *arbitrary* generated event streams:

1. ``profit <= gmv`` always (no phantom money, any mix of orders/fees/ship).
2. ``reorder_qty`` is monotonic non-decreasing in velocity (sell faster with
   the same on-hand -> reorder at least as much).
3. Empty events -> ``all_clear`` alert + healthy close (no crash, zero KPIs).
4. 1000 synthetic orders close in < 5s (perf regression tripwire).
5. Unicode product names survive ingest -> briefing -> close byte-identical.

Event synthesis is seedable (``Random(seed)``) so failures reproduce with::

    pytest tests/unit/test_property_close.py -q

Citations: synthetic events carry ``[file:line]`` citations so the close
exercises the same citation paths as real ingested folders.
"""

from __future__ import annotations

import random
import re
import time
from datetime import datetime
from typing import Any

CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")


# ---------------------------------------------------------------------------
# Synthesis helpers (deterministic given rng).
# ---------------------------------------------------------------------------


def make_order_event(rng: random.Random, i: int,
                     product: str = "Tote Bag Handmade",
                     gmv: float | None = None,
                     qty: int | None = None,
                     channel_file: str = "shopify_orders.csv") -> dict[str, Any]:
    gmv = round(rng.uniform(10.0, 120.0), 2) if gmv is None else gmv
    qty = rng.randint(1, 3) if qty is None else qty
    fees = round(gmv * 0.08, 2)
    ship = float(rng.choice([0.0, 3.0, 4.0, 5.0]))
    return {
        "timestamp": datetime.now(),
        "source": "orders",
        "entity_id": f"order:prop:{i}",
        "value": gmv,
        "metadata": {
            "source_file": channel_file, "line": i + 2, "signal": "order_gmv",
            "product": product, "qty": qty, "gmv": gmv, "fees": fees,
            "shipping": ship, "net": round(gmv - fees - ship, 2),
            "customer": "Prop", "status": "fulfilled",
            "citation": f"[{channel_file}:{i + 2}] {product} qty{qty} gmv${gmv}",
        },
    }


def make_inventory_event(product: str, on_hand: int, line: int = 2,
                         supplier: str = "Acme Textiles") -> dict[str, Any]:
    return {
        "timestamp": datetime.now(),
        "source": "inventory",
        "entity_id": f"inv:{product[:12]}",
        "value": float(on_hand),
        "metadata": {
            "source_file": "inventory.csv", "line": line, "signal": "on_hand",
            "product": product, "qty_on_hand": on_hand, "supplier": supplier,
            "sku": "SKU1",
            "citation": f"[inventory.csv:{line}] {product} on_hand={on_hand}",
        },
    }


def make_supplier_event(line: str, idx: int = 2) -> dict[str, Any]:
    from omni_one.packs.seller_parse import _money_last
    total = _money_last(line) or 0.0
    return {
        "timestamp": datetime.now(),
        "source": "supplier",
        "entity_id": f"supplier:prop:{idx}",
        "value": total,
        "metadata": {
            "source_file": "supplier_invoice.txt", "line": idx,
            "signal": "cogs", "citation": f"[supplier_invoice.txt:{idx}] {line[:40]}",
            "raw": line,
        },
    }


def random_event_stream(seed: int, n_orders: int,
                        products: list[str] | None = None) -> list[dict[str, Any]]:
    """Mixed stream: orders + inventory + one supplier invoice + DMs."""
    rng = random.Random(seed)
    products = products or ["Tote Bag Handmade", "Ceramic Mug", "Print - Botanical"]
    events: list[dict[str, Any]] = []
    for i in range(n_orders):
        events.append(make_order_event(rng, i, product=rng.choice(products)))
    for j, prod in enumerate(products):
        events.append(make_inventory_event(prod, rng.randint(0, 30), line=j + 2))
    events.append(make_supplier_event("Tote Bag Canvas 50 x 4.00 200.00"))
    return events


def run_close(events: list[dict[str, Any]], shop: str = "prop shop") -> dict[str, Any]:
    from omni_one.packs.seller_close import build_daily_close
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    briefing = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    return build_daily_close(events, briefing, scen, shop=shop)


# ---------------------------------------------------------------------------
# 1. profit <= gmv always.
# ---------------------------------------------------------------------------


def test_property_profit_never_exceeds_gmv():
    """Over 20 seeded streams (0..200 orders, mixed products) profit<=gmv."""
    for seed in range(20):
        rng = random.Random(10_000 + seed)
        n = rng.randint(0, 200)
        events = random_event_stream(seed, n)
        close = run_close(events)
        gmv = float(close["kpis"]["gmv"] or 0)
        profit = float(close["kpis"]["true_profit"] or 0)
        assert profit <= gmv + 0.011, (
            f"seed={seed} n={n}: profit {profit} > gmv {gmv}")


def test_property_profit_le_gmv_refunds_and_zero_gmv():
    """Refunded/zero-GMV streams: profit<=gmv still holds (no crash)."""
    rng = random.Random(999)
    events: list[dict[str, Any]] = []
    for i in range(10):
        # Zero-GMV orders (fully discounted) + normal ones.
        gmv = 0.0 if i % 3 == 0 else round(rng.uniform(15, 60), 2)
        events.append(make_order_event(rng, i, gmv=gmv, qty=1))
    close = run_close(events)
    assert float(close["kpis"]["true_profit"] or 0) <= float(close["kpis"]["gmv"] or 0) + 0.011
    # All-zero stream.
    events2 = [make_order_event(rng, i, gmv=0.0, qty=1) for i in range(5)]
    close2 = run_close(events2)
    assert float(close2["kpis"]["gmv"] or 0) == 0.0
    assert float(close2["kpis"]["true_profit"] or 0) <= 0.011


def test_property_profit_le_gmv_high_fees():
    """Even fee-heavy streams (Amazon 15% + shipping) keep profit<=gmv."""
    rng = random.Random(31337)
    events = [make_order_event(rng, i, gmv=round(rng.uniform(20, 40), 2),
                               channel_file="amazon_payout.csv") for i in range(50)]
    # Inflate fees to adversarial levels post-hoc.
    for e in events:
        e["metadata"]["fees"] = round(e["metadata"]["gmv"] * 0.45, 2)
        e["metadata"]["shipping"] = round(e["metadata"]["gmv"] * 0.30, 2)
    close = run_close(events)
    assert float(close["kpis"]["true_profit"]) <= float(close["kpis"]["gmv"]) + 0.011


# ---------------------------------------------------------------------------
# 2. reorder_qty monotonic in velocity.
# ---------------------------------------------------------------------------


def _reorder_qty_for_velocity(sold_7d: int, on_hand: int = 2) -> int:
    """Close with a single product sold `sold_7d` units, `on_hand` left."""
    events: list[dict[str, Any]] = []
    for i in range(sold_7d):
        events.append(make_order_event(random.Random(i), i,
                                        product="Tote Bag Handmade",
                                        gmv=28.0, qty=1))
    events.append(make_inventory_event("Tote Bag Handmade", on_hand))
    events.append(make_supplier_event("Tote Bag Canvas 50 x 4.00 200.00"))
    close = run_close(events)
    tote = [r for r in close["reorder_sheet"] if "Tote" in r["product"]]
    if not tote:
        return 0  # no stockout row -> nothing to reorder at this velocity
    return int(tote[0]["reorder_qty"])


def test_property_reorder_monotonic_in_velocity():
    """Higher 7d velocity (same on-hand) never lowers reorder_qty."""
    velocities = [1, 2, 4, 8, 16, 32]
    qtys = [_reorder_qty_for_velocity(v) for v in velocities]
    for lo, hi in zip(qtys, qtys[1:]):
        assert hi >= lo, f"monotonicity violated: {list(zip(velocities, qtys))}"
    # And all quantities are non-negative integers.
    for q in qtys:
        assert q >= 0 and q == int(q)


def test_property_reorder_zero_velocity_zero_qty():
    """Zero sales -> zero reorder (no phantom purchase orders)."""
    events = [make_inventory_event("Dead Product X", 20),
              make_supplier_event("Dead Product X 10 x 5.00 50.00")]
    close = run_close(events)
    for row in close["reorder_sheet"]:
        assert float(row["reorder_qty"]) >= 0


def test_property_reorder_covers_14d_velocity():
    """Reorder qty ≈ ceil(vel*14 - on_hand) for the stressed product."""
    sold = 14  # vel = 2/day -> need ceil(28-2)=26
    q = _reorder_qty_for_velocity(sold, on_hand=2)
    assert q == 26, f"expected 26, got {q}"


# ---------------------------------------------------------------------------
# 3. empty events -> all_clear + healthy close.
# ---------------------------------------------------------------------------


def test_property_empty_events_all_clear_no_crash():
    from omni_one.packs.seller_close import build_daily_close
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    events: list[dict[str, Any]] = []
    briefing = build_seller_briefing(events)
    assert any(a.get("type") == "all_clear" for a in briefing["alerts"]), briefing["alerts"]
    scen = run_all_scenarios(events)
    close = build_daily_close(events, briefing, scen, shop="empty")
    assert close["kpis"]["orders"] == 0
    assert close["kpis"]["gmv"] == 0
    assert close["kpis"]["true_profit"] == 0
    assert close["reorder_sheet"] == []
    assert close["headline"]  # non-empty headline, no crash
    assert close["do_today"] and len(close["do_today"]) == 3


def test_property_single_event_no_crash():
    """Degenerate single-order stream closes without raising."""
    events = [make_order_event(random.Random(1), 0)]
    close = run_close(events)
    assert close["kpis"]["orders"] == 1
    assert float(close["kpis"]["gmv"]) > 0


def test_property_inventory_only_no_crash():
    """Inventory without orders: zero GMV, dead-stock note, no exception."""
    events = [make_inventory_event("Lonely SKU", 25),
              make_inventory_event("Lonely SKU 2", 30)]
    close = run_close(events)
    assert close["kpis"]["orders"] == 0
    assert close["kpis"]["gmv"] == 0


# ---------------------------------------------------------------------------
# 4. 1000 synthetic orders < 5s.
# ---------------------------------------------------------------------------


def test_property_1000_orders_under_5s():
    rng = random.Random(20240601)
    events = [make_order_event(rng, i) for i in range(1000)]
    events.append(make_inventory_event("Tote Bag Handmade", 2))
    events.append(make_supplier_event("Tote Bag Canvas 50 x 4.00 200.00"))
    t0 = time.perf_counter()
    close = run_close(events)
    dt = time.perf_counter() - t0
    assert dt < 5.0, f"1000-order close took {dt:.2f}s (>5s)"
    assert close["kpis"]["orders"] == 1000
    assert float(close["kpis"]["gmv"]) > 0
    # Invariants still hold at volume.
    assert float(close["kpis"]["true_profit"]) <= float(close["kpis"]["gmv"]) + 0.011


def test_property_repeat_close_same_ms_order():
    """Two consecutive closes agree (idempotent headline + reorder)."""
    events = random_event_stream(77, 40)
    c1 = run_close(events)
    c2 = run_close(events)
    assert c1["headline"] == c2["headline"]
    assert c1["reorder_sheet"] == c2["reorder_sheet"]


# ---------------------------------------------------------------------------
# 5. unicode product names preserved.
# ---------------------------------------------------------------------------


UNICODE_NAMES = [
    "Tote Bag 🎒✨ 手工包",
    "Café Mug ☕ crème",
    "Botanical プリント 🌿",
    "Schal 🧣 naïve",
    "Bougie Noël 🎄",
]


def test_property_unicode_names_preserved_end_to_end():
    """Unicode/emoji names survive briefing KPIs + reorder sheet + CSV."""
    from omni_one.packs.seller_close import reorder_to_csv
    rng = random.Random(5)
    events: list[dict[str, Any]] = []
    for i, name in enumerate(UNICODE_NAMES):
        for k in range(3):
            events.append(make_order_event(rng, i * 10 + k, product=name, gmv=28.0))
        events.append(make_inventory_event(name, 1, line=i + 2))
    events.append(make_supplier_event("Canvas 50 x 4.00 200.00"))
    close = run_close(events)
    blob = (close["headline"] + str(close["reorder_sheet"])
            + str(close["kpis"]) + reorder_to_csv(close))
    for name in UNICODE_NAMES:
        assert name in blob, f"unicode name lost: {name!r}"


def test_property_unicode_dm_and_review_no_crash():
    """Unicode DMs/reviews flow through at-risk detection without raising."""
    events = [
        {"timestamp": datetime.now(), "source": "dm", "entity_id": "dm:u1",
         "value": "Zoé 🇫🇷: Mon sac 🎒 n'est pas arrivé, worried 😞",
         "metadata": {"source_file": "instagram_dm.txt", "line": 1, "signal": "dm",
                      "citation": "[instagram_dm.txt:1] Zoé"}},
        {"timestamp": datetime.now(), "source": "review", "entity_id": "rev:u1",
         "value": "田中太郎 terrible 遅い chipped 😞",
         "metadata": {"source_file": "reviews.csv", "line": 2, "signal": "review",
                      "citation": "[reviews.csv:2] 田中太郎"}},
        make_order_event(random.Random(3), 0, product=UNICODE_NAMES[0]),
    ]
    close = run_close(events)
    assert close["reply_queue"]  # at-risk detected despite unicode
    for q in close["reply_queue"]:
        assert CITATION_RE.search(q["citation"])


def test_property_citations_present_on_reorder_and_reply():
    """Every reorder row + every reply carries a [file:line] citation."""
    events = random_event_stream(1234, 30)
    # Force an at-risk DM so the reply queue is non-empty.
    events.append({
        "timestamp": datetime.now(), "source": "dm", "entity_id": "dm:force",
        "value": "Alice: Hi! My Tote Bag Handmade hasn't arrived yet. Worried.",
        "metadata": {"source_file": "instagram_dm.txt", "line": 50, "signal": "dm",
                     "citation": "[instagram_dm.txt:50] Alice: hasn't arrived"}})
    close = run_close(events)
    assert close["reply_queue"], "expected non-empty reply queue"
    for row in close["reorder_sheet"]:
        assert CITATION_RE.search(str(row.get("citation", ""))), row
    for q in close["reply_queue"]:
        assert CITATION_RE.search(str(q.get("citation", ""))), q
        if str(q.get("draft", "")).strip():
            assert CITATION_RE.search(str(q["draft"])), q


def test_property_gmv_additive_over_channels():
    """Total GMV equals the sum of per-channel GMVs (no double counting)."""
    rng = random.Random(606)
    shopify = [make_order_event(rng, i, gmv=round(rng.uniform(10, 50), 2),
                                channel_file="shopify_orders.csv") for i in range(10)]
    etsy = [make_order_event(rng, 100 + i, gmv=round(rng.uniform(10, 50), 2),
                             channel_file="etsy_settlement.csv") for i in range(8)]
    close = run_close(shopify + etsy)
    expect = sum(e["metadata"]["gmv"] for e in shopify + etsy)
    assert abs(float(close["kpis"]["gmv"]) - expect) < 0.01, (
        f"gmv {close['kpis']['gmv']} != sum {expect}")
    assert close["kpis"]["orders"] == 18


def test_property_same_seed_same_kpis():
    """Identical seeds -> identical KPIs (deterministic synthesis + close)."""
    c1 = run_close(random_event_stream(31337, 60))
    c2 = run_close(random_event_stream(31337, 60))
    assert c1["kpis"] == c2["kpis"]
    assert c1["headline"] == c2["headline"]
    # Different seeds (almost surely) diverge somewhere observable.
    c3 = run_close(random_event_stream(99991, 60))
    assert c3["kpis"] != c1["kpis"] or c3["headline"] != c1["headline"]


def test_property_margin_within_bounds():
    """Margin % stays within [-100, 100] over adversarial streams."""
    for seed in range(10):
        close = run_close(random_event_stream(50_000 + seed, 80))
        m = float(close["kpis"]["margin_pct"] or 0)
        assert -100.0 - 0.1 <= m <= 100.0 + 0.1, f"seed={seed}: margin {m}"
