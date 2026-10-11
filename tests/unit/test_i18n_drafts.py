"""drafts golden tests: citation+name, CJK, 2 horas, neg-words, idempotent."""
import json
import re
from pathlib import Path

FIX_DIR = Path(__file__).parent.parent / "fixtures" / "i18n"
CJK_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

COVER_14D = {
    "en": "14 days",
    "es": "14 d\u00edas",
    "zh": "14 \u5929",
    "fr": "14 jours",
    "de": "14 Tage",
}


def _dm_items():
    items = []
    for name in [
        "es_instagram.json",
        "zh_tiktok.json",
        "fr_etsy.json",
        "de_amazon.json",
        "en_whatsapp.json",
        "en_email.json",
    ]:
        data = json.loads((FIX_DIR / name).read_text(encoding="utf-8"))
        for e in data:
            items.append(e)
    return items


def test_every_draft_contains_citation_and_customer_name():
    from omni_one.i18n.channels import normalize_dm
    from omni_one.i18n.drafts import build_reply

    items = _dm_items()
    assert len(items) >= 20
    for entry in items:
        norm = normalize_dm(entry["raw"], entry["channel"])
        customer = norm["sender"]
        citation = entry["citation"]
        draft = build_reply(entry["channel"], entry["locale"], customer, norm["text"], citation, "Solmar")
        assert citation in draft, f"missing citation in {entry['locale']} draft: {draft[:120]}"
        assert customer in draft, f"missing customer {customer} in draft: {draft[:120]}"
        assert not re.search(r"#\d", draft), f"invented order number in draft: {draft[:120]}"


def test_zh_draft_contains_cjk_and_citation():
    from omni_one.i18n.drafts import build_reply

    draft = build_reply("tiktok", "zh", "\u5c0f\u660e", "\u60a8\u597d\uff0c\u5305\u88f9\u4e22\u5931\u4e86", "tiktok_dm.json", "Solmar")
    assert CJK_RE.search(draft), f"zh draft missing CJK: {draft}"
    assert "tiktok_dm.json" in draft
    assert "\u5c0f\u660e" in draft


def test_es_draft_contains_2_horas():
    from omni_one.i18n.drafts import build_reply

    draft = build_reply("instagram", "es", "Mar\u00eda", "Hola, mi pedido lleg\u00f3 tarde", "instagram_dm.txt", "Solmar")
    assert "2 horas" in draft, draft
    assert "Mar\u00eda" in draft and "instagram_dm.txt" in draft


def test_complaint_phrases_trigger_negative_per_locale():
    from omni_one.i18n import get_locale_module

    for locale in ["en", "es", "zh", "fr", "de"]:
        mod = get_locale_module(locale)
        assert len(mod.COMPLAINT_PHRASES) >= 15, f"{locale} needs 15+ phrases"
        assert len(mod.NEGATIVE_WORDS) >= 20, f"{locale} needs 20+ words"
        assert isinstance(mod.ISSUE_LABELS, dict) and len(mod.ISSUE_LABELS) >= 5
        assert isinstance(mod.FORMALITY, str) and len(mod.FORMALITY) > 20
        # Every complaint phrase triggers is_complaint + is_negative.
        for phrase in mod.COMPLAINT_PHRASES:
            assert mod.is_complaint(phrase) is True, f"{locale} missed complaint: {phrase}"
            assert mod.is_negative(phrase) is True, f"{locale} missed neg: {phrase}"
        # Every negative word triggers is_negative in a neutral carrier.
        for word in mod.NEGATIVE_WORDS:
            assert mod.is_negative(f"carrier {word} carrier") is True, f"{locale} word missed: {word}"


def test_templates_include_citation_placeholder():
    from omni_one.i18n import get_locale_module

    for locale in ["en", "es", "zh", "fr", "de"]:
        mod = get_locale_module(locale)
        for attr in ["DM_REPLY_TEMPLATE", "REVIEW_REPLY_TEMPLATE", "PO_EMAIL_TEMPLATE", "COVER_NOTE_14D_TEMPLATE"]:
            tpl = getattr(mod, attr)
            assert "{citation}" in tpl, f"{locale}.{attr} missing {{citation}}"


def test_build_po_and_cover_note_localized():
    from omni_one.i18n.drafts import build_po, cover_note_14d

    lines = [{"product": "Canvas Tote", "qty": 20}, {"product": "Linen Pouch", "qty": 10}]
    for locale, marker in COVER_14D.items():
        po = build_po(locale, "Acme Supplies", lines, "Solmar", "inventory.csv")
        assert "Acme Supplies" in po, f"{locale} po missing supplier"
        assert "Solmar" in po
        assert "inventory.csv" in po
        assert marker in po, f"{locale} po missing 14-day marker {marker!r}: {po[:200]}"
        assert not re.search(r"#\d", po)
        note = cover_note_14d(locale, "Solmar", "inventory.csv")
        assert marker in note, f"{locale} cover missing {marker!r}"
        assert "Solmar" in note and "inventory.csv" in note


def test_review_reply_contains_product_and_citation():
    from omni_one.i18n.drafts import build_review_reply

    for locale in ["en", "es", "zh", "fr", "de"]:
        d = build_review_reply(locale, "Canvas Tote", "reviews.csv", "Solmar")
        assert "reviews.csv" in d
        # zh product name check uses localized default when ascii product given:
        # at least citation + shop must appear; product appears verbatim.
        assert "Canvas Tote" in d and "Solmar" in d


def test_idempotent():
    from omni_one.i18n.channels import normalize_dm
    from omni_one.i18n.drafts import build_po, build_reply, cover_note_14d

    d1 = build_reply("instagram", "es", "Mar\u00eda", "Hola, lleg\u00f3 roto", "instagram_dm.txt", "Solmar")
    d2 = build_reply("instagram", "es", "Mar\u00eda", "Hola, lleg\u00f3 roto", "instagram_dm.txt", "Solmar")
    assert d1 == d2
    z1 = build_reply("tiktok", "zh", "\u5c0f\u660e", "\u5305\u88f9\u4e22\u5931", "tiktok_dm.json", "Solmar")
    assert build_reply("tiktok", "zh", "\u5c0f\u660e", "\u5305\u88f9\u4e22\u5931", "tiktok_dm.json", "Solmar") == z1
    lines = [{"product": "Canvas Tote", "qty": 5}]
    assert build_po("fr", "Fourn", lines, "Solmar") == build_po("fr", "Fourn", lines, "Solmar")
    assert cover_note_14d("de", "Solmar") == cover_note_14d("de", "Solmar")
    # normalize idempotent on fixture raws.
    for entry in _dm_items()[:4]:
        a = normalize_dm(entry["raw"], entry["channel"])
        b = normalize_dm(entry["raw"], entry["channel"])
        assert a == b
