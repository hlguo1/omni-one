"""Shared deterministic helpers for connectors (free, stdlib only, no network/LLM)."""
from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple

# --- reuse seller_parse helpers with fallback ---
try:
    from omni_one.packs.seller_parse import _money_last as _sp_money_last  # type: ignore
    from omni_one.packs.seller_parse import _norm_header as _sp_norm_header  # type: ignore
    from omni_one.packs.seller_parse import _norm_product as _sp_norm_product  # type: ignore
    from omni_one.packs.seller_parse import detect_currency as _sp_detect  # type: ignore
except Exception:
    try:
        from ..packs.seller_parse import _money_last as _sp_money_last  # type: ignore
        from ..packs.seller_parse import _norm_header as _sp_norm_header  # type: ignore
        from ..packs.seller_parse import _norm_product as _sp_norm_product  # type: ignore
        from ..packs.seller_parse import detect_currency as _sp_detect  # type: ignore
    except Exception:
        _sp_money_last = None  # type: ignore
        _sp_norm_header = None  # type: ignore
        _sp_norm_product = None  # type: ignore
        _sp_detect = None  # type: ignore


def _fallback_money_last(s: str):
    if not s:
        return None
    text = str(s)
    text = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", text)
    text = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", text)
    t = text.replace(",", "")
    for sym in ("£", "€", "¥", "$"):
        t = t.replace(sym, " ")
    vals = []
    for m in re.finditer(r"(\d+(?:\.\d{1,2})?)", t):
        try:
            vals.append(float(m.group(1)))
        except Exception:
            continue
    return vals[-1] if vals else None


def _fallback_norm_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_")


