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
        self.layer1 = Layer1Ingestion()
        self.layer2 = Layer2StatisticalProcessing()
        self.layer3 = Layer3MLFeatures()
        self.model_router = model_router
        self.cache = cache
        self.llm_gate = IntelligentLLMGate(model_router, cache, per_record_budget_usd=per_record_budget_usd) if model_router else None
        
        self.metrics = PipelineMetrics()
        self.per_record_budget_usd = per_record_budget_usd
    
    def _generate_record_id(self, record: Dict[str, Any]) -> str:
        """Generate unique ID for tracking."""
        entity_id = record.get("entity_id", "unknown")
        timestamp = record.get("timestamp", "")
        return f"{entity_id}_{timestamp}"

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
        return audit
    
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
        
        # LAYER 1: Fast Ingestion & Validation
        start_layer1 = time.time()
        normalized, layer1_errors = self.layer1.normalize_record(record)
        result.layer1_time_ms = (time.time() - start_layer1) * 1000
        
        if layer1_errors:
            result.processing_stage = ProcessingStage.INGESTION_ERROR
            result.layer1_result = {"errors": layer1_errors}
            result.llm_bypassed = True
            result.llm_decision_audit = self._build_llm_decision_audit(
                decision="not_required",
                llm_bypassed=True,
                gate_reason="Layer 1 validation failed",
                layer3_skipped=False,
                batch_context=None
            )
            self.metrics.records_resolved_at_layer1 += 1
            return result
        
        result.final_record = normalized
        result.layer1_result = {"valid": True}
        
        # LAYER 2: Statistical Anomaly Detection
        start_layer2 = time.time()
        enriched_l2, anomalies = self.layer2.process_record(normalized)
        result.layer2_time_ms = (time.time() - start_layer2) * 1000
        result.final_record = enriched_l2
        result.layer2_result = enriched_l2.get("_layer2_results", {})
        
        # Check for critical anomalies requiring LLM
        if result.layer2_result.get("anomaly_detected"):
            for anom in result.layer2_result.get("anomalies", []):
                if anom["severity"] == "critical":
                    self.metrics.critical_anomalies_detected += 1
                elif anom["severity"] == "high":
                    self.metrics.high_anomalies_detected += 1
        
        # LAYER 3: ML Feature Engineering
        start_layer3 = time.time()
        enriched_l3, layer3_results = self.layer3.process_record(enriched_l2)
        result.layer3_time_ms = (time.time() - start_layer3) * 1000
        result.final_record = enriched_l3
        result.layer3_result = enriched_l3.get("_layer3_results", {})
        
        # Determine if LLM is needed
        requires_llm = layer3_results.get("requires_llm", False)
        priority_score = layer3_results.get("predictions", {}).get("priority", {}).get("score", 0.0)
        confidence_score = max([
            p.get("confidence", 0.0) 
            for p in layer3_results.get("predictions", {}).values()
            if isinstance(p, dict)
        ], default=0.5)
        
        result.confidence_score = confidence_score
        
        # LAYER 4: Intelligent LLM Gating
        anomaly_severity = (
            result.layer2_result.get("anomalies", [{}])[0].get("severity")
            if result.layer2_result.get("anomalies")
            else None
        )

        if not requires_llm:
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
            self.metrics.records_resolved_at_layer3 += 1
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
            self.metrics.records_resolved_at_layer3 += 1
        else:
            # Check if LLM gate approves (batch_context=None for standard processing)
            should_invoke, reason = self.llm_gate.should_invoke_llm(
                enriched_l3,
                priority_score,
                anomaly_severity,
                batch_context=None
            )
            
            if should_invoke:
                # Generate prompt from enriched record
                prompt = self._generate_synthesis_prompt(enriched_l3, layer3_results)
                cache_status = "not_configured"
                
                start_layer4 = time.time()
                try:
                    # Check cache first
                    if self.cache:
                        cached = self.cache.retrieve(prompt, k=1)
                        if cached:
                            result.layer4_llm_response = cached[0].page_content
                            self.metrics.cache_hits += 1
                            cache_status = "hit"
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self.metrics.cache_misses += 1
                            cache_status = "miss"
                    else:
                        result.layer4_llm_response = self.model_router.generate(prompt)
                        self.metrics.cache_misses += 1
                    
                    result.layer4_time_ms = (time.time() - start_layer4) * 1000
                    result.processing_stage = ProcessingStage.LLM_REQUIRED
                    result.llm_bypassed = False
                    self.metrics.records_requiring_llm += 1
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
                result.processing_stage = ProcessingStage.ML_FEATURE
                result.llm_bypassed = True
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="gate_bypassed",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=None,
                    gate_reason=reason,
                    layer3_skipped=False,
                    cache_status="not_checked"
                )
                self.metrics.records_resolved_at_layer3 += 1
        
        # --- Evidence bundle & cost ledger (new in STRATEGY.md) ---
        try:
            evidence_steps = []
            # Layer 1 evidence
            if result.layer1_result is not None:
                if result.layer1_result.get("errors"):
                    evidence_steps.append(_build_evidence_step("layer_1_ingestion", "validation_failed", f"Layer 1: validation failed {result.layer1_result.get('errors')}", raw=result.layer1_result, latency_ms=result.layer1_time_ms))
                else:
                    # deterministic dedup hash citation
                    raw = {"source": record.get("source"), "entity_id": record.get("entity_id")}
                    h = hashlib.sha256(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:8]
                    evidence_steps.append(_build_evidence_step("layer_1_ingestion", f"validated hash={h}", f"Layer 1: validated record hash {h}", raw=raw, latency_ms=result.layer1_time_ms))
            # Layer 2 evidence
            if result.layer2_result is not None:
                anomalies = result.layer2_result.get("anomalies", [])
                if anomalies:
                    for anom in anomalies[:2]:
                        evidence_steps.append(_build_evidence_step("layer_2_statistical", f"{anom.get('type')} severity={anom.get('severity')} score={anom.get('score',0):.2f}", f"Layer 2: {anom.get('explanation','')}", raw=anom, latency_ms=result.layer2_time_ms / max(len(anomalies),1)))
                else:
                    evidence_steps.append(_build_evidence_step("layer_2_statistical", "no_anomaly", "Layer 2: no statistical anomaly detected", raw=result.layer2_result, latency_ms=result.layer2_time_ms))
            # Layer 3 evidence
            if result.layer3_result is not None:
                prio = result.layer3_result.get("predictions", {}).get("priority", {})
                if result.layer3_result.get("skipped"):
                    evidence_steps.append(_build_evidence_step("layer_3_ml_features", f"skipped reason={result.layer3_result.get('skip_reason')}", f"Layer 3: skipped ({result.layer3_result.get('skip_reason')})", raw=result.layer3_result, latency_ms=0))
                else:
                    evidence_steps.append(_build_evidence_step("layer_3_ml_features", f"priority={prio.get('value')} score={prio.get('score',0):.2f}", f"Layer 3: priority {prio.get('value')} ({prio.get('score',0):.2f}) reasons={prio.get('reasons')}", raw=result.layer3_result, latency_ms=result.layer3_time_ms))
            # Layer 4 evidence
            prompt_for_cost = None
            model_used = None
            cached_flag = False
            if result.llm_decision_audit.get("prompt_preview"):
                prompt_for_cost = result.llm_decision_audit.get("prompt_preview")
                # try to infer model
                model_used = getattr(self.model_router, "registry", {}).get("balanced", {}).get("model") if self.model_router else None
                if result.llm_decision_audit.get("cache_status") == "hit":
                    cached_flag = True
                evidence_steps.append(_build_evidence_step("layer_4_llm_synthesis", f"decision={result.llm_decision_audit.get('decision')} gate={result.llm_decision_audit.get('gate_reason','')[:40]}", f"Layer 4: {result.llm_decision_audit.get('decision')} - {result.llm_decision_audit.get('gate_reason','')}", raw={"gate_reason": result.llm_decision_audit.get("gate_reason")}, cost_usd=0.0 if cached_flag else 0.0005, latency_ms=result.layer4_time_ms))
            else:
                # no LLM
                evidence_steps.append(_build_evidence_step("layer_4_llm_synthesis", f"bypassed reason={result.llm_decision_audit.get('gate_reason','')[:40]}", f"Layer 4: bypassed - {result.llm_decision_audit.get('gate_reason','')}", raw=result.llm_decision_audit, latency_ms=0))

            # Build bundle
            if EvidenceBundle is not None:
                try:
                    bundle = EvidenceBundle(record_id=record_id, steps=[s if hasattr(s, "model_dump") else EvidenceStep(**s) for s in evidence_steps if isinstance(s, dict)] if isinstance(evidence_steps[0], dict) else evidence_steps, final_decision=result.processing_stage.value if hasattr(result.processing_stage,"value") else str(result.processing_stage), llm_bypassed=result.llm_bypassed)
                    # If we passed dicts, pydantic will validate; if we passed EvidenceStep objects, keep as is
                    result.evidence_bundle = bundle
                except Exception:
                    # fallback dict bundle
                    result.evidence_bundle = {"record_id": record_id, "steps": [s if isinstance(s, dict) else s.model_dump() for s in evidence_steps], "final_decision": result.processing_stage.value if hasattr(result.processing_stage,"value") else str(result.processing_stage), "llm_bypassed": result.llm_bypassed}
            else:
                result.evidence_bundle = {"record_id": record_id, "steps": evidence_steps, "final_decision": result.processing_stage.value if hasattr(result.processing_stage,"value") else str(result.processing_stage), "llm_bypassed": result.llm_bypassed}
            result.evidence_steps = [s if isinstance(s, dict) else s.model_dump() for s in evidence_steps]

            # Cost ledger
            result.cost_ledger = _build_cost_ledger(record_id, prompt=prompt_for_cost, model_used=model_used, cached=cached_flag, budget_usd=getattr(self.llm_gate, "per_record_budget_usd", None) if self.llm_gate else None, model_router=self.model_router)
            # Accumulate total cost
            cost_val = result.cost_ledger.cost_usd if hasattr(result.cost_ledger, "cost_usd") else result.cost_ledger.get("cost_usd", 0)
            self.metrics.total_cost_usd += float(cost_val or 0)
            self.metrics.evidence_bundles_produced += 1
        except Exception as e:
            logger.warning(f"Evidence bundle build failed: {e}")
            result.evidence_steps = []
            result.evidence_bundle = {"error": str(e), "record_id": record_id}
            result.cost_ledger = {"record_id": record_id, "cost_usd": 0.0}

        # Complete timing
        result.total_time_ms = (time.time() - start_total) * 1000
        self.metrics.total_layer1_time_ms += result.layer1_time_ms
        self.metrics.total_layer2_time_ms += result.layer2_time_ms
        self.metrics.total_layer3_time_ms += result.layer3_time_ms
        self.metrics.total_layer4_time_ms += result.layer4_time_ms
        
        self.metrics.total_records_processed += 1
        self.metrics.avg_processing_time_ms = (
            self.metrics.total_layer1_time_ms + 
            self.metrics.total_layer2_time_ms + 
            self.metrics.total_layer3_time_ms + 
            self.metrics.total_layer4_time_ms
        ) / max(self.metrics.total_records_processed, 1)
        
        # Update bypass rate
        self.metrics.llm_bypass_rate = (
            (self.metrics.records_resolved_at_layer1 + 
              self.metrics.records_resolved_at_layer2 +
              self.metrics.records_resolved_at_layer3) / 
             max(self.metrics.total_records_processed, 1) * 100
        )
        
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
        
        batch_start = time.time()
        results = []
        
        # Phase 1: Layer 1 & Layer 2 on all records
        layer2_outputs = []
        layer2_summary = None
        
        for record in records:
            # Layer 1: Ingestion
            normalized, layer1_errors = self.layer1.normalize_record(record)
            if layer1_errors:
                result = ProcessingResult(
                    record_id=record.get("entity_id", "unknown"),
                    original_record=record,
                    final_record=normalized,
                    processing_stage=ProcessingStage.INGESTION_ERROR,
                    layer1_result={"errors": layer1_errors},
                    llm_bypassed=True,
                    llm_decision_audit=self._build_llm_decision_audit(
                        decision="not_required",
                        llm_bypassed=True,
                        gate_reason="Layer 1 validation failed",
                        layer3_skipped=False,
                        batch_context=None
                    )
                )
                results.append(result)
                self.metrics.records_resolved_at_layer1 += 1
                continue
            
            # Layer 2: Statistical Anomaly Detection
            enriched_l2, anomalies = self.layer2.process_record(normalized)
            layer2_outputs.append((record, normalized, enriched_l2, anomalies))
        
        # Compute batch aggregates from Layer 2
        batch_context = self._compute_batch_context(layer2_outputs)
        
        # Phase 2: Selective propagation to Layer 3
        for record, normalized, enriched_l2, anomalies in layer2_outputs:
            layer2_result = enriched_l2.get("_layer2_results", {})
            anomaly_severity = None
            if layer2_result.get("anomalies"):
                anomaly_severity = max(
                    [a["severity"] for a in layer2_result.get("anomalies", [])],
                    key=lambda x: ["low", "medium", "high", "critical"].index(x)
                )
            
            # SELECTIVE PROPAGATION LOGIC
            skip_layer3 = False
            skip_reason = ""
            
            if enable_selective_propagation:
                # Skip Layer 3 for records that clearly don't need it
                if not layer2_result.get("anomaly_detected"):
                    # No anomalies = likely doesn't need expensive ML scoring
                    skip_layer3 = True
                    skip_reason = "no_anomalies"
                elif anomaly_severity == "low":
                    # Low severity = skip ML scoring
                    skip_layer3 = True
                    skip_reason = "low_severity"
            
            # Process Layer 3 if needed
            if not skip_layer3:
                # Inject batch context into record for Layer 3
                enriched_l2["_batch_context"] = batch_context
                enriched_l3, layer3_results = self.layer3.process_record(enriched_l2)
                final_record = enriched_l3
                layer3_result = enriched_l3.get("_layer3_results", {})
            else:
                # Layer 3 skipped - construct minimal Layer 3 result
                final_record = enriched_l2
                final_record["_batch_context"] = batch_context
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
                self.metrics.records_resolved_at_layer3 += 1
            
            # Layer 4: Intelligent LLM Gating with batch context
            priority_score = layer3_result.get("predictions", {}).get("priority", {}).get("score", 0.0)
            requires_llm = layer3_result.get("requires_llm", False)
            
            result = ProcessingResult(
                record_id=record.get("entity_id", "unknown"),
                original_record=record,
                final_record=final_record,
                processing_stage=ProcessingStage.ML_FEATURE,
                layer2_result=layer2_result,
                layer3_result=layer3_result,
                llm_bypassed=True,
                confidence_score=layer3_result.get("predictions", {}).get("priority", {}).get("confidence", 0.5)
            )

            if skip_layer3:
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
            elif not requires_llm:
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="not_required",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=batch_context,
                    gate_reason="Layer 3 did not require LLM synthesis",
                    layer3_skipped=False,
                    cache_status="not_checked"
                )
            elif requires_llm and not self.model_router:
                result.llm_decision_audit = self._build_llm_decision_audit(
                    decision="gate_bypassed",
                    llm_bypassed=True,
                    priority_score=priority_score,
                    anomaly_severity=anomaly_severity,
                    batch_context=batch_context,
                    gate_reason="LLM required but no model router configured",
                    layer3_skipped=False,
                    cache_status="not_configured"
                )
            
            # LLM invocation with batch context awareness
            if requires_llm and self.model_router:
                should_invoke, gate_reason = self.llm_gate.should_invoke_llm(
                    final_record,
                    priority_score,
                    anomaly_severity,
                    batch_context  # Pass batch context for adaptive gating
                )
                
                if should_invoke:
                    prompt = self._generate_synthesis_prompt(final_record, layer3_result)
                    cache_status = "not_configured"
                    
                    try:
                        if self.cache:
                            cached = self.cache.retrieve(prompt, k=1)
                            if cached:
                                result.layer4_llm_response = cached[0].page_content
                                self.metrics.cache_hits += 1
                                cache_status = "hit"
                            else:
                                result.layer4_llm_response = self.model_router.generate(prompt)
                                self.metrics.cache_misses += 1
                                cache_status = "miss"
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self.metrics.cache_misses += 1
                        
                        result.processing_stage = ProcessingStage.LLM_REQUIRED
                        result.llm_bypassed = False
                        self.metrics.records_requiring_llm += 1
                    except Exception as e:
                        logger.error(f"LLM generation failed: {e}")
                        result.layer4_llm_response = f"LLM Error: {str(e)}"
                        cache_status = "error"
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision="invoked",
                        llm_bypassed=False,
                        priority_score=priority_score,
                        anomaly_severity=anomaly_severity,
                        batch_context=batch_context,
                        gate_reason=gate_reason,
                        layer3_skipped=False,
                        cache_status=cache_status,
                        prompt=prompt
                    )
                else:
                    result.llm_decision_audit = self._build_llm_decision_audit(
                        decision="gate_bypassed",
                        llm_bypassed=True,
                        priority_score=priority_score,
                        anomaly_severity=anomaly_severity,
                        batch_context=batch_context,
                        gate_reason=gate_reason,
                        layer3_skipped=False,
                        cache_status="not_checked"
                    )
            
            results.append(result)
            self.metrics.total_records_processed += 1
        
        # Update metrics
        batch_elapsed = (time.time() - batch_start) * 1000
        self.metrics.avg_processing_time_ms = batch_elapsed / max(len(results), 1)
        self.metrics.llm_bypass_rate = (
            (self.metrics.records_resolved_at_layer1 + 
             self.metrics.records_resolved_at_layer2 +
             self.metrics.records_resolved_at_layer3) / 
            max(self.metrics.total_records_processed, 1) * 100
        )
        
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
