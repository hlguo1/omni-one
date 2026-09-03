"""
Omni-One Enterprise AI Platform Server (Clean)
===============================================
Thin Flask shim for backward compatibility. Production traffic should use
FastAPI via `src/omni_one/api/fastapi_app.py` / `infra/fastapi_factory.py`.

This file is intentionally minimal and runnable: it resolves all historic
import errors, removes duplicated enterprise/mock blocks, and delegates
real intelligence to the 4-layer pipeline + ModelRouter + RAG.
"""
import os
import json
import time
import logging
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, Response, stream_with_context, g
from flask_cors import CORS

# --- Optional enterprise infra (graceful fallback) ---
try:
    from .infrastructure import gateway, create_api_gateway_app, initialize_enterprise_workers  # type: ignore
    from .infrastructure.pipelines import initialize_data_pipelines  # type: ignore
    from .infrastructure.monitoring import metrics_collector, health_checker, initialize_monitoring, AlertSeverity  # type: ignore
    ENTERPRISE_FEATURES_AVAILABLE = True
except ImportError:
    try:
        from infrastructure import gateway, create_api_gateway_app, initialize_enterprise_workers  # type: ignore
        from infrastructure.pipelines import initialize_data_pipelines  # type: ignore
        from infrastructure.monitoring import metrics_collector, health_checker, initialize_monitoring, AlertSeverity  # type: ignore
        ENTERPRISE_FEATURES_AVAILABLE = True
    except ImportError as _e:
        ENTERPRISE_FEATURES_AVAILABLE = False
        # Dummy shims so decorators don't fail
        class _DummyGateway:
            def register_service(self, *a, **kw): pass
        gateway = _DummyGateway()
        create_api_gateway_app = lambda: None  # type: ignore
        initialize_enterprise_workers = lambda: True  # type: ignore
        initialize_data_pipelines = lambda: True  # type: ignore
        initialize_monitoring = lambda: True  # type: ignore
        class _DummyMetrics:
            def record_metric(self, *a, **kw): pass
            def get_metric_stats(self, *a, **kw): return {}
        metrics_collector = _DummyMetrics()
        class _DummyHealth:
            def get_overall_health(self): return {"status": "healthy", "mode": "mvp", "enterprise": False}
        health_checker = _DummyHealth()
        class _DummySeverity:
            INFO = "info"; WARNING = "warning"; ERROR = "error"; CRITICAL = "critical"
        AlertSeverity = _DummySeverity

# --- Core AI components (robust imports) ---
try:
    from .core.rag_engine import RAGEngine  # type: ignore
    from .core.model_router import ModelRouter  # type: ignore
    from .core.cache import SemanticCache  # type: ignore
    from .agents.proactive.engine import ProactiveEngine  # type: ignore
    from .data.connectors.ingestion import DataIngestionService  # type: ignore
    from .models.agent_orchestrator import AgentOrchestrator  # type: ignore
    from .models.continuous_learning import ContinuousLearning  # type: ignore
except ImportError:
    try:
        from core.rag_engine import RAGEngine  # type: ignore
        from core.model_router import ModelRouter  # type: ignore
        from core.cache import SemanticCache  # type: ignore
        from agents.proactive.engine import ProactiveEngine  # type: ignore
        from data.connectors.ingestion import DataIngestionService  # type: ignore
        from models.agent_orchestrator import AgentOrchestrator  # type: ignore
        from models.continuous_learning import ContinuousLearning  # type: ignore
    except ImportError:
        # Last-resort flat imports (for legacy scripts that set PYTHONPATH=src/omni_one)
        from rag_engine import RAGEngine  # type: ignore
        from model_router import ModelRouter  # type: ignore
        from cache import SemanticCache  # type: ignore
        from proactive_agents.engine import ProactiveEngine  # type: ignore
        from data_connectors.ingestion import DataIngestionService  # type: ignore
        from integrations.webhooks import init_integration_blueprint as _unused  # type: ignore
        from models.agent_orchestrator import AgentOrchestrator  # type: ignore
        from models.continuous_learning import ContinuousLearning  # type: ignore

