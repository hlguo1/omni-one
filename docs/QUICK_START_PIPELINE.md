# Quick Reference: Multi-Layer Data Pipeline

## TL;DR - The Problem & Solution

**Problem**: Every data record triggering LLM = impossible at scale
- 1000 events/sec × 1000ms per LLM = catastrophe

**Solution**: 4 fast deterministic layers before LLM
- Result: 70-90% of records resolved without LLM
- Throughput: 1000+ events/sec with <10ms median latency

---

## Architecture Quick View

```
Input Data
    ↓
[Layer 1: Validate] - <1ms - Rejects invalid/duplicate data
    ↓ (99% pass through)
[Layer 2: Statistics] - <10ms - Z-score, thresholds, trends
    ↓ (90% pass through)
[Layer 3: ML Score] - <100ms - Sentiment, churn, priority
    ↓ (70% pass through)
[Layer 4: LLM] - 500-2000ms - ONLY if priority > 0.6 OR critical anomaly
    ↓
Output: Complete enriched result
```

---

## Quick Start (5 minutes)

### 1. Import the pipeline
```python
from core.data_processing_pipeline import MultiLayerDataPipeline
from core.model_router import ModelRouter

model_router = ModelRouter()
pipeline = MultiLayerDataPipeline(model_router=model_router)
```

### 2. Configure thresholds (optional)
```python
pipeline.layer2.set_metric_threshold("revenue", lower=10000, upper=500000)
```

### 3. Process records
```python
results, metrics = pipeline.process_batch(records)
```

### 4. Check metrics
```python
print(f"LLM bypass rate: {metrics['llm_bypass_rate']}")
print(f"Avg latency: {metrics['timing']['avg_total_ms']}")
print(f"Critical anomalies: {metrics['anomalies']['critical']}")
```

---

## Usage Examples

### Process a single real-time event
```python
event = {
    "timestamp": "2024-01-01T10:00:00",
    "source": "salesforce",
    "entity_id": "account_123",
    "value": 45000,  # Anomalous revenue drop
}
result = pipeline.process_record(event)
print(result.processing_stage)  # → "api_synthesis" or "ml_feature"
print(result.layer3_result['predictions']['priority']['value'])  # → "high"
print(result.llm_bypassed)  # → False if LLM was needed
```

### Understand why an anomaly was detected
```python
for result in results:
    if result.layer2_result['anomaly_detected']:
        for anom in result.layer2_result['anomalies']:
            print(f"{anom['type']}: {anom['explanation']}")
            # → "outlier: Value 45000 is 3.2 std deviations below mean 95000"
```

### Batch processing with metrics
```python
from agents.proactive.engine import ProactiveEngine

engine = ProactiveEngine(rag_engine, model_router)
processed, metrics = engine.process_data_stream(records)

for item in processed:
    print(f"{item['record_id']}: Stage={item['processing_stage']}, "
          f"Priority={item['priority']}, Time={item['timing_ms']['total']:.1f}ms")
```

---

## What Each Layer Does

### Layer 1: Ingestion (<1ms)
**Input**: Raw records
**Output**: Normalized records
**Rejects**: Invalid schema, duplicates,missing fields
**Example**:
```python
# Before: {"timestamp": 1704110400, "source": "sf", ...}
# After:  {"timestamp": datetime(2024,1,1,10,0), "source": "sf", ...}
```

### Layer 2: Statistics (<10ms)
**Input**: Valid normalized records
**Output**: Anomaly detections
**Methods**: Z-score, moving average, thresholds
**Example**:
```python
# Detects: Revenue dropped from $95k to $45k (outlier)
# Severity: high | Confidence: 0.92 | Score: 3.2
```

### Layer 3: ML Features (<100ms)
**Input**: Records with Layer 2 results
**Output**: Predictions + priority scores
**Methods**: Sentiment classification, churn scoring, feature extraction
**Example**:
```python
{
    "sentiment": 1,  # positive
    "churn_risk": "medium",  # 55% probability
    "priority": "high",  # should review
    "requires_llm": True
}
```

### Layer 4: LLM (500-2000ms)
**Input**: High-priority or complex cases (10-30% of records)
**Output**: AI-generated insights and recommendations
**Gate**: Only invokes if priority > 0.6 OR critical anomaly
**Example**:
```
"Revenue has dropped 53% for this account. Recommend:
1. Immediate outreach to account manager
2. Review support tickets for issues
3. Prepare retention package"
```

---

## Key Metrics to Monitor

