from typing import Dict, Any, List
from model_router import ModelRouter
from proactive_agents.sentiment import SentimentAnalyzer
from proactive_agents.predictive import PredictiveAnalytics

class AgentOrchestrator:
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        self.agents = {
            'sentiment_agent': SentimentAnalyzer(),
            'predictive_agent': PredictiveAnalytics(),
            'reasoning_agent': ReasoningAgent(model_router),
            'synthesis_agent': SynthesisAgent(model_router)
        }

    def process_client_query(self, client_name: str, query: str) -> Dict[str, Any]:
        """Process a complex client query using multiple agents."""
        # Step 1: Sentiment analysis
        sentiment_result = self.agents['sentiment_agent'].analyze(f"Query: {query}")

        # Step 2: Predictive analysis (if applicable)
        predictive_result = None
        if 'risk' in query.lower() or 'churn' in query.lower():
            predictive_result = self.agents['predictive_agent'].predict_churn_risk({
                'name': client_name,
                'email_sentiment': 1 if sentiment_result['sentiment'] == 'positive' else -1
            })

        # Step 3: Reasoning chain
        reasoning_result = self.agents['reasoning_agent'].reason_about_client(client_name, query, sentiment_result)

        # Step 4: Synthesis
        final_result = self.agents['synthesis_agent'].synthesize_insights(
            client_name, query, sentiment_result, predictive_result, reasoning_result
        )

        return {
            'client': client_name,
            'query': query,
            'sentiment_analysis': sentiment_result,
            'predictive_analysis': predictive_result,
            'reasoning': reasoning_result,
            'final_insights': final_result,
            'agent_chain': ['sentiment', 'predictive', 'reasoning', 'synthesis']
        }

class ReasoningAgent:
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router

    def reason_about_client(self, client_name: str, query: str, sentiment: Dict[str, Any]) -> str:
        """Perform chain-of-thought reasoning about client situation."""
        prompt = f"""
Client: {client_name}
Query: {query}
Current Sentiment: {sentiment['sentiment']} (confidence: {sentiment['confidence']:.2f})

Perform step-by-step reasoning:
1. What is the core issue or opportunity?
2. What data do we need to address this?
3. What are the potential outcomes?
4. What immediate actions should be taken?
5. What are the long-term implications?

Provide a structured reasoning chain.
"""
        return self.model_router.generate(prompt)

class SynthesisAgent:
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router

    def synthesize_insights(self, client_name: str, query: str, sentiment: Dict[str, Any],
                          predictive: Dict[str, Any] = None, reasoning: str = None) -> str:
        """Synthesize all insights into actionable recommendations."""
        context = f"""
Client: {client_name}
Query: {query}
Sentiment: {sentiment['sentiment']}
"""
        if predictive:
            context += f"Risk Assessment: {predictive['risk']} (confidence: {predictive['confidence']:.2f})\n"
        if reasoning:
            context += f"Reasoning: {reasoning[:500]}...\n"

        prompt = f"""
Based on the following context, provide comprehensive, actionable insights and recommendations:

{context}

Structure your response with:
- Executive Summary
- Key Findings
- Recommended Actions (prioritized)
- Risk Mitigation Strategies
- Success Metrics
"""
        return self.model_router.generate(prompt)