"""
API endpoints and middleware for Omni-One Enterprise AI Platform
"""

try:
    from flask import Blueprint  # type: ignore

    api_bp = Blueprint('api', __name__)
except ImportError:  # pragma: no cover - legacy Flask blueprint, optional in minimal/FastAPI installs
    Blueprint = None  # type: ignore
    api_bp = None  # type: ignore

# Import routes here when created
# from .routes import *

__all__ = ['api_bp']