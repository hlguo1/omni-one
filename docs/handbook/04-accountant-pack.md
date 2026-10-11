# Accountant Pack — `close.csv` field dictionary + reconciliation

> Your accountant doesn't want a dashboard. They want totals that tie to the
> bank, with receipts. The daily close produces exactly that: `close.csv`
> (money), `reorder.csv` (inventory movement intent), `replies.txt` (refund
> evidence trail). This page is the dictionary + the monthly routine.

## 1. `close.csv` field dictionary

`close.csv` has four sections. Section 1 is a title row (`DAILY CLOSE,
<date>, <headline>`). Then:

### Section A — `metric,value` (the ledger row)

| metric | Type | Definition | Source files |
|---|---|---|---|
| `gmv` | USD, 2dp | Gross merchandise value: sum of order-row totals | `shopify_orders.csv`, `etsy_settlement.csv`, `amazon_payout.csv` |
| `fees` | USD, 2dp | Channel fees: parsed per row, else estimated (Etsy 6.5%+$0.20 · Shopify 2.9%+$0.30 · Amazon 15% · other 8%) | same order files |
| `shipping` | USD, 2dp | Shipping paid/collected per order rows | same order files |
| `net` | USD, 2dp | `gmv − fees − shipping` | computed |
| `cogs` | USD, 2dp | Cost of goods sold, allocated per-unit from supplier invoices (see §3) | `supplier_invoice_*.txt` (+ OCR sidecars) |
| `true_profit` | USD, 2dp | `net − cogs`. **The** number. Golden: demo shop = $169.09 | computed |
| `margin_pct` | %, 1dp | `true_profit / gmv × 100` (0 when gmv = 0) | computed |
| `orders` | int | Order rows ingested | order files |
| `aov` | USD, 2dp | `gmv / orders` (0 when no orders) | computed |
| `best_seller` | object | `{product, qty, gmv}` top seller by units | computed |
| `money_at_risk_usd` | USD, 2dp | `len(reply_queue) × aov` — refund exposure in unanswered complaints | DMs + reviews |

**Invariant your accountant can check:** `true_profit ≤ gmv` on every row,
always. (Evals assert this per shop; see `evals/run.py`.) If it ever fails,
the data is corrupt — re-export the channel CSVs.

### Section B — `do_today_n,do_today` (actions, not money)
Three lines: reply workload, top reorder, top leak. Informational; not booked.

### Section C — reorder block
`product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation`
— the stock position at close time. `reorder_qty_14d` is a *purchase intent*,
not a booked expense. Book the expense when the supplier invoice arrives.

### Section D — leak block
`leak,amount_usd,note,evidence` — fee creep / shipping loss / margin dip
with dollar amounts. `amount_usd` may be empty for unit-level leaks (e.g.
per-order shipping loss); the `note` carries the detail.

## 2. `reorder.csv` + `replies.txt` + `po.txt`

| File | Accountant use |
|---|---|
| `reorder.csv` | Inventory intent: what you ordered and why (citation per row). File with purchase invoices. |
| `replies.txt` | Evidence trail for refunds/chargebacks: customer words + your draft + citation. Attach to disputed transactions. |
| `po.txt` | The PO email as sent. File the supplier's confirmation next to it. |
| `close.json` | Machine-readable everything (KPIs, full reorder sheet, reply queue, leaks, PO draft). Keep 12 months. |

## 3. How COGS is computed (explain it once, then point here forever)

1. Each supplier `.txt` line shaped `MATERIAL QTY x UNIT TOTAL`
   (example: `Tote Bag Canvas 50 x 4.00 200.00`) registers a unit cost.
2. Each order row fuzzy-matches its product to the catalog; COGS += unit × qty.
3. Unmatched products fall back to 30% of row GMV (flagged implicitly: COGS
   ends in round heuristic values — investigate if a whole month looks like that).
4. No invoices at all → 25% of smallest invoice total (emergency fallback).

**What this means for bookkeeping:** COGS in `close.csv` is *allocated cost
of goods sold for that day's mix*, suitable for margin tracking. Your tax
filing still uses actual purchase invoices (cash basis) — the close tells
you the margin story; the invoice shoebox tells the tax story. They should
converge within a few % monthly. If they don't, a supplier line stopped
matching (rename drift) — see supplier playbook §4.

## 4. Reconciliation steps (monthly, 30 min)

**You need:** the month's `close.csv` files, channel payout statements
(Shopify/Etsy/Amazon), bank statements, supplier invoices.

- [ ] **Step 1 — Sum the closes.** Add `gmv`, `fees`, `shipping`, `true_profit`
      across the month's `close.csv` Section A rows. (One-liner:
      `awk -F, '/^(gmv|fees|shipping|true_profit),/{s[$1]+=$2} END{for(k in s)print k,s[k]}' close_*/close.csv`.)
- [ ] **Step 2 — Tie GMV to channels.** Monthly GMV should match channel
      dashboards within ±2%. Bigger gap → missing export (a week of orders
      never dropped in the folder) or a duplicated file.
- [ ] **Step 3 — Tie fees to payouts.** `fees` should match
      (channel sales − channel payout) within ±3%. Etsy/Shopify estimate
      formulas when the export omits fee columns, so ±3% is normal; ±10% means
      a fee column is being mis-parsed — check header names.
- [ ] **Step 4 — Tie profit to bank.** `true_profit − supplier payments −
      refunds issued` should track the business account delta within $5–10
      (timing: payouts lag 2–5 days; carry the lag explicitly month to month).
- [ ] **Step 5 — Refund audit.** Count `replies.txt` P0s vs refunds in the
      bank feed. Every refund needs a citation (customer message). Orphans →
      update the DM export habit.
- [ ] **Step 6 — Sign off.** Write one line: `2024-09: GMV $X, profit $Y,
      reconciled ±$Z — initials`. Save with the month's closes.

## 5. Common discrepancies and fixes

| Discrepancy | Cause | Fix |
|---|---|---|
| GMV 5–15% low vs dashboard | Etsy `price` column held unit price, file used qty>1 (or vice versa) | Re-export with line totals; generator writes totals (see `evals/generate.py`) |
| Fees ~0 on Shopify rows | Export omitted fee column → 2.9%+$0.30 estimated | Fine for ops; for filing, use the payout statement, not the estimate |
| COGS jumps month to month | New supplier wording broke fuzzy match | Align one word between invoice and listing (supplier playbook §4) |
| Profit > GMV (never normal) | Corrupt row (negative fee parsed as credit) | Fails eval invariant — find the row, fix the CSV, re-run close |
| `money_at_risk` looks huge | Old DMs never cleared from the folder | Archive handled DMs monthly; the folder is a *queue*, not an archive |
| Semicolon/BOM files show 0 rows | Excel locale export | Supported by the parser; verify the file opens as UTF-8 and the name contains `order/shopify/etsy/amazon` |

## 6. Year-end (2 h, once)
- [ ] 12 monthly sign-off lines → totals for the tax preparer.
- [ ] Inventory count (physical) vs sum of `inventory.csv` on-hands; book shrinkage.
- [ ] Supplier 1099s (US) / equivalents: total paid per supplier from invoices.
- [ ] Archive: `my_shop/` + all `close_*` bundles + payout PDFs → two places (USB + cloud).
- [ ] Delete nothing until the return is filed and the refund window (chargebacks: 120 days) has passed.
