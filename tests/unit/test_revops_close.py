"""RevOps Close golden tests — the Monday ritual must never regress.

Golden book: n=20, seed=42 (measured 2026-10-11, deterministic fallback/lab):
  accounts=20, healthy=14, watch=0, flagged(at-risk+critical)=6, critical=6,
  churn_risk_usd=314555, expansion_usd=224146, recall=1.0, precision=1.0,
  headline="14/20 healthy (70.0%) · $314,555 at risk in 6 acct(s) · "
           "Top play: Exec Sponsor Rescue (4 acct(s))"

Covers: golden KPIs/headline, evidence+play on every at-risk row, churn
formula (churn == sum flagged MRR), idempotency, n=1/n=200 bounds, 4-file
bundle, CSV parse + headers, call-sheet talk tracks, tier math, play ranking,
expansion sizing (15% rule), and explicit-accounts + determinism paths.
"""
import csv
import io
import json
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOLDEN_HEADLINE = (
    "14/20 healthy (70.0%) · $314,555 at risk in 6 acct(s) · "
    "Top play: Exec Sponsor Rescue (4 acct(s))"
)
GOLDEN_KPIS = {
    "accounts": 20,
    "healthy": 14,
    "watch": 0,
    "at_risk": 6,
    "critical": 6,
    "healthy_pct": 70.0,
    "churn_risk_usd": 314555,
    "expansion_usd": 224146,
    "recall": 1.0,
    "precision": 1.0,
    "ground_truth_at_risk": 6,
}


def _close(n=20, seed=42, **kw):
    from omni_one.packs.revops_close import build_revops_close
    return build_revops_close(n=n, seed=seed, **kw)


def _custom_book():
    """Small hand-built book exercising every tier without randomness."""
    return [
        {
            "account_id": "acct_0001",
            "account_name": "HealthyCo-001",
            "industry": "saas",
            "region": "us-east",
            "base_mrr": 100000,
            "current_mrr": 105000,
            "mrr_trend": 0.05,
            "ticket_volume_7d": 1,
            "last_sentiment": "great! love the product",
            "logins_7d": 25,
            "feature_adoption": 0.80,
            "days_since_contact": 3,
            "contract_value": 300000,
            "ground_truth_at_risk": False,
        },
        {
            "account_id": "acct_0002",
            "account_name": "RiskyCo-002",
            "industry": "fintech",
            "region": "eu",
            "base_mrr": 100000,
            "current_mrr": 60000,
            "mrr_trend": -0.40,
            "ticket_volume_7d": 9,
            "last_sentiment": "terrible. Very disappointed and frustrated",
            "logins_7d": 2,
            "feature_adoption": 0.20,
            "days_since_contact": 30,
            "contract_value": 200000,
            "ground_truth_at_risk": True,
        },
        {
            "account_id": "acct_0003",
            "account_name": "WatchCo-003",
            "industry": "retail",
            "region": "us-west",
            "base_mrr": 50000,
            "current_mrr": 46000,
            "mrr_trend": -0.08,
            "ticket_volume_7d": 2,
            "last_sentiment": "good progress today",
            "logins_7d": 12,
            "feature_adoption": 0.60,
            "days_since_contact": 5,
            "contract_value": 120000,
            "ground_truth_at_risk": False,
        },
    ]


# ---------------------------------------------------------------------------
# 1. Golden: seed=42 book never drifts
# ---------------------------------------------------------------------------

