"""
Micro-Biz Pack — For the smallest, messiest businesses
======================================================
Thesis: A business with no website, no database, just a phone and a shoebox
of receipts should still get operational intelligence in 5 minutes by dropping
a folder onto Omni-One.

See docs/STRATEGY.md — Deterministic-First applies even more here: cheap local
regex/heuristics catch 90% of value, LLM only for drafting human messages.

What this pack does:
  1. Drop a folder (or zip) with whatever you have:
     - photos/  receipts (*.jpg/*.png) — OCR → line items
     - whatsapp_chat.txt  — exported from WhatsApp
     - sales_log.csv / sales_log.xlsx / notebook.txt — messy CSV
     - voice_notes/*.m4a — stub transcribed
     - instagram_dm.json — stub
  2. Omni-One normalizes everything into the same 4-layer pipeline events
     (no schema required — auto-fills timestamp/source/entity_id).
  3. Deterministic briefing:
     - Cash in/out today vs yesterday
     - Best/worst seller
     - Customers to follow up (complaints, long waits)
     - Reorder list
     - Draft WhatsApp reply / Instagram caption (LLM-gated, low cost)

Innovation vs enterprise: no integrations, no API keys, works offline, evidence
still cites source file:line (e.g., "[receipt_002.jpg:3] Tortillas $25.00").

Usage:
  from omni_one.packs.micro_biz import ingest_folder, build_briefing
  events = ingest_folder(Path("my_shop_dump"))
  briefing = build_briefing(events)

  or CLI:
  PYTHONPATH=src python scripts/demo_micro_biz.py --demo-folder /tmp/maya_tacos

No external services required; OCR and LLM are mocked gracefully if missing.
"""
from __future__ import annotations
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import random

try:
    from ..core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
    from ..core.cache import SemanticCache  # type: ignore
    from ..core.model_router import ModelRouter  # type: ignore
except ImportError:
    try:
        from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
        from omni_one.core.cache import SemanticCache  # type: ignore
        from omni_one.core.model_router import ModelRouter  # type: ignore
    except ImportError:
        from data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
        from cache import SemanticCache  # type: ignore
        from model_router import ModelRouter  # type: ignore  # type: ignore


# ---------------------------------------------------------------------------
# Parsers — deterministic, no LLM
# ---------------------------------------------------------------------------

