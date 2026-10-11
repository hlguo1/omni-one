"""Connectors golden tests: stripe/paypal/square/faire + payouts reconcile."""
from pathlib import Path

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"


def _parse(name):
    from omni_one.connectors import parse_file
    return parse_file(FIX / name)


def test_stripe_basic_golden():
    ev = _parse("stripe_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 50.00
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 2.05


def test_stripe_refund_negative():
    ev = _parse("stripe_refund.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == -20.00
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 10.00


def test_paypal_basic_and_eur():
    ev = _parse("paypal_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 50.00
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == 2.73
    ev2 = _parse("paypal_eur.csv")
    assert len(ev2) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev2)
    assert round(sum(e["metadata"]["gmv"] for e in ev2), 2) == 75.00


def test_square_basic_and_refund():
    ev = _parse("square_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 50.00
    ev2 = _parse("square_refund.csv")
    assert len(ev2) == 2
    refunds = [e for e in ev2 if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == -20.00


def test_faire_basic_zero_fees():
    ev = _parse("faire_basic.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 160.00
    assert all(e["metadata"]["fees"] == 0.0 for e in ev)


def test_reconcile_matched_unmatched_fee_delta():
    from omni_one.connectors.payouts import reconcile
    orders = _parse("shopify_basic.csv")  # 56,22,45 fees 4.47
    payouts = [
        {"order_id": "#1001", "amount": 56.00, "fees": 1.92},
        {"order_id": "#1002", "amount": 22.00, "fees": 0.94},
    ]
    r = reconcile(orders, payouts)
    assert r["matched"] == ["#1001", "#1002"], r
    assert r["unmatched"] == ["#1003"], r
    assert r["fee_delta"] == 1.61, r
    assert r["order_total"] == 123.00
    assert r["matched_count"] == 2 and r["unmatched_count"] == 1
    # empty safe
    r2 = reconcile([], [])
    assert r2["matched"] == [] and r2["fee_delta"] == 0.0
    # event-vs-event reconcile (amount match)
    payout_events = _parse("stripe_basic.csv")
    r3 = reconcile(payout_events, payout_events)
    assert r3["matched_count"] == 2
    assert r3["fee_delta"] == 0.0


def test_bom_and_epoch_dates():
    ev = _parse("bom_shopify.csv")
    assert len(ev) == 3
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == 123.00
    ev2 = _parse("epoch_dates.csv")
    assert len(ev2) == 3
    assert round(sum(e["metadata"]["gmv"] for e in ev2), 2) == 75.00
    # epoch rows parse to 2024
    assert ev2[0]["timestamp"].year == 2024
    assert ev2[1]["timestamp"].year == 2024


def test_idempotent_rerun_same_output():
    from omni_one.connectors import parse_file
    for f in ["stripe_basic.csv", "paypal_basic.csv", "square_basic.csv", "faire_basic.csv"]:
        assert parse_file(FIX / f) == parse_file(FIX / f), f


def test_unknown_headers_no_crash():
    from omni_one.connectors import parse_file, parse_rows
    assert parse_file(FIX / "unknown_headers.csv") == []
    for ch in ["stripe", "paypal", "square", "faire"]:
        assert parse_rows(ch, [{"unknown_col_xyz": "1"}]) == []


def test_detect_all_payout_channels():
    from omni_one.connectors import detect, CHANNELS
    assert detect(FIX / "stripe_basic.csv") == "stripe"
    assert detect(FIX / "paypal_basic.csv") == "paypal"
    assert detect(FIX / "square_basic.csv") == "square"
    assert detect(FIX / "faire_basic.csv") == "faire"
    assert set(CHANNELS.keys()) == {"shopify", "etsy", "amazon", "tiktok", "ebay",
                                    "woocommerce", "stripe", "paypal", "square", "faire"}
    for mod in CHANNELS.values():
        assert len(mod.HEADER_ALIASES) >= 20
