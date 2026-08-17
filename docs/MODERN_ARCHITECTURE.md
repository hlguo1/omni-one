# Omni-One: Industry-Advanced Architecture Guide

## Overview

This document describes the modern, production-grade architecture implemented in Omni-One. It demonstrates industry-standard patterns used at FAANG companies, including proper type safety, dependency injection, structured logging, health checks, and comprehensive error handling.

## Table of Contents

1. [Core Pillars](#core-pillars)
2. [Type System](#type-system)
3. [Error Handling](#error-handling)
4. [Dependency Injection](#dependency-injection)
5. [Structured Logging](#structured-logging)
6. [Configuration Management](#configuration-management)
7. [Health Checks](#health-checks)
8. [API Design](#api-design)
9. [Middleware](#middleware)
10. [Best Practices](#best-practices)

---

## Core Pillars

The modern architecture is built on these pillars:

### 1. Type Safety (Pydantic v2)
```python
from omni_one.core.types import AIRequest, AIResponse

# Automatic validation at runtime
request = AIRequest(
    query="Analyze customer churn",
    context=["Q3 revenue: $2.5M"],
    user_tier="enterprise",
    max_tokens=1024
)

# Type hints work with IDE and type checkers
async def process_request(req: AIRequest) -> AIResponse:
    ...
```

**Benefits:**
- IDE autocomplete and refactoring support
- Runtime validation with clear error messages
- OpenAPI documentation auto-generation
- Serialization/deserialization

### 2. Error Handling
```python
from omni_one.core.exceptions import (
    ValidationError, ModelInferenceError, format_exception
)

try:
    if not query:
        raise ValidationError("Query cannot be empty")
    
    response = await model.infer(query)
except ModelInferenceError as e:
    logger.error("inference_failed", error=e.to_error_detail())
    # Returns proper HTTP 500 with structured error info
```

**Features:**
- Custom exception hierarchy with HTTP status codes
- Error codes and severity levels
- Request correlation IDs in errors
- Structured error details for APIs

### 3. Dependency Injection
```python
from omni_one.infra.di_container import get_container

container = get_container()

# Register services
container.register_singleton(RAGEngine, factory=RAGEngine)
container.register_transient(ModelRouter, factory=ModelRouter)

# Resolve with automatic dependency injection
rag_engine = container.get_service(RAGEngine)
```

**Lifecycle Scopes:**
- **Singleton**: Single instance for app lifetime
- **Transient**: New instance every time
- **Request**: Single instance per HTTP request

### 4. Structured Logging
```python
from omni_one.infra.logging_config import get_logger, OperationTimer

logger = get_logger(__name__)

# Automatic context propagation
with OperationTimer("model_inference", logger):
    response = await model.infer(query)
    # Logs: operation_completed, duration_ms, request_id, user_id, etc.
```

**Features:**
- JSON structured logging for machine parsing
- Automatic correlation IDs
- Request context (user_id, session_id, trace_id)
- Performance metrics in every log
- Integration with Datadog/ELK/Splunk

### 5. Configuration Management
```python
from omni_one.infra.settings import Settings, Environment

settings = Settings()

# Type-safe configuration with validation
if settings.is_production():
    # Set stricter limits in production
    settings.rate_limit_requests = 1000
```

**Features:**
- Environment variable binding
- Runtime validation
- Development vs production differentiation
- Type hints for all settings

---

## Type System

Located in `src/omni_one/core/types.py`

### Request Models

```python
from omni_one.core.types import AIRequest, TaskType, UserTier

request = AIRequest(
    query="What is our churn risk?",
    context=["Customer revenue: $100k", "Support tickets: 3"],
    task_type=TaskType.ANALYSIS,
    user_tier=UserTier.ENTERPRISE,
    require_rag=True,
    temperature=0.7,
    max_tokens=1024
)

# Automatic validation
# - query: 1-4096 chars
# - temperature: 0.0-2.0
# - max_tokens: 100-4096
# - context: max 100 items
```

### Response Models

```python
from omni_one.core.types import AIResponse

response = AIResponse(
    request_id=request.request_id,
    response="Based on your data, we estimate 5% churn risk",
    model_used="gemini-2.5-flash",
    quality_score=0.95,
    cached=False,
    latency_ms=245,
    citations=[{"source": "CRM", "text": "..."}],
    metadata={"processing_layers": ["layer_1", "layer_2", "layer_3"]}
)
```

### Domain Models

```python
from omni_one.core.types import AnomalyAlert, ProcessingMetrics

alert = AnomalyAlert(
    entity_id="customer_123",
    anomaly_type="churn_spike",
    severity="high",
    recommended_actions=["Schedule call", "Offer discount"]
)

metrics = ProcessingMetrics(
    total_records=10000,
    llm_bypass_rate=0.92,  # 92% of records handled without LLM
    average_processing_time_ms=45.5,
    total_cost_usd=125.50
)
```

---

## Error Handling

Located in `src/omni_one/core/exceptions.py`

### Standard Pattern

```python
from omni_one.core.exceptions import (
    OmniOneException, ValidationError, ModelInferenceError,
    ErrorCode, ErrorSeverity
)

# Validation error
if not query:
    raise ValidationError(
        message="Query cannot be empty",
        context={"field": "query"},
        suggestion="Provide a non-empty query string",
        request_id=request_id
    )

# Service error
try:
    response = await model.infer(query)
except Exception as e:
    raise ModelInferenceError(
        model="gemini-2.5-flash",
        reason=str(e),
        request_id=request_id
    )
```

### Error Codes

```python
# Validation errors (4xx)
INVALID_REQUEST
MISSING_REQUIRED_FIELD
INVALID_FIELD_VALUE
RATE_LIMIT_EXCEEDED
AUTHENTICATION_FAILED
AUTHORIZATION_FAILED
RESOURCE_NOT_FOUND

# Service errors (5xx)
INTERNAL_SERVER_ERROR
SERVICE_UNAVAILABLE
MODEL_INFERENCE_FAILED
CACHE_ERROR
DATABASE_ERROR
TIMEOUT
```

### API Response Format

```json
{
  "code": "MODEL_INFERENCE_FAILED",
  "message": "Model inference failed for gemini-2.5-flash: ...",
  "status_code": 500,
  "severity": "error",
  "context": {"model": "gemini-2.5-flash"},
  "suggestion": "Try again or use a different model",
  "timestamp": "2024-01-15T10:30:45.123456",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Dependency Injection

Located in `src/omni_one/infra/di_container.py`

### Registration

```python
from omni_one.infra.di_container import get_container
from omni_one.core.rag_engine import RAGEngine
from omni_one.core.model_router import ModelRouter

container = get_container()

# Singleton - single instance for app
container.register_singleton(RAGEngine)

# Transient - new instance every time
container.register_transient(ModelRouter)

# Request-scoped - single per HTTP request
container.register_request_scoped(CacheManager)

# With factory function
def create_db_connection():
    return PostgresConnection("postgresql://...")

container.register_singleton(DatabaseConnection, factory=create_db_connection)
```

### Resolution

```python
# Automatic dependency resolution
rag_engine = container.get_service(RAGEngine)

# Try to get (returns None if not registered)
router = container.try_get_service(ModelRouter)

# Get all implementations
handlers = container.get_all_services(RequestHandler)
```

### FastAPI Integration

```python
from fastapi import Depends
from omni_one.infra.settings import get_settings

app = FastAPI()

@app.get("/synthesize")
async def synthesize(
    settings = Depends(get_settings),
    rag_engine = Depends(lambda: container.get_service(RAGEngine))
):
    # Services automatically injected
    return {"response": "..."}
```

---

## Structured Logging

Located in `src/omni_one/infra/logging_config.py`

### Basic Usage

```python
from omni_one.infra.logging_config import get_logger, set_request_context

logger = get_logger(__name__)

# Logs automatically include: timestamp, request_id, user_id, logger_name
logger.info("synthesis_started", model="gemini-2.5-flash", input_size=150)

# Output (JSON):
// {
//   "event": "synthesis_started",
//   "model": "gemini-2.5-flash",
//   "input_size": 150,
//   "request_id": "550e8400-e29b-41d4-a716-446655440000",
//   "timestamp": "2024-01-15T10:30:45.123456"
// }
```

### Request Context

```python
from omni_one.infra.logging_config import RequestContext

with RequestContext(request_id="unique-id", user_id="user_123"):
    logger.info("processing_start")
    # All logs in this context automatically include request_id and user_id
    do_work()
    logger.info("processing_complete")
```

### Performance Tracking

```python
from omni_one.infra.logging_config import OperationTimer

with OperationTimer("model_inference", logger) as timer:
    response = await model.infer(query)
    
# Logs: operation_completed with duration_ms=245

# Check timing
if timer.duration_ms > 5000:
    print("Slow operation!")
```

---

## Configuration Management

Located in `src/omni_one/infra/settings.py`

### Environment Binding

```python
# .env file
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=5003
GOOGLE_API_KEY=sk-...
REDIS_URL=redis://cache:6379
DATABASE_URL=postgresql://...
LOG_LEVEL=INFO
RATE_LIMIT_REQUESTS=1000
```

### Using Settings

```python
from omni_one.infra.settings import get_settings, Environment

settings = get_settings()

print(settings.environment)  # Environment.PRODUCTION
print(settings.port)  # 5003
print(settings.is_production())  # True
print(settings.is_development())  # False

# Type-safe access with autocomplete
if settings.enable_rag:
    rag_engine = RAGEngine(settings.weaviate_url)
```

### Validation

```python
# Automatic validation on load
if settings.is_production():
    # Checks enforced
    if settings.secret_key == "dev-secret-key-change-in-production":
        raise ValueError("Secret key must be changed in production!")
    
    if len(settings.secret_key) < 32:
        raise ValueError("Secret key must be at least 32 chars in production")
```

---

## Health Checks

Located in `src/omni_one/infra/health_checks.py`

### Registration

```python
from omni_one.infra.health_checks import get_health_registry, check_redis, check_database

registry = get_health_registry()

# Register health checks
registry.register_check(
    name="redis",
    check_func=lambda: check_redis(settings.redis_url),
    critical=True,  # Fail readiness if this fails
    timeout_seconds=2.0
)

registry.register_check(
    name="database",
    check_func=lambda: check_database(settings.database_url),
    critical=True,
    timeout_seconds=5.0
)

registry.register_check(
    name="weaviate",
    check_func=lambda: check_weaviate(settings.weaviate_url),
    critical=False,  # Degrade but still ready if this fails
    timeout_seconds=3.0
)
```

### Kubernetes Probes

```yaml
# Liveness probe - is container alive?
livenessProbe:
  httpGet:
    path: /health
    port: 5003
  initialDelaySeconds: 10
  periodSeconds: 10

# Readiness probe - is it ready to serve traffic?
readinessProbe:
  httpGet:
    path: /readiness
    port: 5003
  initialDelaySeconds: 5
  periodSeconds: 5
```

### API Endpoints

```
GET /health          - Simple liveness check
GET /readiness       - All critical checks pass?
GET /status          - Detailed health + metrics
GET /ping            - Load balancer check
```

---

## API Design

Located in `src/omni_one/api/fastapi_app.py` and `src/omni_one/infra/fastapi_factory.py`

### Creating an App

```python
from omni_one.infra.fastapi_factory import create_app
from fastapi import FastAPI

def setup_routes(app: FastAPI):
    @app.get("/api/v1/synthesize")
    async def synthesize(request: AIRequest) -> AIResponse:
        return {"response": "..."}

app = create_app(setup_routes=setup_routes)

# Run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)
```

### Request/Response Validation

```python
from fastapi import Depends, Body

@app.post("/api/v1/synthesize")
async def synthesize(
    request: AIRequest = Body(...),
    settings: Settings = Depends(get_settings)
) -> AIResponse:
    # Request automatically validated by Pydantic
    # - Type checking
    # - Bounds checking (temperature: 0.0-2.0)
    # - String lengths (query: 1-4096)
    
    return AIResponse(...)

# If validation fails, returns:
# {
//   "code": "INVALID_FIELD_VALUE",
//   "message": "Invalid value for field 'temperature': ...",
//   "status_code": 400,
//   ...
// }
```

### Dependency Injection

```python
def get_current_user(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None

@app.get("/api/v1/profile")
async def get_profile(
    current_user: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    db = Depends(lambda: container.get_service(Database))
) -> dict:
    # Dependencies injected automatically
    return db.get_user_profile(current_user)
```

---

## Middleware

Located in `src/omni_one/infra/middleware.py`

### Automatic Features

1. **Request ID Tracking**
   - Generates unique ID per request
   - Propagates through all logs
   - Returns in response headers

2. **Authentication**
   - API key validation from header or query
   - Header: `Authorization: Bearer <key>`
   - Header: `X-API-Key: <key>`
   - Query param: `?api_key=<key>`

3. **CORS**
   - Configurable allowed origins
   - Automatic preflight handling

4. **Input Validation**
   - Content-Type checking
   - Request size limits
   - Header validation

5. **Error Handling**
   - Catches all exceptions
   - Returns structured error responses
   - Logs with correlation ID

6. **Performance Monitoring**
   - Measures request latency
   - Adds timing headers
   - Logs slow operations

---

## Best Practices

### 1. Always Use Type Hints

```python
# Good
async def synthesize(request: AIRequest) -> AIResponse:
    pass

# Avoid
async def synthesize(request):
    pass
```

### 2. Use DI for Dependencies

```python
# Good
async def my_handler(
    rag_engine: RAGEngine = Depends(lambda: container.get_service(RAGEngine))
):
    pass

# Avoid
from omni_one.core.rag_engine import RAGEngine
rag = RAGEngine()  # Creates new instance, no testing support
```

### 3. Handle Errors Properly

```python
# Good
try:
    response = await model.infer(query)
except Exception as e:
    raise ModelInferenceError(model="...", reason=str(e), request_id=request_id)

# Avoid
try:
    response = await model.infer(query)
except:
    return {"error": "Something went wrong"}
```

### 4. Use Structured Logging

```python
# Good
logger.info("synthesis_complete", model=model_name, latency_ms=245, quality=0.95)

# Avoid
print(f"Done: {model_name} in 245ms")
```

### 5. Validate Inputs

```python
# Good
from omni_one.core.types import AIRequest

async def handle(request: AIRequest) -> AIResponse:
    # Validation happens automatically
    pass

# Avoid
async def handle(request: dict) -> dict:
    if "query" not in request:
        # Manual validation
        return {"error": "Missing query"}
```

---

## Migration Path from Flask to FastAPI

The codebase includes both Flask (`server.py`) and FastAPI implementations. To migrate:

1. **Existing endpoints**: Keep `server.py` running
2. **New endpoints**: Implement using FastAPI
3. **Gradual migration**: Move endpoints one by one to FastAPI
4. **Testing**: Use new test suite with pytest
5. **Monitoring**: Unified logging via structlog

---

## Key Files

| File | Purpose |
|------|---------|
| `core/types.py` | Pydantic type definitions |
| `core/exceptions.py` | Error handling hierarchy |
| `core/settings.py` | Configuration management |
| `infra/di_container.py` | Dependency injection |
| `infra/logging_config.py` | Structured logging |
| `infra/health_checks.py` | Health monitoring |
| `infra/middleware.py` | FastAPI middleware |
| `infra/fastapi_factory.py` | App factory |
| `api/fastapi_app.py` | Example routes |

---

## Conclusion

This architecture provides:
- ✅ Enterprise-grade error handling
- ✅ Type safety with full IDE support  
- ✅ Dependency injection for testability
- ✅ Structured logging for observability
- ✅ Health checks for Kubernetes
- ✅ Production-ready configuration
- ✅ Modern async FastAPI
- ✅ OpenAPI documentation
- ✅ Extensible middleware
- ✅ Security built-in

It follows patterns used at major tech companies and is ready for production deployment.
