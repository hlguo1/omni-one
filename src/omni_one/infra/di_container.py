"""
Dependency Injection Container for Omni-One.

Provides centralized service management, lifecycle control, and dependency resolution
for enterprise-grade dependency injection and service locator patterns.
"""

from typing import Any, Callable, Dict, Optional, Type, TypeVar, Generic
from abc import ABC, abstractmethod
from enum import Enum
import inspect
from threading import RLock

from .exceptions import ServiceError, ErrorCode, ConfigurationError

T = TypeVar("T")


class Scope(str, Enum):
    """Service lifecycle scopes."""
    SINGLETON = "singleton"  # Single instance for entire application
    TRANSIENT = "transient"  # New instance every time
    REQUEST = "request"      # Single instance per request


class ServiceDescriptor(Generic[T]):
    """Descriptor for a registered service."""
    
    def __init__(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
        instance: Optional[T] = None,
        scope: Scope = Scope.SINGLETON,
        dependencies: Optional[Dict[str, Type]] = None,
    ):
        self.service_type = service_type
        self.factory = factory
        self.instance = instance
        self.scope = scope
        self.dependencies = dependencies or {}
    
    def is_singleton(self) -> bool:
        return self.scope == Scope.SINGLETON
    
    def is_transient(self) -> bool:
        return self.scope == Scope.TRANSIENT
    
    def is_request_scoped(self) -> bool:
        return self.scope == Scope.REQUEST


class IServiceProvider(ABC):
    """Interface for service provider."""
    
    @abstractmethod
    def get_service(self, service_type: Type[T]) -> T:
        """Resolve and return service instance."""
        pass
    
    @abstractmethod
    def try_get_service(self, service_type: Type[T]) -> Optional[T]:
        """Try to resolve service, return None if not found."""
        pass
    
    @abstractmethod
    def get_all_services(self, service_type: Type[T]) -> list[T]:
        """Get all registered instances of service type."""
        pass


