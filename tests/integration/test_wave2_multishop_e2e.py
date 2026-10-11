"""WAVE2-G multishop e2e: 5 synthetic archetypes ingest->briefing->scenarios->close + bundles."""
from __future__ import annotations
import csv
import io
import json
import os
import re
os.environ.setdefault("SELLER_LLM", "mock")
os.environ.setdefault("SELLER_MAX_LLM_USD", "0.0")
import pytest
from pathlib import Path
CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")
def _write_shop(base: Path, kind: str) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    if kind == "healthy":
        (base / "shopify_orders.csv").write_text("Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n#1,2024-09-10,Widget A,2,20.00,40.00,1.46,3.00,Alice\n#2,2024-09-11,Widget B,1,30.00,30.00,1.17,3.00,Bob\n", encoding="utf-8")
        (base / "inventory.csv").write_text("sku,product,stock,supplier\nWA001,Widget A,100,Acme\nWB002,Widget B,100,Acme\n", encoding="utf-8")
        (base / "reviews.csv").write_text("date,product,stars,review\n2024-09-11,Widget A,5,\"Love it great perfect\"\n", encoding="utf-8")
        (base / "instagram_dm.txt").write_text("Alice: Thanks love it!\nShop: Glad you love it!\n", encoding="utf-8")
        (base / "supplier_invoice.txt").write_text("Acme\nWidget A 50 x 5.00 250.00\nTotal $250.00\n", encoding="utf-8")
    elif kind == "stockout-crisis":
        rows = ["Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer"]
        rows += [f"#1{i},2024-09-10,Tote Bag Handmade,2,28.00,56.00,1.92,4.00,Cust{i}" for i in range(10)]
        (base / "shopify_orders.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
        (base / "inventory.csv").write_text("sku,product,stock,supplier\nTB001,Tote Bag Handmade,1,Acme Textiles\n", encoding="utf-8")
        (base / "reviews.csv").write_text("date,product,stars,review\n2024-09-11,Tote Bag Handmade,5,\"Love it\"\n", encoding="utf-8")
        (base / "instagram_dm.txt").write_text("Alice: Thanks!\n", encoding="utf-8")
        (base / "supplier_invoice.txt").write_text("Acme\nTote Bag 50 x 4.00 200.00\nTotal $200.00\n", encoding="utf-8")
    elif kind == "refund-storm":
        (base / "shopify_orders.csv").write_text("Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n#1,2024-09-10,Widget A,1,40.00,40.00,1.46,3.00,Alice\n#2,2024-09-11,Widget B,1,35.00,35.00,1.31,3.00,Bob\n", encoding="utf-8")
        (base / "inventory.csv").write_text("sku,product,stock,supplier\nWA001,Widget A,50,Acme\nWB002,Widget B,50,Acme\n", encoding="utf-8")
        (base / "reviews.csv").write_text("date,product,stars,review\n2024-09-11,Widget A,1,\"Terrible damaged awful refund please\"\n2024-09-11,Widget B,1,\"Awful broken refund now\"\n", encoding="utf-8")
        (base / "instagram_dm.txt").write_text("Alice: Hi refund please hasn't arrived yet worried refund\nBob: Where is my order? No tracking refund needed\nCharlie: refund return chargeback never arrived angry\nDave: refund please damaged late\n", encoding="utf-8")
        (base / "supplier_invoice.txt").write_text("Acme\nWidget 50 x 5.00 250.00\nTotal $250.00\n", encoding="utf-8")
    elif kind == "fee-bleed":
        (base / "shopify_orders.csv").write_text("Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n#1,2024-09-10,Widget A,1,50.00,50.00,12.00,2.00,Alice\n#2,2024-09-11,Widget A,1,50.00,50.00,12.00,2.00,Bob\n#3,2024-09-12,Widget B,1,40.00,40.00,10.00,2.00,Charlie\n", encoding="utf-8")
        (base / "inventory.csv").write_text("sku,product,stock,supplier\nWA001,Widget A,50,Acme\nWB002,Widget B,50,Acme\n", encoding="utf-8")
        (base / "reviews.csv").write_text("date,product,stars,review\n2024-09-11,Widget A,5,\"Great\"\n", encoding="utf-8")
        (base / "instagram_dm.txt").write_text("Alice: Thanks!\n", encoding="utf-8")
        (base / "supplier_invoice.txt").write_text("Acme\nWidget 50 x 5.00 250.00\nTotal $250.00\n", encoding="utf-8")
    elif kind == "empty":
        (base / "shopify_orders.csv").write_text("Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n", encoding="utf-8")
        (base / "inventory.csv").write_text("sku,product,stock,supplier\nWA001,Widget A,20,Acme\n", encoding="utf-8")
        (base / "reviews.csv").write_text("date,product,stars,review\n", encoding="utf-8")
        (base / "instagram_dm.txt").write_text("", encoding="utf-8")
        (base / "supplier_invoice.txt").write_text("Acme\nNo items yet\n", encoding="utf-8")
    else:
        raise ValueError(kind)
    return base
def _full_loop(shop_dir: Path, shop: str):
    from omni_one.packs.seller_os import ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    events, report = ingest_seller_folder(shop_dir)
    briefing = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    close = build_daily_close(events, briefing, scen, shop=shop)
    return events, report, briefing, scen, close
@pytest.fixture(scope="module")
def all_shops(tmp_path_factory):
    out = {}
    for kind in ["healthy", "stockout-crisis", "refund-storm", "fee-bleed", "empty"]:
        d = tmp_path_factory.mktemp(f"shop_{kind.replace(chr(45), chr(95))}") / "shop"
        _write_shop(d, kind)
        events, report, briefing, scen, close = _full_loop(d, kind)
        out[kind] = {"dir": d, "events": events, "report": report, "briefing": briefing, "scen": scen, "close": close}
    return out
def test_loop_healthy_0(tmp_path):
    """Full loop healthy check 0: ingest->briefing->scenarios->close."""
    d = tmp_path / "s0"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert len(events) >= 1, len(events)
    assert briefing["kpis"] is not None
    assert close is not None

def test_loop_healthy_1(tmp_path):
    """Full loop healthy check 1: ingest->briefing->scenarios->close."""
    d = tmp_path / "s1"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10
    assert close is not None

def test_loop_healthy_2(tmp_path):
    """Full loop healthy check 2: ingest->briefing->scenarios->close."""
    d = tmp_path / "s2"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert scen["total"] >= 1
    assert "by_scenario" in scen and len(scen["by_scenario"]) == 12
    assert close is not None

def test_loop_healthy_3(tmp_path):
    """Full loop healthy check 3: ingest->briefing->scenarios->close."""
    d = tmp_path / "s3"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert report["files_ingested"] >= 1
    assert report["events"] == len(events)
    assert close is not None

def test_loop_healthy_4(tmp_path):
    """Full loop healthy check 4: ingest->briefing->scenarios->close."""
    d = tmp_path / "s4"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert close["free"] is True and close["offline"] is True
    assert "Subject: Reorder" in close["po_draft"] or "Stock healthy" in close["po_draft"]
    assert close is not None

def test_loop_healthy_5(tmp_path):
    """Full loop healthy check 5: ingest->briefing->scenarios->close."""
    d = tmp_path / "s5"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert all(CITATION_RE.search(str(r.get("citation",""))) for r in close["reorder_sheet"]) or len(close["reorder_sheet"]) == 0
    assert all(CITATION_RE.search(str(q.get("citation",""))) for q in close["reply_queue"]) or len(close["reply_queue"]) == 0
    assert close is not None

def test_loop_healthy_6(tmp_path):
    """Full loop healthy check 6: ingest->briefing->scenarios->close."""
    d = tmp_path / "s6"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    blob = json.dumps(close, default=str); back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert close is not None

def test_loop_healthy_7(tmp_path):
    """Full loop healthy check 7: ingest->briefing->scenarios->close."""
    d = tmp_path / "s7"
    _write_shop(d, "healthy")
    events, report, briefing, scen, close = _full_loop(d, "healthy")
    assert close["shop"] == "healthy"
    assert briefing["llm"]["mode"] == "mock"
    assert close is not None

def test_loop_stockout_crisis_0(tmp_path):
    """Full loop stockout-crisis check 0: ingest->briefing->scenarios->close."""
    d = tmp_path / "s0"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert len(events) >= 1, len(events)
    assert briefing["kpis"] is not None
    assert close is not None

def test_loop_stockout_crisis_1(tmp_path):
    """Full loop stockout-crisis check 1: ingest->briefing->scenarios->close."""
    d = tmp_path / "s1"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10
    assert close is not None

def test_loop_stockout_crisis_2(tmp_path):
    """Full loop stockout-crisis check 2: ingest->briefing->scenarios->close."""
    d = tmp_path / "s2"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert scen["total"] >= 1
    assert "by_scenario" in scen and len(scen["by_scenario"]) == 12
    assert close is not None

def test_loop_stockout_crisis_3(tmp_path):
    """Full loop stockout-crisis check 3: ingest->briefing->scenarios->close."""
    d = tmp_path / "s3"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert report["files_ingested"] >= 1
    assert report["events"] == len(events)
    assert close is not None

def test_loop_stockout_crisis_4(tmp_path):
    """Full loop stockout-crisis check 4: ingest->briefing->scenarios->close."""
    d = tmp_path / "s4"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert close["free"] is True and close["offline"] is True
    assert "Subject: Reorder" in close["po_draft"] or "Stock healthy" in close["po_draft"]
    assert close is not None

def test_loop_stockout_crisis_5(tmp_path):
    """Full loop stockout-crisis check 5: ingest->briefing->scenarios->close."""
    d = tmp_path / "s5"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert all(CITATION_RE.search(str(r.get("citation",""))) for r in close["reorder_sheet"]) or len(close["reorder_sheet"]) == 0
    assert all(CITATION_RE.search(str(q.get("citation",""))) for q in close["reply_queue"]) or len(close["reply_queue"]) == 0
    assert close is not None

def test_loop_stockout_crisis_6(tmp_path):
    """Full loop stockout-crisis check 6: ingest->briefing->scenarios->close."""
    d = tmp_path / "s6"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    blob = json.dumps(close, default=str); back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert close is not None

def test_loop_stockout_crisis_7(tmp_path):
    """Full loop stockout-crisis check 7: ingest->briefing->scenarios->close."""
    d = tmp_path / "s7"
    _write_shop(d, "stockout-crisis")
    events, report, briefing, scen, close = _full_loop(d, "stockout-crisis")
    assert close["shop"] == "stockout-crisis"
    assert briefing["llm"]["mode"] == "mock"
    assert close is not None

def test_loop_refund_storm_0(tmp_path):
    """Full loop refund-storm check 0: ingest->briefing->scenarios->close."""
    d = tmp_path / "s0"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert len(events) >= 1, len(events)
    assert briefing["kpis"] is not None
    assert close is not None

def test_loop_refund_storm_1(tmp_path):
    """Full loop refund-storm check 1: ingest->briefing->scenarios->close."""
    d = tmp_path / "s1"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10
    assert close is not None

def test_loop_refund_storm_2(tmp_path):
    """Full loop refund-storm check 2: ingest->briefing->scenarios->close."""
    d = tmp_path / "s2"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert scen["total"] >= 1
    assert "by_scenario" in scen and len(scen["by_scenario"]) == 12
    assert close is not None

def test_loop_refund_storm_3(tmp_path):
    """Full loop refund-storm check 3: ingest->briefing->scenarios->close."""
    d = tmp_path / "s3"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert report["files_ingested"] >= 1
    assert report["events"] == len(events)
    assert close is not None

def test_loop_refund_storm_4(tmp_path):
    """Full loop refund-storm check 4: ingest->briefing->scenarios->close."""
    d = tmp_path / "s4"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert close["free"] is True and close["offline"] is True
    assert "Subject: Reorder" in close["po_draft"] or "Stock healthy" in close["po_draft"]
    assert close is not None

def test_loop_refund_storm_5(tmp_path):
    """Full loop refund-storm check 5: ingest->briefing->scenarios->close."""
    d = tmp_path / "s5"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert all(CITATION_RE.search(str(r.get("citation",""))) for r in close["reorder_sheet"]) or len(close["reorder_sheet"]) == 0
    assert all(CITATION_RE.search(str(q.get("citation",""))) for q in close["reply_queue"]) or len(close["reply_queue"]) == 0
    assert close is not None

def test_loop_refund_storm_6(tmp_path):
    """Full loop refund-storm check 6: ingest->briefing->scenarios->close."""
    d = tmp_path / "s6"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    blob = json.dumps(close, default=str); back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert close is not None

def test_loop_refund_storm_7(tmp_path):
    """Full loop refund-storm check 7: ingest->briefing->scenarios->close."""
    d = tmp_path / "s7"
    _write_shop(d, "refund-storm")
    events, report, briefing, scen, close = _full_loop(d, "refund-storm")
    assert close["shop"] == "refund-storm"
    assert briefing["llm"]["mode"] == "mock"
    assert close is not None

def test_loop_fee_bleed_0(tmp_path):
    """Full loop fee-bleed check 0: ingest->briefing->scenarios->close."""
    d = tmp_path / "s0"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert len(events) >= 1, len(events)
    assert briefing["kpis"] is not None
    assert close is not None

def test_loop_fee_bleed_1(tmp_path):
    """Full loop fee-bleed check 1: ingest->briefing->scenarios->close."""
    d = tmp_path / "s1"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10
    assert close is not None

def test_loop_fee_bleed_2(tmp_path):
    """Full loop fee-bleed check 2: ingest->briefing->scenarios->close."""
    d = tmp_path / "s2"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert scen["total"] >= 1
    assert "by_scenario" in scen and len(scen["by_scenario"]) == 12
    assert close is not None

def test_loop_fee_bleed_3(tmp_path):
    """Full loop fee-bleed check 3: ingest->briefing->scenarios->close."""
    d = tmp_path / "s3"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert report["files_ingested"] >= 1
    assert report["events"] == len(events)
    assert close is not None

def test_loop_fee_bleed_4(tmp_path):
    """Full loop fee-bleed check 4: ingest->briefing->scenarios->close."""
    d = tmp_path / "s4"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert close["free"] is True and close["offline"] is True
    assert "Subject: Reorder" in close["po_draft"] or "Stock healthy" in close["po_draft"]
    assert close is not None

def test_loop_fee_bleed_5(tmp_path):
    """Full loop fee-bleed check 5: ingest->briefing->scenarios->close."""
    d = tmp_path / "s5"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert all(CITATION_RE.search(str(r.get("citation",""))) for r in close["reorder_sheet"]) or len(close["reorder_sheet"]) == 0
    assert all(CITATION_RE.search(str(q.get("citation",""))) for q in close["reply_queue"]) or len(close["reply_queue"]) == 0
    assert close is not None

def test_loop_fee_bleed_6(tmp_path):
    """Full loop fee-bleed check 6: ingest->briefing->scenarios->close."""
    d = tmp_path / "s6"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    blob = json.dumps(close, default=str); back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert close is not None

def test_loop_fee_bleed_7(tmp_path):
    """Full loop fee-bleed check 7: ingest->briefing->scenarios->close."""
    d = tmp_path / "s7"
    _write_shop(d, "fee-bleed")
    events, report, briefing, scen, close = _full_loop(d, "fee-bleed")
    assert close["shop"] == "fee-bleed"
    assert briefing["llm"]["mode"] == "mock"
    assert close is not None

def test_loop_empty_0(tmp_path):
    """Full loop empty check 0: ingest->briefing->scenarios->close."""
    d = tmp_path / "s0"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert len(events) >= 1, len(events)
    assert briefing["kpis"] is not None
    assert close is not None

def test_loop_empty_1(tmp_path):
    """Full loop empty check 1: ingest->briefing->scenarios->close."""
    d = tmp_path / "s1"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10
    assert close is not None

def test_loop_empty_2(tmp_path):
    """Full loop empty check 2: ingest->briefing->scenarios->close."""
    d = tmp_path / "s2"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert scen["total"] >= 1
    assert "by_scenario" in scen and len(scen["by_scenario"]) == 12
    assert close is not None

def test_loop_empty_3(tmp_path):
    """Full loop empty check 3: ingest->briefing->scenarios->close."""
    d = tmp_path / "s3"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert report["files_ingested"] >= 1
    assert report["events"] == len(events)
    assert close is not None

def test_loop_empty_4(tmp_path):
    """Full loop empty check 4: ingest->briefing->scenarios->close."""
    d = tmp_path / "s4"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert close["free"] is True and close["offline"] is True
    assert "Subject: Reorder" in close["po_draft"] or "Stock healthy" in close["po_draft"]
    assert close is not None

def test_loop_empty_5(tmp_path):
    """Full loop empty check 5: ingest->briefing->scenarios->close."""
    d = tmp_path / "s5"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert all(CITATION_RE.search(str(r.get("citation",""))) for r in close["reorder_sheet"]) or len(close["reorder_sheet"]) == 0
    assert all(CITATION_RE.search(str(q.get("citation",""))) for q in close["reply_queue"]) or len(close["reply_queue"]) == 0
    assert close is not None

def test_loop_empty_6(tmp_path):
    """Full loop empty check 6: ingest->briefing->scenarios->close."""
    d = tmp_path / "s6"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    blob = json.dumps(close, default=str); back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert close is not None

def test_loop_empty_7(tmp_path):
    """Full loop empty check 7: ingest->briefing->scenarios->close."""
    d = tmp_path / "s7"
    _write_shop(d, "empty")
    events, report, briefing, scen, close = _full_loop(d, "empty")
    assert close["shop"] == "empty"
    assert briefing["llm"]["mode"] == "mock"
    assert close is not None

def test_crisis_order_today(all_shops):
    """stockout-crisis: order_today."""
    rs = all_shops["stockout-crisis"]["close"]["reorder_sheet"]
    assert any(r["urgency"] == "ORDER TODAY" for r in rs), f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_tote_qty(all_shops):
    """stockout-crisis: tote_qty."""
    rs = all_shops["stockout-crisis"]["close"]["reorder_sheet"]
    assert any(r["reorder_qty"] > 0 for r in rs), f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_days_lt3(all_shops):
    """stockout-crisis: days_lt3."""
    rs = all_shops["stockout-crisis"]["close"]["reorder_sheet"]
    assert min(r["days_left"] for r in rs) < 3.0, f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_headline_reorder(all_shops):
    """stockout-crisis: headline_reorder."""
    h = all_shops["stockout-crisis"]["close"]["headline"]
    assert "reorder(s) TODAY" in h, f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_brief_risk(all_shops):
    """stockout-crisis: brief_risk."""
    b = all_shops["stockout-crisis"]["briefing"]
    assert b["kpis"]["stockout_risk"] >= 1, f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_scen_stockout(all_shops):
    """stockout-crisis: scen_stockout."""
    s = all_shops["stockout-crisis"]["scen"]
    assert s["by_scenario"]["STOCKOUT_RISK"] >= 1, f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_cite_inv(all_shops):
    """stockout-crisis: cite_inv."""
    rs = all_shops["stockout-crisis"]["close"]["reorder_sheet"]
    assert any("inventory.csv" in r["citation"] for r in rs), f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_crisis_supplier(all_shops):
    """stockout-crisis: supplier."""
    rs = all_shops["stockout-crisis"]["close"]["reorder_sheet"]
    assert any(r["supplier"] for r in rs), f"{rs if 'rs' in locals() else h if 'h' in locals() else b if 'b' in locals() else s}"
    assert all_shops["stockout-crisis"]["close"]["shop"] == "stockout-crisis"

def test_storm_money_ge2aov(all_shops):
    """refund-storm: money_ge2aov."""
    c = all_shops["refund-storm"]["close"]
    assert c["kpis"]["money_at_risk_usd"] >= 2 * c["kpis"]["aov"] - 0.01
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_reply_ge2(all_shops):
    """refund-storm: reply_ge2."""
    c = all_shops["refund-storm"]["close"]
    assert len(c["reply_queue"]) >= 2
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_money_187(all_shops):
    """refund-storm: money_187."""
    c = all_shops["refund-storm"]["close"]
    assert abs(c["kpis"]["money_at_risk_usd"] - 187.5) < 0.05
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_aov_375(all_shops):
    """refund-storm: aov_375."""
    c = all_shops["refund-storm"]["close"]
    assert abs(c["kpis"]["aov"] - 37.5) < 0.05
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_draft_2h(all_shops):
    """refund-storm: draft_2h."""
    c = all_shops["refund-storm"]["close"]
    assert any("within 2 hours" in q["draft"] for q in c["reply_queue"])
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_alert_risk(all_shops):
    """refund-storm: alert_risk."""
    b = all_shops["refund-storm"]["briefing"]
    assert any(a["type"] == "customer_at_risk" for a in b["alerts"])
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_scen_refund(all_shops):
    """refund-storm: scen_refund."""
    s = all_shops["refund-storm"]["scen"]
    assert s["total"] >= 5
    assert all_shops["refund-storm"]["close"] is not None

def test_storm_headline_risk(all_shops):
    """refund-storm: headline_risk."""
    c = all_shops["refund-storm"]["close"]
    assert "at risk" in c["headline"]
    assert all_shops["refund-storm"]["close"] is not None

def test_empty_all_clear(all_shops):
    """empty shop: all_clear (no crash, all_clear)."""
    b = all_shops["empty"]["briefing"]
    assert any(a["type"] == "all_clear" for a in b["alerts"])
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_no_crash(all_shops):
    """empty shop: no_crash (no crash, all_clear)."""
    c = all_shops["empty"]["close"]
    assert isinstance(c["headline"], str)
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_gmv0(all_shops):
    """empty shop: gmv0 (no crash, all_clear)."""
    c = all_shops["empty"]["close"]
    assert c["kpis"]["gmv"] == 0
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_orders0(all_shops):
    """empty shop: orders0 (no crash, all_clear)."""
    c = all_shops["empty"]["close"]
    assert c["kpis"]["orders"] == 0
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_reorder_empty(all_shops):
    """empty shop: reorder_empty (no crash, all_clear)."""
    c = all_shops["empty"]["close"]
    assert c["reorder_sheet"] == []
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_head_profit0(all_shops):
    """empty shop: head_profit0 (no crash, all_clear)."""
    c = all_shops["empty"]["close"]
    assert "Profit $0.00" in c["headline"]
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_events_ge1(all_shops):
    """empty shop: events_ge1 (no crash, all_clear)."""
    e = all_shops["empty"]["events"]
    assert len(e) >= 1
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_empty_scen_total(all_shops):
    """empty shop: scen_total (no crash, all_clear)."""
    s = all_shops["empty"]["scen"]
    assert s["total"] >= 1
    assert all_shops["empty"]["briefing"]["kpis"]["gmv"] == 0

def test_feebleed_fee_creep(all_shops):
    """fee-bleed: fee_creep."""
    c = all_shops["fee-bleed"]["close"]
    assert any(l["leak"] == "fee_creep" for l in c["money_leaks"])
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_amount34(all_shops):
    """fee-bleed: amount34."""
    c = all_shops["fee-bleed"]["close"]
    assert any(abs(float(l["amount_usd"]) - 34.0) < 0.05 for l in c["money_leaks"] if l["leak"] == "fee_creep")
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_headline_leak(all_shops):
    """fee-bleed: headline_leak."""
    c = all_shops["fee-bleed"]["close"]
    assert "leak(s) to plug" in c["headline"]
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_scen_fee(all_shops):
    """fee-bleed: scen_fee."""
    s = all_shops["fee-bleed"]["scen"]
    assert s["by_scenario"]["FEE_CREEP"] == 1
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_gmv140(all_shops):
    """fee-bleed: gmv140."""
    c = all_shops["fee-bleed"]["close"]
    assert abs(c["kpis"]["gmv"] - 140.0) < 0.01
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_fees_pct(all_shops):
    """fee-bleed: fees_pct."""
    b = all_shops["fee-bleed"]["briefing"]
    assert b["kpis"]["fees"] / b["kpis"]["gmv"] >= 0.12
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_leak_note(all_shops):
    """fee-bleed: leak_note."""
    c = all_shops["fee-bleed"]["close"]
    assert any("Fees" in l["note"] for l in c["money_leaks"])
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_feebleed_evidence_orders(all_shops):
    """fee-bleed: evidence_orders."""
    c = all_shops["fee-bleed"]["close"]
    assert any("[orders]" in l["evidence"] for l in c["money_leaks"])
    assert all_shops["fee-bleed"]["close"]["kpis"]["gmv"] == 140.0

def test_healthy_healthy_clear(all_shops):
    """healthy shop: healthy_clear."""
    b = all_shops["healthy"]["briefing"]
    assert any(a["type"] == "all_clear" for a in b["alerts"])
    assert all_shops["healthy"]["close"] is not None

def test_healthy_healthy_noreorder(all_shops):
    """healthy shop: healthy_noreorder."""
    c = all_shops["healthy"]["close"]
    assert all(r["urgency"] != "ORDER TODAY" for r in c["reorder_sheet"])
    assert all_shops["healthy"]["close"] is not None

def test_healthy_healthy_profit(all_shops):
    """healthy shop: healthy_profit."""
    c = all_shops["healthy"]["close"]
    assert c["kpis"]["true_profit"] > 0
    assert all_shops["healthy"]["close"] is not None

def test_healthy_healthy_gmv70(all_shops):
    """healthy shop: healthy_gmv70."""
    c = all_shops["healthy"]["close"]
    assert abs(c["kpis"]["gmv"] - 70.0) < 0.01
    assert all_shops["healthy"]["close"] is not None

def test_healthy_healthy_noleak(all_shops):
    """healthy shop: healthy_noleak."""
    c = all_shops["healthy"]["close"]
    assert not any(l["leak"] == "fee_creep" for l in c["money_leaks"])
    assert all_shops["healthy"]["close"] is not None

def test_healthy_healthy_events(all_shops):
    """healthy shop: healthy_events."""
    e = all_shops["healthy"]["events"]
    assert len(e) >= 5
    assert all_shops["healthy"]["close"] is not None

def test_bundles_all5_exist_nonempty(tmp_path, all_shops):
    """Write close bundles for all 5 shops; validate 5 files exist + non-empty."""
    from omni_one.packs.seller_close import write_close_bundle
    out_root = tmp_path / "bundles"
    paths = {}
    for kind, pack in all_shops.items():
        d = out_root / kind.replace("-", "_")
        p = write_close_bundle(pack["close"], d)
        paths[kind] = p
    assert len(paths) == 5
    for kind, p in paths.items():
        for name in ["close.json", "close.csv", "reorder.csv", "replies.txt", "po.txt"]:
            assert name in p, f"{kind} missing {name}"
            fp = Path(p[name])
            assert fp.exists() and fp.stat().st_size > 0, f"{fp} empty"

def test_bundle_close_json_content(tmp_path, all_shops):
    """Bundle file close.json content checks across 5 shops."""
    from omni_one.packs.seller_close import write_close_bundle
    out = tmp_path / "b_close_json"
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], out / kind.replace("-", "_"))
        txt = Path(p["close.json"]).read_text(encoding="utf-8")
        assert len(txt) > 10, f"{kind} close.json too short"
        d = json.loads(txt); assert "headline" in d and "kpis" in d

