# Quickstart (60 seconds, $0)

```bash
git clone https://github.com/garyguo123456789/omni-one.git && cd omni-one
pip install -r requirements-seller.txt && pip install -e .
omni-one doctor                                        # deps + pipeline smoke
omni-one close --demo --out ./close_today             # THE ritual: profit + reorders + replies
cat ./close_today/replies.txt                         # copy-paste a draft, send the PO
```

Your shop:

```bash
mkdir -p /tmp/my_shop
cp ~/Downloads/*orders*.csv ~/Downloads/inventory.csv /tmp/my_shop/
cp examples/my_shop_template/*.csv /tmp/my_shop/   # fill blanks if needed
omni-one close --folder /tmp/my_shop --out ./close_2026-10-11 --shop "Maya's Handmade"
```

Server + SDK + bot:

```bash
omni-one serve --port 5003 &                            # docs at /api/docs
PYTHONPATH=src python3 examples/sdk_demo.py
PYTHONPATH=src python3 examples/daily_close_demo.py
```

Claude/Cursor MCP: `python3 -m omni_one.mcp_server` (stdio), tools:
`seller_close`, `seller_briefing`, `seller_scenarios`, `seller_operations`,
`pipeline_analyze`, `vision_analyze`.
