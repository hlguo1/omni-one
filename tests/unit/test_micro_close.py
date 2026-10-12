"""Micro-biz Close golden tests — the street-shop ritual must never regress.

Covers ``omni_one.packs.micro_close`` (PACK C), the street-shop sibling of
Seller Daily Close. Same testing contract as ``test_daily_close.py``:

- golden KPIs measured from the deterministic demo folder (seed=42),
- headline carries the revenue number,
- every reorder row and every reply draft carries a ``[file:line]`` citation,
- reply drafts promise a 2-hour window in both locales,
- money_at_risk == at_risk_count x avg_ticket (exact invariant),
- idempotent builds, empty-events no-crash, 5-file bundle,
- ``es`` locale changes words, never numbers.

Golden demo (seed=42, Maya's Tacos) — measured, do not hand-edit:
  revenue $241.50 = 112.00 + 48.00 + 24.00 + 40.00 + 17.50 (sales_log.csv)
  expenses $219.50 = 12.00 notebook quirk + 68.50 + 69.50 + 69.50 (receipts)
  net $22.00, orders 5, items 77.0, avg ticket $48.30
  best seller "tacos al pastor" x32, worst "tacos" x5
  at-risk customers 2 (Maria line 2, Ana line 7), happy 2
  money at risk $96.60 (= 2 x $48.30)
  reorder head: cilantro, ORDER TODAY, [receipt_2024-09-11.txt:4]
  headline: "Maya's Tacos $241.50 today · 2 customer(s) to win back ·
             2 buy(s) TODAY · $96.60 at risk"
"""
import json
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Golden constants — measured from make_demo_folder(seed=42), see docstring
# ---------------------------------------------------------------------------

GOLDEN_REVENUE = 241.50
GOLDEN_EXPENSES = 219.50
GOLDEN_NET = 22.00
GOLDEN_ORDERS = 5
GOLDEN_ITEMS = 77.0
GOLDEN_AVG_TICKET = 48.30
GOLDEN_BEST_ITEM = "tacos al pastor"
GOLDEN_BEST_QTY = 32.0
GOLDEN_AT_RISK = 2
GOLDEN_MONEY_AT_RISK = 96.60
GOLDEN_HEADLINE = ("Maya's Tacos $241.50 today · 2 customer(s) to win back · "
                   "2 buy(s) TODAY · $96.60 at risk")
GOLDEN_DATE = "2024-09-12"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _demo_events(seed=42):
    """Build demo events exactly like the pack's morning ritual does."""
    from omni_one.packs._labs.micro_biz import make_demo_folder, ingest_folder
    tmp = Path(tempfile.mkdtemp())
    folder = make_demo_folder(tmp / "maya_tacos", seed=seed)
    events, _report = ingest_folder(folder)
    return events


def _demo_close(locale="en"):
    """Build the golden close with a fixed date (fully deterministic)."""
    from omni_one.packs.micro_close import build_micro_close
    return build_micro_close(_demo_events(), date_str=GOLDEN_DATE,
                             locale=locale)


def _assert_file_line_citation(citation, where):
    """Every grounded string cites a real source as [file.ext:line]."""
    assert citation, f"missing citation in {where}"
    assert "[" in citation and ":" in citation, f"bad citation {citation!r} in {where}"
    low = citation.lower()
    assert any(ext in low for ext in (".csv", ".txt", ".jpg", ".md", ".log")), \
        f"citation has no source file in {where}: {citation!r}"


# ---------------------------------------------------------------------------
# 1. Golden KPIs — revenue, orders, best seller, at-risk, money at risk
# ---------------------------------------------------------------------------