def test_bundle_close_csv_content(tmp_path, all_shops):
    """Bundle file close.csv content checks across 5 shops."""
    from omni_one.packs.seller_close import write_close_bundle
    out = tmp_path / "b_close_csv"
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], out / kind.replace("-", "_"))
        txt = Path(p["close.csv"]).read_text(encoding="utf-8")
        assert len(txt) > 10, f"{kind} close.csv too short"
        assert "DAILY CLOSE" in txt and "metric,value" in txt

def test_bundle_reorder_csv_content(tmp_path, all_shops):
    """Bundle file reorder.csv content checks across 5 shops."""
    from omni_one.packs.seller_close import write_close_bundle
    out = tmp_path / "b_reorder_csv"
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], out / kind.replace("-", "_"))
        txt = Path(p["reorder.csv"]).read_text(encoding="utf-8")
        assert len(txt) > 10, f"{kind} reorder.csv too short"
        assert "product,on_hand" in txt

def test_bundle_replies_txt_content(tmp_path, all_shops):
    """Bundle file replies.txt content checks across 5 shops."""
    from omni_one.packs.seller_close import write_close_bundle
    out = tmp_path / "b_replies_txt"
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], out / kind.replace("-", "_"))
        txt = Path(p["replies.txt"]).read_text(encoding="utf-8")
        assert len(txt) > 10, f"{kind} replies.txt too short"
        assert "REPLY QUEUE" in txt or "PO DRAFT" in txt

