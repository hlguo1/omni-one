# API

> 先看 Base 和健康检查，再看路由。默认全本地（$0，mock LLM）。
> 所有卖家数字都引用 `file:line`。

## Base 与可观测性

Base: `http://localhost:5003`. Docs: `/api/docs`. Health: `/health`, `/readiness`, `/status`, `/ping`. Metrics: `/metrics` (Prometheus).

启动服务器：

```bash
omni-one serve --port 5003
curl -sf http://localhost:5003/health
```

平台说明：

- 默认 Mock LLM（`SELLER_LLM=mock`，`$0`）。
- `GET /metrics` 里有计数器（briefings、场景、结算、视觉 + `omni_one_up`）。
- 审计 `verify()` 证明防篡改。见 `SECURITY.md`。
- 上传限制（5MB、类型检查、60/min）。
- 文件夹关在 `ALLOWED_ROOT` 内。
- 演示 key（`demo-key`/`test-key`）在生产会被拒绝。

## 每日结算（核心）

早晨仪式三路由。计数器 `closes_total` 随每次结算增长。

- `POST /api/v1/seller/close` `{"demo":true}` or `{"folder":"/path","shop":"Maya's"}` → close bundle (headline, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft). Counter `closes_total`.
- `GET /api/v1/seller/close.csv?demo=true` → accountant CSV download.
- `GET /api/v1/seller/export.csv?demo=true` → briefing CSV.

`curl` 示例：

```bash
curl -s -X POST http://localhost:5003/api/v1/seller/close \
  -H 'Content-Type: application/json' -d '{"demo":true}' | head -c 500
curl -s 'http://localhost:5003/api/v1/seller/close.csv?demo=true' -o close.csv
curl -s 'http://localhost:5003/api/v1/seller/export.csv?demo=true' -o briefing.csv
```

期望的黄金标题：

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

落盘输出（等价 CLI）：

```bash
omni-one close --demo --out ./close_today
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

## Seller OS

卖家操作系统的五个路由：从简报到完整循环。

- `POST /api/v1/seller/briefing` — true profit/stockout/alerts/draft/chart.
- `POST /api/v1/seller/operations` — briefing→ontology→workshop→AIP→audit full loop.
- `GET /api/v1/seller/scenarios` — 12-scenario registry + thresholds.
- `POST /api/v1/seller/scenarios/run` — ranked idempotent decisions + workshop + audit.
- `POST /api/v1/seller/photo` (multipart) — supplier invoice/product photo → OCR+chart+pipeline.

示例：

```bash
curl -s -X POST http://localhost:5003/api/v1/seller/briefing -H 'Content-Type: application/json' -d '{"demo":true}'
curl -s -X POST http://localhost:5003/api/v1/seller/scenarios/run -H 'Content-Type: application/json' -d '{"demo":true}'
curl -s http://localhost:5003/api/v1/seller/scenarios
```

阈值（代码 `src/omni_one/packs/seller_scenarios.py`）：

- 断货 5d、覆盖 14d、费率 12%、运费 20%、毛利 10%、积压 3、不一致 5%。
- 见 `docs/SCENARIOS.md` 和 `docs/handbook/00-quick-reference.md`。

## 引擎

引擎七路由：pipeline、门控合成、视觉、指标与实验。

- `POST /api/v1/analyze` `{"records":[...]}` — 4-layer pipeline + evidence + cost.
- `POST /api/v1/synthesize` — gated LLM synthesis with cache + citations.
- `POST /api/v1/vision/analyze` (multipart) / `GET /api/v1/vision/demo` — free OCR+chart.
- `GET /api/v1/metrics` — live 200-record eval metrics. `GET /api/v1/models` — model catalog.
- Labs: `POST /api/v1/micro/briefing`, `POST /api/v1/revenue/health`.
- Admin (`X-API-Key`/`Bearer`, fail closed): `GET /api/v1/admin/services`, `POST /api/v1/admin/clear-cache`.

引擎示例：

```bash
curl -s -X POST http://localhost:5003/api/v1/analyze -H 'Content-Type: application/json' -d '{"records":[]}'
curl -s http://localhost:5003/api/v1/metrics
curl -s http://localhost:5003/api/v1/models
curl -s http://localhost:5003/api/v1/vision/demo
```

SDK 与 MCP（等价）：

```python
from omni_one.client import OmniOneClient
OmniOneClient.local().close(demo=True)["headline"]
```

```json
{"tool":"seller_close","args":{"demo":true}}
```

## 汇总表（18 路由）

| # | 路由 | 分组 |
|---|---|---|
| 1 | `POST /api/v1/seller/close` | 结算 |
| 2 | `GET /api/v1/seller/close.csv` | 结算 |
| 3 | `GET /api/v1/seller/export.csv` | 结算 |
| 4 | `POST /api/v1/seller/briefing` | seller OS |
| 5 | `POST /api/v1/seller/operations` | seller OS |
| 6 | `GET /api/v1/seller/scenarios` | seller OS |
| 7 | `POST /api/v1/seller/scenarios/run` | seller OS |
| 8 | `POST /api/v1/seller/photo` | seller OS |
| 9 | `POST /api/v1/analyze` | 引擎 |
| 10 | `POST /api/v1/synthesize` | 引擎 |
| 11 | `POST /api/v1/vision/analyze` | 引擎 |
| 12 | `GET /api/v1/vision/demo` | 引擎 |
| 13 | `GET /api/v1/metrics` | 引擎 |
| 14 | `GET /api/v1/models` | 引擎 |
| 15 | `POST /api/v1/micro/briefing` | 实验 |
| 16 | `POST /api/v1/revenue/health` | 实验 |
| 17 | `GET /api/v1/admin/services` | 管理 |
| 18 | `POST /api/v1/admin/clear-cache` | 管理 |

All seller numbers cite `file:line`. Mock LLM by default (`SELLER_LLM=mock`, `$0`).
