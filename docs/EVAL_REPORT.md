# Eval Report — Deterministic-First Pipeline
Generated: 2026-09-02T21:01:42.379987
Config: n=500 seed=42 anomaly_rate=0.12 duplicate_rate=0.05 budget=None

## Throughput
- Total: 68.06 ms for 500 records
- Avg per record: 0.136 ms
- Records/sec: 7346

## Latency Distribution (Layers 1-3 dominate)
- p50: 0.09 ms
- p95: 0.2 ms
- p99: 1.45 ms
- min/max: 0.03 / 5.18 ms
> Target: p50 <10ms, p99 <100ms — achieved via fast path (no LLM for 70-90%).

## LLM Bypass
- Naive calls: 500
- Actual calls: 6
- Bypass rate: 98.8%
- Expected: 70-90% bypass — **REVIEW**

## Cost
- Est naive (LLM everywhere): $0.0391
- Actual (gated): $0.0005
- Savings: $0.0386 (98.7%)
- Metrics: {"total_usd": 0.0005, "avg_per_1k_usd": 0.0011, "est_savings_vs_naive_llm_everywhere_usd": 0.04}

## Quality & Audit
- Layer 2 anomalies detected: 6
- Evidence bundles produced: 481 (96.2%)
- Cache: {"hits": 0, "misses": 6, "hit_rate": "0.0%"}
> Every record now carries an EvidenceBundle (layers 1→4 citations) — see docs/STRATEGY.md Pillar 2.

## Raw Metrics
```json
{
  "total_records": 500,
  "llm_bypass_rate": "98.8%",
  "llm_call_reduction": "99%",
  "records_by_stage": {
    "layer1_rejected": 19,
    "layer2_statistical": 0,
    "layer3_ml": 475,
    "layer4_llm": 6
  },
  "anomalies": {
    "critical": 1,
    "high": 5
  },
  "timing": {
    "avg_total_ms": "0.07ms",
    "layer1_avg_ms": "0.00ms",
    "layer2_avg_ms": "0.01ms",
    "layer3_avg_ms": "0.03ms",
    "layer4_avg_ms": "1.85ms"
  },
  "cache": {
    "hits": 0,
    "misses": 6,
    "hit_rate": "0.0%"
  },
  "cost": {
    "total_usd": 0.0005,
    "avg_per_1k_usd": 0.0011,
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
