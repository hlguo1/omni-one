"""Channel normalizers for Omni-One i18n seller pack.

Normalize raw direct messages and marketplace reviews from six channels
(instagram, tiktok, etsy, amazon, whatsapp, email) into stable dicts:

  normalize_dm(raw, channel) -> {"sender": str, "text": str, "ts": str}
  parse_review_row(row, channel) -> {"product": str, "stars": int, "text": str}

All functions are deterministic, dependency-free (stdlib only), and never
invent order numbers. Missing fields fall back to "" (or 0 stars) rather
than raising, so batch ingestion never crashes on a single bad row.

Raw shapes handled
------------------
instagram:
  - dict {"sender": ..., "text": ..., "timestamp"/"ts"/"date"/"created_at": ...}
  - dict {"from": ..., "message": ..., "ts": ...}
  - dict {"author": ..., "body": ..., "created_time": ...}
  - str "Sender: message" or plain message text
  - list with one such dict (takes first element)

tiktok (tiktok_dm.json export shapes):
  - dict {"messages": [ {...}, ... ]} (takes first message for single-DM view)
  - dict {"data": {"messages": [...]}} (nested export wrapper)
  - dict {"sender_name"/"sender"/"user"/"nickname": ...,
          "text"/"content"/"message"/"body": ...,
          "created_at"/"timestamp"/"date"/"createTime": ...}
  - list of message dicts (takes first)
  - str plain text (sender "tiktok_user")

etsy (convo CSV rows, as dicts from csv.DictReader):
  - keys like Buyer/Buyer Name/From/Sender, Message/Message Text/Body/Text,
    Date/Created At/Created/Message Date/Timestamp
  - str CSV row "buyer,message,date" (best-effort split, header-aware)
  - str plain message

amazon (buyer-message exports):
  - dict {"buyer-name"/"buyerName"/"Buyer Name"/"recipient": ...,
          "message"/"Message"/"buyer-message"/"text"/"body": ...,
          "date"/"Message Date"/"timestamp"/"created_at": ...}
  - dict {"messages": [...]} (takes first)
  - str plain message

whatsapp (txt export lines):
  - "[dd/mm HH:MM] Sender: msg" and "[dd/mm/yyyy, HH:MM:SS] Sender: msg"
  - "dd/mm/yyyy HH:MM - Sender: msg" (Android export variant)
  - dict {"sender": ..., "text": ..., "ts"/"date": ...}
  - str plain message (sender "whatsapp_user")

email (mbox-ish):
  - str with headers "From: ...\\nDate: ...\\nSubject: ...\\n\\nBody..."
  - str with "From ... Date ..." mbox "From " separator line
  - dict {"From"/"from"/"sender": ..., "Body"/"body"/"text": ...,
          "Date"/"date": ..., "Subject"/"subject": ...}
  - body is text after blank line; Subject kept as "[Subject] body" prefix
    so no information is lost, but no order numbers are invented.

Reviews:
  parse_review_row accepts dicts with many key spellings
  (product/Product/product_name/title/ASIN, stars/rating/Stars/Star Rating,
  text/review/body/comment/Review Text) plus list/tuple rows
  [product, stars, text] and plain strings (product "unknown", stars 0).
  Star normalization covers ints 1-5, floats, "5", "5 stars", "5/5",
  "4 out of 5", star glyphs (count of black stars), and English words
  "one star".."five stars" (case-insensitive).
"""

from __future__ import annotations

import csv
import io
import re

SUPPORTED_CHANNELS = ["instagram", "tiktok", "etsy", "amazon", "whatsapp", "email"]

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

_SENDER_KEYS = [
    "sender",
    "sender_name",
    "from",
    "author",
    "user",
    "username",
    "nickname",
    "buyer",
    "buyer_name",
    "buyer-name",
    "buyername",
    "customer",
    "customer_name",
    "name",
    "recipient",
]

