# Edge fixtures (wave3) — adversarial-but-real channel exports

| fixture | channel | quirk covered |
|---|---|---|
| edge_klarna_afterpay.csv | stripe | Klarna/APay fee rows mixed with card payouts |
| edge_sepa_payout.csv | stripe | SEPA EUR payout, comma decimals |
| edge_wise_payout.csv | paypal | Wise batch payout, GBP, fee column named 'charges' |
| edge_etsy_pattern.csv | etsy | pattern-SKU headers ('Item Name'/'Quantity'/'Price') |
| edge_digital_sku.csv | shopify | digital goods, zero shipping, 'Delivery: download' |
| edge_giftwrap_fee.csv | amazon | giftwrap fee column adds to fees, FBA flag |
| edge_coupon_code.csv | woocommerce | coupon column reduces GMV, refund row with negative qty |
| edge_bundle_sku.csv | shopify | bundle SKU 'A+B', qty prefix '2 x $15.00' in line total |
| edge_vip_discount.csv | ebay | VIP discount + promoted-listing fee row |
| edge_weekend_sale.csv | tiktok | LIVE badge orders, 5%+30c fees, epoch-ms dates |

Goldens: tests/unit/test_connectors_wave3.py. All 10 auto-detect + parse without raising;
4 carry refunds/disputes, 3 non-USD, 2 semicolon/BOM-adjacent header quirks.
