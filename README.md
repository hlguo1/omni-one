# Omni-One — Deterministic-First Intelligence Platform

**Core engine: 4-layer deterministic pipeline (`src/omni_one/core/data_processing_pipeline.py:1`). Highlight use case: Seller OS for people selling stuff online.**

Omni-One is a local-first, free ($0) alternative to Palantir Foundry/Gotham — ingest any messy folder (CSV, receipt photo, WhatsApp/DM) → OCR + chart + pipeline → evidence-backed briefing. The engine is generic; Seller OS is the **featured, outstanding app** built on it (not the only thing).

> Pipeline remains — not deleted. Seller OS is a showcase of what the engine can do for a concrete SMB.

---

## 1. Core Engine (always here)

**4-layer pipeline** — the moat, reused by every app:
- **Layer 1** Ingestion `<1ms` `core/layer_1_ingestion.py:1` schema + dedup + TTL
- **Layer 2** Statistical `<10ms` `core/layer_2_statistical.py:1` Z-score, trend, thresholds
- **Layer 3** ML `<100ms` `core/layer_3_ml_features.py:1` sentiment, churn, priority
- **Layer 4** LLM gated `core/data_processing_pipeline.py:311` `IntelligentLLMGate` budget-aware, `evidence_bundle` + `cost_ledger` `core/types.py:213`

**Free local stack:** Tesseract OCR `core/vision.py:83`, OpenCV chart `core/vision.py:120`, Matplotlib `core/vision.py:297`, DuckDB+Pandas Foundry `palantir_free/foundry.py:22`, in-mem Ontology `palantir_free/ontology.py:58`, Graph `palantir_free/gotham.py:30`, mock LLM (Ollama optional) `core/model_router.py:231` → **98.4% LLM bypass `docs/EVAL_REPORT.md:17` p50 0.03ms $0.0014/1k**

Use the engine directly:
```bash
PYTHONPATH=src python -m pytest tests/unit -q # 9 passed includes pipeline audit
PYTHONPATH=src python -c "from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline; p=MultiLayerDataPipeline(); print(p.process_record({'timestamp':__import__('datetime').datetime.now(),'source':'test','entity_id':'x','value':100}).evidence_bundle)"
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

## 3. All Capabilities (engine + highlights + labs)

| Layer | Engine (core, always) | Highlight App (Seller OS) | Labs (still runnable) |
|---|---|---|---|
| Ingest | 4-layer pipeline + vision OCR/chart | `packs/seller_os.py:236` shopify/etsy/inventory/DM/supplier photo | `_labs/micro_biz.py`, `_labs/revenue_ops.py` |
| Store | Foundry `foundry.py:22` DuckDB/Parquet | Seller briefing `seller_os.py:319` | e2e `scripts/e2e_palantir_free.py:1` |
| Twin | Ontology `ontology.py:58` | Seller products/customers graph | Palantir-free ontology demo |
| Investigate | Gotham `gotham.py:30` | At-risk customer graph | RevOps churn graph |
| Act | AIP `aip.py:40` gated LLM | Win-back draft, reorder action | Proactive engine |
| Deploy | Apollo `apollo.py:22` compose | `web/seller.html` | `web/index.html` generic |

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

## 5. APIs

| Endpoint | Purpose | Cost |
|---|---|---|
| `POST /api/v1/seller/briefing {"demo":true}` | Seller highlight demo | $0 |
| `POST /api/v1/seller/photo` multipart | Seller invoice/product photo → OCR+chart+pipeline | $0 |
| `POST /api/v1/vision/analyze` | Generic photo (engine) | $0 |
| `GET /api/v1/vision/demo` | Synthetic receipt+chart | $0 |
| `POST /api/v1/analyze {"records":[...]}` | Raw pipeline (engine) | $0 |
| `POST /api/v1/synthesize` | Pipeline + gated LLM | $0 mock |
| Labs: `POST /api/v1/micro/briefing`, `POST /api/v1/revenue/health` | `_labs` | $0 |

## 6. Docs

- **Engine:** `docs/MULTI_LAYER_ARCHITECTURE.md`, `docs/QUICK_START_PIPELINE.md`, `docs/EVAL_REPORT.md` (98.4% bypass), `core/data_processing_pipeline.py:170`
- **Highlight:** `docs/SELLER_OS.md`, `docs/FOCUS.md` (why ONE product), `packs/seller_os.py:1`, `web/seller.html:1`
- **Labs:** `packs/_labs/` + `docs/MICRO_BIZ.md` (labs), `palantir_free/` free Palantir alt `scripts/e2e_palantir_free.py:1`
- **Vision free:** `core/vision.py:1`

## 7. Verify

```bash
PYTHONPATH=src python -m pytest tests/unit -q  # 9 passed
PYTHONPATH=src python scripts/e2e_palantir_free.py --out /tmp/e2e  # 6 pillars PASSED $0
ls src/omni_one/core/data_processing_pipeline.py  # 49K, not deleted
```

*Core engine stays. Seller OS is the outstanding showcase — not the only thing.*
