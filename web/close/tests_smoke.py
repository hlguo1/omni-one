"""WORKSTREAM B smoke tests — web PWA Close dashboard (stdlib only, no network).

Checks:
  1. Files exist under web/close/
  2. index.html references app.js / sw.js / manifest
  3. app.js defines required functions (loadDemo, loadFolderHint, renderClose,
     copyText, downloadCSV)
  4. No external CDN <script> tags (offline rule)
  5. Content sanity (tabs, APIs, print CSS, CLOSE_V1, badges, PO pre, ingest)
  6. Size report (wc -l per file)

Run:
  python3 web/close/tests_smoke.py
  python3 -m compileall -q web/close/tests_smoke.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # web/close -> web -> repo (robust either way)
if not (REPO / "web" / "close").exists():
    # Fallback: locate by walking up until web/close found (bazel-friendly).
    p = HERE
    for _ in range(6):
        if (p / "web" / "close").exists():
            REPO = p
            break
        p = p.parent

CLOSE = REPO / "web" / "close"

REQUIRED_FILES = [
    "index.html",
    "app.js",
    "sw.js",
    "manifest.webmanifest",
    "icon.svg",
    "README.md",
    "tests_smoke.py",
]

REQUIRED_FUNCS = [
    "loadDemo",
    "loadFolderHint",
    "renderClose",
    "copyText",
    "downloadCSV",
]

TABS = ["Today", "Reorder+PO", "Replies", "Leaks", "Listings", "Files"]

FAILURES: list[str] = []


def check(cond: bool, msg: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        FAILURES.append(msg)


def main() -> int:
    print("== WORKSTREAM B smoke: web/close PWA ==")
    print(f"dir: {CLOSE}")

    # 1. Files exist + non-empty.
    for name in REQUIRED_FILES:
        fp = CLOSE / name
        check(fp.is_file(), f"exists: web/close/{name}")
        if fp.is_file():
            try:
                check(fp.stat().st_size > 0, f"non-empty: web/close/{name} ({fp.stat().st_size}B)")
            except OSError as e:
                check(False, f"stat web/close/{name}: {e}")

    idx = CLOSE / "index.html"
    app = CLOSE / "app.js"
    sw = CLOSE / "sw.js"
    manifest = CLOSE / "manifest.webmanifest"

    html = idx.read_text(encoding="utf-8") if idx.is_file() else ""
    js = app.read_text(encoding="utf-8") if app.is_file() else ""
    sw_text = sw.read_text(encoding="utf-8") if sw.is_file() else ""
    man_text = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""

    # 2. index.html references app.js / sw.js / manifest.
    check("app.js" in html, "index.html references app.js")
    check("sw.js" in html, "index.html references sw.js")
    check("manifest.webmanifest" in html or ("rel=\"manifest\"" in html and "manifest" in html),
          "index.html references manifest.webmanifest")
    check(re.search(r'<script[^>]+src=["\']app\.js["\']', html) is not None,
          'index.html has <script src="app.js">')
    check('rel="manifest"' in html, 'index.html has <link rel="manifest">')

    # 3. app.js defines required functions.
    for fn in REQUIRED_FUNCS:
        pat = re.compile(r"(function\s+" + re.escape(fn) + r"\b|"
                         r"(async\s+)?function\s+" + re.escape(fn) + r"\b|"
                         + re.escape(fn) + r"\s*=\s*(async\s*)?function\b|"
                         + re.escape(fn) + r"\s*\(|"
                         r"window\." + re.escape(fn) + r"\b)")
        check(pat.search(js) is not None, f"app.js defines {fn}()")

    # 4. No external CDN script tags (offline rule). No network calls in tests.
    cdn_scripts = re.findall(r'<script[^>]+src=["\']https?://[^"\']+["\']', html, re.IGNORECASE)
    check(len(cdn_scripts) == 0, f"no external CDN <script src=http...> in index.html (found {len(cdn_scripts)})")
    cdn_links = re.findall(r'<link[^>]+href=["\']https?://[^"\']+["\']', html, re.IGNORECASE)
    # Allow nothing external at all (fonts/CDN banned).
    check(len(cdn_links) == 0, f"no external <link href=http...> in index.html (found {len(cdn_links)})")
    check("http://localhost" not in html or "api" in html.lower(),
          "index.html has no hardcoded localhost API origin (same-origin + ?api=)")
    js_cdn = re.findall(r'from\s+["\']https?://|import\(["\']https?://', js)
    check(len(js_cdn) == 0, "app.js has no CDN imports")

    # 5a. API contract strings.
    check("/api/v1/seller/close" in html, "index.html calls POST /api/v1/seller/close")
    check("/api/v1/seller/close.csv" in html, "index.html calls GET /api/v1/seller/close.csv")
    check("/api/v1/seller/close" in js, "app.js calls POST /api/v1/seller/close")
    check("/api/v1/seller/close.csv" in js, "app.js calls GET /api/v1/seller/close.csv")

    # 5b. Tabs.
    for t in TABS:
        check(t in html, f"index.html tab: {t}")

    # 5c. Key UI pieces.
    check("@media print" in html, "index.html printable (@media print)")
    check("no-print" in html, "index.html hides buttons in print (.no-print)")
    check("reorderBody" in html or "reorder" in html.lower(), "index.html reorder table")
    check("ORDER TODAY" in html, "index.html urgency badges (ORDER TODAY)")
    check("replyCards" in html or "reply-card" in html, "index.html reply cards")
    check("poPre" in html or "<pre" in html, "index.html PO <pre>")
    check("leaksList" in html or "leak" in html.lower(), "index.html leaks list")
    check("listingFixes" in html or "listing" in html.lower(), "index.html listing fixes")
    check("ingest" in html.lower(), "index.html ingest report")
    check("file:line" in html, "index.html file:line citations")
    check("localStorage" in js, "app.js uses localStorage (base URL + 24h cache)")
    check("close_last" in js or "24" in js, "app.js 24h cache")
    check("CLOSE_V1" in sw_text, "sw.js versioned CLOSE_V1")
    check("cache-first" in sw_text or "caches.match" in sw_text, "sw.js cache-first")
    check("index.html" in sw_text and "app.js" in sw_text, "sw.js caches index.html+app.js")
    check("manifest" in sw_text, "sw.js caches manifest")
    check("Close" in man_text or "close" in man_text.lower(), "manifest names Close app")
    check("icon.svg" in man_text, "manifest references icon.svg")

    # 5d. README sanity.
    readme = (CLOSE / "README.md").read_text(encoding="utf-8") if (CLOSE / "README.md").is_file() else ""
    check("http.server" in readme, "README how to serve (python3 -m http.server)")
    check("/api/v1/seller/close" in readme, "README API contract")
    check("print" in readme.lower(), "README print flow")

    # 6. Size report + line-count gates (~1200+ for index.html/app.js).
    print("\n-- size report (wc -l + bytes) --")
    total_lines = 0
    for name in REQUIRED_FILES:
        fp = CLOSE / name
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
            print(f"{lines:6d} lines  {size:8d}B  web/close/{name}")
        else:
            print(f"     0 lines         0B  web/close/{name} (MISSING)")
    print(f"{total_lines:6d} lines  total")

    try:
        html_lines = html.count("\n") + (0 if html.endswith("\n") or not html else 1)
        js_lines = js.count("\n") + (0 if js.endswith("\n") or not js else 1)
    except Exception:
        html_lines, js_lines = 0, 0
    check(html_lines >= 1200, f"index.html ~1200+ lines (got {html_lines})")
    check(js_lines >= 1200, f"app.js ~1200+ lines (got {js_lines})")

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
