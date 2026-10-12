"""
Cash-Flow Close — the Friday money-in-hand ritual shops actually run.
=====================================================================
Sellers close the day; operators close the cash. Every Friday at 4pm the
owner asks three questions:

  1. How much money actually lands in the next 7 days? (net arriving, cited)
  2. Can I pay every bill and still make payroll? (cash after payables + runway)
  3. What do I do TODAY so Friday doesn't bounce? (3 money moves, cited)

One call, offline, $0, deterministic (seeded), no network, no LLM::

    from omni_one.packs.cashflow_close import build_cashflow_close
    close = build_cashflow_close(seed=42)
    # -> headline + kpis + payouts[10] + payables[3] + pay_schedule + do_today[3]

    write_close_bundle(close, "./cashflow_close_2026-10-11")
    # -> close.json + close.csv + payouts.csv + actions.txt (print / send / file)

Design rules (mirrors revops_close.py, micro_close.py):
- Deterministic: same (payouts, payables, seed, cash_on_hand) -> same close
  (minus date stamp). No LLM/network/wall-clock in math. Only `date` uses
  today, never scoring.
- Every dollar cites a record: [shopify/stripe/paypal:payouts#N] for money in,
  [ledger:payables#N] for money out.
- Idempotent, private, offline, $0.
- Fixed daily burn: DAILY_BURN = 85.0 USD/day. Runway = cash_after / burn.
- Tight day = earliest day index 0..7 with the minimum projected cash balance,
  where balance[d] = cash_on_hand + arrived_net(<=d) - due_bills(<=d).

Payout schema: payout_id, channel, gross, fees, net, arrival_day, citation.
Payable schema: payable_id, name, amount, due_day, citation.
Pay-schedule schema: payable_id, payable, amount, due_day, pay_from,
  arrival_day, covered, citation, note.

Golden demo (seed=42, cash_on_hand=1200.0) — asserted in tests, do not drift.
Run once to refresh the numbers below after any generator change.
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
# Constants — Friday ritual tuning (see module docstring for rationale)
# ---------------------------------------------------------------------------

DAILY_BURN = 85.0
PAYOUT_CHANNELS = ["shopify", "stripe", "paypal"]
FEE_RATES: dict[str, float] = {
    "shopify": 0.029,
    "stripe": 0.029,
    "paypal": 0.0349,
}
FIXED_FEE = 0.30
DEMO_PAYOUT_N = 10
DO_TODAY_N = 3

CITATIONS_NOTE = (
    "every dollar cites a record: [shopify/stripe/paypal:payouts#N] money in, "
    "[ledger:payables#N] money out; audit via payouts.csv; offline $0"
)

__all__ = [
    "DAILY_BURN",
    "PAYOUT_CHANNELS",
    "FEE_RATES",
    "CITATIONS_NOTE",
    "DEMO_PAYOUTS",
    "DEMO_PAYABLES",
    "build_cashflow_close",
    "close_to_csv",
    "payouts_to_csv",
    "actions_to_txt",
    "write_close_bundle",
]


# ---------------------------------------------------------------------------
# Demo generators — deterministic, seeded, offline
# ---------------------------------------------------------------------------

def DEMO_PAYOUTS(seed: int = 42, n: int = DEMO_PAYOUT_N) -> list[dict[str, Any]]:  # noqa: N802 - spec-mandated CAPS name
    """Deterministic ~10 payout records for the golden demo.

    Each record: channel (shopify/stripe/paypal), gross, fees, net,
    arrival_day (+0..+5 days out), citation "[<channel>:payouts#N]".
    Fees = gross * channel_rate + $0.30, rounded to cents; net = gross - fees.
    """
    rng = random.Random(seed)
    payouts: list[dict[str, Any]] = []
    for i in range(max(0, int(n))):
        channel = rng.choice(PAYOUT_CHANNELS)
        gross = round(rng.uniform(200.0, 1200.0), 2)
        rate = FEE_RATES[channel]
        fees = round(gross * rate + FIXED_FEE, 2)
        net = round(gross - fees, 2)
        arrival_day = rng.randint(0, 5)
        payouts.append({
            "payout_id": f"PO-{i + 1:03d}",
            "channel": channel,
            "gross": gross,
            "fees": fees,
            "net": net,
            "arrival_day": arrival_day,
            "citation": f"[{channel}:payouts#{i + 1}]",
        })
    return payouts


# Three fixed payables: supplier, rent, shipping (spec-mandated constant).
DEMO_PAYABLES: list[dict[str, Any]] = [
    {
        "payable_id": "BILL-001",
        "name": "supplier restock",
        "amount": 650.00,
        "due_day": 2,
        "citation": "[ledger:payables#1]",
    },
    {
        "payable_id": "BILL-002",
        "name": "rent",
        "amount": 900.00,
        "due_day": 5,
        "citation": "[ledger:payables#2]",
    },
    {
        "payable_id": "BILL-003",
        "name": "shipping",
        "amount": 320.00,
        "due_day": 1,
        "citation": "[ledger:payables#3]",
    },
]


def _copy_payables(
    payables: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Copy caller payables as-is, else the 3 fixed demo bills."""
    if payables is not None:
        return [dict(p) for p in payables]
    return [dict(p) for p in DEMO_PAYABLES]


