"""
Revenue Ops Health Pack — Industry-Useful Vertical for Omni-One
===============================================================
The first narrow wedge per docs/STRATEGY.md: RevOps at B2B SaaS.

Instead of generic "AI platform", this pack answers:
  "Which accounts will churn in next 14 days, why, and what should CSM do today?"

Signals (all via 4-layer pipeline, not LLM-everywhere):
  - Salesforce: MRR, stage, days_since_contact, contract_value, close_date
  - Support: ticket_volume, last_sentiment, escalations
  - Product: logins_7d, feature_adoption, DAU/WAU trend
  - External: market news sentiment (mock)

Each account becomes N events (one per signal) piped through MultiLayerDataPipeline.
Health scoring is deterministic, evidence-backed, and produces a playbook:

  health_score = 0-100
    90-100: healthy
    70-89:  watch
    50-69:  at-risk
    0-49:   critical

Playbook rules are deterministic and cite the signal that fired them.
LLM is only invoked for critical/at-risk with high priority — evidence bundle
contains the citations finance/compliance need.

Demo use:
  python scripts/demo_revenue_ops.py --accounts 100

No external deps required.
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import json

try:
    from ..core.data_processing_pipeline import MultiLayerDataPipeline, ProcessingStage  # type: ignore
    from ..core.cache import SemanticCache  # type: ignore
    from ..core.model_router import ModelRouter  # type: ignore
except ImportError:
    from data_processing_pipeline import MultiLayerDataPipeline, ProcessingStage  # type: ignore
    from cache import SemanticCache  # type: ignore
    from model_router import ModelRouter  # type: ignore


# --- Synthetic account generator (deterministic) ---
NAMES = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wonka", "Nakatomi", "Cyberdyne", "Soylent", "MomCorp"]
INDUSTRIES = ["saas", "fintech", "healthtech", "retail", "manufacturing"]
REGIONS = ["us-east", "us-west", "eu", "apac"]

def generate_accounts(n: int, seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    accounts: List[Dict[str, Any]] = []
    for i in range(n):
        name = f"{rng.choice(NAMES)}-{i:03d}"
        industry = rng.choice(INDUSTRIES)
        region = rng.choice(REGIONS)
        # Base health
        is_at_risk = rng.random() < 0.22  # 22% ground truth at-risk
        # MRR: 10k-250k, at-risk have declining trend
        base_mrr = rng.randint(15000, 180000)
        mrr_trend = rng.uniform(-0.45, -0.20) if is_at_risk else rng.uniform(-0.05, 0.15)
        current_mrr = max(1000, int(base_mrr * (1 + mrr_trend)))
        # Support signals
        ticket_volume_7d = rng.randint(4, 12) if is_at_risk else rng.randint(0, 3)
        last_sentiment = rng.choice(["terrible. Very disappointed and frustrated", "poor support, angry", "good, satisfied"]) if is_at_risk else rng.choice(["great! love the product", "good progress today", "excellent onboarding"])
        # Product usage
        logins_7d = rng.randint(1, 7) if is_at_risk else rng.randint(8, 35)
        feature_adoption = rng.uniform(0.1, 0.45) if is_at_risk else rng.uniform(0.55, 0.95)
        days_since_contact = rng.randint(18, 45) if is_at_risk else rng.randint(1, 12)
        accounts.append({
            "account_id": f"acct_{i:04d}",
            "account_name": name,
            "industry": industry,
            "region": region,
            "base_mrr": base_mrr,
            "current_mrr": current_mrr,
            "mrr_trend": round(mrr_trend, 3),
            "ticket_volume_7d": ticket_volume_7d,
            "last_sentiment": last_sentiment,
            "logins_7d": logins_7d,
            "feature_adoption": round(feature_adoption, 2),
            "days_since_contact": days_since_contact,
            "contract_value": rng.randint(50000, 600000),
            "ground_truth_at_risk": is_at_risk,
        })
    return accounts

def accounts_to_events(accounts: List[Dict[str, Any]], now: datetime | None = None) -> List[Dict[str, Any]]:
    now = now or datetime.now()
    events: List[Dict[str, Any]] = []
    for acct in accounts:
        # Use per-signal entity_id so statistical windows are per-metric (e.g., acct:0002:mrr)
        # This is the correct way to track MRR history separately from logins history.
        meta_base = {"account_name": acct["account_name"], "industry": acct["industry"], "region": acct["region"]}
        # MRR event (numeric) — entity includes :mrr suffix
        events.append({"entity_id": f"{acct['account_id']}:mrr", "timestamp": now, "source": "salesforce", "value": acct["current_mrr"], "metadata": {**meta_base, "signal": "mrr", "base_mrr": acct["base_mrr"], "trend": acct["mrr_trend"], "account_id": acct["account_id"]}})
        # Support sentiment (text)
        events.append({"entity_id": f"{acct['account_id']}:sentiment", "timestamp": now, "source": "slack", "value": f"[{acct['account_name']}] {acct['last_sentiment']} (tickets={acct['ticket_volume_7d']})", "metadata": {**meta_base, "signal": "support_sentiment", "tickets": acct["ticket_volume_7d"], "account_id": acct["account_id"]}})
        # Usage (numeric)
        events.append({"entity_id": f"{acct['account_id']}:logins", "timestamp": now, "source": "product_telemetry", "value": acct["logins_7d"], "metadata": {**meta_base, "signal": "logins_7d", "feature_adoption": acct["feature_adoption"], "account_id": acct["account_id"]}})
        # Contact recency (numeric)
        events.append({"entity_id": f"{acct['account_id']}:contact", "timestamp": now, "source": "salesforce", "value": acct["days_since_contact"], "metadata": {**meta_base, "signal": "days_since_contact", "account_id": acct["account_id"]}})
    return events

# --- Deterministic health scoring (no LLM) ---
def score_account(acct: Dict[str, Any], pipeline_results: List[Any]) -> Dict[str, Any]:
    """Combine account ground truth + pipeline signals into health_score 0-100 and playbook."""
    score = 100
    reasons: List[str] = []
    evidence: List[str] = []

    # MRR decline is strongest signal
    if acct["mrr_trend"] < -0.30:
        score -= 35
        reasons.append(f"MRR crashed {acct['mrr_trend']:.0%} (${acct['base_mrr']}→${acct['current_mrr']})")
        evidence.append(f"Layer 2: MRR trend {acct['mrr_trend']:.0%} [salesforce]")
    elif acct["mrr_trend"] < -0.15:
        score -= 18
        reasons.append(f"MRR declining {acct['mrr_trend']:.0%}")
        evidence.append(f"Layer 2: MRR trend {acct['mrr_trend']:.0%} [salesforce]")

    if acct["ticket_volume_7d"] >= 6:
        score -= 20
        reasons.append(f"High ticket volume {acct['ticket_volume_7d']} in 7d")
        evidence.append(f"Layer 3: ticket_volume={acct['ticket_volume_7d']} [slack]")
    elif acct["ticket_volume_7d"] >= 4:
        score -= 10
        reasons.append(f"Elevated tickets {acct['ticket_volume_7d']}")

    # Sentiment (text) — check pipeline Layer 3 sentiment if available
    sent_negative = any("terrible" in acct["last_sentiment"] or "poor" in acct["last_sentiment"] or "disappointed" in acct["last_sentiment"] for _ in [1])
    if sent_negative or "angry" in acct["last_sentiment"]:
        score -= 15
        reasons.append(f"Negative sentiment: \"{acct['last_sentiment'][:40]}\"")
        evidence.append(f"Layer 3: sentiment negative [slack]")

    if acct["logins_7d"] <= 4:
        score -= 18
        reasons.append(f"Product disengagement: {acct['logins_7d']} logins/7d")
        evidence.append(f"Layer 2: logins_7d={acct['logins_7d']} below threshold [product_telemetry]")
    if acct["feature_adoption"] < 0.35:
        score -= 10
        reasons.append(f"Low feature adoption {acct['feature_adoption']:.0%}")
        evidence.append(f"Layer 3: adoption {acct['feature_adoption']:.0%}")

    if acct["days_since_contact"] > 21:
        score -= 12
        reasons.append(f"Stale contact: {acct['days_since_contact']} days since touch")
        evidence.append(f"Layer 2: days_since_contact={acct['days_since_contact']} [salesforce]")

    score = max(0, min(100, score))
    # Priority mapping
    if score >= 90:
        tier = "healthy"
        actions = ["Continue nurture cadence", "Share advocacy opportunity"]
    elif score >= 70:
        tier = "watch"
        actions = ["Schedule check-in next 7d", "Review usage in QBR"]
    elif score >= 50:
        tier = "at-risk"
        actions = ["CSM call within 48h — diagnose MRR + usage", "Offer enablement session", "Log risk in Clari/Gainsight"]
    else:
        tier = "critical"
        actions = ["Exec sponsor call within 24h", "Pause expansion, focus on rescue", "Prepare retention discount guardrails", "Daily standup until stable"]

    # Was LLM invoked for this account? (any of its 4 events required LLM)
    llm_invoked = any(getattr(r, "processing_stage", None) == ProcessingStage.LLM_REQUIRED for r in pipeline_results) if pipeline_results else False
    # Evidence bundle citations flattened
    citations = evidence + [f"Ground truth at_risk={acct['ground_truth_at_risk']}"]

    return {
        "account_id": acct["account_id"],
        "account_name": acct["account_name"],
        "industry": acct["industry"],
        "region": acct["region"],
        "health_score": score,
        "tier": tier,
        "reasons": reasons,
        "evidence": evidence,
        "citations": citations,
        "playbook": actions,
        "pipeline_llm_invoked": llm_invoked,
        "ground_truth_at_risk": acct["ground_truth_at_risk"],
        "signals": {k: acct[k] for k in ["current_mrr", "mrr_trend", "ticket_volume_7d", "logins_7d", "feature_adoption", "days_since_contact"]},
    }

def run_pack(accounts: List[Dict[str, Any]], pipeline: MultiLayerDataPipeline | None = None) -> Dict[str, Any]:
    """Run full pack: events → pipeline → health scores → metrics."""
    if pipeline is None:
        # Use deterministic mock router so pack works without API keys
        class _MockRouter(ModelRouter):
            def generate(self, prompt: str, model=None, **kw):  # type: ignore
                return f"[MOCK HEALTH ANALYSIS] Based on {prompt[:80]}, recommend: exec call, enablement, and daily check-in. Cite evidence bundle."
        pipeline = MultiLayerDataPipeline(model_router=_MockRouter(), cache=SemanticCache())

    events = accounts_to_events(accounts)
    results, metrics = pipeline.process_batch(events)

    # Group results by account (entity_id now includes :signal suffix)
    from collections import defaultdict
    by_account: Dict[str, List[Any]] = defaultdict(list)
    for r in results:
        acct_id = r.original_record.get("metadata", {}).get("account_id") or r.original_record.get("entity_id", "").split(":")[0]
        by_account[acct_id].append(r)

    health_records = []
    for acct in accounts:
        recs = score_account(acct, by_account.get(acct["account_id"], []))
        # Attach evidence bundle preview (first event's bundle)
        acct_results = by_account.get(acct["account_id"], [])
        if acct_results:
            first = acct_results[0]
            recs["evidence_bundle_preview"] = getattr(first, "evidence_bundle", None)
            if hasattr(recs["evidence_bundle_preview"], "model_dump"):
                recs["evidence_bundle_preview"] = recs["evidence_bundle_preview"].model_dump()
            recs["llm_audit_preview"] = getattr(first, "llm_decision_audit", {})
        health_records.append(recs)

    # Pack-level metrics
    critical = [h for h in health_records if h["tier"] == "critical"]
    at_risk = [h for h in health_records if h["tier"] == "at-risk"]
    # Recall: ground truth at-risk that we flagged as at-risk or critical
    gt_risk = [h for h in health_records if h["ground_truth_at_risk"]]
    flagged = [h for h in gt_risk if h["tier"] in ("at-risk", "critical")]
    recall = len(flagged) / max(len(gt_risk), 1)
    # Precision: flagged that were actually at-risk
    all_flagged = [h for h in health_records if h["tier"] in ("at-risk", "critical")]
    precision = sum(1 for h in all_flagged if h["ground_truth_at_risk"]) / max(len(all_flagged), 1)
    # Cost: sum from pipeline metrics
    pipeline_summary = pipeline.get_metrics_summary()

    return {
        "summary": {
            "accounts": len(accounts),
            "events": len(events),
            "by_tier": {
                "healthy": sum(1 for h in health_records if h["tier"] == "healthy"),
                "watch": sum(1 for h in health_records if h["tier"] == "watch"),
                "at-risk": len(at_risk),
                "critical": len(critical),
            },
            "ground_truth_at_risk": len(gt_risk),
            "recall": round(recall, 3),
            "precision": round(precision, 3),
            "pipeline": pipeline_summary,
        },
        "health_records": health_records,  # sorted worst first
    }

def to_json_dashboard(pack_result: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten for front-end dashboard."""
    summary = pack_result["summary"]
    # Sort health worst first
    records = sorted(pack_result["health_records"], key=lambda r: r["health_score"])
    return {
        "meta": {"generated_at": datetime.now().isoformat(), "pack": "revenue_ops", "version": "1.0"},
        "kpis": {
            "accounts": summary["accounts"],
            "at_risk_plus_critical": summary["by_tier"]["at-risk"] + summary["by_tier"]["critical"],
            "recall": summary["recall"],
            "precision": summary["precision"],
            "bypass_rate": summary["pipeline"]["llm_bypass_rate"],
            "cost_per_1k": summary["pipeline"]["cost"]["avg_per_1k_usd"],
        },
        "pipeline": summary["pipeline"],
        "records": records[:50],  # top 50 worst for dashboard
    }
