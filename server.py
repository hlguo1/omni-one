"""
Omni-One Enterprise AI Platform Server
======================================

Enterprise-grade AI platform with multi-tier architecture, advanced worker systems,
real-time analytics, and comprehensive monitoring - designed for scale like Meta/Google.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, Response, stream_with_context, g
from flask_cors import CORS
import redis
import psutil

# --- Enterprise Infrastructure Imports (Optional) ---
try:
    from infrastructure import (
        gateway, create_api_gateway_app,
        worker_pool, scheduler, workflow_engine, event_processor,
        initialize_enterprise_workers
    )
    from infrastructure.pipelines import (
        streaming_processor, etl_orchestrator, data_quality_engine, real_time_analytics,
        initialize_data_pipelines
    )
    from infrastructure.monitoring import (
        metrics_collector, alert_manager, log_aggregator, health_checker,
        initialize_monitoring, AlertSeverity
    )
    ENTERPRISE_FEATURES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Enterprise features not available: {e}")
    # Create dummy objects for when enterprise features aren't available
    class DummyGateway:
        def register_service(self, *args, **kwargs): pass
    gateway = DummyGateway()
    create_api_gateway_app = lambda: None
    initialize_enterprise_workers = lambda: True
    initialize_data_pipelines = lambda: True
    initialize_monitoring = lambda: True

    class DummyMetricsCollector:
        def record_metric(self, *args, **kwargs): pass
    metrics_collector = DummyMetricsCollector()

    class DummyAlertManager:
        pass
    alert_manager = DummyAlertManager()

    class DummyLogAggregator:
        def log_event(self, *args, **kwargs): print(f"LOG: {args}")
    log_aggregator = DummyLogAggregator()

    class DummyHealthChecker:
        def get_overall_health(self): return {"status": "basic", "mode": "mvp"}
    health_checker = DummyHealthChecker()

    class DummyAlertSeverity:
        INFO = "info"
        WARNING = "warning"
        ERROR = "error"
        CRITICAL = "critical"
    AlertSeverity = DummyAlertSeverity

    ENTERPRISE_FEATURES_AVAILABLE = False

# Core AI Components
from rag_engine import RAGEngine
from model_router import ModelRouter
from cache import SemanticCache
from proactive_agents.engine import ProactiveEngine
from data_connectors.ingestion import DataIngestionService
from integrations.webhooks import init_integration_blueprint
from models.agent_orchestrator import AgentOrchestrator
from models.continuous_learning import ContinuousLearning

# --- Enterprise Configuration ---
class EnterpriseConfig:
    """Enterprise-grade configuration management."""

    def __init__(self):
        # API Configuration
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        self.api_url_base = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20"
        self.gemini_model = "gemini-2.5-flash-preview-05-20"

        # Infrastructure Configuration
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.enable_api_gateway = os.getenv('ENABLE_API_GATEWAY', 'true').lower() == 'true'
        self.enable_worker_system = os.getenv('ENABLE_WORKER_SYSTEM', 'true').lower() == 'true'
        self.enable_monitoring = os.getenv('ENABLE_MONITORING', 'true').lower() == 'true'

        # Try to connect to Redis
        try:
            import redis
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running in degraded mode.")
            self.redis_client = None
            self.redis_available = False

        # Security Configuration
        self.valid_api_keys = set(os.getenv('VALID_API_KEYS', 'demo-key,test-key').split(','))
        self.rate_limit_requests = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
        self.rate_limit_window = int(os.getenv('RATE_LIMIT_WINDOW', '3600'))  # seconds

        # Performance Configuration
        self.max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '50'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '300'))
        self.streaming_chunk_size = int(os.getenv('STREAMING_CHUNK_SIZE', '1024'))

        # Feature Flags
        self.enable_rag = os.getenv('ENABLE_RAG', 'true').lower() == 'true'
        self.enable_proactive = os.getenv('ENABLE_PROACTIVE', 'true').lower() == 'true'
        self.enable_analytics = os.getenv('ENABLE_ANALYTICS', 'true').lower() == 'true'

        # Validate critical configuration
        if not self.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY environment variable is required")

# Global configuration
config = EnterpriseConfig()

# --- Enterprise Service Registry ---
class EnterpriseServiceRegistry:
    """Service registry for enterprise components."""

    def __init__(self):
        self.services = {}
        self.redis_client = redis.from_url(config.redis_url)

    def register_service(self, name: str, service_instance, health_check=None):
        """Register a service instance."""
        self.services[name] = {
            'instance': service_instance,
            'health_check': health_check,
            'registered_at': datetime.now(),
            'status': 'healthy'
        }
        logger.info(f"Registered enterprise service: {name}")

    def get_service(self, name: str):
        """Get a service instance."""
        if name not in self.services:
            raise RuntimeError(f"Service {name} not registered")
        return self.services[name]['instance']

    def check_service_health(self, name: str) -> bool:
        """Check health of a service."""
        if name not in self.services:
            return False

        service_info = self.services[name]
        if service_info['health_check']:
            try:
                return service_info['health_check']()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                return False
        return True

# Global service registry
service_registry = EnterpriseServiceRegistry()

# --- Enterprise Security & Rate Limiting ---
class EnterpriseSecurity:
    """Enterprise-grade security with authentication and rate limiting."""

    def __init__(self):
        self.rate_limit_cache = {}

    def authenticate_request(self, api_key: str) -> bool:
        """Authenticate API request."""
        return api_key in config.valid_api_keys

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if request is within rate limits."""
        now = time.time()
        window_start = now - config.rate_limit_window

        # Clean old entries
        self.rate_limit_cache[client_id] = [
            timestamp for timestamp in self.rate_limit_cache.get(client_id, [])
            if timestamp > window_start
        ]

        # Check limit
        if len(self.rate_limit_cache[client_id]) >= config.rate_limit_requests:
            return False

        # Add current request
        self.rate_limit_cache[client_id].append(now)
        return True

    def get_client_id(self, request) -> str:
        """Extract client identifier from request."""
        # Use API key as client ID for simplicity
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
        if not api_key:
            return request.remote_addr
        return api_key

