# API

> Base y salud primero, rutas después. Todo local por defecto ($0, mock LLM).
> Cada número de vendedor cita `file:line`.

## Base y observabilidad

Base: `http://localhost:5003`. Docs: `/api/docs`. Health: `/health`, `/readiness`, `/status`, `/ping`. Metrics: `/metrics` (Prometheus).

Arranque del servidor:

```bash
omni-one serve --port 5003
curl -sf http://localhost:5003/health
```

Notas de plataforma:

- Mock LLM por defecto (`SELLER_LLM=mock`, `$0`).
- Contadores en `GET /metrics` (briefings, escenarios, cierres, visión + `omni_one_up`).
- Auditoría `verify()` demuestra inviolabilidad. Ver `SECURITY.md`.
- Subidas limitadas (5MB, con tipo verificado, 60/min).
- Carpetas enjauladas en `ALLOWED_ROOT`.
- Claves demo (`demo-key`/`test-key`) rechazadas en producción.

## Cierre diario (héroe)

El ritual de la mañana en tres rutas. El contador `closes_total` crece por cierre.

- `POST /api/v1/seller/close` `{"demo":true}` o `{"folder":"/path","shop":"Maya's"}` → close bundle (headline, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft). Counter `closes_total`.
- `GET /api/v1/seller/close.csv?demo=true` → accountant CSV download.
- `GET /api/v1/seller/export.csv?demo=true` → briefing CSV.

Ejemplo con `curl`:

```bash
curl -s -X POST http://localhost:5003/api/v1/seller/close \
  -H 'Content-Type: application/json' -d '{"demo":true}' | head -c 500
curl -s 'http://localhost:5003/api/v1/seller/close.csv?demo=true' -o close.csv
curl -s 'http://localhost:5003/api/v1/seller/export.csv?demo=true' -o briefing.csv
```

Titular dorado esperado:

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

Salida en disco (vía CLI equivalente):

```bash
omni-one close --demo --out ./close_today
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

## Seller OS

Cinco rutas del sistema operativo del vendedor: del resumen al bucle completo.

- `POST /api/v1/seller/briefing` — true profit/stockout/alerts/draft/chart.
- `POST /api/v1/seller/operations` — briefing→ontology→workshop→AIP→audit full loop.
- `GET /api/v1/seller/scenarios` — 12-scenario registry + thresholds.
- `POST /api/v1/seller/scenarios/run` — ranked idempotent decisions + workshop + audit.
- `POST /api/v1/seller/photo` (multipart) — supplier invoice/product photo → OCR+chart+pipeline.

Ejemplos:

```bash
curl -s -X POST http://localhost:5003/api/v1/seller/briefing -H 'Content-Type: application/json' -d '{"demo":true}'
curl -s -X POST http://localhost:5003/api/v1/seller/scenarios/run -H 'Content-Type: application/json' -d '{"demo":true}'
curl -s http://localhost:5003/api/v1/seller/scenarios
```

Umbrales (código `src/omni_one/packs/seller_scenarios.py`):

- rotura 5d, cobertura 14d, comisiones 12%, envío 20%, margen 10%, cola 3, descuadre 5%.
- Ver `docs/SCENARIOS.md` y `docs/handbook/00-quick-reference.md`.

## Motor

Siete rutas del motor: pipeline, síntesis con compuerta, visión, métricas y laboratorio.

- `POST /api/v1/analyze` `{"records":[...]}` — 4-layer pipeline + evidence + cost.
- `POST /api/v1/synthesize` — gated LLM synthesis with cache + citations.
- `POST /api/v1/vision/analyze` (multipart) / `GET /api/v1/vision/demo` — free OCR+chart.
- `GET /api/v1/metrics` — live 200-record eval metrics. `GET /api/v1/models` — model catalog.
- Labs: `POST /api/v1/micro/briefing`, `POST /api/v1/revenue/health`.
- Admin (`X-API-Key`/`Bearer`, fail closed): `GET /api/v1/admin/services`, `POST /api/v1/admin/clear-cache`.

Ejemplo del motor:

```bash
curl -s -X POST http://localhost:5003/api/v1/analyze -H 'Content-Type: application/json' -d '{"records":[]}'
curl -s http://localhost:5003/api/v1/metrics
curl -s http://localhost:5003/api/v1/models
curl -s http://localhost:5003/api/v1/vision/demo
```

SDK y MCP (equivalentes):

```python
from omni_one.client import OmniOneClient
OmniOneClient.local().close(demo=True)["headline"]
```

```json
{"tool":"seller_close","args":{"demo":true}}
```

## Tabla resumen (18 rutas)

| # | Ruta | Grupo |
|---|---|---|
| 1 | `POST /api/v1/seller/close` | cierre |
| 2 | `GET /api/v1/seller/close.csv` | cierre |
| 3 | `GET /api/v1/seller/export.csv` | cierre |
| 4 | `POST /api/v1/seller/briefing` | seller OS |
| 5 | `POST /api/v1/seller/operations` | seller OS |
| 6 | `GET /api/v1/seller/scenarios` | seller OS |
| 7 | `POST /api/v1/seller/scenarios/run` | seller OS |
| 8 | `POST /api/v1/seller/photo` | seller OS |
| 9 | `POST /api/v1/analyze` | motor |
| 10 | `POST /api/v1/synthesize` | motor |
| 11 | `POST /api/v1/vision/analyze` | motor |
| 12 | `GET /api/v1/vision/demo` | motor |
| 13 | `GET /api/v1/metrics` | motor |
| 14 | `GET /api/v1/models` | motor |
| 15 | `POST /api/v1/micro/briefing` | labs |
| 16 | `POST /api/v1/revenue/health` | labs |
| 17 | `GET /api/v1/admin/services` | admin |
| 18 | `POST /api/v1/admin/clear-cache` | admin |

All seller numbers cite `file:line`. Mock LLM by default (`SELLER_LLM=mock`, `$0`).
