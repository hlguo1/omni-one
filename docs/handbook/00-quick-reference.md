# Quick Reference — Omni-One Seller Close (one-page cheat sheet)

> Print this. Tape it to the wall by the packing table.
> One command runs the whole shop morning: profit, reorders, replies, leaks.
> Every number cites `file:line`. No citation, no action.
> Sources: `docs/QUICKSTART.md`, `docs/API.md`, `docs/CLI.md`,
> `docs/DEPLOYMENT.md`, `docs/ROADMAP.md`, `docs/DAILY_CLOSE.md`,
> `docs/handbook/01-morning-routine.md`, `docs/handbook/05-incidents.md`,
> `docs/SCENARIOS.md`, `src/omni_one/packs/seller_scenarios.py`.

```bash
omni-one close --folder ~/my_shop --out ./close_today
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

Headline example (the only line you must read):

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

---

## 1. The 5-minute ritual (checklist)

Copy this to a laminated card. Timer on. No dashboard spelunking.

- [ ] **0:00–0:30 — Run the close.**
  ```bash
  omni-one close --folder ~/my_shop --out ./close_today
  ```
  Read the headline out loud. If it errors, see §12 Troubleshooting.

- [ ] **0:30–2:00 — Replies first.**
  Open `replies.txt`. Copy-paste draft #1, personalise one sentence, send.
  Repeat while the kettle boils.
  Rule: **P0 (refund / hasn't-arrived / damaged) within 2 hours, no exceptions.**
  See `docs/handbook/03-reply-playbook.md`.

- [ ] **2:00–3:30 — Reorders.**
  Open `reorder.csv`. Anything `ORDER TODAY` → send `po.txt` draft today.
  Anything `this week` → diary it.
  See `docs/handbook/02-supplier-playbook.md`.

- [ ] **3:30–4:30 — One leak.**
  If `money_leaks` in `close.csv` is non-empty, do the cheapest fix:
  usually raise one price $1, or move one SKU off the expensive channel.
  Log it in one line.

- [ ] **4:30–5:00 — File it.**
  Move the day's exports into the shop folder.
  Append one line to your ledger (see `docs/handbook/04-accountant-pack.md`).

Daily laminate checklist (short version):

- [ ] Close run, headline read
- [ ] All P0 replies sent < 2h
- [ ] ORDER TODAY POs sent
- [ ] One leak touched
- [ ] Files archived

Weekly (Friday, 20 min):

- [ ] 7 closes reconciled, GMV vs channel dashboards ±2%
- [ ] Supplier ETAs chased (ordered > 7 days ago, no tracking)
- [ ] Dead stock listed (0 sales + 5+ units → clearance draft)
- [ ] Prices reviewed against fee changes
- [ ] Backup: copy `~/my_shop` to USB / second machine

Monthly (first Monday, 1 h):

- [ ] Month's `close.csv` files → accountant pack
- [ ] Supplier scorecard updated (price, ETA, defect rate)
- [ ] Worst seller decision: kill, bundle, or clearance
- [ ] Margin floor check: blended true margin ≥ 10%?

---

## 2. Install + first run (60 seconds, $0)

```bash
git clone https://github.com/garyguo123456789/omni-one.git && cd omni-one
pip install -r requirements-seller.txt && pip install -e .
omni-one doctor                                        # deps + pipeline smoke
omni-one close --demo --out ./close_today             # THE ritual: profit + reorders + replies
cat ./close_today/replies.txt                         # copy-paste a draft, send the PO
```

Your shop:

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv /tmp/my_shop/
cp examples/my_shop_template/*.csv /tmp/my_shop/   # fill blanks if needed
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
```

Server + SDK + bot:

