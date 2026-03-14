# Omni – The AI-Native Knowledge Synthesis Engine

**Production-grade AI intelligence layer for corporate knowledge synthesis with streaming responses, multi-mode analysis, and citation-driven insights.**

## Overview

Omni is an advanced knowledge synthesis engine that analyzes multiple data sources (internal reports, external market intelligence, competitive analysis) and synthesizes actionable insights with enforced citations. Unlike traditional document analysis tools, Omni uses specialized AI prompts for different analysis modes and streams responses in real-time with progress indicators.

**Key Features:**
- 🎯 **4 Synthesis Modes**: Strategic Summary, Detailed Analysis, Action Items, Comparative Analysis
- ⚡ **Real-Time Streaming**: Token-based progress estimation with live streaming responses
- 🔗 **Citation Enforcement**: Every insight is backed by source attribution (`[Internal Data]` or `[External Report]`)
- 🛡️ **Enterprise Ready**: Secure API key management, quality validation, robust error handling
- 🔀 **Multi-Source Intelligence**: Bridge internal metrics with external market data seamlessly
- 🎨 **Modern UI**: Clean, responsive interface with progress visualization

## Quick Start

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Node.js or a modern web browser (frontend only)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/omni-one.git
   cd omni-one
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API Key**
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env` and add your Google Gemini API key:
     ```
     GOOGLE_API_KEY=your-actual-api-key-here
     ```
   - Get a free API key from [Google AI Studio](https://aistudio.google.com/app/apikeys)

4. **Start the backend server**
   ```bash
   python server.py
   ```
   You should see:
   ```
   Omni Backend Server running.
   API Key loaded from GOOGLE_API_KEY environment variable.
   Available endpoints:
     GET  /modes - List available synthesis modes
     POST /synthesize - Synchronous synthesis
     POST /synthesize-stream - Streaming synthesis
   Listening on http://127.0.0.1:5003
   ```

5. **Open the frontend**
   - Open `index.html` in your web browser
   - Or serve it via a local server:
     ```bash
     python -m http.server 8000
     # Then open http://localhost:8000/index.html
     ```

## Usage

### Basic Workflow

1. **Input Data Sources**
   - Paste internal data (e.g., Q3 metrics, company financials, product roadmap)
   - Paste external report (e.g., market analysis, competitor updates, industry trends)

2. **Select Analysis Mode**
   - **Strategic Summary**: High-level insights and competitive implications
   - **Detailed Analysis**: Comprehensive breakdown with supporting evidence
   - **Action Items**: Concrete, prioritized recommendations with success metrics
   - **Comparative Analysis**: Compare and contrast findings across sources

3. **Ask a Question**
   - Example: "Based on our Q3 performance and the market report, what are the top 3 product gaps causing us to lose market share?"

4. **Review Results**
   - Watch the progress bar with real-time token counting
   - See the synthesis appear live with citations
   - Review quality indicators if there are any warnings

## Synthesis Modes Explained

### 1. Strategic Summary
**Best for:** Executive briefings, decision-making, strategic planning

Omni identifies the core business question, extracts strategic themes, and articulates competitive implications. Outputs are concise, 1-2 high-level strategic priorities with citations.

```
Example Output:
"Our Q3 decline [Internal Data] combined with market growth [External Report]
indicates competitive displacement rather than market downfall. Strategic priority:
Audit product-market fit against emerging competitors [External Report]."
```

### 2. Detailed Analysis
**Best for:** Deep dives, comprehensive research, complex decision validation

Provides separate breakdowns of each source, interconnections, assumptions, and detailed evidence chains with explicit citations for every claim.

```
Example Output:
"Internal Analysis: Revenue dropped 12% Q3-Q4 [Internal Data]...
Market Context: Industry grew 8% in same period [External Report]...
Key Insight: We're losing to product X, which dominates on feature Y [External Report]..."
```

### 3. Action Items
**Best for:** Execution planning, resource allocation, performance management

Synthesizes decision points into numbered, prioritized actions with success metrics and timeline considerations. Each action is backed by supporting evidence.

```
Example Output:
"1. AUDIT PRODUCT-MARKET FIT: Compare our top features against competitor X
   [External Report] | Why: We're #2 in adopter surveys [Internal Data] |
   Success metric: Identify top 5 feature gaps within 2 weeks"
