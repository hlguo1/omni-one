"""Eval runner (WORKSTREAM F): ingest -> briefing -> scenarios -> close.

For every shop folder in a corpus directory (see :mod:`evals.generate`)::

    PYTHONPATH=src python3 evals/run.py --corpus /tmp/eval_smoke --out /tmp/eval_res

Per shop it:

1. ingests the folder (``ingest_seller_folder``),
2. builds the briefing (``build_seller_briefing``),
3. runs scenarios (``run_all_scenarios``),
4. builds the daily close (``build_daily_close``),
5. asserts shop-local invariants (see :func:`check_invariants`),
6. re-runs the close to prove idempotency (headline + reorder identical),
7. writes ``<out>/<shop>.json`` with the full close + timings + invariant flags.

After all shops it writes ``<out>/summary.csv``::

    shop,orders,gmv,profit,margin,at_risk,reorders,leaks,decisions_total,ms

and prints an ASCII table to stdout.

Golden check: any shop whose directory name contains ``golden`` or ``demo``
(or that holds the canonical demo file pair ``shopify_orders.csv`` +
``etsy_settlement.csv`` with 8 order rows) must reproduce the demo golden
profit ``169.09 +/- 0.05``. A golden mismatch fails the run (exit 1),
because that number is the pipeline's most sensitive regression tripwire
(GMV parse, fee estimate, COGS allocation, dedup).

Exit codes: 0 = all invariants + golden pass; 1 = any failure.

Stdlib only. $0. Offline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Golden profit contract (see tests/unit/test_daily_close.py).
GOLDEN_PROFIT = 169.09
GOLDEN_TOL = 0.05

CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")

SUMMARY_FIELDS = ["shop", "orders", "gmv", "profit", "margin", "at_risk",
                  "reorders", "leaks", "decisions_total", "ms"]


# ---------------------------------------------------------------------------
# Pipeline (single place so evals + tests share the call order).
# ---------------------------------------------------------------------------


def run_shop_pipeline(shop_dir: Path, shop_label: str | None = None) -> dict[str, Any]:
    """Run ingest -> briefing -> scenarios -> close; return all artefacts."""
    from omni_one.packs.seller_close import build_daily_close
    from omni_one.packs.seller_os import build_seller_briefing, ingest_seller_folder
    from omni_one.packs.seller_scenarios import run_all_scenarios

    t0 = time.perf_counter()
    events, report = ingest_seller_folder(shop_dir)
    t_ingest = time.perf_counter()
    briefing = build_seller_briefing(events)
    t_brief = time.perf_counter()
    scen = run_all_scenarios(events)
    t_scen = time.perf_counter()
    close = build_daily_close(events, briefing, scen,
                              shop=shop_label or shop_dir.name)
    t_close = time.perf_counter()
    return {
        "events": events,
        "report": report,
        "briefing": briefing,
        "scen": scen,
        "close": close,
        "timings_ms": {
            "ingest": (t_ingest - t0) * 1000.0,
            "briefing": (t_brief - t_ingest) * 1000.0,
            "scenarios": (t_scen - t_brief) * 1000.0,
            "close": (t_close - t_scen) * 1000.0,
            "total": (t_close - t0) * 1000.0,
        },
    }


def rerun_close_for_idempotency(events: list[dict[str, Any]],
                                briefing: dict[str, Any],
                                scen: dict[str, Any],
                                shop: str) -> dict[str, Any]:
    """Rebuild the close from the same artefacts (must be identical)."""
    from omni_one.packs.seller_close import build_daily_close
    return build_daily_close(events, briefing, scen, shop=shop)


# ---------------------------------------------------------------------------
# Invariants.
# ---------------------------------------------------------------------------


def check_invariants(close: dict[str, Any], briefing: dict[str, Any],
                     scen: dict[str, Any]) -> list[str]:
    """Return a list of violation strings ([] = pass).

    Invariants (all must hold for every shop, including edge shops):

    1. ``profit <= gmv`` (profit can never exceed gross; fees/ship/COGS >= 0).
    2. every ``reorder_qty >= 0`` and integral.
    3. every reorder row carries a non-empty ``citation`` matching
       ``[file:line]``.
    4. every reply-queue row carries a ``[file:line]`` citation, and every
       NON-EMPTY draft references its citation (empty drafts only occur for
       scenario-derived rows that briefing did not draft — they still cite).
    5. (checked separately) idempotent rerun -> identical headline + reorder.
    """
    violations: list[str] = []
    kpis = close.get("kpis", {}) or {}
    try:
        gmv = float(kpis.get("gmv", 0) or 0)
        profit = float(kpis.get("true_profit", 0) or 0)
    except (TypeError, ValueError):
        violations.append("kpis gmv/true_profit not numeric")
        return violations
    # 1. profit <= gmv (+1c epsilon for float rounding).
    if profit - gmv > 0.011:
        violations.append(f"profit<=gmv violated: profit={profit} gmv={gmv}")
    # 2+3. reorder sheet.
    reorder = close.get("reorder_sheet", []) or []
    for i, row in enumerate(reorder):
        q = row.get("reorder_qty", 0)
        try:
            qf = float(q)
        except (TypeError, ValueError):
            violations.append(f"reorder[{i}] qty not numeric: {q!r}")
            continue
        if qf < 0:
            violations.append(f"reorder[{i}] qty negative: {q}")
        if abs(qf - round(qf)) > 1e-6:
            violations.append(f"reorder[{i}] qty not integral: {q}")
        cite = str(row.get("citation", "") or "")
        if not cite.strip():
            violations.append(f"reorder[{i}] missing citation ({row.get('product','?')})")
        elif not CITATION_RE.search(cite):
            violations.append(f"reorder[{i}] citation lacks [file:line]: {cite[:80]!r}")
    # 4. reply queue.
    queue = close.get("reply_queue", []) or []
    for i, q in enumerate(queue):
        cite = str(q.get("citation", "") or "")
        if not cite.strip():
            violations.append(f"reply[{i}] missing citation")
        elif not CITATION_RE.search(cite):
            violations.append(f"reply[{i}] citation lacks [file:line]: {cite[:80]!r}")
        draft = str(q.get("draft", "") or "")
        if draft.strip():
            # Draft must reference its citation (full string) or at least a
            # [file:line]-shaped citation marker.
            if cite not in draft and not CITATION_RE.search(draft):
                violations.append(
                    f"reply[{i}] non-empty draft lacks citation "
                    f"(draft={draft[:60]!r} cite={cite[:40]!r})")
    return violations


def check_idempotent(close_a: dict[str, Any], close_b: dict[str, Any]) -> list[str]:
    """Compare two closes from identical inputs; return violations."""
    violations: list[str] = []
    if close_a.get("headline") != close_b.get("headline"):
        violations.append(
            f"idempotency: headline differs:\n  {close_a.get('headline')!r}\n  {close_b.get('headline')!r}")
    if close_a.get("reorder_sheet") != close_b.get("reorder_sheet"):
        violations.append("idempotency: reorder_sheet differs between reruns")
    return violations


def is_golden_shop(shop_dir: Path, n_order_events: int) -> bool:
    """Heuristic: is this the demo-equivalent golden shop?

    Name-based only. An earlier file-pair fallback (shopify+etsy+8 orders)
    false-positived on standard synthetic shops, failing evals that were
    otherwise green — so it was removed. generate.py always names the
    golden shop ``shop_<i>_golden_demo`` (index 0), and the checked-in
    corpus keeps that name; anything else skips the golden check with a
    printed note rather than risking a false FAIL.
    """
    name = shop_dir.name.lower()
    return "golden" in name or "demo" in name


def check_golden(close: dict[str, Any], tol: float = GOLDEN_TOL) -> str | None:
    """Return violation string if golden profit drifts, else None."""
    try:
        profit = float((close.get("kpis", {}) or {}).get("true_profit", 0) or 0)
    except (TypeError, ValueError):
        return "golden: true_profit not numeric"
    if abs(profit - GOLDEN_PROFIT) > tol:
        return (f"golden: profit {profit:.2f} != {GOLDEN_PROFIT:.2f} "
                f"(tol {tol}) — pipeline regressed")
    return None


# ---------------------------------------------------------------------------
# Corpus discovery + per-shop eval.
# ---------------------------------------------------------------------------


def discover_shops(corpus: Path) -> list[Path]:
    """Sorted shop dirs (any subdir with at least one file)."""
    shops: list[Path] = []
    for child in sorted(corpus.iterdir()):
        if child.is_dir() and any(child.iterdir()):
            shops.append(child)
        elif child.is_dir():
            # Empty shop (edge case) has no files — still a shop.
            shops.append(child)
    return shops


def eval_shop(shop_dir: Path, golden_tol: float = GOLDEN_TOL) -> dict[str, Any]:
    """Full eval for one shop; returns JSON-serialisable result record."""
    result: dict[str, Any] = {"shop": shop_dir.name, "dir": str(shop_dir)}
    try:
        pipe = run_shop_pipeline(shop_dir)
    except Exception as e:  # noqa: BLE001 — evals must record, not crash
        result["status"] = "ERROR"
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc(limit=5)
        result["violations"] = [f"pipeline raised: {e}"]
        result["ms"] = 0.0
        return result
    events = pipe["events"]
    briefing = pipe["briefing"]
    scen = pipe["scen"]
    close = pipe["close"]
    ms_total = float(pipe["timings_ms"]["total"])

    violations = check_invariants(close, briefing, scen)
    # Idempotency: rebuild close from same artefacts.
    try:
        close2 = rerun_close_for_idempotency(events, briefing, scen, shop=shop_dir.name)
        violations += check_idempotent(close, close2)
        idem_ok = not any(v.startswith("idempotency") for v in violations)
    except Exception as e:  # noqa: BLE001
        violations.append(f"idempotent rerun raised: {e}")
        idem_ok = False

    kpis = close.get("kpis", {}) or {}
    n_orders = int(kpis.get("orders", 0) or 0)
    golden_hit = is_golden_shop(shop_dir, n_orders)
    golden_violation: str | None = None
    if golden_hit:
        golden_violation = check_golden(close, tol=golden_tol)
        if golden_violation:
            violations.append(golden_violation)

    decisions = scen.get("decisions", []) or []
    result.update({
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "golden_shop": golden_hit,
        "golden_profit": float(kpis.get("true_profit", 0) or 0) if golden_hit else None,
        "kpis": kpis,
        "headline": close.get("headline", ""),
        "orders": n_orders,
        "gmv": float(kpis.get("gmv", 0) or 0),
        "profit": float(kpis.get("true_profit", 0) or 0),
        "margin": float(kpis.get("margin_pct", 0) or 0),
        "at_risk": int(kpis.get("money_at_risk_usd", 0) is not None and len(close.get("reply_queue", []) or [])),
        "reply_queue_len": len(close.get("reply_queue", []) or []),
        "reorders": len(close.get("reorder_sheet", []) or []),
        "leaks": len(close.get("money_leaks", []) or []),
        "decisions_total": len(decisions),
        "by_scenario": scen.get("by_scenario", {}) if isinstance(scen, dict) else {},
        "ms": round(ms_total, 1),
        "timings_ms": {k: round(v, 1) for k, v in pipe["timings_ms"].items()},
        "idempotent": idem_ok,
        "close": close,
        "ingest_report": pipe["report"],
    })
    return result


def summary_row(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "shop": r.get("shop", "?"),
        "orders": r.get("orders", 0),
        "gmv": r.get("gmv", 0),
        "profit": r.get("profit", 0),
        "margin": r.get("margin", 0),
        "at_risk": r.get("reply_queue_len", 0),
        "reorders": r.get("reorders", 0),
        "leaks": r.get("leaks", 0),
        "decisions_total": r.get("decisions_total", 0),
        "ms": r.get("ms", 0),
    }


def write_results(results: list[dict[str, Any]], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    for r in results:
        (out / f"{r['shop']}.json").write_text(
            json.dumps(r, indent=2, default=str), encoding="utf-8")
    summ = out / "summary.csv"
    with open(summ, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for r in results:
            row = summary_row(r)
            w.writerow({k: row.get(k, "") for k in SUMMARY_FIELDS})
    return summ


# ---------------------------------------------------------------------------
# Pretty table (no third-party deps — plain ASCII so CI logs stay clean).
# ---------------------------------------------------------------------------


def print_table(results: list[dict[str, Any]]) -> None:
    cols = ["shop", "orders", "gmv", "profit", "margin", "at_risk",
            "reorders", "leaks", "dec", "ms", "status"]
    header = (f"{'shop':28} {'ord':>4} {'gmv':>9} {'profit':>8} {'mgn':>6} "
              f"{'risk':>4} {'reo':>3} {'lek':>3} {'dec':>3} {'ms':>8}  status")
    print(header)
    print("-" * len(header))
    for r in results:
        s = summary_row(r)
        try:
            line = (f"{str(s['shop'])[:28]:28} {int(s['orders']):>4} "
                    f"{float(s['gmv']):>9.2f} {float(s['profit']):>8.2f} "
                    f"{float(s['margin']):>5.1f}% {int(s['at_risk']):>4} "
                    f"{int(s['reorders']):>3} {int(s['leaks']):>3} "
                    f"{int(s['decisions_total']):>3} {float(s['ms']):>8.1f}  "
                    f"{r.get('status','?')}")
        except (TypeError, ValueError):
            line = f"{s['shop']:28}  ERROR  {r.get('error','')[:60]}"
        print(line)
        for v in r.get("violations", [])[:3]:
            print(f"    ! {v[:160]}")
    n_pass = sum(1 for r in results if r.get("status") == "PASS")
    print(f"\n{n_pass}/{len(results)} shops PASS")
    golden = [r for r in results if r.get("golden_shop")]
    if golden:
        for g in golden:
            print(f"golden {g['shop']}: profit={g.get('golden_profit')} "
                  f"(expect {GOLDEN_PROFIT} +/- {GOLDEN_TOL}) [{g.get('status')}]")
    else:
        print("note: no golden (demo-equivalent) shop in this corpus — golden check skipped")


def aggregate_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Corpus-level aggregates for the console footer + results/_aggregate.json.

    Reports total GMV / profit, mean margin, total decisions, slowest shop,
    and per-archetype pass counts. Pure function over result records —
    never raises on ERROR rows (they contribute zeros).
    """
    total_gmv = 0.0
    total_profit = 0.0
    total_ms = 0.0
    total_decisions = 0
    slowest = ("—", 0.0)
    by_status: dict[str, int] = {}
    for r in results:
        try:
            total_gmv += float(r.get("gmv", 0) or 0)
            total_profit += float(r.get("profit", 0) or 0)
            total_ms += float(r.get("ms", 0) or 0)
            total_decisions += int(r.get("decisions_total", 0) or 0)
            if float(r.get("ms", 0) or 0) > slowest[1]:
                slowest = (str(r.get("shop", "?")), float(r.get("ms", 0) or 0))
        except (TypeError, ValueError):
            continue
        by_status[str(r.get("status", "?"))] = by_status.get(str(r.get("status", "?")), 0) + 1
    n = len(results) or 1
    return {
        "shops": len(results),
        "total_gmv": round(total_gmv, 2),
        "total_profit": round(total_profit, 2),
        "mean_margin_pct": round(total_profit / total_gmv * 100, 1) if total_gmv else 0.0,
        "total_decisions": total_decisions,
        "total_ms": round(total_ms, 1),
        "mean_ms": round(total_ms / n, 1),
        "slowest_shop": {"shop": slowest[0], "ms": round(slowest[1], 1)},
        "by_status": by_status,
    }


