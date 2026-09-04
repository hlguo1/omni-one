"""
Evidence — file:line citations helper (free, deterministic).
============================================================
Small extraction so packs + pipeline share one citation format.
"""
from __future__ import annotations

from typing import Any, Dict, List


def cite(source_file: str, line: int, snippet: str = "", max_len: int = 80) -> str:
    snippet = (snippet or "")[:max_len]
    return f"[{source_file}:{line}] {snippet}".strip()


def evidence_step(layer: str, signal: str, citation: str, detail: str = "") -> Dict[str, Any]:
    return {"layer": layer, "signal": signal, "citation": citation, "detail": detail}


__all__ = ["cite", "evidence_step"]