_TEXT_KEYS = [
    "text",
    "message",
    "message_text",
    "body",
    "content",
    "comment",
    "buyer_message",
    "buyer-message",
    "review",
    "review_text",
]

_TS_KEYS = [
    "timestamp",
    "ts",
    "date",
    "created_at",
    "created",
    "created_time",
    "message_date",
    "time",
    "datetime",
]

_PRODUCT_KEYS = [
    "product",
    "product_name",
    "productname",
    "title",
    "item",
    "item_name",
    "asin",
    "listing",
    "listing_title",
]

_STAR_KEYS = [
    "stars",
    "star",
    "rating",
    "rate",
    "score",
    "star_rating",
    "stars_given",
]

_REVIEW_TEXT_KEYS = [
    "text",
    "review",
    "review_text",
    "body",
    "comment",
    "message",
    "content",
    "feedback",
]


def _safe_str(value, fallback: str = "") -> str:
    """Coerce to stripped string; None -> fallback; non-str -> str()."""
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip()
    try:
        return str(value).strip()
    except Exception:
        return fallback


def _norm_key(key) -> str:
    """Normalize a dict key for fuzzy matching: lower, alnum only."""
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _pick_first(mapping: dict, candidates: list) -> str:
    """Return first non-empty value for candidate keys (fuzzy match).

    Exact match tried first, then normalized-key match so "Buyer Name",
    "buyer_name" and "buyer-name" all resolve. Returns "" if nothing found.
    """
    if not isinstance(mapping, dict):
        return ""
    # Exact pass.
    for key in candidates:
        if key in mapping and mapping[key] not in (None, ""):
            val = mapping[key]
            if isinstance(val, (str, int, float)):
                text = _safe_str(val)
                if text:
                    return text
    # Normalized pass.
    norm_map = {_norm_key(k): v for k, v in mapping.items()}
    for key in candidates:
        nk = _norm_key(key)
        if nk in norm_map and norm_map[nk] not in (None, ""):
            text = _safe_str(norm_map[nk])
            if text:
                return text
    return ""


def _norm_channel(channel) -> str:
    """Normalize channel name; unknown -> 'instagram' default is NOT used.

    Unknown channels fall back to generic dict/str parsing but keep the
    channel label in code paths that need it. Returns lowered string.
    """
    ch = _safe_str(channel, "instagram").lower()
    # Allow common aliases.
    aliases = {
        "ig": "instagram",
        "tt": "tiktok",
        "wa": "whatsapp",
        "mail": "email",
        "e-mail": "email",
    }
    return aliases.get(ch, ch)


def _first_message(messages):
    """Return first dict/str element of a message list, else {}."""
    if isinstance(messages, list) and messages:
        for item in messages:
            if isinstance(item, (dict, str)):
                return item
    return {}


# ---------------------------------------------------------------------------
# Star normalization
# ---------------------------------------------------------------------------

