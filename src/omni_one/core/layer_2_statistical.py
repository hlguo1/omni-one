"""
Layer 2: Statistical Anomaly Detection
=======================================

Fast, deterministic anomaly detection for time series data.
Uses z-score, isolation forest, moving averages, and statistical methods.

Target: <10ms per batch
No LLM calls - pure mathematical/statistical detection.
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    anomaly_type: str  # "outlier", "trend_change", "pattern_deviation", "threshold_breach"
    severity: str  # "low", "medium", "high", "critical"
    confidence: float  # 0.0 to 1.0
    score: float  # 0.0 to 1.0
    explanation: str  # Human-readable explanation
    metrics: Dict[str, Any] = field(default_factory=dict)  # Raw metrics for Layer 3/4


class StatisticalAnomalyDetector:
    """
    Statistical anomaly detection using Z-score and moving statistics.
    Fast, interpretable, no ML training needed.
    """
    
    def __init__(self, window_size: int = 50, z_threshold: float = 3.0):
        """
        Args:
            window_size: Number of historical points to consider
            z_threshold: Number of standard deviations for outlier detection
        """
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.data_windows: Dict[str, deque] = {}  # Per entity/metric windows
    
    def _ensure_numeric(self, value: Any) -> Optional[float]:
        """Convert value to numeric or None."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None
    
    def detect_outlier(self, entity_id: str, current_value: float) -> AnomalyResult:
        """
        Detect if current value is a statistical outlier using Z-score.
        """
        if entity_id not in self.data_windows:
            self.data_windows[entity_id] = deque(maxlen=self.window_size)
        
        window = self.data_windows[entity_id]
        
        # Need at least 2 points for statistics
        if len(window) < 2:
            window.append(current_value)
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type="insufficient_data",
                severity="low",
                confidence=0.0,
                score=0.0,
                explanation="Insufficient historical data"
            )
        
        # Compute statistics
        values = np.array(list(window))
        mean = np.mean(values)
        std = np.std(values)
        
        # Handle case where all values are the same
        if std == 0:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type="constant_signal",
                severity="low",
                confidence=0.0,
                score=0.0,
                explanation="All historical values are identical"
            )
        
        # Compute z-score
        z_score = abs((current_value - mean) / std)
        is_anomaly = z_score > self.z_threshold
        
        # Add to window
        window.append(current_value)
        
        # Confidence based on z-score magnitude
        confidence = min(z_score / self.z_threshold, 1.0) if is_anomaly else 0.0
        
        # Determine severity
        if z_score > 4.0:
            severity = "critical"
        elif z_score > 3.0:
            severity = "high"
        elif z_score > 2.0:
            severity = "medium"
        else:
            severity = "low"
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type="outlier",
            severity=severity,
            confidence=confidence,
            score=z_score / 5.0,  # Normalize to 0-1
            explanation=f"Value {current_value} is {z_score:.1f} std deviations from mean {mean:.2f}",
            metrics={
                "z_score": z_score,
                "mean": mean,
                "std": std,
                "current_value": current_value
            }
        )


class ThresholdAnomalyDetector:
    """Rule-based threshold violation detection."""
    
    def __init__(self):
        self.thresholds: Dict[str, Dict[str, float]] = {}
    
    def set_threshold(self, metric_name: str, lower: Optional[float] = None, upper: Optional[float] = None):
        """Set threshold for a metric."""
        self.thresholds[metric_name] = {"lower": lower, "upper": upper}
    
    def detect_threshold_breach(self, metric_name: str, value: float) -> AnomalyResult:
        """Check if value violates thresholds."""
        if metric_name not in self.thresholds:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type="no_threshold",
                severity="low",
                confidence=0.0,
                score=0.0,
                explanation=f"No threshold defined for {metric_name}"
            )
        
        thresholds = self.thresholds[metric_name]
        lower = thresholds.get("lower")
        upper = thresholds.get("upper")
        
        breach_lower = lower is not None and value < lower
        breach_upper = upper is not None and value > upper
        
        if breach_lower or breach_upper:
            if breach_lower:
                explanation = f"Value {value} below lower threshold {lower}"
                severity = "high"
            else:
                explanation = f"Value {value} above upper threshold {upper}"
                severity = "high"
            
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type="threshold_breach",
                severity=severity,
                confidence=1.0,
                score=1.0,
                explanation=explanation,
                metrics={"value": value, "lower_threshold": lower, "upper_threshold": upper}
            )
        
        return AnomalyResult(
            is_anomaly=False,
            anomaly_type="within_threshold",
            severity="low",
            confidence=0.0,
            score=0.0,
            explanation=f"Value {value} within acceptable range"
        )


class TrendAnomalyDetector:
    """Detect sudden trend changes using moving averages."""
    
    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window
        self.data_windows: Dict[str, deque] = {}
    
    def _get_moving_average(self, values: List[float], window: int) -> Optional[float]:
        """Compute moving average."""
        if len(values) < window:
            return None
        return np.mean(values[-window:])
    
    def detect_trend_change(self, entity_id: str, current_value: float) -> AnomalyResult:
        """Detect sudden changes in trend."""
        if entity_id not in self.data_windows:
            self.data_windows[entity_id] = deque(maxlen=self.long_window)
        
        window = self.data_windows[entity_id]
        window.append(current_value)
        
        # Need enough data for moving averages
        if len(window) < self.long_window:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type="insufficient_data",
                severity="low",
                confidence=0.0,
                score=0.0,
                explanation="Insufficient data for trend detection"
            )
        
        values = list(window)
        short_ma = self._get_moving_average(values, self.short_window)
        long_ma = self._get_moving_average(values, self.long_window)
        
        if short_ma is None or long_ma is None:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_type="insufficient_data",
                severity="low",
                confidence=0.0,
                score=0.0,
                explanation="Cannot compute moving averages"
            )
        
        # Calculate % change
        pct_change = ((short_ma - long_ma) / abs(long_ma)) * 100 if long_ma != 0 else 0
        
        # Significant trend change if >15% deviation
        is_anomaly = abs(pct_change) > 15
        
        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type="trend_change",
            severity="high" if is_anomaly else "low",
            confidence=min(abs(pct_change) / 30, 1.0),
            score=min(abs(pct_change) / 100, 1.0),
            explanation=f"Trend changed by {pct_change:.1f}% (short MA {short_ma:.2f} vs long MA {long_ma:.2f})",
            metrics={
                "short_ma": short_ma,
                "long_ma": long_ma,
                "pct_change": pct_change
            }
        )


