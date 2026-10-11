"""Fuzz tests for money / CSV-header / file parsers (WORKSTREAM F).

The seller pipeline ingests hostile, real-world shop exports: BOM headers,
semicolon delimiters, null bytes, lone quotes, 100KB fields, £€¥ symbols,
date-like numbers, qty-prefix lines ("50 x 4.00 200.00"). These tests fuzz
the three parser layers and assert they *never raise* and *never produce
NaN/inf*:

1. ``_norm_header`` over 2000 seeded random header variants — no raise,
   canonical columns still recognised (order/qty/gmv/fees/shipping/product).
2. ``parse_orders_csv`` / ``parse_inventory_csv`` over malformed CSVs
   (null bytes, lone quotes, huge fields, mixed delimiters, BOM, latin-1
   bytes, truncation) — never raise; always return a list.
3. ``_money`` / ``_money_last`` / ``_money_all`` over adversarial money
   strings — never NaN/inf; totals prefer the LAST number (qty-prefix safe);
   dates never leak in as money.

Seeded ``random.Random`` everywhere: failures reproduce exactly.
"""

from __future__ import annotations

import csv
import math
import random
import string
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _write_raw(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _write_text(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.write_text(text, encoding=encoding)
    return path


def _tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="fuzz-parsers-"))


def _assert_no_raise(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"{fn.__name__} raised on {args!r:.120}: {e}") from e


def _assert_all_finite(vals: list[float], ctx: str) -> None:
    for v in vals:
        assert isinstance(v, float), f"{ctx}: non-float {v!r}"
        assert math.isfinite(v), f"{ctx}: non-finite {v!r}"


# ---------------------------------------------------------------------------
# 1. Header normalisation fuzz (2000 variants, no raise).
# ---------------------------------------------------------------------------


HEADER_SEEDS = [
    "Order Name", "order_id", "Receipt", "ORDER NUMBER", "OrderId",
    "Created at", "order_date", "Date", "purchase-date", "TIMESTAMP",
    "Lineitem name", "product", "Listing Title", "SKU", "Item Description",
    "Lineitem quantity", "qty", "Quantity", "QTY", "units",
    "Lineitem price", "Total", "price", "Gross", "Order Total", "item-price",
    "Fees", "fee", "Etsy Fee", "commission", "Amazon Fee", "SHOPİFY_FEE",
    "Shipping", "postage", "delivery", "SHIPPING COST",
    "Customer", "buyer", "Recipient", "CUSTOMER NAME",
    "Status", "fulfillment", "state",
]

HEADER_NOISE = [" ", "  ", "_", "-", ".", ":", "/", "\\", "#", "$", "%",
                "!", "?", "(", ")", "[", "]", "{", "}", "'", '"', "*"]


def _random_header_variant(rng: random.Random) -> str:
    base = rng.choice(HEADER_SEEDS)
    # Random case mangling.
    mode = rng.randint(0, 4)
    if mode == 0:
        base = base.lower()
    elif mode == 1:
        base = base.upper()
    elif mode == 2:
        base = base.title()
    elif mode == 3:
        base = "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in base)
    # Random surrounding noise / separators.
    if rng.random() < 0.5:
        base = rng.choice(HEADER_NOISE) + base
    if rng.random() < 0.5:
        base = base + rng.choice(HEADER_NOISE)
    if rng.random() < 0.3:
        base = base.replace(" ", rng.choice(["_", "-", ".", "  "]))
    if rng.random() < 0.2:
        base = base.replace("_", rng.choice([" ", "-", "/"]))
    # Occasional BOM / unicode whitespace prefix.
    if rng.random() < 0.1:
        base = "\ufeff" + base
    if rng.random() < 0.1:
        base = base + rng.choice(["\u00a0", "\u2007", "\t"])
    return base


def test_fuzz_norm_header_2000_variants_no_raise():
    from omni_one.packs.seller_parse import _norm_header
    rng = random.Random(20241011)
    seen: set[str] = set()
    for _ in range(2000):
        h = _random_header_variant(rng)
        out = _assert_no_raise(_norm_header, h)
        assert isinstance(out, str) and out, f"empty mapping for {h!r}"
        seen.add(out)
    # Canonical buckets must all be reachable through the noise.
    for bucket in ("order_id", "qty", "gmv", "fees", "shipping", "product", "date"):
        assert bucket in seen, f"bucket {bucket!r} unreachable; got {sorted(seen)}"


