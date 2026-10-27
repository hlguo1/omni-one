# Contributing to Omni-One

Thanks for helping make local-first intelligence useful. We optimize for: **$0 default, offline-first, cited, audited.**

## 60-second setup

```bash
git clone https://github.com/garyguo123456789/omni-one.git
cd omni-one
pip install -r requirements-seller.txt   # minimal $0
# or: pip install -e ".[dev]"
make test        # 31 tests, offline
make demo        # Seller OS demo, golden KPIs
```

## Notification email (required before your first PR)

Stale-branch notices go to the branch creator's commit email. Set a real,
deliverable address before you commit:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

Then add and verify the same address at
[github.com/settings/emails](https://github.com/settings/emails). The bot only
emails addresses that GitHub has verified and linked to your account. Do **not**
use an `@users.noreply.github.com` address — GitHub cannot deliver mail to it,
and the cleanup bot will skip your branch (or route it to the maintainer
fallback).

If you already pushed with a throwaway or noreply address, rewrite your branch
before opening the PR (`git commit --amend --reset-author --no-edit`, or
`git rebase -i` for multiple commits). The `commit-email` CI check fails PRs
whose human-authored commits use a noreply or unverified address.

The cleanup bot emails on days 12–14 of branch inactivity and deletes on day
15 unless you comment `/opt-out` on the tracking issue.

## How to contribute

1. **Find an issue** — look for `good first issue` / `help wanted`. Seller OS scenarios (`docs/SCENARIOS.md`) are the best entry point.
2. **Branch**: `git checkout -b feat/<short-name>`
3. **Code style**: `pre-commit run --all-files` (ruff + end-of-file + yaml). Line length 110.
4. **Tests required**: every fix/feature needs a unit test in `tests/unit/` or `tests/integration/`. Run `PYTHONPATH=src python3 -m pytest tests/unit tests/integration -q`.
5. **Determinism rule**: no wall-clock randomness in parsers/scenarios. Pass `seed=` explicitly. Stable IDs for Workshop decisions (idempotent reruns must not duplicate).
6. **$0 rule**: new deps must be optional. Core + Seller OS run with `requirements-seller.txt` only. Heavy deps go in `[project.optional-dependencies]`.
7. **Evidence rule**: user-facing numbers must carry `file:line` citations. No phantom Workshop tasks — queue only FROM ontology objects.

## PR checklist

- [ ] `make test` passes locally
- [ ] `make lint` passes (ruff)
- [ ] Added/updated test
- [ ] Updated docs if user-facing (`docs/`, `README.md`, `CHANGELOG.md` under Unreleased)
- [ ] No secrets, no absolute paths, no `__pycache__`
- [ ] Commit author email is real and verified (not `@users.noreply.github.com`)

## Project layout

- `src/omni_one/core/` — 4-layer deterministic pipeline (ingest → statistical → ML features → gated LLM)
- `src/omni_one/engine/` — Foundry / Ontology / Workshop / AIP / Governance / Apollo / Gotham ($0 methodology)
- `src/omni_one/packs/seller_os.py` — THE highlight app + `seller_scenarios.py` (12 scenarios) + `seller_parse.py`
- `src/omni_one/api/fastapi_app.py` — REST: `/seller/*`, `/vision/*`, `/analyze`
- `src/omni_one/cli.py` — `omni-one` CLI; `src/omni_one/client.py` — Python SDK; `src/omni_one/mcp_server.py` — MCP
- `scripts/` — demos + E2E; `web/seller.html` — single-page Seller OS UI; `examples/` — sample shop folders

## Release

Maintainers: bump `pyproject.toml` version, add `CHANGELOG.md` entry, tag `vX.Y.Z`. CI builds Docker + runs golden-KPI check.

## Code of Conduct

Be kind. See `CODE_OF_CONDUCT.md`. Violations → open an issue titled `[CoC]`.
