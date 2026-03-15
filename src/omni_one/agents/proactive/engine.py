from .sentiment import SentimentAnalyzer
from .predictive import PredictiveAnalytics
from .anomaly import AnomalyDetector
from typing import Dict, Any, List
from rag_engine import RAGEngine
from model_router import ModelRouter

class ProactiveEngine:
    def __init__(self, rag_engine: RAGEngine, model_router: ModelRouter):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.predictive_analytics = PredictiveAnalytics()
        self.anomaly_detector = AnomalyDetector()
        self.rag_engine = rag_engine
        self.model_router = model_router

    def analyze_client_sentiment(self, client_name: str) -> Dict[str, Any]:
        """Analyze sentiment from all client communications."""
        # Search for client-related documents
        query = f"communications with {client_name}"
        docs = self.rag_engine.retrieve(query, k=20)

        if not docs:
            return {'sentiment': 'neutral', 'confidence': 0.0, 'message': 'No data found'}

        # Extract text from documents
        texts = [doc.page_content for doc in docs]
        combined_text = ' '.join(texts)

        # Analyze sentiment
        sentiment_result = self.sentiment_analyzer.analyze(combined_text)

        return {
            'client': client_name,
            'sentiment': sentiment_result['sentiment'],
            'confidence': sentiment_result['confidence'],
            'documents_analyzed': len(docs),
            'alert': sentiment_result['sentiment'] == 'negative'
        }

    def predict_client_risk(self, client_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predict churn risk and provide recommendations."""
        risk_assessment = self.predictive_analytics.predict_churn_risk(client_data)

        recommendations = []
        if risk_assessment['risk'] == 'high':
            recommendations.extend([
                "Schedule immediate follow-up call",
                "Review recent interactions for issues",
                "Prepare retention strategy"
            ])
        elif risk_assessment['risk'] == 'medium':
            recommendations.extend([
                "Monitor closely over next month",
                "Send satisfaction survey"
            ])

        return {
            'client': client_data.get('name', 'Unknown'),
            'risk_assessment': risk_assessment,
            'recommendations': recommendations
        }

    def detect_anomalies(self, recent_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect anomalous patterns in recent data."""
        anomalies = self.anomaly_detector.detect_anomalies(recent_data)

        alerts = []
        for anomaly in anomalies:
            if anomaly['severity'] == 'high':
                alerts.append({
                    'type': 'high_priority',
                    'message': f"Anomalous activity detected: {anomaly['data']}",
                    'severity': anomaly['severity'],
                    'score': anomaly['anomaly_score']
                })

        return alerts

    def generate_proactive_insights(self, client_name: str) -> Dict[str, Any]:
        """Generate comprehensive proactive insights for a client."""
        sentiment = self.analyze_client_sentiment(client_name)

        # Mock client data for prediction (in real implementation, fetch from CRM)
        client_data = {
            'name': client_name,
            'email_sentiment': 1 if sentiment['sentiment'] == 'positive' else -1,
            'interaction_frequency': 5,  # Mock
            'contract_value': 100000,   # Mock
            'days_since_last_contact': 7,  # Mock
            'industry': 'technology',   # Mock
            'region': 'us'             # Mock
        }

        risk = self.predict_client_risk(client_data)

        # Generate AI-powered suggestions
        context = f"Client {client_name} sentiment: {sentiment['sentiment']}. Risk: {risk['risk_assessment']['risk']}."
        prompt = f"Based on this context, provide 3 specific, actionable suggestions for improving client relationship: {context}"

        ai_suggestions = self.model_router.generate(prompt)

        return {
            'client': client_name,
            'sentiment_analysis': sentiment,
            'risk_assessment': risk,
            'ai_suggestions': ai_suggestions,
            'timestamp': '2024-01-01T00:00:00Z'  # Current timestamp
        }