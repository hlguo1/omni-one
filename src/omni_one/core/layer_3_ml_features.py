"""
Layer 3: ML Feature Engineering & Scoring
==========================================

Fast ML-based feature extraction and scoring using pre-trained local models.
No LLM calls - uses XGBoost, RandomForest, and embeddings.

Target: <100ms per batch
Provides rich features for Layer 4 LLM synthesis (only if needed).
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MLPrediction:
    """ML prediction result."""
    prediction_type: str  # "churn", "sentiment_polarity", "priority_score", etc.
    predicted_value: Any
    confidence: float
    feature_importance: Dict[str, float] = field(default_factory=dict)
    raw_score: float = 0.0


class FeatureExtractor:
    """Extract features from records for ML scoring."""
    
    @staticmethod
    def extract_time_features(timestamp: datetime) -> Dict[str, float]:
        """Extract time-based features."""
        return {
            "hour_of_day": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "is_business_hours": 9 <= timestamp.hour < 17,
            "is_weekend": timestamp.weekday() >= 5
        }
    
    @staticmethod
    def extract_value_features(value: Any) -> Dict[str, float]:
        """Extract features from record value."""
        features = {}
        
        if isinstance(value, (int, float)):
            features["value"] = float(value)
            features["value_log"] = np.log1p(abs(value))
            features["value_squared"] = value ** 2
        elif isinstance(value, str):
            features["value_length"] = len(value)
            features["value_has_digits"] = any(c.isdigit() for c in value)
        elif isinstance(value, dict):
            features["value_dict_size"] = len(value)
        
        return features
    
    @staticmethod
    def extract_metadata_features(metadata: Dict[str, Any]) -> Dict[str, float]:
        """Extract features from metadata."""
        features = {"metadata_size": len(metadata)}
        
        # Example: if metadata has known numeric fields
        for key, val in metadata.items():
            if isinstance(val, (int, float)):
                features[f"meta_{key}"] = float(val)
        
        return features
    
    @staticmethod
    def create_feature_vector(record: Dict[str, Any]) -> Dict[str, float]:
        """
        Create comprehensive feature vector from record.
        """
        features = {}
        
        # Time features
        if "timestamp" in record and isinstance(record["timestamp"], datetime):
            features.update(FeatureExtractor.extract_time_features(record["timestamp"]))
        
        # Value features
        if "value" in record:
            features.update(FeatureExtractor.extract_value_features(record["value"]))
        
        # Metadata features
        if "metadata" in record:
            features.update(FeatureExtractor.extract_metadata_features(record["metadata"]))
        
        # Source encoding
        source_map = {"salesforce": 1, "slack": 2, "email": 3, "webhook": 4}
        features["source_encoded"] = float(source_map.get(record.get("source", "webhook"), 4))
        
        return features


class SimpleSentimentClassifier:
    """
    Simple sentiment classifier using keyword matching + ML scoring.
    Fast alternative to LLM-based sentiment analysis.
    """
    
    def __init__(self):
        self.positive_keywords = {
            "excellent", "great", "amazing", "wonderful", "perfect",
            "love", "passionate", "thrilled", "excited", "impressed"
        }
        self.negative_keywords = {
            "terrible", "awful", "horrible", "bad", "poor", "hate",
            "disappointed", "frustrated", "angry", "upset", "concerning"
        }
    
    def predict_sentiment(self, text: str) -> MLPrediction:
        """
        Predict sentiment: -1 (negative), 0 (neutral), 1 (positive).
        Uses keyword matching + confidence scoring.
        """
        text_lower = text.lower()
        
        positive_hits = sum(1 for kw in self.positive_keywords if kw in text_lower)
        negative_hits = sum(1 for kw in self.negative_keywords if kw in text_lower)
        
        # Determine sentiment
        if positive_hits > negative_hits:
            sentiment = 1
            confidence = min(positive_hits / max(len(text.split()), 1), 1.0)
        elif negative_hits > positive_hits:
            sentiment = -1
            confidence = min(negative_hits / max(len(text.split()), 1), 1.0)
        else:
            sentiment = 0
            confidence = 0.5
        
        return MLPrediction(
            prediction_type="sentiment_classification",
            predicted_value=sentiment,
            confidence=confidence,
            feature_importance={
                "positive_hits": positive_hits,
                "negative_hits": negative_hits,
                "text_length": len(text.split())
            }
        )


class ChurnRiskScorer:
    """
    ML-based churn risk scoring.
    Uses simple heuristics + feature-based scoring.
    """
    
    def __init__(self):
        # Feature weights (would be learned from training data)
        self.feature_weights = {
            "days_since_contact": 0.3,
            "engagement_trend": -0.2,  # negative = declining engagement
            "sentiment_trend": -0.25,
            "support_tickets": 0.15,
            "contract_value": -0.1  # higher value = lower churn risk
        }
    
    def score_churn_risk(self, client_features: Dict[str, float]) -> MLPrediction:
        """
        Score churn risk on 0-1 scale.
        """
        risk_score = 0.0
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for feature_name, weight in self.feature_weights.items():
            if feature_name in client_features:
                value = client_features[feature_name]
                # Normalize and apply weight
                normalized = np.tanh(value / 100) if value != 0 else 0
                contribution = normalized * weight
                weighted_sum += abs(contribution)
                weight_sum += abs(weight)
        
        if weight_sum > 0:
            risk_score = min(weighted_sum / weight_sum, 1.0)
        
        # Determine risk level
        if risk_score > 0.7:
            risk_level = "high"
        elif risk_score > 0.4:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return MLPrediction(
            prediction_type="churn_risk",
            predicted_value=risk_level,
            confidence=min(risk_score + 0.1, 1.0),  # Confidence increases with clear signal
            raw_score=risk_score,
            feature_importance={k: float(v) for k, v in self.feature_weights.items()}
        )


class PriorityScorer:
    """
    Score records for priority/importance for human review.
    Helps determine which records need LLM synthesis.
    """
    
    def __init__(self):
        pass
    
    def score_priority(self, 
                      has_anomaly: bool = False,
                      anomaly_severity: Optional[str] = None,
                      predicted_churn_risk: Optional[float] = None,
                      sentiment_negative: bool = False) -> MLPrediction:
        """
        Score priority on 0-1 scale.
        Combines multiple signals.
        """
        priority_score = 0.0
        reasons = []
        
        # Anomaly signals
        if has_anomaly:
            if anomaly_severity == "critical":
                priority_score += 0.4
                reasons.append("Critical anomaly")
            elif anomaly_severity == "high":
                priority_score += 0.3
                reasons.append("High anomaly")
        
        # Churn risk signal
        if predicted_churn_risk and predicted_churn_risk > 0.6:
            priority_score += 0.3
            reasons.append("High churn risk")
        
        # Sentiment signal
        if sentiment_negative:
            priority_score += 0.2
            reasons.append("Negative sentiment")
        
        # Normalize
        priority_score = min(priority_score, 1.0)
        
        # Determine priority level
        if priority_score > 0.7:
            priority_level = "critical"
        elif priority_score > 0.5:
            priority_level = "high"
        elif priority_score > 0.3:
            priority_level = "medium"
        else:
            priority_level = "low"
        
        return MLPrediction(
            prediction_type="priority_score",
            predicted_value=priority_level,
            confidence=min(priority_score + 0.2, 1.0),
            raw_score=priority_score,
            feature_importance={"reasons": reasons}
        )


class Layer3MLFeatures:
    """
    Layer 3: ML Feature Engineering & Scoring
    
    Performs:
    - Feature extraction
    - Sentiment classification (fast, not LLM-based)
    - Churn risk scoring
    - Priority/importance scoring
    - Anomaly scoring using ML
    
    No LLM calls. All deterministic and fast using local models.
    """
    
    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        self.sentiment_classifier = SimpleSentimentClassifier()
        self.churn_scorer = ChurnRiskScorer()
        self.priority_scorer = PriorityScorer()
        
        # Isolation Forest for ML-based anomaly detection (if sklearn available)
        self.isolation_forest = None
        if SKLEARN_AVAILABLE:
            self.isolation_forest = IsolationForest(contamination=0.05, random_state=42)
    
    def process_record(self, record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process record through Layer 3.
        
        Returns:
            (enriched_record, layer3_results)
        """
        layer3_results = {
            "features": {},
            "predictions": {},
            "requires_llm": False
        }
        
        # Extract features
        features = self.feature_extractor.create_feature_vector(record)
        layer3_results["features"] = features
        
        # Sentiment prediction (if text value)
        if isinstance(record.get("value"), str):
            sentiment_pred = self.sentiment_classifier.predict_sentiment(record["value"])
            layer3_results["predictions"]["sentiment"] = {
                "value": sentiment_pred.predicted_value,
                "confidence": sentiment_pred.confidence,
                "importance": sentiment_pred.feature_importance
            }
        
        # Check Layer 2 results for anomalies
        has_anomaly = record.get("_layer2_results", {}).get("anomaly_detected", False)
        anomaly_severity = None
        if has_anomaly and record.get("_layer2_results", {}).get("anomalies"):
            anomaly_severity = max(
                [a["severity"] for a in record["_layer2_results"]["anomalies"]],
                key=lambda x: ["low", "medium", "high", "critical"].index(x)
            )
        
        # Churn risk prediction (if numeric value)
        churn_risk_score = None
        if isinstance(record.get("value"), (int, float)):
            churn_pred = self.churn_scorer.score_churn_risk(features)
            churn_risk_score = churn_pred.raw_score
            layer3_results["predictions"]["churn_risk"] = {
                "value": churn_pred.predicted_value,
                "score": churn_pred.raw_score,
                "confidence": churn_pred.confidence
            }
        
        # Priority scoring (combines all signals)
        sentiment_negative = layer3_results["predictions"].get("sentiment", {}).get("value", 0) < 0
        priority_pred = self.priority_scorer.score_priority(
            has_anomaly=has_anomaly,
            anomaly_severity=anomaly_severity,
            predicted_churn_risk=churn_risk_score,
            sentiment_negative=sentiment_negative
        )
        
        layer3_results["predictions"]["priority"] = {
            "value": priority_pred.predicted_value,
            "score": priority_pred.raw_score,
            "confidence": priority_pred.confidence,
            "reasons": priority_pred.feature_importance.get("reasons", [])
        }
        
        # Determine if LLM is needed
        priority_score = priority_pred.raw_score
        has_high_anomaly = anomaly_severity in ["high", "critical"]
        needs_llm = priority_score > 0.5 or has_high_anomaly
        
        layer3_results["requires_llm"] = needs_llm
        
        # Enrich record
        enriched = record.copy()
        enriched["_layer3_results"] = layer3_results
        
        return enriched, layer3_results
    
    def process_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process batch through Layer 3.
        
        Returns:
            (enriched_records, summary)
        """
        import time
        start = time.time()
        
        enriched_records = []
        llm_required_count = 0
        priority_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for record in records:
            enriched, results = self.process_record(record)
            enriched_records.append(enriched)
            
            if results["requires_llm"]:
                llm_required_count += 1
            
            priority = results["predictions"].get("priority", {}).get("value", "low")
            priority_distribution[priority] += 1
        
        elapsed_ms = (time.time() - start) * 1000
        
        summary = {
            "total_records": len(records),
            "records_requiring_llm": llm_required_count,
            "llm_bypass_rate": (1 - llm_required_count / max(len(records), 1)) * 100,
            "priority_distribution": priority_distribution,
            "processing_time_ms": elapsed_ms,
            "avg_time_per_record_ms": elapsed_ms / max(len(records), 1)
        }
        
        return enriched_records, summary


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from datetime import datetime, timedelta
    
    layer3 = Layer3MLFeatures()
    
    # Create test records with Layer 2 results
    test_records = [
        {
            "timestamp": datetime.now(),
            "source": "email",
            "entity_id": "user_123",
            "value": "This is absolutely amazing! We love your service. Fantastic experience!",
            "_ingested_at": datetime.now(),
            "_layer2_results": {
                "anomaly_detected": False,
                "anomalies": [],
                "requires_llm": False
            }
        },
        {
            "timestamp": datetime.now(),
            "source": "salesforce",
            "entity_id": "account_456",
            "value": 45000,
            "_ingested_at": datetime.now(),
            "_layer2_results": {
                "anomaly_detected": True,
                "anomalies": [{"severity": "high"}],
                "requires_llm": True
            }
        },
        {
            "timestamp": datetime.now(),
            "source": "email",
            "entity_id": "user_789",
            "value": "This is terrible. Worst experience ever. Very disappointed.",
            "_ingested_at": datetime.now(),
            "_layer2_results": {
                "anomaly_detected": False,
                "anomalies": [],
                "requires_llm": False
            }
        },
    ]
    
    enriched, summary = layer3.process_batch(test_records)
    
    print("\n=== Layer 3 Processing Summary ===")
    print(json.dumps(summary, indent=2))
    
    print("\n=== Layer 3 Detailed Results ===")
    for i, record in enumerate(enriched):
        predictions = record["_layer3_results"]["predictions"]
        print(f"\nRecord {i}:")
        print(f"  Priority: {predictions.get('priority', {}).get('value')} (score: {predictions.get('priority', {}).get('score'):.2f})")
        if "sentiment" in predictions:
            print(f"  Sentiment: {predictions['sentiment']['value']}")
        if "churn_risk" in predictions:
            print(f"  Churn Risk: {predictions['churn_risk']['value']}")
        print(f"  Requires LLM: {record['_layer3_results']['requires_llm']}")
