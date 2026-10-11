# 09 — Migrating from spreadsheets (weekend switch)

Friday: export every sheet you have (orders, inventory, payouts) as CSV into `./data/inbox`.
Do NOT clean them — the parsers handle weird headers, semicolons, BOM, multi-currency.

Saturday: run `omni-one close --folder ./data/inbox --out ./close_first`. Compare ONE number
against your sheet: GMV. If it differs >1%, the cause is in `ingest_report.errors` or a
refunded row your sheet excluded — check `order_refund` signals first.

Sunday: send the first `po.txt`, reply the first 3 drafts, hand `close.csv` to the accountant
with the field dictionary (`docs/handbook/04-accountant-pack.md`). Monday onward: the 5-minute
close replaces the spreadsheet. Keep the old sheet read-only for 30 days, then archive.

What NOT to migrate: pivot-table lore, color-coded gut feelings, "adjusted" GMV. If a number
can't cite `file:line`, it doesn't cross over.
