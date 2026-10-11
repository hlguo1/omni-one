# Omni-One · Daily Close PWA (WORKSTREAM B)

Dependency-free (no npm build step) PWA a shop owner opens daily.
5-minute morning ritual: profit → reorder+PO → replies → leaks → print.

Files (all under `web/close/`):

| File | Purpose |
|---|---|
| `index.html` | Shell: headline KPIs, 6 tabs, dropzone, inline CSS, SW registration |
| `app.js` | Vanilla logic: API client, store, renderers, cache, copy, CSV |
| `sw.js` | Service worker `CLOSE_V1`, cache-first offline shell |
| `manifest.webmanifest` | PWA manifest (standalone, icon.svg) |
| `icon.svg` | Inline SVG shop icon |
| `README.md` | This file |
| `tests_smoke.py` | Stdlib-only smoke checks (no network) |

## 1. How to open

### A. `file://` (shell preview, no API)

```bash
open web/close/index.html
# or: python3 -c "import webbrowser; webbrowser.open('web/close/index.html')"
```

Works: layout, tabs, theme, cached close (if any), demo hint.
Fails gracefully: API calls show error banner + “Load demo instead”.
Service workers do NOT run on `file://` — that is expected.

### B. Served static only (shell + offline, no API)

```bash
python3 -m http.server 8080 -d web/close
# open http://localhost:8080/index.html
```

SW `sw.js` now registers; shell works with WiFi off after first load.

### C. Served via API (full: Demo → CSV → Print)

```bash
# from repo root — serves API + static (see Makefile / docker-compose)
python3 -m uvicorn omni_one.api.app:app --port 5003
# then open http://localhost:5003/close/  (if statically mounted)
# or serve close/ separately and point API base at :5003:
python3 -m http.server 8080 -d web/close
# open http://localhost:8080/index.html?api=http://localhost:5003
```

In-app: set **API base URL** box (persisted to `localStorage close_api_base`),
or use `?api=http://localhost:5003`. Empty = same-origin.

## 2. Daily flow (owner, 5 min)

1. Open PWA → **▶ Demo close** (or `d`). Reads shop + seed inputs.
2. Read **Today**: 3 bullets (reply → reorder → leak). Headline KPIs on top.
3. **Replies**: copy P0 drafts (each cites `file:line`), paste to DM/reviews.
4. **Reorder+PO**: copy PO `<pre>`, email supplier.
5. **Leaks/Listings**: note one fix.
6. **⬇ CSV** (or `c`) → send `close.csv` to accountant.
7. **🖨 Print** (or `p`) → Save as PDF / fridge printout.

Folder mode (machine that HAS the files):

```bash
curl -X POST http://localhost:5003/api/v1/seller/close \
  -H 'Content-Type: application/json' \
  -d '{"folder": "/tmp/my_shop", "shop": "our shop"}'

curl 'http://localhost:5003/api/v1/seller/close.csv?demo=true&seed=42&shop=our%20shop' -o close.csv

omni-one close --folder /tmp/my_shop --out ./close_2026-10-11
# → close.json + close.csv + reorder.csv + replies.txt + po.txt
```

Browser drops log file NAMES only (cannot send server paths) + show this hint.
Citations (`[shopify_orders.csv:5]` etc.) come from the server bundle.

## 3. API contract

### `POST /api/v1/seller/close`

Request (JSON):

```json
{ "demo": true, "seed": 42, "shop": "our shop" }
{ "folder": "/tmp/my_shop", "shop": "Sunny Ceramics", "seed": 42 }
```

Response (`close.json` bundle):

```json
{
  "date": "2026-10-11",
  "shop": "our shop",
  "headline": "Profit $.. (..%) · $.. at risk in N angry messages · M reorder(s) TODAY · K leak(s)",
  "kpis": {
    "gmv": 0, "fees": 0, "shipping": 0, "net": 0, "cogs": 0,
    "true_profit": 0, "margin_pct": 0, "orders": 0, "aov": 0,
    "best_seller": {"product": "…", "qty": 0},
    "money_at_risk_usd": 0
  },
  "do_today": ["Reply …", "Reorder …", "Plug leak …"],
  "reorder_sheet": [
    {"product": "…", "on_hand": 0, "sold_7d": 0, "daily_velocity": 0,
     "days_left": 0, "reorder_qty": 0, "cover_days": 14,
     "supplier": "…", "urgency": "ORDER TODAY|this week|watch",
     "citation": "[inventory.csv:2]"}
  ],
  "dead_stock_note": [{"title": "…", "evidence": "[…]"}],
  "reply_queue": [
    {"channel": "dm|review|scenario", "customer": "…", "summary": "…",
     "draft": "…", "citation": "[instagram_dm.txt:3]", "priority": "P0-reply-in-2h|P1-today"}
  ],
  "money_leaks": [
    {"leak": "fee_creep|shipping_loss|margin_dip", "amount_usd": 0,
     "note": "…", "evidence": "[…]"}
  ],
  "listing_fixes": [{"fix": "LISTING_GAP|…", "title": "…", "evidence": "[…]"}],
  "po_draft": "Subject: Reorder request — …",
  "ingest_report": {"folder": "…", "files_seen": 0, "files_ingested": 0,
    "by_source": {"order": 0}, "errors": [], "events": 0},
  "free": true, "offline": true
}
```