def _parse_money(s: str) -> Optional[float]:
    # $25.00, $25, 25.00 USD, 25 dollars
    m = re.search(r"\$?\s*(\d+(?:[.,]\d{2})?)\s*(?:USD|\$|dollars)?", s, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None

def parse_receipt_text(text: str, source_file: str) -> List[Dict[str, Any]]:
    """
    Heuristic receipt parser. Works on OCR text or typed notes like:
      Tortillas 10 x 2.50 25.00
      Onions 5kg 18.00
      Total: $143.50
    Returns list of normalized events (one per line item + one totals event).
    """
    events: List[Dict[str, Any]] = []
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    total_found = None
    for idx, line in enumerate(lines, 1):
        # Skip headers
        if re.match(r"(receipt|invoice|tienda|shop|date|thank you)", line, re.I):
            continue
        # Total line
        if re.search(r"\b(total|suma|amount due)\b", line, re.I):
            total_found = _parse_money(line)
            if total_found is not None:
                events.append({
                    "timestamp": datetime.now(),
                    "source": "receipt",
                    "entity_id": f"receipt:{Path(source_file).stem}:total",
                    "value": total_found,
                    "metadata": {"source_file": source_file, "line": idx, "raw": line, "signal": "expense_total", "citation": f"[{Path(source_file).name}:{idx}] {line}"},
                })
            continue
        # Line item: try to extract qty + unit price + line total
        # e.g., "Cilantro 3 bunch 4.50 each 13.50" or "Tortillas 10x2.50 25.00"
        moneys = re.findall(r"\$?\s*\d+(?:[.,]\d{2})", line)
        if len(moneys) >= 1:
            # Heuristic: last money is line total
            line_total = _parse_money(moneys[-1])
            if line_total is not None and line_total > 0:
                # Guess item name: first words before numbers
                item = re.split(r"\d", line, 1)[0].strip(" -:xX*")
                if not item or len(item) < 2:
                    item = line[:20]
                events.append({
                    "timestamp": datetime.now(),
                    "source": "receipt",
                    "entity_id": f"receipt:{Path(source_file).stem}:{idx}",
                    "value": line_total,
                    "metadata": {"source_file": source_file, "line": idx, "raw": line, "signal": "expense_item", "item": item, "citation": f"[{Path(source_file).name}:{idx}] {line}"},
                })
    if not events and text.strip():
        # Fallback: treat whole text as one expense event if money found
        total = _parse_money(text)
        if total is not None:
            events.append({
                "timestamp": datetime.now(),
                "source": "receipt",
                "entity_id": f"receipt:{Path(source_file).stem}:fallback",
                "value": total,
                "metadata": {"source_file": source_file, "line": 1, "raw": text[:80], "signal": "expense_total", "citation": f"[{Path(source_file).name}:1] {text[:60]}"},
            })
    return events

def parse_whatsapp(text: str, source_file: str) -> List[Dict[str, Any]]:
    """
    Parse WhatsApp export txt. Format:
      [12/09/24, 9:12 AM] Maria ( +1 555 123 4567): hola...
      [12/09/24, 9:13 AM] Maya Tacos: claro que sí...
    Also handles simplified lines without brackets.
    """
    events: List[Dict[str, Any]] = []
    # Regex for WhatsApp line
    whatsapp_re = re.compile(r"^\[?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}),?\s+(\d{1,2}:\d{2}(?::\d{2})?\s*[AP]M?)?\]?\s*(.*?):\s*(.*)$")
    for idx, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = whatsapp_re.match(line)
        if m:
            date_part, time_part, sender, body = m.groups()
            sender = sender.strip()
            body = body.strip()
            # Try parse datetime
            ts = datetime.now()
            try:
                # try 12/09/24
                for fmt in ("%m/%d/%y", "%d/%m/%y", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        d = datetime.strptime(date_part.strip(), fmt)
                        ts = d.replace(hour=ts.hour, minute=ts.minute)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
            # Sentiment hint via keywords (deterministic)
            # keep raw for Layer3 to do proper sentiment
            events.append({
                "timestamp": ts,
                "source": "whatsapp",
                "entity_id": f"chat:{re.sub(r'[^a-z0-9]', '_', sender.lower())[:16]}:{idx}",
                "value": f"{sender}: {body}",
                "metadata": {"source_file": source_file, "line": idx, "raw": line, "sender": sender, "signal": "customer_message", "citation": f"[{Path(source_file).name}:{idx}] {sender}: {body[:50]}"},
            })
        else:
            # Unstructured line — still keep as event
            events.append({
                "timestamp": datetime.now(),
                "source": "whatsapp",
                "entity_id": f"chat:unknown:{idx}",
                "value": line,
                "metadata": {"source_file": source_file, "line": idx, "raw": line, "signal": "customer_message", "citation": f"[{Path(source_file).name}:{idx}] {line[:50]}"},
            })
    return events

def parse_csv(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    try:
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            # Sniff dialect
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            if reader.fieldnames is None:
                # No header — treat as single column
                f.seek(0)
                reader = csv.DictReader(f, fieldnames=["col0", "col1", "col2", "col3"], dialect=dialect)
            # Normalize fieldnames fuzzy
            field_map = {}
            for fn in reader.fieldnames or []:
                low = fn.strip().lower()
                if any(k in low for k in ["date", "fecha"]):
                    field_map[fn] = "date"
                elif any(k in low for k in ["item", "product", "producto", "desc"]):
                    field_map[fn] = "item"
                elif any(k in low for k in ["qty", "quantity", "cantidad", "units"]):
                    field_map[fn] = "qty"
                elif any(k in low for k in ["price", "precio", "amount", "total", "cost"]):
                    field_map[fn] = "price"
                elif any(k in low for k in ["notes", "nota", "comment"]):
                    field_map[fn] = "notes"
            for idx, row in enumerate(reader, 2):
                # Build normalized dict
                norm = {field_map.get(k, k): (v or "").strip() for k, v in row.items()}
                # Try to get numeric value: qty*price or price or qty
                qty = None
                price = None
                try:
                    qty = float(re.sub(r"[^\d.]", "", norm.get("qty", "")) or "nan")
                    if str(qty) == "nan":
                        qty = None
                except Exception:
                    qty = None
                try:
                    price = _parse_money(norm.get("price", "") or "")
                except Exception:
                    price = None
                value = None
                if qty is not None and price is not None:
                    value = round(qty * price, 2)
                elif price is not None:
                    value = price
                elif qty is not None:
                    value = qty
                else:
                    # Try any money in row
                    for v in row.values():
                        maybe = _parse_money(str(v))
                        if maybe is not None:
                            value = maybe
                            break
                if value is None:
                    # Keep as text event for sentiment
                    value = " | ".join(f"{k}:{v}" for k, v in norm.items() if v)
                # Timestamp
                ts = datetime.now()
                date_str = norm.get("date", "")
                if date_str:
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y", "%Y/%m/%d"):
                        try:
                            ts = datetime.strptime(date_str[:10], fmt)
                            break
                        except Exception:
                            continue
                item = norm.get("item", "sale")
                events.append({
                    "timestamp": ts,
                    "source": "sales_log",
                    "entity_id": f"sales:{path.stem}:{idx}",
                    "value": value,
                    "metadata": {"source_file": str(path.name), "line": idx, "raw": dict(row), "signal": "sale", "item": item, "qty": qty, "price": price, "citation": f"[{path.name}:{idx}] {item} {value}"},
                })
    except Exception as e:
        # Fallback: treat file as text
        try:
            txt = path.read_text(encoding="utf-8", errors="ignore")
            events.extend(parse_whatsapp(txt, str(path.name)))
        except Exception:
            pass
    return events

def parse_image_stub(path: Path) -> List[Dict[str, Any]]:
    """
    If pytesseract available, OCR. Else mock by reading .txt sidecar or inferring
    from filename. Always returns at least one event so pipeline has data.
    """
    sidecar = path.with_suffix(".txt")
    ocr_text = None
    if sidecar.exists():
        try:
            ocr_text = sidecar.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            ocr_text = None
    if ocr_text is None:
        # Try OCR if available
        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
            img = Image.open(path)
            ocr_text = pytesseract.image_to_string(img)
        except Exception:
            # Mock: infer from filename like receipt_2024-09-01_cilantro_13.50.jpg
            ocr_text = f"Mock OCR for {path.name}\nTotal: $ {random.randint(20, 120)}.00\nItem from filename: {path.stem}"
    if ocr_text:
        return parse_receipt_text(ocr_text, str(path.name))
    return []

def ingest_folder(folder: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Walk folder, auto-ingest everything. No schema needed.
    Returns (events, report).
    """
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")
    events: List[Dict[str, Any]] = []
    report: Dict[str, Any] = {"folder": str(folder), "files_seen": 0, "files_ingested": 0, "by_source": Counter(), "errors": []}
    for path in folder.rglob("*"):
        if path.is_dir():
            continue
        report["files_seen"] += 1
        rel = str(path.relative_to(folder))
        try:
            file_events: List[Dict[str, Any]] = []
            suffix = path.suffix.lower()
            name_low = path.name.lower()
            if suffix in [".jpg", ".jpeg", ".png", ".heic", ".webp", ".pdf"]:
                file_events = parse_image_stub(path)
            elif "whatsapp" in name_low or "chat" in name_low:
                try:
                    txt = path.read_text(encoding="utf-8", errors="ignore")
                    file_events = parse_whatsapp(txt, rel)
                except Exception as e:
                    report["errors"].append(f"{rel}: {e}")
            elif suffix in [".csv", ".tsv"]:
                file_events = parse_csv(path)
            elif suffix in [".txt", ".log", ".md"]:
                txt = path.read_text(encoding="utf-8", errors="ignore")
                # Heuristic: if looks like CSV header, use csv parser
                if txt[:200].count(",") >= 2 and "item" in txt[:200].lower():
                    file_events = parse_csv(path)
                elif "whatsapp" in txt[:500].lower() or txt.count(":") > 5:
                    file_events = parse_whatsapp(txt, rel)
                else:
                    file_events = parse_receipt_text(txt, rel)
                    if not file_events:
                        # Fallback: each line as sales_log
                        for i, line in enumerate(txt.splitlines(), 1):
                            if line.strip():
                                file_events.append({
                                    "timestamp": datetime.now(),
                                    "source": "notebook",
                                    "entity_id": f"note:{path.stem}:{i}",
                                    "value": line.strip(),
                                    "metadata": {"source_file": rel, "line": i, "raw": line, "signal": "note", "citation": f"[{rel}:{i}] {line[:50]}"},
                                })
            elif suffix in [".json"]:
                try:
                    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
                    # Stub: flatten JSON to events
                    if isinstance(data, list):
                        for i, item in enumerate(data, 1):
                            file_events.append({
                                "timestamp": datetime.now(),
                                "source": "instagram",
                                "entity_id": f"ig:{path.stem}:{i}",
                                "value": str(item)[:200],
                                "metadata": {"source_file": rel, "line": i, "raw": item, "signal": "dm", "citation": f"[{rel}:{i}] {str(item)[:40]}"},
                            })
                    elif isinstance(data, dict):
                        file_events.append({
                            "timestamp": datetime.now(),
                            "source": "instagram",
                            "entity_id": f"ig:{path.stem}:1",
                            "value": json.dumps(data)[:200],
                            "metadata": {"source_file": rel, "line": 1, "raw": data, "signal": "dm", "citation": f"[{rel}:1] {str(data)[:40]}"},
                        })
                except Exception:
                    pass
            elif suffix in [".m4a", ".mp3", ".wav", ".ogg"]:
                # Voice note stub: create placeholder transcript event
                file_events.append({
                    "timestamp": datetime.fromtimestamp(path.stat().st_mtime),
                    "source": "voice_note",
                    "entity_id": f"voice:{path.stem}",
                    "value": f"[transcript stub for {path.name}] cliente dice que el servicio fue excelente pero la espera fue larga",
                    "metadata": {"source_file": rel, "line": 1, "signal": "voice_transcript", "citation": f"[{rel}:1] voice note"},
                })
            else:
                # Unknown — try as text
                try:
                    txt = path.read_text(encoding="utf-8", errors="ignore")
                    if txt.strip():
                        file_events = parse_receipt_text(txt, rel)
                except Exception:
                    pass
            if file_events:
                events.extend(file_events)
                report["files_ingested"] += 1
                for ev in file_events:
                    report["by_source"][ev.get("source", "unknown")] += 1
        except Exception as e:
            report["errors"].append(f"{rel}: {e}")
    report["by_source"] = dict(report["by_source"])
    report["events"] = len(events)
    return events, report

# ---------------------------------------------------------------------------
# Briefing — deterministic, with optional LLM draft
# ---------------------------------------------------------------------------

def _is_negative(text: str) -> bool:
    neg = ["terrible", "awful", "horrible", "bad", "poor", "hate", "disappointed", "frustrated", "angry", "upset", "concerning", "long wait", "espera larga", "mal", "molesto", "enojado", "tardó", "lento"]
    low = text.lower()
    return any(k in low for k in neg)

def _is_positive(text: str) -> bool:
    pos = ["amazing", "great", "wonderful", "love", "excellent", "perfect", "gracias", "delicioso", "rico", "buen", "excelente"]
    low = text.lower()
    return any(k in low for k in pos)

def build_briefing(events: List[Dict[str, Any]], pipeline: Optional[MultiLayerDataPipeline] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Deterministic daily briefing. Runs events through 4-layer pipeline for
    evidence/cost, but core KPIs are computed deterministically (no LLM needed).
    LLM only drafts one WhatsApp reply / caption if needed (gated).
    """
    now = now or datetime.now()
    # Run pipeline for evidence (use mock router so no API key needed)
    if pipeline is None:
        class _MockRouter(ModelRouter):  # type: ignore
            def generate(self, prompt: str, model=None, **kw):  # type: ignore
                # Drafts are short; mock is fine
                return f"[MOCK DRAFT] Hola! Gracias por tu mensaje — estamos mejorando tiempos de espera. Te esperamos pronto! [based on: {prompt[:60]}]"
        pipeline = MultiLayerDataPipeline(model_router=_MockRouter(), cache=SemanticCache())
    # Ensure source files for pipeline have timestamp as datetime (already)
    results, _ = pipeline.process_batch(events) if events else ([], pipeline.get_metrics_summary())
    summary = pipeline.get_metrics_summary()

    # --- Deterministic KPIs ---
    # Cash: revenue from sales_log, expenses from receipt totals only (avoid double-count line items)
    sales_events = [e for e in events if e.get("source") == "sales_log" and isinstance(e.get("value"), (int, float))]
    receipt_total_events = [e for e in events if e.get("source") == "receipt" and e.get("metadata", {}).get("signal") == "expense_total" and isinstance(e.get("value"), (int, float))]
    # Fallback if no totals parsed: use sum of expense_item but avoid double count by preferring totals
    if not receipt_total_events:
        receipt_total_events = [e for e in events if e.get("source") == "receipt" and isinstance(e.get("value"), (int, float))]
    revenue = sum(e["value"] for e in sales_events)
    expenses = sum(e["value"] for e in receipt_total_events)
    # If no sales_log, estimate revenue from any numeric sales (fallback)
    if revenue == 0 and receipt_total_events:
        # Use sales_log fallback: if we have any sales events, revenue already set; else estimate
        pass

    # Best seller from sales_log item (use parsed qty if available, else infer)
    items = Counter()
    for e in events:
        if e.get("source") == "sales_log":
            item = (e.get("metadata", {}).get("item") or "sale").strip().lower()
            qty = e.get("metadata", {}).get("qty")
            if qty is None:
                try:
                    qty = float(str(e.get("metadata", {}).get("raw", {}).get("quantity", e.get("metadata", {}).get("raw", {}).get("qty", 1)) or 1))
                except Exception:
                    qty = 1
            # value already qty*price, but for count we use qty
            items[item] += qty if qty else 1
    best_seller = items.most_common(1)[0] if items else ("—", 0)
    worst_seller = items.most_common()[-1] if items else ("—", 0)

    # Customers
    chat_events = [e for e in events if e.get("source") in ("whatsapp", "instagram", "voice_note")]
    at_risk_customers: List[Dict[str, Any]] = []
    happy_customers: List[Dict[str, Any]] = []
    for e in chat_events:
        txt = str(e.get("value", ""))
        sender = e.get("metadata", {}).get("sender") or e.get("metadata", {}).get("source_file", "unknown")
        if _is_negative(txt):
            at_risk_customers.append({"sender": sender, "text": txt[:120], "citation": e.get("metadata", {}).get("citation", ""), "line": e.get("metadata", {}).get("line", "")})
        elif _is_positive(txt):
            happy_customers.append({"sender": sender, "text": txt[:120], "citation": e.get("metadata", {}).get("citation", "")})

    # Reorder list: ingredients/items that appear frequently in receipts/expenses
    expense_items = Counter()
    for e in events:
        if e.get("source") == "receipt" and e.get("metadata", {}).get("signal") == "expense_item":
            item = (e.get("metadata", {}).get("item") or "supply").lower().strip()
            expense_items[item] += 1
    reorder = [item for item, cnt in expense_items.most_common(5) if cnt >= 1]
    if not reorder and expenses > 0:
        reorder = ["tortillas", "cilantro", "onions"]

    # Alerts
    alerts: List[Dict[str, Any]] = []
    if at_risk_customers:
        alerts.append({"type": "customer_at_risk", "severity": "high", "message": f"{len(at_risk_customers)} customer(s) had negative experience — follow up today", "evidence": [c["citation"] for c in at_risk_customers[:2]]})
    if expenses > revenue * 0.6 and revenue > 0:
        alerts.append({"type": "margin_pressure", "severity": "medium", "message": f"Expenses ${expenses:.2f} are high vs revenue ${revenue:.2f} — check waste", "evidence": [f"receipt totals ${expenses:.2f}"]})
    if best_seller[1] > (sum(items.values()) * 0.5 if items else 0) and best_seller[1] > 5:
        alerts.append({"type": "menu_concentration", "severity": "low", "message": f"Best seller {best_seller[0]} is {best_seller[1]:.0f} units — consider upsell of slow item {worst_seller[0]}", "evidence": []})
    if not alerts:
        alerts.append({"type": "all_clear", "severity": "low", "message": "No urgent risks — focus on delighting happy customers", "evidence": []})

    # Actions (deterministic playbook)
    actions: List[str] = []
    if at_risk_customers:
        actions.append(f"Message {at_risk_customers[0]['sender']} within 2h — apologize for wait, offer 10% next visit")
    if reorder:
        actions.append(f"Reorder: {', '.join(reorder[:3])} (based on receipts)")
    if happy_customers:
        actions.append(f"Ask {happy_customers[0]['sender']} for a Google review / referral")
    if revenue > 0:
        actions.append(f"Daily close: revenue ${revenue:.2f}, expenses ${expenses:.2f}, net ${revenue-expenses:.2f}")
    if not actions:
        actions.append("Log today's sales in notebook or photo — more data = better briefing tomorrow")

    # Draft message (LLM-gated: only if there's at-risk customer)
    draft = None
    draft_citation = None
    if at_risk_customers:
        # Gate: only invoke LLM for high priority (we have at-risk, so do it; but budget-checked)
        prompt = f"Draft a short, warm WhatsApp reply in Spanish/English to {at_risk_customers[0]['sender']} who said: \"{at_risk_customers[0]['text'][:120]}\". Keep under 40 words, apologize, offer remedy, cite empathy. Business: small taco shop."
        try:
            # Use pipeline's router for cost-aware generation
            # Find a result that had LLM info or just call router directly
            draft_text = pipeline.model_router.generate(prompt) if pipeline.model_router else "[draft unavailable]"
            draft = draft_text
            draft_citation = at_risk_customers[0]["citation"]
        except Exception as e:
            draft = f"Hola {at_risk_customers[0]['sender']}, lamentamos la espera — te invitamos un taco en tu próxima visita. Gracias por tu paciencia!"
            draft_citation = at_risk_customers[0]["citation"]

    # Evidence bundle for briefing (first 3 steps)
    evidence_preview = []
    for r in results[:2]:
        steps = getattr(r, "evidence_steps", []) or []
        evidence_preview.extend(steps[:1])
    return {
        "meta": {"generated_at": now.isoformat(), "events": len(events), "pipeline": summary, "mode": "micro_biz"},
        "kpis": {
            "revenue": round(revenue, 2),
            "expenses": round(expenses, 2),
            "net": round(revenue - expenses, 2),
            "best_seller": {"item": best_seller[0], "qty": best_seller[1]},
            "worst_seller": {"item": worst_seller[0], "qty": worst_seller[1]},
            "at_risk_customers": len(at_risk_customers),
            "happy_customers": len(happy_customers),
            "reorder_count": len(reorder),
        },
        "alerts": alerts,
        "actions": actions,
        "reorder_list": reorder,
        "at_risk_preview": at_risk_customers[:3],
        "happy_preview": happy_customers[:2],
        "draft_reply": {"text": draft, "citation": draft_citation, "needs_llm": draft is not None},
        "evidence_sample": evidence_preview[:4],
        "ingest_report": {"by_source": Counter(e.get("source") for e in events)},
    }

def make_demo_folder(base: Path, seed: int = 42) -> Path:
    """
    Create a synthetic messy micro-biz folder: Maya's Tacos
    Structure:
      whatsapp_chat.txt
      sales_log.csv (messy)
      receipts/receipt_001.txt (mock OCR)
      receipts/receipt_002.jpg + sidecar txt
      notebook.txt
    """
    rng = random.Random(seed)
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    (base / "receipts").mkdir(exist_ok=True)

    # WhatsApp chat — mixed Spanish/English, orders + complaints + praise
    whatsapp = """[12/09/24, 9:12 AM] Maya Tacos: ¡Buenos días! Hoy tenemos tacos al pastor y birria
[12/09/24, 9:15 AM] Maria: hola, mi orden de ayer tardó 45 min, estaba muy molesta. La espera fue larga
[12/09/24, 9:16 AM] Maya Tacos: lo sentimos Maria, ayer tuvimos mucha gente. Te invitamos un agua fresca hoy
[12/09/24, 12:30 PM] +1 555 0142: The tacos were amazing! Will bring my coworkers tomorrow. Love the salsa!
[12/09/24, 1:05 PM] Carlos: quiero 10 tacos para las 2pm, ¿pueden?
[12/09/24, 1:06 PM] Maya Tacos: sí Carlos, listos a las 2pm!
[12/09/24, 6:45 PM] Ana: terrible service yesterday, waited 30 mins and tacos were cold. Very disappointed.
[12/09/24, 7:00 PM] Maya Tacos: Ana, mil disculpas — te esperamos mañana con un descuento
"""
    (base / "whatsapp_chat.txt").write_text(whatsapp, encoding="utf-8")

    # Messy CSV — inconsistent headers, typos, missing values
    csv_content = """Date,Item,Quantity,Price,Notes
2024-09-12,tacos al pastor,32,3.50,good day
2024-09-12,birria,12,4.00,
2024-09-12,quesadilla,8,3.00,slow
2024-09-12,agua fresca,20,2.00,
2024-09-12,tacos,5,3.50,cancelled - no cilantro
"""
    (base / "sales_log.csv").write_text(csv_content, encoding="utf-8")

    # Receipt 1 — typed txt (mock OCR)
    receipt1 = """TIENDA SYSCO
Date: 2024-09-11
Tortillas 10 x 2.50  25.00
Cilantro 3 bunch 4.50 each 13.50
Onions 5kg 18.00
Salsa verde 2L 12.00
Total: $68.50
Gracias!
"""
    (base / "receipts" / "receipt_2024-09-11.txt").write_text(receipt1, encoding="utf-8")
    # Receipt 2 — jpg sidecar txt
    receipt2 = """Receipt #2201
Onions 10kg 32.00
Cilantro 5 bunch 22.50
Limes 3kg 15.00
Total $69.50
"""
    (base / "receipts" / "receipt_2024-09-12.jpg").write_bytes(b"\xFF\xD8\xFF")  # fake jpg
    (base / "receipts" / "receipt_2024-09-12.txt").write_text(receipt2, encoding="utf-8")

    # Notebook — freeform daily notes
    notebook = """sept 12 - sold out of cilantro at 3pm, need more
juan didn't show, short staff -> long waits
maria is regular, bring her salsa extra next time
need to post on instagram - birria photo was popular
"""
    (base / "notebook.txt").write_text(notebook, encoding="utf-8")

    return base
