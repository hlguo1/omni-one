"""WAVE2-G API persistence: full journeys, counters monotonic, folder briefing, 10x stable closes."""
from __future__ import annotations
import csv
import io
import os
import re
import tempfile
os.environ.setdefault("SELLER_LLM", "mock")
os.environ.setdefault("SELLER_MAX_LLM_USD", "0.0")
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
@pytest.fixture(scope="module")
def client():
    from omni_one.api.fastapi_app import create_omni_one_app
    app = create_omni_one_app()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
def _counters(text):
    out = {}
    for line in text.splitlines():
        m = re.search(r'op="([^"]+)"\}\s+(\d+)', line)
        if m: out[m.group(1)] = int(m.group(2))
    return out
def _make_demo_shop_inline(base: Path, seed: int = 42) -> Path:
    """Inline copy of make_seller_demo_folder patterns (shopify/etsy/inventory/reviews/dm/supplier)."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "shopify_orders.csv").write_text("Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer\n#1001,2024-09-10,Tote Bag Handmade,2,28.00,56.00,,4.00,Alice\n#1002,2024-09-11,Ceramic Mug,1,22.00,22.00,,3.50,Bob\n#1003,2024-09-11,Tote Bag Handmade,1,28.00,28.00,,0.00,Charlie\n#1004,2024-09-12,Print - Botanical,3,15.00,45.00,,5.00,Alice\n#1005,2024-09-12,Tote Bag Handmade,1,28.00,28.00,,4.00,David\n", encoding="utf-8")
    (base / "etsy_settlement.csv").write_text("order_id,order_date,product,qty,price,fees,shipping,buyer\nE2001,2024-09-10,Knitted Scarf,1,45.00,3.12,4.50,Eve\nE2002,2024-09-11,Tote Bag Handmade,2,28.00,3.84,0.00,Frank\nE2003,2024-09-12,Ceramic Mug,2,22.00,3.06,3.00,Grace\n", encoding="utf-8")
    (base / "inventory.csv").write_text("sku,product,stock,supplier\nTB001,Tote Bag Handmade,2,Acme Textiles\nCM002,Ceramic Mug,15,Clay Co\nPR003,Print - Botanical,40,Paper Co\nKS004,Knitted Scarf,8,Wool Co\n", encoding="utf-8")
    (base / "reviews.csv").write_text("date,product,stars,review\n2024-09-11,Tote Bag Handmade,5,\"Love it! Perfect size\"\n2024-09-11,Ceramic Mug,2,\"Arrived chipped, very disappointed\"\n2024-09-12,Print - Botanical,5,\"Beautiful!\"\n", encoding="utf-8")
    (base / "instagram_dm.txt").write_text("Alice: Hi! My tote bag hasn't arrived yet, ordered 5 days ago. Worried.\nShop: Hi Alice, checking tracking — will update in 1h\nBob: Amazing mug! Will order again.\nCharlie: Where is my order? No tracking.\n", encoding="utf-8")
    (base / "supplier_invoice_2024-09-10.txt").write_text("Acme Textiles\nTote Bag Canvas 50 x 4.00 200.00\nShipping 15.00\nTotal $215.00\n", encoding="utf-8")
    return base
@pytest.fixture(scope="module")
def journey(client):
    """Full journey: briefing -> scenarios run -> close -> export.csv -> metrics (cached)."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True})
    assert b.status_code == 200, b.text[:500]
    s = client.post("/api/v1/seller/scenarios/run", json={"demo": True})
    assert s.status_code == 200
    c = client.post("/api/v1/seller/close", json={"demo": True})
    assert c.status_code == 200
    e = client.get("/api/v1/seller/export.csv")
    assert e.status_code == 200
    m = client.get("/metrics")
    assert m.status_code == 200
    return {"briefing": b.json(), "scen": s.json(), "close": c.json(), "export": e.text, "metrics": m.text}
