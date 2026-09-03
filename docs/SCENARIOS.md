# Seller Scenarios — 12 Sharp, Practical Use Cases

**Sharp = 60-second demo each: trigger → evidence `file:line` → Workshop action. All deterministic, idempotent, $0.**

Run: `POST /api/v1/seller/scenarios/run {"demo":true}` or `PYTHONPATH=src python -c "from omni_one.packs.seller_scenarios import run_all_scenarios; ..."`

| # | Scenario | Practical trigger (when it fires) | Evidence | Workshop action |
|---|---|---|---|---|
| 1 | STOCKOUT_RISK `high` | Velocity 7d vs on-hand <5 days. Demo: Tote 2 left, sold 6/7d = 2.3d | `[inventory.csv:2] Tote 2 left` | `reorderProduct` |
| 2 | DEAD_STOCK `medium` | On-hand ≥5 with zero sales 7d → clearance | `[inventory.csv]` | `markDownProduct` |
| 3 | UNANSWERED_COMPLAINT `critical` | Negative DM with no shop reply next | `[instagram_dm.txt:1] Alice…` | `messageCustomer` |
| 4 | REFUND_RISK `critical` | Refund/return/not-arrived language | `[dm:1] …` | `messageCustomer` 2h SLA |
| 5 | REVIEW_CRISIS `high` | 1-2 star or chipped/damaged | `[reviews.csv:3] …` | `replyReview` |
| 6 | DM_BACKLOG `medium` | ≥3 open DMs | `[dm:1]` oldest | `triageDMs` |
| 7 | FEE_CREEP `medium` | Fees/GMV ≥12% | `[orders] fees $…` | `reviewPricing` |
| 8 | SHIPPING_LOSS `medium` | Ship/GMV ≥20% on order | `[shopify:5] ship $…` | `adjustShipping` |
| 9 | PROFIT_DIP `high` | Net margin <10% | `[orders] net $…` | `reviewPricing` |
| 10 | SUPPLIER_COGS_SPIKE `medium` | Supplier $ / GMV >1.5× | `[supplier_invoice…]` | `renegotiateSupplier` |
| 11 | PRICE_MISMATCH `low` | Same SKU ±5% across Shopify/Etsy | `[orders] {shopify:28, etsy:30}` | `alignPrice` |
| 12 | LISTING_GAP `low` | Sales ≥2 with zero reviews → UGC ask | `[orders] sold N` | `requestReview` |

**Tech sound:** `packs/seller_scenarios.py:1` single-pass `_ctx()` O(n), stable `_sid()` IDs (same events → same decisions), severity-sorted, pure functions. `scenarios_to_workshop()` grounds to `Product:*` (no phantoms) with `stable_id` upsert.

**Methodology mapping (Palantir-style, not clone):**
- Foundry datasets → Ontology `Product/Order` twins → Pipeline evidence → **Scenarios** → Workshop queue → AIP draft → Governance audit. See `scripts/e2e_core_methodology.py:1`, `POST /api/v1/seller/operations`.

**Thresholds:** `SCENARIO_THRESHOLDS` in code (stockout 5d, fee 12%, ship 20%, margin 10%, backlog 3, price 5%). Tune per shop.

**Verify:** `PYTHONPATH=src python -m pytest tests/unit/test_seller_scenarios.py -q` (idempotency + grounding + <2s).
