# API

Base: `http://localhost:5003`. Docs: `/api/docs`. Health: `/health`, `/readiness`, `/status`, `/ping`. Metrics: `/metrics` (Prometheus).

## Daily Close (hero)

- `POST /api/v1/seller/close` `{"demo":true}` (opt `locale: en|es|zh|fr/de` — drafts only, numbers invariant) or `{"folder":"/path","shop":"Maya's"}` → close bundle (headline, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft). Counter `closes_total`.
- `GET /api/v1/seller/close.csv?demo=true` → accountant CSV download.
- `GET /api/v1/seller/export.csv?demo=true` → briefing CSV.

## Seller OS

- `POST /api/v1/seller/briefing` — true profit/stockout/alerts/draft/chart.
- `POST /api/v1/seller/operations` — briefing→ontology→workshop→AIP→audit full loop.
- `GET /api/v1/seller/scenarios` — 12-scenario registry + thresholds.
- `POST /api/v1/seller/scenarios/run` — ranked idempotent decisions + workshop + audit.
- `POST /api/v1/seller/photo` (multipart) — supplier invoice/product photo → OCR+chart+pipeline.

## Engine

- `POST /api/v1/analyze` `{"records":[...]}` — 4-layer pipeline + evidence + cost.
- `POST /api/v1/synthesize` — gated LLM synthesis with cache + citations.
- `POST /api/v1/vision/analyze` (multipart) / `GET /api/v1/vision/demo` — free OCR+chart.
- `GET /api/v1/metrics` — live 200-record eval metrics. `GET /api/v1/models` — model catalog.
- Labs: `POST /api/v1/micro/briefing`, `POST /api/v1/revenue/health`.
- Admin (`X-API-Key`/`Bearer`, fail closed): `GET /api/v1/admin/services`, `POST /api/v1/admin/clear-cache`.

All seller numbers cite `file:line`. Mock LLM by default (`SELLER_LLM=mock`, `$0`).
