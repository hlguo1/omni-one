"""
Industry-grade type definitions and data models for Omni-One.

Uses Pydantic v2 for runtime validation, serialization, and OpenAPI compatibility.
Provides comprehensive type safety across the platform.
"""

from typing import Any, Optional, Dict, List, Union, Literal
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel, Field, ConfigDict, field_validator,
    field_serializer, ValidationError as PydanticValidationError
)


# ============================================================================
# ENUMS
# ============================================================================

class TaskType(str, Enum):
    """Supported task types for AI inference."""
    GENERAL_QA = "general_qa"
    SYNTHESIS = "synthesis"
    ANALYSIS = "analysis"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    ANOMALY_DETECTION = "anomaly_detection"


class UserTier(str, Enum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class ModelQuality(str, Enum):
    """Model quality/capability levels."""
    FAST = "fast"
    BALANCED = "balanced"
    PREMIUM = "premium"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProcessingMode(str, Enum):
    """Data processing pipeline stages."""
    LAYER_1_INGESTION = "layer_1_ingestion"
    LAYER_2_STATISTICAL = "layer_2_statistical"
    LAYER_3_ML_FEATURES = "layer_3_ml_features"
    LAYER_4_LLM_SYNTHESIS = "layer_4_llm_synthesis"


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AIRequest(BaseModel):
    """Unified AI inference request model."""
    
    model_config = ConfigDict(
        json_schema_extra={"example": {
            "query": "Analyze customer churn risk",
            "context": ["Q3 revenue: $2.5M"],
            "task_type": "analysis",
            "user_tier": "enterprise",
            "require_rag": True,
            "temperature": 0.7,
            "max_tokens": 1024
        }}
    )
    
    request_id: UUID = Field(default_factory=uuid4, description="Unique request identifier")
    query: str = Field(..., min_length=1, max_length=4096, description="User query or prompt")
    context: List[str] = Field(
        default_factory=list,
        max_length=100,
        description="Contextual information for the query"
    )
    user_id: Optional[str] = Field(None, description="User identifier")
    user_tier: UserTier = Field(default=UserTier.FREE, description="User subscription tier")
    task_type: TaskType = Field(default=TaskType.GENERAL_QA, description="Type of task")
    require_rag: bool = Field(default=True, description="Whether to use RAG for context")
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature parameter for generation"
    )
    max_tokens: int = Field(
        default=1024,
        ge=100,
        le=4096,
        description="Maximum tokens to generate"
    )
    model_preference: Optional[ModelQuality] = Field(None, description="Preferred model quality")
    include_reasoning: bool = Field(default=False, description="Include reasoning chain in response")
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        return v.strip()
    
    @field_validator("context")
    @classmethod
    def validate_context(cls, v: List[str]) -> List[str]:
        return [item.strip() for item in v if item.strip()]


class ModelSelection(BaseModel):
    """Model selection decision with fallback chain."""
    
    primary_model: str = Field(..., description="Primary selected model")
    fallback_chain: List[str] = Field(
        default_factory=list,
        description="Fallback models in order of preference"
    )
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost in USD")
    estimated_latency_ms: int = Field(..., ge=0, description="Estimated latency in milliseconds")
    confidence_score: float = Field(ge=0, le=1, description="Confidence score of selection")
    routing_decision_reason: str = Field(description="Why this model was selected")
    ml_routed: bool = Field(default=False, description="Whether ML-based routing was used")


class AIResponse(BaseModel):
    """Unified AI inference response model."""
    
    request_id: UUID = Field(..., description="Correlates to request ID")
    response: str = Field(..., description="Generated response text")
    model_used: str = Field(..., description="Model that generated the response")
    quality_score: float = Field(ge=0, le=1, description="Quality assessment score")
    cached: bool = Field(default=False, description="Whether response was cached")
    latency_ms: int = Field(..., ge=0, description="Round-trip latency")
    reasoning_chain: Optional[List[str]] = Field(None, description="Chain of thought if included")
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Citations for RAG-sourced information"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional response metadata"
    )
    
    @field_serializer("request_id")
    def serialize_request_id(self, value: UUID) -> str:
        return str(value)


class QAValidationResult(BaseModel):
    """Quality assurance validation result."""
    
    quality_score: float = Field(ge=0, le=1, description="Quality score")
    is_hallucination: bool = Field(description="Whether response contains hallucinations")
    confidence_level: float = Field(ge=0, le=1, description="Confidence in validation")
    issues: List[str] = Field(default_factory=list, description="Detected quality issues")
    recommendations: List[str] = Field(default_factory=list, description="Improvement suggestions")


