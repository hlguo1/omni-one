"""
Pipeline Analyze Close (PACK A) — the 5-minute ritual for pipeline operators.
=============================================================================

Operators don't want "another dashboard". They want to CLOSE the pipeline:

  1. Did every record actually process? (processed vs rejected, per-stage split)
  2. What is anomalous RIGHT NOW and needs a human? (spikes, toxic text, ...)
  3. Where is the proof? (evidence steps with layer citations on every result)
  4. Where is money going? (per-record cost ledger, offline $0 mock by default)
  5. Hand the on-call something. (close.json + close.csv + evidence.jsonl)

One call, every morning, offline, $0::

    from omni_one.packs.pipeline_close import (
        DEMO_RECORDS, build_pipeline_close, close_to_csv, write_close_bundle,
    )

    close = build_pipeline_close(DEMO_RECORDS())
    paths = write_close_bundle(close, "./close_pipeline_2026-10-11")
    # -> close.json + close.csv + evidence.jsonl

Design rules (why operators trust it):

- Deterministic. No randomness; the only wall-clock value in outputs is
  ``meta.generated_at``. Same records + same seed -> same verdict/KPIs
  (up to sub-ms jitter in ``avg_ms``), same anomalies, same evidence.
- Offline. Layer 4 never leaves the laptop: this pack injects a mock
  router whose ``generate()`` returns ``"[MOCK]"``. No keys, no network,
  cost always ``0.0`` in mock runs.
- Every anomaly cites evidence (``evidence_cite``) — no phantom alerts.
- Idempotent: same records -> same close (minus ``generated_at``/jitter).
- No central wiring here: this module does NOT touch ``cli.py``,
  ``client.py``, ``api/`` or ``mcp_server.py``. Intended commands
  (``omni-one pipeline-close``, ``POST /api/v1/pipeline/close``) are
  placeholders documented in ``docs/PIPELINE_CLOSE.md``.

Close verdict bands (see :func:`verdict_for_ratio`): ``healthy`` (ratio 0),
``needs review`` (0 < ratio < 0.40), ``critical`` (ratio >= 0.40).

Golden demo numbers (``DEMO_RECORDS()``): processed 8, rejected 0,
cost 0.0, 2 anomalies (``sensor-A-spike`` + ``review-neg-01``),
ratio 0.25, verdict ``"needs review"``, bypass 100.0.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Pack identity + tuning constants
# ---------------------------------------------------------------------------

PACK_NAME = "pipeline_close"
PACK_VERSION = "1.0.0"

#: Keywords marking a text value as negative-sentiment (lowercase substring
#: match; deterministic, dependency-free).
NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "terrible",
    "awful",
    "horrible",
    "hate",
    "worst",
    "failure",
    "fail",
    "refund",
    "angry",
    "broken",
    "disgusting",
    "useless",
    "scam",
    "disappointed",
    "furious",
)

#: Numeric spike gate: value >= max(5x median, median + 100). The floor keeps
#: tiny baselines from flagging noise; the factor catches 10-100x blowups.
SPIKE_FACTOR = 5.0
SPIKE_FLOOR = 100.0

#: Verdict bands on anomaly_ratio = len(anomalies) / max(processed, 1).
HEALTHY_MAX_RATIO = 0.0  # exactly zero anomalies -> healthy
REVIEW_MAX_RATIO = 0.40  # below this -> needs review, at/above -> critical

#: How many evidence steps to keep in the headline ``evidence_sample``.
EVIDENCE_SAMPLE_SIZE = 6

#: Mock LLM response. Layer 4 never leaves the laptop.
MOCK_RESPONSE = "[MOCK]"

#: Fixed base day for demo timestamps (deterministic, no wall clock).
DEMO_BASE_DATE = "2026-01-05"
DEMO_BASE_HOUR = 9


# ---------------------------------------------------------------------------
# Mock router (offline: Layer 4 never leaves the laptop)
# ---------------------------------------------------------------------------


class MockModelRouter:
    """Drop-in mock for ``ModelRouter`` used only by this pack.

    ``generate()`` always returns ``"[MOCK]"`` and never touches the network
    (no litellm, no keys, no sockets). Cost helpers always report ``0.0``
    so golden runs have ``cost_usd == 0.0``. Implements only what the
    pipeline touches: ``generate``, ``registry``, ``_estimate_tokens``,
    ``estimate_cost_for_model`` (+ ``estimate_cost``/``select_model`` shims).
    """

    MOCK_MODEL = "mock/balanced"

    def __init__(self) -> None:
        self.registry: dict[str, dict[str, Any]] = {"balanced": {"model": self.MOCK_MODEL}}

    def generate(self, prompt: str, model: str | None = None, **kwargs: Any) -> str:
        """Return the canned mock response. Never calls the network."""
        return MOCK_RESPONSE

    def _estimate_tokens(self, text: str) -> int:
        """Char-heuristic token estimate (mirrors the real router fallback)."""
        return max(1, len(text) // 4)

    def estimate_cost_for_model(
        self, model: str, prompt: str, output_tokens: int = 512
    ) -> float:
        """Mock runs are free: always ``0.0`` USD."""
        return 0.0

    def estimate_cost(
        self, prompt: str, model_key: str = "balanced", output_tokens: int = 512
    ) -> float:
        """Mock runs are free: always ``0.0`` USD."""
        return 0.0

    def select_model(
        self,
        query_complexity: str = "medium",
        budget: float | None = None,
        latency_sla_ms: int | None = None,
    ) -> str:
        """Compat shim: always route to the mock model."""
        return self.MOCK_MODEL


def build_mock_router() -> MockModelRouter:
    """Factory for a fresh mock router (one per close keeps runs isolated)."""
    return MockModelRouter()


# ---------------------------------------------------------------------------
# Deterministic demo records (golden fixture: 8 records, 2 clear anomalies)
# ---------------------------------------------------------------------------


def DEMO_RECORDS(seed: int = 42) -> list[dict[str, Any]]:
    """Return 8 deterministic demo records including 2 clear anomalies.

    - 6 normal numeric sensor readings (``sensor``, ~100 kWh; ``seed`` only
      jitters them ±5 via pure arithmetic — no ``random``, no wall clock).
    - 1 value spike: ``sensor-A-spike`` = 9999.0 (~100x the median).
    - 1 negative-sentiment text: ``review-neg-01`` (hits several
      :data:`NEGATIVE_KEYWORDS`: terrible/awful/failure/hate/worst/refund).

    All records carry Layer-1 required fields, fixed ``DEMO_BASE_DATE``
    timestamps (5-min spacing, distinct so dedup never fires) → golden run
    has ``processed == 8``, ``rejected == 0``.
    """
    records: list[dict[str, Any]] = []
    for i in range(6):
        # Pure-arithmetic jitter in [-5, +5] around 100; deterministic.
        jitter = ((seed * 7 + i * 13) % 11) - 5
        records.append(
            {
                "timestamp": f"{DEMO_BASE_DATE}T{DEMO_BASE_HOUR:02d}:{i * 5:02d}:00",
                "source": "sensor",
                "entity_id": f"sensor-A-{i:02d}",
                "value": 100 + jitter,
                "metadata": {"unit": "kwh", "seed": seed},
            }
        )
    records.append(
        {
            "timestamp": f"{DEMO_BASE_DATE}T{DEMO_BASE_HOUR:02d}:35:00",
            "source": "sensor",
            "entity_id": "sensor-A-spike",
            "value": 9999.0,
            "metadata": {"unit": "kwh", "note": "spike anomaly fixture"},
        }
    )
    records.append(
        {
            "timestamp": f"{DEMO_BASE_DATE}T{DEMO_BASE_HOUR:02d}:40:00",
            "source": "review",
            "entity_id": "review-neg-01",
            "value": (
                "Terrible awful service, complete failure, hate it, "
                "worst experience ever, refund now"
            ),
            "metadata": {"channel": "web", "note": "negative sentiment fixture"},
        }
    )
    return records


# ---------------------------------------------------------------------------
# Small deterministic helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Current UTC time as ISO string. The ONLY wall-clock value in outputs."""
    return datetime.now(timezone.utc).isoformat()


