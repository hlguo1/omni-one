# Returns & Refunds Close — the weekly money-leak ritual your support team runs

Refunds don't live in dashboards. They **close the week**: how much bled,
which reason leaks the most dollars, what restocks today, what to copy-paste
to customers — every dollar cited, every reply scripted. Omni-One's Returns
Close is that ritual in one call — offline, free ($0), private, deterministic
by seed.

```python
from omni_one.packs.returns_close import build_returns_close, write_close_bundle
close = build_returns_close(seed=42)
write_close_bundle(close, "./returns_close_2026-10-11")
# -> close.json + close.csv + returns.csv + drafts.txt
```

> Scope note: this pack ships the engine + sheets + docs only.
> CLI (`omni-one returns-close`) and API (`POST /api/v1/returns/close`) are
> **wiring notes** at the bottom — not implemented here on purpose (must not
> touch `cli.py`, `client.py`, `api/`, `mcp_server.py`).

## The weekly routine (10 min)

| Min  | You do               | Close gives you |
|------|----------------------|-----------------|
| 0–1  | Read the headline    | `RETURNS CLOSE: $868.73 refunded in 12 return(s) · top leak wrong_item $359.02 · $513.95 restockable today` |
| 1–5  | Work the restock sheet | `returns.csv`: 6 resellable item(s) = $513.95, each with inspect + relist action + `[shopify:orders#N]` citation |
| 5–8  | Send the replies     | `drafts.txt`: 3 copy-paste drafts (apology + RESHIP/REFUND choice), each citing its order |
| 8–10 | Stop next week's leak | `do_today[3]` + `prevented_today[2]`: photo-QC guardrail for `wrong_item` + relist run |

The rule: **no refund leaves the week without a cited reason, a restock
decision, and a reply on record.** The close makes that checkable in one page.

## What it computes (deterministic, no LLM, no network)

- **Refund total / count / rate** — `refund_total = sum(amounts)`,
  `refund_count = len(records)`, `refund_rate = count / 60 * 100`
  (ASSUMED_SALES = 60 orders/week). Golden demo: **$868.73 in 12 return(s),
  20.0%, avg $72.39**.
- **Reason breakdown** — group by reason → `{count, amount_usd}`, sorted
  amount desc; `top_reason = max(amount)` (alphabetical tie-break).
  Golden: wrong_item 3/$359.02 · damaged 3/$204.20 · quality 3/$150.58 ·
  changed_mind 2/$111.22 · late 1/$43.71.
- **Restock sheet** — `restock_value = sum(amount where restockable)`.
  Restockable = resellable as-new: `changed_mind` / `wrong_item` always;
  `late` only when `days_since_purchase <= 14`; `damaged` / `quality` never.
  Golden: **6 item(s) = $513.95**, head `#1010 Trail Sneakers $164.06`.
  Each row carries `inspect + relist in 24h` action with its citation.
- **Drafts (3)** — top-3 refunds by amount, each a template: apology +
  product/order/reason + verbatim `[shopify:orders#N]` + RESHIP (free
  replacement in 2 days) / REFUND ($X back in 3-5 days) choice + 2-hour
  confirm promise. Golden: `#1010 $164.06`, `#1007 $157.59`, `#1011 $144.04`.
- **do_today[3]** — exactly three concrete strings, each with a $ amount:
  restock run ($513.95), top-leak audit (wrong_item $359.02), reply batch
  (3 totalling $465.69).
- **prevented_today[2]** — template guardrails: `wrong_item` photo-QC
  checklist (prevents ~$89.75/wk) + relist run ($513.95 back on shelf).

## Golden numbers (seed=42 — do not change without updating tests)

```
headline: RETURNS CLOSE: $868.73 refunded in 12 return(s) · top leak wrong_item $359.02 · $513.95 restockable today
kpis: refund_total=868.73 refund_count=12 refund_rate_pct=20.0 assumed_sales=60
      avg_refund=72.39 top_reason=wrong_item top_reason_usd=359.02 top_reason_count=3
      restock_value=513.95 restock_count=6 top3_sum=465.69 prevented_today_usd=346.73
breakdown: wrong_item 3/$359.02 · damaged 3/$204.20 · quality 3/$150.58 · changed_mind 2/$111.22 · late 1/$43.71
restock head: #1010 Trail Sneakers $164.06 [shopify:orders#1010] -> inspect + relist in 24h
drafts head: #1010 Trail Sneakers wrong_item $164.06 [shopify:orders#1010] (RESHIP/REFUND choice)
```

