"""
Gotham — Free alternative to Palantir Gotham (investigation graph)
===============================================================
Palantir Gotham: $10M+ for intel, entity resolution, link analysis.
Free alternative: ontology traversal + simple entity resolution (deterministic), no fees.

Mirrors:
  Object search (Gotham Object Explorer) → ontology.search()
  Graph expansion (Gotham Graph) → ontology.traverse()
  Entity resolution (Gotham Resolve) → deterministic blocking + Levenshtein (free)

Tech: Python only, no GraphDB fees. Deterministic, explainable.

Use case: upload transactions + chat logs + photos → find fraud ring or intel cell.
"""
from __future__ import annotations
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict, deque
import re
from difflib import SequenceMatcher

from .ontology import Ontology, ObjectInstance


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def entity_resolution_candidates(objects: List[ObjectInstance], threshold: float = 0.85) -> List[Tuple[str, str, float]]:
    """
    Free entity resolution. Compares title/primary properties via SequenceMatcher.
    Like Gotham Resolve but deterministic, free.
    Returns [(pk1, pk2, score), ...] where score >= threshold.
    """
    # Blocking: first letter to reduce O(n^2) — free optimization
    blocks: Dict[str, List[ObjectInstance]] = defaultdict(list)
    for o in objects:
        # Use first char of title or pk
        title = str(o.properties.get("name") or o.properties.get("title") or o.primary_key)
        key = _norm(title)[:2] or "zz"
        blocks[key[:1]].append(o)
    candidates: List[Tuple[str, str, float]] = []
    for bucket in blocks.values():
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                a = bucket[i]
                b = bucket[j]
                # Compare names
                name_a = str(a.properties.get("name") or a.properties.get("title") or a.primary_key)
                name_b = str(b.properties.get("name") or b.properties.get("title") or b.primary_key)
                score = SequenceMatcher(None, _norm(name_a), _norm(name_b)).ratio()
                # Also compare other fields if both have phone/email
                if "phone" in a.properties and "phone" in b.properties:
                    if _norm(str(a.properties["phone"])) == _norm(str(b.properties["phone"])) and a.properties["phone"]:
                        score = max(score, 0.95)
                if score >= threshold:
                    candidates.append((a.primary_key, b.primary_key, round(score, 3)))
    return sorted(candidates, key=lambda x: x[2], reverse=True)


class Investigation:
    """
    Free Gotham-like investigation. Holds a working set (like Gotham's dossier)
    and supports graph expansion, path finding, and timeline.
    """
    def __init__(self, ontology: Ontology, name: str = "investigation"):
        self.ontology = ontology
        self.name = name
        self.working_set: Set[str] = set()  # "Type:pk"
        self.events: List[Dict[str, Any]] = []

    def add(self, object_type: str, pk: str):
        key = f"{object_type}:{pk}"
        if self.ontology.get(object_type, pk):
            self.working_set.add(key)
            self.events.append({"op": "add", "key": key})

    def expand(self, link_type: str, depth: int = 1) -> int:
        """Expand all working_set objects via link_type, like Gotham graph expand."""
        new_keys: Set[str] = set()
        for key in list(self.working_set):
            t, pk = key.split(":", 1)
            neighbors = self.ontology.traverse(t, pk, link_type, depth=depth)
            for nb in neighbors:
                new_keys.add(f"{nb.object_type}:{nb.primary_key}")
        before = len(self.working_set)
        self.working_set |= new_keys
        self.events.append({"op": "expand", "link": link_type, "depth": depth, "added": len(new_keys)})
        return len(self.working_set) - before

    def find_path(self, from_key: str, to_key: str, max_depth: int = 4) -> List[str] | None:
        """BFS path between two objects across any link types, free."""
        # Build adjacency from ontology links
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for t, objs in self.ontology.objects.items():
            for pk, obj in objs.items():
                src = f"{t}:{pk}"
                for lt, targets in obj.links.items():
                    lt_def = self.ontology.link_types.get(lt)
                    if not lt_def:
                        continue
                    for tgt_pk in targets:
                        dst = f"{lt_def.to_type}:{tgt_pk}"
                        adjacency[src].add(dst)
                        adjacency[dst].add(src)  # undirected for investigation
        # BFS
        queue = deque([[from_key]])
        visited = {from_key}
        while queue:
            path = queue.popleft()
            cur = path[-1]
            if cur == to_key:
                return path
            if len(path) > max_depth:
                continue
            for nb in adjacency.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(path + [nb])
        return None

    def timeline(self) -> List[Dict[str, Any]]:
        """Sort working_set objects by timestamp property, like Gotham timeline."""
        objs: List[Dict[str, Any]] = []
        for key in self.working_set:
            t, pk = key.split(":", 1)
            obj = self.ontology.get(t, pk)
            if not obj:
                continue
            ts = obj.properties.get("timestamp") or obj.properties.get("date") or obj.updated_at
            objs.append({"key": key, "timestamp": str(ts), "type": t, "title": obj.title(self.ontology.object_types.get(t))})
        return sorted(objs, key=lambda x: x["timestamp"])

    def summary(self) -> Dict[str, Any]:
        by_type = defaultdict(int)
        for key in self.working_set:
            t = key.split(":", 1)[0]
            by_type[t] += 1
        return {
            "investigation": self.name,
            "working_set_size": len(self.working_set),
            "by_type": dict(by_type),
            "events": self.events[-5:],
            "free": True,
        }
