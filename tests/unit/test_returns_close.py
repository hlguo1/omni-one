"""Returns & Refunds Close golden tests — the weekly money-leak ritual.

Golden demo: seed=42, 12 records (measured, deterministic):

  refund_total $868.73 in 12 return(s), refund_rate 20.0% (12/60),
  avg_refund $72.39, top leak wrong_item $359.02 (3 orders),
  restock $513.95 across 6 item(s), top3 $465.69, prevented $346.73.

Covers: golden headline/KPIs, reason breakdown math, refund_total ==
sum(amounts), restock_value == sum(restockable), refund_rate formula,
determinism modulo date, bundle files + valid JSON/CSV, drafts grounded
in citations, do_today carries $ amounts, free/offline/seed flags,
demo determinism + empty-records no-crash.
"""
import csv
import io
import json
import tempfile
from pathlib import Path

GOLDEN_HEADLINE = (
    "RETURNS CLOSE: $868.73 refunded in 12 return(s) "
    "· top leak wrong_item $359.02 · $513.95 restockable today"
)

GOLDEN_KPIS = {
    "refund_total": 868.73,
    "refund_count": 12,
    "refund_rate_pct": 20.0,
    "assumed_sales": 60,
    "avg_refund": 72.39,
    "top_reason": "wrong_item",
    "top_reason_usd": 359.02,
    "top_reason_count": 3,
    "restock_value": 513.95,
    "restock_count": 6,
    "top3_sum": 465.69,
    "prevented_today_usd": 346.73,
}

GOLDEN_BREAKDOWN = {
    "wrong_item": {"count": 3, "amount_usd": 359.02},
    "damaged": {"count": 3, "amount_usd": 204.2},
    "quality": {"count": 3, "amount_usd": 150.58},
    "changed_mind": {"count": 2, "amount_usd": 111.22},
    "late": {"count": 1, "amount_usd": 43.71},
}

GOLDEN_DATE = "2026-10-11"


def _close(**kw):
    from omni_one.packs.returns_close import build_returns_close

    kw.setdefault("seed", 42)
    kw.setdefault("date_str", GOLDEN_DATE)
    return build_returns_close(**kw)


# ---------------------------------------------------------------------------
# 1. Golden headline + KPIs
# ---------------------------------------------------------------------------

def test_returns_golden_headline_and_kpis():
    c = _close()
    assert c["headline"] == GOLDEN_HEADLINE, c["headline"]
    for k, v in GOLDEN_KPIS.items():
        assert c["kpis"][k] == v, (k, c["kpis"][k], v)
    assert c["free"] is True
    assert c["offline"] is True
    assert c["seed"] == 42
    assert c["date"] == GOLDEN_DATE


def test_returns_golden_reason_breakdown():
    c = _close()
    assert c["reason_breakdown"] == GOLDEN_BREAKDOWN, c["reason_breakdown"]
    assert set(c["reason_breakdown"]) == {
        "wrong_item", "damaged", "quality", "changed_mind", "late",
    }
    assert c["kpis"]["top_reason"] == "wrong_item"
    assert c["kpis"]["top_reason_usd"] == 359.02
    # breakdown amounts sum to refund_total
    total = round(sum(v["amount_usd"] for v in c["reason_breakdown"].values()), 2)
    assert total == c["kpis"]["refund_total"] == 868.73
    # breakdown counts sum to refund_count
    assert sum(v["count"] for v in c["reason_breakdown"].values()) == 12


# ---------------------------------------------------------------------------
# 2. Money math: totals are sums, not magic numbers
# ---------------------------------------------------------------------------

def test_refund_total_equals_sum_of_amounts():
    from omni_one.packs.returns_close import DEMO_RETURNS

    recs = DEMO_RETURNS(seed=42)
    assert len(recs) == 12
    c = _close()
    expected = round(sum(float(r["amount"]) for r in recs), 2)
    assert c["kpis"]["refund_total"] == expected == 868.73
    assert c["kpis"]["refund_count"] == len(recs) == 12
    assert c["kpis"]["avg_refund"] == round(expected / len(recs), 2) == 72.39


