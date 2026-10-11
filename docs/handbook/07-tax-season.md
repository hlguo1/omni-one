# 07 — Tax-season playbook (for the accountant meeting)

Bring: 12 × `close.json` + `close.csv` + `reorder.csv` + this checklist.

1. P&L tie-out: sum monthly `true_profit` == annual profit. Any month with margin < 0 gets
   a one-line cause from its `money_leaks` (fee_creep/shipping_loss/margin_dip/cogs_spike).
2. COGS proof: supplier invoices (`supplier_invoice*`) + OCR sidecars + `supplier_catalog`
   implied unit costs. Flag any month where COGS used the 30%-of-GMV fallback (no invoice).
3. Fee schedule: per-channel fees paid vs schedule (Shopify 2.9%+30c, Etsy 6.5%+20c,
   Amazon 15%, TikTok 5%+30c, eBay 13.25%+30c, Stripe 2.9%+30c, PayPal 3.49%+49c).
   Attach `money_leaks` fee_creep rows as the variance explanation.
4. Refunds/returns: count `REFUND_RISK` + `order_refund` events; tie to payout debits.
   Every refund must have a DM/review citation — or it didn't happen.
5. Inventory: year-end `on_hand` × unit cost = balance-sheet stock. Dead-stock list
   (`DEAD_STOCK` decisions) supports any write-down.
6. ZIP it: `accountant_pack` (see `cli_extra.py`) → one ZIP per year, manifest inside.

Red lines: no invented numbers (everything cites `file:line`), no edited CSVs
(regenerate via `omni-one close`), no missing months (cron `7am-close.cron`).
