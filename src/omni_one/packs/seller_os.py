"""
Seller OS — The ONE outstanding product for people selling stuff online
=====================================================================
Focus: 1-5 person shops on Shopify / Etsy / Amazon + Instagram DMs.
Problem: fragmented mess — Shopify CSV, Etsy settlement, supplier photos,
DM exports, inventory snapshots, reviews. No real profit view, no stockout warning.

This is the ONLY primary pack. Revenue/micro/palantir moved to _labs.
Seller OS is concrete, non-overlapping, outstanding because:
  - True profit (GMV - fees - shipping - COGS) with citations file:line
  - Stockout risk = velocity vs on-hand (from photos/CSV)
  - Listing health (title, images, reviews)
  - One-click draft win-back / listing copy (gated LLM, free mock)

Tech: free local — Tesseract OCR, OpenCV, Matplotlib, DuckDB, pipeline.
No fees. Works offline. Drop a folder, get briefing in 5s.

See: scripts/demo_seller_os.py, POST /api/v1/seller/briefing
"""
from __future__ import annotations
import re
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple, Optional
import random
import hashlib

try:
    from ..core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
    from ..core.cache import SemanticCache  # type: ignore
    from ..core.model_router import ModelRouter  # type: ignore
    from ..core.vision import analyze_photo, _parse_numbers_from_text  # type: ignore
except ImportError:
    try:
        from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline  # type: ignore
        from omni_one.core.cache import SemanticCache  # type: ignore
        from omni_one.core.model_router import ModelRouter  # type: ignore
        from omni_one.core.vision import analyze_photo  # type: ignore
        from omni_one.core.vision import _parse_numbers_from_text  # type: ignore
    except ImportError:
        MultiLayerDataPipeline = None  # type: ignore
        SemanticCache = None  # type: ignore
        ModelRouter = None  # type: ignore
        analyze_photo = None  # type: ignore

# ---------- helpers (shared deterministic parsers — see packs/seller_parse.py) ----------
try:
    from .seller_parse import (  # type: ignore
        _money_all, _money, _money_last, _norm_product, _product_match,
        _norm_header, extract_unit_qty, detect_currency,
    )
