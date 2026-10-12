"""Multi-Shop Rollup Close golden tests — the Sunday ritual must never regress.

Golden demo: seed=42, 4 shops (measured, deterministic — do not hand-edit):

  Harbor Goods  [shopify]  gmv 28952  fees 2638  ship 1926  cogs 11551
    -> profit 12837, margin 44.34%, orders 292, stockouts 5, angry 1 (rank 1)
  Pixel Pantry  [amazon]   gmv 25870  fees 2294  ship 2528  cogs 9218
    -> profit 11830, margin 45.73%, orders 245, stockouts 1, angry 3 (rank 2)
  Northwind Home [etsy]    gmv 24559  fees 3443  ship 3098  cogs 9572
    -> profit 8446, margin 34.39%, orders 815, stockouts 5, angry 8 (rank 3)
  Velvet Vinyl  [tiktok]   gmv 21746  fees 2219  ship 3213  cogs 8821
    -> profit 7493, margin 34.46%, orders 156, stockouts 6, angry 2 (rank 4)

  totals: gmv 101127, profit 40606, blended 40.2%, orders 1508,
    stockouts 17, angry 14; best Harbor Goods, worst Velvet Vinyl.
  plays: FEE-AUDIT -> Northwind Home (thinnest margin),
    REPLY-SPRINT -> Northwind Home (8 angry), PO-SPRINT -> Velvet Vinyl (6).
  headline: "ROLLUP CLOSE: 4 shops · $101,127 GMV · $40,606 profit (40.2%) ·
    ★ Harbor Goods / ⚠ Velvet Vinyl"

Covers: golden headline/kpis, profit math, ranking, totals, best/worst,
plays on real shops, do_today, determinism modulo date, CSV shape, 4-file
bundle, explicit-shops path, free/offline flags.
"""
import csv
import io
import json
import tempfile
from pathlib import Path

GOLDEN_HEADLINE = (
    "ROLLUP CLOSE: 4 shops · $101,127 GMV · $40,606 profit (40.2%) · "
    "★ Harbor Goods / ⚠ Velvet Vinyl"
)
GOLDEN_KPIS = {
    "shops": 4,
    "gmv": 101127,
    "profit": 40606,
    "blended_margin_pct": 40.2,
    "best_shop": "Harbor Goods",
    "worst_shop": "Velvet Vinyl",
    "orders": 1508,
    "stockouts": 17,
    "angry": 14,
}
GOLDEN_PROFITS = {
    "Harbor Goods": 12837,
    "Pixel Pantry": 11830,
    "Northwind Home": 8446,
    "Velvet Vinyl": 7493,
}
GOLDEN_MARGINS = {
    "Harbor Goods": 44.34,
    "Pixel Pantry": 45.73,
    "Northwind Home": 34.39,
    "Velvet Vinyl": 34.46,
}
GOLDEN_DATE = "2026-10-12"


def _close(**kw):
    from omni_one.packs.rollup_close import build_rollup_close
    kw.setdefault("seed", 42)
    kw.setdefault("date_str", GOLDEN_DATE)
    return build_rollup_close(**kw)


# ---------------------------------------------------------------------------
# 1. Golden: seed=42 headline + kpis never drift
# ---------------------------------------------------------------------------

def test_rollup_golden_headline_and_kpis():
    c = _close()
    assert c["headline"] == GOLDEN_HEADLINE, c["headline"]
    for k, v in GOLDEN_KPIS.items():
        assert c["kpis"][k] == v, (k, c["kpis"][k], v)
    assert c["seed"] == 42
    assert c["date"] == GOLDEN_DATE
    assert c["free"] is True
    assert c["offline"] is True
    assert "shop" in c["citations"]


