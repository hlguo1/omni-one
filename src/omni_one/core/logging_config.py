"""
Structured logging with context propagation for enterprise observability.

Provides contextualized logging using structlog with automatic correlation IDs,
request context, and performance metrics.
"""

import logging
import sys
import json
from contextvars import ContextVar
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID
import time

import structlog
from structlog.types import EventDict
from structlog.processors import (
    TimeStamper, add_log_level, JSONRenderer,
    format_exc_info, UnicodeDecoder
)


# Context variables for request tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class RequestContextFilter(logging.Filter):
    """Add request context to standard logging records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.session_id = session_id_var.get()
        record.trace_id = trace_id_var.get()
        return True


class ContextualProcessor:
    """Add contextual information to every log entry."""
    
    @staticmethod
    def __call__(logger, name: str, event_dict: EventDict) -> EventDict:
        """Add context variables to event dict."""
        event_dict["request_id"] = request_id_var.get()
        event_dict["user_id"] = user_id_var.get()
        event_dict["session_id"] = session_id_var.get()
        event_dict["trace_id"] = trace_id_var.get()
        event_dict["timestamp"] = datetime.utcnow().isoformat()
        return event_dict


class PerformanceMetricsProcessor:
    """Track and log performance metrics."""
    
    @staticmethod
    def __call__(logger, name: str, event_dict: EventDict) -> EventDict:
        """Add performance metrics to event dict."""
        if "duration_ms" in event_dict:
            # Add performance classification
            duration = event_dict["duration_ms"]
            if duration > 5000:
                event_dict["performance"] = "slow"
            elif duration > 1000:
                event_dict["performance"] = "moderate"
            else:
                event_dict["performance"] = "fast"
        return event_dict


class ExceptionDetailProcessor:
    """Add detailed exception information."""
    
    @staticmethod
    def __call__(logger, name: str, event_dict: EventDict) -> EventDict:
        """Enhance exception information."""
        if "exc_info" in event_dict and event_dict.get("exc_info"):
            exc = event_dict.get("exception")
            if exc:
                event_dict["exception_type"] = type(exc).__name__
                event_dict["exception_message"] = str(exc)
        return event_dict


def configure_logging(log_level=logging.INFO, use_json: bool = True):
    """Configure structured logging for production readiness."""
    
    # Standard logging configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add request context filter
    root_logger.addFilter(RequestContextFilter())
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Configure structlog processors
    processors = [
        TimeStamper(fmt="iso"),
        add_log_level,
        format_exc_info,
        UnicodeDecoder(),
        ContextualProcessor(),
        PerformanceMetricsProcessor(),
        ExceptionDetailProcessor(),
    ]
    
    if use_json:
        processors.append(JSONRenderer())
        formatter = logging.Formatter("%(message)s")
    else:
        # Human-readable format for development
        from structlog.dev import ConsoleRenderer
        processors.append(ConsoleRenderer(colors=True))
        formatter = logging.Formatter("%(message)s")
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )
    
    return structlog.get_logger()


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# ============================================================================
# CONTEXT MANAGERS FOR REQUEST TRACKING
# ============================================================================

class RequestContext:
    """Context manager for request-scoped logging."""
    
    def __init__(
        self,
        request_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.session_id = session_id
        self.trace_id = trace_id
        self.tokens = []
    
    def __enter__(self):
        """Set context variables on entry."""
        self.tokens.append(request_id_var.set(self.request_id))
        self.tokens.append(user_id_var.set(self.user_id))
        self.tokens.append(session_id_var.set(self.session_id))
        self.tokens.append(trace_id_var.set(self.trace_id))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clear context variables on exit."""
        for token in reversed(self.tokens):
            try:
                token.delete()
            except RuntimeError:
                pass  # Token already deleted
        return False


class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, logger: Optional[structlog.stdlib.BoundLogger] = None):
        self.operation_name = operation_name
        self.logger = logger or get_logger()
        self.start_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug("operation_started", operation=self.operation_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.logger.error(
                "operation_failed",
                operation=self.operation_name,
                duration_ms=self.duration_ms,
                exception=exc_val,
            )
        else:
            self.logger.info(
                "operation_completed",
                operation=self.operation_name,
                duration_ms=round(self.duration_ms, 2),
            )
        
        return False


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def set_request_context(
    request_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    trace_id: Optional[str] = None,
):
    """Set logging context for current request."""
    request_id_var.set(request_id)
    user_id_var.set(user_id)
    session_id_var.set(session_id)
    trace_id_var.set(trace_id)


def clear_request_context():
    """Clear all request context."""
    request_id_var.set(None)
    user_id_var.set(None)
    session_id_var.set(None)
    trace_id_var.set(None)


def get_request_context() -> Dict[str, Optional[str]]:
    """Get current request context."""
    return {
        "request_id": request_id_var.get(),
        "user_id": user_id_var.get(),
        "session_id": session_id_var.get(),
        "trace_id": trace_id_var.get(),
    }


__all__ = [
    "configure_logging",
    "get_logger",
    "RequestContext",
    "OperationTimer",
    "set_request_context",
    "clear_request_context",
    "get_request_context",
]
