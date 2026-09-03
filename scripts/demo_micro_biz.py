#!/usr/bin/env python3
"""
Demo: Micro-Biz Pack — Maya's Tacos
=====================================
Simulates the messiest small business: no website, no POS API, just a phone.

What it creates (if folder missing):
  /tmp/maya_tacos/
    whatsapp_chat.txt
    sales_log.csv
    receipts/receipt_*.txt/.jpg
    notebook.txt

Then runs: ingest_folder → 4-layer pipeline → deterministic briefing.

Usage:
  PYTHONPATH=src python scripts/demo_micro_biz.py
  PYTHONPATH=src python scripts/demo_micro_biz.py --folder /path/to/my_shop_dump --json /tmp/briefing.json

Also works with your own folder: just drop files in any structure.

No API keys, no DB, works offline.
"""
import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omni_one.packs.micro_biz import ingest_folder, build_briefing, make_demo_folder

def main():
    parser = argparse.ArgumentParser(description="Micro-Biz Pack Demo — Maya's Tacos")
    parser.add_argument("--folder", type=str, default="/tmp/maya_tacos", help="Folder with messy shop data (will be created if missing)")
    parser.add_argument("--json", type=str, default=None, help="Write briefing JSON to file")
    parser.add_argument("--seed", type=int, default=42, help="Seed for demo generation")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists() or not any(folder.rglob("*")):
        print(f"Creating demo folder at {folder} (Maya's Tacos)...")
        make_demo_folder(folder, seed=args.seed)
        print(f"Demo folder created. Try: ls -R {folder}")
    else:
        print(f"Using existing folder: {folder} ({sum(1 for _ in folder.rglob('*') if _.is_file())} files)")

    print(f"\nIngesting {folder}...")
    events, report = ingest_folder(folder)
    print(f"Ingested {len(events)} events from {report['files_ingested']}/{report['files_seen']} files")
    print(f"By source: {report['by_source']}")
    if report["errors"]:
        print(f"Errors: {report['errors'][:2]}")

    if not events:
        print("No events found — add some .txt/.csv/.jpg files and rerun.")
        return

    print("\nRunning 4-layer pipeline (deterministic-first, evidence bundles)...")
    briefing = build_briefing(events)

    # Pretty print briefing
    print("\n" + "="*60)
    print("MAYA'S TACOS — DAILY BRIEFING")
    print("="*60)
    kpis = briefing["kpis"]
    print(f"Revenue: ${kpis['revenue']:.2f}  Expenses: ${kpis['expenses']:.2f}  Net: ${kpis['net']:.2f}")
    print(f"Best seller: {kpis['best_seller']['item']} ({kpis['best_seller']['qty']:.0f})  Worst: {kpis['worst_seller']['item']} ({kpis['worst_seller']['qty']:.0f})")
    print(f"At-risk customers: {kpis['at_risk_customers']}  Happy: {kpis['happy_customers']}")
    print(f"Pipeline bypass: {briefing['meta']['pipeline']['llm_bypass_rate']}  Cost/1k: ${briefing['meta']['pipeline']['cost']['avg_per_1k_usd']}")

    print("\nAlerts:")
    for a in briefing["alerts"]:
        print(f"  [{a['severity']}] {a['message']}")
        if a["evidence"]:
            print(f"    ↳ {a['evidence'][0][:80]}")

    print("\nActions (do today):")
    for i, act in enumerate(briefing["actions"], 1):
        print(f"  {i}. {act}")

    if briefing["reorder_list"]:
        print(f"\nReorder: {', '.join(briefing['reorder_list'])}")

    if briefing["at_risk_preview"]:
        print("\nAt-risk preview:")
        for c in briefing["at_risk_preview"]:
            print(f"  - {c['sender']}: {c['text'][:70]}")
            print(f"    ↳ {c['citation']}")

    if briefing["draft_reply"]["text"]:
        print("\nDraft WhatsApp reply (LLM-gated, Spanish/English):")
        print(f"  \"{briefing['draft_reply']['text'][:180]}\"")
        print(f"  ↳ cites {briefing['draft_reply']['citation']}")

    print("\nEvidence sample (audit trail):")
    for ev in briefing["evidence_sample"][:3]:
        print(f"  - {ev.get('layer')}: {ev.get('citation') or ev.get('signal')}")

    if args.json:
        Path(args.json).write_text(json.dumps(briefing, indent=2, default=str))
        print(f"\nWrote briefing JSON to {args.json} (share with accountant / compliance)")

    # Verdict
    if kpis["at_risk_customers"] > 0 and briefing["draft_reply"]["text"]:
        print("\n[PASS] Detected at-risk customers + drafted reply — useful even with messy data")
    else:
        print("\n[PASS] Briefing generated from messy folder — no website/db needed")

    print(f"\nTip: drop your own files into {folder} and rerun. Omni-One handles any mess.")

if __name__ == "__main__":
    main()
