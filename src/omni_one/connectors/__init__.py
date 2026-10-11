"""Connectors universe registry: 10 channels, auto-detect, parse_file/parse_rows."""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any

try:
    from . import shopify, etsy, amazon, tiktok, ebay, woocommerce, stripe, paypal, square, faire
    from ._common import read_csv_rows
except Exception:
    from omni_one.connectors import shopify, etsy, amazon, tiktok, ebay, woocommerce, stripe, paypal, square, faire  # type: ignore
    from omni_one.connectors._common import read_csv_rows  # type: ignore

CHANNELS: Dict[str, Any] = {
    "shopify": shopify,
    "etsy": etsy,
    "amazon": amazon,
    "tiktok": tiktok,
    "ebay": ebay,
    "woocommerce": woocommerce,
    "stripe": stripe,
    "paypal": paypal,
    "square": square,
    "faire": faire,
}

# filename keywords (lower) per channel
_FILENAME_HINTS: Dict[str, List[str]] = {
    "shopify": ["shopify"],
    "etsy": ["etsy"],
    "amazon": ["amazon"],
    "tiktok": ["tiktok", "tik-tok"],
    "ebay": ["ebay"],
    "woocommerce": ["woo", "woocommerce"],
    "stripe": ["stripe"],
    "paypal": ["paypal"],
    "square": ["square"],
    "faire": ["faire"],
}

# header fingerprints (lower substrings) per channel
_HEADER_HINTS: Dict[str, List[str]] = {
    "shopify": ["lineitem", "financial status", "fulfillment status", "order name", "created at"],
    "etsy": ["listing", "sale date", "receipt", "item total", "ship name", "deposit date"],
    "amazon": ["asin", "purchase-date", "fulfillment-channel", "sales-channel", "order-id", "ship-service-level"],
    "tiktok": ["order created time", "seller sku", "order amount", "tiktok"],
    "ebay": ["item title", "sold price", "final value fee", "sale date"],
    "woocommerce": ["order number", "tax total", "shipping total", "fee total", "billing email", "coupon"],
    "stripe": ["balance transaction", "charge id", "created (utc)", "statement descriptor"],
    "paypal": ["from email", "time zone", "timezone", "gross", "transaction id"],
    "square": ["gross sales", "net sales", "tender", "total collected"],
    "faire": ["retailer", "wholesale price", "retail price", "brand"],
}


def _score_headers(channel: str, header_text: str) -> int:
    score = 0
    for hint in _HEADER_HINTS.get(channel, []):
        if hint in header_text:
            score += 1
    return score


def detect(path_or_header: Any) -> str:
    """Detect channel from file path, header list, row dict, or header string."""
    try:
        filename = ""
        header_text = ""
        # Path object
        if isinstance(path_or_header, Path):
            filename = path_or_header.name.lower()
            try:
                if path_or_header.exists() and path_or_header.is_file():
                    fns, _ = read_csv_rows(path_or_header)
                    header_text = " | ".join(fns).lower()
            except Exception:
                pass
        elif isinstance(path_or_header, dict):
            header_text = " | ".join(str(k) for k in path_or_header.keys()).lower()
        elif isinstance(path_or_header, (list, tuple)):
            # list of fieldnames or list of rows?
            if path_or_header and isinstance(path_or_header[0], dict):
                header_text = " | ".join(str(k) for k in path_or_header[0].keys()).lower()
            else:
                header_text = " | ".join(str(x) for x in path_or_header).lower()
        elif isinstance(path_or_header, str):
            s = path_or_header
            p = Path(s)
            # looks like a path?
            if p.exists() and p.is_file():
                filename = p.name.lower()
                try:
                    fns, _ = read_csv_rows(p)
                    header_text = " | ".join(fns).lower()
                except Exception:
                    pass
            elif s.lower().endswith((".csv", ".tsv", ".txt")) or "/" in s or "\\" in s:
                filename = s.lower()
                # also try reading if it exists relative
                try:
                    if p.exists():
                        fns, _ = read_csv_rows(p)
                        header_text = " | ".join(fns).lower()
                    else:
                        header_text = s.lower()
                except Exception:
                    header_text = s.lower()
            else:
                header_text = s.lower()
        else:
            return "unknown"
        combined = (filename + " " + header_text).lower()
        best = "unknown"
        best_score = 0
        # filename hits weigh 5
        for ch in CHANNELS:
            score = _score_headers(ch, header_text) + _score_headers(ch, combined)
            for hint in _FILENAME_HINTS.get(ch, []):
                if hint and hint in filename:
                    score += 5
            # tie-break deterministic: keep first max (dict order)
            if score > best_score:
                best_score = score
                best = ch
        return best if best_score > 0 else "unknown"
    except Exception:
        return "unknown"


def parse_file(path: Any) -> List[Dict[str, Any]]:
    """Auto-detect channel from filename+headers and parse. Unknown -> []."""
    try:
        p = Path(str(path))
        if not p.exists():
            raise FileNotFoundError(str(path))
        fns, rows = read_csv_rows(p)
        if not fns or not rows:
            # empty or header-only with unknown? return []
            # if header-only unknown, still []
            return []
        channel = detect(p)
        # if filename gave unknown, try headers alone
        if channel == "unknown":
            channel = detect(fns)
        if channel == "unknown" or channel not in CHANNELS:
            return []
        mod = CHANNELS[channel]
        try:
            return list(mod.parse_rows(rows, source_file=p.name))
        except Exception:
            return []
    except FileNotFoundError:
        raise
    except Exception:
        return []


def parse_rows(channel: str, rows: List[Dict[str, Any]], source_file: str = "") -> List[Dict[str, Any]]:
    """Dispatch rows to channel parser. Unknown channel -> []."""
    try:
        if not rows:
            return []
        ch = (channel or "").strip().lower()
        if ch not in CHANNELS:
            return []
        mod = CHANNELS[ch]
        sf = source_file or f"{ch}_rows.csv"
        try:
            return list(mod.parse_rows(rows, source_file=sf))
        except Exception:
            return []
    except Exception:
        return []


__all__ = ["CHANNELS", "detect", "parse_file", "parse_rows"]
