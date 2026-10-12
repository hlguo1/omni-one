"""
RevOps Close — the Monday pipeline-review ritual revenue teams actually run.
============================================================================
Sellers close the day; RevOps closes the week. Every Monday at 9am the CRO asks
three questions:

  1. How much of my book is actually healthy? (healthy % + tier mix, cited)
  2. Which dollars will churn in the next 14 days, why, and who calls today?
     (at-risk sheet: account + owner + cited reason + MRR + next-step play)
  3. Where is expansion hiding? (candidates with adoption proof + talk track)

One call, offline, $0, deterministic (seeded), no network, no LLM:

  from omni_one.packs.revops_close import build_revops_close
  close = build_revops_close(n=20, seed=42)
  # -> headline + kpis + tiers + at_risk[5] + plays + expansion + do_today[3]

  write_close_bundle(close, "./revops_close_2026-10-11")
  # -> close.json + accounts.csv + plays.csv + calls.txt (print / send / file)

Design rules (mirrors seller_close.py, B2C parcels -> B2B books):
- Deterministic: same (accounts, n, seed) -> same close (minus date stamp).
  No LLM/network/wall-clock in math. Only `date` uses today, never scoring.
- Every dollar cites a signal: [salesforce]/[slack]/[product_telemetry].
- Idempotent, private, offline, $0.
- Grounded in _labs/revenue_ops.py :: generate_accounts/score_account.
  Scoring here is standalone (no pipeline import) but numerically identical:
  healthy >= 90, watch 70-89, at-risk 50-69, critical < 50.

Account schema (same keys as generate_accounts): account_id/name, industry,
region, base/current_mrr, mrr_trend, ticket_volume_7d, last_sentiment,
logins_7d, feature_adoption, days_since_contact, contract_value,
ground_truth_at_risk (optional).

Health math (lab copy, see _score_one): start 100; trend<-30% -35 / <-15% -18;
tickets>=6 -20 / >=4 -10; negative sentiment -15; logins<=4 -18; adoption<35%
-10; stale>21d -12; clamp 0..100; tier by thresholds above.

Play assignment (first match wins): critical+MRR crash -> SAVE-EXEC;
critical+tickets>=6 -> SAVE-SUPPORT; critical+logins<=4 -> SAVE-ENABLE;
critical+stale -> SAVE-MULTI; critical fallback -> SAVE-COMMERCIAL;
at-risk -> SAVE-MULTI; watch -> WATCH-QBR; healthy+adopt>=.60 -> EXPAND-UPSELL;
healthy fallback -> EXPAND-ADVOCACY.

Expansion: healthy + adoption >= 0.60 + logins >= 10;
per-account int(mrr * 0.15); total = sum(candidates).
Churn: sum(current_mrr for tier in {at-risk, critical}) — contract-tested.
Owners: account_id suffix % len(CLOSE_OWNERS), stable across runs.
"""
from __future__ import annotations

import csv
import io
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants: tiers, owners, play library
# ---------------------------------------------------------------------------

# Tier cutoffs — must match _labs/revenue_ops.py exactly.
TIER_HEALTHY_MIN = 90
TIER_WATCH_MIN = 70
TIER_AT_RISK_MIN = 50

TIER_ORDER = ["healthy", "watch", "at-risk", "critical"]

TIER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "healthy": {
        "range": "90-100",
        "meaning": "On track. Usage + sentiment + contact fresh.",
        "motion": "Nurture + expand where adoption proves value.",
        "sla": "Standard cadence; QBR as scheduled.",
    },
    "watch": {
        "range": "70-89",
        "meaning": "One yellow signal (soft usage dip, mild ticket bump).",
        "motion": "Check-in inside 7 days; review usage in QBR.",
        "sla": "CSM check-in < 7d.",
    },
    "at-risk": {
        "range": "50-69",
        "meaning": "Two+ degrading signals or a steep single drop.",
        "motion": "CSM call inside 48h; diagnose MRR + usage; log risk.",
        "sla": "CSM call < 48h; risk logged in Clari/Gainsight.",
    },
    "critical": {
        "range": "0-49",
        "meaning": "Churn pattern: MRR crash + disengagement + anger/staleness.",
        "motion": "Exec sponsor call inside 24h; pause expansion; daily standup.",
        "sla": "Exec call < 24h; daily standup until stable.",
    },
}

# Deterministic owner pool: account_id % len(pool).
CLOSE_OWNERS: list[str] = [
    "Ava Chen",
    "Ben Ortiz",
    "Cara Lin",
    "Dev Patel",
    "Elif Yilmaz",
]

