# Micro-biz Close (PACK C) — the taco-stand morning ritual

> Street-shop sibling of **Seller Daily Close** (`docs/DAILY_CLOSE.md`,
> `src/omni_one/packs/seller_close.py`). Same contract — deterministic,
> cited, offline, $0 — retuned for businesses with no website, no POS,
> just a phone and a shoebox of receipts.

Maya runs a taco stand. Every morning she drops yesterday's mess — a
WhatsApp export, a messy `sales_log.csv`, supplier receipt photos, a
notebook page — into one folder and gets a **close bundle** she can act on
in 5 minutes from her phone:

```
close_2024-09-12/
  close.json    full close dict (audit trail)
  close.csv     numbers for the accountant / spreadsheet
  reorder.csv   buy sheet for the market run
  replies.txt   copy-paste WhatsApp drafts (the phone screen)
  vendor.txt    supplier text + buy table (forward on WhatsApp)
```

No CLI, API, or MCP changes were needed for this pack: it is a pure
library (`src/omni_one/packs/micro_close.py`) proven by
`tests/unit/test_micro_close.py`. Wiring notes for the future
`omni-one micro-close` command and `POST /api/v1/micro/close` live at the
bottom of this doc — and only there. (`cli.py`, `client.py`, `api/`,
`mcp_server.py` are untouched by PACK C.)

---

## 1. The 5-minute morning ritual

| Min | Maya does | Pack does | File she reads |
|-----|-----------|-----------|----------------|
| 0–1 | Drops folder: `whatsapp_chat.txt`, `sales_log.csv`, `receipts/`, `notebook.txt` | `ingest_folder()` normalizes everything into pipeline events (no schema) | — |
| 1–2 | Reads **one line**: revenue, who to win back, what to buy, $ at risk | `build_micro_close()` → `headline` | `close.json` / terminal |
| 2–3 | Pastes 2 WhatsApp replies (Maria + Ana), answers inside 2h | `reply_queue[]`: drafts embed `[whatsapp_chat.txt:N]` + 2h promise | `replies.txt` |
| 3–4 | Checks the buy sheet: cilantro + onions TODAY, rest can wait | `reorder_sheet[]`: `reorder_qty / urgency / citation` per ingredient | `reorder.csv` |
| 4–5 | Forwards the supplier text, confirms tomorrow's shift | `vendor_draft` (chat-short, <500 chars) + `money_leaks[]` nudge | `vendor.txt` |

```python
from pathlib import Path
from omni_one.packs._labs.micro_biz import make_demo_folder, ingest_folder
from omni_one.packs.micro_close import build_micro_close, write_close_bundle

events, report = ingest_folder(Path("my_shop_dump"))   # or make_demo_folder(..., seed=42)
close = build_micro_close(events, shop="Maya's Tacos", locale="es")
write_close_bundle(close, Path("close_2024-09-12"))
print(close["headline"])
# Maya's Tacos $241.50 today · 2 customer(s) to win back · 2 buy(s) TODAY · $96.60 at risk
```

---

## 2. Golden numbers (demo `seed=42`, asserted in tests — do not drift)

| KPI | Golden | Where it comes from |
|-----|--------|---------------------|
| revenue | **$241.50** | `sales_log.csv`: 112.00 + 48.00 + 24.00 + 40.00 + 17.50 |
| expenses | $219.50 | receipt totals: 68.50 + 69.50 + 69.50 + **$12.00 notebook quirk** (see §5) |
| net | $22.00 | revenue − expenses |
| orders / items | 5 / 77.0 | 5 sale rows; portions 32+12+8+20+5 |
| avg ticket | **$48.30** | 241.50 ÷ 5 |
| best seller | tacos al pastor ×32 | `sales_log.csv:2` |
| at-risk / happy | 2 / 2 | Maria (`whatsapp_chat.txt:2`), Ana (`:7`) |
| **money at risk** | **$96.60** | invariant: `at_risk × avg_ticket` = 2 × 48.30 |
| stockout_n | 2 | cilantro + onions are `ORDER TODAY` |
| headline | `Maya's Tacos $241.50 today · 2 customer(s) to win back · 2 buy(s) TODAY · $96.60 at risk` | read while coffee brews |
| vendor draft | SYSCO, cilantro/onions ×3, 173 chars | chat-short, cited |

