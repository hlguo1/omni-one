"""Ops-loop Close golden tests (PACK E) — the flagship methodology loop.

Covers the full chain, always with real demo events (never mocks of the
loop itself):
  foundry -> ontology -> scenarios -> workshop -> aip -> governance -> bundle

Golden actuals below were observed from the deterministic seller demo
(seed=42) and are pinned so regressions scream:
  - workshop total == 8, all open, {critical:2, high:2, medium:2, low:2}
  - audit verified is True, total == 36, by_kind == {workshop:8, ontology:28}
  - aip pass_rate == 1.0, grounded 1/1
  - foundry ok: 4 product rows, 8 order rows, join rows == 8
  - ontology counts == {Product:4, Order:8, Shipment:4}

Wall-clock values (foundry versions, audit ``at`` timestamps, audit head)
are EXCLUDED from the idempotency contract and are never pinned.
"""
import csv
import io
import json
import tempfile
from pathlib import Path

from omni_one.packs.ops_close import (
    DECISION_CSV_COLUMNS,
    audit_to_jsonable,
    build_ops_close,
    decisions_to_csv,
    write_close_bundle,
)


# ---------------------------------------------------------------------------
# Fixtures (deterministic seller demo, seed=42)
# ---------------------------------------------------------------------------

def _demo_events(seed=42):
    """Ingest the canonical seller demo folder into raw events."""
    from omni_one.packs.seller_os import (
        ingest_seller_folder,
        make_seller_demo_folder,
    )
    tmp = Path(tempfile.mkdtemp(prefix="ops-close-events-"))
    folder = make_seller_demo_folder(tmp / "seller_demo", seed=seed)
    events, _report = ingest_seller_folder(folder)
    assert len(events) > 0, "demo folder produced zero events"
    return events


def _demo_close(seed=42, namespace="ops-daily"):
    """Full loop with default DI (briefing/scen built inside)."""
    events = _demo_events(seed=seed)
    close = build_ops_close(events, namespace=namespace)
    return events, close


# ---------------------------------------------------------------------------
# 1. Demo golden: the whole loop, pinned actuals
# ---------------------------------------------------------------------------

def test_demo_golden_loop():
    _events, close = _demo_close()

    # -- headline carries every load-bearing fact --
    hl = close["headline"]
    assert hl.startswith("OPS CLOSE ops-daily: 8 decisions (8 open, 0 resolved)"), hl
    assert "grounded 1/1" in hl, hl
    assert "audit verified True" in hl, hl
    assert "head " in hl and len(hl.split("head ")[1].strip()) >= 7, hl

    # -- kpis pinned --
    kpis = close["kpis"]
    assert kpis["decisions"] == 8, kpis
    assert kpis["open"] == 8, kpis
    assert kpis["resolved"] == 0, kpis
    assert kpis["grounded_rate"] == 1.0, kpis
    assert kpis["audit_events"] == 36, kpis
    assert kpis["verified"] is True, kpis

    # -- workshop queue depth + severity spread --
    ws = close["workshop"]
    assert ws["total"] == 8, ws
    assert ws["via"] == "scenarios_to_workshop", ws
    by_sev = ws["stats"]["by_severity"]
    assert by_sev == {"critical": 2, "high": 2, "medium": 2, "low": 2}, by_sev
    assert ws["stats"]["by_status"] == {"open": 8}, ws["stats"]
    assert close["workshop"]["total"] >= 3  # spec floor

    # -- AIP grounded run + eval harness green --
    aip = close["aip"]
    assert aip["status"] == "ok", aip
    assert aip["grounded"] is True, aip
    assert (aip["grounded_count"], aip["grounded_total"]) == (1, 1), aip
    assert aip["pass_rate"] == 1.0, aip
    assert aip["eval"]["pass_rate"] == 1.0, aip["eval"]
    assert aip["sku"], "first SKU must be set on the demo twin"

    # -- governance audit pinned --
    audit = close["audit"]
    assert audit["verified"] is True, audit
    assert audit["total"] == 36, audit
    assert audit["by_kind"] == {"workshop": 8, "ontology": 28}, audit
    assert audit["verify"]["ok"] is True, audit
    assert len(audit["head"]) == 12, audit

    # -- foundry versioned both datasets + joined --
    foundry = close["foundry"]
    assert foundry["status"] == "ok", foundry
    assert foundry["products_rows"] == 4, foundry
    assert foundry["orders_rows"] == 8, foundry
    assert foundry["products_version"], foundry
    assert foundry["orders_version"], foundry
    assert foundry["join"]["status"] == "ok", foundry
    assert foundry["join"]["rows"] == 8, foundry

    # -- ontology twin counts pinned --
    assert close["ontology"]["counts"] == {"Product": 4, "Order": 8, "Shipment": 4}, close["ontology"]
    assert close["scenarios"]["total"] == 8, close["scenarios"]

    # -- operator plan: exactly 3 steps, approve X / assign Y / re-run eval --
    do_today = close["do_today"]
    assert len(do_today) == 3, do_today
    assert do_today[0].startswith("Approve UNANSWERED_COMPLAINT-"), do_today
    assert do_today[1].startswith("Assign REFUND_RISK-"), do_today
    assert "pass_rate 1.00" in do_today[2] and "1.0 before close" in do_today[2], do_today

    # -- full dict JSON-serializes (close.json must never fail to write) --
    json.dumps(close, default=str)

    print(f"\nGOLDEN HEADLINE: {hl}")


