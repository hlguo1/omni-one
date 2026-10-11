# web/assets — static demo bundles (offline-first, $0)

This folder holds small static files the PWAs can load via `file://` or
`http://` with **zero backend** (plane-wifi friendly).

## Files

| File | Purpose | Size budget |
|------|---------|-------------|
| `close-sample.json` | Trimmed Daily Close demo bundle (seed 42). Keeps `kpis`, `reorder_sheet`, `reply_queue`, `money_leaks`, `listing_fixes`, `po_draft`. Base64 chart payloads **dropped** so the file stays tiny and offline-friendly. | < 60KB |
| `README.md` | This file. | — |

## How the sample was built

```bash
# Real demo close bundle, trimmed: drop base64, keep kpis/reorder/replies/po
curl -s -X POST localhost:5003/api/v1/seller/close \
  -H 'Content-Type: application/json' \
  -d '{"demo":true,"seed":42,"shop":"our shop"}' > /tmp/close_full.json
python3 - <<'PY'
import json
c = json.load(open('/tmp/close_full.json'))
keep = {k: c[k] for k in [
  "date","shop","headline","kpis","do_today","reorder_sheet",
  "reply_queue","money_leaks","listing_fixes","po_draft","citations"] if k in c}
# drop any *base64* keys recursively
def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k,v in o.items() if "base64" not in k.lower()}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o
json.dump(strip(keep), open('web/assets/close-sample.json','w'), indent=2)
PY
ls -la web/assets/
```

## Usage

- **Close PWA** (`web/close/index.html`): "Load sample JSON" fetches
  `../assets/close-sample.json` with fallback to inline demo when opened
  via `file://` (fetch is blocked there — the PWA embeds the same bundle).
- **Accountant PWA** (`web/accountant/index.html`): "Load sample JSON"
  and "Load demo CSV" buttons use the same numbers, so both PWAs agree:
  GMV $274.00 · fees $16.71 · ship $24.00 · COGS $64.20 · profit $169.09.
- **Seller page** (`web/seller.html`): Daily Close banner links here for
  accountants who only need the CSV/JSON, not the dashboard.

## Offline notes

- No CDN, no fonts, no framework. All files are static and cacheable.
- `close-sample.json` contains **no base64** (`generated_chart_base64`
  removed) — charts re-render client-side from numbers.
- Every dollar in the sample cites `file:line`
  (e.g. `[inventory.csv:2]`, `[instagram_dm.txt:1]`, `[reviews.csv:3]`).

## Regenerating

Re-run the snippet above after any `seller_close.py` change and keep the
file under 60KB (`wc -c web/assets/close-sample.json`).
