# 08 — Peak-season playbook (holidays, promos, virality)

1. Two weeks out: raise `COVER_DAYS` 14 → 21 for bestsellers, confirm supplier ETA in writing.
2. Daily during peak: run the close TWICE (7am + 7pm). Reply SLA drops 2h → 1h; every
   `UNANSWERED_COMPLAINT` older than 4h is a refund — treat it as one.
3. Price freeze: no channel edits mid-peak unless `PRICE_MISMATCH` fires — then align UP,
   never race down. Note the reason in `close.json`.
4. Dead stock becomes bundle fodder: pair any `DEAD_STOCK` SKU with the bestseller at
   15% off rather than discounting the winner.
5. Cash: peak GMV lies (refunds lag 7–14d). Watch `money_at_risk_usd`, not GMV. Keep a
   20% refund reserve from `true_profit` until returns settle.
6. After: one retro close (`--out ./close_peak_retro`) — top leak, slowest reply, worst
   stockout. Fix exactly one knob before next peak.