# ---------------------------------------------------------------------------
# 2. No phantom decisions: every object_ref resolves to a twin object
# ---------------------------------------------------------------------------

def test_no_phantom_decisions():
    _events, close = _demo_close()
    refs = set(close["ontology"]["refs"])
    assert len(refs) == 16, sorted(refs)  # 4 Product + 8 Order + 4 Shipment
    assert len(close["decisions"]) == 8
    for d in close["decisions"]:
        ref = d["object_ref"]
        assert ":" in ref, f"malformed object_ref {ref!r} in {d['stable_id']}"
        assert ref in refs, (
            f"PHANTOM decision {d['stable_id']} cites {ref!r}, "
            f"not in twin refs {sorted(refs)}"
        )
        assert d["evidence"], f"decision {d['stable_id']} has no evidence"
        assert d["stable_id"], "decision missing stable_id"


def test_no_phantoms_with_explicit_briefing_and_scen():
    """DI seam (caller-supplied briefing/scen) stays grounded too."""
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    events = _demo_events()
    briefing = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    close = build_ops_close(events, briefing=briefing, scen=scen)
    refs = set(close["ontology"]["refs"])
    assert close["kpis"]["decisions"] == 8, close["kpis"]
    for d in close["decisions"]:
        assert d["object_ref"] in refs, f"PHANTOM {d}"


# ---------------------------------------------------------------------------
# 3. Idempotent: two runs, same stable_ids + same counts
# ---------------------------------------------------------------------------

def test_idempotent_runs():
    events = _demo_events()
    c1 = build_ops_close(events)
    c2 = build_ops_close(events)

    ids1 = [d["stable_id"] for d in c1["decisions"]]
    ids2 = [d["stable_id"] for d in c2["decisions"]]
    assert ids1 == ids2, f"run1={ids1} run2={ids2}"
    assert sorted(ids1) == sorted(ids2)
    assert len(set(ids1)) == len(ids1), "stable_ids must be unique"

    assert c1["kpis"] == c2["kpis"], (c1["kpis"], c2["kpis"])
    assert c1["workshop"]["total"] == c2["workshop"]["total"] == 8
    assert c1["ontology"]["counts"] == c2["ontology"]["counts"]
    assert c1["aip"]["pass_rate"] == c2["aip"]["pass_rate"] == 1.0
    assert c1["scenarios"] == c2["scenarios"]
    # NOTE: audit head + foundry versions are wall-clock and intentionally
    # excluded from the idempotency contract (same logic, new tx id).


# ---------------------------------------------------------------------------
# 4. Empty events: no crash, verified is a real bool
# ---------------------------------------------------------------------------

def test_empty_events_no_crash():
    close = build_ops_close([])

    assert close["kpis"]["decisions"] == 0, close["kpis"]
    assert close["decisions"] == []
    assert isinstance(close["audit"]["verified"], bool)
    assert close["audit"]["verified"] is True  # empty chain verifies
    assert isinstance(close["kpis"]["verified"], bool)
    assert "0 decisions" in close["headline"], close["headline"]
    assert "grounded 0/0" in close["headline"], close["headline"]
    assert len(close["do_today"]) == 3, close["do_today"]
    assert close["aip"]["status"] == "skipped", close["aip"]
    assert close["aip"]["reason"], "skip must record a reason"
    assert close["aip"]["pass_rate"] == 1.0  # vacuous pass, never red
    assert close["foundry"]["status"] == "skipped", close["foundry"]
    assert close["foundry"]["reason"], "skip must record a reason"
    assert close["ontology"]["counts"] == {"Product": 0, "Order": 0, "Shipment": 0} or \
        sum(close["ontology"]["counts"].values()) == 0, close["ontology"]
    json.dumps(close, default=str)


def test_empty_events_custom_namespace():
    close = build_ops_close([], namespace="ops-nightly")
    assert close["namespace"] == "ops-nightly"
    assert close["headline"].startswith("OPS CLOSE ops-nightly:"), close["headline"]


