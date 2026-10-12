# Forecast Close — the Sunday stock-up ritual your shop runs

Shops don't live in dashboards. They **close the week**: what stocks out
first, how much cash covers 14 days, who gets a PO today — every unit cited,
every email drafted. Omni-One's Forecast Close is that ritual in one call —
offline, free ($0), private, deterministic by seed.

```python
from omni_one.packs.forecast_close import build_forecast_close, write_close_bundle
close = build_forecast_close(seed=42)
write_close_bundle(close, "./forecast_close_2026-10-11")
# -> close.json + close.csv + forecast.csv + po.txt
```

> Scope note: this pack ships the engine + sheets + docs only.
> CLI (`omni-one forecast-close`) and API (`POST /api/v1/forecast/close`) are
> **wiring notes** at the bottom — not implemented here on purpose (must not
> touch `cli.py`, `client.py`, `api/`, `mcp_server.py`).

## The Sunday routine (10 min)

| Min  | You do               | Close gives you |
|------|----------------------|-----------------|
| 0–1  | Read the headline    | `FORECAST CLOSE: 3/8 SKUs critical · $2,220.95 to cover 14d · first stockout Croissant Butter Frozen in 1d` |
| 1–5  | Order the criticals  | `do_today[3]`: worst-first order + top-supplier PO + low-stock cover, each with $ and days |
| 5–8  | Email suppliers      | `po.txt`: per-supplier drafts in `seller_close.draft_po_email` style, cited `[inventory:skus#N]` |
| 8–10 | File + cover         | `forecast.csv` → sheets/accountant; `close.json` is the audit trail |

The rule: **no critical SKU enters Monday without a reorder qty and a PO
draft.** The close makes that checkable in one page.

## What it computes (deterministic, no LLM, no network)

- **Demo book `DEMO_SKUS(seed=42)`** — 8 SKUs: name, on_hand,
  daily_velocity, unit_cost, supplier, lead_days, citation
  `[inventory:skus#N]`. Seed 42 returns the canonical book exactly; other
  seeds jitter `on_hand` ±5 (clamped ≥ 0) via `random.Random(seed)` so the
  generator is genuinely seeded while goldens never drift.
- **Per-SKU forecast** — sorted worst-first (days_left asc):
  `Espresso Beans 1kg`, `Oat Milk 12-pack`, `Ceramic Mug 350ml`,
  `Cold Brew Bottles`, `Paper Filters #4`, `Vanilla Syrup 750ml`,
  `Croissant Butter Frozen`, `Reusable Tote` across 5 suppliers
  (`Andes Coffee Co.`, `Kiln Works`, `BottlePro`, `Syrup House`, `FreshBake`).
- **KPIs** — `sku_count=8`, `critical_count=3`,
  `reorder_lines=5 (qty > 0)`, `reorder_cost=$2,220.95 (sum qty*unit_cost)`,
  `stockout_soon=[Croissant Butter Frozen, Cold Brew Bottles, Espresso Beans 1kg]`.
- **PO drafts** — one per supplier (all 5), grouped reorder lines rendered
  through `omni_one.packs.seller_close.draft_po_email` (same
  `Subject: Reorder request — <supplier>` shape). Critical suppliers
  (`FreshBake`, `BottlePro`, `Andes Coffee Co.`) always present with qty +
  citation.
- **do_today[3]** — `[0]` order the first stockout (Croissant x97, $184.30,
  1.1d left), `[1]` send PO to the top-cost supplier (Andes Coffee Co.,
  2 lines, $1,555.50, 14d cover), `[2]` cover all reorder lines (5 lines,
  $2,220.95, next low from 6.0d). Every string carries `$` and `d`.
- **Headline** — `FORECAST CLOSE: {critical}/{total} SKUs critical ·
  ${reorder_cost} to cover {cover_days}d · first stockout {name} in {floor(days_left)}d`.

## Golden numbers (seed=42, cover_days=14 — do not change without updating tests)

```
headline: FORECAST CLOSE: 3/8 SKUs critical · $2,220.95 to cover 14d ·
          first stockout Croissant Butter Frozen in 1d
kpis: sku_count=8 critical_count=3 reorder_lines=5 reorder_cost=2220.95
      stockout_soon=[Croissant Butter Frozen, Cold Brew Bottles, Espresso Beans 1kg]
skus (worst-first):
  Croissant Butter Frozen  8/7.0d  ->  1.14d critical x97  ($184.30)  FreshBake [skus#6]  out 2026-10-12*
  Cold Brew Bottles       12/5.0d  ->  2.40d critical x68  ($258.40)  BottlePro [skus#3]
  Espresso Beans 1kg      18/6.0d  ->  3.00d critical x87 ($1087.50)  Andes     [skus#0]
  Vanilla Syrup 750ml     15/2.5d  ->  6.00d low      x33  ($222.75)  Syrup H.  [skus#5]
  Oat Milk 12-pack        40/4.0d  -> 10.00d low      x26  ($468.00)  Andes     [skus#1]
  Paper Filters #4       200/8.0d  -> 25.00d ok       x0               BottlePro [skus#4]
  Ceramic Mug 350ml      120/3.0d  -> 40.00d ok       x0               Kiln Works[skus#2]
  Reusable Tote           60/1.5d  -> 40.00d ok       x0               Kiln Works[skus#7]
  (*stockout_date shifts with `date_str`; math modulo date is identical)
po_drafts (5): Andes Coffee Co. / BottlePro / FreshBake / Kiln Works / Syrup House
do_today[3]: order-first + top-supplier-PO + cover-all (each with $ and d)
```