def test_revops_close_golden_seed42():
    from omni_one.packs.revops_close import build_revops_close
    c = build_revops_close(n=20, seed=42)
    # Exact headline (healthy% + $ at-risk + top play in one line).
    assert c["headline"] == GOLDEN_HEADLINE, c["headline"]
    # Exact KPIs measured from the deterministic generator + lab scoring.
    for k, v in GOLDEN_KPIS.items():
        assert c["kpis"][k] == v, (k, c["kpis"][k], v)
    # Tier distribution adds up and matches KPIs.
    assert sum(t["count"] for t in c["tiers"]) == 20
    by_tier = {t["tier"]: t for t in c["tiers"]}
    assert by_tier["healthy"]["count"] == 14
    assert by_tier["watch"]["count"] == 0
    assert by_tier["at-risk"]["count"] == 0
    assert by_tier["critical"]["count"] == 6
    assert by_tier["healthy"]["pct"] == 70.0
    assert by_tier["critical"]["pct"] == 30.0
    assert by_tier["critical"]["mrr_usd"] == 314555
    # At-risk sheet is a top-5 preview of the 6 flagged; worst first.
    assert len(c["at_risk"]) == 5
    scores = [r["health_score"] for r in c["at_risk"]]
    assert scores == sorted(scores), scores
    assert c["at_risk"][0]["account"] == "Nakatomi-002"
    assert c["at_risk"][0]["health_score"] == 0
    # Plays ranked: save dollars first; top play is the golden one.
    assert c["plays"][0]["play"] == "Exec Sponsor Rescue"
    assert c["plays"][0]["play_id"] == "SAVE-EXEC"
    assert c["plays"][0]["accounts"] == 4
    assert c["plays"][0]["mrr_covered"] == 212002
    # do_today has exactly 3 calls in worst-first order.
    assert len(c["do_today"]) == 3
    assert "Nakatomi-002" in c["do_today"][0]
    assert "at risk" in c["do_today"][0]
    # Expansion: 13 proven-healthy candidates sized at 15%.
    assert len(c["expansion"]) == 13
    assert c["kpis"]["expansion_usd"] == 224146
    # Citations note present; offline/free flags set; deterministic seed kept.
    assert "salesforce" in c["citations"] and "slack" in c["citations"]
    assert c["free"] is True and c["offline"] is True
    assert c["seed"] == 42 and c["n"] == 20


def test_revops_close_golden_tiers_mrr_add_up():
    c = _close()
    # Tier MRR buckets sum to the book's total MRR; counts sum to n.
    total_mrr = sum(r["mrr"] for r in c["accounts"])
    assert sum(t["mrr_usd"] for t in c["tiers"]) == total_mrr
    assert sum(t["count"] for t in c["tiers"]) == c["kpis"]["accounts"] == 20
    # healthy_pct KPI matches tier pct; flagged KPI matches at-risk+critical.
    by_tier = {t["tier"]: t for t in c["tiers"]}
    assert c["kpis"]["healthy_pct"] == by_tier["healthy"]["pct"] == 70.0
    assert c["kpis"]["at_risk"] == by_tier["at-risk"]["count"] + by_tier["critical"]["count"] == 6
    # Every account row carries tier + owner + health in range.
    for r in c["accounts"]:
        assert r["tier"] in ("healthy", "watch", "at-risk", "critical")
        assert r["owner"] and r["health_score"] >= 0 and r["health_score"] <= 100
        assert r["mrr"] > 0
    # Accounts list is worst-first (health asc, MRR desc tie-break).
    keys = [(r["health_score"], -r["mrr"]) for r in c["accounts"]]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# 2. Every at-risk row has cited evidence + a next-step play
# ---------------------------------------------------------------------------

def test_at_risk_rows_all_have_evidence_and_play():
    c = _close()
    assert len(c["at_risk"]) >= 1
    for r in c["at_risk"]:
        # Identity + dollars.
        assert r["account"] and r["account_id"].startswith("acct_")
        assert isinstance(r["mrr"], int) and r["mrr"] > 0
        # Cited reason: non-empty reason + evidence citing a signal layer.
        assert r["reason"] and len(r["reason"]) >= 5, r
        assert r["evidence"] and len(r["evidence"]) >= 5, r
        assert any(sig in r["evidence"] for sig in ("[salesforce]", "[slack]", "[product_telemetry]")), r["evidence"]
        assert r["evidence_list"] and len(r["evidence_list"]) >= 1
        assert r["citation"] == r["evidence"]
        # Play: id + name + concrete next step + talk track naming the account.
        assert r["play"] and r["play_id"] and r["next_step"], r
        assert r["play_id"] in (
            "SAVE-EXEC", "SAVE-SUPPORT", "SAVE-ENABLE", "SAVE-MULTI",
            "SAVE-COMMERCIAL", "WATCH-QBR", "EXPAND-UPSELL", "EXPAND-ADVOCACY",
        )
        assert len(r["next_step"]) > 10
        assert r["talk_track"] and len(r["talk_track"]) > 40, r
        # Owner assigned deterministically.
        assert r["owner"] and r["owner_role"]
    # Full flagged set (not just preview) also clean when checked via accounts.
    flagged = [r for r in c["accounts"] if r["tier"] in ("at-risk", "critical")]
    assert len(flagged) == 6
    for r in flagged:
        assert r["evidence"] and r["play"] and r["next_step"]