```

### 4. Comparative Analysis
**Best for:** Gap analysis, contradiction resolution, integrated insights

Documents explicit alignments, critical contradictions, and gaps between sources. Analyzes whether contradictions are data-driven or methodological.

```
Example Output:
"Alignment: Both sources show market growth [Internal Data] [External Report]
Contradiction: Internal data shows us losing share, but external report calls us
'stable player' [Internal Data vs External Report]
Gap: External report discusses AI features but our internal roadmap doesn't mention them..."
```

## API Endpoints

### GET /modes
Returns available synthesis modes.

```json
{
  "modes": [
    {"id": "STRATEGIC_SUMMARY", "name": "Strategic Summary"},
    {"id": "DETAILED_ANALYSIS", "name": "Detailed Analysis"},
    {"id": "ACTION_ITEMS", "name": "Action Items & Recommendations"},
    {"id": "COMPARATIVE", "name": "Comparative Analysis"}
  ]
}
```

### POST /synthesize
Synchronous synthesis (immediate response, no streaming).

**Request:**
```json
{
  "internalData": "Q3 financial metrics...",
  "externalData": "Market analysis report...",
  "userPrompt": "What are our biggest gaps?",
  "mode": "STRATEGIC_SUMMARY"
}
```

**Response:**
```json
{
  "insight": "Our market share decline [Internal Data]...",
  "quality": {
    "passed": true,
    "issues": [],
    "score": 100
  }
}
```

### POST /synthesize-stream
Streaming synthesis with token-based progress estimation.

**Request:** (same as /synthesize)

**Response:** Server-Sent Events (SSE) stream
```
data: {"type": "metadata", "estimated_time_seconds": 12, "input_tokens": 450, "estimated_output_tokens": 500}

data: {"type": "content", "text": "Our market share"}

data: {"type": "content", "text": " decline [Internal Data]"}

data: {"type": "done", "total_tokens": 950, "quality": {"passed": true, "issues": [], "score": 100}}
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Frontend (index.html)                  │
│  - Mode selector, input forms, streaming response UI     │
│  - ReadableStream handler for real-time display          │
│  - Progress bar with token-based estimation              │
└────────────────────┬────────────────────────────────────┘
                     │ XHR / Fetch
                     │
┌────────────────────▼────────────────────────────────────┐
│          Backend (server.py - Flask)                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Routes:                                          │  │
│  │ - GET /modes: List synthesis modes               │  │
│  │ - POST /synthesize: Sync synthesis (fallback)    │  │
│  │ - POST /synthesize-stream: Streaming synthesis   │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Core Functions:                                  │  │
│  │ - count_tokens: Token estimation with tiktoken   │  │
│  │ - estimate_response_time: Time calculation       │  │
│  │ - validate_output_quality: Citation & QA checks  │  │
│  │ - construct_payload: Mode-specific prompt setup  │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS
                     │
┌────────────────────▼────────────────────────────────────┐
│        Google Generative AI API (Gemini)                │
│  - Model: gemini-2.5-flash-preview-05-20                │
│  - Stream: Yes (for /synthesize-stream)                 │
│  - Temperature: Mode-dependent (0.4-0.7)               │
└─────────────────────────────────────────────────────────┘
```

## Configuration

### Mode Configurations (server.py)

Each mode has its own:
- **system_prompt**: Detailed instructions for analysis style
- **temperature**: Creativity level (0.3=analytical, 0.7=creative)
- **max_tokens**: Output length limit

Customize modes in `MODE_CONFIGS` dictionary in `server.py`.

### Environment Variables

```env
# Required
GOOGLE_API_KEY=your-google-gemini-api-key

