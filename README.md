# Omni-One — the 5-minute Daily Close for sellers (free, offline, cited)

![ci](https://github.com/garyguo123456789/omni-one/actions/workflows/ci/badge.svg)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-green)
![cost](https://img.shields.io/badge/cost-%240%20default-brightgreen)
![tests](https://img.shields.io/badge/tests-1350%2B%20passing-success)

**Live demo:** https://omni-one-dw5t.onrender.com/ — free Render instance; may sleep when idle and resets data on restart. Do not upload real shop data.

**Sellers don't live in dashboards. They close the day.** Omni-One's **Daily Close** answers the 5
questions a 1–5 person Shopify/Etsy/Amazon shop asks every morning — in one command, offline, $0:

> Did I actually make money? What stocks out TODAY? Who is angry RIGHT NOW? Where is money
> leaking? What do I hand my accountant? → `close.json + close.csv + reorder.csv + replies.txt + po.txt`

```bash
git clone https://github.com/garyguo123456789/omni-one.git && cd omni-one
pip install -r requirements-seller.txt && pip install -e .
omni-one close --demo --out ./close_today   # profit $169.09 · $102.75 at risk · Tote ORDER TODAY
cat ./close_today/replies.txt                # copy-paste a draft, send the PO — done
```

Your shop: drop the mess in a folder (any headers, DMs, invoice photos), no renaming, no integration:

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv ~/Downloads/*dm*.txt /tmp/my_shop/
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
```

Demo headline: `Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder TODAY · 0 leaks`.
Every dollar cites `file:line` (e.g. `[inventory.csv:2] Tote on_hand=2`). See `docs/DAILY_CLOSE.md`.

---

## Why shops use it daily (not another dashboard)

| Pain (real money) | Daily Close gives you | File |
|---|---|---|
| "GMV is vanity" | True profit GMV−fees−ship−COGS ($169.09 on $274 demo) | `close.csv` |
| Stockout kills tomorrow | Reorder sheet: velocity→days_left→qty_14d + urgency + supplier + PO email | `reorder.csv` + `po.txt` |
| Slow reply → refund/1-star | Reply queue with copy-paste drafts (name, issue, order cite, 2h promise) | `replies.txt` |
| Fees/shipping quietly eat margin | Leaks with $: fee creep, shipping loss, margin dip, COGS spike | `close.csv` |
| Accountant needs something | One CSV: KPIs + actions + leaks; JSON for automation | `close.csv`/`close.json` |

Day 1: one refund saved pays for the year (it's $0). Day 7: velocity learned, POs one-click.
Day 30: `money_at_risk → $0` streak. Principles: **$0 default, offline-first, cited numbers,
no phantom tasks, mock-by-default LLM, laptop-private data.**

## Engine underneath (deterministic-first)

```
messy folder → [Foundry: versioned datasets, expectations gate, DuckDB $0]
  → [Ontology: typed twin Product/Order/Shipment, history, approvals, markings]
  → [4-layer pipeline: <1ms ingest → <10ms stats → <100ms ML → gated LLM + evidence/cost ledger, 98.8% bypass]
  → [12 scenarios: STOCKOUT…LISTING_GAP, stable IDs, idempotent]
  → [Workshop: queue FROM ontology only] → [AIP: grounded check, eval 2/2]
  → [Governance: hash-chained audit, verify()] → DAILY CLOSE bundle
```

- **Pipeline** `src/omni_one/core/data_processing_pipeline.py` (+ `layer_1/2/3`, `types.py` evidence/cost)
- **Suite** `src/omni_one/engine/`: `foundry.py` `ontology.py` `workshop.py` `aip.py` `governance.py` `apollo.py`
- **Vision** `src/omni_one/core/vision.py`: Tesseract + OpenCV + Matplotlib ($0, offline, photo→text+chart)
- **Seller packs** `src/omni_one/packs/`: `seller_os.py` (parsers+briefing) `seller_scenarios.py` (12)
  `seller_close.py` (Daily Close) `seller_export.py` (CSV) `seller_parse.py` (money/fuzzy shared)

## Use it your way

```bash
omni-one briefing --demo --json b.json     # KPIs + alerts + draft
omni-one scenarios --demo                 # 12 ranked decisions
omni-one operations                        # full loop: briefing→ontology→workshop→AIP→audit
omni-one serve --port 5003 &               # API at /api/docs
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/seller/close {"demo":true}` | Daily Close bundle (hero) |
| `GET /api/v1/seller/close.csv?demo=true` | accountant CSV download |
| `POST /api/v1/pipeline/close` | pipeline evidence + cost + verdict |
| `POST /api/v1/vision/close` | photo → OCR + COGS + numbers bundle |
| `POST /api/v1/micro/close` | micro-biz (taco shop) daily ritual |
| `POST /api/v1/revenue/close` | RevOps pipeline review (tiers, churn $) |
| `POST /api/v1/ops/close` | methodology loop bundle (foundry→audit, verified) |
| `POST /api/v1/returns/close` | refund leaks + restock + reply drafts |
| `POST /api/v1/cashflow/close` | payouts in, bills out, runway |
| `POST /api/v1/reputation/close` | review reply queue + star repair |
| `POST /api/v1/forecast/close` | stockout forecast + safety stock + PO |
| `POST /api/v1/rollup/close` | multi-shop ranking + cross-shop plays |
| `POST /api/v1/auto/close` | **sniff a folder → run the right closes, with reasons** |
| `POST /api/v1/seller/briefing` / `operations` / `scenarios/run` | briefing / full loop / 12 decisions |
| `POST /api/v1/seller/photo` (multipart) | invoice photo → OCR+COGS |
| `POST /api/v1/analyze {"records":[...]}` | raw 4-layer pipeline |
| `GET /metrics` | Prometheus counters (12 closes/briefings/scenarios/vision) |
| MCP `python3 -m omni_one.mcp_server` | 17 tools for Claude/Cursor: `seller_close`, `pipeline_close`, `vision_close`, `micro_close`, `revops_close`, `ops_close`, `returns_close`, `cashflow_close`, `reputation_close`, `forecast_close`, `rollup_close`, `auto`, `seller_briefing`, `seller_scenarios`, `seller_operations`, `pipeline_analyze`, `vision_analyze` |

**Don't know which close to run?** Dump everything into one folder and run one command —
it sniffs your files/pics/docs and runs the right closes, telling you why:

```bash
omni-one auto --folder ./my_shop --out ./auto_today
# [✓] vision: 2 photo(s) found — OCR + COGS [receipt_001.png, ...]
# [✓] returns: return/refund files found — plug the leak [refunds.csv]
```

Python SDK: `from omni_one.client import OmniOneClient; OmniOneClient.local().close(demo=True)`.
Also `client.pipeline_close()`, `.vision_close()`, `.micro_close()`, `.revops_close()`, `.ops_close()`, `.returns_close()`, `.cashflow_close()`, `.reputation_close()`, `.forecast_close()`, `.rollup_close()`, `.auto(folder)` — local or HTTP.
CLI: `omni-one close | pipeline-close | vision-close | micro-close | revops-close | ops-close | returns-close | cashflow-close | reputation-close | forecast-close | rollup-close | auto`.

## vs. the world

| | Omni-One Daily Close | Shopify reports | LangChain/RAG demo | Enterprise suite |
|---|---|---|---|---|
| True profit (fees+ship+COGS, cited) | yes, `file:line` | GMV-centric | no | yes, enterprise cost |
| Stockout→PO draft | yes, offline | alerts only | no | custom build |
| Angry-customer drafts now | yes, copy-paste | no | generic chat | no |
| Cost / privacy | $0, laptop-private | subscription + cloud | API $$$ | enterprise $$$ |
| Audit (hash-chained, verify) | yes | no | no | yes |

## Verify (robust, offline)

```bash
make test    # 1350+ tests (core + methodology + seller + daily close + connectors + i18n + API matrix + e2e)
make test-all# + generated-client contracts (py/ts/go), regen check
make close   # Daily Close bundle -> ./close_today (ORDER TODAY + replies + PO)
make e2e     # methodology loop PASSED + golden KPIs (GMV $274 / profit $169.09)
make eval    # 500-record bypass/cost/latency -> docs/EVAL_REPORT.md
```

Scale of this repo: **100k+ LOC, 870+ files** — 10 channel connectors (58 fixtures),
5-locale i18n (EN/ES/ZH/FR/DE), 80-shop eval corpus + 9 notebooks, TS + Go + generated
Python/TS/Go clients (18 routes), Close + Accountant PWAs, K8s/Helm/Terraform/Grafana,
ES/ZH docs. See `docs/handbook/00-quick-reference.md`.

## Docs

- Ritual: `docs/DAILY_CLOSE.md` · 60s: `docs/QUICKSTART.md` · API: `docs/API.md` · CLI: `docs/CLI.md`
- Deploy/cron/7am: `docs/DEPLOYMENT.md` · Roadmap: `docs/ROADMAP.md` · Scenarios: `docs/SCENARIOS.md`
- Core: `docs/MULTI_LAYER_ARCHITECTURE.md` `docs/EVAL_REPORT.md` · Seller: `docs/SELLER_OS.md`
- Contribute: `CONTRIBUTING.md` (+ `CODE_OF_CONDUCT.md` `SECURITY.md` `CHANGELOG.md`)

## Roadmap

**v1.1 now**: Daily Close ritual (this README). **v1.2**: 7am cron+email, risk→$0 streak, margin trend,
multi-shop, ES/ZH drafts, TikTok parser. **v1.3**: DuckDB cost memory, shelf-photo counts, review webhook.
Propose a scenario: `.github/ISSUE_TEMPLATE/seller_scenario.yml`.

*Apache-2.0. Built for the shop that can't afford a data team — one close at a time.*
