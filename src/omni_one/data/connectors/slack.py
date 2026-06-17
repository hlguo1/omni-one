import requests
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseConnector

class SlackConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.token = config['token']
        self.channels = config.get('channels', [])
        self.base_url = 'https://slack.com/api'

    def connect(self) -> bool:
        # Test connection
        response = requests.get(f'{self.base_url}/auth.test', headers=self._headers())
        return response.json().get('ok', False)

    def fetch_data(self, since: datetime = None) -> List[Dict[str, Any]]:
        messages = []
        oldest = since.timestamp() if since else 0

        for channel in self.channels:
            # Get channel history
            params = {
                'channel': channel,
                'oldest': oldest,
                'limit': 100
            }
            response = requests.get(
                f'{self.base_url}/conversations.history',
                headers=self._headers(),
                params=params
            )

            if response.json().get('ok'):
                for msg in response.json()['messages']:
                    messages.append({
                        'id': msg['ts'],
                        'text': msg['text'],
                        'user': msg.get('user', ''),
                        'channel': channel,
                        'timestamp': msg['ts'],
                        'type': 'slack_message'
                    })

        return messages

    def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transformed = []
        for item in raw_data:
            transformed.append({
                'content': item['text'],
                'source': 'slack',
                'type': 'chat',
                'metadata': {
                    'channel': item['channel'],
                    'user': item['user'],
                    'timestamp': item['timestamp']
                },
                'timestamp': datetime.fromtimestamp(float(item['timestamp'])).isoformat()
            })
        return transformed

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }