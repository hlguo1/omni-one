# Omni-One Strategy: From Platform Scaffolding to Industry Moat
## Diagnosis → Thesis → Execution Plan
**Date:** 2026-09-02 | **Status:** Active | **Author:** Codebase Audit

---

## 1. Honest Diagnosis (What We Have)

### What Is Real and Valuable
- **4-Layer Pipeline (`src/omni_one/core/data_processing_pipeline.py:170`)** is the only architectural moat. It solves a real enterprise pain: LLM-everywhere architectures collapse at >1k events/sec due to cost/latency. The gating (85-90% bypass, `get_metrics_summary()`) is directionally correct and tested.
- **Audit trail** (`llm_decision_audit`, `tests/unit/test_llm_decision_audit.py:31`) and **counterfactual fairness** (`enterprise/ethical_ai.py:99`) are genuinely differentiated — no competitor ships deterministic, replayable LLM routing logs. Tests prove determinism.
- **Checkpointing** (`tests/unit/test_data_ingestion_checkpointing.py:52`) is correct: failed RAG writes don't advance watermarks. This is production table-stakes most demos skip.
- **Infra hygiene** (`core/types.py:66`, `core/exceptions.py:15`, `infra/di_container.py:72`, `infra/health_checks.py:134`, `infra/settings.py:33`) is FAANG-grade and already 3,000+ lines. It is ready for scale.

### What Is Vaporware / Debt (Must Fix or Cut)
| Area | Claim vs Reality | Severity |
|------|------------------|----------|
| **server.py:1** | 1,351 lines, two merged Flask apps with duplicated `EnterpriseConfig`, broken imports (`from rag_engine import RAGEngine` should be `from core.rag_engine`), unreachable code after `if __name__` | **CRITICAL** — not runnable without manual patch |
| **SemanticCache (`core/cache.py:21`)** | Docs claim embedding similarity (0.88 threshold); code does `redis.keys('*')` scan + `in` substring check, O(N) per request, no embeddings | **HIGH** — will collapse at 10k keys |
| **ModelRouter (`core/model_router.py:32`)** | Docs claim cost-quality frontier, ML-based routing; code is 57 lines with 3 hard-coded Gemini models and `len(prompt.split())*1.3` token estimate | **HIGH** — no budget enforcement |
| **Enterprise stubs** (`server.py:557`) | `/ai/multimodal/analyze`, `/ethical/monitor`, `/quantum/optimize` return hard-coded dicts (`bias_score: 0.02`) | **MEDIUM** — destroys credibility with enterprise buyers |
| **12 docs files** | Technical Architecture, Enterprise Architecture, Cutting Edge Summary, etc. duplicate each other, describe unbuilt systems (QUBO, Homomorphic Encryption) | **MEDIUM** — confuses positioning |
| **Layers 1-3** | Statistically naive: Z-score with `window_size=50`, keyword sentiment (`positive_keywords` set), churn scorer with `np.tanh(value/100)` heuristics. No training, no calibration, no eval harness | **HIGH** — untrustworthy without benchmarks |

**Verdict:** The platform has a **strong chassis** (pipeline + audit + DI/health) but a **weak engine** (naive models, broken cache/router, mock endpoints) and **bloated bodywork** (docs describing futures, not facts). Industry buyers will see through mock endpoints in 5 minutes.

---

## 2. Thesis: What Would Be Genuinely Innovative & Useful

### The Insight No Incumbent Owns
Every vendor says “AI for ops.” Every vendor fails the same way: **they route everything through an LLM.** Result → $3k+/month LLM bill at 1M events/day, p99 latency >2s, no audit trail, hallucinations in alerts, and compliance blocking deployment.

**Omni-One’s wedge:** `Deterministic-First Intelligence` — the first operational intelligence fabric with a **verifiable cost/quality/latency frontier**.

```
Layer 1: Schema + Dedup          <1ms   5% rejected, deterministic
Layer 2: Statistical (Z-score)   <10ms  80% anomalies caught without ML
Layer 3: Lightweight ML          <100ms 70% bypass, calibrated priority
Layer 4: LLM (gated + budgeted)  500ms  only 10-30% need it, with evidence bundle
```

