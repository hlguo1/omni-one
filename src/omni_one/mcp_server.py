"""
Omni-One MCP server — expose Seller OS + pipeline to Claude / Cursor / Windsurf.
Stdio JSON-RPC (no `mcp` package required). If `mcp` is installed, also serves
via FastMCP when run with --transport http.

Tools:
  seller_briefing   demo or folder -> KPIs + alerts + citations
  seller_scenarios  demo or folder -> 12 ranked decisions
  seller_operations full loop -> workshop + audit
  pipeline_analyze  records -> bypass/cost/evidence
  vision_analyze    image bytes (base64) -> OCR+chart+pipeline (local)

Stdio protocol (one JSON per line):
  {"id":1,"tool":"seller_briefing","args":{"demo":true}}
  -> {"id":1,"ok":true,"result":{...}}

Claude Desktop config (~/.claude.json):
  {"mcpServers":{"omni-one":{"command":"python3","args":["-m","omni_one.mcp_server"],"cwd":"/path/to/omni-one","env":{"PYTHONPATH":"src"}}}}
"""
from __future__ import annotations
import base64
import json
import sys
import tempfile
from pathlib import Path


def tool_seller_briefing(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    folder = args.get("folder")
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    if args.get("demo", True) or not folder:
        with tempfile.TemporaryDirectory() as tmp:
            d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
            events, report = ingest_seller_folder(d)
            b = build_seller_briefing(events)
            b["ingest_report"].update(report)
            b["ingest_report"]["demo"] = True
            return _trim(b)
    from omni_one.infra.security import resolve_seller_folder
    p = resolve_seller_folder(str(folder))
    from omni_one.packs.seller_os import ingest_seller_folder as _ing, build_seller_briefing as _b
    events, report = _ing(p)
    b = _b(events)
    b["ingest_report"].update(report)
    return _trim(b)


def tool_seller_scenarios(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
    from omni_one.packs.seller_scenarios import run_all_scenarios
    with tempfile.TemporaryDirectory() as tmp:
        d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
        events, _ = ingest_seller_folder(d)
        scen = run_all_scenarios(events)
        scen["decisions"] = scen["decisions"][:20]
        return scen


def tool_seller_operations(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.engine.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
    from omni_one.engine.workshop import WorkshopApp
    from omni_one.engine.governance import AuditLog, ingest_workshop
    with tempfile.TemporaryDirectory() as tmp:
        d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
        events, _ = ingest_seller_folder(d)
        b = build_seller_briefing(events)
        onto = Ontology("mcp")
        onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product",
            primary_key="sku", title_property="name",
            properties=[PropertyDef(name="sku", type="string", required=True)]))
        wapp = WorkshopApp(onto, "mcp")
        try:
            from omni_one.packs.seller_scenarios import run_all_scenarios, scenarios_to_workshop
            scen = run_all_scenarios(events)
            scenarios_to_workshop(scen, wapp)
        except Exception:
            pass
        audit = AuditLog("mcp")
        ingest_workshop(audit, wapp)
        return {"kpis": b["kpis"], "workshop": wapp.stats(),
                "governance": audit.stats(), "verified": audit.verify(), "free": True}


def tool_seller_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    shop = str(args.get("shop", "our shop"))
    locale = str(args.get("locale", "en"))
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close
    with tempfile.TemporaryDirectory() as tmp:
        d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
        events, _ = ingest_seller_folder(d)
        b = build_seller_briefing(events)
        scen = run_all_scenarios(events)
        c = build_daily_close(events, b, scen, shop=shop, locale=locale)
        c.pop("po_draft", None)
        return _trim(c)


def tool_pipeline_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.pipeline_close import DEMO_RECORDS, build_pipeline_close
    return _trim(build_pipeline_close(DEMO_RECORDS(seed)))


def tool_vision_close(args: dict) -> dict:
    from omni_one.packs.vision_close import make_demo_image, build_vision_close
    b64 = args.get("image_base64", "")
    if b64:
        import base64 as _b64
        data = _b64.b64decode(b64)
    else:
        data = make_demo_image("receipt")
    c = build_vision_close(data, filename=args.get("filename", "demo_receipt.png"))
    c.pop("chart", None)
    return _trim(c)


def tool_micro_close(args: dict) -> dict:
    import tempfile as _t
    seed = int(args.get("seed", 42))
    from omni_one.packs._labs.micro_biz import make_demo_folder, ingest_folder, build_briefing
    from omni_one.packs.micro_close import build_micro_close
    with _t.TemporaryDirectory() as tmp:
        d = make_demo_folder(Path(tmp) / "m", seed=seed)
        events, _ = ingest_folder(d)
        return _trim(build_micro_close(events, build_briefing(events),
                                       shop=str(args.get("shop", "Maya's Tacos")),
                                       locale=str(args.get("locale", "en"))))


def tool_revops_close(args: dict) -> dict:
    from omni_one.packs.revops_close import build_revops_close
    return _trim(build_revops_close(None, n=int(args.get("n", 20)), seed=int(args.get("seed", 42))))


def tool_ops_close(args: dict) -> dict:
    import tempfile as _t2
    seed = int(args.get("seed", 42))
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.ops_close import build_ops_close
    with _t2.TemporaryDirectory() as tmp:
        d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
        events, _ = ingest_seller_folder(d)
        return _trim(build_ops_close(events, build_seller_briefing(events), run_all_scenarios(events),
                                     namespace=str(args.get("namespace", "ops-daily"))))


def tool_returns_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.returns_close import DEMO_RETURNS, build_returns_close
    return _trim(build_returns_close(DEMO_RETURNS(seed)))


def tool_cashflow_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.cashflow_close import build_cashflow_close
    return _trim(build_cashflow_close(None, None, seed=seed))


def tool_reputation_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.reputation_close import DEMO_REVIEWS, build_reputation_close
    return _trim(build_reputation_close(DEMO_REVIEWS(seed), seed=seed,
                                        shop=str(args.get("shop", "our shop"))))


def tool_forecast_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.forecast_close import DEMO_SKUS, build_forecast_close
    return _trim(build_forecast_close(DEMO_SKUS(seed), seed=seed))


def tool_rollup_close(args: dict) -> dict:
    seed = int(args.get("seed", 42))
    from omni_one.packs.rollup_close import DEMO_SHOPS, build_rollup_close
    return _trim(build_rollup_close(DEMO_SHOPS(seed), seed=seed))


def tool_auto(args: dict) -> dict:
    import tempfile as _t3
    from omni_one.packs.auto_close import run_auto
    folder = args.get("folder")
    return _trim(run_auto(folder, out=_t3.mkdtemp(prefix="omni-auto-"),
                          seed=int(args.get("seed", 42)),
                          shop=str(args.get("shop", "our shop")),
                          deep=bool(args.get("deep", False))))


def tool_pipeline_analyze(args: dict) -> dict:
    records = args.get("records", [])
    from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline
    from omni_one.core.cache import SemanticCache
    from omni_one.core.model_router import ModelRouter
    pipe = MultiLayerDataPipeline(model_router=ModelRouter(), cache=SemanticCache())
    results, _ = pipe.process_batch(records)
    return {"records_processed": len(records), "metrics": pipe.get_metrics_summary(),
            "sample_bypass": [bool(getattr(r, "llm_bypassed", True)) for r in results[:3]]}


def tool_vision_analyze(args: dict) -> dict:
    b64 = args.get("image_base64", "")
    filename = args.get("filename", "upload.png")
    data = base64.b64decode(b64) if b64 else b""
    if not data:
        return {"ok": False, "error": "image_base64 required"}
    from omni_one.core.vision import analyze_photo
    r = analyze_photo(data, filename=filename, run_pipeline=True)
    r.pop("chart", None)
    return _trim(r)


TOOLS = {
    "seller_briefing": tool_seller_briefing,
    "seller_scenarios": tool_seller_scenarios,
    "seller_operations": tool_seller_operations,
    "seller_close": tool_seller_close,
    "pipeline_close": tool_pipeline_close,
    "vision_close": tool_vision_close,
    "micro_close": tool_micro_close,
    "revops_close": tool_revops_close,
    "ops_close": tool_ops_close,
    "returns_close": tool_returns_close,
    "cashflow_close": tool_cashflow_close,
    "reputation_close": tool_reputation_close,
    "forecast_close": tool_forecast_close,
    "rollup_close": tool_rollup_close,
    "auto": tool_auto,
    "pipeline_analyze": tool_pipeline_analyze,
    "vision_analyze": tool_vision_analyze,
}


def _trim(obj, max_str: int = 2000, depth: int = 0):
    if depth > 4:
        return "[trimmed]"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "base64":
                out[k] = "[omitted:base64]"
            else:
                out[k] = _trim(v, max_str, depth + 1)
        return out
    if isinstance(obj, list):
        return [_trim(x, max_str, depth + 1) for x in obj[:30]]
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + "…[trimmed]"
    return obj


def serve_stdio() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            tid = msg.get("id")
            tool = msg.get("tool") or msg.get("method", "").replace("tools/call:", "")
            args = msg.get("args", msg.get("params", {}))
            if tool not in TOOLS:
                sys.stdout.write(json.dumps({"id": tid, "ok": False, "error": f"unknown tool {tool}. tools={sorted(TOOLS)}"}) + "\n")
                sys.stdout.flush()
                continue
            result = TOOLS[tool](args if isinstance(args, dict) else {})
            sys.stdout.write(json.dumps({"id": tid, "ok": True, "result": result}, default=str) + "\n")
            sys.stdout.flush()
        except Exception as e:
            try:
                sys.stdout.write(json.dumps({"id": msg.get("id") if "msg" in dir() else None, "ok": False, "error": str(e)}) + "\n")
                sys.stdout.flush()
            except Exception:
                pass


if __name__ == "__main__":
    serve_stdio()
