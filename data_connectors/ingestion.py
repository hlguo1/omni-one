from typing import Dict, Any, List
from datetime import datetime
from .base import BaseConnector
from .email import EmailConnector
from .slack import SlackConnector
from .salesforce import SalesforceConnector
from rag_engine import RAGEngine

class DataIngestionService:
    def __init__(self, rag_engine: RAGEngine):
        self.rag_engine = rag_engine
        self.connectors: Dict[str, BaseConnector] = {}

    def add_connector(self, name: str, connector_type: str, config: Dict[str, Any]):
        """Add a data connector."""
        if connector_type == 'email':
            connector = EmailConnector(config)
        elif connector_type == 'slack':
            connector = SlackConnector(config)
        elif connector_type == 'salesforce':
            connector = SalesforceConnector(config)
        else:
            raise ValueError(f"Unknown connector type: {connector_type}")

        self.connectors[name] = connector

    def sync_all(self):
        """Sync data from all connectors."""
        for name, connector in self.connectors.items():
            try:
                print(f"Syncing {name}...")
                data = connector.sync()
                if data:
                    self.rag_engine.add_documents(data)
                    print(f"Synced {len(data)} documents from {name}")
            except Exception as e:
                print(f"Failed to sync {name}: {e}")

    def sync_connector(self, name: str):
        """Sync a specific connector."""
        if name not in self.connectors:
            raise ValueError(f"Connector {name} not found")

        connector = self.connectors[name]
        data = connector.sync()
        if data:
            self.rag_engine.add_documents(data)
            return len(data)
        return 0

    def get_connector_status(self) -> Dict[str, Any]:
        """Get status of all connectors."""
        status = {}
        for name, connector in self.connectors.items():
            status[name] = {
                'type': type(connector).__name__,
                'last_sync': connector.last_sync.isoformat() if connector.last_sync else None
            }
        return status