def _median(values: list[float]) -> float:
    """Median of a list (0.0 when empty). Pure, no dependencies."""
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def _round2(value: Any) -> float:
    """Round a timing value to 2 decimals (0.0 on any bad input)."""
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def _cost_usd_of(cost_ledger: Any) -> float:
    """Extract ``cost_usd`` from a CostLedgerEntry pydantic model or dict."""
    try:
        if cost_ledger is None:
            return 0.0
        if isinstance(cost_ledger, dict):
            return round(float(cost_ledger.get("cost_usd", 0.0) or 0.0), 6)
        return round(float(getattr(cost_ledger, "cost_usd", 0.0) or 0.0), 6)
    except (TypeError, ValueError):
        return 0.0


def _model_used_of(cost_ledger: Any) -> str:
    """Extract ``model_used`` (``"none-local"`` when the LLM was bypassed)."""
    try:
        if cost_ledger is None:
            return "none-local"
        if isinstance(cost_ledger, dict):
            return str(cost_ledger.get("model_used") or "none-local")
        return str(getattr(cost_ledger, "model_used", None) or "none-local")
    except Exception:
        return "none-local"


def _cached_of(cost_ledger: Any) -> bool:
    """Extract the ``cached`` flag from a cost ledger entry."""
    try:
        if isinstance(cost_ledger, dict):
            return bool(cost_ledger.get("cached", False))
        return bool(getattr(cost_ledger, "cached", False))
    except Exception:
        return False


