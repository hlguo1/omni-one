"""
Ops endpoints — Prometheus metrics + CSV export. $0, no extra deps.
Counters are in-process (reset on restart); Prometheus scrapes /metrics.
"""
from __future__ import annotations
from collections import Counter

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, Response

COUNTERS: Counter = Counter({
    "briefings_total": 0,
    "scenarios_runs_total": 0,
    "operations_total": 0,
    "vision_total": 0,
    "analyzes_total": 0,
    "closes_total": 0,
})


def bump(key: str, n: int = 1) -> None:
    try:
        COUNTERS[key] += n
    except Exception:
        pass


def prometheus_text() -> str:
    lines = ["# HELP omni_one_requests Total Omni-One ops requests", "# TYPE omni_one_requests counter"]
    for k, v in COUNTERS.items():
        lines.append(f'omni_one_requests{{op="{k}"}} {int(v)}')
    # pipeline health hint (cheap, cached 60s would be better; keep simple + guarded)
    lines.append("# HELP omni_one_up 1 if process alive")
    lines.append("# TYPE omni_one_up gauge")
    lines.append("omni_one_up 1")
    return "\n".join(lines) + "\n"


def setup_ops_routes(app: FastAPI) -> None:
    @app.get("/metrics", tags=["Ops"], response_class=PlainTextResponse, summary="Prometheus metrics ($0)")
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(prometheus_text(), media_type="text/plain; version=0.0.4")

    @app.get("/api/v1/seller/export.csv", tags=["Seller OS"], summary="Briefing KPIs + actions as CSV")
    async def seller_export_csv(demo: bool = True, seed: int = 42):
        import tempfile
        from pathlib import Path
        from ..packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
        from ..packs.seller_export import briefing_to_csv
        with tempfile.TemporaryDirectory() as tmp:
            d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
            events, _ = ingest_seller_folder(d)
            b = build_seller_briefing(events)
            bump("briefings_total")
            csv_text = briefing_to_csv(b)
        return Response(content=csv_text, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=briefing.csv"})

    @app.get("/api/v1/openapi-tags", tags=["Ops"], summary="Tag catalog for integrators")
    async def tags() -> dict:
        return {"tags": ["Health", "AI", "Data", "Analytics", "Seller OS", "Vision", "Verticals", "Admin", "Ops"],
                "mcp": {"server": "src/omni_one/mcp_server.py", "tools": 6}, "free": True}

    @app.post("/api/v1/seller/close", tags=["Seller OS"], summary="DAILY CLOSE: profit + reorder/PO + reply drafts + leaks ($0)")
    async def seller_close(payload: dict) -> dict:
        """5-min morning ritual. demo=true or folder=path. Returns close bundle (JSON)."""
        import tempfile
        from pathlib import Path as _P
        folder = payload.get("folder")
        use_demo = payload.get("demo", False) or not folder
        seed = int(payload.get("seed", 42))
        shop = str(payload.get("shop", "our shop"))
        locale = str(payload.get("locale", "en"))
        from ..packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
        from ..packs.seller_scenarios import run_all_scenarios
        from ..packs.seller_close import build_daily_close
        if use_demo:
            with tempfile.TemporaryDirectory() as tmp:
                d = make_seller_demo_folder(_P(tmp) / "d", seed=seed)
                events, report = ingest_seller_folder(d)
                b = build_seller_briefing(events)
                scen = run_all_scenarios(events)
                c = build_daily_close(events, b, scen, shop=shop, locale=locale)
                c["ingest_report"] = report
                bump("closes_total")
                return c
        try:
            from ..infra.security import resolve_seller_folder as _resolve
        except ImportError:
            from omni_one.infra.security import resolve_seller_folder as _resolve  # type: ignore
        try:
            p = _resolve(str(folder))
        except ValueError as e:
            from fastapi import HTTPException as _H
            raise _H(status_code=400, detail=str(e))
        from ..packs.seller_os import ingest_seller_folder as _ing, build_seller_briefing as _bb
        events, report = _ing(p)
        b = _bb(events)
        scen = run_all_scenarios(events)
        c = build_daily_close(events, b, scen, shop=shop, locale=locale)
        c["ingest_report"] = report
        bump("closes_total")
        return c

    @app.get("/api/v1/seller/close.csv", tags=["Seller OS"], summary="DAILY CLOSE as CSV (accountant-ready)")
    async def seller_close_csv(demo: bool = True, seed: int = 42, shop: str = "our shop", locale: str = "en"):
        import tempfile
        from pathlib import Path as _P
        from fastapi.responses import Response as _R
        from ..packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
        from ..packs.seller_scenarios import run_all_scenarios
        from ..packs.seller_close import build_daily_close, close_to_csv
        with tempfile.TemporaryDirectory() as tmp:
            d = make_seller_demo_folder(_P(tmp) / "d", seed=seed)
            events, _ = ingest_seller_folder(d)
            b = build_seller_briefing(events)
            scen = run_all_scenarios(events)
            c = build_daily_close(events, b, scen, shop=shop, locale=locale)
            bump("closes_total")
            return _R(content=close_to_csv(c), media_type="text/csv",
                      headers={"Content-Disposition": "attachment; filename=close.csv"})