def test_fuzz_norm_header_canonical_recognition():
    """Known messy headers map to the canonical bucket (spot checks)."""
    from omni_one.packs.seller_parse import _norm_header
    cases = {
        "Order Name": "order_id", "Receipt": "order_id", "ORDER NUMBER": "order_id",
        "Created at": "date", "purchase-date": "date", "TIMESTAMP": "date",
        "Lineitem name": "product", "Listing Title": "product", "SKU": "product",
        "Lineitem quantity": "qty", "QTY": "qty", "units": "qty",
        "Lineitem price": "gmv", "Order Total": "gmv", "Gross": "gmv", "price": "gmv",
        "Etsy Fee": "fees", "commission": "fees", "fee": "fees",
        "postage": "shipping", "delivery": "shipping",
        "buyer": "customer", "Recipient": "customer",
        "fulfillment": "status",
    }
    for raw, want in cases.items():
        got = _norm_header(raw)
        assert got == want, f"{raw!r} -> {got!r}, want {want!r}"


def test_fuzz_norm_header_empty_and_weird_no_raise():
    from omni_one.packs.seller_parse import _norm_header
    for h in ["", " ", "   ", "\ufeff", "\x00", "12345", "!!!", "price price price",
              "a" * 500, "数量", "💰 total 💰", "Total ($)", "Fee %", "\n\t "]:
        out = _assert_no_raise(_norm_header, h)
        assert isinstance(out, str)


# ---------------------------------------------------------------------------
# 2. Malformed-CSV fuzz (never raise).
# ---------------------------------------------------------------------------


def _malformed_csv_bodies() -> list[bytes]:
    return [
        b"order_id,product,qty,price\n",  # header only
        b"",  # empty file
        b"\x00\x01\x02\xff\xfe garbage \x00 nulls\n",  # null bytes
        b'order_id,product,qty,price\n1,"lone quote,2,10.00\n',  # lone quote
        b'order_id,product,qty,price\n1,"embedded ""quote"" ok",2,10.00\n',  # ok quotes
        b"order_id;product;qty;price\n1;Tote;2;28.00\n",  # semicolon
        b"\xef\xbb\xbforder_id,order_date,product,qty,price\n1,2024-09-10,Tote,1,28.00\n",  # BOM
        b"order_id,product,qty,price\r\n1,Tote,1,28.00\r\n2,Mug,2,22.00\r\n",  # CRLF
        b"order_id,product,qty,price\n" + b"x" * 100_000 + b",Tote,1,28.00\n",  # huge field
        b" just one line no commas at all\n second line\n",
        b"order_id,product,qty,price\n1,Tote,notanumber,$$$ \n",  # junk numbers
        b"order_id,product,qty,price\n1,Tote,2,\n2,,,\n,,,\n",  # empties
        "order_id,product,qty,price\n1,Café ☕,2,28.00\n".encode("latin-1", errors="ignore"),
        "order_id,product,qty,price\n1,Tote 🎒,2,28.00\n".encode("utf-8"),
        b"order_id,product,qty,price\n1,Tote,2,28.00",  # no trailing newline
        b"a,b,c\n1,2\n3,4,5,6,7\n",  # ragged rows
        b"order_id,product,qty,price\n1,Tote,2,28.00\n" * 3000,  # many rows
        b"\xff\xfe bad \x80\x81 encoding \x90 soup \n still,text,here\n",
        b"Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n"
        b"#1001,2024-09-10,Tote Bag,2,28.00,56.00,,4.00,Alice\n"
        b"#BADROW no commas\n"
        b"#1002,2024-09-11,Mug,1,22.00,22.00,,3.50,Bob\n",
    ]


def test_fuzz_orders_csv_malformed_never_raise():
    from omni_one.packs.seller_os import parse_inventory_csv, parse_orders_csv
    bodies = _malformed_csv_bodies()
    tmp = _tmpdir()
    for i, body in enumerate(bodies):
        p = _write_raw(tmp / f"shopify_malformed_{i}.csv", body)
        orders = _assert_no_raise(parse_orders_csv, p)
        assert isinstance(orders, list), f"body {i}: not a list"
        for e in orders:
            assert isinstance(e, dict) and "metadata" in e
        inv = _assert_no_raise(parse_inventory_csv, p)
        assert isinstance(inv, list)


def test_fuzz_ingest_folder_hostile_files_never_raise():
    """Whole-folder ingest over hostile files: no raise, report counts."""
    from omni_one.packs.seller_os import ingest_seller_folder
    tmp = _tmpdir()
    shop = tmp / "hostile_shop"
    shop.mkdir()
    bodies = _malformed_csv_bodies()
    for i, body in enumerate(bodies[:8]):
        _write_raw(shop / f"shopify_orders_{i}.csv", body)
    _write_raw(shop / "inventory.csv", b"sku,product,stock,supplier\n\x00,Broken,NaN,\n")
    (shop / "instagram_dm.txt").write_bytes(b"\x00 dm \xff with \xfe bad bytes \x00\n")
    (shop / "reviews.csv").write_bytes(b"date,product,stars,review\n\x00,\xff,,\n")
    events, report = _assert_no_raise(ingest_seller_folder, shop)
    assert isinstance(events, list)
    assert report["files_seen"] >= 8


