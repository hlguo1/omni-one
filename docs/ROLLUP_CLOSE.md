# Multi-Shop Rollup Close — the portfolio-owner Sunday ritual

One owner, four shops, one page. Every Sunday night the portfolio owner
**closes the portfolio**: did it actually make money, which shop carries the
week and which one drags it, and what three moves fix the most dollars before
Monday — every dollar cited, every move named. Omni-One's Rollup Close is
that ritual in one call — offline, free ($0), private, deterministic by seed.

```python
from omni_one.packs.rollup_close import build_rollup_close, write_close_bundle
close = build_rollup_close(seed=42)
write_close_bundle(close, "./rollup_close_2026-10-12")
# -> close.json + close.csv + shops.csv + actions.txt
```

> Scope note: this pack ships the engine + sheets + docs only.
> CLI (`omni-one rollup-close`) and API (`POST /api/v1/rollup/close`) are
> **wiring notes** at the bottom — not implemented here on purpose (this pack
> must not touch `cli.py`, `client.py`, `api/`, `mcp_server.py`).

## The Sunday routine (10 min)

| Min  | You do               | Close gives you |
|------|----------------------|-----------------|
| 0–1  | Read the headline    | `ROLLUP CLOSE: 4 shops · $101,127 GMV · $40,606 profit (40.2%) · ★ Harbor Goods / ⚠ Velvet Vinyl` |
| 1–5  | Read the ranked sheet| `shops.csv`: 4 shops by profit desc, each with profit, margin, citation |
| 5–8  | Work the 3 plays     | `actions.txt`: fee audit + reply sprint + PO sprint, each on a real shop |
| 8–10 | File it              | `close.json` → sheets; `close.csv` → accountant |

The rule: **no Sunday ends without knowing the best shop, the worst shop,
and Monday's first three moves.** The close makes that checkable in one page.

## What it computes (deterministic, no LLM, no network)

- **Per-shop profit** — exact integers: `profit = gmv - fees - ship_cost -
  cogs`; `margin_pct = profit / gmv * 100` (2 decimals stored, headline
  shows blended to 1 decimal). Contract-tested on every row.
- **Ranking** — shops sorted by profit desc (name asc tie-break), ranks 1–4.
  Golden: Harbor Goods $12,837 > Pixel Pantry $11,830 > Northwind Home $8,446
  > Velvet Vinyl $7,493. Note rank is by profit, not margin — Pixel Pantry
  has the fattest margin (45.73%) but Harbor Goods carries the week.
- **Totals** — `gmv/profit/orders/stockouts/angry = sum(shop values)`;
  `blended_margin_pct = round(total_profit / total_gmv * 100, 1)`.
  Golden: $101,127 GMV · $40,606 profit (40.2%) · 1,508 orders.
- **Cross-shop plays (3, fixed order)** — FEE-AUDIT → thinnest-margin shop
  (Northwind Home 34.39%); REPLY-SPRINT → most angry messages (Northwind
  Home, 8 open); PO-SPRINT → most stockouts (Velvet Vinyl, 6). Tie-breaks:
  lower profit first, then name asc. A shop may own two plays.
- **do_today[3]** — one line per play, each naming a real shop, carrying a
  `$` amount and the shop's `[<channel>:shop:<name>]` citation.
- **Citations** — every dollar cites a shop: `[shopify:shop:Harbor Goods]`,
  `[amazon:shop:Pixel Pantry]`, `[etsy:shop:Northwind Home]`,
  `[tiktok:shop:Velvet Vinyl]`. Audit via the `citation` column.

## Golden numbers (seed=42 — do not change without updating tests)

```
headline: ROLLUP CLOSE: 4 shops · $101,127 GMV · $40,606 profit (40.2%) ·
          ★ Harbor Goods / ⚠ Velvet Vinyl
kpis: shops=4 gmv=101127 profit=40606 blended_margin_pct=40.2
      best_shop=Harbor Goods worst_shop=Velvet Vinyl
      orders=1508 stockouts=17 angry=14
shops (profit desc):
  #1 Harbor Goods   shopify  28952 / 2638 / 1926 / 11551 -> 12837 (44.34%)
  #2 Pixel Pantry   amazon   25870 / 2294 / 2528 / 9218  -> 11830 (45.73%)
  #3 Northwind Home etsy     24559 / 3443 / 3098 / 9572  -> 8446  (34.39%)
  #4 Velvet Vinyl   tiktok   21746 / 2219 / 3213 / 8821  -> 7493  (34.46%)
plays: FEE-AUDIT @ Northwind Home · REPLY-SPRINT @ Northwind Home (8 angry) ·
       PO-SPRINT @ Velvet Vinyl (6 stockouts)
```