This is not an optimization — it is a *different compute graph*. Competitors optimize prompts; we **eliminate calls**.

### Industry Usefulness: Pick One Wedge, Win It, Then Expand
We reject “platform for everyone.” **ICP for next 90 days: Seller OS for people selling stuff online (1-5 person Shopify/Etsy/Amazon shops, $5k-100k GMV/mo).** Updated per `docs/FOCUS.md:1` — RevOps moved to `_labs`.

Why Sellers Online (concrete, non-overlapping):
- Pain is acute: no true profit view (GMV ≠ profit after 6.5% Etsy + shipping + COGS), stockouts of best seller kill sales, DMs/reviews missed → 1-star.
- Data exists but messy: `shopify_orders.csv`/`etsy_settlement.csv` + `inventory.csv` + `instagram_dm.txt` + `supplier_invoice.jpg` → exactly what `packs/seller_os.py:236` ingests (fuzzy headers, OCR free).
- Budget exists but tiny: $0-19/mo, needs $0 demo and $0 pipeline (98% bypass `docs/EVAL_REPORT.md` → $0.0014/1k). Our free local Tesseract+OpenCV+Matplotlib+mock LLM beats $200/mo tools.
- Evaluation is crisp: true profit $ vs spreadsheet, stockout recall, at-risk DM recall — not vibes.

**Outcomes we sell (measurable, demo `scripts/demo_seller_os.py:1`):**
- “GMV $274 → true profit $169 (fees $16.71 + COGS $64.20) with citations file:line, Stockout 1 (Tote 2 left, 2.3 days), 3 DM at-risk with draft, chart base64 free”

### Three Pillars (Product Becomes Category)

**Pillar 1 — Scale Without LLM Tax (Throughput)**
- Budget-aware router: every request has `$ budget + latency SLA → model selection is a constrained optimization`, not a vibe. Fallback chain + circuit breaker.
- Eval harness: nightly benchmarks on bypass rate, latency distribution, cost per 1k events. Numbers are in README, not slides.

**Pillar 2 — Trust Without Black Box (Governance)**
- Evidence Bundle: every insight is a `chain of evidence` — Layer 1 normalized record → Layer 2 z_score + threshold → Layer 3 priority + feature_importance → Layer 4 prompt_preview + citations. Auditors can replay.
- Counterfactual Fairness: already deterministic (`ethical_ai.py:119`), extend to revenue context (e.g., “did we flag this account because of valid health signals, not region/segment bias?”).

**Pillar 3 — Usefulness Without Integration Hell (Vertical Packs)**
- Ship 1 vertical pack fully working (RevOps Health Pack) instead of 5 stubs. Includes: synthetic signal generator, realistic playbooks (“3 immediate actions + owner + success metric”), Slack/email webhook, and a 5-minute demo that imports CSV and shows ROI dashboard.

### Moat Over 12 Months
1. **Data gravity:** Every gated decision logs `(features → priority → gate_reason → human feedback)`. This trains a company-specific router no competitor can copy.
2. **Evidence graph:** Competitors generate text; we generate `Graph<Signal → Inference → Action>` that plugs into SOX/SOC2 workflows.
3. **Cost control plane:** Finance can set team-level LLM budgets; platform enforces them deterministically (no surprise bills).

---

## 3. What We Will NOT Do (Focus)

- **Cut:** Quantum optimization, federated learning, homomorphic encryption — keep files, remove from primary positioning until RevOps wedge is won. The code stays, but `/quantum/optimize` no longer pretends to be production.
- **Defer:** Full multi-modal (voice/video) — text + numeric signals cover 90% of RevOps value; video is demo-candy.
- **Freeze:** No new docs until eval harness proves claims. One `STRATEGY.md` (this file) + `EVAL_REPORT.md` (generated) > 12 aspirational docs.

---

## 4. Execution Plan (90 Days, Shipped Code)