class ServiceContainer(IServiceProvider):
    """Central dependency injection container."""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._multi_services: Dict[Type, list[ServiceDescriptor]] = {}
        self._lock = RLock()
        self._request_scope: Dict[Type, Any] = {}
    
    # ========================================================================
    # REGISTRATION METHODS
    # ========================================================================
    
    def register_singleton(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
        instance: Optional[T] = None,
    ) -> "ServiceContainer":
        """Register a singleton service (single instance for app lifetime)."""
        if instance is None and factory is None:
            factory = service_type
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            instance=instance,
            scope=Scope.SINGLETON,
        )
        
        with self._lock:
            self._services[service_type] = descriptor
        
        return self
    
    def register_transient(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
    ) -> "ServiceContainer":
        """Register a transient service (new instance every time)."""
        if factory is None:
            factory = service_type
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=Scope.TRANSIENT,
        )
        
        with self._lock:
            self._services[service_type] = descriptor
        
        return self
    
    def register_request_scoped(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
    ) -> "ServiceContainer":
        """Register a request-scoped service (single instance per request)."""
        if factory is None:
            factory = service_type
        
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            scope=Scope.REQUEST,
        )
        
        with self._lock:
            self._services[service_type] = descriptor
        
        return self
    
    def register_multi(
        self,
        service_type: Type[T],
        implementation_type: Type[T],
    ) -> "ServiceContainer":
        """Register multiple implementations for same interface."""
        if service_type not in self._multi_services:
            self._multi_services[service_type] = []
        
        descriptor = ServiceDescriptor(
            service_type=implementation_type,
            factory=implementation_type,
            scope=Scope.SINGLETON,
        )
        
        with self._lock:
            self._multi_services[service_type].append(descriptor)
        
        return self
    
    # ========================================================================
    # RESOLUTION METHODS
    # ========================================================================
    
    def get_service(self, service_type: Type[T]) -> T:
        """Resolve and return service instance."""
        service = self.try_get_service(service_type)
        if service is None:
            raise ServiceError(
                message=f"Service not registered: {service_type.__name__}",
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            )
        return service
    
    def try_get_service(self, service_type: Type[T]) -> Optional[T]:
        """Try to resolve service, return None if not found."""
        with self._lock:
            if service_type not in self._services:
                return None
            
            descriptor = self._services[service_type]
        
        # Handle different scopes
        if descriptor.is_singleton():
            if descriptor.instance is None:
                descriptor.instance = self._create_instance(descriptor)
            return descriptor.instance
        
        elif descriptor.is_request_scoped():
            # Check request-scoped cache
            if service_type in self._request_scope:
                return self._request_scope[service_type]
            
            instance = self._create_instance(descriptor)
            self._request_scope[service_type] = instance
            return instance
        
        else:  # Transient
            return self._create_instance(descriptor)
    
    def get_all_services(self, service_type: Type[T]) -> list[T]:
        """Get all registered implementations of service type."""
        with self._lock:
            if service_type not in self._multi_services:
                return []
            
            descriptors = self._multi_services[service_type]
        
        return [self._create_instance(d) for d in descriptors]
    
    # ========================================================================
    # PRIVATE METHODS
    # ========================================================================
    
    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create service instance with automatic dependency resolution."""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory is None:
            raise ServiceError(
                message=f"Cannot create instance of {descriptor.service_type.__name__}",
                code=ErrorCode.CONFIGURATION_ERROR,
            )
        
        # Get constructor parameters
        try:
            sig = inspect.signature(descriptor.factory)
            kwargs = {}
            
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                
                # Try to resolve from type annotation
                if param.annotation != inspect.Parameter.empty:
                    param_type = param.annotation
                    resolved = self.try_get_service(param_type)
                    if resolved is not None:
                        kwargs[param_name] = resolved
                    elif param.default == inspect.Parameter.empty:
                        raise ServiceError(
                            message=f"Cannot resolve dependency {param_name}: {param_type.__name__}",
                            code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                        )
            
            return descriptor.factory(**kwargs)
        
        except Exception as e:
            if isinstance(e, ServiceError):
                raise
            raise ServiceError(
                message=f"Failed to create instance of {descriptor.service_type.__name__}: {str(e)}",
                code=ErrorCode.CONFIGURATION_ERROR,
            )
    
    def clear_request_scope(self):
        """Clear request-scoped instances (call at end of request)."""
        with self._lock:
            self._request_scope.clear()
    
    # ========================================================================
    # INTROSPECTION
    # ========================================================================
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if service is registered."""
        with self._lock:
            return service_type in self._services
    
    def get_registered_services(self) -> list[Type]:
        """Get list of all registered service types."""
        with self._lock:
            return list(self._services.keys())
    
    def get_service_info(self, service_type: Type) -> Optional[Dict[str, Any]]:
        """Get information about registered service."""
        with self._lock:
            if service_type not in self._services:
                return None
            
            descriptor = self._services[service_type]
            return {
                "type": descriptor.service_type.__name__,
                "scope": descriptor.scope.value,
                "is_singleton": descriptor.is_singleton(),
                "has_instance": descriptor.instance is not None,
            }


# Global container instance
_container: Optional[ServiceContainer] = None
_container_lock = RLock()


def get_container() -> ServiceContainer:
    """Get or create global service container."""
    global _container
    
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = ServiceContainer()
    
    return _container


def configure_container(setup_func: Callable[[ServiceContainer], None]) -> ServiceContainer:
    """Configure the global service container."""
    container = get_container()
    setup_func(container)
    return container


def reset_container():
    """Reset the global container (for testing)."""
    global _container
    with _container_lock:
        _container = None


__all__ = [
    "ServiceContainer",
    "ServiceDescriptor",
    "IServiceProvider",
    "Scope",
    "get_container",
    "configure_container",
    "reset_container",
]
