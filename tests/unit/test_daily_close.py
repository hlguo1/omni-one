"""Daily Close golden tests — the ritual shops run every morning must never regress."""
import tempfile
from pathlib import Path


def _demo_events(seed=42):
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
    tmp = Path(tempfile.mkdtemp())
    d = make_seller_demo_folder(tmp / "d", seed=seed)
    events, _ = ingest_seller_folder(d)
    return events


def test_close_golden_kpis_and_headline():
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    events = _demo_events()
    b = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    c = build_daily_close(events, b, scen)
    assert abs(c["kpis"]["true_profit"] - 169.09) < 0.05, c["kpis"]
    assert c["kpis"]["money_at_risk_usd"] > 0
    assert "Profit $169.09" in c["headline"]
    # reorder: Tote must be ORDER TODAY with qty > 0 and citation
    tote = next(r for r in c["reorder_sheet"] if "Tote" in r["product"])
    assert tote["urgency"] == "ORDER TODAY"
    assert tote["reorder_qty"] > 0
    assert "inventory.csv" in tote["citation"]
    assert tote["supplier"]  # supplier captured from inventory.csv


def test_close_reply_queue_has_copy_paste_drafts():
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    events = _demo_events()
    c = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    assert len(c["reply_queue"]) >= 2
    q0 = c["reply_queue"][0]
    assert q0["draft"] and len(q0["draft"]) > 40
    assert "2 hour" in q0["draft"]
    assert "instagram_dm.txt" in q0["citation"] or "reviews.csv" in q0["citation"]
    assert "Subject: Reorder" in c["po_draft"]
    assert "Tote" in c["po_draft"]


def test_close_exports_and_idempotent():
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close, close_to_csv, reorder_to_csv, replies_to_txt
    events = _demo_events()
    c1 = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    c2 = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    assert c1["headline"] == c2["headline"]
    assert c1["reorder_sheet"] == c2["reorder_sheet"]
    csv_text = close_to_csv(c1)
    assert "money_at_risk_usd" in csv_text and "reorder_qty_14d" in reorder_to_csv(c1)
    txt = replies_to_txt(c1)
    assert "COPY-PASTE DRAFT" in txt and "PO DRAFT" in txt


def test_cli_close_and_sdk_close_and_api_close():
    from typer.testing import CliRunner
    from omni_one.cli import app
    r = CliRunner().invoke(app, ["close", "--demo", "--out", tempfile.mkdtemp()])
    assert r.exit_code == 0, r.output
    assert "DAILY CLOSE" in r.output
    from omni_one.client import OmniOneClient
    c = OmniOneClient.local().close(demo=True)
    assert c["kpis"]["orders"] == 8
    # API (in-process, no server)
    import asyncio
    from omni_one.api.fastapi_app import create_omni_one_app
    from fastapi.testclient import TestClient
    tc = TestClient(create_omni_one_app())
    resp = tc.post("/api/v1/seller/close", json={"demo": True})
    assert resp.status_code == 200, resp.text
    assert "headline" in resp.json()
    assert tc.get("/metrics").status_code == 200
    assert "closes_total" in tc.get("/metrics").text