```bash
omni-one serve --port 5003 &                            # docs at /api/docs
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

Claude/Cursor MCP:

```bash
python3 -m omni_one.mcp_server
```

MCP tools: `seller_close`, `seller_briefing`, `seller_scenarios`,
`seller_operations`, `pipeline_analyze`, `vision_analyze`.

---

## 3. All CLI commands

Run as `omni-one <cmd>` (after `pip install -e .`)
or `PYTHONPATH=src python3 -m omni_one.cli <cmd>`.
`make demo|close|test|e2e|serve|docker|lint|doctor` wraps the same.

| Command | What it does | Typical invocation |
|---|---|---|
| `omni-one doctor` | env + deps + pipeline smoke | `omni-one doctor` |
| `omni-one demo` | Seller demo briefing | `omni-one demo` |
| `omni-one briefing --demo --json b.json` | briefing; `--folder /p` for real shop | `omni-one briefing --folder ~/my_shop` |
| `omni-one scenarios --demo` | 12 scenarios ranked | `omni-one scenarios --demo` |
| `omni-one operations` | full ontology→workshop→AIP→audit loop | `omni-one operations --demo` |
| `omni-one close --demo --out ./close_today` | **Daily Close bundle** (json/csv/reorder/replies/po) | `omni-one close --folder ~/my_shop --out ./close_today` |
| `omni-one export --demo --out briefing.csv` | briefing CSV | `omni-one export --demo --out briefing.csv` |
| `omni-one serve --port 5003` | API server | `omni-one serve --port 5003` |
| `omni-one evaluate --n 500` | eval harness | `omni-one evaluate --n 500` |

CLI flags you will actually use:

| Flag | Meaning | Example |
|---|---|---|
| `--demo` | use built-in golden demo shop | `omni-one close --demo --out ./close_today` |
| `--folder /path` | your real shop folder | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11` |
| `--out ./dir` | where to write the bundle | `omni-one close --demo --out ./close_today` |
| `--shop "Name"` | shop display name in header | `omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"` |
| `--json b.json` | write briefing JSON to file | `omni-one briefing --demo --json b.json` |
| `--port 5003` | API port | `omni-one serve --port 5003` |
| `--n 500` | eval record count | `omni-one evaluate --n 500` |

Cron: 7am Daily Close:

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

Docker (single service):

```bash
docker build -t omni-one:latest .
docker compose up -d && curl -sf http://localhost:5003/health
```

Production hardening:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # twice
ENVIRONMENT=production VALID_API_KEYS=<32+> SECRET_KEY=<32+> docker compose up -d
```

---

## 4. All API routes (18)

Base: `http://localhost:5003`. Docs: `/api/docs`.
Health: `/health`, `/readiness`, `/status`, `/ping`.
Metrics: `/metrics` (Prometheus).

### 4a. Daily Close (hero) — 3 routes

| # | Method + path | Body / query | Returns |
|---|---|---|---|
| 1 | `POST /api/v1/seller/close` | `{"demo":true}` or `{"folder":"/path","shop":"Maya's"}` | close bundle (headline, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft). Counter `closes_total`. |
| 2 | `GET /api/v1/seller/close.csv?demo=true` | `?demo=true` or `?folder=/path` | accountant CSV download |
| 3 | `GET /api/v1/seller/export.csv?demo=true` | `?demo=true` | briefing CSV |

### 4b. Seller OS — 5 routes

| # | Method + path | Body / query | Returns |
|---|---|---|---|
| 4 | `POST /api/v1/seller/briefing` | `{"demo":true}` or `{"folder":"/path"}` | true profit / stockout / alerts / draft / chart |
| 5 | `POST /api/v1/seller/operations` | `{"demo":true}` | briefing→ontology→workshop→AIP→audit full loop |
| 6 | `GET /api/v1/seller/scenarios` | — | 12-scenario registry + thresholds |
| 7 | `POST /api/v1/seller/scenarios/run` | `{"demo":true}` | ranked idempotent decisions + workshop + audit |
| 8 | `POST /api/v1/seller/photo` (multipart) | image file field | supplier invoice / product photo → OCR+chart+pipeline |

### 4c. Engine — 7 routes

| # | Method + path | Body / query | Returns |
|---|---|---|---|
| 9 | `POST /api/v1/analyze` | `{"records":[...]}` | 4-layer pipeline + evidence + cost |
| 10 | `POST /api/v1/synthesize` | gated synthesis body | gated LLM synthesis with cache + citations |
| 11 | `POST /api/v1/vision/analyze` (multipart) | image file field | free OCR+chart |
| 12 | `GET /api/v1/vision/demo` | — | vision demo result |
| 13 | `GET /api/v1/metrics` | — | live 200-record eval metrics |
| 14 | `GET /api/v1/models` | — | model catalog |
| 15 | `POST /api/v1/micro/briefing` | micro-biz body | lab: micro briefing |

### 4d. Labs + admin — 3 routes

| # | Method + path | Body / query | Returns |
|---|---|---|---|
| 16 | `POST /api/v1/revenue/health` | revenue body | lab: revenue health |
| 17 | `GET /api/v1/admin/services` | header `X-API-Key` / `Bearer`, fail closed | service status (prod: key required) |
| 18 | `POST /api/v1/admin/clear-cache` | header `X-API-Key` / `Bearer`, fail closed | cache clear (prod: key required) |