class Layer2StatisticalProcessing:
    """
    Layer 2: Fast Statistical Anomaly Detection
    
    Detects anomalies using purely statistical methods:
    - Z-score outlier detection
    - Threshold violations
    - Trend changes
    
    No LLM calls, no ML training, all deterministic.
    """
    
    def __init__(self):
        self.z_detector = StatisticalAnomalyDetector()
        self.threshold_detector = ThresholdAnomalyDetector()
        self.trend_detector = TrendAnomalyDetector()
        
        # Default thresholds for common metrics
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """Setup sensible default thresholds."""
        # Customer sentiment (-1 to 1)
        self.threshold_detector.set_threshold("sentiment", lower=-1.0, upper=1.0)
        # Revenue typically positive
        self.threshold_detector.set_threshold("revenue", lower=0.0)
    
    def set_metric_threshold(self, metric_name: str, lower: Optional[float] = None, upper: Optional[float] = None):
        """Allow dynamic threshold configuration."""
        self.threshold_detector.set_threshold(metric_name, lower, upper)
    
    def process_record(self, record: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[AnomalyResult]]:
        """
        Process a single normalized record through Layer 2.
        
        Returns:
            (enriched_record, anomalies)
        """
        anomalies = []
        numeric_value = None
        
        # Try to extract numeric value
        if isinstance(record.get("value"), (int, float)):
            numeric_value = float(record["value"])
        
        entity_id = record.get("entity_id", "unknown")
        source = record.get("source", "unknown")
        
        # Check for anomalies
        if numeric_value is not None:
            # Z-score based outlier detection
            z_anomaly = self.z_detector.detect_outlier(entity_id, numeric_value)
            if z_anomaly.is_anomaly:
                anomalies.append(z_anomaly)
            
            # Trend change detection
            trend_anomaly = self.trend_detector.detect_trend_change(entity_id, numeric_value)
            if trend_anomaly.is_anomaly:
                anomalies.append(trend_anomaly)
            
            # Threshold detection (if source-specific threshold exists)
            metric_key = f"{source}_{entity_id}"
            threshold_anomaly = self.threshold_detector.detect_threshold_breach(metric_key, numeric_value)
            if threshold_anomaly.is_anomaly:
                anomalies.append(threshold_anomaly)
        
        # Enrich record with Layer 2 results
        enriched = record.copy()
        enriched["_layer2_results"] = {
            "anomaly_detected": len(anomalies) > 0,
            "anomaly_count": len(anomalies),
            "anomalies": [
                {
                    "type": a.anomaly_type,
                    "severity": a.severity,
                    "confidence": a.confidence,
                    "score": a.score,
                    "explanation": a.explanation
                }
                for a in anomalies
            ],
            "requires_llm": any(a.severity in ["high", "critical"] for a in anomalies)
        }
        
        return enriched, anomalies
    
    def process_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process batch of records through Layer 2.
        
        Returns:
            (enriched_records, summary)
        """
        import time
        start = time.time()
        
        enriched_records = []
        all_anomalies = []
        critical_count = 0
        high_count = 0
        
        for record in records:
            enriched, anomalies = self.process_record(record)
            enriched_records.append(enriched)
            all_anomalies.extend(anomalies)
            
            for anom in anomalies:
                if anom.severity == "critical":
                    critical_count += 1
                elif anom.severity == "high":
                    high_count += 1
        
        elapsed_ms = (time.time() - start) * 1000
        
        summary = {
            "total_records": len(records),
            "records_with_anomalies": len([r for r in enriched_records if r["_layer2_results"]["anomaly_detected"]]),
            "total_anomalies": len(all_anomalies),
            "critical_anomalies": critical_count,
            "high_anomalies": high_count,
            "processing_time_ms": elapsed_ms,
            "records_requiring_llm": len([r for r in enriched_records if r["_layer2_results"]["requires_llm"]])
        }
        
        return enriched_records, summary


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    layer2 = Layer2StatisticalProcessing()
    
    # Simulate stream of records
    test_records = [
        {
            "timestamp": datetime.now(),
            "source": "salesforce",
            "entity_id": "account_123",
            "value": 95000,
            "_ingested_at": datetime.now()
        },
        # Normal variations
        {
            "timestamp": datetime.now(),
            "source": "salesforce",
            "entity_id": "account_123",
            "value": 96000,
            "_ingested_at": datetime.now()
        },
        # Outlier - should be flagged
        {
            "timestamp": datetime.now(),
            "source": "salesforce",
            "entity_id": "account_123",
            "value": 50000,
            "_ingested_at": datetime.now()
        },
    ]
    
    enriched, summary = layer2.process_batch(test_records)
    print(f"\n=== Layer 2 Processing Summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nAnomaly Details:")
    for i, record in enumerate(enriched):
        if record["_layer2_results"]["anomaly_detected"]:
            print(f"Record {i}: {record['_layer2_results']}")
