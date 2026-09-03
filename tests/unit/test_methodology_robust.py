"""Methodology robustness: ontology types/history/approvals, foundry gates, workshop grounding, governance chain, AIP eval."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, LinkTypeDef, ObjectInstance, ActionDef
from omni_one.palantir_free.foundry import FoundryDataset, FoundryBranch, Transform, check_not_null, sql_join
from omni_one.palantir_free.workshop import WorkshopApp
from omni_one.palantir_free.governance import AuditLog, ingest_ontology_edits, can_access
from omni_one.palantir_free.aip import AIPLogic, check_grounding
import tempfile


def _onto():
    o = Ontology("t")
    o.define_object_type(ObjectTypeDef(api_name="Product", display_name="P", primary_key="sku", title_property="name",
        properties=[PropertyDef(name="sku", type="string", required=True), PropertyDef(name="name", type="string", required=True), PropertyDef(name="on_hand", type="integer")]))
    o.define_object_type(ObjectTypeDef(api_name="Order", display_name="O", primary_key="order_id",
        properties=[PropertyDef(name="order_id", type="string", required=True)]))
    o.define_link_type(LinkTypeDef(api_name="CONTAINS", display_name="C", from_type="Order", to_type="Product", cardinality="MANY_TO_ONE"))
    o.define_action(ActionDef(api_name="reorder", display_name="R", object_type="Product",
        parameters=[PropertyDef(name="status", type="string")], checks=[{"field": "status", "allowed": ["REORDERED"]}],
        requires_approval=True, allowed_approvers=["lead"]))
    return o


def test_ontology_types_history_approvals():
    o = _onto()
    o.create_object(ObjectInstance(object_type="Product", primary_key="A", properties={"sku": "A", "name": "x", "on_hand": "5"}))
    assert o.get("Product", "A").properties["on_hand"] == 5  # coerced string->int
    try:
        o.create_object(ObjectInstance(object_type="Product", primary_key="B", properties={"sku": "B", "name": "y", "on_hand": "bad"}))
        assert False, "should reject bad int"
    except ValueError:
        pass
    assert len(o.history("Product", "A")) == 1
    # Approval required
    try:
        o.apply_action("reorder", "A", {"status": "REORDERED"})
        assert False
    except ValueError:
        pass
    pid = o.propose_action("reorder", "A", {"status": "REORDERED"}, proposer="ops")
    try:
        o.approve_action(pid, "intruder")
        assert False
    except ValueError:
        pass
    o.approve_action(pid, "lead")
    assert o.get("Product", "A").version == 2
    assert len(o.history("Product", "A")) == 2
    # Persistence roundtrip keeps edits
    with tempfile.TemporaryDirectory() as tmp:
        o.save(tmp)
        o2 = Ontology.load(tmp)
        assert o2.get("Product", "A").properties["status"] == "REORDERED"
        assert len(o2._edits) == len(o._edits)


def test_foundry_gate_and_incremental():
    import pandas as pd
    with tempfile.TemporaryDirectory() as tmp:
        br = FoundryBranch(Path(tmp), "master")
        ds = br.dataset("t")
        ds.write(pd.DataFrame([{"sku": "A", "gmv": 10}]), "v1")
        out = br.dataset("out")
        tr = Transform("t", [ds], out, lambda df: df, expectations=[lambda df: check_not_null(df, "sku")])
        tr.build()
        # Failing expectation blocks
        tr2 = Transform("bad", [ds], br.dataset("out2"), lambda df: df.assign(sku=None),
                        expectations=[lambda df: check_not_null(df, "sku")])
        try:
            tr2.build()
            assert False
        except ValueError:
            pass
        # Incremental skips
        assert tr.build_if_stale() is None


def test_workshop_grounding_and_governance():
    o = _onto()
    o.create_object(ObjectInstance(object_type="Product", primary_key="A", properties={"sku": "A", "name": "x", "on_hand": 1}))
    o.create_object(ObjectInstance(object_type="Order", primary_key="O1", properties={"order_id": "O1"}))
    o.link("Order", "O1", "CONTAINS", "A")
    app = WorkshopApp(o, "q")
    d = app.add_decision("fix", "Product:A", "high", ["ontology:Product:A"], {"action": "reorder", "params": {"status": "REORDERED"}})
    app.assign(d.id, "ops")
    app.approve(d.id, "lead")
    app.resolve(d.id, "lead")
    assert app.decisions[d.id].status == "resolved"
    try:
        app.add_decision("phantom", "Product:NOPE", "high")
        assert False
    except ValueError:
        pass
    log = AuditLog("t")
    assert ingest_ontology_edits(log, o) >= 3
    assert log.verify()["ok"]
    # Tamper detection
    log.events[0]["payload"] = {"tampered": True}
    assert not log.verify()["ok"]
    assert can_access(["internal"], ["internal"])
    assert not can_access(["restricted"], ["internal"])


def test_aip_grounding_and_eval():
    o = _onto()
    o.create_object(ObjectInstance(object_type="Product", primary_key="A", properties={"sku": "A", "name": "x", "on_hand": 1}))
    logic = AIPLogic(o, "t")
    g = check_grounding(o, ["ontology:Product:A.on_hand=1"])
    assert g["ok"] and g["score"] == 1.0
    g2 = check_grounding(o, ["Product:GHOST"])
    assert not g2["ok"]
    ev = logic.evaluate([{"name": "x", "fn": lambda oo, ii, pp: {"answer": "Product A ok", "citations": ["ontology:Product:A"], "actions": []}, "inputs": {}, "expect_contains": ["Product A"], "require_grounded": True}])
    assert ev["pass_rate"] == 1.0
