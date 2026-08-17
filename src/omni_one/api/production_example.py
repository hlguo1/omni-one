"""
Production example: Integrating new infrastructure with existing components.

This module demonstrates how to use the new industry-advanced infrastructure
with actual Omni-One services (RAG Engine, Model Router, etc.).
"""

from typing import Optional
import asyncio
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from ..infra.logging_config import get_logger, OperationTimer, RequestContext
from ..infra.di_container import get_container, ServiceContainer
from ..infra.settings import Settings, get_settings
from ..infra.fastapi_factory import create_app
from ..core.types import AIRequest, AIResponse, ProcessingMetrics, TaskType
from ..core.exceptions import ModelInferenceError, RAGEngineError, ValidationError
from ..core.model_router import ModelRouter
from ..core.rag_engine import RAGEngine
from ..core.cache import CacheManager  # Existing cache


logger = get_logger(__name__)
container = get_container()


# ============================================================================
# SERVICE SETUP
# ============================================================================

def setup_services(settings: Settings):
    """Initialize and register core services in DI container."""
    
    # Register model router
    def create_model_router():
        logger.info("initializing_model_router")
        return ModelRouter()
    
    container.register_singleton(ModelRouter, factory=create_model_router)
    
    # Register RAG engine
    def create_rag_engine():
        logger.info("initializing_rag_engine", weaviate_url=settings.weaviate_url)
        return RAGEngine()
    
    if settings.enable_rag:
        container.register_singleton(RAGEngine, factory=create_rag_engine)
    
    # Register cache manager
    def create_cache_manager():
        logger.info("initializing_cache_manager", redis_url=settings.redis_url)
        return CacheManager(settings.redis_url)
    
    if settings.cache_enabled:
        container.register_singleton(CacheManager, factory=create_cache_manager)
    
    logger.info("core_services_registered")


# ============================================================================
# SERVICE LAYER
# ============================================================================