class CacheEntry(BaseModel):
    """Semantic cache entry."""
    
    cache_key: str = Field(..., description="Unique cache key")
    query: str = Field(..., description="Original query")
    context: str = Field(..., description="Context used for query")
    response: str = Field(..., description="Cached response")
    model: str = Field(..., description="Model that generated response")
    similarity_score: float = Field(ge=0, le=1, description="Semantic similarity score")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: Optional[int] = Field(None, description="Time to live in seconds")
    cost_usd: float = Field(default=0.0, description="Cost of generation")


# ============================================================================
# DOMAIN MODELS
# ============================================================================

class Document(BaseModel):
    """Knowledge base document for RAG."""
    
    doc_id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., description="Document content")
    source: str = Field(..., description="Document source")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding: Optional[List[float]] = Field(None, description="Embedding vector")


class AnomalyAlert(BaseModel):
    """Anomaly detection alert."""
    
    alert_id: UUID = Field(default_factory=uuid4)
    entity_id: str = Field(..., description="Entity with anomaly")
    anomaly_type: str = Field(..., description="Type of anomaly detected")
    severity: AnomalySeverity = Field(..., description="Alert severity level")
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)
    recommended_actions: List[str] = Field(default_factory=list)
    
    @field_serializer("alert_id")
    def serialize_alert_id(self, value: UUID) -> str:
        return str(value)


class EvidenceStep(BaseModel):
    """Single step in an evidence chain (auditable, cited)."""
    layer: str = Field(description="Layer 1-4 id, e.g., layer_1_ingestion")
    signal: str = Field(description="Machine-readable signal, e.g., z_score=4.2")
    citation: str = Field(description="Human-readable citation, e.g., 'Layer 2: z_score 4.2 vs mean 95000'")
    raw: Dict[str, Any] = Field(default_factory=dict, description="Raw metrics for replay")
    cost_usd: float = Field(default=0.0, ge=0, description="Cost incurred at this step")
    latency_ms: float = Field(default=0.0, ge=0, description="Latency for this step")

class EvidenceBundle(BaseModel):
    """Full chain of evidence for a record — every insight is citeable."""
    record_id: str
    steps: List[EvidenceStep] = Field(default_factory=list)
    final_decision: str = Field(description="Why we stopped: ingestion_error, statistical, ml_feature, llm_required")
    llm_bypassed: bool
    total_cost_usd: float = Field(default=0.0, ge=0)
    total_latency_ms: float = Field(default=0.0, ge=0)
    citations: List[str] = Field(default_factory=list, description="All citations flattened for rendering")

    def add_step(self, step: EvidenceStep):
        self.steps.append(step)
        self.citations.append(step.citation)
        self.total_cost_usd += step.cost_usd
        self.total_latency_ms += step.latency_ms


class CostLedgerEntry(BaseModel):
    """Per-record cost accounting."""
    record_id: str
    model_used: Optional[str] = None
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    cost_usd: float = Field(ge=0, default=0.0)
    cached: bool = False
    budget_usd: Optional[float] = None
    budget_exceeded: bool = False


class ProcessingMetrics(BaseModel):
    """Pipeline processing metrics."""
    
    total_records: int = Field(ge=0)
    successfully_processed: int = Field(ge=0)
    failed_records: int = Field(ge=0)
    llm_bypass_rate: float = Field(ge=0, le=1)
    average_processing_time_ms: float = Field(ge=0)
    layer_1_time_ms: Optional[float] = None
    layer_2_time_ms: Optional[float] = None
    layer_3_time_ms: Optional[float] = None
    layer_4_time_ms: Optional[float] = None
    total_cost_usd: float = Field(ge=0)
    # New in STRATEGY.md Phase 1
    evidence_bundles_produced: int = Field(default=0, ge=0, description="Number of evidence bundles emitted")
    avg_evidence_steps: float = Field(default=0.0, ge=0, description="Avg steps per bundle")


class HealthStatus(BaseModel):
    """System health status."""
    
    status: Literal["healthy", "degraded", "unhealthy"] = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual component health"
    )
    uptime_seconds: float = Field(ge=0)
    version: str = Field(...)
    
    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.isoformat()


# ============================================================================
# CONFIGURATION MODELS
# ============================================================================

class RedisConfig(BaseModel):
    """Redis connection configuration."""
    
    url: str = Field(default="redis://localhost:6379")
    max_connections: int = Field(default=50, ge=1)
    socket_timeout: int = Field(default=5, ge=1)
    retry_on_timeout: bool = Field(default=True)


class ModelConfig(BaseModel):
    """Individual model configuration."""
    
    name: str = Field(...)
    provider: str = Field(...)
    cost_per_mtok: float = Field(ge=0)
    latency_p95_ms: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=1)
    max_context_tokens: int = Field(ge=100)
    is_default: bool = Field(default=False)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""
    
    enabled: bool = Field(default=True)
    requests_per_window: int = Field(default=100, ge=1)
    window_size_seconds: int = Field(default=3600, ge=1)
    burst_allowance: int = Field(default=10, ge=1)
