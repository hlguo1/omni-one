# @omni-one/sdk-ts — Omni-One TypeScript SDK

Fetch-based client for the Omni-One Seller OS API. Works on **node18+** and **browsers**. $0, offline-friendly, citation-preserving.

Mirrors the Python SDK (`src/omni_one/client.py`): same methods, same close shape, same golden KPIs.

## Install

```bash
npm install @omni-one/sdk-ts
# dev (this repo):
#   cd sdks/ts && npm install && npm run build
```

Requires node >= 18 (global `fetch`). No runtime dependencies.

## Quickstart

```ts
import { OmniOneClient } from "@omni-one/sdk-ts";

const client = new OmniOneClient({ baseUrl: "http://localhost:5003" });

// Health
console.log(await client.health()); // { status: "alive", ... }

// Demo briefing (golden: GMV 274.00 / true_profit 169.09)
const briefing = await client.briefingDemo();
console.log(briefing.kpis);

// Daily close (profit, reorder+PO, reply drafts, leaks — all cited file:line)
const close = await client.close({ demo: true });
console.log(close.headline); // "Profit $169.09 ..."
console.log(close.kpis.true_profit); // 169.09
console.log(close.kpis.money_at_risk_usd); // > 0
console.log(close.reorder_sheet[0]); // { product, reorder_qty, citation: "inventory.csv:2", ... }
console.log(close.reply_queue[0].draft); // copy-paste reply (>40 chars)
console.log(close.po_draft.slice(0, 60)); // "Subject: Reorder ..."
```

With an API key:

```ts
const authed = new OmniOneClient({ baseUrl, apiKey: process.env.OMNI_ONE_API_KEY });
// sends `X-API-Key: ...` on every request
```

## API surface

| Method | Endpoint | Returns |
|---|---|---|
| `briefingDemo({seed})` | `POST /api/v1/seller/briefing` | `BriefingBundle` |
| `briefingFolder(folder, {seed})` | `POST /api/v1/seller/briefing` | `BriefingBundle` |
| `scenariosRun({demo, folder, seed})` | `POST /api/v1/seller/scenarios/run` | `ScenariosResult` |
| `operations({seed})` | `POST /api/v1/seller/operations` | `OperationsResult` |
| `close({demo, folder, seed, shop})` | `POST /api/v1/seller/close` | `CloseBundle` (shape-validated) |
| `analyze(records)` | `POST /api/v1/analyze` | `AnalyzeResult` |
| `health()` | `GET /health` | `HealthResult` |
| `exportCSV({demo, folder, seed})` | briefing + local CSV render | `string` (CSV) |
| `closeCSV({demo, folder, seed, shop})` | close + local renders | `CloseCSVBundle` |

Typed interfaces: `CloseBundle`, `KPIs`, `ReorderLine`, `ReplyItem`, `MoneyLeak`, `BriefingBundle`, `ScenariosResult`, `OperationsResult`, `AnalyzeResult`, `HealthResult`.

Close-only subpath:

```ts
import { closeToCsv, repliesToTxt } from "@omni-one/sdk-ts/close";
```

## Reliability

- **Retry with backoff**: 3 tries on 429 / 408 / 5xx + network errors. Backoff 400ms → 800ms + jitter. Other 4xx fail fast with the server message.
- **Timeout**: per-attempt `AbortController` timeout (default 30s, `timeoutMs` option, per-call `RequestOptions.timeoutMs`). Surfaced as `OmniOneTimeoutError`.
- **Auth**: `apiKey` option (or per-call override) sends `X-API-Key` on every request.
- **Errors**: `OmniOneError` (`.status`, `.path`, `.attempts`), `OmniOneTimeoutError`, `OmniOneRateLimitError`.

## Citations (file:line passthrough)

Every `citation` / `evidence` / `draft` / `po_draft` string passes through **verbatim** — never stripped, lowercased, or truncated. CSV helpers (`briefingToCsv`, `closeToCsv`, `reorderToCsv`, `repliesToTxt`) copy citations cell-for-cell so accountants can audit any dollar back to `file:line` (e.g. `inventory.csv:2`).

## ESM + CJS

Dual `exports` (`import` → `dist/esm`, `require` → `dist/cjs`). Build with `npm run build` (needs `typescript` dev dep). The source has no node-only imports, so bundlers + browsers work.

## Smoke test (no network)

```bash
node tests/run.mjs
# spins local expectations only; asserts method shapes + retry logic with mocked fetch
```

See `tests/run.mjs` and `../../examples/sdk_ts_demo.mjs`.
