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
    "pipeline_closes_total": 0,
    "vision_closes_total": 0,
    "micro_closes_total": 0,
    "revops_closes_total": 0,
    "ops_closes_total": 0,
    "returns_closes_total": 0,
    "cashflow_closes_total": 0,
    "reputation_closes_total": 0,
    "forecast_closes_total": 0,
    "rollup_closes_total": 0,
    "auto_runs_total": 0,
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
                "closes": ["seller", "pipeline", "vision", "micro", "revenue", "ops",
                           "returns", "cashflow", "reputation", "forecast", "rollup", "auto"],
                "mcp": {"server": "src/omni_one/mcp_server.py", "tools": 17}, "free": True}

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

    @app.post("/api/v1/pipeline/close", tags=["Ops"], summary="PIPELINE CLOSE: evidence + cost + verdict ($0)")
    async def pipeline_close(payload: dict) -> dict:
        from ..packs.pipeline_close import DEMO_RECORDS, build_pipeline_close
        c = build_pipeline_close(DEMO_RECORDS(int(payload.get("seed", 42))))
        bump("pipeline_closes_total")
        return c

    @app.post("/api/v1/vision/close", tags=["Vision"], summary="VISION CLOSE: photo -> OCR + COGS + evidence ($0)")
    async def vision_close(payload: dict) -> dict:
        """Demo bundle (no upload). For uploads use POST /api/v1/vision/analyze."""
        from ..packs.vision_close import make_demo_image, build_vision_close
        c = build_vision_close(make_demo_image("receipt"), filename="demo_receipt.png")
        bump("vision_closes_total")
        return c

    @app.post("/api/v1/micro/close", tags=["Verticals"], summary="MICRO CLOSE: taco-shop ritual ($0)")
    async def micro_close(payload: dict) -> dict:
        import tempfile
        from pathlib import Path as _P
        from ..packs._labs.micro_biz import make_demo_folder, ingest_folder, build_briefing
        from ..packs.micro_close import build_micro_close
        seed = int(payload.get("seed", 42))
        with tempfile.TemporaryDirectory() as tmp:
            d = make_demo_folder(_P(tmp) / "m", seed=seed)
            events, _ = ingest_folder(d)
            c = build_micro_close(events, build_briefing(events),
                                  shop=str(payload.get("shop", "Maya's Tacos")),
                                  locale=str(payload.get("locale", "en")))
            bump("micro_closes_total")
            return c

    @app.post("/api/v1/revenue/close", tags=["Verticals"], summary="REVOPS CLOSE: pipeline review ($0)")
    async def revenue_close(payload: dict) -> dict:
        from ..packs.revops_close import build_revops_close
        c = build_revops_close(None, n=int(payload.get("n", 20)), seed=int(payload.get("seed", 42)))
        bump("revops_closes_total")
        return c

    @app.post("/api/v1/ops/close", tags=["Ops"], summary="OPS CLOSE: methodology loop bundle ($0)")
    async def ops_close(payload: dict) -> dict:
        import tempfile
        from pathlib import Path as _P
        from ..packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
        from ..packs.seller_scenarios import run_all_scenarios
        from ..packs.ops_close import build_ops_close
        seed = int(payload.get("seed", 42))
        with tempfile.TemporaryDirectory() as tmp:
            d = make_seller_demo_folder(_P(tmp) / "d", seed=seed)
            events, _ = ingest_seller_folder(d)
            c = build_ops_close(events, build_seller_briefing(events), run_all_scenarios(events),
                                namespace=str(payload.get("namespace", "ops-daily")))
            bump("ops_closes_total")
            return c

    @app.post("/api/v1/returns/close", tags=["Verticals"], summary="RETURNS CLOSE: refund leaks + restock ($0)")
    async def returns_close(payload: dict) -> dict:
        from ..packs.returns_close import DEMO_RETURNS, build_returns_close
        c = build_returns_close(DEMO_RETURNS(int(payload.get("seed", 42))))
        bump("returns_closes_total")
        return c

    @app.post("/api/v1/cashflow/close", tags=["Verticals"], summary="CASHFLOW CLOSE: payouts + runway ($0)")
    async def cashflow_close(payload: dict) -> dict:
        from ..packs.cashflow_close import build_cashflow_close
        c = build_cashflow_close(None, None, seed=int(payload.get("seed", 42)))
        bump("cashflow_closes_total")
        return c

    @app.post("/api/v1/reputation/close", tags=["Verticals"], summary="REPUTATION CLOSE: reply queue ($0)")
    async def reputation_close(payload: dict) -> dict:
        from ..packs.reputation_close import DEMO_REVIEWS, build_reputation_close
        c = build_reputation_close(DEMO_REVIEWS(int(payload.get("seed", 42))),
                                   seed=int(payload.get("seed", 42)),
                                   shop=str(payload.get("shop", "our shop")))
        bump("reputation_closes_total")
        return c

    @app.post("/api/v1/forecast/close", tags=["Verticals"], summary="FORECAST CLOSE: stockouts + PO ($0)")
    async def forecast_close(payload: dict) -> dict:
        from ..packs.forecast_close import DEMO_SKUS, build_forecast_close
        c = build_forecast_close(DEMO_SKUS(int(payload.get("seed", 42))), seed=int(payload.get("seed", 42)))
        bump("forecast_closes_total")
        return c

    @app.post("/api/v1/rollup/close", tags=["Verticals"], summary="ROLLUP CLOSE: portfolio ranking ($0)")
    async def rollup_close(payload: dict) -> dict:
        from ..packs.rollup_close import DEMO_SHOPS, build_rollup_close
        c = build_rollup_close(DEMO_SHOPS(int(payload.get("seed", 42))), seed=int(payload.get("seed", 42)))
        bump("rollup_closes_total")
        return c

    @app.post("/api/v1/auto/close", tags=["Ops"], summary="AUTO: sniff folder -> run the right closes ($0)")
    async def auto_close(payload: dict) -> dict:
        import tempfile as _t
        from ..packs.auto_close import run_auto
        folder = payload.get("folder")
        s = run_auto(folder, out=_t.mkdtemp(prefix="omni-auto-"),
                     seed=int(payload.get("seed", 42)),
                     shop=str(payload.get("shop", "our shop")),
                     deep=bool(payload.get("deep", False)))
        bump("auto_runs_total")
        return s
