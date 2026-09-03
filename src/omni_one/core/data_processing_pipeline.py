"""
Integrated Multi-Layered Data Processing Pipeline
==================================================

Master orchestrator for the 4-layer architecture:
1. Fast Ingestion & Validation (<1ms)
2. Statistical Anomaly Detection (<10ms)
3. ML Feature Engineering (<100ms)
4. LLM Synthesis (only if needed, 500ms-2s, can be async)

This architecture resolves the LLM bottleneck for high-velocity time series data
by using deterministic fast processing first, then intelligently gating LLM calls.

For 1000 events/sec:
- Without pipeline: 1000 LLM calls = 500-2000 seconds = impossible
- With pipeline: ~5 LLMs calls = 2-10 seconds = feasible
"""

import hashlib
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

def _load_types():
    try:
        from .types import EvidenceBundle as EB, EvidenceStep as ES, CostLedgerEntry as CE  # type: ignore
        return EB, ES, CE
    except (ImportError, ValueError):
        try:
            from omni_one.core.types import EvidenceBundle as EB, EvidenceStep as ES, CostLedgerEntry as CE  # type: ignore
            return EB, ES, CE
        except (ImportError, ValueError):
            import importlib.util as _ilu, pathlib as _pl
            for _p in [_pl.Path(__file__).parent / "types.py", _pl.Path(__file__).parent.parent.parent / "omni_one" / "core" / "types.py"]:
                if _p.exists():
                    _spec = _ilu.spec_from_file_location("omni_one_core_types", _p)
                    _mod = _ilu.module_from_spec(_spec)  # type: ignore
                    assert _spec and _spec.loader
                    _spec.loader.exec_module(_mod)  # type: ignore
                    return _mod.EvidenceBundle, _mod.EvidenceStep, _mod.CostLedgerEntry  # type: ignore
            return None, None, None  # type: ignore

EvidenceBundle, EvidenceStep, CostLedgerEntry = _load_types()  # type: ignore

def _load_layer_modules():
    try:
        from .layer_1_ingestion import Layer1Ingestion as L1, IngestionMetrics as IM  # type: ignore
        from .layer_2_statistical import Layer2StatisticalProcessing as L2  # type: ignore
        from .layer_3_ml_features import Layer3MLFeatures as L3  # type: ignore
        from .model_router import ModelRouter as MR  # type: ignore
        from .cache import SemanticCache as SC  # type: ignore
        return L1, IM, L2, L3, MR, SC
    except (ImportError, ValueError):
        try:
            from omni_one.core.layer_1_ingestion import Layer1Ingestion as L1, IngestionMetrics as IM  # type: ignore
            from omni_one.core.layer_2_statistical import Layer2StatisticalProcessing as L2  # type: ignore
            from omni_one.core.layer_3_ml_features import Layer3MLFeatures as L3  # type: ignore
            from omni_one.core.model_router import ModelRouter as MR  # type: ignore
            from omni_one.core.cache import SemanticCache as SC  # type: ignore
            return L1, IM, L2, L3, MR, SC
        except (ImportError, ValueError):
            from layer_1_ingestion import Layer1Ingestion as L1, IngestionMetrics as IM  # type: ignore
            from layer_2_statistical import Layer2StatisticalProcessing as L2  # type: ignore
            from layer_3_ml_features import Layer3MLFeatures as L3  # type: ignore
            from model_router import ModelRouter as MR  # type: ignore
            from cache import SemanticCache as SC  # type: ignore
            return L1, IM, L2, L3, MR, SC