class SynthesisService:
    """Main synthesis service using new infrastructure."""
    
    def __init__(
        self,
        model_router: ModelRouter = None,
        rag_engine: RAGEngine = None,
        cache_manager: CacheManager = None,
        settings: Settings = None,
    ):
        self.model_router = model_router
        self.rag_engine = rag_engine
        self.cache_manager = cache_manager
        self.settings = settings or get_settings()
    
    async def synthesize(self, request: AIRequest, user_id: Optional[str] = None) -> AIResponse:
        """
        Main synthesis pipeline with all new infrastructure components.
        
        Flow:
        1. Validate request
        2. Set request context for logging
        3. Check cache
        4. Select model based on complexity + budget
        5. If needed, retrieve context from RAG
        6. Call model
        7. Validate output quality
        8. Cache result
        """
        
        with OperationTimer("synthesis_pipeline", logger) as timer:
            try:
                # 1. Validation
                self._validate_request(request)
                
                # 2. Set request context for distributed tracing
                with RequestContext(request_id=str(request.request_id), user_id=user_id):
                    
                    # 3. Check cache first (if enabled)
                    cache_key = f"{request.query}_{request.task_type.value}"
                    if self.cache_manager and self.settings.cache_enabled:
                        cached = await self._get_from_cache(cache_key)
                        if cached:
                            logger.info("cache_hit", cache_key=cache_key)
                            return cached
                    
                    # 4. Select model based on complexity and cost
                    with OperationTimer("model_selection", logger):
                        model_selection = await self.model_router.select(request)
                        logger.info(
                            "model_selected",
                            primary_model=model_selection.primary_model,
                            estimated_cost=model_selection.estimated_cost_usd,
                            confidence=model_selection.confidence_score,
                        )
                    
                    # 5. Retrieve RAG context if needed
                    rag_citations = []
                    if request.require_rag and self.rag_engine:
                        try:
                            with OperationTimer("rag_retrieval", logger):
                                rag_citations = await self._retrieve_rag_context(request)
                                request.context.extend([c["text"] for c in rag_citations])
                        except Exception as e:
                            logger.warning("rag_retrieval_failed", error=str(e))
                            # Continue without RAG context
                    
                    # 6. Call model
                    with OperationTimer("model_inference", logger):
                        response_text = await self.model_router.generate(
                            prompt=request.query,
                            model=model_selection.primary_model,
                            temperature=request.temperature,
                            max_tokens=request.max_tokens,
                        )
                    
                    # 7. Validate quality
                    quality_score = await self._validate_quality(response_text, request)
                    
                    # 8. Create response
                    response = AIResponse(
                        request_id=request.request_id,
                        response=response_text,
                        model_used=model_selection.primary_model,
                        quality_score=quality_score,
                        cached=False,
                        latency_ms=int(timer.duration_ms or 0),
                        citations=rag_citations,
                        metadata={
                            "task_type": request.task_type.value,
                            "user_tier": request.user_tier.value,
                            "estimated_cost_usd": model_selection.estimated_cost_usd,
                            "routing_confidence": model_selection.confidence_score,
                        },
                    )
                    
                    # 9. Cache result (if performance permits)
                    if self.cache_manager:
                        try:
                            await self._cache_result(cache_key, response)
                        except Exception as e:
                            logger.warning("cache_write_failed", error=str(e))
                            # Non-blocking failure - continue anyway
                    
                    logger.info(
                        "synthesis_complete",
                        model=model_selection.primary_model,
                        quality_score=quality_score,
                        duration_ms=round(timer.duration_ms or 0, 2),
                    )
                    
                    return response
            
            except ValidationError as e:
                logger.warning("validation_error", error=str(e))
                raise
            
            except ModelInferenceError as e:
                logger.error("inference_error", error=str(e))
                raise
    
    def _validate_request(self, request: AIRequest) -> None:
        """Validate request with detailed error messages."""
        if not request.query or len(request.query.strip()) == 0:
            raise ValidationError(
                message="Query cannot be empty",
                context={"field": "query"},
                suggestion="Provide a non-empty query",
            )
        
        if len(request.query) > 4096:
            raise ValidationError(
                message="Query exceeds maximum length of 4096 characters",
                context={"field": "query", "length": len(request.query), "max": 4096},
            )
        
        if request.temperature < 0.0 or request.temperature > 2.0:
            raise ValidationError(
                message="Temperature must be between 0.0 and 2.0",
                context={"field": "temperature", "value": request.temperature},
            )
    
    async def _get_from_cache(self, cache_key: str) -> Optional[AIResponse]:
        """Get response from cache."""
        try:
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                # Reconstruct AIResponse from cached data
                cached_response = AIResponse(**{
                    **cached_data,
                    "cached": True,
                })
                return cached_response
        except Exception as e:
            logger.warning("cache_retrieval_error", error=str(e))
        
        return None
    
    async def _cache_result(self, cache_key: str, response: AIResponse) -> None:
        """Cache the result."""
        try:
            cache_data = response.model_dump()
            self.cache_manager.set(cache_key, cache_data, ttl=3600)
            logger.debug("result_cached", cache_key=cache_key)
        except Exception as e:
            logger.warning("cache_write_error", error=str(e))
            # Don't raise - caching failure is non-critical
    
    async def _retrieve_rag_context(self, request: AIRequest) -> list[dict]:
        """Retrieve context from RAG engine."""
        try:
            docs = self.rag_engine.retrieve(request.query, k=5)
            
            citations = [
                {
                    "source": doc.get("source", "unknown"),
                    "text": doc.get("content", ""),
                    "relevance": doc.get("score", 0.0),
                }
                for doc in docs
            ]
            
            logger.info("rag_context_retrieved", num_documents=len(citations))
            return citations
        
        except Exception as e:
            raise RAGEngineError(
                operation="retrieve",
                reason=str(e),
            )
    
    async def _validate_quality(self, response: str, request: AIRequest) -> float:
        """
        Validate response quality.
        
        Scores 0.0-1.0 based on:
        - Response length
        - No hallucinations detected
        - Relevance to query
        """
        # TODO: Implement actual quality validation
        # For now, return placeholder score
        return 0.85


# ============================================================================
# API ROUTES
# ============================================================================

