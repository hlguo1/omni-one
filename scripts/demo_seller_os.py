#!/usr/bin/env python3
"""
Demo Seller OS — ONE outstanding product for people selling stuff online
Drop a folder with Shopify/Etsy CSV, inventory, DMs, reviews, supplier invoices.
Works with zero integration, zero fees, offline.

Usage:
  PYTHONPATH=src python scripts/demo_seller_os.py
  PYTHONPATH=src python scripts/demo_seller_os.py --folder /tmp/my_shop --json /tmp/briefing.json
"""
import argparse, json, sys
from pathlib import Path
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from omni_one.packs.seller_os import ingest_seller_folder, build_seller_briefing, make_seller_demo_folder

def main():
    p = argparse.ArgumentParser(description="Seller OS — for people selling stuff online")
    p.add_argument("--folder", type=str, default="/tmp/seller_demo", help="Folder with messy seller files")
    p.add_argument("--json", type=str, default=None)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    folder = Path(args.folder)
    if not folder.exists() or not any(folder.rglob("*")):
        print(f"Creating demo seller folder at {folder}...")
        make_seller_demo_folder(folder, seed=args.seed)
        print(f"Demo created: {folder} (Shopify/Etsy/inventory/reviews/DMs/supplier photo)")
    events, report = ingest_seller_folder(folder)
    print(f"Ingested {len(events)} events from {report['files_ingested']}/{report['files_seen']} files {report['by_source']}")
    briefing = build_seller_briefing(events)
    k = briefing["kpis"]
    print("\n" + "="*60)
    print("SELLER OS — DAILY BRIEFING (people selling online)")
    print("="*60)
    print(f"GMV ${k['gmv']:.2f}  Fees ${k['fees']:.2f}  Ship ${k['shipping']:.2f}  Net ${k['net']:.2f}")
    print(f"COGS ${k['cogs']:.2f}  True Profit ${k['true_profit']:.2f}  Margin {k['margin_pct']:.1f}%")
    print(f"Orders {k['orders']}  AOV ${k['aov']:.2f}  Best: {k['best_seller']['product']} ({k['best_seller']['qty']})  Worst: {k['worst_seller']['product']} ({k['worst_seller']['qty']})")
    print(f"At-risk {k['at_risk']}  Stockout risk {k['stockout_risk']}")
    print(f"Pipeline {briefing['meta']['pipeline'].get('llm_bypass_rate','—')} bypass  Cost ${briefing['meta']['pipeline'].get('cost',{}).get('total_usd','—')}")
    print("\nAlerts:")
    for a in briefing["alerts"]:
        print(f"  [{a['severity']}] {a['message']}")
        if a["evidence"]: print(f"    ↳ {a['evidence'][0][:80]}")
    print("\nActions (do today):")
    for i, a in enumerate(briefing["actions"], 1):
        print(f"  {i}. {a}")
    if briefing["draft_reply"]["text"]:
        print(f"\nDraft reply ({briefing['draft_reply']['citation']}):")
        print(f"  \"{briefing['draft_reply']['text'][:180]}\"")
    if args.json:
        Path(args.json).write_text(json.dumps(briefing, indent=2, default=str))
        print(f"\nWrote {args.json}")

if __name__ == "__main__":
    main()
