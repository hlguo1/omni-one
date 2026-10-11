# Supplier Playbook — POs, renegotiation, and COGS tracking

> Suppliers are your second-biggest cost after channel fees, and the only one
> you can negotiate with a human. This playbook turns the daily close's
> `reorder.csv` + `po.txt` into purchase orders that arrive on time, at a
> price you can prove.

## 1. Reading `reorder.csv`

```
product,on_hand,sold_7d,daily_velocity,days_left,reorder_qty_14d,supplier,urgency,citation
Tote Bag Handmade,2,6,0.86,2.3,10,Acme Textiles,ORDER TODAY,[inventory.csv:2]
```

| Column | Definition |
|---|---|
| `on_hand` | Units in `inventory.csv` right now |
| `sold_7d` | Units sold in the last 7 days of order files |
| `daily_velocity` | `sold_7d / 7` |
| `days_left` | `on_hand / daily_velocity` (999 = no sales) |
| `reorder_qty_14d` | `ceil(velocity × 14 − on_hand)`, floored at 0 |
| `urgency` | `ORDER TODAY` (< 3d) · `this week` (< 5d) · `watch` |

**Cover policy:** 14 days. Why 14? It covers the average small-supplier lead
time (7–10 days) plus a weekend of over-selling, without locking cash in
dead stock. If your supplier ships in 3 days, drop to 7 (edit `COVER_DAYS`
in `seller_close.py`). If they ship from overseas (20+ days), raise to 30 —
and find a backup supplier (section 5).

## 2. PO scripts (copy-paste, then fill the brackets)

### 2a. Standard reorder (generated automatically as `po.txt`)

```
Subject: Reorder request — [SUPPLIER]

Hi [NAME]!

Please send the following for [YOUR SHOP]:
  - Tote Bag Handmade: 10 units (have 2, 2.3d left) [[inventory.csv:2]]

Please confirm price + ETA. Last invoice numbers are cited above from our records.

Thanks!
[YOUR SHOP]
```

Rules: always cite your last invoice, always ask for **price + ETA in the
same email** (one round-trip, not two), always state the quantity as a
number, never "some more".

### 2b. First order with a new supplier

```
Subject: First order + samples — [YOUR SHOP]

Hi [NAME], I run [SHOP], [X] orders/month on [CHANNEL].
I'd like to start with:
  - [PRODUCT]: [QTY] units at [TARGET UNIT PRICE]
Questions:
  1. Unit price at [QTY] and at [2×QTY]?
  2. Lead time to [CITY]? Defect/return policy?
  3. Can you send 1 sample? I'll pay + shipping.
If samples pass, first PO goes out this week.
Thanks! [YOU]
```

### 2c. Chasing a late delivery (7+ days, no tracking)

```
Subject: Checking ETA — PO of [DATE] ([QTY]× [PRODUCT])

Hi [NAME], our PO from [DATE] hasn't arrived and we're [N] days from
stockout ([citation]). Can you confirm tracking today?
If it can't ship by [DATE], please tell me now so I can split the order.
Thanks! [YOU]
```

### 2d. Defect batch

```
Subject: Defect batch — [PRODUCT], [N] units ([DATE] delivery)

Hi [NAME], [N] of [QTY] units from the [DATE] batch have [DEFECT].
Photos attached. Per your return policy, I'd like [replacement / refund
of $X]. I need the replacements by [DATE] to avoid stockout.
Can you confirm today? Thanks! [YOU]
```

## 3. Renegotiation thresholds

Renegotiate (or re-shop) when **any** of these trip — check monthly:

| # | Threshold | How to detect | Action |
|---|---|---|---|
| 1 | Unit cost rises > 5% with no notice | New invoice line vs COGS bible (§4) | Email within 48h citing old price + invoice line |
| 2 | COGS > 45% of retail on any top-3 SKU | `close.csv` cogs vs GMV per product | Raise retail $1–2 *or* renegotiate *or* re-source |
| 3 | Lead time slips 2× in a quarter | Your PO log (date sent vs arrived) | Dual-source that SKU (section 5) |
| 4 | Defect rate > 3% of a batch | Review/DM complaints citing damage + your QC count | Defect email (§2d) + 5% discount or free replacements |
| 5 | Supplier unresponsive > 72h on an ORDER TODAY | Your sent folder | Escalate to phone; start backup-supplier trial |
| 6 | Blended true margin < 10% for 2 weeks | Close headlines | Full cost review: fees (§4 in morning routine), COGS, shipping — in that order |

### Renegotiation script

```
Subject: Price review — [PRODUCT] ([QTY]/month run-rate)

Hi [NAME], we've ordered [QTY] units/month for [N] months (last:
[invoice citation]). Your latest quote is $[NEW] vs our working
cost of $[OLD] (invoice [citation]).
I want to stay with you — can you meet $[TARGET]? I can commit to
[QTY] units/month for 3 months + pay in [X] days.
If not, I understand — I'll need to split volume elsewhere.
Thanks! [YOU]
```

Mechanics that work better than begging: **commit volume** (even small),
**pay faster** (7 days beats 30), **order predictably** (same day monthly).
Suppliers discount reliability, not sympathy.

## 4. COGS tracking (the bible)

Keep one file — paper is fine — with one row per SKU:

```
SKU     Product            Supplier      Unit $  Since       Lead time  Notes
TB001   Tote Bag Handmade  Acme Textiles 4.00    2024-09-10   8d        canvas+strap
CM002   Ceramic Mug        Clay Co       6.10    2024-09-10   6d
```

How the close computes COGS (so you can audit it):

1. Supplier `.txt` invoice lines shaped `NAME QTY x UNIT TOTAL`
   (e.g. `Tote Bag Canvas 50 x 4.00 200.00`) build a per-material catalog.
2. Each order's product fuzzy-matches the catalog → `unit × qty` COGS.
3. No match → 30% of that row's GMV (documented heuristic).
4. No invoices at all → 25% of smallest invoice total (last resort).

**Your job:** make step 2 always hit — keep invoice product words overlapping
your listing titles (`Tote`, `Mug`, `Print`, `Scarf`). One shared word is
enough. Check `close.json → kpis.cogs` weekly: if it jumps without a price
change, an invoice line stopped matching.

### Invoice hygiene
- One `.txt` per delivery: supplier name, one `QTY x UNIT TOTAL` line per
  material, `Shipping`, `Total $X`. Photo invoices work too (OCR), but text
  is exact.
- Never keep both a photo and a hand-typed copy with different numbers —
  the close dedups *identical* files, not *conflicting* ones.
- Filename pattern: `supplier_invoice_YYYY-MM-DD.txt` (date keeps them sortable).

## 5. Dual-sourcing (the 1-person insurance policy)

For your #1 best seller only:
- [ ] Identify backup supplier (Etsy wholesale, Alibaba sample, local maker).
- [ ] Trial order: smallest qty, record unit + lead time + defect count.
- [ ] Split rule: primary 70% / backup 30% once backup passes 2 clean deliveries.
- [ ] If primary lead time exceeds `days_left` on `reorder.csv`, flip the split immediately.

Cost: one extra sample order per quarter. Payout: you never lose your best
seller to someone else's shipping delay.

## 6. Monthly supplier scorecard (10 min)

| Supplier | Orders | On-time % | Defect % | Unit Δ | Verdict |
|---|---|---|---|---|---|
| Acme Textiles | 3 | 100 | 0 | +0% | keep |
| Clay Co | 2 | 50 | 5% | +6% | renegotiate / trial backup |

Drop any supplier with < 70% on-time or > 5% defects two months running.
Your shop is too small to subsidise someone else's chaos.
