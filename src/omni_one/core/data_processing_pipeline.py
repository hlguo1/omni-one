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
                         anomaly_severity: Optional[str] = None) -> Tuple[bool, str]:
        """
        Determine if LLM invocation is justified.
        
        Returns:
            (should_invoke, reason)
        """
        # Critical or high priority = always invoke
        if priority_score > 0.6 or anomaly_severity in ["critical", "high"]:
            return True, f"High priority ({priority_score:.2f}) or critical anomaly"
        
        # Medium priority = check cache first
        if priority_score > 0.4:
            if self.cache and self._check_cache(record):
                return False, "Similar record in cache"
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
    The complete multi-layered data processing pipeline.
    
    Key benefits:
    - Handles high-velocity data efficiently
    - Minimizes LLM calls through intelligent gating
    - Provides maximum transparency (each layer's results visible)
    - Scales to 1000s events/sec with <10ms latency (Layer 1-3)
    - Only complex cases escalate to LLM
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
            final_record=record
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
            # Check if LLM gate approves
            should_invoke, reason = self.llm_gate.should_invoke_llm(
                enriched_l3,
                priority_score,
                result.layer2_result.get("anomalies", [{}])[0].get("severity") if result.layer2_result.get("anomalies") else None
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