# ---------------------------------------------------------------------------
# Internal: cash math (pure, deterministic)
# ---------------------------------------------------------------------------

def _daily_balances(
    payouts: list[dict[str, Any]],
    payables: list[dict[str, Any]],
    cash_on_hand: float,
    horizon: int = 7,
) -> list[float]:
    """Projected end-of-day cash for day 0..horizon (inclusive)."""
    balances: list[float] = []
    for d in range(horizon + 1):
        arrived = sum(float(p.get("net", 0) or 0) for p in payouts if int(p.get("arrival_day", 0) or 0) <= d)
        due = sum(float(b.get("amount", 0) or 0) for b in payables if int(b.get("due_day", 0) or 0) <= d)
        balances.append(round(float(cash_on_hand) + arrived - due, 2))
    return balances


def _build_pay_schedule(
    payouts: list[dict[str, Any]],
    payables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match each payable (due-day order) to the earliest payout on/before due.

    Falls back to the earliest payout overall (marked late) when nothing
    lands in time, or "cash_on_hand" when there are no payouts at all.
    Deterministic: ties break by payout_id.
    """
    ordered_payouts = sorted(
        list(payouts or []),
        key=lambda p: (int(p.get("arrival_day", 0) or 0), str(p.get("payout_id", ""))),
    )
    ordered_bills = sorted(
        list(payables or []),
        key=lambda b: (int(b.get("due_day", 0) or 0), str(b.get("payable_id", ""))),
    )
    schedule: list[dict[str, Any]] = []
    for b in ordered_bills:
        due = int(b.get("due_day", 0) or 0)
        cands = [p for p in ordered_payouts if int(p.get("arrival_day", 0) or 0) <= due]
        if cands:
            chosen = cands[0]
            covered = True
        elif ordered_payouts:
            chosen = ordered_payouts[0]
            covered = False
        else:
            chosen = None
            covered = False
        if chosen is None:
            schedule.append({
                "payable_id": str(b.get("payable_id", "")),
                "payable": str(b.get("name", "")),
                "amount": round(float(b.get("amount", 0) or 0), 2),
                "due_day": due,
                "pay_from": "cash_on_hand",
                "payout_channel": "",
                "arrival_day": -1,
                "covered": (float(cash_on_hand_fallback()) >= float(b.get("amount", 0) or 0)),
                "citation": str(b.get("citation", "")),
                "note": "no payouts — pay from cash on hand",
            })
            continue
        pay_from = str(chosen.get("payout_id", ""))
        arr = int(chosen.get("arrival_day", 0) or 0)
        if covered:
            note = f"pay {b.get('name', '')} from {pay_from} (lands day {arr}, due day {due})"
        else:
            note = (
                f"hold {b.get('name', '')} until {pay_from} lands day {arr} "
                f"(due day {due} — late, delay or split)"
            )
        schedule.append({
            "payable_id": str(b.get("payable_id", "")),
            "payable": str(b.get("name", "")),
            "amount": round(float(b.get("amount", 0) or 0), 2),
            "due_day": due,
            "pay_from": pay_from,
            "payout_channel": str(chosen.get("channel", "")),
            "arrival_day": arr,
            "covered": covered,
            "citation": f"{b.get('citation', '')} <- {chosen.get('citation', '')}",
            "note": note,
        })
    return schedule


def cash_on_hand_fallback() -> float:
    """Default cash used only for the no-payouts schedule branch (kept tiny)."""
    return 1200.0


# ---------------------------------------------------------------------------
# Main builder — payouts + payables -> Friday close
# ---------------------------------------------------------------------------

def build_cashflow_close(
    payouts: list[dict[str, Any]] | None = None,
    payables: list[dict[str, Any]] | None = None,
    seed: int = 42,
    cash_on_hand: float = 1200.0,
    date_str: str | None = None,
) -> dict[str, Any]:
    """Build the Friday Cash-Flow Close (deterministic, offline, $0).

    Args:
        payouts: explicit payout dicts (same keys as DEMO_PAYOUTS rows).
            When None, generates ~10 seeded demo payouts.
        payables: explicit payable dicts (payable_id/name/amount/due_day).
            When None, uses the 3 fixed demo bills.
        seed: demo generator seed (ignored when payouts are explicit).
        cash_on_hand: starting cash USD.
        date_str: ``YYYY-MM-DD`` label. Defaults to today. Excluded from
            every idempotency comparison except the ``date`` field itself.

    Returns:
        dict with ``date, headline, kpis, payouts, payables, pay_schedule,
        do_today[3], citations, free, seed`` (+ ``offline, daily_cash``).
    """
    if payouts is not None:
        payout_rows = [dict(p) for p in payouts]
    else:
        payout_rows = DEMO_PAYOUTS(seed=seed)
    payable_rows = _copy_payables(payables)
    cash = round(float(cash_on_hand or 0), 2)

    gross_total = round(sum(float(p.get("gross", 0) or 0) for p in payout_rows), 2)
    fee_total = round(sum(float(p.get("fees", 0) or 0) for p in payout_rows), 2)
    # Net is defined as gross - fees so the identity always holds to the cent.
    net_total = round(gross_total - fee_total, 2)
    arriving_7d = round(
        sum(float(p.get("net", 0) or 0) for p in payout_rows if int(p.get("arrival_day", 0) or 0) <= 7),
        2,
    )
    payables_total = round(sum(float(b.get("amount", 0) or 0) for b in payable_rows), 2)
    cash_after = round(cash + arriving_7d - payables_total, 2)
    runway_days = round(cash_after / DAILY_BURN, 1) if DAILY_BURN else 0.0

    balances = _daily_balances(payout_rows, payable_rows, cash, horizon=7)
    tight_day = min(range(len(balances)), key=lambda d: (balances[d], d))

    schedule = _build_pay_schedule(payout_rows, payable_rows)

    # ---- do_today: exactly three money moves, each with $ + citation -------
    if payable_rows:
        biggest_bill = max(payable_rows, key=lambda b: (float(b.get("amount", 0) or 0), str(b.get("name", ""))))
    else:
        biggest_bill = {"name": "no bills", "amount": 0.0, "due_day": 0, "citation": "[ledger:payables#0]"}
    if payout_rows:
        latest_payout = max(
            payout_rows,
            key=lambda p: (int(p.get("arrival_day", 0) or 0), float(p.get("net", 0) or 0)),
        )
        leakiest = max(
            payout_rows,
            key=lambda p: (float(p.get("fees", 0) or 0), -float(p.get("gross", 0) or 0)),
        )
    else:
        latest_payout = {"payout_id": "PO-000", "channel": "none", "gross": 0.0, "fees": 0.0, "net": 0.0, "arrival_day": 0, "citation": "[none:payouts#0]"}
        leakiest = dict(latest_payout)

    bill_amt = round(float(biggest_bill.get("amount", 0) or 0), 2)
    bill_due = int(biggest_bill.get("due_day", 0) or 0)
    # Which payout funds the biggest bill? Look it up in the schedule.
    fund = next(
        (s for s in schedule if s.get("payable") == biggest_bill.get("name", "")),
        None,
    )
    fund_ref = fund["pay_from"] if fund else "cash_on_hand"
    do_hold = (
        f"Hold/delay {biggest_bill.get('name', '')} ${bill_amt:,.2f} due day {bill_due} — "
        f"pay from {fund_ref} {biggest_bill.get('citation', '')} to protect tight day {tight_day}"
    )
    lp_net = round(float(latest_payout.get("net", 0) or 0), 2)
    lp_gross = round(float(latest_payout.get("gross", 0) or 0), 2)
    lp_arr = int(latest_payout.get("arrival_day", 0) or 0)
    do_chase = (
        f"Chase {latest_payout.get('payout_id', '')} ${lp_net:,.2f} net "
        f"({latest_payout.get('channel', '')} gross ${lp_gross:,.2f}) arriving day {lp_arr} "
        f"{latest_payout.get('citation', '')} — ping provider before bills hit"
    )
    lk_fees = round(float(leakiest.get("fees", 0) or 0), 2)
    lk_gross = round(float(leakiest.get("gross", 0) or 0), 2)
    lk_pct = (lk_fees / lk_gross * 100.0) if lk_gross else 0.0
    do_fee = (
        f"Fix fee leak: {leakiest.get('payout_id', '')} fees ${lk_fees:,.2f} on "
        f"${lk_gross:,.2f} gross ({lk_pct:.1f}%) {leakiest.get('citation', '')} — "
        f"route next drop via lower-fee channel"
    )
    do_today = [do_hold, do_chase, do_fee][:DO_TODAY_N]

    headline = (
        f"CASHFLOW CLOSE: ${arriving_7d:,.2f} net arriving 7d · "
        f"cash after bills ${cash_after:,.2f} · runway {runway_days:.1f}d"
    )

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day,
        "seed": seed,
        "cash_on_hand": cash,
        "headline": headline,
        "kpis": {
            "gross_total": gross_total,
            "fee_total": fee_total,
            "net_total": net_total,
            "arriving_7d": arriving_7d,
            "payables_total": payables_total,
            "cash_on_hand": cash,
            "cash_after_payables": cash_after,
            "daily_burn": DAILY_BURN,
            "runway_days": runway_days,
            "tight_day": tight_day,
            "payouts_n": len(payout_rows),
            "payables_n": len(payable_rows),
        },
        "payouts": payout_rows,
        "payables": payable_rows,
        "daily_cash": balances,
        "pay_schedule": schedule,
        "do_today": do_today,
        "citations": CITATIONS_NOTE,
        "free": True,
        "offline": True,
    }


# ---------------------------------------------------------------------------
# Exporters — CSV/TXT shapes mirror the flagship packs for tooling reuse
# ---------------------------------------------------------------------------

def payouts_to_csv(close: dict[str, Any]) -> str:
    """Render payouts-only sheet (one row per payout, arrival-day order)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["payout_id", "channel", "gross_usd", "fees_usd", "net_usd", "arrival_day", "citation"])
    rows = sorted(
        list(close.get("payouts", []) or []),
        key=lambda p: (int(p.get("arrival_day", 0) or 0), str(p.get("payout_id", ""))),
    )
    for p in rows:
        w.writerow([
            p.get("payout_id", ""),
            p.get("channel", ""),
            p.get("gross", ""),
            p.get("fees", ""),
            p.get("net", ""),
            p.get("arrival_day", ""),
            p.get("citation", ""),
        ])
    return buf.getvalue()