try:
    from .data.integrations.webhooks import init_integration_blueprint  # type: ignore
except ImportError:
    try:
        from data.integrations.webhooks import init_integration_blueprint  # type: ignore
    except ImportError:
        init_integration_blueprint = lambda engine: type("BP", (), {"register": lambda *a, **kw: None})()  # type: ignore

import redis
import psutil
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
class EnterpriseConfig:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "demo-key"
        self.api_url_base = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20"
        self.gemini_model = "gemini-2.5-flash-preview-05-20"
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.enable_api_gateway = os.getenv("ENABLE_API_GATEWAY", "false").lower() == "true"
        self.enable_worker_system = os.getenv("ENABLE_WORKER_SYSTEM", "false").lower() == "true"
        self.enable_monitoring = os.getenv("ENABLE_MONITORING", "false").lower() == "true"
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.redis_client = None
            self.redis_available = False
        self.valid_api_keys = set(os.getenv("VALID_API_KEYS", "demo-key,test-key").split(","))
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "50"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))
        self.streaming_chunk_size = int(os.getenv("STREAMING_CHUNK_SIZE", "1024"))
        self.enable_rag = os.getenv("ENABLE_RAG", "true").lower() == "true"
        self.enable_proactive = os.getenv("ENABLE_PROACTIVE", "true").lower() == "true"
        self.enable_analytics = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"

config = EnterpriseConfig()

class EnterpriseServiceRegistry:
    def __init__(self):
        self.services = {}
    def register_service(self, name: str, svc, health_check=None):
        self.services[name] = {"instance": svc, "health_check": health_check, "registered_at": datetime.now(), "status": "healthy"}
        logger.info(f"Registered service: {name}")
    def get_service(self, name: str):
        if name not in self.services:
            raise RuntimeError(f"Service {name} not registered")
        return self.services[name]["instance"]
    def check_service_health(self, name: str) -> bool:
        if name not in self.services:
            return False
        hc = self.services[name].get("health_check")
        if hc:
            try: return bool(hc())
            except Exception: return False
        return True

service_registry = EnterpriseServiceRegistry()

class EnterpriseSecurity:
    def __init__(self): self.rate_limit_cache = {}
    def authenticate_request(self, api_key: str) -> bool: return api_key in config.valid_api_keys
    def check_rate_limit(self, client_id: str) -> bool:
        now = time.time(); win = now - config.rate_limit_window
        self.rate_limit_cache[client_id] = [t for t in self.rate_limit_cache.get(client_id, []) if t > win]
        if len(self.rate_limit_cache[client_id]) >= config.rate_limit_requests: return False
        self.rate_limit_cache[client_id].append(now); return True
    def get_client_id(self, req) -> str:
        api_key = req.headers.get("X-API-Key") or req.headers.get("Authorization","").replace("Bearer ","")
        return api_key or req.remote_addr or "anonymous"

security = EnterpriseSecurity()

def require_auth(f):
    @wraps(f)
    def wrapper(*a, **kw):
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization","").replace("Bearer ","")
        if not api_key: return jsonify({"error": "API key required", "code": "AUTHENTICATION_FAILED"}), 401
        if not security.authenticate_request(api_key): return jsonify({"error": "Invalid API key", "code": "AUTHENTICATION_FAILED"}), 401
        if not security.check_rate_limit(security.get_client_id(request)): return jsonify({"error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"}), 429
        g.client_id = security.get_client_id(request)
        return f(*a, **kw)
    return wrapper

def monitor_request(f):
    @wraps(f)
    def wrapper(*a, **kw):
        start = time.time(); endpoint = request.endpoint or "unknown"; method=request.method
        try: response = f(*a, **kw); status = response[1] if isinstance(response, tuple) else 200
        except Exception: status=500; raise
        finally:
            dur=time.time()-start
            try: metrics_collector.record_metric("api.request.duration", dur, {"endpoint": endpoint, "method": method})
            except Exception: pass
        return response
    return wrapper

