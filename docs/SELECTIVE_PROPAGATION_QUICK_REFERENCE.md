# Quick Reference: Selective Propagation & Batch Enrichment

## Usage Examples

### Basic Usage: Optimized Batch Processing
```python
from data_processing_pipeline import MultiLayerDataPipeline

# Initialize pipeline
pipeline = MultiLayerDataPipeline(model_router=your_router, cache=your_cache)

# Process batch with optimizations enabled (recommended)
results, metrics = pipeline.process_batch_optimized(
    records=your_records,
    enable_selective_propagation=True  # Enable layer skipping (default)
)

# Access results
for result in results:
    print(f"Record {result.record_id}:")
    print(f"  Processing Stage: {result.processing_stage}")
    print(f"  LLM Bypassed: {result.llm_bypassed}")
    
    # Check if Layer 3 was skipped
    layer3_results = result.final_record.get("_layer3_results", {})
    if layer3_results.get("skipped"):
        print(f"  Layer 3 Skipped: {layer3_results['skip_reason']}")
    
    # See batch context
    batch_ctx = result.final_record.get("_batch_context", {})
    print(f"  Batch Anomaly Rate: {batch_ctx.get('anomaly_rate', 0):.1%}")
```

### Backward Compatible: Original Behavior
```python
# Old code still works - processes all records through all layers
results, metrics = pipeline.process_batch(your_records)
```

### Single Record Processing (Unchanged)
```python
# Single record still goes through full pipeline
result = pipeline.process_record(single_record)
```

### Disable Optimizations If Needed
```python
# Process batch but skip all optimizations
results, metrics = pipeline.process_batch_optimized(
    records=your_records,
    enable_selective_propagation=False  # Skip gating optimizations
)
```

## Understanding the Results

### When Layer 3 is Skipped
```python
layer3_results = {
    "predictions": {
        "priority": {
            "value": "low",           # Auto-generated
            "score": 0.2,             # Auto-generated (~0.2)
            "confidence": 0.8,        # High confidence (wasn't processed)
            "reasons": ["no_anomalies - layer3_skipped"]
        }
    },
    "requires_llm": False,
    "skipped": True,                  # ←← Key marker
    "skip_reason": "no_anomalies"     # ←← Why it was skipped
}
```

### When Layer 3 is NOT Skipped
```python
layer3_results = {
    "predictions": {
        "priority": {
            "value": "high",          # Real ML prediction
            "score": 0.78,            # Real score
            "confidence": 0.92,       # Model confidence
            "reasons": ["high_anomaly_detected", "negative_sentiment", ...]
        },
        "sentiment": {...},
        "churn_risk": {...}
    },
    "requires_llm": True,
    # No "skipped" key or it's False
}
```

### Batch Context Available on Every Record
```python
batch_context = result.final_record.get("_batch_context", {})

print(f"Batch Size: {batch_context['batch_size']}")
print(f"Anomaly Rate: {batch_context['anomaly_rate']:.1%}")
print(f"Clean Rate: {batch_context['clean_rate']:.1%}")
print(f"Critical Anomalies: {batch_context['critical_count']}")
print(f"High Anomalies: {batch_context['high_count']}")
print(f"Anomaly Types: {batch_context['anomaly_types']}")
```

## Performance Metrics

### Check Metrics After Batch Processing
```python
results, metrics = pipeline.process_batch_optimized(records)

print(f"Total Records Processed: {metrics.total_records_processed}")
print(f"LLM Bypass Rate: {metrics.llm_bypass_rate:.1f}%")
print(f"Records by Stage:")
print(f"  Layer 1 Rejected: {metrics.records_resolved_at_layer1}")
print(f"  Layer 2 Anomalies: {metrics.records_resolved_at_layer2}")  
print(f"  Layer 3 Complete: {metrics.records_resolved_at_layer3}")
print(f"  Layer 4 LLM: {metrics.records_requiring_llm}")

print(f"\nTiming:")
print(f"  Avg Total: {metrics.avg_processing_time_ms:.2f}ms")
print(f"  Cache Hit Rate: {metrics.cache_hits / (metrics.cache_hits + metrics.cache_misses):.1%}")
```