def test_at_risk_reasons_match_worst_signals():
    c = _close()
    # Worst account crashed -42% MRR: reason must name the crash, evidence the layer.
    worst = c["at_risk"][0]
    assert "MRR crashed" in worst["reason"]
    assert "-42%" in worst["reason"]
    assert "[salesforce]" in worst["evidence"]
    assert worst["play"] == "Exec Sponsor Rescue"
    # A ticket-surge account routes to Support Swarm with slack evidence.
    swarm = next(r for r in c["at_risk"] if r["play_id"] == "SAVE-SUPPORT")
    assert "tickets" in swarm["reason"].lower() or "MRR declining" in swarm["reason"]
    assert "[salesforce]" in swarm["evidence"] or "[slack]" in swarm["evidence"]


# ---------------------------------------------------------------------------
# 3. Churn formula: churn_risk_usd == sum of flagged MRR
# ---------------------------------------------------------------------------

def test_churn_risk_usd_equals_sum_of_flagged_mrr():
    c = _close()
    flagged = [r for r in c["accounts"] if r["tier"] in ("at-risk", "critical")]
    expected = sum(r["mrr"] for r in flagged)
    assert c["kpis"]["churn_risk_usd"] == expected == 314555
    # Tier-bucket cross-check: at-risk + critical MRR equals the KPI.
    by_tier = {t["tier"]: t for t in c["tiers"]}
    assert by_tier["at-risk"]["mrr_usd"] + by_tier["critical"]["mrr_usd"] == expected
    # Same formula holds on a custom book (not just the golden seed).
    from omni_one.packs.revops_close import build_revops_close
    c2 = build_revops_close(accounts=_custom_book())
    flagged2 = [r for r in c2["accounts"] if r["tier"] in ("at-risk", "critical")]
    assert c2["kpis"]["churn_risk_usd"] == sum(r["mrr"] for r in flagged2)
    # And on other seeds/sizes (formula, not a magic number).
    for seed, n in ((7, 15), (99, 30), (1234, 50)):
        cx = build_revops_close(n=n, seed=seed)
        fx = [r for r in cx["accounts"] if r["tier"] in ("at-risk", "critical")]
        assert cx["kpis"]["churn_risk_usd"] == sum(r["mrr"] for r in fx), (seed, n)


def test_expansion_usd_equals_sum_of_candidates_at_15pct():
    from omni_one.packs.revops_close import EXPANSION_RATE
    c = _close()
    assert c["kpis"]["expansion_usd"] == sum(e["expansion_usd"] for e in c["expansion"]) == 224146
    for e in c["expansion"]:
        # Each candidate is proven healthy usage with a 15% sized upside.
        src = next(r for r in c["accounts"] if r["account_id"] == e["account_id"])
        assert src["tier"] == "healthy"
        assert src["feature_adoption"] >= 0.60 and src["logins_7d"] >= 10
        assert e["expansion_usd"] == int(src["mrr"] * EXPANSION_RATE)
        assert e["evidence"] and e["next_step"] and e["owner"]
    # Custom book: both healthy books with adoption >= 60% expand
    # (HealthyCo 0.80 + WatchCo 0.60-at-threshold both qualify; RiskyCo is critical).
    from omni_one.packs.revops_close import build_revops_close
    c2 = build_revops_close(accounts=_custom_book())
    assert len(c2["expansion"]) == 2
    by_exp = {e["account"]: e for e in c2["expansion"]}
    assert by_exp["HealthyCo-001"]["expansion_usd"] == int(105000 * 0.15) == 15750
    assert by_exp["WatchCo-003"]["expansion_usd"] == int(46000 * 0.15) == 6900
    assert c2["kpis"]["expansion_usd"] == 15750 + 6900 == 22650


# ---------------------------------------------------------------------------
# 4. Idempotent: same inputs -> same close
# ---------------------------------------------------------------------------

def test_revops_close_idempotent():
    from omni_one.packs.revops_close import (
        build_revops_close, accounts_to_csv, plays_to_csv, calls_to_txt,
    )
    c1 = build_revops_close(n=20, seed=42, date_str="2026-10-11")
    c2 = build_revops_close(n=20, seed=42, date_str="2026-10-11")
    assert c1 == c2
    assert c1["headline"] == c2["headline"] == GOLDEN_HEADLINE
    assert c1["kpis"] == c2["kpis"]
    assert c1["tiers"] == c2["tiers"]
    assert c1["at_risk"] == c2["at_risk"]
    assert c1["plays"] == c2["plays"]
    assert c1["expansion"] == c2["expansion"]
    assert c1["do_today"] == c2["do_today"]
    assert c1["accounts"] == c2["accounts"]
    # Exporters are pure functions of the close: byte-identical.
    assert accounts_to_csv(c1) == accounts_to_csv(c2)
    assert plays_to_csv(c1) == plays_to_csv(c2)
    assert calls_to_txt(c1) == calls_to_txt(c2)
    # Explicit accounts are order-independent in scoring (sorted worst-first).
    from omni_one.packs.revops_close import build_revops_close as b
    book = _custom_book()
    fwd = b(accounts=book, date_str="2026-10-11")
    rev = b(accounts=list(reversed(book)), date_str="2026-10-11")
    assert fwd["accounts"] == rev["accounts"]
    assert fwd["headline"] == rev["headline"]


