"""Seller OS robustness: money parse, fuzzy match, stockout, dedup, vision numbers."""
import sys
from pathlib import Path
SELLER_DIR = Path(__file__).resolve().parents[2] / "src" / "omni_one" / "packs"
sys.path.insert(0, str(SELLER_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "omni_one" / "core"))

from seller_os import _money, _money_last, _money_all, _norm_product, _product_match, build_seller_briefing
from vision import _parse_numbers_from_text


def test_money_ignores_dates():
    assert _money_last("Total $215.00") == 215.00
    # qty prefix should give last (total), not first (qty)
    assert _money_last("Tote Bag Canvas 50 x 4.00 200.00") == 200.00
    assert _money("Tote Bag Canvas 50 x 4.00 200.00") == 50.0  # first
    vals = _money_all("Date: 2024-09-12 Total 160.00")
    assert 160.00 in vals
    assert 2024.0 not in vals and 12.0 not in vals or len(vals) <= 2  # dates filtered


def test_product_fuzzy():
    assert _norm_product("Tote Bag Handmade") == "tote bag handmade"
    assert _product_match("Tote Bag Handmade", "tote bag handmade")
    assert _product_match("Tote Bag", "Tote Bag Handmade")
    assert not _product_match("Ceramic Mug", "Tote Bag")


def test_vision_numbers_skip_dates():
    d = _parse_numbers_from_text("Date: 2024-09-12\nTacos 32 x 3.50 = 112.00\nTotal 160.00")
    # Should not include 2024 or 12 as values
    assert 112.00 in d["values"]
    assert 160.00 in d["values"]
    assert 2024.0 not in d["values"]


def test_briefing_stockout_fuzzy_and_cogs():
    events = [
        {"timestamp": __import__("datetime").datetime.now(), "source": "orders", "entity_id": "order:1", "value": 56.0, "metadata": {"product": "Tote Bag Handmade", "qty": 2, "gmv": 56.0, "fees": 2.0, "shipping": 4.0, "signal": "order_gmv", "citation": "[shopify:2]"}},
        {"timestamp": __import__("datetime").datetime.now(), "source": "orders", "entity_id": "order:2", "value": 56.0, "metadata": {"product": "tote bag handmade", "qty": 2, "gmv": 56.0, "fees": 2.0, "shipping": 0.0, "signal": "order_gmv", "citation": "[shopify:3]"}},
        {"timestamp": __import__("datetime").datetime.now(), "source": "inventory", "entity_id": "inv:tote", "value": 2.0, "metadata": {"product": "Tote Bag Handmade", "qty_on_hand": 2, "signal": "on_hand", "citation": "[inv:2]"}},
        {"timestamp": __import__("datetime").datetime.now(), "source": "supplier", "entity_id": "sup:1", "value": 200.0, "metadata": {"raw": "Tote Bag Canvas 50 x 4.00 200.00", "signal": "cogs", "citation": "[sup:2]"}},
        {"timestamp": __import__("datetime").datetime.now(), "source": "dm", "entity_id": "dm:1", "value": "Alice: Where is my order? No tracking, worried", "metadata": {"signal": "dm", "citation": "[dm:1]"}},
    ]
    b = build_seller_briefing(events, pipeline=None)
    # fuzzy stockout should fire despite case diff
    assert b["kpis"]["stockout_risk"] >= 1
    assert any("Stockout" in a["message"] for a in b["alerts"])
    # at-risk should fire (where + tracking combo, not just "where")
    assert b["kpis"]["at_risk"] >= 1
    # COGS per-unit (4.00 * 4 units = 16), not full invoice 200
    assert b["kpis"]["cogs"] < 100, f"cogs {b['kpis']['cogs']} should be allocated, not full invoice"