def test_micro_golden_kpis():
    """Demo seed=42 produces the measured golden KPIs (no drift allowed)."""
    close = _demo_close()
    k = close["kpis"]
    assert abs(k["revenue"] - GOLDEN_REVENUE) < 0.01, k
    assert abs(k["expenses"] - GOLDEN_EXPENSES) < 0.01, k
    assert abs(k["net"] - GOLDEN_NET) < 0.01, k
    assert k["orders"] == GOLDEN_ORDERS, k
    assert abs(k["items"] - GOLDEN_ITEMS) < 0.01, k
    assert abs(k["avg_ticket"] - GOLDEN_AVG_TICKET) < 0.01, k
    assert k["best_item"]["item"] == GOLDEN_BEST_ITEM, k
    assert abs(k["best_item"]["qty"] - GOLDEN_BEST_QTY) < 0.01, k
    assert k["at_risk"] == GOLDEN_AT_RISK, k
    assert abs(k["money_at_risk"] - GOLDEN_MONEY_AT_RISK) < 0.01, k
    # exactly three actions for the morning ritual
    assert len(close["do_today"]) == 3, close["do_today"]
    # free + offline flags are part of the pack contract
    assert close["free"] is True and close["offline"] is True


def test_micro_headline_contains_revenue_and_risk():
    """Headline is the one line read while coffee brews: exact golden text."""
    close = _demo_close()
    assert close["headline"] == GOLDEN_HEADLINE, close["headline"]
    assert "241.50" in close["headline"]
    assert "Maya's Tacos" in close["headline"]
    assert "2 customer(s)" in close["headline"]
    assert "96.60" in close["headline"]


# ---------------------------------------------------------------------------
# 2. Reorder sheet — citations, urgency order, grounded quantities
# ---------------------------------------------------------------------------

def test_micro_reorder_sheet_cited_and_sorted():
    """First row is cilantro ORDER TODAY with a receipt file:line citation."""
    close = _demo_close()
    sheet = close["reorder_sheet"]
    assert len(sheet) == 5, sheet  # cilantro, onions, limes, tortillas, salsa
    head = sheet[0]
    assert head["item"] == "cilantro", sheet
    assert head["urgency"] == "ORDER TODAY", sheet
    assert head["reorder_qty"] > 0, sheet
    _assert_file_line_citation(head["citation"], "reorder head")
    assert ".txt:" in head["citation"] or ".csv:" in head["citation"], head
    # sorted most-urgent-first: days_left never decreases down the sheet
    days = [r["days_left"] for r in sheet]
    assert days == sorted(days), days
    # every row carries the full street-shop contract
    for row in sheet:
        for key in ("item", "on_hand", "sold", "days_left", "reorder_qty",
                    "urgency", "citation", "vendor"):
            assert key in row, (key, row)
        _assert_file_line_citation(row["citation"], f"reorder {row['item']}")
        assert row["vendor"] == "SYSCO", row
    # stockout_n counts exactly the ORDER TODAY rows
    today_n = sum(1 for r in sheet if r["urgency"] == "ORDER TODAY")
    assert close["kpis"]["stockout_n"] == today_n == 2, sheet


# ---------------------------------------------------------------------------
# 3. Reply queue — WhatsApp drafts with citations + 2h promise (en + es)
# ---------------------------------------------------------------------------

def test_micro_reply_queue_whatsapp_drafts_en():
    """Both at-risk regulars get copy-paste drafts: cited + 2-hour promise."""
    close = _demo_close(locale="en")
    queue = close["reply_queue"]
    assert len(queue) == 2, queue
    names = {q["customer"] for q in queue}
    assert names == {"Maria", "Ana"}, names
    for q in queue:
        assert q["channel"] == "whatsapp", q
        assert q["priority"] == "P0-reply-in-2h", q  # churn risk -> answer fast
        assert len(q["draft"]) > 40, q
        # draft embeds its own citation verbatim (grounded, no phantom text)
        assert q["citation"] in q["draft"], q
        _assert_file_line_citation(q["citation"], f"reply {q['customer']}")
        assert "within 2 hours" in q["draft"], q["draft"]
        assert q["customer"] in q["draft"], q["draft"]  # named, not generic
    # citations point at the real chat lines
    cites = sorted(q["citation"] for q in queue)
    assert any("whatsapp_chat.txt:2" in c for c in cites), cites
    assert any("whatsapp_chat.txt:7" in c for c in cites), cites


