"""Layer 4 user-LLM handoff: basic analytics always returned, copy-paste prompt only on fallback."""
import time

from omni_one.core.data_processing_pipeline import (
    MultiLayerDataPipeline,
    ProcessingStage,
    build_basic_analytics,
    build_copy_paste_prompt,
)


def _rec(entity_id, value, source="salesforce"):
    return {
        "timestamp": time.time(),
        "source": source,
        "entity_id": entity_id,
        "value": value,
        "metadata": {},
    }


def test_layers_1_to_3_resolve_without_llm_and_return_basic_analytics():
    pipeline = MultiLayerDataPipeline()  # no router: Layers 1-3 only
    result = pipeline.process_record(_rec("account_clean", 100))

    assert result.processing_stage in (ProcessingStage.ML_FEATURE, ProcessingStage.STATISTICAL)
    assert result.llm_bypassed is True
    assert result.needs_user_llm is False
    assert result.copy_paste_prompt is None
    # Basic analytics from previous layers is still returned.
    assert result.basic_analytics is not None
    assert result.basic_analytics["entity_id"] == "account_clean"
    assert result.basic_analytics["verdict"] == "resolved_locally"
    d = result.to_dict()
    assert d["basic_analytics"] == result.basic_analytics
    assert d["needs_user_llm"] is False


def test_no_router_handoff_returns_analytics_plus_copy_paste_prompt():
    pipeline = MultiLayerDataPipeline()  # no router on purpose
    pipeline.layer2.set_metric_threshold("salesforce_acct_hot", upper=100)

    result = pipeline.process_record(_rec("acct_hot", 250))

    assert result.llm_bypassed is True
    assert result.needs_user_llm is True
    assert result.basic_analytics is not None
    assert result.basic_analytics["anomaly_detected"] is True
    assert result.basic_analytics["verdict"] == "needs_human_review"
    prompt = result.copy_paste_prompt or ""
    assert len(prompt) > 50 and len(prompt) < 900
    assert "paste this into any LLM" in prompt
    assert "acct_hot" in prompt
    assert "150 words" in prompt
    assert result.llm_decision_audit.get("has_copy_paste_prompt") is True


def test_llm_error_handoff_keeps_stage_and_hands_prompt():
    class FailRouter:
        def generate(self, prompt):
            raise RuntimeError("boom offline")

    pipeline = MultiLayerDataPipeline(model_router=FailRouter())
    pipeline.layer2.set_metric_threshold("salesforce_acct_boom", upper=100)

    result = pipeline.process_record(_rec("acct_boom", 9999))

    assert result.processing_stage is ProcessingStage.LLM_REQUIRED
    assert result.needs_user_llm is True
    assert result.basic_analytics is not None
    assert result.copy_paste_prompt is not None
    assert "likely causes" in result.copy_paste_prompt


def test_degraded_offline_llm_hands_prompt():
    from omni_one.core.model_router import ModelRouter

    pipeline = MultiLayerDataPipeline(model_router=ModelRouter())
    pipeline.layer2.set_metric_threshold("salesforce_acct_deg", upper=10)
    result = pipeline.process_record(_rec("acct_deg", 999))

    assert result.layer4_llm_response is not None
    if str(result.layer4_llm_response).startswith("[DEGRADED"):
        assert result.needs_user_llm is True
        assert result.copy_paste_prompt is not None
        assert result.basic_analytics is not None


def test_build_helpers_are_short_and_deterministic():
    analytics = build_basic_analytics(
        {"entity_id": "e1", "source": "orders", "value": 42},
        {"anomaly_detected": True, "anomalies": [
            {"type": "outlier", "severity": "high", "explanation": "spike explanation here"}]},
        {"predictions": {"priority": {"value": "high", "score": 0.8, "reasons": ["High anomaly"]}}},
        0.7,
    )
    assert analytics["verdict"] == "needs_human_review"
    prompt = build_copy_paste_prompt(analytics)
    assert len(prompt) < 900
    # Deterministic: same input -> same prompt.
    assert build_copy_paste_prompt(analytics) == prompt
