"""
Omni-One Enterprise AI Platform
A revolutionary enterprise proactive AI platform with multi-modal capabilities,
ethical AI governance, quantum-inspired optimization, and federated learning.
"""

__version__ = "1.0.0"
__author__ = "Omni-One Team"
__description__ = "Enterprise Proactive AI Platform"

from .server import app
from .core.model_router import ModelRouter
from .core.rag_engine import RAGEngine
from .core.cache import CacheManager
from .core.async_tasks import TaskManager

__all__ = [
    "app",
    "ModelRouter",
    "RAGEngine",
    "CacheManager",
    "TaskManager"
]