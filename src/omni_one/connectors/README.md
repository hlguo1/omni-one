# Connectors — channel parsers that feed the Daily Close

`from omni_one.connectors import detect, parse_file, parse_rows`

Every connector returns the SAME canonical event dicts as `seller_os` parsers, so
briefing/scenarios/close work unchanged. Auto-detect: filename + header fingerprints
(BOM/semicolon/currency/refund/date tolerant). Fee heuristics per channel when the
export omits fees (Shopify 2.9%+30c, Etsy 6.5%+20c, Amazon 15%, TikTok 5%+30c,
eBay 13.25%+30c, Woo 2.9%+30c, Stripe 2.9%+30c, PayPal 3.49%+49c, Square 2.9%+30c).

Channels: `shopify etsy amazon tiktok ebay woocommerce stripe paypal square faire`.
Plus `payouts.reconcile(orders, payouts)` — matches payouts to order GMVs, surfaces
fee deltas. 58 fixtures in `tests/fixtures/connectors/`; suites:
`test_connectors_shopify_etsy/amazon_tiktok/ebay_woo/payouts/wave3`.
