"""Reviews & Reputation Close golden tests — the daily 5-star ritual.

Covers ``omni_one.packs.reputation_close`` (flagship pack, sibling of
seller_close / micro_close). Same testing contract:

- golden headline/KPIs from the deterministic demo (seed=42),
- avg math verified by hand, reply queue worst-first, drafts cited+named,
- idempotent builds modulo date, empty input never crashes,
- 4-file bundle, free flag, CSV shapes carry stars+theme.

Golden demo (seed=42) — measured, do not hand-edit:
  stars [5]*7 + [4,2,1] = 42 / 10 = 4.2 avg
  count_1_2 = 2 (Ivan 2*, Judy 1*), count_5 = 7, need_reply = 2
  themes: late 3, damaged 1, wrong 1; top gripe 'late' (3)
  headline: "REPUTATION CLOSE: 4.2\u2605 across 10 review(s) \u00b7 2 need reply NOW \u00b7 top gripe 'late' (3)"
"""
import json
import tempfile
from pathlib import Path

GOLDEN_HEADLINE = "REPUTATION CLOSE: 4.2\u2605 across 10 review(s) \u00b7 2 need reply NOW \u00b7 top gripe 'late' (3)"
GOLDEN_AVG = 4.2
GOLDEN_TOTAL = 10
GOLDEN_COUNT_1_2 = 2
GOLDEN_COUNT_5 = 7
GOLDEN_NEED_REPLY = 2
GOLDEN_THEMES = {"late": 3, "damaged": 1, "wrong": 1}
GOLDEN_DATE = "2026-10-11"


def _demo_close(**kw):
    from omni_one.packs.reputation_close import build_reputation_close
    base = {"date_str": GOLDEN_DATE}
    base.update(kw)
    return build_reputation_close(**base)


def test_golden_headline():
    close = _demo_close()
    assert close["headline"] == GOLDEN_HEADLINE, close["headline"]


def test_golden_kpis():
    close = _demo_close()
    k = close["kpis"]
    assert k["avg_stars"] == GOLDEN_AVG, k
    assert k["total"] == GOLDEN_TOTAL, k
    assert k["count_1_2"] == GOLDEN_COUNT_1_2, k
    assert k["count_5"] == GOLDEN_COUNT_5, k
    assert k["need_reply"] == GOLDEN_NEED_REPLY, k
    assert k["top_theme"] == "late" and k["top_theme_n"] == 3, k


def test_avg_math_by_hand():
    from omni_one.packs.reputation_close import DEMO_REVIEWS
    reviews = DEMO_REVIEWS(seed=42)
    assert len(reviews) == 10, len(reviews)
    assert sum(r["stars"] for r in reviews) == 42, reviews
    assert round(sum(r["stars"] for r in reviews) / len(reviews), 2) == GOLDEN_AVG
    close = _demo_close()
    assert close["kpis"]["avg_stars"] == round(42 / 10, 2)


def test_reply_queue_only_le3_sorted_asc():
    close = _demo_close()
    q = close["reply_queue"]
    assert len(q) == GOLDEN_NEED_REPLY, q
    assert all(item["stars"] <= 3 for item in q), q
    assert [item["stars"] for item in q] == sorted(item["stars"] for item in q), q
    assert [item["reviewer"] for item in q] == ["Judy", "Ivan"], q


def test_drafts_contain_first_name_and_citation():
    close = _demo_close()
    for item in close["reply_queue"]:
        first = item["reviewer"].split()[0]
        assert first in item["draft"], item
        assert item["citation"] in item["draft"], item
        assert len(item["draft"]) > 40, item


def test_free_seed_and_citations_flags():
    close = _demo_close()
    assert close["free"] is True
    assert close["seed"] == 42
    assert "reviews" in close["citations"].lower() or "citation" in close["citations"].lower() or "[" in close["citations"], close["citations"]
    assert len(close["do_today"]) == 3, close["do_today"]


def test_complaint_themes_and_do_today():
    close = _demo_close()
    assert close["complaint_themes"] == GOLDEN_THEMES, close["complaint_themes"]
    assert "Judy" in close["do_today"][0], close["do_today"]
    assert "'late'" in close["do_today"][1] and "(3" in close["do_today"][1], close["do_today"]
    assert len(close["ask_list"]) <= 3 and len(close["ask_list"]) == 3, close["ask_list"]
    assert all(a["stars"] == 5 for a in close["ask_list"]), close["ask_list"]


def test_determinism_modulo_date():
    from omni_one.packs.reputation_close import build_reputation_close, DEMO_REVIEWS
    reviews = DEMO_REVIEWS(seed=42)
    a = build_reputation_close(reviews, date_str="2026-10-11")
    b = build_reputation_close(reviews, date_str="2026-10-12")
    assert a["headline"] == b["headline"]
    assert a["kpis"] == b["kpis"]
    assert a["reply_queue"] == b["reply_queue"]
    assert a["date"] != b["date"]


def test_bundle_files_exist():
    from omni_one.packs.reputation_close import write_close_bundle
    close = _demo_close()
    out = Path(tempfile.mkdtemp()) / "rep_close"
    paths = write_close_bundle(close, out)
    assert sorted(paths) == ["close.csv", "close.json", "replies.txt", "reviews.csv"], paths
    for name, p in paths.items():
        assert Path(p).exists() and Path(p).stat().st_size > 0, name
    loaded = json.loads((out / "close.json").read_text(encoding="utf-8"))
    assert loaded["headline"] == GOLDEN_HEADLINE
    assert "Judy" in (out / "replies.txt").read_text(encoding="utf-8")


def test_close_to_csv_has_stars_and_theme():
    from omni_one.packs.reputation_close import close_to_csv
    close = _demo_close()
    csv_text = close_to_csv(close)
    assert "reviewer" in csv_text and "stars" in csv_text and "theme" in csv_text, csv_text
    assert "late" in csv_text, csv_text
    assert "Judy" in csv_text and ",1," in csv_text, csv_text


def test_demo_reviews_shape_and_empty_no_crash():
    from omni_one.packs.reputation_close import DEMO_REVIEWS, build_reputation_close
    reviews = DEMO_REVIEWS(seed=42)
    for r in reviews:
        for key in ("reviewer", "stars", "text", "product", "channel", "citation"):
            assert key in r, (key, r)
        assert "[" in r["citation"] and ":" in r["citation"], r
    empty = build_reputation_close([], date_str=GOLDEN_DATE)
    assert empty["kpis"]["avg_stars"] == 0.0
    assert empty["reply_queue"] == [] and len(empty["do_today"]) == 3
    assert empty["free"] is True
