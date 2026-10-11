"""Close x i18n smoke: every reply in the demo queue can be re-rendered in each locale."""
import tempfile
from pathlib import Path


def _close():
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    tmp = Path(tempfile.mkdtemp())
    d = make_seller_demo_folder(tmp / "d", seed=42)
    events, _ = ingest_seller_folder(d)
    return build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))


def test_queue_rerender_all_locales():
    from omni_one.i18n import list_locales
    from omni_one.i18n.drafts import build_reply
    c = _close()
    assert len(c["reply_queue"]) >= 2
    locales = list_locales()
    assert set(locales) >= {"en", "es", "zh", "fr", "de"}
    for q in c["reply_queue"][:3]:
        for loc in locales:
            d = build_reply("dm", loc, q["customer"], q["summary"], q["citation"], "Test Shop")
            assert q["citation"] in d, (loc, q)
            assert len(d) > 30


def test_po_all_locales():
    from omni_one.i18n import list_locales
    from omni_one.i18n.drafts import build_po
    c = _close()
    lines = [{"product": r["product"], "reorder_qty": r["reorder_qty"],
              "on_hand": r["on_hand"], "days_left": r["days_left"],
              "citation": r["citation"]} for r in c["reorder_sheet"][:2]]
    for loc in list_locales():
        po = build_po(loc, "Acme", lines, "Test Shop")
        assert "Acme" in po and len(po) > 50, loc


def test_detect_on_queue_text():
    from omni_one.i18n import detect_locale
    c = _close()
    for q in c["reply_queue"][:3]:
        assert detect_locale(q["summary"]) in {"en", "es", "zh", "fr", "de"}


def test_channel_normalizers_on_demo_sources():
    from omni_one.i18n.channels import normalize_dm
    assert normalize_dm({"from": "Alice", "text": "hi", "channel": "instagram"}, "instagram")["sender"] == "Alice"
    assert normalize_dm("Bob: amazing mug", "instagram")["text"]
    assert normalize_dm({"text": "hi", "sender": "Shop"}, "tiktok")["sender"] == "Shop"


def test_close_locale_es_changes_drafts_not_numbers():
    import tempfile
    from pathlib import Path
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    tmp = Path(tempfile.mkdtemp())
    d = make_seller_demo_folder(tmp / "d", seed=42)
    events, _ = ingest_seller_folder(d)
    en = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    es = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events), locale="es", shop="Solmar")
    assert es["locale"] == "es"
    assert es["kpis"] == en["kpis"]  # numbers never change with locale
    assert es["headline"] == en["headline"]
    assert es["reply_queue"][0]["draft"] != en["reply_queue"][0]["draft"]
    assert "2 horas" in es["reply_queue"][0]["draft"]
    assert es["reply_queue"][0]["citation"] == en["reply_queue"][0]["citation"]
    zh = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events), locale="zh")
    assert zh["locale"] == "zh"
    assert zh["kpis"] == en["kpis"]
    bad = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events), locale="xx")
    assert bad["locale"] == "en"  # unknown falls back, never crashes


def test_locale_wiring_cli_sdk_api():
    from typer.testing import CliRunner
    from omni_one.cli import app
    import tempfile
    r = CliRunner().invoke(app, ["close", "--demo", "--locale", "es", "--out", tempfile.mkdtemp()])
    assert r.exit_code == 0, r.output
    assert "2 horas" in r.output or "DAILY CLOSE" in r.output
    from omni_one.client import OmniOneClient
    c = OmniOneClient.local().close(demo=True, locale="fr")
    assert c["locale"] == "fr" and c["kpis"]["true_profit"] == 169.09 or abs(c["kpis"]["true_profit"] - 169.09) < 0.05
    from fastapi.testclient import TestClient
    from omni_one.api.fastapi_app import create_omni_one_app
    tc = TestClient(create_omni_one_app())
    resp = tc.post("/api/v1/seller/close", json={"demo": True, "locale": "zh"})
    assert resp.status_code == 200 and resp.json()["locale"] == "zh"
    assert resp.json()["kpis"]["true_profit"] == tc.post("/api/v1/seller/close", json={"demo": True}).json()["kpis"]["true_profit"]
