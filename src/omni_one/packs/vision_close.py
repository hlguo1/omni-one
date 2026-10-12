"""Vision Close — photo -> OCR -> numbers -> COGS -> verdict + bundle (PACK B).

Deterministic, offline, $0. Wraps ``core/vision.analyze_photo`` with a
seller-flavoured close: per-line money extraction, unit-qty COGS hits,
top-number chart, trimmed pipeline evidence, rule-based verdict, 3
do-today actions, file:line citations, CSV + bundle writers.

Pipeline: bytes -> analyze_photo (Tesseract + OpenCV + Matplotlib +
mock pipeline, $0) -> OCR text (truncated 2000) -> lines -> numbers[]
(_money_last per line) -> cogs_lines[] (extract_unit_qty hits) ->
chart{labels, values} (top numbers) -> evidence[] (trimmed, no payloads)
-> verdict{label, rule, reason} -> do_today[3] + citations[filename:line].
Never raises on garbage: empty/corrupt bytes -> verdict=unreadable.

VERDICT RULES (in order): unreadable/no_text_no_numbers (blank OCR and no
numbers/chart); invoice-like/invoice_signals (numbers>=1 and score>=2 over
$ present, qty Nx pattern, invoice keyword, numbers>=2); chart-like/
chart_or_many_numbers (opencv is_chart or numbers>=3, not invoice-like);
photo/has_text_no_numbers (text but no amounts); unreadable/empty_fallback.

Privacy: blobs >=120 chars become [omitted]; full image payloads never
reach evidence, close.json, or logs. Tesseract/OpenCV/Matplotlib optional.
Intended wiring: `omni-one vision-close` + POST /api/v1/vision/close.
See core/vision.py:analyze_photo, packs/seller_os.py parsers.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# seller_parse helpers with a 10-line local regex fallback (same semantics:
# _money_last takes the LAST number; extract_unit_qty parses "<qty> x <unit>").
try:
    from .seller_parse import _money_last as _seller_money_last  # type: ignore
    from .seller_parse import extract_unit_qty as _seller_extract_unit_qty  # type: ignore
    _MONEY_LAST = _seller_money_last
    _EXTRACT_UNIT_QTY = _seller_extract_unit_qty
    _PARSER_SOURCE = "seller_parse"
except ImportError:
    try:
        from omni_one.packs.seller_parse import (  # type: ignore
            _money_last as _seller_money_last2,
            extract_unit_qty as _seller_extract_unit_qty2,
        )
        _MONEY_LAST = _seller_money_last2
        _EXTRACT_UNIT_QTY = _seller_extract_unit_qty2
        _PARSER_SOURCE = "seller_parse"
    except ImportError:
        def _MONEY_LAST(s: str) -> Optional[float]:  # type: ignore
            t = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", str(s or ""))
            t = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", t)
            ns = re.findall(r"\$?\s*(\d+(?:\.\d{1,2})?)", t.replace(",", ""))
            return float(ns[-1]) if ns else None
        def _EXTRACT_UNIT_QTY(line: str):  # type: ignore
            m = re.search(r"(\d+)\s*x\s*\$?\s*(\d+(?:[.,]\d+)?)", str(line), re.I)
            if not m:
                return None
            return (float(m.group(1)), float(m.group(2).replace(",", "")), float(_MONEY_LAST(line) or 0))
        _PARSER_SOURCE = "local_fallback"

# vision core — optional; degrade gracefully when absent.
try:
    from ..core.vision import analyze_photo as _analyze_photo  # type: ignore
    _VISION_SOURCE = "core.vision"
except ImportError:
    try:
        from omni_one.core.vision import analyze_photo as _analyze_photo  # type: ignore
        _VISION_SOURCE = "core.vision"
    except ImportError:
        _analyze_photo = None  # type: ignore
        _VISION_SOURCE = "none"

try:
    from ..core.vision import ocr_image as _ocr_image_fn  # type: ignore
except ImportError:
    try:
        from omni_one.core.vision import ocr_image as _ocr_image_fn  # type: ignore
    except ImportError:
        _ocr_image_fn = None  # type: ignore


__all__ = ["build_vision_close", "make_demo_image", "close_to_csv", "write_close_bundle"]

OCR_TRUNCATE_CHARS = 2000
EVIDENCE_TRIM_CHARS = 200
EVIDENCE_MAX_STEPS = 6
CHART_TOP_N = 6
LABEL_MAX_CHARS = 18
OMITTED = "[omitted]"

INVOICE_KEYWORDS = (
    "total", "receipt", "invoice", "subtotal", "sub total", "tax",
    "payment", "amount", "due", "balance", "shipping", "change",
    "tender", "store", "market", "thank",
)

_QTY_RE = re.compile(r"\d+\s*[xX\xd7]\s*\$?\s*\d", re.IGNORECASE)
_BLOB_RE = re.compile(r"^[A-Za-z0-9+/=\s]{120,}$")


def _trim(text: Any, limit: int = EVIDENCE_TRIM_CHARS) -> str:
    """Coerce to str, replace blob-looking strings with [omitted], trim."""
    s = "" if text is None else str(text)
    s = s.strip()
    if not s:
        return ""
    compact = re.sub(r"\s+", "", s)
    if len(compact) >= 120 and _BLOB_RE.match(s):
        return OMITTED
    if len(compact) >= 400 and len(s) >= 400:
        return OMITTED
    if len(s) > limit:
        return s[:limit] + "..."
    return s


def _sanitize_evidence_step(step: Any) -> str:
    """Flatten one pipeline evidence step to a trimmed, payload-free line."""
    if isinstance(step, dict):
        for key in ("citation", "reason", "signal", "summary", "text", "value"):
            if key in step and step[key] not in (None, ""):
                v = step[key]
                if isinstance(v, str) and len(re.sub(r"\s+", "", v)) >= 400:
                    return OMITTED
                return _trim(f"{key}={v}")
        try:
            rendered = json.dumps(step, default=str)[:500]
        except Exception:
            rendered = str(step)[:500]
        rendered = re.sub(r"[A-Za-z0-9+/=]{200,}", OMITTED, rendered)
        return _trim(rendered)
    if isinstance(step, (list, tuple)):
        parts = [_sanitize_evidence_step(p) for p in step[:3]]
        parts = [p for p in parts if p]
        return _trim(" | ".join(parts)) if parts else ""
    s = re.sub(r"[A-Za-z0-9+/=]{200,}", OMITTED, str(step))
    return _trim(s)


def _scrub_payload_word(obj: Any) -> Any:
    """Recursively replace payload blobs / long tokens with [omitted]."""
    if isinstance(obj, dict):
        return {k: _scrub_payload_word(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub_payload_word(v) for v in obj]
    if isinstance(obj, str):
        if len(re.sub(r"\s+", "", obj)) >= 400:
            return OMITTED
        return re.sub(r"[A-Za-z0-9+/=]{200,}", OMITTED, obj)
    return obj


def _split_lines(text: str) -> List[str]:
    """Split OCR text into non-empty stripped lines (1-indexed downstream)."""
    if not text or not text.strip():
        return []
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


def _label_for_line(text: str, fallback: str) -> str:
    """Short chart label: line stripped of currency/numbers, max 18 chars."""
    t = re.sub(r"[\$\u00a3\u20ac\u00a5]", " ", text)
    t = re.sub(r"\d+(?:[.,]\d+)?", " ", t)
    t = re.sub(r"\b[xX\xd7]\b", " ", t)
    t = re.sub(r"[^A-Za-z .\-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .-")
    if len(t) < 2:
        return fallback
    return t[:LABEL_MAX_CHARS].strip() or fallback


def _build_numbers(lines: List[str]) -> List[Dict[str, Any]]:
    """Per-line money via _money_last -> {line_no, text, amount}.

    Last-money wins so "50 x 4.00 200.00" yields 200.00. Deterministic.
    """
    out: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines, 1):
        try:
            amount = _MONEY_LAST(line)
        except Exception:
            amount = None
        if amount is None:
            continue
        try:
            amt = float(amount)
        except Exception:
            continue
        if amt != amt or amt in (float("inf"), float("-inf")):
            continue
        out.append({"line_no": idx, "text": line[:120], "amount": round(amt, 2)})
    return out


def _build_cogs_lines(lines: List[str], filename: str) -> List[Dict[str, Any]]:
    """Unit-qty hits via extract_unit_qty -> {line_no, text, qty, unit, ...}."""
    out: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines, 1):
        try:
            parsed = _EXTRACT_UNIT_QTY(line)
        except Exception:
            parsed = None
        if not parsed:
            continue
        try:
            qty, unit, total = float(parsed[0]), float(parsed[1]), float(parsed[2])
        except Exception:
            continue
        out.append({
            "line_no": idx, "text": line[:120], "qty": qty,
            "unit": round(unit, 2), "total": round(total, 2),
            "citation": f"{filename}:{idx}",
        })
    return out


def _build_chart(numbers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Top-number chart: labels/values by amount desc, cap 6, deduped."""
    if not numbers:
        return {"labels": [], "values": [], "source": "none", "top_n": 0}
    ranked = sorted(numbers, key=lambda n: n["amount"], reverse=True)[:CHART_TOP_N]
    labels = [_label_for_line(h["text"], f"Line {h['line_no']}") for h in ranked]
    values = [float(h["amount"]) for h in ranked]
    seen: set = set()
    ulabels: List[str] = []
    uvalues: List[float] = []
    for lb, vv in zip(labels, values):
        if lb.lower() in seen:
            continue
        seen.add(lb.lower())
        ulabels.append(lb)
        uvalues.append(vv)
    return {"labels": ulabels, "values": uvalues, "source": "top_numbers", "top_n": len(ulabels)}