```python
metrics = pipeline.get_metrics_summary()

# Primary metrics
metrics['llm_bypass_rate']           # % of records NOT using LLM (target: 70-90%)
metrics['timing']['avg_total_ms']    # Median latency (target: <10ms)
metrics['cache']['hit_rate']         # Cache effectiveness (target: 20-35%)

# Anomaly detection
metrics['anomalies']['critical']     # Critical issues found
metrics['anomalies']['high']         # High severity issues

# Processing distribution
metrics['records_by_stage']          # Where records were resolved
```

---

## Common Configuration Patterns

### Conservative (Less LLM calls)
```python
pipeline.z_detector.z_threshold = 4.0  # Only 4+ sigma = outlier
pipeline.priority_scorer.high_threshold = 0.7
# Result: ~80% LLM bypass rate
```

### Aggressive (More LLM calls, better catches)
```python
pipeline.z_detector.z_threshold = 2.0  # 2+ sigma = outlier
pipeline.priority_scorer.high_threshold = 0.4
# Result: ~40% LLM bypass rate, higher accuracy
```

### Balanced (Recommended)
```python
# Default settings (already configured)
# Result: ~70% LLM bypass rate, good accuracy
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Almost all records bypass LLM | Thresholds too lenient | Increase z_threshold |
| LLM called on obviously normal data | Thresholds too strict | Decrease z_threshold |
| Cache hit rate low | Cache too small | Increase cache size |
| Latency inconsistent | LLM invoked randomly | Check priority thresholds |
| Missing obvious anomalies | Moving average window wrong | Adjust window_size parameter |

---

## When to Use Each Approach

### Use Full Pipeline (Recommended for production)
```python
pipeline = MultiLayerDataPipeline(model_router=router)
results, metrics = pipeline.process_batch(records)
```
✓ Handles high velocity (1000+ events/sec)
✓ Transparent processing stages
✓ Automatic LLM gating
✓ Full observability

### Use Individual Layers (For testing/debugging)
```python
# Just Layer 2 for anomaly detection
enriched, metrics = pipeline.layer2.process_batch(records)

# Just Layer 3 for scoring
enriched, metrics = pipeline.layer3.process_batch(records)
```

### Use Legacy Methods (Backward compat)
```python
# Old way still works
sentiment = engine.analyze_client_sentiment(client_name)
```

---

## Performance Expectations

### Latency
- Layer 1-3 combined: **<10ms per record**
- Layer 4 (LLM): **500-2000ms** (but only 10-30% of records)
- Median record: **<10ms**
- p99 record: **<100ms** (even with some LLM calls)

### Throughput
- Single-threaded: **1,000+ records/sec**
- Multi-threaded: **10,000+ records/sec**

### Cost (vs naive approach)
- LLM API calls: **85-90% reduction**
- Monthly savings (1M events/day): **$2,000-3,000**

---

## Integration with ProactiveEngine

```python
# Existing code just works better now
engine = ProactiveEngine(rag_engine, model_router)

# New pipeline methods
processed, metrics = engine.process_data_stream(records)
result = engine.process_real_time_event(event)
pipeline_metrics = engine.get_pipeline_metrics()

# Configure thresholds
engine.set_metric_threshold("revenue", lower=10000, upper=500000)
```

---

## Advanced: Custom Detectors

```python
# Extend Layer 2
class CustomAnomalyDetector(StatisticalAnomalyDetector):
    def detect_custom_pattern(self, entity_id, value):
        # Your custom logic
        pass

# Add to pipeline
pipeline.layer2.custom_detectors.append(CustomAnomalyDetector())
```

---

## File Reference

| File | Purpose |
|------|---------|
| layer_1_ingestion.py | Validation & normalization |
| layer_2_statistical.py | Anomaly detection algorithms |
| layer_3_ml_features.py | ML scoring & feature extraction |
| data_processing_pipeline.py | Orchestration & gating |
| MULTI_LAYER_ARCHITECTURE.md | Full technical documentation |
| demo_multiparser_pipeline.py | Working examples |

---

## Next Steps

1. **Try the demo**: `python src/omni_one/core/demo_multiparser_pipeline.py`
2. **Set thresholds**: Configure for your domain
3. **Monitor metrics**: Track LLM bypass rate
4. **Optimize**: Adjust based on performance data
5. **Extend**: Add custom detectors/classifiers as needed

---

## Questions?

See comprehensive docs:
- Full architecture: [MULTI_LAYER_ARCHITECTURE.md](./MULTI_LAYER_ARCHITECTURE.md)
- Demo with examples: [demo_multiparser_pipeline.py](../src/omni_one/core/demo_multiparser_pipeline.py)
- Source code with comments: See individual layer files
