# AUTO CLOSE — one command, right closes

Small sellers shouldn't have to learn our 11 closes. They dump whatever they
have — sales CSVs, phone photos of receipts, a reviews export, supplier
invoices — into one folder and run:

```bash
omni-one auto --folder ./my_shop --out ./auto_today
```

The router sniffs the folder (filenames + extensions + a 4KB content peek),
prints a **plan with reasons** (`vision: 2 photo(s) found — OCR + COGS`),
runs exactly those closes, and writes `auto.json` + `AUTO.txt` (+ per-close
bundles live under each close's own `write_close_bundle`).

```python
from omni_one.packs.auto_close import run_auto
s = run_auto("./my_shop", out="./auto_today", seed=42)
print(s["ran"])        # e.g. ['vision', 'seller', 'returns', 'reputation', 'forecast', 'pipeline']
print(s["headlines"])  # one line per close
```

## Selection rules

| What we find | Close that runs | Why |
|---|---|---|
| photos (png/jpg/webp…) | `vision` | OCR + COGS + numbers |
| sales/order files | `seller` | daily money close (profit, PO, replies) |
| return/refund/cancel files | `returns` | plug the leak |
| payout/bank/invoice files | `cashflow` | cash-in-hand check |
| review files | `reputation` | reply queue + star repair |
| inventory/stock files | `forecast` | stockout forecast + PO |
| ≥2 shop subfolders | `rollup` | portfolio rollup |
| B2B pipeline files | `revops` | churn $ + call sheet |
| any data files | `pipeline` | quality + cost check on the way in |
| `--deep` | `ops` | full methodology audit bundle |

- **Empty folder** → `seller` on seeded demo (never an empty answer).
- **No folder** → demo showcase (`seller, vision, returns, cashflow, reputation, forecast`).
- **Real CSVs are used when they parse** (inventory → SKUs, refunds → returns,
  reviews → reviews, payouts → payouts); anything unparseable falls back to
  seeded demo for that close only. One close never kills the run
  (`{"ok": False, "error": ...}` + continue).

## Design rules

- Deterministic: sorted walk, seeded demos, same folder → same plan.
- $0, offline, no LLM. Sniffing is keyword matching, capped at 4KB/file.
- Every pick cites evidence filenames; `AUTO.txt` is the human-readable plan.
- Intended CLI: `omni-one auto`. Intended API: `POST /api/v1/auto/close`.
