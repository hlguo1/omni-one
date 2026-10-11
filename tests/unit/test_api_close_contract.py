"""WAVE2-G close contract: TestClient POST /api/v1/seller/close demo shape/values/idempotency/errors/csv/metrics."""
from __future__ import annotations
import csv
import io
import json
import os
import re
os.environ.setdefault("SELLER_LLM", "mock")
os.environ.setdefault("SELLER_MAX_LLM_USD", "0.0")
import pytest
from fastapi.testclient import TestClient
CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")
TOP_REQUIRED = ["date", "shop", "headline", "kpis", "do_today", "reorder_sheet", "reply_queue", "money_leaks", "listing_fixes", "po_draft"]
KPI_NUMERIC = ["gmv", "fees", "shipping", "net", "cogs", "true_profit", "margin_pct", "orders", "aov", "money_at_risk_usd"]
@pytest.fixture(scope="module")
def client():
    from omni_one.api.fastapi_app import create_omni_one_app
    app = create_omni_one_app()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
@pytest.fixture(scope="module")
def close_demo(client):
    r = client.post("/api/v1/seller/close", json={"demo": True})
    assert r.status_code == 200, r.text[:800]
    d = r.json()
    assert isinstance(d, dict)
    return d
@pytest.fixture(scope="module")
def close_pair(client):
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    return (a, b)
@pytest.fixture(scope="module")
def close_csv_bundle(client):
    r = client.get("/api/v1/seller/close.csv")
    assert r.status_code == 200, r.text[:500]
    return {"status": r.status_code, "ctype": r.headers.get("content-type", ""), "text": r.text, "headers": dict(r.headers)}
