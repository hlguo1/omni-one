# corpus_big — 40-shop deterministic eval corpus (WAVE2-H)

40 small shops (`shop_01` … `shop_40`), each 5–6 files. Stable on disk
(no randomness at rest — generated once from index-based formulas).

## Layout per shop

- `shopify_orders.csv` **OR** `etsy_settlement.csv` (4–10 rows) — one orders file.
  `pricemismatch` shops carry **both** (Shopify + Etsy) to demo cross-channel
  price drift. `semicolon` shops carry `shopify_orders_semicolon.csv`
  (`;`-delimited, Sniffer must survive).
- `inventory.csv` (3–6 rows, `sku,product,stock,supplier`)
- `instagram_dm.txt` **OR** `tiktok_dm.json` (2–5 msgs, `tiktok` when `shop % 3 == 0`)
- `reviews.csv` (2–4 rows, `date,product,stars,review`)
- `supplier_invoice.txt` (~11 lines, `QTY x UNIT TOTAL` + `Total $`)

All files < 60 lines. All ingest via
`omni_one.packs.seller_os.ingest_seller_folder` (>5 events/shop).

## Archetype rotation (shop index % 10)

| # | archetype | signal |
|---|-----------|--------|
| 1 | `healthy` | balanced fees/ship/stock, mostly 5-star, 1 at-risk + 1 happy DM |
| 2 | `stockout` | best seller 1–2 left, 75% orders = best seller → `STOCKOUT_RISK`, 2.3d supply |
| 3 | `refundstorm` | `Status=refunded/returned`, all-negative reviews, refund DMs → `REFUND_RISK` |
| 4 | `feebleed` | fees ~18.5%+ $1.20 (~20% GMV) → `FEE_CREEP` leak (threshold 12%) |
| 5 | `deadstock` | 2 inventory lines 30–38 units, zero sales → `DEAD_STOCK` clearance |
| 6 | `pricemismatch` | same SKU $28 Shopify vs $34 Etsy (+22%) → `PRICE_MISMATCH` |
| 7 | `shippingloss` | ship $12–14/order (~40% GMV) → `SHIPPING_LOSS` |
| 8 | `unicode` | CJK + emoji + accents in products/customers/reviews/DMs — parser must not crash |
| 9 | `empty-ish` | sparse minimum: 4 orders, 3 inv, 2 DM, 2 reviews, 1-line invoice (13 events) |
| 10 | `semicolon` | `;`-delimited orders, same schema — Sniffer path |

Rotation repeats 4×: `shop_01=healthy`, `shop_02=stockout`, … `shop_10=semicolon`,
`shop_11=healthy`, etc. 4 shops per archetype.

## manifest.csv

Columns: `shop,archetype,orders,gmv`.
`orders` = rows written, `gmv` = sum of line totals (Shopify `Total` + Etsy `price`
which already holds line total). Verified: parsed GMV via `ingest_seller_folder`
matches manifest to < $0.02 for all 40 shops.

## Determinism

No `random` at rest. All choices are `(shop_index, row_index)` modular arithmetic:
qty `1+((i+j)%3)`, price jitter `((i*7+j*3)%5-2)*0.5`, customers round-robin,
dates `2024-09-10..12`, COGS `32–42%` retail, invoice qty `20..60`.
Same generator always yields byte-identical CSVs.

## Use

```bash
PYTHONPATH=src python3 -c "from omni_one.packs.seller_os import ingest_seller_folder; e,r=ingest_seller_folder('evals/corpus_big/shop_01'); print(len(e))"
PYTHONPATH=src python3 evals/run.py --corpus evals/corpus_big --out /tmp/big_res
```

Golden demo values live in `evals/corpus` (`shop_00_golden_demo`, profit 169.09);
`corpus_big` shops are intentionally varied — no golden assertion here.
