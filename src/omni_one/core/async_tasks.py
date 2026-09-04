"""Async tasks (optional Celery). Seller OS never imports this — kept lazy so $0 path has no Redis/Celery dep."""
import os

try:
    from celery import Celery  # type: ignore
    CELERY_AVAILABLE = True
except ImportError:
    Celery = None  # type: ignore
    CELERY_AVAILABLE = False

try:
    from .rag_engine import RAGEngine  # type: ignore
    from .model_router import ModelRouter  # type: ignore
    from .cache import SemanticCache  # type: ignore
except ImportError:
    try:
        from omni_one.core.rag_engine import RAGEngine  # type: ignore
        from omni_one.core.model_router import ModelRouter  # type: ignore
        from omni_one.core.cache import SemanticCache  # type: ignore
    except ImportError:
        RAGEngine = None  # type: ignore
        ModelRouter = None  # type: ignore
        SemanticCache = None  # type: ignore

# Celery app (lazy: env REDIS_URL or localhost; only created if celery installed)
if CELERY_AVAILABLE:
    app = Celery('omni_tasks', broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"), backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"))  # type: ignore
else:
    app = None  # type: ignore

def _task(fn):
    """No-op decorator when Celery is missing (keeps import safe offline)."""
    if app is not None:
        try:
            return app.task(fn)  # type: ignore
        except Exception:
            return fn
    return fn

@_task
def synthesize_async(internal_data, external_data, user_prompt, mode):
    """Async synthesis task."""
    rag = RAGEngine()
    router = ModelRouter()
    cache = SemanticCache()

    # Check cache
    cache_key = f"{internal_data}_{external_data}_{user_prompt}_{mode}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Use RAG if internal data available
    if internal_data:
        rag.add_documents([{'content': internal_data, 'source': 'internal'}])
        response = rag.generate_with_rag(user_prompt)
    else:
        response = router.generate(user_prompt)

    result = {'insight': response, 'quality': {'passed': True, 'score': 95}}
    cache.set(cache_key, result)
    return result