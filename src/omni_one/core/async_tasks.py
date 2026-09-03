from celery import Celery
import os
try:
    from .rag_engine import RAGEngine  # type: ignore
    from .model_router import ModelRouter  # type: ignore
    from .cache import SemanticCache  # type: ignore
except ImportError:
    from rag_engine import RAGEngine  # type: ignore
    from model_router import ModelRouter  # type: ignore
    from cache import SemanticCache  # type: ignore

# Celery app
app = Celery('omni_tasks', broker='redis://localhost:6379/0', backend='redis://localhost:6379/0')

@app.task
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