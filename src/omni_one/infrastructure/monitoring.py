"""
Monitoring and Observability System
===================================

Enterprise-grade monitoring, logging, alerting, and observability
for the Omni-One platform.
"""

import os
import time
import threading
import logging
import logging.handlers
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import psutil
import socket
from collections import deque
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class AlertStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"

@dataclass
class Alert:
    """Represents a system alert."""
    alert_id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Metric:
    """Represents a system metric."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class MetricsCollector:
    """Advanced metrics collection and aggregation."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.metrics_buffer: Dict[str, deque] = {}
        self.collection_interval = 60  # seconds
        self.retention_period = 3600  # 1 hour
        self._collection_thread = threading.Thread(target=self._collect_system_metrics, daemon=True)
        self._collection_thread.start()

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a custom metric."""
        metric = Metric(
            name=name,
            value=value,
            tags=tags or {}
        )

        # Store in Redis with expiration
        key = f"metric:{name}:{json.dumps(tags, sort_keys=True)}"
        self.redis.lpush(key, json.dumps({
            "value": value,
            "timestamp": metric.timestamp.isoformat()
        }))
        self.redis.expire(key, self.retention_period)

        # Maintain in-memory buffer for quick access
        if name not in self.metrics_buffer:
            self.metrics_buffer[name] = deque(maxlen=1000)
        self.metrics_buffer[name].append(metric)

    def get_metric_stats(self, name: str, time_range: timedelta = timedelta(hours=1)) -> Dict:
        """Get statistics for a metric over a time range."""
        cutoff_time = datetime.now() - time_range

        if name in self.metrics_buffer:
            recent_metrics = [m for m in self.metrics_buffer[name]
                            if m.timestamp > cutoff_time]
        else:
            # Fetch from Redis
            pattern = f"metric:{name}:*"
            keys = self.redis.keys(pattern)
            recent_metrics = []

            for key in keys:
                data_list = self.redis.lrange(key, 0, -1)
                for data in data_list:
                    try:
                        metric_data = json.loads(data.decode())
                        timestamp = datetime.fromisoformat(metric_data["timestamp"])
                        if timestamp > cutoff_time:
                            recent_metrics.append(Metric(
                                name=name,
                                value=metric_data["value"],
                                timestamp=timestamp
                            ))
                    except:
                        pass

        if not recent_metrics:
            return {"count": 0, "avg": 0, "min": 0, "max": 0}

        values = [m.value for m in recent_metrics]
        return {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "latest": values[-1] if values else 0
        }

    def _collect_system_metrics(self):
        """Collect system-level metrics."""
        while True:
            try:
                # CPU metrics
                self.record_metric("system.cpu.percent", psutil.cpu_percent(interval=1))
                self.record_metric("system.cpu.count", psutil.cpu_count())

                # Memory metrics
                memory = psutil.virtual_memory()
                self.record_metric("system.memory.percent", memory.percent)
                self.record_metric("system.memory.used", memory.used)
                self.record_metric("system.memory.available", memory.available)

                # Disk metrics
                disk = psutil.disk_usage('/')
                self.record_metric("system.disk.percent", disk.percent)
                self.record_metric("system.disk.used", disk.used)
                self.record_metric("system.disk.free", disk.free)

                # Network metrics
                net = psutil.net_io_counters()
                self.record_metric("system.network.bytes_sent", net.bytes_sent)
                self.record_metric("system.network.bytes_recv", net.bytes_recv)

                # Process metrics
                process = psutil.Process()
                self.record_metric("process.cpu.percent", process.cpu_percent())
                self.record_metric("process.memory.percent", process.memory_percent())
                self.record_metric("process.memory.rss", process.memory_info().rss)
                self.record_metric("process.threads", process.num_threads())

            except Exception as e:
                logger.error(f"Metrics collection error: {e}")

            time.sleep(self.collection_interval)

class AlertManager:
    """Alert management and notification system."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.alerts: Dict[str, Alert] = {}
        self.alert_handlers: Dict[str, List[Callable]] = {}
        self.notification_channels: Dict[str, Callable] = {}

        # Default notification channels
        self.add_notification_channel("email", self._send_email_notification)
        self.add_notification_channel("slack", self._send_slack_notification)
        self.add_notification_channel("webhook", self._send_webhook_notification)

    def create_alert(self, title: str, message: str, severity: AlertSeverity,
                    source: str, tags: Dict[str, str] = None) -> str:
        """Create a new alert."""
        alert_id = f"alert_{int(time.time())}_{hash(title + message) % 10000}"
        alert = Alert(
            alert_id=alert_id,
            title=title,
            message=message,
            severity=severity,
            source=source,
            tags=tags or {}
        )

        self.alerts[alert_id] = alert

        # Store in Redis
        self.redis.setex(f"alert:{alert_id}", 86400 * 7, json.dumps({
            "alert_id": alert_id,
            "title": title,
            "message": message,
            "severity": severity.value,
            "source": source,
            "status": alert.status.value,
            "created_at": alert.created_at.isoformat(),
            "tags": tags or {}
        }))

        # Trigger alert handlers
        self._trigger_alert_handlers(alert)

        logger.warning(f"Alert created: {title} ({severity.value})")
        return alert_id

    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        if alert_id in self.alerts:
            alert = self.alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now()

            # Update Redis
            self.redis.setex(f"alert:{alert_id}", 86400 * 7, json.dumps({
                "status": "resolved",
                "resolved_at": alert.resolved_at.isoformat()
            }))

            logger.info(f"Alert resolved: {alert.title}")

    def add_alert_handler(self, condition: str, handler: Callable):
        """Add handler for specific alert conditions."""
        if condition not in self.alert_handlers:
            self.alert_handlers[condition] = []
        self.alert_handlers[condition].append(handler)

    def add_notification_channel(self, channel_name: str, sender: Callable):
        """Add notification channel."""
        self.notification_channels[channel_name] = sender

    def send_notification(self, alert: Alert, channels: List[str]):
        """Send alert notification via specified channels."""
        for channel in channels:
            if channel in self.notification_channels:
                try:
                    self.notification_channels[channel](alert)
                except Exception as e:
                    logger.error(f"Notification error for {channel}: {e}")

    def _trigger_alert_handlers(self, alert: Alert):
        """Trigger appropriate alert handlers."""
        # Check severity-based handlers
        severity_handlers = self.alert_handlers.get(f"severity:{alert.severity.value}", [])
        for handler in severity_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        # Check source-based handlers
        source_handlers = self.alert_handlers.get(f"source:{alert.source}", [])
        for handler in source_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    def _send_email_notification(self, alert: Alert):
        """Send email notification."""
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")
        recipients = os.getenv("ALERT_EMAIL_RECIPIENTS", "").split(",")

        if not all([smtp_user, smtp_password, recipients]):
            logger.warning("Email notification not configured")
            return

        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"

        body = f"""
        Alert Details:
        - Title: {alert.title}
        - Message: {alert.message}
        - Severity: {alert.severity.value}
        - Source: {alert.source}
        - Time: {alert.created_at.isoformat()}

        Please check the system immediately.
        """
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipients, msg.as_string())
            server.quit()
            logger.info(f"Email alert sent to {recipients}")
        except Exception as e:
            logger.error(f"Email sending failed: {e}")

    def _send_slack_notification(self, alert: Alert):
        """Send Slack notification."""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("Slack webhook not configured")
            return

        payload = {
            "text": f"🚨 *{alert.severity.value.upper()}* {alert.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{alert.title}*\n{alert.message}\n\n*Severity:* {alert.severity.value}\n*Source:* {alert.source}"
                    }
                }
            ]
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Slack alert sent")
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    def _send_webhook_notification(self, alert: Alert):
        """Send webhook notification."""
        webhook_url = os.getenv("ALERT_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("Alert webhook not configured")
            return

        payload = {
            "alert_id": alert.alert_id,
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity.value,
            "source": alert.source,
            "timestamp": alert.created_at.isoformat(),
            "tags": alert.tags
        }

        try:
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Webhook alert sent")
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")

class LogAggregator:
    """Centralized logging aggregation and analysis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.log_levels = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50
        }

    def log_event(self, level: str, message: str, source: str,
                  metadata: Dict[str, Any] = None):
        """Log an event to centralized store."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "level_code": self.log_levels.get(level.upper(), 20),
            "message": message,
            "source": source,
            "metadata": metadata or {},
            "hostname": socket.gethostname()
        }

        # Store in Redis sorted set by timestamp
        score = time.time()
        self.redis.zadd("logs", {json.dumps(log_entry): score})

        # Keep only last 10000 logs
        self.redis.zremrangebyrank("logs", 0, -10001)

    def get_logs(self, level: str = None, source: str = None,
                 time_range: timedelta = timedelta(hours=1)) -> List[Dict]:
        """Retrieve logs with filtering."""
        cutoff_time = time.time() - time_range.total_seconds()

        # Get logs within time range
        logs_data = self.redis.zrangebyscore("logs", cutoff_time, "+inf")

        logs = []
        for log_data in logs_data:
            try:
                log_entry = json.loads(log_data.decode())

                # Apply filters
                if level and log_entry["level"] != level:
                    continue
                if source and log_entry["source"] != source:
                    continue

                logs.append(log_entry)
            except:
                pass

        return logs

    def get_log_stats(self, time_range: timedelta = timedelta(hours=1)) -> Dict:
        """Get log statistics."""
        logs = self.get_logs(time_range=time_range)

        stats = {
            "total_logs": len(logs),
            "by_level": {},
            "by_source": {},
            "error_rate": 0
        }

        for log in logs:
            level = log["level"]
            source = log["source"]

            stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
            stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

        # Calculate error rate
        error_logs = stats["by_level"].get("ERROR", 0) + stats["by_level"].get("CRITICAL", 0)
        stats["error_rate"] = error_logs / max(stats["total_logs"], 1)

        return stats

