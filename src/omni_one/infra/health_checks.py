"""
Health checks and readiness probes for production deployment.

Provides comprehensive health status monitoring for Kubernetes liveness/readiness probes
and system health dashboard.
"""

from typing import Any, Dict, Optional, Callable, Coroutine
from datetime import datetime
from enum import Enum
import asyncio
import platform
import psutil

from .exceptions import ServiceError
from .logging_config import get_logger

logger = get_logger(__name__)


class ComponentStatus(str, Enum):
    """Health status of a component."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Individual health check."""
    
    def __init__(
        self,
        name: str,
        check_func: Callable[[], Coroutine[Any, Any, bool]],
        timeout_seconds: float = 5.0,
        critical: bool = False,
    ):
        self.name = name
        self.check_func = check_func
        self.timeout_seconds = timeout_seconds
        self.critical = critical
        self.last_status: Optional[bool] = None
        self.last_check: Optional[datetime] = None
        self.error_message: Optional[str] = None
    
    async def run(self) -> Dict[str, Any]:
        """Run the health check."""
        try:
            result = await asyncio.wait_for(
                self.check_func(),
                timeout=self.timeout_seconds
            )
            
            self.last_status = result
            self.last_check = datetime.utcnow()
            self.error_message = None
            
            return {
                "name": self.name,
                "status": "healthy" if result else "unhealthy",
                "critical": self.critical,
                "timestamp": self.last_check.isoformat(),
            }
        
        except asyncio.TimeoutError:
            self.last_status = False
            self.last_check = datetime.utcnow()
            self.error_message = f"Health check timed out after {self.timeout_seconds}s"
            
            return {
                "name": self.name,
                "status": "unhealthy",
                "critical": self.critical,
                "error": self.error_message,
                "timestamp": self.last_check.isoformat(),
            }
        
        except Exception as e:
            self.last_status = False
            self.last_check = datetime.utcnow()
            self.error_message = str(e)
            
            logger.error(
                "health_check_exception",
                check_name=self.name,
                exception=e,
            )
            
            return {
                "name": self.name,
                "status": "unhealthy",
                "critical": self.critical,
                "error": self.error_message,
                "timestamp": self.last_check.isoformat(),
            }


class SystemHealthMonitor:
    """Monitor system-level health metrics."""
    
    @staticmethod
    async def get_system_metrics() -> Dict[str, Any]:
        """Get system-level metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_mb": round(memory.available / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_mb": round(disk.free / 1024 / 1024, 2),
                "process_count": len(psutil.pids()),
            }
        except Exception as e:
            logger.error("system_metrics_error", exception=e)
            return {"error": str(e)}
    
    @staticmethod
    async def get_system_info() -> Dict[str, Any]:
        """Get system information."""
        return {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }


class HealthCheckRegistry:
    """Registry for health checks."""
    
    def __init__(self):
        self.checks: Dict[str, HealthCheck] = {}
        self.last_full_check: Optional[datetime] = None
    
    def register(self, health_check: HealthCheck) -> None:
        """Register a health check."""
        self.checks[health_check.name] = health_check
        logger.info("health_check_registered", check_name=health_check.name)
    
    def register_check(
        self,
        name: str,
        check_func: Callable[[], Coroutine[Any, Any, bool]],
        timeout_seconds: float = 5.0,
        critical: bool = False,
    ) -> None:
        """Register a new health check."""
        check = HealthCheck(
            name=name,
            check_func=check_func,
            timeout_seconds=timeout_seconds,
            critical=critical,
        )
        self.register(check)
    
    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks concurrently."""
        results = await asyncio.gather(*[check.run() for check in self.checks.values()])
        
        self.last_full_check = datetime.utcnow()
        
        return {
            "checks": results,
            "timestamp": self.last_full_check.isoformat(),
            "total": len(results),
            "healthy": sum(1 for r in results if r.get("status") == "healthy"),
            "unhealthy": sum(1 for r in results if r.get("status") == "unhealthy"),
        }
    
    async def check_critical(self) -> bool:
        """Check only critical health checks."""
        critical_checks = [c for c in self.checks.values() if c.critical]
        
        if not critical_checks:
            return True
        
        results = await asyncio.gather(*[check.run() for check in critical_checks])
        return all(r.get("status") == "healthy" for r in results)
    
    def get_summary(self) -> str:
        """Get human-readable health summary."""
        if not self.checks:
            return "No health checks registered"
        
        healthy = sum(1 for c in self.checks.values() if c.last_status)
        total = len(self.checks)
        
        return f"{healthy}/{total} checks healthy"


# Global registry
_health_registry: Optional[HealthCheckRegistry] = None


def get_health_registry() -> HealthCheckRegistry:
    """Get or create global health check registry."""
    global _health_registry
    
    if _health_registry is None:
        _health_registry = HealthCheckRegistry()
    
    return _health_registry


# ============================================================================
# COMMON HEALTH CHECKS
# ============================================================================

async def check_redis(redis_url: str, timeout: float = 2.0) -> bool:
    """Check Redis connectivity."""
    try:
        import redis.asyncio as redis
        r = await redis.from_url(redis_url)
        await asyncio.wait_for(r.ping(), timeout=timeout)
        await r.close()
        return True
    except Exception as e:
        logger.warning("redis_health_check_failed", error=str(e))
        return False


async def check_database(connection_string: str, timeout: float = 2.0) -> bool:
    """Check database connectivity."""
    try:
        import asyncpg
        conn = await asyncio.wait_for(
            asyncpg.connect(connection_string),
            timeout=timeout
        )
        await conn.close()
        return True
    except Exception as e:
        logger.warning("database_health_check_failed", error=str(e))
        return False


async def check_weaviate(weaviate_url: str, timeout: float = 2.0) -> bool:
    """Check Weaviate connectivity."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{weaviate_url}/.well-known/live",
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                return response.status == 200
    except Exception as e:
        logger.warning("weaviate_health_check_failed", error=str(e))
        return False


async def check_external_api(url: str, timeout: float = 3.0) -> bool:
    """Check external API connectivity."""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.head(
                url,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                return response.status < 500
    except Exception as e:
        logger.warning("external_api_health_check_failed", error=str(e))
        return False


__all__ = [
    "ComponentStatus",
    "HealthCheck",
    "HealthCheckRegistry",
    "SystemHealthMonitor",
    "get_health_registry",
    "check_redis",
    "check_database",
    "check_weaviate",
    "check_external_api",
]