def test_micro_reply_queue_es_locale():
    """Spanish drafts promise 'en menos de 2 horas' (not English words)."""
    close = _demo_close(locale="es")
    assert close["locale"] == "es"
    queue = close["reply_queue"]
    assert len(queue) == 2, queue
    for q in queue:
        assert "en menos de 2 horas" in q["draft"], q["draft"]
        assert q["citation"] in q["draft"], q
        _assert_file_line_citation(q["citation"], f"reply-es {q['customer']}")


def test_micro_money_at_risk_is_count_times_avg():
    """Core invariant: money_at_risk == at_risk_count x avg_ticket, exactly."""
    close = _demo_close()
    k = close["kpis"]
    assert k["money_at_risk"] == round(k["at_risk"] * k["avg_ticket"], 2), k
    assert k["avg_ticket"] == round(k["revenue"] / k["orders"], 2), k
    # and the queue length agrees with the at-risk count behind the math
    assert len(close["reply_queue"]) == k["at_risk"] == GOLDEN_AT_RISK


# ---------------------------------------------------------------------------
# 4. Determinism — idempotent builds, empty events never crash
# ---------------------------------------------------------------------------

def test_micro_idempotent():
    """Same events -> same close (headline, KPIs, sheet, drafts, vendor)."""
    from omni_one.packs.micro_close import build_micro_close
    events = _demo_events()
    first = build_micro_close(events, date_str=GOLDEN_DATE)
    second = build_micro_close(events, date_str=GOLDEN_DATE)
    assert first["headline"] == second["headline"]
    assert first["kpis"] == second["kpis"]
    assert first["reorder_sheet"] == second["reorder_sheet"]
    assert first["reply_queue"] == second["reply_queue"]
    assert first["money_leaks"] == second["money_leaks"]
    assert first["vendor_draft"] == second["vendor_draft"]
    assert first["do_today"] == second["do_today"]


def test_micro_empty_events_no_crash():
    """A brand-new shop with zero data still gets a well-formed close."""
    from omni_one.packs.micro_close import build_micro_close
    close = build_micro_close([], date_str=GOLDEN_DATE)
    k = close["kpis"]
    assert k["revenue"] == 0.0 and k["orders"] == 0
    assert k["avg_ticket"] == 0.0 and k["money_at_risk"] == 0.0
    assert k["at_risk"] == 0 and k["stockout_n"] == 0
    assert "0.00" in close["headline"]  # headline still renders money
    assert len(close["do_today"]) == 3  # ritual shape never breaks
    assert close["reply_queue"] == [] and close["money_leaks"] == []
    assert close["reorder_sheet"] == []
    assert isinstance(close["vendor_draft"], str) and close["vendor_draft"]
    # exporters survive empty closes too
    from omni_one.packs.micro_close import (close_to_csv, reorder_to_csv,
                                            replies_to_txt)
    assert "MICRO CLOSE" in close_to_csv(close)
    assert "item" in reorder_to_csv(close)
    assert "VENDOR DRAFT" in replies_to_txt(close)


# ---------------------------------------------------------------------------
# 5. Bundle — exactly the 5 files, byte-stable, JSON round-trips
# ---------------------------------------------------------------------------

def test_micro_bundle_five_files():
    """write_close_bundle writes close.json/csv + reorder.csv + replies/vendor."""
    from omni_one.packs.micro_close import (build_micro_close,
                                            write_close_bundle)
    close = build_micro_close(_demo_events(), date_str=GOLDEN_DATE)
    out = Path(tempfile.mkdtemp()) / "close_2024-09-12"
    paths = write_close_bundle(close, out)
    assert sorted(paths) == ["close.csv", "close.json", "reorder.csv",
                             "replies.txt", "vendor.txt"], paths
    for name, path in paths.items():
        assert Path(path).exists() and Path(path).stat().st_size > 0, name
    # JSON round-trips the headline + KPIs
    loaded = json.loads((out / "close.json").read_text(encoding="utf-8"))
    assert loaded["headline"] == GOLDEN_HEADLINE
    assert abs(loaded["kpis"]["money_at_risk"] - GOLDEN_MONEY_AT_RISK) < 0.01
    # CSVs carry the machine-readable shapes
    assert "money_at_risk" in (out / "close.csv").read_text(encoding="utf-8")
    reorder_csv = (out / "reorder.csv").read_text(encoding="utf-8")
    assert "reorder_qty_7d" in reorder_csv and "cilantro" in reorder_csv
    # replies.txt is the phone screen: drafts + vendor text
    replies = (out / "replies.txt").read_text(encoding="utf-8")
    assert "COPY-PASTE DRAFT" in replies and "VENDOR DRAFT" in replies
    assert "within 2 hours" in replies
    vendor = (out / "vendor.txt").read_text(encoding="utf-8")
    assert "SYSCO" in vendor and "cilantro" in vendor