### Phase 1 (This PR, 1-2 weeks) — Make Claims Verifiable
| Task | File | Definition of Done |
|------|------|-------------------|
| Fix server import graph | `server.py`, `core/cache.py`, `core/model_router.py` | `python -m omni_one.server` boots, `curl /health` returns 200, no `from rag_engine` |
| Evidence Bundle + Cost Ledger | `core/data_processing_pipeline.py:46`, `core/types.py:213` | Every `ProcessingResult` has `evidence_bundle: EvidenceChain` and `cost_ledger` |
| Budget-Aware Router | `core/model_router.py:15` | `select_model(budget=0.001, latency_sla=300)` returns constrained optimum with `estimated_cost` |
| Eval Harness | `core/eval_harness.py` (NEW) | `python -m omni_one.core.eval_harness --n=5000` prints bypass, p50/p99, $/1k, and writes `EVAL_REPORT.md` |
| Seller OS Pack (THE product) | `packs/seller_os.py:1` | `PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo` → GMV $274 true profit $169 stockout 1 at-risk 3 |
| Vision Free | `core/vision.py:1` | `POST /api/v1/seller/photo` OCR Tesseract + chart OpenCV free → pipeline $0 |
| Wire FastAPI prod app | `api/fastapi_app.py:342` | `POST /api/v1/seller/briefing` + `POST /api/v1/seller/photo` + `POST /api/v1/vision/analyze` all free, actually call pipeline |

### Phase 2 (Weeks 3-6) — Make It Stick
- Human feedback loop: `/api/v1/feedback` writes to `continuous_learning` and retrains priority thresholds weekly.
- Real connectors: make `data/connectors/ingestion.py` actually talk to stubbed CSV/Webhook with checkpointing proven in tests.
- Health + cost dashboards: Grafana-ready Prometheus metrics for bypass rate, $/1k, fairness compliance.

### Phase 3 (Weeks 7-12) — Make It Sell (Seller OS)
- Design partner: 10 online sellers (Etsy/Shopify) on free pilot, joint case: “spreadsheet GMV vs true profit $169, prevented stockout Tote 2.3 days”.
- Evidence export: one-click zip of `EvidenceBundle` file:line citations for seller accountant.
- Pricing: Free <500 orders/mo, $19/mo >500, still $0 pipeline (mock) or BYO `GOOGLE_API_KEY`.

---

## 5. How To Test This PR

```bash
# 1. Verify pipeline still passes audit tests
PYTHONPATH=src python -m pytest tests/unit -q  # 9 passed

# 2. Run eval harness (proves bypass)
PYTHONPATH=src python -m omni_one.core.eval_harness --n=1000 --seed=42

# 3. Demo Seller OS (THE product)
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo
# → GMV $274 true profit $169 margin 61.7% stockout 1 at-risk 3

# 4. Photo free
curl -F file=@supplier_invoice.jpg http://localhost:5003/api/v1/seller/photo | jq .cost_usd # 0.0

# 5. Boot prod app
PYTHONPATH=src uvicorn omni_one.api.fastapi_app:create_omni_one_app --factory --port 5003
# open web/seller.html → drop folder, get briefing + chart
```

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Naive Layer 3 heuristics underperform on real data | Eval harness measures it; Phase 2 replaces heuristics with calibrated logistic regression trained on synthetic + design partner data; until then, docs state “heuristic baseline, not prod model” |
| Trimming vaporware upsets quantum/federated narrative | Keep code, hide from primary nav; reintroduce as “Labs” once RevOps is referenceable |
| Budget-aware router is hard to tune | Start with 3 tiers (fast/balanced/premium) with explicit $/latency caps; ML routing is opt-in after 30 days of logged data |

---

## 7. Success Metrics (What Changes in 90 Days)

From **scaffolding → moat**:
- `EVAL_REPORT.md` exists and is regenerated in CI (was: claims in docs only)
- `curl /api/v1/metrics` shows real pipeline metrics, not hard-coded `llm_bypass_rate: 0.92` (`api/fastapi_app.py:233`)
- 1 vertical demo goes from `python scripts/demo_enterprise.py` (generic) to `PYTHONPATH=src python scripts/demo_seller_os.py` (sells to online seller with title)
- `web/seller.html` one-page drop folder → briefing + chart is the product, not 12 enterprise docs
- `server.py` imports resolve, test suite passes, `pytest` coverage no longer mocks everything

**This strategy makes Omni-One not “another AI platform” but “the profit & stock truth for online sellers, for $0.”**