Verify locally:

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_forecast_close.py -q
```

## Inputs: your inventory, as-is

Explicit dicts or generated on demand:

```python
build_forecast_close(skus=None, seed=42, cover_days=14)
build_forecast_close(skus=[{"name": "Beans", "on_hand": 10, "daily_velocity": 2.0,
  "unit_cost": 5.0, "supplier": "Acme", "lead_days": 4, "citation": "[inventory:skus#0]"}])
build_forecast_close(seed=7)              # seeded variant (on_hand jitter)
build_forecast_close(cover_days=7)        # 7-day cover lowers reorder_cost
build_forecast_close(skus=[])             # empty book: honest "0/0 ... no stockouts" headline
```

SKU keys: `name, on_hand, daily_velocity, unit_cost, supplier, lead_days,
citation?`. Missing citation defaults to `[inventory:skus#i]`. Zero velocity
→ `days_left=999.0`, `status=ok`, no reorder (never divides by zero).

## Outputs: artifacts the shop already uses

- `close.json` — everything (date, headline, kpis, skus worst-first,
  po_drafts, do_today, citations, free/offline, seed/cover_days).
- `close.csv` — per-SKU rows: `sku,on_hand,daily_velocity,days_left,
  safety_stock,reorder_qty,unit_cost,reorder_cost,supplier,lead_days,
  stockout_date,status,citation` (8 rows + header golden).
- `forecast.csv` — same per-SKU forecast sheet (byte-identical to `close.csv`;
  kept as a separate file so sheets/accountant imports stay stable).
- `po.txt` — printable POs: headline + line/cost summary + per-supplier
  `draft_po_email` blocks + citations footer.

```python
from omni_one.packs.forecast_close import close_to_csv, forecast_to_csv, po_to_txt
close_to_csv(close)     # str with exact header above
forecast_to_csv(close)  # alias, same bytes
po_to_txt(close)        # str with "--- PO: <supplier> ---" blocks
```

## Intended wiring (NOT shipped here — notes for the next pack)

When the team is ready to expose the close, the intended surface mirrors the
seller close exactly (do not implement until this pack is merged):

```bash
# Intended CLI (requires touching cli.py — out of scope here):
omni-one forecast-close --seed 42 --cover-days 14 --out ./forecast_close_2026-10-11
omni-one forecast-close --seed 7 --cover-days 7 --out ./forecast_close_7d
```

```python
# Intended API (requires touching api/ — out of scope here):
# POST /api/v1/forecast/close {"seed": 42, "cover_days": 14} -> close.json
# GET  /api/v1/forecast/close.csv?seed=42&cover_days=14  -> forecast.csv download
# Intended MCP: {"tool": "forecast_close", "args": {"seed": 42, "cover_days": 14}}
# Intended SDK: OmniOneClient.local().forecast_close(seed=42)["headline"]
```

Wiring checklist for that pack: add `forecast-close` command in `cli.py`
(thin wrapper over `build_forecast_close` + `write_close_bundle`), add
`POST /api/v1/forecast/close` (+ CSV download) in `api/`, register the MCP
tool in `mcp_server.py`, add a `forecast_close()` SDK method in `client.py`,
and contract-test CLI/SDK/API parity the way `test_daily_close.py` does for
the seller close. Keep the engine import-free (except `draft_po_email`) so
none of that changes golden numbers.

## Design rules incl. formula docs

- **Deterministic, $0 offline**: same `(skus, seed, cover_days)` → same
  close modulo `date`/`stockout_date`. No LLM, no network, no wall-clock in
  math. `COVER_DAYS=14`, `STOCKOUT_DAYS=5.0` mirror `seller_close.py`.
- **Formulas (per SKU)**:
  ```
  days_left    = on_hand / daily_velocity            (999.0 if velocity <= 0)
  safety_stock = ceil(daily_velocity * lead_days * 0.5)
  reorder_qty  = max(0, ceil(daily_velocity * cover_days + safety_stock - on_hand))
  reorder_cost = reorder_qty * unit_cost              (kpis reorder_cost = sum, rounded 2dp)
  stockout_date = date + floor(days_left) days        (ISO string; +999d when days_left >= 900)
  status        = critical if days_left <= 5.0 else low if days_left <= cover_days else ok
  ```
- **Every unit cited**: each SKU carries `[inventory:skus#N]`; PO lines echo
  `have X, Yd left [citation]`; bundle footer repeats the audit note.
- **Idempotent + private**: same folder → same bytes on rewrite; data never
  leaves the laptop.
- **PO style reuse**: `from omni_one.packs.seller_close import draft_po_email`
  — one template for all POs, not a second dialect.

See: `src/omni_one/packs/forecast_close.py`,
`tests/unit/test_forecast_close.py` (10 tests),
`src/omni_one/packs/seller_close.py` (COVER_DAYS/STOCKOUT_DAYS/draft_po_email),
`src/omni_one/packs/revops_close.py` (flagship structure: headline/do_today/sheets/bundle).