### Use get_metrics_summary() for Pretty Output
```python
summary = pipeline.get_metrics_summary()
import pprint
pprint.pprint(summary)
```

## Decision Tree: Will Layer 3 Be Skipped?

```
Record enters Layer 2 (Statistical Anomaly Detection)
    ↓
    Has anomalies detected?
    ├─ NO  → SKIP LAYER 3 ✓
    └─ YES → Check severity
            ├─ LOW severity → SKIP LAYER 3 ✓
            └─ MEDIUM/HIGH/CRITICAL → Process Layer 3 ✓
```

## LLM Gating Logic with Batch Context

```
Layer 4 Intelligent LLM Gate receives:
  - priority_score: 0.0 to 1.0 from Layer 3
  - anomaly_severity: "low" | "medium" | "high" | "critical" from Layer 2
  - batch_context: {"anomaly_rate": 0.15, "clean_rate": 0.85, ...}

Decision:
  1. If priority_score > 0.6 OR anomaly_severity in [high, critical]
     → INVOKE LLM (highest confidence signals)
  
  2. If priority_score > 0.4 AND priority_score <= 0.6
     → Check batch context:
        If batch is clean (anomaly_rate < 0.1) AND priority_score < 0.55
        → SKIP LLM (clean batch context suggests not needed)
        Else → INVOKE LLM
  
  3. If priority_score <= 0.4
     → SKIP LLM (low confidence)
```

## Common Scenarios

### Scenario 1: Clean Batch Arrives
- All 100 records: error-free, no anomalies
- Result: 100% skip Layer 3 (100 records × 70ms = 7 seconds saved)
- LLM calls: Near 0% (batch context shows clean)
- Batch context: anomaly_rate=0%, clean_rate=100%

### Scenario 2: One Problem Record in Clean Batch
- 99 records: clean, 1 record: critical anomaly
- Result: 99 skip Layer 3, 1 processes full pipeline
- LLM calls: 1-2% instead of 5% (batch context helps skip borderline)
- Batch context: anomaly_rate=1%, clean_rate=99%

### Scenario 3: Mixed Batch
- 60 clean, 20 low-severity anomaly, 20 high-severity anomaly
- Result: Layer 3 skipped for 80 records
- LLM calls: ~10-15% (all high-severity + some medium)
- Batch context: anomaly_rate=40%, critical/high=20%

## Troubleshooting

### Check if Layer 3 was skipped
```python
if result.final_record.get("_layer3_results", {}).get("skipped"):
    skip_reason = result.final_record["_layer3_results"]["skip_reason"]
    print(f"Layer 3 skipped due to: {skip_reason}")
else:
    print("Layer 3 was processed")
```

### See full record enrichment path
```python
print("Layer 1 Results:", result.layer1_result)
print("Layer 2 Results:", result.layer2_result)
print("Layer 3 Results:", result.layer3_result)
print("Layer 4 Results:", result.layer4_llm_response)
print("Batch Context:", result.final_record.get("_batch_context"))
```

### Compare performance
```python
# Standard processing
results_std, metrics_std = pipeline.process_batch(records)
time_std = metrics_std.avg_processing_time_ms * len(records)

# Optimized processing  
results_opt, metrics_opt = pipeline.process_batch_optimized(records)
time_opt = metrics_opt.avg_processing_time_ms * len(records)

improvement = (time_std - time_opt) / time_std * 100
print(f"Optimization Improvement: {improvement:.1f}%")
```

## Tips for Best Results

1. **Use process_batch_optimized() for batch processing**
   - Single records use process_record() (no optimization needed)

2. **Monitor skip rates**
   - Check if Layer 3 is being skipped as expected
   - Investigate if skip_reason is unexpected

3. **Tune batch size**
   - Larger batches give better batch context statistics
   - 100-500 records per batch is optimal

4. **Enable batch context awareness**
   - Set enable_selective_propagation=True (default)
   - Only disable if troubleshooting issues

5. **Track metrics**
   - Watch llm_bypass_rate trend over time
   - Monitor cache hit rates
   - Alert if skip rates change unexpectedly

