"""
Modern FastAPI application example for Omni-One.

Demonstrates best practices for:
- Dependency injection
- Error handling with custom exceptions
- Structured logging with tracing
- Input validation with Pydantic models
- Health checks and monitoring
- Type safety and documentation
"""

from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, Query, Body, status
from fastapi.responses import JSONResponse

from ..infra.fastapi_factory import create_app
from ..infra.di_container import get_container
from ..infra.logging_config import get_logger, OperationTimer, set_request_context
from ..infra.settings import get_settings, Settings
from ..core.types import AIRequest, AIResponse, ProcessingMetrics, UserTier, TaskType
from ..core.exceptions import (
    ValidationError, InvalidFieldError, ModelInferenceError,
    format_exception
)


logger = get_logger(__name__)
container = get_container()


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_current_user(authorization: Optional[str] = None) -> Optional[str]:
    """Extract user from authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


# ============================================================================
# API ROUTES
# ============================================================================

def setup_ai_routes(app: FastAPI):
    """Setup AI inference routes."""
    
    @app.post(
        "/api/v1/synthesize",
        response_model=AIResponse,
        status_code=status.HTTP_200_OK,
        summary="AI Synthesis",
        tags=["AI"],
        responses={
            200: {"description": "Synthesis successful"},
            400: {"description": "Invalid request"},
            429: {"description": "Rate limit exceeded"},
            500: {"description": "Internal server error"},
        },
    )
    async def synthesize(
        request: AIRequest,
        settings: Settings = Depends(get_settings),
        current_user: Optional[str] = Depends(get_current_user),
    ) -> AIResponse:
        """
        Generate AI synthesis for complex data.
        
        Combines multiple data sources and AI models to produce actionable insights.
        
        **Features:**
        - Multi-modal data processing
        - Retrieval-Augmented Generation (RAG)
        - Model routing based on complexity
        - Response caching and quality validation
        
        **Request Body:**
        - `query`: The synthesis prompt (required)
        - `context`: List of context strings to augment the query
        - `task_type`: Type of task (general_qa, synthesis, analysis, etc.)
        - `user_tier`: User subscription tier
        - `temperature`: Generation temperature (0.0-2.0)
        - `max_tokens`: Maximum tokens to generate
        
        **Response:**
        - `response`: Generated synthesis text
        - `quality_score`: Quality assessment (0-1)
        - `model_used`: Which model was used
        - `latency_ms`: Response time in milliseconds
        - `citations`: Sources used for RAG-augmented response
        """
        
        # Set request context for logging
        set_request_context(request_id=str(request.request_id), user_id=current_user)
        
        with OperationTimer("synthesis_operation", logger) as timer:
            try:
                # Validate request
                if not request.query or len(request.query.strip()) == 0:
                    raise ValidationError("Query cannot be empty")
                
                if request.max_tokens < 100 or request.max_tokens > 4096:
                    raise InvalidFieldError(
                        field_name="max_tokens",
                        value=request.max_tokens,
                        reason="Must be between 100 and 4096"
                    )
                
                # TODO: Implement actual synthesis logic
                # This would integrate with RAG engine, model router, etc.
                response_text = f"Synthesized response for: {request.query}"
                
                return AIResponse(
                    request_id=request.request_id,
                    response=response_text,
                    model_used="gemini-2.5-flash",
                    quality_score=0.95,
                    cached=False,
                    latency_ms=int(timer.duration_ms or 0),
                    citations=[],
                    metadata={
                        "processing_layers": ["layer_1", "layer_2", "layer_3"],
                        "user_tier": request.user_tier.value,
                        "task_type": request.task_type.value,
                    },
                )
            
            except (ValidationError, InvalidFieldError) as e:
                logger.warning("request_validation_failed", error=str(e))
                raise
            
            except ModelInferenceError as e:
                logger.error("model_inference_failed", error=str(e))
                raise
    
    
    @app.post(
        "/api/v1/analyze",
        response_model=dict,
        status_code=status.HTTP_200_OK,
        summary="Data Analysis",
        tags=["Data"],
    )
    async def analyze(
        data: dict = Body(..., example={"records": [{"id": 1, "value": 100}]}),
        settings: Settings = Depends(get_settings),
    ) -> dict:
        """
        Analyze structured data using multi-layer pipeline.
        
        **Layers:**
        1. **Layer 1**: Fast ingestion and validation (<1ms)
        2. **Layer 2**: Statistical anomaly detection (<10ms)
        3. **Layer 3**: ML feature engineering (<100ms)
        4. **Layer 4**: LLM synthesis (gated, only if needed)
        
        This approach dramatically reduces LLM calls while maintaining quality.
        """
        
        with OperationTimer("data_analysis", logger):
            if not isinstance(data, dict) or "records" not in data:
                raise ValidationError("Request must contain 'records' field")
            
            records = data.get("records", [])
            
            # TODO: Implement actual analysis
            return {
                "analysis": "Complete",
                "records_processed": len(records),
                "metrics": {
                    "total": len(records),
                    "anomalies_detected": 0,
                    "llm_bypass_rate": 0.95,
                },
            }
    
    
    @app.get(
        "/api/v1/models",
        response_model=list,
        summary="List Available Models",
        tags=["AI"],
    )
    async def list_models() -> list[dict]:
        """
        List available AI models with costs and performance metrics.
        
        **Model Tiers:**
        - **Fast**: Low latency, lower quality (good for high volume)
        - **Balanced**: Good latency-quality tradeoff
        - **Premium**: Higher quality (good for complex tasks)
        """
        
        return [
            {
                "name": "gemini-2.5-flash",
                "quality": "fast",
                "cost_per_mtok": 0.075,
                "latency_p95_ms": 120,
            },
            {
                "name": "gemini-2-pro",
                "quality": "premium",
                "cost_per_mtok": 0.10,
                "latency_p95_ms": 300,
            },
            {
                "name": "gpt-4o",
                "quality": "premium",
                "cost_per_mtok": 1.00,
                "latency_p95_ms": 400,
            },
        ]
    
    
    @app.get(
        "/api/v1/metrics",
        response_model=ProcessingMetrics,
        summary="System Metrics",
        tags=["Analytics"],
    )
    async def get_metrics() -> ProcessingMetrics:
        """
        Get system-wide processing metrics.
        
        Shows throughput, costs, and efficiency metrics for the platform.
        """
        
        return ProcessingMetrics(
            total_records=10000,
            successfully_processed=9950,
            failed_records=50,
            llm_bypass_rate=0.92,
            average_processing_time_ms=45.5,
            layer_1_time_ms=0.5,
            layer_2_time_ms=5.2,
            layer_3_time_ms=35.0,
            layer_4_time_ms=120.0,
            total_cost_usd=125.50,
        )


def setup_admin_routes(app: FastAPI):
    """Setup admin/internal routes."""
    
    @app.get("/api/v1/admin/services", tags=["Admin"])
    async def list_services() -> dict:
        """List all registered services in DI container."""
        services = container.get_registered_services()
        
        service_info = {
            str(svc): container.get_service_info(svc)
            for svc in services
        }
        
        return {
            "total_services": len(services),
            "services": service_info,
        }
    
    
    @app.post("/api/v1/admin/clear-cache", tags=["Admin"])
    async def clear_cache() -> dict:
        """Clear request-scoped cache and reset DI container."""
        container.clear_request_scope()
        
        logger.info("admin_cache_cleared")
        
        return {
            "status": "success",
            "message": "Request scope cleared",
        }


# ============================================================================
# APPLICATION FACTORY
# ============================================================================

def create_omni_one_app() -> FastAPI:
    """
    Create fully configured Omni-One FastAPI application.
    
    Includes:
    - Dependency injection
    - Error handling
    - Health checks
    - Structured logging
    - Input validation
    - OpenAPI documentation
    """
    
    def setup_routes(app: FastAPI):
        """Setup all application routes."""
        setup_ai_routes(app)
        setup_admin_routes(app)
    
    app = create_app(setup_routes=setup_routes)
    
    logger.info("omni_one_fastapi_app_created")
    
    return app


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    app = create_omni_one_app()
    
    # Run with auto-reload in development
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5003,
        reload=True,
        log_level="info",
    )
