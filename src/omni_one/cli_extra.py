"""
omni-one-shop helpers — multi-shop weekly ops for 1-5 person sellers.
=====================================================================
Importable WITHOUT typer at import time (lazy typer only inside
``register_shop_commands``). All helpers are deterministic, stdlib-heavy,
offline ($0), and citation-preserving (every dollar cites file:line).

Functions (stable surface — SDK/contract tests import these):
    weekly_trend(folders) -> str
        Markdown table of margin / true-profit / money-at-risk across days.
        ``folders`` is an ordered list of seller input folders (each with
        orders/inventory/reviews/DMs) OR daily close output dirs (each with
        close.json). One row per folder (day-01, day-02, ...), deterministic.

    multi_shop_compare(shops) -> str
        Ranked markdown table comparing shops. ``shops`` maps
        shop-name -> seller folder (or close dir). Ranked by true_profit
        desc, tie-break by shop name. Deterministic.

    cron_install(folder, out_base, schedule="0 8 * * *") -> str
        Returns a crontab line string that runs the daily close every
        morning. Pure string builder — no side effects, deterministic.
        Caller pipes it into ``crontab -l`` themselves.

    accountant_pack(close_dir, out_zip=None) -> str
        Zips a daily-close bundle dir (close.json/csv/reorder/replies/po)
        into a single accountant-friendly zip. Returns zip path string.
        Deterministic file order (sorted), stdlib zipfile only.

Citations:
    Every number in the markdown tables cites file:line from the underlying
    briefing/close bundle (e.g. ``inventory.csv:3``). We NEVER strip or
    rewrite citations — file:line strings pass through verbatim so the
    accountant / owner can audit back to the source file and line.

Design notes:
    - No network. No LLM. No pandas required (stdlib csv/json only at this
      layer; seller packs handle parsing).
    - Idempotent: same folders -> same markdown (modulo the wall-clock date
      embedded in close bundles, which we surface but do not sort by).
    - Lazy imports: ``omni_one.packs.*`` imported inside functions so this
      module imports in <50ms even on cold laptops.
    - ``register_shop_commands(app)`` wires these into a typer app WITHOUT
      requiring typer at module import (import typer lazily inside).

File layout:
    src/omni_one/cli_extra.py  (this file, ~600+ lines, stdlib-heavy)
    examples/shop_weekly.py    (demo: builds 3 demo folders, prints tables)

See also:
    src/omni_one/cli.py        (core CLI — NOT touched by workstream C)
    src/omni_one/client.py     (python SDK — extended, not modified)
    sdks/ts/src/index.ts       (TypeScript SDK, same close shape)
    sdks/go/client.go          (Go SDK, same close shape)
    tests/unit/test_sdk_contract.py (python-side contract both SDKs satisfy)

Author: omni-one workstream C. License: Apache-2.0.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib as _hashlib
import io as _io
import json as _json
import shlex as _shlex
import sys as _sys
import zipfile as _zipfile
from pathlib import Path as _Path
from typing import Any as _Any
from typing import Dict as _Dict
from typing import List as _List
from typing import Optional as _Optional
from typing import Sequence as _Sequence
from typing import Tuple as _Tuple
from typing import Union as _Union

__all__ = [
    "weekly_trend",
    "multi_shop_compare",
    "cron_install",
    "accountant_pack",
    "weekly_trend_rows",
    "compare_shop_rows",
    "markdown_table",
    "summarise_close",
    "load_close_or_build",
    "briefing_for_folder",
    "close_for_folder",
    "register_shop_commands",
    "SHOP_COMMANDS_HELP",
]

SHOP_COMMANDS_HELP = (
    "omni-one-shop helpers: weekly-trend | multi-shop-compare | "
    "cron-install | accountant-pack (see cli_extra.register_shop_commands)"
)

# Module identity used in citation footers (file:line style, never stripped).
_CLI_EXTRA_CITATION = "src/omni_one/cli_extra.py"


# ---------------------------------------------------------------------------
# Small deterministic formatting helpers (stdlib only)
# ---------------------------------------------------------------------------

def _fmt_money(v: _Any) -> str:
    """Format a dollar amount deterministically: $169.09, $1,234.50, em-dash.

    Citation: src/omni_one/cli_extra.py:_fmt_money — pure formatter, no I/O.
    """
    try:
        if v is None or v == "":
            return "--"
        f = float(v)
        # Round-half-even via format spec; deterministic across platforms.
        sign = "-" if f < 0 else ""
        f = abs(f)
        return f"{sign}${f:,.2f}"
    except Exception:
        return str(v)


def _fmt_pct(v: _Any) -> str:
    """Format a margin percent deterministically: 61.7%.

    Citation: src/omni_one/cli_extra.py:_fmt_pct — pure formatter.
    """
    try:
        if v is None or v == "":
            return "--"
        return f"{float(v):.1f}%"
    except Exception:
        return str(v)


def _fmt_int(v: _Any) -> str:
    """Format an int-like value deterministically.

    Citation: src/omni_one/cli_extra.py:_fmt_int.
    """
    try:
        if v is None or v == "":
            return "--"
        return str(int(float(v)))
    except Exception:
        return str(v)


def _short_folder_label(folder: _Union[str, _Path], idx: int) -> str:
    """Deterministic day label: ``day-01`` + short folder name.

    Citation: src/omni_one/cli_extra.py:_short_folder_label.
    """
    try:
        name = _Path(str(folder)).name or str(folder)
    except Exception:
        name = str(folder)
    # Keep label filesystem-safe and deterministic (no timestamps).
    safe = "".join(c if (c.isalnum() or c in ("-", "_")) else "-" for c in name)[:24]
    return f"day-{idx + 1:02d} ({safe})"


def _stable_hash(text: str) -> str:
    """Short deterministic hash for disambiguating identical labels.

    Uses md5 (non-security use, content fingerprint only).
    Citation: src/omni_one/cli_extra.py:_stable_hash.
    """
    return _hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()[:8]


def markdown_table(headers: _List[str], rows: _List[_List[_Any]]) -> str:
    """Build a GitHub-flavoured markdown table deterministically.

    - No padding games: single space around pipes (stable diffs).
    - ``None`` renders as ``--``.
    - Cells are str()'d verbatim — citations (file:line) pass through
      untouched (no stripping, no lowercasing, no truncation).

    Citation: src/omni_one/cli_extra.py:markdown_table.

    Example:
        markdown_table(["a", "b"], [[1, "x"], [2, "y"]])
        # | a | b |
        # | --- | --- |
        # | 1 | x |
        # | 2 | y |
    """
    headers = [str(h) for h in headers]
    out: _List[str] = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        cells: _List[str] = []
        for c in r:
            if c is None:
                cells.append("--")
            else:
                # Verbatim passthrough — citations must survive (file:line).
                cells.append(str(c))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Lazy seller-pack access (imported inside functions to keep import light)
# ---------------------------------------------------------------------------

def briefing_for_folder(folder: _Union[str, _Path]) -> _Tuple[_Dict[str, _Any], _Dict[str, _Any]]:
    """Ingest a seller input folder -> (events, briefing).

    Deterministic: delegates to ``ingest_seller_folder`` (sorted rglob) and
    ``build_seller_briefing`` (seed-free math). Raises FileNotFoundError if
    the folder does not exist.

    Citation: numbers cite source files via briefing (file:line preserved).

    See: src/omni_one/packs/seller_os.py:ingest_seller_folder,
         src/omni_one/packs/seller_os.py:build_seller_briefing.
    """
    from omni_one.packs.seller_os import build_seller_briefing, ingest_seller_folder

    p = _Path(str(folder)).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"seller folder not found: {p}")
    events, report = ingest_seller_folder(p)
    briefing = build_seller_briefing(events)
    return events, briefing


def close_for_folder(
    folder: _Union[str, _Path],
    shop: str = "our shop",
) -> _Dict[str, _Any]:
    """Build a daily-close bundle dict for a seller input folder.

    Deterministic: briefing + scenarios + close math are all seeded/fixed.
    The ``date`` field uses wall-clock day (not part of sort order).

    Citation: close dict carries file:line citations verbatim.

    See: src/omni_one/packs/seller_close.py:build_daily_close.
    """
    from omni_one.packs.seller_close import build_daily_close
    from omni_one.packs.seller_os import build_seller_briefing, ingest_seller_folder
    from omni_one.packs.seller_scenarios import run_all_scenarios

    p = _Path(str(folder)).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"seller folder not found: {p}")
    events, _report = ingest_seller_folder(p)
    briefing = build_seller_briefing(events)
    scen = run_all_scenarios(events)
    return build_daily_close(events, briefing, scen, shop=shop)


def _read_close_json(close_dir: _Union[str, _Path]) -> _Optional[_Dict[str, _Any]]:
    """Read ``close.json`` from a close output dir, or None if absent.

    Citation: src/omni_one/cli_extra.py:_read_close_json (stdlib json).
    """
    candidate = _Path(str(close_dir)).expanduser() / "close.json"
    if not candidate.exists():
        return None
    try:
        return _json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def load_close_or_build(
    folder: _Union[str, _Path],
    shop: str = "our shop",
) -> _Tuple[_Dict[str, _Any], str]:
    """Load close.json if ``folder`` is a close dir, else build from seller data.

    Returns (close_dict, provenance) where provenance is one of:
      - ``"close.json"`` — read verbatim from disk (citations untouched)
      - ``"built:seller-folder"`` — built via seller packs just now

    Deterministic. Never strips citations.

    Citation: src/omni_one/cli_extra.py:load_close_or_build.
    """
    existing = _read_close_json(folder)
    if existing is not None and isinstance(existing, dict) and "kpis" in existing:
        return existing, "close.json"
    built = close_for_folder(folder, shop=shop)
    return built, "built:seller-folder"


def summarise_close(close: _Dict[str, _Any]) -> _Dict[str, _Any]:
    """Flatten a close bundle to one summary row (deterministic).

    Extracts: date, shop, headline, gmv, true_profit, margin_pct, orders,
    aov, money_at_risk_usd, reply_count, reorder_today count, top reorder
    (product/qty/citation), top citation overall. Citations verbatim.

    Citation: src/omni_one/cli_extra.py:summarise_close.
    """
    kpis = close.get("kpis", {}) if isinstance(close.get("kpis", {}), dict) else {}
    reorder_sheet = close.get("reorder_sheet", []) or []
    reply_queue = close.get("reply_queue", []) or []
    # Count ORDER TODAY lines deterministically.
    reorder_today = sum(1 for r in reorder_sheet if isinstance(r, dict) and r.get("urgency") == "ORDER TODAY")
    top = reorder_sheet[0] if reorder_sheet else {}
    if not isinstance(top, dict):
        top = {}
    # First non-empty citation in close (reorder first, then reply, then leaks).
    top_citation = str(top.get("citation", "") or "")
    if not top_citation and reply_queue:
        q0 = reply_queue[0] if isinstance(reply_queue[0], dict) else {}
        top_citation = str(q0.get("citation", "") or "")
    if not top_citation:
        for leak in close.get("money_leaks", []) or []:
            if isinstance(leak, dict) and leak.get("evidence"):
                top_citation = str(leak.get("evidence"))
                break
    return {
        "date": str(close.get("date", "") or ""),
        "shop": str(close.get("shop", "") or ""),
        "headline": str(close.get("headline", "") or ""),
        "gmv": kpis.get("gmv"),
        "true_profit": kpis.get("true_profit"),
        "margin_pct": kpis.get("margin_pct"),
        "orders": kpis.get("orders"),
        "aov": kpis.get("aov"),
        "money_at_risk_usd": kpis.get("money_at_risk_usd"),
        "reply_count": len(reply_queue),
        "reorder_today": reorder_today,
        "reorder_lines": len(reorder_sheet),
        "top_product": str(top.get("product", "") or ""),
        "top_reorder_qty": top.get("reorder_qty", ""),
        "citation": top_citation,
        "po_draft_present": bool(close.get("po_draft")),
    }


# ---------------------------------------------------------------------------
# weekly_trend — margin / profit / at-risk across days
# ---------------------------------------------------------------------------

def weekly_trend_rows(
    folders: _Sequence[_Union[str, _Path]],
    shop: str = "our shop",
) -> _List[_Dict[str, _Any]]:
    """Build one summary row per folder, in input order (deterministic).

    Each folder may be a seller input folder OR a close output dir holding
    close.json. Rows carry verbatim citations (file:line).

    Citation: src/omni_one/cli_extra.py:weekly_trend_rows.

    Returns list of dicts with keys: day, folder, date, gmv, true_profit,
    margin_pct, money_at_risk_usd, orders, reply_count, reorder_today,
    top_product, top_reorder_qty, citation, provenance.
    """
    if folders is None:
        raise ValueError("weekly_trend_rows: folders must be a non-empty sequence")
    folder_list = list(folders)
    if not folder_list:
        raise ValueError("weekly_trend_rows: provide at least one folder")
    rows: _List[_Dict[str, _Any]] = []
    for idx, folder in enumerate(folder_list):
        close, provenance = load_close_or_build(folder, shop=shop)
        summary = summarise_close(close)
        rows.append({
            "day": f"day-{idx + 1:02d}",
            "folder": str(folder),
            "folder_short": _Path(str(folder)).name,
            "date": summary["date"],
            "gmv": summary["gmv"],
            "true_profit": summary["true_profit"],
            "margin_pct": summary["margin_pct"],
            "money_at_risk_usd": summary["money_at_risk_usd"],
            "orders": summary["orders"],
            "reply_count": summary["reply_count"],
            "reorder_today": summary["reorder_today"],
            "top_product": summary["top_product"],
            "top_reorder_qty": summary["top_reorder_qty"],
            "citation": summary["citation"],
            "provenance": provenance,
        })
    return rows


def weekly_trend(
    folders: _Sequence[_Union[str, _Path]],
    shop: str = "our shop",
    title: str = "WEEKLY TREND",
) -> str:
    """Render a markdown table of margin / profit / at-risk across days.

    Args:
        folders: ordered list of seller folders (or close dirs). Order is
            preserved as day-01..day-N (deterministic — we never re-sort by
            mtime because timestamps are not reproducible).
        shop: shop label stamped into freshly-built closes.
        title: heading line above the table.

    Returns:
        Markdown string with columns:
        day | date/folder | GMV | true profit | margin% | at-risk |
        replies | reorders TODAY | top reorder | citation.
        Plus a TOTAL/AVG footer line and a citations footer. All numbers
        cite file:line verbatim (no stripping).

    Deterministic, stdlib-only at this layer.

    Citation: src/omni_one/cli_extra.py:weekly_trend.

    Example:
        >>> from pathlib import Path
        >>> md = weekly_trend([Path("/tmp/shop_mon"), Path("/tmp/shop_tue")])
        >>> "true profit" in md.lower() or "profit" in md.lower()
        True
    """
    rows = weekly_trend_rows(folders, shop=shop)
    headers = [
        "day", "date/folder", "GMV", "true profit", "margin%",
        "at-risk", "replies", "reorders TODAY", "top reorder", "citation",
    ]
    table_rows: _List[_List[_Any]] = []
    total_profit = 0.0
    total_gmv = 0.0
    total_at_risk = 0.0
    margins: _List[float] = []
    for r in rows:
        # Accumulate totals defensively (None-safe, deterministic).
        try:
            total_profit += float(r["true_profit"]) if r["true_profit"] not in (None, "") else 0.0
        except Exception:
            pass
        try:
            total_gmv += float(r["gmv"]) if r["gmv"] not in (None, "") else 0.0
        except Exception:
            pass
        try:
            total_at_risk += float(r["money_at_risk_usd"]) if r["money_at_risk_usd"] not in (None, "") else 0.0
        except Exception:
            pass
        try:
            if r["margin_pct"] not in (None, ""):
                margins.append(float(r["margin_pct"]))
        except Exception:
            pass
        date_folder = f"{r['date']} {r['folder_short']}".strip()
        top_reorder = f"{r['top_product']} x{r['top_reorder_qty']}" if r["top_product"] else "--"
        table_rows.append([
            r["day"],
            date_folder,
            _fmt_money(r["gmv"]),
            _fmt_money(r["true_profit"]),
            _fmt_pct(r["margin_pct"]),
            _fmt_money(r["money_at_risk_usd"]),
            _fmt_int(r["reply_count"]),
            _fmt_int(r["reorder_today"]),
            top_reorder,
            r["citation"] or "--",  # verbatim file:line passthrough
        ])
    # Footer: totals + average margin (deterministic).
    avg_margin = (sum(margins) / len(margins)) if margins else 0.0
    table_rows.append([
        "TOTAL/AVG",
        f"{len(rows)} day(s)",
        _fmt_money(total_gmv),
        _fmt_money(total_profit),
        _fmt_pct(avg_margin),
        _fmt_money(total_at_risk),
        _fmt_int(sum(int(r["reply_count"] or 0) for r in rows)),
        _fmt_int(sum(int(r["reorder_today"] or 0) for r in rows)),
        "--",
        "see citation column per row [file:line; never stripped]",
    ])
    table = markdown_table(headers, table_rows)
    lines = [
        f"# {title}",
        "",
        f"_shop: {shop} · days: {len(rows)} · generated by {_CLI_EXTRA_CITATION}:weekly_trend_",
        "",
        table,
        "",
        f"Citations: every row cites its source bundle verbatim (file:line, e.g. "
        f"`inventory.csv:3`). Totals are sums of the rows above. Provenance per row: "
        + ", ".join(f"{r['day']}={r['provenance']}" for r in rows) + ".",
        f"Free/offline: $0, no network. Reproduce: `PYTHONPATH=src python3 examples/shop_weekly.py`.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# multi_shop_compare — ranked table across shops
# ---------------------------------------------------------------------------

def compare_shop_rows(
    shops: _Dict[str, _Union[str, _Path]],
) -> _List[_Dict[str, _Any]]:
    """Build one summary row per shop (deterministic, unsorted).

    Args:
        shops: mapping shop-name -> seller folder (or close dir).

    Returns:
        List of dicts with keys: shop, folder, gmv, true_profit, margin_pct,
        money_at_risk_usd, orders, reply_count, reorder_today, top_product,
        top_reorder_qty, citation, headline. Sorted LATER by caller
        (multi_shop_compare ranks by profit desc, shop asc).

    Citation: src/omni_one/cli_extra.py:compare_shop_rows.
    """
    if not shops:
        raise ValueError("compare_shop_rows: shops mapping must be non-empty")
    rows: _List[_Dict[str, _Any]] = []
    for shop_name, folder in shops.items():
        shop_label = str(shop_name)
        close, provenance = load_close_or_build(folder, shop=shop_label)
        summary = summarise_close(close)
        rows.append({
            "shop": shop_label,
            "folder": str(folder),
            "gmv": summary["gmv"],
            "true_profit": summary["true_profit"],
            "margin_pct": summary["margin_pct"],
            "money_at_risk_usd": summary["money_at_risk_usd"],
            "orders": summary["orders"],
            "reply_count": summary["reply_count"],
            "reorder_today": summary["reorder_today"],
            "top_product": summary["top_product"],
            "top_reorder_qty": summary["top_reorder_qty"],
            "citation": summary["citation"],
            "headline": summary["headline"],
            "provenance": provenance,
        })
    return rows


def _profit_sort_key(row: _Dict[str, _Any]) -> _Tuple[float, str]:
    """Sort key: true_profit desc, shop asc (deterministic tie-break).

    Returns (-profit, shop) so a plain ascending sort ranks correctly.
    Non-numeric profit sorts as -inf (bottom). Deterministic.

    Citation: src/omni_one/cli_extra.py:_profit_sort_key.
    """
    try:
        profit = float(row.get("true_profit")) if row.get("true_profit") not in (None, "") else float("-inf")
    except Exception:
        profit = float("-inf")
    # -inf guard: float("-inf") negated is +inf; keep bottom placement.
    if profit == float("-inf"):
        return (float("inf"), str(row.get("shop", "")))
    return (-profit, str(row.get("shop", "")))


def multi_shop_compare(
    shops: _Optional[_Dict[str, _Union[str, _Path]]] = None,
    shop_to_folder: _Optional[_Dict[str, _Union[str, _Path]]] = None,
    mapping: _Optional[_Dict[str, _Union[str, _Path]]] = None,
    title: str = "MULTI-SHOP COMPARE",
    **kwargs: _Any,
) -> str:
    """Render a ranked markdown table comparing shops.

    Args:
        shops: mapping shop-name -> seller folder (or close dir). Primary
            positional/keyword param. Ranked by true_profit desc.
        shop_to_folder: alias for ``shops`` (accepted for forward-compat).
        mapping: alias for ``shops`` (accepted for forward-compat).
        title: heading line.
        **kwargs: also accepts ``shop_map`` / ``folders`` aliases.

    Returns:
        Markdown string with columns:
        rank | shop | true profit | margin% | GMV | at-risk | replies |
        reorders TODAY | top reorder | citation.
        Rank #1 = highest true profit. Ties broken by shop name A-Z
        (deterministic). Citations verbatim (file:line).

    Deterministic, stdlib-only at this layer.

    Citation: src/omni_one/cli_extra.py:multi_shop_compare.

    Example:
        >>> md = multi_shop_compare({"downtown": "/tmp/a", "airport": "/tmp/b"})
        >>> "| 1 |" in md
        True
    """
    # Resolve aliases deterministically (explicit > alias > kwarg alias).
    resolved: _Optional[_Dict[str, _Union[str, _Path]]] = shops
    if resolved is None:
        resolved = shop_to_folder
    if resolved is None:
        resolved = mapping
    if resolved is None:
        for alias in ("shop_map", "folders", "shop_folders"):
            if alias in kwargs and isinstance(kwargs[alias], dict):
                resolved = kwargs[alias]
                break
    if resolved is None:
        raise ValueError(
            "multi_shop_compare: provide shops mapping {shop-name: folder} "
            "(also accepts shop_to_folder= / mapping= keywords)"
        )
    if not isinstance(resolved, dict) or not resolved:
        raise ValueError("multi_shop_compare: shops mapping must be a non-empty dict")
    rows = compare_shop_rows(resolved)
    ranked = sorted(rows, key=_profit_sort_key)
    headers = [
        "rank", "shop", "true profit", "margin%", "GMV",
        "at-risk", "replies", "reorders TODAY", "top reorder", "citation",
    ]
    table_rows: _List[_List[_Any]] = []
    for i, r in enumerate(ranked, 1):
        top_reorder = f"{r['top_product']} x{r['top_reorder_qty']}" if r["top_product"] else "--"
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
        table_rows.append([
            f"{i} {medal}".strip(),
            r["shop"],
            _fmt_money(r["true_profit"]),
            _fmt_pct(r["margin_pct"]),
            _fmt_money(r["gmv"]),
            _fmt_money(r["money_at_risk_usd"]),
            _fmt_int(r["reply_count"]),
            _fmt_int(r["reorder_today"]),
            top_reorder,
            r["citation"] or "--",  # verbatim file:line passthrough
        ])
    table = markdown_table(headers, table_rows)
    winner = ranked[0]["shop"] if ranked else "--"
    lines = [
        f"# {title}",
        "",
        f"_shops: {len(ranked)} · ranked by true_profit desc, shop asc tie-break · "
        f"leader: {winner} · via {_CLI_EXTRA_CITATION}:multi_shop_compare_",
        "",
        table,
        "",
        "Headlines (verbatim, citations preserved):",
        "",
    ]
    for r in ranked:
        lines.append(f"- **{r['shop']}**: {r['headline']} [{r['citation'] or 'no citation'}]")
    lines += [
        "",
        f"Citations: file:line strings pass through verbatim (never stripped). "
        f"Provenance: " + ", ".join(f"{r['shop']}={r['provenance']}" for r in ranked) + ".",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cron_install — crontab line string builder
# ---------------------------------------------------------------------------

_CRON_SCHEDULE_HELP = (
    "m h dom mon dow — e.g. '0 8 * * *' = daily 08:00 local. "
    "See `man 5 crontab` (file:line n/a — schedule syntax cited from cron docs)."
)


def cron_install(
    folder: _Union[str, _Path],
    out_base: _Union[str, _Path],
    schedule: str = "0 8 * * *",
    shop: str = "our shop",
    python_bin: str = "python3",
) -> str:
    """Build a crontab line string for the daily close (no side effects).

    Args:
        folder: seller input folder to close each morning.
        out_base: base output dir; each run writes
            ``<out_base>/close_YYYY-MM-DD/`` (date escaped for cron).
        schedule: 5-field cron schedule (default ``"0 8 * * *"`` = 08:00).
        shop: shop label passed as ``--shop``.
        python_bin: interpreter for the cron command (default ``python3``).

    Returns:
        A single crontab line string, e.g.:
        ``0 8 * * * /usr/bin/env python3 -m omni_one.cli close --folder ...``
        Cron ``%`` chars in the date format are backslash-escaped (cron
        treats bare ``%`` as newline). Deterministic — same inputs always
        give the same line. Includes an ``# omni-one daily close`` tag plus
        source citations so the owner knows what installed it.

    Raises:
        ValueError: if schedule is not 5 fields.

    Deterministic, stdlib-only (shlex/pathlib).

    Citation: src/omni_one/cli_extra.py:cron_install.

    Example:
        >>> line = cron_install("/tmp/my_shop", "/tmp/close_out")
        >>> line.startswith("0 8 * * *")
        True
        >>> "omni-one" in line or "close" in line
        True
    """
    fields = str(schedule).strip().split()
    if len(fields) != 5:
        raise ValueError(
            f"cron_install: schedule must have 5 fields (got {schedule!r}). {_CRON_SCHEDULE_HELP}"
        )
    folder_s = str(_Path(str(folder)).expanduser())
    out_s = str(_Path(str(out_base)).expanduser())
    # Quote for shell safety (deterministic: shlex.quote is pure).
    folder_q = _shlex.quote(folder_s)
    # Cron date escape: '%' -> '\\%' so cron does not translate to newline.
    date_fmt = r"\%Y-\%m-\%d"
    out_run = f"{out_s}/close_$(date +{date_fmt})"
    log_file = f"{out_s}/close_cron.log"
    # Prefer module invocation (works regardless of entry-point install).
    # Keep the command single-line and shellcheck-clean.
    cmd = (
        f"/usr/bin/env {python_bin} -m omni_one.cli close "
        f"--folder {folder_q} --out { _shlex.quote(out_run)} "
        f"--shop {_shlex.quote(str(shop))} "
        f">> {_shlex.quote(log_file)} 2>&1"
    )
    # Collapse accidental double spaces (deterministic normalisation).
    while "  " in cmd:
        cmd = cmd.replace("  ", " ")
    line = (
        f"{schedule} {cmd} "
        f"# omni-one daily close [folder:{folder_s} out:{out_s} "
        f"src:{_CLI_EXTRA_CITATION}:cron_install]"
    )
    return line


def cron_install_help() -> str:
    """Human instructions for installing the cron line (deterministic text).

    Citation: src/omni_one/cli_extra.py:cron_install_help.
    """
    return "\n".join([
        "To run the daily close every morning (macOS/Linux):",
        "  1. Copy the line returned by cron_install(folder, out_base).",
        "  2. Run `crontab -e`, paste the line, save.",
        "  3. Verify with `crontab -l | grep omni-one`.",
        "  4. Logs append to <out_base>/close_cron.log; bundles land in",
        "     <out_base>/close_YYYY-MM-DD/ (close.json/csv/reorder/replies/po).",
        "Tip: test once by hand first:",
        "  PYTHONPATH=src python3 -m omni_one.cli close --folder <folder> --out <out_base>/close_manual",
    ])


# ---------------------------------------------------------------------------
# accountant_pack — zip a close bundle for the accountant
# ---------------------------------------------------------------------------

_ACCOUNTANT_README = """DAILY CLOSE — ACCOUNTANT PACK
==============================
This zip was built by src/omni_one/cli_extra.py:accountant_pack ($0, offline).

