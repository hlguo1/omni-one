"""Synthetic seller-corpus generator (WORKSTREAM F).

Generates an N-shop deterministic corpus for evals + hardening:

    PYTHONPATH=src python3 evals/generate.py --shops 3 --out /tmp/eval_smoke --seed 7

Each shop is a folder that :func:`ingest_seller_folder` can read:

* ``*_orders.csv`` / ``shopify_*`` / ``etsy_*`` / ``amazon_*`` — orders across
  channels (Shopify / Etsy / Amazon payout flavours, messy headers).
* ``inventory.csv`` — on-hand quantities with supplier column.
* ``reviews.csv`` — star ratings + free text (multi-issue mix).
* ``instagram_dm.txt`` / ``messages.json`` — DMs (multi-issue mix).
* ``supplier_invoice_*.txt`` (+ sidecar ``*.jpg.txt``) — supplier invoices
  with ``QTY x UNIT TOTAL`` lines the COGS allocator parses.

Layout written::

    <out>/<shop_name>/...files...
    <out>/manifest.csv            # shop,orders,gmv

Determinism: every random choice goes through ``random.Random(seed)``.
Same ``(seed, shops)`` always yields byte-identical CSVs (modulo nothing).
No wall-clock, no uuid, no global ``random`` module use.

Edge shops (always available; first N archetypes are used when ``--shops N``
is small so smoke stays fast, full edge coverage appears at larger N):

* ``empty`` — folder with no ingestable files (ingest must not crash).
* ``refunds_only`` — every order has status refunded/returned + refund DMs.
* ``single_sku`` — exactly one product across all orders/inventory.
* ``stress_10k`` — 10 000-order CSV (ingest + close perf probe).
* ``unicode`` — product/customer names with CJK + emoji + accents.
* ``semicolon`` — ``;``-delimited orders CSV (Sniffer must survive).
* ``bom`` — UTF-8-SIG BOM headers (header normaliser must survive).

Archetype order (index -> archetype)::

    0 golden_demo   (byte-equivalent to make_seller_demo_folder(seed=42))
    1 standard
    2 refunds_only
    3 single_sku
    4 empty
    5 unicode
    6 semicolon
    7 bom
    8 standard (variant)
    9 stress_10k
    10+ standard (rotating variants)

``--shops 3`` therefore yields golden + standard + refunds_only (fast).
``--shops 10`` yields the full edge matrix including the stress shop.

Manifest columns: ``shop,orders,gmv`` where ``orders`` is the number of
order rows written and ``gmv`` is the rounded sum of row totals.

Stdlib only. $0. Offline.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Static pools (no randomness here — randomness only enters via rng.choice).
# ---------------------------------------------------------------------------

BASE_PRODUCTS: list[tuple[str, str, float, str]] = [
    # (display name, sku, base price, supplier)
    ("Tote Bag Handmade", "TB001", 28.00, "Acme Textiles"),
    ("Ceramic Mug", "CM002", 22.00, "Clay Co"),
    ("Print - Botanical", "PR003", 15.00, "Paper Co"),
    ("Knitted Scarf", "KS004", 45.00, "Wool Co"),
    ("Leather Wallet", "LW005", 39.00, "Hide Works"),
    ("Soy Candle - Vanilla", "SC006", 18.00, "Wax & Wick"),
    ("Embroidered Cap", "EC007", 25.00, "Stitch Supply"),
    ("Silver Ring", "SR008", 55.00, "Metal House"),
]

UNICODE_PRODUCTS: list[tuple[str, str, float, str]] = [
    ("Tote Bag 🎒✨ 手工包", "UTB01", 28.00, "Acme Textiles 纺织"),
    ("Café Mug ☕ crème", "UCM02", 22.00, "Clay Co 🏺"),
    ("Botanical プリント 🌿", "UPR03", 15.00, "Paper Co 紙"),
    ("Schal 🧣 naïve", "UKS04", 45.00, "Wool Co 🐑"),
    ("Bougie Noël 🎄", "UBN05", 18.00, "Wax & Wick 🕯️"),
]

CUSTOMER_NAMES = [
    "Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hank",
    "Ivy", "Jack", "Karen", "Leo", "Mona", "Nina", "Omar", "Priya",
    "Quinn", "Rosa", "Sam", "Tara", "Uma", "Victor", "Wendy", "Yusuf",
]

UNICODE_CUSTOMERS = [
    "Zoé 🇫🇷", "田中太郎", "Müller", "José 🎉", "Åsa", "李小龙 🐉",
    "O'Brien", " mBah ", "Élodie", "北京店",
]

# Multi-issue DM mix: late / tracking / damaged / refund / happy / question.
DM_TEMPLATES: list[str] = [
    "{name}: Hi! My {product} hasn't arrived yet, ordered 5 days ago. Worried.",
    "{name}: Where is my order? No tracking number received.",
    "{name}: My {product} arrived chipped/damaged, very disappointed. Want refund.",
    "{name}: I want a refund for order, please advise on return.",
    "{name}: Amazing {product}! Will order again. Love it!",
    "{name}: Do you have the {product} in blue? Quick question.",
    "{name}: Package shows delivered but nothing arrived. Missing?!",
    "{name}: Late delivery — expected yesterday. Angry, need update.",
    "{name}: Perfect quality, fast shipping! Beautiful work.",
    "{name}: Tracking hasn't moved in 4 days, where is my package?",
    "{name}: Wrong item received — ordered {product}, got something else.",
    "{name}: Can I change my address? Order placed an hour ago.",
]

REVIEW_TEXTS: list[tuple[int, str]] = [
    (5, "Love it! Perfect size, fast shipping."),
    (5, "Beautiful! Exceeded expectations."),
    (5, "Amazing quality, will buy again."),
    (4, "Good, shipping took a bit long but happy."),
    (3, "OK product, average packaging."),
    (2, "Arrived chipped, very disappointed."),
    (1, "Terrible — damaged and late, want refund."),
    (1, "Awful experience, never arrived, no tracking."),
    (5, "Perfect gift! My sister loves it."),
    (2, "Poor quality, bad stitching on arrival."),
    (4, "Great seller, quick reply to my DM."),
    (1, "Horrible — broken on arrival, angry."),
]

SUPPLIER_LINES = [
    ("{supplier}", None, None, None),
]

CHANNELS = ("shopify", "etsy", "amazon")

# Messy header variants per channel (all must normalise via _norm_header).
SHOPIFY_HEADERS = [
    ["Order Name", "Created at", "Lineitem name", "Lineitem quantity",
     "Lineitem price", "Total", "Fees", "Shipping", "Customer"],
]
ETSY_HEADERS = [
    ["order_id", "order_date", "product", "qty", "price", "fees", "shipping", "buyer"],
    ["Receipt", "Sale Date", "Listing Title", "Units", "Order Total", "Etsy Fee", "Postage", "Buyer"],
]
AMAZON_HEADERS = [
    ["order-id", "purchase-date", "sku", "quantity", "item-price", "commission", "delivery", "recipient"],
    ["Order ID", "Date", "Item Description", "Qty", "Gross", "Amazon Fee", "Shipping", "Customer"],
]

SEMICOLON_HEADERS = ["order_id", "order_date", "product", "qty", "price", "fees", "shipping", "buyer"]

BOM_HEADERS = ["order_id", "order_date", "product", "qty", "price", "fees", "shipping", "buyer"]

INVENTORY_HEADERS = ["sku", "product", "stock", "supplier"]
REVIEW_HEADERS = ["date", "product", "stars", "review"]

# ---------------------------------------------------------------------------
# Small deterministic helpers (all take rng explicitly).
# ---------------------------------------------------------------------------


def _pick(rng: random.Random, seq: list[Any]) -> Any:
    """RNG-pinned choice (wraps Random.choice for grep-ability)."""
    return rng.choice(seq)


def _rint(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def _price_jitter(rng: random.Random, base: float) -> float:
    """Small deterministic price wobble (+/-10%) rounded to cents."""
    jitter = 1.0 + (rng.random() - 0.5) * 0.2
    return round(base * jitter, 2)


def _iso_date(rng: random.Random, base: datetime, span_days: int = 7) -> str:
    delta = rng.randint(0, span_days)
    return (base - timedelta(days=delta)).strftime("%Y-%m-%d")


def _fee_for(channel: str, gmv: float, rng: random.Random) -> float:
    """Channel-realistic fee formulas (match seller_os ingest heuristics)."""
    if channel == "etsy":
        return round(gmv * 0.065 + 0.20, 2)
    if channel == "shopify":
        return round(gmv * 0.029 + 0.30, 2)
    if channel == "amazon":
        return round(gmv * 0.15, 2)
    return round(gmv * 0.08, 2)


def _ship_for(channel: str, rng: random.Random) -> float:
    return float(rng.choice([0.00, 3.00, 3.50, 4.00, 4.50, 5.00]))


def _cogs_unit(price: float, rng: random.Random) -> float:
    """Supplier unit cost ~30-45% of retail (matches briefing heuristic)."""
    frac = 0.30 + rng.random() * 0.15
    return round(price * frac, 2)


# ---------------------------------------------------------------------------
# File writers — each is deterministic given rng.
# ---------------------------------------------------------------------------


def write_orders_csv(
    path: Path,
    rng: random.Random,
    n_orders: int,
    channel: str,
    products: list[tuple[str, str, float, str]],
    base_date: datetime,
    start_id: int = 1000,
    status_pool: list[str] | None = None,
    delimiter: str = ",",
    encoding: str = "utf-8",
) -> tuple[int, float]:
    """Write an orders CSV; returns (n_rows, gmv_sum)."""
    status_pool = status_pool or ["fulfilled", "fulfilled", "fulfilled", "pending"]
    if channel == "shopify":
        headers = _pick(rng, SHOPIFY_HEADERS)
        use_shopify_shape = True
    elif channel == "etsy":
        headers = _pick(rng, ETSY_HEADERS)
        use_shopify_shape = False
    else:
        headers = _pick(rng, AMAZON_HEADERS)
        use_shopify_shape = False
    if delimiter == ";":
        headers = list(SEMICOLON_HEADERS)
        use_shopify_shape = False

    total_gmv = 0.0
    with open(path, "w", newline="", encoding=encoding) as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(headers)
        # Map header names to writer lambdas by position for realism.
        for i in range(n_orders):
            name, _sku, base_price, _sup = _pick(rng, products)
            qty = _rint(rng, 1, 3)
            unit = _price_jitter(rng, base_price)
            line_total = round(unit * qty, 2)
            fee = _fee_for(channel, line_total, rng)
            ship = _ship_for(channel, rng)
            customer = _pick(rng, CUSTOMER_NAMES)
            date = _iso_date(rng, base_date)
            status = _pick(rng, status_pool)
            oid = f"{start_id + i}"
            total_gmv += line_total
            if use_shopify_shape:
                # Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer
                w.writerow([f"#{oid}", date, name, qty, f"{unit:.2f}",
                            f"{line_total:.2f}", f"{fee:.2f}", f"{ship:.2f}", customer])
            else:
                # Generic 8-col: id,date,product,qty,price,fee,ship,buyer.
                # The gmv-mapped column MUST hold the LINE TOTAL (unit*qty):
                # ingest treats that column as the row's GMV and never
                # multiplies by qty itself (Shopify shape is the exception —
                # it carries both unit price and Total, and ingest keeps max).
                row = [oid, date, name, qty, f"{line_total:.2f}",
                       f"{fee:.2f}", f"{ship:.2f}", customer]
                # Keep row length == header length (pad/truncate deterministically).
                if len(row) < len(headers):
                    row += [status] * (len(headers) - len(row))
                row = row[:len(headers)]
                # If this header set expects unit price in col 4 but we wrote total,
                # that is fine — ingest takes last money for totals; keep varied.
                w.writerow(row)
    return n_orders, round(total_gmv, 2)


def write_orders_bom(
    path: Path,
    rng: random.Random,
    n_orders: int,
    products: list[tuple[str, str, float, str]],
    base_date: datetime,
) -> tuple[int, float]:
    """BOM-header orders CSV (utf-8-sig so first header has \\ufeff)."""
    headers = list(BOM_HEADERS)
    total = 0.0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for i in range(n_orders):
            name, _sku, base_price, _sup = _pick(rng, products)
            qty = _rint(rng, 1, 2)
            unit = _price_jitter(rng, base_price)
            line_total = round(unit * qty, 2)
            total += line_total
            w.writerow([f"B{i:04d}", _iso_date(rng, base_date), name, qty,
                        f"{line_total:.2f}", f"{_fee_for('etsy', line_total, rng):.2f}",
                        f"{_ship_for('etsy', rng):.2f}", _pick(rng, CUSTOMER_NAMES)])
    return n_orders, round(total, 2)


def write_inventory_csv(
    path: Path,
    rng: random.Random,
    products: list[tuple[str, str, float, str]],
    low_stock_product: str | None = None,
) -> int:
    """Write inventory.csv; forces one low-stock line so stockout fires."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(INVENTORY_HEADERS)
        for name, sku, _price, supplier in products:
            if low_stock_product is not None and name == low_stock_product:
                stock = _rint(rng, 1, 3)
            else:
                stock = _rint(rng, 5, 40)
            w.writerow([sku, name, stock, supplier])
    return len(products)