_WORD_STARS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _normalize_stars(raw) -> int:
    """Normalize star ratings to int 1-5 (0 = unknown/missing).

    Handles:
      int/float 1-5 (floats rounded; out-of-range clamped only if 0.5-5.5,
      else 0), numeric strings "5", "5.0", "5 stars", "5/5", "4 out of 5",
      glyph runs "*****", star chars (black star count wins),
      English words "one star".."five stars" (also bare "one".."five"
      when the string mentions star/rate), "no stars"/"zero" -> 0.
    Deterministic; never raises.
    """
    if raw is None:
        return 0
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, (int, float)):
        try:
            val = int(round(float(raw)))
        except Exception:
            return 0
        return val if 1 <= val <= 5 else 0
    text = _safe_str(raw, "")
    if not text:
        return 0
    lowered = text.lower().strip()
    if lowered in ("0", "no stars", "no star", "zero", "zero stars", "n/a", "na", "-"):
        return 0
    # Star glyphs: black stars count; white stars fill remainder.
    # e.g. "*****" (5 black) -> 5; "***oo" style with white stars.
    if any(c in text for c in ("\u2605", "\u2b50", "*")):
        black = text.count("\u2605") + text.count("\u2b50")
        # ASCII asterisks only count when the string is mostly asterisks
        # (avoids matching "*important*" prose).
        ascii_stars = text.count("*")
        non_space = len(re.sub(r"\s", "", text))
        if ascii_stars >= 1 and non_space > 0 and (ascii_stars / non_space) >= 0.5:
            black += ascii_stars
        white = text.count("\u2606")
        if black >= 1:
            # "****o" (4 black + 1 white) -> 4; clamp 1-5.
            total = black
            if white and black + white <= 5:
                total = black
            return max(1, min(5, total))
        # Only white stars (e.g. "ooooo") -> treat as 0 unknown.
        if white:
            return 0
    # Word forms: "one star", "two stars", "three out of five", bare words.
    for word, val in _WORD_STARS.items():
        if re.search(r"(?<!\w)" + word + r"(?!\w)", lowered):
            # Require star-ish context for bare words except explicit forms.
            if "star" in lowered or "rate" in lowered or word == lowered.strip():
                return val
            # "one star" already matched; bare "one" without context -> still
            # accept only if the whole string is the word.
            if lowered.strip() == word:
                return val
    # Numeric forms: leading number wins ("5", "5.0", "5 stars", "5/5").
    m = re.search(r"(\d+(?:\.\d+)?)", lowered)
    if m:
        try:
            num = float(m.group(1))
        except ValueError:
            return 0
        # "4 out of 5" / "5/5" patterns: first number is the rating.
        val = int(round(num))
        if 1 <= val <= 5:
            # Guard "10/10"-style scales: if denominator suggests /10, map?
            # Keep simple: values >5 are unknown -> 0 (no invention).
            return val
        return 0
    return 0


# ---------------------------------------------------------------------------
# Per-channel DM parsers (each returns sender, text, ts strings)
# ---------------------------------------------------------------------------

def _parse_instagram(raw) -> tuple:
    """Parse instagram DM shapes."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        sender = _pick_first(raw, _SENDER_KEYS) or _safe_str(raw.get("handle"), "")
        text = _pick_first(raw, _TEXT_KEYS)
        ts = _pick_first(raw, _TS_KEYS)
        return sender or "instagram_user", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        # "Sender: message" split on first colon (but not URL colons).
        m = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m and "://" not in m.group(1):
            return m.group(1).strip(), m.group(2).strip(), ""
        return "instagram_user", text, ""
    return "instagram_user", "", ""


def _parse_tiktok(raw) -> tuple:
    """Parse tiktok_dm.json export shapes (nested + flat)."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        # Unwrap export wrappers: {"messages": [...]}, {"data": {...}}.
        if "messages" in raw and isinstance(raw["messages"], list) and raw["messages"]:
            return _parse_tiktok(_first_message(raw["messages"]))
        if "data" in raw and isinstance(raw["data"], dict):
            inner = raw["data"]
            if "messages" in inner and isinstance(inner["messages"], list) and inner["messages"]:
                return _parse_tiktok(_first_message(inner["messages"]))
            # Flat data wrapper: {"data": {"sender": ..., "text": ...}}.
            if any(k in inner for k in ("sender", "text", "content", "user")):
                return _parse_tiktok(inner)
        # TikTok web export spellings: sender_name, content, createTime.
        tiktok_sender_keys = _SENDER_KEYS + ["sender_name", "nickname", "unique_id", "display_name"]
        tiktok_text_keys = _TEXT_KEYS + ["content", "msg", "caption"]
        tiktok_ts_keys = _TS_KEYS + ["createtime", "create_time", "sent_at"]
        sender = _pick_first(raw, tiktok_sender_keys)
        text = _pick_first(raw, tiktok_text_keys)
        ts = _pick_first(raw, tiktok_ts_keys)
        return sender or "tiktok_user", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        m = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m and "://" not in m.group(1):
            return m.group(1).strip(), m.group(2).strip(), ""
        return "tiktok_user", text, ""
    return "tiktok_user", "", ""