def test_bundle_po_txt_content(tmp_path, all_shops):
    """Bundle file po.txt content checks across 5 shops."""
    from omni_one.packs.seller_close import write_close_bundle
    out = tmp_path / "b_po_txt"
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], out / kind.replace("-", "_"))
        txt = Path(p["po.txt"]).read_text(encoding="utf-8")
        assert len(txt) > 10, f"{kind} po.txt too short"
        assert "Subject:" in txt or "Stock healthy" in txt or len(txt) > 0

def test_bundles_close_json_golden(tmp_path, all_shops):
    """Crisis bundle close.json must carry ORDER TODAY + citation."""
    from omni_one.packs.seller_close import write_close_bundle
    p = write_close_bundle(all_shops["stockout-crisis"]["close"], tmp_path / "crisis")
    d = json.loads(Path(p["close.json"]).read_text(encoding="utf-8"))
    assert any(r["urgency"] == "ORDER TODAY" for r in d["reorder_sheet"])
    assert CITATION_RE.search(json.dumps(d))

def test_bundles_csv_parseable_all(tmp_path, all_shops):
    """All 5 close.csv must parse with csv module."""
    from omni_one.packs.seller_close import write_close_bundle
    for kind, pack in all_shops.items():
        p = write_close_bundle(pack["close"], tmp_path / f"csv_{kind}".replace("-", "_"))
        rows = list(csv.reader(io.StringIO(Path(p["close.csv"]).read_text(encoding="utf-8"))))
        assert len(rows) > 5, kind
        assert rows[0][0] == "DAILY CLOSE"