def _invoice_score(text: str, numbers: List[Dict[str, Any]], has_qty: bool) -> Tuple[int, Dict[str, bool]]:
    """Invoice-likeness 0-4: $ present, qty Nx, keyword, numbers>=2."""
    low = (text or "").lower()
    signals = {
        "money_symbol": ("$" in (text or "") or "usd" in low),
        "qty_pattern": bool(has_qty),
        "invoice_keyword": any(kw in low for kw in INVOICE_KEYWORDS),
        "multi_numbers": len(numbers) >= 2,
    }
    return sum(1 for v in signals.values() if v), signals


def _decide_verdict(ocr_text: str, numbers: List[Dict[str, Any]],
                    cogs_lines: List[Dict[str, Any]], chart: Dict[str, Any],
                    chart_detected: bool) -> Dict[str, Any]:
    """Rule-based verdict {label, rule, reason}; see module VERDICT RULES."""
    stripped = (ocr_text or "").strip()
    values = chart.get("values", []) if isinstance(chart, dict) else []
    has_qty = len(cogs_lines) > 0 or bool(_QTY_RE.search(ocr_text or ""))
    if not stripped and not numbers and not values:
        return {"label": "unreadable", "rule": "no_text_no_numbers",
                "reason": "OCR text blank and no numbers or chart values extracted"}
    score, signals = _invoice_score(ocr_text or "", numbers, has_qty)
    if numbers and score >= 2:
        on = [k for k, v in signals.items() if v]
        return {"label": "invoice-like", "rule": "invoice_signals",
                "reason": f"invoice_score={score}/4 signals={','.join(on)} numbers={len(numbers)}"}
    if chart_detected or len(numbers) >= 3 or len(values) >= 3:
        why = "opencv_is_chart" if chart_detected else f"numbers={len(numbers)}"
        return {"label": "chart-like", "rule": "chart_or_many_numbers",
                "reason": f"{why} without invoice signals"}
    if stripped:
        return {"label": "photo", "rule": "has_text_no_numbers",
                "reason": f"OCR {len(stripped)} chars but no parseable amounts"}
    return {"label": "unreadable", "rule": "empty_fallback", "reason": "no OCR and no numbers"}


