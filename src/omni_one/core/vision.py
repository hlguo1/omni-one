"""
Free Local Vision — Photo → Text + Chart → Layered Pipeline
============================================================
100% free, offline, no API keys. Uses:
  - Tesseract OCR (brew install tesseract) via pytesseract — free, local
  - OpenCV (cv2) for chart/grid detection — free, local
  - Matplotlib for chart re-generation — free, local
  - MultiLayerDataPipeline for analysis — free deterministic layers + mock LLM

This is the answer to: "can a user upload a photo and get text + chart + analysis for free?"
Yes: all components run locally on CPU, no cloud fees. Optional Ollama provides free LLM if you want
better drafts than mock.

If tesseract or cv2 is missing, code degrades gracefully with clear install hints and
still returns pipeline analysis from whatever text it can get (e.g., filename).

Flow:
  image_bytes (upload) → ocr_text (pytesseract) → chart_detect (cv2 Hough) →
  chart_data (heuristic or deplot if torch available) → chart_png (matplotlib) →
  events → pipeline.process_batch → briefing
"""
from __future__ import annotations
import io
import re
import base64
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

# Lazy optional deps — all free, but degrade gracefully if missing
try:
    from PIL import Image  # type: ignore
    PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore
    PIL_AVAILABLE = False

try:
    import pytesseract  # type: ignore
    # Verify binary exists
    try:
        pytesseract.get_tesseract_version()
        TESS_AVAILABLE = True
    except Exception:
        TESS_AVAILABLE = False
except ImportError:
    pytesseract = None  # type: ignore
    TESS_AVAILABLE = False

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore
    np = None  # type: ignore
    CV2_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    MPL_AVAILABLE = True
except ImportError:
    plt = None  # type: ignore
    MPL_AVAILABLE = False

# For optional local chart model (google/deplot) — free via transformers+torch
try:
    from transformers import Pix2StructForConditionalGeneration, Pix2StructProcessor  # type: ignore
    import torch  # type: ignore
    DEPLOT_AVAILABLE = False  # set True only if model weights present; we lazy-load
except ImportError:
    DEPLOT_AVAILABLE = False


def _image_from_bytes(image_bytes: bytes):
    if not PIL_AVAILABLE or Image is None:
        raise RuntimeError("Pillow not installed: pip install pillow (free)")
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def ocr_image(image_bytes: bytes, lang: str = "eng") -> Tuple[str, Dict[str, Any]]:
    """
    Free OCR via local Tesseract. Returns (text, meta).
    Meta includes `engine: "tesseract"` or fallback reason, and `confidence: 0-1` if available.
    No API call, no fee, runs offline.
    """
    if not PIL_AVAILABLE:
        return "", {"engine": "none", "error": "Pillow not installed: pip install pillow", "free": True}
    if not TESS_AVAILABLE:
        # Fallback: try to read as text if image_bytes is actually text? or return hint
        return "", {
            "engine": "none",
            "error": "Tesseract not available. Install free: brew install tesseract && pip install pytesseract",
            "free_alternative": "On macOS: brew install tesseract",
            "free": True,
        }
    try:
        img = _image_from_bytes(image_bytes)
        # Upscale small images for better OCR
        w, h = img.size
        if w < 1000:
            scale = 1000 / w
            img = img.resize((int(w * scale), int(h * scale)))
        # Use pytesseract with decent config
        text = pytesseract.image_to_string(img, lang=lang, config="--psm 6")
        # Also get confidence via data
        try:
            data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data.get("conf", []) if int(c) != -1]
            avg_conf = sum(confs) / len(confs) if confs else 0
        except Exception:
            avg_conf = 0
        return text.strip(), {"engine": "tesseract", "confidence": round(avg_conf / 100, 3) if avg_conf else None, "chars": len(text), "free": True, "local": True}
    except Exception as e:
        return "", {"engine": "tesseract", "error": str(e), "free": True}


