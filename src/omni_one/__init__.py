"""
Omni-One Enterprise AI Platform
A revolutionary enterprise proactive AI platform with multi-modal capabilities,
ethical AI governance, quantum-inspired optimization, and federated learning.
"""

__version__ = "1.0.0"
__author__ = "Omni-One Team"
__description__ = "Enterprise Proactive AI Platform"

try:
    from .server import app  # type: ignore
except Exception:
    app = None  # type: ignore
try:
    from .core.model_router import ModelRouter  # type: ignore
except Exception:
    ModelRouter = None  # type: ignore
try:
    from .core.rag_engine import RAGEngine  # type: ignore
except Exception:
    RAGEngine = None  # type: ignore
try:
    from .core.cache import SemanticCache as CacheManager  # type: ignore
    from .core.cache import SemanticCache  # type: ignore
except Exception:
    CacheManager = None  # type: ignore
    SemanticCache = None  # type: ignore
try:
    from .core.async_tasks import app as TaskManager  # type: ignore
except Exception:
    TaskManager = None  # type: ignore

__all__ = [
    "app",
    "ModelRouter",
    "RAGEngine",
    "CacheManager",
    "SemanticCache",
    "TaskManager"
]