# Optional (defaults to 127.0.0.1:5003)
FLASK_HOST=0.0.0.0
FLASK_PORT=5003
```

## Quality Assurance

Omni includes built-in output validation:

1. **Citation Presence**: Every response must include `[Internal Data]` or `[External Report]`
2. **Content Quality**: Minimum 100 characters, maximum 5000 characters
3. **Preamble Detection**: Filters out conversational opening phrases
4. **Consistency Checks**: (Optional) Validates claims are supported by source data

Quality score (0-100) is returned with every response. Warnings appear if score < 80.

## Performance & Estimation

- **Token Counting**: Uses `tiktoken` library for accurate estimation
- **Streaming Speed**: ~100 tokens/second (Gemini Flash baseline)
- **Timeout**: 60 seconds for streaming, 30 seconds for sync
- **Progress Updates**: Every 200ms with elapsed/remaining time calculation

## Security

✅ **Implemented:**
- API key loaded from environment variable (never hardcoded)
- Request validation and sanitization
- Error messages don't expose sensitive information
- CORS enabled for local development

🔒 **Recommended for Production:**
- HTTPS/TLS enforcement
- Rate limiting (add Flask-Limiter)
- Authentication layer (OAuth/JWT tokens)
- Request signing to prevent tampering
- Encrypted data persistence
- Comprehensive audit logging

## Troubleshooting

### "Could not connect to backend server"
- Ensure `python server.py` is running
- Check that `GOOGLE_API_KEY` environment variable is set
- Verify server is listening on `http://127.0.0.1:5003`

### "Model response was empty or blocked"
- Input may have violated the model's content policy
- Try rephrasing the question or removing sensitive information
- Check API quota and rate limits

### "Request timeout"
- Input documents were too large
- API is under high load
- Network connection issue
- Increase timeout in `server.py` (currently 60s)

### API Key Issues
- Verify key format (should be ~40 characters)
- Confirm key is active in [Google AI Studio](https://aistudio.google.com/app/apikeys)
- Check you're using `GOOGLE_API_KEY` environment variable, not `API_KEY`

## Development

### Running Tests
```bash
# Manual testing: Select each mode and verify outputs differ
# Verify progress bar updates smoothly
# Test with documents of varying sizes
# Check error messages for edge cases
```

### Adding Custom Modes
1. Add new entry to `MODE_CONFIGS` in `server.py`
2. Add radio button to mode selector in `index.html`
3. Verify mode is accessible via `/modes` endpoint

### Extending the API
- Add new endpoints in `server.py` (following Flask patterns)
- Update frontend to call new endpoints
- Document new endpoints in this README

## Deployment

### Docker (Recommended)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV GOOGLE_API_KEY=your-key-here
CMD ["python", "server.py"]
```

### Cloud Platforms
- **Google Cloud Run**: Stateless, scales automatically
- **AWS Lambda + API Gateway**: Serverless option
- **Heroku**: Simple deployment with environment variables
- **DigitalOcean App Platform**: Cost-effective VPS option

### Production Checklist
- [ ] API keys in secrets manager (not environment variables for production)
- [ ] HTTPS/TLS enabled
- [ ] Rate limiting added
- [ ] Database for synthesis history (optional)
- [ ] Monitoring and alerting configured
- [ ] Error logging to centralized service
- [ ] Load balancer for multiple instances
- [ ] CORS properly configured for your domain
- [ ] Database backups enabled (if using persistence)

## Roadmap

**Near term (v0.2):**
- PDF/Word file upload support
- Synthesis history and caching
- Export to PDF with embedded citations
- Multi-language support

**Medium term (v0.3):**
- Citation graph visualization
- Multi-model support (Claude, Grok, custom models)
- Fine-tuning on custom documents
- Team collaboration and annotations

**Long term (v0.4+):**
- Knowledge base management
- Webhook integrations
- Advanced quality assurance with fact-checking
- Custom synthesis templates per industry

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/omni-one/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/omni-one/discussions)
- **Email**: contact@example.com

## Citation

If you use Omni in research or production, please cite:

```
Guo, H. et al. "Omni: AI-Native Knowledge Synthesis Engine" (2024)
```

---

**Built with:** Flask, Tailwind CSS, Google Gemini API, tiktoken
**Status:** Active Development (Pre-release)
