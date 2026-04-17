from .sentiment import SentimentAnalyzer
from .predictive import PredictiveAnalytics
from .anomaly import AnomalyDetector
from typing import Dict, Any, List, Optional, Tuple
from rag_engine import RAGEngine
from model_router import ModelRouter
import logging

# Import new multi-layer pipeline
try:
    from core.data_processing_pipeline import MultiLayerDataPipeline, ProcessingResult
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False
    ProcessingResult = None

logger = logging.getLogger(__name__)


class ProactiveEngine:
    """
    Proactive Intelligence Engine with Multi-Layered Data Processing
    
    Now integrates 4-layer pipeline to handle high-velocity data efficiently:
    1. Fast Ingestion & Validation (<1ms)
    2. Statistical Anomaly Detection (<10ms)
    3. ML Feature Engineering (<100ms)
    4. LLM Synthesis (only if needed, with intelligent gating)
    
    This dramatically reduces LLM calls while maintaining intelligence quality.
    """
    
    def __init__(self, rag_engine: RAGEngine, model_router: ModelRouter):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.predictive_analytics = PredictiveAnalytics()
        self.anomaly_detector = AnomalyDetector()
        self.rag_engine = rag_engine
        self.model_router = model_router
        
        # Initialize multi-layer pipeline if available
        self.pipeline = None
        self.use_pipeline = PIPELINE_AVAILABLE
        
        if self.use_pipeline:
            try:
                self.pipeline = MultiLayerDataPipeline(
                    model_router=model_router,
                    cache=None  # Cache can be initialized separately
                )
                logger.info("Multi-layer data processing pipeline initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize pipeline: {e}. Falling back to legacy mode.")
                self.use_pipeline = False

    # ========== LEGACY METHODS (Backward Compatible) ==========
    
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
    
    # ========== MULTI-LAYER PIPELINE METHODS (NEW) ==========
    
    def process_data_stream(self, records: List[Dict[str, Any]], 
                           use_pipeline: bool = True) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process a stream of records using the multi-layer pipeline.
        
        This is the recommended way to handle high-velocity data!
        
        Args:
            records: List of data records to process
            use_pipeline: If True, use multi-layer pipeline; if False, use legacy method
        
        Returns:
            (processed_records, metrics_summary)
        
        Example:
            >>> records = [
            ...     {"timestamp": "2024-01-01T10:00:00", "source": "salesforce", 
            ...      "entity_id": "acct_123", "value": 95000},
            ...     {"timestamp": "2024-01-01T10:00:01", "source": "salesforce",
            ...      "entity_id": "acct_123", "value": 45000}  # Outlier
            ... ]
            >>> processed, metrics = engine.process_data_stream(records)
            >>> print(f"LLM bypass rate: {metrics['llm_bypass_rate']}")
            LLM bypass rate: 50.0%
        """
        if not use_pipeline or not self.pipeline:
            logger.warning("Pipeline not available, using legacy processing")
            return self._process_legacy_batch(records)
        
        results, pipeline_metrics = self.pipeline.process_batch(records)
        
        # Extract insights and format output
        processed = []
        for result in results:
            processed.append({
                'record_id': result.record_id,
                'original': result.original_record,
                'processing_stage': result.processing_stage.value,
                'llm_bypassed': result.llm_bypassed,
                'priority': result.layer3_result.get('predictions', {}).get('priority', {}).get('value') if result.layer3_result else 'unknown',
                'anomalies': result.layer2_result.get('anomalies', []) if result.layer2_result else [],
                'insights': result.layer4_llm_response if result.layer4_llm_response else 'Processed without LLM',
                'timing_ms': {
                    'layer1': result.layer1_time_ms,
                    'layer2': result.layer2_time_ms,
                    'layer3': result.layer3_time_ms,
                    'layer4': result.layer4_time_ms,
                    'total': result.total_time_ms
                }
            })
        
        return processed, self.pipeline.get_metrics_summary()
    
    def process_real_time_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single real-time event through the pipeline.
        
        Fast path for individual record processing with full transparency.
        """
        if not self.pipeline:
            logger.warning("Pipeline not available")
            return {}
        
        result = self.pipeline.process_record(event)
        
        return {
            'record_id': result.record_id,
            'processing_stage': result.processing_stage.value,
            'confidence': result.confidence_score,
            'llm_bypassed': result.llm_bypassed,
            'layer2_anomalies': result.layer2_result.get('anomalies', []) if result.layer2_result else [],
            'layer3_predictions': result.layer3_result.get('predictions', {}) if result.layer3_result else {},
            'llm_insight': result.layer4_llm_response,
            'timing_ms': result.total_time_ms
        }
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get detailed pipeline performance metrics."""
        if not self.pipeline:
            return {"status": "pipeline_not_available"}
        
        return self.pipeline.get_metrics_summary()
    
    def set_metric_threshold(self, metric_name: str, lower: Optional[float] = None, 
                            upper: Optional[float] = None) -> None:
        """
        Configure threshold-based anomaly detection for specific metrics.
        
        Example:
            >>> engine.set_metric_threshold("revenue", lower=10000, upper=200000)
            >>> engine.set_metric_threshold("sentiment", lower=-1.0, upper=1.0)
        """
        if self.pipeline:
            self.pipeline.layer2.set_metric_threshold(metric_name, lower, upper)
    
    def _process_legacy_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Legacy batch processing for backward compatibility."""
        processed = []
        for record in records:
            processed.append({
                'record_id': record.get('entity_id', 'unknown'),
                'original': record,
                'processing_stage': 'legacy',
                'llm_bypassed': False
            })
        
        return processed, {
            'processing_method': 'legacy',
            'total_records': len(records),
            'note': 'Multi-layer pipeline not available'
        }