Notes:

- All seller numbers cite `file:line`. Mock LLM by default (`SELLER_LLM=mock`, `$0`).
- Demo keys (`demo-key` / `test-key`) are rejected in production; `/admin/*` needs key.
- Uploads capped (5MB, type-checked, 60/min); folders jailed to `ALLOWED_ROOT`.
- Audit `verify()` proves tamper-evidence. See `SECURITY.md`.
- Monitoring: scrape `GET /metrics` (briefings / scenarios / closes / vision counters + `omni_one_up`).
- SDK:
  ```python
  from omni_one.client import OmniOneClient
  OmniOneClient.local().close(demo=True)["headline"]
  ```
- MCP: `{"tool":"seller_close","args":{"demo":true}}`.

---

## 5. Thresholds table (tune per shop, code: `src/omni_one/packs/seller_scenarios.py`)

| Key | Value | Fires when | Action |
|---|---|---|---|
| stockout | 5d | velocity 7d vs on-hand < 5 days | `reorderProduct` |
| cover | 14d | `reorder_qty = ceil(velocity×14 − on_hand)` | order 14 days of cover |
| fee creep | 12% | fees / GMV × 100 ≥ 12% | `reviewPricing` |
| shipping loss | 20% | ship / GMV × 100 ≥ 20% per order | `adjustShipping` |
| margin floor | 10% | net margin < 10% | `reviewPricing` |
| DM backlog | 3 | ≥ 3 open DMs | `triageDMs` |
| price mismatch | 5% | same SKU ±5% across channels | `alignPrice` |

Urgency overlay used by the close bundle:

| `days_left` | Label | Do |
|---|---|---|
| < 3d | `ORDER TODAY` | send PO today |
| 3–5d | `this week` | diary + confirm ETA |
| > 5d | healthy | recheck tomorrow |

Formulas (deterministic, no LLM for numbers):

| Metric | Formula | Golden demo |
|---|---|---|
| true profit | GMV − fees − shipping − COGS | GMV $274.00 → profit $169.09 (61.7%) |
| AOV | GMV / orders | ≈ $34.25 in demo |
| money at risk | unanswered complaints × AOV | 3 × $34.25 ≈ $102.75 |
| daily velocity | sold_7d / 7 | Tote: 6 / 7 ≈ 0.857/d |
| days left | on_hand / velocity | Tote: 2 / 0.857 ≈ 2.3d → ORDER TODAY |
| reorder qty | ceil(velocity × 14 − on_hand) | Tote: ceil(12 − 2) = x10 |
| fee % | fees / GMV × 100 | ≥ 12% → leak |
| ship % | ship / GMV × 100 per order | ≥ 20% → leak |
| net margin | (GMV − fees − ship) / GMV × 100 (quick) | < 10% → PROFIT_DIP |

Dead stock: on-hand ≥ 5 with zero sales 7d → `markDownProduct` (bundle/clearance).
COGS spike: supplier $ / GMV > 1.5× → `renegotiateSupplier`.
Listing gap: sales ≥ 2 with zero reviews → `requestReview` (UGC ask).

---

## 6. The 12 scenarios (60-second demos)

Run: `POST /api/v1/seller/scenarios/run {"demo":true}`.
Verify: `PYTHONPATH=src python -m pytest tests/unit/test_seller_scenarios.py -q`.

