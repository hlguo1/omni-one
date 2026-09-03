# Eval Report — Deterministic-First Pipeline
Generated: 2026-09-02T19:37:35.805802
Config: n=500 seed=42 anomaly_rate=0.12 duplicate_rate=0.05 budget=None

## Throughput
- Total: 38.89 ms for 500 records
- Avg per record: 0.078 ms
- Records/sec: 12857

## Latency Distribution (Layers 1-3 dominate)
- p50: 0.05 ms
- p95: 0.11 ms
- p99: 0.65 ms
- min/max: 0.04 / 2.09 ms
> Target: p50 <10ms, p99 <100ms — achieved via fast path (no LLM for 70-90%).

## LLM Bypass
- Naive calls: 500
- Actual calls: 8
- Bypass rate: 98.4%
- Expected: 70-90% bypass — **REVIEW**

## Cost
- Est naive (LLM everywhere): $0.0391
- Actual (gated): $0.0007
- Savings: $0.0384 (98.2%)
- Metrics: {"total_usd": 0.0007, "avg_per_1k_usd": 0.0014, "est_savings_vs_naive_llm_everywhere_usd": 0.04}

## Quality & Audit
- Layer 2 anomalies detected: 8
- Evidence bundles produced: 500 (100.0%)
- Cache: {"hits": 0, "misses": 8, "hit_rate": "0.0%"}
> Every record now carries an EvidenceBundle (layers 1→4 citations) — see docs/STRATEGY.md Pillar 2.

## Raw Metrics
```json
{
  "total_records": 500,
  "llm_bypass_rate": "98.4%",
  "llm_call_reduction": "98%",
  "records_by_stage": {
    "layer1_rejected": 0,
    "layer2_statistical": 0,
    "layer3_ml": 492,
    "layer4_llm": 8
  },
  "anomalies": {
    "critical": 4,
    "high": 4
  },
  "timing": {
    "avg_total_ms": "0.03ms",
    "layer1_avg_ms": "0.00ms",
    "layer2_avg_ms": "0.01ms",
    "layer3_avg_ms": "0.01ms",
    "layer4_avg_ms": "0.35ms"
  },
  "cache": {
    "hits": 0,
    "misses": 8,
    "hit_rate": "0.0%"
  },
  "cost": {
    "total_usd": 0.0007,
    "avg_per_1k_usd": 0.0014,
    "est_savings_vs_naive_llm_everywhere_usd": 0.04
  },
  "evidence": {
    "bundles_produced": 500
  }
}
```

## How to Reproduce
```bash
python -m omni_one.core.eval_harness --n 500 --seed 42
```
