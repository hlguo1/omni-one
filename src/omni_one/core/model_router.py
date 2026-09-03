"""
ModelRouter — budget & latency aware, deterministic fallback chain.

See docs/STRATEGY.md Pillar 1: cost/latency/quality frontier.
- Each model has cost_per_mtok, latency_p95_ms, quality_score, max_context.
- select() returns ModelSelection (core/types.py) with fallback_chain.
- estimate_cost() uses tiktoken if available else char heuristic.
- generate() supports injected mock for tests via model="mock/..." .
"""
import os
import time
from typing import Dict, Any, List, Optional, Tuple
import logging

try:
    import litellm  # type: ignore
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    litellm = None  # type: ignore

try:
    import tiktoken  # type: ignore
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

try:
    from .types import ModelSelection  # type: ignore
except (ImportError, ValueError):
    try:
        from omni_one.core.types import ModelSelection  # type: ignore
    except (ImportError, ValueError):
        import importlib.util as _ilu, pathlib as _pl
        _spec = _ilu.spec_from_file_location("omni_one_core_types", _pl.Path(__file__).parent / "types.py")
        _mod = _ilu.module_from_spec(_spec)  # type: ignore
        assert _spec and _spec.loader
        _spec.loader.exec_module(_mod)  # type: ignore
        ModelSelection = _mod.ModelSelection  # type: ignore

logger = logging.getLogger(__name__)


MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "fast": {
        "model": "gemini/gemini-1.5-flash",
        "cost_per_mtok": 0.075,   # $ per 1M tokens (input+output blended, approx)
        "latency_p95_ms": 120,
        "quality_score": 0.68,
        "max_context_tokens": 1_000_000,
        "provider": "google",
    },
    "fast-mini": {
        "model": "gemini/gemini-1.5-flash-8b",
        "cost_per_mtok": 0.03,
        "latency_p95_ms": 90,
        "quality_score": 0.62,
        "max_context_tokens": 1_000_000,
        "provider": "google",
    },
    "balanced": {
        "model": "gemini/gemini-2.5-flash",
        "cost_per_mtok": 0.15,
        "latency_p95_ms": 250,
        "quality_score": 0.84,
        "max_context_tokens": 1_000_000,
        "provider": "google",
    },
    "reasoning": {
        "model": "gemini/gemini-1.5-pro",
        "cost_per_mtok": 1.25,
        "latency_p95_ms": 600,
        "quality_score": 0.91,
        "max_context_tokens": 2_000_000,
        "provider": "google",
    },
    "premium": {
        "model": "openai/gpt-4o",
        "cost_per_mtok": 2.50,
        "latency_p95_ms": 800,
        "quality_score": 0.95,
        "max_context_tokens": 128_000,
        "provider": "openai",
    },
}

# Backwards compat for old keys used elsewhere
LEGACY_ALIAS = {"gemini-2.5-flash": "balanced", "gpt-4o": "premium", "gemini-1.5-flash": "fast"}


