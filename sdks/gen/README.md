# sdks/gen — GENERATED clients from openapi_snapshot.json (WAVE2-I)

> **GENERATED bulk — do not hand-edit `*_generated.*`.**
> Edit `openapi_snapshot.json`, then re-run `regen.py`.

## Contents

| File | Lines | Purpose |
|---|---|---|
| `openapi_snapshot.json` | 1500+ | Hand-written but complete OpenAPI-ish snapshot (`openapi 3.0.0`, `info.title omni-one`, `v1.1.0`). 18 paths + 6 schemas. Source of truth for codegen. |
| `python/client_generated.py` | ~2500 | GENERATED urllib-only client. Dataclasses + `OmniOneGeneratedClient` (18 methods). |
| `typescript/client_generated.ts` | ~2500 | GENERATED fetch client. Interfaces + class (18 methods, `AbortController` timeout). |
| `regen.py` | — | Validator + coverage checker. Must pass (`python3 sdks/gen/regen.py`). |
| `README.md` | — | This file. |

## 18 routes → 18 methods (1:1)

| # | Path | Verbs | Python / TS method |
|---|---|---|---|
| 1 | `POST /api/v1/seller/close` | post | `seller_close` |
| 2 | `GET /api/v1/seller/close.csv` | get | `seller_close_csv` |
| 3 | `POST /api/v1/seller/briefing` | post | `seller_briefing` |
| 4 | `POST /api/v1/seller/operations` | post | `seller_operations` |
| 5 | `GET /api/v1/seller/scenarios` | get | `seller_scenarios_list` |
| 6 | `POST /api/v1/seller/scenarios/run` | post | `seller_scenarios_run` |
| 7 | `GET /api/v1/seller/export.csv` | get | `seller_export_csv` |
| 8 | `POST /api/v1/seller/photo` | post multipart | `seller_photo` |
| 9 | `POST /api/v1/vision/analyze` | post multipart | `vision_analyze` |
| 10 | `GET /api/v1/vision/demo` | get | `vision_demo` |
| 11 | `POST /api/v1/analyze` | post | `analyze` |
| 12 | `POST /api/v1/synthesize` | post | `synthesize` |
| 13 | `POST /api/v1/revenue/health` | post | `revenue_health` |
| 14 | `POST /api/v1/micro/briefing` | post | `micro_briefing` |
| 15 | `GET /api/v1/metrics` (alias `GET /metrics` Prometheus text) | get | `get_metrics` |
| 16 | `GET /api/v1/models` | get | `list_models` |
| 17 | `GET /health` | get | `health` |
| 18 | `GET /api/v1/openapi-tags` | get | `openapi_tags` |

Schemas (6): `CloseBundle`, `KPIs`, `ReorderLine`, `ReplyItem`, `Briefing`, `ScenarioDecision`
(+ request bodies `CloseRequest`, `BriefingRequest`, `OperationsRequest`, `ScenariosRunRequest`,
`AnalyzeRequest`, `SynthesizeRequest`, `RevenueHealthRequest`, `MicroBriefingRequest`).

## Regeneration procedure

```bash
# 1. Edit the snapshot (ONLY source of truth you hand-edit):
$EDITOR sdks/gen/openapi_snapshot.json

# 2. If you added/renamed a path, add the matching method to BOTH clients:
#    python:  sdks/gen/python/client_generated.py  ->  def <method>(self, ...)
#    typescript: sdks/gen/typescript/client_generated.ts -> async <method>(...)
#    (For bulk regen, re-run the generators in /tmp or extend regen.py.)

# 3. Validate + coverage:
python3 sdks/gen/regen.py

# 4. Parsing guarantees:
python3 -c "import json; json.load(open('sdks/gen/openapi_snapshot.json')); print('snapshot valid')"
python3 -c "import ast; ast.parse(open('sdks/gen/python/client_generated.py').read()); print('py ok')"
# TS: balanced braces always; node --check attempted when node supports the ext,
# else brace-check (TS interfaces need tsc — see below).

# 5. Line counts:
wc -l sdks/gen/* sdks/gen/python/* sdks/gen/typescript/* docs/handbook/es/* docs/handbook/zh/*
```

`regen.py` asserts:
- snapshot is valid JSON, `openapi == 3.0.0`, `info.title == omni-one`, `info.version == 1.1.0`,
- all 18 paths present, all 6 schemas present,
- every path has a matching method in **both** clients (name search),
- python parses via `ast.parse`, TS braces balanced (+ best-effort `node --check`),
- prints a coverage table; exits non-zero on any gap.

## Version pinning

- Snapshot `info.version`, python `__VERSION__`, TS `GENERATED_VERSION` must all equal **`1.1.0`**.
- Servers pinned: `http://localhost:5003` (dev), docker alias, production placeholder.
- `regen.py` fails if versions diverge. Bump all three together.
- Snapshot date: `2026-10-11` (`info.x-snapshot-date`).
- Upstream sources: `src/omni_one/api/fastapi_app.py`, `src/omni_one/api/ops.py`,
  `src/omni_one/infra/fastapi_factory.py` (tags, `/health`, `/metrics`).

## Parsing guarantees

| Artifact | Guarantee | How verified |
|---|---|---|
| `openapi_snapshot.json` | Valid JSON, 1500+ lines | `json.load` in regen.py |
| `python/client_generated.py` | `ast.parse` clean, ~2500 lines, urllib-only, header `# GENERATED` | `ast.parse` in regen.py + `python3 -c` |
| `typescript/client_generated.ts` | Balanced `{}` (187/187), ~2500 lines, header `// GENERATED`, `fetch` + `AbortController` only | Brace count in regen.py; `node --check` attempted, skipped gracefully for `.ts` (`ERR_UNKNOWN_FILE_EXTENSION` → brace-check + optional `tsc --noEmit`) |

TS note: `node --check` on Node 20 does not accept `.ts` (`ERR_UNKNOWN_FILE_EXTENSION`).
That is expected — regen.py treats it as *skip gracefully* and still enforces brace balance
plus `interface`/`async <method>` presence. For strict type-check run:

```bash
npx --yes tsc --noEmit --skipLibCheck sdks/gen/typescript/client_generated.ts
```

## Design rules (both clients)

- **urllib / fetch only** — no `requests`, `httpx`, `pydantic`, no new deps.
- **retry + timeout + api-key** on every call (`X-API-Key` when provided; 429 retried, 400/401 fast-fail).
- **Citation-preserving**: return raw dict + typed wrapper; `.citations` / `citationsOf()` never drops `[file:line]`.
- **Docstrings with curl** on every method (copy-paste against `localhost:5003`).
- **Golden demo**: `seller_close(demo=True)` → `true_profit 169.09`, headline `Profit $169.09 (61.7%) …`.
- **Invariant**: `true_profit <= gmv` (`check_invariant_close` / `checkInvariantClose`).