| # | Scenario | Severity | Trigger | Evidence | Workshop action |
|---|---|---|---|---|---|
| 1 | STOCKOUT_RISK | `high` | on-hand < 5d supply. Demo: Tote 2 left, sold 6/7d = 2.3d | `[inventory.csv:2] Tote 2 left` | `reorderProduct` |
| 2 | DEAD_STOCK | `medium` | on-hand ≥ 5, zero sales 7d → clearance | `[inventory.csv]` | `markDownProduct` |
| 3 | UNANSWERED_COMPLAINT | `critical` | negative DM, no shop reply next | `[instagram_dm.txt:1] Alice…` | `messageCustomer` |
| 4 | REFUND_RISK | `critical` | refund/return/not-arrived language | `[dm:1] …` | `messageCustomer` 2h SLA |
| 5 | REVIEW_CRISIS | `high` | 1–2 star or chipped/damaged | `[reviews.csv:3] …` | `replyReview` |
| 6 | DM_BACKLOG | `medium` | ≥ 3 open DMs | `[dm:1]` oldest | `triageDMs` |
| 7 | FEE_CREEP | `medium` | fees/GMV ≥ 12% | `[orders] fees $…` | `reviewPricing` |
| 8 | SHIPPING_LOSS | `medium` | ship/GMV ≥ 20% on order | `[shopify:5] ship $…` | `adjustShipping` |
| 9 | PROFIT_DIP | `high` | net margin < 10% | `[orders] net $…` | `reviewPricing` |
| 10 | SUPPLIER_COGS_SPIKE | `medium` | supplier $ / GMV > 1.5× | `[supplier_invoice…]` | `renegotiateSupplier` |
| 11 | PRICE_MISMATCH | `low` | same SKU ±5% across Shopify/Etsy | `[orders] {shopify:28, etsy:30}` | `alignPrice` |
| 12 | LISTING_GAP | `low` | sales ≥ 2, zero reviews → UGC ask | `[orders] sold N` | `requestReview` |

Severity sort: `critical` → `high` → `medium` → `low`.
IDs stable (`_sid` hash of type+key) → idempotent: same events → same decisions.
`scenarios_to_workshop()` grounds to `Product:*` (no phantoms) with `stable_id` upsert.
Tech: `packs/seller_scenarios.py:1` single-pass `_ctx()` O(n), pure functions.

---

## 7. Citation format (the one rule)

> **No citation, no action.** The close refuses to invent tasks.
> If it tells you to reorder, it shows `[inventory.csv:2]`.
> If it tells you to reply, it shows `[instagram_dm.txt:4]`.

| Pattern | Example | Meaning |
|---|---|---|
| `[inventory.csv:2]` | `Reorder Tote — 2.3d left [inventory.csv:2]` | row 2 of inventory file |
| `[instagram_dm.txt:4]` | `Unanswered complaint [instagram_dm.txt:4]` | line 4 of DM export |
| `[reviews.csv:3]` | `Bad review [reviews.csv:3]` | row 3 of reviews |
| `[shopify_orders.csv:5]` | `Shipping loss [shopify_orders.csv:5]` | row 5 of orders |
| `[supplier_invoice.jpg:1]` | `COGS $… [supplier_invoice.jpg:1]` | OCR line 1 + sidecar `.jpg.txt` |

Rules:

- Every headline number has a citation chain in `close.json`.
- If a number has no citation, don't trust it — fix the source file, not the spreadsheet.
- Matching is fuzzy (`Tote` ≈ `Tote Bag Handmade`) but exact names are bulletproof — rename to match.
- Dedup is by content hash: identical invoice content (`.jpg` + `.jpg.txt` + `.txt`) counts once. Check `files_ingested` vs `files_seen` in the briefing.
- `file:line` strings are never translated/localised — keep verbatim in ES/ZH docs.

---

## 8. File inputs (drop your mess, as-is)

Parsers auto-detect, no renaming. Name order files `shopify_*`, `etsy_*`, `amazon_*` for best channel detection.

| File | What | Notes |
|---|---|---|
| `shopify_orders.csv` / `etsy_settlement.csv` / `amazon_*.csv` | orders (any headers) | Sniffer handles `;` delimiter + BOM (`UTF-8-SIG`) |
| `inventory.csv` | on-hand + `supplier` column kept | product names must match orders |
| `reviews.csv` | reviews with stars | 1–2★ or damage words trigger crisis |
| `instagram_dm.txt` / `tiktok_dm.json` | DMs as text/JSON | screenshots don't parse — paste text |
| `supplier_invoice.jpg/png/pdf/txt` | COGS via OCR or CSV | Tesseract OCR + sidecar `.jpg.txt` dedup via content hash |
| `examples/my_shop_template/*.csv` | blanks starter | copy to shop folder, fill blanks |

Day-1 folder recipe:

```bash
mkdir -p ~/my_shop
# drop: order exports + inventory.csv + reviews export + DM export + supplier invoices
omni-one briefing --folder ~/my_shop   # confirm GMV within 5% of channel dashboard
omni-one close --folder ~/my_shop --out ./close_day1
```

---

## 9. File outputs (artifacts you already use)