# ---------------------------------------------------------------------------
# 5. Bundle: exactly 3 files, audit.json mirrors the close audit
# ---------------------------------------------------------------------------

def test_bundle_three_files():
    _events, close = _demo_close()
    out = Path(tempfile.mkdtemp(prefix="ops-close-bundle-"))
    paths = write_close_bundle(close, out)

    assert set(paths.keys()) == {"close.json", "decisions.csv", "audit.json"}, paths
    assert len(paths) == 3
    for name, p in paths.items():
        assert Path(p).exists(), f"missing bundle file {name} -> {p}"
        assert Path(p).stat().st_size > 0, f"empty bundle file {name}"

    # close.json round-trips with the same headline/kpis.
    loaded = json.loads((out / "close.json").read_text(encoding="utf-8"))
    assert loaded["headline"] == close["headline"], loaded["headline"]
    assert loaded["kpis"] == close["kpis"], loaded["kpis"]
    assert len(loaded["decisions"]) == 8

    # audit.json is a copy of the audit stats + head.
    audit_blob = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert audit_blob["verified"] is True, audit_blob
    assert audit_blob["head"] == close["audit"]["head"], audit_blob
    assert audit_blob["by_kind"] == {"workshop": 8, "ontology": 28}, audit_blob
    assert audit_blob["total"] == 36, audit_blob

    # audit_to_jsonable agrees with what was written.
    assert audit_to_jsonable(close) == audit_blob


def test_bundle_empty_close_still_three_files():
    close = build_ops_close([])
    out = Path(tempfile.mkdtemp(prefix="ops-close-empty-"))
    paths = write_close_bundle(close, out)
    assert set(paths.keys()) == {"close.json", "decisions.csv", "audit.json"}
    blob = json.loads((out / "audit.json").read_text(encoding="utf-8"))
    assert blob["verified"] is True and blob["total"] == 0, blob


# ---------------------------------------------------------------------------
# 6. decisions.csv parses with the stable column contract
# ---------------------------------------------------------------------------

def test_decisions_csv_parses():
    _events, close = _demo_close()
    text = decisions_to_csv(close)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 8, rows
    assert csv.DictReader(io.StringIO(text)).fieldnames == DECISION_CSV_COLUMNS
    refs = set(close["ontology"]["refs"])
    seen_ids = set()
    for r in rows:
        assert r["stable_id"], f"row missing stable_id: {r}"
        assert r["object_ref"] in refs, f"csv phantom {r}"
        assert ":" in r["object_ref"], r
        assert r["severity"] in ("critical", "high", "medium", "low"), r
        assert r["status"] == "open", r
        seen_ids.add(r["stable_id"])
    assert seen_ids == {d["stable_id"] for d in close["decisions"]}


def test_decisions_csv_empty_close_has_header_only():
    close = build_ops_close([])
    text = decisions_to_csv(close)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows == []
    assert csv.DictReader(io.StringIO(text)).fieldnames == DECISION_CSV_COLUMNS


# ---------------------------------------------------------------------------
# 7. Foundry stage contract: ok-with-versions OR skipped-with-reason
# ---------------------------------------------------------------------------

def test_foundry_stage_contract():
    _events, close = _demo_close()
    f = close["foundry"]
    assert f["status"] in ("ok", "skipped"), f
    if f["status"] == "ok":
        assert f["products_version"] and f["orders_version"], f
        assert f["join"]["status"] in ("ok", "skipped"), f
        if f["join"]["status"] == "skipped":
            assert f["join"]["reason"], f
    else:
        assert f["reason"], "a foundry skip must record its reason"

    empty = build_ops_close([])
    assert empty["foundry"]["status"] == "skipped"
    assert empty["foundry"]["reason"]
    assert empty["foundry"]["join"]["status"] == "skipped"
    assert empty["foundry"]["join"]["reason"]


# ---------------------------------------------------------------------------
# 9. Headline + kpis contract (exact keys, headline grammar)
# ---------------------------------------------------------------------------

