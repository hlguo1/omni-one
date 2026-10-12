"""Cash-Flow Close golden tests — the Friday ritual must never regress.

Golden demo: seed=42, cash_on_hand=1200.0 (measured 2026-10-11):
  gross_total=5112.01, fee_total=163.32, net_total=4948.69,
  arriving_7d=4948.69, payables_total=1870.00, cash_after=4278.69,
  runway_days=50.3, tight_day=0,
  headline="CASHFLOW CLOSE: $4,948.69 net arriving 7d · "
           "cash after bills $4,278.69 · runway 50.3d"

Covers: golden KPIs/headline, payout/payable schemas, net/gross-fees
identity, cash-after + runway formulas, tight-day math, determinism
modulo date, 4-file bundle, CSV parse + headers, actions sheet, pay
schedule, and custom/empty inputs.
"""
import csv
import io
import json
import tempfile
from pathlib import Path

GOLDEN_HEADLINE = (
    "CASHFLOW CLOSE: $4,948.69 net arriving 7d · "
    "cash after bills $4,278.69 · runway 50.3d"
)
GOLDEN_KPIS = {
    "gross_total": 5112.01,
    "fee_total": 163.32,
    "net_total": 4948.69,
    "arriving_7d": 4948.69,
    "payables_total": 1870.0,
    "cash_on_hand": 1200.0,
    "cash_after_payables": 4278.69,
    "daily_burn": 85.0,
    "runway_days": 50.3,
    "tight_day": 0,
    "payouts_n": 10,
    "payables_n": 3,
}


def _close(**kw):
    from omni_one.packs.cashflow_close import build_cashflow_close
    kw.setdefault("seed", 42)
    return build_cashflow_close(**kw)


# ---------------------------------------------------------------------------
# 1. Golden: seed=42 never drifts
# ---------------------------------------------------------------------------

def test_cashflow_close_golden_seed42():
    c = _close(date_str="2026-10-11")
    assert c["headline"] == GOLDEN_HEADLINE, c["headline"]
    for k, v in GOLDEN_KPIS.items():
        assert c["kpis"][k] == v, (k, c["kpis"][k], v)
    assert c["seed"] == 42
    assert c["free"] is True
    assert c["offline"] is True
    assert len(c["payouts"]) == 10
    assert len(c["payables"]) == 3
    assert len(c["do_today"]) == 3
    assert len(c["pay_schedule"]) == 3
    assert "payouts" in c["citations"] and "payables" in c["citations"]
    # Spot-check first demo payout rows are stable.
    assert c["payouts"][0]["payout_id"] == "PO-001"
    assert c["payouts"][0]["channel"] == "paypal"
    assert c["payouts"][0]["gross"] == 311.33
    assert c["payouts"][5]["payout_id"] == "PO-006"
    assert c["payouts"][5]["net"] == 684.6


def test_cashflow_demo_payouts_schema_and_citations():
    c = _close(date_str="2026-10-11")
    for i, p in enumerate(c["payouts"], 1):
        assert p["channel"] in ("shopify", "stripe", "paypal"), p
        assert p["gross"] > 0 and p["fees"] >= 0 and p["net"] > 0
        assert 0 <= int(p["arrival_day"]) <= 5, p
        assert p["citation"] == f"[{p['channel']}:payouts#{i}]", p
        assert p["payout_id"] == f"PO-{i:03d}", p
        # Per-row identity holds to the cent.
        assert round(p["gross"] - p["fees"], 2) == p["net"], p


def test_cashflow_demo_payables_fixed():
    from omni_one.packs.cashflow_close import DEMO_PAYABLES
    assert len(DEMO_PAYABLES) == 3
    by_name = {b["name"]: b for b in DEMO_PAYABLES}
    assert by_name["supplier restock"]["amount"] == 650.00
    assert by_name["rent"]["amount"] == 900.00
    assert by_name["shipping"]["amount"] == 320.00
    assert by_name["supplier restock"]["due_day"] == 2
    assert by_name["rent"]["due_day"] == 5
    assert by_name["shipping"]["due_day"] == 1
    assert sum(b["amount"] for b in DEMO_PAYABLES) == 1870.00


# ---------------------------------------------------------------------------
# 2. Money identities (formulas, not magic numbers)
# ---------------------------------------------------------------------------

def test_net_total_equals_gross_minus_fees():
    c = _close(date_str="2026-10-11")
    assert c["kpis"]["net_total"] == round(c["kpis"]["gross_total"] - c["kpis"]["fee_total"], 2)
    assert c["kpis"]["net_total"] == 4948.69
    # Holds on other seeds and custom books too.
    from omni_one.packs.cashflow_close import build_cashflow_close
    for seed in (1, 7, 99):
        cx = build_cashflow_close(seed=seed, date_str="2026-10-11")
        assert cx["kpis"]["net_total"] == round(cx["kpis"]["gross_total"] - cx["kpis"]["fee_total"], 2), seed


