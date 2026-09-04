"""Offline seller E2E: demo folder -> briefing KPIs, $0 mock, file:line cites. No network, no keys."""
import os
os.environ["SELLER_LLM"] = "mock"
os.environ["SELLER_MAX_LLM_USD"] = "0.0"
from pathlib import Path
import tempfile


def test_seller_e2e_offline():
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    with tempfile.TemporaryDirectory() as tmp:
        demo = make_seller_demo_folder(Path(tmp) / "d", seed=42)
        events, report = ingest_seller_folder(demo)
        assert len(events) > 10, f"expected events, got {len(events)}"
        b = build_seller_briefing(events)
        k = b["kpis"]
        # Golden demo numbers (must not drift)
        assert k["gmv"] == 274.00, k
        assert k["fees"] == 16.71, k
        assert k["true_profit"] == 169.09, k
        assert k["margin_pct"] == 61.7, k
        assert k["best_seller"]["product"] == "Tote Bag Handmade" and k["best_seller"]["qty"] == 6
        assert k["stockout_risk"] == 1
        assert k["at_risk"] == 3
        # Evidence + $0
        assert any("inventory.csv" in a.get("evidence", [""])[0] for a in b["alerts"] if a["type"] == "stockout_risk")
        assert b["llm"]["mode"] == "mock" and b["llm"]["cost_usd"] == 0.0
        assert "[MOCK SELLER DRAFT]" in (b["draft_reply"]["text"] or "")
