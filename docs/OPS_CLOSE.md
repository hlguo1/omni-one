# OPS CLOSE — flagship methodology loop bundle (PACK E)

> One command every morning closes the ops loop: data is versioned,
> the twin is seeded, the queue is grounded, the answer is evaluated,
> the audit is verified, and three files are filed. Deterministic,
> mock-only, $0, offline.

## 1. The loop

```text
                    ┌──────────────────────────────────────────────────┐
                    │              OPS CLOSE (ops-daily)               │
                    └──────────────────────────────────────────────────┘

  raw seller events (orders / inventory / reviews / DMs / supplier)
        │
        ▼
  ┌─────────────┐   versions products + orders, LEFT JOINs them
  │   FOUNDRY   │   on lower(name)=lower(product). DuckDB missing?
  │ version+join│──▶ recorded SKIP with reason (loop never crashes).
  └─────────────┘
        │
        ▼
  ┌─────────────┐   Product / Order / Shipment types + actions.
  │  ONTOLOGY   │   Products ← chart labels + scenario products
  │    twin     │   (shared rows => foundry/ontology agree on SKUs).
  └─────────────┘   Orders ← order events. Shipments ← supplier lines.
        │           Links: ORDER_CONTAINS, SHIPMENT_FULFILLS (best-effort).
        ▼
  ┌─────────────┐   run_all_scenarios (12 detectors, md5 stable IDs)
  │  SCENARIOS  │──▶ scenarios_to_workshop → WorkshopApp.add_decision
  │     x12     │   with stable_id (re-runs UPSERT, never duplicate).
  └─────────────┘   Fallback: build_seller_queue (recorded in `via`).
        │
        ▼
  ┌─────────────┐   Every decision cites Type:pk from THIS run's twin.
  │  WORKSHOP   │   Ungroundable scenario? Falls back to first Product.
  │    queue    │   References are NEVER invented (see §2).
  └─────────────┘
        │
        ▼
  ┌─────────────┐   seller_stockout on the FIRST SKU (sorted).
  │     AIP     │   Citations grounding-checked vs the twin.
  │  grounded   │   evaluate() case asserts answer ⊇ SKU + grounded:
  └─────────────┘   pass_rate must stay 1.0 before close.
        │
        ▼
  ┌─────────────┐   ingest_workshop + ingest_ontology_edits into a
  │ GOVERNANCE  │   hash-chained AuditLog. verify()["ok"] is the
  │    audit    │   `verified` bool; `head` is the 12-char chain tip.
  └─────────────┘
        │
        ▼
  ┌─────────────┐   close.json (full close) + decisions.csv (queue for
  │   BUNDLE    │   sheets/accounting) + audit.json (stats + head copy).
  │   3 files   │   Exactly three files — the morning file-set.
  └─────────────┘
```

Entry point: `build_ops_close(events, briefing=None, scen=None,
namespace="ops-daily")` in `src/omni_one/packs/ops_close.py`.
`briefing` / `scen` are DI seams (prebuilt inputs accepted, built when
`None`); `namespace` isolates parallel loops (`ops-daily`,
`ops-nightly`, …).

## 2. No-phantoms rule (load-bearing)

A *phantom* is a decision that cites an object that does not exist —
the ops equivalent of a hallucinated citation. This pack forbids them
structurally, not by convention:

1. **Seed before queue.** Products are seeded from the briefing chart
   labels *plus* every scenario decision's `product` field, so each
   scenario has a twin object waiting before the queue is built.
2. **Shared rows.** `_product_rows()` feeds *both* the foundry version
   and the ontology seed, so SKUs and counts agree across stages.
3. **Grounded builder.** `scenarios_to_workshop()` resolves each
   decision to a live `Product:pk` (exact name → fuzzy ≥0.60 → first
   Product). If nothing resolves, the decision is *skipped*, never
   invented.
4. **Emitted proof.** Every close ships `ontology.refs` — the sorted
   `Type:pk` inventory of the twin. Tests assert every
   `decisions[].object_ref ∈ refs` (16 refs on the demo: 4 Product +
   8 Order + 4 Shipment).

If you add a 13th scenario, add its `product` (or accept first-Product
fallback) and its action (see §3) — the phantom test will catch you if
you forget.

## 3. Approval flow (human-in-the-loop)

Queuing is automatic; **acting is not**. The operator works each
decision with proposal + lead review before anything writes:

| Step | Call | Effect |
|------|------|--------|
| 1. Own | `WorkshopApp.assign(decision_id, "ops-1")` | `open → assigned`, assignee set, history appended |
| 2. Approve | `WorkshopApp.approve(decision_id, "lead")` | propose via `Ontology.propose_action` → approve via `Ontology.approve_action` → `assigned → approved`; writeback lands on the twin object |
| 3. Close | `WorkshopApp.resolve(decision_id, "lead", note)` | `approved → resolved`, note in history |

