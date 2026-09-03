"""
Governance — Unified audit + lineage + markings (methodology like Palantir)
============================================================================
Palantir's core methodology: every read/write/decision is audited, lineage-tracked,
and markings-enforced. We don't replicate their stack — same methodology, free:

  Append-only hash-chained AuditLog ingests:
    - pipeline evidence bundles (Layer1-4 citations + cost)
    - ontology edits/history/proposals
    - workshop decisions (assign/approve/resolve)
    - AIP runs (grounded answers)
    - foundry builds (dataset versions)

  Markings: objects carry ["public","internal","restricted"]; actors have clearance;
  governance filters (like Palantir markings).

Free: stdlib hashlib/json only.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def _hash(prev: str, event: Dict[str, Any]) -> str:
    return hashlib.sha256((prev + _canonical(event)).encode()).hexdigest()


class AuditLog:
    """Append-only hash chain. Verify detects tampering (like Palantir audit)."""

    def __init__(self, name: str = "omni-audit"):
        self.name = name
        self.events: List[Dict[str, Any]] = []
        self._prev = "GENESIS"

    def append(self, kind: str, ref: str, payload: Dict[str, Any], actor: str = "system",
               markings: Optional[List[str]] = None) -> Dict[str, Any]:
        event = {
            "seq": len(self.events),
            "at": datetime.now().isoformat(),
            "kind": kind,  # pipeline | ontology | workshop | aip | foundry
            "ref": ref,
            "actor": actor,
            "markings": markings or ["internal"],
            "payload": payload,
            "prev": self._prev,
        }
        h = _hash(self._prev, {k: v for k, v in event.items() if k != "prev"})
        # Store hash + prev for verify
        event["hash"] = h
        self.events.append(event)
        self._prev = h
        return event

    def verify(self) -> Dict[str, Any]:
        """Recompute chain. Returns {ok, checked, first_bad}."""
        prev = "GENESIS"
        for i, ev in enumerate(self.events):
            body = {k: v for k, v in ev.items() if k not in ("prev", "hash")}
            # body includes seq/at/kind/ref/actor/markings/payload — recompute
            expect = _hash(prev, body)
            if expect != ev.get("hash") or ev.get("prev") != prev:
                return {"ok": False, "checked": i, "first_bad": i, "total": len(self.events)}
            prev = ev["hash"]
        return {"ok": True, "checked": len(self.events), "total": len(self.events)}

    def query(self, kind: Optional[str] = None, actor: Optional[str] = None,
              ref_contains: Optional[str] = None) -> List[Dict[str, Any]]:
        out = self.events
        if kind:
            out = [e for e in out if e["kind"] == kind]
        if actor:
            out = [e for e in out if e["actor"] == actor]
        if ref_contains:
            out = [e for e in out if ref_contains in e["ref"]]
        return list(out)

    def export(self, path) -> str:
        from pathlib import Path as _P
        p = _P(path)
        p.write_text(json.dumps({"name": self.name, "events": self.events}, indent=2, default=str))
        return str(p)

    @classmethod
    def load(cls, path) -> "AuditLog":
        from pathlib import Path as _P
        data = json.loads(_P(path).read_text())
        log = cls(name=data.get("name", "omni-audit"))
        log.events = data.get("events", [])
        log._prev = log.events[-1]["hash"] if log.events else "GENESIS"
        return log

    def stats(self) -> Dict[str, Any]:
        from collections import Counter as _C
        return {
            "name": self.name, "total": len(self.events),
            "by_kind": dict(_C(e["kind"] for e in self.events)),
            "head": self._prev[:12] if self._prev != "GENESIS" else "GENESIS",
            "verified": self.verify()["ok"],
        }


# --- markings (like Palantir markings) ---
def can_access(obj_markings: List[str], actor_clearance: List[str]) -> bool:
    """Actor must hold at least one of the object's markings (simple intersection)."""
    return bool(set(obj_markings) & set(actor_clearance))


def filter_by_markings(objects: List[Any], actor_clearance: List[str]) -> List[Any]:
    """Filter ontology objects / decisions by markings."""
    out = []
    for o in objects:
        mk = getattr(o, "markings", None)
        if mk is None and isinstance(o, dict):
            mk = o.get("markings", ["internal"])
        if can_access(list(mk or ["internal"]), actor_clearance):
            out.append(o)
    return out


# --- collectors: pipeline -> ontology -> workshop -> aip -> foundry ---
def ingest_pipeline_results(log: AuditLog, results, actor: str = "pipeline") -> int:
    n = 0
    for r in results or []:
        try:
            payload = {
                "stage": getattr(r.processing_stage, "value", str(r.processing_stage)),
                "bypassed": r.llm_bypassed,
                "audit": r.llm_decision_audit,
                "evidence": getattr(r, "evidence_steps", [])[:3],
            }
            markings = ["internal"]
            log.append("pipeline", getattr(r, "record_id", "unknown"), payload, actor=actor, markings=markings)
            n += 1
        except Exception:
            continue
    return n


def ingest_ontology_edits(log: AuditLog, ontology, actor: str = "ontology") -> int:
    n = 0
    for e in getattr(ontology, "_edits", [])[-500:]:
        try:
            ref = e.get("pk") or e.get("from") or e.get("id") or e.get("action") or "ontology"
            log.append("ontology", str(ref), dict(e), actor=actor)
            n += 1
        except Exception:
            continue
    return n


def ingest_workshop(log: AuditLog, app, actor: str = "workshop") -> int:
    n = 0
    for d in getattr(app, "decisions", {}).values():
        try:
            dd = d.to_dict() if hasattr(d, "to_dict") else dict(d)
            log.append("workshop", dd.get("id", "decision"), {"status": dd.get("status"), "object": dd.get("object_ref"), "history": dd.get("history", [])[-3:]}, actor=actor)
            n += 1
        except Exception:
            continue
    return n


def ingest_aip_runs(log: AuditLog, logic, actor: str = "aip") -> int:
    n = 0
    for r in getattr(logic, "runs", [])[-200:]:
        try:
            log.append("aip", r.get("logic", "logic"), {"answer": str(r.get("answer", ""))[:120], "citations": r.get("citations", [])[:3]}, actor=actor)
            n += 1
        except Exception:
            continue
    return n


def ingest_foundry_versions(log: AuditLog, datasets: List, actor: str = "foundry") -> int:
    n = 0
    for ds in datasets or []:
        try:
            for v in ds.versions()[-5:]:
                log.append("foundry", f"{ds.name}:{v['version']}", v, actor=actor)
                n += 1
        except Exception:
            continue
    return n
