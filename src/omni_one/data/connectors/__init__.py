"""
Data connectors for various data sources
"""

from .base import BaseConnector
from .email import EmailConnector
from .salesforce import SalesforceConnector
from .slack import SlackConnector
from .ingestion import DataIngestionService

__all__ = [
    "BaseConnector",
    "EmailConnector",
    "SalesforceConnector",
    "SlackConnector",
    "DataIngestionService"
]
