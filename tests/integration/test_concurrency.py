"""Thread-safety smoke: concurrent cache + ontology writes don't corrupt."""
import threading


def test_concurrent_writes_safe():
    from omni_one.core.cache import SemanticCache
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
    cache = SemanticCache()
    errs = []

    def writer(n):
        try:
            for i in range(50):
                cache.set(f"q-{n}-{i}", {"response": f"r-{n}-{i}"})
                assert cache.get(f"q-{n}-{i}") is not None
        except Exception as e:
            errs.append(e)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errs, errs
    assert cache.get_stats()["writes"] == 200

    onto = Ontology("conc")
    onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="P", primary_key="sku",
        properties=[PropertyDef(name="sku", type="string", required=True)]))
    errs2 = []

    def owriter(n):
        try:
            for i in range(25):
                pk = f"S{n}-{i}"
                onto.create_object(ObjectInstance(object_type="Product", primary_key=pk, properties={"sku": pk}))
        except Exception as e:
            errs2.append(e)

    ts = [threading.Thread(target=owriter, args=(n,)) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs2, errs2
    assert onto.stats()["counts"]["Product"] == 100
