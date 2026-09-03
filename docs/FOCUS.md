# Focus — One Outstanding Product

**We were building in too many directions.** Revenue OS, Micro-Biz, Palantir-free, Vision generic — overlapping, diluted.

**Decision: ONE product — Seller OS for people selling stuff online (1-5 person shops on Shopify/Etsy/Amazon/Instagram).**

## Why This One (concrete, non-overlapping)
- **Concrete ICP:** solo/2-5 people, $5k-100k GMV/mo, lives in Shopify CSV + Etsy settlement + supplier photo + DM export + inventory snapshot. No data team. Needs profit truth.
- **Non-overlapping:** Not generic AI platform (everyone does that), not enterprise RevOps (too broad), not hospital Gotham (unfocused). Seller profit + stockout is unsolved and measurable.
- **Outstanding bar:** Must be *obviously better than spreadsheet* in 5 minutes, with evidence, for $0.

Other packs moved to `src/omni_one/packs/_labs/` (still runnable, not primary). `palantir_free/` remains as internal engine but not marketed.

## What Outstanding Means (must pass)
- **True profit** GMV - fees - shipping - COGS (per-unit from supplier invoice OCR) with `file:line` citations — competitors show GMV only.
- **Stockout risk** velocity 7d vs on_hand → days_supply <5 → alert with citation `[inventory.csv:2] Tote Bag 2 left, sold 6/7d` — prevents lost sales.
- **Win-back draft** grounded in DM line, one click — not generic chatbot.
- **One page** `web/seller.html` → drop folder or photo → briefing + chart base64 (Matplotlib free) + evidence trail. No website/DB needed.
- **Free:** Tesseract + OpenCV + Matplotlib + DuckDB + pipeline mock = $0; optional Ollama for better draft.

## What We Cut
- Revenue OS demo: kept in `_labs/revenue_ops.py` but not on seller page
- Micro taco demo: kept in `_labs/micro_biz.py` (now seller inherits its ingest + vision)
- Generic `/api/v1/micro/briefing` still works but tagged LABS; primary is `POST /api/v1/seller/briefing` and `POST /api/v1/seller/photo`

## Primary APIs (seller focus)
- `POST /api/v1/seller/briefing {"demo":true}` → demo KPIs (GMV $274 fees $16 true profit $169 margin 61.7% stockout 1)
- `POST /api/v1/seller/briefing {"folder":"/tmp/my_shop"}` → your messy folder
- `POST /api/v1/seller/photo` multipart supplier invoice/product photo → OCR → chart → pipeline
- `POST /api/v1/vision/analyze` generic photo (labs)
- `GET /api/v1/vision/demo` synthetic demo

## Verify focused build
```bash
PYTHONPATH=src python3 scripts/demo_seller_os.py --folder /tmp/seller_demo_test3  # KPIs outstanding
PYTHONPATH=src python3 -m pytest tests/unit -q  # 9 passed
# E2E seller via API
curl -X POST http://localhost:5003/api/v1/seller/briefing -H "Content-Type: application/json" -d '{"demo":true}' | jq .kpis
```

This focus makes Omni-One not "another AI platform" but "the profit & stock truth for online sellers."