def test_rollup_demo_shops_deterministic_four():
    from omni_one.packs.rollup_close import DEMO_SHOPS
    a = DEMO_SHOPS(seed=42)
    b = DEMO_SHOPS(seed=42)
    assert a == b
    assert len(a) == 4
    names = [s["name"] for s in a]
    assert names == ["Harbor Goods", "Pixel Pantry", "Northwind Home", "Velvet Vinyl"]
    for s in a:
        for key in ("name", "channel", "gmv", "fees", "ship_cost", "cogs",
                    "orders", "stockout_count", "angry_count"):
            assert key in s, (key, s)
        assert s["gmv"] > 0 and s["orders"] > 0
    # citations derive from channel + name
    from omni_one.packs.rollup_close import build_rollup_close
    c = build_rollup_close(seed=42, date_str=GOLDEN_DATE)
    by_name = {r["name"]: r for r in c["shops"]}
    assert by_name["Harbor Goods"]["citation"] == "[shopify:shop:Harbor Goods]"
    assert by_name["Velvet Vinyl"]["citation"] == "[tiktok:shop:Velvet Vinyl]"


# ---------------------------------------------------------------------------
# 2. Profit math per shop: profit = gmv - fees - ship - cogs
# ---------------------------------------------------------------------------

def test_rollup_profit_math_per_shop():
    c = _close()
    assert len(c["shops"]) == 4
    for row in c["shops"]:
        expected = row["gmv"] - row["fees"] - row["ship_cost"] - row["cogs"]
        assert row["profit"] == expected, row
        assert row["profit"] == GOLDEN_PROFITS[row["name"]], row
        assert row["margin_pct"] == GOLDEN_MARGINS[row["name"]], row
        assert row["margin_pct"] == round(row["profit"] / row["gmv"] * 100, 2)


# ---------------------------------------------------------------------------
# 3. Ranking sorted desc, best/worst correct, totals == sums
# ---------------------------------------------------------------------------

def test_rollup_ranking_sorted_desc():
    c = _close()
    profits = [r["profit"] for r in c["shops"]]
    assert profits == sorted(profits, reverse=True), profits
    assert profits == [12837, 11830, 8446, 7493]
    assert [r["rank"] for r in c["shops"]] == [1, 2, 3, 4]
    assert [r["name"] for r in c["shops"]] == [
        "Harbor Goods", "Pixel Pantry", "Northwind Home", "Velvet Vinyl"]


def test_rollup_totals_equal_sums():
    c = _close()
    k = c["kpis"]
    assert k["gmv"] == sum(r["gmv"] for r in c["shops"]) == 101127
    assert k["profit"] == sum(r["profit"] for r in c["shops"]) == 40606
    assert k["orders"] == sum(r["orders"] for r in c["shops"]) == 1508
    assert k["stockouts"] == sum(r["stockout_count"] for r in c["shops"]) == 17
    assert k["angry"] == sum(r["angry_count"] for r in c["shops"]) == 14
    assert k["blended_margin_pct"] == round(40606 / 101127 * 100, 1) == 40.2


def test_rollup_best_worst_correct():
    c = _close()
    assert c["kpis"]["best_shop"] == "Harbor Goods"
    assert c["kpis"]["worst_shop"] == "Velvet Vinyl"
    assert c["shops"][0]["name"] == "Harbor Goods"
    assert c["shops"][-1]["name"] == "Velvet Vinyl"
    assert "Harbor Goods" in c["headline"] and "Velvet Vinyl" in c["headline"]


# ---------------------------------------------------------------------------
# 4. Plays reference real shop names; do_today carries $ + names
# ---------------------------------------------------------------------------

def test_rollup_plays_reference_real_shop_names():
    c = _close()
    real = {r["name"] for r in c["shops"]}
    assert len(c["plays"]) == 3
    assert [p["play_id"] for p in c["plays"]] == ["FEE-AUDIT", "REPLY-SPRINT", "PO-SPRINT"]
    for p in c["plays"]:
        assert p["shop"] in real, p
        assert p["evidence"] and p["citation"] == p["evidence"]
        assert p["next_step"] and len(p["next_step"]) > 10
    by_id = {p["play_id"]: p for p in c["plays"]}
    # worst margin (34.39) gets the fee audit; most angry (8) the reply sprint
    assert by_id["FEE-AUDIT"]["shop"] == "Northwind Home"
    assert by_id["REPLY-SPRINT"]["shop"] == "Northwind Home"
    assert by_id["PO-SPRINT"]["shop"] == "Velvet Vinyl"  # 6 stockouts leads
    assert c["free"] is True


def test_rollup_do_today_has_dollars_and_shop_names():
    c = _close()
    real = {r["name"] for r in c["shops"]}
    assert len(c["do_today"]) == 3
    for task in c["do_today"]:
        assert "$" in task, task
        assert any(name in task for name in real), task
        assert "[" in task and "]" in task  # cited shop


