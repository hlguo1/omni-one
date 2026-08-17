"""
FastAPI application factory for modern, production-grade API.

Creates fully configured FastAPI application with all middleware, error handling,
documentation, and health checks pre-configured.
"""

from typing import Optional, Callable, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from .settings import Settings, get_settings
from .logging_config import configure_logging, get_logger
from .middleware import setup_middleware
from .health_checks import (
    get_health_registry, SystemHealthMonitor,
    check_redis, check_database, check_weaviate
)
from .exceptions import OmniOneException
from .di_container import get_container
from .types import HealthStatus


logger = get_logger(__name__)


class OmniOneAPIFactory:
    """Factory for creating fully configured FastAPI applications."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.container = get_container()
        self.health_registry = get_health_registry()
    
    def create_app(
        self,
        title: str = "Omni-One Enterprise AI Platform",
        version: str = "1.0.0",
        setup_routes: Optional[Callable[[FastAPI], None]] = None,
    ) -> FastAPI:
        """Create and configure FastAPI application."""
        
        # Setup logging
        configure_logging(log_level=self.settings.log_level.value)
        
        # Lifespan context manager for startup/shutdown
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info("application_startup", environment=self.settings.environment.value)
            
            # Setup health checks
            await self._setup_health_checks()
            
            yield
            
            # Shutdown
            logger.info("application_shutdown")
            self.container.clear_request_scope()
        
        # Create FastAPI app
        app = FastAPI(
            title=title,
            version=version,
            description="Enterprise AI platform with proactive intelligence, multi-modal processing, and ethical AI governance",
            lifespan=lifespan,
            docs_url="/api/docs" if not self.settings.is_production() else None,
            redoc_url="/api/redoc" if not self.settings.is_production() else None,
            openapi_url="/api/openapi.json" if not self.settings.is_production() else None,
        )
        
        # Custom OpenAPI schema
        def custom_openapi():
            if app.openapi_schema:
                return app.openapi_schema
            
            openapi_schema = get_openapi(
                title=title,
                version=version,
                description=app.description,
                routes=app.routes,
                tags=self._get_openapi_tags(),
            )
            
            openapi_schema["info"]["x-logo"] = {
                "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
            }
            
            app.openapi_schema = openapi_schema
            return app.openapi_schema
        
        app.openapi = custom_openapi
        
        # Setup middleware
        setup_middleware(app, self.settings, self.settings.api_keys)
        
        # Add health check endpoints
        self._add_health_endpoints(app)
        
        # Add dependency injection
        app.dependency_overrides[get_settings] = lambda: self.settings
        
        # Setup custom routes
        if setup_routes:
            setup_routes(app)
        
        logger.info(
            "fastapi_application_created",
            title=title,
            version=version,
            debug=self.settings.debug,
        )
        
        return app
    
    def _add_health_endpoints(self, app: FastAPI):
        """Add health check endpoints."""
        
        @app.get("/health", tags=["Health"])
        async def health_check():
            """
            Liveness probe for Kubernetes.
            
            Returns immediately if service is running.
            """
            return {
                "status": "alive",
                "service": "omni-one",
                "version": "1.0.0",
            }
        
        @app.get("/readiness", tags=["Health"])
        async def readiness_check():
            """
            Readiness probe for Kubernetes.
            
            Checks critical dependencies (Redis, Database, Weaviate).
            """
            is_ready = await self.health_registry.check_critical()
            
            status_code = 200 if is_ready else 503
            return JSONResponse(
                status_code=status_code,
                content={
                    "ready": is_ready,
                    "service": "omni-one",
                    "checks": await self.health_registry.check_all(),
                },
            )
        
        @app.get("/status", tags=["Health"])
        async def status_check():
            """
            Detailed system status including component health and metrics.
            """
            all_checks = await self.health_registry.check_all()
            system_metrics = await SystemHealthMonitor.get_system_metrics()
            system_info = await SystemHealthMonitor.get_system_info()
            
            healthy_count = sum(1 for c in all_checks["checks"] if c.get("status") == "healthy")
            total_count = all_checks["total"]
            
            overall_status = "healthy" if healthy_count == total_count else "degraded"
            
            return HealthStatus(
                status=overall_status,
                components={
                    "checks": all_checks["checks"],
                    "system_metrics": system_metrics,
                    "system_info": system_info,
                },
                uptime_seconds=0,  # Would need to track from startup
                version="1.0.0",
            )
        
        @app.get("/ping", tags=["Health"])
        async def ping():
            """Simple ping for load balancer checks."""
            return {"pong": True}
    
    async def _setup_health_checks(self):
        """Register health checks."""
        registry = self.health_registry
        
        # Only setup if not in test mode
        if self.settings.is_production():
            # Redis health check
            if self.settings.cache_enabled:
                registry.register_check(
                    name="redis",
                    check_func=lambda: check_redis(self.settings.redis_url),
                    critical=True,
                )
            
            # Database health check
            registry.register_check(
                name="database",
                check_func=lambda: check_database(self.settings.database_url),
                critical=True,
            )
            
            # Weaviate health check
            if self.settings.enable_rag:
                registry.register_check(
                    name="weaviate",
                    check_func=lambda: check_weaviate(self.settings.weaviate_url),
                    critical=False,
                )
        
        logger.info("health_checks_registered", count=len(registry.checks))
    
    @staticmethod
    def _get_openapi_tags() -> List[dict]:
        """Get OpenAPI tags for documentation."""
        return [
            {
                "name": "Health",
                "description": "Health checks and readiness probes",
            },
            {
                "name": "AI",
                "description": "AI inference and synthesis endpoints",
            },
            {
                "name": "Data",
                "description": "Data ingestion and processing",
            },
            {
                "name": "Analytics",
                "description": "Analytics and metrics",
            },
        ]


def create_app(
    settings: Optional[Settings] = None,
    setup_routes: Optional[Callable[[FastAPI], None]] = None,
) -> FastAPI:
    """
    Convenience function to create fully configured FastAPI app.
    
    Args:
        settings: Custom settings. If None, uses environment/defaults.
        setup_routes: Optional function to setup custom routes.
    
    Returns:
        Configured FastAPI application ready to run.
    
    Example:
        ```python
        from omni_one.infra.fastapi_factory import create_app
        
        app = create_app()
        
        # Or with custom routes:
        def setup_routes(app: FastAPI):
            @app.get("/custom")
            async def custom_endpoint():
                return {"message": "custom"}
        
        app = create_app(setup_routes=setup_routes)
        ```
    """
    if settings is None:
        settings = get_settings()
    
    factory = OmniOneAPIFactory(settings)
    return factory.create_app(setup_routes=setup_routes)


__all__ = [
    "OmniOneAPIFactory",
    "create_app",
]
