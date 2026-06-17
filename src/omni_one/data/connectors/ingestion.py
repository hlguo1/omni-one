from typing import Dict, Any, List, TYPE_CHECKING
from datetime import datetime
from .base import BaseConnector
from .email import EmailConnector
from .slack import SlackConnector
from .salesforce import SalesforceConnector

if TYPE_CHECKING:
    from omni_one.core.rag_engine import RAGEngine

class DataIngestionService:
    def __init__(self, rag_engine: "RAGEngine"):
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
        """Sync data from all connectors and return a structured report."""
        connector_reports = {}
        for name, connector in self.connectors.items():
            connector_reports[name] = self._sync_connector_report(name, connector)

        successful = sum(1 for report in connector_reports.values() if report["status"] == "success")
        failed = sum(1 for report in connector_reports.values() if report["status"] == "failed")
        documents_added = sum(report["documents_added"] for report in connector_reports.values())

        return {
            "total_connectors": len(connector_reports),
            "successful_connectors": successful,
            "failed_connectors": failed,
            "documents_added": documents_added,
            "connectors": connector_reports
        }

    def sync_connector(self, name: str):
        """Sync a specific connector and return a structured report."""
        if name not in self.connectors:
            raise ValueError(f"Connector {name} not found")

        connector = self.connectors[name]
        return self._sync_connector_report(name, connector)

    def _sync_connector_report(self, name: str, connector: BaseConnector) -> Dict[str, Any]:
        """Run one connector sync without advancing checkpoints until persistence succeeds."""
        previous_last_sync = connector.last_sync
        completed_at = datetime.now()

        try:
            data = self._fetch_without_commit(connector, completed_at)
            documents_added = len(data)

            if data:
                self.rag_engine.add_documents(data)

            self._commit_connector_sync(connector, completed_at)

            return {
                "connector": name,
                "status": "success",
                "documents_added": documents_added,
                "error": None,
                "previous_last_sync": previous_last_sync.isoformat() if previous_last_sync else None,
                "last_sync": connector.last_sync.isoformat() if connector.last_sync else None
            }
        except Exception as e:
            connector.last_sync = previous_last_sync
            return {
                "connector": name,
                "status": "failed",
                "documents_added": 0,
                "error": str(e),
                "previous_last_sync": previous_last_sync.isoformat() if previous_last_sync else None,
                "last_sync": previous_last_sync.isoformat() if previous_last_sync else None
            }

    def _fetch_without_commit(self, connector: BaseConnector, sync_time: datetime) -> List[Dict[str, Any]]:
        """Fetch transformed records while preserving the connector checkpoint."""
        previous_last_sync = connector.last_sync
        try:
            return connector.sync(commit=False, sync_time=sync_time)
        except TypeError:
            data = connector.sync()
            connector.last_sync = previous_last_sync
            return data

    def _commit_connector_sync(self, connector: BaseConnector, sync_time: datetime):
        if hasattr(connector, "mark_synced"):
            connector.mark_synced(sync_time)
        else:
            connector.last_sync = sync_time

    def get_connector_status(self) -> Dict[str, Any]:
        """Get status of all connectors."""
        status = {}
        for name, connector in self.connectors.items():
            status[name] = {
                'type': type(connector).__name__,
                'last_sync': connector.last_sync.isoformat() if connector.last_sync else None
            }
        return status
