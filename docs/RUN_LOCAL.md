# Run Local — Seller OS in 5 minutes ($0, offline-friendly)

**For 1–5 person shops. No cloud, no keys, mock LLM by default.**

## 1. Laptop (fastest)

```bash
git clone https://github.com/garyguo123456789/omni-one.git
cd omni-one
brew install tesseract          # free OCR (apt-get on Linux)
pip install -r requirements-seller.txt

# Demo (synthetic shop, proves engine)
PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/seller_demo
# -> GMV $274.00 Fees $16.71 True Profit $169.09 Margin 61.7% Best Tote Bag Handmade (6) Stockout 1

# Your mess (copy shop files into inbox — path-traversal safe)
mkdir -p ./data/inbox
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv ./data/inbox/ 2>/dev/null || true
PYTHONPATH=src python scripts/demo_seller_os.py --folder ./data/inbox --json /tmp/briefing.json

# Tests + eval (offline, mock LLM)
PYTHONPATH=src python -m pytest tests/unit tests/integration -q
PYTHONPATH=src python -m omni_one.core.eval_harness --n 500
```

## 2. Single Docker (same, containerized)

```bash
cp .env.example .env   # set VALID_API_KEYS + SECRET_KEY (random 32+ chars)
docker compose up --build
curl -X POST http://localhost:5003/api/v1/seller/briefing -H "Content-Type: application/json" -d '{"demo":true}' | jq .kpis
open web/seller.html   # same-origin API, works offline after load
```

## 3. API surface (free)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/seller/briefing {"demo":true}` | Demo KPIs |
| `POST /api/v1/seller/briefing {"folder":"./data/inbox"}` | Your folder (must be `./data/inbox` or `/tmp/*`) |
| `POST /api/v1/seller/scenarios/run {"demo":true}` | 12 scenarios → Workshop queue + audit |
| `POST /api/v1/seller/operations {"demo":true}` | Full loop: briefing → ontology → workshop → AIP → governance |
| `POST /api/v1/seller/photo` multipart | Invoice photo → OCR+chart+pipeline (≤5MB, jpg/png/webp/pdf) |
| `GET /health`, `/readiness`, `/status` | Liveness/readiness (mode:mvp when Redis/Weaviate down) |
| `GET /api/v1/admin/services` | Admin (requires `X-API-Key` or `Bearer`) |

## 4. Free-first rules

- `SELLER_LLM=mock` (default) — never calls paid LLM. Set `SELLER_LLM=google` + `GOOGLE_API_KEY` only to opt into live.
- `SELLER_MAX_LLM_USD=0.0` (default cap) — ledger proves $0 in `data/cost_ledger.jsonl` + DuckDB.
- Persistence: `data/omni.duckdb` + `data/audit.jsonl` (hash-chained, `verify()`). Backup: `./scripts/backup.sh`.
- Uploads: `./data/inbox` only (traversal blocked), 5MB max, Pillow-verified.

## 5. Verify

```bash
PYTHONPATH=src python -m pytest tests/unit tests/integration -q  # 24 + 7 passed
PYTHONPATH=src python scripts/e2e_core_methodology.py --out /tmp/e2e_method  # PASSED
./scripts/backup.sh
```
