"""Connectors golden tests: shopify + etsy."""
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"


def _parse(name):
    from omni_one.connectors import parse_file
    return parse_file(FIX / name)


def test_shopify_basic_golden():
    ev = _parse("shopify_basic.csv")
    assert len(ev) == 3
    gmv = round(sum(e["metadata"]["gmv"] for e in ev), 2)
    fees = round(sum(e["metadata"]["fees"] for e in ev), 2)
    assert gmv == 123.00, gmv
    assert fees == 4.47, fees
    # canonical shape
    e0 = ev[0]
    assert set(["timestamp", "source", "entity_id", "value", "metadata"]) <= set(e0.keys())
    md = e0["metadata"]
    for k in ["source_file", "line", "signal", "product", "qty", "gmv", "fees",
              "shipping", "net", "customer", "status", "citation"]:
        assert k in md, k
    assert e0["source"] == "orders"
    assert md["signal"] == "order_gmv"
    assert md["product"] == "Tote Bag Handmade"
    assert md["qty"] == 2
    assert md["gmv"] == 56.00
    assert "shopify_basic.csv:2" in md["citation"]


def test_shopify_refund_negative():
    ev = _parse("shopify_refund.csv")
    assert len(ev) == 3
    sigs = [e["metadata"]["signal"] for e in ev]
    assert "order_refund" in sigs
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == -20.00
    assert refunds[0]["metadata"]["qty"] == -1
    assert refunds[0]["value"] == -20.00
    total = round(sum(e["metadata"]["gmv"] for e in ev), 2)
    assert total == 60.00, total


def test_shopify_currency_gbp():
    ev = _parse("shopify_gbp.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "GBP" for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 52.00


def test_shopify_semicolon_and_weird():
    ev = _parse("shopify_semicolon.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 74.00
    ev2 = _parse("shopify_weird_headers.csv")
    assert len(ev2) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev2), 2) == 70.00


def test_etsy_basic_golden():
    ev = _parse("etsy_basic.csv")
    assert len(ev) == 3
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 145.00
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 10.02


def test_etsy_refund_negative():
    ev = _parse("etsy_refund.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 2
    assert all(r["metadata"]["gmv"] < 0 for r in refunds)
    assert all(r["metadata"]["qty"] < 0 for r in refunds)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == -15.00


def test_etsy_eur_currency_and_ddmmyyyy():
    ev = _parse("etsy_eur.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 75.00
    # 15/09/2024 must parse as 15 Sep (DD/MM, day>12)
    assert ev[0]["timestamp"].day == 15
    assert ev[0]["timestamp"].month == 9


def test_idempotent_rerun_same_output():
    from omni_one.connectors import parse_file
    a = parse_file(FIX / "shopify_basic.csv")
    b = parse_file(FIX / "shopify_basic.csv")
    assert a == b
    c = parse_file(FIX / "etsy_basic.csv")
    d = parse_file(FIX / "etsy_basic.csv")
    assert c == d


def test_unknown_headers_no_crash():
    from omni_one.connectors import parse_file, parse_rows
    ev = parse_file(FIX / "unknown_headers.csv")
    assert ev == []
    # direct rows with unknown headers
    ev2 = parse_rows("shopify", [{"foo": "a", "bar": "b"}])
    assert ev2 == []
    ev3 = parse_rows("etsy", [{"zzz": "1"}])
    assert ev3 == []
    ev4 = parse_rows("nosuch", [{"Order ID": "1"}])
    assert ev4 == []


def test_detect_filename_and_header():
    from omni_one.connectors import detect
    assert detect(FIX / "shopify_basic.csv") == "shopify"
    assert detect(FIX / "etsy_basic.csv") == "etsy"
    assert detect(["Order Name", "Created at", "Lineitem name", "Total"]) == "shopify"
    assert detect({"foo": "a", "bar": "b"}) == "unknown"


def test_header_aliases_20plus():
    from omni_one.connectors import shopify, etsy
    assert len(shopify.HEADER_ALIASES) >= 20
    assert len(etsy.HEADER_ALIASES) >= 20


def test_date_parsing_variants():
    from omni_one.connectors._common import parse_date
    assert (parse_date("2024-09-10").year, parse_date("2024-09-10").month) == (2024, 9)
    assert parse_date("09/12/2024").month == 9 and parse_date("09/12/2024").day == 12
    assert parse_date("15/09/2024").day == 15
    assert parse_date("1710000000").year == 2024
    assert parse_date("1710000000000").year == 2024
