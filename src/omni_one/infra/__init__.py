"""
Infrastructure components initialization and utilities.

Centralized module for infrastructure setup including dependency injection,
health checks, logging, settings, and middleware configuration.
"""

from typing import Optional, Callable
from pathlib import Path

from .di_container import ServiceContainer, get_container, configure_container
from .health_checks import HealthCheckRegistry, get_health_registry
from .logging_config import configure_logging as setup_logging, get_logger
from .middleware import setup_middleware as setup_app_middleware
from .settings import Settings, get_settings

__all__ = [
    # Dependency Injection
    "ServiceContainer",
    "get_container",
    "configure_container",
    
    # Health Checks
    "HealthCheckRegistry",
    "get_health_registry",
    
    # Logging
    "setup_logging",
    "get_logger",
    
    # Middleware
    "setup_app_middleware",
    
    # Settings
    "Settings",
    "get_settings",
]


def initialize_infrastructure(settings: Optional[Settings] = None) -> tuple[ServiceContainer, HealthCheckRegistry]:
    """
    Initialize all infrastructure components.
    
    Args:
        settings: Custom settings instance. If None, uses default.
    
    Returns:
        Tuple of (service_container, health_registry)
    """
    # Get or create settings
    if settings is None:
        settings = get_settings()
    
    # Setup logging
    setup_logging(log_level=settings.log_level.value)
    logger = get_logger(__name__)
    
    logger.info("infrastructure_initialization_started", environment=settings.environment.value)
    
    # Initialize DI container
    container = get_container()
    
    # Register settings as singleton
    container.register_singleton(Settings, instance=settings)
    
    # Initialize health registry
    registry = get_health_registry()
    
    logger.info(
        "infrastructure_initialization_complete",
        services_registered=len(container.get_registered_services()),
    )
    
    return container, registry