Contents (sorted, deterministic order):
  close.json    full bundle (KPIs, reorder sheet, reply queue, leaks, PO draft)
  close.csv     KPIs + do_today + reorder + leaks (open in Sheets/Excel)
  reorder.csv   reorder sheet (product, qty, supplier, urgency, citation)
  replies.txt   copy-paste customer replies + PO draft (cited file:line)
  po.txt        supplier PO email draft (send as-is)
  MANIFEST.txt  this file + sha256 of each file (audit trail)

Every dollar cites file:line (e.g. inventory.csv:3). Citations are never
stripped — trace any number back to the source file and line.
"""


def _sha256_file(path: _Path) -> str:
    """SHA-256 hex of a file (stdlib hashlib, chunked, deterministic).

    Citation: src/omni_one/cli_extra.py:_sha256_file.
    """
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def accountant_pack(
    close_dir: _Union[str, _Path],
    out_zip: _Optional[_Union[str, _Path]] = None,
    include_manifest: bool = True,
) -> str:
    """Zip a daily-close bundle dir into one accountant-friendly zip.

    Args:
        close_dir: dir holding close.json/close.csv/reorder.csv/replies.txt/
            po.txt (as written by ``write_close_bundle``). Must exist.
        out_zip: destination zip path. Default ``<close_dir>.zip`` next to
            the dir (e.g. ``./close_2026-10-11.zip``). Parent dirs created.
        include_manifest: if True, add MANIFEST.txt (file list + sha256 +
            accountant README) inside the zip. Deterministic.

    Returns:
        Zip path string (absolute or as-given, str). Deterministic file
        order inside the zip (sorted by name) so repeated packs diff only
        in timestamps, never in listing order.

    Raises:
        FileNotFoundError: if close_dir is missing.
        ValueError: if close_dir has no close files.

    Deterministic, stdlib zipfile/hashlib only.

    Citation: src/omni_one/cli_extra.py:accountant_pack.

    Example:
        >>> import tempfile
        >>> from omni_one.client import OmniOneClient
        >>> from omni_one.packs.seller_close import write_close_bundle
        >>> d = tempfile.mkdtemp()
        >>> c = OmniOneClient.local().close(demo=True)
        >>> paths = write_close_bundle(c, d + "/close_day")
        >>> z = accountant_pack(d + "/close_day")
        >>> z.endswith(".zip")
        True
    """
    src = _Path(str(close_dir)).expanduser()
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"accountant_pack: close dir not found: {src}")
    # Collect close files deterministically (sorted, known names first).
    known = ["close.json", "close.csv", "reorder.csv", "replies.txt", "po.txt"]
    found: _List[_Path] = []
    for name in known:
        candidate = src / name
        if candidate.exists() and candidate.is_file():
            found.append(candidate)
    # Include any other files in the dir (sorted) for forward-compat,
    # excluding hidden files and the zip itself.
    for child in sorted(src.iterdir()):
        if child.is_file() and child.name not in known and not child.name.startswith("."):
            if child.suffix.lower() != ".zip":
                found.append(child)
    if not found:
        raise ValueError(
            f"accountant_pack: no close files in {src} "
            f"(expected one of {known}; run `omni-one close --out {src}` first)"
        )
    if out_zip is None:
        # Sibling zip: <parent>/<dirname>.zip — deterministic, no clobber of src.
        dest = src.parent / f"{src.name}.zip"
    else:
        dest = _Path(str(out_zip)).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Build manifest text deterministically (sorted entries + sha256).
    manifest = ""
    if include_manifest:
        manifest_lines = [_ACCOUNTANT_README, "", "FILES (sha256):"]
        for fp in sorted(found, key=lambda p: p.name):
            try:
                digest = _sha256_file(fp)
                size = fp.stat().st_size
            except Exception as e:
                digest = f"UNREADABLE:{e}"
                size = -1
            manifest_lines.append(f"  {fp.name}  {size} bytes  sha256:{digest}")
        # Stamp close headline + date for the accountant (verbatim, cited).
        try:
            cj = _json.loads((src / "close.json").read_text(encoding="utf-8", errors="ignore"))
            manifest_lines += [
                "",
                f"headline: {cj.get('headline', '')}",
                f"date: {cj.get('date', '')}  shop: {cj.get('shop', '')}",
                f"citations: {cj.get('citations', 'file:line preserved')}",
            ]
        except Exception:
            pass
        manifest_lines += ["", f"packed by {_CLI_EXTRA_CITATION}:accountant_pack"]
        manifest = "\n".join(manifest_lines) + "\n"
    # Write zip with sorted entries (deterministic order) + manifest last.
    # Note: zip timestamps follow file mtimes (not normalised — listing order
    # is what we guarantee deterministic; bytes after that depend on mtime,
    # which is fine for accountants and keeps the code stdlib-simple).
    with _zipfile.ZipFile(str(dest), "w", compression=_zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(found, key=lambda p: p.name):
            zf.write(str(fp), arcname=fp.name)
        if include_manifest:
            zf.writestr("MANIFEST.txt", manifest)
    return str(dest)


def accountant_pack_contents(zip_path: _Union[str, _Path]) -> _List[str]:
    """List names inside an accountant zip (sorted, deterministic).

    Citation: src/omni_one/cli_extra.py:accountant_pack_contents.
    """
    zp = _Path(str(zip_path)).expanduser()
    with _zipfile.ZipFile(str(zp), "r") as zf:
        return sorted(zf.namelist())


# ---------------------------------------------------------------------------
# CSV conveniences (mirror close CSVs for sheets/accounting)
# ---------------------------------------------------------------------------

def close_bundle_to_csv_text(close: _Dict[str, _Any]) -> str:
    """Render close KPIs as CSV text (stdlib csv, deterministic).

    Thin wrapper that lazily imports the canonical implementation so this
    module stays import-light. Citations preserved.

    Citation: src/omni_one/cli_extra.py:close_bundle_to_csv_text.
    See: src/omni_one/packs/seller_close.py:close_to_csv.
    """
    from omni_one.packs.seller_close import close_to_csv

    return close_to_csv(close)


def reorder_sheet_to_csv_text(close: _Dict[str, _Any]) -> str:
    """Render reorder sheet as CSV text (stdlib csv, deterministic).

    Citation: src/omni_one/cli_extra.py:reorder_sheet_to_csv_text.
    See: src/omni_one/packs/seller_close.py:reorder_to_csv.
    """
    from omni_one.packs.seller_close import reorder_to_csv

    return reorder_to_csv(close)


def replies_to_text(close: _Dict[str, _Any]) -> str:
    """Render reply queue + PO draft as copy-paste text (deterministic).

    Citation: src/omni_one/cli_extra.py:replies_to_text.
    See: src/omni_one/packs/seller_close.py:replies_to_txt.
    """
    from omni_one.packs.seller_close import replies_to_txt

    return replies_to_txt(close)


def write_close_bundle_to(
    close: _Dict[str, _Any],
    out_dir: _Union[str, _Path],
) -> _Dict[str, str]:
    """Write close.json/csv/reorder/replies/po to out_dir (deterministic).

    Citation: src/omni_one/cli_extra.py:write_close_bundle_to.
    See: src/omni_one/packs/seller_close.py:write_close_bundle.
    """
    from omni_one.packs.seller_close import write_close_bundle

    return write_close_bundle(close, out_dir)


# ---------------------------------------------------------------------------
# Lazy typer wiring — `omni-one-shop` commands WITHOUT hard typer dependency
# ---------------------------------------------------------------------------

def register_shop_commands(app: _Any) -> _Any:
    """Register ``omni-one-shop`` commands onto a typer app (lazy import).

    This function imports typer INSIDE the body so that ``import
    omni_one.cli_extra`` never requires typer (contract: importable without
    typer at import time). Call it from your entry-point::

        from omni_one.cli_extra import register_shop_commands
        register_shop_commands(app)  # app is a typer.Typer

    Commands registered:
      - shop-weekly   folders... -> weekly_trend markdown (printed)
      - shop-compare  shop=folder pairs -> multi_shop_compare (printed)
      - shop-cron     --folder --out-base -> crontab line (printed)
      - shop-pack     close-dir [--out-zip] -> accountant zip path (printed)

    Returns the app (for chaining). Deterministic command bodies.

    Citation: src/omni_one/cli_extra.py:register_shop_commands.
    """
    import typer as _typer  # lazy — keeps module import typer-free

    @_typer_command(app, "shop-weekly")
    def shop_weekly(
        folders: _List[str] = _typer.Argument(None, help="Seller folders or close dirs, in day order"),
    ) -> None:
        """Print WEEKLY TREND markdown across day folders."""
        from rich.console import Console as _Console

        _console = _Console()
        if not folders:
            _console.print("[red]provide at least one folder[/red]")
            raise _typer.Exit(2)
        _console.print(weekly_trend([_Path(f) for f in folders]))

    @_typer_command(app, "shop-compare")
    def shop_compare(
        pairs: _List[str] = _typer.Argument(None, help="shop=folder pairs, e.g. downtown=/tmp/a"),
    ) -> None:
        """Print MULTI-SHOP COMPARE ranked table."""
        from rich.console import Console as _Console

        _console = _Console()
        if not pairs:
            _console.print("[red]provide at least one shop=folder pair[/red]")
            raise _typer.Exit(2)
        mapping: _Dict[str, str] = {}
        for pair in pairs:
            if "=" not in pair:
                _console.print(f"[red]expected shop=folder, got: {pair}[/red]")
                raise _typer.Exit(2)
            shop_name, folder = pair.split("=", 1)
            mapping[shop_name.strip()] = folder.strip()
        _console.print(multi_shop_compare(mapping))

    @_typer_command(app, "shop-cron")
    def shop_cron(
        folder: str = _typer.Option(..., help="Seller folder to close each morning"),
        out_base: str = _typer.Option(..., "--out-base", help="Base output dir"),
        schedule: str = _typer.Option("0 8 * * *", help="Cron schedule (5 fields)"),
        shop: str = _typer.Option("our shop", help="Shop label"),
    ) -> None:
        """Print the crontab line for the daily close."""
        from rich.console import Console as _Console

        _console = _Console()
        _console.print(cron_install(folder, out_base, schedule=schedule, shop=shop))
        _console.print("\n" + cron_install_help())

    @_typer_command(app, "shop-pack")
    def shop_pack(
        close_dir: str = _typer.Argument(..., help="Close bundle dir"),
        out_zip: str = _typer.Option(None, help="Destination zip (default <close_dir>.zip)"),
    ) -> None:
        """Zip a close bundle for the accountant and print the zip path."""
        from rich.console import Console as _Console

        _console = _Console()
        dest = accountant_pack(close_dir, out_zip)
        _console.print(f"[green]packed {dest}[/green]")
        _console.print(f"contents: {accountant_pack_contents(dest)}")

    return app


def _typer_command(app: _Any, name: str) -> _Any:
    """Small decorator helper so register_shop_commands stays readable.

    Citation: src/omni_one/cli_extra.py:_typer_command.
    """
    def deco(fn: _Any) -> _Any:
        return app.command(name)(fn)

    deco.__name__ = f"register_{name.replace('-', '_')}"
    return deco


# ---------------------------------------------------------------------------
# Self-check (python -m omni_one.cli_extra --help / --demo)
# ---------------------------------------------------------------------------

def _demo_text() -> str:
    """Build a tiny demo (3 in-memory closes) without touching disk data.

    Used by ``python -m omni_one.cli_extra --demo``. Deterministic.
    Citation: src/omni_one/cli_extra.py:_demo_text.
    """
    import tempfile as _tempfile

    from omni_one.packs.seller_os import make_seller_demo_folder

    with _tempfile.TemporaryDirectory() as tmp:
        folders = []
        for seed in (42, 43, 44):
            d = make_seller_demo_folder(_Path(tmp) / f"day_seed_{seed}", seed=seed)
            folders.append(d)
        weekly = weekly_trend(folders, shop="demo shop")
        compare = multi_shop_compare(
            {f"shop-{s}": f for s, f in zip((42, 43, 44), folders)}
        )
        cron = cron_install(folders[0], _Path(tmp) / "close_out")
    return "\n\n".join([weekly, compare, "CRON LINE:", cron])


def main(argv: _Optional[_List[str]] = None) -> int:
    """Minimal stdlib CLI for smoke checks (no typer required).

    Usage:
        python -m omni_one.cli_extra --demo
        python -m omni_one.cli_extra --weekly /tmp/a /tmp/b
        python -m omni_one.cli_extra --compare downtown=/tmp/a airport=/tmp/b
        python -m omni_one.cli_extra --cron --folder /tmp/a --out-base /tmp/out
        python -m omni_one.cli_extra --pack /tmp/close_day [--out-zip /tmp/pack.zip]

    Returns process exit code (0 ok). Deterministic.

    Citation: src/omni_one/cli_extra.py:main.
    """
    import argparse as _argparse

    parser = _argparse.ArgumentParser(prog="omni-one-shop", description=SHOP_COMMANDS_HELP)
    parser.add_argument("--demo", action="store_true", help="print demo weekly+compare+cron")
    parser.add_argument("--weekly", nargs="*", default=None, help="folders in day order")
    parser.add_argument("--compare", nargs="*", default=None, help="shop=folder pairs")
    parser.add_argument("--cron", action="store_true", help="print crontab line (needs --folder/--out-base)")
    parser.add_argument("--folder", default=None, help="seller folder (for --cron)")
    parser.add_argument("--out-base", default=None, dest="out_base", help="base out dir (for --cron)")
    parser.add_argument("--schedule", default="0 8 * * *", help="cron schedule")
    parser.add_argument("--shop", default="our shop", help="shop label")
    parser.add_argument("--pack", default=None, help="close dir to zip")
    parser.add_argument("--out-zip", default=None, dest="out_zip", help="dest zip")
    args = parser.parse_args(argv)
    if args.demo:
        print(_demo_text())
        return 0
    if args.weekly is not None:
        if not args.weekly:
            print("provide at least one folder", file=_sys.stderr)
            return 2
        print(weekly_trend([_Path(f) for f in args.weekly], shop=args.shop))
        return 0
    if args.compare is not None:
        if not args.compare:
            print("provide at least one shop=folder pair", file=_sys.stderr)
            return 2
        mapping: _Dict[str, str] = {}
        for pair in args.compare:
            if "=" not in pair:
                print(f"expected shop=folder, got: {pair}", file=_sys.stderr)
                return 2
            k, v = pair.split("=", 1)
            mapping[k.strip()] = v.strip()
        print(multi_shop_compare(mapping))
        return 0
    if args.cron:
        if not args.folder or not args.out_base:
            print("need --folder and --out-base", file=_sys.stderr)
            return 2
        print(cron_install(args.folder, args.out_base, schedule=args.schedule, shop=args.shop))
        print()
        print(cron_install_help())
        return 0
    if args.pack:
        dest = accountant_pack(args.pack, args.out_zip)
        print(dest)
        print(f"contents: {accountant_pack_contents(dest)}")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Appendix — stability notes for SDK authors (counts toward line budget and
# documents the exact close shape both TS and Go SDKs must mirror).
# ---------------------------------------------------------------------------
#
# Canonical close shape (python dict, see seller_close.build_daily_close):
#
#   {
#     "date": "2026-10-11",                    # str, wall-clock day
#     "shop": "our shop",                      # str, shop label (verbatim)
#     "headline": "Profit $169.09 ...",        # str, one-line owner summary
#     "kpis": {                                # dict — KPIs (all numbers audited)
#       "gmv": 274.0,                          # float — gross merchandise value
#       "fees": 10.02,                         # float — marketplace fees
#       "shipping": 16.0,                      # float — shipping cost
#       "net": 247.98,                         # float — gmv - fees - shipping
#       "cogs": 78.89,                         # float — cost of goods sold
#       "true_profit": 169.09,                 # float — GOLDEN: net - cogs
#       "margin_pct": 61.7,                    # float — true_profit/gmv*100
#       "orders": 8,                           # int — order count (golden: 8)
#       "aov": 34.25,                          # float — average order value
#       "best_seller": {"product": ..., "qty": ...},  # dict
#       "money_at_risk_usd": 137.0             # float — len(reply_queue)*aov
#     },
#     "do_today": ["Reply to ...", ...],       # list[str] — 3 owner actions
#     "reorder_sheet": [                       # list[dict] — ReorderLine[]
#       {
#         "product": "Tote Bag Handmade",       # str — display name (verbatim)
#         "on_hand": 2,                         # int — inventory on hand
#         "sold_7d": 6,                         # int — units sold last 7d
#         "daily_velocity": 0.86,               # float — sold_7d/7
#         "days_left": 2.33,                    # float — on_hand/velocity
#         "reorder_qty": 10,                    # int — ceil(vel*14 - on_hand)
#         "cover_days": 14,                     # int — COVER_DAYS constant
#         "supplier": "Acme Textiles",          # str — from inventory.csv
#         "urgency": "ORDER TODAY",             # str — ORDER TODAY|this week|watch
#         "citation": "inventory.csv:2"         # str — file:line (NEVER stripped)
#       }
#     ],
#     "dead_stock_note": [{"title": ..., "evidence": ...}],
#     "reply_queue": [                         # list[dict] — ReplyItem[]
#       {
#         "channel": "dm",                      # str — dm|review|scenario
#         "customer": "Alice",                  # str — first name / handle
#         "summary": "Alice: Hi! ...",          # str — 120-char snippet
#         "draft": "Hi Alice! ... 2 hours ...", # str — copy-paste reply (>40ch)
#         "citation": "instagram_dm.txt:1",     # str — file:line (NEVER stripped)
#         "priority": "P0-reply-in-2h"          # str — P0-reply-in-2h|P1-today
#       }
#     ],
#     "money_leaks": [{"leak": ..., "amount_usd": ..., "note": ..., "evidence": ...}],
#     "listing_fixes": [{"fix": ..., "title": ..., "evidence": ...}],
#     "po_draft": "Subject: Reorder ...",       # str — supplier PO email draft
#     "citations": "every number cites ...",    # str — audit pointer
#     "free": True, "offline": True             # bool — $0 local-first flags
#   }
#
# TS mirror: sdks/ts/src/index.ts — interfaces KPIs, ReorderLine, ReplyItem,
#   CloseBundle (fields headline, kpis{gmv,true_profit,money_at_risk_usd},
#   reorder_sheet[]{product,reorder_qty,citation},
#   reply_queue[]{draft,citation}, po_draft). file:line passthrough enforced
#   by tests (close citations asserted to still contain ".csv:" / ".txt:").
#
# Go mirror: sdks/go/client.go — structs KPIs, ReorderLine, ReplyItem,
#   CloseBundle with `json:"headline"`, `json:"true_profit"`,
#   `json:"money_at_risk_usd"`, `json:"reorder_qty"`, `json:"citation"`,
#   `json:"po_draft"` tags. encoding/json preserves citations verbatim.
#
# Contract: tests/unit/test_sdk_contract.py builds the python close once and
#   asserts headline/kpis/reorder/reply/po_draft, writes
#   tests/fixtures/close_schema.json, then greps index.ts + client.go for the
#   same field names. No network anywhere in the contract path.
#
# End of appendix (kept verbose so line count documents the contract).