def _build_do_today(verdict_label: str, numbers: List[Dict[str, Any]],
                    cogs_lines: List[Dict[str, Any]]) -> List[str]:
    """Three deterministic next actions tailored to the verdict."""
    if verdict_label == "invoice-like":
        top = max((n["amount"] for n in numbers), default=0.0)
        cogs_hint = (f"({len(cogs_lines)} hits, e.g. qty {cogs_lines[0]['qty']:g} x ${cogs_lines[0]['unit']:.2f})"
                     if cogs_lines else "(no qty x unit hits — type supplier cost manually)")
        return [
            f"Verify receipt total ${top:.2f} against {len(numbers)} line amounts, then file photo by date.",
            f"Reconcile COGS from unit-qty lines {cogs_hint} into today's close.",
            "Log payment + snap a backup photo; flag any line whose total != qty x unit.",
        ]
    if verdict_label == "chart-like":
        return [
            f"Transcribe the top {min(len(numbers), 3)} chart values into today's sales sheet and sanity-check the max.",
            "Re-shoot the chart straight-on (no glare) so bars stay countable for tomorrow's close.",
            "Compare today's top bar vs yesterday's — note any swing over 20% with a one-line cause.",
        ]
    if verdict_label == "photo":
        return [
            "Retake the photo closer with flash off — current shot has text but no readable $ amounts.",
            "Type the 2-3 key amounts manually with filename:line citations for today's close.",
            "Keep the original photo; re-run vision-close after retake to auto-fill numbers.",
        ]
    return [
        "Retake the photo (fill frame, steady hands, flash off) — current bytes yielded no text.",
        "Type amounts manually for today's close; cite the paper receipt line numbers.",
        "If retakes stay unreadable, install Tesseract (brew install tesseract) and re-run — fallback stays $0 offline.",
    ]


