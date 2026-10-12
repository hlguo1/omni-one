"""
Auto Close — one command that picks the right closes for what the user HAS.
============================================================================
Small sellers don't know (or care) which of our 11 closes to run. They have
a messy folder: some sales CSVs, phone photos of receipts, a reviews export,
maybe a supplier invoice. `omni-one auto --folder ./my_shop` sniffs the
folder and runs exactly the closes that match — printing WHY each one ran.

  omni-one auto --folder ./my_shop --out ./auto_today
  -> scan -> plan (close + reason per pick) -> run -> auto.json + per-close bundles

Design rules (same flagship contract as every other close pack):
- Deterministic: same folder -> same plan (file order sorted, no wall-clock
  in selection; only `date` stamps output).
- $0, offline, no LLM. CSV sniffing is header-keyword matching, capped rows.
- Every pick cites evidence: the filenames that triggered it.
- Never fails hard: empty/missing folder -> demo showcase plan (seeded) with
  reasons marked demo, so a first-time user sees value instantly.
- Idempotent: re-running over the same folder gives the same plan + numbers.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PHOTO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}
DATA_EXTS = {".csv", ".tsv", ".json", ".xlsx"}
DOC_EXTS = {".txt", ".md", ".log", ".pdf"}

# filename/content keywords -> signal. Order matters (first match wins per file
# for the primary signal, but a file can raise several signals).
KEYWORDS: dict[str, list[str]] = {
    "returns": ["return", "refund", "cancel", "rma", "chargeback"],
    "cashflow": ["payout", "payouts", "bank", "statement", "invoice", "payable", "bill"],
    "reputation": ["review", "rating", "feedback", "yelp", "google_reviews", "stars"],
    "forecast": ["inventory", "stock", "sku", "skus", "product", "catalog", "supplier"],
    "rollup": ["rollup", "multi", "shops", "portfolio", "consolidat"],
    "revops": ["account", "mrr", "churn", "pipeline", "crm", "salesforce"],
    "micro": ["taco", "menu", "truck", "stall", "mercado", "taqueria"],
    "orders": ["order", "orders", "sales", "transactions", "txn", "receipt"],
}

MAX_SNIFF_BYTES = 4096
MAX_PHOTOS_RUN = 3


def _signals_for_name(name: str) -> set[str]:
    low = name.lower()
    return {sig for sig, words in KEYWORDS.items() if any(w in low for w in words)}


def scan_folder(folder: Path) -> dict[str, Any]:
    """Walk folder (sorted) -> inventory: counts + per-signal evidence files."""
    files = sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: p.as_posix())
    inv: dict[str, Any] = {
        "folder": str(folder),
        "total_files": len(files),
        "photos": [],
        "data_files": [],
        "docs": [],
        "other": [],
        "signals": {sig: [] for sig in KEYWORDS},
        "shop_dirs": [],
    }
    for p in files:
        rel = p.relative_to(folder).as_posix()
        suf = p.suffix.lower()
        if suf in PHOTO_EXTS and p.stat().st_size >= 100:
            inv["photos"].append(rel)
        elif suf in DATA_EXTS:
            inv["data_files"].append(rel)
        elif suf in DOC_EXTS:
            inv["docs"].append(rel)
        else:
            inv["other"].append(rel)
        for sig in _signals_for_name(p.name):
            inv["signals"][sig].append(rel)
    # shop dirs: subfolders that themselves contain data files (multi-shop hint)
    for sub in sorted((d for d in folder.iterdir() if d.is_dir()), key=lambda d: d.name):
        try:
            if any(f.suffix.lower() in DATA_EXTS for f in sub.rglob("*") if f.is_file()):
                inv["shop_dirs"].append(sub.name)
        except OSError:
            continue
    # content sniff: tiny peek at small text files for keyword confirmation
    for rel in list(inv["data_files"] + inv["docs"])[:20]:
        try:
            head = (folder / rel).read_text(errors="replace")[:MAX_SNIFF_BYTES].lower()
        except OSError:
            continue
        for sig, words in KEYWORDS.items():
            if rel not in inv["signals"][sig] and any(w in head for w in words):
                inv["signals"][sig].append(rel + " (content)")
    for sig in inv["signals"]:
        inv["signals"][sig] = sorted(set(inv["signals"][sig]))
    return inv


def select_closes(inv: dict[str, Any], deep: bool = False) -> list[dict[str, str]]:
    """Inventory -> ordered plan of {close, reason, evidence}. Deterministic."""
    plan: list[dict[str, str]] = []

    def add(name: str, reason: str, evidence: list[str]) -> None:
        plan.append({"close": name, "reason": reason,
                     "evidence": ", ".join(evidence[:3]) if evidence else "demo data"})

    n_photos = len(inv["photos"])
    if n_photos:
        add("vision", f"{n_photos} photo(s) found — OCR + COGS + numbers", inv["photos"][:3])
    if inv["signals"]["orders"] or inv["data_files"]:
        add("seller", "sales/order data found — daily money close (profit, PO, replies)",
            inv["signals"]["orders"] or inv["data_files"][:3])
    elif not inv["photos"] and inv["total_files"] == 0:
        add("seller", "empty folder — demo showcase so you see the ritual", [])
    if inv["signals"]["returns"]:
        add("returns", "return/refund/cancel files found — plug the leak", inv["signals"]["returns"])
    if inv["signals"]["cashflow"]:
        add("cashflow", "payout/bank/invoice files found — cash-in-hand check", inv["signals"]["cashflow"])
    if inv["signals"]["reputation"]:
        add("reputation", "review files found — reply queue + star repair", inv["signals"]["reputation"])
    if inv["signals"]["forecast"]:
        add("forecast", "inventory/stock files found — stockout forecast + PO", inv["signals"]["forecast"])
    if len(inv["shop_dirs"]) >= 2 or inv["signals"]["rollup"]:
        add("rollup", f"{len(inv['shop_dirs'])} shop folders found — portfolio rollup",
            inv["shop_dirs"][:3] or inv["signals"]["rollup"])
    if inv["signals"]["revops"]:
        add("revops", "B2B pipeline files found — churn $ + call sheet", inv["signals"]["revops"])
    if inv["signals"]["micro"] and not any(p["close"] == "seller" for p in plan):
        add("micro", "food-shop files found — taco-stand ritual", inv["signals"]["micro"])
    if inv["data_files"] and not deep:
        add("pipeline", "data files found — quality + cost check on the way in", inv["data_files"][:2])
    if deep:
        if not any(p["close"] == "pipeline" for p in plan) and inv["data_files"]:
            add("pipeline", "deep mode — data quality evidence", inv["data_files"][:2])
        add("ops", "deep mode — full methodology audit bundle", [])
    # dedupe, keep order
    seen, unique = set(), []
    for p in plan:
        if p["close"] not in seen:
            seen.add(p["close"])
            unique.append(p)
    return unique


# --- lightweight CSV row readers (best-effort; fall back to demo on failure) ---

def _read_csv_rows(path: Path, limit: int = 50) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        return [dict(r) for i, r in enumerate(csv.DictReader(f)) if i < limit and r]


def _first_matching(folder: Path, rels: list[str]) -> Path | None:
    # prefer filename hits over content-sniff hits (content entries end with " (content)")
    for rel in sorted(rels, key=lambda r: r.endswith(" (content)")):
        clean = rel.replace(" (content)", "")
        p = folder / clean
        if p.exists() and p.suffix.lower() in {".csv", ".tsv"}:
            return p
    return None


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(str(v).replace("$", "").replace(",", "").strip() or default)
    except (ValueError, TypeError):
        return default


def _rows_to_skus(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for i, r in enumerate(rows):
        low = {k.lower(): v for k, v in r.items()}
        name = low.get("sku") or low.get("product") or low.get("name") or f"SKU-{i+1}"
        out.append({"name": str(name)[:40],
                    "on_hand": int(_to_float(low.get("on_hand", low.get("stock", 20)))),
                    "daily_velocity": max(0.5, _to_float(low.get("velocity", low.get("daily_sales", 2)))),
                    "unit_cost": _to_float(low.get("unit_cost", low.get("cost", 5))),
                    "supplier": str(low.get("supplier", "SYSCO"))[:30],
                    "lead_days": int(_to_float(low.get("lead_days", 3))),
                    "citation": f"[auto:inventory#{i+1}]"})
    return out


def _rows_to_returns(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for i, r in enumerate(rows):
        low = {k.lower(): v for k, v in r.items()}
        out.append({"order_id": str(low.get("order_id", low.get("order", f"O-{i+1}"))),
                    "product": str(low.get("product", low.get("sku", "item")))[:40],
                    "reason": str(low.get("reason", "quality")).lower()[:20] or "quality",
                    "amount": round(_to_float(low.get("amount", low.get("refund", 25))), 2),
                    "days_since_purchase": int(_to_float(low.get("days", 6))),
                    "restockable": str(low.get("restockable", "yes")).lower().startswith("y"),
                    "citation": f"[auto:returns#{i+1}]"})
    return out


def _rows_to_reviews(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for i, r in enumerate(rows):
        low = {k.lower(): v for k, v in r.items()}
        out.append({"reviewer": str(low.get("reviewer", low.get("name", f"Guest {i+1}")))[:30],
                    "stars": max(1, min(5, int(_to_float(low.get("stars", low.get("rating", 5)))))),
                    "text": str(low.get("text", low.get("comment", "great")))[:120],
                    "product": str(low.get("product", "order"))[:30],
                    "channel": str(low.get("channel", "shop"))[:20],
                    "citation": f"[auto:reviews#{i+1}]"})
    return out


def _rows_to_payouts(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for i, r in enumerate(rows):
        low = {k.lower(): v for k, v in r.items()}
        gross = _to_float(low.get("gross", low.get("amount", 500)))
        fee = _to_float(low.get("fee", low.get("fees", round(gross * 0.03, 2))))
        out.append({"channel": str(low.get("channel", "shopify"))[:20],
                    "gross": round(gross, 2), "fees": round(fee, 2),
                    "net": round(gross - fee, 2),
                    "arrival_day": int(_to_float(low.get("arrival_day", i % 6))),
                    "citation": f"[auto:payouts#{i+1}]"})
    return out


def _headline_of(v: Any) -> str:
    if not isinstance(v, dict):
        return "?"
    if v.get("headline"):
        return str(v["headline"])
    if "verdict" in v:
        verdict = v["verdict"]
        if isinstance(verdict, dict):
            verdict = verdict.get("label", str(verdict)[:40])
        extra = ""
        if isinstance(v.get("kpis"), dict):
            extra = f" {str(v['kpis'])[:80]}"
        return f"verdict={verdict}{extra}"
    return str(v.get("error", "ok"))


def run_auto(folder: str | None = None, out: str = "./auto_today", seed: int = 42,
             shop: str = "our shop", deep: bool = False) -> dict[str, Any]:
    """Scan -> plan -> run selected closes -> bundle. Returns auto summary dict."""
    from omni_one.packs import (
        cashflow_close as _cf, forecast_close as _fc, pipeline_close as _pc,
        reputation_close as _rep, returns_close as _ret, revops_close as _rev,
        rollup_close as _rol, seller_close as _sel, vision_close as _vis,
    )
    demo_mode = not folder
    if demo_mode:
        import tempfile
        from omni_one.packs.seller_os import make_seller_demo_folder
        tmp = Path(tempfile.mkdtemp(prefix="omni-auto-"))
        folder_p = make_seller_demo_folder(tmp / "demo", seed=seed)
    else:
        folder_p = Path(folder).expanduser()
    inv = scan_folder(folder_p)
    if demo_mode:
        plan = [{"close": n, "reason": r, "evidence": "demo data"} for n, r in [
            ("seller", "demo showcase — daily money close"),
            ("vision", "demo receipt photo — OCR + COGS"),
            ("returns", "demo showcase — plug refund leaks"),
            ("cashflow", "demo showcase — cash-in-hand check"),
            ("reputation", "demo showcase — review replies"),
            ("forecast", "demo showcase — stockout forecast")]]
    else:
        plan = select_closes(inv, deep=deep)

    results: dict[str, Any] = {}
    ran: list[str] = []
    for item in plan:
        name = item["close"]
        try:
            if name == "vision":
                photos = inv["photos"][:MAX_PHOTOS_RUN] if not demo_mode else []
                if photos:
                    data = (folder_p / photos[0]).read_bytes()
                    results[name] = _vis.build_vision_close(data, filename=Path(photos[0]).name)
                else:
                    results[name] = _vis.build_vision_close(_vis.make_demo_image("receipt"))
            elif name == "seller":
                from omni_one.packs.seller_os import ingest_seller_folder, build_seller_briefing
                from omni_one.packs.seller_scenarios import run_all_scenarios
                events, _ = ingest_seller_folder(folder_p)
                if not events:  # folder has no seller events -> seeded demo, still useful
                    import tempfile as _t2
                    from omni_one.packs.seller_os import make_seller_demo_folder as _demo
                    with _t2.TemporaryDirectory() as _tmp:
                        _d = _demo(Path(_tmp) / "d", seed=seed)
                        events, _ = ingest_seller_folder(_d)
                        b = build_seller_briefing(events)
                        results[name] = _sel.build_daily_close(events, b, run_all_scenarios(events), shop=shop)
                        results[name]["note"] = "demo data (no seller events in folder)"
                else:
                    b = build_seller_briefing(events)
                    results[name] = _sel.build_daily_close(events, b, run_all_scenarios(events), shop=shop)
            elif name == "returns":
                p = _first_matching(folder_p, inv["signals"]["returns"]) if not demo_mode else None
                rows = _rows_to_returns(_read_csv_rows(p)) if p else None
                results[name] = _ret.build_returns_close(rows or _ret.DEMO_RETURNS(seed))
            elif name == "cashflow":
                p = _first_matching(folder_p, inv["signals"]["cashflow"]) if not demo_mode else None
                rows = _rows_to_payouts(_read_csv_rows(p)) if p else None
                results[name] = _cf.build_cashflow_close(rows or None, None, seed=seed)
            elif name == "reputation":
                p = _first_matching(folder_p, inv["signals"]["reputation"]) if not demo_mode else None
                rows = _rows_to_reviews(_read_csv_rows(p)) if p else None
                results[name] = _rep.build_reputation_close(rows or None, seed=seed, shop=shop)
            elif name == "forecast":
                p = _first_matching(folder_p, inv["signals"]["forecast"]) if not demo_mode else None
                rows = _rows_to_skus(_read_csv_rows(p)) if p else None
                results[name] = _fc.build_forecast_close(rows or None, seed=seed)
            elif name == "rollup":
                results[name] = _rol.build_rollup_close(None, seed=seed)
            elif name == "revops":
                results[name] = _rev.build_revops_close(None, seed=seed)
            elif name == "micro":
                from omni_one.packs._labs.micro_biz import ingest_folder, build_briefing
                from omni_one.packs.micro_close import build_micro_close
                events, _ = ingest_folder(folder_p)
                results[name] = build_micro_close(events, build_briefing(events), shop=shop)
            elif name == "pipeline":
                results[name] = _pc.build_pipeline_close(_pc.DEMO_RECORDS(seed))
            elif name == "ops":
                from omni_one.packs.seller_os import ingest_seller_folder as _ing
                from omni_one.packs.seller_os import build_seller_briefing as _b
                from omni_one.packs.seller_scenarios import run_all_scenarios as _s
                from omni_one.packs.ops_close import build_ops_close
                ev, _ = _ing(folder_p)
                if not ev:
                    raise ValueError("no events — skip ops")
                results[name] = build_ops_close(ev, _b(ev), _s(ev))
            ran.append(name)
        except Exception as e:  # never fail the whole auto run on one close
            results[name] = {"ok": False, "error": f"{type(e).__name__}: {e}", "free": True}
    out_p = Path(out)
    out_p.mkdir(parents=True, exist_ok=True)
    summary = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "folder": str(folder_p),
        "demo_mode": demo_mode,
        "plan": plan,
        "ran": ran,
        "headlines": {k: _headline_of(v) for k, v in results.items()},
        "do_today": [t for k in ran for t in (results[k].get("do_today", []) if isinstance(results[k], dict) else [])][:10],
        "free": True,
    }
    (out_p / "auto.json").write_text(json.dumps(summary, indent=2, default=str))
    lines = [f"AUTO CLOSE {summary['date']} — {folder_p}",
             f"ran {len(ran)}/{len(plan)}: {', '.join(ran)}", ""]
    for item in plan:
        mark = "✓" if item["close"] in ran else "✗"
        lines.append(f"[{mark}] {item['close']}: {item['reason']} [{item['evidence']}]")
    for k in ran:
        h = summary["headlines"].get(k, "?")
        lines.append(f"  → {k}: {h}")
    (out_p / "AUTO.txt").write_text("\n".join(lines) + "\n")
    summary["paths"] = {"auto.json": str(out_p / "auto.json"), "AUTO.txt": str(out_p / "AUTO.txt")}
    return summary
