"""
Production middleware for FastAPI with validation, tracing, and performance monitoring.

Provides middleware for request validation, error handling, correlation IDs,
response timing, and audit logging.
"""

from typing import Callable, Any, Optional
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import (
    AuthenticationBackend, AuthCredentials, SimpleUser, AuthenticationError
)
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from .exceptions import OmniOneException, AuthenticationError as AuthError
from .logging_config import (
    get_logger, RequestContext, OperationTimer, 
    set_request_context, clear_request_context
)
from .settings import Settings


logger = get_logger(__name__)


# ============================================================================
# AUTHENTICATION BACKEND
# ============================================================================

class APIKeyAuthBackend(AuthenticationBackend):
    """API key authentication backend."""
    
    def __init__(self, valid_api_keys: list[str]):
        self.valid_api_keys = set(valid_api_keys)
    
    async def authenticate(self, request: Request):
        """Authenticate request using API key from header or query param."""
        # Check header first
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
            if api_key in self.valid_api_keys:
                return AuthCredentials(["authenticated"]), SimpleUser(api_key)
            raise AuthenticationError("Invalid API key")
        
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            if api_key in self.valid_api_keys:
                return AuthCredentials(["authenticated"]), SimpleUser(api_key)
            raise AuthenticationError("Invalid API key")
        
        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            if api_key in self.valid_api_keys:
                return AuthCredentials(["authenticated"]), SimpleUser(api_key)
            raise AuthenticationError("Invalid API key")
        
        # For public endpoints, return None
        return None


# ============================================================================
# MIDDLEWARE
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add correlation ID to every request and response."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request context."""
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Extract user info if available
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")
        trace_id = request.headers.get("X-Trace-ID", request_id)
        
        # Set context for logging
        set_request_context(
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
        )
        
        # Store request ID and trace ID in request state
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.user_id = user_id
        
        try:
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            
            return response
        finally:
            clear_request_context()


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Track request performance and add timing headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request timing."""
        start_time = time.time()
        request_id = getattr(request.state, "request_id", "unknown")
        
        try:
            response = await call_next(request)
        except Exception as e:
            # Log exception with timing
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                path=request.url.path,
                method=request.method,
                duration_ms=round(duration_ms, 2),
                exception=e,
                request_id=request_id,
            )
            raise
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Add timing headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Process-Time"] = f"{duration_ms:.4f}"
        
        # Log request completion
        log_level = "warning" if duration_ms > 5000 else "info"
        logger.log(
            log_level,
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )
        
        return response


class ExceptionMiddleware(BaseHTTPMiddleware):
    """Handle exceptions and return structured error responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Catch exceptions and return proper error responses."""
        request_id = getattr(request.state, "request_id", None)
        
        try:
            response = await call_next(request)
            return response
        
        except OmniOneException as e:
            # Handle Omni-One exceptions
            e.request_id = request_id
            error_detail = e.to_error_detail()
            
            logger.error(
                "omni_exception",
                error_code=e.code.value,
                error_message=e.message,
                status_code=e.status_code,
                request_id=request_id,
            )
            
            return JSONResponse(
                status_code=e.status_code,
                content=error_detail.to_dict(),
            )
        
        except AuthError as e:
            # Handle authentication errors
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={
                    "code": "AUTHENTICATION_FAILED",
                    "message": str(e),
                    "status_code": HTTP_401_UNAUTHORIZED,
                    "request_id": request_id,
                },
            )
        
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(
                "unhandled_exception",
                exception=e,
                request_id=request_id,
                exc_info=True,
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "status_code": 500,
                    "request_id": request_id,
                },
            )


class InputValidationMiddleware(BaseHTTPMiddleware):
    """Validate request inputs and headers."""
    
    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Validate request inputs."""
        # Skip validation for health checks and swagger docs
        if request.url.path in ["/health", "/readiness", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Validate content type for POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "code": "INVALID_REQUEST",
                        "message": "Content-Type must be application/json",
                        "status_code": 400,
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )
        
        # Validate request size (max 10MB by default)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size_bytes = int(content_length)
                max_size = 10 * 1024 * 1024  # 10MB
                if size_bytes > max_size:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "code": "INVALID_REQUEST",
                            "message": f"Request too large (max {max_size} bytes)",
                            "status_code": 413,
                            "request_id": getattr(request.state, "request_id", None),
                        },
                    )
            except ValueError:
                pass
        
        return await call_next(request)


def setup_middleware(app, settings: Settings, valid_api_keys: list[str]):
    """Setup all middleware for FastAPI app."""
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add input validation
    app.add_middleware(InputValidationMiddleware, settings=settings)
    
    # Add exception handling
    app.add_middleware(ExceptionMiddleware)
    
    # Add performance monitoring
    app.add_middleware(PerformanceMiddleware)
    
    # Add request ID tracking
    app.add_middleware(RequestIDMiddleware)
    
    # Add authentication
    app.add_middleware(
        AuthenticationMiddleware,
        backend=APIKeyAuthBackend(valid_api_keys)
    )
    
    logger.info("middleware_setup_complete")


__all__ = [
    "RequestIDMiddleware",
    "PerformanceMiddleware",
    "ExceptionMiddleware",
    "InputValidationMiddleware",
    "APIKeyAuthBackend",
    "setup_middleware",
]