# Global security instance
security = EnterpriseSecurity()

def require_auth(f):
    """Decorator for API authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')

        if not api_key:
            return jsonify({"error": "API key required"}), 401

        if not security.authenticate_request(api_key):
            return jsonify({"error": "Invalid API key"}), 401

        # Rate limiting
        client_id = security.get_client_id(request)
        if not security.check_rate_limit(client_id):
            return jsonify({"error": "Rate limit exceeded"}), 429

        g.client_id = client_id
        return f(*args, **kwargs)
    return decorated_function

def monitor_request(f):
    """Decorator for request monitoring."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        endpoint = request.endpoint or 'unknown'
        method = request.method

        try:
            response = f(*args, **kwargs)
            status_code = response[1] if isinstance(response, tuple) else 200
        except Exception as e:
            status_code = 500
            raise e
        finally:
            duration = time.time() - start_time

            # Record metrics
            metrics_collector.record_metric(
                f"api.request.duration",
                duration,
                {"endpoint": endpoint, "method": method}
            )
            metrics_collector.record_metric(
                f"api.request.count",
                1,
                {"endpoint": endpoint, "method": method, "status": status_code}
            )

            # Log request
            log_aggregator.log_event(
                "INFO" if status_code < 400 else "ERROR",
                f"{method} {endpoint} - {status_code}",
                "api",
                {"duration": duration, "client_id": getattr(g, 'client_id', 'unknown')}
            )

        return response
    return decorated_function