class ModelRouter:
    def __init__(self, registry: Optional[Dict[str, Dict[str, Any]]] = None, default_model: str = "balanced"):
        if LITELLM_AVAILABLE and litellm is not None:
            try:
                # litellm reads env keys automatically; just ensure google key is set
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                if api_key:
                    litellm.api_key = api_key  # type: ignore
            except Exception:
                pass
        self.registry = registry or MODEL_REGISTRY
        self.default_model_key = default_model if default_model in self.registry else "balanced"
        self._call_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Token & cost helpers
    # ------------------------------------------------------------------
    def _estimate_tokens(self, text: str) -> int:
        if TIKTOKEN_AVAILABLE:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
                return len(enc.encode(text))
            except Exception:
                pass
        # Fallback: ~4 chars per token (conservative)
        return max(1, len(text) // 4)

    def estimate_cost(self, prompt: str, model_key: str = "balanced", output_tokens: int = 512) -> float:
        """Estimate USD cost for a request (input + expected output)."""
        # Normalize key
        if model_key in LEGACY_ALIAS:
            model_key = LEGACY_ALIAS[model_key]
        cfg = self.registry.get(model_key, self.registry[self.default_model_key])
        input_tokens = self._estimate_tokens(prompt)
        total_tokens = input_tokens + output_tokens
        return (total_tokens / 1_000_000) * cfg["cost_per_mtok"]

    def estimate_cost_for_model(self, model: str, prompt: str, output_tokens: int = 512) -> float:
        # model may be full litellm model string like "gemini/gemini-1.5-flash"
        # reverse lookup
        for k, cfg in self.registry.items():
            if cfg["model"] == model:
                return self.estimate_cost(prompt, k, output_tokens)
        return self.estimate_cost(prompt, self.default_model_key, output_tokens)

    # ------------------------------------------------------------------
    # Selection: budget & latency constrained optimization
    # ------------------------------------------------------------------
    def select_model(self, query_complexity: str = "medium", budget: Optional[float] = None, latency_sla_ms: Optional[int] = None) -> str:
        """
        Legacy compat: returns model string.
        Use select() for structured ModelSelection.
        """
        sel = self.select(query_complexity=query_complexity, budget_usd=budget, latency_sla_ms=latency_sla_ms)
        return sel.primary_model

    def select(self, query_complexity: str = "medium", budget_usd: Optional[float] = None, latency_sla_ms: Optional[int] = None,
               estimated_input_tokens: int = 512, estimated_output_tokens: int = 512,
               user_tier: str = "free") -> ModelSelection:
        """
        Cost/quality/latency frontier:
          score = quality * 0.5 + (budget headroom) * 0.25 + (latency headroom) * 0.25
        Filters models that violate hard constraints (context window, budget, latency).
        Returns ModelSelection with fallback chain sorted by score.
        """
        tier_caps = {"free": 0.002, "pro": 0.01, "enterprise": 0.05}
        effective_budget = budget_usd if budget_usd is not None else tier_caps.get(user_tier, tier_caps["free"])
        # Also cap by latency SLA (if not given, use tier default)
        tier_latency = {"free": 2000, "pro": 1000, "enterprise": 600}
        effective_latency = latency_sla_ms if latency_sla_ms is not None else tier_latency.get(user_tier, 2000)

        # Complexity -> quality floor
        complexity_floor = {"low": 0.0, "medium": 0.75, "high": 0.88, "very_high": 0.93}
        floor = complexity_floor.get(query_complexity, 0.75)

        total_tokens = estimated_input_tokens + estimated_output_tokens
        candidates: List[Tuple[str, float, Dict[str, Any], float]] = []
        for key, cfg in self.registry.items():
            # Context window hard constraint
            if total_tokens > cfg["max_context_tokens"]:
                continue
            est_cost = (total_tokens / 1_000_000) * cfg["cost_per_mtok"]
            # Budget hard constraint (allow 10% overrun for high complexity)
            if est_cost > effective_budget * (1.1 if query_complexity == "high" else 1.0):
                continue
            if cfg["latency_p95_ms"] > effective_latency:
                continue
            if cfg["quality_score"] < floor - 0.08:  # allow small slack, else no candidate
                # but if no candidate passes floor, we relax later
                pass
            # Score
            quality_fit = cfg["quality_score"]
            # Penalize if below floor
            if quality_fit < floor:
                quality_fit -= (floor - quality_fit) * 0.5
            cost_eff = min(effective_budget / max(est_cost, 1e-9) * 0.02, 1.0)  # saturates
            latency_eff = min(effective_latency / max(cfg["latency_p95_ms"], 1), 1.0)
            score = quality_fit * 0.5 + cost_eff * 0.25 + latency_eff * 0.25
            candidates.append((cfg["model"], score, cfg, est_cost))

        if not candidates:
            # Fallback: cheapest that fits context
            sorted_by_cost = sorted(self.registry.items(), key=lambda kv: kv[1]["cost_per_mtok"])
            for k, cfg in sorted_by_cost:
                if total_tokens <= cfg["max_context_tokens"]:
                    est_cost = (total_tokens / 1_000_000) * cfg["cost_per_mtok"]
                    return ModelSelection(
                        primary_model=cfg["model"],
                        fallback_chain=[c["model"] for _, c in sorted_by_cost if c["model"] != cfg["model"]][:2],
                        estimated_cost_usd=round(est_cost, 6),
                        estimated_latency_ms=cfg["latency_p95_ms"],
                        confidence_score=0.45,
                        routing_decision_reason=f"budget/latency over-constrained; fell back to cheapest viable {k}",
                        ml_routed=False,
                    )
            # Ultimate fallback
            cfg = self.registry[self.default_model_key]
            return ModelSelection(primary_model=cfg["model"], fallback_chain=[], estimated_cost_usd=0.001, estimated_latency_ms=cfg["latency_p95_ms"], confidence_score=0.4, routing_decision_reason="no viable candidate; default", ml_routed=False)

        candidates.sort(key=lambda x: x[1], reverse=True)
        primary_model, primary_score, primary_cfg, primary_cost = candidates[0]
        fallbacks = [m for m, _, _, _ in candidates[1:4]]
        # Confidence: distance between top-2
        confidence = 0.75
        if len(candidates) > 1:
            gap = candidates[0][1] - candidates[1][1]
            confidence = min(0.95, 0.6 + gap * 0.8)
        return ModelSelection(
            primary_model=primary_model,
            fallback_chain=fallbacks,
            estimated_cost_usd=round(primary_cost, 6),
            estimated_latency_ms=primary_cfg["latency_p95_ms"],
            confidence_score=round(confidence, 3),
            routing_decision_reason=f"complexity={query_complexity} budget=${effective_budget} sla={effective_latency}ms → {primary_model} (score {primary_score:.3f})",
            ml_routed=False,
        )

    # ------------------------------------------------------------------
    # Generation with fallback chain + mock support
    # ------------------------------------------------------------------
    def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Unified generation. Supports model='mock/...' for tests without API keys."""
        chosen_model = model or self.select_model()
        # Mock mode: no network
        if chosen_model.startswith("mock/"):
            return f"[MOCK:{chosen_model}] {prompt[:120]}"
        # If no API key for Gemini/OpenAI, degrade gracefully (demo mode)
        has_google = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        needs_google = chosen_model.startswith("gemini/")
        needs_openai = chosen_model.startswith("openai/")
        if (needs_google and not has_google) or (needs_openai and not has_openai):
            return f"[DEGRADED_NO_KEY:{chosen_model}] {prompt[:180]} | (set GOOGLE_API_KEY for live LLM)"
        if not LITELLM_AVAILABLE or litellm is None:
            # Degraded: return prompt echo (keeps pipeline functional without keys)
            try: logger.warning("litellm_not_available_degraded_mode")
            except TypeError: logger.warning("litellm_not_available_degraded_mode")
            return f"[DEGRADED_NO_LITELLM] {prompt[:200]}"
        # Budget logging
        start = time.time()
        try:
            response = litellm.completion(model=chosen_model, messages=[{"role": "user", "content": prompt}], **kwargs)
            text = response.choices[0].message.content  # type: ignore
            self._call_log.append({"model": chosen_model, "prompt_len": len(prompt), "latency_ms": round((time.time()-start)*1000,1), "success": True})
            return text
        except Exception as e:
            self._call_log.append({"model": chosen_model, "error": str(e), "latency_ms": round((time.time()-start)*1000,1), "success": False})
            try:
                logger.error("model_generate_failed", extra={"model": chosen_model, "error": str(e)})  # type: ignore
            except TypeError:
                logger.error(f"model_generate_failed model={chosen_model} error={e}")
            # Try fallback once
            fallback = self.select().fallback_chain
            for fb in fallback[:1]:
                if fb == chosen_model:
                    continue
                try:
                    response = litellm.completion(model=fb, messages=[{"role": "user", "content": prompt}], **kwargs)  # type: ignore
                    return response.choices[0].message.content  # type: ignore
                except Exception:
                    continue
            # All LLM attempts failed — degrade gracefully for demo/offline (no API key)
            return f"[DEGRADED_FALLBACK:{chosen_model}] {prompt[:180]} | (add GOOGLE_API_KEY for live LLM)"

    def generate_with_payload(self, payload: Dict[str, Any]) -> str:
        """Compat shim for server.py which builds Gemini payload dicts."""
        # Extract prompt from payload if possible
        try:
            parts = payload.get("contents", [{}])[0].get("parts", [])
            prompt = " ".join(p.get("text","") for p in parts)
            if not prompt:
                prompt = str(payload)[:2000]
            return self.generate(prompt)
        except Exception as e:
            return self.generate(str(payload)[:2000])

    def get_call_log(self) -> List[Dict[str, Any]]:
        return list(self._call_log)