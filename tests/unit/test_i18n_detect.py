"""detect_locale golden tests: accuracy on fixtures >= 90% + unit checks."""
import json
from pathlib import Path

FIX_DIR = Path(__file__).parent.parent / "fixtures" / "i18n"


def _load_all_dm():
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
        for entry in data:
            items.append(entry)
    return items


def _load_reviews():
    data = json.loads((FIX_DIR / "reviews.json").read_text(encoding="utf-8"))
    return data


def test_supported_and_list_locales():
    from omni_one.i18n import SUPPORTED, list_locales

    assert set(SUPPORTED) == {"en", "es", "zh", "fr", "de"}
    assert set(list_locales()) == set(SUPPORTED)
    # canonical order preserved
    assert list_locales() == ["en", "es", "zh", "fr", "de"]


def test_detect_locale_accuracy_on_dm_fixtures():
    from omni_one.i18n import detect_locale
    from omni_one.i18n.channels import normalize_dm

    items = _load_all_dm()
    assert len(items) >= 20, f"need 20+ DM samples, got {len(items)}"
    correct = 0
    misses = []
    for entry in items:
        norm = normalize_dm(entry["raw"], entry["channel"])
        text = norm["text"]
        assert text, f"empty normalized text for {entry}"
        got = detect_locale(text)
        if got == entry["locale"]:
            correct += 1
        else:
            misses.append((entry["locale"], got, text[:80]))
    acc = correct / len(items)
    assert acc >= 0.90, f"accuracy {acc:.2f} < 0.90 misses={misses}"


def test_detect_locale_accuracy_on_review_fixtures():
    from omni_one.i18n import detect_locale
    from omni_one.i18n.channels import parse_review_row

    rows = _load_reviews()
    assert len(rows) >= 6
    correct = 0
    for entry in rows:
        parsed = parse_review_row(entry["row"], entry.get("channel"))
        got = detect_locale(parsed["text"])
        if got == entry["locale"]:
            correct += 1
    acc = correct / len(rows)
    assert acc >= 0.90, f"review accuracy {acc:.2f}"


def test_detect_locale_unit_heuristics():
    from omni_one.i18n import detect_locale

    # Empty / None defaults to en.
    assert detect_locale("") == "en"
    assert detect_locale("   ") == "en"
    assert detect_locale(None) == "en"
    assert detect_locale(123) == "en"
    # CJK ratio -> zh.
    assert detect_locale("\u60a8\u597d\uff0c\u6211\u7684\u8ba2\u5355\u5ef6\u8fdf\u4e86\uff0c\u8bf7\u5e2e\u5fd9\u3002") == "zh"
    assert detect_locale("Hello \u60a8\u597d \u8c22\u8c22 test \u8ba2\u5355\u5ef6\u8fdf") == "zh"
    # Accent / keyword heuristics.
    assert detect_locale("Hola, gracias por tu ayuda con mi pedido") == "es"
    assert detect_locale("Bonjour, merci pour votre aide avec ma commande svp") == "fr"
    assert detect_locale("Hallo, danke f\u00fcr Ihre Hilfe mit der Bestellung bitte") == "de"
    # Default en.
    assert detect_locale("Hello, thanks for your help with my order please") == "en"
    # Deterministic.
    t = "Hola, mi pedido lleg\u00f3 tarde, gracias"
    assert detect_locale(t) == detect_locale(t)


def test_t_with_en_fallback():
    from omni_one.i18n import t

    # Known key in each locale.
    assert "2 horas" in t("reply_window", "es")
    assert "2\u5c0f\u65f6" in t("reply_window", "zh")
    assert "2 heures" in t("reply_window", "fr")
    assert "2 Stunden" in t("reply_window", "de")
    assert "2 hours" in t("reply_window", "en")
    # Unknown locale falls back to en.
    assert t("reply_window", "xx") == t("reply_window", "en")
    # Formatting with vars.
    assert "Solmar" in t("thanks", "es", shop="Solmar")
    # Unknown key raises KeyError.
    try:
        t("no_such_key_xyz", "en")
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError for unknown key")