def _parse_etsy(raw) -> tuple:
    """Parse etsy convo CSV rows (dicts from csv.DictReader) or strings."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        etsy_sender_keys = [
            "buyer", "buyer_name", "from", "sender", "author", "user",
            "customer", "customer_name", "name",
        ]
        etsy_text_keys = [
            "message", "message_text", "body", "text", "content", "comment",
        ]
        etsy_ts_keys = [
            "date", "created_at", "created", "message_date", "timestamp",
            "ts", "time",
        ]
        sender = _pick_first(raw, etsy_sender_keys)
        text = _pick_first(raw, etsy_text_keys)
        ts = _pick_first(raw, etsy_ts_keys)
        return sender or "etsy_buyer", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return "etsy_buyer", "", ""
        # Try CSV row parse when commas/newlines suggest tabular data.
        # Header-aware: skip a header line mentioning buyer+message.
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2 and re.search(r"buyer", lines[0], re.I) and re.search(r"messag", lines[0], re.I):
            try:
                reader = csv.DictReader(io.StringIO(text))
                rows = list(reader)
                if rows:
                    return _parse_etsy(rows[0])
            except Exception:
                pass
        # Single CSV data row "buyer,message,date" (quoted commas ok).
        if "," in text and "\n" not in text:
            try:
                cells = next(csv.reader(io.StringIO(text)))
                if len(cells) >= 2:
                    sender = cells[0].strip() or "etsy_buyer"
                    msg = cells[1].strip()
                    ts = cells[2].strip() if len(cells) >= 3 else ""
                    return sender, msg, ts
            except Exception:
                pass
        m = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m and "://" not in m.group(1):
            return m.group(1).strip(), m.group(2).strip(), ""
        return "etsy_buyer", text, ""
    return "etsy_buyer", "", ""


def _parse_amazon(raw) -> tuple:
    """Parse amazon buyer-message exports (varied vendor spellings)."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        if "messages" in raw and isinstance(raw["messages"], list) and raw["messages"]:
            return _parse_amazon(_first_message(raw["messages"]))
        amazon_sender_keys = [
            "buyer-name", "buyer_name", "buyername", "buyer", "sender",
            "from", "customer", "customer_name", "recipient", "name", "user",
        ]
        amazon_text_keys = [
            "message", "buyer-message", "buyer_message", "text", "body",
            "content", "comment", "message_text",
        ]
        amazon_ts_keys = [
            "date", "message_date", "timestamp", "ts", "created_at",
            "created", "time",
        ]
        sender = _pick_first(raw, amazon_sender_keys)
        text = _pick_first(raw, amazon_text_keys)
        ts = _pick_first(raw, amazon_ts_keys)
        return sender or "amazon_buyer", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        m = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m and "://" not in m.group(1):
            return m.group(1).strip(), m.group(2).strip(), ""
        return "amazon_buyer", text, ""
    return "amazon_buyer", "", ""


# WhatsApp line shapes:
#   [12/03 14:22] Maria: Hola ...
#   [12/03/2024, 14:22:05] Maria: Hola ...
#   12/03/2024 14:22 - Maria: Hola ...
_WHATSAPP_BRACKET_RE = re.compile(
    r"^\s*\[(?P<ts>[^\]]+)\]\s*(?P<sender>[^:]{1,60})\s*:\s*(?P<msg>.*)$",
    re.DOTALL,
)
_WHATSAPP_DASH_RE = re.compile(
    r"^\s*(?P<ts>\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+\d{1,2}:\d{2}(?::\d{2})?)"
    r"\s*[-–]\s*(?P<sender>[^:]{1,60})\s*:\s*(?P<msg>.*)$",
    re.DOTALL,
)


