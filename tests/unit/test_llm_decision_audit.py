import sys
import time
from pathlib import Path


CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "omni_one" / "core"
sys.path.insert(0, str(CORE_DIR))

from data_processing_pipeline import MultiLayerDataPipeline, ProcessingStage


class RecordingModelRouter:
    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "Investigate the threshold breach and contact the account owner."


def record(entity_id, value, source="salesforce"):
    return {
        "timestamp": time.time(),
        "source": source,
        "entity_id": entity_id,
        "value": value,
        "metadata": {},
    }


def test_clean_optimized_batch_records_include_audit_for_selective_skip():
    pipeline = MultiLayerDataPipeline()

    results, _ = pipeline.process_batch_optimized(
        [
            record("account_clean_1", 100),
            record("account_clean_2", 101),
        ]
    )

    for result in results:
        audit = result.llm_decision_audit

        assert audit["decision"] == "skipped_by_selective_propagation"
        assert audit["llm_bypassed"] is True
        assert audit["layer3_skipped"] is True
        assert audit["skip_reason"] == "no_anomalies"
        assert audit["gate_reason"] == "LLM not required after selective propagation"
        assert audit["priority_score"] == 0.2
        assert audit["anomaly_severity"] is None
        assert audit["batch_context"]["batch_size"] == 2
        assert audit["batch_context"]["anomaly_count"] == 0
        assert audit["batch_context"]["anomaly_rate"] == 0.0


def test_high_anomaly_invocation_records_gate_reason_and_prompt_metadata():
    router = RecordingModelRouter()
    pipeline = MultiLayerDataPipeline(model_router=router)
    pipeline.layer2.set_metric_threshold("salesforce_account_hot", upper=100)

    results, _ = pipeline.process_batch_optimized([record("account_hot", 250)])

    assert len(router.prompts) == 1
    result = results[0]
    audit = result.llm_decision_audit

    assert result.processing_stage is ProcessingStage.LLM_REQUIRED
    assert result.llm_bypassed is False
    assert audit["decision"] == "invoked"
    assert audit["llm_bypassed"] is False
    assert audit["layer3_skipped"] is False
    assert audit["gate_reason"].startswith("High priority")
    assert audit["priority_score"] >= 0.3
    assert audit["anomaly_severity"] == "high"
    assert audit["cache_status"] == "not_configured"
    assert audit["prompt_preview"].startswith("Analyze this business intelligence record")
    assert audit["batch_context"]["anomaly_count"] == 1
    assert audit["batch_context"]["high_count"] == 1


def test_single_record_processing_exposes_not_required_audit_contract():
    pipeline = MultiLayerDataPipeline()

    result = pipeline.process_record(record("account_single", 42))
    audit = result.llm_decision_audit

    assert result.processing_stage is ProcessingStage.ML_FEATURE
    assert audit["decision"] == "not_required"
    assert audit["llm_bypassed"] is True
    assert audit["layer3_skipped"] is False
    assert audit["batch_context"] is None
    assert audit["gate_reason"] == "Layer 3 did not require LLM synthesis"
    assert isinstance(audit["priority_score"], float)
    assert audit["cache_status"] == "not_checked"
