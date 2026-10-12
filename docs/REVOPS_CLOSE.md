# RevOps Close — the Monday pipeline-review ritual your revenue team runs

RevOps doesn't live in dashboards. It **closes the week**: how healthy the book
is, which dollars churn next, who calls today, where expansion hides — every
number cited, every call scripted. Omni-One's RevOps Close is that ritual in
one call — offline, free ($0), private, deterministic by seed.

```python
from omni_one.packs.revops_close import build_revops_close, write_close_bundle
close = build_revops_close(n=20, seed=42)
write_close_bundle(close, "./revops_close_2026-10-11")
# -> close.json + accounts.csv + plays.csv + calls.txt
```

> Scope note (PACK D): this pack ships the engine + sheets + docs only.
> CLI (`omni-one revops-close`) and API (`POST /api/v1/revenue/close`) are
> **wiring notes** at the bottom — not implemented here on purpose (PACK D
> must not touch `cli.py`, `client.py`, `api/`, `mcp_server.py`).

## The Monday routine (10 min)

| Min  | You do               | Close gives you |
|------|----------------------|-----------------|
| 0–1  | Read the headline    | `14/20 healthy (70.0%) · $314,555 at risk in 6 acct(s) · Top play: Exec Sponsor Rescue (4 acct(s))` |
| 1–6  | Work the call list   | `calls.txt`: 3 calls in order — worst MRR first, each with owner, cited reason, talk track, next step |
| 6–8  | Assign the plays     | `plays.csv`: ranked GTM motions by MRR covered (save dollars first, then watch, then expand) |
| 8–10 | File + expand        | `accounts.csv` → CRM/CS sheets; book 1 expansion call from the proof-backed upside list |

The rule: **no flagged account leaves Monday without an owner, a play, and a
call on the calendar.** The close makes that checkable in one page.

## What it computes (deterministic, no LLM, no network)

- **Health score 0–100 per account** — exact copy of the lab pack math in
  `src/omni_one/packs/_labs/revenue_ops.py :: score_account`, re-implemented
  standalone (no pipeline import) so the close runs with zero deps:
  start 100; MRR trend < −30% → −35 / < −15% → −18 `[salesforce]`;
  tickets ≥ 6 → −20 / ≥ 4 → −10 `[slack]`; negative sentiment
  (terrible/poor/disappointed/angry) → −15 `[slack]`; logins ≤ 4 → −18
  `[product_telemetry]`; adoption < 35% → −10 `[product_telemetry]`;
  stale contact > 21d → −12 `[salesforce]`; clamp 0–100.
- **Churn at risk** — `churn_risk_usd = sum(current_mrr for tier in
  {at-risk, critical})`. Contract-tested: the KPI always equals the flagged
  MRR sum, on every seed and book size. Golden demo: **$314,555 across 6
  flagged accounts**.
- **Expansion upside** — healthy accounts with adoption ≥ 60% **and** logins ≥
  10 are candidates; each sized at `int(current_mrr * 0.15)` (conservative
  land-and-expand on proven users). Golden demo: **13 candidates,
  +$224,146**.
- **Recall-ish** — when `ground_truth_at_risk` labels exist (generator books),
  recall = flagged-gt / all-gt and precision = correct-flagged / all-flagged.
  Golden demo: **recall 1.0, precision 1.0** (6/6 found, 0 false alarms).
  Custom books without labels report 1.0/1.0 neutral so the dollars stay the
  signal.
- **At-risk sheet (worst 5)** — each row: account, owner, cited reason, MRR,
  evidence (`Layer N: … [source]`), play + next step + word-for-word talk
  track. The KPI covers *all* flagged; the sheet previews the 5 worst.
- **Ranked plays** — accounts grouped by assigned play, ranked with save
  motions first by MRR covered, then expand/watch. Golden: Exec Sponsor
  Rescue (4 accts, $212,002) > Support Swarm (1, $84,782) > Enablement Sprint
  (1, $17,771) > Usage Upsell (13, $1,494,361) > Advocacy Ask (1, $56,597).
- **do_today[3]** — the 3 calls in order: flagged worst-first, backfilled with
  expansion calls (then health checks) when the book is cleaner than 3 alarms.
  Golden call #1: `Call Nakatomi-002 (Cara Lin) — MRR crashed -42% …`.

