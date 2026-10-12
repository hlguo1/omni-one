# Reviews & Reputation Close — the daily 5-star ritual

> Flagship-pack sibling of **Seller Daily Close** (`src/omni_one/packs/seller_close.py`,
> `docs/DAILY_CLOSE.md`) and **Micro-biz Close** (`src/omni_one/packs/micro_close.py`,
> `docs/MICRO_CLOSE.md`). Same contract — deterministic, cited, offline, $0 —
> retuned for reviews: answer the angry, cherish the happy, fix the pattern.

Every morning the owner gets a **reputation bundle** they can act on in 5 minutes:

```
reputation_close_today/
  close.json    full close dict (audit trail)
  close.csv     KPIs + actions + reviews table (accountant / spreadsheet)
  reviews.csv   one row per review: reviewer, stars, product, channel, theme, citation
  replies.txt   copy-paste review replies (worst-first) + 5-star ask list
```

No CLI, API, or MCP changes were needed for this pack: it is a pure
library (`src/omni_one/packs/reputation_close.py`) proven by
`tests/unit/test_reputation_close.py`. Wiring notes for the future
`omni-one reputation-close` command and `POST /api/v1/reputation/close`
live in §6 below — and only there. (`cli.py`, `client.py`, `api/`,
`mcp_server.py`, `README.md`, `CHANGELOG.md`, `Makefile` are untouched.)

---

## 1. Purpose

Sellers drown in reviews across Etsy / Shopify / Amazon. This pack answers three questions:

| # | Owner question | Pack answer |
|---|----------------|-------------|
| 1 | What is my average, and who will 1-star me if I sleep? | `avg_stars`, `reply_queue` (stars ≤ 3, worst-first, cited drafts) |
| 2 | What keeps going wrong? | `complaint_themes`: `late` / `damaged` / `wrong` keyword counts + `top gripe` in headline |
| 3 | Who loves me that I should activate today? | `ask_list`: up to 3 five-star reviewers to ask for referral / photo review |

## 2. Quick start (python snippet)

```python
from omni_one.packs.reputation_close import (
    DEMO_REVIEWS, build_reputation_close, write_close_bundle,
)

reviews = DEMO_REVIEWS(seed=42)          # deterministic demo: 10 reviews, avg 4.2
close = build_reputation_close(reviews, shop="our shop")
print(close["headline"])
# REPUTATION CLOSE: 4.2★ across 10 review(s) · 2 need reply NOW · top gripe 'late' (3)

write_close_bundle(close, "./reputation_close_today")
# -> close.json + close.csv + reviews.csv + replies.txt
```

Bring your own reviews — same shape, no pipeline required:

```python
mine = [{"reviewer": "Sam", "stars": 2, "text": "Arrived late, box torn",
         "product": "Mug", "channel": "etsy", "citation": "[etsy:reviews#1]"}]
close = build_reputation_close(mine, shop="our shop", date_str="2026-10-11")
```

## 3. Golden numbers (demo `seed=42`, asserted in tests — do not drift)

| KPI | Golden | Where it comes from |
|-----|--------|---------------------|
| total | 10 | `DEMO_REVIEWS(seed=42)` fixed list |
| stars | `[5]×7 + [4,2,1]` | sum 42 / 10 |
| avg_stars | **4.2** | `round(42/10, 2)` |
| count_1_2 (detractors) | 2 | Ivan 2★, Judy 1★ |
| count_5 (promoters) | 7 | Alice…Grace |
| need_reply (≤3★) | 2 | Judy, Ivan (worst-first) |
| complaint_themes | late 3, damaged 1, wrong 1 | `late` in Heidi+Ivan+Judy; `damag` in Ivan; `wrong` in Judy |
| ask_list | Alice, Bob, Cara | first three 5★, max 3 |
| headline | `REPUTATION CLOSE: 4.2★ across 10 review(s) · 2 need reply NOW · top gripe 'late' (3)` | read while coffee brews |
| do_today | reply Judy / fix 'late' / ask Alice | exactly 3 strings |

Reply drafts reuse `seller_close.draft_review_reply` (same claims + citation),
prefixed with `Hi <FirstName>!` so each draft is personal; when that import is
unavailable a local template with the identical contract is used. Every draft
embeds its `[channel:reviews#N]` citation verbatim.

## 4. Bundle layout

