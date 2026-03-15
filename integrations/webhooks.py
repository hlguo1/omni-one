from flask import Blueprint, request, jsonify
from typing import Dict, Any
from integrations.slack import SlackIntegration
from integrations.outlook import OutlookIntegration
from proactive_agents.engine import ProactiveEngine

class IntegrationManager:
    def __init__(self, proactive_engine: ProactiveEngine):
        self.proactive_engine = proactive_engine
        self.integrations: Dict[str, Any] = {}

    def add_slack_integration(self, token: str, default_channel: str):
        """Add Slack integration."""
        self.integrations['slack'] = SlackIntegration(token, self.proactive_engine)
        self.slack_channel = default_channel

    def add_outlook_integration(self, client_id: str, client_secret: str, tenant_id: str, user_email: str):
        """Add Outlook integration."""
        self.integrations['outlook'] = OutlookIntegration(client_id, client_secret, tenant_id, self.proactive_engine)
        self.outlook_user = user_email

    def handle_webhook(self, integration_type: str, data: Dict[str, Any]):
        """Handle incoming webhooks from integrations."""
        if integration_type == 'slack':
            return self._handle_slack_webhook(data)
        elif integration_type == 'outlook':
            return self._handle_outlook_webhook(data)
        return {'status': 'unknown_integration'}

    def _handle_slack_webhook(self, data: Dict[str, Any]):
        """Handle Slack webhook events."""
        event = data.get('event', {})
        if event.get('type') == 'message' and 'bot_id' not in event:
            # Process message for client mentions
            text = event.get('text', '')
            if 'client' in text.lower():
                # Extract client name (simple extraction)
                client_name = self._extract_client_name(text)
                if client_name:
                    # Send proactive insights
                    slack = self.integrations.get('slack')
                    if slack:
                        slack.send_notification(self.slack_channel, f"Client mentioned: {client_name}", client_name)
        return {'status': 'processed'}

    def _handle_outlook_webhook(self, data: Dict[str, Any]):
        """Handle Outlook webhook events."""
        # Process new emails
        outlook = self.integrations.get('outlook')
        if outlook:
            alerts = outlook.scan_emails_for_sentiment(self.outlook_user)
            for alert in alerts:
                # Send alert to Slack
                slack = self.integrations.get('slack')
                if slack:
                    slack.alert_negative_sentiment(self.slack_channel, alert['client'])
        return {'status': 'processed'}

    def _extract_client_name(self, text: str) -> str:
        """Simple client name extraction from text."""
        # This would be more sophisticated in production
        words = text.split()
        for word in words:
            if word.istitle() and len(word) > 3:  # Likely a name
                return word
        return None

# Flask blueprint for integrations
integration_bp = Blueprint('integrations', __name__)
integration_manager = None

def init_integration_blueprint(proactive_engine: ProactiveEngine):
    global integration_manager
    integration_manager = IntegrationManager(proactive_engine)
    return integration_bp

@integration_bp.route('/slack/webhook', methods=['POST'])
def slack_webhook():
    """Slack webhook endpoint."""
    data = request.json
    if integration_manager:
        result = integration_manager.handle_webhook('slack', data)
        return jsonify(result)
    return jsonify({'error': 'Integration manager not initialized'}), 500

@integration_bp.route('/outlook/webhook', methods=['POST'])
def outlook_webhook():
    """Outlook webhook endpoint."""
    data = request.json
    if integration_manager:
        result = integration_manager.handle_webhook('outlook', data)
        return jsonify(result)
    return jsonify({'error': 'Integration manager not initialized'}), 500