## Golden numbers (n=20, seed=42 — do not change without updating tests)

```
headline: 14/20 healthy (70.0%) · $314,555 at risk in 6 acct(s) ·
          Top play: Exec Sponsor Rescue (4 acct(s))
kpis: accounts=20 healthy=14 watch=0 at_risk(flagged)=6 critical=6
      healthy_pct=70.0 churn_risk_usd=314555 expansion_usd=224146
      recall=1.0 precision=1.0 ground_truth_at_risk=6
tiers: healthy 14 (70.0%, $1,550,958) · watch 0 · at-risk 0 · critical 6 (30.0%, $314,555)
at_risk preview (5): Nakatomi-002 (0, $59,417, SAVE-EXEC) · MomCorp-012 (7, $84,782, SAVE-SUPPORT) ·
  MomCorp-008 (18, $34,723, SAVE-EXEC) · Globex-016 (32, $17,771, SAVE-ENABLE) ·
  Soylent-010 (33, $76,033, SAVE-EXEC) [+1 more flagged beyond preview]
plays (5): SAVE-EXEC 4/$212,002 · SAVE-SUPPORT 1/$84,782 · SAVE-ENABLE 1/$17,771 ·
  EXPAND-UPSELL 13/$1,494,361 · EXPAND-ADVOCACY 1/$56,597
expansion: 13 candidates (top: Nakatomi-009 $196,756 → +$29,513)
```

Verify locally:

```bash
python3 -m compileall -q src/omni_one/packs/revops_close.py
PYTHONPATH=src python3 -m pytest tests/unit/test_revops_close.py -q
```

## Tier definitions (match the lab pack cutoffs exactly)

| Tier | Score | Meaning | Motion | SLA |
|------|-------|---------|--------|-----|
| healthy | 90–100 | On track; usage + sentiment + contact fresh | Nurture + expand where adoption proves value | Standard cadence; QBR as scheduled |
| watch | 70–89 | One yellow signal (soft dip, mild ticket bump) | Check-in inside 7 days; usage review in QBR | CSM check-in < 7d |
| at-risk | 50–69 | Two+ degrading signals or a steep single drop | CSM call inside 48h; diagnose MRR + usage; log risk | CSM call < 48h; risk in Clari/Gainsight |
| critical | 0–49 | Churn pattern: MRR crash + disengagement + anger/staleness | Exec sponsor call inside 24h; pause expansion; daily standup | Exec call < 24h; daily standup until stable |

Cutoffs live in `TIER_HEALTHY_MIN / TIER_WATCH_MIN / TIER_AT_RISK_MIN` and
`TIER_DEFINITIONS` (meaning + SLA per tier, surfaced in `tiers[]`).

## Play library (8 motions — file order is not rank; rank is per-close MRR)

| Play ID | Play | Trigger | Owner role | Next step |
|---------|------|---------|------------|-----------|
| SAVE-EXEC | Exec Sponsor Rescue | critical + MRR crash (trend ≤ −30%) | Exec Sponsor | Book exec call 24h; bring MRR bridge + retention options |
| SAVE-SUPPORT | Support Swarm | critical + tickets ≥ 6 / 7d | Support Lead | Swarm tickets today; daily status until backlog < 2 |
| SAVE-ENABLE | Enablement Sprint | critical + logins ≤ 4 / 7d | CSM | Book 45-min sprint on core workflow this week |
| SAVE-MULTI | Multithreading Blitz | at-risk (any) OR critical + stale > 21d | CSM | Multithread power user + economic buyer in 48h |
| SAVE-COMMERCIAL | Commercial Save | critical fallback (no dominant signal) | AE | Prep guardrailed offer; AE joins next call |
| EXPAND-UPSELL | Usage Upsell | healthy + adoption ≥ 60% | AE — Expansion | Send win recap + 15% quote; ask for buyer intro |
| EXPAND-ADVOCACY | Advocacy Ask | healthy fallback | CSM | Ask G2/review + referral; log seed for QBR |
| WATCH-QBR | QBR Nurture | watch tier | CSM | Check-in 7d; pin usage review to QBR |

