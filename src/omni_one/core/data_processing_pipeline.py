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

import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from layer_1_ingestion import Layer1Ingestion, IngestionMetrics
from layer_2_statistical import Layer2StatisticalProcessing
from layer_3_ml_features import Layer3MLFeatures
from model_router import ModelRouter  # Our existing LLM router
from cache import SemanticCache

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


class IntelligentLLMGate:
    """
    Intelligent gating for LLM invocations.
    Decides whether to call LLM based on confidence, priority, cache, etc.
    """
    
    def __init__(self, model_router: ModelRouter, cache: SemanticCache = None):
        self.model_router = model_router
        self.cache = cache
        self.llm_call_history = []  # Track LLM calls for analytics
    
    def should_invoke_llm(self, 
                         record: Dict[str, Any],
                         priority_score: float,
                         anomaly_severity: Optional[str] = None,
                         batch_context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Determine if LLM invocation is justified.
        
        Args:
            record: The processed record
            priority_score: Priority score from Layer 3
            anomaly_severity: Anomaly severity from Layer 2
            batch_context: Aggregate statistics from batch (for contextual gating)
        
        Returns:
            (should_invoke, reason)
        """
        # Critical or high priority = always invoke
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
        response = self.model_router.generate(prompt)
        self.llm_call_history.append({
            "timestamp": datetime.now(),
            "record_id": record.get("entity_id"),
            "response": response
        })
        return response


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
    
    def __init__(self, model_router: Optional[ModelRouter] = None, cache: Optional[SemanticCache] = None):
        self.layer1 = Layer1Ingestion()
        self.layer2 = Layer2StatisticalProcessing()
        self.layer3 = Layer3MLFeatures()
        self.model_router = model_router
        self.cache = cache
        self.llm_gate = IntelligentLLMGate(model_router, cache) if model_router else None
        
        self.metrics = PipelineMetrics()
    
    def _generate_record_id(self, record: Dict[str, Any]) -> str:
        """Generate unique ID for tracking."""
        entity_id = record.get("entity_id", "unknown")
        timestamp = record.get("timestamp", "")
        return f"{entity_id}_{timestamp}"
    
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
        if not requires_llm or not self.model_router:
            result.processing_stage = ProcessingStage.ML_FEATURE
            result.llm_bypassed = True
            self.metrics.records_resolved_at_layer3 += 1
        else:
            # Check if LLM gate approves (batch_context=None for standard processing)
            should_invoke, reason = self.llm_gate.should_invoke_llm(
                enriched_l3,
                priority_score,
                result.layer2_result.get("anomalies", [{}])[0].get("severity") if result.layer2_result.get("anomalies") else None,
                batch_context=None
            )
            
            if should_invoke:
                # Generate prompt from enriched record
                prompt = self._generate_synthesis_prompt(enriched_l3, layer3_results)
                
                start_layer4 = time.time()
                try:
                    # Check cache first
                    if self.cache:
                        cached = self.cache.retrieve(prompt, k=1)
                        if cached:
                            result.layer4_llm_response = cached[0].page_content
                            self.metrics.cache_hits += 1
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self.metrics.cache_misses += 1
                    else:
                        result.layer4_llm_response = self.model_router.generate(prompt)
                        self.metrics.cache_misses += 1
                    
                    result.layer4_time_ms = (time.time() - start_layer4) * 1000
                    result.processing_stage = ProcessingStage.LLM_REQUIRED
                    self.metrics.records_requiring_llm += 1
                except Exception as e:
                    logger.error(f"LLM generation failed: {e}")
                    result.layer4_llm_response = f"LLM Error: {str(e)}"
            else:
                result.processing_stage = ProcessingStage.ML_FEATURE
                result.llm_bypassed = True
                self.metrics.records_resolved_at_layer3 += 1
        
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
                    llm_bypassed=True
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
                    
                    try:
                        if self.cache:
                            cached = self.cache.retrieve(prompt, k=1)
                            if cached:
                                result.layer4_llm_response = cached[0].page_content
                                self.metrics.cache_hits += 1
                            else:
                                result.layer4_llm_response = self.model_router.generate(prompt)
                                self.metrics.cache_misses += 1
                        else:
                            result.layer4_llm_response = self.model_router.generate(prompt)
                            self.metrics.cache_misses += 1
                        
                        result.processing_stage = ProcessingStage.LLM_REQUIRED
                        result.llm_bypassed = False
                        self.metrics.records_requiring_llm += 1
                    except Exception as e:
                        logger.error(f"LLM generation failed: {e}")
                        result.layer4_llm_response = f"LLM Error: {str(e)}"
            
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
        """Get human-readable metrics summary."""
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