# --- Enterprise Application ---
def create_enterprise_app() -> Flask:
    """Create the enterprise Flask application."""

    app = Flask(__name__)
    CORS(app)

    # Configure logging
    app.logger.setLevel(logging.INFO)

    # Register enterprise services
    _initialize_enterprise_services()

    # API Gateway integration
    if config.enable_api_gateway:
        gateway_app = create_api_gateway_app()
        app.register_blueprint(gateway_app, url_prefix='/gateway')

    # Integration blueprints
    proactive_engine = service_registry.get_service('proactive_engine')
    integration_blueprint = init_integration_blueprint(proactive_engine)
    app.register_blueprint(integration_blueprint, url_prefix='/integrations')

    # Health and monitoring endpoints
    @app.route('/health')
    def health_check():
        """Enterprise health check endpoint."""
        return jsonify(health_checker.get_overall_health())

    @app.route('/metrics')
    @require_auth
    def get_metrics():
        """Get system metrics."""
        system_metrics = metrics_collector.get_metric_stats("system.cpu.percent")
        return jsonify({
            "system": system_metrics,
            "services": {
                name: service_registry.check_service_health(name)
                for name in service_registry.services.keys()
            },
            "timestamp": datetime.now().isoformat()
        })

    @app.route('/alerts')
    @require_auth
    def get_alerts():
        """Get active alerts."""
        # Mock alerts for now
        return jsonify({"alerts": [], "total": 0})

    # Core AI endpoints
    @app.route('/synthesize', methods=['POST'])
    @require_auth
    @monitor_request
    def synthesize():
        """Synchronous synthesis endpoint."""
        try:
            data = request.json
            internal_data = data.get('internalData', '').strip()
            external_data = data.get('externalData', '').strip()
            user_prompt = data.get('userPrompt', '').strip()
            mode = data.get('mode', 'STRATEGIC_SUMMARY')

            if not user_prompt:
                return jsonify({"error": "Synthesis prompt is required."}), 400

            # Get services
            model_router = service_registry.get_service('model_router')
            rag_engine = service_registry.get_service('rag_engine')

            # Construct payload and generate
            payload = _construct_payload(internal_data, external_data, user_prompt, mode)
            response = model_router.generate_with_payload(payload)

            # Record success metric
            metrics_collector.record_metric("ai.synthesis.success", 1)

            return jsonify({
                "response": response,
                "mode": mode,
                "timestamp": datetime.now().isoformat()
            }), 200

        except Exception as e:
            # Record error metric
            metrics_collector.record_metric("ai.synthesis.error", 1)
            log_aggregator.log_event("ERROR", f"Synthesis failed: {e}", "ai")
            return jsonify({"error": "Synthesis failed"}), 500

    @app.route('/synthesize-stream', methods=['POST'])
    @require_auth
    @monitor_request
    def synthesize_stream():
        """Streaming synthesis with enterprise features."""
        try:
            data = request.json
            internal_data = data.get('internalData', '').strip()
            external_data = data.get('externalData', '').strip()
            user_prompt = data.get('userPrompt', '').strip()
            mode = data.get('mode', 'STRATEGIC_SUMMARY')

            if not user_prompt:
                return jsonify({"error": "Synthesis prompt is required."}), 400

            # Get services
            model_router = service_registry.get_service('model_router')

            # Construct payload
            payload = _construct_payload(internal_data, external_data, user_prompt, mode)
            payload["stream"] = True

            def generate_stream():
                """Enterprise streaming handler."""
                headers = {
                    'Content-Type': 'application/json',
                    'x-goog-api-key': config.google_api_key,
                }

                try:
                    # Send metadata
                    yield f"data: {json.dumps({'type': 'metadata', 'mode': mode})}\n\n"

                    # Make streaming request
                    response = requests.post(
                        f"{config.api_url_base}:streamGenerateContent",
                        headers=headers,
                        data=json.dumps(payload),
                        timeout=config.request_timeout,
                        stream=True
                    )
                    response.raise_for_status()

                    full_response = ""
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                text = chunk.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                                if text:
                                    full_response += text
                                    yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"
                            except json.JSONDecodeError:
                                pass

                    # Quality validation
                    quality = _validate_output_quality(full_response, internal_data, external_data, mode)

                    # Send completion
                    yield f"data: {json.dumps({'type': 'done', 'quality': quality})}\n\n"

                except Exception as e:
                    log_aggregator.log_event("ERROR", f"Streaming error: {e}", "ai")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return Response(
                stream_with_context(generate_stream()),
                mimetype='text/event-stream',
                headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
            )

        except Exception as e:
            log_aggregator.log_event("ERROR", f"Stream setup error: {e}", "ai")
            return jsonify({"error": "Streaming setup failed"}), 500

    @app.route('/proactive/client-search', methods=['POST'])
    @require_auth
    @monitor_request
    def client_search():
        """Enterprise proactive client search."""
        try:
            data = request.json
            client_name = data.get('clientName', '').strip()

            if not client_name:
                return jsonify({"error": "Client name required"}), 400

            # Get proactive engine
            proactive_engine = service_registry.get_service('proactive_engine')

            # Generate insights
            insights = proactive_engine.generate_proactive_insights(client_name)

            # Publish event for analytics
            event_processor.publish_event("client_search", {
                "client_name": client_name,
                "timestamp": datetime.now().isoformat(),
                "insights_count": len(insights) if isinstance(insights, dict) else 1
            })

            return jsonify(insights), 200

        except Exception as e:
            log_aggregator.log_event("ERROR", f"Client search error: {e}", "proactive")
            return jsonify({"error": "Client search failed"}), 500

    @app.route('/ai/advanced-query', methods=['POST'])
    @require_auth
    @monitor_request
    def advanced_query():
        """Multi-agent advanced query processing."""
        try:
            data = request.json
            client_name = data.get('clientName', '').strip()
            query = data.get('query', '').strip()

            if not query:
                return jsonify({"error": "Query required"}), 400

            # Get agent orchestrator
            agent_orchestrator = service_registry.get_service('agent_orchestrator')

            # Process query
            result = agent_orchestrator.process_client_query(client_name, query)

            # Record analytics
            metrics_collector.record_metric("ai.advanced_query.count", 1)

            return jsonify(result), 200

        except Exception as e:
            log_aggregator.log_event("ERROR", f"Advanced query error: {e}", "ai")
            return jsonify({"error": "Advanced query failed"}), 500

    @app.route('/data/connectors', methods=['POST'])
    @require_auth
    @monitor_request
    def add_connector():
        """Add data connector."""
        try:
            data = request.json
            connector_type = data.get('type')
            config_data = data.get('config', {})

            if not connector_type:
                return jsonify({"error": "Connector type required"}), 400

            # Get data ingestion service
            data_service = service_registry.get_service('data_ingestion')

            # Add connector
            connector_id = data_service.add_connector(connector_type, config_data)

            return jsonify({"connector_id": connector_id, "status": "added"}), 201

        except Exception as e:
            log_aggregator.log_event("ERROR", f"Add connector error: {e}", "data")
            return jsonify({"error": "Failed to add connector"}), 500

    @app.route('/data/sync', methods=['POST'])
    @require_auth
    @monitor_request
    def sync_data():
        """Sync data from connectors."""
        try:
            # Get data ingestion service
            data_service = service_registry.get_service('data_ingestion')

            # Trigger sync
            sync_result = data_service.sync_all_connectors()

            return jsonify(sync_result), 200

        except Exception as e:
            log_aggregator.log_event("ERROR", f"Data sync error: {e}", "data")
            return jsonify({"error": "Data sync failed"}), 500

    @app.route('/analytics/realtime', methods=['GET'])
    @require_auth
    def get_realtime_analytics():
        """Get real-time analytics data."""
        try:
            # Get analytics data
            sentiment_trend = real_time_analytics.get_analytics_result("client_events", "sentiment_trend")
            activity_volume = real_time_analytics.get_analytics_result("client_events", "activity_volume")

            return jsonify({
                "sentiment_trend": sentiment_trend,
                "activity_volume": activity_volume,
                "timestamp": datetime.now().isoformat()
            }), 200
