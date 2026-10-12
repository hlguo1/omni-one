"""Forecast Close golden tests — the Sunday stock-up ritual must never regress.

Golden book: DEMO_SKUS(seed=42), cover_days=14 (measured 2026-10-11):
  sku_count=8, critical_count=3, reorder_lines=5, reorder_cost=2220.95,
  stockout_soon=[Croissant, Cold Brew, Espresso],
  headline="FORECAST CLOSE: 3/8 SKUs critical · $2,220.95 to cover 14d · "
           "first stockout Croissant Butter Frozen in 1d"
"""
import csv
import io
import json
import math
import tempfile
from pathlib import Path

GOLDEN_HEADLINE = (
    "FORECAST CLOSE: 3/8 SKUs critical · $2,220.95 to cover 14d · "
    "first stockout Croissant Butter Frozen in 1d"
)
GOLDEN_KPIS = {
    "sku_count": 8,
    "critical_count": 3,
    "reorder_lines": 5,
    "reorder_cost": 2220.95,
    "stockout_soon": ["Croissant Butter Frozen", "Cold Brew Bottles", "Espresso Beans 1kg"],
}


def _close(**kw):
    from omni_one.packs.forecast_close import build_forecast_close
    kw.setdefault("seed", 42)
    kw.setdefault("date_str", "2026-10-11")
    return build_forecast_close(**kw)


def test_forecast_close_golden_seed42():
    c = _close()
    assert c["headline"] == GOLDEN_HEADLINE, c["headline"]
    for k, v in GOLDEN_KPIS.items():
        assert c["kpis"][k] == v, (k, c["kpis"][k], v)
    assert c["free"] is True
    assert c["seed"] == 42 and c["cover_days"] == 14
    assert c["date"] == "2026-10-11"
    assert "inventory:skus#" in c["citations"]
    assert len(c["skus"]) == 8
    assert len(c["do_today"]) == 3
    assert set(c["po_drafts"].keys()) == {
        "Andes Coffee Co.", "BottlePro", "FreshBake", "Kiln Works", "Syrup House",
    }
    # worst-first ordering: croissant stocks out first
    assert c["skus"][0]["name"] == "Croissant Butter Frozen"
    assert c["skus"][0]["days_left"] == 1.14


def test_demo_skus_shape_and_citations():
    from omni_one.packs.forecast_close import DEMO_SKUS
    skus = DEMO_SKUS(seed=42)
    assert len(skus) == 8
    for i, s in enumerate(skus):
        for key in ("name", "on_hand", "daily_velocity", "unit_cost", "supplier", "lead_days", "citation"):
            assert key in s, (i, key)
        assert s["citation"].startswith("[inventory:skus#"), s["citation"]
        assert s["on_hand"] >= 0 and s["daily_velocity"] > 0
    again = DEMO_SKUS(seed=42)
    assert skus == again


def test_days_left_and_reorder_math_two_skus():
    c = _close()
    by_name = {s["name"]: s for s in c["skus"]}
    esp = by_name["Espresso Beans 1kg"]
    assert esp["days_left"] == round(18 / 6.0, 2) == 3.0
    assert esp["safety_stock"] == math.ceil(6.0 * 7 * 0.5) == 21
    assert esp["reorder_qty"] == max(0, math.ceil(6.0 * 14 + 21 - 18)) == 87
    assert esp["status"] == "critical"
    assert esp["stockout_date"] == "2026-10-14"
    cro = by_name["Croissant Butter Frozen"]
    assert cro["days_left"] == round(8 / 7.0, 2) == 1.14
    assert cro["safety_stock"] == math.ceil(7.0 * 2 * 0.5) == 7
    assert cro["reorder_qty"] == max(0, math.ceil(7.0 * 14 + 7 - 8)) == 97
    assert cro["status"] == "critical"
    assert cro["stockout_date"] == "2026-10-12"
    # status thresholds: low <=14d, ok beyond
    assert by_name["Vanilla Syrup 750ml"]["status"] == "low"
    assert by_name["Oat Milk 12-pack"]["status"] == "low"
    assert by_name["Reusable Tote"]["status"] == "ok"
    # healthy SKUs need no reorder
    assert by_name["Ceramic Mug 350ml"]["reorder_qty"] == 0
    assert by_name["Paper Filters #4"]["reorder_qty"] == 0