# --- Synthesis helpers ---
MODE_CONFIGS = {
    "STRATEGIC_SUMMARY": {"system_prompt": "You are an enterprise strategic intelligence analyst. Synthesize [Internal Data] and [External Report] into executive guidance. For every claim cite [Internal Data] or [External Report]. Output concise strategic priorities.", "max_tokens": 1024, "display_name": "Strategic Summary"},
    "DETAILED_ANALYSIS": {"system_prompt": "You are an analytical engine. For every claim cite [Internal Data] or [External Report] with evidence. Break down findings, interconnections, assumptions, and uncertainties.", "max_tokens": 2500, "display_name": "Detailed Analysis"},
    "ACTION_ITEMS": {"system_prompt": "You are an operations consultant. For every action cite [Internal Data] or [External Report]. Output numbered prioritized actions: '1. [ACTION]: [what] | [why] | [success metric]'.", "max_tokens": 2000, "display_name": "Action Items"},
    "COMPARATIVE": {"system_prompt": "You are a comparative analyst. Structure: Alignment, Contradiction, Gap. For every point cite [Internal Data] or [External Report].", "max_tokens": 2500, "display_name": "Comparative"},
}

def _get_mode_config(mode: str) -> dict:
    return MODE_CONFIGS.get(mode, MODE_CONFIGS["STRATEGIC_SUMMARY"])

def _construct_payload(internal_data: str, external_data: str, user_prompt: str, mode: str) -> dict:
    cfg = _get_mode_config(mode)
    prompt = f"{cfg['system_prompt']}\n\nInternal Data: {internal_data or 'No internal data'}\nExternal Data: {external_data or 'No external data'}\nUSER QUERY: {user_prompt}\n"
    return {"contents": [{"parts": [{"text": prompt}], "role": "user"}], "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": cfg["max_tokens"]}}

def _validate_output_quality(text: str, internal_data: str, external_data: str, mode: str) -> dict:
    import re
    issues=[]
    if not re.search(r"\[Internal Data\]|\[External Report\]", text): issues.append("No citations found")
    if re.search(r"^(Sure|Certainly|Based on|Let me|I would|As requested)", text, re.I | re.M): issues.append("Contains conversational preamble")
    if len(text.strip()) < 100: issues.append("Output too brief")
    passed=len(issues)==0
    return {"passed": passed, "issues": issues, "score": max(0, 100-len(issues)*25)}

# --- App factory ---
def _initialize_enterprise_services():
    # RAG
    if config.enable_rag:
        try:
            rag = RAGEngine()
            service_registry.register_service("rag_engine", rag)
        except Exception as e: logger.warning(f"RAG init failed: {e}")
    # Model router (always)
    try:
        router = ModelRouter()
        service_registry.register_service("model_router", router)
    except Exception as e: logger.warning(f"ModelRouter init failed: {e}")
    # Cache
    if config.redis_available:
        try:
            cache = SemanticCache()
            service_registry.register_service("cache", cache)
        except Exception as e: logger.warning(f"Cache init failed: {e}")
    # Proactive
    if config.enable_proactive:
        try:
            rag_inst = service_registry.services.get("rag_engine", {}).get("instance")
            router_inst = service_registry.get_service("model_router")
            eng = ProactiveEngine(rag_inst, router_inst)
            service_registry.register_service("proactive_engine", eng)
        except Exception as e: logger.warning(f"ProactiveEngine init failed: {e}")
    # Data ingestion
    try:
        ingestion = DataIngestionService()
        service_registry.register_service("data_ingestion", ingestion)
    except Exception as e: logger.warning(f"DataIngestion init failed: {e}")
    # Agent orchestrator and continuous learning (optional)
    try:
        pro = service_registry.services.get("proactive_engine", {}).get("instance")
        router_inst = service_registry.services.get("model_router", {}).get("instance")
        if pro and router_inst:
            from .models.agent_orchestrator import AgentOrchestrator as AO  # type: ignore
            ao = AO(pro, router_inst)
            service_registry.register_service("agent_orchestrator", ao)
    except Exception as e: logger.warning(f"AgentOrchestrator init failed: {e}")
    try:
        router_inst = service_registry.services.get("model_router", {}).get("instance")
        if router_inst:
            from .models.continuous_learning import ContinuousLearning as CL  # type: ignore
            cl = CL(router_inst)
            service_registry.register_service("continuous_learning", cl)
    except Exception as e: logger.warning(f"ContinuousLearning init failed: {e}")

