# Pipeline Analyze Close (PACK A)

> One call, every morning, offline, $0: run the 4-layer pipeline over a batch,
> get a verdict, anomalies with evidence cites, a $0 cost ledger, and 3
> operator actions — as `close.json` + `close.csv` + `evidence.jsonl`.

## 1. What / why

Operators drowning in pipeline telemetry don't need another dashboard. They
need to **close** the pipeline the way a shop owner closes the day:

1. **Did every record actually process?** — `processed` vs `rejected`, plus a
   per-stage split from the pipeline metrics (Layer 1 rejects, Layer 2
   statistical, Layer 3 ML, Layer 4 LLM).
2. **What is anomalous RIGHT NOW?** — spike values, negative-sentiment text,
   and anything Layer 2 flags, each row carrying an evidence citation.
3. **Where is the proof?** — every result carries `evidence_steps`
   (`layer` / `signal` / `citation`); the close ships the first 6 as
   `evidence_sample` and the full trail as `evidence.jsonl`.
4. **Where is money going?** — a per-record `cost_ledger` plus a `__total__`
   line. Mock runs are exactly `$0.00`.
5. **What do I do next?** — `do_today[3]`: review the top anomaly, check
   rejects, confirm spend.

Design rules:

- **Deterministic.** No randomness; the only wall-clock value in any output
  is `meta.generated_at`. Same records + same seed → same verdict, same KPIs
  (up to sub-millisecond `avg_ms` jitter), same anomalies.
- **Offline.** Layer 4 never leaves the laptop: the pack injects
  `MockModelRouter`, whose `generate()` returns `"[MOCK]"`. No API keys, no
  sockets, no litellm calls.
- **No phantom alerts.** Every anomaly cites the evidence step that flagged
  it (`evidence_cite`).
- **Central wiring later.** This pack does NOT touch `cli.py`, `client.py`,
  `api/`, or `mcp_server.py`. Section 6 documents the intended commands as
  placeholders only.

## 2. Record schema

Input records are the standard pipeline records
(`src/omni_one/core/data_processing_pipeline.py`, validated by Layer 1):

| Field       | Type                          | Required | Notes                                              |
| ----------- | ----------------------------- | -------- | -------------------------------------------------- |
| `timestamp` | ISO-8601 str / epoch sec / ms | yes      | Must parse; unparsable → `ingestion_error` reject  |
| `source`    | non-empty string              | yes      | e.g. `sensor`, `review`, `salesforce`              |
| `entity_id` | non-empty string              | yes      | Distinct ids avoid the dedup filter                |
| `value`     | number / string / list / dict | no       | Numbers feed the spike heuristic; text feeds sentiment |
| `metadata`  | dict                          | no       | Passed through to Layer 3 features                 |
| `tags`      | list / dict                   | no       | Passed through                                     |

Minimal healthy record:

```python
{"timestamp": "2026-01-05T09:00:00", "source": "sensor",
 "entity_id": "sensor-A-00", "value": 101, "metadata": {"unit": "kwh"}}
```

Quick start:

```python
from omni_one.packs.pipeline_close import (
    DEMO_RECORDS, build_pipeline_close, close_to_csv, write_close_bundle)

close = build_pipeline_close(DEMO_RECORDS())   # offline, $0, deterministic
print(close["verdict"], close["kpis"])          # needs review {...}
paths = write_close_bundle(close, "./close_pipeline")
# {"close.json": ..., "close.csv": ..., "evidence.jsonl": ...}
```

## 3. Close schema

`build_pipeline_close(records, seed=42) -> dict` returns:

| Key               | Contents                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `pack` / `pack_version` / `seed` | Identity + audit seed                                          |
| `meta`            | `{generated_at, records, seed, pipeline}` — pipeline is `get_metrics_summary()` |
| `kpis`            | `{processed, rejected, bypass_rate, avg_ms, cost_usd}`                    |
| `results`         | Per-record `{record_id, stage, llm_bypassed, latency_ms, cost_usd, model_used, cached, evidence_steps[], signals[]}` |
| `anomalies[]`     | `{record_id, stage, signals[], evidence_cite, latency_ms}`, sorted by `record_id` |
| `anomaly_ratio`   | `len(anomalies) / max(processed, 1)`, rounded to 4 decimals               |
| `verdict`         | `healthy` \| `needs review` \| `critical` (Section 4)                     |
| `evidence_sample` | First 6 evidence steps across results (headline proof)                   |
| `cost_ledger`     | Per-record `{record_id, model_used, cost_usd, cached}` + `__total__` line |
| `do_today[3]`     | Review top anomaly → check rejects → confirm spend (Section 5)           |
| `notes`           | `"offline mock close; Layer 4 never leaves the laptop."`                 |

`close_to_csv(close) -> str` renders three `csv`-parseable sections:
`metric,value` rows → anomaly rows → evidence rows.
`write_close_bundle(close, out_dir)` writes `close.json` (full close),
`close.csv` (the CSV), and `evidence.jsonl` (one JSON object per evidence
step across **all** results, `record_id` injected per line), returning the
3 paths. Empty closes still yield a non-empty `evidence.jsonl` via a single
`__meta__` marker line.

## 4. Verdict bands

`anomaly_ratio = len(anomalies) / max(processed, 1)`:

