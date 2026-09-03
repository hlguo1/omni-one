"""
Ontology — Free alternative to Palantir Ontology (digital twin)
==============================================================
Palantir Ontology costs ~$1M/yr. This is free, local, typed.

Concepts:
  ObjectType  — e.g., Supplier, Shipment, Patient, Transaction (like Palantir)
  Property    — typed field with lineage
  LinkType    — e.g., SUPPLIES, TREATS, SENT
  Object      — instance with id, properties, links
  Action      — state transition with checks (like Palantir Actions)

Storage: in-memory dict + optional Parquet backing via Foundry. No DB fees.
Graph: adjacency dict (no Neo4j fees). Queries are Python, free.
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
import hashlib
import json


def _coerce_value(ptype: str, value: Any) -> Any:
    """Strict-ish type coercion for ontology properties. Raises ValueError on mismatch. Free."""
    if value is None:
        return None
    t = (ptype or "string").lower()
    try:
        if t in ("string", "str"):
            return str(value)
        if t in ("double", "float", "number"):
            if isinstance(value, bool):
                raise ValueError("bool is not double")
            return float(value)
        if t in ("integer", "int", "long"):
            if isinstance(value, bool):
                raise ValueError("bool is not integer")
            # Allow "12.0" -> 12
            return int(float(str(value).strip()))
        if t in ("boolean", "bool"):
            if isinstance(value, bool):
                return value
            s = str(value).strip().lower()
            if s in ("true", "1", "yes", "y"):
                return True
            if s in ("false", "0", "no", "n"):
                return False
            raise ValueError(f"cannot coerce {value!r} to boolean")
        if t in ("timestamp", "datetime", "date"):
            from datetime import datetime as _dt
            if isinstance(value, _dt):
                return value.isoformat()
            s = str(value).strip()
            # Try ISO first
            try:
                iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
                dt = _dt.fromisoformat(iso)
                return dt.replace(tzinfo=None).isoformat() if dt.tzinfo else dt.isoformat()
            except Exception:
                pass
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    return _dt.strptime(s[:19], fmt).isoformat()
                except Exception:
                    continue
            raise ValueError(f"cannot coerce {value!r} to timestamp")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"coerce {value!r} to {ptype}: {e}")
    return value


class PropertyDef(BaseModel):
    name: str
    type: str = "string"  # string, double, integer, timestamp, boolean
    required: bool = False
    lineage: Optional[str] = None  # e.g., "foundry://suppliers.csv:column"

class ObjectTypeDef(BaseModel):
    api_name: str  # e.g., "Supplier"
    display_name: str
    primary_key: str
    properties: List[PropertyDef] = Field(default_factory=list)
    icon: str = "cube"
    # Palantir-like: title property for display
    title_property: Optional[str] = None
    # Governance: default markings for objects of this type
    default_markings: List[str] = Field(default_factory=lambda: ["internal"])

class LinkTypeDef(BaseModel):
    api_name: str  # e.g., "SUPPLIES"
    display_name: str
    from_type: str
    to_type: str
    cardinality: str = "MANY_TO_MANY"  # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY

class ObjectInstance(BaseModel):
    object_type: str
    primary_key: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    # Palantir-like: __ontology edges
    links: Dict[str, List[str]] = Field(default_factory=dict)  # linkType -> [targetPk ...]
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    lineage: Optional[str] = None  # which dataset/build produced it
    # Methodology: version + markings + validity (like Palantir time + markings)
    version: int = 1
    markings: List[str] = Field(default_factory=lambda: ["internal"])
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

    def title(self, type_def: Optional[ObjectTypeDef] = None) -> str:
        if type_def and type_def.title_property and type_def.title_property in self.properties:
            return str(self.properties[type_def.title_property])
        # Fallback to name/title property if present
        for k in ("name", "title"):
            if k in self.properties:
                return str(self.properties[k])
        return f"{self.object_type}:{self.primary_key}"

class ActionDef(BaseModel):
    api_name: str
    display_name: str
    object_type: str
    # What properties it changes, with checks
    parameters: List[PropertyDef] = Field(default_factory=list)
    # Simple checks: e.g., {"field": "status", "allowed": ["SHIPPED","DELAYED"]}
    checks: List[Dict[str, Any]] = Field(default_factory=list)
    # Methodology: approval workflow (like Palantir Actions with review)
    requires_approval: bool = False
    allowed_approvers: List[str] = Field(default_factory=list)


class Ontology:
    """
    In-memory Ontology. Free, no DB. Mirrors Palantir's central semantic layer.
    All writes are versioned via lineage string (like Foundry builds).
    """
    def __init__(self, name: str = "free-ontology"):
        self.name = name
        self.object_types: Dict[str, ObjectTypeDef] = {}
        self.link_types: Dict[str, LinkTypeDef] = {}
        self.actions: Dict[str, ActionDef] = {}
        self.objects: Dict[str, Dict[str, ObjectInstance]] = {}  # type -> pk -> obj
        self._edits: List[Dict[str, Any]] = []  # Palantir-like edit log
        self._history: Dict[str, List[Dict[str, Any]]] = {}  # "Type:pk" -> [snapshots]
        self._proposals: Dict[str, Dict[str, Any]] = {}  # proposal_id -> {action, pk, params, status}
        self._proposal_seq = 0
        self.created_at = datetime.now().isoformat()

    # --- internal ---
    def _snapshot(self, obj: ObjectInstance, op: str):
        key = f"{obj.object_type}:{obj.primary_key}"
        self._history.setdefault(key, []).append({
            "op": op, "version": obj.version, "at": datetime.now().isoformat(),
            "properties": dict(obj.properties), "links": {k: list(v) for k, v in obj.links.items()},
            "lineage": obj.lineage, "markings": list(obj.markings),
        })

    def history(self, object_type: str, pk: str) -> List[Dict[str, Any]]:
        return list(self._history.get(f"{object_type}:{pk}", []))

    # --- DDL ---
    def define_object_type(self, t: ObjectTypeDef):
        self.object_types[t.api_name] = t
        self.objects.setdefault(t.api_name, {})

    def define_link_type(self, lt: LinkTypeDef):
        # Validate from/to exist
        assert lt.from_type in self.object_types, f"from_type {lt.from_type} not defined"
        assert lt.to_type in self.object_types, f"to_type {lt.to_type} not defined"
        self.link_types[lt.api_name] = lt

    def define_action(self, a: ActionDef):
        assert a.object_type in self.object_types, f"object_type {a.object_type} not defined"
        self.actions[a.api_name] = a

    # --- DML (typed, versioned, cardinality-aware) ---
    def create_object(self, obj: ObjectInstance, lineage: Optional[str] = None):
        assert obj.object_type in self.object_types, f"unknown type {obj.object_type}"
        tdef = self.object_types[obj.object_type]
        # Coerce + validate properties against type defs
        coerced: Dict[str, Any] = {}
        prop_defs = {p.name: p for p in tdef.properties}
        for prop in tdef.properties:
            if prop.required and prop.name not in obj.properties:
                raise ValueError(f"missing required {prop.name} for {obj.object_type}")
        for k, v in obj.properties.items():
            if k in prop_defs:
                try:
                    coerced[k] = _coerce_value(prop_defs[k].type, v)
                except ValueError as e:
                    raise ValueError(f"{obj.object_type}.{k}: {e}")
            else:
                coerced[k] = v  # undeclared props allowed (flexible, like Palantir)
        obj.properties = coerced
        # Default markings from type if not set
        if not obj.markings or obj.markings == ["internal"]:
            try:
                if tdef.default_markings:
                    obj.markings = list(tdef.default_markings)
            except Exception:
                pass
        obj.version = 1
        obj.lineage = lineage or f"manual:{datetime.now().isoformat()}"
        obj.updated_at = datetime.now().isoformat()
        self.objects[obj.object_type][obj.primary_key] = obj
        self._snapshot(obj, "create")
        self._edits.append({"op": "create", "type": obj.object_type, "pk": obj.primary_key, "at": obj.updated_at, "lineage": obj.lineage})

    def bulk_create(self, objs: List[ObjectInstance], lineage: str):
        for o in objs:
            self.create_object(o, lineage=lineage)

    def _check_cardinality(self, lt: LinkTypeDef, from_obj: ObjectInstance, to_pk: str):
        """Enforce Palantir-like cardinality.
        ONE_TO_ONE: from single, to single.
        ONE_TO_MANY (one Supplier -> many Shipments): from multiple, to single.
        MANY_TO_ONE (many Tx -> one Account): from single, to multiple.
        MANY_TO_MANY: both multiple.
        """
        card = (lt.cardinality or "MANY_TO_MANY").upper()
        existing = from_obj.links.get(lt.api_name, [])
        if to_pk in existing:
            return  # idempotent
        if card in ("ONE_TO_ONE", "MANY_TO_ONE") and len(existing) >= 1:
            raise ValueError(f"Cardinality {card}: {lt.api_name} already has outgoing link from {from_obj.primary_key}")
        if card in ("ONE_TO_ONE", "ONE_TO_MANY"):
            for other_pk, other_obj in self.objects.get(lt.from_type, {}).items():
                if other_pk == from_obj.primary_key:
                    continue
                if to_pk in other_obj.links.get(lt.api_name, []):
                    raise ValueError(f"Cardinality {card}: {lt.to_type}:{to_pk} already linked from {other_pk}")

    def link(self, from_type: str, from_pk: str, link_type: str, to_pk: str):
        assert link_type in self.link_types, f"unknown link {link_type}"
        lt = self.link_types[link_type]
        assert from_type == lt.from_type
        assert from_pk in self.objects.get(from_type, {}), f"from {from_type}:{from_pk} not found"
        assert to_pk in self.objects.get(lt.to_type, {}), f"to {lt.to_type}:{to_pk} not found"
        from_obj = self.objects[from_type][from_pk]
        from_obj.links.setdefault(link_type, [])
        if to_pk in from_obj.links[link_type]:
            return
        self._check_cardinality(lt, from_obj, to_pk)
        from_obj.links[link_type].append(to_pk)
        from_obj.version += 1
        from_obj.updated_at = datetime.now().isoformat()
        self._snapshot(from_obj, f"link:{link_type}")
        self._edits.append({"op": "link", "from": f"{from_type}:{from_pk}", "link": link_type, "to": to_pk, "at": from_obj.updated_at})

    def _validate_action_params(self, adef: ActionDef, parameters: Dict[str, Any]):
        # Coerce declared params
        pdefs = {p.name: p for p in adef.parameters}
        for k, v in parameters.items():
            if k in pdefs:
                try:
                    parameters[k] = _coerce_value(pdefs[k].type, v)
                except ValueError as e:
                    raise ValueError(f"Action {adef.api_name} param {k}: {e}")
        for chk in adef.checks:
            field = chk.get("field")
            allowed = chk.get("allowed")
            if field and allowed is not None and parameters.get(field) not in allowed:
                raise ValueError(f"Action {adef.api_name} check failed: {field} must be in {allowed}")
            # Range check: {"field": "x", "min": 0, "max": 100}
            if field and ("min" in chk or "max" in chk) and field in parameters:
                try:
                    vv = float(parameters[field])
                    if "min" in chk and vv < float(chk["min"]):
                        raise ValueError(f"Action {adef.api_name} check failed: {field} < min {chk['min']}")
                    if "max" in chk and vv > float(chk["max"]):
                        raise ValueError(f"Action {adef.api_name} check failed: {field} > max {chk['max']}")
                except ValueError:
                    raise
                except Exception:
                    pass

    def apply_action(self, action_api: str, pk: str, parameters: Dict[str, Any], actor: str = "system") -> ObjectInstance:
        assert action_api in self.actions, f"unknown action {action_api}"
        adef = self.actions[action_api]
        if adef.requires_approval:
            raise ValueError(f"Action {action_api} requires approval: use propose_action/approve_action")
        if pk not in self.objects.get(adef.object_type, {}):
            raise KeyError(f"{adef.object_type}:{pk} not found")
        obj = self.objects[adef.object_type][pk]
        params = dict(parameters)
        self._validate_action_params(adef, params)
        for k, v in params.items():
            obj.properties[k] = v
        obj.version += 1
        obj.updated_at = datetime.now().isoformat()
        self._snapshot(obj, f"action:{action_api}")
        self._edits.append({"op": "action", "action": action_api, "pk": pk, "params": params, "actor": actor, "at": obj.updated_at, "version": obj.version})
        return obj

    # --- Approval workflow (methodology: human-in-the-loop, like Palantir Actions) ---
    def propose_action(self, action_api: str, pk: str, parameters: Dict[str, Any], proposer: str = "user") -> str:
        assert action_api in self.actions, f"unknown action {action_api}"
        adef = self.actions[action_api]
        params = dict(parameters)
        self._validate_action_params(adef, params)  # validate early, apply on approve
        self._proposal_seq += 1
        pid = f"P-{self._proposal_seq:04d}"
        self._proposals[pid] = {
            "id": pid, "action": action_api, "pk": pk, "params": params,
            "proposer": proposer, "status": "pending" if adef.requires_approval else "auto-approved",
            "at": datetime.now().isoformat(),
        }
        self._edits.append({"op": "propose", "id": pid, "action": action_api, "pk": pk})
        # Auto-apply if no approval required (keeps old behavior)
        if not adef.requires_approval:
            self.apply_action_direct(pid, actor=proposer)
        return pid

    def apply_action_direct(self, proposal_id: str, actor: str = "system") -> ObjectInstance:
        """Apply a proposal bypassing approval (for auto-approved or admin)."""
        p = self._proposals.get(proposal_id)
        if not p:
            raise KeyError(f"proposal {proposal_id} not found")
        if p["status"] not in ("pending", "auto-approved", "approved"):
            raise ValueError(f"proposal {proposal_id} status {p['status']} cannot apply")
        adef = self.actions[p["action"]]
        obj = self.objects[adef.object_type][p["pk"]]
        for k, v in p["params"].items():
            obj.properties[k] = v
        obj.version += 1
        obj.updated_at = datetime.now().isoformat()
        p["status"] = "applied"
        p["applied_at"] = obj.updated_at
        self._snapshot(obj, f"action:{p['action']}:{proposal_id}")
        self._edits.append({"op": "action", "action": p["action"], "pk": p["pk"], "params": p["params"], "actor": actor, "proposal": proposal_id, "at": obj.updated_at})
        return obj

    def approve_action(self, proposal_id: str, approver: str) -> ObjectInstance:
        p = self._proposals.get(proposal_id)
        if not p:
            raise KeyError(f"proposal {proposal_id} not found")
        adef = self.actions[p["action"]]
        if adef.allowed_approvers and approver not in adef.allowed_approvers:
            raise ValueError(f"approver {approver} not allowed for {p['action']}")
        if p["status"] != "pending":
            raise ValueError(f"proposal {proposal_id} not pending ({p['status']})")
        p["status"] = "approved"
        p["approver"] = approver
        return self.apply_action_direct(proposal_id, actor=approver)

    def reject_action(self, proposal_id: str, approver: str, reason: str = ""):
        p = self._proposals.get(proposal_id)
        if not p:
            raise KeyError(proposal_id)
        p["status"] = "rejected"
        p["approver"] = approver
        p["reason"] = reason
        self._edits.append({"op": "reject", "id": proposal_id, "by": approver})

    # --- Queries (free, no Spark) ---
    def search(self, object_type: str, where: Optional[Dict[str, Any]] = None, allowed_markings: Optional[List[str]] = None) -> List[ObjectInstance]:
        """where: {"status": "DELAYED"} exact match + operators {"delay_hours": {">": 24}}. Markings-filtered."""
        all_objs = list(self.objects.get(object_type, {}).values())
        if allowed_markings is not None:
            allowed = set(allowed_markings)
            all_objs = [o for o in all_objs if set(o.markings) & allowed]
        if not where:
            return all_objs
        out = []
        for o in all_objs:
            ok = True
            for k, v in where.items():
                pv = o.properties.get(k)
                # Operator dict: {">": 24, "<=": 100, "in": [...]}
                if isinstance(v, dict):
                    for op, ov in v.items():
                        try:
                            if op == ">":
                                if not (pv is not None and float(pv) > float(ov)): ok = False
                            elif op == ">=":
                                if not (pv is not None and float(pv) >= float(ov)): ok = False
                            elif op == "<":
                                if not (pv is not None and float(pv) < float(ov)): ok = False
                            elif op == "<=":
                                if not (pv is not None and float(pv) <= float(ov)): ok = False
                            elif op in ("in", "IN"):
                                if pv not in ov: ok = False
                            elif op in ("contains",):
                                if str(ov).lower() not in str(pv or "").lower(): ok = False
                            else:
                                if pv != ov: ok = False
                        except Exception:
                            ok = False
                        if not ok:
                            break
                else:
                    if pv != v:
                        ok = False
                if not ok:
                    break
            if ok:
                out.append(o)
        return out

    def get(self, object_type: str, pk: str, allowed_markings: Optional[List[str]] = None) -> Optional[ObjectInstance]:
        obj = self.objects.get(object_type, {}).get(pk)
        if obj is None or allowed_markings is None:
            return obj
        if set(obj.markings) & set(allowed_markings):
            return obj
        return None  # hidden by markings (like Palantir)

    def traverse(self, start_type: str, start_pk: str, link_type: str, depth: int = 1) -> List[ObjectInstance]:
        """BFS traverse links, like Gotham graph expansion. Free."""
        assert link_type in self.link_types
        lt = self.link_types[link_type]
        visited: Set[str] = set()
        frontier = [(start_type, start_pk, 0)]
        result: List[ObjectInstance] = []
        while frontier:
            cur_type, cur_pk, d = frontier.pop(0)
            key = f"{cur_type}:{cur_pk}"
            if key in visited or d > depth:
                continue
            visited.add(key)
            obj = self.get(cur_type, cur_pk)
            if not obj:
                continue
            if d > 0:
                result.append(obj)
            if d < depth:
                for tgt_pk in obj.links.get(link_type, []):
                    frontier.append((lt.to_type, tgt_pk, d + 1))
        return result

    def stats(self) -> Dict[str, Any]:
        return {
            "ontology": self.name,
            "object_types": list(self.object_types.keys()),
            "link_types": list(self.link_types.keys()),
            "actions": list(self.actions.keys()),
            "counts": {t: len(objs) for t, objs in self.objects.items()},
            "edits": len(self._edits),
            "proposals": len(self._proposals),
            "history_entries": sum(len(v) for v in self._history.values()),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "object_types": {k: v.model_dump() for k, v in self.object_types.items()},
            "link_types": {k: v.model_dump() for k, v in self.link_types.items()},
            "actions": {k: v.model_dump() for k, v in self.actions.items()},
            "objects": {t: {pk: o.model_dump() for pk, o in objs.items()} for t, objs in self.objects.items()},
            "edits": self._edits[-200:],
            "proposals": self._proposals,
        }

    def lineage_hash(self) -> str:
        # Hash types + objects only (not volatile edit timestamps) for stable lineage
        payload = {
            "types": {k: v.model_dump() for k, v in self.object_types.items()},
            "objects": {t: {pk: {"p": o.properties, "v": o.version} for pk, o in objs.items()} for t, objs in self.objects.items()},
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]

    # --- Persistence (free: JSON dir, includes edits/proposals for audit parity) ---
    def save(self, path) -> str:
        """Save ontology to directory (types/links/actions/objects/history/edits). Free."""
        from pathlib import Path as _P
        p = _P(path)
        p.mkdir(parents=True, exist_ok=True)
        (p / "types.json").write_text(json.dumps({k: v.model_dump() for k, v in self.object_types.items()}, indent=2))
        (p / "links.json").write_text(json.dumps({k: v.model_dump() for k, v in self.link_types.items()}, indent=2))
        (p / "actions.json").write_text(json.dumps({k: v.model_dump() for k, v in self.actions.items()}, indent=2))
        (p / "objects.json").write_text(json.dumps({t: {pk: o.model_dump() for pk, o in objs.items()} for t, objs in self.objects.items()}, indent=2, default=str))
        (p / "history.json").write_text(json.dumps(self._history, indent=2, default=str))
        (p / "edits.json").write_text(json.dumps(self._edits[-1000:], indent=2, default=str))
        (p / "proposals.json").write_text(json.dumps(self._proposals, indent=2, default=str))
        (p / "meta.json").write_text(json.dumps({"name": self.name, "created_at": self.created_at, "hash": self.lineage_hash(), "proposal_seq": self._proposal_seq}, indent=2))
        return str(p)

    @classmethod
    def load(cls, path) -> "Ontology":
        from pathlib import Path as _P
        p = _P(path)
        meta = json.loads((p / "meta.json").read_text())
        onto = cls(name=meta.get("name", "free-ontology"))
        for k, v in json.loads((p / "types.json").read_text()).items():
            onto.define_object_type(ObjectTypeDef(**v))
        if (p / "links.json").exists():
            for k, v in json.loads((p / "links.json").read_text()).items():
                try:
                    onto.define_link_type(LinkTypeDef(**v))
                except Exception:
                    pass
        if (p / "actions.json").exists():
            for k, v in json.loads((p / "actions.json").read_text()).items():
                onto.actions[k] = ActionDef(**v)
        objs = json.loads((p / "objects.json").read_text())
        for t, mp in objs.items():
            for pk, od in mp.items():
                onto.objects.setdefault(t, {})[pk] = ObjectInstance(**od)
        if (p / "history.json").exists():
            onto._history = json.loads((p / "history.json").read_text())
        if (p / "edits.json").exists():
            onto._edits = json.loads((p / "edits.json").read_text())
        if (p / "proposals.json").exists():
            onto._proposals = json.loads((p / "proposals.json").read_text())
        onto._proposal_seq = int(meta.get("proposal_seq", len(onto._proposals)))
        return onto
