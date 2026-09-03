"""12-scenario sharpness: triggers, idempotency, performance, grounding."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
from omni_one.packs.seller_scenarios import run_all_scenarios, scenarios_to_workshop, SCENARIOS
from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
from omni_one.palantir_free.workshop import WorkshopApp
import tempfile, time

def _demo_events():
    tmp = tempfile.mkdtemp()
    f = make_seller_demo_folder(Path(tmp) / "d")
    ev, _ = ingest_seller_folder(f)
    return ev

def test_all_12_registered_and_fast():
    assert len(SCENARIOS) == 12
    ev = _demo_events()
    t0 = time.time()
    r1 = run_all_scenarios(ev)
    dt = (time.time() - t0) * 1000
    assert r1["total"] >= 5, f"expected practical hits, got {r1['by_scenario']}"
    assert dt < 2000, f"too slow {dt}ms"
    # Idempotent: same events → same IDs
    r2 = run_all_scenarios(ev)
    assert [d["id"] for d in r1["decisions"]] == [d["id"] for d in r2["decisions"]]
    # Severity sorted critical→low
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    seq = [order[d["severity"]] for d in r1["decisions"]]
    assert seq == sorted(seq)
    # Key scenarios fire on demo
    assert r1["by_scenario"]["STOCKOUT_RISK"] >= 1
    assert r1["by_scenario"]["UNANSWERED_COMPLAINT"] >= 1

def test_scenarios_to_workshop_grounded_idempotent():
    ev = _demo_events()
    scen = run_all_scenarios(ev)
    onto = Ontology("t")
    onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="P", primary_key="sku", title_property="name",
        properties=[PropertyDef(name="sku", type="string", required=True), PropertyDef(name="name", type="string", required=True)]))
    # Seed from scenario products
    seen = set()
    for d in scen["decisions"]:
        prod = d.get("product")
        if prod and prod not in seen:
            seen.add(prod)
            sku = "".join(c if c.isalnum() else "" for c in prod)[:10] or f"P{len(seen)}"
            try:
                onto.create_object(ObjectInstance(object_type="Product", primary_key=sku, properties={"sku": sku, "name": prod}))
            except Exception:
                pass
    if not seen:
        onto.create_object(ObjectInstance(object_type="Product", primary_key="G", properties={"sku": "G", "name": "General"}))
    app = WorkshopApp(onto, "t")
    m1 = scenarios_to_workshop(scen, app)
    n1 = len(app.decisions)
    assert n1 >= 3
    # Second run upserts (no duplicates)
    m2 = scenarios_to_workshop(scen, app)
    assert len(app.decisions) == n1
    # All grounded
    for d in app.decisions.values():
        t, pk = d.object_ref.split(":", 1)
        assert onto.get(t, pk) is not None
