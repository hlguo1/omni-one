"""
Production-grade configuration management.

Uses Pydantic v2 for validation, environment variable binding, and development/production
environment differentiation.
"""

import os
from pathlib import Path
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Main application settings with Pydantic v2."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )
    
    # ========================================================================
    # ENVIRONMENT & DEPLOYMENT
    # ========================================================================
    
    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # ========================================================================
    # SERVER CONFIGURATION
    # ========================================================================
    
    host: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    port: int = Field(
        default=5003,
        ge=1,
        le=65535,
        description="Server port"
    )
    workers: int = Field(
        default=4,
        ge=1,
        description="Number of Gunicorn workers"
    )
    worker_timeout: int = Field(
        default=120,
        ge=30,
        description="Worker timeout in seconds"
    )
    
    # ========================================================================
    # SECURITY
    # ========================================================================
    
    secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Flask secret key for sessions"
    )
    api_keys: List[str] = Field(
        default_factory=lambda: ["demo-key", "test-key"],
        description="Valid API keys for authentication"
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5003"],
        description="Allowed CORS origins"
    )
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        if info.data.get("environment") == Environment.PRODUCTION:
            if v == "dev-secret-key-change-in-production":
                raise ValueError("Secret key must be changed in production")
            if len(v) < 32:
                raise ValueError("Secret key must be at least 32 characters in production")
        return v

    @field_validator("api_keys")
    @classmethod
    def validate_api_keys(cls, v: list, info) -> list:
        # Fail closed in prod: demo/test keys must not survive
        if info.data.get("environment") == Environment.PRODUCTION:
            bad = {"demo-key", "test-key"}
            if any(str(k).strip() in bad for k in (v or [])):
                raise ValueError("Remove demo-key/test-key from VALID_API_KEYS in production")
            if not v:
                raise ValueError("VALID_API_KEYS must be set in production")
        return v
    
    # ========================================================================
    # RATE LIMITING
    # ========================================================================
    
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    rate_limit_requests: int = Field(
        default=100,
        ge=1,
        description="Number of requests per window"
    )
    rate_limit_window: int = Field(
        default=3600,
        ge=1,
        description="Rate limit window in seconds"
    )
    rate_limit_burst: int = Field(
        default=10,
        ge=1,
        description="Burst allowance for rate limiting"
    )
    
    # ========================================================================
    # AI MODEL CONFIGURATION
    # ========================================================================
    
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key"
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic Claude API key"
    )
    
    default_model: str = Field(
        default="gemini-2.5-flash-preview-05-20",
        description="Default LLM model"
    )

    # Seller OS free-first LLM policy: mock by default, never paid unless explicit
    seller_llm: str = Field(
        default="mock",
        description="Seller LLM mode: mock (default $0) | ollama | google. Paid only if explicitly set + key present."
    )
    seller_max_llm_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Per-briefing LLM budget cap in USD. 0.0 = $0 mock only."
    )
    briefing_cache_ttl_s: int = Field(
        default=3600,
        ge=60,
        description="Seller briefing cache TTL in seconds (DuckDB/JSON)."
    )
    max_upload_mb: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Max photo upload size in MB."
    )
    
    # Model inference configuration
    request_timeout: int = Field(
        default=300,
        ge=30,
        description="Request timeout in seconds"
    )
    max_concurrent_requests: int = Field(
        default=50,
        ge=1,
        description="Maximum concurrent requests"
    )
    max_tokens: int = Field(
        default=1024,
        ge=100,
        le=4096,
        description="Maximum tokens for generation"
    )
    default_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Default temperature for generation"
    )
    
    # ========================================================================
    # CACHE CONFIGURATION
    # ========================================================================
    
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(
        default=50,
        ge=1,
        description="Maximum Redis connections"
    )
    cache_ttl: int = Field(
        default=3600,
        ge=60,
        description="Cache time-to-live in seconds"
    )
    cache_enabled: bool = Field(
        default=True,
        description="Enable semantic caching"
    )
    
    # ========================================================================
    # DATABASE CONFIGURATION
    # ========================================================================
    
    database_url: str = Field(
        default="postgresql://user:pass@localhost:5432/omni_one",
        description="PostgreSQL database URL"
    )
    # Local-first persistence ($0): DuckDB file + JSONL audit + inbox root
    duckdb_path: str = Field(
        default="./data/omni.duckdb",
        description="Local DuckDB file path (free, no server)."
    )
    audit_path: str = Field(
        default="./data/audit.jsonl",
        description="Append-only audit JSONL path."
    )
    allowed_root: str = Field(
        default="./data/inbox",
        description="Only allowed folder root for seller briefing uploads (path-traversal guard)."
    )
    database_min_connections: int = Field(
        default=5,
        ge=1,
        description="Minimum database connections"
    )
    database_max_connections: int = Field(
        default=20,
        ge=5,
        description="Maximum database connections"
    )
    
    # ========================================================================
    # VECTOR DATABASE (WEAVIATE/PINECONE)
    # ========================================================================
    
    weaviate_url: str = Field(
        default="http://localhost:8080",
        description="Weaviate endpoint"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence Transformer model for embeddings"
    )
    
    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================
    
    enable_rag: bool = Field(
        default=True,
        description="Enable Retrieval-Augmented Generation"
    )
    enable_cache: bool = Field(
        default=True,
        description="Enable semantic caching"
    )
    enable_proactive_agents: bool = Field(
        default=True,
        description="Enable proactive anomaly detection"
    )
    enable_ethical_ai: bool = Field(
        default=True,
        description="Enable ethical AI governance"
    )
    enable_federated_learning: bool = Field(
        default=True,
        description="Enable federated learning"
    )
    enable_quantum_optimization: bool = Field(
        default=True,
        description="Enable quantum-inspired optimization"
    )
    enable_monitoring: bool = Field(
        default=True,
        description="Enable Prometheus monitoring"
    )
    enable_api_gateway: bool = Field(
        default=True,
        description="Enable API gateway"
    )
    enable_worker_system: bool = Field(
        default=True,
        description="Enable worker pool system"
    )
    
    # ========================================================================
    # INTEGRATIONS
    # ========================================================================
    
    slack_webhook_url: Optional[str] = Field(
        default=None,
        description="Slack webhook for alerts"
    )
    slack_bot_token: Optional[str] = Field(
        default=None,
        description="Slack bot token"
    )
    
    # ========================================================================
    # MONITORING & OBSERVABILITY
    # ========================================================================
    
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level"
    )
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry error tracking DSN"
    )
    datadog_api_key: Optional[str] = Field(
        default=None,
        description="Datadog API key"
    )
    enable_structured_logging: bool = Field(
        default=True,
        description="Enable structured logging with structlog"
    )
    
    # ========================================================================
    # PATHS
    # ========================================================================
    
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent,
        description="Base directory of the project"
    )
    logs_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "logs",
        description="Logs directory"
    )
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "data",
        description="Data directory"
    )
    models_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "models",
        description="Models directory"
    )
    
    @field_validator("logs_dir", "data_dir", "models_dir", mode="after")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        """Create directories if they don't exist."""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    # ========================================================================
    # VALIDATION & COMPUTED PROPERTIES
    # ========================================================================
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT
    
    def get_model_url(self) -> str:
        """Get the model endpoint URL."""
        if "gemini" in self.default_model.lower():
            return "https://generativelanguage.googleapis.com/v1beta/models"
        elif "claude" in self.default_model.lower():
            return "https://api.anthropic.com/v1"
        else:
            return "https://api.openai.com/v1"


# Global settings instance
def get_settings() -> Settings:
    """Get application settings (singleton pattern)."""
    return Settings()


# Default settings for backwards compatibility
settings = get_settings()


__all__ = ["Settings", "Environment", "LogLevel", "get_settings", "settings"]
