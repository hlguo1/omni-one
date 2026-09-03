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

# ---------- helpers ----------
def _money(s: str) -> Optional[float]:
    if not s: return None
    m = re.search(r"\$?\s*(\d+(?:[.,]\d{2})?)", str(s).replace(",", ""))
    if not m: return None
    try: return float(m.group(1).replace(",", ""))
    except: return None

def _norm_header(h: str) -> str:
    # Prioritize specific fields first to avoid substring collisions (e.g., "lineitem quantity" contains "item")
    h_low = h.strip().lower()
    h_norm = h_low.replace(" ", "_")
    # Ordered: most specific first — product before customer to avoid "Lineitem name" -> customer
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
        # fallback generic
        ("product", ["item"]),  # item last, after qty
        ("gmv", ["price", "total"]),
        ("date", ["date"]),
        ("order_id", ["order"]),
    ]
    for norm, variants in mapping_ordered:
        for v in variants:
            # Use word boundary or exact substring with underscores
            if v in h_norm or v.replace("_", " ") in h_low:
                return norm
    return h_norm

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
                norm = {field_map.get(k, k): (v or "").strip() for k, v in row.items()}
                # extract
                gmv = _money(norm.get("gmv", "")) or _money(norm.get("total", "")) or 0.0
                fees = _money(norm.get("fees", "")) or 0.0
                ship = _money(norm.get("shipping", "")) or 0.0
                qty = 1
                try: qty = int(float(re.sub(r"[^\d.]", "", norm.get("qty", "1") or "1")))
                except: qty = 1
                product = norm.get("product") or norm.get("item") or "unknown"
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
    if path.suffix.lower() == ".txt":
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            events: List[Dict[str, Any]] = []
            for idx, line in enumerate([l for l in text.splitlines() if l.strip()], 1):
                total = _money(line)
                if total and total > 0 and ("total" in line.lower() or "x" in line.lower() or "$" in line):
                    events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:{idx}", "value": total, "metadata": {"source_file": path.name, "line": idx, "signal": "cogs" if "total" not in line.lower() else "cogs_total", "citation": f"[{path.name}:{idx}] {line[:60]}", "raw": line}})
            if not events:
                total = _money(text)
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
        # Extract line items via numbers
        for idx, line in enumerate([l for l in text.splitlines() if l.strip()], 1):
            total = _money(line)
            if total and total > 0:
                # crude COGS per line
                events.append({"timestamp": datetime.now(), "source": "supplier", "entity_id": f"supplier:{path.stem}:{idx}", "value": total, "metadata": {"source_file": path.name, "line": idx, "signal": "cogs", "citation": f"[{path.name}:{idx}] {line[:60]}", "raw": line}})
        if not events:
            # fallback total
            total = _money(text)
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
    report = {"folder": str(folder), "files_seen": 0, "files_ingested": 0, "by_source": Counter(), "errors": []}
    for p in folder.rglob("*"):
        if p.is_dir(): continue
        report["files_seen"] += 1
        rel = str(p.relative_to(folder))
        suffix = p.suffix.lower()
        name_low = p.name.lower()
        try:
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
                # try orders as default for seller
                file_events = parse_orders_csv(p)
                if not file_events:
                    file_events = parse_inventory_csv(p)
            elif suffix in [".jpg",".jpeg",".png",".pdf",".webp"] or "supplier" in name_low or "invoice" in name_low:
                file_events = parse_supplier_image(p)
            elif suffix in [".json"]:
                file_events = parse_dm_file(p)
            # count
            if file_events:
                events.extend(file_events)
                report["files_ingested"] += 1
                for e in file_events:
                    report["by_source"][e["source"]] += 1
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
    # pipeline for evidence (free)
    if pipeline is None and MultiLayerDataPipeline and SemanticCache and ModelRouter:
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
            # Try to extract "50 x 4.00"
            m = re.search(r"(\d+)\s*x\s*\$?\s*(\d+(?:[.,]\d+)?)", raw, re.I)
            item = (e["metadata"].get("raw", "") or "").lower()
            # crude product key: first words
            key = None
            for prod in ["tote", "mug", "print", "scarf", "canvas", "clay", "paper"]:
                if prod in raw.lower():
                    key = prod
                    break
            if m and key:
                try:
                    qty = float(m.group(1)); unit = float(m.group(2).replace(",", ""))
                    supplier_catalog[key] = unit
                except: pass
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

    # best/worst by qty
    product_qty = Counter()
    product_gmv = Counter()
    for e in orders:
        prod = (e["metadata"].get("product") or "unknown").strip()
        qty = e["metadata"].get("qty", 1)
        product_qty[prod] += qty
        product_gmv[prod] += e["metadata"].get("gmv",0)
    best = product_qty.most_common(1)[0] if product_qty else ("—",0)
    worst = product_qty.most_common()[-1] if product_qty else ("—",0)

    # inventory risk
    inv_events = [e for e in events if e["source"] == "inventory"]
    inv_map = {e["metadata"]["product"]: e["metadata"]["qty_on_hand"] for e in inv_events}
    # velocity last 7 days: qty sold per product
    risk = []
    for prod, sold in product_qty.items():
        on_hand = inv_map.get(prod)
        if on_hand is not None:
            days_supply = on_hand / (sold / 7) if sold else 999
            if days_supply < 5:
                risk.append({"product": prod, "on_hand": on_hand, "sold_7d": sold, "days_supply": round(days_supply,1), "citation": f"[inventory.csv] {prod} {on_hand} left, sold {sold}/7d"})

    # DM at-risk / review at-risk
    dm_events = [e for e in events if e["source"] in ("dm",)]
    review_events = [e for e in events if e["source"] == "review"]
    def is_negative(txt: str) -> bool:
        txt = txt.lower()
        return any(w in txt for w in ["where","worried","hasn't arrived","no tracking","disappointed","chipped","late","angry","terrible","bad"])
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
    }