OWNER_ROLES: dict[str, str] = {
    "Ava Chen": "CSM — Enterprise",
    "Ben Ortiz": "CSM — Mid-Market",
    "Cara Lin": "AE — Expansion",
    "Dev Patel": "Support Lead",
    "Elif Yilmaz": "Exec Sponsor",
}

# Fallback generator pools (mirror lab pack).
_FALLBACK_NAMES = [
    "Acme", "Globex", "Initech", "Umbrella", "Stark",
    "Wonka", "Nakatomi", "Cyberdyne", "Soylent", "MomCorp",
]
_FALLBACK_INDUSTRIES = ["saas", "fintech", "healthtech", "retail", "manufacturing"]
_FALLBACK_REGIONS = ["us-east", "us-west", "eu", "apac"]

# Play library. File order is NOT rank; rank = MRR covered desc per close.
PLAY_LIBRARY: list[dict[str, Any]] = [
    {
        "play_id": "SAVE-EXEC",
        "play": "Exec Sponsor Rescue",
        "category": "save",
        "trigger": "critical + MRR crash (trend <= -30%)",
        "owner_role": "Exec Sponsor",
        "motion": "Exec-to-exec call in 24h; name the dollar gap; offer guardrailed save.",
        "next_step": "Book exec call within 24h; bring MRR bridge + retention options.",
        "talk_track": (
            "Hi {name}, it's {owner} — I'm pulling your exec sponsor in because your "
            "results slipped ({reason}). We see {evidence} and we own the fix. "
            "Can we get 20 min tomorrow with your sponsor? I'll bring a recovery plan "
            "and commercial options so {account} gets value back this week."
        ),
    },
    {
        "play_id": "SAVE-SUPPORT",
        "play": "Support Swarm",
        "category": "save",
        "trigger": "critical + ticket surge (tickets >= 6 in 7d)",
        "owner_role": "Support Lead",
        "motion": "Swarm open tickets today; daily update until backlog < 2.",
        "next_step": "Swarm tickets today; send daily status; close loop on each thread.",
        "talk_track": (
            "Hi {name}, {owner} here — I see {reason} and that's on us. I've pulled "
            "your {evidence} into a swarm today. You'll get one thread, one owner, "
            "and a daily update until every ticket is closed. First update by 5pm."
        ),
    },
    {
        "play_id": "SAVE-ENABLE",
        "play": "Enablement Sprint",
        "category": "save",
        "trigger": "critical + disengagement (logins <= 4 / 7d)",
        "owner_role": "CSM",
        "motion": "45-min enablement sprint on the one workflow they bought for.",
        "next_step": "Book 45-min enablement sprint on core workflow this week.",
        "talk_track": (
            "Hi {name}, {owner} here — usage shows {evidence}, so the team isn't "
            "getting the win you bought {account} for. Let's run a 45-min sprint on "
            "that one workflow Thursday — I'll bring a tailored walkthrough and leave "
            "your team with a checklist. Worth a shot before you decide anything?"
        ),
    },
    {
        "play_id": "SAVE-MULTI",
        "play": "Multithreading Blitz",
        "category": "save",
        "trigger": "at-risk (any) OR critical + stale contact (> 21d)",
        "owner_role": "CSM",
        "motion": "Map 3+ contacts in 48h; re-anchor on power user + economic buyer.",
        "next_step": "Multithread: book power user + economic buyer inside 48h.",
        "talk_track": (
            "Hi {name}, {owner} here — it's been a while ({reason}), and I want to "
            "re-anchor. Who else on your side feels {evidence} most? I'll do a 15-min "
            "listen with each of them this week and bring back one fix we can ship fast."
        ),
    },
    {
        "play_id": "SAVE-COMMERCIAL",
        "play": "Commercial Save",
        "category": "save",
        "trigger": "critical fallback (no single dominant signal)",
        "owner_role": "AE",
        "motion": "Retention offer inside guardrails; trade concession for multi-year/commit.",
        "next_step": "Prep guardrailed commercial option; AE joins next call.",
        "talk_track": (
            "Hi {name}, {owner} here — {reason} tells me we need to talk openly about "
            "fit and terms. I can bring options ({evidence}) if we can align on what "
            "success looks like for {account} this quarter. 20 min this week?"
        ),
    },
    {
        "play_id": "EXPAND-UPSELL",
        "play": "Usage Upsell",
        "category": "expand",
        "trigger": "healthy + adoption >= 60%",
        "owner_role": "AE — Expansion",
        "motion": "Quantify win; propose seat/feature add sized at ~15% of MRR.",
        "next_step": "Send win recap + 15% expansion quote; ask for intro to buyer.",
        "talk_track": (
            "Hi {name}, {owner} here — your team is crushing it ({reason}: {evidence}). "
            "Teams like yours usually add seats once adoption passes 60%. I sized a "
            "~15% add for {account} — can I send the one-pager and get 15 min Friday?"
        ),
    },
    {
        "play_id": "EXPAND-ADVOCACY",
        "play": "Advocacy Ask",
        "category": "expand",
        "trigger": "healthy fallback (adoption < 60% or light usage)",
        "owner_role": "CSM",
        "motion": "Ask for review/referral; plant expansion seed for next QBR.",
        "next_step": "Ask for G2/review + referral; log expansion seed for QBR.",
        "talk_track": (
            "Hi {name}, {owner} here — glad {account} is steady ({reason}). Would you "
            "be open to a 2-line G2 review? It helps your team get recognized, and "
            "I'll bring expansion ideas sized to your roadmap at the QBR."
        ),
    },
    {
        "play_id": "WATCH-QBR",
        "play": "QBR Nurture",
        "category": "watch",
        "trigger": "watch tier (single yellow signal)",
        "owner_role": "CSM",
        "motion": "7-day check-in; usage review pinned to next QBR agenda.",
        "next_step": "Schedule check-in inside 7d; pin usage review to QBR.",
        "talk_track": (
            "Hi {name}, {owner} here — quick pulse check: {reason} ({evidence}). "
            "Nothing urgent, but let's grab 20 min next week so {account} stays green, "
            "and I'll add a usage review to our QBR agenda."
        ),
    },
]

