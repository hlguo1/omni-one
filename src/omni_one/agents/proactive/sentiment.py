from transformers import pipeline
from typing import Dict, Any

class SentimentAnalyzer:
    def __init__(self):
        # Load pre-trained sentiment analysis model
        self.analyzer = pipeline("sentiment-analysis",
                                model="cardiffnlp/twitter-roberta-base-sentiment-latest")

    def analyze(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        try:
            result = self.analyzer(text[:512])  # Limit input length
            sentiment = result[0]['label'].lower()
            confidence = result[0]['score']

            # Map to simple sentiment
            if sentiment == 'label_2':  # Positive
                sentiment = 'positive'
            elif sentiment == 'label_0':  # Negative
                sentiment = 'negative'
            else:  # Neutral
                sentiment = 'neutral'

            return {
                'sentiment': sentiment,
                'confidence': confidence,
                'raw_result': result[0]
            }
        except Exception as e:
            print(f"Sentiment analysis failed: {e}")
            return {'sentiment': 'neutral', 'confidence': 0.0, 'error': str(e)}

    def analyze_batch(self, texts: list) -> list:
        """Analyze sentiment for multiple texts."""
        return [self.analyze(text) for text in texts]