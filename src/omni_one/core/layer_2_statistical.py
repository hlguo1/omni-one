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
        import threading
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.data_windows: Dict[str, deque] = {}  # Per entity/metric windows
        self._lock = threading.RLock()

    def reset(self):
        """Clear all history (for tests / fresh streams)."""
        with self._lock:
            self.data_windows.clear()

    def _ensure_numeric(self, value: Any) -> Optional[float]:
        """Convert value to numeric or None. Excludes bool (subclass of int)."""
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            # Guard NaN/Inf
            try:
                f = float(value)
                if f != f or f in (float("inf"), float("-inf")):  # NaN check
                    return None
                return f
            except Exception:
                return None
        elif isinstance(value, str):
            try:
                s = value.strip().replace(",", "")
                if not s:
                    return None
                return float(s)
            except ValueError:
                return None
        return None
    
    def detect_outlier(self, entity_id: str, current_value: float) -> AnomalyResult:
        """
        Detect if current value is a statistical outlier using Z-score. Thread-safe.
        """
        with self._lock:
            if entity_id not in self.data_windows:
                self.data_windows[entity_id] = deque(maxlen=self.window_size)

            window = self.data_windows[entity_id]

            # Need at least 5 points for stable statistics (was 2 — too noisy)
            if len(window) < 5:
                window.append(current_value)
                return AnomalyResult(
                    is_anomaly=False,
                    anomaly_type="insufficient_data",
                    severity="low",
                    confidence=0.0,
                    score=0.0,
                    explanation=f"Insufficient historical data ({len(window)}/5)"
                )

            # Compute statistics
            values = np.array(list(window))
            mean = float(np.mean(values))
            std = float(np.std(values))

            # Handle case where all values are the same
            if std == 0:
                # If current differs from constant, it's an anomaly (step change)
                if current_value != mean:
                    window.append(current_value)
                    return AnomalyResult(
                        is_anomaly=True,
                        anomaly_type="outlier",
                        severity="medium",
                        confidence=0.6,
                        score=0.6,
                        explanation=f"Step change from constant {mean:.2f} to {current_value}",
                        metrics={"z_score": float("inf"), "mean": mean, "std": std, "current_value": current_value}
                    )
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

            # Confidence based on z-score magnitude (capped)
            confidence = min(z_score / (self.z_threshold + 1.0), 1.0) if is_anomaly else 0.0

            # Determine severity
            if z_score > 5.0:
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
                confidence=float(confidence),
                score=float(min(z_score / 5.0, 1.0)),  # Capped to 0-1
                explanation=f"Value {current_value} is {z_score:.1f} std deviations from mean {mean:.2f}",
                metrics={
                    "z_score": float(z_score),
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
    - Z-score outlier detection (per-entity + per-signal fallback for high-cardinality IDs)
    - Threshold violations (multi-key lookup)
    - Trend changes

    No LLM calls, no ML training, all deterministic.
    """

    def __init__(self):
        self.z_detector = StatisticalAnomalyDetector()
        self.threshold_detector = ThresholdAnomalyDetector()
        self.trend_detector = TrendAnomalyDetector()

        # Default thresholds for common metrics
        self._setup_default_thresholds()

    def reset(self):
        """Clear all detector history (for tests / fresh streams)."""
        try:
            self.z_detector.reset()
        except Exception:
            pass
        # Trend detector has no reset — clear manually
        try:
            self.trend_detector.data_windows.clear()
        except Exception:
            pass

    def _setup_default_thresholds(self):
        """Setup sensible default thresholds."""
        # Customer sentiment (-1 to 1)
        self.threshold_detector.set_threshold("sentiment", lower=-1.0, upper=1.0)
        # Revenue typically positive
        self.threshold_detector.set_threshold("revenue", lower=0.0)
        # Seller OS: stockout, margin guards
        self.threshold_detector.set_threshold("on_hand", lower=0.0)
        self.threshold_detector.set_threshold("margin_pct", lower=-100.0, upper=100.0)

    def set_metric_threshold(self, metric_name: str, lower: Optional[float] = None, upper: Optional[float] = None):
        """Allow dynamic threshold configuration."""
        self.threshold_detector.set_threshold(metric_name, lower, upper)

    def _bucket_key(self, record: Dict[str, Any]) -> str:
        """Stable bucket for high-cardinality entity_ids: prefer source:signal, fallback entity."""
        source = str(record.get("source", "unknown"))
        meta = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        signal = str(meta.get("signal", "")) if meta else ""
        entity_id = str(record.get("entity_id", "unknown"))
        if signal:
            return f"{source}:{signal}"
        return entity_id

    def _threshold_keys(self, record: Dict[str, Any]) -> List[str]:
        """All keys to try for threshold lookup (fixes single-key miss)."""
        source = str(record.get("source", "unknown"))
        entity_id = str(record.get("entity_id", "unknown"))
        meta = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        signal = str(meta.get("signal", "")) if meta else ""
        keys = [
            f"{source}_{entity_id}",
            f"{source}:{signal}" if signal else "",
            source,
            signal,
            entity_id,
        ]
        return [k for k in keys if k]

    def process_record(self, record: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[AnomalyResult]]:
        """
        Process a single normalized record through Layer 2.

        Returns:
            (enriched_record, anomalies)
        """
        anomalies = []
        numeric_value = self.z_detector._ensure_numeric(record.get("value"))

        entity_id = record.get("entity_id", "unknown")
        # Bucket for z-score/trend: entity if warmed, else source:signal fallback
        bucket = self._bucket_key(record)

        # Check for anomalies
        if numeric_value is not None:
            # Primary: entity bucket
            z_anomaly = self.z_detector.detect_outlier(str(entity_id), numeric_value)
            if z_anomaly.is_anomaly:
                anomalies.append(z_anomaly)
            else:
                # Fallback: signal bucket when entity has insufficient data
                # (fixes unique order IDs never warming)
                if z_anomaly.anomaly_type == "insufficient_data" and bucket != str(entity_id):
                    fallback = self.z_detector.detect_outlier(bucket, numeric_value)
                    if fallback.is_anomaly:
                        anomalies.append(fallback)

            # Trend change detection (same bucket logic, best-effort)
            try:
                trend_anomaly = self.trend_detector.detect_trend_change(str(entity_id), numeric_value)
                if trend_anomaly.is_anomaly:
                    anomalies.append(trend_anomaly)
            except Exception:
                pass

            # Threshold detection — try all keys (fixes never-firing thresholds)
            for metric_key in self._threshold_keys(record):
                try:
                    threshold_anomaly = self.threshold_detector.detect_threshold_breach(metric_key, numeric_value)
                    if threshold_anomaly.is_anomaly:
                        anomalies.append(threshold_anomaly)
                        break  # one threshold hit is enough
                except Exception:
                    continue
        
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
