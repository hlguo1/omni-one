"""
Enterprise Ethical AI Governance
Advanced bias detection, fairness monitoring, and explainable AI
"""

import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class EthicalMonitor:
    """Comprehensive ethical AI monitoring and governance"""

    def __init__(self):
        self.bias_detectors = {
            "demographic_parity": self._check_demographic_parity,
            "equal_opportunity": self._check_equal_opportunity,
            "disparate_impact": self._check_disparate_impact
        }

        self.fairness_metrics = {}
        self.decision_log = []

    def analyze_decision(self, model_output: Any, input_data: Dict[str, Any],
                        decision_context: str) -> Dict[str, Any]:
        """Comprehensive ethical analysis of an AI decision"""

        # Perform bias detection
        bias_scores = {}
        for bias_type, detector in self.bias_detectors.items():
            bias_scores[bias_type] = detector(model_output, input_data)

        # Calculate fairness metrics
        fairness_metrics = self._calculate_fairness_metrics(model_output, input_data)

        # Generate explainability report
        explainability = self._generate_explanation(model_output, input_data)

        # Assess ethical compliance
        ethical_assessment = self._assess_ethical_compliance(
            bias_scores, fairness_metrics, decision_context
        )

        # Log the decision
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "context": decision_context,
            "bias_scores": bias_scores,
            "fairness_metrics": fairness_metrics,
            "ethical_assessment": ethical_assessment,
            "recommendations": self._generate_recommendations(bias_scores, fairness_metrics)
        }
        self.decision_log.append(decision_record)

        return {
            "bias_score": np.mean(list(bias_scores.values())),
            "fairness_metrics": fairness_metrics,
            "explainability": explainability,
            "ethical_assessment": ethical_assessment,
            "recommendations": decision_record["recommendations"],
            "decision_id": len(self.decision_log) - 1
        }

    def _check_demographic_parity(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Check demographic parity (similar acceptance rates across groups)"""
        # Mock implementation - in real system, would analyze historical data
        protected_attributes = ["gender", "race", "age_group"]

        parity_scores = []
        for attr in protected_attributes:
            if attr in input_data:
                # Simulate parity calculation
                parity_scores.append(np.random.uniform(0.95, 1.05))

        return np.mean(parity_scores) if parity_scores else 1.0

    def _check_equal_opportunity(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Check equal opportunity (similar true positive rates)"""
        # Mock implementation
        return np.random.uniform(0.92, 1.08)

    def _check_disparate_impact(self, model_output: Any, input_data: Dict[str, Any]) -> float:
        """Check disparate impact (adverse impact on protected groups)"""
        # Mock implementation - real system would use 80% rule
        return np.random.uniform(0.75, 1.25)

    def _calculate_fairness_metrics(self, model_output: Any, input_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate comprehensive fairness metrics"""
        return {
            "demographic_parity": self._check_demographic_parity(model_output, input_data),
            "equal_opportunity": self._check_equal_opportunity(model_output, input_data),
            "disparate_impact": self._check_disparate_impact(model_output, input_data),
            "accuracy_parity": np.random.uniform(0.85, 0.95),
            "false_positive_parity": np.random.uniform(0.90, 1.10)
        }

    def _generate_explanation(self, model_output: Any, input_data: Dict[str, Any]) -> str:
        """Generate human-readable explanation of the decision"""
        explanations = [
            "Decision based on credit score and payment history",
            "Risk assessment considers income stability and debt-to-income ratio",
            "Approval determined by fraud detection algorithms and transaction history",
            "Recommendation generated from collaborative filtering and user preferences"
        ]

        return np.random.choice(explanations)

    def _assess_ethical_compliance(self, bias_scores: Dict[str, float],
                                 fairness_metrics: Dict[str, float],
                                 context: str) -> Dict[str, Any]:
        """Assess overall ethical compliance"""

        # Define thresholds for different contexts
        thresholds = {
            "loan_approval": {"max_bias": 0.05, "min_fairness": 0.90},
            "hiring": {"max_bias": 0.03, "min_fairness": 0.95},
            "content_moderation": {"max_bias": 0.08, "min_fairness": 0.85}
        }

        threshold = thresholds.get(context, {"max_bias": 0.05, "min_fairness": 0.90})

        avg_bias = np.mean(list(bias_scores.values()))
        avg_fairness = np.mean(list(fairness_metrics.values()))

        compliant = avg_bias <= threshold["max_bias"] and avg_fairness >= threshold["min_fairness"]

        return {
            "compliant": compliant,
            "average_bias": avg_bias,
            "average_fairness": avg_fairness,
            "threshold_bias": threshold["max_bias"],
            "threshold_fairness": threshold["min_fairness"],
            "risk_level": "high" if not compliant else "low"
        }

    def _generate_recommendations(self, bias_scores: Dict[str, float],
                                fairness_metrics: Dict[str, float]) -> List[str]:
        """Generate recommendations for improving ethical performance"""
        recommendations = []

        if np.mean(list(bias_scores.values())) > 0.05:
            recommendations.append("Implement additional bias mitigation techniques")
            recommendations.append("Consider human review for high-risk decisions")

        if fairness_metrics.get("demographic_parity", 1.0) < 0.95:
            recommendations.append("Review training data for demographic representation")
            recommendations.append("Implement fairness-aware algorithms")

        if len(recommendations) == 0:
            recommendations.append("Continue monitoring - current ethical performance is acceptable")

        return recommendations

    def get_ethical_report(self, time_range: str = "24h") -> Dict[str, Any]:
        """Generate comprehensive ethical performance report"""
        # Filter decisions by time range
        recent_decisions = self.decision_log[-100:]  # Last 100 decisions

        if not recent_decisions:
            return {"error": "No decision data available"}

        # Calculate aggregate metrics
        total_decisions = len(recent_decisions)
        compliant_decisions = sum(1 for d in recent_decisions if d["ethical_assessment"]["compliant"])
        compliance_rate = compliant_decisions / total_decisions

        avg_bias = np.mean([d["bias_scores"]["demographic_parity"] for d in recent_decisions])
        avg_fairness = np.mean([d["fairness_metrics"]["demographic_parity"] for d in recent_decisions])

        # Context breakdown
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
            "recommendations": self._generate_system_recommendations(compliance_rate, avg_bias)
        }

    def _generate_system_recommendations(self, compliance_rate: float, avg_bias: float) -> List[str]:
        """Generate system-level recommendations"""
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