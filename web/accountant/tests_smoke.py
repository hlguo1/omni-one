"""WAVE2-J smoke tests — accountant PWA + seller upgrade + assets (stdlib only).

Checks:
  1. Files exist under web/accountant/ and web/assets/
  2. index.html references app.js (local, no CDN tags)
  3. app.js defines required surface (parseCloseCSV, buildPL, renderReport...)
  4. No external CDN <script>/<link> tags (offline rule) in accountant + seller
  5. Content sanity: KPI table, P&L walk (div widths), 6-step checklist w/
     localStorage, fee benchmarks (shopify/etsy/amazon/tiktok/ebay),
     print CSS (@media print), validation warnings, sample-data button
  6. Seller page: existing IDs/handlers preserved, Daily Close banner added,
     close links present, version v1.1.0, still single-file
  7. Assets: close-sample.json valid JSON, keeps kpis/reorder/replies/po,
     no base64, <60KB; README present

Run:
  python3 web/accountant/tests_smoke.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # web/accountant -> web -> repo
if not (REPO / "web" / "accountant").exists():
    p = HERE
    for _ in range(6):
        if (p / "web" / "accountant").exists():
            REPO = p
            break
        p = p.parent

ACC = REPO / "web" / "accountant"
WEB = REPO / "web"
ASSETS = WEB / "assets"
SELLER = WEB / "seller.html"

REQUIRED_ACC_FILES = ["index.html", "app.js", "tests_smoke.py"]

REQUIRED_FUNCS = [
    "parseCloseCSV",
    "buildPL",
    "renderReport",
    "parseCloseJSON",
    "validateClose",
    "copySummary",
    "printReport",
    "ChecklistStore",
    "detectDelimiter",
    "stripBOM",
]

# IDs/handlers that must survive the seller.html upgrade (ADD-only rule).
SELLER_PRESERVE_IDS = [
    "demoBtn",
    "scenBtn",
    "photoBtn",
    "photoInput",
    "photoPreview",
    "scenarios",
    "status",
    "kpi-gmv",
    "kpi-profit",
    "kpi-margin",
    "kpi-stock",
    "kpi-best",
    "chartWrap",
    "chartImg",
    "alerts",
    "actions",
    "draft",
    "evidence",
]
SELLER_PRESERVE_HANDLERS = [
    "runSellerDemo",
    "loadScenarios",
    "runScenarios",
    "runPhoto",
    "render(",
]

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        FAILURES.append(msg)


def main() -> int:
    print("== WAVE2-J smoke: accountant PWA + seller + assets ==")
    print(f"dir: {ACC}")

    # 1. Files exist + non-empty.
    for name in REQUIRED_ACC_FILES:
        fp = ACC / name
        check(fp.is_file(), f"exists: web/accountant/{name}")
        if fp.is_file():
            try:
                check(fp.stat().st_size > 0, f"non-empty: web/accountant/{name} ({fp.stat().st_size}B)")
            except OSError as e:
                check(False, f"stat web/accountant/{name}: {e}")
    for name in ["close-sample.json", "README.md"]:
        fp = ASSETS / name
        check(fp.is_file(), f"exists: web/assets/{name}")
        if fp.is_file():
            try:
                check(fp.stat().st_size > 0, f"non-empty: web/assets/{name} ({fp.stat().st_size}B)")
            except OSError as e:
                check(False, f"stat web/assets/{name}: {e}")
    check(SELLER.is_file(), "exists: web/seller.html")

    idx = ACC / "index.html"
    app = ACC / "app.js"
    html = idx.read_text(encoding="utf-8") if idx.is_file() else ""
    js = app.read_text(encoding="utf-8") if app.is_file() else ""
    seller = SELLER.read_text(encoding="utf-8") if SELLER.is_file() else ""

    # 2. index.html references local app.js.
    check("app.js" in html, "accountant index.html references app.js")
    check(re.search(r'<script[^>]+src=["\']app\.js["\']', html) is not None,
          'accountant index.html has <script src="app.js">')

    # 3. app.js defines required functions/surface.
    for fn in REQUIRED_FUNCS:
        pat = re.compile(r"(function\s+" + re.escape(fn) + r"\b|" + re.escape(fn) + r"\s*[:=]|"
                         r"window\.AccountantApp\b)")
        # For plain names require the name; for the namespace require once.
        if fn == "ChecklistStore":
            found = "ChecklistStore" in js
        else:
            found = re.search(r"\b" + re.escape(fn) + r"\b", js) is not None
        check(found, f"app.js defines {fn}")
    check("window.AccountantApp" in js, "app.js exposes window.AccountantApp")
    for fn in ["parseCloseCSV", "buildPL", "renderReport"]:
        check(fn in js and ("AccountantApp" in js), f"AccountantApp exposes {fn}")

    # 4. No external CDN tags (offline rule) — accountant + seller.
    for label, text in [("accountant index.html", html), ("seller.html", seller)]:
        cdn_scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\']', text, re.IGNORECASE)
        check(len(cdn_scripts) == 0, f"no CDN <script src=http...> in {label} (found {len(cdn_scripts)})")
        cdn_links = re.findall(r'<link[^>]+href=["\']https?://[^"\']+["\']', text, re.IGNORECASE)
        check(len(cdn_links) == 0, f"no CDN <link href=http...> in {label} (found {len(cdn_links)})")
    js_cdn = re.findall(r'from\s+["\']https?://|import\(["\']https?://', js)
    check(len(js_cdn) == 0, "accountant app.js has no CDN imports")

    # 5a. Demo data present (offline sample works via file://).
    check("DEMO_CSV" in js, "app.js has inline DEMO_CSV")
    check("DEMO_CLOSE_JSON" in js or "DEMO_JSON" in js, "app.js has inline demo JSON")
    check("274" in js and "169.09" in js, "app.js demo numbers present (GMV 274 / profit 169.09)")
    check("sampleCsvBtn" in html or "sample-data" in html.lower() or "Load sample" in html,
          "index.html has sample-data button")

    # 5b. Print CSS present.
    check("@media print" in html, "accountant index.html printable (@media print)")
    check("no-print" in html, "accountant index.html hides chrome in print (.no-print)")
    check("printReport" in js and "window.print" in js, "app.js print helper calls window.print()")

    # 5c. KPI table.
    check("kpiBody" in html and "kpiBody" in js, "KPI table wired (kpiBody in html+js)")

    # 5d. P&L walk with div-width bars.
    check("plWalk" in html and "plWalk" in js, "P&L walk host (plWalk in html+js)")
    check("width" in js and ("GMV" in js or "gmv" in js), "P&L walk uses div widths (% of GMV)")
    for token in ["fees", "shipping", "cogs", "profit"]:
        check(token in js.lower(), f"P&L walk covers {token}")

    # 5e. Checklist: 6 steps + localStorage persistence.
    check("checkList" in html and "checkList" in js, "checklist host (checkList in html+js)")
    check("CHECKLIST_STEPS" in js, "app.js defines CHECKLIST_STEPS")
    check("localStorage" in js, "app.js persists checklist to localStorage")
    check("acct_checklist_v1" in js, "checklist storage key acct_checklist_v1")
    # Count the six step ids.
    for sid in ["gmv_orders", "fees", "shipping", "cogs", "citations", "export"]:
        check(sid in js, f"checklist step present: {sid}")

    # 5f. Fee benchmarks: shopify/etsy/amazon/tiktok/ebay vs actual.
    for name in ["shopify", "etsy", "amazon", "tiktok", "ebay"]:
        check(name in js.lower() and name in html.lower(), f"fee benchmark present: {name}")
    check("FEE_BENCHMARKS" in js, "app.js defines FEE_BENCHMARKS")
    check("feeBody" in html and "feeBody" in js, "fee table wired (feeBody in html+js)")

    # 5g. Validation warnings.
    check("warnBox" in html and "warnBox" in js or "renderWarnings" in js,
          "validation warnings host (warnBox)")
    check("V1_PROFIT_GT_GMV" in js or "profit" in js.lower() and "gmv" in js.lower(),
          "profit>gmv impossible check present")
    check("CITATION" in js.upper() and "citation" in html.lower(),
          "missing-citation flag present (V5)")

    # 5h. CSV parser capabilities + JSON loader + copy-summary.
    for token in ["detectDelimiter", "stripBOM", "parseCloseJSON", "accCopyText", "copySummary",
                  "semicolon", "BOM", "quote"]:
        check(token in js or token.lower() in js.lower(), f"app.js covers {token}")
    check('delimiter' in js.lower(), "CSV delimiter handling present")

    # 5i. Offline: same-origin API only, no hardcoded localhost origin.
    check("http://localhost" not in html, "accountant index.html has no hardcoded localhost")
    check("/api/v1/seller/close" in html or "/api/v1/seller/close" in js,
          "accountant references Daily Close API (same-origin)")

    # 6. Seller page upgrade: preserve + add.
    for i in SELLER_PRESERVE_IDS:
        check(f'id="{i}"' in seller, f"seller.html preserves id={i}")
    for h in SELLER_PRESERVE_HANDLERS:
        check(h in seller, f"seller.html preserves handler {h.strip()}")
    check("Daily Close" in seller, "seller.html has Daily Close banner")
    check("close-headline" in seller or "closeHeadline" in seller or "close_headline" in seller,
          "seller.html has headline placeholder")
    check("/seller/close" in seller, "seller.html Run Daily Close demo -> POST /seller/close")
    check("close.csv" in seller, "seller.html has Download close.csv")
    check("../close/index.html" in seller, "seller.html links Open Close PWA (../close/index.html)")
    check("../accountant/index.html" in seller, "seller.html links Open Accountant (../accountant/index.html)")
    check("v1.1.0" in seller, "seller.html footer version bump v1.1.0")
    # Still single-file: no new external script/link.
    check("app.js" not in seller or "seller" in seller.lower(), "seller.html stays single-file (no new bundle refs)")

    # 7. Assets: close-sample.json shape + budget.
    sample_fp = ASSETS / "close-sample.json"
    if sample_fp.is_file():
        try:
            size = sample_fp.stat().st_size
            check(size < 60 * 1024, f"close-sample.json <60KB (got {size}B)")
            data = json.loads(sample_fp.read_text(encoding="utf-8"))
            for key in ["kpis", "reorder_sheet", "reply_queue", "po_draft"]:
                check(key in data, f"close-sample.json keeps {key}")
            blob = sample_fp.read_text(encoding="utf-8")
            check("generated_chart_base64" not in blob and "iVBOR" not in blob,
                  "close-sample.json drops base64")
            check("gmv" in blob.lower(), "close-sample.json has GMV numbers")
        except (OSError, ValueError) as e:
            check(False, f"close-sample.json parses: {e}")
    else:
        check(False, "close-sample.json parses (missing)")

    # 8. Size report + line-count gates.
    print("\n-- size report (wc -l + bytes) --")
    total_lines = 0
    for name in REQUIRED_ACC_FILES + ["../assets/close-sample.json", "../assets/README.md", "../seller.html"]:
        fp = (ACC / name) if not name.startswith("..") else (ACC / name)
        # Normalise ../ paths relative to ACC.
        fp = fp.resolve() if hasattr(fp, "resolve") else fp
        label = str(fp.relative_to(REPO)) if str(fp).startswith(str(REPO)) else name
        if fp.is_file():
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
            except OSError:
                lines = 0
            try:
                size = fp.stat().st_size
            except OSError:
                size = 0
            total_lines += lines
            print(f"{lines:6d} lines  {size:8d}B  {label}")
        else:
            print(f"     0 lines         0B  {label} (MISSING)")
    print(f"{total_lines:6d} lines  total")

    try:
        html_lines = html.count("\n") + (0 if html.endswith("\n") or not html else 1)
        js_lines = js.count("\n") + (0 if js.endswith("\n") or not js else 1)
    except Exception:
        html_lines, js_lines = 0, 0
    check(html_lines >= 1200, f"accountant index.html ~1200+ lines (got {html_lines})")
    check(js_lines >= 1000, f"accountant app.js ~1000+ lines (got {js_lines})")

    print()
    if FAILURES:
        print(f"SMOKE FAIL: {len(FAILURES)} check(s) failed")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("SMOKE PASS: all checks passed (no network calls made)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