def test_micro_export_shapes_mirror_seller_close():
    """CSV/TXT shapes mirror seller_close so the same tooling keeps working."""
    from omni_one.packs.micro_close import (close_to_csv, reorder_to_csv,
                                            replies_to_txt)
    close = _demo_close()
    table = close_to_csv(close)
    assert table.splitlines()[0].startswith("MICRO CLOSE")
    assert "metric,value" in table.replace(" ", "") or "metric" in table
    assert "do_today" in table and "reorder_qty_7d" in table
    assert "cancelled_sale" in table  # leaks table present with golden leak
    sheet = reorder_to_csv(close)
    header = sheet.splitlines()[0]
    for col in ("item", "on_hand", "sold", "daily_velocity", "days_left",
                "reorder_qty_7d", "vendor", "urgency", "citation"):
        assert col in header, header
    assert len(sheet.splitlines()) == 1 + len(close["reorder_sheet"])
    txt = replies_to_txt(close)
    assert txt.splitlines()[0].startswith("MICRO CLOSE")
    assert "96.60" in txt  # money at risk on the phone screen


# ---------------------------------------------------------------------------
# 6. Locale isolation + vendor draft + leaks grounding
# ---------------------------------------------------------------------------

def test_micro_es_locale_changes_drafts_not_numbers():
    """es<>en: same KPIs/sheet/numbers, different human words only."""
    en = _demo_close(locale="en")
    es = _demo_close(locale="es")
    assert en["kpis"] == es["kpis"]
    assert en["reorder_sheet"] == es["reorder_sheet"]
    assert en["headline"] == es["headline"]
    assert en["money_leaks"] == es["money_leaks"]
    en_drafts = [q["draft"] for q in en["reply_queue"]]
    es_drafts = [q["draft"] for q in es["reply_queue"]]
    assert en_drafts != es_drafts  # words changed ...
    assert [q["citation"] for q in en["reply_queue"]] == \
           [q["citation"] for q in es["reply_queue"]]  # ... evidence didn't
    assert en["vendor_draft"] != es["vendor_draft"]
    assert "Could you send tomorrow" in en["vendor_draft"]
    assert "mandas mañana" in es["vendor_draft"]
    # unknown locales fall back to English, never crash, never change numbers
    from omni_one.packs.micro_close import build_micro_close
    weird = build_micro_close(_demo_events(), date_str=GOLDEN_DATE,
                              locale="xx")
    assert weird["locale"] == "en"
    assert weird["kpis"] == en["kpis"]


def test_micro_vendor_draft_chat_short_and_grounded():
    """Vendor text is a chat message (<500 chars), not a PO email."""
    close = _demo_close()
    draft = close["vendor_draft"]
    assert len(draft) < 500, draft
    assert "SYSCO" in draft
    assert "cilantro" in draft  # top buy line present with real quantity
    assert "x 3" in draft, draft  # ceil(0.4286*7 - 1) = 3, not a guess
    assert "Subject:" not in draft  # chat-short: no email boilerplate
    _assert_file_line_citation(draft, "vendor draft")