Every play carries a `talk_track` template filled with `{name, owner,
account, reason, evidence}` — see `calls.txt` for the rendered call sheet.
Assignment is deterministic first-match-wins (`_play_id_for`); owners are
`account_id % len(CLOSE_OWNERS)` over Ava Chen / Ben Ortiz / Cara Lin /
Dev Patel / Elif Yilmaz, so the same account always pages the same human.

## Inputs: your book, as-is

Explicit dicts (lab schema) or generated on demand:

```python
build_revops_close(accounts=[...])   # your CRM/CS export, same keys as generate_accounts
build_revops_close(n=200, seed=7)    # synthetic book: 200 accounts, seeded
build_revops_close(n=1, seed=42)     # single-account triage still yields 3 calls
build_revops_close(n=0)              # empty book: honest "Empty book" headline, no crash
```

Account keys: `account_id, account_name, industry, region, base_mrr,
current_mrr, mrr_trend, ticket_volume_7d, last_sentiment, logins_7d,
feature_adoption, days_since_contact, contract_value,
ground_truth_at_risk?`. When `accounts=None`, the loader prefers
`_labs/revenue_ops.generate_accounts` (proves wiring) and falls back to an
identical local generator when pipeline deps are unavailable — same schema,
same seed behavior either way.

## Outputs: artifacts the team already uses

- `close.json` — everything (headline, kpis, tiers, at_risk, plays, expansion,
  do_today, accounts worst-first, citations, seed/n/date).
- `accounts.csv` — `account,tier,mrr,owner,risk,evidence` (all accounts,
  worst-first; 20 rows + header in the golden book).
- `plays.csv` — `play,trigger,owner,accounts,mrr_covered,evidence` (one row
  per ranked play; 5 rows + header golden).
- `calls.txt` — printable call sheet: headline + DO TODAY[3] + save-call
  blocks (talk track + next step each) + top-5 expansion calls + play ranking
  + citations footer.

```python
from omni_one.packs.revops_close import accounts_to_csv, plays_to_csv, calls_to_txt
accounts_to_csv(close)  # str with exact header above
plays_to_csv(close)     # str with exact header above
calls_to_txt(close)     # str with TALK TRACK: per at-risk account
```

## Intended wiring (NOT shipped in PACK D — notes for the next pack)

When the team is ready to expose the close, the intended surface mirrors the
seller close exactly (do not implement until PACK D is merged):

```bash
# Intended CLI (requires touching cli.py — out of scope here):
omni-one revops-close --accounts 20 --seed 42 --out ./revops_close_2026-10-11
omni-one revops-close --accounts 200 --seed 7 --out ./revops_close_big
```

```python
# Intended API (requires touching api/ — out of scope here):
# POST /api/v1/revenue/close {"n": 20, "seed": 42} -> close.json
# GET  /api/v1/revenue/close.csv?n=20&seed=42      -> accounts.csv download
# Intended MCP: {"tool": "revops_close", "args": {"n": 20, "seed": 42}}
# Intended SDK: OmniOneClient.local().revops_close(n=20, seed=42)["headline"]
```

Wiring checklist for that pack: add `revops-close` command in `cli.py`
(thin wrapper over `build_revops_close` + `write_close_bundle`), add
`POST /api/v1/revenue/close` (+ CSV download) in `api/`, register the MCP
tool in `mcp_server.py`, add a `revops_close()` SDK method in `client.py`,
and contract-test CLI/SDK/API parity the way `test_daily_close.py` does for
the seller close. Keep the engine import-free so none of that changes golden
numbers.

## Habit loop (why teams stick)

Week 1: paste the book → close bundle → worst 5 called Monday → 1 save pays
for the ritual (it's $0). Week 4: multithreading + support-swarm motions get
named in standup; stale-contact rate drops. Quarter: `churn_risk → $0`
streak + expansion pipeline from proven adoption → the close becomes the
Monday forecast input.

Roadmap: scheduled 9am Monday close (`cron` + email/Slack), CRM write-back
(risk + play → Gainsight/Clari), sequence autopilot (multithreading mails
from talk tracks), Spanish/Chinese talk tracks (numbers never change).

See: `src/omni_one/packs/revops_close.py` (871 lines),
`tests/unit/test_revops_close.py` (13 tests), `src/omni_one/packs/_labs/revenue_ops.py`
(generator + scoring reference), `src/omni_one/packs/seller_close.py`
(structural model: headline/do_today/sheets/bundle).