def _build_citations(filename: str, numbers: List[Dict[str, Any]]) -> List[str]:
    """Citations as <filename>:<line_no> per numbers hit (deterministic)."""
    return [f"{filename}:{n['line_no']}" for n in numbers]


def _collect_evidence(raw: Optional[Dict[str, Any]], filename: str, lang: str) -> List[Dict[str, Any]]:
    """Trimmed pipeline evidence (payload-free, max 6 steps).

    Sources: OCR engine line, chart detection line, chart data line,
    preview-size line ([omitted], never the payload), plus up to 3
    pipeline sample_evidence steps. Every detail trimmed to 200 chars.
    """
    evidence: List[Dict[str, Any]] = []
    if not raw:
        evidence.append({"step": "vision_unavailable",
                         "detail": _trim("core.vision unavailable — parsers ran on empty text ($0 offline fallback)"),
                         "citation": f"{filename}:1"})
        return evidence[:EVIDENCE_MAX_STEPS]
    ocr_meta = (raw.get("ocr") or {}).get("meta", {}) if isinstance(raw.get("ocr"), dict) else {}
    engine = str(ocr_meta.get("engine", "none"))
    evidence.append({"step": "ocr",
                     "detail": _trim(f"tesseract lang={lang} engine={engine} chars={ocr_meta.get('chars', '?')} ($0 local)"),
                     "citation": f"{filename}:1"})
    chart = raw.get("chart") or {}
    detected = chart.get("detected", {}) if isinstance(chart, dict) else {}
    is_chart = bool(detected.get("is_chart")) if isinstance(detected, dict) else False
    reason = detected.get("reason", "?") if isinstance(detected, dict) else "?"
    evidence.append({"step": "chart_detect", "detail": _trim(f"is_chart={is_chart} reason={reason}"),
                     "citation": f"{filename}:chart"})
    data = chart.get("data") if isinstance(chart, dict) else None
    if isinstance(data, dict) and data.get("labels"):
        evidence.append({"step": "chart_data",
                         "detail": _trim(f"source={data.get('source', '?')} bars={len(data.get('labels', []))}"),
                         "citation": f"{filename}:chart"})
    preview_len = 0
    try:
        for key in ("generated_chart_base64", "chart_png", "image_data"):
            cand = chart.get(key) if isinstance(chart, dict) else None
            if isinstance(cand, str) and cand:
                preview_len = max(preview_len, len(cand))
    except Exception:
        preview_len = 0
    evidence.append({"step": "chart_preview",
                     "detail": OMITTED if preview_len else _trim("no preview generated (text-only close)"),
                     "citation": f"{filename}:chart"})
    try:
        pipe = raw.get("pipeline") or {}
        sample = pipe.get("sample_evidence", []) if isinstance(pipe, dict) else []
        flat: List[Any] = []
        if isinstance(sample, list):
            for entry in sample:
                flat.extend(entry) if isinstance(entry, list) else flat.append(entry)
        for entry in flat[:3]:
            detail = _sanitize_evidence_step(entry)
            if detail:
                evidence.append({"step": "pipeline", "detail": detail, "citation": f"{filename}:pipe"})
    except Exception:
        pass
    return evidence[:EVIDENCE_MAX_STEPS]