def test_restock_value_equals_sum_of_restockable():
    from omni_one.packs.returns_close import DEMO_RETURNS

    recs = DEMO_RETURNS(seed=42)
    c = _close()
    expected = round(sum(float(r["amount"]) for r in recs if r["restockable"]), 2)
    assert c["kpis"]["restock_value"] == expected == 513.95
    assert c["kpis"]["restock_count"] == sum(1 for r in recs if r["restockable"]) == 6
    sheet_sum = round(sum(float(r["amount"]) for r in c["restock_sheet"]), 2)
    assert sheet_sum == expected
    for row in c["restock_sheet"]:
        assert row["action"] and row["citation"] in row["action"]
        assert float(row["amount"]) > 0


def test_refund_rate_is_count_over_60():
    c = _close()
    assert c["kpis"]["refund_rate_pct"] == round(12 / 60 * 100, 1) == 20.0
    assert c["kpis"]["assumed_sales"] == 60
    from omni_one.packs.returns_close import build_returns_close

    tiny = build_returns_close(records=[], date_str=GOLDEN_DATE)
    assert tiny["kpis"]["refund_rate_pct"] == 0.0
    assert tiny["kpis"]["refund_total"] == 0.0


# ---------------------------------------------------------------------------
# 3. Determinism (identical except date)
# ---------------------------------------------------------------------------

def test_returns_determinism_modulo_date():
    from omni_one.packs.returns_close import build_returns_close

    a = build_returns_close(seed=42, date_str="2026-10-11")
    b = build_returns_close(seed=42, date_str="2026-10-12")
    assert a["date"] != b["date"]
    for key in ("headline", "kpis", "reason_breakdown", "restock_sheet",
                "drafts", "do_today", "citations", "records"):
        assert a[key] == b[key], key
    c1 = build_returns_close(seed=42, date_str=GOLDEN_DATE)
    c2 = build_returns_close(seed=42, date_str=GOLDEN_DATE)
    assert c1 == c2
    other = build_returns_close(seed=7, date_str=GOLDEN_DATE)
    assert other["headline"] != c1["headline"] or other["records"] != c1["records"]


def test_demo_returns_deterministic():
    from omni_one.packs.returns_close import DEMO_RETURNS

    assert DEMO_RETURNS(seed=42) == DEMO_RETURNS(seed=42)
    assert DEMO_RETURNS(seed=42) != DEMO_RETURNS(seed=7)
    recs = DEMO_RETURNS(seed=42)
    for r in recs:
        for key in ("order_id", "product", "reason", "amount",
                    "days_since_purchase", "restockable", "citation"):
            assert key in r, (key, r)
        assert r["reason"] in ("damaged", "late", "wrong_item", "changed_mind", "quality")
        assert r["citation"].startswith("[shopify:orders#")


# ---------------------------------------------------------------------------
# 4. Bundle: 4 files, valid JSON/CSV
# ---------------------------------------------------------------------------

def test_returns_bundle_writes_four_files():
    from omni_one.packs.returns_close import build_returns_close, write_close_bundle

    c = build_returns_close(seed=42, date_str=GOLDEN_DATE)
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert set(paths.keys()) == {"close.json", "close.csv", "returns.csv", "drafts.txt"}, paths
        for key, p in paths.items():
            assert Path(p).is_file(), (key, p)
            assert Path(p).stat().st_size > 0, (key, p)
        loaded = json.loads(Path(paths["close.json"]).read_text())
        assert loaded["headline"] == GOLDEN_HEADLINE
        assert loaded["kpis"] == c["kpis"]
        # rewrite is idempotent (same bytes)
        before = {k: Path(v).read_text() for k, v in paths.items()}
        paths2 = write_close_bundle(c, tmp)
        for k, v in paths2.items():
            assert Path(v).read_text() == before[k]


