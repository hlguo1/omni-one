# Compatibility — generated clients vs server

Source of truth: `sdks/gen/openapi_snapshot.json` (openapi 3.0.0, v1.1.0, 18 paths, 6 schemas).

| Client | Methods | Transport | Retry | Timeout | Check |
|---|---|---|---|---|---|
| `sdks/gen/python/client_generated.py` | 18 | urllib (stdlib) | 429/408/5xx ×3 exp-backoff | 30s | `pytest sdks/gen/python/tests/` 42 green |
| `sdks/gen/typescript/client_generated.ts` | 18 async | fetch + AbortController | 429/5xx ×3 | 30s | `node .../contract.mjs` 86 green |
| `sdks/gen/go/client_generated.go` | 18 | net/http + context | 429/408/5xx ×3 | 30s | `go test ./...` green |
| `sdks/ts/src/index.ts` (hand) | 9 | fetch | 429/5xx ×3 | 30s | `node sdks/ts/tests/run.mjs` 38 green |
| `sdks/go/client.go` (hand) | 9 | net/http | 429/408/5xx ×3 | 30s | `go vet/build` clean |
| `src/omni_one/client.py` (python) | 7 | httpx or in-process | httpx-level | 30s | unit contract green |

Regenerate: edit snapshot → mirror in all 3 generated clients → `python3 sdks/gen/regen.py`
(18/18 coverage required). Citations are never stripped — every client returns raw
`file:line` strings verbatim.