def close_to_csv(close: dict[str, Any]) -> str:
    """Render payouts + payables rows in one sheet (money in, then money out)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["kind", "ref", "channel_or_payee", "gross_usd", "fees_usd", "net_usd", "day", "citation"])
    rows = sorted(
        list(close.get("payouts", []) or []),
        key=lambda p: (int(p.get("arrival_day", 0) or 0), str(p.get("payout_id", ""))),
    )
    for p in rows:
        w.writerow([
            "payout",
            p.get("payout_id", ""),
            p.get("channel", ""),
            p.get("gross", ""),
            p.get("fees", ""),
            p.get("net", ""),
            p.get("arrival_day", ""),
            p.get("citation", ""),
        ])
    bills = sorted(
        list(close.get("payables", []) or []),
        key=lambda b: (int(b.get("due_day", 0) or 0), str(b.get("payable_id", ""))),
    )
    for b in bills:
        amt = round(float(b.get("amount", 0) or 0), 2)
        w.writerow([
            "payable",
            b.get("payable_id", ""),
            b.get("name", ""),
            f"{amt:.2f}",
            "0.00",
            f"{-amt:.2f}",
            b.get("due_day", ""),
            b.get("citation", ""),
        ])
    return buf.getvalue()


def actions_to_txt(close: dict[str, Any]) -> str:
    """Render the Friday actions sheet (headline + 3 moves + pay schedule)."""
    k = close.get("kpis", {}) or {}
    out = [
        f"CASHFLOW CLOSE {close.get('date', '')} — MONEY-IN-HAND SHEET",
        f"{close.get('headline', '')}",
        "=" * 72,
        "",
        f"Cash on hand ${k.get('cash_on_hand', 0):,.2f} · "
        f"net arriving 7d ${k.get('arriving_7d', 0):,.2f} · "
        f"bills ${k.get('payables_total', 0):,.2f} · "
        f"cash after ${k.get('cash_after_payables', 0):,.2f} · "
        f"runway {k.get('runway_days', 0)}d (burn ${k.get('daily_burn', 0):,.2f}/d) · "
        f"tight day {k.get('tight_day', 0)}",
        "",
        "DO TODAY (in this order):",
    ]
    for i, t in enumerate(close.get("do_today", []), 1):
        out.append(f"  [{i}] {t}")
    out += ["", "-" * 72, "PAY SCHEDULE (bill -> payout):", "-" * 72, ""]
    sched = close.get("pay_schedule", []) or []
    if not sched:
        out.append("(no payables — bank the payouts)")
        out.append("")
    for s in sched:
        flag = "covered" if s.get("covered") else "HOLD/DELAY"
        out.append(
            f"  - {s.get('payable', '')} ${float(s.get('amount', 0)):,.2f} due day {s.get('due_day', '')} "
            f"-> {s.get('pay_from', '')} (day {s.get('arrival_day', '')}) [{flag}] {s.get('citation', '')}"
        )
        out.append(f"    {s.get('note', '')}")
    out += ["", "-" * 72, "DAILY CASH (day: balance):", "-" * 72, ""]
    for d, bal in enumerate(close.get("daily_cash", []) or []):
        out.append(f"  day +{d}: ${float(bal):,.2f}")
    out += ["", str(close.get("citations", "")), "free: true · offline: true"]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Bundle writer: 4 files
# ---------------------------------------------------------------------------

def write_close_bundle(close: dict[str, Any], outdir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + payouts.csv + actions.txt. Returns paths."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(json.dumps(close, indent=2, default=str))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close))
    paths["payouts.csv"] = str(out / "payouts.csv")
    (out / "payouts.csv").write_text(payouts_to_csv(close))
    paths["actions.txt"] = str(out / "actions.txt")
    (out / "actions.txt").write_text(actions_to_txt(close))
    return paths