| File | For whom | Contains |
|---|---|---|
| `close.json` | API / MCP / automation | everything: headline, kpis+money_at_risk, do_today, reorder_sheet, reply_queue+drafts, leaks, listing_fixes, po_draft |
| `close.csv` | accountant / sheets | KPIs + actions + leaks (Section A: fees/shipping/cogs; `money_leaks`) |
| `reorder.csv` | supplier | product, on_hand, days_left, qty_14d, supplier, citation |
| `replies.txt` | you (copy-paste) | drafts + PO email in one printable file |
| `po.txt` | supplier | send as-is: `Subject: Reorder — Acme Textiles: Tote x10 (2 left, 2.3d supply) [inventory.csv:2]` |
| `briefing.csv` | sheets | briefing export via `omni-one export` / `GET /api/v1/seller/export.csv` |

Morning mapping (from `docs/DAILY_CLOSE.md`):

| Min | You do | Close gives you |
|---|---|---|
| 0–1 | Read the headline | `Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder TODAY · 0 leaks` |
| 1–3 | Copy-paste replies | `replies.txt`: 3 drafts with name, issue, order citation |
| 3–4 | Send the PO | `po.txt`: reorder with citation |
| 4–5 | File + fix | `close.csv` → accountant; fix 1 listing from `listing_fixes` |

Habit loop:

- Day 1: folder drop → close bundle → 1 refund saved ≈ pays for the year (it's $0).
- Day 7: supplier catalog + velocity learned → reorder qty smarter, PO one-click.
- Day 30: `money_at_risk → $0` streak + margin trend → close becomes the shop's P&L.

---

## 10. Incident severity table + runbooks (first hour wins)

### Severity scale (all runbooks)

| Sev | Meaning | Response time | Who |
|---|---|---|---|
| S1 critical | Losing money *right now* (chargeback, stockout of #1 seller, account warning) | < 1h | you, drop everything |
| S2 high | Will cost money within days (2d of stock, 1-star gaining views, fee jump) | < 4h | you, today |
| S3 medium | Margin erosion / slow bleed | this week | scheduled block |
| S4 low | Watch item, no action | note + recheck | next close |

Triage order when everything fires: stockout (revenue stops) → 1-star (reputation) → fees (margin). Say it out loud.

### Runbook A — STOCKOUT

Detect: `reorder.csv` shows #1 seller `ORDER TODAY` (`days_left` < 3),
or briefing alert `Stockout risk: X only N left, D days supply` + `[inventory.csv:N]`.

| Signal | Sev |
|---|---|
| `days_left` < 1 on top-3 seller | S1 |
| `days_left` 1–3 on any seller | S2 |
| `days_left` 3–5 | S3 |
| No inventory file / product unmatched | S2 (blind = dangerous) |

Act (S1/S2, 30-min box): confirm `on_hand` on shelf → send `po.txt` (ask tracking + split shipment)
→ protect listing (raise price 10–15% / cap qty / pause ads beats oversell)
→ message waiting buyers (template 19) → trial order to backup supplier if ETA > `days_left`.

### Runbook B — 1-STAR REVIEW

Detect: `at_risk` jumps, `reply_queue` gains a `review` row, or `REVIEW_CRISIS` + `[reviews.csv:N]`.

| Signal | Sev |
|---|---|
| 1★ on best seller + safety/allergy/chargeback | S1 |
| 1–2★ damage/late specifics, < 24h old | S2 |
| 1–2★ vague, older | S3 |
| 3★ constructive | S4 |

Act (S1/S2, 45-min box): read `[reviews.csv:line]` → public reply once (template 08, never argue/refund publicly)
→ private DM with choice (template 05/06, S1 leads with refund)
→ fix cause for next buyer today → log: date, SKU, claim, cost, fix.

### Runbook C — FEE SPIKE / MARGIN COLLAPSE

Detect: `money_leaks` shows `fee_creep` (fees ≥ 12% GMV), or margin drops > 5 pts WoW, or channel announces fee change.

| Signal | Sev |
|---|---|
| Blended margin < 0% | S1 — stop paid traffic + pause worst SKU today |
| Blended margin 0–10% for 2+ weeks | S2 |
| Single-channel fee rise announced | S3 |
| Shipping drift (+$1/order trend) | S3 |

Act (S1/S2, 60-min box): verify in `close.csv` Section A (fees vs shipping vs cogs — different owners)
→ fees: reprice (`fee_delta / (1 − fee_rate)`; 2 pts on $28 ≈ +$1) or re-channel next 10 orders
→ shipping: re-weigh packed parcel, right-size box
→ COGS: +5% unannounced = email in 48h; COGS > 45% retail on top-3 = reprice + renegotiate
→ kill/fix worst seller: clearance / bundle / delist.

Cross-incident rules: one incident at a time · write citations as you go
· time-box everything (good in 2h beats perfect tomorrow)
· post-mortem 5 lines max · know when it's not an incident (S4, ±2 pts wobble, slow Tuesday).

---

## 11. Fee table + margin math

| Channel | Fee | On $28 example | Note |
|---|---|---|---|
| Etsy | ≈ 6.5% + $0.20 | ≈ $2.02 | per-order fixed bites small baskets |
| Shopify | ≈ 2.9% + $0.30 | ≈ $1.11 | cheapest for own-store volume |
| Amazon | ≈ 15% | ≈ $4.20 | route only high-margin SKUs here |
| Blended alarm | ≥ 12% of GMV | — | `FEE_CREEP` fires, review pricing/channel mix |

Rules of thumb:

- Price increase needed ≈ `fee_delta / (1 − fee_rate)`.
- If blended fees > 12% of GMV, pick one SKU to reprice or re-channel.
- Margin floor: blended true margin ≥ 10%. Below 2 weeks = S2 incident.
- COGS > 45% of retail on top-3 SKU = reprice + renegotiate in parallel.
- Shipping loss per order ≥ 20% = `adjustShipping` (re-weigh, right-size, bake into price).
- State your fee % from memory to within 1 point (Day-4 drill).

---

## 12. Troubleshooting (symptom → cause → fix)

| Symptom | Likely cause | Fix |
|---|---|---|
| Profit too high | supplier invoice missing → COGS under-counted | drop invoice `.txt`/photo in folder |
| Profit too low | duplicate invoice (`.jpg` + `.jpg.txt` + `.txt`) | dedup is automatic; check `files_ingested` vs `files_seen` |
| `reorder.csv` empty but shelves bare | names differ (`Tote` vs `Tote Bag Handmade`) | rename to match; exact is bulletproof |
| Reply queue empty but complaints live | DMs as screenshots, not text | export `.txt`/`.json` or paste into `instagram_dm.txt` |
| Fees look wrong | channel misdetected from filename | name files `shopify_*`, `etsy_*`, `amazon_*` |
| Semicolon CSV ignored | locale export (`;` delimiter) | supported — Sniffer handles it; check UTF-8 |
| Weird chars (`ï»¿`) | BOM headers from Excel | supported (`UTF-8-SIG`) |
| 0 rows from a file | wrong encoding / no headers | open as UTF-8, confirm header row |

---

## 13. Golden numbers (know these cold)

| Number | Value | Where |
|---|---|---|
| demo profit | $169.09 (61.7%) on $274.00 GMV | `close --demo` headline |
| money at risk | $102.75 in 3 messages (older doc: $82 variant) | `close --demo` headline |
| Tote reorder | 2 left, 6 sold/7d → 2.3d → ORDER TODAY x10 | `reorder.csv` demo |
| fee alarm | 12% | `money_leaks` |
| ship alarm | 20% | per-order |
| margin floor | 10% | blended |
| P0 SLA | 2h | replies |
| server | `http://localhost:5003`, docs `/api/docs` | `serve` |
| cost | $0, offline, mock LLM default | `SELLER_LLM=mock` |
| tests | 35 green (v1.1) | `make test` |

Roadmap memory hook — Now / Next / Then / Later:

- **Now (v1.1):** Daily Close ritual. `close` → profit + reorder/PO + drafts + leaks.
- **Next (v1.2):** habit — 7am cron + email, `money_at_risk → $0` streak, margin trend, multi-shop compare, ES/ZH DM drafts, TikTok parser.
- **Then (v1.3):** smarter — DuckDB cost catalog, shelf-photo count, review webhook, one-click price-align.
- **Later:** hosted close-by-email, accountant portal CSV, supplier network, mobile one-pager.
- Principles: $0 default, offline-first, cited numbers, no phantom tasks, mock-by-default LLM, laptop-first data.

Pointers: `src/omni_one/packs/seller_close.py` · `tests/unit/test_daily_close.py` (4 golden tests)
· `examples/daily_close_demo.py` · `docs/SCENARIOS.md` · `.github/ISSUE_TEMPLATE/seller_scenario.yml`.

| `locale` (close) | `en` | drafts only: reply + PO language; KPIs/citations identical |