def test_micro_money_leaks_grounded():
    """Golden leaks: cancelled $17.50, food-cost 90.9%, slow service cited."""
    close = _demo_close()
    leaks = {l["leak"]: l for l in close["money_leaks"]}
    assert set(leaks) == {"cancelled_sale", "food_cost_high",
                          "slow_service"}, leaks
    cancelled = leaks["cancelled_sale"]
    assert cancelled["amount_usd"] == 17.50, cancelled
    _assert_file_line_citation(cancelled["evidence"], "cancelled leak")
    assert "sales_log.csv:6" in cancelled["evidence"], cancelled
    food = leaks["food_cost_high"]
    assert food["amount_usd"] == GOLDEN_EXPENSES, food
    assert "90.9%" in food["note"], food
    slow = leaks["slow_service"]
    _assert_file_line_citation(slow["evidence"], "slow-service leak")


def test_micro_custom_shop_and_date_flow_everywhere():
    """Shop/date params reach headline, drafts, vendor text, and bundle."""
    from omni_one.packs.micro_close import (build_micro_close,
                                            write_close_bundle)
    close = build_micro_close(_demo_events(), date_str="2024-09-13",
                              shop="Tacos El Faro", locale="es")
    assert close["date"] == "2024-09-13"
    assert close["shop"] == "Tacos El Faro"
    assert close["headline"].startswith("Tacos El Faro $241.50"), \
        close["headline"]
    # numbers identical to the golden close — only words moved
    golden = _demo_close(locale="es")
    assert close["kpis"] == golden["kpis"]
    assert close["reorder_sheet"] == golden["reorder_sheet"]
    # ... but every human surface carries the new shop name
    assert "Tacos El Faro" in close["reply_queue"][0]["draft"]
    assert "Tacos El Faro" in close["vendor_draft"]
    assert "SYSCO" in close["do_today"][1]  # buy line names vendor, not shop
    out = Path(tempfile.mkdtemp())
    write_close_bundle(close, out)
    assert "2024-09-13" in (out / "replies.txt").read_text(encoding="utf-8")


def test_micro_briefing_passthrough_matches_rebuild():
    """A precomputed briefing is reused verbatim (no double pipeline work)."""
    from omni_one.packs._labs.micro_biz import build_briefing
    from omni_one.packs.micro_close import build_micro_close
    events = _demo_events()
    briefing = build_briefing(events)
    via_arg = build_micro_close(events, briefing=briefing,
                                date_str=GOLDEN_DATE)
    rebuilt = build_micro_close(events, date_str=GOLDEN_DATE)
    assert via_arg["headline"] == rebuilt["headline"] == GOLDEN_HEADLINE
    assert via_arg["kpis"] == rebuilt["kpis"]
    assert via_arg["reorder_sheet"] == rebuilt["reorder_sheet"]
    assert via_arg["reply_queue"] == rebuilt["reply_queue"]
    # briefing KPIs flow through untouched (close never recomputes revenue)
    assert via_arg["kpis"]["revenue"] == round(briefing["kpis"]["revenue"], 2)
    assert via_arg["kpis"]["at_risk"] == briefing["kpis"]["at_risk_customers"]


def test_micro_draft_helper_falls_back_without_i18n():
    """draft_whatsapp_reply keeps its contract even if i18n import fails."""
    from omni_one.packs import micro_close as mc
    cite = "[whatsapp_chat.txt:2] Maria: hola"
    en = mc._local_whatsapp_reply("Maria", "la espera fue larga", cite,
                                  "Maya's Tacos", "en")
    es = mc._local_whatsapp_reply("Maria", "la espera fue larga", cite,
                                  "Maya's Tacos", "es")
    for draft, promise in ((en, "within 2 hours"), (es, "en menos de 2 horas")):
        assert "Maria" in draft and cite in draft, draft
        assert promise in draft, draft
        assert "Maya's Tacos" in draft, draft
    # public helper never raises on garbage input (empty shop/locale/None)
    fallback = mc.draft_whatsapp_reply("", "", "", "", locale="xx")
    assert isinstance(fallback, str) and len(fallback) > 40


# ---------------------------------------------------------------------------
# End of micro-close tests. When adding cases, keep the golden constants
# above in sync with docs/MICRO_CLOSE.md and the appendix at the bottom of
# src/omni_one/packs/micro_close.py — all three state the same numbers.
# ---------------------------------------------------------------------------