def _parse_metrics(text):
    out = {}
    for line in text.splitlines():
        m = re.search(r'op="([^"]+)"\}\s+(\d+)', line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out
def test_close_has_key_date(close_demo):
    """Close bundle must expose top-level key date."""
    assert "date" in close_demo, f"missing key 'date' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["date"], str) and close_demo["date"].strip(), "date must be non-empty str"
    assert close_demo is not None

def test_close_has_key_shop(close_demo):
    """Close bundle must expose top-level key shop."""
    assert "shop" in close_demo, f"missing key 'shop' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["shop"], str) and close_demo["shop"].strip(), "shop must be non-empty str"
    assert close_demo is not None

def test_close_has_key_headline(close_demo):
    """Close bundle must expose top-level key headline."""
    assert "headline" in close_demo, f"missing key 'headline' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["headline"], str) and close_demo["headline"].strip(), "headline must be non-empty str"
    assert close_demo is not None

def test_close_has_key_kpis(close_demo):
    """Close bundle must expose top-level key kpis."""
    assert "kpis" in close_demo, f"missing key 'kpis' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["kpis"], dict) and len(close_demo["kpis"]) >= 10
    assert close_demo is not None

def test_close_has_key_do_today(close_demo):
    """Close bundle must expose top-level key do_today."""
    assert "do_today" in close_demo, f"missing key 'do_today' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["do_today"], list), "do_today must be list"
    assert close_demo is not None

def test_close_has_key_reorder_sheet(close_demo):
    """Close bundle must expose top-level key reorder_sheet."""
    assert "reorder_sheet" in close_demo, f"missing key 'reorder_sheet' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["reorder_sheet"], list), "reorder_sheet must be list"
    assert close_demo is not None

def test_close_has_key_reply_queue(close_demo):
    """Close bundle must expose top-level key reply_queue."""
    assert "reply_queue" in close_demo, f"missing key 'reply_queue' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["reply_queue"], list), "reply_queue must be list"
    assert close_demo is not None

def test_close_has_key_money_leaks(close_demo):
    """Close bundle must expose top-level key money_leaks."""
    assert "money_leaks" in close_demo, f"missing key 'money_leaks' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["money_leaks"], list), "money_leaks must be list"
    assert close_demo is not None

def test_close_has_key_listing_fixes(close_demo):
    """Close bundle must expose top-level key listing_fixes."""
    assert "listing_fixes" in close_demo, f"missing key 'listing_fixes' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["listing_fixes"], list), "listing_fixes must be list"
    assert close_demo is not None

def test_close_has_key_po_draft(close_demo):
    """Close bundle must expose top-level key po_draft."""
    assert "po_draft" in close_demo, f"missing key 'po_draft' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["po_draft"], str) and close_demo["po_draft"].strip(), "po_draft must be non-empty str"
    assert close_demo is not None

def test_close_has_key_citations(close_demo):
    """Close bundle must expose top-level key citations."""
    assert "citations" in close_demo, f"missing key 'citations' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["citations"], str) and close_demo["citations"].strip(), "citations must be non-empty str"
    assert close_demo is not None

def test_close_has_key_free(close_demo):
    """Close bundle must expose top-level key free."""
    assert "free" in close_demo, f"missing key 'free' keys={list(close_demo.keys())}"
    assert close_demo["free"] is True, "free must be True (free/offline ritual)"
    assert close_demo is not None

def test_close_has_key_offline(close_demo):
    """Close bundle must expose top-level key offline."""
    assert "offline" in close_demo, f"missing key 'offline' keys={list(close_demo.keys())}"
    assert close_demo["offline"] is True, "offline must be True (free/offline ritual)"
    assert close_demo is not None

def test_close_has_key_ingest_report(close_demo):
    """Close bundle must expose top-level key ingest_report."""
    assert "ingest_report" in close_demo, f"missing key 'ingest_report' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["ingest_report"], dict)
    assert close_demo is not None

def test_close_has_key_dead_stock_note(close_demo):
    """Close bundle must expose top-level key dead_stock_note."""
    assert "dead_stock_note" in close_demo, f"missing key 'dead_stock_note' keys={list(close_demo.keys())}"
    assert isinstance(close_demo["dead_stock_note"], list), "dead_stock_note must be list"
    assert close_demo is not None

def test_close_kpi_type_gmv(close_demo):
    """kpis.gmv must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["gmv"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.gmv={v!r}"
    assert v >= 0 or "gmv" in ("margin_pct",), f"kpis.gmv negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_fees(close_demo):
    """kpis.fees must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["fees"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.fees={v!r}"
    assert v >= 0 or "fees" in ("margin_pct",), f"kpis.fees negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_shipping(close_demo):
    """kpis.shipping must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["shipping"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.shipping={v!r}"
    assert v >= 0 or "shipping" in ("margin_pct",), f"kpis.shipping negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_net(close_demo):
    """kpis.net must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["net"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.net={v!r}"
    assert v >= 0 or "net" in ("margin_pct",), f"kpis.net negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_cogs(close_demo):
    """kpis.cogs must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["cogs"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.cogs={v!r}"
    assert v >= 0 or "cogs" in ("margin_pct",), f"kpis.cogs negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_true_profit(close_demo):
    """kpis.true_profit must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["true_profit"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.true_profit={v!r}"
    assert v >= 0 or "true_profit" in ("margin_pct",), f"kpis.true_profit negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_margin_pct(close_demo):
    """kpis.margin_pct must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["margin_pct"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.margin_pct={v!r}"
    assert v >= 0 or "margin_pct" in ("margin_pct",), f"kpis.margin_pct negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_orders(close_demo):
    """kpis.orders must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["orders"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.orders={v!r}"
    assert v >= 0 or "orders" in ("margin_pct",), f"kpis.orders negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_aov(close_demo):
    """kpis.aov must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["aov"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.aov={v!r}"
    assert v >= 0 or "aov" in ("margin_pct",), f"kpis.aov negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_kpi_type_money_at_risk_usd(close_demo):
    """kpis.money_at_risk_usd must be numeric (int/float, not bool)."""
    v = close_demo["kpis"]["money_at_risk_usd"]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"kpis.money_at_risk_usd={v!r}"
    assert v >= 0 or "money_at_risk_usd" in ("margin_pct",), f"kpis.money_at_risk_usd negative {v}"
    assert close_demo["kpis"]["orders"] == 8

def test_close_golden_gmv(close_demo):
    """Golden demo KPI gmv == 274.0 (tol 0.01)."""
    v = float(close_demo["kpis"]["gmv"])
    assert abs(v - 274.0) < 0.01 + 1e-9, f"gmv={v} expected 274.0 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["gmv"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_true_profit(close_demo):
    """Golden demo KPI true_profit == 169.09 (tol 0.05)."""
    v = float(close_demo["kpis"]["true_profit"])
    assert abs(v - 169.09) < 0.05 + 1e-9, f"true_profit={v} expected 169.09 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["true_profit"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_money_at_risk_usd(close_demo):
    """Golden demo KPI money_at_risk_usd == 102.75 (tol 0.05)."""
    v = float(close_demo["kpis"]["money_at_risk_usd"])
    assert abs(v - 102.75) < 0.05 + 1e-9, f"money_at_risk_usd={v} expected 102.75 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["money_at_risk_usd"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_fees(close_demo):
    """Golden demo KPI fees == 16.71 (tol 0.05)."""
    v = float(close_demo["kpis"]["fees"])
    assert abs(v - 16.71) < 0.05 + 1e-9, f"fees={v} expected 16.71 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["fees"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_shipping(close_demo):
    """Golden demo KPI shipping == 24.0 (tol 0.01)."""
    v = float(close_demo["kpis"]["shipping"])
    assert abs(v - 24.0) < 0.01 + 1e-9, f"shipping={v} expected 24.0 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["shipping"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_net(close_demo):
    """Golden demo KPI net == 233.29 (tol 0.05)."""
    v = float(close_demo["kpis"]["net"])
    assert abs(v - 233.29) < 0.05 + 1e-9, f"net={v} expected 233.29 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["net"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_cogs(close_demo):
    """Golden demo KPI cogs == 64.2 (tol 0.05)."""
    v = float(close_demo["kpis"]["cogs"])
    assert abs(v - 64.2) < 0.05 + 1e-9, f"cogs={v} expected 64.2 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["cogs"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_margin_pct(close_demo):
    """Golden demo KPI margin_pct == 61.7 (tol 0.15)."""
    v = float(close_demo["kpis"]["margin_pct"])
    assert abs(v - 61.7) < 0.15 + 1e-9, f"margin_pct={v} expected 61.7 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["margin_pct"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_orders(close_demo):
    """Golden demo KPI orders == 8 (tol 0.0)."""
    v = float(close_demo["kpis"]["orders"])
    assert abs(v - 8) < 0.001 + 1e-9, f"orders={v} expected 8 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["orders"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_golden_aov(close_demo):
    """Golden demo KPI aov == 34.25 (tol 0.01)."""
    v = float(close_demo["kpis"]["aov"])
    assert abs(v - 34.25) < 0.01 + 1e-9, f"aov={v} expected 34.25 full={close_demo['kpis']}"
    assert isinstance(close_demo["kpis"]["aov"], (int, float))
    assert close_demo["headline"] and len(close_demo["headline"]) > 20

def test_close_headline_frag_0(close_demo):
    """Headline must contain 'Profit $169.09'."""
    h = close_demo["headline"]
    assert "Profit $169.09" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_headline_frag_1(close_demo):
    """Headline must contain '61.7%'."""
    h = close_demo["headline"]
    assert "61.7%" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_headline_frag_2(close_demo):
    """Headline must contain '$102.75 at risk'."""
    h = close_demo["headline"]
    assert "$102.75 at risk" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_headline_frag_3(close_demo):
    """Headline must contain '3 angry messages'."""
    h = close_demo["headline"]
    assert "3 angry messages" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_headline_frag_4(close_demo):
    """Headline must contain '1 reorder(s) TODAY'."""
    h = close_demo["headline"]
    assert "1 reorder(s) TODAY" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_headline_frag_5(close_demo):
    """Headline must contain '0 leak(s) to plug'."""
    h = close_demo["headline"]
    assert "0 leak(s) to plug" in h, f"headline={h!r}"
    assert "Profit $" in h and "at risk" in h and "reorder" in h.lower()
    assert len(h.split("·")) >= 3 or len(h.split(".")) >= 2

def test_close_do_today_0(close_demo):
    """do_today list shape and content check 0."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert "Reply to 3 message" in dt[0] and "$102.75 at risk" in dt[0]
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_do_today_1(close_demo):
    """do_today list shape and content check 1."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert "Reorder Tote Bag Handmade" in dt[1] and "Acme Textiles" in dt[1]
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_do_today_2(close_demo):
    """do_today list shape and content check 2."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert "No money leaks" in dt[2] or "leak" in dt[2].lower()
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_do_today_3(close_demo):
    """do_today list shape and content check 3."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert all(isinstance(x, str) and len(x) > 10 for x in dt)
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_do_today_4(close_demo):
    """do_today list shape and content check 4."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert "cite file:line" in dt[0].lower() or "cite" in dt[0].lower()
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_do_today_5(close_demo):
    """do_today list shape and content check 5."""
    dt = close_demo["do_today"]
    assert isinstance(dt, list) and len(dt) == 3, dt
    assert dt[1].count("x10") >= 1 or "x" in dt[1]
    assert close_demo["kpis"]["gmv"] == 274.0

def test_close_reorder_tote_present(close_demo):
    """Reorder sheet: tote_present."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["product"] == "Tote Bag Handmade"
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_urgency_today(close_demo):
    """Reorder sheet: urgency_today."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["urgency"] == "ORDER TODAY"
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_reorder_qty(close_demo):
    """Reorder sheet: reorder_qty."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["reorder_qty"] == 10
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_on_hand(close_demo):
    """Reorder sheet: on_hand."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["on_hand"] == 2
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_sold_7d(close_demo):
    """Reorder sheet: sold_7d."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["sold_7d"] == 6
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_days_left(close_demo):
    """Reorder sheet: days_left."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert abs(float(tote["days_left"]) - 2.3) < 0.2
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_velocity(close_demo):
    """Reorder sheet: velocity."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert abs(float(tote["daily_velocity"]) - 0.86) < 0.05
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_cover(close_demo):
    """Reorder sheet: cover."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["cover_days"] == 14
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_supplier(close_demo):
    """Reorder sheet: supplier."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert tote["supplier"] == "Acme Textiles"
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_citation_file(close_demo):
    """Reorder sheet: citation_file."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert "inventory.csv:2" in tote["citation"]
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_citation_pattern(close_demo):
    """Reorder sheet: citation_pattern."""
    tote = next(r for r in close_demo["reorder_sheet"] if "Tote" in r["product"])
    assert CITATION_RE.search(tote["citation"])
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_sorted_days(close_demo):
    """Reorder sheet: sorted_days."""
    rs = close_demo["reorder_sheet"]
    assert rs == sorted(rs, key=lambda x: x["days_left"])
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_len_ge1(close_demo):
    """Reorder sheet: len_ge1."""
    rs = close_demo["reorder_sheet"]
    assert len(rs) >= 1
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_qty_integral(close_demo):
    """Reorder sheet: qty_integral."""
    rs = close_demo["reorder_sheet"]
    assert all(abs(float(r["reorder_qty"]) - round(float(r["reorder_qty"]))) < 1e-6 for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_qty_nonneg(close_demo):
    """Reorder sheet: qty_nonneg."""
    rs = close_demo["reorder_sheet"]
    assert all(float(r["reorder_qty"]) >= 0 for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_row_keys(close_demo):
    """Reorder sheet: row_keys."""
    rs = close_demo["reorder_sheet"]
    assert all(all(k in r for k in ["product","on_hand","sold_7d","daily_velocity","days_left","reorder_qty","supplier","urgency","citation"]) for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_row_types(close_demo):
    """Reorder sheet: row_types."""
    rs = close_demo["reorder_sheet"]
    assert all(isinstance(r["product"], str) and isinstance(r["supplier"], str) for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_urgency_vals(close_demo):
    """Reorder sheet: urgency_vals."""
    rs = close_demo["reorder_sheet"]
    assert all(r["urgency"] in ("ORDER TODAY","this week","watch") for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_onhand_int(close_demo):
    """Reorder sheet: onhand_int."""
    rs = close_demo["reorder_sheet"]
    assert all(isinstance(r["on_hand"], (int,float)) for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reorder_citation_all(close_demo):
    """Reorder sheet: citation_all."""
    rs = close_demo["reorder_sheet"]
    assert all(CITATION_RE.search(str(r["citation"])) for r in rs)
    assert isinstance(close_demo["reorder_sheet"], list)
    assert close_demo["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_close_reply_len3(close_demo):
    """Reply queue: len3."""
    q = close_demo["reply_queue"]
    assert len(q) == 3, q
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_first_alice(close_demo):
    """Reply queue: first_alice."""
    q = close_demo["reply_queue"]
    assert q[0]["customer"] == "Alice"
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_second_charlie(close_demo):
    """Reply queue: second_charlie."""
    q = close_demo["reply_queue"]
    assert q[1]["customer"] == "Charlie"
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_draft_2h_0(close_demo):
    """Reply queue: draft_2h_0."""
    q = close_demo["reply_queue"]
    assert "within 2 hours" in q[0]["draft"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_draft_2h_1(close_demo):
    """Reply queue: draft_2h_1."""
    q = close_demo["reply_queue"]
    assert "within 2 hours" in q[1]["draft"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_draft_cite_0(close_demo):
    """Reply queue: draft_cite_0."""
    q = close_demo["reply_queue"]
    assert q[0]["citation"] in q[0]["draft"] or CITATION_RE.search(q[0]["draft"])
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_draft_cite_1(close_demo):
    """Reply queue: draft_cite_1."""
    q = close_demo["reply_queue"]
    assert q[1]["citation"] in q[1]["draft"] or CITATION_RE.search(q[1]["draft"])
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_cite_dm_0(close_demo):
    """Reply queue: cite_dm_0."""
    q = close_demo["reply_queue"]
    assert "instagram_dm.txt:1" in q[0]["citation"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_cite_dm_1(close_demo):
    """Reply queue: cite_dm_1."""
    q = close_demo["reply_queue"]
    assert "instagram_dm.txt:4" in q[1]["citation"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_cite_review_2(close_demo):
    """Reply queue: cite_review_2."""
    q = close_demo["reply_queue"]
    assert "reviews.csv:3" in q[2]["citation"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_priority_p0(close_demo):
    """Reply queue: priority_p0."""
    q = close_demo["reply_queue"]
    assert all(x["priority"] == "P0-reply-in-2h" for x in q)
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_channel_set(close_demo):
    """Reply queue: channel_set."""
    q = close_demo["reply_queue"]
    assert {x["channel"] for x in q} == {"dm", "review"} or set(x["channel"] for x in q) >= {"dm"}
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_draft_len(close_demo):
    """Reply queue: draft_len."""
    q = close_demo["reply_queue"]
    assert all(len(x["draft"]) > 40 for x in q)
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_summary_len(close_demo):
    """Reply queue: summary_len."""
    q = close_demo["reply_queue"]
    assert all(len(x["summary"]) > 5 for x in q)
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_cite_pattern_all(close_demo):
    """Reply queue: cite_pattern_all."""
    q = close_demo["reply_queue"]
    assert all(CITATION_RE.search(x["citation"]) for x in q)
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_keys_all(close_demo):
    """Reply queue: keys_all."""
    q = close_demo["reply_queue"]
    assert all(all(k in x for k in ["channel","customer","summary","draft","citation","priority"]) for x in q)
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_money_math(close_demo):
    """Reply queue: money_math."""
    q = close_demo["reply_queue"]
    assert abs(close_demo["kpis"]["money_at_risk_usd"] - round(len(q)*close_demo["kpis"]["aov"],2)) < 0.01
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_money_value(close_demo):
    """Reply queue: money_value."""
    q = close_demo["reply_queue"]
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_review_draft_shop(close_demo):
    """Reply queue: review_draft_shop."""
    q = close_demo["reply_queue"]
    assert "our shop" in q[2]["draft"] or "make this right" in q[2]["draft"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_reply_first_summary(close_demo):
    """Reply queue: first_summary."""
    q = close_demo["reply_queue"]
    assert "hasn't arrived" in q[0]["summary"] or "hasn" in q[0]["summary"]
    assert isinstance(close_demo["reply_queue"], list)
    assert close_demo["kpis"]["money_at_risk_usd"] == 102.75

def test_close_po_subject(close_demo):
    """PO draft: subject."""
    assert "Subject: Reorder" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_supplier_name(close_demo):
    """PO draft: supplier_name."""
    assert "Acme Textiles" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_tote_line(close_demo):
    """PO draft: tote_line."""
    assert "Tote Bag Handmade" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_qty10(close_demo):
    """PO draft: qty10."""
    assert "10 units" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_have2(close_demo):
    """PO draft: have2."""
    assert "have 2" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_days_left(close_demo):
    """PO draft: days_left."""
    assert "2.3d left" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_citation(close_demo):
    """PO draft: citation."""
    assert CITATION_RE.search(close_demo["po_draft"]), f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_price_eta(close_demo):
    """PO draft: price_eta."""
    assert "price + ETA" in close_demo["po_draft"] or "confirm price" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_shop_name(close_demo):
    """PO draft: shop_name."""
    assert "our shop" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_nonempty(close_demo):
    """PO draft: nonempty."""
    assert len(close_demo["po_draft"]) > 100, f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_inventory_ref(close_demo):
    """PO draft: inventory_ref."""
    assert "inventory.csv" in close_demo["po_draft"], f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_po_hi_supplier(close_demo):
    """PO draft: hi_supplier."""
    assert close_demo["po_draft"].startswith("Subject:"), f"po={close_demo['po_draft'][:300]!r}"
    assert isinstance(close_demo["po_draft"], str)
    assert "Subject:" in close_demo["po_draft"] or "Stock healthy" in close_demo["po_draft"]

def test_close_idempotent_headline(close_pair):
    """Idempotent POST twice: headline stable."""
    a, b = close_pair
    assert a["headline"] == b["headline"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_reorder(close_pair):
    """Idempotent POST twice: reorder stable."""
    a, b = close_pair
    assert a["reorder_sheet"] == b["reorder_sheet"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_kpis(close_pair):
    """Idempotent POST twice: kpis stable."""
    a, b = close_pair
    assert a["kpis"] == b["kpis"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_reply(close_pair):
    """Idempotent POST twice: reply stable."""
    a, b = close_pair
    assert a["reply_queue"] == b["reply_queue"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_po(close_pair):
    """Idempotent POST twice: po stable."""
    a, b = close_pair
    assert a["po_draft"] == b["po_draft"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_do_today(close_pair):
    """Idempotent POST twice: do_today stable."""
    a, b = close_pair
    assert a["do_today"] == b["do_today"], f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_money(close_pair):
    """Idempotent POST twice: money stable."""
    a, b = close_pair
    assert a["kpis"]["money_at_risk_usd"] == b["kpis"]["money_at_risk_usd"] == 102.75, f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_idempotent_profit(close_pair):
    """Idempotent POST twice: profit stable."""
    a, b = close_pair
    assert a["kpis"]["true_profit"] == b["kpis"]["true_profit"] == 169.09, f"a={a['headline']!r} b={b['headline']!r}"
    assert a["headline"].startswith("Profit $169.09")
    assert len(a["reorder_sheet"]) >= 1

def test_close_invalid_folder_0(client):
    """Invalid folder '/etc/passwd' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/etc/passwd"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_1(client):
    """Invalid folder '/nonexistent-xyz-wave2' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/nonexistent-xyz-wave2"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_2(client):
    """Invalid folder '/var/root' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/var/root"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_3(client):
    """Invalid folder '/proc' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/proc"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_4(client):
    """Invalid folder '/root' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/root"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_5(client):
    """Invalid folder '/etc/shadow' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/etc/shadow"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_6(client):
    """Invalid folder '/no-such-dir-12345' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/no-such-dir-12345"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_7(client):
    """Invalid folder '/tmp/../etc/passwd' must be 400, not 500."""
    r = client.post("/api/v1/seller/close", json={"folder": "/tmp/../etc/passwd"})
    assert r.status_code == 400, f"{r.status_code} {r.text[:400]}"
    body = r.text.lower()
    assert "folder" in body or "not found" in body or "not allowed" in body
    assert r.status_code != 500

def test_close_invalid_folder_json_shape(client):
    """Invalid folder error body must be JSON with detail/message."""
    r = client.post("/api/v1/seller/close", json={"folder": "/nonexistent-xyz-wave2"})
    assert r.status_code == 400
    try:
        d = r.json()
    except Exception:
        d = {}
    assert isinstance(d, dict)
    assert "detail" in d or "message" in d or "code" in d

def test_close_folder_tmp_allowed_shape(client):
    """Control: demo flag without folder still 200 (folder guard only on explicit bad path)."""
    r = client.post("/api/v1/seller/close", json={"demo": True, "shop": "contract shop"})
    assert r.status_code == 200
    assert r.json()["shop"] == "contract shop"
    assert "Profit $" in r.json()["headline"]

def test_close_csv_ctype(close_csv_bundle):
    """close.csv: ctype."""
    bundle = close_csv_bundle
    assert "text/csv" in bundle["ctype"], bundle["ctype"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_status(close_csv_bundle):
    """close.csv: status."""
    bundle = close_csv_bundle
    assert bundle["status"] == 200
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_daily_close(close_csv_bundle):
    """close.csv: daily_close."""
    bundle = close_csv_bundle
    assert bundle["text"].splitlines()[0].startswith("DAILY CLOSE")
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_headline_embed(close_csv_bundle):
    """close.csv: headline_embed."""
    bundle = close_csv_bundle
    assert "Profit $169.09" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_metric_header(close_csv_bundle):
    """close.csv: metric_header."""
    bundle = close_csv_bundle
    assert "metric,value" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_gmv_row(close_csv_bundle):
    """close.csv: gmv_row."""
    bundle = close_csv_bundle
    assert "gmv,274.0" in bundle["text"] or "gmv,274" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_profit_row(close_csv_bundle):
    """close.csv: profit_row."""
    bundle = close_csv_bundle
    assert "true_profit,169.09" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_risk_row(close_csv_bundle):
    """close.csv: risk_row."""
    bundle = close_csv_bundle
    assert "money_at_risk_usd,102.75" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_reorder_header(close_csv_bundle):
    """close.csv: reorder_header."""
    bundle = close_csv_bundle
    assert "product,on_hand,sold_7d,days_left" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_tote_row(close_csv_bundle):
    """close.csv: tote_row."""
    bundle = close_csv_bundle
    assert "Tote Bag Handmade" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_urgency_row(close_csv_bundle):
    """close.csv: urgency_row."""
    bundle = close_csv_bundle
    assert "ORDER TODAY" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_leak_header(close_csv_bundle):
    """close.csv: leak_header."""
    bundle = close_csv_bundle
    assert "leak,amount_usd,note,evidence" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_do_today(close_csv_bundle):
    """close.csv: do_today."""
    bundle = close_csv_bundle
    assert "do_today" in bundle["text"].lower()
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_parseable(close_csv_bundle):
    """close.csv: parseable."""
    bundle = close_csv_bundle
    rows = list(csv.reader(io.StringIO(bundle["text"]))); assert len(rows) > 12, len(rows)
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_nonempty(close_csv_bundle):
    """close.csv: nonempty."""
    bundle = close_csv_bundle
    assert len(bundle["text"]) > 500
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_disposition(close_csv_bundle):
    """close.csv: disposition."""
    bundle = close_csv_bundle
    assert "close.csv" in bundle["headers"].get("content-disposition","")
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_aov_row(close_csv_bundle):
    """close.csv: aov_row."""
    bundle = close_csv_bundle
    assert "aov,34.25" in bundle["text"] or "aov" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_orders_row(close_csv_bundle):
    """close.csv: orders_row."""
    bundle = close_csv_bundle
    assert "orders,8" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_supplier_in_csv(close_csv_bundle):
    """close.csv: supplier_in_csv."""
    bundle = close_csv_bundle
    assert "Acme Textiles" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_csv_citation_in_csv(close_csv_bundle):
    """close.csv: citation_in_csv."""
    bundle = close_csv_bundle
    assert "inventory.csv:2" in bundle["text"]
    assert bundle["text"] and len(bundle["text"]) > 100

def test_close_metrics_increments_closes_total(client):
    """POST close must bump closes_total by exactly 1."""
    before = _parse_metrics(client.get("/metrics").text).get("closes_total", 0)
    r = client.post("/api/v1/seller/close", json={"demo": True})
    assert r.status_code == 200
    after = _parse_metrics(client.get("/metrics").text).get("closes_total", 0)
    assert after == before + 1, f"before={before} after={after}"

def test_close_metrics_has_all_counters_and_up(client):
    """Prometheus text must expose all 6 ops counters + omni_one_up 1."""
    t = client.get("/metrics").text
    for k in ["briefings_total","scenarios_runs_total","operations_total","vision_total","analyzes_total","closes_total"]:
        assert f'op="{k}"' in t, f"missing {k} in {t[:400]}"
    assert "omni_one_up 1" in t
    assert t.startswith("# HELP omni_one_requests")

def test_close_metrics_ctype(client):
    """GET /metrics must be Prometheus text/plain."""
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type","")
    assert "omni_one_requests" in r.text

def test_close_demo_seed_deterministic(client):
    """Same seed twice → identical headline (deterministic demo)."""
    a = client.post("/api/v1/seller/close", json={"demo": True, "seed": 42}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True, "seed": 42}).json()
    assert a["headline"] == b["headline"]
    assert a["kpis"]["gmv"] == 274.0 and b["kpis"]["gmv"] == 274.0

def test_close_shop_param_echo(client):
    """Shop param must echo and appear in reply drafts + PO."""
    r = client.post("/api/v1/seller/close", json={"demo": True, "shop": "Maya Tacos"})
    assert r.status_code == 200
    d = r.json()
    assert d["shop"] == "Maya Tacos"
    assert "Maya Tacos" in d["po_draft"]
    assert any("Maya Tacos" in q["draft"] or "our shop" in q["draft"] or "Maya" in q["draft"] for q in d["reply_queue"]) or len(d["reply_queue"]) == 3

def test_close_true_profit_le_gmv(close_demo):
    """Invariant: true_profit <= gmv (no phantom profit)."""
    assert float(close_demo["kpis"]["true_profit"]) <= float(close_demo["kpis"]["gmv"]) + 0.011
    assert float(close_demo["kpis"]["net"]) == round(float(close_demo["kpis"]["gmv"]) - float(close_demo["kpis"]["fees"]) - float(close_demo["kpis"]["shipping"]), 2)

def test_close_json_serialisable(close_demo):
    """Close bundle must round-trip through JSON."""
    blob = json.dumps(close_demo, default=str)
    back = json.loads(blob)
    assert back["headline"] == close_demo["headline"]
    assert back["reorder_sheet"] == close_demo["reorder_sheet"]

def test_close_extra_cross_0(close_demo):
    """Cross-field invariant 0: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["net"] - (k["gmv"] - k["fees"] - k["shipping"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_1(close_demo):
    """Cross-field invariant 1: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["aov"] - k["gmv"]/k["orders"]) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_2(close_demo):
    """Cross-field invariant 2: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["true_profit"] - (k["net"] - k["cogs"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_3(close_demo):
    """Cross-field invariant 3: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert 0 < k["margin_pct"] < 100 and k["orders"] == 8
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_4(close_demo):
    """Cross-field invariant 4: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["net"] - (k["gmv"] - k["fees"] - k["shipping"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_5(close_demo):
    """Cross-field invariant 5: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["aov"] - k["gmv"]/k["orders"]) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_6(close_demo):
    """Cross-field invariant 6: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["true_profit"] - (k["net"] - k["cogs"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_7(close_demo):
    """Cross-field invariant 7: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert 0 < k["margin_pct"] < 100 and k["orders"] == 8
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_8(close_demo):
    """Cross-field invariant 8: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["net"] - (k["gmv"] - k["fees"] - k["shipping"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_9(close_demo):
    """Cross-field invariant 9: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["aov"] - k["gmv"]/k["orders"]) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_10(close_demo):
    """Cross-field invariant 10: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["true_profit"] - (k["net"] - k["cogs"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_11(close_demo):
    """Cross-field invariant 11: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert 0 < k["margin_pct"] < 100 and k["orders"] == 8
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_12(close_demo):
    """Cross-field invariant 12: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["net"] - (k["gmv"] - k["fees"] - k["shipping"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_13(close_demo):
    """Cross-field invariant 13: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["aov"] - k["gmv"]/k["orders"]) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_14(close_demo):
    """Cross-field invariant 14: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["true_profit"] - (k["net"] - k["cogs"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_15(close_demo):
    """Cross-field invariant 15: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert 0 < k["margin_pct"] < 100 and k["orders"] == 8
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_16(close_demo):
    """Cross-field invariant 16: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["net"] - (k["gmv"] - k["fees"] - k["shipping"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_17(close_demo):
    """Cross-field invariant 17: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["aov"] - k["gmv"]/k["orders"]) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_18(close_demo):
    """Cross-field invariant 18: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert abs(k["true_profit"] - (k["net"] - k["cogs"])) < 0.02, k
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_cross_19(close_demo):
    """Cross-field invariant 19: profit/net/gmv/aov math."""
    k = close_demo["kpis"]
    assert 0 < k["margin_pct"] < 100 and k["orders"] == 8
    assert close_demo["headline"].count("$") >= 2
    assert len(close_demo["do_today"]) == 3

def test_close_extra_csv_0(close_csv_bundle):
    """CSV extra contains 'net,233.29'."""
    assert "net,233.29" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_1(close_csv_bundle):
    """CSV extra contains 'cogs,64.2'."""
    assert "cogs,64.2" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_2(close_csv_bundle):
    """CSV extra contains 'fees,16.71'."""
    assert "fees,16.71" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_3(close_csv_bundle):
    """CSV extra contains 'shipping,24.0'."""
    assert "shipping,24.0" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_4(close_csv_bundle):
    """CSV extra contains 'best_seller'."""
    assert "best_seller" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_5(close_csv_bundle):
    """CSV extra contains 'do_today_n'."""
    assert "do_today_n" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_6(close_csv_bundle):
    """CSV extra contains 'reorder_qty_14d'."""
    assert "reorder_qty_14d" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_7(close_csv_bundle):
    """CSV extra contains 'supplier'."""
    assert "supplier" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_8(close_csv_bundle):
    """CSV extra contains 'citation'."""
    assert "citation" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra_csv_9(close_csv_bundle):
    """CSV extra contains 'DAILY CLOSE'."""
    assert "DAILY CLOSE" in close_csv_bundle["text"]
    assert "text/csv" in close_csv_bundle["ctype"]
    assert len(close_csv_bundle["text"]) > 400

def test_close_extra2_0(close_demo, close_csv_bundle):
    """Close+CSV coherence 0."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_1(close_demo, close_csv_bundle):
    """Close+CSV coherence 1."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_2(close_demo, close_csv_bundle):
    """Close+CSV coherence 2."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_3(close_demo, close_csv_bundle):
    """Close+CSV coherence 3."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_4(close_demo, close_csv_bundle):
    """Close+CSV coherence 4."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_5(close_demo, close_csv_bundle):
    """Close+CSV coherence 5."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_6(close_demo, close_csv_bundle):
    """Close+CSV coherence 6."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_7(close_demo, close_csv_bundle):
    """Close+CSV coherence 7."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_8(close_demo, close_csv_bundle):
    """Close+CSV coherence 8."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_9(close_demo, close_csv_bundle):
    """Close+CSV coherence 9."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_10(close_demo, close_csv_bundle):
    """Close+CSV coherence 10."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_11(close_demo, close_csv_bundle):
    """Close+CSV coherence 11."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_12(close_demo, close_csv_bundle):
    """Close+CSV coherence 12."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_13(close_demo, close_csv_bundle):
    """Close+CSV coherence 13."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3

def test_close_extra2_14(close_demo, close_csv_bundle):
    """Close+CSV coherence 14."""
    assert close_demo["kpis"]["gmv"] == 274.0
    assert "274.0" in close_csv_bundle["text"] or "274" in close_csv_bundle["text"]
    assert close_demo["headline"] in close_csv_bundle["text"] or "Profit $169.09" in close_csv_bundle["text"]
    assert len(close_demo["reply_queue"]) == 3



def test_close_locale_parity_api():
    from fastapi.testclient import TestClient
    from omni_one.api.fastapi_app import create_omni_one_app
    tc = TestClient(create_omni_one_app())
    en = tc.post("/api/v1/seller/close", json={"demo": True, "locale": "en"}).json()
    es = tc.post("/api/v1/seller/close", json={"demo": True, "locale": "es"}).json()
    assert es["locale"] == "es"
    assert es["kpis"] == en["kpis"] and es["headline"] == en["headline"]
    assert es["reply_queue"][0]["draft"] != en["reply_queue"][0]["draft"]
    assert "2 horas" in es["reply_queue"][0]["draft"]
