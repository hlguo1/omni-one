# Seller OS — One Outstanding Product

**For people selling stuff online (Shopify / Etsy / Amazon + Instagram DMs), 1-5 person shops.**

This is **THE** product. See `docs/FOCUS.md`. All other packs are `_labs`.

## Problem
Spreadsheets lie: GMV $274 hides fees $16.71 + shipping $24 + COGS $64 → true profit $169 (61.7% margin). Sellers stockout best seller (Tote 2 left, sold 6/7d = 2.3 days) and miss DMs (`Alice: hasn't arrived`) → refunds/1-star.

## Solution (free, offline, 5s)
Drop folder:
```
my_shop/
  shopify_orders.csv (Order Name, Lineitem name, Total...)
  etsy_settlement.csv (order_id, product, qty, price, fees)
  inventory.csv (sku, product, stock)
  reviews.csv (stars, review)
  instagram_dm.txt (Sender: message)
  supplier_invoice.jpg + .txt sidecar (photo)
```
Run:
```bash
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/my_shop --json /tmp/briefing.json
# or API
curl -X POST http://localhost:5003/api/v1/seller/briefing -H "Content-Type: application/json" -d '{"demo":true}' | jq .kpis
curl -F file=@supplier_invoice.jpg http://localhost:5003/api/v1/seller/photo | jq .cost_usd # 0.0
open web/seller.html # drag-drop
```

## How outstanding (deterministic-first)
- **True profit** `packs/seller_os.py:155` parses supplier `50 x 4.00` → unit $4 → per-order COGS, cites `[shopify_orders.csv:5] gmv$56` + `[supplier_invoice.txt:2] 200.00`
- **Stockout** `packs/seller_os.py:258` velocity vs on_hand → `[inventory.csv:2] Tote 2 left, sold 6/7d 2.3 days`
- **Win-back** `packs/seller_os.py:267` keyword `where/ worried/ hasn't arrived` → draft `[MOCK SELLER DRAFT]` free, or real via `GOOGLE_API_KEY`
- **Chart** `core/vision.py:297` Matplotlib bar `Units sold (7d)` base64 free
- **Pipeline** `core/data_processing_pipeline.py:311` 100% bypass demo → $0, evidence `file:line` trail

Demo output (synthetic):
```
GMV $274.00 Fees $16.71 Net $233.29 COGS $64.20 True Profit $169.09 Margin 61.7%
Best Tote Bag Handmade (6) Worst Knitted Scarf (1) At-risk 3 Stockout 1
[high] Stockout risk: Tote Bag Handmade only 2 left, 2.3 days supply
[high] 3 customers need reply now
Actions: 1. Reorder Tote  2. Reply to Alice  3. Ask Bob for review  4. Daily close
Draft: "Hi! Sorry for delay — checking tracking..." cite [instagram_dm.txt:1]
```

## Tech (cheapest efficient, $0)
Python + DuckDB (free OLAP) + Pandas+Parquet + FastAPI + Pydantic + Tesseract `brew install tesseract` + OpenCV + Matplotlib + mock LLM (Ollama optional). No cloud fees.

## Code map
- `packs/seller_os.py:1` parsers + `ingest_seller_folder()` `236` + `build_seller_briefing()` `319` + `make_seller_demo_folder()` `279`
- `scripts/demo_seller_os.py:1` CLI
- `api/fastapi_app.py:342` `POST /api/v1/seller/briefing` + `POST /api/v1/seller/photo`
- `web/seller.html:1` one-page UI
- `core/vision.py:1` free OCR/chart

## Why this wins (non-overlapping)
- **Not Shopify analytics:** Shopify hides true profit (fees+COGS+ship). We show it with citations.
- **Not generic AI platform:** One filing cabinet, one briefing, not 12 enterprise docs.
- **Free:** $0 demo, $19/mo >500 orders (still mock $0), vs $200/mo tools.

## Verify
```bash
PYTHONPATH=src python -m pytest tests/unit -q # 9 passed
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo_test3 | grep -E "GMV|True Profit|Best|Stockout"
```