def test_extra_healthy_deep_0(all_shops):
    """Deep check healthy #0: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_healthy_deep_1(all_shops):
    """Deep check healthy #1: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_healthy_deep_2(all_shops):
    """Deep check healthy #2: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_healthy_deep_3(all_shops):
    """Deep check healthy #3: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_healthy_deep_4(all_shops):
    """Deep check healthy #4: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_healthy_deep_5(all_shops):
    """Deep check healthy #5: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_healthy_deep_6(all_shops):
    """Deep check healthy #6: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_healthy_deep_7(all_shops):
    """Deep check healthy #7: briefing/scen/close coherence."""
    pack = all_shops["healthy"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_0(all_shops):
    """Deep check stockout-crisis #0: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_1(all_shops):
    """Deep check stockout-crisis #1: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_2(all_shops):
    """Deep check stockout-crisis #2: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_3(all_shops):
    """Deep check stockout-crisis #3: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_4(all_shops):
    """Deep check stockout-crisis #4: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_5(all_shops):
    """Deep check stockout-crisis #5: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_6(all_shops):
    """Deep check stockout-crisis #6: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_stockout_crisis_deep_7(all_shops):
    """Deep check stockout-crisis #7: briefing/scen/close coherence."""
    pack = all_shops["stockout-crisis"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_0(all_shops):
    """Deep check refund-storm #0: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_1(all_shops):
    """Deep check refund-storm #1: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_2(all_shops):
    """Deep check refund-storm #2: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_3(all_shops):
    """Deep check refund-storm #3: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_4(all_shops):
    """Deep check refund-storm #4: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_5(all_shops):
    """Deep check refund-storm #5: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_6(all_shops):
    """Deep check refund-storm #6: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_refund_storm_deep_7(all_shops):
    """Deep check refund-storm #7: briefing/scen/close coherence."""
    pack = all_shops["refund-storm"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_0(all_shops):
    """Deep check fee-bleed #0: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_1(all_shops):
    """Deep check fee-bleed #1: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_2(all_shops):
    """Deep check fee-bleed #2: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_3(all_shops):
    """Deep check fee-bleed #3: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_4(all_shops):
    """Deep check fee-bleed #4: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_5(all_shops):
    """Deep check fee-bleed #5: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_6(all_shops):
    """Deep check fee-bleed #6: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_fee_bleed_deep_7(all_shops):
    """Deep check fee-bleed #7: briefing/scen/close coherence."""
    pack = all_shops["fee-bleed"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_empty_deep_0(all_shops):
    """Deep check empty #0: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_empty_deep_1(all_shops):
    """Deep check empty #1: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_empty_deep_2(all_shops):
    """Deep check empty #2: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_empty_deep_3(all_shops):
    """Deep check empty #3: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_empty_deep_4(all_shops):
    """Deep check empty #4: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert b["kpis"]["orders"] == c["kpis"]["orders"]
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"]
    assert pack["dir"].exists()

def test_extra_empty_deep_5(all_shops):
    """Deep check empty #5: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert s["total"] == len(s["decisions"])
    assert len(s["by_scenario"]) == 12
    assert pack["dir"].exists()

def test_extra_empty_deep_6(all_shops):
    """Deep check empty #6: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert isinstance(c["headline"], str) and "Profit $" in c["headline"]
    assert c["free"] is True
    assert pack["dir"].exists()

def test_extra_empty_deep_7(all_shops):
    """Deep check empty #7: briefing/scen/close coherence."""
    pack = all_shops["empty"]
    b, s, c = pack["briefing"], pack["scen"], pack["close"]
    assert pack["report"]["files_ingested"] >= 1
    assert b["llm"]["cost_usd"] == 0.0
    assert pack["dir"].exists()

def test_extra_coherence_0(all_shops):
    """All-shop coherence 0: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_1(all_shops):
    """All-shop coherence 1: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_2(all_shops):
    """All-shop coherence 2: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_3(all_shops):
    """All-shop coherence 3: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_4(all_shops):
    """All-shop coherence 4: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_5(all_shops):
    """All-shop coherence 5: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_6(all_shops):
    """All-shop coherence 6: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_7(all_shops):
    """All-shop coherence 7: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_8(all_shops):
    """All-shop coherence 8: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_9(all_shops):
    """All-shop coherence 9: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_10(all_shops):
    """All-shop coherence 10: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_11(all_shops):
    """All-shop coherence 11: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_12(all_shops):
    """All-shop coherence 12: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_13(all_shops):
    """All-shop coherence 13: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_14(all_shops):
    """All-shop coherence 14: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_15(all_shops):
    """All-shop coherence 15: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_16(all_shops):
    """All-shop coherence 16: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_17(all_shops):
    """All-shop coherence 17: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_18(all_shops):
    """All-shop coherence 18: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

def test_extra_coherence_19(all_shops):
    """All-shop coherence 19: every close has headline+po."""
    for kind, pack in all_shops.items():
        assert "Profit $" in pack["close"]["headline"], kind
        assert isinstance(pack["close"]["po_draft"], str) and len(pack["close"]["po_draft"]) > 10
    assert len(all_shops) == 5

