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
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
    from omni_one.palantir_free.workshop import WorkshopApp
    from omni_one.palantir_free.governance import AuditLog, ingest_workshop
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
