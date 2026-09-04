"""Compat shim — infra.settings. Tries core.settings, else minimal fallback without pydantic_settings."""
try:
    from ..core.settings import Settings, Environment, LogLevel, get_settings, settings  # type: ignore
except Exception as _e1:
    try:
        from core.settings import Settings, Environment, LogLevel, get_settings, settings  # type: ignore
    except Exception as _e2:
        # Minimal fallback Settings (no pydantic_settings needed)
        from enum import Enum
        class Environment(str, Enum):
            DEVELOPMENT = "development"
            STAGING = "staging"
            PRODUCTION = "production"
        class LogLevel(str, Enum):
            DEBUG = "DEBUG"; INFO = "INFO"; WARNING = "WARNING"; ERROR = "ERROR"; CRITICAL = "CRITICAL"
        class Settings:
            def __init__(self):
                import os
                self.environment = Environment(os.getenv("ENVIRONMENT", "development"))
                self.debug = os.getenv("DEBUG", "false").lower() == "true"
                self.host = os.getenv("HOST", "0.0.0.0")
                self.port = int(os.getenv("PORT", "5003"))
                self.log_level = LogLevel(os.getenv("LOG_LEVEL", "INFO"))
                self.allowed_origins = ["http://localhost:3000", "http://localhost:5003"]
                self.api_keys = [k.strip() for k in os.getenv("VALID_API_KEYS", "demo-key,test-key").split(",") if k.strip()]
                # Fail closed in prod (no demo keys)
                if self.environment == Environment.PRODUCTION:
                    bad = {"demo-key", "test-key"}
                    if any(k in bad for k in self.api_keys):
                        raise ValueError("Remove demo-key/test-key from VALID_API_KEYS in production")
                    if not self.api_keys:
                        raise ValueError("VALID_API_KEYS must be set in production")
                self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                self.database_url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/omni_one")
                self.weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
                self.cache_enabled = os.getenv("ENABLE_CACHE", "true").lower() == "true"
                self.enable_rag = os.getenv("ENABLE_RAG", "true").lower() == "true"
                self.enable_proactive_agents = True
            def is_production(self): return self.environment == Environment.PRODUCTION
            def is_development(self): return self.environment == Environment.DEVELOPMENT
        _settings_instance = None
        def get_settings():
            global _settings_instance
            if _settings_instance is None:
                _settings_instance = Settings()
            return _settings_instance
        settings = get_settings()
