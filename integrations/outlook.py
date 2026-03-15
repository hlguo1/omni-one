import requests
from typing import Dict, Any, List
from proactive_agents.engine import ProactiveEngine

class OutlookIntegration:
    def __init__(self, client_id: str, client_secret: str, tenant_id: str, proactive_engine: ProactiveEngine):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.proactive_engine = proactive_engine
        self.access_token = None
        self.base_url = 'https://graph.microsoft.com/v1.0'

    def authenticate(self):
        """Get access token for Microsoft Graph API."""
        token_url = f'https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        self.access_token = response.json()['access_token']

    def scan_emails_for_sentiment(self, user_email: str) -> List[Dict[str, Any]]:
        """Scan recent emails for sentiment analysis."""
        if not self.access_token:
            self.authenticate()

        # Get recent emails
        endpoint = f'{self.base_url}/users/{user_email}/messages'
        params = {
            '$top': 50,
            '$orderby': 'receivedDateTime desc',
            '$select': 'subject,body,receivedDateTime,from'
        }
        headers = {'Authorization': f'Bearer {self.access_token}'}

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()

        emails = response.json()['value']
        alerts = []

        for email in emails:
            # Analyze sentiment of email body
            body_text = self._extract_text_from_html(email['body']['content'])
            if len(body_text) > 50:  # Only analyze substantial emails
                sentiment = self.proactive_engine.sentiment_analyzer.analyze(body_text)
                if sentiment['sentiment'] == 'negative' and sentiment['confidence'] > 0.7:
                    alerts.append({
                        'type': 'negative_email',
                        'client': email['from']['emailAddress']['name'],
                        'subject': email['subject'],
                        'sentiment': sentiment,
                        'email_id': email['id']
                    })

        return alerts

    def send_proactive_email(self, to_email: str, client_name: str, subject: str, body: str):
        """Send a proactive email with insights."""
        if not self.access_token:
            self.authenticate()

        insights = self.proactive_engine.generate_proactive_insights(client_name)

        # Enhance email with insights
        enhanced_body = f"{body}\n\n---\n*AI Insights for {client_name}:*\n"
        enhanced_body += f"Sentiment: {insights['sentiment_analysis']['sentiment']}\n"
        enhanced_body += f"Risk Level: {insights['risk_assessment']['risk_assessment']['risk']}\n"
        enhanced_body += f"Suggestions: {insights['ai_suggestions'][:200]}..."

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": enhanced_body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            }
        }

        endpoint = f'{self.base_url}/users/{to_email}/sendMail'
        headers = {'Authorization': f'Bearer {self.access_token}'}

        response = requests.post(endpoint, headers=headers, json=payload)
        return response.status_code == 202  # Accepted

    def _extract_text_from_html(self, html_content: str) -> str:
        """Simple HTML to text conversion."""
        # Basic HTML stripping (in production, use beautifulsoup)
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        return text.strip()