PLAY_BY_ID: dict[str, dict[str, Any]] = {p["play_id"]: p for p in PLAY_LIBRARY}

CITATIONS_NOTE = (
    "every number cites a signal: [salesforce] MRR/contact, "
    "[slack] tickets/sentiment, [product_telemetry] logins/adoption; "
    "audit via accounts.csv evidence column; method matches "
    "src/omni_one/packs/_labs/revenue_ops.py scoring"
)

# Expansion: 15% uplift on proven healthy usage.
EXPANSION_RATE = 0.15
EXPANSION_ADOPTION_MIN = 0.60
EXPANSION_LOGINS_MIN = 10

# Preview depths: KPI covers ALL flagged; sheet shows worst 5; 3 calls.
AT_RISK_PREVIEW = 5
DO_TODAY_N = 3


# Internal: account loading (lab generator if importable, else fallback)

def _fallback_generate_accounts(n: int, seed: int = 42) -> list[dict[str, Any]]:
    """Standalone copy of lab generate_accounts (same math, zero deps)."""
    rng = random.Random(seed)
    accounts: list[dict[str, Any]] = []
    for i in range(n):
        name = f"{rng.choice(_FALLBACK_NAMES)}-{i:03d}"
        industry = rng.choice(_FALLBACK_INDUSTRIES)
        region = rng.choice(_FALLBACK_REGIONS)
        is_at_risk = rng.random() < 0.22
        base_mrr = rng.randint(15000, 180000)
        mrr_trend = rng.uniform(-0.45, -0.20) if is_at_risk else rng.uniform(-0.05, 0.15)
        current_mrr = max(1000, int(base_mrr * (1 + mrr_trend)))
        if is_at_risk:
            ticket_volume_7d = rng.randint(4, 12)
            last_sentiment = rng.choice([
                "terrible. Very disappointed and frustrated",
                "poor support, angry",
                "good, satisfied",
            ])
            logins_7d = rng.randint(1, 7)
            feature_adoption = rng.uniform(0.1, 0.45)
            days_since_contact = rng.randint(18, 45)
        else:
            ticket_volume_7d = rng.randint(0, 3)
            last_sentiment = rng.choice([
                "great! love the product",
                "good progress today",
                "excellent onboarding",
            ])
            logins_7d = rng.randint(8, 35)
            feature_adoption = rng.uniform(0.55, 0.95)
            days_since_contact = rng.randint(1, 12)
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


