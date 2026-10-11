# Accountant Close Samples (WAVE3-O)

Five `*.json` + `*.csv` pairs showing real daily-close outputs for the
accountant UI. Generated with repo code — no hand-written numbers:

```python
from omni_one.packs.seller_close import build_daily_close, close_to_csv
close = build_daily_close(events, date_str="2024-09-12", shop="Demo Shop")
```

* JSON = `build_daily_close(...)` plus `archetype`, `expected`, `inputs`,
  `generated_by`, `how_to_read`, `sample_notes` (shape is a superset of the
  live close: `kpis`, `headline`, `do_today`, `reorder_sheet`,
  `dead_stock_note`, `reply_queue`, `money_leaks`, `listing_fixes`,
  `po_draft`, `citations`).
* CSV = `close_to_csv(close)` exactly (columns: `DAILY CLOSE` header row,
  `metric,value` KPIs, `do_today_n,do_today`, reorder sheet
  `product,on_hand,sold_7d,days_left,reorder_qty_14d,supplier,urgency,citation`,
  leaks `leak,amount_usd,note,evidence`).

## Archetypes

| pair | archetype | expected profit | at-risk |
|---|---|---|---|
| `healthy` | Steady profitable day. Fees 3.6% of GMV, no angry inbox, stock healthy. One dead-stock line (Clay Ornament x40, zero sales) for the bundle note. | **$142.42 (58.4%)** | **$0.00**, 0 replies, 0 TODAY reorders, 0 leaks |
| `stockout` | Canvas Tote sells 16 units/7d with 3 on hand (~1.3 days left). Close screams reorder. | **$332.04 (59.7%)** | **$0.00**, 0 replies, **1 TODAY reorder** (Canvas Tote → Austin Textiles), 0 leaks |
| `refundstorm` | 4 refund/dispute orders, 4 angry DMs, one 1-star "chipped mug" review. GMV collapses to $80 and the close goes negative. | **$-76.22 (-95.3%)** | **$40.00 in 5 replies**, 0 TODAY reorders, 2 leaks (fee_creep + margin_dip) |
| `feebleed` | Silent bleed: fees 12.4% of GMV (fee_creep) + Bulky Vase ships at 30% of GMV (shipping_loss). Happy inbox — nobody complains, margin just leaks. | **$129.04 (52.7%)** | **$0.00**, 0 replies, 0 TODAY reorders, **2 leaks** |
| `empty` | Null state: zero events (closed day / empty export folder). All KPIs 0, lists empty-not-null, PO draft falls back to healthy-stock text. | **$0.00 (0%)** | **$0.00**, 0 replies, 0 reorders, 0 leaks |

## Sizes

Every JSON is 80+ lines, every CSV is 20+ lines:

* healthy.json 145 / healthy.csv 23
* stockout.json 185 / stockout.csv 24
* refundstorm.json 222 / refundstorm.csv 25
* feebleed.json 119 / feebleed.csv 25
* empty.json 82 / empty.csv 23

## Use

Load any pair in the accountant UI to preview that archetype
(all-clear, reorder-today, inbox-fire, fee-bleed, null-state).

## Second batch (from evals/corpus_big archetypes, generated via build_daily_close)

| Pair | Shop | Profit | At-risk | Note |
|---|---|---|---|---|
| deadstock | shop_05 | $209.25 | $141.40 | clearance candidate present |
| pricemismatch | shop_06 | $314.63 | $106.12 | align channels up |
| shippingloss | shop_07 | $101.31 | $232.00 | free-shipping audit |
| unicode | shop_08 | $183.42 | $143.58 | CJK/emoji names preserved |
| semicolon | shop_10 | $245.50 | $140.00 | delimiter-tolerant parse |