def test_revops_close_seed_determinism_and_variance():
    from omni_one.packs.revops_close import build_revops_close
    a = build_revops_close(n=20, seed=42, date_str="2026-10-11")
    b = build_revops_close(n=20, seed=42, date_str="2026-10-11")
    assert a["headline"] == b["headline"]
    # Different seeds diverge (generator is actually seeded).
    other = build_revops_close(n=20, seed=7, date_str="2026-10-11")
    assert other["headline"] != a["headline"] or other["accounts"] != a["accounts"]
    # Same explicit book ignores seed/n entirely.
    book = _custom_book()
    s1 = build_revops_close(accounts=book, n=999, seed=1, date_str="2026-10-11")
    s2 = build_revops_close(accounts=book, n=5, seed=999, date_str="2026-10-11")
    assert s1["kpis"] == s2["kpis"] and s1["headline"] == s2["headline"]


# ---------------------------------------------------------------------------
# 5. Bounds: n=1 and n=200 never crash
# ---------------------------------------------------------------------------

def test_revops_close_bounds_n1_and_n200_no_crash():
    from omni_one.packs.revops_close import (
        build_revops_close, accounts_to_csv, plays_to_csv, calls_to_txt,
    )
    # n=1: single-account book still yields headline + 3 calls + sheets.
    tiny = build_revops_close(n=1, seed=42)
    assert tiny["kpis"]["accounts"] == 1
    assert len(tiny["accounts"]) == 1
    assert len(tiny["do_today"]) == 3
    assert "healthy" in tiny["headline"] and "at risk" in tiny["headline"]
    assert tiny["kpis"]["churn_risk_usd"] == sum(
        r["mrr"] for r in tiny["accounts"] if r["tier"] in ("at-risk", "critical")
    )
    assert isinstance(accounts_to_csv(tiny), str)
    assert isinstance(plays_to_csv(tiny), str)
    assert "CALL SHEET" in calls_to_txt(tiny)
    # n=200: large book scores fast, stays consistent, all sheets export.
    big = build_revops_close(n=200, seed=42)
    assert big["kpis"]["accounts"] == 200
    assert len(big["accounts"]) == 200
    assert sum(t["count"] for t in big["tiers"]) == 200
    assert big["kpis"]["churn_risk_usd"] == sum(
        r["mrr"] for r in big["accounts"] if r["tier"] in ("at-risk", "critical")
    )
    assert big["kpis"]["expansion_usd"] == sum(e["expansion_usd"] for e in big["expansion"])
    assert len(big["do_today"]) == 3
    assert len(big["at_risk"]) <= 5
    assert accounts_to_csv(big).count("\n") >= 201  # header + 200 rows
    assert "TALK TRACK" in calls_to_txt(big)
    # n=0: empty book is valid (no division by zero, headline explains).
    empty = build_revops_close(n=0, seed=42)
    assert empty["kpis"]["accounts"] == 0
    assert empty["kpis"]["churn_risk_usd"] == 0
    assert empty["kpis"]["expansion_usd"] == 0
    assert "Empty book" in empty["headline"]
    assert len(empty["do_today"]) == 3


def test_revops_close_explicit_and_empty_accounts():
    from omni_one.packs.revops_close import build_revops_close
    # Explicit book: tiers follow lab math (critical/healthy/healthy here).
    c = build_revops_close(accounts=_custom_book())
    assert c["kpis"]["accounts"] == 3
    by_id = {r["account_id"]: r for r in c["accounts"]}
    assert by_id["acct_0002"]["tier"] == "critical"
    assert by_id["acct_0001"]["tier"] == "healthy"
    assert by_id["acct_0002"]["play_id"] == "SAVE-EXEC"  # MRR crash dominates
    assert by_id["acct_0001"]["play_id"] == "EXPAND-UPSELL"
    assert len(c["do_today"]) == 3
    assert "RiskyCo-002" in c["do_today"][0]
    # Empty list behaves like n=0 (no crash, honest headline).
    e = build_revops_close(accounts=[])
    assert e["kpis"]["accounts"] == 0 and e["at_risk"] == [] and e["plays"] == []


