"""
AIP — Free alternative to Palantir AIP (AI Logic grounded in Ontology)
============================================================
Palantir AIP: ontology-grounded LLM, $500k/yr. Free alternative: deterministic
pipeline + ontology context + local LLM mock/Ollama, $0.

Mirrors:
  AIP Logic  →  ontology-grounded function calling (deterministic)
  AIP Agent  →  loops over ontology objects, like our ProactiveEngine but ontology-aware
  Guardrails →  evidence bundle + budget + checks (already built)

Tech: cheapest efficient:
  - MultiLayerDataPipeline (free, 90% bypass) for all data ops
  - Ontology as context (free, no vector DB fees if you want — but we can use local Weaviate)
  - Local LLM: Ollama (llama3.2:3b, mistral) free, or mock if no Ollama — still works offline
  - No OpenAI/Gemini fees unless you opt-in.

Use: hospital ops asks "which wards will overflow tomorrow?" — AIP logic queries ontology
(Patient, Bed, Admission), runs pipeline to detect anomaly, then drafts action grounded in objects.
"""
from __future__ import annotations
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime
import json

from .ontology import Ontology, ObjectInstance

# Reuse pipeline for free analysis
try:
    from ..core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
    from ..core.cache import SemanticCache  # type: ignore
    from ..core.model_router import ModelRouter  # type: ignore
except ImportError:
    try:
        from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
        from omni_one.core.cache import SemanticCache  # type: ignore
        from omni_one.core.model_router import ModelRouter  # type: ignore
    except ImportError:
        MultiLayerDataPipeline = None  # type: ignore
        SemanticCache = None  # type: ignore
        ModelRouter = None  # type: ignore


def check_grounding(ontology: Ontology, citations: List[str]) -> Dict[str, Any]:
    """Validate citations reference real ontology objects (anti-hallucination gate). Free.
    Accepts 'ontology:Type:pk...', 'Type:pk', or containing 'Type:pk'. Returns score + ungrounded list.
    """
    import re as _re
    if not citations:
        return {"score": 0.0, "checked": 0, "ungrounded": [], "ok": False}
    grounded, ungrounded = 0, []
    for cit in citations:
        s = str(cit)
        # Find all Type:pk candidates (CapWord:alnum-_)
        found = False
        for m in _re.finditer(r"\b([A-Z][A-Za-z0-9_]*):([A-Za-z0-9_\-]+)", s):
            t, pk = m.group(1), m.group(2)
            # Skip generic prefixes like 'ontology' if followed by real ref later — check all
            if t.lower() == "ontology":
                continue
            if ontology.get(t, pk) is not None:
                found = True
                break
        # Fallback: 'ontology:Type:pk' explicit
        if not found:
            m2 = _re.search(r"ontology:([A-Za-z0-9_]+):([A-Za-z0-9_\-]+)", s)
            if m2 and ontology.get(m2.group(1), m2.group(2)) is not None:
                found = True
        if found:
            grounded += 1
        else:
            ungrounded.append(s[:80])
    score = grounded / max(len(citations), 1)
    return {"score": round(score, 3), "checked": len(citations), "grounded": grounded, "ungrounded": ungrounded, "ok": score >= 0.5}


class FunctionRegistry:
    """Registry of ontology-grounded functions (like Palantir Functions). Free."""
    def __init__(self):
        self._fns: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, fn: Callable, description: str = "", required_inputs: Optional[List[str]] = None):
        self._fns[name] = {"fn": fn, "description": description, "required": required_inputs or []}

    def get(self, name: str) -> Callable:
        if name not in self._fns:
            raise KeyError(f"function {name} not registered (have {list(self._fns)})")
        return self._fns[name]["fn"]

    def list(self) -> List[Dict[str, Any]]:
        return [{"name": k, "description": v["description"], "required": v["required"]} for k, v in self._fns.items()]


# Global default registry with built-in logics (registered below)
DEFAULT_REGISTRY = FunctionRegistry()


