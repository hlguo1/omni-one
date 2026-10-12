# Changelog

All notable changes. Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]

### Fixed
- `GET /status` 500 (`HealthStatus.components.checks` was a list, model demands dicts): endpoint wraps checks as `{items, total, healthy}`; tolerant test hardened into strict 200 + dict-components regression test

### Fixed/CI
- CI `ci.yml`: new API probe job step (`/status` 200 + all 12 closes 200 + tools/tags/counters cross-checked against code), regen now fails on drift (`grep REGEN PASS`), CLI smoke covers `auto` + wave-2 closes, docker job probes `/status` + `/api/v1/auto/close`; `permissions: read` + `concurrency` cancel on both workflows; `seller-ci.yml` normalized to `python3`
- Makefile: new `make auto` (one-command router) + `make closes` (wave-2 smoke)

### Added (close-pack wave 2 + AUTO router)
- Returns Close `src/omni_one/packs/returns_close.py` + docs/RETURNS_CLOSE.md ($868.73 refunded, top leak wrong_item $359.02)
- Cash-Flow Close `src/omni_one/packs/cashflow_close.py` + docs/CASHFLOW_CLOSE.md ($4,948.69 net 7d, runway 50.3d)
- Reputation Close `src/omni_one/packs/reputation_close.py` + docs/REPUTATION_CLOSE.md (4.2★, reply queue, gripe themes)
- Forecast Close `src/omni_one/packs/forecast_close.py` + docs/FORECAST_CLOSE.md (safety stock, stockout dates, PO)
- Multi-Shop Rollup Close `src/omni_one/packs/rollup_close.py` + docs/ROLLUP_CLOSE.md (4 shops, $101,127 GMV, ranking)
- **AUTO router `src/omni_one/packs/auto_close.py` + docs/AUTO_CLOSE.md**: `omni-one auto --folder ./my_shop` sniffs files/pics/docs, runs the right closes with cited reasons, never hard-fails (demo fallback); no folder = demo showcase
- Wiring wave 2: CLI (6 commands), SDK (6 methods), API (6 endpoints), MCP (17 tools), Prometheus (17 counters)

### Added (close-pack wave: 5 new flagship closes, 1399 tests green)
- Pipeline Analyze Close `src/omni_one/packs/pipeline_close.py` + docs/PIPELINE_CLOSE.md (evidence + cost ledger + verdict, mock-LLM, $0)
- Vision Close `src/omni_one/packs/vision_close.py` + docs/VISION_CLOSE.md (photo→OCR + numbers + COGS + chart, offline)
- Micro-biz Close `src/omni_one/packs/micro_close.py` + docs/MICRO_CLOSE.md (taco-shop ritual: revenue, buys, win-backs, vendor SMS, locale)
- RevOps Close `src/omni_one/packs/revops_close.py` + docs/REVOPS_CLOSE.md (pipeline tiers, churn $ at risk, call sheet, top plays)
- Ops-loop Close `src/omni_one/packs/ops_close.py` + docs/OPS_CLOSE.md (foundry→ontology→workshop→AIP→audit, hash-verified)
- Wiring: CLI (`pipeline-close`, `vision-close`, `micro-close`, `revops-close`, `ops-close`), SDK (`pipeline_close`/`vision_close`/`micro_close`/`revops_close`/`ops_close`), API (`POST /api/v1/{pipeline,vision,micro,revenue,ops}/close`), MCP (11 tools), Prometheus (+5 counters)

### Added (scale push: ~100k LOC, 1350+ tests)
- Connectors universe `src/omni_one/connectors/` (10 channels + payouts reconcile, 58 fixtures, fee/refund/currency/date hardened)
- i18n `src/omni_one/i18n/` (EN/ES/ZH/FR/DE drafts + channel DM/review normalizers, 30 fixtures)
- Close PWA `web/close/` + Accountant PWA `web/accountant/` (offline, printable, 10 sample pairs) + `web/seller.html` Close banner
- SDKs: hand TS + Go (`sdks/ts`, `sdks/go`) + generated Python/TS/Go (`sdks/gen`, 18 routes, regen-checked, COMPATIBILITY matrix)
- Evals: `evals/` generator + runner + 6-shop corpus + 80-shop `corpus_big` + gate test; 9 notebooks
- Deploy: prod Dockerfile, K8s + dev/staging/prod overlays, Helm, Terraform, Grafana, backup/restore, cron, compose variants, devcontainer, Tiltfile, per-shop examples, load selftest (p95 469ms)
- Docs: handbook (routine/supplier/reply/accountant/incidents/thresholds/quick-ref) + full ES/ZH translations
- Tests: API contract matrix (3 files), multishop + persistence e2e, property/fuzz/contract, corpus gate, deploy validation — 1350+ green

### Added
- `omni-one` CLI (`demo`, `briefing`, `scenarios`, `serve`, `eval`, `doctor`, `export`) + `pip install -e .`
- Python SDK `omni_one.client.OmniOneClient` (briefing/scenarios/operations/vision/health, retry + file:line passthrough)
- MCP server `src/omni_one/mcp_server.py` (tools: seller_briefing, seller_scenarios, seller_operations, vision_analyze, pipeline_analyze) for Claude/Cursor
- Prometheus metrics: `GET /metrics` (briefings, scenarios, vision, pipeline counters) + `GET /api/v1/seller/export.csv`
- `Makefile` (install/demo/test/e2e/serve/docker/lint), `pre-commit`, full CI matrix, Dependabot, Docker ignore
- Community health: LICENSE (Apache-2.0), CONTRIBUTING, Code of Conduct, Security policy, PR/issue templates, CODEOWNERS, FUNDING
- `examples/` quickstart shops (demo + empty template), `docs/QUICKSTART.md`, `docs/API.md`, `docs/CLI.md`, `docs/DEPLOYMENT.md`, `docs/ROADMAP.md`
- Coverage + golden-KPI gates in CI

### Changed
- README rewritten for 60-second adoption: badges, quickstart, comparison, architecture, roadmap
- API OpenAPI tags extended (Seller OS, Vision, Verticals, Ops); versioned title

## [1.0.0] — 2026-04-16
- 4-layer pipeline + ontology suite + Seller OS 12 scenarios + vision OCR + audit chain
- 24 unit + 7 integration tests, E2E methodology loop, golden KPIs (GMV $274 / profit $169.09)
- Daily Close `locale` (en/es/zh/fr/de) end-to-end: pack → CLI `--locale` → SDK/API/MCP `locale` → Close PWA dropdown; numbers invariant, drafts localized
- Wave 3: Go generated client + gen contract suites (42 py / 86 ts / go httptest green),
  80-shop corpus_big + INDEX, notebooks 05–10, handbook 00/06–09 + ES/ZH mirrors,
  68 connector fixtures, 10 accountant sample pairs, k8s overlays, compose variants,
  devcontainer, Tiltfile, per-shop deploy examples, cron i18n + README
- Scale: ~100k LOC / 900+ files / 1350+ tests green (unit + integration + contracts)