Layer1Ingestion, IngestionMetrics, Layer2StatisticalProcessing, Layer3MLFeatures, ModelRouter, SemanticCache = _load_layer_modules()  # type: ignore

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Stages at which a record can be resolved without LLM."""
    INGESTION_ERROR = "ingestion_error"  # Failed validation
    STATISTICAL = "statistical"  # Caught by Layer 2
    ML_FEATURE = "ml_feature"  # Analyzed in Layer 3
    LLM_REQUIRED = "llm_required"  # Needs LLM synthesis


@dataclass
class ProcessingResult:
    """Complete result of multi-layer processing."""
    record_id: str
    original_record: Dict[str, Any]
    final_record: Dict[str, Any]
    processing_stage: ProcessingStage
    layer1_result: Optional[Dict[str, Any]] = None
    layer2_result: Optional[Dict[str, Any]] = None
    layer3_result: Optional[Dict[str, Any]] = None
    layer4_llm_response: Optional[str] = None
    
    # Timing
    layer1_time_ms: float = 0.0
    layer2_time_ms: float = 0.0
    layer3_time_ms: float = 0.0
    layer4_time_ms: float = 0.0
    total_time_ms: float = 0.0
    
    # Metrics
    llm_bypassed: bool = False
    confidence_score: float = 0.0
    llm_decision_audit: Dict[str, Any] = field(default_factory=dict)
    # New in STRATEGY.md: audit-grade evidence + cost
    evidence_bundle: Any = None  # EvidenceBundle when available, else dict
    cost_ledger: Any = None  # CostLedgerEntry when available
    evidence_steps: List[Dict[str, Any]] = field(default_factory=list)  # flat for JSON serialization

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "record_id": self.record_id,
            "processing_stage": self.processing_stage.value if hasattr(self.processing_stage, "value") else str(self.processing_stage),
            "llm_bypassed": self.llm_bypassed,
            "confidence_score": self.confidence_score,
            "total_time_ms": round(self.total_time_ms, 2),
            "llm_decision_audit": self.llm_decision_audit,
            "cost_ledger": self.cost_ledger.model_dump() if hasattr(self.cost_ledger, "model_dump") else self.cost_ledger,
            "evidence_bundle": self.evidence_bundle.model_dump() if hasattr(self.evidence_bundle, "model_dump") else self.evidence_bundle,
            "evidence_steps": self.evidence_steps,
        }
        return base


@dataclass
class PipelineMetrics:
    """Metrics for overall pipeline performance."""
    total_records_processed: int = 0
    records_resolved_at_layer1: int = 0
    records_resolved_at_layer2: int = 0
    records_resolved_at_layer3: int = 0
    records_requiring_llm: int = 0
    
    llm_bypass_rate: float = 0.0
    avg_processing_time_ms: float = 0.0
    
    # Detailed timing
    total_layer1_time_ms: float = 0.0
    total_layer2_time_ms: float = 0.0
    total_layer3_time_ms: float = 0.0
    total_layer4_time_ms: float = 0.0
    
    # Anomaly statistics
    critical_anomalies_detected: int = 0
    high_anomalies_detected: int = 0
    
    # Cache statistics
    cache_hits: int = 0
    cache_misses: int = 0
    # Evidence + cost (new)
    total_cost_usd: float = 0.0
    evidence_bundles_produced: int = 0


class IntelligentLLMGate:
    """
    Intelligent gating for LLM invocations — now budget-aware.
    Decides whether to call LLM based on priority, severity, cache, batch context, and $ budget.
    See docs/STRATEGY.md Pillar 1: cost/latency/quality frontier.
    """
    
    def __init__(self, model_router: Optional[ModelRouter] = None, cache: Optional[SemanticCache] = None, per_record_budget_usd: Optional[float] = None):
        self.model_router = model_router
        self.cache = cache
        self.per_record_budget_usd = per_record_budget_usd
        self.llm_call_history = []  # Track LLM calls for analytics
    
    def should_invoke_llm(self, 
                         record: Dict[str, Any],
                         priority_score: float,
                         anomaly_severity: Optional[str] = None,
                         batch_context: Optional[Dict[str, Any]] = None,
                         estimated_cost_usd: Optional[float] = None) -> Tuple[bool, str]:
        """
        Determine if LLM invocation is justified.
        
        Args:
            record: The processed record
            priority_score: Priority score from Layer 3
            anomaly_severity: Anomaly severity from Layer 2
            batch_context: Aggregate statistics from batch (for contextual gating)
            estimated_cost_usd: Pre-estimated cost for this record's LLM call
        
        Returns:
            (should_invoke, reason)
        """
        # Budget gate: if cost would exceed per-record budget, never invoke unless critical
        if self.per_record_budget_usd is not None and estimated_cost_usd is not None:
            if estimated_cost_usd > self.per_record_budget_usd and anomaly_severity not in ["critical"]:
                return False, f"Budget exceeded: est ${estimated_cost_usd:.4f} > budget ${self.per_record_budget_usd:.4f}"
        # Critical or high priority = always invoke (unless budget hard block above)
        if priority_score > 0.6 or anomaly_severity in ["critical", "high"]:
            reason = f"High priority ({priority_score:.2f}) or critical anomaly"
            if batch_context:
                reason += f" [batch_anomaly_rate={batch_context.get('anomaly_rate', 0):.1%}]"
            return True, reason
        
        # Medium priority = check cache first
        if priority_score > 0.4:
            if self.cache and self._check_cache(record):
                return False, "Similar record in cache"
            
            # Consider batch context: if batch has low anomaly rate, reduce LLM calls
            if batch_context and batch_context.get('anomaly_rate', 0) < 0.1:
                # Batch is mostly clean, only invoke for very high priority in this record
                if priority_score > 0.55:
                    return True, f"Medium-high priority ({priority_score:.2f}) in low-anomaly batch"
                return False, "Medium priority but batch is clean"
            
            return True, f"Medium priority ({priority_score:.2f})"
        
        # Low priority = skip LLM
        return False, "Low priority score"
    
    def _check_cache(self, record: Dict[str, Any]) -> bool:
        """Check if we have a cached response for similar record."""
        if not self.cache:
            return False
        
        # Create query from record
        query = f"{record.get('source', '')} {record.get('entity_id', '')} {record.get('value', '')}"
        results = self.cache.retrieve(query, k=1)
        return len(results) > 0
    
    def invoke_llm(self, record: Dict[str, Any], prompt: str) -> str:
        """Invoke LLM with proper routing."""
        if not self.model_router:
            raise RuntimeError("No model router configured")
        response = self.model_router.generate(prompt)
        self.llm_call_history.append({
            "timestamp": datetime.now(),
            "record_id": record.get("entity_id"),
            "response": response
        })
        return response


def _build_evidence_step(layer: str, signal: str, citation: str, raw: Optional[Dict[str, Any]] = None, cost_usd: float = 0.0, latency_ms: float = 0.0):
    """Helper to build EvidenceStep or dict if pydantic unavailable."""
    raw = raw or {}
    if EvidenceBundle is not None and EvidenceStep is not None:
        try:
            return EvidenceStep(layer=layer, signal=signal, citation=citation, raw=raw, cost_usd=cost_usd, latency_ms=latency_ms)
        except Exception:
            pass
    return {"layer": layer, "signal": signal, "citation": citation, "raw": raw, "cost_usd": cost_usd, "latency_ms": latency_ms}

def _build_cost_ledger(record_id: str, prompt: Optional[str] = None, model_used: Optional[str] = None, cached: bool = False, budget_usd: Optional[float] = None, model_router: Optional[ModelRouter] = None):
    if CostLedgerEntry is None:
        return {"record_id": record_id, "model_used": model_used, "cached": cached, "cost_usd": 0.0, "budget_usd": budget_usd}
    try:
        cost = 0.0
        input_tokens = 0
        output_tokens = 0
        if prompt and model_router and model_used:
            input_tokens = model_router._estimate_tokens(prompt) if hasattr(model_router, "_estimate_tokens") else len(prompt)//4  # type: ignore
            output_tokens = 512
            # find model key
            cost = model_router.estimate_cost_for_model(model_used, prompt, output_tokens) if hasattr(model_router, "estimate_cost_for_model") else 0.0
            if cached:
                cost = 0.0
        return CostLedgerEntry(record_id=record_id, model_used=model_used, input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=round(cost, 6), cached=cached, budget_usd=budget_usd, budget_exceeded=(budget_usd is not None and cost > budget_usd))
    except Exception:
        return CostLedgerEntry(record_id=record_id, model_used=model_used, input_tokens=0, output_tokens=0, cost_usd=0.0, cached=cached, budget_usd=budget_usd, budget_exceeded=False)


class MultiLayerDataPipeline:
    """
    The complete multi-layered data processing pipeline with selective propagation.
    
    Key benefits:
    - Handles high-velocity data efficiently
    - Minimizes LLM calls through intelligent gating
    - Provides maximum transparency (each layer's results visible)
    - Scales to 1000s events/sec with <10ms latency (Layer 1-3)
    - Only complex cases escalate to LLM
    
    NEW: Selective Propagation & Aggregate Enrichment
    - Skips expensive Layer 3 (ML features) for records with no/low anomalies
    - Injects batch context (anomaly rate, statistics) for adaptive routing
    - Batch-aware LLM gating reduces unnecessary LLM invocations
    
    Usage:
        - process_record(): Process single record (backward compatible)
        - process_batch(): Process multiple records (original behavior)
        - process_batch_optimized(enable_selective_propagation=True): Optimized batch processing
    """
    
    def __init__(self, model_router: Optional[ModelRouter] = None, cache: Optional[SemanticCache] = None, per_record_budget_usd: Optional[float] = None):
        import threading
        self.layer1 = Layer1Ingestion()
        self.layer2 = Layer2StatisticalProcessing()
        self.layer3 = Layer3MLFeatures()
        self.model_router = model_router
        self.cache = cache
        self.llm_gate = IntelligentLLMGate(model_router, cache, per_record_budget_usd=per_record_budget_usd) if model_router else None

        self.metrics = PipelineMetrics()
        self.per_record_budget_usd = per_record_budget_usd
        self._metrics_lock = threading.RLock()

    def reset(self):
        """Reset pipeline state for fresh streams/tests (clears windows, dedup, metrics)."""
        try:
            self.layer1.reset()
        except Exception:
            pass
        try:
            self.layer2.reset()
        except Exception:
            pass
        with self._metrics_lock:
            self.metrics = PipelineMetrics()

    def _generate_record_id(self, record: Dict[str, Any]) -> str:
        """Generate stable unique ID for tracking (isoformat for datetime)."""
        entity_id = str(record.get("entity_id", "unknown"))
        ts = record.get("timestamp", "")
        try:
            if isinstance(ts, datetime):
                ts = ts.isoformat()
            else:
                ts = str(ts)
        except Exception:
            ts = str(ts)
        # Truncate long timestamps, keep deterministic
        return f"{entity_id}_{ts[:26]}" if ts else entity_id

    def _build_llm_decision_audit(self,
                                  decision: str,
                                  llm_bypassed: bool,
                                  priority_score: float = 0.0,
                                  anomaly_severity: Optional[str] = None,
                                  batch_context: Optional[Dict[str, Any]] = None,
                                  gate_reason: str = "",
                                  layer3_skipped: bool = False,
                                  skip_reason: Optional[str] = None,
                                  cache_status: str = "not_checked",
                                  prompt: Optional[str] = None) -> Dict[str, Any]:
        """Create a structured audit trail for LLM routing decisions."""
        audit = {
            "decision": decision,
            "llm_bypassed": llm_bypassed,
            "layer3_skipped": layer3_skipped,
            "batch_context": batch_context,
            "gate_reason": gate_reason,
            "priority_score": float(priority_score),
            "anomaly_severity": anomaly_severity,
            "cache_status": cache_status
        }
        if skip_reason is not None:
            audit["skip_reason"] = skip_reason
        if prompt is not None:
            audit["prompt_preview"] = prompt[:200]
            # Store full length for accurate cost (not just preview)
            audit["prompt_len"] = len(prompt)
        return audit

    def _inc(self, field: str, amount: int = 1):
        """Thread-safe metrics increment."""
        try:
            with self._metrics_lock:
                setattr(self.metrics, field, getattr(self.metrics, field) + amount)
        except Exception:
            pass

    def _store_cache(self, prompt: str, response: str):
        """Best-effort cache store after LLM miss (was missing — hit_rate always 0)."""
        if not self.cache or not prompt or not response:
            return
        try:
            # Store as dict with response key for retrieve() compat
            self.cache.set(prompt, {"response": response})
        except Exception:
            pass

    def _finalize_evidence(
        self,
        result: ProcessingResult,
        record: Dict[str, Any],
        record_id: str,
        full_prompt: Optional[str] = None,
    ):
        """Shared evidence + cost builder for process_record and optimized path. Robust, never throws."""
        try:
            evidence_steps = []
            if result.layer1_result is not None:
                if result.layer1_result.get("errors"):
                    # Handle ValidationError dataclasses or dicts
                    try:
                        errs = str(result.layer1_result.get("errors"))[:120]
                    except Exception:
                        errs = "validation failed"
                    evidence_steps.append(_build_evidence_step("layer_1_ingestion", "validation_failed", f"Layer 1: validation failed {errs}", raw={"errors": str(errs)[:200]}, latency_ms=result.layer1_time_ms))
                else:
                    raw = {"source": record.get("source"), "entity_id": record.get("entity_id")}
                    h = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:8]
                    evidence_steps.append(_build_evidence_step("layer_1_ingestion", f"validated hash={h}", f"Layer 1: validated record hash {h}", raw=raw, latency_ms=result.layer1_time_ms))
            if result.layer2_result is not None:
                anomalies = result.layer2_result.get("anomalies", []) or []
                if anomalies:
                    for anom in anomalies[:2]:
                        try:
                            score = float(anom.get("score", 0) or 0)
                        except Exception:
                            score = 0.0
                        evidence_steps.append(_build_evidence_step("layer_2_statistical", f"{anom.get('type')} severity={anom.get('severity')} score={score:.2f}", f"Layer 2: {anom.get('explanation','')}", raw=anom, latency_ms=result.layer2_time_ms / max(len(anomalies), 1)))
                else:
                    evidence_steps.append(_build_evidence_step("layer_2_statistical", "no_anomaly", "Layer 2: no statistical anomaly detected", raw=result.layer2_result, latency_ms=result.layer2_time_ms))
            if result.layer3_result is not None:
                prio = (result.layer3_result.get("predictions", {}) or {}).get("priority", {}) or {}
                if result.layer3_result.get("skipped"):
                    evidence_steps.append(_build_evidence_step("layer_3_ml_features", f"skipped reason={result.layer3_result.get('skip_reason')}", f"Layer 3: skipped ({result.layer3_result.get('skip_reason')})", raw=result.layer3_result, latency_ms=0))
                else:
                    try:
                        sc = float(prio.get("score", 0) or 0)
                    except Exception:
                        sc = 0.0
                    evidence_steps.append(_build_evidence_step("layer_3_ml_features", f"priority={prio.get('value')} score={sc:.2f}", f"Layer 3: priority {prio.get('value')} ({sc:.2f}) reasons={prio.get('reasons')}", raw=result.layer3_result, latency_ms=result.layer3_time_ms))
            # Layer 4
            prompt_for_cost = full_prompt or result.llm_decision_audit.get("prompt_preview")
            model_used = None
            cached_flag = result.llm_decision_audit.get("cache_status") == "hit"
            if result.llm_decision_audit.get("prompt_preview") or full_prompt:
                try:
                    model_used = getattr(self.model_router, "registry", {}).get("balanced", {}).get("model") if self.model_router else None
                except Exception:
                    model_used = None
                evidence_steps.append(_build_evidence_step("layer_4_llm_synthesis", f"decision={result.llm_decision_audit.get('decision')} gate={str(result.llm_decision_audit.get('gate_reason',''))[:40]}", f"Layer 4: {result.llm_decision_audit.get('decision')} - {result.llm_decision_audit.get('gate_reason','')}", raw={"gate_reason": result.llm_decision_audit.get("gate_reason")}, cost_usd=0.0 if cached_flag else 0.0005, latency_ms=result.layer4_time_ms))
            else:
                evidence_steps.append(_build_evidence_step("layer_4_llm_synthesis", f"bypassed reason={str(result.llm_decision_audit.get('gate_reason',''))[:40]}", f"Layer 4: bypassed - {result.llm_decision_audit.get('gate_reason','')}", raw=result.llm_decision_audit, latency_ms=0))

            if EvidenceBundle is not None and evidence_steps:
                try:
                    if isinstance(evidence_steps[0], dict):
                        steps = [EvidenceStep(**s) for s in evidence_steps]  # type: ignore
                    else:
                        steps = evidence_steps  # type: ignore
                    bundle = EvidenceBundle(record_id=record_id, steps=steps, final_decision=result.processing_stage.value if hasattr(result.processing_stage, "value") else str(result.processing_stage), llm_bypassed=result.llm_bypassed)  # type: ignore
                    result.evidence_bundle = bundle
                except Exception:
                    result.evidence_bundle = {"record_id": record_id, "steps": [s if isinstance(s, dict) else s.model_dump() for s in evidence_steps], "final_decision": result.processing_stage.value if hasattr(result.processing_stage, "value") else str(result.processing_stage), "llm_bypassed": result.llm_bypassed}
            else:
                result.evidence_bundle = {"record_id": record_id, "steps": evidence_steps, "final_decision": result.processing_stage.value if hasattr(result.processing_stage, "value") else str(result.processing_stage), "llm_bypassed": result.llm_bypassed}
            result.evidence_steps = [s if isinstance(s, dict) else s.model_dump() for s in evidence_steps]

            result.cost_ledger = _build_cost_ledger(record_id, prompt=prompt_for_cost, model_used=model_used, cached=cached_flag, budget_usd=getattr(self.llm_gate, "per_record_budget_usd", None) if self.llm_gate else None, model_router=self.model_router)
            try:
                cost_val = result.cost_ledger.cost_usd if hasattr(result.cost_ledger, "cost_usd") else result.cost_ledger.get("cost_usd", 0)  # type: ignore
                with self._metrics_lock:
                    self.metrics.total_cost_usd += float(cost_val or 0)
                    self.metrics.evidence_bundles_produced += 1
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Evidence bundle build failed: {e}")
            result.evidence_steps = []
            result.evidence_bundle = {"error": str(e), "record_id": record_id}
            result.cost_ledger = {"record_id": record_id, "cost_usd": 0.0}

    def _update_timing_and_bypass(self, result: ProcessingResult, start_total: float):
        """Shared timing + bypass update (thread-safe)."""
        result.total_time_ms = (time.time() - start_total) * 1000
        with self._metrics_lock:
            self.metrics.total_layer1_time_ms += result.layer1_time_ms
            self.metrics.total_layer2_time_ms += result.layer2_time_ms
            self.metrics.total_layer3_time_ms += result.layer3_time_ms
            self.metrics.total_layer4_time_ms += result.layer4_time_ms
            self.metrics.total_records_processed += 1
            total = max(self.metrics.total_records_processed, 1)
            self.metrics.avg_processing_time_ms = (
                self.metrics.total_layer1_time_ms +
                self.metrics.total_layer2_time_ms +
                self.metrics.total_layer3_time_ms +
                self.metrics.total_layer4_time_ms
            ) / total
            resolved = (
                self.metrics.records_resolved_at_layer1 +
                self.metrics.records_resolved_at_layer2 +
                self.metrics.records_resolved_at_layer3
            )
            self.metrics.llm_bypass_rate = (resolved / total * 100)

    def process_record(self, record: Dict[str, Any]) -> ProcessingResult:
        """
        Process a single record through all layers.
        
        Returns:
            Complete processing result with all layer outputs
        """
        start_total = time.time()
        record_id = self._generate_record_id(record)
        result = ProcessingResult(
            record_id=record_id,
            original_record=record,
            final_record=record,
            processing_stage=ProcessingStage.INGESTION_ERROR  # Default, will be updated
        )
        
        # LAYER 1: Fast Ingestion & Validation (+ dedup, was missing in pipeline path)
        start_layer1 = time.time()
        try:
            normalized, layer1_errors = self.layer1.normalize_record(record)
        except Exception as e:
            from layer_1_ingestion import ValidationError as _VE  # type: ignore
            try:
                from .layer_1_ingestion import ValidationError as _VE  # type: ignore
            except Exception:
                pass
            layer1_errors = [{"code": "EXCEPTION", "message": str(e)}]  # type: ignore
            normalized = None  # type: ignore
        result.layer1_time_ms = (time.time() - start_layer1) * 1000

        if layer1_errors:
            result.processing_stage = ProcessingStage.INGESTION_ERROR
            # Serialize ValidationError dataclasses safely
            try:
                errs = [e.__dict__ if hasattr(e, "__dict__") else str(e) for e in layer1_errors]  # type: ignore
            except Exception:
                errs = str(layer1_errors)
            result.layer1_result = {"errors": errs}
            result.llm_bypassed = True
            result.llm_decision_audit = self._build_llm_decision_audit(
                decision="not_required",
                llm_bypassed=True,
                gate_reason="Layer 1 validation failed",
                layer3_skipped=False,
                batch_context=None
            )
            self._inc("records_resolved_at_layer1")
            self._finalize_evidence(result, record, record_id)
            self._update_timing_and_bypass(result, start_total)
            return result

        # Dedup check (pipeline previously bypassed DuplicateDetector)
        try:
            if self.layer1.duplicate_detector.is_duplicate(normalized):  # type: ignore
                result.processing_stage = ProcessingStage.INGESTION_ERROR
                result.layer1_result = {"valid": True, "duplicate": True}
                result.final_record = normalized
                result.llm_bypassed = True
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="duplicate",
                    llm_bypassed=True,
                    gate_reason="Duplicate record (dedup hash match)",
                    layer3_skipped=False,
                    batch_context=None,
                    cache_status="not_checked",
                )
                self._inc("records_resolved_at_layer1")
                self._finalize_evidence(result, record, record_id)
                self._update_timing_and_bypass(result, start_total)
                return result
        except Exception:
            pass

        result.final_record = normalized
        result.layer1_result = {"valid": True}

        # LAYER 2: Statistical Anomaly Detection
        start_layer2 = time.time()
        try:
            enriched_l2, anomalies = self.layer2.process_record(normalized)
        except Exception as e:
            logger.warning(f"Layer2 failed: {e}")
            enriched_l2, anomalies = normalized, []
            enriched_l2 = dict(enriched_l2) if isinstance(enriched_l2, dict) else normalized
            enriched_l2["_layer2_results"] = {"anomaly_detected": False, "anomalies": [], "requires_llm": False, "error": str(e)}
        result.layer2_time_ms = (time.time() - start_layer2) * 1000
        result.final_record = enriched_l2
        result.layer2_result = enriched_l2.get("_layer2_results", {}) if isinstance(enriched_l2, dict) else {}

        # Check for critical anomalies requiring LLM (thread-safe)
        if result.layer2_result.get("anomaly_detected"):
            for anom in result.layer2_result.get("anomalies", []):
                try:
                    if anom.get("severity") == "critical":
                        self._inc("critical_anomalies_detected")
                    elif anom.get("severity") == "high":
                        self._inc("high_anomalies_detected")
                except Exception:
                    pass

        # LAYER 3: ML Feature Engineering
        start_layer3 = time.time()
        try:
            enriched_l3, layer3_results = self.layer3.process_record(enriched_l2)
        except Exception as e:
            logger.warning(f"Layer3 failed: {e}")
            enriched_l3, layer3_results = enriched_l2, {"predictions": {"priority": {"value": "low", "score": 0.0, "confidence": 0.3, "reasons": [f"layer3_error:{e}"]}}, "requires_llm": False}
        result.layer3_time_ms = (time.time() - start_layer3) * 1000
        result.final_record = enriched_l3
        result.layer3_result = enriched_l3.get("_layer3_results", {}) if isinstance(enriched_l3, dict) else layer3_results

        # Determine if LLM is needed (robust defaults)
        try:
            requires_llm = bool(layer3_results.get("requires_llm", False))
            priority_score = float((layer3_results.get("predictions", {}) or {}).get("priority", {}).get("score", 0.0) or 0.0)
        except Exception:
            requires_llm, priority_score = False, 0.0
        try:
            confidence_score = max([
                float(p.get("confidence", 0.0) or 0.0)
                for p in (layer3_results.get("predictions", {}) or {}).values()
                if isinstance(p, dict)
            ], default=0.5)
        except Exception:
            confidence_score = 0.5

        result.confidence_score = confidence_score

        # LAYER 4: Intelligent LLM Gating (max severity, not first)
        try:
            severities = [a.get("severity") for a in (result.layer2_result.get("anomalies", []) or []) if isinstance(a, dict)]
            order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            anomaly_severity = max(severities, key=lambda s: order.get(str(s), -1)) if severities else None
        except Exception:
            anomaly_severity = None

        full_prompt: Optional[str] = None
        if not requires_llm:
            # Distinguish STATISTICAL (anomaly but no LLM) vs ML_FEATURE for accurate bypass metrics
            if result.layer2_result.get("anomaly_detected"):
                result.processing_stage = ProcessingStage.STATISTICAL
                result.llm_bypassed = True
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="statistical_only",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=None,
                    gate_reason="Anomaly detected but Layer 3 did not require LLM",
                    layer3_skipped=False,
                    cache_status="not_checked"
                )
                self._inc("records_resolved_at_layer2")
            else:
                result.processing_stage = ProcessingStage.ML_FEATURE
                result.llm_bypassed = True
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="not_required",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=None,
                    gate_reason="Layer 3 did not require LLM synthesis",
                    layer3_skipped=False,
                    cache_status="not_checked"
                )
                self._inc("records_resolved_at_layer3")
        elif not self.model_router:
            result.processing_stage = ProcessingStage.ML_FEATURE
            result.llm_bypassed = True
            result.llm_decision_audit = self._build_llm_decision_audit(
                decision="gate_bypassed",
                llm_bypassed=True,
                priority_score=priority_score,
                anomaly_severity=anomaly_severity,
                batch_context=None,
                gate_reason="LLM required but no model router configured",
                layer3_skipped=False,
                cache_status="not_configured"
            )
            self._inc("records_resolved_at_layer3")
        else:
            # Check if LLM gate approves (batch_context=None for standard processing)
            try:
                should_invoke, reason = self.llm_gate.should_invoke_llm(  # type: ignore
                    enriched_l3,
                    priority_score,
                    anomaly_severity,
                    batch_context=None
                )
            except Exception as e:
                should_invoke, reason = False, f"gate_error:{e}"

            if should_invoke:
                # Generate prompt from enriched record
                prompt = self._generate_synthesis_prompt(enriched_l3, layer3_results)
                full_prompt = prompt
                cache_status = "not_configured"

                start_layer4 = time.time()
                try:
                    # Check cache first
                    if self.cache:
                        try:
                            cached = self.cache.retrieve(prompt, k=1)
                        except Exception:
                            cached = []
                        if cached:
                            result.layer4_llm_response = cached[0].page_content
                            self._inc("cache_hits")
                            cache_status = "hit"
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self._inc("cache_misses")
                            cache_status = "miss"
                            # Store for future (was missing — hit_rate always 0)
                            self._store_cache(prompt, result.layer4_llm_response or "")
                    else:
                        result.layer4_llm_response = self.model_router.generate(prompt)
                        self._inc("cache_misses")

                    result.layer4_time_ms = (time.time() - start_layer4) * 1000
                    result.processing_stage = ProcessingStage.LLM_REQUIRED
                    result.llm_bypassed = False
                    self._inc("records_requiring_llm")
                except Exception as e:
                    logger.error(f"LLM generation failed: {e}")
                    result.layer4_llm_response = f"LLM Error: {str(e)}"
                    cache_status = "error"
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="invoked",
                    llm_bypassed=False,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=None,
                    gate_reason=reason,
                    layer3_skipped=False,
                    cache_status=cache_status,
                    prompt=prompt
                )
            else:
                # Gate bypassed — still distinguish statistical
                if result.layer2_result.get("anomaly_detected"):
                    result.processing_stage = ProcessingStage.STATISTICAL
                    self._inc("records_resolved_at_layer2")
                    decision = "gate_bypassed_statistical"
                else:
                    result.processing_stage = ProcessingStage.ML_FEATURE
                    self._inc("records_resolved_at_layer3")
                    decision = "gate_bypassed"
                result.llm_bypassed = True
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision=decision,
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=None,
                    gate_reason=reason,
                    layer3_skipped=False,
                    cache_status="not_checked"
                )
        
        # --- Evidence + cost (shared helper, uses full prompt for accurate cost) ---
        self._finalize_evidence(result, record, record_id, full_prompt=full_prompt)
        self._update_timing_and_bypass(result, start_total)

        return result
    
    def _generate_synthesis_prompt(self, record: Dict[str, Any], layer3_results: Dict[str, Any]) -> str:
        """Generate synthesis prompt for LLM based on enriched record."""
        predictions = layer3_results.get("predictions", {})
        
        prompt = f"""Analyze this business intelligence record and provide insights:

Entity: {record.get('entity_id', 'N/A')}
Source: {record.get('source', 'N/A')}
Value: {record.get('value', 'N/A')}
Priority: {predictions.get('priority', {}).get('value', 'unknown')}
"""
        
        if "sentiment" in predictions:
            prompt += f"Sentiment: {predictions['sentiment']['value']}\n"
        
        if "churn_risk" in predictions:
            prompt += f"Churn Risk: {predictions['churn_risk']['value']} ({predictions['churn_risk']['score']:.2%})\n"
        
        if record.get("_layer2_results", {}).get("anomaly_detected"):
            prompt += "Anomalies detected:\n"
            for anom in record.get("_layer2_results", {}).get("anomalies", []):
                prompt += f"- {anom['type']}: {anom['explanation']}\n"
        
        prompt += "\nProvide 2-3 actionable insights or recommendations based on this data."
        
        return prompt
    
    def process_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[ProcessingResult], PipelineMetrics]:
        """
        Process batch of records through entire pipeline.
        
        Returns:
            (results_list, metrics)
        """
        results = []
        for record in records:
            result = self.process_record(record)
            results.append(result)
        
        return results, self.metrics
    
    def process_batch_optimized(self, records: List[Dict[str, Any]], 
                               enable_selective_propagation: bool = True) -> Tuple[List[ProcessingResult], PipelineMetrics]:
        """
        Process batch with selective propagation and aggregate enrichment.
        
        Optimizations:
        1. Selective Propagation: Skip Layer 3 (expensive ML) for low-severity records
        2. Aggregate Enrichment: Inject batch context to later layers
        3. Adaptive Routing: Route records based on batch characteristics
        
        Args:
            records: List of records to process
            enable_selective_propagation: Enable layer skipping optimization
        
        Returns:
            (results_list, metrics)
        """
        if not records:
            return [], self.metrics

        results: List[ProcessingResult] = []
        layer2_outputs: List[Tuple] = []

        # Phase 1: Layer 1 & Layer 2 on all records (with timing, dedup, counters)
        for record in records:
            rec_start = time.time()
            record_id = self._generate_record_id(record)
            # Layer 1: Ingestion
            try:
                normalized, layer1_errors = self.layer1.normalize_record(record)
            except Exception as e:
                normalized, layer1_errors = None, [{"code": "EXCEPTION", "message": str(e)}]  # type: ignore
            if layer1_errors:
                try:
                    errs = [e.__dict__ if hasattr(e, "__dict__") else str(e) for e in layer1_errors]  # type: ignore
                except Exception:
                    errs = str(layer1_errors)
                result = ProcessingResult(
                    record_id=record_id,
                    original_record=record,
                    final_record=normalized if isinstance(normalized, dict) else record,  # type: ignore
                    processing_stage=ProcessingStage.INGESTION_ERROR,
                    layer1_result={"errors": errs},
                    layer1_time_ms=(time.time() - rec_start) * 1000,
                    llm_bypassed=True,
                    llm_decision_audit=self._build_llm_decision_audit(
                        decision="not_required",
                        llm_bypassed=True,
                        gate_reason="Layer 1 validation failed",
                        layer3_skipped=False,
                        batch_context=None
                    )
                )
                self._finalize_evidence(result, record, record_id)
                self._inc("records_resolved_at_layer1")
                self._update_timing_and_bypass(result, rec_start)
                results.append(result)
                continue

            # Dedup (was missing in optimized path)
            try:
                if self.layer1.duplicate_detector.is_duplicate(normalized):  # type: ignore
                    result = ProcessingResult(
                        record_id=record_id,
                        original_record=record,
                        final_record=normalized,
                        processing_stage=ProcessingStage.INGESTION_ERROR,
                        layer1_result={"valid": True, "duplicate": True},
                        layer1_time_ms=(time.time() - rec_start) * 1000,
                        llm_bypassed=True,
                        llm_decision_audit=self._build_llm_decision_audit(
                            decision="duplicate", llm_bypassed=True,
                            gate_reason="Duplicate record (dedup hash match)",
                            layer3_skipped=False, batch_context=None,
                        ),
                    )
                    self._finalize_evidence(result, record, record_id)
                    self._inc("records_resolved_at_layer1")
                    self._update_timing_and_bypass(result, rec_start)
                    results.append(result)
                    continue
            except Exception:
                pass

            # Layer 2: Statistical Anomaly Detection (timed)
            l2_start = time.time()
            try:
                enriched_l2, anomalies = self.layer2.process_record(normalized)
            except Exception as e:
                enriched_l2, anomalies = dict(normalized), []
                enriched_l2["_layer2_results"] = {"anomaly_detected": False, "anomalies": [], "requires_llm": False, "error": str(e)}
            l2_time = (time.time() - l2_start) * 1000
            # Track critical/high (parity with process_record)
            try:
                for anom in (enriched_l2.get("_layer2_results", {}) or {}).get("anomalies", []) or []:
                    if anom.get("severity") == "critical":
                        self._inc("critical_anomalies_detected")
                    elif anom.get("severity") == "high":
                        self._inc("high_anomalies_detected")
            except Exception:
                pass
            layer2_outputs.append((record, normalized, enriched_l2, anomalies, rec_start, l2_time))

        # Compute batch aggregates from Layer 2
        batch_context = self._compute_batch_context([(r, n, e, a) for (r, n, e, a, _, _) in layer2_outputs])

        # Phase 2: Selective propagation to Layer 3 (with evidence parity)
        for record, normalized, enriched_l2, anomalies, rec_start, l2_time in layer2_outputs:
            layer2_result = enriched_l2.get("_layer2_results", {}) if isinstance(enriched_l2, dict) else {}
            try:
                severities = [a.get("severity") for a in (layer2_result.get("anomalies", []) or []) if isinstance(a, dict)]
                order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                anomaly_severity = max(severities, key=lambda s: order.get(str(s), -1)) if severities else None
            except Exception:
                anomaly_severity = None

            # SELECTIVE PROPAGATION LOGIC
            skip_layer3 = False
            skip_reason = ""

            if enable_selective_propagation:
                if not layer2_result.get("anomaly_detected"):
                    skip_layer3 = True
                    skip_reason = "no_anomalies"
                elif anomaly_severity == "low":
                    skip_layer3 = True
                    skip_reason = "low_severity"

            # Process Layer 3 if needed (timed)
            l3_start = time.time()
            full_prompt: Optional[str] = None
            if not skip_layer3:
                try:
                    enriched_l2["_batch_context"] = batch_context
                    enriched_l3, layer3_results = self.layer3.process_record(enriched_l2)
                except Exception as e:
                    enriched_l3, layer3_results = enriched_l2, {"predictions": {"priority": {"value": "low", "score": 0.0, "confidence": 0.3, "reasons": [f"layer3_error:{e}"]}}, "requires_llm": False}
                final_record = enriched_l3
                layer3_result = enriched_l3.get("_layer3_results", {}) if isinstance(enriched_l3, dict) else layer3_results
                l3_time = (time.time() - l3_start) * 1000
            else:
                final_record = enriched_l2
                try:
                    final_record["_batch_context"] = batch_context
                except Exception:
                    pass
                final_record["_layer3_results"] = {
                    "predictions": {
                        "priority": {
                            "value": "low",
                            "score": 0.2,
                            "confidence": 0.8,
                            "reasons": ["no_anomalies - layer3_skipped"]
                        }
                    },
                    "requires_llm": False,
                    "skipped": True,
                    "skip_reason": skip_reason
                }
                layer3_result = final_record["_layer3_results"]
                l3_time = 0.0
                # Don't increment here — increment after stage decision for accuracy

            # Layer 4: Intelligent LLM Gating with batch context
            try:
                priority_score = float((layer3_result.get("predictions", {}) or {}).get("priority", {}).get("score", 0.0) or 0.0)
                requires_llm = bool(layer3_result.get("requires_llm", False))
                conf = float((layer3_result.get("predictions", {}) or {}).get("priority", {}).get("confidence", 0.5) or 0.5)
            except Exception:
                priority_score, requires_llm, conf = 0.0, False, 0.5

            result = ProcessingResult(
                record_id=self._generate_record_id(record),
                original_record=record,
                final_record=final_record,
                processing_stage=ProcessingStage.ML_FEATURE,
                layer1_result={"valid": True},
                layer1_time_ms=0.0,  # set below from rec_start? keep 0, total covers it
                layer2_result=layer2_result,
                layer2_time_ms=l2_time,
                layer3_result=layer3_result,
                layer3_time_ms=l3_time,
                llm_bypassed=True,
                confidence_score=conf,
            )
            # Approximate layer1 time as small (already validated); total measured from rec_start
            try:
                result.layer1_time_ms = 0.1
            except Exception:
                pass

            if skip_layer3:
                result.processing_stage = ProcessingStage.ML_FEATURE
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="skipped_by_selective_propagation",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=batch_context,
                    gate_reason="LLM not required after selective propagation",
                    layer3_skipped=True,
                    skip_reason=skip_reason,
                    cache_status="not_checked"
                )
                self._inc("records_resolved_at_layer3")
            elif not requires_llm:
                # Distinguish STATISTICAL vs ML_FEATURE (was always ML_FEATURE)
                if layer2_result.get("anomaly_detected"):
                    result.processing_stage = ProcessingStage.STATISTICAL
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision="statistical_only", llm_bypassed=True,
                        priority_score=priority_score, anomaly_severity=anomaly_severity,
                        batch_context=batch_context,
                        gate_reason="Anomaly detected but Layer 3 did not require LLM",
                        layer3_skipped=False, cache_status="not_checked",
                    )
                    self._inc("records_resolved_at_layer2")
                else:
                    result.processing_stage = ProcessingStage.ML_FEATURE
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision="not_required", llm_bypassed=True,
                        priority_score=priority_score, anomaly_severity=anomaly_severity,
                        batch_context=batch_context,
                        gate_reason="Layer 3 did not require LLM synthesis",
                        layer3_skipped=False, cache_status="not_checked",
                    )
                    self._inc("records_resolved_at_layer3")
            elif requires_llm and not self.model_router:
                result.processing_stage = ProcessingStage.ML_FEATURE
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="gate_bypassed", llm_bypassed=True,
                    priority_score=priority_score, anomaly_severity=anomaly_severity,
                    batch_context=batch_context,
                    gate_reason="LLM required but no model router configured",
                    layer3_skipped=False, cache_status="not_configured",
                )
                self._inc("records_resolved_at_layer3")

            # LLM invocation with batch context awareness
            if requires_llm and self.model_router and not skip_layer3:
                try:
                    should_invoke, gate_reason = self.llm_gate.should_invoke_llm(  # type: ignore
                        final_record, priority_score, anomaly_severity, batch_context,
                    )
                except Exception as e:
                    should_invoke, gate_reason = False, f"gate_error:{e}"

                if should_invoke:
                    prompt = self._generate_synthesis_prompt(final_record, layer3_result)
                    full_prompt = prompt
                    cache_status = "not_configured"

                    l4_start = time.time()
                    try:
                        if self.cache:
                            try:
                                cached = self.cache.retrieve(prompt, k=1)
                            except Exception:
                                cached = []
                            if cached:
                                result.layer4_llm_response = cached[0].page_content
                                self._inc("cache_hits")
                                cache_status = "hit"
                            else:
                                result.layer4_llm_response = self.model_router.generate(prompt)
                                self._inc("cache_misses")
                                cache_status = "miss"
                                self._store_cache(prompt, result.layer4_llm_response or "")
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self._inc("cache_misses")

                        result.layer4_time_ms = (time.time() - l4_start) * 1000
                        result.processing_stage = ProcessingStage.LLM_REQUIRED
                        result.llm_bypassed = False
                        self._inc("records_requiring_llm")
                    except Exception as e:
                        logger.error(f"LLM generation failed: {e}")
                        result.layer4_llm_response = f"LLM Error: {str(e)}"
                        result.layer4_time_ms = (time.time() - l4_start) * 1000
                        cache_status = "error"
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision="invoked", llm_bypassed=False,
                        priority_score=priority_score, anomaly_severity=anomaly_severity,
                        batch_context=batch_context, gate_reason=gate_reason,
                        layer3_skipped=False, cache_status=cache_status, prompt=prompt,
                    )
                else:
                    if layer2_result.get("anomaly_detected"):
                        result.processing_stage = ProcessingStage.STATISTICAL
                        self._inc("records_resolved_at_layer2")
                        decision = "gate_bypassed_statistical"
                    else:
                        # Already counted? skip_layer3 False here, so count now
                        self._inc("records_resolved_at_layer3")
                        decision = "gate_bypassed"
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision=decision, llm_bypassed=True,
                        priority_score=priority_score, anomaly_severity=anomaly_severity,
                        batch_context=batch_context, gate_reason=gate_reason,
                        layer3_skipped=False, cache_status="not_checked",
                    )

            # Evidence parity (was missing in optimized path)
            self._finalize_evidence(result, record, result.record_id, full_prompt=full_prompt)
            self._update_timing_and_bypass(result, rec_start)
            results.append(result)

        return results, self.metrics
    
    def _compute_batch_context(self, layer2_outputs: List[Tuple]) -> Dict[str, Any]:
        """
        Compute aggregate statistics from batch for enrichment.
        
        Args:
            layer2_outputs: List of (record, normalized, enriched_l2, anomalies) tuples
        
        Returns:
            batch_context dict with aggregate statistics
        """
        total = len(layer2_outputs)
        if total == 0:
            return {}
        
        anomaly_count = 0
        critical_count = 0
        high_count = 0
        anomaly_types = {}
        
        for _, _, enriched_l2, anomalies in layer2_outputs:
            layer2_result = enriched_l2.get("_layer2_results", {})
            if layer2_result.get("anomaly_detected"):
                anomaly_count += 1
                for anom in layer2_result.get("anomalies", []):
                    severity = anom.get("severity", "unknown")
                    if severity == "critical":
                        critical_count += 1
                    elif severity == "high":
                        high_count += 1
                    
                    anom_type = anom.get("type", "unknown")
                    anomaly_types[anom_type] = anomaly_types.get(anom_type, 0) + 1
        
        return {
            "batch_size": total,
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_count / total,
            "critical_count": critical_count,
            "high_count": high_count,
            "anomaly_types": anomaly_types,
            "clean_rate": 1.0 - (anomaly_count / total),
            "timestamp": datetime.now().isoformat()
        }
    
    async def process_batch_async(self, 
                                  records: List[Dict[str, Any]],
                                  max_concurrent: int = 5) -> Tuple[List[ProcessingResult], PipelineMetrics]:
        """
        Process batch asynchronously with concurrency limit.
        Useful for high-volume scenarios.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def bounded_process(record):
            async with semaphore:
                return self.process_record(record)
        
        tasks = [bounded_process(r) for r in records]
        results = await asyncio.gather(*tasks)
        
        return results, self.metrics
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get human-readable metrics summary (now with cost & evidence)."""
        return {
            "total_records": self.metrics.total_records_processed,
            "llm_bypass_rate": f"{self.metrics.llm_bypass_rate:.1f}%",
            "llm_call_reduction": f"{self.metrics.llm_bypass_rate:.0f}%",
            "records_by_stage": {
                "layer1_rejected": self.metrics.records_resolved_at_layer1,
                "layer2_statistical": self.metrics.records_resolved_at_layer2,
                "layer3_ml": self.metrics.records_resolved_at_layer3,
                "layer4_llm": self.metrics.records_requiring_llm
            },
            "anomalies": {
                "critical": self.metrics.critical_anomalies_detected,
                "high": self.metrics.high_anomalies_detected
            },
            "timing": {
                "avg_total_ms": f"{self.metrics.avg_processing_time_ms:.2f}ms",
                "layer1_avg_ms": f"{self.metrics.total_layer1_time_ms / max(self.metrics.total_records_processed, 1):.2f}ms",
                "layer2_avg_ms": f"{self.metrics.total_layer2_time_ms / max(self.metrics.total_records_processed, 1):.2f}ms",
                "layer3_avg_ms": f"{self.metrics.total_layer3_time_ms / max(self.metrics.total_records_processed, 1):.2f}ms",
                "layer4_avg_ms": f"{self.metrics.total_layer4_time_ms / max(self.metrics.records_requiring_llm, 1):.2f}ms" if self.metrics.records_requiring_llm > 0 else "N/A"
            },
            "cache": {
                "hits": self.metrics.cache_hits,
                "misses": self.metrics.cache_misses,
                "hit_rate": f"{self.metrics.cache_hits / max(self.metrics.cache_hits + self.metrics.cache_misses, 1) * 100:.1f}%"
            },
            "cost": {
                "total_usd": round(self.metrics.total_cost_usd, 4),
                "avg_per_1k_usd": round((self.metrics.total_cost_usd / max(self.metrics.total_records_processed,1))*1000, 4),
                "est_savings_vs_naive_llm_everywhere_usd": round(self.metrics.total_cost_usd * (100 / max(100 - self.metrics.llm_bypass_rate, 1) - 1), 2) if self.metrics.llm_bypass_rate < 99 else 0,
            },
            "evidence": {
                "bundles_produced": self.metrics.evidence_bundles_produced,
            }
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from datetime import datetime
    
    # Initialize pipeline (without LLM for demo)
    pipeline = MultiLayerDataPipeline()
    
    # Create test records simulating high-velocity stream
    print("=" * 60)
    print("MULTI-LAYER DATA PROCESSING PIPELINE DEMO")
    print("=" * 60)
    
    test_records = [
        {
            "timestamp": datetime.now().isoformat(),
            "source": "salesforce",
            "entity_id": "account_001",
            "value": 95000,
            "metadata": {"type": "MRR", "currency": "USD"}
        },
        {
            "timestamp": datetime.now().isoformat(),
            "source": "email",
            "entity_id": "user_002",
            "value": "Great service! Very satisfied.",
            "metadata": {"sentiment_hint": "positive"}
        },
        {
            "timestamp": datetime.now().isoformat(),
            "source": "slack",
            "entity_id": "team_003",
            "value": "Having issues with system performance",
            "metadata": {"channel": "support"}
        },
        # Outlier
        {
            "timestamp": datetime.now().isoformat(),
            "source": "salesforce",
            "entity_id": "account_001",
            "value": 15000,  # Sudden drop
            "metadata": {"type": "MRR", "currency": "USD"}
        },
    ]
    
    # Process batch
    results, metrics = pipeline.process_batch(test_records)
    
    print("\n" + "=" * 60)
    print("PROCESSING RESULTS")
    print("=" * 60)
    
    for i, result in enumerate(results):
        print(f"\n[Record {i+1}]")
        print(f"  Entity: {result.original_record.get('entity_id')}")
        print(f"  Stage: {result.processing_stage.value}")
        print(f" LLM Bypassed: {result.llm_bypassed}")
        print(f"  Total Time: {result.total_time_ms:.2f}ms")
        print(f"  Confidence: {result.confidence_score:.2f}")
        
        if result.layer3_result and "predictions" in result.layer3_result:
            preds = result.layer3_result["predictions"]
            if "priority" in preds:
                print(f"  Priority: {preds['priority'].get('value')}")
    
    print("\n" + "=" * 60)
    print("PIPELINE METRICS SUMMARY")
    print("=" * 60)
    import pprint
    pprint.pprint(pipeline.get_metrics_summary())