| Band           | Condition              | Meaning                                  |
| -------------- | ---------------------- | ---------------------------------------- |
| `healthy`      | ratio == 0             | No anomalies — nothing to review.        |
| `needs review` | 0 < ratio < 0.40       | A few alerts — look today (golden: 0.25).|
| `critical`     | ratio >= 0.40          | Pipeline on fire — stop and triage.      |

Empty input (`[]` or `None`) → `processed == 0`, ratio `0.0`, `healthy`, no
crash. A total `process_batch` exception still returns a well-formed close
with `verdict == "critical"` and the error under `meta.pipeline.error`.

## 5. `do_today[3]` (always exactly 3)

1. **Review top anomaly** — `Review top anomaly <id> (<stage>): <signal>
   [<evidence_cite>]`, or `No anomalies — nothing to review; …` when clean.
2. **Check rejects** — `<n> rejected record(s) … fix schema, re-run`, or
   `No rejected records — ingestion clean (8/8 valid).`
3. **Confirm spend** — `Nothing to spend — mock run cost $0.0000 (LLM bypass
   …%, Layer 4 never left the laptop).`

## 6. CLI / API placeholders (wiring later — NOT implemented here)

Central wiring (`cli.py`, `client.py`, `api/`, `mcp_server.py`) happens in a
later step. Intended surface, documented so the wiring PR has a contract to
hit:

```bash
# Intended CLI (placeholder — not wired yet):
omni-one pipeline-close --seed 42 --out ./close_pipeline
omni-one pipeline-close --records ./events.json --out ./close_pipeline
```

```http
POST /api/v1/pipeline/close
Content-Type: application/json

{"records": [ {"timestamp": "...", "source": "sensor", "entity_id": "..."} ],
 "seed": 42}
→ 200 {"verdict": "needs review", "kpis": {...}, "anomalies": [...], ...}
```

MCP sketch (also later): tool `pipeline.close` with `{records, seed}` input
returning the close dict; bundle files remain on local disk by design
(private-by-default, plane-wifi friendly).

## 7. Golden numbers (default `DEMO_RECORDS(seed=42)`)

`DEMO_RECORDS()` builds 8 deterministic records (fixed `2026-01-05` morning
timestamps, 5-minute spacing, distinct entity ids): 6 normal sensor readings
(~100 kWh, ±5 seed jitter via pure arithmetic), `sensor-A-spike`
(`9999.0`, ~100× median), and `review-neg-01`
(`"Terrible awful service, complete failure, hate it, worst experience
ever, refund now"`).

| KPI / field      | Golden value | Why stable                                              |
| ---------------- | ------------ | ------------------------------------------------------- |
| `processed`      | 8            | All 8 pass Layer-1 validation                           |
| `rejected`       | 0            | No schema violations, no dedup hits                     |
| `bypass_rate`    | 100.0        | Layer 3 requires no LLM; gate never invoked             |
| `cost_usd`       | 0.0          | Mock router costs 0.0; no real LLM calls                |
| `anomalies`      | 2            | Spike heuristic + sentiment heuristic (Layer 2 quiet)   |
| `anomaly_ratio`  | 0.25         | 2 / 8                                                   |
| `verdict`        | `needs review` | 0 < 0.25 < 0.40                                       |
| `evidence_sample`| 6 steps      | First 6 across results                                  |
| `do_today`       | 3 actions    | Top anomaly = `review-neg-01` (sorted by `record_id`)   |

Note: `avg_ms` is intentionally excluded from golden equality — it measures
real (sub-millisecond) wall clock. Tests bound its run-to-run jitter instead.

## 8. Evidence & cost explanation

**Evidence.** Each pipeline result already builds 4 evidence steps
(`_finalize_evidence`): Layer 1 validation hash, Layer 2 anomaly / clean
bill, Layer 3 priority (or skip reason), Layer 4 decision / bypass note. The
pack flattens these to `{layer, signal, citation}` per result, cites the
first step of a flagged record as `evidence_cite`, and ships the first 6
steps as `evidence_sample` (full trail → `evidence.jsonl`).

**Anomaly signals.** Three deterministic sources, in order:
`layer2:<type> severity=<sev> score=<s>` (pipeline's own stats),
`value_spike:<v>_vs_median_<m>_threshold_<t>` (numbers ≥
`max(5×median, median+100)`), `negative_sentiment:<n> keywords(…)` (text
matching `NEGATIVE_KEYWORDS`), plus a corroborating
`layer3:sentiment=<v> confidence=<c>` when Layer 3 agrees.

**Cost.** The pipeline's `_build_cost_ledger` prices Layer-4 prompts through
the router — but the mock router's `estimate_cost_for_model()` returns `0.0`
and `generate()` returns `"[MOCK]"` without any network call, so every
ledger line and the `__total__` line read `cost_usd: 0.0`, `model_used:
mock/balanced` (or `none-local` when Layer 4 was bypassed). Swap in the real
`ModelRouter` + keys later and the same ledger code prices real calls.

## 9. Files & tests

- `src/omni_one/packs/pipeline_close.py` — the pack (mock router, demo
  fixture, detectors, close/CSV/bundle builders).
- `tests/unit/test_pipeline_close.py` — 10 tests: golden metrics, spike +
  sentiment anomalies, detector units, evidence on every result, $0 ledger,
  idempotency, empty-input health, rejects, 3-file bundle, CSV sections,
  offline mock contract.
- Verify: `python3 -m compileall -q src/omni_one/packs/pipeline_close.py
  && PYTHONPATH=src python3 -m pytest tests/unit/test_pipeline_close.py -q`
  (green required before any wiring PR).