# ---------------------------------------------------------------------------
# 6. Bundle: exactly 4 files; CSVs parse; call sheet has talk tracks
# ---------------------------------------------------------------------------

def test_revops_close_bundle_writes_four_files():
    from omni_one.packs.revops_close import build_revops_close, write_close_bundle
    c = build_revops_close(n=20, seed=42)
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        # Exactly the 4 contract files (mirrors seller bundle shape).
        assert set(paths.keys()) == {"close.json", "accounts.csv", "plays.csv", "calls.txt"}, paths
        assert len(paths) == 4
        for key, p in paths.items():
            assert Path(p).is_file(), (key, p)
            assert Path(p).stat().st_size > 0, (key, p)
        # close.json round-trips and preserves the golden headline.
        loaded = json.loads(Path(paths["close.json"]).read_text())
        assert loaded["headline"] == GOLDEN_HEADLINE
        assert loaded["kpis"] == c["kpis"]
        # Re-writing into the same dir is idempotent (no dupes, same bytes).
        before = {k: Path(v).read_text() for k, v in paths.items()}
        paths2 = write_close_bundle(c, tmp)
        assert set(paths2.keys()) == set(paths.keys())
        for k, v in paths2.items():
            assert Path(v).read_text() == before[k]


def test_revops_close_csvs_parse_with_exact_headers():
    from omni_one.packs.revops_close import (
        build_revops_close, accounts_to_csv, plays_to_csv,
    )
    c = build_revops_close(n=20, seed=42)
    # accounts.csv: exact header + one row per account, worst-first.
    a_text = accounts_to_csv(c)
    a_rows = list(csv.DictReader(io.StringIO(a_text)))
    assert a_rows and len(a_rows) == 20
    reader = csv.reader(io.StringIO(a_text))
    assert next(reader) == ["account", "tier", "mrr", "owner", "risk", "evidence"]
    for row in a_rows:
        assert row["account"] and row["tier"] in ("healthy", "watch", "at-risk", "critical")
        assert int(row["mrr"]) > 0 and row["owner"] and row["risk"] and row["evidence"]
    assert a_rows[0]["account"] == c["accounts"][0]["account"] == "Nakatomi-002"
    # plays.csv: exact header + one row per ranked play, MRR covered numeric.
    p_text = plays_to_csv(c)
    p_rows = list(csv.DictReader(io.StringIO(p_text)))
    assert p_rows and len(p_rows) == len(c["plays"]) == 5
    reader2 = csv.reader(io.StringIO(p_text))
    assert next(reader2) == ["play", "trigger", "owner", "accounts", "mrr_covered", "evidence"]
    assert p_rows[0]["play"] == "Exec Sponsor Rescue"
    assert int(p_rows[0]["accounts"]) == 4 and int(p_rows[0]["mrr_covered"]) == 212002
    for row in p_rows:
        assert row["play"] and row["trigger"] and row["owner"] and row["evidence"]
    # Bundle CSVs on disk match the in-memory exporters byte-for-byte.
    from omni_one.packs.revops_close import write_close_bundle
    with tempfile.TemporaryDirectory() as tmp:
        from omni_one.packs.revops_close import build_revops_close as b
        cc = b(n=20, seed=42)
        paths = write_close_bundle(cc, tmp)
        assert Path(paths["accounts.csv"]).read_text() == accounts_to_csv(cc)
        assert Path(paths["plays.csv"]).read_text() == plays_to_csv(cc)


def test_revops_close_calls_txt_has_talk_tracks():
    from omni_one.packs.revops_close import build_revops_close, calls_to_txt, write_close_bundle
    c = build_revops_close(n=20, seed=42)
    txt = calls_to_txt(c)
    # Header + headline + ordered call list.
    assert "REVOPS CLOSE" in txt and "CALL SHEET" in txt
    assert c["headline"] in txt
    assert "DO TODAY" in txt
    for i, call in enumerate(c["do_today"], 1):
        assert f"[{i}]" in txt and call[:40] in txt
    # Every at-risk account gets a talk track + next step block.
    assert txt.count("TALK TRACK:") == len(c["at_risk"]) == 5
    assert txt.count("NEXT STEP:") >= len(c["at_risk"])
    for r in c["at_risk"]:
        assert r["account"] in txt
        assert r["talk_track"][:40] in txt
        assert r["evidence"] in txt
    # Expansion section + play ranking + citations footer.
    assert "EXPANSION CALLS" in txt and "PLAY RANKING" in txt
    assert "Exec Sponsor Rescue" in txt
    assert "salesforce" in txt
    # calls.txt on disk equals the exporter.
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert Path(paths["calls.txt"]).read_text() == txt