def test_cash_after_equals_hand_plus_arriving_minus_bills():
    c = _close(date_str="2026-10-11")
    k = c["kpis"]
    assert k["cash_after_payables"] == round(k["cash_on_hand"] + k["arriving_7d"] - k["payables_total"], 2)
    assert k["cash_after_payables"] == 4278.69
    from omni_one.packs.cashflow_close import build_cashflow_close
    cx = build_cashflow_close(seed=7, cash_on_hand=500.0, date_str="2026-10-11")
    kx = cx["kpis"]
    assert kx["cash_after_payables"] == round(500.0 + kx["arriving_7d"] - kx["payables_total"], 2)


def test_runway_math_daily_burn_85():
    c = _close(date_str="2026-10-11")
    k = c["kpis"]
    assert k["daily_burn"] == 85.0
    assert k["runway_days"] == round(k["cash_after_payables"] / 85.0, 1)
    assert k["runway_days"] == 50.3


def test_tight_day_is_min_cash_day():
    c = _close(date_str="2026-10-11")
    balances = c["daily_cash"]
    assert len(balances) == 8  # day 0..7
    assert c["kpis"]["tight_day"] == 0
    assert balances[0] == min(balances)
    # Recompute independently: cash + arrived(<=d) - due(<=d).
    cash = c["kpis"]["cash_on_hand"]
    for d in range(8):
        arrived = sum(p["net"] for p in c["payouts"] if p["arrival_day"] <= d)
        due = sum(b["amount"] for b in c["payables"] if b["due_day"] <= d)
        assert balances[d] == round(cash + arrived - due, 2), d


# ---------------------------------------------------------------------------
# 3. Determinism modulo date
# ---------------------------------------------------------------------------

def test_cashflow_close_deterministic_modulo_date():
    from omni_one.packs.cashflow_close import build_cashflow_close
    a = build_cashflow_close(seed=42, date_str="2026-10-11")
    b = build_cashflow_close(seed=42, date_str="2026-10-11")
    assert a == b
    c = build_cashflow_close(seed=42, date_str="2026-10-12")
    assert c["date"] == "2026-10-12"
    for key in ("headline", "kpis", "payouts", "payables", "pay_schedule", "do_today"):
        assert c[key] == a[key], key
    other = build_cashflow_close(seed=7, date_str="2026-10-11")
    assert other["headline"] != a["headline"] or other["payouts"] != a["payouts"]


def test_demo_payouts_seeded_generator():
    from omni_one.packs.cashflow_close import DEMO_PAYOUTS
    first = DEMO_PAYOUTS(seed=42)
    again = DEMO_PAYOUTS(seed=42)
    assert first == again
    assert len(first) == 10
    other = DEMO_PAYOUTS(seed=7)
    assert other != first


# ---------------------------------------------------------------------------
# 4. do_today + pay schedule
# ---------------------------------------------------------------------------

def test_do_today_three_money_moves_with_dollars():
    c = _close(date_str="2026-10-11")
    assert len(c["do_today"]) == 3
    for t in c["do_today"]:
        assert "$" in t, t
    # Hold/delay names the biggest bill, chase names a payout, fee fix names fees.
    assert "rent" in c["do_today"][0] and "$900.00" in c["do_today"][0]
    assert "Chase" in c["do_today"][1] and "arriving day" in c["do_today"][1]
    assert "fee" in c["do_today"][2].lower() and "gross" in c["do_today"][2].lower()


def test_pay_schedule_covers_each_payable():
    c = _close(date_str="2026-10-11")
    sched = c["pay_schedule"]
    assert len(sched) == 3
    names = {s["payable"] for s in sched}
    assert names == {"supplier restock", "rent", "shipping"}
    for s in sched:
        assert s["pay_from"] and s["citation"] and s["note"], s
        assert "ledger:payables" in s["citation"] and "payouts#" in s["citation"]
    # Due-day order: shipping(1) < supplier(2) < rent(5).
    assert [s["payable"] for s in sched] == ["shipping", "supplier restock", "rent"]


# ---------------------------------------------------------------------------
# 5. Bundle: exactly 4 files; CSVs parse; actions sheet grounded
# ---------------------------------------------------------------------------

