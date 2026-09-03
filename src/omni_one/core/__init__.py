"""
Core business logic and utilities for Omni-One Enterprise AI Platform
"""

try:
    from .model_router import ModelRouter  # type: ignore
except Exception:
    ModelRouter = None  # type: ignore
try:
    from .rag_engine import RAGEngine  # type: ignore
except Exception:
    RAGEngine = None  # type: ignore
try:
    from .cache import SemanticCache, CacheManager  # type: ignore
except Exception:
    try:
        from .cache import SemanticCache as CacheManager  # type: ignore
        SemanticCache = CacheManager  # type: ignore
    except Exception:
        CacheManager = None  # type: ignore
        SemanticCache = None  # type: ignore
try:
    from .async_tasks import app as TaskManager  # type: ignore
except Exception:
    TaskManager = None  # type: ignore

__all__ = [
    "ModelRouter",
    "RAGEngine",
    "CacheManager",
    "SemanticCache",
    "TaskManager"
]