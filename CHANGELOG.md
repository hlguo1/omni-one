# Changelog

All notable changes. Format: Keep a Changelog. Versioning: SemVer.

## [Unreleased]

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