def build_vision_close(image_bytes: bytes, filename: str = "upload.png", lang: str = "eng") -> Dict[str, Any]:
    """Build a deterministic vision close from raw image bytes.

    Never raises on garbage: b"" / corrupt bytes -> verdict=unreadable.
    Returns meta, ocr (text truncated 2000 + lines), numbers[] ({line_no,
    text, amount} via _money_last), cogs_lines[] (extract_unit_qty hits),
    chart{labels, values} (top numbers), evidence[] (trimmed, no payloads),
    verdict{label, rule, reason}, do_today[3], citations[filename:line],
    totals, cost_usd ($0). Payload-free by construction.
    """
    started = datetime.now(timezone.utc)
    safe_name = (filename or "upload.png").strip() or "upload.png"
    safe_lang = (lang or "eng").strip() or "eng"
    n_bytes = len(image_bytes) if isinstance(image_bytes, (bytes, bytearray)) else 0

    if not isinstance(image_bytes, (bytes, bytearray)) or n_bytes == 0:
        raw: Optional[Dict[str, Any]] = {"ocr": {"text": "", "meta": {"engine": "none", "error": "empty input"}}}
        ocr_text = ""
        chart_detected = False
    else:
        payload = bytes(image_bytes)
        raw = None
        ocr_text = ""
        ocr_meta: Dict[str, Any] = {}
        try:
            if _analyze_photo is not None:
                raw = _analyze_photo(payload, filename=safe_name, run_pipeline=True)
            else:
                raw = None
        except Exception as exc:
            raw = {"ocr": {"text": "", "meta": {"engine": "none", "error": _trim(str(exc), 120)}},
                   "error": _trim(str(exc), 120)}
        try:
            if isinstance(raw, dict):
                ocr_block = raw.get("ocr", {})
                if isinstance(ocr_block, dict):
                    ocr_text = str(ocr_block.get("text", "") or "")
                    ocr_meta = ocr_block.get("meta", {}) if isinstance(ocr_block.get("meta"), dict) else {}
                elif isinstance(ocr_block, str):
                    ocr_text = ocr_block
        except Exception:
            ocr_text = ""
        if (not (ocr_text or "").strip()) and safe_lang != "eng" and _ocr_image_fn is not None:
            try:
                retry_text, retry_meta = _ocr_image_fn(payload, lang=safe_lang)
                if (retry_text or "").strip():
                    ocr_text = retry_text
                    ocr_meta = retry_meta if isinstance(retry_meta, dict) else {}
                    if isinstance(raw, dict):
                        raw["ocr"] = {"text": ocr_text, "meta": ocr_meta}
            except Exception:
                pass
        chart_detected = False
        try:
            chart_block = (raw.get("chart") or {}) if isinstance(raw, dict) else {}
            det = chart_block.get("detected", {}) if isinstance(chart_block, dict) else {}
            chart_detected = bool(det.get("is_chart")) if isinstance(det, dict) else False
        except Exception:
            chart_detected = False

    ocr_lines = _split_lines(ocr_text)
    ocr_trunc = (ocr_text or "")[:OCR_TRUNCATE_CHARS]
    numbers = _build_numbers(ocr_lines)
    cogs_lines = _build_cogs_lines(ocr_lines, safe_name)
    chart = _build_chart(numbers)
    if raw is None:
        chart_detected = False
    verdict = _decide_verdict(ocr_trunc, numbers, cogs_lines, chart, chart_detected)
    do_today = _build_do_today(verdict["label"], numbers, cogs_lines)
    citations = _build_citations(safe_name, numbers)
    evidence = _collect_evidence(raw, safe_name, safe_lang)
    amounts = [n["amount"] for n in numbers]
    totals = {
        "lines_with_amounts": len(numbers),
        "cogs_hits": len(cogs_lines),
        "sum_amounts": round(sum(amounts), 2) if amounts else 0.0,
        "max_amount": round(max(amounts), 2) if amounts else 0.0,
        "min_amount": round(min(amounts), 2) if amounts else 0.0,
    }
    engine_name = "none"
    try:
        if isinstance(raw, dict):
            meta_block = (raw.get("ocr") or {}).get("meta", {}) if isinstance(raw.get("ocr"), dict) else {}
            engine_name = str(meta_block.get("engine", "none"))
    except Exception:
        engine_name = "none"
    try:
        digest = hashlib.sha256(bytes(image_bytes) if isinstance(image_bytes, (bytes, bytearray)) else b"").hexdigest()[:16]
    except Exception:
        digest = "0" * 16
    close: Dict[str, Any] = {
        "meta": {"filename": safe_name, "bytes": n_bytes, "lang": safe_lang, "sha256": digest,
                 "generated_at": started.isoformat(), "engine": engine_name,
                 "vision_source": _VISION_SOURCE, "parser_source": _PARSER_SOURCE,
                 "cost_usd": 0.0, "free": True, "offline": True},
        "ocr": {"text": ocr_trunc, "lines": ocr_lines[:40], "chars": len(ocr_text or ""),
                "lines_count": len(ocr_lines), "truncated": len(ocr_text or "") > OCR_TRUNCATE_CHARS},
        "numbers": numbers,
        "cogs_lines": cogs_lines,
        "chart": chart,
        "evidence": evidence,
        "verdict": verdict,
        "do_today": do_today,
        "citations": citations,
        "totals": totals,
        "cost_usd": 0.0,
    }
    return _scrub_payload_word(close)  # type: ignore[return-value]