def _load_accounts(
    accounts: list[dict[str, Any]] | None, n: int, seed: int
) -> list[dict[str, Any]]:
    """Caller-supplied as-is, else seeded generation (lab first, fallback)."""
    if accounts is not None:
        return list(accounts)
    n = max(0, int(n))
    if n == 0:
        return []
    try:
        from omni_one.packs._labs.revenue_ops import (  # type: ignore
            generate_accounts as _lab_gen,
        )
        return list(_lab_gen(n, seed=seed))
    except Exception:
        return _fallback_generate_accounts(n, seed=seed)


# Internal: scoring (exact lab math, pipeline-free)

def _is_negative_sentiment(text: str) -> bool:
    low = (text or "").lower()
    return (
        "terrible" in low
        or "poor" in low
        or "disappointed" in low
        or "angry" in low
    )


def _score_one(acct: dict[str, Any]) -> dict[str, Any]:
    """Score one account; mirrors lab score_account with no pipeline."""
    score = 100
    reasons: list[str] = []
    evidence: list[str] = []

    trend = float(acct.get("mrr_trend", 0) or 0)
    base_mrr = int(acct.get("base_mrr", 0) or 0)
    current_mrr = int(acct.get("current_mrr", 0) or 0)
    tickets = int(acct.get("ticket_volume_7d", 0) or 0)
    sentiment = str(acct.get("last_sentiment", "") or "")
    logins = int(acct.get("logins_7d", 0) or 0)
    adoption = float(acct.get("feature_adoption", 0) or 0)
    stale = int(acct.get("days_since_contact", 0) or 0)

    # MRR decline is the strongest signal.
    if trend < -0.30:
        score -= 35
        reasons.append(f"MRR crashed {trend:.0%} (${base_mrr}->${current_mrr})")
        evidence.append(f"Layer 2: MRR trend {trend:.0%} [salesforce]")
    elif trend < -0.15:
        score -= 18
        reasons.append(f"MRR declining {trend:.0%}")
        evidence.append(f"Layer 2: MRR trend {trend:.0%} [salesforce]")

    # Support load.
    if tickets >= 6:
        score -= 20
        reasons.append(f"High ticket volume {tickets} in 7d")
        evidence.append(f"Layer 3: ticket_volume={tickets} [slack]")
    elif tickets >= 4:
        score -= 10
        reasons.append(f"Elevated tickets {tickets}")
        evidence.append(f"Layer 3: ticket_volume={tickets} [slack]")

    # Sentiment.
    if _is_negative_sentiment(sentiment):
        score -= 15
        reasons.append(f"Negative sentiment: \"{sentiment[:40]}\"")
        evidence.append("Layer 3: sentiment negative [slack]")

    # Product disengagement.
    if logins <= 4:
        score -= 18
        reasons.append(f"Product disengagement: {logins} logins/7d")
        evidence.append(
            f"Layer 2: logins_7d={logins} below threshold [product_telemetry]"
        )
    if adoption < 0.35:
        score -= 10
        reasons.append(f"Low feature adoption {adoption:.0%}")
        evidence.append(f"Layer 3: adoption {adoption:.0%} [product_telemetry]")

    # Stale contact.
    if stale > 21:
        score -= 12
        reasons.append(f"Stale contact: {stale} days since touch")
        evidence.append(f"Layer 2: days_since_contact={stale} [salesforce]")

    score = max(0, min(100, score))
    if score >= TIER_HEALTHY_MIN:
        tier = "healthy"
    elif score >= TIER_WATCH_MIN:
        tier = "watch"
    elif score >= TIER_AT_RISK_MIN:
        tier = "at-risk"
    else:
        tier = "critical"
    return {
        "health_score": score,
        "tier": tier,
        "reasons": reasons,
        "evidence": evidence,
    }


def _owner_for(acct: dict[str, Any]) -> str:
    """Deterministic owner from account_id suffix (name-hash fallback)."""
    aid = str(acct.get("account_id", "") or "")
    try:
        num = int(aid.split("_")[-1].split(":")[0])
        return CLOSE_OWNERS[num % len(CLOSE_OWNERS)]
    except Exception:
        name = str(acct.get("account_name", "") or aid or "?")
        h = sum(ord(c) for c in name) % len(CLOSE_OWNERS)
        return CLOSE_OWNERS[h]