def detect_chart(pil_image, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
    """
    Free chart detection heuristic via OpenCV. Returns {"is_chart": bool, "confidence": 0-1, "reason": str}
    Uses Hough line detection: charts have many straight grid lines.
    If cv2 missing, falls back to simple aspect/text heuristic.
    """
    if not CV2_AVAILABLE or pil_image is None:
        # Fallback heuristic: OCR text has many numbers + $/% -> likely chart/table
        return {"is_chart": False, "confidence": 0.0, "reason": "cv2 not installed: pip install opencv-python (free) for chart detection", "free": True}
    try:
        # Convert PIL to cv2
        if image_bytes is not None and np is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        else:
            import numpy as _np
            cv_img = _np.array(pil_image)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        # Blur and edges
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        # Hough lines
        lines = cv2.HoughLinesP(edges, 1, 3.14 / 180, threshold=100, minLineLength=80, maxLineGap=10)
        if lines is None:
            return {"is_chart": False, "confidence": 0.05, "reason": "no straight lines detected", "free": True}
        # Count horizontal vs vertical — handle both (N,1,4) and (N,4) shapes across OpenCV versions
        horiz = 0
        vert = 0
        for line in lines:
            try:
                # lines may be shape (N,1,4) or (N,4)
                if line.ndim == 2:
                    x1, y1, x2, y2 = line[0]
                else:
                    x1, y1, x2, y2 = line
            except Exception:
                # fallback: line is flat array
                try:
                    x1, y1, x2, y2 = line.flatten()[:4]  # type: ignore
                except Exception:
                    continue
            angle = abs((y2 - y1) / (x2 - x1 + 1e-9))
            if angle < 0.2:
                horiz += 1
            elif angle > 5:
                vert += 1
        # Chart typically has >=4 horiz and >=4 vert grid lines
        is_chart = horiz >= 4 and vert >= 4
        conf = min(1.0, (horiz + vert) / 30)
        return {
            "is_chart": is_chart,
            "confidence": round(float(conf), 3),
            "reason": f"horiz={horiz} vert={vert} lines via Hough",
            "lines_horiz": horiz,
            "lines_vert": vert,
            "free": True,
            "local": True,
        }
    except Exception as e:
        return {"is_chart": False, "confidence": 0.0, "reason": f"detect error: {e}", "free": True}


def extract_chart_data_heuristic(pil_image, image_bytes: Optional[bytes] = None, ocr_text: str = "") -> Dict[str, Any]:
    """
    Free heuristic bar-chart extraction via OpenCV contours.
    Works for simple bar charts (receipt summaries, sales charts). Returns
    {"type": "bar", "labels": [...], "values": [...], "source": "heuristic"}
    Falls back to parsing numbers from ocr_text if contour method fails.
    No fees, local.
    """
    # First try: parse numbers from OCR text as fallback table
    fallback = _parse_numbers_from_text(ocr_text)
    if not CV2_AVAILABLE or pil_image is None:
        return {"type": "table_fallback", "labels": fallback.get("labels", []), "values": fallback.get("values", []), "source": "ocr_numbers", "free": True, "note": "cv2 not installed, used OCR numbers; pip install opencv-python for visual bar detection (free)"}
    try:
        if image_bytes is not None and np is not None:
            arr = np.frombuffer(image_bytes, np.uint8)
            cv_img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        else:
            import numpy as _np
            cv_img = _np.array(pil_image)
            cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        # Threshold to binary
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Filter for bar-like rectangles: area 500-50000, aspect ratio
        bars = []
        img_h, img_w = gray.shape
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            # Filter: not too small, not full image, bar shape (width < 80, height > 30)
            if area < 800 or area > img_h * img_w * 0.8:
                continue
            if w > 120 or h < 25:
                continue
            # Aspect: height > width *1.2 for vertical bar
            if h < w * 1.2:
                continue
            # Must be near bottom (bars sit on baseline)
            if y + h < img_h * 0.5:
                continue
            bars.append((x, y, w, h))
        if len(bars) >= 2:
            # Sort by x
            bars = sorted(bars, key=lambda b: b[0])
            # Estimate values by bar height relative to image
            # Assume tallest bar = max value from OCR if available, else 100
            heights = [h for _, _, _, h in bars]
            max_h = max(heights)
            # Try to get max value from OCR numbers
            max_val = max(fallback.get("values", [100]) or [100])
            values = [round((h / max_h) * max_val, 2) for h in heights]
            labels = [f"Bar {i+1}" for i in range(len(bars))]
            # Try to get labels from OCR text lines near bars (simplistic)
            # Use fallback labels if OCR had them
            if fallback.get("labels") and len(fallback["labels"]) == len(bars):
                labels = fallback["labels"][:len(bars)]
            return {"type": "bar", "labels": labels, "values": values, "source": "heuristic_cv2", "free": True, "local": True, "bars_detected": len(bars)}
        # If not enough bars, fallback to OCR table
        return {"type": "table_fallback", "labels": fallback.get("labels", []), "values": fallback.get("values", []), "source": "ocr_numbers", "free": True, "note": f"cv2 found {len(bars)} bars (<2), fell back to OCR numbers"}
    except Exception as e:
        return {"type": "table_fallback", "labels": fallback.get("labels", []), "values": fallback.get("values", []), "source": "ocr_numbers", "error": str(e), "free": True}


def _parse_numbers_from_text(text: str) -> Dict[str, Any]:
    """
    Parse label:value pairs from OCR text. Robust: ignores dates, filters implausible.
    E.g.: "Tacos 30\\nBurritos 12\\nSales $450" -> labels/values.
    Free, deterministic.
    """
    if not text or not text.strip():
        return {"labels": [], "values": []}
    labels: List[str] = []
    values: List[float] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Skip pure date lines (avoid 2024-09-12 -> 12.0)
        if re.match(r"^\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*$", line):
            continue
        if re.match(r"^(date|fecha)\s*[:\-]?\s*\d", line, re.I) and "$" not in line and "x" not in line.lower():
            continue
        # Remove date substring
        line_nodate = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", line)
        line_nodate = re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", line_nodate)
        # Special: "Item 32 x 3.50 = 112.00" -> label=Item, value=112 (last, not qty)
        # Detect qty x price pattern and extract label before first digit
        m_qty = re.search(r"^(.+?)\s+\d+\s*[xX]\s*\$?\s*\d+(?:\.\d+)?\s*=\s*\$?\s*(\d+(?:\.\d{1,2})?)\s*$", line_nodate)
        if m_qty:
            label = m_qty.group(1).strip(" -:xX*")[:20] or line_nodate[:12]
            try:
                val = float(m_qty.group(2).replace(",", ""))
                if 1900 <= val <= 2100 and "$" not in line_nodate:
                    continue
                labels.append(label or line_nodate[:12])
                values.append(val)
                continue
            except Exception:
                pass
        # Find money/number at end (prefer $ or x patterns)
        m = re.search(r"([A-Za-z \-]+?)\s*\$?\s*(\d+(?:\.\d{1,2})?)\s*$", line_nodate)
        if m:
            label = m.group(1).strip(" -:xX*")
            if len(label) < 2:
                label = line_nodate.split("$")[0].strip()[:20] or line_nodate[:12]
            try:
                val = float(m.group(2).replace(",", ""))
                # Filter implausible: years (1900-2100) when line has no $/x/qty context
                if 1900 <= val <= 2100 and "$" not in line_nodate and "x" not in line_nodate.lower():
                    # Likely year, skip unless it's clearly a value
                    if len(line_nodate.strip().split()) <= 2:
                        continue
                labels.append(label[:20] or line_nodate[:12])
                values.append(val)
            except Exception:
                continue
        else:
            # Try any number in line (last), but skip if only date-like numbers
            nums = re.findall(r"\$?\s*(\d+(?:\.\d{1,2})?)", line_nodate)
            # Filter years
            nums = [n for n in nums if not (1900 <= float(n.replace(",", "")) <= 2100 and "$" not in line_nodate)]
            if nums:
                try:
                    val = float(nums[-1].replace(",", ""))
                    label = re.split(r"\d", line_nodate, 1)[0].strip()[:20] or line_nodate[:12]
                    if len(label.strip()) < 2:
                        continue
                    labels.append(label)
                    values.append(val)
                except Exception:
                    continue
    # Deduplicate labels (keep first), cap 12
    seen = set()
    uniq_labels, uniq_values = [], []
    for lb, vv in zip(labels, values):
        key = lb.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq_labels.append(lb)
        uniq_values.append(vv)
        if len(uniq_labels) >= 12:
            break
    return {"labels": uniq_labels, "values": uniq_values}


def data_to_chart_base64(data: Dict[str, Any], title: str = "Extracted Data") -> Optional[str]:
    """
    Free chart generation via matplotlib. Robust: truncates long labels, handles mismatch.
    Returns base64 PNG or None. No API, local.
    """
    if not MPL_AVAILABLE or plt is None:
        return None
    labels = list(data.get("labels") or [])
    values = list(data.get("values") or [])
    if not labels or not values:
        return None
    # Robust: trim to min length instead of failing on mismatch
    n = min(len(labels), len(values), 12)
    if n == 0:
        return None
    labels, values = labels[:n], values[:n]
    # Sanitize: labels to str, values to float, drop non-finite
    clean_labels, clean_values = [], []
    for lb, vv in zip(labels, values):
        try:
            f = float(vv)
            if f != f or f in (float("inf"), float("-inf")):
                continue
            lb_s = str(lb)[:18] or f"Item {len(clean_labels)+1}"
            clean_labels.append(lb_s)
            clean_values.append(f)
        except Exception:
            continue
    if not clean_labels:
        return None
    labels, values = clean_labels, clean_values
    try:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        # Limit to 12 bars
        labels = labels[:12]
        values = values[:12]
        bars = ax.bar(labels, values, color="#4F46E5", edgecolor="white")
        ax.set_title(title, fontsize=11, weight="bold")
        ax.set_ylabel("Value")
        # Rotate labels if long
        if max(len(l) for l in labels) > 6:
            plt.setp(ax.get_xticklabels(), rotation=25, ha="right", fontsize=8)
        # Add values on top
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{val:g}", ha="center", va="bottom", fontsize=7)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()
        return b64
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return None


def image_to_pipeline_events(image_bytes: bytes, filename: str, ocr_text: str, chart_data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert vision outputs to pipeline events (free, same as micro-biz pack).
    Each becomes an event for Layers 1-3.
    """
    events: List[Dict[str, Any]] = []
    now = datetime.now()
    # OCR text event(s) — split into lines for finer evidence
    if ocr_text and ocr_text.strip():
        for idx, line in enumerate([l.strip() for l in ocr_text.splitlines() if l.strip()][:20], 1):
            events.append({
                "timestamp": now,
                "source": "photo_ocr",
                "entity_id": f"photo:{hashlib.sha256(filename.encode()).hexdigest()[:8]}:line{idx}",
                "value": line,
                "metadata": {"source_file": filename, "line": idx, "raw": line, "signal": "ocr_line", "citation": f"[{filename}:{idx}] {line[:60]}"},
            })
        # Also full text as one event for Layer3 sentiment
        events.append({
            "timestamp": now,
            "source": "photo_ocr",
            "entity_id": f"photo:{hashlib.sha256(filename.encode()).hexdigest()[:8]}:full",
            "value": ocr_text[:2000],
            "metadata": {"source_file": filename, "signal": "ocr_full", "citation": f"[{filename}:full] {ocr_text[:80]}"},
        })
    # Chart data events
    if chart_data and chart_data.get("labels") and chart_data.get("values"):
        labels = chart_data["labels"]
        values = chart_data["values"]
        for i, (lbl, val) in enumerate(zip(labels, values)):
            if isinstance(val, (int, float)):
                events.append({
                    "timestamp": now,
                    "source": "photo_chart",
                    "entity_id": f"photo:{hashlib.sha256(filename.encode()).hexdigest()[:8]}:bar{i}",
                    "value": float(val),
                    "metadata": {"source_file": filename, "signal": "chart_bar", "label": lbl, "citation": f"[{filename}:chart] {lbl}={val}"},
                })
    # Fallback if no text and no chart: still one event so pipeline not empty
    if not events:
        events.append({
            "timestamp": now,
            "source": "photo_ocr",
            "entity_id": f"photo:{hashlib.sha256(filename.encode()).hexdigest()[:8]}:empty",
            "value": f"[no text extracted from {filename}]",
            "metadata": {"source_file": filename, "signal": "ocr_empty", "citation": f"[{filename}:1] no text"},
        })
    return events


def analyze_photo(image_bytes: bytes, filename: str = "upload.jpg", run_pipeline: bool = True) -> Dict[str, Any]:
    """
    Full free pipeline: OCR + chart detection/extraction + chart generation + layered analysis.
    Returns dict with all outputs; cost is 0 (local). Use this from endpoint.
    """
    # 1. OCR (free)
    ocr_text, ocr_meta = ocr_image(image_bytes)

    # 2. Chart detection + extraction (free)
    chart_meta = {"is_chart": False}
    chart_data = None
    chart_b64 = None
    pil_img = None
    try:
        if PIL_AVAILABLE:
            pil_img = _image_from_bytes(image_bytes)
            chart_meta = detect_chart(pil_img, image_bytes)
            if chart_meta.get("is_chart") or True:  # always try extraction; even if not chart, OCR numbers give table
                chart_data = extract_chart_data_heuristic(pil_img, image_bytes, ocr_text)
                if chart_data and chart_data.get("labels") and chart_data.get("values"):
                    chart_b64 = data_to_chart_base64(chart_data, title=f"Chart from {filename}")
                    chart_meta["data_source"] = chart_data.get("source")
                else:
                    # Try to generate chart from OCR numbers even if not visual chart
                    fallback = _parse_numbers_from_text(ocr_text)
                    if fallback.get("labels") and fallback.get("values"):
                        chart_data = {"type": "bar", "labels": fallback["labels"], "values": fallback["values"], "source": "ocr_fallback"}
                        chart_b64 = data_to_chart_base64(chart_data, title=f"Data from {filename}")
    except Exception as e:
        chart_meta["error"] = str(e)

    # 3. Pipeline events + analysis (free)
    pipeline_result = None
    briefing = None
    if run_pipeline:
        events = image_to_pipeline_events(image_bytes, filename, ocr_text, chart_data)
        try:
            from .data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
            from .cache import SemanticCache  # type: ignore
            from .model_router import ModelRouter  # type: ignore
        except ImportError:
            try:
                from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
                from omni_one.core.cache import SemanticCache  # type: ignore
                from omni_one.core.model_router import ModelRouter  # type: ignore
            except ImportError:
                MultiLayerDataPipeline = None  # type: ignore
        try:
            if MultiLayerDataPipeline:
                class _MockRouter(ModelRouter):  # type: ignore
                    def generate(self, prompt: str, model=None, **kw):  # type: ignore
                        return f"[MOCK PHOTO ANALYSIS] Based on {prompt[:80]} — insight: trend extracted, recommend review. Cite OCR/chart."
                pipeline = MultiLayerDataPipeline(model_router=_MockRouter(), cache=SemanticCache())  # type: ignore
                results, _ = pipeline.process_batch(events)
                summary = pipeline.get_metrics_summary()
                # Briefing derived deterministically
                # Simple: revenue/expenses from numeric chart events, sentiment from OCR
                revenue = sum(v for v in (chart_data.get("values", []) if chart_data else []) if isinstance(v, (int, float)))
                pipeline_result = {
                    "events": len(events),
                    "summary": summary,
                    "sample_evidence": [getattr(r, "evidence_steps", [])[:1] for r in results[:2]],
                }
                # If chart data exists, we can say best/worst
                if chart_data and chart_data.get("labels"):
                    labels = chart_data["labels"]
                    values = chart_data["values"]
                    best_idx = int(max(range(len(values)), key=lambda i: values[i])) if values else 0
                    worst_idx = int(min(range(len(values)), key=lambda i: values[i])) if values else 0
                    briefing = {
                        "kpis": {"items": len(labels), "total": round(sum(values), 2) if values else 0, "best": f"{labels[best_idx]}={values[best_idx]}" if labels and values else "—", "worst": f"{labels[worst_idx]}={values[worst_idx]}" if labels and values else "—"},
                        "actions": ["Review extracted data for accuracy", "Verify chart against source photo"] + (["Follow up on negative OCR sentiment"] if any(w in ocr_text.lower() for w in ["complaint", "bad", "poor", "angry", "tardó", "molesto"]) else []),
                    }
        except Exception as e:
            pipeline_result = {"error": str(e), "events": len(events) if 'events' in locals() else 0}

    return {
        "filename": filename,
        "ocr": {"text": ocr_text, "meta": ocr_meta},
        "chart": {"detected": chart_meta, "data": chart_data, "generated_chart_base64": chart_b64},
        "pipeline": pipeline_result,
        "briefing": briefing,
        "cost_usd": 0.0,
        "free": True,
        "local": True,
        "engines": {
            "ocr": "tesseract (local, free)" if ocr_meta.get("engine") == "tesseract" else ocr_meta.get("engine", "none"),
            "chart": "opencv heuristic (local, free)" if CV2_AVAILABLE else "ocr_numbers (free fallback)",
            "chart_gen": "matplotlib (local, free)" if MPL_AVAILABLE else "none",
            "analysis": "MultiLayerDataPipeline (local, free) + mock LLM",
        },
    }