def _step_field(step: Any, field: str, default: str = "") -> str:
    """Read a field from an evidence step (dict or pydantic model)."""
    try:
        if isinstance(step, dict):
            return str(step.get(field, default))
        return str(getattr(step, field, default))
    except Exception:
        return default


def _first_citation(steps: list[Any], fallback_record_id: str) -> str:
    """Cite the first evidence step as ``<layer>: <citation>`` (never empty)."""
    if not steps:
        return f"{fallback_record_id}:no-evidence"
    layer = _step_field(steps[0], "layer", "unknown-layer")
    citation = _step_field(steps[0], "citation", "no citation")
    return f"{layer}: {citation}"[:280]


# ---------------------------------------------------------------------------
# Anomaly detectors (deterministic, dependency-free)
# ---------------------------------------------------------------------------


def detect_numeric_spike(value: Any, median: float) -> str | None:
    """Spike signal when ``value`` dwarfs ``median``; None for text/bool/ok."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    try:
        threshold = max(SPIKE_FACTOR * median, median + SPIKE_FLOOR)
        if float(value) >= threshold:
            return f"value_spike:{value:g}_vs_median_{median:g}_threshold_{threshold:g}"
    except (TypeError, ValueError):
        return None
    return None


def detect_negative_sentiment(value: Any) -> list[str]:
    """Matched negative keywords in a text value ([] for clean/non-string)."""
    if not isinstance(value, str):
        return []
    lowered = value.lower()
    return [kw for kw in NEGATIVE_KEYWORDS if kw in lowered]


def layer2_signals(layer2_result: Any) -> list[str]:
    """Layer-2 anomalies -> ``layer2:<type> severity=<sev> score=<s>`` strings."""
    signals: list[str] = []
    try:
        anomalies = (layer2_result or {}).get("anomalies", []) or []
        for anomaly in anomalies[:4]:
            if not isinstance(anomaly, dict):
                continue
            kind = anomaly.get("type", "unknown")
            severity = anomaly.get("severity", "unknown")
            try:
                score = float(anomaly.get("score", 0) or 0)
            except (TypeError, ValueError):
                score = 0.0
            signals.append(f"layer2:{kind} severity={severity} score={score:.2f}")
    except Exception:
        pass
    return signals


def layer3_sentiment_signal(layer3_result: Any) -> str | None:
    """Corroborating ``layer3:sentiment=<v> confidence=<c>`` (None if absent)."""
    try:
        predictions = (layer3_result or {}).get("predictions", {}) or {}
        sentiment = predictions.get("sentiment")
        if not isinstance(sentiment, dict):
            return None
        value = sentiment.get("value", "?")
        try:
            confidence = float(sentiment.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        return f"layer3:sentiment={value} confidence={confidence:.2f}"
    except Exception:
        return None


def verdict_for_ratio(anomaly_ratio: float) -> str:
    """Ratio -> verdict: 0 healthy, <0.40 needs review, else critical."""
    try:
        ratio = float(anomaly_ratio)
    except (TypeError, ValueError):
        ratio = 0.0
    if ratio <= HEALTHY_MAX_RATIO:
        return "healthy"
    if ratio < REVIEW_MAX_RATIO:
        return "needs review"
    return "critical"


# ---------------------------------------------------------------------------
# Per-result summarising
# ---------------------------------------------------------------------------


def _summarize_result(result: Any, median_numeric: float) -> dict[str, Any]:
    """Flatten one ``ProcessingResult`` into a JSON-safe summary (never raises)."""
    try:
        record_id = str(getattr(result, "record_id", "unknown"))
    except Exception:
        record_id = "unknown"
    try:
        stage_obj = getattr(result, "processing_stage", "unknown")
        stage = stage_obj.value if hasattr(stage_obj, "value") else str(stage_obj)
    except Exception:
        stage = "unknown"
    try:
        llm_bypassed = bool(getattr(result, "llm_bypassed", True))
    except Exception:
        llm_bypassed = True
    latency_ms = _round2(getattr(result, "total_time_ms", 0.0))
    cost_usd = _cost_usd_of(getattr(result, "cost_ledger", None))

    try:
        raw_steps = list(getattr(result, "evidence_steps", None) or [])
    except Exception:
        raw_steps = []
    steps: list[dict[str, Any]] = []
    for step in raw_steps:
        try:
            if isinstance(step, dict):
                steps.append(
                    {
                        "layer": str(step.get("layer", "")),
                        "signal": str(step.get("signal", "")),
                        "citation": str(step.get("citation", "")),
                    }
                )
            else:
                steps.append(
                    {
                        "layer": _step_field(step, "layer"),
                        "signal": _step_field(step, "signal"),
                        "citation": _step_field(step, "citation"),
                    }
                )
        except Exception:
            continue

    # ---- signals (ordered: pipeline first, heuristics second) ----
    signals: list[str] = []
    try:
        signals.extend(layer2_signals(getattr(result, "layer2_result", None)))
    except Exception:
        pass
    try:
        original = getattr(result, "original_record", None) or {}
        value = original.get("value") if isinstance(original, dict) else None
    except Exception:
        value = None
    try:
        spike = detect_numeric_spike(value, median_numeric)
        if spike:
            signals.append(spike)
    except Exception:
        pass
    negative_hits: list[str] = []
    try:
        negative_hits = detect_negative_sentiment(value)
        if negative_hits:
            shown = ",".join(negative_hits[:6])
            signals.append(f"negative_sentiment:{len(negative_hits)} keywords({shown})")
    except Exception:
        pass
    try:
        sentiment_sig = layer3_sentiment_signal(getattr(result, "layer3_result", None))
        if sentiment_sig and negative_hits:
            signals.append(sentiment_sig)
    except Exception:
        pass

    return {
        "record_id": record_id,
        "stage": stage,
        "llm_bypassed": llm_bypassed,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "model_used": _model_used_of(getattr(result, "cost_ledger", None)),
        "cached": _cached_of(getattr(result, "cost_ledger", None)),
        "evidence_steps": steps,
        "signals": signals,
    }


def _build_anomaly(summary: dict[str, Any]) -> dict[str, Any]:
    """Turn a flagged result summary into an anomaly row dict."""
    steps = summary.get("evidence_steps", []) or []
    return {
        "record_id": summary.get("record_id", "unknown"),
        "stage": summary.get("stage", "unknown"),
        "signals": list(summary.get("signals", []) or []),
        "evidence_cite": _first_citation(steps, str(summary.get("record_id", "unknown"))),
        "latency_ms": summary.get("latency_ms", 0.0),
    }


def _build_cost_ledger_lines(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-record cost lines + a ``__total__`` line (all 0.0 on mock runs)."""
    lines: list[dict[str, Any]] = []
    for summary in summaries:
        lines.append(
            {
                "record_id": summary.get("record_id", "unknown"),
                "model_used": summary.get("model_used", "none-local"),
                "cost_usd": summary.get("cost_usd", 0.0),
                "cached": bool(summary.get("cached", False)),
            }
        )
    total = 0.0
    for line in lines:
        try:
            total += float(line.get("cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
    lines.append(
        {
            "record_id": "__total__",
            "model_used": "mock/offline",
            "cost_usd": round(total, 6),
            "cached": False,
        }
    )
    return lines


def _build_do_today(
    anomalies: list[dict[str, Any]],
    processed: int,
    rejected: int,
    cost_usd: float,
    bypass_rate: float,
) -> list[str]:
    """Exactly 3 operator actions (healthy-state fallback per slot, always len 3)."""
    actions: list[str] = []
    if anomalies:
        top = anomalies[0]
        first_signal = (top.get("signals", ["no signal"]) or ["no signal"])[0]
        actions.append(
            f"Review top anomaly {top.get('record_id')} ({top.get('stage')}): "
            f"{first_signal} [{top.get('evidence_cite')}]"
        )
    else:
        actions.append("No anomalies — nothing to review; pipeline healthy.")
    if rejected > 0:
        actions.append(
            f"Check {rejected} rejected record(s) out of {processed} "
            f"processed — fix source schema/timestamps, then re-run."
        )
    else:
        actions.append(
            f"No rejected records — ingestion clean ({processed}/{processed} valid)."
        )
    actions.append(
        f"Nothing to spend — mock run cost ${cost_usd:.4f} "
        f"(LLM bypass {bypass_rate:.1f}%, Layer 4 never left the laptop)."
    )
    return actions[:3]


# ---------------------------------------------------------------------------
# Main entry point: build the close
# ---------------------------------------------------------------------------


def build_pipeline_close(records: list[dict], seed: int = 42) -> dict:
    """Run the pipeline over ``records`` and build the close dict.

    Fresh ``MultiLayerDataPipeline`` + :class:`MockModelRouter`
    (``"[MOCK]"``) + fresh ``SemanticCache`` per call: no network, no
    shared state. ``None`` records degrade to ``[]``; a total
    ``process_batch`` failure still returns a well-formed ``critical`` close.

    Returns keys: ``pack``, ``pack_version``, ``seed``,
    ``meta{generated_at, records, seed, pipeline}``,
    ``kpis{processed, rejected, bypass_rate, avg_ms, cost_usd}``,
    ``results``, ``anomalies[]``, ``anomaly_ratio``, ``verdict``,
    ``evidence_sample`` (first 6 steps), ``cost_ledger``, ``do_today[3]``.
    """
    from omni_one.core.cache import SemanticCache
    from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline

    safe_records: list[dict] = list(records or [])
    generated_at = _utc_now_iso()

    pipeline = MultiLayerDataPipeline(
        model_router=build_mock_router(),  # type: ignore[arg-type]
        cache=SemanticCache(),
    )
    try:
        results, metrics = pipeline.process_batch(safe_records)
    except Exception as exc:
        # Total pipeline failure still yields a valid (critical) close.
        crash_ledger = [{"record_id": "__total__", "model_used": "mock/offline",
                         "cost_usd": 0.0, "cached": False}]
        return {
            "pack": PACK_NAME, "pack_version": PACK_VERSION, "seed": seed,
            "meta": {"generated_at": generated_at, "records": len(safe_records),
                     "seed": seed, "pipeline": {"error": f"process_batch failed: {exc}"}},
            "kpis": {"processed": 0, "rejected": len(safe_records), "bypass_rate": 0.0,
                     "avg_ms": 0.0, "cost_usd": 0.0},
            "results": [], "anomalies": [], "anomaly_ratio": 0.0, "verdict": "critical",
            "evidence_sample": [], "cost_ledger": crash_ledger,
            "do_today": ["Pipeline crashed — read meta.pipeline.error first.",
                         f"Check {len(safe_records)} input record(s) for schema violations.",
                         "Nothing to spend — run never reached Layer 4."],
            "notes": "offline mock close; Layer 4 never leaves the laptop.",
        }
    try:
        metrics_summary = pipeline.get_metrics_summary()
    except Exception:
        metrics_summary = {}

    # Median over numeric inputs (pure function of caller input, not pipeline
    # state) for the spike heuristic; bools excluded (bool subclasses int).
    numeric_inputs: list[float] = []
    for record in safe_records:
        try:
            value = (record or {}).get("value")
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                numeric_inputs.append(float(value))
        except Exception:
            continue
    median_numeric = _median(numeric_inputs)

    summaries = [_summarize_result(result, median_numeric) for result in results]

    processed = len(summaries)
    rejected = sum(1 for s in summaries if s.get("stage") == "ingestion_error")

    def _metric(name: str, places: int) -> float:
        try:
            return round(float(getattr(metrics, name, 0.0) or 0.0), places)
        except (TypeError, ValueError):
            return 0.0

    bypass_rate = _metric("llm_bypass_rate", 2)
    avg_ms = _metric("avg_processing_time_ms", 2)
    cost_usd = _metric("total_cost_usd", 6)

    anomalies = [_build_anomaly(s) for s in summaries if s.get("signals")]
    anomalies.sort(key=lambda a: str(a.get("record_id", "")))

    anomaly_ratio = round(len(anomalies) / max(processed, 1), 4) if processed else 0.0
    verdict = verdict_for_ratio(anomaly_ratio)

    evidence_sample: list[dict[str, Any]] = []
    for summary in summaries:
        for step in summary.get("evidence_steps", []) or []:
            if len(evidence_sample) >= EVIDENCE_SAMPLE_SIZE:
                break
            evidence_sample.append({"record_id": summary.get("record_id", "unknown"),
                                    "layer": step.get("layer", ""),
                                    "signal": step.get("signal", ""),
                                    "citation": step.get("citation", "")})
        if len(evidence_sample) >= EVIDENCE_SAMPLE_SIZE:
            break

    cost_ledger = _build_cost_ledger_lines(summaries)
    do_today = _build_do_today(anomalies, processed, rejected, cost_usd, bypass_rate)

    return {
        "pack": PACK_NAME, "pack_version": PACK_VERSION, "seed": seed,
        "meta": {"generated_at": generated_at, "records": len(safe_records),
                 "seed": seed, "pipeline": metrics_summary},
        "kpis": {"processed": processed, "rejected": rejected,
                 "bypass_rate": bypass_rate, "avg_ms": avg_ms, "cost_usd": cost_usd},
        "results": summaries, "anomalies": anomalies,
        "anomaly_ratio": anomaly_ratio, "verdict": verdict,
        "evidence_sample": evidence_sample, "cost_ledger": cost_ledger,
        "do_today": do_today,
        "notes": "offline mock close; Layer 4 never leaves the laptop.",
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def close_to_csv(close: dict[str, Any]) -> str:
    """Render a close as CSV: metric/value rows + anomaly rows + evidence rows.

    All sections parse with :mod:`csv` (quoting via csv.writer). Missing
    keys degrade to ``""``; never raises on well-formed closes.
    """
    close = close or {}
    kpis = close.get("kpis") or {}
    meta = close.get("meta") or {}
    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(
        ["pipeline_close", meta.get("generated_at", ""), close.get("verdict", "")]
    )
    writer.writerow([])
    writer.writerow(["metric", "value"])
    writer.writerow(["processed", kpis.get("processed", 0)])
    writer.writerow(["rejected", kpis.get("rejected", 0)])
    writer.writerow(["bypass_rate", kpis.get("bypass_rate", 0.0)])
    writer.writerow(["avg_ms", kpis.get("avg_ms", 0.0)])
    writer.writerow(["cost_usd", kpis.get("cost_usd", 0.0)])
    writer.writerow(["anomaly_ratio", close.get("anomaly_ratio", 0.0)])
    writer.writerow(["verdict", close.get("verdict", "")])
    writer.writerow([])

    writer.writerow(
        ["anomaly_record_id", "stage", "signals", "evidence_cite", "latency_ms"]
    )
    for anomaly in close.get("anomalies") or []:
        signals = anomaly.get("signals", []) or []
        writer.writerow(
            [
                anomaly.get("record_id", ""),
                anomaly.get("stage", ""),
                " | ".join(str(s) for s in signals),
                anomaly.get("evidence_cite", ""),
                anomaly.get("latency_ms", 0.0),
            ]
        )
    writer.writerow([])

    writer.writerow(["evidence_n", "record_id", "layer", "signal", "citation"])
    for n, step in enumerate(close.get("evidence_sample") or [], 1):
        writer.writerow(
            [
                n,
                step.get("record_id", ""),
                step.get("layer", ""),
                step.get("signal", ""),
                step.get("citation", ""),
            ]
        )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Bundle writer (close.json + close.csv + evidence.jsonl)
# ---------------------------------------------------------------------------


def write_close_bundle(close: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write ``close.json`` + ``close.csv`` + ``evidence.jsonl``; return 3 paths.

    ``evidence.jsonl`` holds one JSON object per evidence step across ALL
    results (``record_id`` injected per line). Empty closes get a single
    ``__meta__`` marker line so the file stays non-empty and greppable.
    """
    close = close or {}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "close.json"
    json_path.write_text(json.dumps(close, indent=2, default=str))

    csv_path = out / "close.csv"
    csv_path.write_text(close_to_csv(close))

    jsonl_path = out / "evidence.jsonl"
    lines: list[str] = []
    for summary in close.get("results") or []:
        record_id = summary.get("record_id", "unknown")
        for step in summary.get("evidence_steps", []) or []:
            lines.append(
                json.dumps(
                    {
                        "record_id": record_id,
                        "layer": (step or {}).get("layer", ""),
                        "signal": (step or {}).get("signal", ""),
                        "citation": (step or {}).get("citation", ""),
                    },
                    default=str,
                )
            )
    # Belt-and-braces: an (otherwise valid) empty close still yields a
    # non-empty, greppable jsonl with a single pack-meta line.
    if not lines:
        lines.append(
            json.dumps(
                {
                    "record_id": "__meta__",
                    "layer": "pack",
                    "signal": "no evidence steps in this close",
                    "citation": f"verdict={close.get('verdict', '')}",
                }
            )
        )
    jsonl_path.write_text("\n".join(lines) + "\n")

    return {
        "close.json": str(json_path),
        "close.csv": str(csv_path),
        "evidence.jsonl": str(jsonl_path),
    }


# ---------------------------------------------------------------------------
# Demo entry point: python -m omni_one.packs.pipeline_close
# ---------------------------------------------------------------------------


def _demo() -> None:
    """Offline demo: golden records -> close -> bundle in ./close_pipeline."""
    records = DEMO_RECORDS()
    close = build_pipeline_close(records)
    kpis = close.get("kpis", {})
    print(f"verdict={close.get('verdict')} anomalies={len(close.get('anomalies', []))}")
    print(f"kpis={json.dumps(kpis, default=str)}")
    for anomaly in close.get("anomalies", []):
        print(f"  anomaly {anomaly.get('record_id')}: {anomaly.get('signals')}")
    paths = write_close_bundle(close, "./close_pipeline")
    for name, path in paths.items():
        print(f"wrote {name} -> {path}")


if __name__ == "__main__":
    _demo()