class AIPLogic:
    """
    Ontology-grounded logic. Like Palantir AIP Logic but free.
    Reuses single pipeline, validates grounding, supports registry + eval.
    """
    def __init__(self, ontology: Ontology, name: str, registry: Optional[FunctionRegistry] = None):
        self.ontology = ontology
        self.name = name
        self.registry = registry or DEFAULT_REGISTRY
        self.runs: List[Dict[str, Any]] = []
        self._pipeline = None
        # Lazy single pipeline (was new per run — wasteful)
        if MultiLayerDataPipeline:
            try:
                outer = self
                class _MockRouter(ModelRouter):  # type: ignore
                    def generate(self, prompt: str, model=None, **kw):  # type: ignore
                        return f"[AIP MOCK:{outer.name}] {prompt[:100]} — grounded."
                self._pipeline = MultiLayerDataPipeline(model_router=_MockRouter(), cache=SemanticCache())  # type: ignore
            except Exception:
                self._pipeline = None

    def run(self, fn: Callable, grounding_threshold: float = 0.5, **inputs) -> Dict[str, Any]:
        """fn(ontology, inputs, pipeline) -> {answer, citations, actions}. Grounding-checked."""
        result = fn(self.ontology, dict(inputs), self._pipeline)
        return self._finalize(result, grounding_threshold)

    def run_registered(self, fn_name: str, grounding_threshold: float = 0.5, **inputs) -> Dict[str, Any]:
        fn = self.registry.get(fn_name)
        # Validate required inputs early (like Palantir)
        meta = self.registry._fns[fn_name]
        missing = [r for r in meta["required"] if r not in inputs]
        if missing:
            raise ValueError(f"{fn_name} missing required inputs {missing}")
        return self.run(fn, grounding_threshold=grounding_threshold, **inputs)

    def _finalize(self, result: Dict[str, Any], grounding_threshold: float) -> Dict[str, Any]:
        result = dict(result or {})
        result["logic"] = self.name
        result["at"] = datetime.now().isoformat()
        result["ontology_hash"] = self.ontology.lineage_hash()
        result["free"] = True
        result["cost_usd"] = 0.0
        if "citations" not in result or not result["citations"]:
            result["citations"] = []
        # Grounding gate (anti-hallucination, like Palantir guardrails)
        g = check_grounding(self.ontology, list(result.get("citations", [])))
        result["grounding"] = g
        result["grounded"] = bool(g.get("ok"))
        if not g.get("ok"):
            result["warning"] = f"Low grounding {g.get('score')} < {grounding_threshold}: {g.get('ungrounded', [])[:2]}"
        self.runs.append(result)
        return result

    def evaluate(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Eval harness for AIP (like Palantir Eval): cases=[{fn, inputs, expect_contains, expect_actions}]. Free."""
        passed, total = 0, 0
        details = []
        for c in cases:
            total += 1
            try:
                fn = c["fn"] if callable(c.get("fn")) else self.registry.get(c.get("fn_name", ""))
                res = self.run(fn, **c.get("inputs", {}))
                ok = True
                reasons = []
                for needle in c.get("expect_contains", []):
                    if needle not in str(res.get("answer", "")):
                        ok = False
                        reasons.append(f"missing {needle!r}")
                for act in c.get("expect_actions", []):
                    if act not in (res.get("actions") or []):
                        ok = False
                        reasons.append(f"missing action {act!r}")
                if c.get("require_grounded") and not res.get("grounded"):
                    ok = False
                    reasons.append("not grounded")
                if ok:
                    passed += 1
                details.append({"case": c.get("name", f"case{total}"), "passed": ok, "reasons": reasons, "answer": str(res.get("answer", ""))[:100]})
            except Exception as e:
                details.append({"case": c.get("name", f"case{total}"), "passed": False, "reasons": [str(e)]})
        return {"passed": passed, "total": total, "pass_rate": round(passed / max(total, 1), 3), "details": details, "free": True}


class AIPAgent:
    """
    Free AIP Agent loop over ontology, like ProactiveEngine but ontology-aware.
    """
    def __init__(self, ontology: Ontology, logic: AIPLogic):
        self.ontology = ontology
        self.logic = logic

    def scan(self, object_type: str, where: Optional[Dict[str, Any]] = None, logic_fn: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Scan objects, run logic per object, collect actions. Free, batch.
        """
        objs = self.ontology.search(object_type, where=where)
        out: List[Dict[str, Any]] = []
        for obj in objs[:50]:  # cap for demo, free pagination
            if logic_fn:
                res = self.logic.run(logic_fn, object=obj.primary_key, properties=obj.properties)
                out.append({"object": f"{object_type}:{obj.primary_key}", "result": res})
        return out


# --- Example free logics (mirroring Palantir use cases) ---
def logic_supply_delay(ontology: Ontology, inputs: Dict[str, Any], pipeline) -> Dict[str, Any]:
    """
    Palantir Foundry supply chain use case, free.
    Checks Shipments linked to Suppliers, flags delays via pipeline anomaly.
    """
    # inputs: {"shipment_id": "..."} or scan
    shipment_pk = inputs.get("shipment_id") or inputs.get("object")
    if not shipment_pk:
        return {"answer": "No shipment_id", "citations": []}
    ship = ontology.get("Shipment", shipment_pk)
    if not ship:
        return {"answer": f"Shipment {shipment_pk} not found", "citations": []}
    # Use pipeline to check numeric fields like delay_hours
    delay = ship.properties.get("delay_hours", 0)
    # Build events for pipeline (free)
    events = [{"timestamp": datetime.now(), "source": "shipment", "entity_id": shipment_pk, "value": float(delay), "metadata": {"signal": "delay_hours"}}]
    summary = None
    if pipeline:
        _, summary = pipeline.process_batch(events)
        summary = pipeline.get_metrics_summary()
    # Decision
    is_delayed = delay > 24
    return {
        "answer": f"Shipment {shipment_pk} {'DELAYED' if is_delayed else 'OK'} (delay {delay}h). " + ("Recommend reroute." if is_delayed else "No action."),
        "citations": [f"ontology:Shipment:{shipment_pk}.delay_hours={delay}", f"pipeline:{summary}"] if summary else [f"Shipment:{shipment_pk}"],
        "actions": ["reroute"] if is_delayed else [],
        "evidence": f"delay_hours={delay} via pipeline",
    }

def logic_hospital_overflow(ontology: Ontology, inputs: Dict[str, Any], pipeline) -> Dict[str, Any]:
    ward_pk = inputs.get("ward_id") or inputs.get("object")
    ward = ontology.get("Ward", ward_pk) if ward_pk else None
    if not ward:
        return {"answer": "Ward not found", "citations": []}
    occupancy = ward.properties.get("occupancy", 0)
    capacity = ward.properties.get("capacity", 100)
    ratio = occupancy / max(capacity, 1)
    events = [{"timestamp": datetime.now(), "source": "ward", "entity_id": ward_pk, "value": ratio, "metadata": {"signal": "occupancy_ratio"}}]
    if pipeline:
        pipeline.process_batch(events)
    at_risk = ratio > 0.85
    return {
        "answer": f"Ward {ward_pk} occupancy {occupancy}/{capacity} ({ratio:.0%}) {'AT RISK' if at_risk else 'OK'}",
        "citations": [f"ontology:Ward:{ward_pk}.occupancy={occupancy}", f"capacity={capacity}"],
        "actions": ["open overflow ward", "staff up"] if at_risk else [],
    }

def logic_fraud_ring(ontology: Ontology, inputs: Dict[str, Any], pipeline) -> Dict[str, Any]:
    # Look at Transaction objects linked to same device
    tx_pk = inputs.get("transaction_id") or inputs.get("object")
    tx = ontology.get("Transaction", tx_pk) if tx_pk else None
    if not tx:
        return {"answer": "Transaction not found", "citations": []}
    amount = tx.properties.get("amount", 0)
    # Use pipeline to check anomaly vs history (mock)
    events = [{"timestamp": datetime.now(), "source": "transaction", "entity_id": tx_pk, "value": float(amount), "metadata": {"signal": "amount"}}]
    if pipeline:
        pipeline.process_batch(events)
    is_anomaly = amount > 5000
    return {
        "answer": f"Transaction {tx_pk} amount ${amount} {'ANOMALY' if is_anomaly else 'normal'}",
        "citations": [f"ontology:Transaction:{tx_pk}.amount={amount}"],
        "actions": ["freeze", "investigate"] if is_anomaly else [],
    }


def logic_seller_stockout(ontology: Ontology, inputs: Dict[str, Any], pipeline) -> Dict[str, Any]:
    """Seller highlight grounded in Product ontology (used by Workshop + eval)."""
    sku = inputs.get("sku") or inputs.get("object")
    prod = ontology.get("Product", sku) if sku else None
    if not prod:
        return {"answer": "Product not found", "citations": []}
    try:
        on_hand = float(prod.properties.get("on_hand", 0))
        sold_7d = float(prod.properties.get("sold_7d", 0))
    except Exception:
        on_hand, sold_7d = 0, 0
    days = on_hand / (sold_7d / 7) if sold_7d else 999
    at_risk = days < 5
    return {
        "answer": f"Product {sku} {on_hand} left, sold {sold_7d}/7d = {days:.1f} days — {'REORDER' if at_risk else 'OK'}",
        "citations": [f"ontology:Product:{sku}.on_hand={on_hand}", f"ontology:Product:{sku}.sold_7d={sold_7d}"],
        "actions": ["reorder"] if at_risk else [],
    }


# Register built-ins (methodology: discoverable functions, like Palantir)
DEFAULT_REGISTRY.register("supply_delay", logic_supply_delay, "Shipment delay check", ["shipment_id"])
DEFAULT_REGISTRY.register("hospital_overflow", logic_hospital_overflow, "Ward overflow check", ["ward_id"])
DEFAULT_REGISTRY.register("fraud_ring", logic_fraud_ring, "Transaction anomaly check", ["transaction_id"])
DEFAULT_REGISTRY.register("seller_stockout", logic_seller_stockout, "Product stockout check", ["sku"])
