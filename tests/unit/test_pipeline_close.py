"""
Unit tests for PACK A: Pipeline Analyze Close (``omni_one.packs.pipeline_close``).

What is pinned here (golden contract — change deliberately, not casually):

- ``DEMO_RECORDS()`` -> 8 records; close has ``processed == 8``,
  ``rejected == 0``, ``cost_usd == 0.0`` (mock router, offline),
  ``verdict == "needs review"`` with exactly the 2 planted anomalies.
- ``sensor-A-spike`` (value 9999.0) is always in ``anomalies``.
- Every result carries non-empty evidence steps with layer/signal/citation.
- Two runs agree on verdict + KPIs (minus ``generated_at`` and sub-ms
  timing jitter in ``avg_ms``).
- Empty input -> ``healthy`` close, no crash, valid CSV + bundle.
- ``write_close_bundle`` creates 3 non-empty files; CSV parses with
  :mod:`csv`; every ``evidence.jsonl`` line parses with :mod:`json`.

Offline guarantee: the pack injects ``MockModelRouter`` whose ``generate()``
returns ``"[MOCK]"``. ``test_no_network_mock`` asserts that contract
directly, and no test in this file sets API keys or touches sockets.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

import pytest

from omni_one.packs.pipeline_close import (
    DEMO_RECORDS,
    EVIDENCE_SAMPLE_SIZE,
    MOCK_RESPONSE,
    MockModelRouter,
    build_mock_router,
    build_pipeline_close,
    close_to_csv,
    detect_negative_sentiment,
    detect_numeric_spike,
    verdict_for_ratio,
    write_close_bundle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _golden_close() -> dict[str, Any]:
    """Build the golden close once per test (fresh pipeline each call)."""
    return build_pipeline_close(DEMO_RECORDS(), seed=42)


def _kpis_stable(close: dict[str, Any]) -> dict[str, Any]:
    """KPIs minus the wall-clock-jitter field (``avg_ms``)."""
    kpis = dict(close.get("kpis", {}))
    kpis.pop("avg_ms", None)
    return kpis


def _anomaly_ids(close: dict[str, Any]) -> list[str]:
    """Record ids of all anomaly rows, in close order."""
    return [str(a.get("record_id", "")) for a in close.get("anomalies", [])]


# ---------------------------------------------------------------------------
# 1. Golden DEMO_RECORDS metrics
# ---------------------------------------------------------------------------


def test_golden_demo_metrics() -> None:
    """Golden contract: 8 processed, 0 rejected, $0 mock cost, needs review."""
    records = DEMO_RECORDS()
    assert len(records) == 8, "demo fixture must hold exactly 8 records"

    close = build_pipeline_close(records, seed=42)

    kpis = close.get("kpis", {})
    assert kpis.get("processed") == 8, f"expected processed==8, got {kpis}"
    assert kpis.get("rejected") == 0, f"expected rejected==0, got {kpis}"
    assert kpis.get("cost_usd") == 0.0, f"mock run must cost 0.0, got {kpis}"

    bypass = float(kpis.get("bypass_rate", -1))
    assert 0.0 <= bypass <= 100.0, f"bypass_rate out of range: {bypass}"
    assert bypass == 100.0, f"golden bypass_rate==100.0, got {bypass}"

    assert close.get("anomaly_ratio") == pytest.approx(0.25), (
        f"2 anomalies / 8 processed must give ratio 0.25, got {close.get('anomaly_ratio')}"
    )
    assert close.get("verdict") == "needs review", (
        f"golden verdict must be 'needs review', got {close.get('verdict')!r}"
    )
    assert len(close.get("anomalies", [])) == 2, (
        f"golden close must flag exactly 2 anomalies, got {len(close.get('anomalies', []))}"
    )

    # Structural keys the CLI/API placeholders rely on.
    for key in (
        "pack",
        "pack_version",
        "seed",
        "meta",
        "kpis",
        "results",
        "anomalies",
        "anomaly_ratio",
        "verdict",
        "evidence_sample",
        "cost_ledger",
        "do_today",
    ):
        assert key in close, f"close missing required key {key!r}"
    assert close["meta"]["generated_at"], "generated_at must be non-empty"
    assert close["meta"]["records"] == 8
    assert len(close["do_today"]) == 3, "do_today must hold exactly 3 actions"
    assert len(close["evidence_sample"]) == EVIDENCE_SAMPLE_SIZE == 6


def test_golden_demo_record_contents() -> None:
    """Fixture sanity: required Layer-1 fields + the 2 planted anomalies."""
    records = DEMO_RECORDS(seed=42)
    for record in records:
        for field in ("timestamp", "source", "entity_id"):
            assert record.get(field), f"record missing {field}: {record}"

    values = [r.get("value") for r in records]
    assert 9999.0 in values, "spike fixture (value 9999.0) missing from demo"
    texts = [v for v in values if isinstance(v, str)]
    assert any("terrible" in t.lower() for t in texts), "negative text fixture missing"
    assert any("refund" in t.lower() for t in texts), "negative text must mention refund"

    # Same seed -> identical fixture (idempotent demo input).
    assert DEMO_RECORDS(seed=42) == DEMO_RECORDS(seed=42)
    # Distinct entity_ids keep the dedup filter quiet.
    entity_ids = [r["entity_id"] for r in records]
    assert len(set(entity_ids)) == 8, "demo entity_ids must be distinct"


# ---------------------------------------------------------------------------
# 2. Anomalies contain the spike record (+ the negative-sentiment record)
# ---------------------------------------------------------------------------


def test_anomalies_contain_spike_record() -> None:
    """The 9999.0 spike must be flagged with a spike signal + evidence cite."""
    close = _golden_close()
    ids = _anomaly_ids(close)
    spike_ids = [i for i in ids if "spike" in i]
    assert spike_ids, f"spike record missing from anomalies {ids}"

    spike = next(a for a in close["anomalies"] if "spike" in str(a.get("record_id")))
    signals = spike.get("signals", [])
    assert any("value_spike" in str(s) for s in signals), (
        f"spike anomaly must carry a value_spike signal, got {signals}"
    )
    assert spike.get("evidence_cite"), "anomaly must carry a non-empty evidence cite"
    assert spike.get("stage"), "anomaly must carry its processing stage"
    assert isinstance(spike.get("latency_ms"), float)


def test_anomalies_contain_negative_sentiment_record() -> None:
    """The toxic review must be flagged with a sentiment signal + cite."""
    close = _golden_close()
    ids = _anomaly_ids(close)
    neg_ids = [i for i in ids if "neg" in i]
    assert neg_ids, f"negative-sentiment record missing from anomalies {ids}"

    neg = next(a for a in close["anomalies"] if "neg" in str(a.get("record_id")))
    signals = [str(s) for s in neg.get("signals", [])]
    assert any("negative_sentiment" in s for s in signals), (
        f"expected a negative_sentiment signal, got {signals}"
    )
    assert neg.get("evidence_cite"), "anomaly must carry a non-empty evidence cite"


def test_anomaly_detector_units() -> None:
    """Detector units: spike threshold math + keyword matching (no pipeline)."""
    assert detect_numeric_spike(9999.0, 100.0) is not None
    assert "9999" in (detect_numeric_spike(9999.0, 100.0) or "")
    assert detect_numeric_spike(101, 100.0) is None, "normal values must not spike"
    assert detect_numeric_spike("angry text", 100.0) is None
    assert detect_numeric_spike(True, 100.0) is None, "bools are not numbers"
    assert detect_numeric_spike(None, 100.0) is None

    hits = detect_negative_sentiment("Terrible awful failure, refund now")
    assert "terrible" in hits and "refund" in hits
    assert detect_negative_sentiment("Great service, very satisfied!") == []
    assert detect_negative_sentiment(123) == []
    assert detect_negative_sentiment(None) == []

    assert verdict_for_ratio(0.0) == "healthy"
    assert verdict_for_ratio(0.25) == "needs review"
    assert verdict_for_ratio(0.3999) == "needs review"
    assert verdict_for_ratio(0.40) == "critical"
    assert verdict_for_ratio(1.0) == "critical"


# ---------------------------------------------------------------------------
# 3. Evidence steps present on every result
# ---------------------------------------------------------------------------


def test_evidence_steps_present_on_every_result() -> None:
    """Each of the 8 results carries auditable evidence steps (mock run)."""
    close = _golden_close()
    results = close.get("results", [])
    assert len(results) == 8, f"expected 8 result summaries, got {len(results)}"
    for summary in results:
        steps = summary.get("evidence_steps", [])
        assert steps, f"result {summary.get('record_id')} has no evidence steps"
        for step in steps:
            assert step.get("layer"), f"step missing layer: {step}"
            assert step.get("signal"), f"step missing signal: {step}"
            assert step.get("citation"), f"step missing citation: {step}"

    sample = close.get("evidence_sample", [])
    assert len(sample) == 6, f"evidence_sample must hold first 6 steps, got {len(sample)}"
    for step in sample:
        assert step.get("record_id") and step.get("layer") and step.get("citation")


def test_cost_ledger_lines_all_zero_mock() -> None:
    """Mock cost ledger: 8 record lines + __total__, every cost 0.0."""
    close = _golden_close()
    ledger = close.get("cost_ledger", [])
    assert len(ledger) == 9, f"8 records + total line expected, got {len(ledger)}"
    for line in ledger:
        assert line.get("record_id"), "ledger line missing record_id"
        assert float(line.get("cost_usd", -1)) == 0.0, f"mock cost must be 0.0: {line}"
    total = ledger[-1]
    assert total.get("record_id") == "__total__"
    assert float(total.get("cost_usd", -1)) == 0.0


# ---------------------------------------------------------------------------
# 4. Idempotent: two runs agree (minus timestamp / timing jitter)
# ---------------------------------------------------------------------------


def test_idempotent_verdict_and_kpis() -> None:
    """Two runs on DEMO_RECORDS agree on verdict + KPIs (minus timestamp)."""
    first = build_pipeline_close(DEMO_RECORDS(seed=42), seed=42)
    second = build_pipeline_close(DEMO_RECORDS(seed=42), seed=42)

    assert first.get("verdict") == second.get("verdict") == "needs review"
    assert _kpis_stable(first) == _kpis_stable(second), (
        f"KPIs diverged: {first.get('kpis')} vs {second.get('kpis')}"
    )
    # avg_ms may jitter by sub-milliseconds of wall clock — bound it loosely.
    avg_delta = abs(
        float(first["kpis"].get("avg_ms", 0.0)) - float(second["kpis"].get("avg_ms", 0.0))
    )
    assert avg_delta < 500.0, f"avg_ms jitter too large: {avg_delta}ms"

    assert _anomaly_ids(first) == _anomaly_ids(second), "anomaly sets diverged"
    assert first.get("anomaly_ratio") == second.get("anomaly_ratio")
    assert [a.get("signals") for a in first["anomalies"]] == [
        a.get("signals") for a in second["anomalies"]
    ], "anomaly signals must be deterministic"
    assert first.get("do_today") == second.get("do_today"), "do_today diverged"


# ---------------------------------------------------------------------------
# 5. Empty records -> healthy, no crash
# ---------------------------------------------------------------------------


def test_empty_records_healthy_no_crash() -> None:
    """Empty input yields a healthy close (and empty CSV/bundle still work)."""
    close = build_pipeline_close([], seed=42)
    assert close.get("verdict") == "healthy"
    assert close["kpis"].get("processed") == 0
    assert close["kpis"].get("rejected") == 0
    assert close["kpis"].get("cost_usd") == 0.0
    assert close.get("anomalies") == []
    assert close.get("anomaly_ratio") == 0.0
    assert len(close.get("do_today", [])) == 3

    text = close_to_csv(close)
    assert text.strip(), "CSV of an empty close must still be non-empty"
    rows = list(csv.reader(io.StringIO(text)))
    assert rows and rows[0][0] == "pipeline_close"

    # None input degrades to empty instead of raising.
    none_close = build_pipeline_close(None, seed=42)  # type: ignore[arg-type]
    assert none_close.get("verdict") == "healthy"
    assert none_close["kpis"].get("processed") == 0


def test_rejected_records_do_not_crash() -> None:
    """Schema-broken records count as rejected; close stays well-formed."""
    bad = [
        {"source": "sensor", "entity_id": "no-ts", "value": 1},  # missing timestamp
        {"timestamp": "not-a-time", "source": "", "entity_id": ""},  # invalid
    ]
    close = build_pipeline_close(bad, seed=42)
    assert close["kpis"].get("processed") == 2
    assert close["kpis"].get("rejected") == 2, f"both bad rows must reject: {close['kpis']}"
    assert close.get("verdict") in ("healthy", "needs review", "critical")
    assert len(close.get("do_today", [])) == 3
    assert "rejected" in close["do_today"][1].lower() or "2 rejected" in close["do_today"][1]


# ---------------------------------------------------------------------------
# 6. Bundle writer: 3 non-empty files
# ---------------------------------------------------------------------------


def test_write_bundle_creates_three_nonempty_files(tmp_path: Path) -> None:
    """close.json + close.csv + evidence.jsonl exist, non-empty, parseable."""
    close = _golden_close()
    out_dir = tmp_path / "bundle"
    paths = write_close_bundle(close, out_dir)

    assert set(paths) == {"close.json", "close.csv", "evidence.jsonl"}
    for name, path in paths.items():
        file_path = Path(path)
        assert file_path.is_file(), f"{name} was not created at {path}"
        assert file_path.stat().st_size > 0, f"{name} is empty"

    loaded = json.loads((out_dir / "close.json").read_text())
    assert loaded.get("verdict") == "needs review"
    assert loaded["kpis"].get("processed") == 8

    jsonl_lines = (out_dir / "evidence.jsonl").read_text().strip().splitlines()
    assert len(jsonl_lines) >= 8, "jsonl must hold steps for all 8 results"
    for line in jsonl_lines:
        obj = json.loads(line)  # raises if a line is malformed
        assert obj.get("record_id") and obj.get("layer") and "signal" in obj


def test_write_bundle_creates_parent_dirs(tmp_path: Path) -> None:
    """Nested out_dir is created automatically (mkdir parents=True)."""
    close = _golden_close()
    nested = tmp_path / "a" / "b" / "close_out"
    paths = write_close_bundle(close, nested)
    assert Path(paths["close.json"]).is_file()
    assert Path(paths["close.csv"]).is_file()
    assert Path(paths["evidence.jsonl"]).is_file()


# ---------------------------------------------------------------------------
# 7. CSV parses: metric/value + anomaly rows + evidence rows
# ---------------------------------------------------------------------------


def test_csv_parses_with_all_three_sections() -> None:
    """CSV has metric/value rows, 2 anomaly rows, and 6 evidence rows."""
    close = _golden_close()
    text = close_to_csv(close)
    assert text.strip(), "CSV must be non-empty"

    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0][0] == "pipeline_close", f"bad headline row: {rows[0]}"

    metric_block = [r for r in rows if len(r) == 2 and r[0] in ("processed", "verdict")]
    by_metric = {r[0]: r[1] for r in rows if len(r) == 2}
    assert by_metric.get("processed") == "8", f"processed row missing: {by_metric}"
    assert by_metric.get("cost_usd") == "0.0", f"cost row missing: {by_metric}"
    assert by_metric.get("verdict") == "needs review"
    assert metric_block, "metric,value section missing"

    anomaly_header = ["anomaly_record_id", "stage", "signals", "evidence_cite", "latency_ms"]
    assert anomaly_header in rows, "anomaly header row missing"
    header_idx = rows.index(anomaly_header)
    anomaly_rows = [r for r in rows[header_idx + 1 :] if r and r[0].startswith(("sensor", "review"))]
    assert len(anomaly_rows) == 2, f"expected 2 anomaly rows, got {anomaly_rows}"
    joined = " ".join(" ".join(r) for r in anomaly_rows)
    assert "spike" in joined and "neg" in joined

    evidence_header = ["evidence_n", "record_id", "layer", "signal", "citation"]
    assert evidence_header in rows, "evidence header row missing"
    evidence_idx = rows.index(evidence_header)
    evidence_rows = [r for r in rows[evidence_idx + 1 :] if r]
    assert len(evidence_rows) == 6, f"expected 6 evidence rows, got {len(evidence_rows)}"


# ---------------------------------------------------------------------------
# 8. Offline contract: mock router never calls the network
# ---------------------------------------------------------------------------


def test_no_network_mock() -> None:
    """Mock router returns exactly [MOCK]; close cost ledger stays $0."""
    router = build_mock_router()
    assert isinstance(router, MockModelRouter)
    assert router.generate("any prompt about anything") == MOCK_RESPONSE == "[MOCK]"
    assert router.generate("x", model="mock/anything") == "[MOCK]"
    assert router.estimate_cost_for_model("mock/balanced", "prompt") == 0.0
    assert router.estimate_cost("prompt") == 0.0

    close = _golden_close()
    assert close["kpis"].get("cost_usd") == 0.0
    for line in close.get("cost_ledger", []):
        assert float(line.get("cost_usd", -1)) == 0.0
    for summary in close.get("results", []):
        assert summary.get("cost_usd") == 0.0
