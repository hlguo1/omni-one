"""Connectors WAVE3-O golden tests: 30 new fixtures across 10 channels.

Coverage
--------
* 30 new fixtures in tests/fixtures/connectors/ (tiktok_eur ... multiline_quoted).
* Parametrized golden per fixture: row count, GMV sum, fee sum, currency set,
  refund count + refund sign (gmv<0, qty<0, signal == order_refund).
* Auto-detect channel correct for every new fixture (filename + header scoring).
* Malformed twins (truncated last line, latin-1 bytes) never raise.
* Idempotent double-parse identical.
* Unknown-headers file still 0 events, no raise.
* Payouts reconcile smoke on a stripe+paypal pair.

Conventions (match src/omni_one/connectors/*)
---------------------------------------------
* Canonical event: {timestamp, source, entity_id, value, metadata{...}}.
* metadata: source_file, line, signal, product, qty, gmv, fees, shipping, net,
  customer, status, citation, currency, channel, order_id.
* signal is order_gmv (positive) or order_refund (negative gmv + negative qty).
* Fees below are explicit per-row fee columns (no estimator involved) except
  where noted; faire fees are always 0.0 by design.
* EUR/GBP detection comes from EUR/GBP codes or euro/pound symbols in the row.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "connectors"

# (fixture, channel, n_events, gmv_sum, fee_sum, currencies, n_refunds)
GOLDEN = [
    ("tiktok_eur.csv", "tiktok", 3, 129.10, 7.37, {"EUR"}, 0),
    ("tiktok_weird_headers.csv", "tiktok", 2, 54.90, 3.35, {"USD"}, 0),
    ("amazon_de.csv", "amazon", 2, 69.70, 10.46, {"EUR"}, 0),
    ("amazon_jp_dates.csv", "amazon", 3, 47.00, 13.35, {"USD"}, 1),
    ("ebay_uk.csv", "ebay", 2, 55.00, 7.89, {"GBP"}, 0),
    ("ebay_promoted.csv", "ebay", 3, 99.00, 14.02, {"USD"}, 0),
    ("woo_eur.csv", "woocommerce", 2, 89.70, 3.20, {"EUR"}, 0),
    ("woo_refund_partial.csv", "woocommerce", 2, -4.10, 3.60, {"USD"}, 1),
    ("stripe_eur.csv", "stripe", 2, 84.40, 3.05, {"EUR"}, 0),
    ("stripe_dispute.csv", "stripe", 3, 105.00, 6.56, {"USD"}, 1),
    ("paypal_gbp.csv", "paypal", 2, 61.00, 3.11, {"GBP"}, 0),
    ("paypal_refund.csv", "paypal", 2, 15.00, 3.25, {"USD"}, 1),
    ("square_afterpay.csv", "square", 2, 76.00, 2.81, {"USD"}, 0),
    ("square_giftcard.csv", "square", 3, 90.00, 4.67, {"USD"}, 1),
    ("faire_net60.csv", "faire", 2, 320.00, 0.00, {"USD"}, 0),
    ("faire_eur.csv", "faire", 2, 240.00, 0.00, {"EUR"}, 0),
    ("shopify_pos.csv", "shopify", 3, 78.00, 3.16, {"USD"}, 0),
    ("shopify_duties.csv", "shopify", 2, 23.00, 3.71, {"EUR"}, 1),
    ("etsy_ads.csv", "etsy", 2, 83.00, 11.15, {"USD"}, 0),
    ("etsy_offsite.csv", "etsy", 2, 14.00, 8.47, {"USD"}, 1),
    ("amazon_fba_eu.csv", "amazon", 2, 64.70, 9.71, {"EUR"}, 0),
    ("tiktok_live.csv", "tiktok", 2, 39.90, 4.59, {"USD"}, 1),
    ("ebay_authenticity.csv", "ebay", 2, 35.00, 22.76, {"USD"}, 1),
    ("woo_subscription.csv", "woocommerce", 3, 60.00, 4.10, {"USD"}, 1),
    ("stripe_klarna.csv", "stripe", 2, 144.00, 4.78, {"USD"}, 0),
    ("paypal_freunde.csv", "paypal", 2, 69.70, 3.41, {"EUR"}, 0),
    ("square_cash.csv", "square", 2, 55.00, 2.20, {"USD"}, 0),
    ("faire_presale.csv", "faire", 3, 300.00, 0.00, {"USD"}, 1),
    ("mixed_currency.csv", "stripe", 3, 97.00, 3.72, {"USD", "EUR", "GBP"}, 0),
    ("multiline_quoted.csv", "shopify", 2, 60.00, 2.34, {"USD"}, 0),
]

NEW_FIXTURES = [g[0] for g in GOLDEN]


def _parse(name: str):
    from omni_one.connectors import parse_file

    return parse_file(FIX / name)


def _sums(events):
    gmv = round(sum(e["metadata"]["gmv"] for e in events), 2)
    fees = round(sum(e["metadata"]["fees"] for e in events), 2)
    return gmv, fees


# ---------------------------------------------------------------------------
# 1. parametrized golden per new fixture
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,channel,n,gmv,fees,currencies,n_refunds", GOLDEN,
    ids=[g[0] for g in GOLDEN],
)
def test_wave3_golden(name, channel, n, gmv, fees, currencies, n_refunds):
    """Golden: count, GMV sum, fee sum, currency set, refund count + signs."""
    ev = _parse(name)
    assert len(ev) == n, f"{name}: got {len(ev)} events"
    got_gmv, got_fees = _sums(ev)
    assert got_gmv == pytest.approx(gmv, abs=0.011), f"{name}: gmv {got_gmv}"
    assert got_fees == pytest.approx(fees, abs=0.011), f"{name}: fees {got_fees}"
    got_cur = {e["metadata"]["currency"] for e in ev}
    assert got_cur == currencies, f"{name}: currencies {got_cur}"
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == n_refunds, f"{name}: refunds {len(refunds)}"
    for r in refunds:
        assert r["metadata"]["gmv"] < 0, f"{name}: refund gmv not negative"
        assert r["metadata"]["qty"] < 0, f"{name}: refund qty not negative"
        assert r["value"] < 0, f"{name}: refund value not negative"
    for e in ev:
        if e["metadata"]["signal"] == "order_gmv":
            assert e["metadata"]["gmv"] > 0
            assert e["metadata"]["qty"] > 0
        assert e["metadata"]["channel"] == channel, f"{name}: channel tag"
        assert e["source"] == "orders"


@pytest.mark.parametrize(
    "name,channel,n,gmv,fees,currencies,n_refunds", GOLDEN,
    ids=[g[0] for g in GOLDEN],
)
def test_wave3_canonical_shape(name, channel, n, gmv, fees, currencies, n_refunds):
    """Every event keeps the canonical shape + citation points at file:line."""
    ev = _parse(name)
    assert ev, name
    for e in ev:
        assert set(["timestamp", "source", "entity_id", "value", "metadata"]) <= set(e.keys())
        md = e["metadata"]
        for k in ["source_file", "line", "signal", "product", "qty", "gmv",
                  "fees", "shipping", "net", "customer", "status", "citation",
                  "currency", "channel", "order_id"]:
            assert k in md, f"{name}: missing {k}"
        assert md["source_file"] == name
        assert f"[{name}:{md['line']}]" in md["citation"]
        assert md["net"] == pytest.approx(round(md["gmv"] - md["fees"] - md["shipping"], 2))


# ---------------------------------------------------------------------------
# 2. auto-detect channel correct for each new fixture
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,channel,n,gmv,fees,currencies,n_refunds", GOLDEN,
    ids=[g[0] for g in GOLDEN],
)
def test_wave3_detect(name, channel, n, gmv, fees, currencies, n_refunds):
    """detect() resolves the right channel from path + headers."""
    from omni_one.connectors import detect

    assert detect(FIX / name) == channel, name


def test_wave3_detect_header_lists():
    """Header-only detection (no filename hint) still resolves channels."""
    from omni_one.connectors import detect

    assert detect(["Charge ID", "Created (UTC)", "Statement Descriptor", "Amount"]) == "stripe"
    assert detect(["Order Name", "Created at", "Lineitem name", "Total"]) == "shopify"
    assert detect(["order-id", "purchase-date", "product-name", "quantity"]) == "amazon"
    assert detect(["TikTok Order ID", "Order Created Time", "Seller SKU"]) == "tiktok"
    assert detect(["Order number", "Sale date", "Item title", "Sold price"]) == "ebay"
    assert detect(["Order ID", "Order Date", "Billing Email", "Coupon"]) == "woocommerce"
    assert detect(["Date", "Transaction ID", "From Email", "Gross"]) == "paypal"
    assert detect(["Transaction ID", "Gross Sales", "Tender", "Total Collected"]) == "square"
    assert detect(["Order ID", "Wholesale Price", "Retail Price", "Retailer"]) == "faire"
    # mixed_currency / multiline_quoted carry no filename hint but resolve via headers
    assert detect(FIX / "mixed_currency.csv") == "stripe"
    assert detect(FIX / "multiline_quoted.csv") == "shopify"


# ---------------------------------------------------------------------------
# 3. per-fixture detail goldens (tiktok family)
# ---------------------------------------------------------------------------

def test_tiktok_eur_detail():
    ev = _parse("tiktok_eur.csv")
    assert [e["metadata"]["product"] for e in ev] == ["Canvas Tote", "Ceramic Mug", "Botanical Print"]
    assert [e["metadata"]["qty"] for e in ev] == [2, 1, 3]
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert ev[0]["metadata"]["customer"] == "Anna Müller"
    assert ev[0]["metadata"]["gmv"] == pytest.approx(59.90)


def test_tiktok_weird_headers_aliases():
    """Weird-but-aliased headers (Variation/SKU Price/Service Fee/State) parse."""
    ev = _parse("tiktok_weird_headers.csv")
    assert len(ev) == 2
    assert ev[0]["metadata"]["product"] == "Tote Bag, Large Canvas"
    assert ev[1]["metadata"]["product"] == "Mug, Speckled Stoneware"
    # SKU Price (unit) x qty reconciles with Order Amount totals
    assert ev[1]["metadata"]["gmv"] == pytest.approx(25.00)
    assert ev[1]["metadata"]["qty"] == 2
    assert ev[0]["metadata"]["customer"] == "Alice"


def test_tiktok_live_cancelled_refund():
    ev = _parse("tiktok_live.csv")
    assert len(ev) == 2
    refund = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refund) == 1
    assert refund[0]["metadata"]["gmv"] == pytest.approx(-19.90)
    assert refund[0]["metadata"]["qty"] == -1
    assert refund[0]["metadata"]["product"] == "LIVE Flash Mug"
    good = [e for e in ev if e["metadata"]["signal"] == "order_gmv"][0]
    assert good["metadata"]["gmv"] == pytest.approx(59.80)
    assert good["metadata"]["qty"] == 2


# ---------------------------------------------------------------------------
# 4. per-fixture detail goldens (amazon family)
# ---------------------------------------------------------------------------

def test_amazon_de_bom_semicolon_eur():
    """BOM + semicolon delimiter + euro amounts parse cleanly."""
    raw = (FIX / "amazon_de.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "fixture must keep its BOM"
    ev = _parse("amazon_de.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert ev[0]["metadata"]["product"] == "Segeltuchtasche"
    assert ev[0]["metadata"]["gmv"] == pytest.approx(29.90)
    assert ev[0]["metadata"]["fees"] == pytest.approx(4.49)
    assert round(sum(e["metadata"]["shipping"] for e in ev), 2) == pytest.approx(7.80)


def test_amazon_jp_dates_and_cancel():
    """Japanese date variants (slash, dots, DD/MM) + Cancelled row."""
    ev = _parse("amazon_jp_dates.csv")
    assert len(ev) == 3
    assert (ev[0]["timestamp"].year, ev[0]["timestamp"].month, ev[0]["timestamp"].day) == (2024, 9, 10)
    assert ev[0]["timestamp"].hour == 14
    assert (ev[1]["timestamp"].month, ev[1]["timestamp"].day) == (9, 11)
    # 15/09/2024 parses DD/MM (day > 12)
    assert ev[2]["timestamp"].day == 15
    assert ev[2]["timestamp"].month == 9
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-21.00)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(47.00)


def test_amazon_fba_eu_detail():
    ev = _parse("amazon_fba_eu.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(64.70)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(9.71)
    assert ev[0]["metadata"]["qty"] == 1
    assert ev[1]["metadata"]["qty"] == 2


# ---------------------------------------------------------------------------
# 5. per-fixture detail goldens (ebay family)
# ---------------------------------------------------------------------------

def test_ebay_uk_semicolon_gbp():
    ev = _parse("ebay_uk.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "GBP" for e in ev)
    assert ev[0]["metadata"]["gmv"] == pytest.approx(27.00)
    assert ev[1]["metadata"]["gmv"] == pytest.approx(28.00)
    assert ev[0]["metadata"]["customer"] == "alice_uk"
    assert round(sum(e["metadata"]["shipping"] for e in ev), 2) == pytest.approx(6.00)


def test_ebay_promoted_detail():
    ev = _parse("ebay_promoted.csv")
    assert len(ev) == 3
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(99.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(14.02)
    assert all(e["metadata"]["signal"] == "order_gmv" for e in ev)


def test_ebay_authenticity_return():
    ev = _parse("ebay_authenticity.csv")
    assert len(ev) == 2
    # 'Authenticated' is NOT a refund trigger; 'Return started' is.
    good = [e for e in ev if e["metadata"]["signal"] == "order_gmv"]
    bad = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(good) == 1 and len(bad) == 1
    assert good[0]["metadata"]["product"] == "Designer Tote"
    assert bad[0]["metadata"]["gmv"] == pytest.approx(-85.00)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(35.00)


# ---------------------------------------------------------------------------
# 6. per-fixture detail goldens (woo family)
# ---------------------------------------------------------------------------

def test_woo_eur_semicolon():
    ev = _parse("woo_eur.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(89.70)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(3.20)
    assert round(sum(e["metadata"]["shipping"] for e in ev), 2) == pytest.approx(9.80)
    assert ev[0]["metadata"]["customer"] == "anna@example.de"


def test_woo_refund_partial_sign():
    ev = _parse("woo_refund_partial.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-64.00)
    assert refunds[0]["metadata"]["qty"] == -2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(-4.10)


def test_woo_subscription_failed_renewal():
    ev = _parse("woo_subscription.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-25.00)
    assert refunds[0]["metadata"]["customer"] == "bob@example.com"
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(60.00)


# ---------------------------------------------------------------------------
# 7. per-fixture detail goldens (stripe family)
# ---------------------------------------------------------------------------

def test_stripe_eur_detail():
    ev = _parse("stripe_eur.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert ev[0]["metadata"]["gmv"] == pytest.approx(59.90)
    assert ev[0]["metadata"]["customer"] == "anna@example.de"


def test_stripe_dispute_detail():
    ev = _parse("stripe_dispute.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-45.00)
    assert refunds[0]["metadata"]["status"] == "disputed"
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(105.00)


def test_stripe_klarna_detail():
    ev = _parse("stripe_klarna.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(144.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(4.78)
    assert all(e["metadata"]["signal"] == "order_gmv" for e in ev)


# ---------------------------------------------------------------------------
# 8. per-fixture detail goldens (paypal family)
# ---------------------------------------------------------------------------

def test_paypal_gbp_detail():
    ev = _parse("paypal_gbp.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "GBP" for e in ev)
    assert ev[0]["metadata"]["gmv"] == pytest.approx(34.00)
    assert ev[0]["metadata"]["customer"] == "alice@example.co.uk"


def test_paypal_refund_detail():
    ev = _parse("paypal_refund.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-25.00)
    assert refunds[0]["metadata"]["customer"] == "Bob Jones"
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(15.00)


def test_paypal_freunde_unicode():
    """Unicode product + customer names survive UTF-8 parsing."""
    ev = _parse("paypal_freunde.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    customers = [e["metadata"]["customer"] for e in ev]
    assert "Jürgen Müller" in customers
    assert any("O’Brien" in c for c in customers)
    assert any("für Freunde" in e["metadata"]["product"] for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(69.70)


# ---------------------------------------------------------------------------
# 9. per-fixture detail goldens (square family)
# ---------------------------------------------------------------------------

def test_square_afterpay_detail():
    ev = _parse("square_afterpay.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(76.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(2.81)
    assert ev[1]["metadata"]["qty"] == 2


def test_square_giftcard_partial_refund():
    """Gift-card redemption rows stay sales; 'Partial refund issued' flips."""
    ev = _parse("square_giftcard.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-20.00)
    assert refunds[0]["metadata"]["product"] == "Gift Card Partial Refund"
    good = sorted(e["metadata"]["gmv"] for e in ev if e["metadata"]["signal"] == "order_gmv")
    assert good == pytest.approx([50.00, 60.00])
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(90.00)


def test_square_cash_detail():
    ev = _parse("square_cash.csv")
    assert len(ev) == 2
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(55.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(2.20)
    assert ev[0]["metadata"]["customer"] == "Walk-in"


# ---------------------------------------------------------------------------
# 10. per-fixture detail goldens (faire family)
# ---------------------------------------------------------------------------

def test_faire_net60_zero_fees():
    """Faire wholesale: fees always 0.0, Net-60 terms do not trigger refunds."""
    ev = _parse("faire_net60.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["fees"] == 0.0 for e in ev)
    assert all(e["metadata"]["signal"] == "order_gmv" for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(320.00)
    qtys = sorted(e["metadata"]["qty"] for e in ev)
    assert qtys == [6, 10]


def test_faire_eur_detail():
    ev = _parse("faire_eur.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    assert all(e["metadata"]["fees"] == 0.0 for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(240.00)
    assert any("toile" in e["metadata"]["product"] for e in ev)


def test_faire_presale_cancelled():
    ev = _parse("faire_presale.csv")
    assert len(ev) == 3
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-100.00)
    assert refunds[0]["metadata"]["qty"] == -5
    assert all(e["metadata"]["fees"] == 0.0 for e in ev)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(300.00)


# ---------------------------------------------------------------------------
# 11. per-fixture detail goldens (shopify / etsy)
# ---------------------------------------------------------------------------

def test_shopify_pos_detail():
    ev = _parse("shopify_pos.csv")
    assert len(ev) == 3
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(78.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(3.16)
    assert ev[0]["metadata"]["order_id"] == "#POS-1001"
    assert ev[0]["timestamp"].hour == 11


def test_shopify_duties_refund_eur():
    ev = _parse("shopify_duties.csv")
    assert len(ev) == 2
    assert all(e["metadata"]["currency"] == "EUR" for e in ev)
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-42.00)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(23.00)
    assert round(sum(e["metadata"]["shipping"] for e in ev), 2) == pytest.approx(17.00)


def test_etsy_ads_fee_heavy():
    """Offsite-ads style fees are taken as-is (no re-estimate)."""
    ev = _parse("etsy_ads.csv")
    assert len(ev) == 2
    assert ev[0]["metadata"]["fees"] == pytest.approx(8.10)
    assert ev[1]["metadata"]["fees"] == pytest.approx(3.05)
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(83.00)


def test_etsy_offsite_returned():
    ev = _parse("etsy_offsite.csv")
    assert len(ev) == 2
    refunds = [e for e in ev if e["metadata"]["signal"] == "order_refund"]
    assert len(refunds) == 1
    assert refunds[0]["metadata"]["gmv"] == pytest.approx(-22.00)
    assert refunds[0]["metadata"]["customer"] == "Heidi"
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(14.00)


# ---------------------------------------------------------------------------
# 12. mixed currency + multiline special files
# ---------------------------------------------------------------------------

def test_mixed_currency_per_row():
    """One file, three row-level currencies (USD/EUR/GBP)."""
    ev = _parse("mixed_currency.csv")
    assert len(ev) == 3
    by_customer = {e["metadata"]["customer"]: e["metadata"]["currency"] for e in ev}
    assert by_customer == {"Alice": "USD", "Chloé": "EUR", "Oliver": "GBP"}
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(97.00)
    assert round(sum(e["metadata"]["fees"] for e in ev), 2) == pytest.approx(3.72)


def test_multiline_quoted_fields():
    """Quoted fields with embedded newlines + commas stay one row each.

    Note: read_csv_rows splits on physical lines, so the embedded newline is
    consumed (not preserved) — but rows must NOT misalign: still 2 events
    with both name fragments and exact money.
    """
    raw = (FIX / "multiline_quoted.csv").read_bytes().decode("utf-8")
    assert '"Tote Bag\nLarge Canvas, Natural"' in raw
    ev = _parse("multiline_quoted.csv")
    assert len(ev) == 2
    assert "Tote Bag" in ev[0]["metadata"]["product"]
    assert "Large Canvas, Natural" in ev[0]["metadata"]["product"]
    assert "Speckled" in ev[1]["metadata"]["product"] and "Stoneware (Blue)" in ev[1]["metadata"]["product"]
    assert round(sum(e["metadata"]["gmv"] for e in ev), 2) == pytest.approx(60.00)
    assert ev[1]["metadata"]["qty"] == 2


def test_special_format_counts():
    """At least 4 fixtures exercise BOM/semicolon/quoted-multiline/unicode."""
    specials = ["amazon_de.csv", "ebay_uk.csv", "woo_eur.csv",
                "tiktok_weird_headers.csv", "multiline_quoted.csv",
                "paypal_freunde.csv"]
    assert (FIX / "amazon_de.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    for name in specials:
        ev = _parse(name)
        assert len(ev) >= 2, name


def test_non_usd_and_refund_coverage():
    """Suite-level: >=6 non-USD fixtures, >=8 with refunds/disputes."""
    non_usd = [g[0] for g in GOLDEN if g[5] != {"USD"}]
    assert len(non_usd) >= 6, non_usd
    with_refunds = [g[0] for g in GOLDEN if g[6] > 0]
    assert len(with_refunds) >= 8, with_refunds


# ---------------------------------------------------------------------------
# 13. malformed twins never raise (truncate last line, latin-1 bytes)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_wave3_truncated_twin_no_raise(tmp_path, name):
    """Cutting the file mid-last-line must not raise; yields a list."""
    from omni_one.connectors import parse_file

    raw = (FIX / name).read_bytes()
    cut = raw[: max(0, len(raw) - 17)]  # slice inside the final row
    twin = tmp_path / name
    twin.write_bytes(cut)
    try:
        out = parse_file(twin)
    except Exception as exc:  # pragma: no cover - must never happen
        pytest.fail(f"{name}: truncated twin raised {exc!r}")
    assert isinstance(out, list)


@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_wave3_latin1_twin_no_raise(tmp_path, name):
    """Latin-1 encoded bytes must not raise; yields a list."""
    from omni_one.connectors import parse_file

    raw = (FIX / name).read_bytes()
    blob = raw.decode("utf-8-sig", errors="replace").encode("latin-1", errors="replace")
    twin = tmp_path / name
    twin.write_bytes(blob)
    try:
        out = parse_file(twin)
    except Exception as exc:  # pragma: no cover - must never happen
        pytest.fail(f"{name}: latin-1 twin raised {exc!r}")
    assert isinstance(out, list)


def test_wave3_garbage_bytes_no_raise(tmp_path):
    """Random binary content is not a valid ledger: [] and no raise."""
    from omni_one.connectors import parse_file

    for i, name in enumerate(NEW_FIXTURES[:6]):
        twin = tmp_path / f"stripe_garbage_{i}.csv"
        twin.write_bytes(bytes([0x93, 0xFA, 0x00, 0x13, 0x7F, 0xC3, 0x28] * 40))
        assert parse_file(twin) == []


# ---------------------------------------------------------------------------
# 14. idempotent double-parse identical
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", NEW_FIXTURES)
def test_wave3_idempotent(name):
    from omni_one.connectors import parse_file

    first = parse_file(FIX / name)
    second = parse_file(FIX / name)
    assert first == second
    assert first is not second


# ---------------------------------------------------------------------------
# 15. unknown headers still 0 events, no raise
# ---------------------------------------------------------------------------

def test_wave3_unknown_headers_file():
    from omni_one.connectors import parse_file, parse_rows

    assert parse_file(FIX / "unknown_headers.csv") == []
    for ch in ["shopify", "etsy", "amazon", "tiktok", "ebay",
               "woocommerce", "stripe", "paypal", "square", "faire"]:
        assert parse_rows(ch, [{"foo": "a", "bar": "b", "baz": "c"}]) == [], ch
    assert parse_rows("nosuch", [{"Order ID": "1"}]) == []


def test_wave3_empty_and_header_only_no_raise(tmp_path):
    from omni_one.connectors import parse_file

    empty = tmp_path / "stripe_empty.csv"
    empty.write_text("")
    assert parse_file(empty) == []
    header_only = tmp_path / "paypal_header_only.csv"
    header_only.write_text("Date,Transaction ID,Item Title,Quantity,Gross\n")
    assert parse_file(header_only) == []


# ---------------------------------------------------------------------------
# 16. payouts reconcile smoke on stripe+paypal pair
# ---------------------------------------------------------------------------

def test_wave3_reconcile_stripe_paypal_smoke():
    """Reconcile stripe orders against paypal payouts: shape + totals sane."""
    from omni_one.connectors.payouts import reconcile

    stripe_orders = _parse("stripe_dispute.csv")   # 120, -45, 30
    paypal_payouts = _parse("paypal_refund.csv")   # 40, -25
    res = reconcile(stripe_orders, paypal_payouts)
    assert set(["matched", "unmatched", "fee_delta", "order_total",
                "payout_total", "order_fees", "payout_fees",
                "matched_count", "unmatched_count"]) <= set(res.keys())
    assert res["matched_count"] + res["unmatched_count"] == len(stripe_orders)
    assert res["order_total"] == pytest.approx(105.00)
    assert res["payout_total"] == pytest.approx(15.00)
    assert res["order_fees"] == pytest.approx(6.56)
    assert res["payout_fees"] == pytest.approx(3.25)
    assert res["fee_delta"] == pytest.approx(3.31)


def test_wave3_reconcile_self_match_and_empty():
    from omni_one.connectors.payouts import reconcile

    stripe_orders = _parse("stripe_klarna.csv")
    res = reconcile(stripe_orders, stripe_orders)
    assert res["matched_count"] == 2
    assert res["unmatched_count"] == 0
    assert res["fee_delta"] == pytest.approx(0.00)
    blank = reconcile([], [])
    assert blank["matched"] == [] and blank["unmatched"] == []
    assert blank["fee_delta"] == pytest.approx(0.00)
    # raw-row payouts also accepted (never raises)
    raw = [{"order_id": "ch_k1", "amount": 89.00, "fees": 2.88}]
    res2 = reconcile(stripe_orders, raw)
    assert res2["matched"] == ["ch_k1"]
    assert res2["unmatched"] == ["ch_k2"]


def test_wave3_cross_channel_amount_match():
    """Same-amount payouts match across channels (abs comparison for refunds)."""
    from omni_one.connectors.payouts import reconcile

    paypal_orders = _parse("paypal_refund.csv")  # 40.00, -25.00
    square_orders = _parse("square_cash.csv")    # 40.00, 15.00
    res = reconcile(paypal_orders, square_orders)
    # 40.00 matches by amount; -25.00 has no counterpart
    assert res["matched_count"] == 1
    assert res["unmatched_count"] == 1


# ---------------------------------------------------------------------------
# 17. suite-wide invariants across all 30 new fixtures
# ---------------------------------------------------------------------------

def test_wave3_entity_ids_unique_per_file():
    """entity_id order:{channel}:{oid}:{line} must be unique within a file."""
    for name in NEW_FIXTURES:
        ev = _parse(name)
        ids = [e["entity_id"] for e in ev]
        assert len(set(ids)) == len(ids), name
        for e in ev:
            assert e["entity_id"].startswith("order:"), name


def test_wave3_value_matches_signed_gmv():
    """Top-level value always equals signed metadata gmv."""
    for name in NEW_FIXTURES:
        for e in _parse(name):
            assert e["value"] == pytest.approx(e["metadata"]["gmv"]), name


def test_wave3_fees_never_exceed_gmv():
    """Explicit fee columns stay below their row GMV (square guard safe)."""
    for name in NEW_FIXTURES:
        for e in _parse(name):
            assert e["metadata"]["fees"] >= 0, name
            assert e["metadata"]["fees"] < abs(e["metadata"]["gmv"]), name


def test_wave3_faire_fees_always_zero():
    """Faire wholesale logs commission off-platform: fees 0 on every row."""
    for name in ["faire_net60.csv", "faire_eur.csv", "faire_presale.csv"]:
        for e in _parse(name):
            assert e["metadata"]["fees"] == 0.0, name
            assert e["metadata"]["channel"] == "faire", name


def test_wave3_timestamps_in_2024():
    """All wave3 rows are Sep 2024 shop data (no DEFAULT_TS leakage)."""
    for name in NEW_FIXTURES:
        for e in _parse(name):
            ts = e["timestamp"]
            assert (ts.year, ts.month) == (2024, 9), f"{name}: {ts}"


def test_wave3_line_numbers_monotonic():
    """metadata.line starts at 2 and increases (file:line citations audit)."""
    for name in NEW_FIXTURES:
        lines = [e["metadata"]["line"] for e in _parse(name)]
        assert lines[0] >= 2, name
        assert lines == sorted(lines), name


def test_wave3_thirty_new_plus_existing():
    """30 new fixtures land next to the 28 existing ones (58 total)."""
    all_csv = sorted(FIX.glob("*.csv"))
    assert len(all_csv) >= 58, len(all_csv)
    for name in NEW_FIXTURES:
        assert (FIX / name).exists(), name
        assert (FIX / name).stat().st_size > 0, name


def test_wave3_row_counts_two_to_six():
    """Every new fixture holds 2-6 data rows (real-world slice, not dump)."""
    import csv as _csv

    for name, _ch, n, _gmv, _fees, _cur, _nr in GOLDEN:
        assert 2 <= n <= 6, name
        with open(FIX / name, encoding="utf-8-sig", newline="") as f:
            rows = list(_csv.reader(f, delimiter=";" if name in
                                     {"amazon_de.csv", "ebay_uk.csv", "woo_eur.csv"} else ","))
        assert len(rows) - 1 >= 2, name  # header + >=2 data rows


def test_wave3_parse_rows_dispatch_per_channel():
    """parse_rows dispatches first-row dicts to the right channel module."""
    from omni_one.connectors import parse_rows
    from omni_one.connectors._common import read_csv_rows

    for name, channel, n, _gmv, _fees, _cur, _nr in GOLDEN:
        _fns, rows = read_csv_rows(FIX / name)
        out = parse_rows(channel, rows, source_file=name)
        assert len(out) == n, f"{name} via {channel}"
        assert all(e["metadata"]["channel"] == channel for e in out)


def test_wave3_channel_alias_tables_large():
    """All 10 channel modules keep >=20 header aliases (weird headers safe)."""
    from omni_one.connectors import CHANNELS

    assert set(CHANNELS.keys()) == {"shopify", "etsy", "amazon", "tiktok", "ebay",
                                    "woocommerce", "stripe", "paypal", "square", "faire"}
    for ch, mod in CHANNELS.items():
        assert len(mod.HEADER_ALIASES) >= 20, ch


def test_wave3_suite_money_totals():
    """Sanity: wave3 GMV is positive overall; refunds are a small slice."""
    total_gmv = 0.0
    total_refund = 0.0
    for name in NEW_FIXTURES:
        for e in _parse(name):
            g = e["metadata"]["gmv"]
            total_gmv += g
            if e["metadata"]["signal"] == "order_refund":
                total_refund += g
    assert total_gmv > 1000, total_gmv
    assert total_refund < 0, total_refund
    assert abs(total_refund) < total_gmv * 0.25, (total_refund, total_gmv)
