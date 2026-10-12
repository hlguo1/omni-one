"""
Data connectors for various data sources.

Heavy/optional connectors (salesforce, slack) require `requests`.
They are imported lazily so unit tests and minimal installs can still
use BaseConnector / EmailConnector / DataIngestionService without
the optional HTTP dependency.
"""

from .base import BaseConnector
from .email import EmailConnector

try:
    from .salesforce import SalesforceConnector
except Exception:  # pragma: no cover - optional dep (requests) missing
    SalesforceConnector = None  # type: ignore

try:
    from .slack import SlackConnector
except Exception:  # pragma: no cover - optional dep (requests) missing
    SlackConnector = None  # type: ignore

from .ingestion import DataIngestionService

__all__ = [
    "BaseConnector",
    "EmailConnector",
    "SalesforceConnector",
    "SlackConnector",
    "DataIngestionService"
]
