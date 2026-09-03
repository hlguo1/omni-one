"""Infra compat shim — re-export core exceptions for middleware/factory."""
try:
    from ..core.exceptions import *  # type: ignore
except ImportError:
    from core.exceptions import *  # type: ignore