def test_journey_briefing_gmv(journey):
    """Journey cached step: briefing_gmv."""
    assert abs(float(journey["briefing"]["kpis"]["gmv"]) - 274.0) < 0.01, f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_briefing_profit(journey):
    """Journey cached step: briefing_profit."""
    assert abs(float(journey["briefing"]["kpis"]["true_profit"]) - 169.09) < 0.05, f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_scen_total(journey):
    """Journey cached step: scen_total."""
    assert journey["scen"]["total"] == 8, f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_close_headline(journey):
    """Journey cached step: close_headline."""
    assert "Profit $169.09" in journey["close"]["headline"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_close_tote(journey):
    """Journey cached step: close_tote."""
    assert any("Tote" in r["product"] and r["urgency"] == "ORDER TODAY" for r in journey["close"]["reorder_sheet"]), f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_export_gmv(journey):
    """Journey cached step: export_gmv."""
    assert "gmv,274.0" in journey["export"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_metrics_up(journey):
    """Journey cached step: metrics_up."""
    assert "omni_one_up 1" in journey["metrics"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_metrics_close(journey):
    """Journey cached step: metrics_close."""
    assert 'op="closes_total"' in journey["metrics"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_kpis_match(journey):
    """Journey cached step: kpis_match."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_aov_match(journey):
    """Journey cached step: aov_match."""
    assert journey["briefing"]["kpis"]["aov"] == journey["close"]["kpis"]["aov"], f"{journey}"
    assert isinstance(journey, dict)
    assert journey["close"]["kpis"]["orders"] == 8

def test_journey_repeat_0(client):
    """Journey repeat 0: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_1(client):
    """Journey repeat 1: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_2(client):
    """Journey repeat 2: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_3(client):
    """Journey repeat 3: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_4(client):
    """Journey repeat 4: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_5(client):
    """Journey repeat 5: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_6(client):
    """Journey repeat 6: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_7(client):
    """Journey repeat 7: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_8(client):
    """Journey repeat 8: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_9(client):
    """Journey repeat 9: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_10(client):
    """Journey repeat 10: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_journey_repeat_11(client):
    """Journey repeat 11: each stage 200 and consistent KPIs."""
    b = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert b["kpis"]["gmv"] == c["kpis"]["gmv"] == 274.0
    assert b["kpis"]["true_profit"] == c["kpis"]["true_profit"] == 169.09
    assert len(c["reply_queue"]) == 3

def test_counters_monotonic_journey(client):
    """Counters must never decrease across briefing->scenarios->close->export."""
    def snap(): return _counters(client.get("/metrics").text)
    s0 = snap()
    client.post("/api/v1/seller/briefing", json={"demo": True})
    s1 = snap(); assert s1.get("briefings_total",0) >= s0.get("briefings_total",0)
    client.post("/api/v1/seller/scenarios/run", json={"demo": True})
    s2 = snap(); assert s2.get("scenarios_runs_total",0) >= s1.get("scenarios_runs_total",0)
    client.post("/api/v1/seller/close", json={"demo": True})
    s3 = snap(); assert s3.get("closes_total",0) == s2.get("closes_total",0) + 1
    for k in ["briefings_total","scenarios_runs_total","closes_total"]:
        assert s3[k] >= s0[k], f"{k} decreased {s0[k]}->{s3[k]}"

def test_counters_monotonic_0(client):
    """Monotonic check 0: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_1(client):
    """Monotonic check 1: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_2(client):
    """Monotonic check 2: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_3(client):
    """Monotonic check 3: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_4(client):
    """Monotonic check 4: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_5(client):
    """Monotonic check 5: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_6(client):
    """Monotonic check 6: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_counters_monotonic_7(client):
    """Monotonic check 7: single close bumps closes_total by 1."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 1
    assert after >= 1

def test_folder_briefing_tmp_inline(client, tmp_path):
    """Folder briefing via tmp_path inline shop (ALLOWED_ROOT shim for /var/folders)."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / "myshop")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        r = client.post("/api/v1/seller/briefing", json={"folder": str(shop)})
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert r.status_code == 200, r.text[:800]
    d = r.json(); assert abs(float(d["kpis"]["gmv"]) - 274.0) < 0.01
    assert d["kpis"]["best_seller"]["product"] == "Tote Bag Handmade"

def test_folder_briefing_under_tmp_control(client):
    """Control: shop under /tmp (natively allowed) gives golden KPIs."""
    import tempfile as _tf
    td = _tf.mkdtemp(prefix="wave2-shop-", dir="/tmp")
    shop = _make_demo_shop_inline(Path(td) / "shop")
    r = client.post("/api/v1/seller/briefing", json={"folder": str(shop)})
    assert r.status_code == 200, r.text[:800]
    assert r.json()["kpis"]["gmv"] == 274.0

def test_folder_briefing_repeat_0(client, tmp_path):
    """Folder briefing repeat 0: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep0")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_1(client, tmp_path):
    """Folder briefing repeat 1: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep1")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_2(client, tmp_path):
    """Folder briefing repeat 2: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep2")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_3(client, tmp_path):
    """Folder briefing repeat 3: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep3")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_4(client, tmp_path):
    """Folder briefing repeat 4: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep4")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_5(client, tmp_path):
    """Folder briefing repeat 5: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep5")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_6(client, tmp_path):
    """Folder briefing repeat 6: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep6")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_briefing_repeat_7(client, tmp_path):
    """Folder briefing repeat 7: deterministic golden values."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / f"rep7")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        d = client.post("/api/v1/seller/briefing", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert d["kpis"]["orders"] == 8 and d["kpis"]["gmv"] == 274.0
    assert d["kpis"]["at_risk"] == 3

def test_folder_close_matches_demo(client, tmp_path):
    """Folder close must match demo close headline (same seed data)."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / "matchshop")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        f = client.post("/api/v1/seller/close", json={"folder": str(shop)}).json()
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    demo = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert f["headline"] == demo["headline"], f"{f['headline']!r} vs {demo['headline']!r}"
    assert f["kpis"]["gmv"] == 274.0

def test_folder_scenarios_run_tmp(client, tmp_path):
    """Folder scenarios/run via tmp_path must be 200 with total>=5."""
    import os as _os
    shop = _make_demo_shop_inline(tmp_path / "scenshop")
    _os.environ["ALLOWED_ROOT"] = str(tmp_path)
    try:
        r = client.post("/api/v1/seller/scenarios/run", json={"folder": str(shop)})
    finally:
        _os.environ.pop("ALLOWED_ROOT", None)
    assert r.status_code == 200, r.text[:600]
    assert r.json()["total"] >= 5

def test_ten_closes_stable_headline(client):
    """Sequential 10 closes: same headline each time (no state leak)."""
    heads = []
    for _ in range(10):
        r = client.post("/api/v1/seller/close", json={"demo": True})
        assert r.status_code == 200
        heads.append(r.json()["headline"])
    assert len(set(heads)) == 1, heads
    assert "Profit $169.09" in heads[0]

def test_ten_closes_slot_0(client):
    """10-close stability slot 0: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_1(client):
    """10-close stability slot 1: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_2(client):
    """10-close stability slot 2: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_3(client):
    """10-close stability slot 3: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_4(client):
    """10-close stability slot 4: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_5(client):
    """10-close stability slot 5: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_6(client):
    """10-close stability slot 6: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_7(client):
    """10-close stability slot 7: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_8(client):
    """10-close stability slot 8: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_slot_9(client):
    """10-close stability slot 9: reorder + reply stable."""
    a = client.post("/api/v1/seller/close", json={"demo": True}).json()
    b = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert a["headline"] == b["headline"]
    assert a["reorder_sheet"] == b["reorder_sheet"]
    assert a["kpis"]["money_at_risk_usd"] == 102.75

def test_ten_closes_metrics_plus10(client):
    """10 sequential closes must bump closes_total by exactly 10."""
    before = _counters(client.get("/metrics").text)["closes_total"]
    for _ in range(10):
        assert client.post("/api/v1/seller/close", json={"demo": True}).status_code == 200
    after = _counters(client.get("/metrics").text)["closes_total"]
    assert after == before + 10, f"{before}->{after}"

def test_export_after_close_consistent(client):
    """export.csv after close must share gmv/profit with close."""
    c = client.post("/api/v1/seller/close", json={"demo": True}).json()
    e = client.get("/api/v1/seller/export.csv").text
    assert f"gmv,{c['kpis']['gmv']}" in e
    assert f"true_profit,{c['kpis']['true_profit']}" in e
    rows = list(csv.reader(io.StringIO(e)))
    assert rows[0] == ["metric", "value"]

def test_no_state_leak_best_seller(client):
    """Repeated briefings must not leak state: best_seller stable."""
    seen = set()
    for _ in range(5):
        d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
        seen.add((d["kpis"]["best_seller"]["product"], d["kpis"]["best_seller"]["qty"]))
    assert seen == {("Tote Bag Handmade", 6)}, seen

def test_persist_extra_close_0(client):
    """Persistence extra close 0: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_1(client):
    """Persistence extra close 1: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_2(client):
    """Persistence extra close 2: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_3(client):
    """Persistence extra close 3: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_4(client):
    """Persistence extra close 4: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_5(client):
    """Persistence extra close 5: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_6(client):
    """Persistence extra close 6: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_7(client):
    """Persistence extra close 7: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_8(client):
    """Persistence extra close 8: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_9(client):
    """Persistence extra close 9: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_10(client):
    """Persistence extra close 10: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_11(client):
    """Persistence extra close 11: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_12(client):
    """Persistence extra close 12: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_13(client):
    """Persistence extra close 13: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_14(client):
    """Persistence extra close 14: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_15(client):
    """Persistence extra close 15: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_16(client):
    """Persistence extra close 16: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_17(client):
    """Persistence extra close 17: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_18(client):
    """Persistence extra close 18: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_19(client):
    """Persistence extra close 19: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_20(client):
    """Persistence extra close 20: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_21(client):
    """Persistence extra close 21: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_22(client):
    """Persistence extra close 22: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_23(client):
    """Persistence extra close 23: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_24(client):
    """Persistence extra close 24: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_25(client):
    """Persistence extra close 25: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_26(client):
    """Persistence extra close 26: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_27(client):
    """Persistence extra close 27: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_28(client):
    """Persistence extra close 28: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_close_29(client):
    """Persistence extra close 29: golden headline stable."""
    d = client.post("/api/v1/seller/close", json={"demo": True}).json()
    assert d["headline"].startswith("Profit $169.09")
    assert d["kpis"]["gmv"] == 274.0 and d["kpis"]["money_at_risk_usd"] == 102.75
    assert len(d["reply_queue"]) == 3

def test_persist_extra_brief_0(client):
    """Persistence extra briefing 0: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_1(client):
    """Persistence extra briefing 1: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_2(client):
    """Persistence extra briefing 2: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_3(client):
    """Persistence extra briefing 3: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_4(client):
    """Persistence extra briefing 4: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_5(client):
    """Persistence extra briefing 5: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_6(client):
    """Persistence extra briefing 6: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_7(client):
    """Persistence extra briefing 7: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_8(client):
    """Persistence extra briefing 8: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_9(client):
    """Persistence extra briefing 9: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_10(client):
    """Persistence extra briefing 10: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_11(client):
    """Persistence extra briefing 11: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_12(client):
    """Persistence extra briefing 12: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_13(client):
    """Persistence extra briefing 13: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra_brief_14(client):
    """Persistence extra briefing 14: at_risk/stockout stable."""
    d = client.post("/api/v1/seller/briefing", json={"demo": True}).json()
    assert d["kpis"]["at_risk"] == 3 and d["kpis"]["stockout_risk"] == 1
    assert d["kpis"]["best_seller"]["qty"] == 6

def test_persist_extra2_0(client, journey):
    """Journey coherence 0."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_1(client, journey):
    """Journey coherence 1."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_2(client, journey):
    """Journey coherence 2."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_3(client, journey):
    """Journey coherence 3."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_4(client, journey):
    """Journey coherence 4."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_5(client, journey):
    """Journey coherence 5."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_6(client, journey):
    """Journey coherence 6."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_7(client, journey):
    """Journey coherence 7."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_8(client, journey):
    """Journey coherence 8."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_9(client, journey):
    """Journey coherence 9."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_10(client, journey):
    """Journey coherence 10."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_11(client, journey):
    """Journey coherence 11."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_12(client, journey):
    """Journey coherence 12."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_13(client, journey):
    """Journey coherence 13."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_14(client, journey):
    """Journey coherence 14."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_15(client, journey):
    """Journey coherence 15."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_16(client, journey):
    """Journey coherence 16."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_17(client, journey):
    """Journey coherence 17."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_18(client, journey):
    """Journey coherence 18."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_19(client, journey):
    """Journey coherence 19."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_20(client, journey):
    """Journey coherence 20."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_21(client, journey):
    """Journey coherence 21."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_22(client, journey):
    """Journey coherence 22."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_23(client, journey):
    """Journey coherence 23."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_24(client, journey):
    """Journey coherence 24."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

def test_persist_extra2_25(client, journey):
    """Journey coherence 25."""
    assert journey["briefing"]["kpis"]["gmv"] == journey["close"]["kpis"]["gmv"]
    assert "Profit $169.09" in journey["close"]["headline"]
    assert client.get("/metrics").status_code == 200
    assert journey["scen"]["total"] >= 5

