#!/usr/bin/env python3
"""
E2E — Free Palantir Alternative (Omni-One)
==========================================
Proves the free stack actually works end-to-end, $0 cost, no Palantir fees.

Mirrors Palantir use cases:

  1. Foundry: Data integration (CSV, receipt photo, WhatsApp) → DuckDB datasets → lineage
  2. Ontology: Digital twin (Supplier, Shipment, Patient, Ward, Transaction, Person) → links
  3. Gotham: Investigation graph expansion + entity resolution (fraud ring)
  4. AIP: Ontology-grounded LLM logic (supply delay, hospital overflow, fraud) — mock, free
  5. Vision: Photo → OCR (tesseract free) → Chart (opencv+matplotlib free) → pipeline (free)
  6. Apollo: Generate docker-compose (free deploy)

Run:
  PYTHONPATH=src python scripts/e2e_palantir_free.py
  PYTHONPATH=src python scripts/e2e_palantir_free.py --out /tmp/e2e_out

Verify: asserts + prints. If it exits 0, your free Palantir works.
"""
import sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import json
import shutil
import tempfile
from datetime import datetime

def log(step, msg): print(f"[{step}] {msg}")

def main(out_dir: str = "/tmp/e2e_palantir_free"):
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # --- Check free deps ---
    log("SETUP", "Checking free stack (all local, $0)...")
    try:
        import duckdb; log("SETUP", f"duckdb {duckdb.__version__} (free, in-process OLAP)")
    except ImportError:
        log("SETUP", "duckdb missing — pip install duckdb (free)")
    try:
        import pandas; log("SETUP", f"pandas {pandas.__version__} (free)")
    except ImportError:
        log("SETUP", "pandas missing")
    try:
        import pytesseract; pytesseract.get_tesseract_version(); log("SETUP", f"tesseract {pytesseract.get_tesseract_version()} (free OCR)")
    except Exception as e:
        log("SETUP", f"tesseract not ready: {e} — brew install tesseract (free)")

    # ================================================================
    # 1. FOUNDRY — free data integration
    # ================================================================
    log("1/6 FOUNDRY", "Creating Foundry datasets (DuckDB+Parquet, free) like Palantir Foundry...")
    from omni_one.palantir_free.foundry import FoundryDataset, Transform, FoundryBranch
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, LinkTypeDef, ObjectInstance, ActionDef
    from omni_one.palantir_free.gotham import Investigation, entity_resolution_candidates
    from omni_one.palantir_free.aip import AIPLogic, logic_supply_delay, logic_hospital_overflow, logic_fraud_ring
    from omni_one.palantir_free.apollo import generate as apollo_generate
    from omni_one.core.vision import analyze_photo

    base = out / "foundry"
    branch = FoundryBranch(base, branch="master")
    ds_suppliers = branch.dataset("suppliers")
    ds_shipments = branch.dataset("shipments")
    ds_patients = branch.dataset("patients")

    # Write suppliers (like Foundry ingest)
    import pandas as pd
    suppliers_df = pd.DataFrame([
        {"supplier_id": "S1", "name": "Acme Parts", "region": "us-east", "reliability": 0.92},
        {"supplier_id": "S2", "name": "Globex", "region": "eu", "reliability": 0.85},
    ])
    v1 = ds_suppliers.write(suppliers_df, lineage="ingest:suppliers.csv")
    log("1/6 FOUNDRY", f"suppliers {v1} rows={len(suppliers_df)} lineage={ds_suppliers.lineage()}")

    shipments_df = pd.DataFrame([
        {"shipment_id": "SH1", "supplier_id": "S1", "delay_hours": 5, "status": "IN_TRANSIT"},
        {"shipment_id": "SH2", "supplier_id": "S2", "delay_hours": 52, "status": "DELAYED"},
        {"shipment_id": "SH3", "supplier_id": "S1", "delay_hours": 2, "status": "DELIVERED"},
    ])
    v2 = ds_shipments.write(shipments_df, lineage="ingest:shipments.csv")
    log("1/6 FOUNDRY", f"shipments {v2} rows={len(shipments_df)}")

    # Transform: join (like Foundry PySpark) — free via DuckDB
    ds_enriched = branch.dataset("enriched_shipments")
    def enrich(suppliers, shipments):
        # Simple pandas join, like Spark
        return shipments.merge(suppliers, on="supplier_id", how="left")
    tr = Transform("enrich_shipments", inputs=[ds_suppliers, ds_shipments], output=ds_enriched, fn=enrich)
    v3 = tr.build()
    enriched = ds_enriched.read_latest()
    log("1/6 FOUNDRY", f"transform enrich_shipments -> {v3} rows={len(enriched)} (like Foundry build)")
    assert len(enriched) == 3, "Foundry transform failed"
    # Check lineage
    assert ds_enriched.versions()[-1]["lineage"].startswith("transform:enrich_shipments")

    # ================================================================
    # 2. ONTOLOGY — free digital twin
    # ================================================================
    log("2/6 ONTOLOGY", "Building Ontology (free alternative to Palantir Ontology $1M/yr)...")
    onto = Ontology(name="supply-ontology")
    onto.define_object_type(ObjectTypeDef(api_name="Supplier", display_name="Supplier", primary_key="supplier_id", title_property="name", properties=[PropertyDef(name="supplier_id", type="string", required=True), PropertyDef(name="name", type="string"), PropertyDef(name="reliability", type="double")]))
    onto.define_object_type(ObjectTypeDef(api_name="Shipment", display_name="Shipment", primary_key="shipment_id", properties=[PropertyDef(name="shipment_id", type="string", required=True), PropertyDef(name="delay_hours", type="double"), PropertyDef(name="status", type="string")]))
    onto.define_object_type(ObjectTypeDef(api_name="Ward", display_name="Hospital Ward", primary_key="ward_id", properties=[PropertyDef(name="ward_id", type="string", required=True), PropertyDef(name="occupancy", type="integer"), PropertyDef(name="capacity", type="integer")]))
    onto.define_object_type(ObjectTypeDef(api_name="Transaction", display_name="Transaction", primary_key="transaction_id", properties=[PropertyDef(name="transaction_id", type="string", required=True), PropertyDef(name="amount", type="double"), PropertyDef(name="device_id", type="string")]))
    onto.define_object_type(ObjectTypeDef(api_name="Person", display_name="Person", primary_key="person_id", properties=[PropertyDef(name="person_id", type="string", required=True), PropertyDef(name="name", type="string"), PropertyDef(name="phone", type="string")]))
    onto.define_link_type(LinkTypeDef(api_name="SUPPLIES", display_name="Supplies", from_type="Supplier", to_type="Shipment", cardinality="ONE_TO_MANY"))
    onto.define_link_type(LinkTypeDef(api_name="MADE_TRANSACTION", display_name="Made Tx", from_type="Person", to_type="Transaction", cardinality="ONE_TO_MANY"))
    onto.define_action(ActionDef(api_name="rerouteShipment", display_name="Reroute Shipment", object_type="Shipment", parameters=[PropertyDef(name="status", type="string")], checks=[{"field": "status", "allowed": ["REROUTED", "DELAYED", "IN_TRANSIT"]}]))

    # Bulk create objects from Foundry datasets
    for _, row in suppliers_df.iterrows():
        onto.create_object(ObjectInstance(object_type="Supplier", primary_key=row["supplier_id"], properties=dict(row)), lineage=f"foundry:{v1}")
    for _, row in shipments_df.iterrows():
        onto.create_object(ObjectInstance(object_type="Shipment", primary_key=row["shipment_id"], properties=dict(row)), lineage=f"foundry:{v2}")
    # Link
    onto.link("Supplier", "S1", "SUPPLIES", "SH1")
    onto.link("Supplier", "S2", "SUPPLIES", "SH2")
    onto.link("Supplier", "S1", "SUPPLIES", "SH3")
    # Add Gotham-like persons + transactions
    onto.create_object(ObjectInstance(object_type="Person", primary_key="P1", properties={"person_id": "P1", "name": "Maria Lopez", "phone": "555-0142"}))
    onto.create_object(ObjectInstance(object_type="Person", primary_key="P2", properties={"person_id": "P2", "name": "Maria Lopes", "phone": "555-0142"}))  # typo, should resolve
    onto.create_object(ObjectInstance(object_type="Transaction", primary_key="T1", properties={"transaction_id": "T1", "amount": 120, "device_id": "D1"}))
    onto.create_object(ObjectInstance(object_type="Transaction", primary_key="T2", properties={"transaction_id": "T2", "amount": 8900, "device_id": "D1"}))
    onto.link("Person", "P1", "MADE_TRANSACTION", "T1")
    onto.link("Person", "P2", "MADE_TRANSACTION", "T2")
    # Hospital wards
    onto.create_object(ObjectInstance(object_type="Ward", primary_key="W1", properties={"ward_id": "W1", "occupancy": 45, "capacity": 50}))
    onto.create_object(ObjectInstance(object_type="Ward", primary_key="W2", properties={"ward_id": "W2", "occupancy": 12, "capacity": 50}))

    log("2/6 ONTOLOGY", f"ontology stats {onto.stats()} hash={onto.lineage_hash()}")
    assert onto.stats()["counts"]["Supplier"] == 2
    assert onto.stats()["counts"]["Shipment"] == 3
    # Traverse test (like digital twin)
    neighbors = onto.traverse("Supplier", "S1", "SUPPLIES", depth=1)
    log("2/6 ONTOLOGY", f"traverse Supplier S1 -SUPPLIES-> {len(neighbors)} shipments (like twin)")
    assert len(neighbors) == 2

    # Action test
    onto.apply_action("rerouteShipment", "SH2", {"status": "REROUTED"})
    assert onto.get("Shipment", "SH2").properties["status"] == "REROUTED"
    log("2/6 ONTOLOGY", "Action rerouteShipment applied, free, no Palantir fees")

    # ================================================================
    # 3. GOTHAM — free investigation graph
    # ================================================================
    log("3/6 GOTHAM", "Gotham investigation (free graph + entity res)...")
    inv = Investigation(onto, name="fraud-ring")
    inv.add("Person", "P1")
    added = inv.expand("MADE_TRANSACTION", depth=1)
    log("3/6 GOTHAM", f"expand MADE_TRANSACTION added {added}, working_set={inv.summary()}")
    # Entity resolution: P1 and P2 same phone, similar name -> should candidate
    persons = onto.search("Person")
    cands = entity_resolution_candidates(persons, threshold=0.80)
    log("3/6 GOTHAM", f"entity resolution candidates {cands} (free, deterministic)")
    assert any(set([a, b]) == {"P1", "P2"} for a, b, _ in cands), "Gotham resolve failed to link Maria Lopez/Lopes"
    # Path finding: P1 -> T2 via P2? (P1 -? No direct, but via phone similarity we can link)
    # For demo, path P1 -> T1 is direct, P1 -> T2 via resolve
    path = inv.find_path("Person:P1", "Transaction:T1", max_depth=2)
    log("3/6 GOTHAM", f"path Person:P1 -> Transaction:T1 = {path}")
    assert path is not None
    # Add P2 and expand to see T2
    inv.add("Person", "P2")
    inv.expand("MADE_TRANSACTION", depth=1)
    log("3/6 GOTHAM", f"working_set now {len(inv.working_set)} objects, timeline {inv.timeline()[:2]}")
    assert len(inv.working_set) >= 4

    # ================================================================
    # 4. AIP — free ontology-grounded LLM logic
    # ================================================================
    log("4/6 AIP", "AIP logic grounded in ontology (free mock, no OpenAI fees)...")
    aip_logic = AIPLogic(onto, name="supply-aip")
    res1 = aip_logic.run(logic_supply_delay, shipment_id="SH1")
    log("4/6 AIP", f"supply SH1: {res1['answer']} citations={res1['citations'][:1]}")
    assert "OK" in res1["answer"]
    res2 = aip_logic.run(logic_supply_delay, shipment_id="SH2")
    log("4/6 AIP", f"supply SH2: {res2['answer']} actions={res2['actions']}")
    assert "DELAYED" in res2["answer"] or "REROUTED" in res2["answer"] or "reroute" in str(res2["actions"]).lower()
    res3 = aip_logic.run(logic_hospital_overflow, ward_id="W1")
    log("4/6 AIP", f"ward W1: {res3['answer']}")
    assert "AT RISK" in res3["answer"]
    res4 = aip_logic.run(logic_fraud_ring, transaction_id="T2")
    log("4/6 AIP", f"fraud T2: {res4['answer']}")
    assert "ANOMALY" in res4["answer"]
    log("4/6 AIP", f"AIP cost {res3.get('cost_usd')} free={res3.get('free')}")

    # ================================================================
    # 5. VISION — free photo -> text + chart -> pipeline
    # ================================================================
    log("5/6 VISION", "Vision: photo -> OCR (tesseract free) -> chart (opencv+matplotlib free) -> pipeline (free)...")
    # Generate synthetic receipt+chart image via vision demo (free)
    from PIL import Image, ImageDraw, ImageFont
    import io
    img = Image.new("RGB", (1000, 600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except:
        font = ImageFont.load_default()
    lines = ["Maya Tacos Receipt", "Date: 2024-09-12", "Tacos al pastor  32 x 3.50 = 112.00", "Birria          12 x 4.00 = 48.00", "Total 160.00"]
    y = 30
    for l in lines:
        draw.text((30, y), l, fill="black", font=font)
        y += 45
    # Bars
    for i, (x, val) in enumerate(zip([150, 350], [112, 48])):
        draw.rectangle([x, 400 - val, x + 80, 400], fill="#4F46E5", outline="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    photo_bytes = buf.getvalue()
    result = analyze_photo(photo_bytes, filename="e2e_receipt.png", run_pipeline=True)
    log("5/6 VISION", f"OCR chars={result['ocr']['meta'].get('chars')} engine={result['engines']['ocr']}")
    log("5/6 VISION", f"chart {result['chart']['detected']['reason'][:60]} data={result['chart']['data']}")
    assert result["cost_usd"] == 0.0, "Vision should be free"
    assert result["ocr"]["text"] != "", "OCR failed"
    assert result["pipeline"] is not None
    log("5/6 VISION", f"pipeline events {result['pipeline']['events']} summary {result['pipeline']['summary']['llm_bypass_rate']}")
    # Also test upload via FastAPI vision demo endpoint (free)
    from fastapi.testclient import TestClient
    from omni_one.api.fastapi_app import create_omni_one_app
    app = create_omni_one_app()
    client = TestClient(app)
    r = client.get("/api/v1/vision/demo")
    assert r.status_code == 200 and r.json()["cost_usd"] == 0.0
    log("5/6 VISION", "FastAPI /vision/demo 200 free=$0")

    # ================================================================
    # 6. APOLLO — free deploy
    # ================================================================
    log("6/6 APOLLO", "Apollo free alternative (Docker Compose, $0)...")
    apollo_out = apollo_generate(out / "apollo")
    assert (apollo_out / "docker-compose.yml").exists()
    assert (apollo_out / "apollo_manifest.json").exists()
    log("6/6 APOLLO", f"generated {apollo_out} with compose + manifest, free")

    # --- Final verify ---
    log("E2E", f"Ontology hash {onto.lineage_hash()}, Foundry versions {len(ds_suppliers.versions())}, Gotham candidates {len(cands)}, AIP runs {len(aip_logic.runs)}")
    summary = {
        "out_dir": str(out),
        "foundry": {"suppliers": len(suppliers_df), "shipments": len(shipments_df), "enriched": len(enriched)},
        "ontology": onto.stats(),
        "gotham": inv.summary(),
        "aip": {"runs": len(aip_logic.runs), "cost_usd": 0.0},
        "vision": {"ocr_chars": result["ocr"]["meta"].get("chars"), "chart_free": True, "pipeline_free": True},
        "apollo": str(apollo_out),
        "free": True,
        "palantir_alternative_cost": "$0 (vs $1-5M/yr Palantir)",
        "cheapest_tech": ["Python", "DuckDB (free OLAP)", "Pandas+Parquet (free)", "FastAPI (free)", "Pydantic (free)", "Tesseract+OpenCV+Matplotlib (free)", "Local mock LLM (free, Ollama optional)"],
    }
    (out / "e2e_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    log("E2E", f"Wrote {out / 'e2e_summary.json'}")
    print("\n" + "="*70)
    print("E2E FREE PALANTIR ALTERNATIVE — PASSED")
    print("="*70)
    print(json.dumps(summary, indent=2))
    print("\nAll 6 pillars free, local, no API fees. Run again: PYTHONPATH=src python scripts/e2e_palantir_free.py")
    return summary

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="/tmp/e2e_palantir_free")
    args = parser.parse_args()
    main(out_dir=args.out)
