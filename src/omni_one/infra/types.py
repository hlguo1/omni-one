"""Infra compat shim — re-export core types for FastAPI factory."""
try:
    from ..core.types import *  # type: ignore
    from ..core.types import HealthStatus  # type: ignore
except ImportError:
    from core.types import *  # type: ignore
    from core.types import HealthStatus  # type: ignore
