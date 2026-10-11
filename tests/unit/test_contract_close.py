"""Contract tests for the daily-close JSON (WORKSTREAM F).

The close bundle (``close.json``) is consumed by the CLI, the API, the
accountant CSV export, and downstream evals. This module pins its schema so
any pack change that drops/renames a key fails loudly here instead of
silently breaking accountants at month-end.

Contract asserted:

* Required top-level keys: date, shop, headline, kpis, do_today,
  reorder_sheet, reply_queue, money_leaks, listing_fixes, po_draft.
* ``kpis`` types: gmv/fees/shipping/net/cogs/true_profit/margin_pct/orders/
  aov numeric; best_seller object; money_at_risk_usd numeric.
* ``reorder_sheet[]`` row types: product str, on_hand/sold_7d int-like,
  days_left/daily_velocity numeric, reorder_qty int >= 0, supplier str,
  urgency str, citation matching ``[file:line]``.
* ``reply_queue[]`` row types: channel/customer/summary/draft/citation/
  priority str; citation matches ``[file:line]``; the FIRST reply's draft
  is non-empty and references its citation.
* ``po_draft`` is a non-empty string (or the healthy-stock sentence).
* ``money_leaks[]`` rows carry leak/note/evidence keys.

Schema persistence: the canonical schema is written to
``tests/fixtures/close_schema.json`` if missing, then the live close is
validated against the loaded schema (so the file is both documentation and
enforcement). Validation is dependency-free (stdlib only).
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")

TOP_LEVEL_REQUIRED = [
    "date", "shop", "headline", "kpis", "do_today",
    "reorder_sheet", "reply_queue", "money_leaks",
    "listing_fixes", "po_draft",
]

KPIS_NUMERIC = ["gmv", "fees", "shipping", "net", "cogs", "true_profit",
                "margin_pct", "orders", "aov", "money_at_risk_usd"]

REORDER_REQUIRED = ["product", "on_hand", "sold_7d", "daily_velocity",
                    "days_left", "reorder_qty", "supplier", "urgency", "citation"]

REPLY_REQUIRED = ["channel", "customer", "summary", "draft", "citation", "priority"]

SCHEMA_PATH = (Path(__file__).resolve().parents[1] / "fixtures" / "close_schema.json")


def canonical_schema() -> dict[str, Any]:
    """The pinned close.json schema (also persisted to fixtures)."""
    return {
        "$schema": "close/v1",
        "description": "Daily-close JSON contract (WORKSTREAM F).",
        "top_level_required": TOP_LEVEL_REQUIRED,
        "kpis": {
            "numeric": KPIS_NUMERIC,
            "objects": ["best_seller"],
            "best_seller_required": ["product", "qty"],
        },
        "reorder_row": {
            "required": REORDER_REQUIRED,
            "reorder_qty": {"type": "integer", "minimum": 0},
            "citation_pattern": r"\[[^\[\]]+:\d+\]",
        },
        "reply_row": {
            "required": REPLY_REQUIRED,
            "citation_pattern": r"\[[^\[\]]+:\d+\]",
            "first_reply_draft": "non-empty and references its citation",
        },
        "po_draft": {"type": "string", "minLength": 1},
        "money_leak_row": {"required": ["leak", "note", "evidence"]},
    }


def _normalize_schema(loaded: dict[str, Any]) -> dict[str, Any]:
    """Merge an on-disk schema into canonical shape (union of requirements).

    Another workstream persists the same fixture path in an alternate but
    compatible layout (``required_top`` / ``required_kpis`` /
    ``required_reorder`` / ``required_reply`` instead of
    ``top_level_required`` / ``kpis.numeric`` / ...). Rather than fighting
    over the format, normalise either layout into the canonical shape and
    enforce the UNION — the live close satisfies both, so the contract
    only gets stronger.
    """
    if "top_level_required" in loaded:
        return loaded
    norm = canonical_schema()
    alt_top = loaded.get("required_top") or []
    norm["top_level_required"] = sorted(set(norm["top_level_required"]) | set(alt_top))
    alt_kpis = loaded.get("required_kpis") or loaded.get("kpis") or []
    if isinstance(alt_kpis, list):
        norm["kpis"]["numeric"] = sorted(set(norm["kpis"]["numeric"]) | set(alt_kpis))
    alt_reorder = loaded.get("required_reorder") or []
    norm["reorder_row"]["required"] = sorted(
        set(norm["reorder_row"]["required"]) | set(alt_reorder))
    alt_reply = loaded.get("required_reply") or []
    norm["reply_row"]["required"] = sorted(
        set(norm["reply_row"]["required"]) | set(alt_reply))
    return norm


def ensure_schema_file() -> dict[str, Any]:
    """Write tests/fixtures/close_schema.json if missing; return schema.

    Never overwrites an existing file (a parallel workstream may own its
    layout — see _normalize_schema). Returns the canonical schema merged
    with whatever the on-disk file requires.
    """
    try:
        SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not SCHEMA_PATH.exists():
            SCHEMA_PATH.write_text(json.dumps(canonical_schema(), indent=2),
                                   encoding="utf-8")
            return canonical_schema()
        loaded = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        return _normalize_schema(loaded)
    except Exception:
        # Read-only checkout / odd FS: fall back to the in-memory schema so
        # the contract still gets enforced without file IO.
        return canonical_schema()


def demo_close(shop: str = "contract shop") -> dict[str, Any]:
    """Build a live close from the deterministic demo folder."""
    from omni_one.packs.seller_close import build_daily_close
    from omni_one.packs.seller_os import (
        ingest_seller_folder,
        build_seller_briefing,
        make_seller_demo_folder,
    )
    from omni_one.packs.seller_scenarios import run_all_scenarios
    tmp = Path(tempfile.mkdtemp(prefix="contract-close-"))
    folder = make_seller_demo_folder(tmp / "seller_demo", seed=42)
    events, _ = ingest_seller_folder(folder)
    briefing = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    return build_daily_close(events, briefing, scen, shop=shop)


# ---------------------------------------------------------------------------
# Contract assertions (each raises AssertionError with a precise path).
# ---------------------------------------------------------------------------


def assert_top_level(close: dict[str, Any]) -> None:
    for key in TOP_LEVEL_REQUIRED:
        assert key in close, f"close missing top-level key: {key!r}"
    assert isinstance(close["date"], str) and close["date"], "date must be non-empty str"
    assert isinstance(close["shop"], str) and close["shop"], "shop must be non-empty str"
    assert isinstance(close["headline"], str) and len(close["headline"]) > 10, \
        f"headline too short: {close.get('headline')!r}"
    assert isinstance(close["do_today"], list) and len(close["do_today"]) == 3, \
        f"do_today must be 3 items, got {close.get('do_today')!r}"
    assert isinstance(close["reorder_sheet"], list), "reorder_sheet must be a list"
    assert isinstance(close["reply_queue"], list), "reply_queue must be a list"
    assert isinstance(close["money_leaks"], list), "money_leaks must be a list"
    assert isinstance(close["listing_fixes"], list), "listing_fixes must be a list"
    assert isinstance(close["po_draft"], str) and close["po_draft"].strip(), \
        "po_draft must be a non-empty string"


def assert_kpis(close: dict[str, Any]) -> None:
    kpis = close.get("kpis")
    assert isinstance(kpis, dict), "kpis must be an object"
    for key in KPIS_NUMERIC:
        assert key in kpis, f"kpis missing key: {key!r}"
        val = kpis[key]
        assert isinstance(val, (int, float)) and not isinstance(val, bool), \
            f"kpis.{key} must be numeric, got {val!r}"
    assert "best_seller" in kpis and isinstance(kpis["best_seller"], dict), \
        "kpis.best_seller must be an object"
    assert "product" in kpis["best_seller"] and "qty" in kpis["best_seller"], \
        f"kpis.best_seller keys wrong: {kpis['best_seller']!r}"
    # Cross-field sanity (mirrors evals/run.py invariant 1).
    assert float(kpis["true_profit"]) <= float(kpis["gmv"]) + 0.011, \
        f"profit {kpis['true_profit']} > gmv {kpis['gmv']}"


def assert_reorder_rows(close: dict[str, Any]) -> None:
    for i, row in enumerate(close.get("reorder_sheet", [])):
        where = f"reorder_sheet[{i}]"
        assert isinstance(row, dict), f"{where} must be an object"
        for key in REORDER_REQUIRED:
            assert key in row, f"{where} missing key: {key!r}"
        assert isinstance(row["product"], str) and row["product"].strip(), \
            f"{where}.product must be non-empty str"
        for intkey in ("on_hand", "sold_7d", "reorder_qty"):
            assert isinstance(row[intkey], (int, float)) and not isinstance(row[intkey], bool), \
                f"{where}.{intkey} must be numeric, got {row[intkey]!r}"
        assert float(row["reorder_qty"]) >= 0, f"{where}.reorder_qty negative"
        assert abs(float(row["reorder_qty"]) - round(float(row["reorder_qty"]))) < 1e-6, \
            f"{where}.reorder_qty not integral: {row['reorder_qty']!r}"
        for numkey in ("daily_velocity", "days_left"):
            assert isinstance(row[numkey], (int, float)), \
                f"{where}.{numkey} must be numeric, got {row[numkey]!r}"
        cite = str(row.get("citation", ""))
        assert cite.strip(), f"{where} missing citation"
        assert CITATION_RE.search(cite), f"{where} citation lacks [file:line]: {cite!r}"


def assert_reply_rows(close: dict[str, Any]) -> None:
    queue = close.get("reply_queue", [])
    for i, q in enumerate(queue):
        where = f"reply_queue[{i}]"
        assert isinstance(q, dict), f"{where} must be an object"
        for key in REPLY_REQUIRED:
            assert key in q, f"{where} missing key: {key!r}"
        cite = str(q.get("citation", ""))
        assert cite.strip(), f"{where} missing citation"
        assert CITATION_RE.search(cite), f"{where} citation lacks [file:line]: {cite!r}"
    # First-reply contract: non-empty draft that references its citation.
    assert queue, "demo close must have at least one reply (at-risk DMs exist)"
    first = queue[0]
    draft = str(first.get("draft", ""))
    assert draft.strip() and len(draft) > 40, \
        f"first reply draft too short: {draft!r}"
    assert str(first["citation"]) in draft or CITATION_RE.search(draft), \
        f"first reply draft lacks citation: draft={draft[:80]!r} cite={first['citation']!r}"


def assert_leaks_and_po(close: dict[str, Any]) -> None:
    for i, leak in enumerate(close.get("money_leaks", [])):
        for key in ("leak", "note", "evidence"):
            assert key in leak, f"money_leaks[{i}] missing key: {key!r}"
    assert "Subject: Reorder" in close.get("po_draft", "") or \
        "no PO needed" in close.get("po_draft", "").lower() or \
        "Stock healthy" in close.get("po_draft", ""), \
        f"po_draft missing subject/healthy line: {close.get('po_draft','')[:80]!r}"


def validate_against_schema(close: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate the live close against the persisted schema dict."""
    for key in schema.get("top_level_required", []):
        assert key in close, f"schema: missing top-level key {key!r}"
    for key in schema.get("kpis", {}).get("numeric", []):
        assert key in close.get("kpis", {}), f"schema: missing kpis.{key}"
    pat = re.compile(schema.get("reorder_row", {}).get("citation_pattern", r".+"))
    for i, row in enumerate(close.get("reorder_sheet", [])):
        for key in schema.get("reorder_row", {}).get("required", []):
            assert key in row, f"schema: reorder[{i}] missing {key!r}"
        assert pat.search(str(row.get("citation", ""))), \
            f"schema: reorder[{i}] citation pattern miss"
    rpat = re.compile(schema.get("reply_row", {}).get("citation_pattern", r".+"))
    for i, q in enumerate(close.get("reply_queue", [])):
        for key in schema.get("reply_row", {}).get("required", []):
            assert key in q, f"schema: reply[{i}] missing {key!r}"
        assert rpat.search(str(q.get("citation", ""))), \
            f"schema: reply[{i}] citation pattern miss"


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_contract_schema_file_written_and_loaded():
    schema = ensure_schema_file()
    assert SCHEMA_PATH.exists(), f"schema file not written: {SCHEMA_PATH}"
    # Our required keys must be covered (superset allowed — see _normalize_schema).
    assert set(TOP_LEVEL_REQUIRED) <= set(schema["top_level_required"])
    assert set(KPIS_NUMERIC) <= set(schema["kpis"]["numeric"])
    # File must be small, readable JSON documentation.
    assert SCHEMA_PATH.stat().st_size < 10_000


def test_contract_top_level_keys():
    assert_top_level(demo_close())


def test_contract_kpis_types():
    assert_kpis(demo_close())


def test_contract_reorder_rows():
    close = demo_close()
    assert len(close["reorder_sheet"]) >= 1, "demo must yield >=1 reorder row"
    assert_reorder_rows(close)


def test_contract_reply_rows_first_has_cited_draft():
    assert_reply_rows(demo_close())


def test_contract_leaks_and_po():
    assert_leaks_and_po(demo_close())


def test_contract_live_close_matches_persisted_schema():
    schema = ensure_schema_file()
    validate_against_schema(demo_close(), schema)


def test_contract_golden_profit_stable():
    """Schema pin includes the golden number: profit 169.09 +/- 0.05."""
    close = demo_close()
    assert abs(float(close["kpis"]["true_profit"]) - 169.09) < 0.05, close["kpis"]
    assert "Profit $169.09" in close["headline"]


def test_contract_close_json_serialisable():
    """close.json must round-trip through json (no datetimes/objects)."""
    close = demo_close()
    blob = json.dumps(close, default=str)
    back = json.loads(blob)
    assert back["headline"] == close["headline"]
    assert back["reorder_sheet"] == close["reorder_sheet"]
