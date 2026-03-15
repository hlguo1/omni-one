"""
Advanced Worker and Scheduler System
====================================

Enterprise-grade task processing system with multiple queues, priority handling,
scheduled tasks, and complex workflow orchestration.
"""

import os
import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import uuid
import heapq
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import redis
from celery import Celery
import schedule
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"

class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

@dataclass
class Task:
    """Represents a task in the system."""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300  # 5 minutes
    dependencies: List[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "dependencies": self.dependencies,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata
        }

@dataclass
class WorkflowStep:
    """Represents a step in a workflow."""
    step_id: str
    task_type: str
    payload: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 300
    retry_policy: Dict = field(default_factory=lambda: {"max_retries": 3, "backoff": 60})

@dataclass
class Workflow:
    """Represents a complex workflow with multiple steps."""
    workflow_id: str
    name: str
    steps: List[WorkflowStep]
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step: Optional[str] = None
    results: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class TaskQueue:
    """Priority queue for tasks with Redis backend."""

    def __init__(self, redis_client: redis.Redis, queue_name: str = "default"):
        self.redis = redis_client
        self.queue_name = queue_name
        self.processing_key = f"processing:{queue_name}"
        self.dead_letter_key = f"dead_letter:{queue_name}"

    def enqueue(self, task: Task) -> bool:
        """Add task to queue with priority."""
        try:
            # Use Redis sorted set with priority as score
            score = task.priority.value
            self.redis.zadd(self.queue_name, {json.dumps(task.to_dict()): score})
            logger.info(f"Enqueued task {task.task_id} to {self.queue_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task {task.task_id}: {e}")
            return False

    def dequeue(self) -> Optional[Task]:
        """Get highest priority task from queue."""
        try:
            # Get the task with lowest score (highest priority)
            result = self.redis.zpopmin(self.queue_name)
            if result:
                task_data = json.loads(result[0][0])
                task = Task(**task_data)
                # Mark as processing
                self.redis.setex(f"{self.processing_key}:{task.task_id}", task.timeout, json.dumps(task.to_dict()))
                return task
        except Exception as e:
            logger.error(f"Failed to dequeue task: {e}")
        return None

    def requeue_failed(self, task: Task):
        """Requeue a failed task or move to dead letter queue."""
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.RETRY
            # Exponential backoff
            delay = 2 ** task.retry_count
            task.metadata["next_retry"] = (datetime.now() + timedelta(seconds=delay)).isoformat()
            self.redis.zadd(self.queue_name, {json.dumps(task.to_dict()): task.priority.value})
        else:
            # Move to dead letter queue
            self.redis.lpush(self.dead_letter_key, json.dumps(task.to_dict()))

    def complete_task(self, task: Task):
        """Mark task as completed and clean up."""
        self.redis.delete(f"{self.processing_key}:{task.task_id}")

    def get_queue_stats(self) -> Dict:
        """Get queue statistics."""
        return {
            "queued": self.redis.zcard(self.queue_name),
            "processing": len(self.redis.keys(f"{self.processing_key}:*")),
            "dead_letter": self.redis.llen(self.dead_letter_key)
        }

