import requests
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseConnector

class SalesforceConnector(BaseConnector):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.username = config['username']
        self.password = config['password']
        self.instance_url = None
        self.access_token = None

    def connect(self) -> bool:
        try:
            # OAuth login
            login_url = 'https://login.salesforce.com/services/oauth2/token'
            data = {
                'grant_type': 'password',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'username': self.username,
                'password': self.password
            }
            response = requests.post(login_url, data=data)
            response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data['access_token']
            self.instance_url = token_data['instance_url']
            return True
        except Exception as e:
            print(f"Salesforce connection failed: {e}")
            return False

    def fetch_data(self, since: datetime = None) -> List[Dict[str, Any]]:
        if not self.access_token:
            return []

        try:
            # Fetch accounts and opportunities
            accounts = self._query("SELECT Id, Name, Type, Industry, AnnualRevenue, LastModifiedDate FROM Account")
            opportunities = self._query("SELECT Id, Name, AccountId, StageName, Amount, CloseDate, LastModifiedDate FROM Opportunity")

            data = []
            data.extend([{'type': 'account', **acc} for acc in accounts])
            data.extend([{'type': 'opportunity', **opp} for opp in opportunities])

            return data
        except Exception as e:
            print(f"Salesforce fetch failed: {e}")
            return []

    def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        transformed = []
        for item in raw_data:
            if item['type'] == 'account':
                content = f"Account: {item['Name']}\nType: {item.get('Type', 'N/A')}\nIndustry: {item.get('Industry', 'N/A')}\nRevenue: {item.get('AnnualRevenue', 'N/A')}"
            elif item['type'] == 'opportunity':
                content = f"Opportunity: {item['Name']}\nStage: {item['StageName']}\nAmount: {item.get('Amount', 'N/A')}\nClose Date: {item.get('CloseDate', 'N/A')}"

            transformed.append({
                'content': content,
                'source': 'salesforce',
                'type': item['type'],
                'metadata': item,
                'timestamp': datetime.now().isoformat()
            })
        return transformed

    def _query(self, soql: str) -> List[Dict]:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f'{self.instance_url}/services/data/v58.0/query',
            headers=headers,
            params={'q': soql}
        )
        response.raise_for_status()
        return response.json()['records']