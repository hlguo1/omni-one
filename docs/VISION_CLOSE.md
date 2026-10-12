# Vision Close — PACK B (photo → close, $0 offline)

**Deterministic, offline, $0.** Snap a supplier receipt / chart photo, get
OCR text, per-line amounts, COGS hits, a top-number chart, trimmed pipeline
evidence, a rule-based verdict, 3 do-today actions, and `filename:line`
citations — plus a 3-file bundle (`close.json` + `lines.csv` + `ocr.txt`).

Code: `src/omni_one/packs/vision_close.py` (610 lines).
Tests: `tests/unit/test_vision_close.py` (15 tests, green).

```bash
python3 -m compileall -q src/omni_one/packs/vision_close.py
PYTHONPATH=src python3 -m pytest tests/unit/test_vision_close.py -q  # 15 passed
```

## 1. Pipeline (bytes → OCR → numbers → COGS → evidence → verdict)

```
image_bytes (+ filename, lang)
  → core/vision.analyze_photo (Tesseract OCR + OpenCV chart heuristic
     + Matplotlib re-gen + MultiLayerDataPipeline mock analysis, $0)
  → ocr.text truncated to 2000 chars, split into 1-indexed lines
  → numbers[]  {line_no, text, amount} via _money_last per line
     (LAST number wins: "50 x 4.00 200.00" → 200.00, never the 50)
  → cogs_lines[]  {line_no, text, qty, unit, total, citation}
     via extract_unit_qty per line ("<qty> x <unit> <total>" hits)
  → chart{labels, values}  top numbers by amount desc, cap 6, deduped
     (labels = de-numbered line prefixes, max 18 chars)
  → evidence[]  pipeline steps trimmed to 200 chars each, max 6 steps;
     blobs ≥120 chars → [omitted]; full image payloads never stored/logged
  → verdict{label, rule, reason}  (rule table in §2)
  → do_today[3]  deterministic actions per verdict
  → citations[]  "<filename>:<line_no>" per numbers hit
  → totals  {lines_with_amounts, cogs_hits, sum/max/min}
```

Money parsing reuses the Seller OS shared parsers (`packs/seller_parse.py`:
`_money_last`, `extract_unit_qty`) with a `try/except` import and a 10-line
local regex fallback, so Vision Close works even if `seller_parse` is absent.
Fallback semantics match: dates stripped, last number wins.

Entry points:

```python
from omni_one.packs.vision_close import (
    build_vision_close,   # (image_bytes, filename="upload.png", lang="eng") -> dict
    make_demo_image,      # (kind="receipt") -> PNG bytes (PIL only)
    close_to_csv,         # (close) -> "line_no,text,amount" CSV text
    write_close_bundle,   # (close, out_dir) -> 3 paths
)
```

`build_vision_close` never raises on garbage: `b""`, `b"not-an-image"`,
truncated headers, and null bytes all degrade to `verdict=unreadable`
(see §2). Cost is always `$0.0` (`meta.cost_usd`, `cost_usd`, `free: true`,
`offline: true`).

## 2. Verdict rules (deterministic, evaluated in order)

| # | label | rule | condition |
|---|-------|------|-----------|
| 1 | `unreadable` | `no_text_no_numbers` | OCR blank AND numbers empty AND chart values empty (garbage/empty land here, no raise) |
| 2 | `invoice-like` | `invoice_signals` | numbers ≥ 1 AND invoice_score ≥ 2/4 (`$` present; qty `Nx` pattern; invoice keyword; numbers ≥ 2) |
| 3 | `chart-like` | `chart_or_many_numbers` | OpenCV `is_chart` OR numbers ≥ 3 (and not invoice-like) |
| 4 | `photo` | `has_text_no_numbers` | OCR non-empty but no parseable amounts |
| 5 | `unreadable` | `empty_fallback` | anything else (unreachable safety net) |

Invoice keywords: total, receipt, invoice, subtotal, tax, payment, amount,
due, balance, shipping, change, tender, store, market, thank (case-insensitive).

`do_today[3]` per verdict:

- **invoice-like** — verify receipt total vs line amounts; reconcile COGS
  from unit-qty hits into today's close; log payment + flag qty×unit mismatches.
- **chart-like** — transcribe top-3 bars; re-shoot straight-on; note >20% swings.
- **photo** — retake closer (no readable `$`); type 2–3 amounts manually; re-run.
- **unreadable** — retake (fill frame, steady, flash off); type amounts manually;
  install Tesseract and re-run (fallback stays $0 offline).

## 3. Tesseract install note + graceful fallback

OCR uses local Tesseract via `pytesseract` (free, offline). Chart detection
uses OpenCV; chart re-generation uses Matplotlib. All are **optional**:

```bash
# macOS (free)
brew install tesseract && pip install pytesseract opencv-python
# Debian/Ubuntu (free)
sudo apt-get install tesseract-ocr && pip install pytesseract opencv-python
```

Fallback behavior (verified by tests):

