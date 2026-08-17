"""
Enterprise-grade exception hierarchy and error handling.

Provides structured error handling with proper error codes, HTTP status mapping,
and telemetry support for observability systems.
"""

from typing import Any, Dict, Optional, List
from enum import Enum
from dataclasses import dataclass, field, asdict
from datetime import datetime
import traceback


class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    
    # Validation errors (4xx)
    INVALID_REQUEST = "INVALID_REQUEST"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FIELD_VALUE = "INVALID_FIELD_VALUE"
    INVALID_ENUM_VALUE = "INVALID_ENUM_VALUE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    CONFLICT = "CONFLICT"
    
    # Service errors (5xx)
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    MODEL_INFERENCE_FAILED = "MODEL_INFERENCE_FAILED"
    CACHE_ERROR = "CACHE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    RAG_ENGINE_ERROR = "RAG_ENGINE_ERROR"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    
    # Configuration errors
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    MISSING_API_KEY = "MISSING_API_KEY"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    
    # Business logic errors
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    OPERATION_NOT_SUPPORTED = "OPERATION_NOT_SUPPORTED"


class ErrorSeverity(str, Enum):
    """Error severity levels for logging and alerting."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorDetail:
    """Detailed error information."""
    code: ErrorCode
    message: str
    status_code: int
    severity: ErrorSeverity = ErrorSeverity.ERROR
    context: Dict[str, Any] = field(default_factory=dict)
    suggestion: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code.value,
            "message": self.message,
            "status_code": self.status_code,
            "severity": self.severity.value,
            "context": self.context,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp.isoformat(),
            "request_id": self.request_id,
        }


class OmniOneException(Exception):
    """Base exception for Omni-One platform."""
    
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        request_id: Optional[str] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = context or {}
        self.suggestion = suggestion
        self.severity = severity
        self.request_id = request_id
        self.timestamp = datetime.utcnow()
        
        super().__init__(self.message)
    
    def to_error_detail(self) -> ErrorDetail:
        """Convert to ErrorDetail for API responses."""
        return ErrorDetail(
            code=self.code,
            message=self.message,
            status_code=self.status_code,
            severity=self.severity,
            context=self.context,
            suggestion=self.suggestion,
            timestamp=self.timestamp,
            request_id=self.request_id,
        )
    
    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


# ============================================================================
# VALIDATION ERRORS (4xx)
# ============================================================================

class ValidationError(OmniOneException):
    """Raised when request validation fails."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INVALID_REQUEST,
        **kwargs
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=400,
            severity=ErrorSeverity.WARNING,
            **kwargs
        )


class MissingFieldError(ValidationError):
    """Raised when required field is missing."""
    
    def __init__(self, field_name: str, request_id: Optional[str] = None):
        super().__init__(
            message=f"Required field missing: {field_name}",
            code=ErrorCode.MISSING_REQUIRED_FIELD,
            context={"field": field_name},
            suggestion=f"Provide a value for the '{field_name}' field",
            request_id=request_id,
        )


class InvalidFieldError(ValidationError):
    """Raised when field has invalid value."""
    
    def __init__(
        self,
        field_name: str,
        value: Any,
        reason: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=f"Invalid value for field '{field_name}': {reason}",
            code=ErrorCode.INVALID_FIELD_VALUE,
            context={"field": field_name, "value": str(value)},
            suggestion=f"Provide a valid value for '{field_name}'",
            request_id=request_id,
        )


class RateLimitError(OmniOneException):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        retry_after: int = 60,
        request_id: Optional[str] = None
    ):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            status_code=429,
            severity=ErrorSeverity.WARNING,
            context={"limit": limit, "window_seconds": window_seconds},
            suggestion=f"Retry after {retry_after} seconds",
            request_id=request_id,
        )
        self.retry_after = retry_after


class AuthenticationError(OmniOneException):
    """Raised when authentication fails."""
    
    def __init__(self, reason: str, request_id: Optional[str] = None):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_FAILED,
            message=f"Authentication failed: {reason}",
            status_code=401,
            severity=ErrorSeverity.WARNING,
            context={"reason": reason},
            suggestion="Verify API key and try again",
            request_id=request_id,
        )


class AuthorizationError(OmniOneException):
    """Raised when authorization check fails."""
    
    def __init__(self, resource: str, request_id: Optional[str] = None):
        super().__init__(
            code=ErrorCode.AUTHORIZATION_FAILED,
            message=f"Not authorized to access: {resource}",
            status_code=403,
            severity=ErrorSeverity.WARNING,
            context={"resource": resource},
            suggestion="Contact support if you believe you should have access",
            request_id=request_id,
        )