Errors: `400` bad folder, `500` server. App shows banner + cached fallback.

### `GET /api/v1/seller/close.csv?demo=true&seed=42&shop=our%20shop`

Returns `text/csv`, `Content-Disposition: attachment; filename=close.csv`.
Sections: `DAILY CLOSE`, `metric,value`, `do_today`, reorder rows, leaks.
App falls back to client-built CSV from cache when offline.

Backend: `src/omni_one/api/ops.py` (`seller_close`, `seller_close_csv`),
logic `src/omni_one/packs/seller_close.py` (`build_daily_close`, `close_to_csv`).

## 4. Tabs

| Tab | Key | Content |
|---|---|---|
| Today | `1` | 3 bullets + top replies/reorders/leak |
| Reorder+PO | `2` | Sortable table (urgency badges) + PO `<pre>` + dead stock |
| Replies | `3` | Cards with ⧉ Copy + `file:line` citation, P0 first |
| Leaks | `4` | Dollar-amount leaks + evidence |
| Listings | `5` | LISTING_GAP / REVIEW_CRISIS / PRICE_MISMATCH / WORST_SELLER |
| Files | `6` | `ingest_report` JSON + drop log + `curl` + raw `close.json` |

## 5. Keyboard shortcuts

| Key | Action |
|---|---|
| `1`…`6` | Today / Reorder+PO / Replies / Leaks / Listings / Files |
| `d` | Demo close (`POST …/close {demo:true}`) |
| `c` | Download CSV (`GET …/close.csv`) |
| `p` | Print / Save as PDF |
| `/` | Focus search in current tab |
| `←` `→` | Prev / next tab (when a tab is focused) |
| `Home` / `End` | First / last tab |
| `Esc` | Dismiss toast / blur |

## 6. Print flow

1. Open **Today** (or any tab — all panels print; tabs/buttons hide).
2. Press **🖨 Print** or `p` → system dialog → *Save as PDF*.
3. `@media print` in `index.html` hides `.no-print` (buttons, tabs, search,
   dropzone), keeps tables, reply drafts, PO `<pre>`, citations.
4. Print-only header appears (“Daily Close — printout”).

## 7. Offline + cache

- No CDN, no fonts, no framework — WiFi-off safe.
- `sw.js` (`CLOSE_V1`, cache-first) precaches
  `./ ./index.html ./app.js ./manifest.webmanifest ./icon.svg`,
  purges old `CLOSE_*`, serves cached shell on fetch failure.
- Last close cached in `localStorage close_last` (24h TTL, key
  `{savedAt, shop, seed, close}`). Offline banner shows when
  `navigator.onLine === false`; stale cache renders instead of blank.
- `Clear cache` button wipes `close_last`.

## 8. Search / filter / sort

- Today: one search across replies+reorders+leaks.
- Reorder: search (product/supplier/citation) + urgency filter
  (`all|ORDER TODAY|this week|watch`) + sort select + click-to-sort headers
  (`product|on_hand|sold_7d|days_left|reorder_qty`).
- Replies: search + priority (`P0-reply-in-2h|P1-today`) + channel (`dm|review|scenario`).
- Leaks: search + kind (`fee_creep|shipping_loss|margin_dip`).
- Listings: search.
- All idempotent: re-render wipes containers first; same data → same DOM.

## 9. Copy / download fallbacks

- `copyText()`: `navigator.clipboard` → `textarea+execCommand` → `prompt()`.
  Never rejects; toasts ✓/hint.
- `downloadCSV()`: API CSV → client-built CSV from cache → navigate to URL.
- `saveTextFile()`: `Blob+a[download]` → new-tab `<pre>` fallback.
- PO / replies / reorder-CSV / JSON each have copy + download buttons.

## 10. Verify

```bash
python3 web/close/tests_smoke.py
python3 -m compileall -q web/close/tests_smoke.py
```

Stdlib only, no network. Checks: files exist, `index.html` references
`app.js`/`sw.js`/`manifest`, `app.js` defines
`loadDemo loadFolderHint renderClose copyText downloadCSV`,
no external CDN `<script src="http…">`, size report (`wc -l`).

## 11. Citations

Every number cites `file:line`: `[shopify_orders.csv:5]`,
`[inventory.csv:2]`, `[reviews.csv:3]`, `[instagram_dm.txt:1]`,
`[seller_close.py:build_daily_close]`, `[app.js:renderClose]`.
Raw bundle in Files tab is the audit trail.

## 12. Constraints

- ONLY `web/close/` was created/edited. `web/seller.html` untouched.
- No build step. Open directly or via any static server.

## Draft language
Select EN/ES/ZH/FR/DE next to the seed. Sent as `locale` in POST /api/v1/seller/close. Numbers and citations never change — only reply + PO drafts switch language (see src/omni_one/i18n/).
