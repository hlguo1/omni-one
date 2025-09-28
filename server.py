import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS


API_KEY = "AIzaSyBS9PDTwbEgRLcfpntMFzoLq66rqsAtmCE"

# --- Configuration ---

# Ensure the GEMINI_API_KEY environment variable is set before running
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

# The system instruction defines Omni's persona and rules for synthesis/citation
SYSTEM_PROMPT = """
You are Omni, The Knowledge Synthesis Engine. Your task is to analyze the provided documents (Internal Data and External Report) 
and synthesize a single, comprehensive, and actionable insight that answers the user's SYNTHESIS PROMPT. 
For every factual claim, data point, or strategy derived, you MUST provide a citation in brackets using the exact 
document title (either [Internal Data] or [External Report]). 
Focus on bridging high-level strategy and concrete, actionable outcomes. 
Do not use any introductory or concluding conversational phrases, just provide the synthesized insight.
"""

# --- Flask App Setup ---
app = Flask(__name__)
# Enable CORS to allow the frontend HTML file (running locally) to connect to the Flask server
CORS(app) 

@app.route('/synthesize', methods=['POST'])
def synthesize():
    """Handles the synthesis request from the frontend, calls the Gemini API, and returns the result."""
    if not API_KEY:
        return jsonify({"error": "Server error: GEMINI_API_KEY environment variable not set."}), 500

    try:
        data = request.json
        internal_data = data.get('internalData', '').strip()
        external_data = data.get('externalData', '').strip()
        user_prompt = data.get('userPrompt', '').strip()

        if not user_prompt:
            return jsonify({"error": "Synthesis prompt is required."}), 400
        
        # 1. Construct the full contents payload for the API
        parts = []

        if internal_data:
            parts.append({"text": f"DOCUMENT TITLE: [Internal Data]\n---\n{internal_data}"})
        if external_data:
            parts.append({"text": f"DOCUMENT TITLE: [External Report]\n---\n{external_data}"})
        
        parts.append({"text": f"SYNTHESIS PROMPT: {user_prompt}"})

        payload = {
            "contents": [{"parts": parts}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        }

        # 2. Make the API Call to Gemini
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': API_KEY,
        }
        
        response = requests.post(API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)

        result = response.json()
        generated_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')

        if generated_text:
            return jsonify({"insight": generated_text}), 200
        else:
            # Handle cases where the API returns a successful status but no text (e.g., content blocked)
            return jsonify({"error": "Model response was empty or blocked."}), 500

    except requests.exceptions.HTTPError as e:
        app.logger.error(f"Gemini API HTTP Error: {e.response.text}")
        return jsonify({"error": f"Gemini API communication failed: {e.response.status_code}"}), 502
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": f"An unexpected error occurred on the server: {str(e)}"}), 500

if __name__ == '__main__':
    print("Omni Backend Server running. Set GEMINI_API_KEY in your environment.")
    print("Listening on http://127.0.0.1:5003")
    # Setting host='0.0.0.0' allows access from network interfaces
    app.run(host='0.0.0.0', port=5003)
