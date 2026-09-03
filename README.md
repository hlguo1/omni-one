# Omni-One — Seller OS

**The ONE outstanding product for people selling stuff online (Shopify / Etsy / Amazon + Instagram DMs).**

Drop a messy folder — Shopify CSV, Etsy settlement, supplier invoice photo, inventory snapshot, DM export — get a **Daily Seller Briefing** in 5 seconds with true profit, stockout risk, and a win-back draft. **100% free, offline, no API keys.** Other verticals (RevOps, micro-biz) moved to `_labs`.

> **Why Seller OS?** Spreadsheets show GMV. Seller OS shows **true profit = GMV - fees - shipping - COGS (per-unit from supplier OCR)** with `file:line` citations, so a 1-5 person shop can act like it has a data team.

---

## What it delivers (Seller OS)

- **True Profit, Not GMV** — parses Shopify `Total` + Etsy `fees` + supplier `50 x 4.00` → per-unit COGS `packs/seller_os.py:155` → margin with citation `[shopify_orders.csv:5] Tote Bag qty2 gmv$56`
- **Stockout Risk** — velocity 7d vs `on_hand` from `inventory.csv` `packs/seller_os.py:258` → `Tote Bag Handmade 2 left, sold 6/7d = 2.3 days` → high alert
- **Win-back Draft** — detects `where is my order? / chipped / disappointed` in `instagram_dm.txt` / `reviews.csv` `packs/seller_os.py:267` → gated LLM draft `[MOCK SELLER DRAFT]` free, or real via `GOOGLE_API_KEY`
- **One Page** — `web/seller.html` → drop folder or photo → briefing + chart base64 (Matplotlib free) + evidence trail. No website/DB needed.

**Stack: free local** — `core/data_processing_pipeline.py:133` deterministic 4-layer (98% LLM bypass `docs/EVAL_REPORT.md`), `core/vision.py:83` Tesseract + `core/vision.py:120` OpenCV + Matplotlib, `palantir_free/foundry.py:22` DuckDB+Parquet, `palantir_free/ontology.py:58` in-mem graph. All $0; optional Ollama.

---

## Try it in 60 seconds (no keys, no DB)

```bash
git clone https://github.com/garyguo123456789/omni-one.git
cd omni-one
pip install -r requirements.txt          # + free local extras below
# free vision (offline OCR/chart)
brew install tesseract                  # macOS, free; apt-get on Linux
pip install pytesseract opencv-python pillow matplotlib python-multipart

# 1) Demo seller folder (synthetic Shopify/Etsy/inventory/DMs/supplier photo)
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo
# → GMV $274.00 Fees $16.71 Net $233.29 True Profit $169.09 Margin 61.7% Best Tote Bag Handmade (6) Stockout 1 At-risk 3

# 2) Your messy folder
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv /tmp/my_shop/
cp ~/Downloads/inventory.csv /tmp/my_shop/
cp -r ~/Downloads/*dm*.txt /tmp/my_shop/
# drop phone supplier photos into /tmp/my_shop/
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/my_shop --json /tmp/briefing.json
cat /tmp/briefing.json | jq '.kpis, .alerts, .draft_reply'

# 3) Photo → Text + Chart → Pipeline (free)
PYTHONPATH=src python -c "from omni_one.core.vision import analyze_photo; print(analyze_photo(open('receipt.jpg','rb').read(), 'receipt.jpg')['ocr']['text'][:200])"

# 4) API (free, $0)
PYTHONPATH=src uvicorn omni_one.api.fastapi_app:create_omni_one_app --factory --port 5003
curl -X POST http://localhost:5003/api/v1/seller/briefing -H "Content-Type: application/json" -d '{"demo":true}' | jq .kpis
curl -F file=@supplier_invoice.jpg -F lang=eng http://localhost:5003/api/v1/seller/photo | jq .cost_usd  # → 0.0
open web/seller.html  # drag-drop UI for Seller OS
```

---

## Primary APIs (seller focus)

| Endpoint | What it does | Cost |
|---|---|---|
| `POST /api/v1/seller/briefing {"demo":true}` | Demo briefing (GMV $274 true profit $169 stockout 1) | $0 |
| `POST /api/v1/seller/briefing {"folder":"/tmp/my_shop"}` | Your folder → briefing | $0 |
| `POST /api/v1/seller/photo` multipart `file` | Supplier/product photo → OCR → chart → pipeline | $0 |
| `POST /api/v1/vision/analyze` | Generic photo (labs) | $0 |
| `GET /api/v1/vision/demo` | Synthetic receipt+chart demo | $0 |
| `GET /health`, `/api/docs` | Health + OpenAPI | — |

Labs (still runnable, not primary): `POST /api/v1/micro/briefing` `_labs/micro_biz.py`, `POST /api/v1/revenue/health` `_labs/revenue_ops.py`, `POST /api/v1/vision/analyze` generic.

---

## Architecture (Seller OS reuses deterministic-first engine)

```
Folder (CSV/photo/DM) → ingest_seller_folder() packs/seller_os.py:236
  → OCR Tesseract core/vision.py:83 + chart OpenCV core/vision.py:120 + chart Matplotlib core/vision.py:297
  → Events (timestamp,source,entity_id,value,file:line) → MultiLayerDataPipeline core/data_processing_pipeline.py:311
    Layer1 <1ms dedup → Layer2 <10ms Z-score → Layer3 <100ms sentiment/priority → Layer4 gated LLM (mock free, 100% bypass demo)
  → build_seller_briefing() packs/seller_os.py:319 → KPIs + alerts + chart base64 + evidence_sample
  → web/seller.html or API JSON
```

Foundry/Ontology/Gotham/AIP/Apollo (`palantir_free/`) remain as internal engine for lineage/graph/logic/deploy but not marketed; see `scripts/e2e_palantir_free.py:1` for free Palantir alternative e2e ($0 vs $1-5M).

---

## Docs

- **Focus:** `docs/FOCUS.md` — why ONE product, what we cut
- **Strategy (now Seller OS):** `docs/STRATEGY.md` — deterministic-first thesis
- **Seller OS:** `packs/seller_os.py:1` + `scripts/demo_seller_os.py:1` + `web/seller.html:1`
- **Vision (free):** `core/vision.py:1` + `docs/MICRO_BIZ.md` (now labs, see `MICRO_BIZ_LABS.md`)
- **Pipeline:** `core/data_processing_pipeline.py:170` + `docs/MULTI_LAYER_ARCHITECTURE.md` + `docs/EVAL_REPORT.md` (96.4% bypass, p50 0.03ms)
- **Labs:** `packs/_labs/` — RevOps, micro-biz

---

## Verify

```bash
PYTHONPATH=src python -m pytest tests/unit -q  # 9 passed
PYTHONPATH=src python scripts/e2e_palantir_free.py --out /tmp/e2e  # 6 pillars PASSED $0
```

*Built for 1-5 person online sellers who live on spreadsheets and phone photos — not for enterprise decks.*
