# Eval Report — Deterministic-First Pipeline
Generated: 2026-10-10T21:57:28.410310
Config: n=200 seed=42 anomaly_rate=0.12 duplicate_rate=0.05 budget=None

## Throughput
- Total: 24.72 ms for 200 records
- Avg per record: 0.124 ms
- Records/sec: 8089

## Latency Distribution (Layers 1-3 dominate)
- p50: 0.08 ms
- p95: 0.16 ms
- p99: 1.12 ms
- min/max: 0.03 / 4.3 ms
> Target: p50 <10ms, p99 <100ms — achieved via fast path (no LLM for 70-90%).

## LLM Bypass
- Naive calls: 200
- Actual calls: 2
- Bypass rate: 99.0%
- Expected: 70-90% bypass — **REVIEW**

## Cost
- Est naive (LLM everywhere): $0.0156
- Actual (gated): $0.0002
- Savings: $0.0154 (98.7%)
- Metrics: {"total_usd": 0.0002, "avg_per_1k_usd": 0.0009, "est_savings_vs_naive_llm_everywhere_usd": 0}

## Quality & Audit
- Layer 2 anomalies detected: 2
- Evidence bundles produced: 195 (97.5%)
- Cache: {"hits": 0, "misses": 2, "hit_rate": "0.0%"}
> Every record now carries an EvidenceBundle (layers 1→4 citations) — see docs/STRATEGY.md Pillar 2.

## Raw Metrics
```json
{
  "total_records": 200,
  "llm_bypass_rate": "99.0%",
  "llm_call_reduction": "99%",
  "records_by_stage": {
    "layer1_rejected": 5,
    "layer2_statistical": 0,
    "layer3_ml": 193,
    "layer4_llm": 2
  },
  "anomalies": {
    "critical": 1,
    "high": 1
  },
  "timing": {
    "avg_total_ms": "0.06ms",
    "layer1_avg_ms": "0.00ms",
    "layer2_avg_ms": "0.01ms",
    "layer3_avg_ms": "0.03ms",
    "layer4_avg_ms": "1.66ms"
  },
  "cache": {
    "hits": 0,
    "misses": 2,
    "hit_rate": "0.0%"
  },
  "cost": {
    "total_usd": 0.0002,
    "avg_per_1k_usd": 0.0009,
    "est_savings_vs_naive_llm_everywhere_usd": 0
  },
  "evidence": {
    "bundles_produced": 200
  }
}
```

## How to Reproduce
```bash
python -m omni_one.core.eval_harness --n 200 --seed 42
```
