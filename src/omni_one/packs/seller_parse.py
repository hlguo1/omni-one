"""
Seller parse — shared deterministic parsers (free, no LLM).
============================================================
Extracted from seller_os + micro_biz duplicates so both packs share:
money, product normalize/match, headers, currency.

$0, stdlib only. Tested in tests/unit/test_seller_robustness.py.
"""
from __future__ import annotations

import re
from typing import List, Optional


_CURRENCY_SYMBOLS = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY"}

# Words that look like money but aren't (avoid qty prefix false totals)
_STOPWORDS_MONEY = set()


def _strip_dates(text: str) -> str:
    text = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", text)
    text = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", text)
    return text


def normalize_currency(s: str) -> str:
    """Map £/€/¥ to $ numeric value as-is (no FX — shops price in one currency per file)."""
    if not s:
        return ""
    # Keep digits, dot, minus; drop currency symbols/commas/spaces for parsing
    t = str(s)
    for sym in ("£", "€", "¥", "$", "USD", "GBP", "EUR"):
        t = t.replace(sym, " ")
    return t


def _money_all(s: str) -> List[float]:
    """All money-like numbers, robust. Ignores dates. Handles £€, commas, qty prefix safe via _money_last."""
    if not s:
        return []
    text = _strip_dates(str(s))
    text = normalize_currency(text).replace(",", "")
    vals: List[float] = []
    for m in re.finditer(r"(\d+(?:\.\d{1,2})?)", text):
        try:
            vals.append(float(m.group(1)))
        except Exception:
            continue
    return vals


def _money(s: str) -> Optional[float]:
    vals = _money_all(s)
    return vals[0] if vals else None


def _money_last(s: str) -> Optional[float]:
    """Last money (line totals). Robust vs '50 x 4.00 200.00' -> 200.00."""
    vals = _money_all(s)
    return vals[-1] if vals else None


def detect_currency(s: str) -> str:
    for sym, code in _CURRENCY_SYMBOLS.items():
        if sym in str(s or ""):
            return code
    return "USD"


def extract_unit_qty(line: str) -> Optional[tuple[float, float, float]]:
    """Parse '50 x 4.00 200.00' -> (qty=50, unit=4.00, total=200.00). Returns None if no qty pattern."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*\$?\s*(\d+(?:[.,]\d+)?)", str(line), re.I)
    if not m:
        return None
    try:
        qty = float(m.group(1).replace(",", ""))
        unit = float(m.group(2).replace(",", ""))
        total = _money_last(line) or (qty * unit)
        return (qty, unit, float(total))
    except Exception:
        return None


def _norm_product(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _token_jaccard(a: str, b: str) -> float:
    sa, sb = set(_norm_product(a).split()), set(_norm_product(b).split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _product_match(a: str, b: str, threshold: float = 0.72) -> bool:
    """Fuzzy product match: exact → substring → token-Jaccard → SequenceMatcher."""
    from difflib import SequenceMatcher as _SM
    na, nb = _norm_product(a), _norm_product(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    # Token overlap pre-pass (cheap, reduces false positives like Tote vs Tote Bag Handmade ok, Mug vs Tote no)
    try:
        if _token_jaccard(a, b) >= 0.5:
            return True
    except Exception:
        pass
    try:
        return _SM(None, na, nb).ratio() >= threshold
    except Exception:
        return False


def _norm_header(h: str) -> str:
    h_low = h.strip().lower()
    h_norm = h_low.replace(" ", "_")
    mapping_ordered = [
        ("order_id", ["order_id", "order_number", "receipt", "sale_id"]),
        ("date", ["order_date", "created", "settled", "timestamp"]),
        ("qty", ["quantity", "lineitem_quantity", "qty", "units"]),
        ("gmv", ["lineitem_price", "order_total", "gross", "sales"]),
        ("fees", ["etsy_fee", "shopify_fee", "amazon_fee", "fees", "fee", "commission"]),
        ("shipping", ["shipping", "postage", "delivery"]),
        ("product", ["lineitem_name", "product", "listing", "sku", "title", "description"]),
        ("customer", ["customer", "buyer", "recipient"]),
        ("status", ["fulfillment", "status", "state"]),
        ("product", ["item"]),
        ("gmv", ["price", "total"]),
        ("date", ["date"]),
        ("order_id", ["order"]),
    ]
    for norm, variants in mapping_ordered:
        for v in variants:
            if v in h_norm or v.replace("_", " ") in h_low:
                return norm
    return h_norm


__all__ = [
    "_money_all", "_money", "_money_last", "detect_currency", "extract_unit_qty",
    "normalize_currency", "_norm_product", "_token_jaccard", "_product_match", "_norm_header",
]
