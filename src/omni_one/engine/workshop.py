"""
Workshop — Free operational apps on the Ontology (methodology like Palantir Workshop)
=====================================================================================
Palantir Workshop: operators work a queue of ontology-backed decisions, take Actions,
everything audited. We don't replicate their UI — same methodology, free:

  Queue built FROM ontology (not from raw tables) → each Decision cites Type:pk +
  pipeline evidence → operator assigns/approves → writeback via Ontology Actions
  (with approval workflow) → Governance audit log captures all.

This is the "suite surrounding core tech": Foundry feeds Ontology, Workshop acts on it,
Gotham investigates it, AIP drafts for it, Apollo ships it.

Free: stdlib only. No fees.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
import hashlib
import json
import threading

from .ontology import Ontology


class Decision:
    def __init__(self, id: str, title: str, object_ref: str, severity: str = "medium",
                 status: str = "open", evidence: Optional[List[str]] = None,
                 proposed_action: Optional[Dict[str, Any]] = None,
                 assignee: Optional[str] = None, source: str = "manual"):
        self.id = id
        self.title = title
        self.object_ref = object_ref  # "Type:pk" — must exist in ontology (grounded)
        self.severity = severity  # low/medium/high/critical
        self.status = status  # open/assigned/approved/resolved/rejected
        self.evidence = evidence or []
        self.proposed_action = proposed_action  # {"action": api, "params": {...}}
        self.assignee = assignee
        self.source = source
        self.history: List[Dict[str, Any]] = [{"op": "created", "at": datetime.now().isoformat(), "source": source}]
        self.proposal_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "object_ref": self.object_ref,
            "severity": self.severity, "status": self.status, "evidence": self.evidence,
            "proposed_action": self.proposed_action, "assignee": self.assignee,
            "source": self.source, "history": self.history, "proposal_id": self.proposal_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Decision":
        obj = cls(d["id"], d["title"], d["object_ref"], d.get("severity", "medium"),
                  d.get("status", "open"), d.get("evidence", []), d.get("proposed_action"),
                  d.get("assignee"), d.get("source", "manual"))
        obj.history = d.get("history", [])
        obj.proposal_id = d.get("proposal_id")
        return obj


class WorkshopApp:
    """Operational app runtime. One app = one queue (e.g., 'seller-daily', 'supply-exceptions')."""

    def __init__(self, ontology: Ontology, name: str = "workshop"):
        self.ontology = ontology
        self.name = name
        self._lock = threading.RLock()
        self.decisions: Dict[str, Decision] = {}
        self._seq = 0
        self.created_at = datetime.now().isoformat()

    # --- builders (methodology: queue FROM ontology, not raw) ---
    def _next_id(self, prefix: str = "D") -> str:
        with self._lock:
            self._seq += 1
            return f"{prefix}-{self._seq:04d}"

    def add_decision(self, title: str, object_ref: str, severity: str = "medium",
                     evidence: Optional[List[str]] = None,
                     proposed_action: Optional[Dict[str, Any]] = None,
                     source: str = "manual", stable_id: Optional[str] = None) -> Decision:
        # Grounding check: object must exist (like Palantir — no phantom decisions)
        try:
            t, pk = object_ref.split(":", 1)
        except ValueError:
            raise ValueError(f"object_ref must be Type:pk, got {object_ref!r}")
        if not self.ontology.get(t, pk):
            raise ValueError(f"Decision object {object_ref} not in ontology (grounding failed)")
        # Idempotent upsert: stable_id reuses existing decision (tech sound)
        with self._lock:
            if stable_id and stable_id in self.decisions:
                existing = self.decisions[stable_id]
                # Refresh evidence/title if changed (keep status/history)
                existing.title = title
                existing.evidence = evidence or existing.evidence
                existing.proposed_action = proposed_action or existing.proposed_action
                existing.history.append({"op": "upserted", "at": datetime.now().isoformat(), "source": source})
                return existing
        did = stable_id or self._next_id()
        d = Decision(did, title, object_ref, severity, "open", evidence, proposed_action, None, source)
        with self._lock:
            # double-check after id generation (race-safe)
            if did in self.decisions:
                return self.decisions[did]
            self.decisions[d.id] = d
        return d

    def build_from_search(self, object_type: str, where: Dict[str, Any],
                          title_fn, severity: str = "medium",
                          action_fn=None, source: str = "search") -> List[Decision]:
        """Generic builder: ontology search -> decisions. Used by all highlights."""
        out = []
        for obj in self.ontology.search(object_type, where=where):
            ref = f"{object_type}:{obj.primary_key}"
            title = title_fn(obj) if callable(title_fn) else str(title_fn)
            evidence = [f"ontology:{ref}.{k}={v}" for k, v in (where or {}).items()]
            # Enrich with lineage
            if obj.lineage:
                evidence.append(f"lineage:{obj.lineage}")
            proposed = action_fn(obj) if callable(action_fn) else None
            out.append(self.add_decision(title, ref, severity, evidence, proposed, source))
        return out

    def build_seller_queue(self, briefing: Dict[str, Any]) -> List[Decision]:
        """Seller OS highlight -> Workshop queue (methodology demo). Requires Seller ontology loaded."""
        out = []
        # Stockout risks
        for r in briefing.get("stockout_risk", []):
            prod = r.get("product", "unknown")
            # Find ontology Product object by fuzzy title (best-effort)
            ref = self._find_product_ref(prod)
            if not ref:
                continue
            out.append(self.add_decision(
                f"Reorder {prod} — {r.get('days_supply')} days left",
                ref, "high", [r.get("citation", "")],
                {"action": "reorderProduct", "params": {"status": "REORDERED"}},
                source="seller_os",
            ))
        # At-risk customers
        for c in briefing.get("at_risk_preview", []):
            # Customer objects may not exist — link to Product best-effort or skip if ungrounded
            # Methodology: no phantom decisions, so attach to best seller product
            best = (briefing.get("kpis", {}).get("best_seller", {}) or {}).get("product")
            ref = self._find_product_ref(best) if best else None
            if not ref and self.ontology.objects.get("Product"):
                # Fallback to first product
                first_pk = next(iter(self.ontology.objects["Product"]), None)
                ref = f"Product:{first_pk}" if first_pk else None
            if not ref:
                continue
            out.append(self.add_decision(
                f"Win back customer — {c.get('text','')[:50]}",
                ref, "high", [c.get("citation", "")],
                {"action": "messageCustomer", "params": {"status": "CONTACTED"}},
                source="seller_os",
            ))
        return out

    def _find_product_ref(self, product_name: Optional[str]) -> Optional[str]:
        if not product_name or "Product" not in self.ontology.objects:
            return None
        # Exact then fuzzy
        for pk, obj in self.ontology.objects["Product"].items():
            title = obj.properties.get("name") or obj.properties.get("title") or pk
            if str(title).lower() == str(product_name).lower():
                return f"Product:{pk}"
        from difflib import SequenceMatcher as _SM
        best, best_score = None, 0.0
        for pk, obj in self.ontology.objects["Product"].items():
            title = str(obj.properties.get("name") or obj.properties.get("title") or pk)
            s = _SM(None, title.lower(), str(product_name).lower()).ratio()
            if s > best_score:
                best, best_score = f"Product:{pk}", s
        return best if best_score >= 0.6 else None

    # --- operations (methodology: assign -> approve -> resolve, all audited) ---
    def assign(self, decision_id: str, assignee: str, actor: str = "lead") -> Decision:
        d = self._get(decision_id)
        d.assignee = assignee
        d.status = "assigned"
        d.history.append({"op": "assigned", "to": assignee, "by": actor, "at": datetime.now().isoformat()})
        return d

    def approve(self, decision_id: str, approver: str) -> Decision:
        """Approve proposed action via Ontology approval workflow (human-in-the-loop)."""
        d = self._get(decision_id)
        if not d.proposed_action:
            raise ValueError(f"Decision {decision_id} has no proposed_action")
        action_api = d.proposed_action["action"]
        params = d.proposed_action.get("params", {})
        # Propose + approve through ontology (respects requires_approval)
        t, pk = d.object_ref.split(":", 1)
        # Map decision object to action object if types differ (e.g., decision on Product, action on Product)
        # For simplicity, action must target same type; else apply directly to decision object if action type matches
        adef = self.ontology.actions.get(action_api)
        if adef is None:
            raise ValueError(f"Unknown action {action_api}")
        target_pk = pk if adef.object_type == t else None
        if target_pk is None:
            # Try to find linked object of action type (one hop)
            target_pk = self._resolve_action_target(d, adef.object_type)
        if target_pk is None:
            raise ValueError(f"Cannot resolve action target {adef.object_type} from {d.object_ref}")
        pid = self.ontology.propose_action(action_api, target_pk, params, proposer=d.assignee or approver)
        # If auto-approved, it's already applied; else approve
        prop = self.ontology._proposals.get(pid, {})
        if prop.get("status") == "pending":
            self.ontology.approve_action(pid, approver)
        d.proposal_id = pid
        d.status = "approved"
        d.history.append({"op": "approved", "by": approver, "proposal": pid, "at": datetime.now().isoformat()})
        return d

    def resolve(self, decision_id: str, actor: str, note: str = "") -> Decision:
        d = self._get(decision_id)
        d.status = "resolved"
        d.history.append({"op": "resolved", "by": actor, "note": note, "at": datetime.now().isoformat()})
        return d

    def reject(self, decision_id: str, actor: str, reason: str = "") -> Decision:
        d = self._get(decision_id)
        d.status = "rejected"
        d.history.append({"op": "rejected", "by": actor, "reason": reason, "at": datetime.now().isoformat()})
        return d

    def _resolve_action_target(self, d: Decision, target_type: str) -> Optional[str]:
        # One-hop link resolution: decision object -> linked target_type
        try:
            t, pk = d.object_ref.split(":", 1)
            obj = self.ontology.get(t, pk)
            if not obj:
                return None
            for lt_name, targets in obj.links.items():
                lt = self.ontology.link_types.get(lt_name)
                if lt and lt.to_type == target_type and targets:
                    return targets[0]
        except Exception:
            pass
        return None

    def _get(self, decision_id: str) -> Decision:
        if decision_id not in self.decisions:
            raise KeyError(decision_id)
        return self.decisions[decision_id]

    def list(self, status: Optional[str] = None, severity: Optional[str] = None) -> List[Decision]:
        out = list(self.decisions.values())
        if status:
            out = [d for d in out if d.status == status]
        if severity:
            out = [d for d in out if d.severity == severity]
        # Critical first, then high/medium/low
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(out, key=lambda d: order.get(d.severity, 9))

    def stats(self) -> Dict[str, Any]:
        from collections import Counter as _C
        return {
            "app": self.name,
            "total": len(self.decisions),
            "by_status": dict(_C(d.status for d in self.decisions.values())),
            "by_severity": dict(_C(d.severity for d in self.decisions.values())),
            "ontology_hash": self.ontology.lineage_hash(),
        }

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {"app": self.name, "decisions": {k: v.to_dict() for k, v in self.decisions.items()}}

    def persist_to_store(self, store=None) -> str:
        try:
            if store is None:
                try:
                    from ..infra.store import get_store as _gs
                except Exception:
                    from omni_one.infra.store import get_store as _gs  # type: ignore
                store = _gs()
            store.workshop_save({k: v.to_dict() for k, v in self.decisions.items()})
            return getattr(store, "backend", "unknown")
        except Exception as e:
            raise RuntimeError(f"workshop persist failed: {e}")

    def load_from_store(self, store=None) -> int:
        try:
            if store is None:
                try:
                    from ..infra.store import get_store as _gs
                except Exception:
                    from omni_one.infra.store import get_store as _gs  # type: ignore
                store = _gs()
            blob = store.workshop_load()
        except Exception:
            return 0
        n = 0
        with self._lock:
            for did, d in blob.items():
                try:
                    # Only load if grounded (object exists) — skip phantoms
                    ref = str(d.get("object_ref", ""))
                    if ":" in ref:
                        t, pk = ref.split(":", 1)
                        if not self.ontology.get(t, pk):
                            continue
                    self.decisions[did] = Decision.from_dict(d)
                    n += 1
                except Exception:
                    continue
        return n

    def queue_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]
