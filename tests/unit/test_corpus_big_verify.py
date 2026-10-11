"""Corpus-big verification: all 80 shops ingest cleanly, manifest GMV matches parsed GMV."""
import csv
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[2] / "evals" / "corpus_big"


def _manifest():
    rows = list(csv.DictReader(open(CORPUS / "manifest.csv")))
    assert len(rows) == 80, f"manifest rows={len(rows)}"
    return rows


def test_manifest_has_80_shops():
    rows = _manifest()
    archs = {r["archetype"] for r in rows}
    assert len(archs) >= 8, archs


def test_all_shops_ingest():
    from omni_one.packs.seller_os import ingest_seller_folder
    rows = _manifest()
    assert (CORPUS / "shop_01").exists() and (CORPUS / "shop_80").exists()
    total_events = 0
    for r in rows:
        events, report = ingest_seller_folder(CORPUS / r["shop"])
        assert len(events) > 0, r["shop"]
        assert report["files_ingested"] >= 3, (r["shop"], report)
        total_events += len(events)
    assert total_events > 800, total_events


def test_manifest_gmv_matches_parsed():
    from omni_one.packs.seller_os import ingest_seller_folder
    rows = _manifest()
    checked = 0
    for r in rows[:20] + rows[-5:]:
        events, _ = ingest_seller_folder(CORPUS / r["shop"])
        gmv = round(sum(float(e.get("metadata", {}).get("gmv", 0) or 0)
                        for e in events if e.get("source") == "orders"), 2)
        assert abs(gmv - float(r["gmv"])) < 0.05, (r["shop"], gmv, r["gmv"])
        checked += 1
    assert checked == 25


def test_archetype_expectations():
    from omni_one.packs.seller_os import ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    # stockout archetype must produce ORDER TODAY; empty-ish must not crash
    stock = next(s for s in _manifest() if s["archetype"] == "stockout")
    events, _ = ingest_seller_folder(CORPUS / stock["shop"])
    close = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    assert any(x["urgency"] == "ORDER TODAY" for x in close["reorder_sheet"]), stock
    empty = next(s for s in _manifest() if "empty" in s["archetype"])
    events, _ = ingest_seller_folder(CORPUS / empty["shop"])
    close = build_daily_close(events, build_seller_briefing(events), run_all_scenarios(events))
    assert close["kpis"]["orders"] >= 0
    assert "Profit" in close["headline"]
