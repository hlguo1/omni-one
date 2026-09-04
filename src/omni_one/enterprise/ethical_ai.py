"""
Enterprise Ethical AI Governance
Advanced bias detection, fairness monitoring, and explainable AI
"""

import hashlib
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, List

import numpy as np


class EthicalMonitor:
    """Comprehensive ethical AI monitoring and governance."""

    PROTECTED_ATTRIBUTES = {"gender", "race", "age_group", "ethnicity", "disability_status"}
    MAX_LOG = 1000

    def __init__(self):
        self.bias_detectors = {
            "demographic_parity": self._check_demographic_parity,
            "equal_opportunity": self._check_equal_opportunity,
            "disparate_impact": self._check_disparate_impact,
        }

        self.fairness_metrics = {}
        self.decision_log: deque = deque(maxlen=self.MAX_LOG)

    def analyze_decision(
        self,
        model_output: Any,
        input_data: Dict[str, Any],
        decision_context: str,
    ) -> Dict[str, Any]:
        """Comprehensive ethical analysis of an AI decision."""
        bias_scores = {
            bias_type: detector(model_output, input_data)
            for bias_type, detector in self.bias_detectors.items()
        }
        fairness_metrics = self._calculate_fairness_metrics(model_output, input_data)
        explainability = self._generate_explanation(model_output, input_data)
        ethical_assessment = self._assess_ethical_compliance(
            bias_scores, fairness_metrics, decision_context
        )
        recommendations = self._generate_recommendations(bias_scores, fairness_metrics)
        decision_id = self._make_decision_id(model_output, input_data, decision_context)

        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "decision_id": decision_id,
            "context": decision_context,
            "bias_scores": bias_scores,
            "fairness_metrics": fairness_metrics,
            "explainability": explainability,
            "ethical_assessment": ethical_assessment,
            "recommendations": recommendations,
        }
        self.decision_log.append(decision_record)

        return {
            "bias_score": float(np.mean(list(bias_scores.values()))),
            "fairness_metrics": fairness_metrics,
            "explainability": explainability,
            "ethical_assessment": ethical_assessment,
            "recommendations": recommendations,
            "decision_id": decision_id,
        }

    def _check_demographic_parity(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Return deterministic bias risk from protected attribute dependence."""
        return self._protected_dependency_risk(model_output, input_data)

    def _check_equal_opportunity(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Return deterministic opportunity risk from protected attribute dependence."""
        return self._protected_dependency_risk(model_output, input_data)

    def _check_disparate_impact(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Return deterministic disparate impact risk from protected attribute dependence."""
        return self._protected_dependency_risk(model_output, input_data)

    def _calculate_fairness_metrics(self, model_output: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate deterministic fairness metrics."""
        explainability = self._generate_explanation(model_output, input_data)
        counterfactual = explainability["counterfactual_fairness"]
        score = counterfactual["score"]

        return {
            "demographic_parity": score,
            "equal_opportunity": score,
            "disparate_impact": score,
            "accuracy_parity": score,
            "false_positive_parity": score,
            "counterfactual_fairness": score,
            "counterfactual_fairness_passed": counterfactual["passed"],
            "protected_attribute_count": len(explainability["protected_attributes"]),
            "legitimate_feature_count": len(explainability["legitimate_features"]),
        }

    def _generate_explanation(self, model_output: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a deterministic, data-derived explanation of the decision."""
        protected_attributes = sorted(
            attr for attr in self.PROTECTED_ATTRIBUTES
            if attr in input_data
        )
        legitimate_features = sorted(
            key for key in input_data
            if key not in self.PROTECTED_ATTRIBUTES and not key.startswith("_")
        )
        declared_factors = self._extract_declared_factors(model_output)
        primary_factors = [
            factor for factor in declared_factors
            if factor in legitimate_features
        ] or legitimate_features

        protected_dependencies = [
            attr for attr in protected_attributes
            if self._model_depends_on_attribute(model_output, attr)
        ]
        counterfactuals = [
            {
                "attribute": attr,
                "original_value": input_data.get(attr),
                "counterfactual_value": None,
                "decision_changed": attr in protected_dependencies,
            }
            for attr in protected_attributes
        ]
        passed = len(protected_dependencies) == 0

        return {
            "summary": self._build_explanation_summary(primary_factors, protected_dependencies),
            "primary_factors": primary_factors,
            "legitimate_features": legitimate_features,
            "protected_attributes": protected_attributes,
            "protected_attribute_dependencies": protected_dependencies,
            "counterfactuals": counterfactuals,
            "counterfactual_fairness": {
                "passed": passed,
                "score": 1.0 if passed else 0.0,
                "failed_attributes": protected_dependencies,
            },
        }

    def _assess_ethical_compliance(
        self,
        bias_scores: Dict[str, float],
        fairness_metrics: Dict[str, Any],
        context: str,
    ) -> Dict[str, Any]:
        """Assess overall ethical compliance."""
        thresholds = {
            "loan_approval": {"max_bias": 0.05, "min_fairness": 0.90},
            "hiring": {"max_bias": 0.03, "min_fairness": 0.95},
            "content_moderation": {"max_bias": 0.08, "min_fairness": 0.85},
        }

        threshold = thresholds.get(context, {"max_bias": 0.05, "min_fairness": 0.90})

        avg_bias = float(np.mean(list(bias_scores.values())))
        numeric_fairness = [
            value for value in fairness_metrics.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        avg_fairness = float(np.mean(numeric_fairness)) if numeric_fairness else 0.0

        compliant = avg_bias <= threshold["max_bias"] and avg_fairness >= threshold["min_fairness"]

        return {
            "compliant": compliant,
            "average_bias": avg_bias,
            "average_fairness": avg_fairness,
            "threshold_bias": threshold["max_bias"],
            "threshold_fairness": threshold["min_fairness"],
            "risk_level": "high" if not compliant else "low",
        }

    def _generate_recommendations(
        self,
        bias_scores: Dict[str, float],
        fairness_metrics: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations for improving ethical performance."""
        recommendations = []

        if not fairness_metrics.get("counterfactual_fairness_passed", True):
            recommendations.append("Remove protected attributes from decision logic")
            recommendations.append("Require human review for this decision")

        if np.mean(list(bias_scores.values())) > 0.05:
            recommendations.append("Implement additional bias mitigation techniques")
            recommendations.append("Consider human review for high-risk decisions")

        if fairness_metrics.get("counterfactual_fairness", 1.0) < 0.95:
            recommendations.append("Review training data for demographic representation")
            recommendations.append("Implement fairness-aware algorithms")

        if len(recommendations) == 0:
            recommendations.append("Continue monitoring - current ethical performance is acceptable")

        return recommendations

    def get_ethical_report(self, time_range: str = "24h") -> Dict[str, Any]:
        """Generate comprehensive ethical performance report."""
        recent_decisions = list(self.decision_log)[-100:]

        if not recent_decisions:
            return {"error": "No decision data available"}

        total_decisions = len(recent_decisions)
        compliant_decisions = sum(
            1 for decision in recent_decisions
            if decision["ethical_assessment"]["compliant"]
        )
        compliance_rate = compliant_decisions / total_decisions

        avg_bias = float(np.mean([
            decision["bias_scores"]["demographic_parity"]
            for decision in recent_decisions
        ]))
        avg_fairness = float(np.mean([
            decision["fairness_metrics"]["demographic_parity"]
            for decision in recent_decisions
        ]))

        context_stats = {}
        for decision in recent_decisions:
            context = decision["context"]
            if context not in context_stats:
                context_stats[context] = {"count": 0, "compliant": 0}
            context_stats[context]["count"] += 1
            if decision["ethical_assessment"]["compliant"]:
                context_stats[context]["compliant"] += 1

        return {
            "time_range": time_range,
            "total_decisions": total_decisions,
            "compliance_rate": compliance_rate,
            "average_bias_score": avg_bias,
            "average_fairness_score": avg_fairness,
            "context_breakdown": context_stats,
            "recommendations": self._generate_system_recommendations(compliance_rate, avg_bias),
        }

    def _generate_system_recommendations(self, compliance_rate: float, avg_bias: float) -> List[str]:
        """Generate system-level recommendations."""
        recommendations = []

        if compliance_rate < 0.95:
            recommendations.append("Implement automated bias detection alerts")
            recommendations.append("Consider third-party ethical AI audit")

        if avg_bias > 0.05:
            recommendations.append("Review and augment training datasets")
            recommendations.append("Implement bias mitigation preprocessing")

        if len(recommendations) == 0:
            recommendations.append("Ethical performance is within acceptable parameters")

        return recommendations

    def _protected_dependency_risk(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        protected_attributes = [
            attr for attr in self.PROTECTED_ATTRIBUTES
            if attr in input_data
        ]
        if not protected_attributes:
            return 0.0

        dependent_count = sum(
            1 for attr in protected_attributes
            if self._model_depends_on_attribute(model_output, attr)
        )
        return dependent_count / len(protected_attributes)

    def _extract_declared_factors(self, model_output: Any) -> List[str]:
        if not isinstance(model_output, dict):
            return []

        factor_keys = [
            "used_features",
            "features_used",
            "decision_factors",
            "depends_on",
            "reason_codes",
        ]
        factors = []
        for key in factor_keys:
            raw_factors = model_output.get(key, [])
            if isinstance(raw_factors, str):
                raw_factors = [raw_factors]
            if isinstance(raw_factors, list):
                factors.extend(str(factor) for factor in raw_factors)
        return sorted(set(factors))

    def _model_depends_on_attribute(self, model_output: Any, attribute: str) -> bool:
        if isinstance(model_output, dict):
            if model_output.get("protected_attribute_used") is True:
                return True

            if attribute in self._extract_declared_factors(model_output):
                return True

            text_fields = [
                str(model_output.get("explanation", "")),
                str(model_output.get("reason", "")),
                str(model_output.get("rationale", "")),
            ]
            return any(attribute.lower() in text.lower() for text in text_fields)

        return attribute.lower() in str(model_output).lower()

    def _build_explanation_summary(
        self,
        primary_factors: List[str],
        protected_dependencies: List[str],
    ) -> str:
        if protected_dependencies:
            return (
                "Decision may depend on protected attributes: "
                + ", ".join(protected_dependencies)
            )
        if primary_factors:
            return "Decision based on legitimate features: " + ", ".join(primary_factors)
        return "No explicit decision factors were provided"

    def _make_decision_id(
        self,
        model_output: Any,
        input_data: Dict[str, Any],
        decision_context: str,
    ) -> str:
        payload = {
            "model_output": model_output,
            "input_data": input_data,
            "decision_context": decision_context,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