def _play_id_for(tier: str, acct: dict[str, Any]) -> str:
    """Play assignment; first matching rule wins (see module docstring)."""
    trend = float(acct.get("mrr_trend", 0) or 0)
    tickets = int(acct.get("ticket_volume_7d", 0) or 0)
    logins = int(acct.get("logins_7d", 0) or 0)
    stale = int(acct.get("days_since_contact", 0) or 0)
    adoption = float(acct.get("feature_adoption", 0) or 0)
    if tier == "critical":
        if trend <= -0.30:
            return "SAVE-EXEC"
        if tickets >= 6:
            return "SAVE-SUPPORT"
        if logins <= 4:
            return "SAVE-ENABLE"
        if stale > 21:
            return "SAVE-MULTI"
        return "SAVE-COMMERCIAL"
    if tier == "at-risk":
        return "SAVE-MULTI"
    if tier == "watch":
        return "WATCH-QBR"
    # healthy
    if adoption >= EXPANSION_ADOPTION_MIN:
        return "EXPAND-UPSELL"
    return "EXPAND-ADVOCACY"


def _expansion_value(acct: dict[str, Any]) -> int:
    """Expansion USD (0 when not a candidate). Tier checked by caller."""
    adoption = float(acct.get("feature_adoption", 0) or 0)
    logins = int(acct.get("logins_7d", 0) or 0)
    # Only proven healthy usage expands; scoring tier is checked by caller.
    if adoption >= EXPANSION_ADOPTION_MIN and logins >= EXPANSION_LOGINS_MIN:
        return int(int(acct.get("current_mrr", 0) or 0) * EXPANSION_RATE)
    return 0


def _first_name(account_name: str) -> str:
    """First name from 'Name-000' style labels."""
    base = (account_name or "there").split("-")[0].strip()
    return (base.split()[0] if base else "there")[:20] or "there"


def _talk_track(
    acct: dict[str, Any],
    scored: dict[str, Any],
    play: dict[str, Any],
    owner: str,
) -> str:
    """Render the play talk track with account evidence."""
    reasons = scored.get("reasons", []) or ["Scheduled review"]
    evidence_list = scored.get("evidence", []) or ["No single alarm; review book"]
    reason = reasons[0]
    evidence = evidence_list[0]
    return str(play.get("talk_track", "")).format(
        name=_first_name(str(acct.get("account_name", ""))),
        owner=owner,
        account=str(acct.get("account_name", "")),
        reason=reason,
        evidence=evidence,
    )


# Public: build_revops_close