Reorder head row (first of 5, sorted by `days_left`):

| item | on_hand | sold | days_left | reorder_qty | urgency | citation |
|------|---------|------|-----------|-------------|---------|----------|
| cilantro | 1 | 3 | 2.33 | 3 | ORDER TODAY | `[receipt_2024-09-11.txt:4] Cilantro 3 bunch 4.50 each 13.50` |

Golden leaks: `cancelled_sale` $17.50 (`[sales_log.csv:6]`, the no-cilantro
cancellation), `food_cost_high` $219.50 (90.9% of revenue — check portions
before raising prices), `slow_service` (no-show/long-waits note, cited).

---

## 3. WhatsApp vs IG — how Micro Close differs from Seller Close

Seller Close serves online sellers (IG DMs, reviews, email, 5 locales,
14-day warehouse cover, formal PO email). Micro Close serves the street:

| Concern | Seller Close (`seller_close.py`) | Micro Close (`micro_close.py`) |
|---------|----------------------------------|--------------------------------|
| Signal source | `seller_os` briefing + `scenarios` engine | `micro_biz` briefing only (no scenarios dep) |
| Money | GMV / fees / shipping / true profit | cash revenue / expenses / net (no fees, no GMV) |
| Stock model | `inventory.csv` on-hand + 7d velocity | **no inventory file**: receipt mention count → `on_hand = 4 − sold` |
| Cover window | 14 days (warehouse) | **7 days** (fridge, daily market run) |
| Reply channel | IG / DM / review / email | **WhatsApp-first** (IG + voice notes feed the same queue) |
| Reply promise | "within 2 hours" (5 locales) | "within 2 hours" / **"en menos de 2 horas"** (en/es) |
| Supplier doc | `po.txt`: PO email w/ Subject + bullets | **`vendor.txt`**: supplier SMS/WhatsApp, chat-short (<500 chars) |
| Locales | en/es/zh/fr/de | **en/es** (street reality; unknown → en) |
| Bundle file #5 | `po.txt` | `vendor.txt` |
| `do_today` | reply / reorder / leak-or-listing | reply / buy / leak-or-referral (happy regulars bring the line) |

What stays identical (the pack contract, tested): deterministic numbers,
`[file:line]` on every draft and every row, idempotent builds, `free` +
`offline` flags, and CSV/TXT shapes that mirror `seller_close` so the same
accountant scripts keep working (`reorder_qty_7d` renames the 14-day column
for the 7-day cover; `supplier` becomes `vendor`).

---

## 4. Locale note (¡es!)

- `build_micro_close(..., locale="es")` routes drafts through the shared
  `omni_one.i18n.drafts.build_reply("whatsapp", "es", ...)` — the same
  locale modules Seller Close uses — with a `try/except` fallback to a
  local template so drafts **never** crash when i18n is unavailable.
- The vendor text reuses `i18n.build_po` for consistent quantities, then
  compresses the email to chat length (greeting + `- item × qty` bullets +
  first `[file:line]` citation + pay-on-delivery).
- **Guarantee (tested): `es` changes words, never numbers.** KPIs, reorder
  sheet, headline, and leaks are byte-identical across locales; only the
  human sentences switch (`en`: *"Could you send tomorrow?"* /
  `es`: *"¿Me mandas mañana?"*; *"within 2 hours"* /
  *"en menos de 2 horas"*). Unknown locales fall back to `en`.
- Every draft — primary or fallback, either locale — embeds the customer
  first name, the verbatim `[file:line]` citation, a 2-hour promise, a 10%
  remedy, and the shop sign-off. No order numbers are ever invented.