class NotFoundError(OmniOneException):
    """Raised when resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str, request_id: Optional[str] = None):
        super().__init__(
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"{resource_type} not found: {resource_id}",
            status_code=404,
            severity=ErrorSeverity.WARNING,
            context={"resource_type": resource_type, "resource_id": resource_id},
            request_id=request_id,
        )


# ============================================================================
# SERVICE ERRORS (5xx)
# ============================================================================

class ServiceError(OmniOneException):
    """Base for internal service errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_SERVER_ERROR,
        status_code: int = 500,
        **kwargs
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            severity=ErrorSeverity.ERROR,
            **kwargs
        )


class ModelInferenceError(ServiceError):
    """Raised when model inference fails."""
    
    def __init__(
        self,
        model: str,
        reason: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=f"Model inference failed for {model}: {reason}",
            code=ErrorCode.MODEL_INFERENCE_FAILED,
            context={"model": model, "reason": reason},
            suggestion="Try again or use a different model",
            request_id=request_id,
        )


class CacheError(ServiceError):
    """Raised when cache operations fail."""
    
    def __init__(self, operation: str, reason: str, request_id: Optional[str] = None):
        super().__init__(
            message=f"Cache {operation} failed: {reason}",
            code=ErrorCode.CACHE_ERROR,
            context={"operation": operation},
            suggestion="The system will continue without caching",
            request_id=request_id,
        )


class RAGEngineError(ServiceError):
    """Raised when RAG engine fails."""
    
    def __init__(self, operation: str, reason: str, request_id: Optional[str] = None):
        super().__init__(
            message=f"RAG engine {operation} failed: {reason}",
            code=ErrorCode.RAG_ENGINE_ERROR,
            context={"operation": operation},
            suggestion="The system will attempt response without RAG context",
            request_id=request_id,
        )


class DatabaseError(ServiceError):
    """Raised when database operations fail."""
    
    def __init__(self, operation: str, reason: str, request_id: Optional[str] = None):
        super().__init__(
            message=f"Database {operation} failed: {reason}",
            code=ErrorCode.DATABASE_ERROR,
            context={"operation": operation},
            suggestion="Please retry or contact support",
            request_id=request_id,
        )


class ExternalAPIError(ServiceError):
    """Raised when external API call fails."""
    
    def __init__(
        self,
        service: str,
        status_code: int,
        reason: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=f"External API error from {service} (HTTP {status_code}): {reason}",
            code=ErrorCode.EXTERNAL_API_ERROR,
            context={"service": service, "status_code": status_code},
            suggestion="Check external service status or retry later",
            request_id=request_id,
        )


class TimeoutError(ServiceError):
    """Raised when operation times out."""
    
    def __init__(
        self,
        operation: str,
        timeout_seconds: float,
        request_id: Optional[str] = None
    ):
        super().__init__(
            message=f"{operation} timed out after {timeout_seconds}s",
            code=ErrorCode.TIMEOUT,
            status_code=504,
            context={"operation": operation, "timeout_seconds": timeout_seconds},
            suggestion="Try again with a simpler request",
            request_id=request_id,
        )


class DependencyUnavailableError(ServiceError):
    """Raised when dependency is unavailable."""
    
    def __init__(self, dependency: str, request_id: Optional[str] = None):
        super().__init__(
            message=f"Required dependency unavailable: {dependency}",
            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            status_code=503,
            context={"dependency": dependency},
            suggestion="System is temporarily degraded. Please retry soon.",
            request_id=request_id,
        )


# ============================================================================
# CONFIGURATION ERRORS
# ============================================================================

class ConfigurationError(OmniOneException):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.CONFIGURATION_ERROR,
            message=message,
            status_code=500,
            severity=ErrorSeverity.CRITICAL,
            context=context or {},
            suggestion="Check your environment variables and configuration files",
        )


class MissingAPIKeyError(ConfigurationError):
    """Raised when required API key is missing."""
    
    def __init__(self, key_name: str):
        super().__init__(
            message=f"Required API key missing: {key_name}",
            context={"key": key_name}
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_exception(exc: Exception, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Format exception for logging and API responses."""
    if isinstance(exc, OmniOneException):
        error_detail = exc.to_error_detail()
        if request_id:
            error_detail.request_id = request_id
        return error_detail.to_dict()
    
    # For non-Omni exceptions, wrap as internal error
    return {
        "code": ErrorCode.INTERNAL_SERVER_ERROR.value,
        "message": str(exc),
        "status_code": 500,
        "severity": ErrorSeverity.ERROR.value,
        "context": {"exception_type": type(exc).__name__},
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": request_id,
        "traceback": traceback.format_exc() if hasattr(exc, "__traceback__") else None,
    }
