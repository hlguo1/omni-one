"""
Data Pipeline Orchestration System
==================================

Enterprise-grade data processing pipelines with ETL orchestration,
streaming data processing, and complex data workflows.
"""

import os
import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Any, Iterator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import uuid
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import redis
from kafka import KafkaProducer, KafkaConsumer  # Assuming Kafka is available
import asyncio
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PipelineStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class DataFormat(Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    AVRO = "avro"
    PROTOBUF = "protobuf"

@dataclass
class DataSource:
    """Represents a data source in the pipeline."""
    source_id: str
    source_type: str  # "database", "api", "file", "stream"
    connection_config: Dict[str, Any]
    schema: Dict[str, Any] = field(default_factory=dict)
    batch_size: int = 1000
    polling_interval: int = 60  # seconds

@dataclass
class DataSink:
    """Represents a data sink in the pipeline."""
    sink_id: str
    sink_type: str
    connection_config: Dict[str, Any]
    format: DataFormat = DataFormat.JSON
    batch_size: int = 1000

@dataclass
class TransformStep:
    """Represents a data transformation step."""
    step_id: str
    transform_type: str  # "filter", "map", "aggregate", "join", etc.
    config: Dict[str, Any]
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DataPipeline:
    """Represents a complete data pipeline."""
    pipeline_id: str
    name: str
    source: DataSource
    transforms: List[TransformStep]
    sink: DataSink
    status: PipelineStatus = PipelineStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

class StreamingProcessor:
    """Real-time streaming data processor."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.streams: Dict[str, threading.Thread] = {}
        self.processors: Dict[str, Callable] = {}
        self.running = False

    def add_stream_processor(self, stream_name: str, processor: Callable):
        """Add a processor for a specific stream."""
        self.processors[stream_name] = processor

    def start_stream_processing(self, stream_name: str):
        """Start processing a Redis stream."""
        if stream_name in self.streams:
            return

        thread = threading.Thread(
            target=self._process_stream,
            args=(stream_name,),
            daemon=True
        )
        thread.start()
        self.streams[stream_name] = thread

    def publish_to_stream(self, stream_name: str, data: Dict):
        """Publish data to a Redis stream."""
        self.redis.xadd(stream_name, {
            "data": json.dumps(data),
            "timestamp": datetime.now().isoformat()
        })

    def _process_stream(self, stream_name: str):
        """Process messages from a Redis stream."""
        last_id = "0"
        processor = self.processors.get(stream_name)

        if not processor:
            logger.error(f"No processor registered for stream: {stream_name}")
            return

        while self.running:
            try:
                messages = self.redis.xread({stream_name: last_id}, block=1000)
                if messages:
                    for stream, entries in messages:
                        for entry_id, entry_data in entries:
                            last_id = entry_id
                            try:
                                data = json.loads(entry_data[b"data"].decode())
                                processor(data)
                            except Exception as e:
                                logger.error(f"Stream processing error: {e}")
            except Exception as e:
                logger.error(f"Stream read error: {e}")
                time.sleep(1)

class ETLOrchestrator:
    """ETL pipeline orchestrator for batch data processing."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.pipelines: Dict[str, DataPipeline] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)

    def create_pipeline(self, name: str, source: DataSource,
                       transforms: List[TransformStep], sink: DataSink) -> str:
        """Create a new ETL pipeline."""
        pipeline_id = f"pipeline_{uuid.uuid4().hex}"
        pipeline = DataPipeline(
            pipeline_id=pipeline_id,
            name=name,
            source=source,
            transforms=transforms,
            sink=sink
        )
        self.pipelines[pipeline_id] = pipeline
        return pipeline_id

    def execute_pipeline(self, pipeline_id: str) -> bool:
        """Execute a pipeline asynchronously."""
        if pipeline_id not in self.pipelines:
            return False

        pipeline = self.pipelines[pipeline_id]
        pipeline.status = PipelineStatus.RUNNING
        pipeline.started_at = datetime.now()

        # Execute in background
        self.executor.submit(self._execute_pipeline_steps, pipeline)
        return True

    def _execute_pipeline_steps(self, pipeline: DataPipeline):
        """Execute pipeline steps: Extract, Transform, Load."""
        try:
            # Extract
            data = self._extract_data(pipeline.source)
            pipeline.metrics["extracted_records"] = len(data) if hasattr(data, '__len__') else 0

            # Transform
            for transform in pipeline.transforms:
                data = self._apply_transform(data, transform)
                pipeline.metrics[f"transform_{transform.step_id}_records"] = len(data) if hasattr(data, '__len__') else 0

            # Load
            self._load_data(data, pipeline.sink)
            pipeline.metrics["loaded_records"] = len(data) if hasattr(data, '__len__') else 0

            pipeline.status = PipelineStatus.COMPLETED
            pipeline.completed_at = datetime.now()

            logger.info(f"Pipeline {pipeline.pipeline_id} completed successfully")

        except Exception as e:
            logger.error(f"Pipeline {pipeline.pipeline_id} failed: {e}")
            pipeline.status = PipelineStatus.FAILED
            pipeline.error = str(e)

    def _extract_data(self, source: DataSource) -> Any:
        """Extract data from source."""
        if source.source_type == "database":
            return self._extract_from_database(source)
        elif source.source_type == "api":
            return self._extract_from_api(source)
        elif source.source_type == "file":
            return self._extract_from_file(source)
        elif source.source_type == "stream":
            return self._extract_from_stream(source)
        else:
            raise ValueError(f"Unsupported source type: {source.source_type}")

    def _extract_from_database(self, source: DataSource) -> pd.DataFrame:
        """Extract data from database."""
        # Implementation would depend on specific database
        # For now, return mock data
        return pd.DataFrame({
            "id": range(100),
            "name": [f"Item {i}" for i in range(100)],
            "value": np.random.randn(100)
        })

    def _extract_from_api(self, source: DataSource) -> Dict:
        """Extract data from API."""
        # Mock API extraction
        return {"data": "mock_api_data", "timestamp": datetime.now().isoformat()}

    def _extract_from_file(self, source: DataSource) -> pd.DataFrame:
        """Extract data from file."""
        file_path = source.connection_config.get("path")
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.endswith(".csv"):
            return pd.read_csv(file_path)
        elif file_path.endswith(".json"):
            return pd.read_json(file_path)
        elif file_path.endswith(".parquet"):
            return pd.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

    def _extract_from_stream(self, source: DataSource) -> Iterator[Dict]:
        """Extract data from stream."""
        # Mock streaming data
        for i in range(100):
            yield {"id": i, "data": f"stream_item_{i}", "timestamp": datetime.now().isoformat()}

    def _apply_transform(self, data: Any, transform: TransformStep) -> Any:
        """Apply transformation to data."""
        transform_type = transform.transform_type

        if transform_type == "filter":
            return self._apply_filter(data, transform.config)
        elif transform_type == "map":
            return self._apply_map(data, transform.config)
        elif transform_type == "aggregate":
            return self._apply_aggregate(data, transform.config)
        elif transform_type == "join":
            return self._apply_join(data, transform.config)
        else:
            raise ValueError(f"Unsupported transform type: {transform_type}")

    def _apply_filter(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """Apply filter transformation."""
        condition = config.get("condition", "")
        # Simple filtering - in production, use proper query parsing
        if "value > 0" in condition:
            return data[data["value"] > 0]
        return data

    def _apply_map(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """Apply map transformation."""
        mapping = config.get("mapping", {})
        for old_col, new_col in mapping.items():
            if old_col in data.columns:
                data = data.rename(columns={old_col: new_col})
        return data

    def _apply_aggregate(self, data: pd.DataFrame, config: Dict) -> pd.DataFrame:
        """Apply aggregation transformation."""
        group_by = config.get("group_by", [])
        aggregations = config.get("aggregations", {})
        return data.groupby(group_by).agg(aggregations).reset_index()

    def _apply_join(self, data: Any, config: Dict) -> Any:
        """Apply join transformation."""
        # Mock join - in production, handle multiple data sources
        return data

    def _load_data(self, data: Any, sink: DataSink):
        """Load data to sink."""
        if sink.sink_type == "database":
            self._load_to_database(data, sink)
        elif sink.sink_type == "file":
            self._load_to_file(data, sink)
        elif sink.sink_type == "stream":
            self._load_to_stream(data, sink)
        else:
            raise ValueError(f"Unsupported sink type: {sink.sink_type}")

    def _load_to_database(self, data: pd.DataFrame, sink: DataSink):
        """Load data to database."""
        # Mock database loading
        logger.info(f"Loading {len(data)} records to database")

    def _load_to_file(self, data: pd.DataFrame, sink: DataSink):
        """Load data to file."""
        file_path = sink.connection_config.get("path")
        if sink.format == DataFormat.CSV:
            data.to_csv(file_path, index=False)
        elif sink.format == DataFormat.JSON:
            data.to_json(file_path, orient="records")
        elif sink.format == DataFormat.PARQUET:
            data.to_parquet(file_path)

    def _load_to_stream(self, data: Any, sink: DataSink):
        """Load data to stream."""
        # Mock stream loading
        logger.info("Loading data to stream")

class DataQualityEngine:
    """Data quality validation and monitoring engine."""

    def __init__(self):
        self.quality_checks: Dict[str, Callable] = {}
        self.quality_metrics: Dict[str, Dict] = {}

    def add_quality_check(self, check_name: str, check_func: Callable):
        """Add a data quality check."""
        self.quality_checks[check_name] = check_func

    def validate_data(self, data: Any, checks: List[str]) -> Dict[str, Any]:
        """Validate data quality."""
        results = {}
        for check_name in checks:
            if check_name in self.quality_checks:
                try:
                    result = self.quality_checks[check_name](data)
                    results[check_name] = result
                except Exception as e:
                    results[check_name] = {"status": "error", "message": str(e)}
            else:
                results[check_name] = {"status": "not_found"}

        return results

    def get_completeness_score(self, data: pd.DataFrame) -> float:
        """Calculate data completeness score."""
        total_cells = data.shape[0] * data.shape[1]
        null_cells = data.isnull().sum().sum()
        return (total_cells - null_cells) / total_cells if total_cells > 0 else 0

    def get_accuracy_score(self, data: pd.DataFrame, validation_rules: Dict) -> float:
        """Calculate data accuracy score based on validation rules."""
        # Mock accuracy scoring
        return 0.95

    def detect_anomalies(self, data: pd.DataFrame, method: str = "isolation_forest") -> List[Dict]:
        """Detect anomalies in data."""
        # Mock anomaly detection
        anomalies = []
        for i, row in data.iterrows():
            if np.random.random() < 0.05:  # 5% anomaly rate
                anomalies.append({
                    "row_index": i,
                    "anomaly_score": np.random.random(),
                    "reason": "Unusual pattern detected"
                })
        return anomalies

class RealTimeAnalytics:
    """Real-time analytics engine for streaming data."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.analytics_functions: Dict[str, Callable] = {}
        self.windowed_data: Dict[str, List] = {}
        self.window_size = 1000  # Last 1000 events

    def add_analytics_function(self, name: str, func: Callable):
        """Add a real-time analytics function."""
        self.analytics_functions[name] = func

    def process_event(self, event_type: str, event_data: Dict):
        """Process incoming event for real-time analytics."""
        # Maintain sliding window
        if event_type not in self.windowed_data:
            self.windowed_data[event_type] = []
        self.windowed_data[event_type].append(event_data)
        if len(self.windowed_data[event_type]) > self.window_size:
            self.windowed_data[event_type].pop(0)

        # Run analytics functions
        for func_name, func in self.analytics_functions.items():
            try:
                result = func(self.windowed_data[event_type])
                # Store result in Redis
                self.redis.setex(f"analytics:{event_type}:{func_name}",
                               3600, json.dumps(result))
            except Exception as e:
                logger.error(f"Analytics function {func_name} error: {e}")

    def get_analytics_result(self, event_type: str, func_name: str) -> Optional[Dict]:
        """Get latest analytics result."""
        key = f"analytics:{event_type}:{func_name}"
        data = self.redis.get(key)
        return json.loads(data.decode()) if data else None

# Global instances
streaming_processor = StreamingProcessor(redis.from_url("redis://localhost:6379"))
etl_orchestrator = ETLOrchestrator(redis.from_url("redis://localhost:6379"))
data_quality_engine = DataQualityEngine()
real_time_analytics = RealTimeAnalytics(redis.from_url("redis://localhost:6379"))

def initialize_data_pipelines():
    """Initialize the data pipeline system."""
    # Set up streaming processors
    streaming_processor.add_stream_processor("client_events", process_client_event)
    streaming_processor.add_stream_processor("data_ingestion", process_data_ingestion)

    # Start stream processing
    streaming_processor.start_stream_processing("client_events")
    streaming_processor.start_stream_processing("data_ingestion")

    # Set up data quality checks
    data_quality_engine.add_quality_check("completeness", lambda data: data_quality_engine.get_completeness_score(data))
    data_quality_engine.add_quality_check("accuracy", lambda data: data_quality_engine.get_accuracy_score(data, {}))
    data_quality_engine.add_quality_check("anomaly_detection", lambda data: data_quality_engine.detect_anomalies(data))

    # Set up real-time analytics
    real_time_analytics.add_analytics_function("sentiment_trend", calculate_sentiment_trend)
    real_time_analytics.add_analytics_function("activity_volume", calculate_activity_volume)

    logger.info("Data pipeline system initialized")

def process_client_event(event_data: Dict):
    """Process client activity events."""
    # Update real-time analytics
    real_time_analytics.process_event("client_events", event_data)

    # Trigger data quality checks if needed
    if event_data.get("type") == "data_update":
        # Mock data for quality check
        mock_data = pd.DataFrame(event_data.get("data", []))
        quality_results = data_quality_engine.validate_data(
            mock_data, ["completeness", "anomaly_detection"]
        )
        logger.info(f"Data quality results: {quality_results}")

def process_data_ingestion(event_data: Dict):
    """Process data ingestion events."""
    connector_id = event_data.get("connector_id")
    data_type = event_data.get("data_type")

    # Create ETL pipeline for this data
    source = DataSource(
        source_id=f"source_{connector_id}",
        source_type="stream",
        connection_config={"stream": f"data_{connector_id}"}
    )

    transforms = [
        TransformStep(
            step_id="filter_valid",
            transform_type="filter",
            config={"condition": "status == 'valid'"}
        ),
        TransformStep(
            step_id="normalize",
            transform_type="map",
            config={"mapping": {"old_field": "new_field"}}
        )
    ]

    sink = DataSink(
        sink_id=f"sink_{connector_id}",
        sink_type="database",
        connection_config={"table": f"processed_{data_type}"}
    )

    pipeline_id = etl_orchestrator.create_pipeline(
        f"Process {data_type} from {connector_id}",
        source, transforms, sink
    )

    etl_orchestrator.execute_pipeline(pipeline_id)

def calculate_sentiment_trend(events: List[Dict]) -> Dict:
    """Calculate sentiment trend from recent events."""
    sentiments = [e.get("sentiment", 0) for e in events[-100:]]  # Last 100 events
    if not sentiments:
        return {"trend": "neutral", "average": 0}

    avg_sentiment = sum(sentiments) / len(sentiments)
    if avg_sentiment > 0.1:
        trend = "positive"
    elif avg_sentiment < -0.1:
        trend = "negative"
    else:
        trend = "neutral"

    return {"trend": trend, "average": avg_sentiment, "sample_size": len(sentiments)}

def calculate_activity_volume(events: List[Dict]) -> Dict:
    """Calculate activity volume from recent events."""
    recent_events = events[-60*10:]  # Last 10 minutes assuming 1 event/second
    return {
        "events_per_minute": len(recent_events) / 10,
        "total_events": len(events),
        "peak_hour": datetime.now().hour
    }

# Export components
__all__ = [
    "DataSource",
    "DataSink",
    "TransformStep",
    "DataPipeline",
    "StreamingProcessor",
    "ETLOrchestrator",
    "DataQualityEngine",
    "RealTimeAnalytics",
    "streaming_processor",
    "etl_orchestrator",
    "data_quality_engine",
    "real_time_analytics",
    "initialize_data_pipelines"
]