def _parse_whatsapp(raw) -> tuple:
    """Parse whatsapp txt export lines."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        sender = _pick_first(raw, _SENDER_KEYS) or _safe_str(raw.get("author"), "")
        text = _pick_first(raw, _TEXT_KEYS)
        ts = _pick_first(raw, _TS_KEYS)
        # Dict may hold a full export line under text; try line parse.
        if text:
            m = _WHATSAPP_BRACKET_RE.match(text) or _WHATSAPP_DASH_RE.match(text)
            if m:
                return (
                    m.group("sender").strip() or sender or "whatsapp_user",
                    m.group("msg").strip(),
                    m.group("ts").strip(),
                )
        return sender or "whatsapp_user", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return "whatsapp_user", "", ""
        # Multi-line export: join continuation lines? For single-DM view,
        # take the first message block: header line + following non-header
        # lines belong to the same message.
        lines = text.splitlines()
        first = lines[0].strip()
        m = _WHATSAPP_BRACKET_RE.match(first) or _WHATSAPP_DASH_RE.match(first)
        if m:
            sender = m.group("sender").strip()
            ts = m.group("ts").strip()
            body_lines = [m.group("msg")]
            for cont in lines[1:]:
                if _WHATSAPP_BRACKET_RE.match(cont) or _WHATSAPP_DASH_RE.match(cont):
                    break
                # Skip "<Media omitted>"? Keep it: it is real export content.
                body_lines.append(cont)
            return sender or "whatsapp_user", "\n".join(body_lines).strip(), ts
        # "Sender: msg" fallback.
        m2 = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m2 and "://" not in m2.group(1):
            return m2.group(1).strip(), m2.group(2).strip(), ""
        return "whatsapp_user", text, ""
    return "whatsapp_user", "", ""


def _parse_email(raw) -> tuple:
    """Parse mbox-ish email (headers + blank line + body) or dicts."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        sender = _pick_first(raw, ["from", "sender", "author", "reply_to", "user", "name"])
        # Strip "Name <addr>" to plain display name when possible.
        if "<" in sender and ">" in sender:
            display = sender.split("<")[0].strip().strip('"')
            addr = sender[sender.find("<") + 1:sender.find(">")].strip()
            sender = display or addr
        # Strip bare address to local part? Keep full address: it is real data.
        body = _pick_first(raw, ["body", "text", "message", "content", "comment"])
        subject = _pick_first(raw, ["subject", "title"])
        ts = _pick_first(raw, ["date", "timestamp", "ts", "created_at", "time", "sent"])
        if subject and body and not body.lower().startswith(subject.lower()):
            text = f"[{subject}] {body}"
        elif subject and not body:
            text = f"[{subject}]"
        else:
            text = body
        return sender or "email_sender", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return "email_sender", "", ""
        # Drop mbox "From " separator line (not a header).
        lines = text.splitlines()
        if lines and lines[0].startswith("From ") and "@" in lines[0]:
            lines = lines[1:]
            text = "\n".join(lines).strip()
        # Split headers/body on first blank line.
        header_block, sep, body = text.partition("\n\n")
        headers = {}
        sender = ""
        ts = ""
        subject = ""
        if sep:
            for hline in header_block.splitlines():
                if ":" not in hline:
                    continue
                hk, _, hv = hline.partition(":")
                hk = hk.strip().lower()
                hv = hv.strip()
                headers[hk] = hv
            sender = headers.get("from", "")
            if "<" in sender and ">" in sender:
                display = sender.split("<")[0].strip().strip('"')
                addr = sender[sender.find("<") + 1:sender.find(">")].strip()
                sender = display or addr
            ts = headers.get("date", "")
            subject = headers.get("subject", "")
            body_text = body.strip()
            if subject and body_text and not body_text.lower().startswith(subject.lower()):
                body_text = f"[{subject}] {body_text}"
            elif subject and not body_text:
                body_text = f"[{subject}]"
            return sender or "email_sender", body_text, ts
        # No blank line: maybe single "From: x" line + message?
        m = re.match(r"\s*From\s*:\s*([^\n]+)\n?(.*)", text, re.DOTALL | re.IGNORECASE)
        if m:
            sender = m.group(1).strip()
            rest = m.group(2).strip()
            # Peel optional Date:/Subject: leading lines without blank gap.
            date_m = re.match(r"Date\s*:\s*([^\n]+)\n?(.*)", rest, re.DOTALL | re.IGNORECASE)
            if date_m:
                ts = date_m.group(1).strip()
                rest = date_m.group(2).strip()
            subj_m = re.match(r"Subject\s*:\s*([^\n]+)\n?(.*)", rest, re.DOTALL | re.IGNORECASE)
            if subj_m:
                subject = subj_m.group(1).strip()
                rest = subj_m.group(2).strip()
                if subject and rest and not rest.lower().startswith(subject.lower()):
                    rest = f"[{subject}] {rest}"
                elif subject and not rest:
                    rest = f"[{subject}]"
            if "<" in sender and ">" in sender:
                display = sender.split("<")[0].strip().strip('"')
                addr = sender[sender.find("<") + 1:sender.find(">")].strip()
                sender = display or addr
            return sender or "email_sender", rest, ts
        return "email_sender", text, ""
    return "email_sender", "", ""