def _load_demo_font(size: int = 30):
    """Large TTF for OCR-legible fixtures (PIL only); default font fallback."""
    try:
        from PIL import ImageFont  # type: ignore
    except ImportError:
        return None
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        from PIL import ImageFont as _IF  # type: ignore
        return _IF.load_default()
    except Exception:
        return None


def make_demo_image(kind: str = "receipt") -> bytes:
    """Deterministic demo fixture: white 800x400 PNG, dark $ lines + 2 bars.

    PIL only (no Tesseract needed to GENERATE). kind="receipt" embeds
    "50 x 4.00 200.00" supplier-style lines; kind="chart" a minimal sales
    chart. Unknown kinds fall back to receipt. Returns raw PNG bytes.
    """
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Pillow not installed: pip install pillow (free)") from exc
    W, H = 800, 400
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    font = _load_demo_font(30)
    small = _load_demo_font(22) or font
    kind_norm = (kind or "receipt").strip().lower()
    if kind_norm == "chart":
        lines = ["SALES CHART Q3", "Tacos 30", "Burritos 12", "Drinks $45", "Total $87"]
    else:
        lines = ["ACME MARKET - RECEIPT", "Tote Bag Canvas 50 x 4.00 200.00",
                 "Shipping 1 x 15.00 15.00", "Tax $12.50", "Total $227.50"]
    y = 18
    for line in lines:
        try:
            draw.text((28, y), line, fill="black", font=font)
        except Exception:
            draw.text((28, y), line, fill="black")
        y += 44
    # Two solid bars near the baseline (OpenCV bar heuristic); below text.
    try:
        draw.rectangle([80, 300, 150, 360], fill="black", outline="black")
        draw.rectangle([230, 275, 300, 360], fill="black", outline="black")
        draw.line([40, 360, 700, 360], fill="black", width=3)
        try:
            draw.text((40, 368), "sales", fill="black", font=small)
        except Exception:
            pass
    except Exception:
        pass
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def close_to_csv(close: Dict[str, Any]) -> str:
    """numbers[] as CSV text (line_no,text,amount); RFC-4180 quoted, 2dp."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(["line_no", "text", "amount"])
    numbers = close.get("numbers", []) if isinstance(close, dict) else []
    for hit in numbers:
        try:
            line_no = int(hit.get("line_no", 0))
        except Exception:
            line_no = 0
        text = str(hit.get("text", ""))[:120]
        try:
            amount_s = f"{float(hit.get('amount', 0.0)):.2f}"
        except Exception:
            amount_s = "0.00"
        writer.writerow([line_no, text, amount_s])
    return output.getvalue()


def write_close_bundle(close: Dict[str, Any], out_dir: Any) -> Dict[str, str]:
    """Write 3 files: close.json + lines.csv + ocr.txt. Returns str paths.

    close.json is pretty-printed and payload-free (re-scrubbed). lines.csv
    always has a header. ocr.txt holds verbatim OCR or a non-empty fallback
    hint ($ context + Tesseract install note) when OCR came back empty.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    safe = _scrub_payload_word(close) if isinstance(close, dict) else {}
    if not isinstance(safe, dict):
        safe = {"numbers": [], "ocr": {"text": ""}}
    p_json = out / "close.json"
    p_csv = out / "lines.csv"
    p_txt = out / "ocr.txt"
    with open(p_json, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(p_csv, "w", encoding="utf-8", newline="") as f:
        f.write(close_to_csv(safe if isinstance(safe, dict) else {}))
    try:
        ocr_text = str((safe.get("ocr", {}) or {}).get("text", "") or "")
    except Exception:
        ocr_text = ""
    if not ocr_text.strip():
        try:
            meta_name = str((safe.get("meta", {}) or {}).get("filename", "upload.png"))
        except Exception:
            meta_name = "upload.png"
        ocr_text = (
            f"[no OCR text extracted from {meta_name} — fallback hint] "
            "No $ amounts readable. Retake photo (fill frame, flash off) or type "
            "amounts manually. Free OCR: brew install tesseract (macOS) / "
            "sudo apt-get install tesseract-ocr (Linux) + pip install pytesseract. $0 offline."
        )
    with open(p_txt, "w", encoding="utf-8") as f:
        f.write(ocr_text)
        if not ocr_text.endswith("\n"):
            f.write("\n")
    return {"close.json": str(p_json), "lines.csv": str(p_csv), "ocr.txt": str(p_txt)}