| File | Contents |
|------|----------|
| `close.json` | full close dict: `date, shop, seed, headline, kpis, reply_queue[], ask_list[], complaint_themes, do_today[3], reviews[], citations, free, offline` |
| `close.csv` | flagship CSV: title row + `metric,value` KPIs + `do_today` + reviews table (`reviewer,stars,product,channel,theme,citation,snippet`) |
| `reviews.csv` | reviews table only (one row per review, stars + derived `theme`) |
| `replies.txt` | phone screen: numbered `COPY-PASTE DRAFT` blocks (worst-first, each with evidence) + `ASK LIST` |

`reply_queue[]` row: `{reviewer, stars, product, draft, citation}`.
`ask_list[]` row: `{reviewer, stars, product, citation, ask}`.
`theme` values: `late` / `damaged` / `wrong` (joined with `+` when several hit) or `praise`.

## 5. Design rules (why shops trust it — flagship contract)

- **Deterministic, no LLM.** Star math is arithmetic; drafts are templates. A mock
  LLM is never called. Same reviews → same close (minus `date`).
- **Every draft cites `[channel:reviews#N]`.** No phantom reviews, no invented order IDs.
- **Idempotent.** `build_reputation_close(reviews, date_str=X)` twice → identical
  headline/KPIs/queue/asks (tests assert modulo `date`).
- **Private.** Data never leaves the laptop. Works on plane wifi.
- **Free.** Stdlib only (+ optional repo-local `seller_close` import with fallback). `$0 offline`.
- **CSV/TXT shapes mirror `seller_close`** so the same accountant scripts keep working
  (`reorder.csv` becomes `reviews.csv`; `po.txt` becomes the ask list inside `replies.txt`).
- **Empty-safe.** Zero reviews → `avg 0.0`, empty queue, still 3 `do_today` strings, exporters render.

## 6. Wiring note (intended, NOT implemented in this pack)

`reputation_close.py` is library-only today. When the team is ready, the
intended wiring mirrors Seller/Micro Close exactly (do **not** improvise new
shapes — reuse these):

- **CLI:** `omni-one reputation-close [--demo] [--out ./reputation_close_today] [--shop NAME]`
  → builds `DEMO_REVIEWS(seed=42)` or loads a reviews file → `build_reputation_close` →
  `write_close_bundle`, prints the headline. (Seller analog: `omni-one close`.)
- **API:** `POST /api/v1/reputation/close` with `{"demo": true}` or
  `{"reviews": [...]}` payload → returns the close dict (`headline`, `kpis`,
  `reply_queue`, `ask_list`, `complaint_themes`, `do_today`). (Seller analog:
  `POST /api/v1/seller/close`.)
- **SDK:** `OmniOneClient.local().reputation_close(demo=True)`.
- None of the above exists yet — `cli.py`, `client.py`, `api/`, and
  `mcp_server.py` are intentionally untouched by this pack.

## 7. Troubleshooting (2-minute checks)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `avg_stars` looks wrong | custom `stars` are strings, not ints | coerce to int before calling (demo uses ints) |
| `reply_queue` empty but rating fell | all reviews are 4–5★ | check `complaint_themes` — 4★ gripes still count toward `late/damaged/wrong` |
| draft missing first name | `reviewer` field empty | fill `reviewer`; fallback name is `there` (never crashes) |
| `top gripe 'none' (0)` | no late/damaged/wrong keywords | expected when reviews are all praise — `do_today[1]` says keep the checklist tight |
| CSV missing theme | `text` field empty | `theme` falls back to `praise`; fill `text` snippet for real themes |

## 8. File map

| File | Role |
|------|------|
| `src/omni_one/packs/reputation_close.py` | `DEMO_REVIEWS`, `draft_reputation_reply`, `build_reputation_close`, `close_to_csv`, `reviews_to_csv`, `replies_to_txt`, `write_close_bundle` (4 files) |
| `tests/unit/test_reputation_close.py` | golden headline/KPIs, avg math, worst-first queue, named+cited drafts, themes/asks, determinism, 4-file bundle, CSV shapes, empty-safety |
| `docs/REPUTATION_CLOSE.md` | this file: ritual, golden numbers, bundle layout, wiring note |

Upstream (read-only dependency): `src/omni_one/packs/seller_close.py`
(`draft_review_reply` — wording source, with local fallback). Numbers always
come from the review list; words always come from templates; citations always
come from `[channel:reviews#N]`.
