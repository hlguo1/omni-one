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

    def sync(self) -> List[Dict[str, Any]]:
        """Full sync process: connect, fetch, transform."""
        if not self.connect():
            raise ConnectionError("Failed to connect to data source")

        data = self.fetch_data(self.last_sync)
        transformed = self.transform_data(data)
        self.last_sync = datetime.now()
        return transformed