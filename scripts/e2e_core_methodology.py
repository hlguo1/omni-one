#!/usr/bin/env python3
"""
E2E Core Methodology — Palantir-style suite WITHOUT replicating Palantir
========================================================================
Methodology (like Palantir, not a clone):
  Foundry (datasets+transforms+lineage) -> Ontology (typed twin+actions) ->
  Pipeline (4-layer evidence) -> Workshop (decision queue) -> AIP (grounded logic) ->
  Governance (hash-chained audit) -> Apollo (compose)

Highlights wired through ONE loop:
  - Seller OS: Product stockout + win-back (primary highlight)
  - Supply: Shipment delay reroute
  - Hospital: Ward overflow

Free, $0, offline. Verifies robustness of strengthened core.

Run:
  PYTHONPATH=src python3 scripts/e2e_core_methodology.py --out /tmp/e2e_method
"""
import sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json, shutil
from datetime import datetime

def log(s, m): print(f"[{s}] {m}")

def main(out_dir="/tmp/e2e_method"):
    out = Path(out_dir)
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)

    from omni_one.palantir_free.foundry import FoundryDataset, FoundryBranch, Transform, check_not_null, check_unique, check_range, profile_dataset, sql_join
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, LinkTypeDef, ObjectInstance, ActionDef
    from omni_one.palantir_free.workshop import WorkshopApp
    from omni_one.palantir_free.governance import AuditLog, ingest_pipeline_results, ingest_ontology_edits, ingest_workshop, ingest_aip_runs, ingest_foundry_versions, can_access
    from omni_one.palantir_free.aip import AIPLogic, DEFAULT_REGISTRY
    from omni_one.palantir_free.apollo import generate as apollo_generate
    import pandas as pd

    # ---------- 1. Foundry: expectations gate + profiling + incremental + join ----------
    log("1/6 FOUNDRY", "Datasets with expectations, profiling, incremental, multi-SQL...")
    base = out / "foundry"
    branch = FoundryBranch(base, "master")
    ds_products = branch.dataset("products")
    ds_orders = branch.dataset("orders")
    ds_inventory = branch.dataset("inventory")

    products = pd.DataFrame([
        {"sku": "TB001", "name": "Tote Bag Handmade", "on_hand": 2, "sold_7d": 6},
        {"sku": "CM002", "name": "Ceramic Mug", "on_hand": 15, "sold_7d": 3},
    ])
    v_p = ds_products.write(products, "ingest:inventory.csv")
    orders = pd.DataFrame([
        {"order_id": "#1001", "sku": "TB001", "qty": 2, "gmv": 56.0},
        {"order_id": "#1002", "sku": "CM002", "qty": 1, "gmv": 22.0},
    ])
    v_o = ds_orders.write(orders, "ingest:shopify.csv")
    log("1/6", f"products {v_p} orders {v_o} profile={profile_dataset(products)['rows']} rows")

    # Transform with expectations gate (blocks on fail, like Foundry)
    ds_joined = branch.dataset("joined")
    def join_fn(prod_df, ord_df):
        return ord_df.merge(prod_df, on="sku", how="left")
    tr = Transform("join_orders_products", [ds_products, ds_orders], ds_joined, join_fn,
                   expectations=[lambda df: check_not_null(df, "sku"), lambda df: check_range(df, "gmv", min_v=0)])
    v_j = tr.build()
    log("1/6", f"transform join -> {v_j} (gate passed)")
    # Incremental: second build_if_stale should skip (None)
    skipped = tr.build_if_stale()
    assert skipped is None, "incremental should skip when fresh"
    log("1/6", "incremental build_if_stale skipped (fresh) — robust")
    # Multi-dataset SQL
    joined_sql = sql_join({"p": ds_products, "o": ds_orders}, "SELECT o.order_id, p.name, o.gmv FROM o JOIN p ON o.sku = p.sku")
    assert len(joined_sql) == 2
    log("1/6", f"multi-SQL join {len(joined_sql)} rows — robust")

    # ---------- 2. Ontology: types, history, cardinality, approvals, persistence ----------
    log("2/6 ONTOLOGY", "Typed twin with history, cardinality, approvals, markings, save/load...")
    onto = Ontology("seller-ontology")
    onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product", primary_key="sku", title_property="name",
        properties=[PropertyDef(name="sku", type="string", required=True), PropertyDef(name="name", type="string", required=True),
                    PropertyDef(name="on_hand", type="integer", required=True), PropertyDef(name="sold_7d", type="integer")],
        default_markings=["internal"]))
    onto.define_object_type(ObjectTypeDef(api_name="Order", display_name="Order", primary_key="order_id",
        properties=[PropertyDef(name="order_id", type="string", required=True), PropertyDef(name="sku", type="string"), PropertyDef(name="qty", type="integer"), PropertyDef(name="gmv", type="double")]))
    onto.define_object_type(ObjectTypeDef(api_name="Shipment", display_name="Shipment", primary_key="shipment_id",
        properties=[PropertyDef(name="shipment_id", type="string", required=True), PropertyDef(name="delay_hours", type="double")]))
    onto.define_object_type(ObjectTypeDef(api_name="Ward", display_name="Ward", primary_key="ward_id",
        properties=[PropertyDef(name="ward_id", type="string", required=True), PropertyDef(name="occupancy", type="integer"), PropertyDef(name="capacity", type="integer")]))
    onto.define_link_type(LinkTypeDef(api_name="CONTAINS", display_name="Contains", from_type="Order", to_type="Product", cardinality="MANY_TO_ONE"))
    onto.define_link_type(LinkTypeDef(api_name="SUPPLIES", display_name="Supplies", from_type="Product", to_type="Shipment", cardinality="ONE_TO_MANY"))
    onto.define_action(ActionDef(api_name="reorderProduct", display_name="Reorder", object_type="Product",
        parameters=[PropertyDef(name="status", type="string")], checks=[{"field": "status", "allowed": ["REORDERED"]}], requires_approval=True, allowed_approvers=["lead"]))
    onto.define_action(ActionDef(api_name="rerouteShipment", display_name="Reroute", object_type="Shipment",
        parameters=[PropertyDef(name="status", type="string")], checks=[{"field": "status", "allowed": ["REROUTED"]}]))

    # Typed coercion: "2" string -> int 2 should work; bad type should raise
    onto.create_object(ObjectInstance(object_type="Product", primary_key="TB001", properties={"sku": "TB001", "name": "Tote Bag Handmade", "on_hand": "2", "sold_7d": 6}), lineage=f"foundry:{v_p}")
    try:
        onto.create_object(ObjectInstance(object_type="Product", primary_key="BAD", properties={"sku": "BAD", "name": "x", "on_hand": "not-a-number"}))
        raise AssertionError("type coercion should have failed")
    except ValueError:
        log("2/6", "type coercion rejects bad int — robust")
    onto.create_object(ObjectInstance(object_type="Product", primary_key="CM002", properties={"sku": "CM002", "name": "Ceramic Mug", "on_hand": 15, "sold_7d": 3}), lineage=f"foundry:{v_p}")
    onto.create_object(ObjectInstance(object_type="Order", primary_key="#1001", properties={"order_id": "#1001", "sku": "TB001", "qty": 2, "gmv": 56.0}))
    onto.create_object(ObjectInstance(object_type="Shipment", primary_key="SH2", properties={"shipment_id": "SH2", "delay_hours": 52}))
    onto.create_object(ObjectInstance(object_type="Ward", primary_key="W1", properties={"ward_id": "W1", "occupancy": 45, "capacity": 50}))
    # Links with cardinality
    onto.link("Order", "#1001", "CONTAINS", "TB001")
    log("2/6", f"ontology {onto.stats()} hash={onto.lineage_hash()}")
    # History
    assert len(onto.history("Product", "TB001")) >= 1
    # Approval workflow: direct apply should fail (requires_approval), propose+approve works
    try:
        onto.apply_action("reorderProduct", "TB001", {"status": "REORDERED"})
        raise AssertionError("should require approval")
    except ValueError as e:
        assert "requires approval" in str(e)
    pid = onto.propose_action("reorderProduct", "TB001", {"status": "REORDERED"}, proposer="ops")
    assert onto._proposals[pid]["status"] == "pending"
    onto.approve_action(pid, "lead")
    assert onto.get("Product", "TB001").properties["status"] == "REORDERED"
    assert onto.get("Product", "TB001").version >= 2
    log("2/6", f"approval {pid} applied, version={onto.get('Product','TB001').version} — robust")
    # Persistence
    onto.save(out / "ontology")
    onto2 = Ontology.load(out / "ontology")
    assert onto2.get("Product", "TB001").properties["status"] == "REORDERED"
    log("2/6", "save/load roundtrip — robust")
    # Markings
    assert can_access(["internal"], ["internal", "public"])
    assert not can_access(["restricted"], ["internal"])
    assert onto2.get("Product", "TB001", allowed_markings=["public"]) is None  # hidden

    # ---------- 3. Pipeline evidence (Seller highlight through core) ----------
    log("3/6 PIPELINE", "Seller events through 4-layer pipeline (evidence)...")
    from omni_one.packs.seller_os import build_seller_briefing, make_seller_demo_folder, ingest_seller_folder
    demo_folder = make_seller_demo_folder(out / "seller_demo")
    events, report = ingest_seller_folder(demo_folder)
    briefing = build_seller_briefing(events)
    assert briefing["kpis"]["gmv"] > 0 and briefing["kpis"]["stockout_risk"] >= 1
    log("3/6", f"seller briefing GMV ${briefing['kpis']['gmv']} profit ${briefing['kpis']['true_profit']} stockout {briefing['kpis']['stockout_risk']}")

    # ---------- 4. Workshop: decision queue on ontology ----------
    log("4/6 WORKSHOP", "Decision queue FROM ontology (no phantoms)...")
    from omni_one.palantir_free.workshop import WorkshopApp
    app = WorkshopApp(onto2, "seller-daily")
    # Generic builder from ontology search (supply/hospital style)
    made = app.build_from_search("Shipment", {"shipment_id": "SH2"}, title_fn=lambda o: f"Reroute {o.primary_key} delay {o.properties.get('delay_hours')}h",
                                 severity="high", action_fn=lambda o: {"action": "rerouteShipment", "params": {"status": "REROUTED"}}, source="supply")
    assert len(made) == 1
    # Seller builder
    seller_made = app.build_seller_queue(briefing)
    log("4/6", f"workshop queue {app.stats()} (supply {len(made)} + seller {len(seller_made)})")
    assert len(app.decisions) >= 2
    # Operate: assign -> approve -> resolve (writeback via ontology)
    did = made[0].id
    app.assign(did, "ops-1")
    app.approve(did, "lead")
    app.resolve(did, "lead", "rerouted")
    assert app.decisions[did].status == "resolved"
    # Grounding: phantom should fail
    try:
        app.add_decision("phantom", "Product:NOPE", "high")
        raise AssertionError("phantom should fail grounding")
    except ValueError:
        log("4/6", "phantom decision rejected (grounded) — robust")

    # ---------- 5. AIP: registry + grounding + eval ----------
    log("5/6 AIP", "Registry + grounding gate + eval...")
    from omni_one.palantir_free.aip import AIPLogic, check_grounding
    logic = AIPLogic(onto2, "ops-aip")
    assert any(f["name"] == "seller_stockout" for f in logic.registry.list())
    r1 = logic.run_registered("seller_stockout", sku="TB001")
    assert "TB001" in r1["answer"] and r1["grounded"], f"ungrounded: {r1}"
    log("5/6", f"seller_stockout grounded {r1['grounding']} — robust")
    # Ungrounded should warn
    from omni_one.palantir_free.aip import logic_supply_delay
    r_bad = logic.run(lambda o, i, p: {"answer": "ghost", "citations": ["Product:GHOST"]}, test=1)
    assert not r_bad["grounded"]
    ev = logic.evaluate([
        {"name": "stockout", "fn_name": "seller_stockout", "inputs": {"sku": "TB001"}, "expect_contains": ["TB001"], "require_grounded": True},
        {"name": "supply", "fn_name": "supply_delay", "inputs": {"shipment_id": "SH2"}, "expect_contains": ["SH2"], "require_grounded": True},
    ])
    # supply_delay needs Shipment type — registered, should pass grounding (ontology:Shipment:SH2)
    log("5/6", f"AIP eval {ev['passed']}/{ev['total']} — robust")
    assert ev["passed"] >= 1

    # ---------- 6. Governance: unified audit ----------
    log("6/6 GOVERNANCE", "Hash-chained audit across all layers...")
    from omni_one.palantir_free.governance import AuditLog
    audit = AuditLog("methodology-e2e")
    # Ingest pipeline results from briefing pipeline? Re-run pipeline for events sample
    from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline
    from omni_one.core.cache import SemanticCache
    from omni_one.core.model_router import ModelRouter
    class _Mock(ModelRouter):
        def generate(self, prompt: str, model=None, **kw): return "[MOCK] ok"
    pipe = MultiLayerDataPipeline(model_router=_Mock(), cache=SemanticCache())
    sample = events[:8]
    results, _ = pipe.process_batch(sample)
    n1 = ingest_pipeline_results(audit, results)
    n2 = ingest_ontology_edits(audit, onto2)
    n3 = ingest_workshop(audit, app)
    n4 = ingest_aip_runs(audit, logic)
    n5 = ingest_foundry_versions(audit, [ds_products, ds_orders])
    v = audit.verify()
    assert v["ok"], f"audit chain broken {v}"
    log("6/6", f"audit {audit.stats()} (pipe {n1} onto {n2} workshop {n3} aip {n4} foundry {n5}) verified — robust")
    audit.export(out / "audit.json")

    # Apollo
    from omni_one.palantir_free.apollo import generate as apollo_generate
    apollo_generate(out / "apollo")
    summary = {"out": str(out), "foundry": {"products": v_p, "joined": v_j}, "ontology_hash": onto2.lineage_hash(),
               "workshop": app.stats(), "aip_eval": ev, "audit": audit.stats(), "free": True}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n" + "="*70 + "\nE2E CORE METHODOLOGY — PASSED (Palantir-style suite, not a clone)\n" + "="*70)
    print(json.dumps(summary, indent=2))
    return summary

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/e2e_method")
    print(main(ap.parse_args().out))
