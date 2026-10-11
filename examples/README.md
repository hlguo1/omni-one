# Examples — copy, run, adapt

## 1) 30-second Seller briefing (no server)

```bash
PYTHONPATH=src python3 examples/quickstart.py
# GMV $274.00 / True Profit $169.09, alerts + actions + CSV
```

## 2) Your shop

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv /tmp/my_shop/ 2>/dev/null || true
cp examples/my_shop_template/*.csv /tmp/my_shop/  # fill these in if empty
PYTHONPATH=src python3 -m omni_one.cli briefing --folder /tmp/my_shop
PYTHONPATH=src python3 -m omni_one.cli export --folder /tmp/my_shop --out briefing.csv
```

Template headers match real Shopify / Etsy / Amazon exports — the parsers auto-detect
(`_norm_header` + fee heuristics + fuzzy product match). See `src/omni_one/packs/seller_parse.py`.

## 3) API + SDK

```bash
PYTHONPATH=src python3 -m omni_one.cli serve --port 5003 &
PYTHONPATH=src python3 examples/sdk_demo.py
```

## 4) Claude / Cursor (MCP)

Add to Claude Desktop config:
```json
{"mcpServers":{"omni-one":{"command":"python3","args":["-m","omni_one.mcp_server"],"cwd":"/path/to/omni-one","env":{"PYTHONPATH":"src"}}}}
```
Then ask: "seller briefing demo" / "run 12 seller scenarios".