def _fallback_norm_product(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def money_last(s: Any) -> Any:
    try:
        if _sp_money_last is not None:
            return _sp_money_last(str(s) if s is not None else "")
        return _fallback_money_last(str(s) if s is not None else "")
    except Exception:
        return _fallback_money_last(str(s) if s is not None else "")


def norm_header(h: str) -> str:
    try:
        if _sp_norm_header is not None:
            return _sp_norm_header(h)
        return _fallback_norm_header(h)
    except Exception:
        return _fallback_norm_header(h)


def norm_product(s: str) -> str:
    try:
        if _sp_norm_product is not None:
            return _sp_norm_product(s)
        return _fallback_norm_product(s)
    except Exception:
        return _fallback_norm_product(s)


DEFAULT_TS = datetime(2024, 1, 1, 0, 0, 0)

_REFUND_TOKENS = ("refund", "return", "cancel", "void", "revers", "disput", "chargeback", "failed")


def detect_currency_code(*texts: Any) -> str:
    """Detect USD/EUR/GBP via symbols/codes. Priority GBP>EUR>USD."""
    joined = " ".join(str(t or "") for t in texts)
    if "£" in joined or re.search(r"\bGBP\b", joined, re.I):
        return "GBP"
    if "€" in joined or re.search(r"\bEUR\b", joined, re.I):
        return "EUR"
    # $ or USD or default
    return "USD"


def parse_money_abs(s: Any) -> float:
    """Parse money absolute value; returns 0.0 if unparseable."""
    if s is None:
        return 0.0
    try:
        v = money_last(str(s))
        if v is None:
            return 0.0
        return abs(float(v))
    except Exception:
        return 0.0


def is_negative_amount_raw(s: Any) -> bool:
    if s is None:
        return False
    t = str(s).strip()
    if not t:
        return False
    if t.startswith("-") or t.startswith("−"):
        return True
    if t.startswith("(") and t.endswith(")"):
        return True
    # accounting: "-$20.00" or "$-20"
    if re.search(r"\(\s*\$?[\d,]+\.\d+", t):
        return True
    if re.match(r"-\s*\$?[\d,]", t):
        return True
    return False


def parse_qty(s: Any, default: int = 1) -> int:
    if s is None or str(s).strip() == "":
        return default
    t = str(s).strip()
    # handle "(2)" accounting negative
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    m = re.search(r"-?\d+", t)
    if not m:
        return default
    try:
        v = int(m.group(0))
        if neg:
            v = -abs(v)
        if v == 0:
            return default
        return v
    except Exception:
        return default


def parse_date(s: Any) -> datetime:
    """Deterministic date parse: ISO, MM/DD/YYYY, DD/MM/YYYY, epoch, epoch-ms."""
    if s is None:
        return DEFAULT_TS
    t = str(s).strip()
    if not t:
        return DEFAULT_TS
    # epoch: pure digits (optionally with decimal / spaces)
    t_nospace = t.replace(" ", "").replace(",", "")
    # epoch-ms (13 digits) or epoch seconds (10 digits); also handle float
    if re.fullmatch(r"\d{10}(\.\d+)?", t_nospace):
        try:
            return datetime.fromtimestamp(float(t_nospace), tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    if re.fullmatch(r"\d{13}(\.\d+)?", t_nospace):
        try:
            return datetime.fromtimestamp(float(t_nospace) / 1000.0, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    # also handle 9-13 digit ints generically: >=1e12 -> ms else seconds
    if re.fullmatch(r"\d{9,13}", t_nospace):
        try:
            v = int(t_nospace)
            if v >= 100000000000:  # 12+ digits -> ms
                return datetime.fromtimestamp(v / 1000.0, tz=timezone.utc).replace(tzinfo=None)
            return datetime.fromtimestamp(float(v), tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    # strip time suffix Z
    t_iso = t.replace("Z", "").strip()
    # try ISO formats
    iso_fmts = (
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f",
        "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%m-%d-%Y", "%d-%m-%Y", "%Y.%m.%d", "%d.%m.%Y",
    )
    for fmt in iso_fmts:
        try:
            return datetime.strptime(t_iso[: len("2024-09-10 12:00:00") + 4], fmt)
        except Exception:
            continue
    # slash dates with heuristic MM/DD vs DD/MM
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?$", t.strip())
    if m:
        try:
            a, b = int(m.group(1)), int(m.group(2))
            c = m.group(3)
            year = int(c) if len(c) == 4 else (2000 + int(c) if int(c) < 70 else 1900 + int(c))
            # heuristic: a>12 -> DD/MM, b>12 -> MM/DD, else MM/DD (US default)
            if a > 12 and b <= 12:
                day, month = a, b
            elif b > 12 and a <= 12:
                month, day = a, b
            elif a > 12 and b > 12:
                return DEFAULT_TS
            else:
                month, day = a, b
            hh = int(m.group(4)) if m.group(4) else 0
            mm = int(m.group(5)) if m.group(5) else 0
            ss = int(m.group(6)) if m.group(6) else 0
            return datetime(year, month, day, hh, mm, ss)
        except Exception:
            pass
    # try fromisoformat last
    try:
        return datetime.fromisoformat(t_iso)
    except Exception:
        pass
    return DEFAULT_TS


def canonicalize_headers(fieldnames: List[str], aliases: Dict[str, str]) -> Dict[str, str]:
    """Map raw header -> canonical. Aliases keys matched case-insensitively + normalized."""
    # build normalized alias lookup
    alias_norm: Dict[str, str] = {}
    for k, v in aliases.items():
        alias_norm[k.strip().lower()] = v
        alias_norm[k.strip().lower().replace(" ", "_")] = v
        alias_norm[k.strip().lower().replace("_", " ")] = v
        try:
            alias_norm[norm_header(k)] = v
        except Exception:
            pass
    out: Dict[str, str] = {}
    for raw in fieldnames or []:
        if raw is None:
            continue
        key = str(raw)
        low = key.strip().lower()
        if low in alias_norm:
            out[key] = alias_norm[low]
            continue
        us = low.replace(" ", "_")
        if us in alias_norm:
            out[key] = alias_norm[us]
            continue
        sp = low.replace("_", " ")
        if sp in alias_norm:
            out[key] = alias_norm[sp]
            continue
        try:
            nh = norm_header(key)
            if nh in alias_norm:
                out[key] = alias_norm[nh]
                continue
            out[key] = nh
        except Exception:
            out[key] = low.replace(" ", "_")
    return out


KNOWN_CANONICAL = {
    "order_id", "date", "product", "qty", "gmv", "gmv_unit", "fees", "shipping",
    "customer", "status", "type", "currency", "amount", "total", "price",
    "net", "gross", "item", "sku",
}


def has_known_fields(field_map: Dict[str, str]) -> bool:
    vals = set(field_map.values())
    # direct canonical
    if vals & KNOWN_CANONICAL:
        return True
    # seller_parse norm_header already maps to order_id/date/qty/gmv/fees/shipping/product/customer/status
    if vals & {"order_id", "date", "qty", "gmv", "fees", "shipping", "product", "customer", "status"}:
        return True
    return False


def is_refund(type_raw: str, status_raw: str, qty_raw: Any, gmv_raw: Any, qty_parsed: int) -> bool:
    tl = (type_raw or "").lower()
    sl = (status_raw or "").lower()
    for tok in _REFUND_TOKENS:
        if tok in tl or tok in sl:
            return True
    if qty_parsed < 0:
        return True
    if is_negative_amount_raw(qty_raw):
        return True
    if is_negative_amount_raw(gmv_raw):
        return True
    return False


def read_csv_rows(path: Any) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Read CSV with BOM strip + delimiter sniff (comma/semicolon/tab/pipe). Never raises for bad content."""
    p = Path(str(path))
    try:
        raw = p.read_bytes()
    except Exception:
        raise
    # decode with BOM handling
    try:
        text = raw.decode("utf-8-sig")
    except Exception:
        text = raw.decode("utf-8", errors="ignore")
    if not text.strip():
        return [], []
    # sniff delimiter from first non-empty lines
    sample = text[:4096]
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t", "|"])
        delimiter = dialect.delimiter
    except Exception:
        # fallback: count
        candidates = [",", ";", "\t", "|"]
        first_lines = [ln for ln in text.splitlines() if ln.strip()][:3]
        best = ","
        best_n = -1
        for d in candidates:
            n = sum(ln.count(d) for ln in first_lines)
            if n > best_n:
                best_n = n
                best = d
        delimiter = best if best_n > 0 else ","
    try:
        lines = text.splitlines()
        reader = csv.DictReader(lines, delimiter=delimiter)
        if not reader.fieldnames:
            return [], []
        # strip BOM char from first fieldname if present
        fns = [str(fn).lstrip("\ufeff").strip() for fn in reader.fieldnames]
        rows: List[Dict[str, Any]] = []
        for row in reader:
            if row is None:
                continue
            nd: Dict[str, Any] = {}
            for k, v in row.items():
                nk = str(k).lstrip("\ufeff").strip() if k else k
                nd[nk] = v
            # skip fully empty rows
            if not any((str(v or "").strip() for v in nd.values())):
                continue
            rows.append(nd)
        return fns, rows
    except Exception:
        return [], []


def build_event(channel: str, source_file: str, line: int, ts: datetime,
                order_id: str, product: str, qty: int, gmv: float,
                fees: float, shipping: float, customer: str, status: str,
                signal: str, currency: str) -> Dict[str, Any]:
    net = round(gmv - fees - shipping, 2)
    oid = order_id or f"line{line}"
    return {
        "timestamp": ts,
        "source": "orders",
        "entity_id": f"order:{channel}:{oid}:{line}",
        "value": gmv,
        "metadata": {
            "source_file": source_file,
            "line": line,
            "signal": signal,
            "product": product,
            "qty": qty,
            "gmv": gmv,
            "fees": fees,
            "shipping": shipping,
            "net": net,
            "customer": customer,
            "status": status,
            "citation": f"[{source_file}:{line}] {product} qty{qty} gmv${gmv} fees${fees} net${net:.2f}",
            "currency": currency,
            "channel": channel,
            "order_id": oid,
        },
    }
