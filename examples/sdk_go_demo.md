# Go SDK demo — `omnionego`

> Mirrors `examples/sdk_demo.py` (Python) and `examples/sdk_ts_demo.mjs` (TS) for Go.
> Full runnable program: [`sdks/go/example/main.go`](../sdks/go/example/main.go).

## Prerequisites

- Go >= 1.21 (`go version`)
- A running server for live calls: `PYTHONPATH=src python3 -m omni_one.cli serve --port 5003`
  (or `make serve`). Offline/contract checks need no server.

## Run the example (live)

```bash
# from the repo root
go run ./sdks/go/example
# custom server / key:
OMNI_ONE_BASE_URL=http://localhost:5003 OMNI_ONE_API_KEY=secret go run ./sdks/go/example
```

Expected output (golden demo, seed 42):

```text
health: status=alive mode=local service=omni-one
briefing: GMV=274.00 profit=169.09 margin=61.7% orders=8
scenarios: total=12
close: Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY
  true_profit=169.09 at_risk=102.75
  reorder[0]: Tote Bag Handmade x10 [[inventory.csv:2] ...] urgency=ORDER TODAY
  reply[0]: Hi Alice! I'm really sorry ... [[instagram_dm.txt:1] ...]
  po: Subject: Reorder request — Acme Textiles ...
csv bytes: close=… reorder=… replies=… po=…
summary: profit=169.09 margin=61.7% replies=3 today=1 citation=[inventory.csv:2] ...
accountant check: packable (all citations present)
```

## Minimal snippet

```go
import (
    "context"
    omnionego "github.com/omni-one/sdk-go"
)

c := omnionego.NewClient("http://localhost:5003", "")
close, err := c.Close(context.Background(), omnionego.CloseOptions{Demo: true})
// close.Headline, close.KPIs.TrueProfit, close.KPIs.MoneyAtRiskUSD,
// close.ReorderSheet[0].Product/.ReorderQty/.Citation,
// close.ReplyQueue[0].Draft/.Citation, close.PODraft
```

## Method map (parity with Python + TS SDKs)

| Go | Python | TypeScript | Endpoint |
|---|---|---|---|
| `BriefingDemo(ctx, seed)` | `briefing_demo(seed)` | `briefingDemo({seed})` | `POST /api/v1/seller/briefing` |
| `BriefingFolder(ctx, {Folder, Seed})` | `briefing_folder(folder)` | `briefingFolder(folder)` | `POST /api/v1/seller/briefing` |
| `ScenariosRun(ctx, {Demo, Folder, Seed})` | `scenarios_run(demo, folder)` | `scenariosRun({demo, folder})` | `POST /api/v1/seller/scenarios/run` |
| `Operations(ctx, seed)` | `operations(seed)` | `operations({seed})` | `POST /api/v1/seller/operations` |
| `Close(ctx, {Demo, Folder, Seed, Shop})` | `close(demo, folder, shop)` | `close({demo, folder, shop})` | `POST /api/v1/seller/close` |
| `Analyze(ctx, records)` | `analyze(records)` | `analyze(records)` | `POST /api/v1/analyze` |
| `Health(ctx)` | `health()` | `health()` | `GET /health` |
| `ExportCSV(ctx, opts)` | `export_csv(demo, folder)` | `exportCSV(opts)` | briefing + local render |
| `CloseCSV(ctx, opts)` | `closeCSV` via `close_to_csv` | `closeCSV(opts)` | close + local renders |

## Reliability notes

- Retry: 3 tries on 429 / 408 / 5xx + network errors, 400ms → 800ms + jitter.
- Timeout: per-attempt `context.WithTimeout` (default 30s).
- Auth: API key → `X-API-Key` header.
- Citations: `Citation` / `Evidence` / `Draft` / `PODraft` pass through verbatim
  (`file:line` never stripped). CSV helpers copy them cell-for-cell.

## No-network checks

```bash
go vet ./sdks/go/... && go build ./sdks/go/...
PYTHONPATH=src python3 -m pytest tests/unit/test_sdk_contract.py -q  # parses client.go statically
```