# ---------------------------------------------------------------------------
# 5. Determinism modulo date; explicit shops path
# ---------------------------------------------------------------------------

def test_rollup_determinism_modulo_date():
    from omni_one.packs.rollup_close import build_rollup_close
    a = build_rollup_close(seed=42, date_str="2026-10-12")
    b = build_rollup_close(seed=42, date_str="2026-10-12")
    assert a == b
    other_day = build_rollup_close(seed=42, date_str="2026-10-13")
    assert other_day["date"] == "2026-10-13"
    assert other_day["headline"] == a["headline"]
    assert other_day["kpis"] == a["kpis"]
    assert other_day["shops"] == a["shops"]
    assert other_day["plays"] == a["plays"]
    assert other_day["do_today"] == a["do_today"]
    # different seed diverges
    other_seed = build_rollup_close(seed=7, date_str="2026-10-12")
    assert other_seed["headline"] != a["headline"]


def test_rollup_explicit_shops_ranking_and_totals():
    from omni_one.packs.rollup_close import build_rollup_close
    shops = [
        {"name": "A-Shop", "channel": "shopify", "gmv": 10000, "fees": 1000,
         "ship_cost": 1000, "cogs": 3000, "orders": 100,
         "stockout_count": 0, "angry_count": 5},
        {"name": "B-Shop", "channel": "amazon", "gmv": 20000, "fees": 1000,
         "ship_cost": 1000, "cogs": 3000, "orders": 200,
         "stockout_count": 4, "angry_count": 1},
    ]
    c = build_rollup_close(shops=shops, date_str=GOLDEN_DATE)
    # B profit 15000 > A profit 5000
    assert [r["name"] for r in c["shops"]] == ["B-Shop", "A-Shop"]
    assert c["kpis"]["gmv"] == 30000 and c["kpis"]["profit"] == 20000
    assert c["kpis"]["best_shop"] == "B-Shop" and c["kpis"]["worst_shop"] == "A-Shop"
    assert "B-Shop" in c["headline"] and "A-Shop" in c["headline"]
    assert len(c["do_today"]) == 3 and c["free"] is True


# ---------------------------------------------------------------------------
# 6. CSV shape + 4-file bundle
# ---------------------------------------------------------------------------

def test_rollup_csv_per_shop_rows():
    from omni_one.packs.rollup_close import close_to_csv
    c = _close()
    text = close_to_csv(c)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 4
    header = text.splitlines()[0].split(",")
    assert header == ["rank", "shop", "channel", "gmv", "fees", "ship_cost",
                      "cogs", "profit", "margin_pct", "orders",
                      "stockout_count", "angry_count", "citation"]
    by_shop = {r["shop"]: r for r in rows}
    assert int(by_shop["Harbor Goods"]["profit"]) == 12837
    assert int(by_shop["Velvet Vinyl"]["profit"]) == 7493
    for r in rows:
        assert int(r["gmv"]) - int(r["fees"]) - int(r["ship_cost"]) - int(r["cogs"]) == int(r["profit"])
        assert r["citation"].startswith("[") and ":shop:" in r["citation"]


def test_rollup_bundle_writes_four_files():
    from omni_one.packs.rollup_close import write_close_bundle
    c = _close()
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert set(paths.keys()) == {"close.json", "close.csv", "shops.csv", "actions.txt"}
        for key, p in paths.items():
            assert Path(p).is_file(), (key, p)
            assert Path(p).stat().st_size > 0, (key, p)
        loaded = json.loads(Path(paths["close.json"]).read_text())
        assert loaded["headline"] == GOLDEN_HEADLINE
        assert loaded["kpis"] == c["kpis"]
        shops_csv = Path(paths["shops.csv"]).read_text()
        assert "Harbor Goods" in shops_csv and "Velvet Vinyl" in shops_csv
        close_csv = Path(paths["close.csv"]).read_text()
        assert "Harbor Goods" in close_csv
        actions = Path(paths["actions.txt"]).read_text()
        assert c["headline"] in actions
        for task in c["do_today"]:
            assert task[:30] in actions