def write_reviews_csv(
    path: Path,
    rng: random.Random,
    n_reviews: int,
    products: list[tuple[str, str, float, str]],
    base_date: datetime,
    force_negative: bool = False,
) -> int:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REVIEW_HEADERS)
        for _ in range(n_reviews):
            name = _pick(rng, products)[0]
            if force_negative:
                stars, text = _pick(rng, [(t) for t in REVIEW_TEXTS if t[0] <= 2])
            else:
                stars, text = _pick(rng, REVIEW_TEXTS)
            w.writerow([_iso_date(rng, base_date), name, stars, text])
    return n_reviews


def write_dms_txt(
    path: Path,
    rng: random.Random,
    n_dms: int,
    products: list[tuple[str, str, float, str]],
) -> int:
    lines: list[str] = []
    for _ in range(n_dms):
        tpl = _pick(rng, DM_TEMPLATES)
        lines.append(tpl.format(name=_pick(rng, CUSTOMER_NAMES),
                                product=_pick(rng, products)[0]))
    # Guarantee at least one at-risk + one happy line for stable evals.
    if n_dms >= 2:
        lines[0] = (f"{_pick(rng, CUSTOMER_NAMES)}: Hi! My {_pick(rng, products)[0]} "
                    "hasn't arrived yet, ordered 5 days ago. Worried.")
        lines[1] = f"{_pick(rng, CUSTOMER_NAMES)}: Amazing {_pick(rng, products)[0]}! Love it!"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def write_dms_json(path: Path, rng: random.Random, n_dms: int,
                   products: list[tuple[str, str, float, str]]) -> int:
    msgs: list[dict[str, Any]] = []
    for _ in range(n_dms):
        tpl = _pick(rng, DM_TEMPLATES)
        body = tpl.format(name="", product=_pick(rng, products)[0]).lstrip(": ")
        msgs.append({"from": _pick(rng, CUSTOMER_NAMES), "text": body})
    path.write_text(json.dumps(msgs, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(msgs)


def write_supplier_invoice(
    path: Path,
    rng: random.Random,
    products: list[tuple[str, str, float, str]],
    n_lines: int = 2,
) -> float:
    """Supplier .txt invoice with parseable ``QTY x UNIT TOTAL`` lines."""
    lines: list[str] = []
    supplier = products[0][3] if products else "Acme Textiles"
    lines.append(supplier)
    grand = 0.0
    for _ in range(n_lines):
        name, _sku, base_price, _sup = _pick(rng, products)
        qty = _rint(rng, 20, 60)
        unit = _cogs_unit(base_price, rng)
        total = round(qty * unit, 2)
        grand += total
        # Short material word so briefing catalog keys (tote/mug/print/...) hit.
        lines.append(f"{name} {qty} x {unit:.2f} {total:.2f}")
    ship = round(rng.random() * 20, 2)
    grand += ship
    lines.append(f"Shipping {ship:.2f}")
    lines.append(f"Total ${grand:.2f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Sidecar vision file (ingest dedups identical content — keeps COGS stable).
    sidecar = Path(str(path) + ".txt") if not path.name.endswith(".txt") else None
    _ = sidecar
    return round(grand, 2)


def write_golden_demo_shop(dest: Path) -> tuple[int, float]:
    """Byte-equivalent copy of make_seller_demo_folder(seed=42).

    Golden profit for this shop is $169.09 — evals/run.py asserts it.
    Content duplicated here (instead of importing) so the generator stays
    stdlib-only and deterministic even if the demo helper changes shape;
    values below mirror seller_os.make_seller_demo_folder exactly.
    """
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "shopify_orders.csv").write_text(
        """Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer
#1001,2024-09-10,Tote Bag Handmade,2,28.00,56.00,,4.00,Alice
#1002,2024-09-11,Ceramic Mug,1,22.00,22.00,,3.50,Bob
#1003,2024-09-11,Tote Bag Handmade,1,28.00,28.00,,0.00,Charlie
#1004,2024-09-12,Print - Botanical,3,15.00,45.00,,5.00,Alice
#1005,2024-09-12,Tote Bag Handmade,1,28.00,28.00,,4.00,David
""", encoding="utf-8")
    (dest / "etsy_settlement.csv").write_text(
        """order_id,order_date,product,qty,price,fees,shipping,buyer
E2001,2024-09-10,Knitted Scarf,1,45.00,3.12,4.50,Eve
E2002,2024-09-11,Tote Bag Handmade,2,28.00,3.84,0.00,Frank
E2003,2024-09-12,Ceramic Mug,2,22.00,3.06,3.00,Grace
""", encoding="utf-8")
    (dest / "inventory.csv").write_text(
        """sku,product,stock,supplier
TB001,Tote Bag Handmade,2,Acme Textiles
CM002,Ceramic Mug,15,Clay Co
PR003,Print - Botanical,40,Paper Co
KS004,Knitted Scarf,8,Wool Co
""", encoding="utf-8")
    (dest / "reviews.csv").write_text(
        """date,product,stars,review
2024-09-11,Tote Bag Handmade,5,"Love it! Perfect size"
2024-09-11,Ceramic Mug,2,"Arrived chipped, very disappointed"
2024-09-12,Print - Botanical,5,"Beautiful!"
""", encoding="utf-8")
    (dest / "instagram_dm.txt").write_text(
        """Alice: Hi! My tote bag hasn't arrived yet, ordered 5 days ago. Worried.
Shop: Hi Alice, checking tracking — will update in 1h
Bob: Amazing mug! Will order again.
Charlie: Where is my order? No tracking.
""", encoding="utf-8")
    (dest / "supplier_invoice_2024-09-10.txt").write_text(
        "Acme Textiles\nTote Bag Canvas 50 x 4.00 200.00\nShipping 15.00\nTotal $215.00\n",
        encoding="utf-8")
    (dest / "supplier_invoice_2024-09-10.jpg").write_bytes(b"\xFF\xD8\xFF")
    (dest / "supplier_invoice_2024-09-10.jpg.txt").write_text(
        "Acme Textiles\nTote Bag Canvas 50 x 4.00 200.00\nTotal $215.00\n",
        encoding="utf-8")
    # 8 order rows; GMV = 56+22+28+45+28 + 45+56+44 = 324? No:
    # shopify totals: 56+22+28+45+28=179; etsy price col holds LINE totals?
    # etsy rows: 45.00 / 28.00 / 22.00 with qty 1/2/2 — ingest takes LAST money
    # per row as gmv: 45 + 28 + 22 = 95. Total GMV = 179+95 = 274.00.
    return 8, 274.00


# ---------------------------------------------------------------------------
# Archetype builders — each returns (n_orders, gmv).
# ---------------------------------------------------------------------------


def _base_date_for(rng: random.Random) -> datetime:
    return datetime(2024, 9, 12)


def build_standard_shop(dest: Path, rng: random.Random, variant: int = 0) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    n_pool = list(BASE_PRODUCTS)
    # Variant rotates product subset + channel mix for diversity.
    rng.shuffle(n_pool)
    prods = n_pool[:4 + (variant % 3)]
    orders_total = 0
    gmv_total = 0.0
    n_shopify = _rint(rng, 4, 7)
    n_etsy = _rint(rng, 2, 5)
    n_amz = _rint(rng, 0, 3) if variant % 2 == 0 else 0
    n, g = write_orders_csv(dest / "shopify_orders.csv", rng, n_shopify,
                            "shopify", prods, base, start_id=1000 + variant * 100)
    orders_total += n
    gmv_total += g
    n, g = write_orders_csv(dest / "etsy_settlement.csv", rng, n_etsy,
                            "etsy", prods, base, start_id=2000 + variant * 100)
    orders_total += n
    gmv_total += g
    if n_amz:
        n, g = write_orders_csv(dest / "amazon_payout.csv", rng, n_amz,
                                "amazon", prods, base, start_id=3000 + variant * 100)
        orders_total += n
        gmv_total += g
    low = prods[0][0]
    write_inventory_csv(dest / "inventory.csv", rng, prods, low_stock_product=low)
    write_reviews_csv(dest / "reviews.csv", rng, _rint(rng, 3, 6), prods, base)
    write_dms_txt(dest / "instagram_dm.txt", rng, _rint(rng, 4, 8), prods)
    write_supplier_invoice(dest / "supplier_invoice_2024-09-10.txt", rng, prods,
                           n_lines=_rint(rng, 1, 3))
    (dest / "supplier_invoice_2024-09-10.jpg").write_bytes(b"\xFF\xD8\xFF")
    (dest / "supplier_invoice_2024-09-10.jpg.txt").write_text(
        f"{prods[0][3]}\n{prods[0][0]} 50 x 4.00 200.00\nTotal $215.00\n", encoding="utf-8")
    return orders_total, round(gmv_total, 2)


def build_refunds_only_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = list(BASE_PRODUCTS[:4])
    n, gmv = write_orders_csv(
        dest / "shopify_orders.csv", rng, _rint(rng, 4, 6), "shopify", prods,
        base, start_id=9000,
        status_pool=["refunded", "returned", "refunded", "chargeback"])
    write_inventory_csv(dest / "inventory.csv", rng, prods)
    # All-negative reviews + refund-heavy DMs.
    write_reviews_csv(dest / "reviews.csv", rng, 5, prods, base, force_negative=True)
    refund_dms = [
        "Alice: I want a refund for my Tote Bag Handmade, never arrived.",
        "Bob: Return requested — Ceramic Mug arrived damaged, refund please.",
        "Charlie: Chargeback filed, where is my refund?",
        "Shop: Hi all — processing refunds today, sorry for the trouble.",
    ]
    (dest / "instagram_dm.txt").write_text("\n".join(refund_dms) + "\n", encoding="utf-8")
    write_supplier_invoice(dest / "supplier_invoice_refund.txt", rng, prods, n_lines=1)
    return n, round(gmv, 2)


def build_single_sku_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = [BASE_PRODUCTS[0]]  # Tote Bag Handmade only
    n, gmv = write_orders_csv(dest / "shopify_orders.csv", rng, _rint(rng, 5, 8),
                              "shopify", prods, base, start_id=5000)
    write_inventory_csv(dest / "inventory.csv", rng, prods, low_stock_product=prods[0][0])
    write_reviews_csv(dest / "reviews.csv", rng, 3, prods, base)
    write_dms_txt(dest / "instagram_dm.txt", rng, 4, prods)
    write_supplier_invoice(dest / "supplier_invoice_single.txt", rng, prods, n_lines=1)
    return n, round(gmv, 2)


def build_empty_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.md").write_text(
        "# Empty shop\n\nNo sales files yet — ingest must report zero events, not crash.\n",
        encoding="utf-8")
    return 0, 0.00


def build_unicode_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = list(UNICODE_PRODUCTS)
    orders_total = 0
    gmv_total = 0.0
    n, g = write_orders_csv(dest / "shopify_orders.csv", rng, 6, "shopify",
                            prods, base, start_id=7000)
    orders_total += n
    gmv_total += g
    n, g = write_orders_csv(dest / "etsy_settlement.csv", rng, 4, "etsy",
                            prods, base, start_id=7100)
    orders_total += n
    gmv_total += g
    write_inventory_csv(dest / "inventory.csv", rng, prods,
                        low_stock_product=prods[0][0])
    # Reviews + DMs with unicode customers/issues.
    with open(dest / "reviews.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(REVIEW_HEADERS)
        for _ in range(5):
            stars, text = _pick(rng, REVIEW_TEXTS)
            w.writerow([_iso_date(rng, base), _pick(rng, prods)[0], stars,
                        f"{text} {_pick(rng, ['🎉', '😊', '😞', 'ありがとう', 'merci'])}"])
    uni_lines = []
    for _ in range(6):
        tpl = _pick(rng, DM_TEMPLATES)
        uni_lines.append(tpl.format(name=_pick(rng, UNICODE_CUSTOMERS),
                                    product=_pick(rng, prods)[0]))
    (dest / "instagram_dm.txt").write_text("\n".join(uni_lines) + "\n", encoding="utf-8")
    write_supplier_invoice(dest / "supplier_invoice_unicode.txt", rng, prods, n_lines=2)
    return orders_total, round(gmv_total, 2)


def build_semicolon_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = list(BASE_PRODUCTS[:4])
    n, gmv = write_orders_csv(dest / "shopify_orders_semicolon.csv", rng, 6,
                              "shopify", prods, base, start_id=8000,
                              delimiter=";")
    write_inventory_csv(dest / "inventory.csv", rng, prods,
                        low_stock_product=prods[0][0])
    write_reviews_csv(dest / "reviews.csv", rng, 4, prods, base)
    write_dms_txt(dest / "instagram_dm.txt", rng, 5, prods)
    write_supplier_invoice(dest / "supplier_invoice_semi.txt", rng, prods, n_lines=2)
    return n, round(gmv, 2)


def build_bom_shop(dest: Path, rng: random.Random) -> tuple[int, float]:
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = list(BASE_PRODUCTS[:4])
    n, gmv = write_orders_bom(dest / "etsy_orders_bom.csv", rng, 6, prods, base)
    write_inventory_csv(dest / "inventory.csv", rng, prods,
                        low_stock_product=prods[0][0])
    write_reviews_csv(dest / "reviews.csv", rng, 4, prods, base)
    write_dms_txt(dest / "instagram_dm.txt", rng, 5, prods)
    write_supplier_invoice(dest / "supplier_invoice_bom.txt", rng, prods, n_lines=2)
    return n, round(gmv, 2)


def build_stress_shop(dest: Path, rng: random.Random, n_orders: int = 10000) -> tuple[int, float]:
    """10k-order stress shop: one wide CSV + inventory + supplier invoice.

    Reviews/DMs stay small — the stress is order-row throughput.
    """
    dest.mkdir(parents=True, exist_ok=True)
    base = _base_date_for(rng)
    prods = list(BASE_PRODUCTS)
    n, gmv = write_orders_csv(dest / "shopify_orders_stress.csv", rng, n_orders,
                              "shopify", prods, base, start_id=100000)
    write_inventory_csv(dest / "inventory.csv", rng, prods,
                        low_stock_product=prods[0][0])
    write_reviews_csv(dest / "reviews.csv", rng, 10, prods, base)
    write_dms_txt(dest / "instagram_dm.txt", rng, 10, prods)
    write_supplier_invoice(dest / "supplier_invoice_stress.txt", rng, prods, n_lines=4)
    return n, round(gmv, 2)


# ---------------------------------------------------------------------------
# Archetype dispatch + manifest.
# ---------------------------------------------------------------------------

ARCHETYPE_ORDER: list[str] = [
    "golden_demo",
    "standard",
    "refunds_only",
    "single_sku",
    "empty",
    "unicode",
    "semicolon",
    "bom",
    "standard",
    "stress_10k",
]


def archetype_for_index(i: int) -> str:
    if i < len(ARCHETYPE_ORDER):
        return ARCHETYPE_ORDER[i]
    # Beyond the table: rotate standard variants (keeps corpus unbounded).
    return "standard"


def build_shop(dest: Path, archetype: str, rng: random.Random, variant: int,
               stress_orders: int = 10000) -> tuple[int, float]:
    if archetype == "golden_demo":
        return write_golden_demo_shop(dest)
    if archetype == "standard":
        return build_standard_shop(dest, rng, variant=variant)
    if archetype == "refunds_only":
        return build_refunds_only_shop(dest, rng)
    if archetype == "single_sku":
        return build_single_sku_shop(dest, rng)
    if archetype == "empty":
        return build_empty_shop(dest, rng)
    if archetype == "unicode":
        return build_unicode_shop(dest, rng)
    if archetype == "semicolon":
        return build_semicolon_shop(dest, rng)
    if archetype == "bom":
        return build_bom_shop(dest, rng)
    if archetype == "stress_10k":
        return build_stress_shop(dest, rng, n_orders=stress_orders)
    raise ValueError(f"unknown archetype: {archetype}")


def shop_dir_name(i: int, archetype: str) -> str:
    return f"shop_{i:02d}_{archetype}"


def generate_corpus(out: Path, n_shops: int, seed: int,
                    stress_orders: int = 10000) -> list[tuple[str, int, float]]:
    """Generate corpus; returns manifest rows (shop, orders, gmv)."""
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows: list[tuple[str, int, float]] = []
    for i in range(n_shops):
        archetype = archetype_for_index(i)
        name = shop_dir_name(i, archetype)
        dest = out / name
        # Sub-RNG per shop keeps shop i stable regardless of total count.
        shop_rng = random.Random(seed * 1000 + i * 97 + 13)
        n_orders, gmv = build_shop(dest, archetype, shop_rng, variant=i,
                                   stress_orders=stress_orders)
        rows.append((name, n_orders, gmv))
    # Manifest AFTER shops so counts are final.
    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["shop", "orders", "gmv"])
        for name, n_orders, gmv in rows:
            w.writerow([name, n_orders, f"{gmv:.2f}"])
    return rows


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate deterministic N-shop seller eval corpus.")
    p.add_argument("--shops", type=int, default=6,
                   help="Number of shops to generate (default 6).")
    p.add_argument("--out", type=str, default="evals/corpus",
                   help="Output directory (shops + manifest.csv).")
    p.add_argument("--seed", type=int, default=7,
                   help="Deterministic seed (default 7).")
    p.add_argument("--stress-orders", type=int, default=10000,
                   help="Row count for the stress_10k archetype (default 10000).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.shops < 1:
        print("error: --shops must be >= 1", file=sys.stderr)
        return 2
    out = Path(args.out)
    rows = generate_corpus(out, args.shops, args.seed,
                           stress_orders=args.stress_orders)
    total_orders = sum(n for _, n, _ in rows)
    total_gmv = sum(g for _, _, g in rows)
    print(f"generated {len(rows)} shops -> {out} (seed={args.seed})")
    for name, n_orders, gmv in rows:
        print(f"  {name}: orders={n_orders} gmv=${gmv:.2f}")
    print(f"total orders={total_orders} total_gmv=${total_gmv:.2f}")
    print(f"manifest: {out / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