def _parse_generic(raw) -> tuple:
    """Channel-agnostic fallback for unknown channel labels."""
    if isinstance(raw, list):
        raw = _first_message(raw)
    if isinstance(raw, dict):
        sender = _pick_first(raw, _SENDER_KEYS)
        text = _pick_first(raw, _TEXT_KEYS)
        ts = _pick_first(raw, _TS_KEYS)
        return sender or "unknown_user", text, ts
    if isinstance(raw, str):
        text = raw.strip()
        m = re.match(r"\s*([^:\n]{1,60})\s*:\s*(.+)", text, re.DOTALL)
        if m and "://" not in m.group(1):
            return m.group(1).strip(), m.group(2).strip(), ""
        return "unknown_user", text, ""
    return "unknown_user", "", ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_dm(raw, channel) -> dict:
    """Normalize a raw DM into {"sender": str, "text": str, "ts": str}.

    Args:
      raw: dict, list (uses first message), or str export line.
      channel: one of instagram|tiktok|etsy|amazon|whatsapp|email
        (aliases ig/tt/wa/mail accepted; unknown labels use generic parse).

    Always returns all three keys as strings. Never raises on odd input:
    None/numbers/bools coerce to empty text with a channel default sender.
    """
    ch = _norm_channel(channel)
    if raw is None or isinstance(raw, bool):
        defaults = {
            "instagram": "instagram_user",
            "tiktok": "tiktok_user",
            "etsy": "etsy_buyer",
            "amazon": "amazon_buyer",
            "whatsapp": "whatsapp_user",
            "email": "email_sender",
        }
        return {"sender": defaults.get(ch, "unknown_user"), "text": "", "ts": ""}
    if isinstance(raw, (int, float)):
        return normalize_dm(str(raw), ch)
    if ch == "instagram":
        sender, text, ts = _parse_instagram(raw)
    elif ch == "tiktok":
        sender, text, ts = _parse_tiktok(raw)
    elif ch == "etsy":
        sender, text, ts = _parse_etsy(raw)
    elif ch == "amazon":
        sender, text, ts = _parse_amazon(raw)
    elif ch == "whatsapp":
        sender, text, ts = _parse_whatsapp(raw)
    elif ch == "email":
        sender, text, ts = _parse_email(raw)
    else:
        sender, text, ts = _parse_generic(raw)
    return {
        "sender": _safe_str(sender, "unknown_user") or "unknown_user",
        "text": _safe_str(text, ""),
        "ts": _safe_str(ts, ""),
    }


