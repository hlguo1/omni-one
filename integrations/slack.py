import requests
from typing import Dict, Any
from proactive_agents.engine import ProactiveEngine

class SlackIntegration:
    def __init__(self, token: str, proactive_engine: ProactiveEngine):
        self.token = token
        self.proactive_engine = proactive_engine
        self.base_url = 'https://slack.com/api'

    def send_notification(self, channel: str, message: str, client_name: str = None):
        """Send a notification to Slack."""
        payload = {
            "channel": channel,
            "text": message,
            "username": "Omni AI Assistant",
            "icon_emoji": ":robot_face:"
        }

        if client_name:
            # Add client context
            insights = self.proactive_engine.generate_proactive_insights(client_name)
            payload["blocks"] = self._create_insight_blocks(insights)

        response = requests.post(
            f'{self.base_url}/chat.postMessage',
            headers=self._headers(),
            json=payload
        )
        return response.json()

    def create_reminder(self, channel: str, client_name: str, reminder_text: str):
        """Create a reminder for sales team."""
        message = f"📅 *Reminder for {client_name}*\n{reminder_text}"
        return self.send_notification(channel, message, client_name)

    def alert_negative_sentiment(self, channel: str, client_name: str):
        """Send alert for negative client sentiment."""
        insights = self.proactive_engine.generate_proactive_insights(client_name)
        if insights['sentiment_analysis']['alert']:
            message = f"🚨 *Client Alert: {client_name}*\nDetected negative sentiment. Immediate attention required."
            return self.send_notification(channel, message, client_name)
        return None

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

    def _create_insight_blocks(self, insights: Dict[str, Any]) -> list:
        """Create Slack block kit for insights."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Client Insights: {insights['client']}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Sentiment:* {insights['sentiment_analysis']['sentiment']} ({insights['sentiment_analysis']['confidence']:.2f})\n*Risk:* {insights['risk_assessment']['risk_assessment']['risk']}"
                }
            }
        ]

        if insights['ai_suggestions']:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*AI Suggestions:*\n{insights['ai_suggestions'][:500]}..."
                }
            })

        return blocks