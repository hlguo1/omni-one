import sys
from pathlib import Path


ENTERPRISE_DIR = Path(__file__).resolve().parents[2] / "src" / "omni_one" / "enterprise"
sys.path.insert(0, str(ENTERPRISE_DIR))

from ethical_ai import EthicalMonitor


def loan_input():
    return {
        "credit_score": 730,
        "income": 125000,
        "debt_to_income": 0.24,
        "gender": "female",
        "race": "asian",
    }


def test_fair_decision_is_deterministic_and_separates_protected_attributes():
    model_output = {
        "decision": "approved",
        "used_features": ["credit_score", "income", "debt_to_income"],
        "explanation": "Approved because credit and affordability signals are strong.",
    }

    first = EthicalMonitor().analyze_decision(model_output, loan_input(), "loan_approval")
    second = EthicalMonitor().analyze_decision(model_output, loan_input(), "loan_approval")

    assert first == second
    assert first["bias_score"] == 0.0
    assert first["fairness_metrics"]["counterfactual_fairness"] == 1.0
    assert first["fairness_metrics"]["counterfactual_fairness_passed"] is True
    assert first["fairness_metrics"]["protected_attribute_count"] == 2
    assert first["fairness_metrics"]["legitimate_feature_count"] == 3
    assert first["ethical_assessment"]["compliant"] is True
    assert first["ethical_assessment"]["risk_level"] == "low"
    assert first["explainability"]["protected_attributes"] == ["gender", "race"]
    assert first["explainability"]["primary_factors"] == [
        "credit_score",
        "debt_to_income",
        "income",
    ]
    assert all(
        counterfactual["decision_changed"] is False
        for counterfactual in first["explainability"]["counterfactuals"]
    )


def test_protected_attribute_dependency_fails_counterfactual_fairness():
    monitor = EthicalMonitor()
    model_output = {
        "decision": "manual_review",
        "used_features": ["credit_score", "gender"],
        "explanation": "Manual review because gender appeared in the decision rule.",
    }

    report = monitor.analyze_decision(model_output, loan_input(), "loan_approval")

    assert report["bias_score"] == 0.5
    assert report["fairness_metrics"]["counterfactual_fairness"] == 0.0
    assert report["fairness_metrics"]["counterfactual_fairness_passed"] is False
    assert report["ethical_assessment"]["compliant"] is False
    assert report["ethical_assessment"]["risk_level"] == "high"
    assert report["explainability"]["protected_attribute_dependencies"] == ["gender"]
    assert report["explainability"]["counterfactual_fairness"]["failed_attributes"] == ["gender"]
    assert {
        "Remove protected attributes from decision logic",
        "Require human review for this decision",
    }.issubset(set(report["recommendations"]))


def test_decision_log_records_same_audit_fields_returned_to_caller():
    monitor = EthicalMonitor()
    model_output = {
        "decision": "approved",
        "decision_factors": ["credit_score", "income"],
    }

    report = monitor.analyze_decision(model_output, loan_input(), "loan_approval")
    logged = monitor.decision_log[0]

    assert logged["decision_id"] == report["decision_id"]
    assert logged["fairness_metrics"] == report["fairness_metrics"]
    assert logged["explainability"] == report["explainability"]
    assert logged["ethical_assessment"] == report["ethical_assessment"]
    assert logged["recommendations"] == report["recommendations"]

    summary = monitor.get_ethical_report()
    assert summary["total_decisions"] == 1
    assert summary["compliance_rate"] == 1.0
    assert summary["average_bias_score"] == 0.0
    assert summary["average_fairness_score"] == 1.0