def test_returns_csvs_parse_with_exact_headers():
    from omni_one.packs.returns_close import close_to_csv, returns_to_csv

    c = _close()
    reason_text = close_to_csv(c)
    rows = list(csv.DictReader(io.StringIO(reason_text)))
    assert len(rows) == 5
    header = next(csv.reader(io.StringIO(reason_text)))
    assert header == ["reason", "count", "amount_usd"]
    assert rows[0]["reason"] == "wrong_item"
    assert float(rows[0]["amount_usd"]) == 359.02
    rec_text = returns_to_csv(c)
    rec_rows = list(csv.DictReader(io.StringIO(rec_text)))
    assert len(rec_rows) == 12
    header2 = next(csv.reader(io.StringIO(rec_text)))
    assert header2 == ["order_id", "product", "reason", "amount",
                       "days_since_purchase", "restockable", "citation"]
    for row in rec_rows:
        assert row["citation"].startswith("[shopify:orders#")
        assert float(row["amount"]) > 0


# ---------------------------------------------------------------------------
# 5. Drafts grounded, do_today concrete, prevented template
# ---------------------------------------------------------------------------

def test_drafts_cite_citations():
    c = _close()
    assert 2 <= len(c["drafts"]) <= 3
    assert len(c["drafts"]) == 3
    for d in c["drafts"]:
        assert d["citation"] in c["citations"], d
        assert d["citation"] in d["draft"], d
        assert "sorry" in d["draft"].lower(), d["draft"]
        assert "RESHIP" in d["draft"] and "REFUND" in d["draft"], d["draft"]
        assert f"${float(d['amount']):,.2f}" in d["draft"], d["draft"]
    # drafts cover the 3 largest refunds
    amounts = sorted((float(d["amount"]) for d in c["drafts"]), reverse=True)
    assert amounts == [164.06, 157.59, 144.04]
    assert c["drafts"][0]["order_id"] == "#1010"
    # drafts.txt on disk contains the drafts verbatim
    from omni_one.packs.returns_close import write_close_bundle

    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        txt = Path(paths["drafts.txt"]).read_text()
        for d in c["drafts"]:
            assert d["draft"][:40] in txt
            assert d["citation"] in txt


def test_do_today_three_concrete_strings_with_amounts():
    c = _close()
    assert len(c["do_today"]) == 3
    for task in c["do_today"]:
        assert "$" in task, task
        assert len(task) > 20, task
    assert "513.95" in c["do_today"][0]
    assert "wrong_item" in c["do_today"][1] and "359.02" in c["do_today"][1]
    assert "465.69" in c["do_today"][2]
    assert len(c["prevented_today"]) == 2
    for p in c["prevented_today"]:
        assert isinstance(p, str) and len(p) > 20


def test_free_true_and_citations_complete():
    c = _close()
    assert c["free"] is True
    assert len(c["citations"]) == 12
    assert c["citations"][0] == "[shopify:orders#1001]"
    assert all("[shopify:" in cite for cite in c["citations"])
    assert "shopify" in c["citations_note"]


def test_empty_records_no_crash():
    from omni_one.packs.returns_close import (
        build_returns_close, close_to_csv, returns_to_csv, drafts_to_txt,
    )

    c = build_returns_close(records=[], date_str=GOLDEN_DATE)
    assert c["kpis"]["refund_total"] == 0.0
    assert c["kpis"]["refund_count"] == 0
    assert c["kpis"]["restock_value"] == 0.0
    assert c["drafts"] == []
    assert len(c["do_today"]) == 3
    assert "$0.00" in c["headline"]
    assert "reason,count,amount_usd" in close_to_csv(c)
    assert "order_id" in returns_to_csv(c)
    assert "RETURNS CLOSE" in drafts_to_txt(c)