class WorkerPool:
    """Pool of workers processing tasks from multiple queues."""

    def __init__(self, redis_url: str = "redis://localhost:6379", pool_size: int = 4):
        self.redis = redis.from_url(redis_url)
        self.pool_size = pool_size
        self.queues: Dict[str, TaskQueue] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.executor = ThreadPoolExecutor(max_workers=pool_size)
        self.running = False
        self.workers: List[threading.Thread] = []

    def add_queue(self, queue_name: str, priority: int = 1):
        """Add a task queue to process."""
        self.queues[queue_name] = TaskQueue(self.redis, queue_name)

    def register_handler(self, task_type: str, handler: Callable):
        """Register a handler for a specific task type."""
        self.task_handlers[task_type] = handler

    def start(self):
        """Start the worker pool."""
        self.running = True
        for i in range(self.pool_size):
            worker = threading.Thread(target=self._worker_loop, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        logger.info(f"Started worker pool with {self.pool_size} workers")

    def stop(self):
        """Stop the worker pool."""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("Stopped worker pool")

    def _worker_loop(self, worker_id: int):
        """Main worker loop."""
        logger.info(f"Worker {worker_id} started")

        while self.running:
            task = None
            try:
                # Try to get task from queues (priority order)
                for queue_name, queue in self.queues.items():
                    task = queue.dequeue()
                    if task:
                        break

                if task:
                    logger.info(f"Worker {worker_id} processing task {task.task_id}")
                    self._execute_task(task)
                else:
                    time.sleep(1)  # No tasks available

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                if task:
                    # Requeue failed task
                    queue = self.queues.get(task.task_type, list(self.queues.values())[0])
                    queue.requeue_failed(task)

    def _execute_task(self, task: Task):
        """Execute a task with timeout and error handling."""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            # Get handler
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise Exception(f"No handler registered for task type: {task.task_type}")

            # Execute with timeout
            future = self.executor.submit(handler, task.payload)
            result = future.result(timeout=task.timeout)

            # Mark as completed
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result

            # Clean up
            queue = self.queues.get(task.task_type, list(self.queues.values())[0])
            queue.complete_task(task)

            logger.info(f"Task {task.task_id} completed successfully")

        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()

            # Requeue or move to dead letter
            queue = self.queues.get(task.task_type, list(self.queues.values())[0])
            queue.requeue_failed(task)

class AdvancedScheduler:
    """Advanced scheduler for complex time-based and event-driven tasks."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.scheduled_jobs: Dict[str, Dict] = {}
        self.event_listeners: Dict[str, List[Callable]] = {}
        self.timezone = pytz.UTC
        self.running = False
        self.scheduler_thread = None

    def schedule_task(self, task: Task, schedule_time: datetime,
                     recurring: bool = False, interval: timedelta = None) -> str:
        """Schedule a task for execution."""
        job_id = f"scheduled_{task.task_id}_{int(time.time())}"

        job_data = {
            "job_id": job_id,
            "task": task.to_dict(),
            "schedule_time": schedule_time.isoformat(),
            "recurring": recurring,
            "interval_seconds": interval.total_seconds() if interval else None,
            "next_run": schedule_time.isoformat()
        }

        # Store in Redis
        self.redis.setex(f"scheduled_job:{job_id}", 86400 * 30, json.dumps(job_data))  # 30 days

        # Add to in-memory cache
        self.scheduled_jobs[job_id] = job_data

        logger.info(f"Scheduled task {task.task_id} for {schedule_time}")
        return job_id

    def schedule_cron(self, task: Task, cron_expression: str) -> str:
        """Schedule a task using cron expression."""
        # For simplicity, we'll implement basic cron-like scheduling
        # In production, use a proper cron parser
        job_id = f"cron_{task.task_id}_{int(time.time())}"

        job_data = {
            "job_id": job_id,
            "task": task.to_dict(),
            "cron_expression": cron_expression,
            "type": "cron"
        }

        self.redis.setex(f"cron_job:{job_id}", 86400 * 30, json.dumps(job_data))
        self.scheduled_jobs[job_id] = job_data

        return job_id

    def add_event_listener(self, event_type: str, callback: Callable):
        """Add event listener for specific event types."""
        if event_type not in self.event_listeners:
            self.event_listeners[event_type] = []
        self.event_listeners[event_type].append(callback)

    def trigger_event(self, event_type: str, event_data: Dict):
        """Trigger an event and notify all listeners."""
        if event_type in self.event_listeners:
            for callback in self.event_listeners[event_type]:
                try:
                    self.executor.submit(callback, event_data)
                except Exception as e:
                    logger.error(f"Event listener error: {e}")

    def start(self):
        """Start the scheduler."""
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Advanced scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()

    def _scheduler_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                now = datetime.now(self.timezone)

                # Check scheduled jobs
                for job_id, job_data in list(self.scheduled_jobs.items()):
                    next_run = datetime.fromisoformat(job_data["next_run"])

                    if now >= next_run:
                        self._execute_scheduled_job(job_data)

                        # Handle recurring jobs
                        if job_data.get("recurring"):
                            interval = timedelta(seconds=job_data["interval_seconds"])
                            job_data["next_run"] = (next_run + interval).isoformat()
                            self.redis.setex(f"scheduled_job:{job_id}", 86400 * 30,
                                           json.dumps(job_data))
                        else:
                            # Remove one-time job
                            self.redis.delete(f"scheduled_job:{job_id}")
                            del self.scheduled_jobs[job_id]

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            time.sleep(10)  # Check every 10 seconds

    def _execute_scheduled_job(self, job_data: Dict):
        """Execute a scheduled job."""
        try:
            task_data = job_data["task"]
            task = Task(**task_data)

            # Submit to worker pool (assuming global worker pool)
            if hasattr(self, 'worker_pool'):
                self.worker_pool.submit_task(task)

            logger.info(f"Executed scheduled job {job_data['job_id']}")

        except Exception as e:
            logger.error(f"Failed to execute scheduled job {job_data['job_id']}: {e}")

class WorkflowEngine:
    """Engine for executing complex multi-step workflows."""

    def __init__(self, worker_pool: WorkerPool):
        self.worker_pool = worker_pool
        self.workflows: Dict[str, Workflow] = {}
        self.workflow_results: Dict[str, Dict] = {}

    def create_workflow(self, name: str, steps: List[WorkflowStep]) -> str:
        """Create a new workflow."""
        workflow_id = f"workflow_{uuid.uuid4().hex}"
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            steps=steps
        )
        self.workflows[workflow_id] = workflow
        return workflow_id

    def execute_workflow(self, workflow_id: str) -> bool:
        """Execute a workflow asynchronously."""
        if workflow_id not in self.workflows:
            return False

        workflow = self.workflows[workflow_id]
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()

        # Start execution in background
        threading.Thread(target=self._execute_workflow_steps, args=(workflow,), daemon=True).start()
        return True

    def _execute_workflow_steps(self, workflow: Workflow):
        """Execute workflow steps in dependency order."""
        try:
            # Build dependency graph
            step_dict = {step.step_id: step for step in workflow.steps}
            completed_steps = set()
            pending_steps = set(step.step_id for step in workflow.steps)

            while pending_steps:
                # Find steps with satisfied dependencies
                ready_steps = []
                for step_id in pending_steps:
                    step = step_dict[step_id]
                    if all(dep in completed_steps for dep in step.dependencies):
                        ready_steps.append(step)

                if not ready_steps:
                    # Deadlock or circular dependency
                    workflow.status = WorkflowStatus.FAILED
                    break

                # Execute ready steps in parallel
                futures = []
                for step in ready_steps:
                    task = Task(
                        task_id=f"{workflow.workflow_id}_{step.step_id}",
                        task_type=step.task_type,
                        payload=step.payload,
                        timeout=step.timeout
                    )
                    # Submit to worker pool
                    future = self.worker_pool.executor.submit(
                        self.worker_pool.task_handlers.get(step.task_type),
                        task.payload
                    )
                    futures.append((step.step_id, future))

                # Wait for completion
                for step_id, future in futures:
                    try:
                        result = future.result(timeout=step_dict[step_id].timeout)
                        workflow.results[step_id] = result
                        completed_steps.add(step_id)
                        pending_steps.remove(step_id)
                    except Exception as e:
                        logger.error(f"Workflow step {step_id} failed: {e}")
                        workflow.status = WorkflowStatus.FAILED
                        return

            # All steps completed
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            workflow.status = WorkflowStatus.FAILED

class EventDrivenProcessor:
    """Event-driven processor for real-time data processing."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.stream_consumers: Dict[str, threading.Thread] = {}
        self.running = False

    def register_event_handler(self, event_type: str, handler: Callable):
        """Register handler for specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def start_stream_processing(self, stream_name: str):
        """Start processing events from Redis stream."""
        if stream_name in self.stream_consumers:
            return

        consumer = threading.Thread(
            target=self._process_stream,
            args=(stream_name,),
            daemon=True
        )
        consumer.start()
        self.stream_consumers[stream_name] = consumer

    def publish_event(self, event_type: str, event_data: Dict):
        """Publish event to Redis stream."""
        stream_name = f"events:{event_type}"
        self.redis.xadd(stream_name, {"data": json.dumps(event_data), "timestamp": datetime.now().isoformat()})

    def _process_stream(self, stream_name: str):
        """Process events from Redis stream."""
        last_id = "0"
        event_type = stream_name.replace("events:", "")

        while self.running:
            try:
                # Read from stream
                messages = self.redis.xread({stream_name: last_id}, block=1000)
                if messages:
                    for stream, entries in messages:
                        for entry_id, entry_data in entries:
                            last_id = entry_id
                            try:
                                event_data = json.loads(entry_data[b"data"].decode())
                                self._handle_event(event_type, event_data)
                            except Exception as e:
                                logger.error(f"Error processing event: {e}")
            except Exception as e:
                logger.error(f"Stream processing error: {e}")
                time.sleep(1)

    def _handle_event(self, event_type: str, event_data: Dict):
        """Handle incoming event."""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

# Global instances
worker_pool = WorkerPool()
scheduler = AdvancedScheduler(redis.from_url("redis://localhost:6379"))
workflow_engine = WorkflowEngine(worker_pool)
event_processor = EventDrivenProcessor(redis.from_url("redis://localhost:6379"))

def initialize_enterprise_workers():
    """Initialize the enterprise worker system."""
    # Add queues with different priorities
    worker_pool.add_queue("critical", priority=0)
    worker_pool.add_queue("high", priority=1)
    worker_pool.add_queue("normal", priority=2)
    worker_pool.add_queue("background", priority=3)

    # Register task handlers
    from proactive_agents.engine import ProactiveEngine
    from data_connectors.ingestion import DataIngestionService
    from integrations.slack.webhook import SlackIntegration
    from integrations.outlook.webhook import OutlookIntegration

    # Initialize services
    proactive_engine = ProactiveEngine(None, None)  # Will be set up properly
    data_service = DataIngestionService()
    slack_integration = SlackIntegration()
    outlook_integration = OutlookIntegration()

    # Register handlers
    worker_pool.register_handler("proactive_analysis", lambda payload: proactive_engine.generate_proactive_insights(payload.get("client_name")))
    worker_pool.register_handler("data_sync", lambda payload: data_service.sync_connector(payload.get("connector_id")))
    worker_pool.register_handler("sentiment_analysis", lambda payload: proactive_engine.analyze_sentiment(payload.get("text")))
    worker_pool.register_handler("slack_notification", lambda payload: slack_integration.send_notification(payload))
    worker_pool.register_handler("outlook_sync", lambda payload: outlook_integration.sync_emails())

    # Start components
    worker_pool.start()
    scheduler.start()
    event_processor.start_stream_processing("events:client_activity")
    event_processor.start_stream_processing("events:data_changes")

    # Set up event handlers
    event_processor.register_event_handler("client_activity", handle_client_activity_event)
    event_processor.register_event_handler("data_changes", handle_data_change_event)

    logger.info("Enterprise worker system initialized")

def handle_client_activity_event(event_data: Dict):
    """Handle client activity events."""
    client_name = event_data.get("client_name")
    activity_type = event_data.get("activity_type")

    # Trigger proactive analysis
    task = Task(
        task_id=f"proactive_{client_name}_{int(time.time())}",
        task_type="proactive_analysis",
        payload={"client_name": client_name},
        priority=TaskPriority.HIGH
    )
    worker_pool.queues["high"].enqueue(task)

def handle_data_change_event(event_data: Dict):
    """Handle data change events."""
    connector_id = event_data.get("connector_id")

    # Trigger data sync
    task = Task(
        task_id=f"sync_{connector_id}_{int(time.time())}",
        task_type="data_sync",
        payload={"connector_id": connector_id},
        priority=TaskPriority.NORMAL
    )
    worker_pool.queues["normal"].enqueue(task)

# Export components
__all__ = [
    "Task",
    "TaskPriority",
    "TaskStatus",
    "Workflow",
    "WorkflowStatus",
    "TaskQueue",
    "WorkerPool",
    "AdvancedScheduler",
    "WorkflowEngine",
    "EventDrivenProcessor",
    "worker_pool",
    "scheduler",
    "workflow_engine",
    "event_processor",
    "initialize_enterprise_workers"
]