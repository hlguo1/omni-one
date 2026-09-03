# Omni-One — Deterministic-First Intelligence Platform

**Core: 4-layer pipeline + ontology-centered suite (methodology like Palantir, not a clone). Highlight: Seller OS for people selling stuff online.**

Omni-One is local-first, free ($0): ingest messy folder → OCR+chart+pipeline → ontology twin → Workshop decisions → grounded AI → audited actions. The suite surrounds the core tech (like Palantir's methodology); Seller OS is the **featured outstanding app** proving it for concrete SMB (not the only thing).

> Pipeline + ontology + suite remain — not deleted. Seller OS showcases the engine.

---

## 1. Core Meat (always here, now strengthened)

**4-layer pipeline** `src/omni_one/core/data_processing_pipeline.py:1` (thread-safe, dedup, STATISTICAL stage, cache-store, evidence parity):
- **Layer 1** `<1ms` `core/layer_1_ingestion.py:73` robust ISO/epoch/ms timestamps, OrderedDict TTL dedup
- **Layer 2** `<10ms` `core/layer_2_statistical.py:35` signal-bucket fallback (unique IDs), multi-key thresholds
- **Layer 3** `<100ms` `core/layer_3_ml_features.py:45` bilingual sentiment, calibrated priority
- **Layer 4** gated `IntelligentLLMGate` budget-aware + `evidence_bundle`/`cost_ledger` `core/types.py:213`

**Suite surrounding core (Palantir methodology, free):**
- **Foundry** `palantir_free/foundry.py:22` — versioned datasets, expectations gate, `build_if_stale`, `profile_dataset`, multi-SQL `sql_join` (DuckDB+Pandas, $0)
- **Ontology** `palantir_free/ontology.py:16` — typed coercion, history/version, cardinality, propose/approve actions, markings, `save/load`
- **Workshop** `palantir_free/workshop.py:1` — decision queue FROM ontology (no phantoms), assign/approve/resolve → writeback via Actions
- **Governance** `palantir_free/governance.py:1` — hash-chained `AuditLog` across pipeline+ontology+workshop+AIP+foundry, `verify()`, markings filter
- **AIP** `palantir_free/aip.py:44` — `FunctionRegistry`, `check_grounding` anti-hallucination, `evaluate()` harness, single reused pipeline
- **Vision** `core/vision.py:83` Tesseract + OpenCV + Matplotlib ($0) → **98.8% bypass p50 0.07ms $0.0011/1k**

Use the core directly:
```bash
PYTHONPATH=src python -m pytest tests/unit -q # 22 passed (core + methodology)
PYTHONPATH=src python3 scripts/e2e_core_methodology.py --out /tmp/e2e_method # 6-stage loop PASSED
PYTHONPATH=src python -m omni_one.core.eval_harness --n 2000 # writes docs/EVAL_REPORT.md
```

## 2. Highlight: Seller OS — One Outstanding Product for Online Sellers

**For 1-5 person shops on Shopify / Etsy / Amazon + Instagram DMs** who live on spreadsheets and phone photos. Other verticals (RevOps, micro tacos, generic vision) still runnable in `src/omni_one/packs/_labs/` and `palantir_free/` as labs/samples — Seller OS is the polished, focused demo.

**What it proves the engine can do:**
- **True profit, not GMV** — parses Shopify `Total` + Etsy `fees` + supplier `50 x 4.00` → per-unit COGS `packs/seller_os.py:155` → margin with citation `[shopify_orders.csv:5] Tote Bag qty2 gmv$56`
- **Stockout risk** — velocity 7d vs `on_hand` `inventory.csv` `packs/seller_os.py:258` → `Tote Bag Handmade 2 left, sold 6/7d = 2.3 days`
- **Win-back draft** — detects `where is my order? / chipped` in DMs `packs/seller_os.py:267` → gated draft `[MOCK SELLER DRAFT]` free
- **One page** — `web/seller.html` → drop folder or photo → briefing + chart base64 + evidence trail

Demo (synthetic, still uses pipeline engine):
```bash
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo
# → GMV $274.00 Fees $16.71 Net $233.29 True Profit $169.09 Margin 61.7% Best Tote Bag Handmade (6) Stockout 1 At-risk 3
```

Your mess:
```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv ~/Downloads/*dm*.txt /tmp/my_shop/
# drop supplier photos into /tmp/my_shop/
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/my_shop --json /tmp/briefing.json
```

Photo → text+chart → pipeline (free, also generic):
```bash
curl -F file=@supplier_invoice.jpg -F lang=eng http://localhost:5003/api/v1/seller/photo | jq .cost_usd # 0.0 free
curl -F file=@chart.png http://localhost:5003/api/v1/vision/analyze | jq .ocr.text
```

---

## 3. Suite surrounding core (methodology like Palantir, not a clone)

| Pillar | What it does (free) | Highlight wiring |
|---|---|---|
| Foundry `foundry.py:22` | Versioned datasets, expectations gate, incremental `build_if_stale`, profiling, multi-SQL | Seller Shopify/Etsy → joined |
| Ontology `ontology.py:16` | Typed twin, history/version, cardinality, propose/approve, markings, save/load | Product/Order/Shipment/Ward twin |
| Pipeline `data_processing_pipeline.py:1` | 4-layer evidence + cost, dedup, STATISTICAL stage | Seller events → evidence |
| Workshop `workshop.py:1` | Decision queue FROM ontology (no phantoms), assign/approve/resolve → Actions | Seller stockout + supply delay queue |
| AIP `aip.py:44` | Registry, grounding check, eval, reused pipeline | `seller_stockout` grounded 1.0, eval 2/2 |
| Governance `governance.py:1` | Hash-chained audit across all, verify, markings | 29 events verified |
| Apollo `apollo.py:22` | Compose manifest | `web/seller.html` ships |

Labs still runnable: `_labs/micro_biz.py`, `_labs/revenue_ops.py`, `scripts/e2e_palantir_free.py:1` (6 pillars $0).

---

## 4. Try the platform (60 sec)

```bash
git clone https://github.com/garyguo123456789/omni-one.git
cd omni-one
pip install -r requirements.txt
brew install tesseract  # free OCR, apt-get on Linux
pip install pytesseract opencv-python pillow matplotlib python-multipart

# Engine alone
PYTHONPATH=src python -m omni_one.core.eval_harness --n 500

# Highlight app (Seller OS)
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo
open web/seller.html  # drag-drop seller folder

# API (engine + highlight)
PYTHONPATH=src uvicorn omni_one.api.fastapi_app:create_omni_one_app --factory --port 5003
curl -X POST http://localhost:5003/api/v1/seller/briefing -H "Content-Type: application/json" -d '{"demo":true}' | jq .kpis
curl http://localhost:5003/api/docs  # all endpoints
```

## 5. APIs (core + highlight)

| Endpoint | Purpose | Cost |
|---|---|---|
| `POST /api/v1/seller/briefing {"demo":true}` | Seller highlight demo (GMV $274 profit $169) | $0 |
| `POST /api/v1/seller/operations {"demo":true}` | Briefing + Workshop queue + AIP grounded + Governance audit (full loop) | $0 |
| `POST /api/v1/seller/photo` multipart | Seller invoice photo → OCR+chart+pipeline | $0 |
| `POST /api/v1/vision/analyze` | Generic photo (engine) | $0 |
| `POST /api/v1/analyze {"records":[...]}` | Raw pipeline (engine) | $0 |
| Labs: `POST /api/v1/micro/briefing`, `POST /api/v1/revenue/health` | `_labs` | $0 |

## 6. Docs

- **Core:** `docs/MULTI_LAYER_ARCHITECTURE.md`, `docs/EVAL_REPORT.md` (98.8% bypass), `core/data_processing_pipeline.py:1`
- **Suite:** `palantir_free/ontology.py:16`, `foundry.py:22`, `workshop.py:1`, `governance.py:1`, `aip.py:44`, `scripts/e2e_core_methodology.py:1`
- **Highlight:** `docs/SELLER_OS.md`, `docs/FOCUS.md`, `packs/seller_os.py:1`, `web/seller.html:1`
- **Labs:** `packs/_labs/` + `scripts/e2e_palantir_free.py:1`

## 7. Verify (robust)

```bash
PYTHONPATH=src python -m pytest tests/unit -q  # 22 passed (core + methodology)
PYTHONPATH=src python3 scripts/e2e_core_methodology.py --out /tmp/e2e_method  # Foundry→Ontology→Pipeline→Workshop→AIP→Governance PASSED
PYTHONPATH=src python scripts/e2e_palantir_free.py --out /tmp/e2e  # 6 pillars PASSED $0
ls src/omni_one/core/data_processing_pipeline.py  # core meat, not deleted
```

*Core meat strengthened with suite methodology. Seller OS is the outstanding highlight proving it.*