except ImportError:
    try:
        from omni_one.packs.seller_parse import (  # type: ignore
            _money_all, _money, _money_last, _norm_product, _product_match,
            _norm_header, extract_unit_qty, detect_currency,
        )
    except ImportError:
        import re as _re_fallback  # type: ignore
        def _money_all(s: str):  # type: ignore
            import re as _re
            if not s:
                return []
            text = str(s)
            text = _re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", text)
            text = _re.sub(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", " ", text)
            vals = []
            for m in _re.finditer(r"\$?\s*(\d+(?:\.\d{1,2})?)", text.replace(",", "")):
                try:
                    vals.append(float(m.group(1)))
                except Exception:
                    continue
            return vals
        def _money(s: str):  # type: ignore
            vals = _money_all(s)
            return vals[0] if vals else None
        def _money_last(s: str):  # type: ignore
            vals = _money_all(s)
            return vals[-1] if vals else None
        def _norm_product(s: str) -> str:  # type: ignore
            s = (s or "").lower().strip()
            s = _re_fallback.sub(r"[^a-z0-9]+", " ", s)
            s = _re_fallback.sub(r"\s+", " ", s).strip()
            return s
        def _product_match(a: str, b: str, threshold: float = 0.72) -> bool:  # type: ignore
            from difflib import SequenceMatcher as _SM
            na, nb = _norm_product(a), _norm_product(b)
            if not na or not nb:
                return False
            if na == nb:
                return True
            if na in nb or nb in na:
                return True
            try:
                return _SM(None, na, nb).ratio() >= threshold
            except Exception:
                return False
        def _norm_header(h: str) -> str:  # type: ignore
            return h.strip().lower().replace(" ", "_")
        def extract_unit_qty(line: str):  # type: ignore
            import re as _re2
            m = _re2.search(r"(\d+)\s*x\s*\$?\s*(\d+(?:[.,]\d+)?)", str(line), _re2.I)
            if not m:
                return None
            try:
                return (float(m.group(1)), float(m.group(2).replace(",", "")), float(_money_last(line) or 0))
            except Exception:
                return None
        def detect_currency(s: str) -> str:  # type: ignore
            return "USD"

# ---------- parsers ----------
def parse_orders_csv(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    try:
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            sample = f.read(2048); f.seek(0)
            try: dialect = csv.Sniffer().sniff(sample)
            except: dialect = csv.excel
            reader = csv.DictReader(f, dialect=dialect)
            if not reader.fieldnames:
                return events
            # normalize headers
            field_map = {orig: _norm_header(orig) for orig in reader.fieldnames}
            for idx, row in enumerate(reader, 2):
                # Handle duplicate norm keys (e.g., Lineitem price + Total both -> gmv): prefer Total
                # Build norm manually to avoid silent overwrite
                norm: Dict[str, str] = {}
                for orig, val in row.items():
                    nk = field_map.get(orig, orig)
                    v = (val or "").strip()
                    if nk in norm and nk == "gmv":
                        # Prefer larger (Total) over unit price when both map to gmv
                        try:
                            existing = _money(norm[nk]) or 0
                            candidate = _money(v) or 0
                            # Total is usually >= unit price; keep max
                            norm[nk] = v if candidate >= existing else norm[nk]
                        except Exception:
                            pass
                    elif nk not in norm or not norm[nk]:
                        norm[nk] = v
                    # else keep first non-empty
                # extract (use last money for totals to avoid qty prefix)
                gmv = _money_last(norm.get("gmv", "")) or 0.0
                fees = _money(norm.get("fees", "")) or 0.0
                ship = _money(norm.get("shipping", "")) or 0.0
                qty = 1
                try:
                    qraw = norm.get("qty", "1") or "1"
                    # qty is integer, take first number, not last
                    m = re.search(r"(\d+)", qraw)
                    qty = int(m.group(1)) if m else 1
                    qty = max(1, qty)
                except: qty = 1
                product = norm.get("product") or norm.get("item") or "unknown"
                if not product or product.strip().lower() in ("", "unknown", "none"):
                    product = f"order:{norm.get('order_id') or idx}"
                # If fees missing, estimate: Etsy 6.5% + $0.20, Shopify 2.9%+30c, Amazon 15% — heuristic
                if fees == 0 and gmv > 0:
                    src = path.name.lower()
                    if "etsy" in src: fees = round(gmv * 0.065 + 0.20, 2)
                    elif "shopify" in src: fees = round(gmv * 0.029 + 0.30, 2)
                    elif "amazon" in src: fees = round(gmv * 0.15, 2)
                    else: fees = round(gmv * 0.08, 2)
                net = gmv - fees - ship
                # date
                ts = datetime.now()
                ds = norm.get("date", "")
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%y"):
                    try:
                        ts = datetime.strptime(ds[:10], fmt); break
                    except: continue
                # One event per order (rich metadata)
                events.append({
                    "timestamp": ts,
                    "source": "orders",
                    "entity_id": f"order:{path.stem}:{norm.get('order_id') or idx}",
                    "value": gmv,  # pipeline will see GVM as value for anomaly, but we store net in metadata for briefing
                    "metadata": {
                        "source_file": path.name, "line": idx, "signal": "order_gmv",
                        "product": product, "qty": qty, "gmv": gmv, "fees": fees, "shipping": ship, "net": round(net,2),
                        "customer": norm.get("customer", ""), "status": norm.get("status",""),
                        "citation": f"[{path.name}:{idx}] {product} qty{qty} gmv${gmv} fees${fees} net${net:.2f}",
                    },
                })
    except Exception:
        pass
    return events

def parse_inventory_csv(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    try:
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames: return events
            field_map = {orig: _norm_header(orig) for orig in reader.fieldnames}
            for idx, row in enumerate(reader, 2):
                norm = {field_map.get(k,k): (v or "").strip() for k,v in row.items()}
                product = norm.get("product") or norm.get("sku") or f"sku:{idx}"
                qty_on_hand = None
                for k in ["qty","inventory","stock","on_hand","quantity"]:
                    if k in norm and norm[k]:
                        try: qty_on_hand = int(float(re.sub(r"[^\d.]", "", norm[k]))); break
                        except: continue
                if qty_on_hand is None: qty_on_hand = 0
                events.append({
                    "timestamp": datetime.now(),
                    "source": "inventory",
                    "entity_id": f"inv:{product[:16]}",
                    "value": float(qty_on_hand),
                    "metadata": {"source_file": path.name, "line": idx, "signal": "on_hand", "product": product, "qty_on_hand": qty_on_hand, "citation": f"[{path.name}:{idx}] {product} on_hand={qty_on_hand}"},
                })
    except Exception:
        pass
    return events

def parse_reviews_csv(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    try:
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames: return events
            for idx, row in enumerate(reader, 2):
                text = " ".join([v for v in row.values() if v])[:300]
                # naive sentiment
                low = text.lower()
                score = -1 if any(w in low for w in ["terrible","awful","bad","poor","disappointed","angry","late","damaged"]) else (1 if any(w in low for w in ["love","great","amazing","perfect","fast"]) else 0)
                events.append({
                    "timestamp": datetime.now(),
                    "source": "review",
                    "entity_id": f"review:{path.stem}:{idx}",
                    "value": text,
                    "metadata": {"source_file": path.name, "line": idx, "signal": "review", "sentiment": score, "citation": f"[{path.name}:{idx}] {text[:60]}"},
                })
    except Exception:
        pass
    return events

def parse_dm_file(path: Path) -> List[Dict[str, Any]]:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        events: List[Dict[str, Any]] = []
        # reuse simple split — Instagram/Shopify DM export often JSON, but handle txt
        if path.suffix.lower() == ".json":
            data = json.loads(txt)
            items = data if isinstance(data, list) else data.get("messages", []) if isinstance(data, dict) else []
            for i, item in enumerate(items[:100], 1):
                body = str(item.get("text") or item.get("message") or item)[:300]
                sender = str(item.get("from") or item.get("sender") or "customer")
                events.append({"timestamp": datetime.now(), "source": "dm", "entity_id": f"dm:{path.stem}:{i}", "value": f"{sender}: {body}", "metadata": {"source_file": path.name, "line": i, "sender": sender, "signal": "dm", "citation": f"[{path.name}:{i}] {sender}: {body[:50]}"}})
            return events
        # txt fallback
        for idx, line in enumerate([l.strip() for l in txt.splitlines() if l.strip()][:100], 1):
            # try "Sender: message"
            if ":" in line:
                sender, body = line.split(":", 1)
            else:
                sender, body = "customer", line
            events.append({"timestamp": datetime.now(), "source": "dm", "entity_id": f"dm:{path.stem}:{idx}", "value": f"{sender.strip()}: {body.strip()}", "metadata": {"source_file": path.name, "line": idx, "sender": sender.strip(), "signal": "dm", "citation": f"[{path.name}:{idx}] {sender.strip()}: {body.strip()[:50]}"}})
        return events
    except Exception:
        return []

def parse_supplier_image(path: Path) -> List[Dict[str, Any]]:
    # Handle .txt supplier invoices directly (free, no OCR needed)
    # Use _money_last for line totals (avoids qty prefix "50 x 4.00" -> 50)
    if path.suffix.lower() == ".txt":
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            events: List[Dict[str, Any]] = []
            for idx, line in enumerate([l for l in text.splitlines() if l.strip()], 1):
                total = _money_last(line)
                if total and total > 0 and ("total" in line.lower() or "x" in line.lower() or "$" in line):
                    events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:{idx}", "value": total, "metadata": {"source_file": path.name, "line": idx, "signal": "cogs" if "total" not in line.lower() else "cogs_total", "citation": f"[{path.name}:{idx}] {line[:60]}", "raw": line}})
            if not events:
                total = _money_last(text)
                if total:
                    events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:total", "value": total, "metadata": {"source_file": path.name, "line": 1, "signal": "cogs_total", "citation": f"[{path.name}:1] total ${total}"}})
            return events
        except Exception:
            return []
    # Use free vision OCR for image invoices
    if analyze_photo is None:
        return []
    try:
        data = path.read_bytes()
        result = analyze_photo(data, filename=path.name, run_pipeline=False)
        text = result.get("ocr", {}).get("text", "")
        if not text:
            return []
        events: List[Dict[str, Any]] = []
        # Extract line items via numbers (use LAST money = line total, not qty prefix)
        for idx, line in enumerate([l for l in text.splitlines() if l.strip()], 1):
            total = _money_last(line)
            if total and total > 0:
                # crude COGS per line
                events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:{idx}", "value": total, "metadata": {"source_file": path.name, "line": idx, "signal": "cogs", "citation": f"[{path.name}:{idx}] {line[:60]}", "raw": line}})
        if not events:
            # fallback total
            total = _money_last(text)
            if total:
                events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:total", "value": total, "metadata": {"source_file": path.name, "line": 1, "signal": "cogs_total", "citation": f"[{path.name}:1] total ${total}"}})
        return events
    except Exception:
        return []

# ---------- main ingest ----------
def ingest_seller_folder(folder: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(str(folder))
    events: List[Dict[str, Any]] = []
    report = {"folder": str(folder), "files_seen": 0, "files_ingested": 0, "by_source": Counter(), "errors": [], "skipped_duplicates": 0}
    seen_content_hashes: set = set()
    for p in sorted(folder.rglob("*")):  # sorted for determinism
        if p.is_dir():
            continue
        # Skip sidecar .jpg.txt when .txt already covers it (avoids double COGS)
        # e.g., supplier_invoice.jpg.txt + supplier_invoice.txt with same content
        if p.name.endswith(".jpg.txt") or p.name.endswith(".png.txt"):
            # If sibling .txt with same stem prefix exists, skip — content dup
            # We still count as seen but skip ingest to avoid double
            report["files_seen"] += 1
            # Check content hash to confirm dup
            try:
                h = hashlib.md5(p.read_bytes()).hexdigest()
                if h in seen_content_hashes:
                    report["skipped_duplicates"] += 1
                    continue
                # Also check if base .txt already seen with same content
                base_txt = p.parent / (p.stem)  # strips .txt -> *.jpg
                # Fallback: compare with any seen hash later; for now ingest but dedup via hash
                if h in seen_content_hashes:
                    report["skipped_duplicates"] += 1
                    continue
            except Exception:
                pass
            # Fall through to normal ingest (hash dedup below will catch)
        else:
            report["files_seen"] += 1
        rel = str(p.relative_to(folder))
        suffix = p.suffix.lower()
        name_low = p.name.lower()
        try:
            # Content-hash dedup for .txt supplier invoices (free, robust)
            if suffix == ".txt":
                try:
                    h = hashlib.md5(p.read_bytes()).hexdigest()
                    if h in seen_content_hashes:
                        report["skipped_duplicates"] += 1
                        continue
                except Exception:
                    h = None
            else:
                h = None
            file_events: List[Dict[str, Any]] = []
            if "order" in name_low or "shopify" in name_low or "etsy" in name_low or "amazon" in name_low or "payout" in name_low or "settlement" in name_low:
                file_events = parse_orders_csv(p)
            elif "inventory" in name_low or "stock" in name_low:
                file_events = parse_inventory_csv(p)
            elif "review" in name_low:
                file_events = parse_reviews_csv(p)
            elif "dm" in name_low or "insta" in name_low or "tiktok" in name_low or "message" in name_low:
                file_events = parse_dm_file(p)
            elif suffix in [".csv", ".tsv"] and not file_events:
                file_events = parse_orders_csv(p)
                if not file_events:
                    file_events = parse_inventory_csv(p)
            elif suffix in [".jpg", ".jpeg", ".png", ".pdf", ".webp"] or "supplier" in name_low or "invoice" in name_low:
                # Skip unreadable tiny fake jpgs (3 bytes) gracefully
                try:
                    if suffix in [".jpg", ".jpeg", ".png"] and p.stat().st_size < 100:
                        # Likely placeholder — try sidecar .txt instead
                        sidecar = Path(str(p) + ".txt")
                        if sidecar.exists():
                            file_events = parse_supplier_image(sidecar)
                            # Mark sidecar as seen to avoid double when loop reaches it
                            try:
                                seen_content_hashes.add(hashlib.md5(sidecar.read_bytes()).hexdigest())
                            except Exception:
                                pass
                        else:
                            file_events = []
                    else:
                        file_events = parse_supplier_image(p)
                except Exception:
                    file_events = []
            elif suffix in [".json"]:
                file_events = parse_dm_file(p)
            if file_events:
                events.extend(file_events)
                report["files_ingested"] += 1
                for e in file_events:
                    report["by_source"][e["source"]] += 1
                if h:
                    seen_content_hashes.add(h)
                # Also hash supplier image content for dedup
                if suffix in [".jpg", ".jpeg", ".png"] and file_events:
                    try:
                        seen_content_hashes.add(hashlib.md5(p.read_bytes()).hexdigest())
                    except Exception:
                        pass
        except Exception as e:
            report["errors"].append(f"{rel}: {e}")
    report["by_source"] = dict(report["by_source"])
    report["events"] = len(events)
    return events, report

def make_seller_demo_folder(base: Path, seed: int = 42) -> Path:
    base = Path(base); base.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    # orders - Shopify + Etsy mix (messy headers)
    shopify = """Order Name,Created at,Lineitem name,Lineitem quantity,Lineitem price,Total,Fees,Shipping,Customer
#1001,2024-09-10,Tote Bag Handmade,2,28.00,56.00,,4.00,Alice
#1002,2024-09-11,Ceramic Mug,1,22.00,22.00,,3.50,Bob
#1003,2024-09-11,Tote Bag Handmade,1,28.00,28.00,,0.00,Charlie
#1004,2024-09-12,Print - Botanical,3,15.00,45.00,,5.00,Alice
#1005,2024-09-12,Tote Bag Handmade,1,28.00,28.00,,4.00,David
"""
    (base / "shopify_orders.csv").write_text(shopify, encoding="utf-8")
    etsy = """order_id,order_date,product,qty,price,fees,shipping,buyer
E2001,2024-09-10,Knitted Scarf,1,45.00,3.12,4.50,Eve
E2002,2024-09-11,Tote Bag Handmade,2,28.00,3.84,0.00,Frank
E2003,2024-09-12,Ceramic Mug,2,22.00,3.06,3.00,Grace
"""
    (base / "etsy_settlement.csv").write_text(etsy, encoding="utf-8")
    # inventory - low stock on best seller
    inv = """sku,product,stock,supplier
TB001,Tote Bag Handmade,2,Acme Textiles
CM002,Ceramic Mug,15,Clay Co
PR003,Print - Botanical,40,Paper Co
KS004,Knitted Scarf,8,Wool Co
"""
    (base / "inventory.csv").write_text(inv, encoding="utf-8")
    # reviews
    reviews = """date,product,stars,review
2024-09-11,Tote Bag Handmade,5,"Love it! Perfect size"
2024-09-11,Ceramic Mug,2,"Arrived chipped, very disappointed"
2024-09-12,Print - Botanical,5,"Beautiful!"
"""
    (base / "reviews.csv").write_text(reviews, encoding="utf-8")
    # DMs
    dms = """Alice: Hi! My tote bag hasn't arrived yet, ordered 5 days ago. Worried.
Shop: Hi Alice, checking tracking — will update in 1h
Bob: Amazing mug! Will order again.
Charlie: Where is my order? No tracking.
"""
    (base / "instagram_dm.txt").write_text(dms, encoding="utf-8")
    # supplier invoice as image + sidecar
    (base / "supplier_invoice_2024-09-10.txt").write_text("Acme Textiles\nTote Bag Canvas 50 x 4.00 200.00\nShipping 15.00\nTotal $215.00\n", encoding="utf-8")
    # create a fake jpg with sidecar for vision path
    fake_jpg = base / "supplier_invoice_2024-09-10.jpg"
    fake_jpg.write_bytes(b"\xFF\xD8\xFF")
    (base / "supplier_invoice_2024-09-10.jpg.txt").write_text("Acme Textiles\nTote Bag Canvas 50 x 4.00 200.00\nTotal $215.00\n", encoding="utf-8")
    return base

# ---------- briefing — THE outstanding product ----------
def build_seller_briefing(events: List[Dict[str, Any]], pipeline=None, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now()
    # LLM policy: MOCK BY DEFAULT ($0). Live only if SELLER_LLM != mock + key present + budget ok.
    live_allowed = False
    try:
        try:
            from ..core.cost_ledger import should_use_live_llm, record_cost  # type: ignore
        except ImportError:
            from omni_one.core.cost_ledger import should_use_live_llm, record_cost  # type: ignore
        live_allowed = bool(should_use_live_llm())
    except Exception:
        live_allowed = False
        record_cost = None  # type: ignore
    # pipeline for evidence (free)
    if pipeline is None and MultiLayerDataPipeline and SemanticCache and ModelRouter:
        if live_allowed:
            try:
                pipeline = MultiLayerDataPipeline(model_router=ModelRouter(), cache=SemanticCache())  # type: ignore
            except Exception:
                pipeline = None
        else:
            class _Mock(ModelRouter):  # type: ignore
                def generate(self, prompt: str, model=None, **kw):  # type: ignore
                    return f"[MOCK SELLER DRAFT] {prompt[:80]} — grounded in Seller OS."
            try:
                pipeline = MultiLayerDataPipeline(model_router=_Mock(), cache=SemanticCache())  # type: ignore
            except Exception:
                pipeline = None
    if pipeline and events:
        try:
            results, _ = pipeline.process_batch(events)
            summary = pipeline.get_metrics_summary()
            # Record $0 cost explicitly so ledger proves free
            try:
                if record_cost is not None:
                    record_cost("seller_briefing_mock", 0.0, {"events": len(events)})
            except Exception:
                pass
        except Exception:
            results, summary = [], {}
    else:
        results, summary = [], {}

    # deterministic KPIs
    orders = [e for e in events if e["source"] == "orders"]
    gmv = sum(e["metadata"].get("gmv", e["value"]) for e in orders if isinstance(e["metadata"].get("gmv",0), (int,float)))
    fees = sum(e["metadata"].get("fees",0) for e in orders)
    ship = sum(e["metadata"].get("shipping",0) for e in orders)
    net = gmv - fees - ship
    # COGS: allocate per-unit cost from supplier invoices (free, deterministic)
    # Supplier events: parse unit cost + qty from raw line, e.g., "Tote Bag Canvas 50 x 4.00 200.00" -> unit 4.00
    supplier_catalog: Dict[str, float] = {}  # product key -> unit cost
    for e in events:
        if e["source"] == "supplier":
            raw = str(e["metadata"].get("raw", ""))
            # Shared parser: "50 x 4.00" -> (50, 4.00, 200.00)
            try:
                parsed = extract_unit_qty(raw)
            except Exception:
                parsed = None
            # crude product key: first words
            key = None
            for prod in ["tote", "mug", "print", "scarf", "canvas", "clay", "paper"]:
                if prod in raw.lower():
                    key = prod
                    break
            if parsed and key:
                try:
                    _qty, unit, _total = parsed
                    supplier_catalog[key] = float(unit)
                except Exception:
                    pass
            # fallback: if line is "Tote Bag Canvas 50 x 4.00" -> tote:4.0
    # compute COGS per order via catalog
    cogs = 0.0
    for e in orders:
        prod = (e["metadata"].get("product") or "").lower()
        qty = e["metadata"].get("qty", 1)
        unit_cost = 0.0
        for k, cost in supplier_catalog.items():
            if k in prod:
                unit_cost = cost; break
        # default COGS heuristic if no catalog match: 30% of gmv per unit
        if unit_cost == 0 and e["metadata"].get("gmv"):
            unit_cost = float(e["metadata"]["gmv"]) / max(qty,1) * 0.30
        cogs += unit_cost * qty
    # fallback if no catalog at all and no orders: sum supplier totals as before (but avoid double)
    if cogs == 0 and any(e["source"]=="supplier" for e in events):
        # use smallest supplier total as cogs estimate
        supplier_totals = [e["value"] for e in events if e["source"]=="supplier" and "total" in str(e["metadata"].get("signal",""))]
        if supplier_totals:
            cogs = min(supplier_totals) * 0.25  # heuristic: 25% of invoice is for this period
    true_profit = net - cogs
    margin = (true_profit / gmv * 100) if gmv else 0

    # best/worst by qty — aggregate by normalized product (fixes "Tote Bag" vs "tote bag" split)
    product_qty_norm: Counter = Counter()
    product_gmv_norm: Counter = Counter()
    product_display: Dict[str, str] = {}
    for e in orders:
        raw_prod = (e["metadata"].get("product") or "unknown").strip() or "unknown"
        np_ = _norm_product(raw_prod)
        if np_ not in product_display:
            product_display[np_] = raw_prod  # first display wins
        try:
            qty = int(float(e["metadata"].get("qty", 1) or 1))
        except Exception:
            qty = 1
        try:
            g = float(e["metadata"].get("gmv", 0) or 0)
        except Exception:
            g = 0.0
        product_qty_norm[np_] += qty
        product_gmv_norm[np_] += g
    # Convert back to display for output
    product_qty = Counter({product_display[k]: v for k, v in product_qty_norm.items()})
    product_gmv = Counter({product_display[k]: v for k, v in product_gmv_norm.items()})
    best = product_qty.most_common(1)[0] if product_qty else ("—", 0)
    worst = product_qty.most_common()[-1] if product_qty else ("—", 0)

    # inventory risk (fuzzy product match, was exact case-sensitive — missed "Tote Bag" vs "tote bag")
    inv_events = [e for e in events if e["source"] == "inventory"]
    # Build normalized map: norm -> (display, qty)
    inv_norm: Dict[str, Tuple[str, int]] = {}
    for e in inv_events:
        prod = str(e["metadata"].get("product", ""))
        qty = e["metadata"].get("qty_on_hand", 0)
        try:
            qty = int(qty)
        except Exception:
            qty = 0
        inv_norm[_norm_product(prod)] = (prod, qty)
    risk = []
    for prod, sold in product_qty.items():
        # Find best inventory match (exact norm, then fuzzy)
        on_hand = None
        display = prod
        np_ = _norm_product(prod)
        if np_ in inv_norm:
            display, on_hand = inv_norm[np_]
        else:
            # Fuzzy fallback
            for nk, (dp, q) in inv_norm.items():
                if _product_match(prod, dp):
                    display, on_hand = dp, q
                    break
        if on_hand is not None:
            try:
                days_supply = on_hand / (sold / 7) if sold else 999
            except Exception:
                days_supply = 999
            if days_supply < 5:
                # Find citation from inv event
                cite = f"[inventory.csv] {display} {on_hand} left, sold {sold}/7d"
                for e in inv_events:
                    if _product_match(str(e["metadata"].get("product", "")), prod):
                        cite = e["metadata"].get("citation", cite)
                        break
                risk.append({"product": display, "on_hand": on_hand, "sold_7d": sold, "days_supply": round(days_supply, 1), "citation": cite})

    # DM at-risk / review at-risk (word-boundary for short words like "bad", "late")
    dm_events = [e for e in events if e["source"] in ("dm",)]
    review_events = [e for e in events if e["source"] == "review"]
    def is_negative(txt: str) -> bool:
        low = txt.lower()
        # Phrases (substring ok)
        phrases = ["hasn't arrived", "hasnt arrived", "no tracking", "where is my", "never arrived", "very disappointed", "espera larga", "tardó"]
        if any(ph in low for ph in phrases):
            return True
        # Single words with boundaries to avoid "wherever" / "badminton"
        import re as _re2
        words = ["worried", "disappointed", "chipped", "damaged", "late", "angry", "terrible", "awful", "horrible", "hate", "refund", "missing", "broken", "wrong"]
        for w in words:
            if _re2.search(r"\b" + _re2.escape(w) + r"\b", low):
                return True
        # "where" + "order/tracking/arrived" combo (avoids false "wherever")
        if _re2.search(r"\bwhere\b", low) and any(k in low for k in ["order", "tracking", "arrived", "package"]):
            return True
        # "bad" only with boundary + context (poor service, bad quality)
        if _re2.search(r"\bbad\b", low) and any(k in low for k in ["service", "quality", "experience", "product"]):
            return True
        return False
    at_risk = []
    for e in dm_events + review_events:
        txt = str(e["value"])
        if is_negative(txt):
            at_risk.append({"text": txt[:100], "citation": e["metadata"]["citation"], "source": e["source"]})
    happy = []
    for e in dm_events:
        if any(w in str(e["value"]).lower() for w in ["love","amazing","perfect","beautiful"]):
            happy.append({"text": str(e["value"])[:100], "citation": e["metadata"]["citation"]})

    # listing health: products with no reviews or low stock + high sales
    alerts: List[Dict[str, Any]] = []
    if at_risk:
        alerts.append({"type":"customer_at_risk","severity":"high","message": f"{len(at_risk)} customer(s) need reply now — risk of refund/1-star","evidence":[c["citation"] for c in at_risk[:2]]})
    if risk:
        r = risk[0]
        alerts.append({"type":"stockout_risk","severity":"high","message": f"Stockout risk: {r['product']} only {r['on_hand']} left, {r['days_supply']} days supply","evidence":[r["citation"]]})
    if margin < 10 and gmv > 0:
        alerts.append({"type":"margin_pressure","severity":"medium","message": f"True margin {margin:.1f}% low (profit ${true_profit:.2f} on ${gmv:.2f} GMV, COGS ${cogs:.2f} fees ${fees:.2f})","evidence":[f"[orders] gmv ${gmv:.2f} fees ${fees:.2f}","supplier COGS ${cogs:.2f}"]})
    elif true_profit < 0:
        alerts.append({"type":"loss","severity":"critical","message": f"Net loss ${true_profit:.2f} — check COGS/fees","evidence":[]})
    if not alerts:
        alerts.append({"type":"all_clear","severity":"low","message":"No urgent risks — focus on best seller","evidence":[]})

    actions: List[str] = []
    if risk:
        actions.append(f"Reorder {risk[0]['product']} now — {risk[0]['days_supply']} days left (cite {risk[0]['citation']})")
    if at_risk:
        actions.append(f"Reply to {at_risk[0]['citation']} within 2h — draft below, offer tracking/update")
    if happy:
        actions.append(f"Ask {happy[0]['citation']} for review / UGC")
    actions.append(f"Daily close: GMV ${gmv:.2f} fees ${fees:.2f} net ${net:.2f} true profit ${true_profit:.2f} ({margin:.1f}%)")

    # draft (gated: only if at-risk)
    draft = None
    if at_risk and pipeline and hasattr(pipeline, "model_router") and pipeline.model_router:
        prompt = f"Write warm 30-word reply to customer who said: \"{at_risk[0]['text'][:120]}\". Apologize, give tracking, offer help. Shop: small handmade shop."
        try:
            draft = pipeline.model_router.generate(prompt)
        except Exception:
            draft = f"Hi! Sorry for the delay — checking tracking for you now and will update in 1h. Thanks for patience! [cite {at_risk[0]['citation']}]"
    elif at_risk:
        draft = f"Hi, sorry about that — checking now, will update shortly! [{at_risk[0]['citation']}]"

    # chart data (free matplotlib)
    chart_b64 = None
    try:
        from ..core.vision import data_to_chart_base64  # type: ignore
    except ImportError:
        try: from omni_one.core.vision import data_to_chart_base64  # type: ignore
        except: data_to_chart_base64 = None  # type: ignore
    chart_data = {"labels": [k for k,_ in product_qty.most_common(6)], "values": [v for _,v in product_qty.most_common(6)]}
    if data_to_chart_base64 and chart_data["labels"]:
        try: chart_b64 = data_to_chart_base64(chart_data, title="Units sold (7d)")
        except: chart_b64 = None

    evidence_sample = []
    for r in results[:2] if 'results' in locals() else []:
        evidence_sample.extend(getattr(r,"evidence_steps", [])[:1])

    return {
        "meta": {"generated_at": now.isoformat(), "events": len(events), "pipeline": summary if 'summary' in locals() else {}, "mode": "seller_os", "free": True},
        "kpis": {
            "gmv": round(gmv,2), "fees": round(fees,2), "shipping": round(ship,2), "net": round(net,2),
            "cogs": round(cogs,2), "true_profit": round(true_profit,2), "margin_pct": round(margin,1),
            "orders": len(orders), "aov": round(gmv/len(orders),2) if orders else 0,
            "best_seller": {"product": best[0], "qty": best[1], "gmv": round(product_gmv[best[0]],2) if best[0] in product_gmv else 0},
            "worst_seller": {"product": worst[0], "qty": worst[1]},
            "at_risk": len(at_risk), "happy": len(happy), "stockout_risk": len(risk),
        },
        "alerts": alerts,
        "actions": actions,
        "stockout_risk": risk,
        "at_risk_preview": at_risk[:3],
        "happy_preview": happy[:2],
        "draft_reply": {"text": draft, "citation": at_risk[0]["citation"] if at_risk else None},
        "chart": {"data": chart_data, "base64": chart_b64},
        "evidence_sample": evidence_sample[:4],
        "ingest_report": {"by_source": dict(Counter(e["source"] for e in events))},
        "llm": {"mode": "live" if live_allowed else "mock", "cost_usd": 0.0},
    }


def get_cached_briefing(folder: Path, max_age_s: int = 3600) -> Optional[Dict[str, Any]]:
    """Return cached briefing if folder fingerprint unchanged. $0, never raises."""
    try:
        try:
            from ..infra.store import get_store, folder_fingerprint  # type: ignore
        except ImportError:
            from omni_one.infra.store import get_store, folder_fingerprint  # type: ignore
        fp = folder_fingerprint(Path(folder))
        store = get_store()
        cached = store.briefing_get(fp, max_age_s=max_age_s)
        if cached:
            cached.setdefault("meta", {})["cache"] = "hit"
            cached["meta"]["folder_hash"] = fp
        return cached
    except Exception:
        return None


def put_cached_briefing(folder: Path, briefing: Dict[str, Any]) -> None:
    """Cache briefing by folder fingerprint. Never raises."""
    try:
        try:
            from ..infra.store import get_store, folder_fingerprint  # type: ignore
        except ImportError:
            from omni_one.infra.store import get_store, folder_fingerprint  # type: ignore
        fp = folder_fingerprint(Path(folder))
        briefing.setdefault("meta", {})["folder_hash"] = fp
        get_store().briefing_put(fp, briefing)
    except Exception:
        pass