def test_fuzz_dm_and_review_hostile_never_raise():
    from omni_one.packs.seller_os import parse_dm_file, parse_reviews_csv
    tmp = _tmpdir()
    hostile = ["\x00 nulls \x00", "lone \" quote", "x" * 50_000, "emoji 🎒🔥💰",
               "new\nlines\n\n\n   ", "", "a:b:c:d:e", "{not json}"]
    for i, h in enumerate(hostile):
        p = _write_text(tmp / f"insta_dm_{i}.txt", h)
        assert isinstance(_assert_no_raise(parse_dm_file, p), list)
        q = _write_text(tmp / f"reviews_{i}.csv",
                        "date,product,stars,review\n2024-09-10,Tote,5," + h.replace("\n", " ")[:200] + "\n")
        assert isinstance(_assert_no_raise(parse_reviews_csv, q), list)
    # Malformed JSON DM.
    bad_json = _write_text(tmp / "dm_bad.json", "{bad json [")
    assert isinstance(_assert_no_raise(parse_dm_file, bad_json), list)


def test_fuzz_supplier_image_hostile_never_raise():
    from omni_one.packs.seller_os import parse_supplier_image
    tmp = _tmpdir()
    for i, body in enumerate([b"", b"\x00\xff", b"no numbers here at all",
                              b"Total: ???", b"50 x x 4.00 $$ 200..00",
                              ("Tote 50 x 4.00 200.00\n" * 500).encode()]):
        p = _write_raw(tmp / f"supplier_{i}.txt", body)
        assert isinstance(_assert_no_raise(parse_supplier_image, p), list)


# ---------------------------------------------------------------------------
# 3. Money-parser fuzz (never NaN/inf; qty-prefix + date safety).
# ---------------------------------------------------------------------------


def _random_money_string(rng: random.Random) -> str:
    parts: list[str] = []
    # Optional date-like prefix (must be ignored).
    if rng.random() < 0.3:
        parts.append(rng.choice(["2024-09-12", "09/12/2024", "12/09/24", "2024/09/12"]))
    # Optional qty prefix ("50 x 4.00").
    if rng.random() < 0.3:
        parts.append(f"{rng.randint(1, 99)} x {rng.randint(1, 50)}.00")
    # 0-3 money tokens with random symbols/formats.
    for _ in range(rng.randint(0, 3)):
        sym = rng.choice(["$", "£", "€", "¥", "", "USD ", ""])
        num = rng.choice([
            f"{rng.randint(0, 9999)}",
            f"{rng.randint(0, 9999)}.{rng.randint(0, 99):02d}",
            f"{rng.randint(1, 9)},{rng.randint(100, 999)}.00",
            f"{rng.randint(0, 99)}.5",
            ".99" if rng.random() < 0.2 else f"{rng.randint(0, 500)}",
        ])
        parts.append(f"{sym}{num}")
    # Random word noise.
    if rng.random() < 0.4:
        parts.append(rng.choice(["Total", "Tote Bag", "Shipping", "fees", "xxx", "50%", "qty 2"]))
    sep = rng.choice([" ", "  ", " | ", ", ", " - "])
    s = sep.join(parts)
    if rng.random() < 0.1:
        s = "\ufeff" + s
    return s


def test_fuzz_money_never_nan_inf():
    from omni_one.packs.seller_parse import _money, _money_all, _money_last
    rng = random.Random(777)
    for i in range(3000):
        s = _random_money_string(rng)
        all_v = _assert_no_raise(_money_all, s)
        assert isinstance(all_v, list)
        _assert_all_finite(all_v, f"_money_all({s!r})")
        first = _assert_no_raise(_money, s)
        last = _assert_no_raise(_money_last, s)
        for v in (first, last):
            if v is not None:
                assert isinstance(v, float), f"{s!r} -> non-float {v!r}"
                assert math.isfinite(v), f"{s!r} -> non-finite {v!r}"
        if not all_v:
            assert first is None and last is None, f"{s!r}: empty but got {first}/{last}"
        else:
            assert first == all_v[0] and last == all_v[-1], f"{s!r}: first/last mismatch"
        _ = i


def test_fuzz_money_dates_ignored():
    """Date fragments must not leak into money values."""
    from omni_one.packs.seller_parse import _money_all, _money_last
    assert 2024.0 not in _money_all("Date: 2024-09-12 Total 160.00")
    assert _money_last("2024-09-12 Total $160.00") == 160.00
    assert _money_last("09/12/2024 $45.00") == 45.00


def test_fuzz_money_qty_prefix_last_wins():
    """'50 x 4.00 200.00' -> last=200.00 (line total, not qty 50)."""
    from omni_one.packs.seller_parse import _money, _money_last
    assert _money_last("Tote Bag Canvas 50 x 4.00 200.00") == 200.00
    assert _money("Tote Bag Canvas 50 x 4.00 200.00") == 50.0
    assert _money_last("$215.00") == 215.00
    assert _money_last("") is None
    assert _money_last("no numbers") is None