def parse_review_row(row, channel=None) -> dict:
    """Parse a review row into {"product": str, "stars": int, "text": str}.

    Args:
      row: dict (many key spellings), list/tuple [product, stars, text],
        or plain string (product "unknown", stars 0).
      channel: accepted and ignored for normalization except kept for
        signature compatibility (etsy/amazon spelling quirks handled
        regardless of label).

    Star normalization covers 1-5 ints, "5 stars", "5/5", glyph runs and
    English words "one star".."five stars". Missing -> 0.
    """
    _ = channel  # accepted for API compatibility; parsing is channel-agnostic
    if row is None or isinstance(row, bool):
        return {"product": "unknown", "stars": 0, "text": ""}
    if isinstance(row, str):
        text = row.strip()
        if not text:
            return {"product": "unknown", "stars": 0, "text": ""}
        # "product | 5 stars | review text" packed-string convenience.
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) >= 3:
                return {
                    "product": parts[0] or "unknown",
                    "stars": _normalize_stars(parts[1]),
                    "text": " | ".join(parts[2:]),
                }
            if len(parts) == 2:
                stars = _normalize_stars(parts[0])
                if stars:
                    return {"product": "unknown", "stars": stars, "text": parts[1]}
                stars2 = _normalize_stars(parts[1])
                if stars2:
                    return {"product": parts[0] or "unknown", "stars": stars2, "text": ""}
        return {"product": "unknown", "stars": 0, "text": text}
    if isinstance(row, (list, tuple)):
        cells = list(row)
        if len(cells) >= 3:
            return {
                "product": _safe_str(cells[0], "unknown") or "unknown",
                "stars": _normalize_stars(cells[1]),
                "text": _safe_str(cells[2], ""),
            }
        if len(cells) == 2:
            # Ambiguous [stars, text] vs [product, text]: try stars first.
            stars = _normalize_stars(cells[0])
            if stars:
                return {"product": "unknown", "stars": stars, "text": _safe_str(cells[1], "")}
            stars2 = _normalize_stars(cells[1])
            if stars2:
                return {
                    "product": _safe_str(cells[0], "unknown") or "unknown",
                    "stars": stars2,
                    "text": "",
                }
            return {
                "product": _safe_str(cells[0], "unknown") or "unknown",
                "stars": 0,
                "text": _safe_str(cells[1], ""),
            }
        if len(cells) == 1:
            return parse_review_row(cells[0])
        return {"product": "unknown", "stars": 0, "text": ""}
    if isinstance(row, dict):
        product = _pick_first(row, _PRODUCT_KEYS)
        text = _pick_first(row, _REVIEW_TEXT_KEYS)
        # Stars: fuzzy key lookup, then explicit normalized-key scan.
        stars_raw = _pick_first(row, _STAR_KEYS)
        if not stars_raw:
            norm_map = {_norm_key(k): v for k, v in row.items()}
            for key in _STAR_KEYS:
                nk = _norm_key(key)
                if nk in norm_map and norm_map[nk] not in (None, ""):
                    stars_raw = _safe_str(norm_map[nk])
                    if stars_raw:
                        break
        return {
            "product": product or "unknown",
            "stars": _normalize_stars(stars_raw) if stars_raw else 0,
            "text": text,
        }
    # Numbers / odd types: treat as stars if 1-5 else empty review.
    if isinstance(row, (int, float)):
        stars = _normalize_stars(row)
        if stars:
            return {"product": "unknown", "stars": stars, "text": ""}
    return {"product": "unknown", "stars": 0, "text": _safe_str(row, "")}


__all__ = [
    "SUPPORTED_CHANNELS",
    "normalize_dm",
    "parse_review_row",
]
