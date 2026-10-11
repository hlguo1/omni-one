"""Connectors golden tests: ebay + woocommerce."""
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"


def _parse(name):
    from omni_one.connectors import parse_file
    return parse_file(FIX / name)


def test_ebay_basic_golden():
    ev = _parse("ebay_basic.csv")
    assert len(ev) == 2
    # Total price 34 + 23
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 57.00
    # 13.25% + 30c: 34->4.80, 23->3.35
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 8.15


def test_ebay_refund_negative():
    ev = _parse("ebay_refund.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == -20.00
    assert refunds[0]["metadata"]["qty"] == -1
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 10.00


def test_woo_basic_golden():
    ev = _parse("woo_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 70.00
    # 2.9% + 30c: 30->1.17, 40->1.46
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 2.63


def test_woo_semicolon_delimiter():
    ev = _parse("woo_semicolon.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 50.00
    from omni_one.connectors import detect
    assert detect(FIX / "woo_semicolon.csv") == "woocommerce"


def test_currency_usd():
    assert all(e["metadata"]["currency"] == "USD" for e in _parse("ebay_basic.csv"))
    assert all(e["metadata"]["currency"] == "USD" for e in _parse("woo_basic.csv"))


def test_idempotent_rerun_same_output():
    from omni_one.connectors import parse_file
    assert parse_file(FIX / "ebay_basic.csv") == parse_file(FIX / "ebay_basic.csv")
    assert parse_file(FIX / "woo_basic.csv") == parse_file(FIX / "woo_basic.csv")


def test_unknown_headers_no_crash():
    from omni_one.connectors import parse_file, parse_rows
    assert parse_file(FIX / "unknown_headers.csv") == []
    assert parse_rows("ebay", [{"nope": "1"}]) == []
    assert parse_rows("woocommerce", [{"a": "b", "c": "d"}]) == []


def test_detect_ebay_woo():
    from omni_one.connectors import detect
    assert detect(FIX / "ebay_basic.csv") == "ebay"
    assert detect(FIX / "woo_basic.csv") == "woocommerce"


def test_header_aliases_20plus():
    from omni_one.connectors import ebay, woocommerce
    assert len(ebay.HEADER_ALIASES) >= 20
    assert len(woocommerce.HEADER_ALIASES) >= 20


def test_canonical_shape_ebay():
    ev = _parse("ebay_basic.csv")
    md = ev[0]["metadata"]
    for k in ["source_file", "line", "signal", "product", "qty", "gmv", "fees",
              "shipping", "net", "customer", "status", "citation"]:
        assert k in md, k
    assert ev[0]["source"] == "orders"
