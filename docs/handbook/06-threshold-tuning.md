# 06 — Threshold tuning guide

All Seller OS numbers come from one table: `SCENARIO_THRESHOLDS` in
`src/omni_one/packs/seller_scenarios.py` + `COVER_DAYS`/`STOCKOUT_DAYS` in
`src/omni_one/packs/seller_close.py`. Tune per shop, cite changes in the close.

| Knob | Default | Raise when | Lower when |
|---|---|---|---|
| `stockout_days` | 5.0 | supplier lead time > 7d | digital goods / print-on-demand |
| `COVER_DAYS` | 14 | lead time long, bestseller | cash tight, storage small |
| `fee_creep_pct` | 12.0 | Amazon-heavy mix (15% referral normal) | Shopify-only (should be ~3%) |
| `shipping_loss_pct` | 20.0 | free-shipping-over-$X strategy | lightweight goods |
| `margin_low_pct` | 10.0 | handmade premium (target 50%+) | high-volume low-margin resell |
| `dm_backlog_count` | 3 | solo owner, weekends | team inbox, SLA 2h |
| `price_mismatch_pct` | 5.0 | FX wobble across regions | same-currency multi-channel |
| `dead_stock_min_qty` | 5 | bulky storage cost | tiny accessories |

Procedure: change ONE knob → `omni-one close --folder <shop> --out /tmp/close_after` →
diff `reorder.csv` + `close.csv` vs before → keep if `money_at_risk` falls without
reorder spam. Record the knob + reason in `close.json` notes for the accountant.
Never tune to hide a leak — fees are facts, pricing is the lever.
