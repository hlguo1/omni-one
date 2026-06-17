import sys
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "src" / "omni_one" / "data"
sys.path.insert(0, str(DATA_DIR))

from connectors.base import BaseConnector
from connectors.ingestion import DataIngestionService


class FakeConnector(BaseConnector):
    def __init__(self, raw_records, connected=True):
        super().__init__({})
        self.raw_records = raw_records
        self.connected = connected
        self.fetch_since_values = []

    def connect(self):
        return self.connected

    def fetch_data(self, since=None):
        self.fetch_since_values.append(since)
        return self.raw_records

    def transform_data(self, raw_data):
        return [
            {
                "content": item["content"],
                "source": "fake",
                "type": "record",
                "timestamp": "2026-01-01T00:00:00",
            }
            for item in raw_data
        ]


class FakeRAGEngine:
    def __init__(self, fail=False):
        self.fail = fail
        self.documents = []
        self.calls = 0

    def add_documents(self, documents):
        self.calls += 1
        if self.fail:
            raise RuntimeError("vector store unavailable")
        self.documents.extend(documents)


def test_sync_connector_preserves_checkpoint_when_rag_persistence_fails():
    previous_sync = datetime(2026, 1, 1, 12, 0, 0)
    connector = FakeConnector([{"content": "important account update"}])
    connector.last_sync = previous_sync
    service = DataIngestionService(FakeRAGEngine(fail=True))
    service.connectors["crm"] = connector

    report = service.sync_connector("crm")

    assert report["status"] == "failed"
    assert report["documents_added"] == 0
    assert report["error"] == "vector store unavailable"
    assert report["previous_last_sync"] == previous_sync.isoformat()
    assert report["last_sync"] == previous_sync.isoformat()
    assert connector.last_sync == previous_sync
    assert connector.fetch_since_values == [previous_sync]


def test_empty_sync_is_successful_and_advances_checkpoint_without_rag_write():
    previous_sync = datetime(2026, 1, 1, 12, 0, 0)
    connector = FakeConnector([])
    connector.last_sync = previous_sync
    rag_engine = FakeRAGEngine()
    service = DataIngestionService(rag_engine)
    service.connectors["empty"] = connector

    report = service.sync_connector("empty")

    assert report["status"] == "success"
    assert report["documents_added"] == 0
    assert report["error"] is None
    assert report["previous_last_sync"] == previous_sync.isoformat()
    assert connector.last_sync > previous_sync
    assert report["last_sync"] == connector.last_sync.isoformat()
    assert rag_engine.calls == 0


def test_sync_all_reports_partial_failures_without_blocking_other_connectors():
    successful = FakeConnector([{"content": "persist me"}])
    failing = FakeConnector([{"content": "do not checkpoint me"}])
    previous_failure_sync = datetime(2026, 1, 1, 9, 30, 0)
    failing.last_sync = previous_failure_sync

    class SelectiveRAGEngine(FakeRAGEngine):
        def add_documents(self, documents):
            super().add_documents(documents)
            if documents[0]["content"] == "do not checkpoint me":
                raise RuntimeError("write rejected")

    service = DataIngestionService(SelectiveRAGEngine())
    service.connectors["successful"] = successful
    service.connectors["failing"] = failing

    report = service.sync_all()

    assert report["total_connectors"] == 2
    assert report["successful_connectors"] == 1
    assert report["failed_connectors"] == 1
    assert report["documents_added"] == 1
    assert report["connectors"]["successful"]["status"] == "success"
    assert report["connectors"]["successful"]["documents_added"] == 1
    assert successful.last_sync is not None
    assert report["connectors"]["failing"]["status"] == "failed"
    assert report["connectors"]["failing"]["error"] == "write rejected"
    assert failing.last_sync == previous_failure_sync
