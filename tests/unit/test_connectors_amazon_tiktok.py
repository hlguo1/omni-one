"""Connectors golden tests: amazon + tiktok."""
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"


def _parse(name):
    from omni_one.connectors import parse_file
    return parse_file(FIX / name)


def test_amazon_basic_golden():
    ev = _parse("amazon_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 74.00
    # 15% referral + 3.99 FBA guess each
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 19.08
    assert ev[0]["metadata"]["product"] == "Tote Bag"


def test_amazon_fba_fee_heuristic():
    ev = _parse("amazon_fba.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 50.00
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 15.48
    # per-row: 30 -> 8.49, 20 -> 6.99
    fees = sorted(e["metadata"]["fees"] for e in ev)
    assert fees == [6.99, 8.49], fees


def test_amazon_refund_negative():
    ev = _parse("amazon_refund.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 2
    assert all(r["metadata"]["gmv"] < 0 for r in refunds)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == -15.00


def test_tiktok_basic_golden():
    ev = _parse("tiktok_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 70.00
    # 5% + 30c: 30->1.80, 40->2.30
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 4.10


def test_tiktok_refund_negative():
    ev = _parse("tiktok_refund.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == -20.00
    assert refunds[0]["metadata"]["qty"] == -1
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 10.00


def test_currency_defaults_usd():
    ev = _parse("amazon_basic.csv")
    assert all(e["metadata"]["currency"] == "USD" for e in ev)
    ev2 = _parse("tiktok_basic.csv")
    assert all(e["metadata"]["currency"] == "USD" for e in ev2)


def test_idempotent_rerun_same_output():
    from omni_one.connectors import parse_file
    assert parse_file(FIX / "amazon_basic.csv") == parse_file(FIX / "amazon_basic.csv")
    assert parse_file(FIX / "tiktok_refund.csv") == parse_file(FIX / "tiktok_refund.csv")


def test_unknown_headers_no_crash():
    from omni_one.connectors import parse_file, parse_rows
    assert parse_file(FIX / "unknown_headers.csv") == []
    assert parse_rows("amazon", [{"foo": "x"}]) == []
    assert parse_rows("tiktok", [{"bar": "y", "baz": "z"}]) == []


def test_detect_amazon_tiktok():
    from omni_one.connectors import detect
    assert detect(FIX / "amazon_basic.csv") == "amazon"
    assert detect(FIX / "tiktok_basic.csv") == "tiktok"
    assert detect(FIX / "amazon_fba.csv") == "amazon"


def test_header_aliases_20plus():
    from omni_one.connectors import amazon, tiktok
    assert len(amazon.HEADER_ALIASES) >= 20
    assert len(tiktok.HEADER_ALIASES) >= 20


def test_date_epoch_and_iso():
    from omni_one.connectors._common import parse_date
    assert parse_date("1710000000").year == 2024
    assert parse_date("1710000000000").year == 2024
    assert parse_date("2024-09-10").day == 10
    assert parse_date("2024-09-10 12:00:00").hour == 12