if config.enable_rag:
            rag_engine = RAGEngine()
            service_registry.register_service('rag_engine', rag_engine)
    except Exception as e:
        logger.warning(f"RAG Engine initialization failed: {e}")

    model_router = ModelRouter()
    service_registry.register_service('model_router', model_router)

    if config.redis_available:
        cache = SemanticCache()
        service_registry.register_service('cache', cache)

    # Proactive and Analytics Services
    try:
        if config.enable_proactive:
            rag_engine_instance = service_registry.get_service('rag_engine') if 'rag_engine' in service_registry.services else None
            proactive_engine = ProactiveEngine(rag_engine_instance, model_router)
            service_registry.register_service('proactive_engine', proactive_engine)
    except Exception as e:
        logger.warning(f"Proactive Engine initialization failed: {e}")

    try:
        data_ingestion = DataIngestionService()
        service_registry.register_service('data_ingestion', data_ingestion)
    except Exception as e:
        logger.warning(f"Data Ingestion initialization failed: {e}")

    try:
        agent_orchestrator = AgentOrchestrator(
            service_registry.get_service('proactive_engine') if 'proactive_engine' in service_registry.services else None,
            model_router
        )
        service_registry.register_service('agent_orchestrator', agent_orchestrator)
    except Exception as e:
        logger.warning(f"Agent Orchestrator initialization failed: {e}")

    try:
        continuous_learning = ContinuousLearning(model_router)
        service_registry.register_service('continuous_learning', continuous_learning)
    except Exception as e:
        logger.warning(f"Continuous Learning initialization failed: {e}"
    proactive_engine = ProactiveEngine(rag_engine if 'rag_engine' in service_registry.services else None, model_router)
    service_registry.register_service('proactive_engine', proactive_engine)

    data_ingestion = DataIngestionService()
    service_registry.register_service('data_ingestion', data_ingestion)

    agent_orchestrator = AgentOrchestrator(proactive_engine, model_router)
    service_registry.register_service('agent_orchestrator', agent_orchestrator)

    continuous_learning = ContinuousLearning(model_router)
    service_registry.register_service('continuous_learning', continuous_learning)

def _construct_payload(internal_data: str, external_data: str, user_prompt: str, mode: str) -> dict:
    """Construct AI model payload with enterprise features."""
    mode_config = _get_mode_config(mode)

    system_prompt = mode_config['system_prompt']
    max_tokens = mode_config['max_tokens']

    # Enhanced prompt engineering
    full_prompt = f"""
{system_prompt}

INPUT DATA:
Internal Data: {internal_data or 'No internal data provided'}
External Data: {external_data or 'No external data provided'}

USER QUERY: {user_prompt}

Please provide a comprehensive analysis following the synthesis approach above.
"""

    return {
        "contents": [{
            "parts": [{"text": full_prompt}],
            "role": "user"
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": max_tokens,
            "stopSequences": []
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }

def _get_mode_config(mode: str) -> dict:
    """Get configuration for synthesis mode."""
    configs = {
        "STRATEGIC_SUMMARY": {
            "system_prompt": "You are an enterprise strategic intelligence analyst...",
            "max_tokens": 2048
        },
        "DETAILED_ANALYSIS": {
            "system_prompt": "You are a detailed business analyst...",
            "max_tokens": 4096
        },
        "ACTION_ITEMS": {
            "system_prompt": "You are an action-oriented business consultant...",
            "max_tokens": 1536
        },
        "COMPARATIVE_ANALYSIS": {
            "system_prompt": "You are a comparative market analyst...",
            "max_tokens": 3072
        }
    }
    return configs.get(mode, configs["STRATEGIC_SUMMARY"])

def _validate_output_quality(re and ENTERPRISE_FEATURES_AVAILABLE:
        try:
            initialize_monitoring()
            logger.info("✅ Monitoring system initialized")
        except Exception as e:
            logger.warning(f"Monitoring initialization failed: {e}")

    if config.enable_worker_system and ENTERPRISE_FEATURES_AVAILABLE:
        try:
            initialize_enterprise_workers()
            logger.info("✅ Worker system initialized")
        except Exception as e:
            logger.warning(f"Worker system initialization failed: {e}")

    try:
        if ENTERPRISE_FEATURES_AVAILABLE:
            initialize_data_pipelines()
            logger.info("✅ Data pipelines initialized")
    except Exception as e:
        logger.warning(f"Data pipelines initialization failed: {e}")

    # Create and configure the application
    app = create_enterprise_app()

    # API Gateway integration
    if config.enable_api_gateway and ENTERPRISE_FEATURES_AVAILABLE:
        try:
            gateway_app = create_api_gateway_app()
            app.register_blueprint(gateway_app, url_prefix='/gateway')
            gateway.register_service("omni_core", "localhost", 5003)
            logger.info("✅ Service registered with API Gateway")
        except Exception as e:
            logger.warning(f"API Gateway initialization failed: {e}")

    mode = "ENTERPRISE" if ENTERPRISE_FEATURES_AVAILABLE else "MVP"
    logger.info(f"🎯 Omni-One AI Platform ready! (Mode: {mode})")
    logger.info(f"🌐 Server will run on http://0.0.0.0:5003")
    logger.info(f"🔑 API Gateway: {'Enabled' if config.enable_api_gateway and ENTERPRISE_FEATURES_AVAILABLE else 'Disabled'}")
    logger.info(f"⚙️  Worker System: {'Enabled' if config.enable_worker_system and ENTERPRISE_FEATURES_AVAILABLE else 'Disabled'}")
    logger.info(f"📊 Monitoring: {'Enabled' if config.enable_monitoring and ENTERPRISE_FEATURES_AVAILABLE else 'Disabled'}")
    logger.info(f"🗄️  Redis: {'Available' if config.redis_available else 'Unavailable
def bootstrap_enterprise_system():
    """Bootstrap the entire enterprise system."""

    logger.info("🚀 Bootstrapping Omni-One Enterprise AI Platform...")

    # Initialize infrastructure
    if config.enable_monitoring:
        initialize_monitoring()
        logger.info("✅ Monitoring system initialized")

    if config.enable_worker_system:
        initialize_enterprise_workers()
        logger.info("✅ Worker system initialized")

    initialize_data_pipelines()
    logger.info("✅ Data pipelines initialized")

    # Create and configure the application
    app = create_enterprise_app()

    # Register with API Gateway if enabled
    if config.enable_api_gateway:
        gateway.register_service("omni_core", "localhost", 5003)
        logger.info("✅ Service registered with API Gateway")

    logger.info("🎯 Omni-One Enterprise Platform ready!")
    logger.info(f"🌐 Server will run on http://0.0.0.0:5003")
    logger.info(f"🔑 API Gateway: {'Enabled' if config.enable_api_gateway else 'Disabled'}")
    logger.info(f"⚙️  Worker System: {'Enabled' if config.enable_worker_system else 'Disabled'}")
    logger.info(f"📊 Monitoring: {'Enabled' if config.enable_monitoring else 'Disabled'}")

    return app

# --- Main Entry Point ---
if __name__ == '__main__':
    # Bootstrap the enterprise system
    app = bootstrap_enterprise_system()

    # Start the server
    print("Omni-One Enterprise AI Platform running.")
    print("API Key loaded from GOOGLE_API_KEY environment variable.")
    print("Available enterprise endpoints:")
    print("  GET  /health - System health check")
    print("  GET  /metrics - System metrics")
    print("  POST /synthesize - Synchronous synthesis")
    print("  POST /synthesize-stream - Streaming synthesis")
    print("  POST /proactive/client-search - Client intelligence")
    print("  POST /ai/advanced-query - Multi-agent analysis")
    print("  POST /data/connectors - Add data connectors")
    print("  POST /data/sync - Sync enterprise data")
    print("  GET  /analytics/realtime - Real-time analytics")
    print("Listening on http://127.0.0.1:5003")

    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)
2. Extract strategic themes from both sources
3. Articulate the strategic imperative and competitive implications
4. Suggest 1-2 high-level strategic priorities

For every claim, cite [Internal Data] or [External Report].
Output concise, actionable strategic guidance. No pleasantries or introductions.
""",
        "temperature": 0.7,
        "max_tokens": 1024,
    },
    "DETAILED_ANALYSIS": {
        "display_name": "Detailed Analysis",
        "system_prompt": """
You are Omni, the Analytical Intelligence Engine. Your task is to provide a comprehensive analysis synthesizing [Internal Data] and [External Report].

Analysis approach:
1. Break down key findings from each source separately
2. Analyze interconnections and dependencies
3. Examine assumptions and limitations
4. Provide detailed supporting evidence for each claim
5. Highlight areas of uncertainty

For every claim, MUST cite [Internal Data] or [External Report] with specific evidence.
Output detailed, evidence-based analysis. No introductions or conclusions apart from analysis.
""",
        "temperature": 0.4,
        "max_tokens": 2500,
    },
    "ACTION_ITEMS": {
        "display_name": "Action Items & Recommendations",
        "system_prompt": """
You are Omni, the Operations Intelligence Engine. Your task is to synthesize [Internal Data] and [External Report] into concrete, prioritized actions.

Action synthesis approach:
1. Identify decision points that require action
2. For each decision point, recommend specific action(s)
3. Prioritize by impact and urgency
4. Include success metrics and timeline considerations
5. Flag dependencies and risks

For every action recommendation, cite supporting evidence [Internal Data] or [External Report].
Output numbered, prioritized action items with clear owners and success criteria.
Format: "1. [ACTION]: [What to do] | [Why] | [Success metric]"
""",
        "temperature": 0.6,
        "max_tokens": 2000,
    },
    "COMPARATIVE": {
        "display_name": "Comparative Analysis",
        "system_prompt": """
You are Omni, the Comparative Intelligence Engine. Your task is to synthesize [Internal Data] and [External Report] by directly comparing and contrasting findings.

Comparative approach:
1. Identify parallel topics/themes across both sources
2. Document explicit alignments (where sources agree)
3. Document critical contradictions (where sources conflict)
4. Analyze which contradictions are data-driven vs. methodological
5. Identify gaps (what's in one source but not the other?)
6. Synthesize integrated view where possible

Use clear comparative structure:
- Alignment: "[Finding] appears in both [Internal Data] and [External Report]..."
- Contradiction: "[Internal Data] shows X, while [External Report] shows Y..."
- Gap: "[External Report] addresses Y, but [Internal Data] does not..."

Output structured comparative analysis. No pleasantries.
""",
        "temperature": 0.5,
        "max_tokens": 2500,
    },
}

# --- Flask App Setup ---
app = Flask(__name__)
# Enable CORS to allow the frontend HTML file (running locally) to connect to the Flask server
CORS(app)

# --- Security & Rate Limiting ---
# limiter = Limiter(
#     app=app,
#     key_func=get_remote_address,
#     default_limits=["200 per day", "50 per hour"]
# )

# Enhanced logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# --- Authentication ---
API_KEY_HEADER = 'X-API-Key'
VALID_API_KEYS = os.getenv('VALID_API_KEYS', 'demo-key').split(',')

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get(API_KEY_HEADER)
        if not api_key or api_key not in VALID_API_KEYS:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

# --- Initialize AI Components ---
rag_engine = RAGEngine()
model_router = ModelRouter()
semantic_cache = SemanticCache()
ingestion_service = DataIngestionService(rag_engine)
proactive_engine = ProactiveEngine(rag_engine, model_router)

# Initialize advanced AI components
agent_orchestrator = AgentOrchestrator(model_router)
continuous_learning = ContinuousLearning(model_router)

# Register integration blueprint
integration_blueprint = init_integration_blueprint(proactive_engine)
app.register_blueprint(integration_blueprint, url_prefix='/integrations') 

# --- Helper Functions ---

def count_tokens(text):
    """Estimate token count for text. Uses tiktoken if available."""
    if encoding:
        return len(encoding.encode(text))
    # Fallback: rough estimate of 1 token per 4 chars
    return len(text) // 4

def estimate_response_time(output_tokens):
    """Estimate time to generate output_tokens at TOKENS_PER_SECOND rate."""
    return max(1, int(output_tokens / TOKENS_PER_SECOND))

def validate_output_quality(synthesis_text, internal_data, external_data, mode):
    """
    Validates synthesis output meets quality standards.
    Returns: {"passed": bool, "issues": [list], "score": 0-100}
    """
    issues = []

    # Check 1: Citation presence
    has_citations = bool(re.search(r'\[Internal Data\]|\[External Report\]', synthesis_text))
    if not has_citations:
        issues.append("No citations found")

    # Check 2: No conversational preamble
    has_preamble = bool(re.search(r'^(Sure|Certainly|Based on|Let me|I would|As requested)',
                                   synthesis_text, re.IGNORECASE | re.MULTILINE))
    if has_preamble:
        issues.append("Contains conversational preamble")

    # Check 3: Minimum content length
    if len(synthesis_text.strip()) < 100:
        issues.append("Output too brief")

    # Determine pass/fail
    passed = len(issues) == 0
    score = max(0, 100 - (len(issues) * 25))

    return {"passed": passed, "issues": issues, "score": score}

def construct_payload(internal_data, external_data, user_prompt, mode):
    """Constructs the Gemini API payload for the given synthesis mode."""
    mode_config = MODE_CONFIGS.get(mode, MODE_CONFIGS["STRATEGIC_SUMMARY"])

    parts = []
    if internal_data:
        parts.append({"text": f"DOCUMENT TITLE: [Internal Data]\n---\n{internal_data}"})
    if external_data:
        parts.append({"text": f"DOCUMENT TITLE: [External Report]\n---\n{external_data}"})
    parts.append({"text": f"SYNTHESIS PROMPT: {user_prompt}"})

    payload = {
        "contents": [{"parts": parts}],
        "systemInstruction": {"parts": [{"text": mode_config['system_prompt']}]},
        "generationConfig": {
            "temperature": mode_config['temperature'],
            "maxOutputTokens": mode_config['max_tokens'],
        }
    }
    return payload, mode_config

# --- Endpoints ---

@app.route('/modes', methods=['GET'])
def get_modes():
    """Returns available synthesis modes."""
    modes = [
        {"id": mode_id, "name": config["display_name"]}
        for mode_id, config in MODE_CONFIGS.items()
    ]
    return jsonify({"modes": modes}), 200

@app.route('/synthesize', methods=['POST'])
def synthesize():
    """Synchronous synthesis endpoint (legacy/fallback)."""
    try:
        data = request.json
        internal_data = data.get('internalData', '').strip()
        external_data = data.get('externalData', '').strip()
        user_prompt = data.get('userPrompt', '').strip()
        mode = data.get('mode', 'STRATEGIC_SUMMARY')

        if not user_prompt:
            return jsonify({"error": "Synthesis prompt is required."}), 400

        if mode not in MODE_CONFIGS:
            return jsonify({"error": f"Invalid mode: {mode}"}), 400

        # Check semantic cache
        cache_key = f"{internal_data}_{external_data}_{user_prompt}_{mode}"
        cached_result = semantic_cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result), 200

        # Use RAG if internal data provided
        if internal_data:
            rag_engine.add_documents([{'content': internal_data, 'source': 'internal'}])
            generated_text = rag_engine.generate_with_rag(user_prompt)
        else:
            # Use model router for multi-model support
            payload, mode_config = construct_payload(internal_data, external_data, user_prompt, mode)
            generated_text = model_router.generate(json.dumps(payload))

        if generated_text:
            # Quality validation
            quality = validate_output_quality(generated_text, internal_data, external_data, mode)
            result = {
                "insight": generated_text,
                "quality": quality
            }
            # Cache result
            semantic_cache.set(cache_key, result)
            return jsonify(result), 200
        else:
            return jsonify({"error": "Model response was empty or blocked."}), 500

    except requests.exceptions.Timeout:
        app.logger.error("Gemini API timeout")
        return jsonify({"error": "Request timeout. Please try again."}), 504
    except requests.exceptions.HTTPError as e:
        app.logger.error(f"Gemini API HTTP Error: {e.response.status_code}")
        return jsonify({"error": f"API error: {e.response.status_code}"}), 502
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "An unexpected error occurred on the server."}), 500

@app.route('/synthesize-stream', methods=['POST'])
def synthesize_stream():
    """Streaming synthesis endpoint with token-based time estimation."""
    data = request.json
    internal_data = data.get('internalData', '').strip()
    external_data = data.get('externalData', '').strip()
    user_prompt = data.get('userPrompt', '').strip()
    mode = data.get('mode', 'STRATEGIC_SUMMARY')

    if not user_prompt:
        return jsonify({"error": "Synthesis prompt is required."}), 400

    if mode not in MODE_CONFIGS:
        return jsonify({"error": f"Invalid mode: {mode}"}), 400

    payload, mode_config = construct_payload(internal_data, external_data, user_prompt, mode)

    # Add streaming flag
    payload["stream"] = True

    # Token counting for time estimation
    input_text = (internal_data or "") + (external_data or "") + user_prompt
    input_tokens = count_tokens(input_text)
    estimated_output_tokens = min(
        mode_config['max_tokens'],
        int(input_tokens * 1.5)  # Heuristic: output is ~1.5x input
    )
    estimated_time = estimate_response_time(estimated_output_tokens)

    def generate_stream():
        """Stream handler for Gemini API responses."""
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': API_KEY,
        }

        try:
            # Send metadata about time estimation
            yield f"data: {json.dumps({'type': 'metadata', 'estimated_time_seconds': estimated_time, 'input_tokens': input_tokens, 'estimated_output_tokens': estimated_output_tokens})}\n\n"

            # Make streaming API request
            response = requests.post(
                f"{API_URL_BASE}:streamGenerateContent",
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
                stream=True
            )
            response.raise_for_status()

            full_response = ""
            token_count = 0

            # Process streaming response
            for line in response.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        text = chunk.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        if text:
                            full_response += text
                            token_count += count_tokens(text)
                            yield f"data: {json.dumps({'type': 'content', 'text': text})}\n\n"
                    except json.JSONDecodeError:
                        pass

            # Quality validation
            quality = validate_output_quality(full_response, internal_data, external_data, mode)

            # Send completion
            yield f"data: {json.dumps({'type': 'done', 'total_tokens': token_count, 'quality': quality})}\n\n"

        except requests.exceptions.Timeout:
            app.logger.error("Gemini streaming API timeout")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Request timeout. Please try again.'})}\n\n"
        except requests.exceptions.HTTPError as e:
            app.logger.error(f"Gemini streaming API HTTP Error: {e.response.status_code}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'API error: {e.response.status_code}'})}\n\n"
        except Exception as e:
            app.logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred during streaming.'})}\n\n"

    return Response(
        stream_with_context(generate_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

@app.route('/synthesize-async', methods=['POST'])
def synthesize_async_endpoint():
    """Async synthesis endpoint."""
    try:
        data = request.json
        internal_data = data.get('internalData', '').strip()
        external_data = data.get('externalData', '').strip()
        user_prompt = data.get('userPrompt', '').strip()
        mode = data.get('mode', 'STRATEGIC_SUMMARY')

        if not user_prompt:
            return jsonify({"error": "Synthesis prompt is required."}), 400

        # Submit async task
        task = synthesize_async.delay(internal_data, external_data, user_prompt, mode)
        return jsonify({"task_id": task.id, "status": "pending"}), 202

    except Exception as e:
        app.logger.error(f"Async endpoint error: {e}")
        return jsonify({"error": "Failed to start async task"}), 500

@app.route('/data/connectors', methods=['POST'])
def add_connector():
    """Add a data connector."""
    try:
        data = request.json
        name = data['name']
        connector_type = data['type']
        config = data['config']

        ingestion_service.add_connector(name, connector_type, config)
        return jsonify({"message": f"Connector {name} added successfully"}), 201

    except Exception as e:
        app.logger.error(f"Add connector error: {e}")
        return jsonify({"error": "Failed to add connector"}), 500

@app.route('/data/sync', methods=['POST'])
def sync_data():
    """Sync data from connectors."""
    try:
        data = request.json
        connector_name = data.get('connector')

        if connector_name:
            count = ingestion_service.sync_connector(connector_name)
            return jsonify({"message": f"Synced {count} documents from {connector_name}"}), 200
        else:
            ingestion_service.sync_all()
            return jsonify({"message": "Synced all connectors"}), 200

    except Exception as e:
        app.logger.error(f"Sync error: {e}")
        return jsonify({"error": "Failed to sync data"}), 500

@app.route('/data/status', methods=['GET'])
def get_data_status():
    """Get data ingestion status."""
    try:
        status = ingestion_service.get_connector_status()
        return jsonify({"connectors": status}), 200

    except Exception as e:
        app.logger.error(f"Status error: {e}")
        return jsonify({"error": "Failed to get status"}), 500
@app.route('/proactive/client-search', methods=['POST'])
def client_search():
    """Proactive client information search using internal data."""
    try:
        data = request.json
        client_name = data.get('clientName', '').strip()

        # Use proactive engine for comprehensive analysis
        insights = proactive_engine.generate_proactive_insights(client_name)

        return jsonify(insights), 200

    except Exception as e:
        app.logger.error(f"Client search error: {e}")
        return jsonify({"error": "Failed to search client data"}), 500
def get_task_status(task_id):
    """Get status of async task."""
    task = synthesize_async.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {'state': task.state, 'status': 'Task is pending...'}
    elif task.state == 'PROGRESS':
        response = {'state': task.state, 'status': task.info.get('status', '')}
    elif task.state == 'SUCCESS':
        response = {'state': task.state, 'result': task.result}
    else:
        response = {'state': task.state, 'status': str(task.info)}
    return jsonify(response)
def advanced_client_query():
    """Advanced multi-agent client query processing."""
    data = request.json
    client_name = data.get('clientName', '').strip()
    query = data.get('query', '').strip()

    result = agent_orchestrator.process_client_query(client_name, query)
    return jsonify(result), 200

@app.route('/ai/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback for continuous learning."""
    try:
        data = request.json
        query = data.get('query', '')
        response = data.get('response', '')
        rating = data.get('rating', 3)
        user_feedback = data.get('feedback')

        continuous_learning.collect_feedback(query, response, rating, user_feedback)
        return jsonify({"message": "Feedback submitted successfully"}), 201

    except Exception as e:
        app.logger.error(f"Feedback submission error: {e}")
        return jsonify({"error": "Failed to submit feedback"}), 500

@app.route('/ai/learning-insights', methods=['GET'])
def get_learning_insights():
    """Get insights from continuous learning."""
    try:
        insights = continuous_learning.get_learning_insights()
        return jsonify(insights), 200

    except Exception as e:
        app.logger.error(f"Learning insights error: {e}")
        return jsonify({"error": "Failed to get learning insights"}), 500
if __name__ == '__main__':
    print("Omni Backend Server running.")
    print("API Key loaded from GOOGLE_API_KEY environment variable.")
    print("Available endpoints:")
    print("  GET  /modes - List available synthesis modes")
    print("  POST /synthesize - Synchronous synthesis")
    print("  POST /synthesize-stream - Streaming synthesis")
    print("  POST /synthesize-async - Async synthesis")
    print("  GET  /task/<task_id> - Get async task status")
    print("  POST /data/connectors - Add data connector")
    print("  POST /data/sync - Sync data from connectors")
    print("  POST /integrations/slack/webhook - Slack webhook")
    print("  POST /ai/advanced-query - Multi-agent client query")
    print("  POST /ai/feedback - Submit user feedback")
    print("  GET  /ai/learning-insights - Get learning insights")
    print("Listening on http://127.0.0.1:5003")
    app.run(host='0.0.0.0', port=5003, debug=False)