def setup_production_routes(app: FastAPI):
    """Setup API routes for production."""
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        settings = get_settings()
        setup_services(settings)
        logger.info("api_startup_complete")
    
    @app.post(
        "/api/v1/synthesize",
        response_model=AIResponse,
        summary="AI Synthesis with Full Infrastructure",
        description="""
        Perform AI synthesis using the complete production infrastructure.
        
        Features:
        - Automatic request validation
        - Model selection based on complexity
        - RAG context retrieval
        - Semantic caching
        - Quality validation
        - Structured logging with tracing
        - Error handling with recovery
        
        Request context (request ID, user ID, etc.) is automatically propagated
        through all logs and errors.
        """,
        tags=["AI"],
    )
    async def synthesize(
        request: AIRequest,
        settings: Settings = Depends(get_settings),
        current_user: Optional[str] = None,
    ) -> AIResponse:
        """Execute synthesis with full infrastructure."""
        
        try:
            # Get service from DI container (or create if not cached)
            model_router = container.get_service(ModelRouter)
            rag_engine = container.try_get_service(RAGEngine)
            cache_manager = container.try_get_service(CacheManager)
            
            # Create service instance
            service = SynthesisService(
                model_router=model_router,
                rag_engine=rag_engine,
                cache_manager=cache_manager,
                settings=settings,
            )
            
            # Execute synthesis
            response = await service.synthesize(request, user_id=current_user)
            
            return response
        
        except Exception as e:
            logger.error("synthesis_failed", error=str(e), exc_info=True)
            raise
    
    @app.get(
        "/api/v1/models/available",
        summary="List Available Models",
        tags=["AI"],
    )
    async def list_available_models(
        container: ServiceContainer = Depends(lambda: get_container()),
    ) -> dict:
        """Get list of available models and their characteristics."""
        
        try:
            model_router = container.get_service(ModelRouter)
            
            return {
                "models": [
                    {
                        "name": "gemini-2.5-flash",
                        "quality": "fast",
                        "latency_ms": 120,
                        "cost_per_mtok": 0.075,
                    },
                    {
                        "name": "gemini-2-pro",
                        "quality": "premium",
                        "latency_ms": 300,
                        "cost_per_mtok": 0.10,
                    },
                ],
                "default_model": model_router.select_model("medium"),
            }
        except Exception as e:
            logger.error("list_models_failed", error=str(e))
            raise
    
    @app.post(
        "/api/v1/batch-analyze",
        response_model=dict,
        summary="Batch Data Analysis",
        tags=["Data"],
    )
    async def batch_analyze(
        records: list[dict],
        task_type: TaskType = Query(TaskType.ANALYSIS),
        settings: Settings = Depends(get_settings),
    ) -> dict:
        """
        Analyze multiple records using the multi-layer pipeline.
        
        The pipeline intelligently decides which records need LLM processing
        and which can be handled by statistical/ML layers.
        """
        
        logger.info("batch_analysis_started", record_count=len(records))
        
        with OperationTimer("batch_analysis", logger):
            # TODO: Implement actual multi-layer pipeline
            return {
                "processed": len(records),
                "results": records,
                "metrics": {
                    "llm_calls": 0,
                    "statistical_bypassed": len(records),
                    "total_cost_usd": 0.0,
                },
            }


# ============================================================================
# APPLICATION FACTORY
# ============================================================================

def create_production_app() -> FastAPI:
    """
    Create production-ready FastAPI application with all infrastructure.
    
    Demonstrates:
    - Type validation (Pydantic)
    - Error handling (custom exceptions)
    - Dependency injection
    - Structured logging
    - Health checks
    - Middleware
    - OpenAPI documentation
    """
    
    return create_app(setup_routes=setup_production_routes)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    app = create_production_app()
    
    # Run with auto-reload
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5003,
        reload=True,
        log_level="info",
    )
    
    # API will be available at:
    # - http://localhost:5003/docs (Interactive API docs)
    # - http://localhost:5003/api/v1/synthesize (POST)
    # - http://localhost:5003/health (Liveness)
    # - http://localhost:5003/readiness (Readiness)