- Tesseract missing → `ocr.text == ""`, `meta.engine == "none"`, parsers run
  on empty text → `verdict=unreadable`, still 3 `do_today` actions, `$0`.
- Corrupt/empty bytes → same `unreadable` path, **never raises** (the
  `analyze_photo` call is wrapped in `try/except`; `b""` short-circuits
  before touching vision at all).
- `lang` (default `"eng"`) is recorded in `meta` and forwarded to Tesseract
  when available (retry path for non-`eng` requests).
- `ocr.txt` is never empty: when OCR yields nothing, the bundle writer emits
  a fallback hint naming the file, the free install commands, and `$0 offline`.

Privacy: any string that looks like an encoded payload (≥120-char blob token,
or ≥400-char compacted body) is replaced with `[omitted]` before it reaches
`evidence[]`, `close.json`, or logs. `close.json` carries no payload-keyed
fields (the preview step records only `[omitted]` / "no preview generated").

## 4. Intended wiring (NOT implemented — do not touch cli.py/client.py/api/)

Vision Close ships as a pure pack (no CLI/API changes in this drop). The
intended wiring for a follow-up:

```bash
# CLI (proposed — not implemented here)
omni-one vision-close --image receipt.png --out close_today/ --lang eng
# expected: writes close_today/{close.json,lines.csv,ocr.txt}, prints verdict + totals
```

```bash
# API (proposed — not implemented here)
curl -X POST http://localhost:5003/api/v1/vision/close \
  -F file=@receipt.png -F lang=eng | jq '{verdict, totals, do_today}'
# expected: {"verdict": {"label": "invoice-like", ...}, "totals": {...}} cost $0
```

Contract the endpoint should honor: multipart `file` (+ optional `lang`),
JSON close object as defined here, HTTP 200 with `verdict=unreadable` (never
4xx) for undecodable uploads, and zero payload bytes echoed back.

## 5. Golden demo numbers (actuals from THIS fixture)

Fixture: `make_demo_image("receipt")` — white 800×400 PNG (~22 KB),
PIL only (no Tesseract needed to GENERATE), 5 dark text rows + 2 bars:

```
ACME MARKET - RECEIPT
Tote Bag Canvas 50 x 4.00 200.00
Shipping 1 x 15.00 15.00
Tax $12.50
Total $227.50
```

Observed close (`filename="receipt_demo.png"`, Tesseract present):

```
verdict: invoice-like / rule invoice_signals
reason: invoice_score=4/4 signals=money_symbol,qty_pattern,invoice_keyword,multi_numbers numbers=4
numbers:
  line 2 "Tote Bag Canvas 50 x 4.00 200.00" → 200.00
  line 3 "Shipping 1 x 15.00 15.00"         → 15.00
  line 4 "Tax $12.50"                       → 12.50
  line 5 "Total $227.50"                    → 227.50
cogs_lines: 2 hits — (50.0 × $4.00 = $200.00) [receipt_demo.png:2],
                       (1.0 × $15.00 = $15.00) [receipt_demo.png:3]
chart: labels [Total, Tote Bag Canvas, Shipping, Tax]
       values [227.5, 200.0, 15.0, 12.5]  (source top_numbers, top_n 4)
totals: lines_with_amounts 4, cogs_hits 2, sum 455.00, max 227.50, min 12.50
citations: [receipt_demo.png:2, receipt_demo.png:3,
            receipt_demo.png:4, receipt_demo.png:5]
do_today:
  1. "Verify receipt total $227.50 against 4 line amounts, then file photo by date."
  2. "Reconcile COGS from unit-qty lines (2 hits, e.g. qty 50 x $4.00) into today's close."
  3. "Log payment + snap a backup photo; flag any line whose total != qty x unit."
evidence (6 steps): ocr (tesseract, 108 chars, $0 local) →
  chart_detect (is_chart=False, "horiz=16 vert=0 lines via Hough") →
  chart_data (source ocr_numbers, 4 bars) → chart_preview [omitted] →
  2× pipeline citations (Layer 1 validated-record hashes, trimmed).
```

Negative controls: `b"not-an-image"` → `unreadable/no_text_no_numbers`,
numbers `[]`; `b""` → same. Both idempotent (rebuild returns identical
verdict + numbers + chart + sha prefix).

## 6. Verify + bundle layout

```bash
PYTHONPATH=src python3 -c "
from omni_one.packs.vision_close import make_demo_image, build_vision_close, write_close_bundle
close = build_vision_close(make_demo_image('receipt'), filename='receipt_demo.png')
print(close['verdict'], close['totals'])
print(write_close_bundle(close, 'close_today/'))
"
# close_today/close.json   full close (pretty-printed, payload-free)
# close_today/lines.csv    line_no,text,amount (header + 4 rows for the demo)
# close_today/ocr.txt      verbatim OCR text (demo: 5 receipt lines with $)
```

`lines.csv` for the demo:

```
line_no,text,amount
2,Tote Bag Canvas 50 x 4.00 200.00,200.00
3,Shipping 1 x 15.00 15.00,15.00
4,Tax $12.50,12.50
5,Total $227.50,227.50
```