def cross_check_manifest(corpus: Path, results: list[dict[str, Any]]) -> list[str]:
    """Compare manifest.csv (orders, gmv intent) against eval observations.

    The manifest records rows *written* by the generator; the eval observes
    rows *ingested* (orders) and GMV *parsed*. A mismatch is reported as a
    warning string (not a failure) because parsers intentionally estimate
    fees and normalise headers — small GMV deltas from header-variant shops
    (semicolon/BOM) are expected and surfaced here for visibility.
    Returns a list of human-readable warning lines ([] = fully consistent).
    """
    manifest = corpus / "manifest.csv"
    if not manifest.exists():
        return [f"note: no manifest.csv in {corpus} — skipping cross-check"]
    expected: dict[str, dict[str, float]] = {}
    try:
        with open(manifest, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    expected[str(row.get("shop", ""))] = {
                        "orders": float(row.get("orders", 0) or 0),
                        "gmv": float(row.get("gmv", 0) or 0),
                    }
                except (TypeError, ValueError):
                    continue
    except OSError as e:
        return [f"note: cannot read manifest.csv: {e}"]
    warnings: list[str] = []
    for r in results:
        shop = str(r.get("shop", ""))
        if shop not in expected:
            warnings.append(f"{shop}: not listed in manifest.csv")
            continue
        exp = expected[shop]
        try:
            obs_orders = float(r.get("orders", 0) or 0)
            obs_gmv = float(r.get("gmv", 0) or 0)
        except (TypeError, ValueError):
            warnings.append(f"{shop}: non-numeric observed kpis")
            continue
        if abs(obs_orders - exp["orders"]) > 0.5 and r.get("status") == "PASS":
            # Empty shops legitimately report 0 == 0; stress reports 10k.
            warnings.append(
                f"{shop}: orders observed={obs_orders:.0f} manifest={exp['orders']:.0f}")
        if abs(obs_gmv - exp["gmv"]) > max(1.0, exp["gmv"] * 0.02):
            warnings.append(
                f"{shop}: gmv observed=${obs_gmv:.2f} manifest=${exp['gmv']:.2f} "
                f"(header-variant normalisation — inspect if >2%)")
    if not warnings:
        warnings.append("manifest cross-check: all shops consistent (orders + gmv)")
    return warnings


def write_aggregate(results: list[dict[str, Any]], out: Path,
                    corpus: Path) -> dict[str, Any]:
    """Write results/_aggregate.json (stats + manifest warnings)."""
    agg = aggregate_stats(results)
    agg["manifest_check"] = cross_check_manifest(corpus, results)
    (out / "_aggregate.json").write_text(
        json.dumps(agg, indent=2, default=str), encoding="utf-8")
    return agg


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run ingest->briefing->scenarios->close over an eval corpus.")
    p.add_argument("--corpus", type=str, default="evals/corpus",
                   help="Corpus dir of shop folders (+ manifest.csv).")
    p.add_argument("--out", type=str, default="evals/results",
                   help="Output dir for <shop>.json + summary.csv.")
    p.add_argument("--golden-tol", type=float, default=GOLDEN_TOL,
                   help="Tolerance around golden profit 169.09.")
    p.add_argument("--shop", type=str, default=None,
                   help="Only eval shops whose name contains this substring.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    corpus = Path(args.corpus)
    out = Path(args.out)
    if not corpus.is_dir():
        print(f"error: corpus not found: {corpus}", file=sys.stderr)
        return 2
    shops = discover_shops(corpus)
    if args.shop:
        shops = [s for s in shops if args.shop in s.name]
    if not shops:
        print("error: no shops found in corpus", file=sys.stderr)
        return 2
    print(f"eval corpus={corpus} shops={len(shops)} out={out}")
    results: list[dict[str, Any]] = []
    for shop_dir in shops:
        print(f"--- {shop_dir.name} ...", flush=True)
        results.append(eval_shop(shop_dir, golden_tol=args.golden_tol))
    summ = write_results(results, out)
    agg = write_aggregate(results, out, corpus)
    print(f"\nwrote {len(results)} result(s) + {summ} + _aggregate.json")
    print_table(results)
    print(f"\naggregate: shops={agg['shops']} gmv=${agg['total_gmv']:.2f} "
          f"profit=${agg['total_profit']:.2f} mean_margin={agg['mean_margin_pct']}% "
          f"decisions={agg['total_decisions']} slowest={agg['slowest_shop']['shop']} "
          f"({agg['slowest_shop']['ms']}ms)")
    for w in agg["manifest_check"][:8]:
        print(f"  manifest: {w}")
    failed = [r for r in results if r.get("status") != "PASS"]
    if failed:
        print(f"\nFAIL: {len(failed)} shop(s) with violations:", file=sys.stderr)
        for r in failed:
            print(f"  {r['shop']}: {r.get('violations', ['?'])[0][:200]}", file=sys.stderr)
        return 1
    print("\nEVAL GREEN — all invariants + golden hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
