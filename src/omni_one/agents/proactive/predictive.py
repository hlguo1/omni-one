import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from typing import Dict, Any, List
import numpy as np

class PredictiveAnalytics:
    def __init__(self):
        self.model = None
        self.label_encoders = {}
        self.features = ['email_sentiment', 'interaction_frequency', 'contract_value', 'days_since_last_contact']

    def train_model(self, historical_data: List[Dict[str, Any]]):
        """Train predictive model on historical client data."""
        if not historical_data:
            return

        df = pd.DataFrame(historical_data)

        # Encode categorical features
        for feature in ['industry', 'region']:
            if feature in df.columns:
                le = LabelEncoder()
                df[feature + '_encoded'] = le.fit_transform(df[feature].fillna('unknown'))
                self.label_encoders[feature] = le

        # Prepare features and target
        X = df[self.features + [f + '_encoded' for f in self.label_encoders.keys()]]
        y = df['churned']  # Target: whether client churned

        # Handle missing values
        X = X.fillna(0)

        # Split and train
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.model.fit(X_train, y_train)

        # Calculate accuracy
        accuracy = self.model.score(X_test, y_test)
        print(f"Model trained with accuracy: {accuracy:.2f}")

    def predict_churn_risk(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict churn risk for a client."""
        if not self.model:
            return {'risk': 'unknown', 'confidence': 0.0}

        # Prepare features
        features = []
        for feature in self.features:
            features.append(client_data.get(feature, 0))

        # Encode categorical
        for cat_feature in self.label_encoders.keys():
            encoded = self.label_encoders[cat_feature].transform([client_data.get(cat_feature, 'unknown')])[0]
            features.append(encoded)

        # Predict
        prediction = self.model.predict([features])[0]
        probability = self.model.predict_proba([features])[0]

        risk_level = 'high' if prediction == 1 else 'low'
        confidence = max(probability)

        return {
            'risk': risk_level,
            'confidence': confidence,
            'probability_churn': probability[1] if len(probability) > 1 else 0.0
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from the model."""
        if not self.model:
            return {}

        importance = self.model.feature_importances_
        return dict(zip(self.features + list(self.label_encoders.keys()), importance))