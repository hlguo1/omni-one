#!/usr/bin/env python3
"""
Demo: Revenue Ops Health Pack
=============================
Runs 100 synthetic B2B SaaS accounts through the 4-layer pipeline,
produces health scores, playbooks, and a dashboard JSON.

Usage:
  PYTHONPATH=src python scripts/demo_revenue_ops.py --accounts 100 --seed 42
  PYTHONPATH=src python scripts/demo_revenue_ops.py --accounts 100 --json /tmp/revenue_dashboard.json
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure src on path for direct script run
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from omni_one.packs.revenue_ops import generate_accounts, run_pack, to_json_dashboard
from omni_one.core.eval_harness import MockModelRouter  # reuse if available

# fallback mock if import fails
try:
    from omni_one.core.eval_harness import MockModelRouter as _MR
    MockModelRouter = _MR
except Exception:
    pass

def main():
    parser = argparse.ArgumentParser(description="Revenue Ops Pack Demo")
    parser.add_argument("--accounts", type=int, default=100, help="Number of accounts")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--json", type=str, default=None, help="Write dashboard JSON to file")
    parser.add_argument("--full", type=str, default=None, help="Write full pack result JSON to file")
    args = parser.parse_args()

    print(f"Generating {args.accounts} synthetic accounts (seed={args.seed})...")
    accounts = generate_accounts(args.accounts, seed=args.seed)

    print("Running Revenue Ops Health Pack through 4-layer pipeline...")
    result = run_pack(accounts)
    dashboard = to_json_dashboard(result)

    summary = result["summary"]
    print("\n" + "="*60)
    print("REVENUE OPS HEALTH PACK — SUMMARY")
    print("="*60)
    print(f"Accounts: {summary['accounts']}  Events: {summary['events']}")
    print(f"By tier: {summary['by_tier']}")
    print(f"Ground truth at-risk: {summary['ground_truth_at_risk']}")
    print(f"Recall: {summary['recall']:.1%}  Precision: {summary['precision']:.1%}")
    print(f"Pipeline bypass: {summary['pipeline']['llm_bypass_rate']}  cost/1k: ${summary['pipeline']['cost']['avg_per_1k_usd']}")
    print(f"LLM calls: {summary['pipeline']['records_by_stage']['layer4_llm']} / {summary['pipeline']['total_records']}")

    # Show worst 5
    print("\nWorst 5 accounts (playbook):")
    for rec in dashboard["records"][:5]:
        print(f"  - {rec['account_name']} ({rec['account_id']}) score={rec['health_score']} tier={rec['tier']}")
        print(f"    Reasons: {', '.join(rec['reasons'][:2])}")
        print(f"    Playbook: {rec['playbook'][0]}")
        print(f"    Evidence: {rec['evidence'][0] if rec['evidence'] else '—'}")
        print(f"    LLM invoked: {rec['pipeline_llm_invoked']}  GroundTruth at-risk={rec['ground_truth_at_risk']}")

    if summary["recall"] < 0.6:
        print("\n[WARN] Recall <60% — tune thresholds or increase anomaly_rate in generator")
    else:
        print(f"\n[PASS] Recall {summary['recall']:.1%} meets >60% target for synthetic data")

    # Evidence bundle preview
    worst = dashboard["records"][0] if dashboard["records"] else None
    if worst and worst.get("evidence_bundle_preview"):
        print("\nEvidence bundle preview (worst account):")
        print(json.dumps(worst["evidence_bundle_preview"], indent=2)[:800])

    if args.json:
        Path(args.json).write_text(json.dumps(dashboard, indent=2, default=str))
        print(f"\nWrote dashboard JSON to {args.json}")
    if args.full:
        Path(args.full).write_text(json.dumps(result, indent=2, default=str))
        print(f"Wrote full result to {args.full}")

    # Machine-readable KPIs for CI
    print("\nKPIs:", json.dumps(dashboard["kpis"]))

if __name__ == "__main__":
    main()