def test_cashflow_bundle_writes_four_files():
    from omni_one.packs.cashflow_close import build_cashflow_close, write_close_bundle
    c = build_cashflow_close(seed=42, date_str="2026-10-11")
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert set(paths.keys()) == {"close.json", "close.csv", "payouts.csv", "actions.txt"}, paths
        assert len(paths) == 4
        for key, p in paths.items():
            assert Path(p).is_file(), (key, p)
            assert Path(p).stat().st_size > 0, (key, p)
        loaded = json.loads(Path(paths["close.json"]).read_text())
        assert loaded["headline"] == GOLDEN_HEADLINE
        assert loaded["kpis"] == c["kpis"]
        before = {k: Path(v).read_text() for k, v in paths.items()}
        paths2 = write_close_bundle(c, tmp)
        assert set(paths2.keys()) == set(paths.keys())
        for k, v in paths2.items():
            assert Path(v).read_text() == before[k]


def test_cashflow_csvs_parse_with_exact_headers():
    from omni_one.packs.cashflow_close import (
        build_cashflow_close, close_to_csv, payouts_to_csv, write_close_bundle,
    )
    c = build_cashflow_close(seed=42, date_str="2026-10-11")
    combo = list(csv.DictReader(io.StringIO(close_to_csv(c))))
    assert len(combo) == 13  # 10 payouts + 3 payables
    reader = csv.reader(io.StringIO(close_to_csv(c)))
    assert next(reader) == ["kind", "ref", "channel_or_payee", "gross_usd", "fees_usd", "net_usd", "day", "citation"]
    kinds = [r["kind"] for r in combo]
    assert kinds.count("payout") == 10 and kinds.count("payable") == 3
    prows = list(csv.DictReader(io.StringIO(payouts_to_csv(c))))
    assert len(prows) == 10
    reader2 = csv.reader(io.StringIO(payouts_to_csv(c)))
    assert next(reader2) == ["payout_id", "channel", "gross_usd", "fees_usd", "net_usd", "arrival_day", "citation"]
    assert prows[0]["payout_id"].startswith("PO-")
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert Path(paths["close.csv"]).read_text() == close_to_csv(c)
        assert Path(paths["payouts.csv"]).read_text() == payouts_to_csv(c)


def test_cashflow_actions_txt_has_moves_and_schedule():
    from omni_one.packs.cashflow_close import build_cashflow_close, actions_to_txt, write_close_bundle
    c = build_cashflow_close(seed=42, date_str="2026-10-11")
    txt = actions_to_txt(c)
    assert "CASHFLOW CLOSE" in txt
    assert c["headline"] in txt
    assert "DO TODAY" in txt
    for i, task in enumerate(c["do_today"], 1):
        assert f"[{i}]" in txt and task[:30] in txt
    assert "PAY SCHEDULE" in txt
    assert "DAILY CASH" in txt
    assert "rent" in txt and "payouts#" in txt
    with tempfile.TemporaryDirectory() as tmp:
        paths = write_close_bundle(c, tmp)
        assert Path(paths["actions.txt"]).read_text() == txt


# ---------------------------------------------------------------------------
# 6. Custom + edge inputs
# ---------------------------------------------------------------------------

def test_custom_payouts_and_payables():
    from omni_one.packs.cashflow_close import build_cashflow_close
    payouts = [
        {"payout_id": "PO-001", "channel": "stripe", "gross": 1000.0, "fees": 29.30, "net": 970.70,
         "arrival_day": 1, "citation": "[stripe:payouts#1]"},
        {"payout_id": "PO-002", "channel": "paypal", "gross": 500.0, "fees": 17.75, "net": 482.25,
         "arrival_day": 9, "citation": "[paypal:payouts#2]"},
    ]
    payables = [
        {"payable_id": "BILL-9", "name": "test bill", "amount": 400.0, "due_day": 3,
         "citation": "[ledger:payables#9]"},
    ]
    c = build_cashflow_close(payouts=payouts, payables=payables, cash_on_hand=100.0, date_str="2026-10-11")
    assert c["kpis"]["gross_total"] == 1500.00
    assert c["kpis"]["net_total"] == round(1500.00 - 47.05, 2)
    # arriving_7d excludes the day-9 payout.
    assert c["kpis"]["arriving_7d"] == 970.70
    assert c["kpis"]["cash_after_payables"] == round(100.0 + 970.70 - 400.0, 2)
    assert c["free"] is True


def test_empty_payouts_still_closes():
    from omni_one.packs.cashflow_close import build_cashflow_close, close_to_csv, actions_to_txt
    c = build_cashflow_close(payouts=[], payables=[], cash_on_hand=1200.0, date_str="2026-10-11")
    assert c["kpis"]["net_total"] == 0.0
    assert c["kpis"]["arriving_7d"] == 0.0
    assert c["kpis"]["cash_after_payables"] == 1200.00
    assert c["kpis"]["runway_days"] == round(1200.0 / 85.0, 1)
    assert len(c["do_today"]) == 3
    assert isinstance(close_to_csv(c), str)
    assert "CASHFLOW CLOSE" in actions_to_txt(c)