def build_revops_close(
    accounts: list[dict[str, Any]] | None = None,
    n: int = 20,
    seed: int = 42,
    date_str: str | None = None,
) -> dict[str, Any]:
    """Build the Monday Close. None -> generate n with seed. Date stamp only."""


    raw = _load_accounts(accounts, n, seed)
    n_eff = len(raw)
    scored_rows: list[dict[str, Any]] = []
    for acct in raw:
        s = _score_one(acct)
        tier: str = s["tier"]
        owner = _owner_for(acct)
        play_id = _play_id_for(tier, acct)
        play = PLAY_BY_ID[play_id]
        mrr = int(acct.get("current_mrr", 0) or 0)
        reasons = list(s["reasons"])
        evidence = list(s["evidence"])
        if not evidence:
            evidence = ["Layer 2: all signals within bounds [salesforce+slack+product_telemetry]"]
        talk = _talk_track(acct, {"reasons": reasons or ["Steady book"], "evidence": evidence}, play, owner)
        scored_rows.append({
            "account": str(acct.get("account_name", "")),
            "account_id": str(acct.get("account_id", "")),
            "industry": str(acct.get("industry", "")),
            "region": str(acct.get("region", "")),
            "tier": tier,
            "health_score": int(s["health_score"]),
            "mrr": mrr,
            "base_mrr": int(acct.get("base_mrr", 0) or 0),
            "mrr_trend": float(acct.get("mrr_trend", 0) or 0),
            "ticket_volume_7d": int(acct.get("ticket_volume_7d", 0) or 0),
            "logins_7d": int(acct.get("logins_7d", 0) or 0),
            "feature_adoption": float(acct.get("feature_adoption", 0) or 0),
            "days_since_contact": int(acct.get("days_since_contact", 0) or 0),
            "owner": owner,
            "owner_role": OWNER_ROLES.get(owner, "CSM"),
            "reason": reasons[0] if reasons else "Steady — no degrading signal",
            "reasons": reasons,
            "evidence": evidence[0] if evidence else "",
            "evidence_list": evidence,
            "play_id": play_id,
            "play": str(play["play"]),
            "play_category": str(play["category"]),
            "next_step": str(play["next_step"]),
            "talk_track": talk,
            "ground_truth_at_risk": bool(acct.get("ground_truth_at_risk", False)),
        })

    scored_rows.sort(key=lambda r: (r["health_score"], -r["mrr"]))
    by_tier: dict[str, list[dict[str, Any]]] = {t: [] for t in TIER_ORDER}
    for r in scored_rows:
        by_tier[r["tier"]].append(r)
    tiers: list[dict[str, Any]] = []
    for t in TIER_ORDER:
        rows = by_tier[t]
        mrr_sum = sum(r["mrr"] for r in rows)
        pct = (len(rows) / n_eff * 100.0) if n_eff else 0.0
        tiers.append({
            "tier": t,
            "count": len(rows),
            "pct": round(pct, 1),
            "mrr_usd": mrr_sum,
            "definition": TIER_DEFINITIONS[t]["meaning"],
            "sla": TIER_DEFINITIONS[t]["sla"],
        })
    n_healthy = len(by_tier["healthy"])
    n_watch = len(by_tier["watch"])
    n_flagged = len(by_tier["at-risk"]) + len(by_tier["critical"])
    healthy_pct = (n_healthy / n_eff * 100.0) if n_eff else 0.0

    flagged = by_tier["at-risk"] + by_tier["critical"]
    churn_risk_usd = sum(r["mrr"] for r in flagged)
    expansion_rows: list[dict[str, Any]] = []
    for r in scored_rows:
        if r["tier"] != "healthy":
            continue
        probe = {
            "current_mrr": r["mrr"],
            "feature_adoption": r["feature_adoption"],
            "logins_7d": r["logins_7d"],
        }
        val = _expansion_value(probe)
        if val > 0:
            expansion_rows.append({
                "account": r["account"],
                "account_id": r["account_id"],
                "owner": r["owner"],
                "mrr": r["mrr"],
                "expansion_usd": val,
                "reason": f"Adoption {r['feature_adoption']:.0%} + {r['logins_7d']} logins/7d",
                "evidence": "Layer 3: adoption proven [product_telemetry]",
                "play": "Usage Upsell",
                "play_id": "EXPAND-UPSELL",
                "next_step": "Send win recap + 15% expansion quote; ask for buyer intro.",
            })
    expansion_rows.sort(key=lambda r: -r["expansion_usd"])
    expansion_usd = sum(r["expansion_usd"] for r in expansion_rows)

    gt_risk = [r for r in scored_rows if r["ground_truth_at_risk"]]
    flagged_ids = {r["account_id"] for r in flagged}
    gt_flagged = [r for r in gt_risk if r["account_id"] in flagged_ids]
    has_gt = any("ground_truth_at_risk" in a for a in raw) if raw else False
    if gt_risk:
        recall = len(gt_flagged) / len(gt_risk)
        precision = (sum(1 for r in flagged if r["ground_truth_at_risk"]) / len(flagged)) if flagged else 1.0
    elif has_gt:
        recall, precision = 1.0, 1.0
    else:
        recall, precision = 1.0, 1.0
    at_risk_preview = [r for r in scored_rows if r["tier"] in ("at-risk", "critical")][:AT_RISK_PREVIEW]
    at_risk: list[dict[str, Any]] = []
    for r in at_risk_preview:
        at_risk.append({
            "account": r["account"],
            "account_id": r["account_id"],
            "owner": r["owner"],
            "owner_role": r["owner_role"],
            "tier": r["tier"],
            "health_score": r["health_score"],
            "reason": r["reason"],
            "reasons": r["reasons"],
            "mrr": r["mrr"],
            "evidence": r["evidence"],
            "evidence_list": r["evidence_list"],
            "play": r["play"],
            "play_id": r["play_id"],
            "next_step": r["next_step"],
            "talk_track": r["talk_track"],
            "citation": r["evidence"],
        })

    play_groups: dict[str, list[dict[str, Any]]] = {}
    for r in scored_rows:
        play_groups.setdefault(r["play_id"], []).append(r)
    plays: list[dict[str, Any]] = []
    for pid, rows in play_groups.items():
        lib = PLAY_BY_ID[pid]
        rows_sorted = sorted(rows, key=lambda r: (r["health_score"], -r["mrr"]))
        top = rows_sorted[0]
        mrr_covered = sum(r["mrr"] for r in rows)
        owners_ranked = sorted({r["owner"] for r in rows})
        counts = {o: sum(1 for r in rows if r["owner"] == o) for o in owners_ranked}
        owner = sorted(counts, key=lambda o: (-counts[o], o))[0]
        plays.append({
            "play_id": pid,
            "play": lib["play"],
            "category": lib["category"],
            "trigger": lib["trigger"],
            "owner": owner,
            "owner_role": lib["owner_role"],
            "accounts": len(rows),
            "mrr_covered": mrr_covered,
            "evidence": top["evidence"],
            "example_account": top["account"],
            "next_step": lib["next_step"],
            "priority": "P0" if lib["category"] == "save" else ("P1" if pid == "WATCH-QBR" else "P2"),
        })
    cat_rank = {"save": 0, "watch": 1, "expand": 2}
    plays.sort(key=lambda p: (cat_rank.get(str(p["category"]), 9), -int(p["mrr_covered"]), -int(p["accounts"]), str(p["play_id"])))
    save_only = sorted(
        [p for p in plays if p["category"] == "save"],
        key=lambda p: (-int(p["mrr_covered"]), str(p["play_id"])),
    )
    other = [p for p in plays if p["category"] != "save"]
    if save_only:
        plays = save_only + sorted(other, key=lambda p: (-int(p["mrr_covered"]), str(p["play_id"])))
    top_play = plays[0] if plays else None
    do_today: list[str] = []
    for r in at_risk_preview[:DO_TODAY_N]:
        do_today.append(
            f"Call {r['account']} ({r['owner']}) — {r['reason']} — "
            f"${r['mrr']:,} at risk [{r['evidence']}] -> {r['play']}: {r['next_step']}"
        )
    if len(do_today) < DO_TODAY_N:
        for e in expansion_rows:
            if len(do_today) >= DO_TODAY_N:
                break
            if any(e["account"] in d for d in do_today):
                continue
            do_today.append(
                f"Call {e['account']} ({e['owner']}) — expansion: {e['reason']} — "
                f"+${e['expansion_usd']:,} upside [${e['mrr']:,} MRR] -> {e['play']}: {e['next_step']}"
            )
    if len(do_today) < DO_TODAY_N:
        for r in scored_rows:
            if len(do_today) >= DO_TODAY_N:
                break
            if any(r["account"] in d for d in do_today):
                continue
            do_today.append(
                f"Check {r['account']} ({r['owner']}) — {r['reason']} "
                f"[health {r['health_score']}] -> {r['play']}"
            )
    while len(do_today) < DO_TODAY_N:
        do_today.append("Book empty — review expansion pipeline and confirm QBR agenda.")
    do_today = do_today[:DO_TODAY_N]
    if n_eff:
        if top_play:
            headline = (
                f"{n_healthy}/{n_eff} healthy ({healthy_pct:.1f}%) · "
                f"${churn_risk_usd:,} at risk in {n_flagged} acct(s) · "
                f"Top play: {top_play['play']} ({top_play['accounts']} acct(s))"
            )
        else:
            headline = (
                f"{n_healthy}/{n_eff} healthy ({healthy_pct:.1f}%) · "
                f"${churn_risk_usd:,} at risk in {n_flagged} acct(s) · No plays"
            )
    else:
        headline = "0/0 healthy (0.0%) · $0 at risk in 0 acct(s) · Empty book — generate or paste accounts"

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "seed": seed,
        "n": n_eff,
        "headline": headline,
        "kpis": {
            "accounts": n_eff,
            "healthy": n_healthy,
            "watch": n_watch,
            "at_risk": n_flagged,
            "critical": len(by_tier["critical"]),
            "healthy_pct": round(healthy_pct, 1),
            "churn_risk_usd": churn_risk_usd,
            "expansion_usd": expansion_usd,
            "recall": round(float(recall), 3),
            "precision": round(float(precision), 3),
            "ground_truth_at_risk": len(gt_risk),
        },
        "tiers": tiers,
        "at_risk": at_risk,
        "plays": plays,
        "expansion": expansion_rows,
        "do_today": do_today,
        "accounts": scored_rows,
        "citations": CITATIONS_NOTE,
        "free": True,
        "offline": True,
    }


