# Daily Close — the 5-minute ritual your shop runs every morning

Sellers don't live in dashboards. They **close the day**: money in, angry customers answered,
shelves restocked, leaks plugged, accountant handed a file. Omni-One's Daily Close is that ritual
in one command — offline, free ($0), private, every number cited `file:line`.

```bash
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
# -> close.json + close.csv + reorder.csv + replies.txt + po.txt
```

## The morning routine (5 min)

| Min | You do | Close gives you |
|-----|--------|-----------------|
| 0–1 | Read the headline | `Profit $169.09 (61.7%) · $102.75 at risk in 3 angry messages · 1 reorder TODAY · 0 leaks` |
| 1–3 | Copy-paste replies | `replies.txt`: 3 drafts with customer name, issue, order citation — send in IG/Etsy/Amazon |
| 3–4 | Send the PO | `po.txt`: `Subject: Reorder — Acme Textiles: Tote x10 (2 left, 2.3d supply) [inventory.csv:2]` |
| 4–5 | File + fix | `close.csv` → accountant/sheets; fix 1 listing from `listing_fixes` |

## What it computes (deterministic, no LLM for numbers)

- **True profit, not GMV**: GMV − fees − shipping − COGS (COGS from supplier invoices via OCR/photo or CSV; per-unit catalog; 30% heuristic fallback). Golden demo: GMV $274.00 → profit **$169.09**.
- **Money at risk**: `unanswered complaints × AOV`. Each ignored "where is my order" ≈ one refund + one 1-star. Demo: 3 messages × $34.25 AOV ≈ **$102.75 at risk** — that number gets owners out of bed.
- **Reorder sheet**: `daily_velocity = sold_7d/7`, `days_left = on_hand/velocity`, `reorder_qty = ceil(velocity×14 − on_hand)`. Tote demo: 2 left, 6 sold/7d → **2.3d left → ORDER TODAY x10**. Urgency: `<3d ORDER TODAY`, `<5d this week`.
- **Reply drafts**: deterministic templates (no hallucination, no cost) grounded in `[file:line]`: apology + order pull + 2h fix promise + reship/refund choice. Review variant for public replies.
- **Money leaks with $**: fee creep (fees/GMV ≥12% → $ + channel comparison), shipping loss per order (≥20%), margin dip (<10%), COGS spike. Each with dollar + evidence.
- **Listing fixes**: LISTING_GAP (sales, zero reviews → UGC ask), REVIEW_CRISIS (public reply), PRICE_MISMATCH (align channels), WORST_SELLER (clearance).

## Inputs: your mess, as-is

Drop anything in the folder — parsers auto-detect, no renaming:
`shopify_orders.csv` / `etsy_settlement.csv` / `amazon_*.csv` (any headers), `inventory.csv`
(with `supplier` column kept), `reviews.csv`, `instagram_dm.txt` / `tiktok_dm.json`,
`supplier_invoice.jpg/png/pdf/txt` (Tesseract OCR + sidecar `.jpg.txt` dedup via content hash).

## Outputs: artifacts you already use

- `close.csv` — accountant/sheets-ready KPIs + actions + leaks
- `reorder.csv` — supplier-ready: product, on_hand, days_left, qty_14d, supplier, citation
- `replies.txt` — copy-paste drafts + PO email in one printable file
- `po.txt` — send as-is to supplier
- `close.json` — everything, for API/MCP/automation

## Interfaces

```bash
omni-one close --demo --out ./close_today        # CLI
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11
POST /api/v1/seller/close {"demo":true}          # API
GET  /api/v1/seller/close.csv?demo=true          # CSV download
{"tool":"seller_close","args":{"demo":true}}     # MCP (Claude/Cursor)
from omni_one.client import OmniOneClient        # SDK
OmniOneClient.local().close(demo=True)["headline"]
```

## Habit loop (why thousands stick)

Day 1: folder drop → close bundle → 1 refund saved ≈ pays for the year (it's $0).
Day 7: supplier catalog + velocity learned → reorder qty gets smarter, PO one-click.
Day 30: `money_at_risk → $0` streak + margin trend → the close becomes the shop's P&L.

Roadmap: scheduled 7am close (`cron` + email), multi-shop compare, TikTok Shop parser,
Spanish/Chinese DM templates, photo stock-count (`on_hand` from shelf photo).

See: `src/omni_one/packs/seller_close.py`, `tests/unit/test_daily_close.py` (4 golden tests),
`examples/daily_close_demo.py`, `docs/SCENARIOS.md` (12 detectors feeding the close).

## Draft language (numbers never change)

```bash
omni-one close --demo --locale es --out ./close_today   # respuestas + PO en español
POST /api/v1/seller/close {"demo":true,"locale":"zh"}   # 中文草稿
```

`locale` ∈ `en es zh fr de` (see `src/omni_one/i18n/`). Only reply + PO drafts switch language;
KPIs, reorder math, leaks, citations are identical across locales (contract-tested).
The Close PWA has a language dropdown; the API/MCP/SDK all accept `locale`.
