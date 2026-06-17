from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class BaseConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.last_sync = None

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def fetch_data(self, since: datetime = None) -> List[Dict[str, Any]]:
        """Fetch data from the source since the given timestamp."""
        pass

    @abstractmethod
    def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform raw data into standardized format."""
        pass

    def sync(self, commit: bool = True, sync_time: datetime = None) -> List[Dict[str, Any]]:
        """Full sync process: connect, fetch, transform."""
        if not self.connect():
            raise ConnectionError("Failed to connect to data source")

        data = self.fetch_data(self.last_sync)
        transformed = self.transform_data(data)
        if commit:
            self.mark_synced(sync_time)
        return transformed

    def mark_synced(self, sync_time: datetime = None):
        """Advance the connector checkpoint after downstream persistence succeeds."""
        self.last_sync = sync_time or datetime.now()
