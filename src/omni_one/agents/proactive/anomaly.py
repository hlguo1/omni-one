from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pandas as pd
from typing import Dict, Any, List
import numpy as np

class AnomalyDetector:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.features = ['email_volume', 'response_time', 'interaction_score']

    def train_model(self, historical_data: List[Dict[str, Any]]):
        """Train anomaly detection model."""
        if not historical_data:
            return

        df = pd.DataFrame(historical_data)
        X = df[self.features].fillna(0)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train isolation forest
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.model.fit(X_scaled)

    def detect_anomalies(self, current_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalies in current data."""
        if not self.model or not current_data:
            return []

        df = pd.DataFrame(current_data)
        X = df[self.features].fillna(0)
        X_scaled = self.scaler.transform(X)

        # Predict anomalies (-1 for anomaly, 1 for normal)
        predictions = self.model.predict(X_scaled)
        scores = self.model.decision_function(X_scaled)

        anomalies = []
        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:  # Anomaly
                anomalies.append({
                    'index': i,
                    'data': current_data[i],
                    'anomaly_score': score,
                    'severity': 'high' if score < -0.5 else 'medium'
                })

        return anomalies

    def get_normal_ranges(self) -> Dict[str, Dict[str, float]]:
        """Get normal ranges for features."""
        # This would be calculated from training data
        return {
            'email_volume': {'min': 0, 'max': 100, 'mean': 20},
            'response_time': {'min': 0, 'max': 48, 'mean': 12},  # hours
            'interaction_score': {'min': 0, 'max': 10, 'mean': 5}
        }