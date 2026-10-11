"""channels golden tests: normalize_dm + parse_review_row."""
import json
from pathlib import Path

FIX_DIR = Path(__file__).parent.parent / "fixtures" / "i18n"


def test_normalize_dm_fixtures_have_sender_text_ts():
    from omni_one.i18n.channels import normalize_dm

    total = 0
    for name in [
        "es_instagram.json",
        "zh_tiktok.json",
        "fr_etsy.json",
        "de_amazon.json",
        "en_whatsapp.json",
        "en_email.json",
    ]:
        data = json.loads((FIX_DIR / name).read_text(encoding="utf-8"))
        # Each channel file holds 2-4+ samples; each sample text is multi-line.
        assert len(data) >= 2, f"{name} needs >=2 samples"
        for entry in data:
            total += 1
            out = normalize_dm(entry["raw"], entry["channel"])
            assert set(out.keys()) == {"sender", "text", "ts"}, out
            assert out["sender"], f"empty sender in {name}: {entry}"
            assert out["text"] and len(out["text"]) > 10, f"empty text in {name}"
            # Idempotent shape: normalizing the normalized dict is stable.
            out2 = normalize_dm({"sender": out["sender"], "text": out["text"], "ts": out["ts"]}, entry["channel"])
            assert out2["text"] == out["text"]
            assert out2["sender"] == out["sender"]
    assert total >= 20, f"need 20+ DM samples, got {total}"


def test_normalize_dm_channel_shapes():
    from omni_one.i18n.channels import normalize_dm

    # instagram dict variants.
    assert normalize_dm({"sender": "Mia", "text": "hi", "timestamp": "2026-01-01"}, "instagram") == {
        "sender": "Mia",
        "text": "hi",
        "ts": "2026-01-01",
    }
    assert normalize_dm({"from": "Mia", "message": "hi there"}, "instagram")["sender"] == "Mia"
    assert normalize_dm("Mia: hello there", "instagram")["sender"] == "Mia"
    # tiktok nested shapes.
    nested = {"messages": [{"sender_name": "A", "text": "hello tiktok", "createTime": "t1"}]}
    out = normalize_dm(nested, "tiktok")
    assert out == {"sender": "A", "text": "hello tiktok", "ts": "t1"}, out
    wrapped = {"data": {"messages": [{"user": "B", "content": "ni hao", "created_at": "t2"}]}}
    out2 = normalize_dm(wrapped, "tiktok")
    assert out2["sender"] == "B" and out2["text"] == "ni hao" and out2["ts"] == "t2"
    # etsy convo CSV row.
    out3 = normalize_dm({"Buyer": "Camille", "Message": "bonjour", "Date": "d1"}, "etsy")
    assert out3 == {"sender": "Camille", "text": "bonjour", "ts": "d1"}, out3
    # etsy CSV data row string.
    out4 = normalize_dm("Camille,bonjour commande,d1", "etsy")
    assert out4["sender"] == "Camille" and "bonjour" in out4["text"]
    # amazon buyer-message export.
    out5 = normalize_dm({"buyer-name": "Lena", "message": "hallo bitte", "date": "d2"}, "amazon")
    assert out5 == {"sender": "Lena", "text": "hallo bitte", "ts": "d2"}, out5
    out6 = normalize_dm({"messages": [{"buyer-name": "X", "message": "m", "date": "d"}]}, "amazon")
    assert out6["sender"] == "X"
    # whatsapp bracket + dash.
    out7 = normalize_dm("[12/03 14:22] Maria: Hola pedido", "whatsapp")
    assert out7 == {"sender": "Maria", "text": "Hola pedido", "ts": "12/03 14:22"}, out7
    out8 = normalize_dm("12/03/2026 14:22 - Maria: Hola pedido", "whatsapp")
    assert out8["sender"] == "Maria" and out8["text"] == "Hola pedido"
    # email mbox-ish.
    mbox = "From: Emma <emma@example.com>\nDate: 12 Sep 2026\nSubject: Hi\n\nHello body here"
    out9 = normalize_dm(mbox, "email")
    assert out9["sender"] == "Emma", out9
    assert "Hello body here" in out9["text"]
    assert out9["ts"] == "12 Sep 2026"
    out10 = normalize_dm({"From": "Ava", "Subject": "S", "Body": "hello", "Date": "d3"}, "email")
    assert out10["sender"] == "Ava" and "[S]" in out10["text"]
    # Odd inputs never raise.
    assert normalize_dm(None, "instagram")["text"] == ""
    assert normalize_dm("", "tiktok")["text"] == ""
    assert normalize_dm(123, "email")["text"] == "123"


def test_parse_review_row_fixtures():
    import json as _json
    from omni_one.i18n.channels import parse_review_row

    data = _json.loads((FIX_DIR / "reviews.json").read_text(encoding="utf-8"))
    for entry in data:
        out = parse_review_row(entry["row"], entry.get("channel"))
        assert set(out.keys()) == {"product", "stars", "text"}, out
        assert out["product"] == entry["expected_product"], out
        assert out["stars"] == entry["expected_stars"], out
        assert out["text"], out


def test_parse_review_star_normalization():
    from omni_one.i18n.channels import parse_review_row as p

    def stars(v):
        return p({"product": "Tote", "stars": v, "text": "ok"})["stars"]

    # ints 1-5.
    assert stars(1) == 1 and stars(5) == 5 and stars(3) == 3
    assert stars(0) == 0 and stars(9) == 0
    # numeric strings.
    assert stars("5") == 5
    assert stars("1") == 1
    assert stars("5 stars") == 5
    assert stars("1 star") == 1
    assert stars("5/5") == 5
    assert stars("4 out of 5") == 4
    # glyphs.
    assert stars("\u2605\u2605\u2605\u2605\u2605") == 5
    assert stars("\u2605") == 1
    assert stars("\u2605\u2605\u2605\u2605\u2606") == 4
    # words.
    assert stars("one star") == 1
    assert stars("Two Stars") == 2
    assert stars("three stars") == 3
    assert stars("four stars") == 4
    assert stars("five stars") == 5
    # missing -> 0.
    assert p({"product": "Tote", "text": "ok"})["stars"] == 0
    # key spellings.
    assert p({"title": "Tote", "rating": "5", "body": "great"})["stars"] == 5
    assert p({"product_name": "Tote", "Star Rating": "one star", "Review Text": "bad"})["stars"] == 1
    # list + string rows.
    assert p(["Tote", 4, "nice"]) == {"product": "Tote", "stars": 4, "text": "nice"}
    assert p("just a comment")["stars"] == 0
    # idempotent on already-parsed dicts.
    once = p({"product": "Tote", "stars": "5 stars", "text": "great"})
    twice = p({"product": once["product"], "stars": once["stars"], "text": once["text"]})
    assert once == twice