def test_fuzz_money_currency_symbols_finite():
    from omni_one.packs.seller_parse import _money_last
    for s, want in [("£45.00", 45.00), ("€22.50", 22.50), ("¥1000", 1000.0),
                    ("$1,234.56", 1234.56), ("USD 19.99", 19.99)]:
        got = _money_last(s)
        assert got is not None and abs(got - want) < 0.01, f"{s!r} -> {got!r}"


def test_fuzz_money_giant_and_tiny_strings():
    """Pathological lengths: huge field, empty, whitespace, nulls."""
    from omni_one.packs.seller_parse import _money_all, _money_last
    assert _money_last("") is None
    assert _money_last("   \t\n  ") is None
    assert _money_last("\x00\x00") is None
    big = "1.00 " * 20_000
    vals = _assert_no_raise(_money_all, big)
    assert len(vals) == 20_000
    _assert_all_finite(vals, "giant field")
    assert _money_last("$" + "9" * 300) is not None  # giant number still finite float


def test_fuzz_random_csv_roundtrip_never_raise():
    """Random sellers -> write CSV -> parse: row count preserved, no raise."""
    from omni_one.packs.seller_os import parse_orders_csv
    rng = random.Random(4242)
    tmp = _tmpdir()
    products = ["Tote Bag", "Mug ☕", "Print, with comma", 'Quote "Item"', "Café"]
    for trial in range(50):
        n = rng.randint(1, 20)
        p = tmp / f"shopify_trial_{trial}.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Order Name", "Created at", "Lineitem name",
                        "Lineitem quantity", "Lineitem price", "Total",
                        "Fees", "Shipping", "Customer"])
            for i in range(n):
                prod = rng.choice(products)
                qty = rng.randint(1, 5)
                unit = round(rng.uniform(5, 80), 2)
                w.writerow([f"#{i}", "2024-09-10", prod, qty, f"{unit:.2f}",
                            f"{round(unit * qty, 2):.2f}", "", "4.00", "Test"])
        events = _assert_no_raise(parse_orders_csv, p)
        assert len(events) == n, f"trial {trial}: wrote {n}, parsed {len(events)}"
        for e in events:
            gmv = e["metadata"]["gmv"]
            assert isinstance(gmv, (int, float)) and math.isfinite(gmv)


def test_fuzz_semicolon_and_bom_files_ingest():
    """Semicolon-delimited + BOM-header files ingest without raise."""
    from omni_one.packs.seller_os import ingest_seller_folder
    rng = random.Random(808)
    tmp = _tmpdir()
    shop = tmp / "semi_bom_shop"
    shop.mkdir()
    # Semicolon file (name must hint orders so ingest routes it correctly).
    with open(shop / "shopify_orders_semi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["order_id", "order_date", "product", "qty", "price",
                    "fees", "shipping", "buyer"])
        for i in range(6):
            w.writerow([f"S{i}", "2024-09-10", "Tote Bag", 1, "28.00",
                        "1.11", "4.00", "Alice"])
    # BOM file.
    with open(shop / "etsy_orders_bom.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "order_date", "product", "qty", "price",
                    "fees", "shipping", "buyer"])
        for i in range(4):
            w.writerow([f"B{i}", "2024-09-11", "Ceramic Mug", 2, "44.00",
                        "3.06", "3.00", "Bob"])
    (shop / "inventory.csv").write_text(
        "sku,product,stock,supplier\nTB001,Tote Bag,5,Acme\n", encoding="utf-8")
    events, report = _assert_no_raise(ingest_seller_folder, shop)
    n_orders = sum(1 for e in events if e["source"] == "orders")
    assert n_orders == 10, f"expected 10 orders, got {n_orders}: {report}"
    assert report["files_ingested"] >= 3
    _ = rng


def test_fuzz_inventory_variants_never_raise():
    """Inventory CSVs with junk stock cells never raise; qty coerces to int."""
    from omni_one.packs.seller_os import parse_inventory_csv
    tmp = _tmpdir()
    stocks = ["5", " 12 ", "3.0", "N/A", "", "ten", "1,000", "-4", "∞",
              "999999999999", "0", "  ", "$7", "7 units"]
    p = tmp / "inventory.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sku", "product", "stock", "supplier"])
        for i, s in enumerate(stocks):
            w.writerow([f"S{i}", f"Product {i}", s, "Acme"])
    events = _assert_no_raise(parse_inventory_csv, p)
    assert len(events) == len(stocks)
    for e in events:
        q = e["metadata"]["qty_on_hand"]
        assert isinstance(q, int) and math.isfinite(q), f"bad qty {q!r}"
