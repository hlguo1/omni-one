# Morning Routine — the 5-minute daily close (7-day adoption plan)

> **Goal:** every morning, before you pack a single parcel, you know
> (1) did I actually make money yesterday, (2) what will stock out,
> (3) who is angry right now. One command, offline, $0:
>
> ```bash
> omni-one close --folder ~/my_shop --out ./close_today
> ```
>
> You get `close.json` + `close.csv` + `reorder.csv` + `replies.txt` + `po.txt`.
> Print them, or just read the **headline** — one line written for coffee-brain.

## The headline, decoded

```
Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder(s) TODAY · 0 leak(s) to plug
```

| Fragment | Meaning | Where it comes from |
|---|---|---|
| `Profit $169.09 (61.7%)` | True profit = GMV − fees − shipping − COGS, plus margin | orders CSVs + supplier invoices |
| `$102.75 at risk in 3 angry messages` | Refund exposure ≈ 3 × AOV sitting in unanswered complaints | DMs + 1–2★ reviews |
| `1 reorder(s) TODAY` | SKUs with < 3 days of supply left | velocity vs on-hand |
| `0 leak(s) to plug` | Fee/shipping/margin anomalies | channel fee math |

Every number cites `[file:line]`. If a number has no citation, don't trust it —
fix the source file, not the spreadsheet.

## The 5-minute ritual (every day)

- [ ] **0:00–0:30 — Run the close.** `omni-one close --folder … --out …`. Read the headline out loud.
- [ ] **0:30–2:00 — Replies first.** Open `replies.txt`. Copy-paste draft #1, personalise one sentence, send. Repeat while the kettle boils. Rule: **P0 (refund / hasn't-arrived / damaged) within 2 hours, no exceptions.** See `03-reply-playbook.md`.
- [ ] **2:00–3:30 — Reorders.** Open `reorder.csv`. Anything `ORDER TODAY` → send the `po.txt` draft to that supplier *today*. Anything `this week` → diary it. See `02-supplier-playbook.md`.
- [ ] **3:30–4:30 — One leak.** If `money_leaks` is non-empty, do the cheapest fix (usually: raise one price $1, or move one SKU off the expensive channel). Log it.
- [ ] **4:30–5:00 — File it.** Move the day's exports into the shop folder, append one line to your ledger (see `04-accountant-pack.md`).

## 7-day adoption plan

### Day 1 — Drop the folder (15 min, one-off)
- [ ] Create `~/my_shop/` and drop in: Shopify/Etsy/Amazon order exports, `inventory.csv`, review export, DM export (`.txt` or `.json`), supplier invoices (photos or `.txt`).
- [ ] Run `omni-one briefing --folder ~/my_shop`. Confirm GMV looks roughly right (within 5% of what the channel dashboard says).
- [ ] Run `omni-one close --folder ~/my_shop --out ./close_day1`. Read every file once. Don't act yet — just calibrate trust.
- [ ] **Done when:** the headline profit number doesn't surprise you by more than 20%.

### Day 2 — Replies only
- [ ] Run the close. Work *only* the reply queue. Send every P0 draft (edited, not blind).
- [ ] Count replies sent vs queue length. Target: inbox zero on P0s.
- [ ] **Done when:** reply queue is empty or every remaining item has a diary date.

### Day 3 — Suppliers
- [ ] Run the close. Read `02-supplier-playbook.md` sections 1–2.
- [ ] Send the first real PO from `po.txt` (or confirm stock is healthy — also a result).
- [ ] Record unit costs for your top 3 SKUs in a notebook. This is your COGS bible now.
- [ ] **Done when:** one PO sent, or written confirmation that nothing needs reordering.

### Day 4 — Fees & leaks
- [ ] Run the close. Open `close.csv`, section `money_leaks`.
- [ ] Compute your fee % per channel (Etsy ≈ 6.5%+$0.20 · Shopify ≈ 2.9%+$0.30 · Amazon ≈ 15%). If blended fees > 12% of GMV, pick one SKU to reprice or re-channel.
- [ ] **Done when:** you can state your fee % from memory to within 1 point.

### Day 5 — Full loop, timed
- [ ] Run the whole ritual with a timer. Target: under 5 minutes excluding message-sending.
- [ ] Run `omni-one scenarios --folder ~/my_shop` once and read the top 3 decisions. These are tomorrow's work, not today's.
- [ ] **Done when:** close → replies → reorder → leak → file, all inside 30 minutes wall-clock.

### Day 6 — Accountant pack
- [ ] Follow `04-accountant-pack.md` reconciliation steps 1–4 on this week's closes.
- [ ] Send your accountant (or future self) `close.csv` + `reorder.csv` for the week.
- [ ] **Done when:** one week of closes reconciles to the bank statement within $5.

### Day 7 — Incident drill
- [ ] Pick one runbook from `05-incidents.md` (stockout, 1-star, fee spike) and walk it dry — find the citations, draft the messages, price the fix.
- [ ] Write down your personal thresholds (how many days of cover? what margin floor?).
- [ ] **Done when:** you can run any of the three runbooks without re-reading the theory.

## Checklists

### Daily (laminate this)
- [ ] Close run, headline read
- [ ] All P0 replies sent < 2h
- [ ] ORDER TODAY POs sent
- [ ] One leak touched
- [ ] Files archived

### Weekly (Friday, 20 min)
- [ ] 7 closes reconciled, GMV vs channel dashboards ±2%
- [ ] Supplier ETAs chased (anything ordered > 7 days ago with no tracking)
- [ ] Dead stock listed (anything with 0 sales + 5+ units → clearance draft)
- [ ] Prices reviewed against fee changes
- [ ] Backup: copy `~/my_shop` to USB / second machine

### Monthly (first Monday, 1 h)
- [ ] Month's `close.csv` files → accountant pack (`04-accountant-pack.md`)
- [ ] Supplier scorecard updated (price, ETA, defect rate)
- [ ] Worst seller decision: kill, bundle, or clearance
- [ ] Margin floor check: blended true margin ≥ 10%? If not, see leak playbook

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Profit looks too high | Supplier invoice missing → COGS under-counted | Drop the invoice `.txt`/photo in the folder |
| Profit looks too low | Duplicate invoice (`.jpg` + `.jpg.txt` + `.txt`) | Close dedups identical content automatically; check `files_ingested` vs `files_seen` in the briefing |
| `reorder.csv` empty but shelves bare | Product names differ between orders and inventory (`Tote` vs `Tote Bag Handmade`) | Rename to match; matching is fuzzy but exact is bulletproof |
| Reply queue empty but customers complain | DMs exported as screenshots, not text | Export DMs as `.txt`/`.json`, or paste text into `instagram_dm.txt` |
| Fees look wrong | Channel misdetected from filename | Name order files `shopify_*`, `etsy_*`, `amazon_*` |
| Semicolon CSV ignored | Locale export (`;` delimiter) | Supported — the Sniffer handles it; if a file shows 0 rows, check it opens as UTF-8 |
| Weird characters (`ï»¿`) | BOM headers from Excel | Supported (UTF-8-SIG); upgrade with `evals/generate.py --help` edge cases if testing |

## The one rule

> **No citation, no action.** The close refuses to invent tasks. If it tells
> you to reorder, it shows you `[inventory.csv:2]`. If it tells you to reply,
> it shows you `[instagram_dm.txt:4]`. Hold it to that standard — and hold
> your suppliers, channels, and accountant to the same one.
