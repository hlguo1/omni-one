"""
Cost ledger — persisted LLM/$ accounting (free, local-first).
=============================================================
Extracted from data_processing_pipeline god-file so briefing cost
is auditable + restart-safe. Pipeline keeps re-exporting these.

Backend: infra.store LocalStore (DuckDB if available, else JSONL). $0.
Default budget: $0.00 (mock only) unless SELLER_MAX_LLM_USD explicitly raised.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional


def _get_store():
    try:
        from ..infra.store import get_store as _gs
    except Exception:
        try:
            from omni_one.infra.store import get_store as _gs  # type: ignore
        except Exception:
            return None
    try:
        return _gs()
    except Exception:
        return None


def record_cost(label: str, amount_usd: float, meta: Optional[Dict[str, Any]] = None) -> int:
    """Append cost entry. Returns seq. Never raises (free path must not break briefing)."""
    try:
        store = _get_store()
        if store is not None:
            return int(store.ledger_append(label, float(amount_usd), meta or {}))
    except Exception:
        pass
    return 0


def total_cost() -> float:
    try:
        store = _get_store()
        if store is not None:
            return float(store.ledger_total())
    except Exception:
        pass
    return 0.0


def budget_ok(per_briefing_cap_usd: Optional[float] = None) -> bool:
    """True if total spend is within cap. Default cap from env SELLER_MAX_LLM_USD or 0.0."""
    cap = per_briefing_cap_usd
    if cap is None:
        try:
            cap = float(os.getenv("SELLER_MAX_LLM_USD", "0.0"))
        except Exception:
            cap = 0.0
    try:
        return total_cost() <= float(cap) + 1e-9
    except Exception:
        return True


def seller_llm_mode() -> str:
    """mock (default $0) | ollama | google. Env SELLER_LLM."""
    return (os.getenv("SELLER_LLM") or "mock").strip().lower()


def should_use_live_llm() -> bool:
    """Live LLM only if mode != mock AND a key/daemon is explicitly present."""
    mode = seller_llm_mode()
    if mode == "mock":
        return False
    if mode == "google":
        return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    if mode == "ollama":
        # Ollama daemon opt-in; pipeline will degrade to mock if unreachable
        return True
    return False


__all__ = ["record_cost", "total_cost", "budget_ok", "seller_llm_mode", "should_use_live_llm"]