Verify locally:

```bash
PYTHONPATH=src python3 -m pytest tests/unit/test_returns_close.py -q
```

## Inputs: your returns, as-is

Explicit dicts (demo schema) or generated on demand:

```python
build_returns_close(records=[...])  # your Shopify export, same keys as DEMO_RETURNS
build_returns_close(seed=42)        # seeded demo: 12 records
build_returns_close(records=[])     # empty week: honest $0.00 headline, no crash
```

Record keys: `order_id, product, reason
(damaged|late|wrong_item|changed_mind|quality), amount, days_since_purchase,
restockable bool, citation like "[shopify:orders#1001]"`.
When `records=None`, the seeded `DEMO_RETURNS(seed)` generator is used
(`demo_returns` is the same-function lowercase alias). `date_str="YYYY-MM-DD"`
pins the label for deterministic tests; otherwise today is used (never in math).

## Outputs: bundle layout (4 files)

- `close.json` — everything (headline, kpis, reason_breakdown, restock_sheet,
  drafts, do_today, prevented_today, records, citations, seed/date).
- `close.csv` — `reason,count,amount_usd` (one row per reason, amount desc;
  5 rows + header in the golden demo).
- `returns.csv` — `order_id,product,reason,amount,days_since_purchase,
  restockable,citation` (one row per return; 12 rows + header golden).
- `drafts.txt` — printable reply queue: headline + DO TODAY[3] + numbered
  COPY-PASTE DRAFT blocks (each with evidence) + PREVENTED TODAY guardrails
  + citations footer.

```python
from omni_one.packs.returns_close import close_to_csv, returns_to_csv, drafts_to_txt
close_to_csv(close)    # str with reason,count,amount_usd header
returns_to_csv(close)  # str with record-level header above
drafts_to_txt(close)   # str with COPY-PASTE DRAFT per refund
```

## Intended wiring (NOT shipped — notes for the next pack)

When the team is ready to expose the close, the intended surface mirrors the
seller close exactly (do not implement until this pack is merged):

```bash
# Intended CLI (requires touching cli.py — out of scope here):
omni-one returns-close --seed 42 --out ./returns_close_2026-10-11
omni-one returns-close --seed 7 --out ./returns_close_big
```

```python
# Intended API (requires touching api/ — out of scope here):
# POST /api/v1/returns/close {"seed": 42} -> close.json
# GET  /api/v1/returns/close.csv?seed=42   -> close.csv download
# Intended MCP: {"tool": "returns_close", "args": {"seed": 42}}
# Intended SDK: OmniOneClient.local().returns_close(seed=42)["headline"]
```

Wiring checklist for that pack: add `returns-close` command in `cli.py`
(thin wrapper over `build_returns_close` + `write_close_bundle`), add
`POST /api/v1/returns/close` (+ CSV download) in `api/`, register the MCP
tool in `mcp_server.py`, add a `returns_close()` SDK method in `client.py`,
and contract-test CLI/SDK/API parity the way `test_daily_close.py` does for
the seller close. Keep the engine import-free so none of that changes golden
numbers.

## Design rules (why support trusts it — same contract as revops/micro close)

- Deterministic: same (records, seed) → same close (minus date stamp).
  No LLM/network/wall-clock in math. Only `date` uses today, never scoring.
- Every dollar cites a signal: `[shopify:orders#N]` per record; drafts embed
  their citation verbatim; audit via `returns.csv` citation column.
- Idempotent, private, offline, $0. `free: true · offline: true` in every close.
- Template drafts only — apology + reship/refund choice, never invented order IDs.
- `close_to_csv` covers the reason breakdown; `returns.csv` covers records;
  `drafts.txt` is the phone/inbox screen.

See: `src/omni_one/packs/returns_close.py`,
`tests/unit/test_returns_close.py`,
`src/omni_one/packs/revops_close.py` + `src/omni_one/packs/micro_close.py`
(structural models: headline/do_today/sheets/bundle).