class HealthChecker:
    """Comprehensive health checking system."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.health_checks: Dict[str, Callable] = {}
        self.check_results: Dict[str, Dict] = {}

        # Add default health checks
        self.add_health_check("redis", self._check_redis)
        self.add_health_check("system", self._check_system)
        self.add_health_check("memory", self._check_memory)
        self.add_health_check("disk", self._check_disk)

    def add_health_check(self, name: str, check_func: Callable):
        """Add a health check."""
        self.health_checks[name] = check_func

    def run_health_checks(self) -> Dict[str, Dict]:
        """Run all health checks."""
        results = {}

        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()
                result = check_func()
                duration = time.time() - start_time

                results[name] = {
                    "status": "healthy" if result.get("healthy", True) else "unhealthy",
                    "duration": duration,
                    "timestamp": datetime.now().isoformat(),
                    **result
                }

            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e),
                    "duration": 0,
                    "timestamp": datetime.now().isoformat()
                }

        self.check_results = results
        return results

    def get_overall_health(self) -> Dict:
        """Get overall system health status."""
        results = self.run_health_checks()

        healthy_count = sum(1 for r in results.values() if r["status"] == "healthy")
        total_count = len(results)

        overall_status = "healthy" if healthy_count == total_count else "degraded"
        if any(r["status"] == "error" for r in results.values()):
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "healthy_checks": healthy_count,
            "total_checks": total_count,
            "checks": results,
            "timestamp": datetime.now().isoformat()
        }

    def _check_redis(self) -> Dict:
        """Check Redis connectivity."""
        try:
            self.redis.ping()
            return {"healthy": True, "message": "Redis is responsive"}
        except Exception as e:
            return {"healthy": False, "message": f"Redis error: {e}"}

    def _check_system(self) -> Dict:
        """Check system resources."""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent

        healthy = cpu_percent < 90 and memory_percent < 90
        return {
            "healthy": healthy,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "message": f"CPU: {cpu_percent}%, Memory: {memory_percent}%"
        }

    def _check_memory(self) -> Dict:
        """Check memory usage."""
        memory = psutil.virtual_memory()
        healthy = memory.percent < 85

        return {
            "healthy": healthy,
            "used_percent": memory.percent,
            "available_gb": memory.available / (1024**3),
            "message": f"Memory usage: {memory.percent}%"
        }

    def _check_disk(self) -> Dict:
        """Check disk usage."""
        disk = psutil.disk_usage('/')
        healthy = disk.percent < 90

        return {
            "healthy": healthy,
            "used_percent": disk.percent,
            "free_gb": disk.free / (1024**3),
            "message": f"Disk usage: {disk.percent}%"
        }

# Global instances
metrics_collector = MetricsCollector(redis.from_url("redis://localhost:6379"))
alert_manager = AlertManager(redis.from_url("redis://localhost:6379"))
log_aggregator = LogAggregator(redis.from_url("redis://localhost:6379"))
health_checker = HealthChecker(redis.from_url("redis://localhost:6379"))

def initialize_monitoring():
    """Initialize the monitoring and observability system."""
    # Set up alert handlers
    alert_manager.add_alert_handler("severity:critical", lambda alert: alert_manager.send_notification(alert, ["email", "slack"]))
    alert_manager.add_alert_handler("severity:error", lambda alert: alert_manager.send_notification(alert, ["slack"]))
    alert_manager.add_alert_handler("source:system", lambda alert: alert_manager.send_notification(alert, ["webhook"]))

    # Set up automated alerts based on metrics
    monitoring_thread = threading.Thread(target=monitor_system_health, daemon=True)
    monitoring_thread.start()

    logger.info("Monitoring and observability system initialized")

def monitor_system_health():
    """Monitor system health and create alerts."""
    while True:
        try:
            # Check system metrics
            cpu_stats = metrics_collector.get_metric_stats("system.cpu.percent")
            memory_stats = metrics_collector.get_metric_stats("system.memory.percent")

            # CPU alert
            if cpu_stats.get("avg", 0) > 90:
                alert_manager.create_alert(
                    "High CPU Usage",
                    f"CPU usage is {cpu_stats['avg']:.1f}% (threshold: 90%)",
                    AlertSeverity.WARNING,
                    "system",
                    {"metric": "cpu", "value": cpu_stats["avg"]}
                )

            # Memory alert
            if memory_stats.get("avg", 0) > 85:
                alert_manager.create_alert(
                    "High Memory Usage",
                    f"Memory usage is {memory_stats['avg']:.1f}% (threshold: 85%)",
                    AlertSeverity.ERROR,
                    "system",
                    {"metric": "memory", "value": memory_stats["avg"]}
                )

            # Health check
            health_status = health_checker.get_overall_health()
            if health_status["status"] != "healthy":
                alert_manager.create_alert(
                    "System Health Degraded",
                    f"System health status: {health_status['status']}",
                    AlertSeverity.WARNING,
                    "health_checker"
                )

        except Exception as e:
            logger.error(f"Health monitoring error: {e}")

        time.sleep(300)  # Check every 5 minutes

# Export components
__all__ = [
    "Alert",
    "Metric",
    "AlertSeverity",
    "AlertStatus",
    "MetricsCollector",
    "AlertManager",
    "LogAggregator",
    "HealthChecker",
    "metrics_collector",
    "alert_manager",
    "log_aggregator",
    "health_checker",
    "initialize_monitoring"
]