Verify locally:

```bash
python3 -m compileall -q src/omni_one/packs/rollup_close.py
PYTHONPATH=src python3 -m pytest tests/unit/test_rollup_close.py -q
```

## Inputs: your shops, as-is

Explicit dicts or generated on demand:

```python
build_rollup_close(shops=[...])  # your export: name/channel/gmv/fees/ship_cost/cogs/orders/stockout_count/angry_count
build_rollup_close(seed=7)       # reseed the demo book (identities fixed, numbers reseed)
build_rollup_close(shops=[])     # empty book: honest "no shops yet" headline, no crash
```

Shop keys: `name, channel, gmv, fees, ship_cost, cogs, orders,
stockout_count, angry_count`. When `shops=None`, the deterministic
`DEMO_SHOPS(seed)` generator fills the book. `date_str` labels the close;
all math ignores the wall clock.

## Outputs: artifacts the owner already uses

- `close.json` — everything (headline, kpis, ranked shops, plays, do_today,
  citations, seed/date, free/offline).
- `close.csv` — per-shop rows via `close_to_csv(close)`: `rank,shop,
  channel,gmv,fees,ship_cost,cogs,profit,margin_pct,orders,stockout_count,
  angry_count,citation` (4 rows + header golden).
- `shops.csv` — ranked per-shop sheet, same rows as `close.csv` (mirrored so
  spreadsheet imports and accountant scripts both land on shop names).
- `actions.txt` — printable Sunday sheet: headline + DO TODAY[3] +
  cross-shop plays + ranked shops + citations footer.

```python
from omni_one.packs.rollup_close import close_to_csv, actions_to_txt
close_to_csv(close)   # str with exact header above
actions_to_txt(close) # str with DO TODAY + plays + ranked shops
```

## Intended wiring (NOT shipped here — notes for the next pack)

When the team is ready to expose the close, the intended surface mirrors the
seller close exactly (do not implement until this pack is merged):

```bash
# Intended CLI (requires touching cli.py — out of scope here):
omni-one rollup-close --seed 42 --out ./rollup_close_2026-10-12
omni-one rollup-close --seed 7 --out ./rollup_close_big
```

```python
# Intended API (requires touching api/ — out of scope here):
# POST /api/v1/rollup/close {"seed": 42} -> close.json
# GET  /api/v1/rollup/close.csv?seed=42  -> shops.csv download
# Intended MCP: {"tool": "rollup_close", "args": {"seed": 42}}
# Intended SDK: OmniOneClient.local().rollup_close(seed=42)["headline"]
```

Wiring checklist for that pack: add `rollup-close` command in `cli.py`
(thin wrapper over `build_rollup_close` + `write_close_bundle`), add
`POST /api/v1/rollup/close` (+ CSV download) in `api/`, register the MCP
tool in `mcp_server.py`, add a `rollup_close()` SDK method in `client.py`,
and contract-test CLI/SDK/API parity the way `test_daily_close.py` does for
the seller close. Keep the engine import-free so none of that changes golden
numbers.

## Design rules (why owners trust it — same contract as the flagships)

- Deterministic: same (shops, seed) → same close (minus date stamp). No
  LLM/network/wall-clock in math. `$0` offline.
- Every dollar cites a shop (`[<channel>:shop:<name>]`). No phantom tasks,
  no invented shops.
- Idempotent: same inputs → byte-identical bundle on rewrite.
- Private: data never leaves the laptop. Works on plane wifi.

See: `src/omni_one/packs/rollup_close.py`,
`tests/unit/test_rollup_close.py` (12 tests),
`src/omni_one/packs/revops_close.py` + `src/omni_one/packs/micro_close.py`
(structural models: headline/do_today/sheets/bundle).
```