def test_reorder_cost_equals_sum():
    c = _close()
    expected = round(sum(s["reorder_qty"] * s["unit_cost"] for s in c["skus"]), 2)
    assert c["kpis"]["reorder_cost"] == expected == 2220.95
    for s in c["skus"]:
        assert s["reorder_cost"] == round(s["reorder_qty"] * s["unit_cost"], 2)


def test_po_drafts_cover_all_critical_suppliers():
    c = _close()
    critical_sups = {s["supplier"] for s in c["skus"] if s["status"] == "critical"}
    assert critical_sups == {"FreshBake", "BottlePro", "Andes Coffee Co."}
    for sup in critical_sups:
        assert sup in c["po_drafts"], sup
        assert "Subject: Reorder" in c["po_drafts"][sup]
    # each critical SKU appears in its supplier draft
    for s in c["skus"]:
        if s["status"] == "critical":
            assert s["name"] in c["po_drafts"][s["supplier"]]
            assert str(s["reorder_qty"]) in c["po_drafts"][s["supplier"]]
            assert s["citation"] in c["po_drafts"][s["supplier"]]


def test_determinism_modulo_date():
    from omni_one.packs.forecast_close import build_forecast_close
    c1 = build_forecast_close(seed=42, date_str="2026-10-11")
    c2 = build_forecast_close(seed=42, date_str="2026-10-11")
    assert c1 == c2
    assert c1["headline"] == c2["headline"] == GOLDEN_HEADLINE
    c3 = build_forecast_close(seed=42, date_str="2026-10-12")
    assert c3["date"] == "2026-10-12"
    assert c3["headline"] == c1["headline"]
    assert c3["kpis"] == c1["kpis"]
    # math identical modulo date; only stamp + stockout dates shift by one day
    assert [s["days_left"] for s in c3["skus"]] == [s["days_left"] for s in c1["skus"]]
    assert c3["skus"][0]["stockout_date"] == "2026-10-13"
    assert c1["skus"][0]["stockout_date"] == "2026-10-12"


def test_do_today_has_dollars_and_days():
    c = _close()
    assert len(c["do_today"]) == 3
    for t in c["do_today"]:
        assert "$" in t, t
        assert "d" in t, t
    assert "Croissant Butter Frozen" in c["do_today"][0]
    assert "97" in c["do_today"][0]


def test_close_to_csv_per_sku_rows():
    from omni_one.packs.forecast_close import build_forecast_close, close_to_csv
    c = build_forecast_close(seed=42, date_str="2026-10-11")
    text = close_to_csv(c)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 8
    reader = csv.reader(io.StringIO(text))
    assert next(reader) == ["sku", "on_hand", "daily_velocity", "days_left", "safety_stock",
                            "reorder_qty", "unit_cost", "reorder_cost", "supplier",
                            "lead_days", "stockout_date", "status", "citation"]
    by_sku = {r["sku"]: r for r in rows}
    assert by_sku["Espresso Beans 1kg"]["reorder_qty"] == "87"
    assert by_sku["Croissant Butter Frozen"]["status"] == "critical"


def test_bundle_writes_four_files():
    from omni_one.packs.forecast_close import build_forecast_close, write_close_bundle, close_to_csv
    c = build_forecast_close(seed=42, date_str="2026-10-11")
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert set(paths.keys()) == {"close.json", "close.csv", "forecast.csv", "po.txt"}, paths
        for key, p in paths.items():
            assert Path(p).is_file(), (key, p)
            assert Path(p).stat().st_size > 0, (key, p)
        loaded = json.loads(Path(paths["close.json"]).read_text())
        assert loaded["headline"] == GOLDEN_HEADLINE
        assert loaded["kpis"] == c["kpis"]
        assert Path(paths["close.csv"]).read_text() == close_to_csv(c)
        assert Path(paths["forecast.csv"]).read_text() == close_to_csv(c)
        po_text = Path(paths["po.txt"]).read_text()
        for sup in ("FreshBake", "Andes Coffee Co.", "BottlePro"):
            assert sup in po_text


def test_custom_cover_days_changes_reorder():
    from omni_one.packs.forecast_close import build_forecast_close
    c14 = build_forecast_close(seed=42, cover_days=14, date_str="2026-10-11")
    c7 = build_forecast_close(seed=42, cover_days=7, date_str="2026-10-11")
    assert c7["cover_days"] == 7
    assert c7["kpis"]["reorder_cost"] < c14["kpis"]["reorder_cost"]
    assert "7d" in c7["headline"]
