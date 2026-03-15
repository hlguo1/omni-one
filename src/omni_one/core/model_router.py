import os
import litellm
from typing import Dict, Any

class ModelRouter:
    def __init__(self):
        # Configure API keys
        litellm.api_key = os.getenv('GOOGLE_API_KEY')
        # Add other keys as needed
        # litellm.openai_key = os.getenv('OPENAI_API_KEY')
        # etc.

        # Model configurations with cost/quality tradeoffs
        self.models = {
            'fast': {
                'model': 'gemini/gemini-1.5-flash',
                'cost_per_token': 0.000001,  # approx
                'quality_score': 7
            },
            'balanced': {
                'model': 'gemini/gemini-2.5-flash',
                'cost_per_token': 0.00001,
                'quality_score': 9
            },
            'premium': {
                'model': 'openai/gpt-4o',
                'cost_per_token': 0.00003,
                'quality_score': 10
            }
        }

    def select_model(self, query_complexity: str = 'medium', budget: float = None) -> str:
        """Select appropriate model based on complexity and budget."""
        if query_complexity == 'low':
            return self.models['fast']['model']
        elif query_complexity == 'high' or budget and budget > 0.01:
            return self.models['premium']['model']
        else:
            return self.models['balanced']['model']

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        """Unified generation across models."""
        if not model:
            model = self.select_model()

        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content

    def estimate_cost(self, prompt: str, model: str) -> float:
        """Estimate cost for a request."""
        tokens = len(prompt.split()) * 1.3  # rough estimate
        cost_per_token = self.models.get(model.split('/')[-1], {}).get('cost_per_token', 0.00001)
        return tokens * cost_per_token