def create_enterprise_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.logger.setLevel(logging.INFO)
    _initialize_enterprise_services()

    # Integrations blueprint (optional)
    try:
        pe = service_registry.services.get("proactive_engine", {}).get("instance")
        if pe:
            bp = init_integration_blueprint(pe)
            # Flask blueprint compatibility: some stubs return dummy
            if hasattr(bp, "name"):
                app.register_blueprint(bp, url_prefix="/integrations")
    except Exception as e:
        logger.warning(f"Integration blueprint failed: {e}")

    @app.route("/health")
    def health_check():
        try: return jsonify(health_checker.get_overall_health())
        except Exception as e: return jsonify({"status": "degraded", "error": str(e)}), 200

    @app.route("/metrics")
    @require_auth
    def get_metrics():
        try:
            sys_metrics = {}
            try: sys_metrics = metrics_collector.get_metric_stats("system.cpu.percent")
            except Exception: pass
            return jsonify({"system": sys_metrics, "services": {n: service_registry.check_service_health(n) for n in service_registry.services}, "timestamp": datetime.now().isoformat()}), 200
        except Exception as e: return jsonify({"error": str(e)}), 500

    @app.route("/synthesize", methods=["POST"])
    @require_auth
    @monitor_request
    def synthesize():
        try:
            data = request.json or {}
            internal_data = (data.get("internalData") or "").strip()
            external_data = (data.get("externalData") or "").strip()
            user_prompt = (data.get("userPrompt") or "").strip()
            mode = data.get("mode", "STRATEGIC_SUMMARY")
            if not user_prompt: return jsonify({"error": "Synthesis prompt is required."}), 400
            if mode not in MODE_CONFIGS: return jsonify({"error": f"Invalid mode: {mode}"}), 400
            # Check cache if available
            try:
                cache = service_registry.services.get("cache", {}).get("instance")
                if cache:
                    key = f"{internal_data}_{external_data}_{user_prompt}_{mode}"
                    cached = cache.get(key)
                    if cached: return jsonify(cached), 200
            except Exception: pass
            router = service_registry.get_service("model_router")
            rag = service_registry.services.get("rag_engine", {}).get("instance")
            if internal_data and rag:
                try:
                    rag.add_documents([{"content": internal_data, "source": "internal"}])
                    generated = rag.generate_with_rag(user_prompt)
                except Exception:
                    payload = _construct_payload(internal_data, external_data, user_prompt, mode)
                    generated = router.generate_with_payload(payload)
            else:
                payload = _construct_payload(internal_data, external_data, user_prompt, mode)
                generated = router.generate_with_payload(payload)
            if not generated: return jsonify({"error": "Model response empty"}), 500
            quality = _validate_output_quality(generated, internal_data, external_data, mode)
            result = {"insight": generated, "quality": quality}
            try:
                cache = service_registry.services.get("cache", {}).get("instance")
                if cache: cache.set(f"{internal_data}_{external_data}_{user_prompt}_{mode}", result)
            except Exception: pass
            try: metrics_collector.record_metric("ai.synthesis.success", 1)
            except Exception: pass
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            try: metrics_collector.record_metric("ai.synthesis.error", 1)
            except Exception: pass
            return jsonify({"error": "Synthesis failed"}), 500

    @app.route("/synthesize-stream", methods=["POST"])
    @require_auth
    @monitor_request
    def synthesize_stream():
        try:
            data = request.json or {}
            internal_data = (data.get("internalData") or "").strip()
            external_data = (data.get("externalData") or "").strip()
            user_prompt = (data.get("userPrompt") or "").strip()
            mode = data.get("mode", "STRATEGIC_SUMMARY")
            if not user_prompt: return jsonify({"error": "Synthesis prompt required"}), 400
            if mode not in MODE_CONFIGS: return jsonify({"error": f"Invalid mode: {mode}"}), 400
            router = service_registry.get_service("model_router")
            payload = _construct_payload(internal_data, external_data, user_prompt, mode)
            payload["stream"] = True
            def generate_stream():
                headers = {"Content-Type": "application/json", "x-goog-api-key": config.google_api_key}
                try:
                    yield f"data: {json.dumps({'type': 'metadata', 'mode': mode})}\n\n"
                    try:
                        resp = requests.post(f"{config.api_url_base}:streamGenerateContent", headers=headers, data=json.dumps(payload), timeout=config.request_timeout, stream=True)
                        resp.raise_for_status()
                        full=""
                        for line in resp.iter_lines():
                            if line:
                                try:
                                    chunk=json.loads(line)
                                    text=chunk.get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","")
                                    if text: full+=text; yield f"data: {json.dumps({'type':'content','text':text})}\n\n"
                                except json.JSONDecodeError: pass
                        quality=_validate_output_quality(full, internal_data, external_data, mode)
                        yield f"data: {json.dumps({'type':'done','quality':quality})}\n\n"
                    except requests.exceptions.RequestException as re_err:
                        # Fallback to non-streaming generation
                        fallback = router.generate_with_payload(payload)
                        yield f"data: {json.dumps({'type':'content','text': fallback})}\n\n"
                        yield f"data: {json.dumps({'type':'done','quality': _validate_output_quality(fallback, internal_data, external_data, mode)})}\n\n"
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    yield f"data: {json.dumps({'type':'error','message': str(e)})}\n\n"
            return Response(stream_with_context(generate_stream()), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        except Exception as e:
            logger.error(f"Stream setup error: {e}")
            return jsonify({"error": "Streaming setup failed"}), 500

    @app.route("/proactive/client-search", methods=["POST"])
    @require_auth
    @monitor_request
    def client_search():
        try:
            data = request.json or {}
            client_name = (data.get("clientName") or "").strip()
            if not client_name: return jsonify({"error": "Client name required"}), 400
            pe = service_registry.get_service("proactive_engine")
            insights = pe.generate_proactive_insights(client_name)
            return jsonify(insights), 200
        except Exception as e:
            logger.error(f"Client search error: {e}")
            return jsonify({"error": "Client search failed"}), 500

    @app.route("/ai/advanced-query", methods=["POST"])
    @require_auth
    @monitor_request
    def advanced_query():
        try:
            data = request.json or {}
            query = (data.get("query") or "").strip()
            client_name = (data.get("clientName") or "").strip()
            if not query: return jsonify({"error": "Query required"}), 400
            ao = service_registry.get_service("agent_orchestrator")
            result = ao.process_client_query(client_name, query)
            try: metrics_collector.record_metric("ai.advanced_query.count", 1)
            except Exception: pass
            return jsonify(result), 200
        except Exception as e:
            logger.error(f"Advanced query error: {e}")
            return jsonify({"error": "Advanced query failed"}), 500

    @app.route("/data/connectors", methods=["POST"])
    @require_auth
    @monitor_request
    def add_connector():
        try:
            data = request.json or {}
            dtype = data.get("type")
            if not dtype: return jsonify({"error": "Connector type required"}), 400
            svc = service_registry.get_service("data_ingestion")
            cfg = data.get("config", {})
            cid = svc.add_connector(dtype, cfg) if hasattr(svc, "add_connector") else "mock-id"
            return jsonify({"connector_id": cid, "status": "added"}), 201
        except Exception as e:
            logger.error(f"Add connector error: {e}")
            return jsonify({"error": "Failed to add connector"}), 500

    @app.route("/data/sync", methods=["POST"])
    @require_auth
    @monitor_request
    def sync_data():
        try:
            svc = service_registry.get_service("data_ingestion")
            res = svc.sync_all_connectors() if hasattr(svc, "sync_all_connectors") else svc.sync_all() if hasattr(svc, "sync_all") else {"status": "no-op"}
            return jsonify(res), 200
        except Exception as e:
            logger.error(f"Data sync error: {e}")
            return jsonify({"error": "Data sync failed"}), 500

    @app.route("/analytics/realtime", methods=["GET"])
    @require_auth
    def realtime_analytics():
        return jsonify({"status": "not_configured", "message": "Realtime analytics requires streaming_processor", "timestamp": datetime.now().isoformat()}), 200

    # --- Light enterprise stubs (explicitly marked as LABS) ---
    @app.route("/ai/multimodal/analyze", methods=["POST"])
    @require_auth
    def multimodal_analysis():
        return jsonify({"status": "labs", "message": "Multimodal is labs; text+numeric is production path. See packs/revenue_ops.py", "result": {"text_analysis": "stub"}}), 200

    @app.route("/ethical/monitor", methods=["POST"])
    @require_auth
    def ethical_monitor():
        try:
            data = request.json or {}
            # Proxy to real EthicalMonitor if available
            from .enterprise.ethical_ai import EthicalMonitor as EM  # type: ignore
            em = EM()
            out = em.analyze_decision(data.get("model_output", data), data.get("input_data", {}), data.get("context", "general"))
            return jsonify(out), 200
        except Exception as e: return jsonify({"error": str(e)}), 500

    @app.route("/quantum/optimize", methods=["POST"])
    @require_auth
    def quantum_optimize():
        return jsonify({"status": "labs", "message": "Quantum optimizer is research preview. Use deterministic pipeline for production."}), 200

    @app.route("/federated/train", methods=["POST"])
    @require_auth
    def federated_train():
        return jsonify({"status": "labs", "message": "Federated learning is research preview."}), 200

    return app

# --- Bootstrap helpers for scripts ---
def bootstrap_enterprise_system():
    logger.info("Initializing Omni-One (clean Flask shim)...")
    if config.enable_monitoring and ENTERPRISE_FEATURES_AVAILABLE:
        try: initialize_monitoring()
        except Exception as e: logger.warning(f"Monitoring init failed: {e}")
    if config.enable_worker_system and ENTERPRISE_FEATURES_AVAILABLE:
        try: initialize_enterprise_workers()
        except Exception as e: logger.warning(f"Workers init failed: {e}")
    if ENTERPRISE_FEATURES_AVAILABLE:
        try: initialize_data_pipelines()
        except Exception as e: logger.warning(f"Pipelines init failed: {e}")
    app = create_enterprise_app()
    if config.enable_api_gateway and ENTERPRISE_FEATURES_AVAILABLE:
        try:
            bp = create_api_gateway_app()
            if bp: app.register_blueprint(bp, url_prefix="/gateway")
            gateway.register_service("omni_core", "localhost", 5003)
        except Exception as e: logger.warning(f"Gateway init failed: {e}")
    mode = "ENTERPRISE" if ENTERPRISE_FEATURES_AVAILABLE else "MVP"
    logger.info(f"Omni-One ready (mode={mode}) on http://0.0.0.0:5003")
    logger.info(f"Redis: {'Available' if config.redis_available else 'Unavailable (memory fallback)'}")
    return app

if __name__ == "__main__":
    app = bootstrap_enterprise_system()
    print("Omni-One Enterprise AI Platform running (clean).")
    print("Endpoints: GET /health, POST /synthesize, POST /synthesize-stream, POST /proactive/client-search")
    print("Prod FastAPI: uvicorn src.omni_one.api.fastapi_app:create_omni_one_app --factory --port 5003")
    print("Listening on http://127.0.0.1:5003")
    app.run(host="0.0.0.0", port=5003, debug=False, threaded=True)
