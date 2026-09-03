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

class LinkTypeDef(BaseModel):
    api_name: str  # e.g., "SUPPLIES"
    display_name: str
    from_type: str
    to_type: str
    cardinality: str = "MANY_TO_MANY"  # ONE_TO_ONE, etc.
    # Free: no need for foreign key constraints, just logical

class ObjectInstance(BaseModel):
    object_type: str
    primary_key: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    # Palantir-like: __ontology edges
    links: Dict[str, List[str]] = Field(default_factory=dict)  # linkType -> [targetPk ...]
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    lineage: Optional[str] = None  # which dataset/build produced it

    def title(self, type_def: Optional[ObjectTypeDef] = None) -> str:
        if type_def and type_def.title_property and type_def.title_property in self.properties:
            return str(self.properties[type_def.title_property])
        return f"{self.object_type}:{self.primary_key}"

class ActionDef(BaseModel):
    api_name: str
    display_name: str
    object_type: str
    # What properties it changes, with checks
    parameters: List[PropertyDef] = Field(default_factory=list)
    # Simple checks: e.g., {"field": "status", "allowed": ["SHIPPED","DELAYED"]}
    checks: List[Dict[str, Any]] = Field(default_factory=list)


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
        self.created_at = datetime.now().isoformat()

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

    # --- DML ---
    def create_object(self, obj: ObjectInstance, lineage: Optional[str] = None):
        assert obj.object_type in self.object_types, f"unknown type {obj.object_type}"
        # Validate required props
        tdef = self.object_types[obj.object_type]
        for prop in tdef.properties:
            if prop.required and prop.name not in obj.properties:
                raise ValueError(f"missing required {prop.name} for {obj.object_type}")
        obj.lineage = lineage or f"manual:{datetime.now().isoformat()}"
        self.objects[obj.object_type][obj.primary_key] = obj
        self._edits.append({"op": "create", "type": obj.object_type, "pk": obj.primary_key, "at": obj.updated_at})

    def bulk_create(self, objs: List[ObjectInstance], lineage: str):
        for o in objs:
            self.create_object(o, lineage=lineage)

    def link(self, from_type: str, from_pk: str, link_type: str, to_pk: str):
        assert link_type in self.link_types, f"unknown link {link_type}"
        lt = self.link_types[link_type]
        assert from_type == lt.from_type
        # Check objects exist (soft check, free)
        assert from_pk in self.objects.get(from_type, {}), f"from {from_type}:{from_pk} not found"
        assert to_pk in self.objects.get(lt.to_type, {}), f"to {lt.to_type}:{to_pk} not found"
        from_obj = self.objects[from_type][from_pk]
        from_obj.links.setdefault(link_type, [])
        if to_pk not in from_obj.links[link_type]:
            from_obj.links[link_type].append(to_pk)
            from_obj.updated_at = datetime.now().isoformat()
            self._edits.append({"op": "link", "from": f"{from_type}:{from_pk}", "link": link_type, "to": to_pk})

    def apply_action(self, action_api: str, pk: str, parameters: Dict[str, Any]) -> ObjectInstance:
        assert action_api in self.actions, f"unknown action {action_api}"
        adef = self.actions[action_api]
        obj = self.objects[adef.object_type][pk]
        # Checks (free, deterministic)
        for chk in adef.checks:
            field = chk.get("field")
            allowed = chk.get("allowed")
            if field and allowed and parameters.get(field) not in allowed:
                raise ValueError(f"Action {action_api} check failed: {field} must be in {allowed}")
        # Apply
        for k, v in parameters.items():
            obj.properties[k] = v
        obj.updated_at = datetime.now().isoformat()
        self._edits.append({"op": "action", "action": action_api, "pk": pk, "params": parameters})
        return obj

    # --- Queries (free, no Spark) ---
    def search(self, object_type: str, where: Optional[Dict[str, Any]] = None) -> List[ObjectInstance]:
        """where: {"status": "DELAYED"} exact match, free."""
        all_objs = list(self.objects.get(object_type, {}).values())
        if not where:
            return all_objs
        out = []
        for o in all_objs:
            match = all(o.properties.get(k) == v for k, v in where.items())
            if match:
                out.append(o)
        return out

    def get(self, object_type: str, pk: str) -> Optional[ObjectInstance]:
        return self.objects.get(object_type, {}).get(pk)

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
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "object_types": {k: v.model_dump() for k, v in self.object_types.items()},
            "link_types": {k: v.model_dump() for k, v in self.link_types.items()},
            "actions": {k: v.model_dump() for k, v in self.actions.items()},
            "objects": {t: {pk: o.model_dump() for pk, o in objs.items()} for t, objs in self.objects.items()},
        }

    def lineage_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]