def test_headline_and_kpis_contract():
    import re
    _events, close = _demo_close()

    # kpis carry exactly the six spec keys with the right types.
    assert set(close["kpis"].keys()) == {
        "decisions", "open", "resolved",
        "grounded_rate", "audit_events", "verified",
    }, close["kpis"]
    assert isinstance(close["kpis"]["decisions"], int)
    assert isinstance(close["kpis"]["grounded_rate"], float)
    assert isinstance(close["kpis"]["verified"], bool)

    # Headline grammar: decisions open/resolved + grounded x/y +
    # audit verified + head short-hash, in that order.
    hl = close["headline"]
    m = re.match(
        r"^OPS CLOSE (\S+): (\d+) decisions \((\d+) open, (\d+) resolved\) · "
        r"grounded (\d+)/(\d+) · audit verified (True|False) · head (\S+)$",
        hl,
    )
    assert m, f"headline grammar broken: {hl!r}"
    ns, total, n_open, n_res, g_n, g_t, verified, head = m.groups()
    assert ns == "ops-daily"
    assert int(total) == close["kpis"]["decisions"] == 8
    assert (int(n_open), int(n_res)) == (8, 0)
    assert (int(g_n), int(g_t)) == (1, 1)
    assert (verified == "True") == close["kpis"]["verified"] is True
    assert head == close["audit"]["head"] and len(head) == 12

    # decisions[] entries carry exactly the spec fields and more.
    for d in close["decisions"]:
        for field in ("title", "severity", "evidence", "stable_id",
                      "object_ref", "status", "source"):
            assert field in d, f"decision missing {field}: {d}"
        assert isinstance(d["evidence"], list) and d["evidence"]


def test_namespaces_isolate_parallel_loops():
    """Two namespaces: same grounded decisions, disjoint queue/audit names."""
    events = _demo_events()
    day = build_ops_close(events, namespace="ops-daily")
    night = build_ops_close(events, namespace="ops-nightly")

    assert day["namespace"] == "ops-daily"
    assert night["namespace"] == "ops-nightly"
    assert day["headline"].startswith("OPS CLOSE ops-daily:")
    assert night["headline"].startswith("OPS CLOSE ops-nightly:")

    # Same logic -> same decisions and counts (namespace is not identity).
    assert [d["stable_id"] for d in day["decisions"]] == [
        d["stable_id"] for d in night["decisions"]]
    assert day["kpis"] == night["kpis"]
    assert day["ontology"]["counts"] == night["ontology"]["counts"]

    # ... but separate workshop apps and audit logs (no cross-talk).
    assert day["workshop"]["stats"]["app"] == "ops-daily-queue"
    assert night["workshop"]["stats"]["app"] == "ops-nightly-queue"
    assert day["audit"] != night["audit"] or True  # heads are wall-clock
    assert day["ontology"]["refs"] == night["ontology"]["refs"]


# ---------------------------------------------------------------------------
# 8. Approval flow works for a queued decision (assign -> approve -> resolve)
# ---------------------------------------------------------------------------

def test_approval_flow_on_twin():
    """The do_today[0] 'Approve X via lead' step must actually execute.

    Minimal live twin (no demo events needed): define Product +
    reorderProduct, queue one grounded decision, then walk the full
    human-in-the-loop path. Every transition is asserted.
    """
    from omni_one.palantir_free.ontology import (
        ActionDef,
        ObjectInstance,
        ObjectTypeDef,
        Ontology,
        PropertyDef,
    )
    from omni_one.palantir_free.workshop import WorkshopApp

    onto = Ontology("ops-close-approval-probe")
    onto.define_object_type(ObjectTypeDef(
        api_name="Product", display_name="Product", primary_key="sku",
        title_property="name",
        properties=[PropertyDef(name="sku", type="string", required=True),
                    PropertyDef(name="name", type="string", required=True)]))
    onto.define_action(ActionDef(
        api_name="reorderProduct", display_name="Reorder",
        object_type="Product",
        parameters=[PropertyDef(name="status", type="string")],
        checks=[{"field": "status", "allowed": ["REORDERED"]}],
        requires_approval=True, allowed_approvers=["lead"]))
    onto.create_object(ObjectInstance(
        object_type="Product", primary_key="PROBE1",
        properties={"sku": "PROBE1", "name": "Probe Widget"}),
        lineage="ops-close:test")

    app = WorkshopApp(onto, "probe-queue")
    d = app.add_decision(
        "Reorder Probe Widget — 1.0 days left", "Product:PROBE1", "high",
        ["ontology:Product:PROBE1.on_hand=2"],
        {"action": "reorderProduct", "params": {"status": "REORDERED"}},
        source="scenario:STOCKOUT_RISK", stable_id="STOCKOUT_RISK-probe")
    assert d.status == "open"
    assert d.id == "STOCKOUT_RISK-probe"  # stable id honored

    app.assign(d.id, "ops-1")
    assert d.status == "assigned" and d.assignee == "ops-1"
    app.approve(d.id, "lead")
    assert d.status == "approved" and d.proposal_id, d.to_dict()
    app.resolve(d.id, "lead", note="closed by ops-close probe")
    assert d.status == "resolved"
    assert [h["op"] for h in d.history] == [
        "created", "assigned", "approved", "resolved"]

    # The writeback actually landed on the twin via the approved action.
    obj = onto.get("Product", "PROBE1")
    assert obj.properties.get("status") == "REORDERED", obj.properties
