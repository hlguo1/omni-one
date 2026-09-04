"""Scenarios idempotent: same events -> same stable IDs, sorted critical->low."""
import tempfile
from pathlib import Path


def test_idempotent_scenarios():
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
    from omni_one.packs.seller_scenarios import run_all_scenarios
    with tempfile.TemporaryDirectory() as tmp:
        demo = make_seller_demo_folder(Path(tmp) / "d", seed=42)
        events, _ = ingest_seller_folder(demo)
        a = run_all_scenarios(events)
        b = run_all_scenarios(events)
        assert a["total"] == b["total"] and a["total"] >= 5
        assert [d["id"] for d in a["decisions"]] == [d["id"] for d in b["decisions"]]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ranks = [order[d["severity"]] for d in a["decisions"]]
        assert ranks == sorted(ranks), "decisions must be severity-sorted"
        assert a["by_scenario"].get("STOCKOUT_RISK", 0) >= 1
