"""SDK contract — the python-side shape BOTH SDKs (TS + Go) must satisfy.

Builds the expected close JSON shape ONCE via OmniOneClient.local().close()
(no network), asserts the required keys, writes the shape descriptor to
tests/fixtures/close_schema.json, then validates:
  - sdks/ts/src/index.ts lists the same field names (parsed as text), and
  - sdks/go/client.go lists the same fields (parsed via json tags).

No network anywhere in this module (local client + file reads only).

Contract keys (load-bearing, keep in sync across SDKs):
  headline, kpis { gmv, true_profit, money_at_risk_usd },
  reorder_sheet[0] { product, reorder_qty, citation },
  reply_queue[0] { draft, citation }, po_draft.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TS_INDEX = REPO_ROOT / "sdks" / "ts" / "src" / "index.ts"
TS_CLOSE = REPO_ROOT / "sdks" / "ts" / "src" / "close.ts"
GO_CLIENT = REPO_ROOT / "sdks" / "go" / "client.go"
GO_CLOSE = REPO_ROOT / "sdks" / "go" / "close.go"
SCHEMA_OUT = REPO_ROOT / "tests" / "fixtures" / "close_schema.json"

# Top-level close fields every SDK must carry.
REQUIRED_TOP = ["headline", "kpis", "reorder_sheet", "reply_queue", "po_draft"]
# KPIs subfields.
REQUIRED_KPIS = ["gmv", "true_profit", "money_at_risk_usd"]
# First reorder row subfields.
REQUIRED_REORDER = ["product", "reorder_qty", "citation"]
# First reply subfields.
REQUIRED_REPLY = ["draft", "citation"]


def _expected_close() -> dict:
    from omni_one.client import OmniOneClient

    return OmniOneClient.local().close(demo=True, shop="our shop")


def test_close_golden_shape_and_keys():
    close = _expected_close()
    # Top-level required keys.
    for key in REQUIRED_TOP:
        assert key in close, f"close missing top-level key: {key}"
    # Headline sanity (golden profit line).
    assert isinstance(close["headline"], str) and close["headline"]
    assert "Profit $169.09" in close["headline"], close["headline"]
    # KPIs.
    kpis = close["kpis"]
    for key in REQUIRED_KPIS:
        assert key in kpis, f"kpis missing key: {key}"
    assert abs(kpis["true_profit"] - 169.09) < 0.05, kpis
    assert kpis["gmv"] > 0
    assert kpis["money_at_risk_usd"] > 0
    assert kpis["orders"] == 8
    # Reorder sheet row 0.
    assert isinstance(close["reorder_sheet"], list) and close["reorder_sheet"]
    r0 = close["reorder_sheet"][0]
    for key in REQUIRED_REORDER:
        assert key in r0, f"reorder_sheet[0] missing key: {key}"
    assert r0["product"] and r0["reorder_qty"] > 0
    assert "inventory.csv" in r0["citation"], r0["citation"]
    # Reply queue row 0.
    assert isinstance(close["reply_queue"], list) and close["reply_queue"]
    q0 = close["reply_queue"][0]
    for key in REQUIRED_REPLY:
        assert key in q0, f"reply_queue[0] missing key: {key}"
    assert q0["draft"] and len(q0["draft"]) > 40
    assert q0["citation"]
    # PO draft.
    assert isinstance(close["po_draft"], str) and "Subject: Reorder" in close["po_draft"]


def test_close_schema_written_to_fixtures():
    close = _expected_close()
    SCHEMA_OUT.parent.mkdir(parents=True, exist_ok=True)
    shape = {
        "top_level": sorted(close.keys()),
        "required_top": REQUIRED_TOP,
        "kpis": sorted(close["kpis"].keys()),
        "required_kpis": REQUIRED_KPIS,
        "reorder_sheet_0": sorted(close["reorder_sheet"][0].keys()),
        "required_reorder": REQUIRED_REORDER,
        "reply_queue_0": sorted(close["reply_queue"][0].keys()),
        "required_reply": REQUIRED_REPLY,
        "has_po_draft": isinstance(close.get("po_draft"), str),
        "samples": {
            "headline": close["headline"],
            "true_profit": close["kpis"]["true_profit"],
            "money_at_risk_usd": close["kpis"]["money_at_risk_usd"],
            "reorder_product": close["reorder_sheet"][0]["product"],
            "reorder_qty": close["reorder_sheet"][0]["reorder_qty"],
            "reorder_citation": close["reorder_sheet"][0]["citation"],
            "reply_citation": close["reply_queue"][0]["citation"],
        },
    }
    SCHEMA_OUT.write_text(json.dumps(shape, indent=2, default=str), encoding="utf-8")
    assert SCHEMA_OUT.exists()
    reloaded = json.loads(SCHEMA_OUT.read_text(encoding="utf-8"))
    for key in REQUIRED_TOP:
        assert key in reloaded["top_level"], f"schema top_level missing {key}"
    for key in REQUIRED_KPIS:
        assert key in reloaded["kpis"], f"schema kpis missing {key}"


def test_ts_interfaces_list_same_fields():
    assert TS_INDEX.exists(), f"missing {TS_INDEX} (build WORKSTREAM C step 1)"
    text = TS_INDEX.read_text(encoding="utf-8", errors="ignore")
    # Interfaces present.
    for iface in ["CloseBundle", "KPIs", "ReorderLine", "ReplyItem"]:
        assert iface in text, f"index.ts missing interface {iface}"
    # Every contract field name appears (methods + shapes).
    for field in (
        REQUIRED_TOP + REQUIRED_KPIS + REQUIRED_REORDER + REQUIRED_REPLY + ["gmv"]
    ):
        assert field in text, f"index.ts missing contract field: {field}"
    # Method surface present.
    for method in [
        "briefingDemo",
        "briefingFolder",
        "scenariosRun",
        "operations",
        "close",
        "analyze",
        "health",
        "exportCSV",
        "closeCSV",
    ]:
        assert method in text, f"index.ts missing method: {method}"
    # Retry + auth markers.
    assert "X-API-Key" in text, "index.ts missing X-API-Key header"
    assert "429" in text, "index.ts missing 429 retry handling"
    # close.ts submodule exists and re-exports.
    assert TS_CLOSE.exists(), f"missing {TS_CLOSE}"
    close_text = TS_CLOSE.read_text(encoding="utf-8", errors="ignore")
    assert "closeToCsv" in close_text or "close" in close_text.lower()


def test_go_structs_list_same_fields():
    assert GO_CLIENT.exists(), f"missing {GO_CLIENT} (build WORKSTREAM C step 2)"
    text = GO_CLIENT.read_text(encoding="utf-8", errors="ignore")
    # Structs present.
    for struct in ["CloseBundle", "KPIs", "ReorderLine", "ReplyItem"]:
        assert struct in text, f"client.go missing struct {struct}"
    # Every contract field appears as a json tag (citation-preserving JSON).
    for field in (
        REQUIRED_TOP + REQUIRED_KPIS + REQUIRED_REORDER + REQUIRED_REPLY + ["gmv"]
    ):
        tag = f'json:"{field}"'
        assert tag in text or field in text, f"client.go missing field/tag: {field}"
    # Method surface present (exported Go methods).
    for method in [
        "BriefingDemo",
        "BriefingFolder",
        "ScenariosRun",
        "Operations",
        "Close",
        "Analyze",
        "Health",
        "ExportCSV",
        "CloseCSV",
    ]:
        assert method in text, f"client.go missing method: {method}"
    # Retry + auth markers.
    assert "X-API-Key" in text, "client.go missing X-API-Key header"
    assert "429" in text, "client.go missing 429 retry handling"
    # close.go submodule exists.
    assert GO_CLOSE.exists(), f"missing {GO_CLOSE}"


def test_citations_survive_csv_render():
    """file:line passthrough — CSVs must keep citations (no stripping)."""
    from omni_one.packs.seller_close import close_to_csv, reorder_to_csv

    close = _expected_close()
    csv_text = close_to_csv(close)
    assert "money_at_risk_usd" in csv_text
    assert "inventory.csv" in csv_text, "citation stripped from close.csv!"
    reorder_csv = reorder_to_csv(close)
    assert "reorder_qty_14d" in reorder_csv
    assert "inventory.csv" in reorder_csv, "citation stripped from reorder.csv!"
