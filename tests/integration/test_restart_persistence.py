"""Restart persistence: ontology + workshop + audit survive reload via LocalStore/JSONL."""
import tempfile
from pathlib import Path


def test_restart_persistence():
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
    from omni_one.palantir_free.workshop import WorkshopApp
    from omni_one.palantir_free.governance import AuditLog
    from omni_one.infra.store import LocalStore

    with tempfile.TemporaryDirectory() as tmp:
        store = LocalStore(data_root=tmp)
        onto = Ontology("restart-test")
        onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product", primary_key="sku",
            properties=[PropertyDef(name="sku", type="string", required=True), PropertyDef(name="name", type="string", required=True)]))
        onto.create_object(ObjectInstance(object_type="Product", primary_key="SKU1", properties={"sku": "SKU1", "name": "Tote"}))
        assert onto.persist_to_store(store) in ("duckdb", "json")

        app = WorkshopApp(onto, "w1")
        d = app.add_decision("Reorder Tote", "Product:SKU1", "high", ["[inventory.csv:2]"], stable_id="STOCKOUT-abc")
        app.persist_to_store(store)

        audit_path = Path(tmp) / "audit.jsonl"
        audit = AuditLog("t", persist_path=audit_path)
        audit.append("workshop", d.id, {"status": "open"})
        audit.save_jsonl()

        # Simulate restart: fresh objects, load from same store/files
        store2 = LocalStore(data_root=tmp)
        onto2 = Ontology("restart-test")
        onto2.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product", primary_key="sku",
            properties=[PropertyDef(name="sku", type="string", required=True), PropertyDef(name="name", type="string", required=True)]))
        assert onto2.load_from_store(store2) == 1
        assert onto2.get("Product", "SKU1") is not None

        app2 = WorkshopApp(onto2, "w1")
        assert app2.load_from_store(store2) == 1
        assert "STOCKOUT-abc" in app2.decisions

        audit2 = AuditLog.load_jsonl(audit_path)
        assert audit2.verify()["ok"] is True
        assert audit2.verify()["total"] == 1
        store.close(); store2.close()