---

## 5. Known quirks (documented, not hidden — tests pin the behavior)

1. **Notebook phantom $12.** `notebook.txt:1` starts *"sept 12 - sold out…"*;
   the receipt parser reads the date fragment as $12.00 of expense. It flows
   into briefing expenses ($219.50), so the close keeps the number. Fixing
   the parser would change golden revenue math — do it deliberately, with
   all three golden sources (code appendix, tests, this doc) updated together.
2. **JPG/TXT double count.** The demo `.jpg` receipt and its `.txt` sidecar
   parse to identical lines, so cilantro/onions count `sold=3`, not 2. The
   close keeps raw counts (deterministic, stable) instead of silently
   deduping — urgency (`ORDER TODAY`) depends on it.
3. **One supplier.** Street shops buy at the market; the sheet uses a single
   guessed vendor (`TIENDA <name>` regex over receipt raws, else `SYSCO`).

---

## 6. Wiring note (intended, NOT implemented in PACK C)

`micro_close.py` is library-only today. When the team is ready, the
intended wiring mirrors Seller Close exactly (do **not** improvise new
shapes — reuse these):

- **CLI:** `omni-one micro-close --folder <dir> --out <dir> [--locale es]`
  → builds `ingest_folder` → `build_micro_close` → `write_close_bundle`,
  prints the headline. (Seller analog: `omni-one close`.)
- **API:** `POST /api/v1/micro/close` with `{"demo": true}` or folder
  payload → returns the close dict (`headline`, `kpis`, `do_today`,
  `reorder_sheet`, `reply_queue`, `money_leaks`, `vendor_draft`).
  (Seller analog: `POST /api/v1/seller/close`.)
- **SDK:** `OmniOneClient.local().micro_close(demo=True)`.
- None of the above exists yet — `cli.py`, `client.py`, `api/`, and
  `mcp_server.py` are intentionally untouched by this pack.

---

## 7. Troubleshooting (2-minute checks)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `headline` shows $0.00 | folder had no `sales_log.csv` rows | add the CSV or a `notebook.txt` sales line, re-ingest |
| `reply_queue` empty but customers complain on IG | chat file not named `*chat*`/`*whatsapp*` | rename to `whatsapp_chat.txt` (ingest keys off the name) |
| reorder sheet says `watch` for everything | fewer than 2 receipt mentions per ingredient | photo more supplier receipts — mentions are the stock signal |
| draft reads "your message" / "tu mensaje" | Spanish slang the issue-keywords miss | harmless: citation + 2h promise still hold; extend `P0_KEYWORDS` if needed |
| `reorder_qty` 0 on a `watch` row | honest: 7-day cover already met | buy only `ORDER TODAY` rows; watch rows are FYI |

---

## 8. File map
| File | Lines | Role |
|------|-------|------|
| `src/omni_one/packs/micro_close.py` | ~900 | `build_micro_close`, `draft_whatsapp_reply`, `draft_vendor_text`, `close_to_csv`, `reorder_to_csv`, `replies_to_txt`, `vendor_to_txt`, `write_close_bundle` (5 files) |
| `tests/unit/test_micro_close.py` | ~400 | 16 tests: golden KPIs/headline, cited+sorted sheet, en/es drafts, money invariant, idempotency, empty-events, 5-file bundle, locale isolation, leaks, fallback |
| `docs/MICRO_CLOSE.md` | this file | ritual, golden numbers, seller-close diff, locale note, wiring note |

Upstream (read-only dependencies): `src/omni_one/packs/_labs/micro_biz.py`
(`make_demo_folder`, `ingest_folder`, `build_briefing` — KPIs, reorder
list, at-risk preview, draft citation) and `src/omni_one/i18n/drafts.py`
(`build_reply`, `build_po` — locale wording). Numbers always come from the
briefing; words always come from i18n; citations always come from the files.