Guards: every scenario action (`reorderProduct`, `markDownProduct`,
`reviewPricing`, `alignPrice`, `requestReview`, `renegotiateSupplier`,
`messageCustomer`, `replyReview`, `triageDMs`, `adjustShipping`,
`rerouteShipment`) is defined on the twin with `requires_approval=True`
and `allowed_approvers=["lead"]`, so a non-lead approval raises instead
of writing. Every transition (including rejections) is history-logged
on the decision *and* hash-chained by governance.

`do_today` always emits exactly three steps following this flow:
`Approve X via lead` → `Assign Y to ops-1` → `Re-run eval`
(pass_rate must read 1.00).

## 4. Determinism contract

- Same `events` → same decision `stable_id` list (ordered **and**
  sorted) + same `kpis` + same workshop/ontology/aip counts.
  Scenario IDs are `md5(scenario:key)`; workshop upserts on
  `stable_id`, so re-runs never duplicate.
- **Excluded by design:** foundry version strings, audit `at`
  timestamps, and the audit `head` are wall-clock (same logic, new
  transaction id — like Foundry itself). Tests pin counts, never heads.
- Mock only: no network, no LLM keys, no vector DB. Works on plane wifi.

## 5. Wiring note (intended, NOT implemented in this pack)

This pack ships the loop as a pure function + bundle writers only.
Per the task boundary (`cli.py`, `client.py`, `api/`, `mcp_server.py`
untouched), the operator surfaces are described here for the next pack:

```python
# Intended CLI — omni-one ops-close --demo --out ./ops_close_today
from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
from omni_one.packs.ops_close import build_ops_close, write_close_bundle

events, _ = ingest_seller_folder(demo_folder)
close = build_ops_close(events)
paths = write_close_bundle(close, "./ops_close_today")
print(close["headline"])          # OPS CLOSE ops-daily: 8 decisions ...
for step in close["do_today"]:
    print(" •", step)
```

```python
# Intended API — POST /api/v1/ops/close {"demo": true, "seed": 42}
# Handler mirrors seller_operations in src/omni_one/api/fastapi_app.py:
#   ingest demo folder -> build_ops_close(events) -> return {
#     "headline": ..., "kpis": ..., "decisions": ...[:20],
#     "workshop": ..., "aip": {"grounded","answer","pass_rate":...},
#     "governance": ..., "free": True }
```

Both surfaces return the **same dict** `build_ops_close` produces, so
CLI, API, and tests can never drift apart.

## 6. Golden numbers (seller demo, seed=42 — pinned by tests)

Observed from `make_seller_demo_folder(seed=42)` → `build_ops_close`:

- Headline: `OPS CLOSE ops-daily: 8 decisions (8 open, 0 resolved) ·
  grounded 1/1 · audit verified True · head <12-hex, wall-clock>`
- `kpis`: decisions **8**, open **8**, resolved **0**,
  grounded_rate **1.0**, audit_events **36**, verified **True**
- Workshop: total **8** via `scenarios_to_workshop`,
  severity `{critical: 2, high: 2, medium: 2, low: 2}`, all `open`
- AIP: `seller_stockout` on first SKU, grounded **True**,
  `evaluate()` pass_rate **1.0**
- Governance: total **36**, `by_kind = {workshop: 8, ontology: 28}`,
  `verify().ok True`
- Foundry: status `ok`, 4 product rows, 8 order rows versioned,
  join `products LEFT JOIN orders` rows **8**
- Ontology: counts `{Product: 4, Order: 8, Shipment: 4}`, 16 refs
- Scenarios: total **8** (STOCKOUT_RISK 1, UNANSWERED_COMPLAINT 1,
  REFUND_RISK 1, REVIEW_CRISIS 1, DM_BACKLOG 1, SUPPLIER_COGS_SPIKE 1,
  PRICE_MISMATCH 2, rest 0)
- `do_today[0]` approves `UNANSWERED_COMPLAINT-4780385a`,
  `do_today[1]` assigns `REFUND_RISK-e4f05c57`
- Empty events: `0 decisions (0 open, 0 resolved) · grounded 0/0 ·
  audit verified True · head GENESIS`, AIP + foundry skipped with
  reasons, still 3 bundle files

## 7. Files in this pack

| File | Lines | Contents |
|------|-------|----------|
| `src/omni_one/packs/ops_close.py` | ~894 | `build_ops_close`, `decisions_to_csv`, `audit_to_jsonable`, `write_close_bundle` + stage helpers |
| `tests/unit/test_ops_close.py` | ~439 | 14 tests: golden, no-phantoms ×2, idempotent, empty ×2, bundle ×2, csv ×2, foundry, approval, headline grammar, namespaces |
| `docs/OPS_CLOSE.md` | this file | loop diagram, rules, flows, wiring, goldens |

Verify: `python3 -m compileall -q src/omni_one/packs/ops_close.py &&
PYTHONPATH=src python3 -m pytest tests/unit/test_ops_close.py -q`
— green required (14 passed).
