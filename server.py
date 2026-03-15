import os
import json
import re
import time
import requests
import tiktoken
import logging
from functools import wraps
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from rag_engine import RAGEngine
from model_router import ModelRouter
from cache import SemanticCache
from async_tasks import synthesize_async
from data_connectors.ingestion import DataIngestionService
from proactive_agents.engine import ProactiveEngine
from integrations.webhooks import init_integration_blueprint
from models.agent_orchestrator import AgentOrchestrator
from models.continuous_learning import ContinuousLearning

# --- Security: Load API Key from Environment ---
API_KEY = os.getenv('GOOGLE_API_KEY')
if not API_KEY:
    raise RuntimeError(
        "CRITICAL: GOOGLE_API_KEY environment variable not set. "
        "Please set it before running the server. "
        "Example: export GOOGLE_API_KEY='your-key-here'"
    )

# --- Configuration ---
API_URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
TOKENS_PER_SECOND = 100  # Baseline estimate for Gemini Flash streaming

# Token encoder for estimation
try:
    # Fallback to generic encoding since tiktoken may not have exact Gemini encoding
    encoding = tiktoken.get_encoding("cl100k_base")
except:
    encoding = None

# --- Synthesis Mode Configurations (Phase 3) ---
MODE_CONFIGS = {
    "STRATEGIC_SUMMARY": {
        "display_name": "Strategic Summary",
        "system_prompt": """
You are Omni, the Strategic Intelligence Engine. Your task is to synthesize [Internal Data] and [External Report] into a concise, executive-level insight that highlights strategic priorities and implications.

Synthesis approach:
1. Identify the core business question implied by the data
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
