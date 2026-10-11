# omnionego — Omni-One Go SDK

Go client for the Omni-One Seller OS API. `net/http` with context timeouts, retry with backoff, `X-API-Key` auth, typed structs, citation-preserving JSON. $0, offline-friendly.

Mirrors the Python SDK (`src/omni_one/client.py`) and the TS SDK (`sdks/ts/src/index.ts`): same methods, same close shape, same golden KPIs.

## Install

```bash
go get github.com/omni-one/sdk-go
```

Requires Go >= 1.21. No external dependencies (stdlib only).

## Quickstart

```go
package main

import (
    "context"
    "fmt"

    omnionego "github.com/omni-one/sdk-go"
)

func main() {
    c := omnionego.NewClient("http://localhost:5003", "")
    ctx := context.Background()

    h, err := c.Health(ctx)
    fmt.Println(h, err) // {alive local omni-one}

    b, _ := c.BriefingDemo(ctx, 42)
    fmt.Println(b.KPIs) // GMV 274.00 / true_profit 169.09

    close, _ := c.Close(ctx, omnionego.CloseOptions{Demo: true})
    fmt.Println(close.Headline)                 // "Profit $169.09 ..."
    fmt.Println(close.KPIs.TrueProfit)          // 169.09
    fmt.Println(close.KPIs.MoneyAtRiskUSD)      // > 0
    fmt.Println(close.ReorderSheet[0].Citation) // "inventory.csv:2" (verbatim)
    fmt.Println(close.ReplyQueue[0].Draft)      // copy-paste reply
    fmt.Println(close.PODraft[:60])             // "Subject: Reorder ..."
}
```

With an API key:

```go
c := omnionego.NewClient(baseURL, os.Getenv("OMNI_ONE_API_KEY"))
// sends `X-API-Key: ...` on every request
```

See `example/main.go` for the full demo (health → briefing → scenarios → close → CSV).

## API surface

| Method | Endpoint | Returns |
|---|---|---|
| `BriefingDemo(ctx, seed)` | `POST /api/v1/seller/briefing` | `*BriefingBundle` |
| `BriefingFolder(ctx, BriefingFolderOptions{Folder, Seed})` | `POST /api/v1/seller/briefing` | `*BriefingBundle` |
| `ScenariosRun(ctx, ScenariosRunOptions{Demo, Folder, Seed})` | `POST /api/v1/seller/scenarios/run` | `*ScenariosResult` |
| `Operations(ctx, seed)` | `POST /api/v1/seller/operations` | `*OperationsResult` |
| `Close(ctx, CloseOptions{Demo, Folder, Seed, Shop})` | `POST /api/v1/seller/close` | `*CloseBundle` (shape-validated) |
| `Analyze(ctx, records)` | `POST /api/v1/analyze` | `*AnalyzeResult` |
| `Health(ctx)` | `GET /health` | `*HealthResult` |
| `ExportCSV(ctx, CloseOptions)` | briefing + local CSV render | `string` (CSV) |
| `CloseCSV(ctx, CloseOptions)` | close + local renders | `*CloseCSVBundle` |

Typed structs: `CloseBundle`, `KPIs`, `ReorderLine`, `ReplyItem`, `MoneyLeak`, `BriefingBundle`, `ScenariosResult`, `OperationsResult`, `AnalyzeResult`, `HealthResult`. Close helpers in `close.go`: `SummariseClose`, `ValidateCloseForAccountant`, `CloseHeadline`, `CloseReordersToday`, `CloseP0Replies`.

## Reliability

- **Retry with backoff**: 3 tries on 429 / 408 / 5xx + network errors. Backoff 400ms → 800ms + jitter. Other 4xx fail fast with the server message.
- **Timeout**: per-attempt `context.WithTimeout` (default 30s, `Options.Timeout`). Pass your own `ctx` to chain cancellation; parent cancellation is never retried.
- **Auth**: `APIKey` option sends `X-API-Key` on every request.
- **Errors**: `*Error` (`.Status`, `.Path`, `.Attempts`), `*TimeoutError`, `*RateLimitError`.

## Citations (file:line passthrough)

`encoding/json` preserves strings verbatim, and every helper copies `Citation` / `Evidence` / `Draft` / `PODraft` cell-for-cell — never stripped, lowercased, or truncated. CSV renderers (`BriefingToCSV`, `CloseToCSV`, `ReorderToCSV`, `RepliesToTxt`) keep `file:line` (e.g. `inventory.csv:2`) so accountants can audit any dollar back to source.

## Contract

`tests/unit/test_sdk_contract.py` (Python) greps `client.go` for the JSON tags `headline`, `gmv`, `true_profit`, `money_at_risk_usd`, `reorder_sheet`, `product`, `reorder_qty`, `citation`, `reply_queue`, `draft`, `po_draft`. Keep them exact.