# Exporters: CSV + call sheet
def accounts_to_csv(close: dict[str, Any]) -> str:
    """Accounts sheet: account,tier,mrr,owner,risk,evidence (all, worst-first)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["account", "tier", "mrr", "owner", "risk", "evidence"])
    for r in close.get("accounts", []):
        w.writerow([
            r.get("account", ""),
            r.get("tier", ""),
            r.get("mrr", ""),
            r.get("owner", ""),
            r.get("reason", ""),
            r.get("evidence", ""),
        ])
    return buf.getvalue()


def plays_to_csv(close: dict[str, Any]) -> str:
    """Plays sheet: play,trigger,owner,accounts,mrr_covered,evidence."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["play", "trigger", "owner", "accounts", "mrr_covered", "evidence"])
    for p in close.get("plays", []):
        w.writerow([
            p.get("play", ""),
            p.get("trigger", ""),
            p.get("owner", ""),
            p.get("accounts", ""),
            p.get("mrr_covered", ""),
            p.get("evidence", ""),
        ])
    return buf.getvalue()


def calls_to_txt(close: dict[str, Any]) -> str:
    """Call sheet with talk tracks (Monday printout)."""
    k = close.get("kpis", {}) or {}
    out = [
        f"REVOPS CLOSE {close.get('date', '')} — CALL SHEET",
        f"{close.get('headline', '')}",
        "=" * 72,
        "",
        f"Book: {k.get('accounts', 0)} accts · "
        f"healthy {k.get('healthy', 0)} / watch {k.get('watch', 0)} / "
        f"flagged {k.get('at_risk', 0)} · "
        f"churn risk ${k.get('churn_risk_usd', 0):,} · "
        f"expansion +${k.get('expansion_usd', 0):,}",
        "",
        "DO TODAY (call in this order):",
    ]
    for i, t in enumerate(close.get("do_today", []), 1):
        out.append(f"  [{i}] {t}")
    out += ["", "-" * 72, "SAVE CALLS (worst first, cited):", "-" * 72, ""]
    at_risk = close.get("at_risk", []) or []
    if not at_risk:
        out.append("(no flagged accounts — book is clean; see expansion calls below)")
        out.append("")
    for i, r in enumerate(at_risk, 1):
        out += [
            f"[{i}] {r.get('account', '')} ({r.get('account_id', '')}) — "
            f"{r.get('owner', '')} [{r.get('owner_role', '')}]",
            f"    health {r.get('health_score', '')} ({r.get('tier', '')}) · "
            f"${r.get('mrr', 0):,} MRR at risk",
            f"    reason: {r.get('reason', '')}",
            f"    evidence: {r.get('evidence', '')}",
            f"    play: {r.get('play', '')} ({r.get('play_id', '')})",
            f"    TALK TRACK: {r.get('talk_track', '')}",
            f"    NEXT STEP: {r.get('next_step', '')}",
            "",
        ]
    out += ["-" * 72, "EXPANSION CALLS (proof-backed upsides):", "-" * 72, ""]
    expansion = close.get("expansion", []) or []
    if not expansion:
        out.append("(no expansion candidates — nurture the healthy book to 60%+ adoption)")
        out.append("")
    for i, e in enumerate(expansion[:5], 1):
        out += [
            f"[E{i}] {e.get('account', '')} — {e.get('owner', '')}",
            f"    MRR ${e.get('mrr', 0):,} -> +${e.get('expansion_usd', 0):,} upside "
            f"({e.get('reason', '')})",
            f"    evidence: {e.get('evidence', '')}",
            f"    NEXT STEP: {e.get('next_step', '')}",
            "",
        ]
    out += [
        "-" * 72,
        "PLAY RANKING (by MRR covered):",
        "-" * 72,
    ]
    for p in close.get("plays", []):
        out.append(
            f"  - {p.get('play', '')} [{p.get('priority', '')}]: "
            f"{p.get('accounts', 0)} acct(s), ${p.get('mrr_covered', 0):,} covered "
            f"({p.get('trigger', '')}) — owner: {p.get('owner', '')}"
        )
    out += ["", str(close.get("citations", "")), "free: true · offline: true"]
    return "\n".join(out)


# Bundle writer: 4 files
def write_close_bundle(close: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write close.json + accounts.csv + plays.csv + calls.txt. Returns paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(json.dumps(close, indent=2, default=str))
    paths["accounts.csv"] = str(out / "accounts.csv")
    (out / "accounts.csv").write_text(accounts_to_csv(close))
    paths["plays.csv"] = str(out / "plays.csv")
    (out / "plays.csv").write_text(plays_to_csv(close))
    paths["calls.txt"] = str(out / "calls.txt")
    (out / "calls.txt").write_text(calls_to_txt(close))
    return paths


__all__ = [
    "TIER_DEFINITIONS",
    "TIER_ORDER",
    "CLOSE_OWNERS",
    "PLAY_LIBRARY",
    "CITATIONS_NOTE",
    "EXPANSION_RATE",
    "build_revops_close",
    "accounts_to_csv",
    "plays_to_csv",
    "calls_to_txt",
    "write_close_bundle",
]
