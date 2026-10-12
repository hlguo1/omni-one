"""
omni-one CLI — local-first, $0.
  omni-one doctor                  environment + deps check
  omni-one demo                    Seller OS demo briefing (golden KPIs)
  omni-one briefing --demo         same, --folder /path --json out.json
  omni-one scenarios --demo        run 12 scenarios -> Workshop queue
  omni-one operations --demo       full loop: briefing+ontology+workshop+AIP+audit
  omni-one export --demo           briefing -> CSV KPIs + actions
  omni-one serve                   run API on :5003
  omni-one eval                    500-record eval harness
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False, help="Omni-One — deterministic-first local intelligence ($0).")
console = Console()


def _seller_mods():
    from omni_one.packs.seller_os import (
        ingest_seller_folder, build_seller_briefing, make_seller_demo_folder,
    )
    return ingest_seller_folder, build_seller_briefing, make_seller_demo_folder


def _resolve_folder(folder: str | None, demo: bool, seed: int) -> Path:
    from pathlib import Path as _P
    ingest, _, make_demo = _seller_mods()
    if demo or not folder:
        tmp = _P(tempfile.mkdtemp(prefix="omni-seller-"))
        return make_demo(tmp / "seller_demo", seed=seed)
    p = _P(folder).expanduser()
    if not p.exists():
        console.print(f"[red]folder not found: {p}[/red]")
        raise typer.Exit(2)
    try:
        from omni_one.infra.security import resolve_seller_folder as _resolve
        return _resolve(str(p))
    except Exception:
        return p


@app.command()
def doctor():
    """Check python, deps, OCR, folders."""
    import shutil
    console.print("[bold]omni-one doctor[/bold] ($0 local-first)")
    rows = [
        ("python", sys.version.split()[0]),
        ("tesseract", shutil.which("tesseract") or "MISSING (brew install tesseract / apt-get install tesseract-ocr)"),
        ("DUCKDB_PATH", __import__("os").getenv("DUCKDB_PATH", "./data/omni.duckdb")),
        ("AUDIT_PATH", __import__("os").getenv("AUDIT_PATH", "./data/audit.jsonl")),
    ]
    for mod in ["fastapi", "pandas", "duckdb", "PIL", "matplotlib", "sklearn"]:
        try:
            __import__(mod if mod != "PIL" else "PIL.Image")
            rows.append((f"dep:{mod}", "ok"))
        except Exception as e:
            rows.append((f"dep:{mod}", f"MISSING: {e}"))
    t = Table("check", "status")
    for k, v in rows:
        t.add_row(k, str(v)[:90])
    console.print(t)
    # quick pipeline smoke
    try:
        from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline
        from omni_one.core.cache import SemanticCache
        from omni_one.core.model_router import ModelRouter
        pipe = MultiLayerDataPipeline(model_router=ModelRouter(), cache=SemanticCache())
        res, _ = pipe.process_batch([{"timestamp": "2024-01-01", "source": "doctor", "entity_id": "d1", "value": "hello", "metadata": {}}])
        console.print(f"[green]pipeline smoke OK: {len(res)} record(s), bypass={res[0].llm_bypassed}[/green]")
    except Exception as e:
        console.print(f"[yellow]pipeline smoke skipped: {e}[/yellow]")


@app.command()
def demo(seed: int = 42):
    """Run Seller OS demo (golden KPIs) and print briefing."""
    briefing(folder=None, demo=True, seed=seed, json_out=None)


@app.command()
def briefing(folder: str | None = typer.Option(None), demo: bool = typer.Option(False),
             seed: int = 42, json_out: str | None = typer.Option(None, "--json")):
    """Build Seller briefing: true profit, stockout, alerts, draft."""
    ingest, build, _ = _seller_mods()
    p = _resolve_folder(folder, demo, seed)
    events, report = ingest(p)
    b = build(events)
    k = b["kpis"]
    console.print(f"[bold]SELLER BRIEFING[/bold] {report}")
    console.print(f"GMV ${k['gmv']:.2f}  Fees ${k['fees']:.2f}  Net ${k['net']:.2f}  True Profit ${k['true_profit']:.2f}  Margin {k['margin_pct']:.1f}%")
    console.print(f"Orders {k['orders']}  Best {k['best_seller']['product']} ({k['best_seller']['qty']})  At-risk {k['at_risk']}  Stockout {k['stockout_risk']}")
    for a in b["alerts"]:
        console.print(f"  [{a['severity']}] {a['message']}")
    for i, act in enumerate(b["actions"], 1):
        console.print(f"  {i}. {act}")
    if json_out:
        Path(json_out).write_text(json.dumps(b, indent=2, default=str))
        console.print(f"[green]wrote {json_out}[/green]")


@app.command()
def scenarios(folder: str | None = typer.Option(None), demo: bool = typer.Option(False), seed: int = 42):
    """Run 12 Seller scenarios -> ranked Workshop decisions."""
    ingest, _, _ = _seller_mods()
    p = _resolve_folder(folder, demo, seed)
    events, _ = ingest(p)
    from omni_one.packs.seller_scenarios import run_all_scenarios
    scen = run_all_scenarios(events)
    console.print(f"[bold]SCENARIOS[/bold] total={scen['total']} by={scen['by_scenario']}")
    for d in scen["decisions"][:15]:
        console.print(f"  [{d.get('severity','?')}] {d.get('scenario_id')}: {d.get('title','')[:100]}")
        if d.get("evidence"):
            console.print(f"    ↳ {str(d['evidence'][0])[:100]}")


@app.command()
def operations(demo: bool = typer.Option(True), seed: int = 42):
    """Full methodology loop: briefing -> ontology -> workshop -> AIP -> audit."""
    import tempfile as _t
    from pathlib import Path as _P
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ActionDef, ObjectInstance
    from omni_one.palantir_free.workshop import WorkshopApp
    from omni_one.palantir_free.governance import AuditLog, ingest_workshop, ingest_ontology_edits
    from omni_one.palantir_free.aip import AIPLogic
    with _t.TemporaryDirectory() as tmp:
        demo_folder = make_seller_demo_folder(_P(tmp) / "seller_demo", seed=seed)
        events, _ = ingest_seller_folder(demo_folder)
        b = build_seller_briefing(events)
        onto = Ontology("seller-ops")
        onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product", primary_key="sku",
            title_property="name", properties=[PropertyDef(name="sku", type="string", required=True),
            PropertyDef(name="name", type="string", required=True)]))
        seen = set()
        for prod in (b.get("chart", {}) or {}).get("data", {}).get("labels", [])[:6]:
            if prod in seen:
                continue
            seen.add(prod)
            sku = "".join(c for c in prod if c.isalnum())[:8] or f"P{len(seen)}"
            try:
                onto.create_object(ObjectInstance(object_type="Product", primary_key=sku,
                    properties={"sku": sku, "name": prod}))
            except Exception:
                pass
        wapp = WorkshopApp(onto, "seller-daily")
        try:
            from omni_one.packs.seller_scenarios import run_all_scenarios, scenarios_to_workshop
            scen = run_all_scenarios(events)
            made = scenarios_to_workshop(scen, wapp)
        except Exception:
            made = wapp.build_seller_queue(b)
        logic = AIPLogic(onto, "seller-ops")
        audit = AuditLog("seller-ops")
        ingest_workshop(audit, wapp)
        ingest_ontology_edits(audit, onto)
        console.print(f"KPIs={b['kpis']} workshop={wapp.stats()} audit={audit.stats()} verified={audit.verify()}")


@app.command()
def export(folder: str | None = typer.Option(None), demo: bool = typer.Option(False),
           seed: int = 42, out: str = "briefing.csv"):
    """Export briefing KPIs + actions to CSV (for sheets/accounting)."""
    ingest, build, _ = _seller_mods()
    p = _resolve_folder(folder, demo, seed)
    events, _ = ingest(p)
    b = build(events)
    from omni_one.packs.seller_export import briefing_to_csv
    Path(out).write_text(briefing_to_csv(b))
    console.print(f"[green]wrote {out}[/green]")


@app.command()
def close(folder: str | None = typer.Option(None), demo: bool = typer.Option(False),
          seed: int = 42, out: str = typer.Option("./close_today"),
          shop: str = typer.Option("our shop"),
          locale: str = typer.Option("en", help="Reply/PO draft language: en|es|zh|fr|de (numbers never change)")):
    """DAILY CLOSE: 5-min ritual — profit, reorders+PO, reply drafts, leaks -> CSV/TXT bundle."""
    ingest, build, _ = _seller_mods()
    p = _resolve_folder(folder, demo, seed)
    events, _ = ingest(p)
    b = build(events)
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.seller_close import build_daily_close, write_close_bundle
    scen = run_all_scenarios(events)
    c = build_daily_close(events, b, scen, shop=shop, locale=locale)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]DAILY CLOSE {c['date']}[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green] {sorted(paths.values())}")


@app.command(name="pipeline-close")
def pipeline_close(out: str = typer.Option("./pipeline_close"),
                   seed: int = 42):
    """PIPELINE CLOSE: evidence + cost + verdict bundle for any records ($0, mock LLM)."""
    from omni_one.packs.pipeline_close import DEMO_RECORDS, build_pipeline_close, write_close_bundle
    c = build_pipeline_close(DEMO_RECORDS(seed))
    paths = write_close_bundle(c, out)
    console.print(f"[bold]PIPELINE CLOSE[/bold] — {c['kpis']} verdict={c['verdict']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="vision-close")
def vision_close(out: str = typer.Option("./vision_close")):
    """VISION CLOSE: photo -> OCR + numbers + COGS + evidence bundle ($0, offline)."""
    from omni_one.packs.vision_close import make_demo_image, build_vision_close, write_close_bundle
    c = build_vision_close(make_demo_image("receipt"), filename="demo_receipt.png")
    paths = write_close_bundle(c, out)
    console.print(f"[bold]VISION CLOSE[/bold] — verdict={c['verdict']} numbers={len(c['numbers'])}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="micro-close")
def micro_close(folder: str | None = typer.Option(None), demo: bool = typer.Option(True), seed: int = 42,
                out: str = typer.Option("./micro_close"),
                shop: str = typer.Option("Maya's Tacos"),
                locale: str = typer.Option("en", help="Draft language: en|es (numbers never change)")):
    """MICRO CLOSE: taco-shop daily ritual — revenue, buys, win-backs, vendor SMS ($0)."""
    import tempfile as _t
    from pathlib import Path as _P
    from omni_one.packs._labs.micro_biz import make_demo_folder, ingest_folder, build_briefing
    from omni_one.packs.micro_close import build_micro_close, write_close_bundle
    use_demo = demo or not folder
    if use_demo:
        with _t.TemporaryDirectory() as tmp:
            d = make_demo_folder(_P(tmp) / "m", seed=seed)
            events, _ = ingest_folder(d)
            c = build_micro_close(events, build_briefing(events), shop=shop, locale=locale)
    else:
        events, _ = ingest_folder(_P(folder).expanduser())
        from omni_one.packs._labs.micro_biz import build_briefing as _bb
        c = build_micro_close(events, _bb(events), shop=shop, locale=locale)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]MICRO CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="revops-close")
def revops_close(n: int = typer.Option(20), seed: int = 42,
                 out: str = typer.Option("./revops_close")):
    """REVOPS CLOSE: pipeline review — tiers, churn $, call sheet ($0, seeded)."""
    from omni_one.packs.revops_close import build_revops_close, write_close_bundle
    c = build_revops_close(None, n=n, seed=seed)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]REVOPS CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="ops-close")
def ops_close(demo: bool = typer.Option(True), seed: int = 42,
              out: str = typer.Option("./ops_close"),
              namespace: str = typer.Option("ops-daily")):
    """OPS CLOSE: full methodology loop bundle — foundry→ontology→workshop→AIP→audit ($0)."""
    import tempfile as _t
    from pathlib import Path as _P
    from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios
    from omni_one.packs.ops_close import build_ops_close, write_close_bundle
    with _t.TemporaryDirectory() as tmp:
        d = make_seller_demo_folder(_P(tmp) / "d", seed=seed)
        events, _ = ingest_seller_folder(d)
        b, scen = build_seller_briefing(events), run_all_scenarios(events)
        c = build_ops_close(events, b, scen, namespace=namespace)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]OPS CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="returns-close")
def returns_close(seed: int = typer.Option(42), out: str = typer.Option("./returns_close")):
    """RETURNS CLOSE: refund leaks + restock + reply drafts ($0, seeded)."""
    from omni_one.packs.returns_close import DEMO_RETURNS, build_returns_close, write_close_bundle
    c = build_returns_close(DEMO_RETURNS(seed))
    paths = write_close_bundle(c, out)
    console.print(f"[bold]RETURNS CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="cashflow-close")
def cashflow_close(seed: int = typer.Option(42), out: str = typer.Option("./cashflow_close")):
    """CASHFLOW CLOSE: payouts in, bills out, runway ($0, seeded)."""
    from omni_one.packs.cashflow_close import build_cashflow_close, write_close_bundle
    c = build_cashflow_close(None, None, seed=seed)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]CASHFLOW CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="reputation-close")
def reputation_close(seed: int = typer.Option(42), out: str = typer.Option("./reputation_close"),
                     shop: str = typer.Option("our shop")):
    """REPUTATION CLOSE: reply queue + star repair ($0, seeded)."""
    from omni_one.packs.reputation_close import DEMO_REVIEWS, build_reputation_close, write_close_bundle
    c = build_reputation_close(DEMO_REVIEWS(seed), seed=seed, shop=shop)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]REPUTATION CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="forecast-close")
def forecast_close(seed: int = typer.Option(42), out: str = typer.Option("./forecast_close")):
    """FORECAST CLOSE: stockout dates + safety stock + PO ($0, seeded)."""
    from omni_one.packs.forecast_close import DEMO_SKUS, build_forecast_close, write_close_bundle
    c = build_forecast_close(DEMO_SKUS(seed), seed=seed)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]FORECAST CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="rollup-close")
def rollup_close(seed: int = typer.Option(42), out: str = typer.Option("./rollup_close")):
    """ROLLUP CLOSE: portfolio ranking + cross-shop plays ($0, seeded)."""
    from omni_one.packs.rollup_close import DEMO_SHOPS, build_rollup_close, write_close_bundle
    c = build_rollup_close(DEMO_SHOPS(seed), seed=seed)
    paths = write_close_bundle(c, out)
    console.print(f"[bold]ROLLUP CLOSE[/bold] — {c['headline']}")
    for t in c["do_today"]:
        console.print(f"  • {t}")
    console.print(f"[green]wrote {len(paths)} files -> {out}/[/green]")


@app.command(name="auto")
def auto(folder: str | None = typer.Option(None), out: str = typer.Option("./auto_today"),
         seed: int = typer.Option(42), shop: str = typer.Option("our shop"),
         deep: bool = typer.Option(False, help="Also run the methodology audit bundle")):
    """AUTO: sniff the folder, run the right closes, say why. No folder = demo showcase."""
    from omni_one.packs.auto_close import run_auto
    s = run_auto(folder, out=out, seed=seed, shop=shop, deep=deep)
    console.print(f"[bold]AUTO CLOSE[/bold] {s['folder']} — ran {len(s['ran'])}/{len(s['plan'])}")
    for item in s["plan"]:
        mark = "green" if item["close"] in s["ran"] else "red"
        console.print(f"  [{mark}]✓ {item['close']}[/{mark}]: {item['reason']} [{item['evidence']}]")
    for k in s["ran"]:
        console.print(f"  → {k}: {s['headlines'].get(k, '?')}")
    console.print(f"[green]wrote auto.json + AUTO.txt -> {out}/[/green]")


@app.command()
def serve(port: int = 5003, host: str = "0.0.0.0"):
    """Run the FastAPI server (engine + Seller OS)."""
    import uvicorn
    from omni_one.api.fastapi_app import create_omni_one_app
    console.print(f"[bold]serving omni-one on {host}:{port} ($0)[/bold] docs: http://{host}:{port}/api/docs")
    uvicorn.run(create_omni_one_app(), host=host, port=port)


@app.command()
def evaluate(n: int = 500):
    """Run deterministic eval harness (bypass rate, cost, latency)."""
    from omni_one.core.eval_harness import benchmark
    res = benchmark(n=n, seed=42)
    console.print_json(json.dumps(res["pipeline_metrics"], indent=2, default=str)[:2000])


def main():
    app()


if __name__ == "__main__":
    main()
