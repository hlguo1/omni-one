"""
Layer 1: Fast Data Ingestion & Validation
==========================================

Handles real-time data ingestion with deterministic, sub-millisecond validation.
Performs schema normalization, deduplication, and quality checks.

For high-velocity time series data (1000s events/sec), this layer must be
extremely fast and efficient.
"""

import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error."""
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "warning"  # "warning" or "error"


@dataclass
class IngestionMetrics:
    """Tracks ingestion performance metrics."""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicates_detected: int = 0
    errors: List[ValidationError] = field(default_factory=list)
    ingestion_time_ms: float = 0.0
    validation_time_ms: float = 0.0
    dedup_time_ms: float = 0.0


class DataSchema:
    """Defines the schema for normalized data."""
    
    # Required fields for all data
    REQUIRED_FIELDS = {"timestamp", "source", "entity_id"}
    
    # Data types
    ALLOWED_TYPES = {
        "timestamp": (str, int, float),
        "source": str,
        "entity_id": str,
        "value": (str, int, float, list, dict),
        "metadata": dict,
        "tags": (list, dict)
    }
    
    @staticmethod
    def validate_field(field_name: str, value: Any, field_type) -> Optional[ValidationError]:
        """Validate a single field."""
        if not isinstance(value, field_type):
            return ValidationError(
                code="TYPE_MISMATCH",
                message=f"Field '{field_name}' has wrong type. Expected {field_type}, got {type(value).__name__}",
                field=field_name,
                severity="error"
            )
        return None


class DuplicateDetector:
    """Fast deduplication using rolling hash and TTL."""
    
    def __init__(self, max_cache_size: int = 10000, ttl_seconds: int = 300):
        self.max_cache_size = max_cache_size
        self.ttl_seconds = ttl_seconds
        self.seen_hashes: Dict[str, datetime] = {}
    
    def compute_hash(self, record: Dict[str, Any]) -> str:
        """Compute deterministic hash of record."""
        # Create a canonical representation
        canonical = json.dumps(
            {
                "timestamp": record.get("timestamp"),
                "source": record.get("source"),
                "entity_id": record.get("entity_id"),
                "value": record.get("value")
            },
            sort_keys=True,
            default=str
        )
        return hashlib.md5(canonical.encode()).hexdigest()
    
    def is_duplicate(self, record: Dict[str, Any]) -> bool:
        """Check if record is a duplicate (O(1) lookup)."""
        record_hash = self.compute_hash(record)
        now = datetime.now()
        
        # Clean up expired entries
        self._cleanup_expired()
        
        if record_hash in self.seen_hashes:
            return True
        
        # Add to seen hashes
        if len(self.seen_hashes) >= self.max_cache_size:
            # Remove oldest entry
            oldest_key = min(self.seen_hashes, key=self.seen_hashes.get)
            del self.seen_hashes[oldest_key]
        
        self.seen_hashes[record_hash] = now
        return False
    
    def _cleanup_expired(self):
        """Remove entries older than TTL."""
        now = datetime.now()
        expired_keys = [
            k for k, v in self.seen_hashes.items()
            if (now - v).total_seconds() > self.ttl_seconds
        ]
        for k in expired_keys:
            del self.seen_hashes[k]


class Layer1Ingestion:
    """
    Layer 1: Fast Data Ingestion & Validation
    
    Responsibilities:
    - Schema validation
    - Data normalization
    - Deduplication  
    - Quality checks
    - Metrics collection
    
    Target: <1ms per record
    """
    
    def __init__(self):
        self.duplicate_detector = DuplicateDetector()
        self.metrics = IngestionMetrics()
        self.logger = logging.getLogger(f"{__name__}.Layer1")
    
    def normalize_timestamp(self, timestamp: Any) -> datetime:
        """Convert various timestamp formats to datetime."""
        if isinstance(timestamp, datetime):
            return timestamp
        elif isinstance(timestamp, (int, float)):
            # Assume Unix timestamp
            return datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            # Try common formats
            for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(timestamp, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Cannot parse timestamp: {timestamp}")
        else:
            raise ValueError(f"Unknown timestamp type: {type(timestamp)}")
    
    def normalize_record(self, record: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[ValidationError]]:
        """
        Normalize a record to standard format.
        
        Returns:
            (normalized_record, errors)
        """
        errors = []
        normalized = {}
        
        # Check required fields
        for required_field in DataSchema.REQUIRED_FIELDS:
            if required_field not in record:
                errors.append(ValidationError(
                    code="MISSING_FIELD",
                    message=f"Missing required field: {required_field}",
                    field=required_field,
                    severity="error"
                ))
                return None, errors
        
        # Normalize timestamp
        try:
            normalized["timestamp"] = self.normalize_timestamp(record["timestamp"])
        except Exception as e:
            errors.append(ValidationError(
                code="INVALID_TIMESTAMP",
                message=f"Cannot parse timestamp: {str(e)}",
                field="timestamp",
                severity="error"
            ))
            return None, errors
        
        # Copy and validate other fields
        normalized["source"] = str(record.get("source", "")).strip()
        normalized["entity_id"] = str(record.get("entity_id", "")).strip()
        normalized["value"] = record.get("value")
        normalized["metadata"] = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
        normalized["tags"] = record.get("tags", [])
        
        # Validate required field formats
        if not normalized["source"]:
            errors.append(ValidationError(
                code="EMPTY_SOURCE",
                message="Source cannot be empty",
                field="source",
                severity="error"
            ))
            return None, errors
        
        if not normalized["entity_id"]:
            errors.append(ValidationError(
                code="EMPTY_ENTITY_ID",
                message="Entity ID cannot be empty",
                field="entity_id",
                severity="error"
            ))
            return None, errors
        
        # Add ingestion timestamp
        normalized["_ingested_at"] = datetime.now()
        
        return normalized, errors
    
    def ingest_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], IngestionMetrics]:
        """
        Ingest and validate a batch of records (deterministic, fast).
        
        Returns:
            (valid_records, metrics)
        """
        import time
        start_time = time.time()
        
        valid_records = []
        errors = []
        duplicates = 0
        
        for record in records:
            # Normalize
            normalized, validation_errors = self.normalize_record(record)
            
            if validation_errors:
                errors.extend(validation_errors)
                self.metrics.invalid_records += 1
                continue
            
            # Check for duplicates
            if self.duplicate_detector.is_duplicate(normalized):
                duplicates += 1
                self.metrics.duplicates_detected += 1
                continue
            
            valid_records.append(normalized)
            self.metrics.valid_records += 1
        
        # Collect metrics
        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.total_records += len(records)
        self.metrics.invalid_records += len(errors)
        self.metrics.ingestion_time_ms = elapsed_ms
        self.metrics.errors = errors
        
        return valid_records, self.metrics


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test data
    test_records = [
        {
            "timestamp": datetime.now().isoformat(),
            "source": "salesforce",
            "entity_id": "account_123",
            "value": 95000,
            "metadata": {"currency": "USD", "type": "MRR"}
        },
        {
            "timestamp": int(datetime.now().timestamp()),
            "source": "slack",
            "entity_id": "user_456",
            "value": "Sentiment: positive",
            "tags": ["sentiment", "social"]
        },
        {
            # Duplicate of first
            "timestamp": datetime.now().isoformat(),
            "source": "salesforce",
            "entity_id": "account_123",
            "value": 95000,
            "metadata": {"currency": "USD", "type": "MRR"}
        }
    ]
    
    layer1 = Layer1Ingestion()
    valid, metrics = layer1.ingest_batch(test_records)
    
    print(f"Valid records: {metrics.valid_records}")
    print(f"Invalid records: {metrics.invalid_records}")
    print(f"Duplicates: {metrics.duplicates_detected}")
    print(f"Ingestion time: {metrics.ingestion_time_ms:.2f}ms")
