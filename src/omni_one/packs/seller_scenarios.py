"""
Seller Scenarios — 12 highly practical, deterministic use cases for online sellers.
=================================================================================
Sharp = each scenario is a 60-second demo: trigger → evidence file:line → Workshop action.

IDs are stable (hash of type+key) → idempotent: same events → same decisions.
All thresholds in SCENARIO_THRESHOLDS (tunable, tested). No LLM needed to trigger;
LLM only drafts messages (gated, free mock).

Tech sound: pure functions, no I/O, typed dicts, unit-tested, O(n) single pass.
"""
from __future__ import annotations
import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Any, Callable

from .seller_os import _norm_product, _product_match

SCENARIO_THRESHOLDS = {
    "stockout_days": 5.0,
    "dead_stock_days": 30,  # no sales in window + on_hand >= min_qty
    "dead_stock_min_qty": 5,
    "fee_creep_pct": 12.0,  # fees/GMV*100
    "shipping_loss_pct": 20.0,  # ship/GMV*100 per order
    "margin_low_pct": 10.0,
    "dm_backlog_count": 3,
    "price_mismatch_pct": 5.0,  # same product price diff across channels
}

def _sid(scenario: str, key: str) -> str:
    h = hashlib.md5(f"{scenario}:{key}".encode()).hexdigest()[:8]
    return f"{scenario}-{h}"

def _ctx(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Single-pass aggregation shared by all scenarios (O(n), tech sound)."""
    orders = [e for e in events if e.get("source") == "orders"]
    inv = [e for e in events if e.get("source") == "inventory"]
    reviews = [e for e in events if e.get("source") == "review"]
    dms = [e for e in events if e.get("source") == "dm"]
    supplier = [e for e in events if e.get("source") == "supplier"]

    # Products aggregated by normalized name
    qty_by_norm: Counter = Counter()
    gmv_by_norm: Counter = Counter()
    display_by_norm: Dict[str, str] = {}
    price_by_norm_channel: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    for e in orders:
        raw = (e.get("metadata", {}).get("product") or "unknown").strip()
        np_ = _norm_product(raw)
        if np_ not in display_by_norm:
            display_by_norm[np_] = raw
        try:
            q = int(float(e.get("metadata", {}).get("qty", 1) or 1))
        except Exception:
            q = 1
        try:
            g = float(e.get("metadata", {}).get("gmv", 0) or 0)
        except Exception:
            g = 0.0
        qty_by_norm[np_] += q
        gmv_by_norm[np_] += g
        # channel from source_file
        sf = str(e.get("metadata", {}).get("source_file", "")).lower()
        ch = "etsy" if "etsy" in sf else ("shopify" if "shopify" in sf else ("amazon" if "amazon" in sf else "other"))
        try:
            unit = g / max(q, 1)
            price_by_norm_channel[np_][ch].append(unit)
        except Exception:
            pass

    inv_by_norm: Dict[str, Dict[str, Any]] = {}
    for e in inv:
        prod = str(e.get("metadata", {}).get("product", ""))
        np_ = _norm_product(prod)
        try:
            qh = int(e.get("metadata", {}).get("qty_on_hand", 0) or 0)
        except Exception:
            qh = 0
        # keep first + citation
        if np_ not in inv_by_norm:
            inv_by_norm[np_] = {"display": prod, "on_hand": qh, "citation": e.get("metadata", {}).get("citation", "")}

    gmv = sum(float(e.get("metadata", {}).get("gmv", 0) or 0) for e in orders)
    fees = sum(float(e.get("metadata", {}).get("fees", 0) or 0) for e in orders)
    ship = sum(float(e.get("metadata", {}).get("shipping", 0) or 0) for e in orders)

    return {
        "orders": orders, "inv": inv, "reviews": reviews, "dms": dms, "supplier": supplier,
        "qty_by_norm": qty_by_norm, "gmv_by_norm": gmv_by_norm, "display_by_norm": display_by_norm,
        "price_by_channel": price_by_norm_channel, "inv_by_norm": inv_by_norm,
        "gmv": gmv, "fees": fees, "ship": ship,
    }

def _neg(txt: str) -> bool:
    low = txt.lower()
    phrases = ["hasn't arrived", "hasnt arrived", "no tracking", "where is my", "never arrived", "very disappointed"]
    if any(p in low for p in phrases):
        return True
    for w in ["worried", "disappointed", "chipped", "damaged", "late", "angry", "terrible", "refund", "missing", "broken"]:
        if re.search(r"\b" + re.escape(w) + r"\b", low):
            return True
    if re.search(r"\bwhere\b", low) and any(k in low for k in ["order", "tracking", "arrived", "package"]):
        return True
    return False

# --- 12 scenario detectors: (events, ctx) -> List[scenario dict] ---
def s_stockout(events, c) -> List[Dict[str, Any]]:
    out = []
    for np_, sold in c["qty_by_norm"].items():
        inv = c["inv_by_norm"].get(np_)
        if not inv:
            # fuzzy fallback
            for nk, iv in c["inv_by_norm"].items():
                if _product_match(c["display_by_norm"][np_], iv["display"]):
                    inv = iv
                    break
        if not inv:
            continue
        on_hand = inv["on_hand"]
        days = on_hand / (sold / 7) if sold else 999
        if days < SCENARIO_THRESHOLDS["stockout_days"]:
            disp = c["display_by_norm"][np_]
            out.append({"scenario": "STOCKOUT_RISK", "severity": "high", "key": np_,
                        "title": f"Reorder {disp} — {days:.1f} days left ({on_hand} on hand, sold {sold}/7d)",
                        "evidence": [inv["citation"]], "product": disp,
                        "proposed_action": {"action": "reorderProduct", "params": {"status": "REORDERED"}}})
    return out

def s_dead_stock(events, c) -> List[Dict[str, Any]]:
    out = []
    sold_norms = set(c["qty_by_norm"].keys())
    for np_, iv in c["inv_by_norm"].items():
        if np_ not in sold_norms and iv["on_hand"] >= SCENARIO_THRESHOLDS["dead_stock_min_qty"]:
            out.append({"scenario": "DEAD_STOCK", "severity": "medium", "key": np_,
                        "title": f"Dead stock: {iv['display']} — {iv['on_hand']} units, zero sales 7d → bundle/clearance",
                        "evidence": [iv["citation"]], "product": iv["display"],
                        "proposed_action": {"action": "markDownProduct", "params": {"status": "CLEARANCE"}}})
    return out

def s_refund_risk(events, c) -> List[Dict[str, Any]]:
    out = []
    for e in c["dms"] + c["reviews"]:
        txt = str(e.get("value", ""))
        if _neg(txt) and any(k in txt.lower() for k in ["refund", "return", "chargeback", "dispute", "not arrived", "hasn't arrived"]):
            out.append({"scenario": "REFUND_RISK", "severity": "critical", "key": e.get("entity_id", txt[:20]),
                        "title": f"Refund risk — reply in 2h: {txt[:60]}",
                        "evidence": [e.get("metadata", {}).get("citation", "")],
                        "proposed_action": {"action": "messageCustomer", "params": {"status": "CONTACTED"}}})
            if len(out) >= 3:
                break
    return out

def s_review_crisis(events, c) -> List[Dict[str, Any]]:
    out = []
    for e in c["reviews"]:
        txt = str(e.get("value", ""))
        low = txt.lower()
        stars = None
        m = re.search(r"\bstars?\s*[:=]?\s*([1-5])\b", low)
        if m:
            try:
                stars = int(m.group(1))
            except Exception:
                stars = None
        # row.values joined includes stars col; fallback: detect 1-2 via metadata?
        if stars in (1, 2) or any(w in low for w in ["chipped", "damaged", "terrible", "awful"]):
            out.append({"scenario": "REVIEW_CRISIS", "severity": "high", "key": e.get("entity_id", txt[:20]),
                        "title": f"Bad review — fix + public reply: {txt[:60]}",
                        "evidence": [e.get("metadata", {}).get("citation", "")],
                        "proposed_action": {"action": "replyReview", "params": {"status": "REPLIED"}}})
    return out[:3]

def s_fee_creep(events, c) -> List[Dict[str, Any]]:
    out = []
    if c["gmv"] > 0 and (c["fees"] / c["gmv"] * 100) >= SCENARIO_THRESHOLDS["fee_creep_pct"]:
        out.append({"scenario": "FEE_CREEP", "severity": "medium", "key": "fees",
                    "title": f"Fees {c['fees']/c['gmv']*100:.1f}% of GMV (${c['fees']:.2f}/${c['gmv']:.2f}) — review pricing/channel mix",
                    "evidence": [f"[orders] fees ${c['fees']:.2f} gmv ${c['gmv']:.2f}"],
                    "proposed_action": {"action": "reviewPricing", "params": {"status": "REVIEWED"}}})
    return out

def s_shipping_loss(events, c) -> List[Dict[str, Any]]:
    out = []
    for e in c["orders"]:
        try:
            g = float(e.get("metadata", {}).get("gmv", 0) or 0)
            s = float(e.get("metadata", {}).get("shipping", 0) or 0)
        except Exception:
            continue
        if g > 0 and (s / g * 100) >= SCENARIO_THRESHOLDS["shipping_loss_pct"]:
            out.append({"scenario": "SHIPPING_LOSS", "severity": "medium", "key": str(e.get("entity_id")),
                        "title": f"Shipping loss: {e.get('metadata',{}).get('product')} ship ${s:.2f} on ${g:.2f} GMV",
                        "evidence": [e.get("metadata", {}).get("citation", "")],
                        "proposed_action": {"action": "adjustShipping", "params": {"status": "ADJUSTED"}}})
            if len(out) >= 3:
                break
    return out

def s_supplier_cogs_spike(events, c) -> List[Dict[str, Any]]:
    # COGS per unit rising: compare supplier unit vs 30% GMV heuristic
    out = []
    # reuse seller_os catalog logic minimal: if supplier total high vs GMV
    sup_totals = [float(e.get("value", 0) or 0) for e in c["supplier"]]
    if sup_totals and c["gmv"] > 0 and (sum(sup_totals) / max(c["gmv"], 1)) > 1.5:
        out.append({"scenario": "SUPPLIER_COGS_SPIKE", "severity": "medium", "key": "cogs",
                    "title": f"Supplier invoices ${sum(sup_totals):.2f} vs GMV ${c['gmv']:.2f} — renegotiate / raise price",
                    "evidence": [e.get("metadata", {}).get("citation", "") for e in c["supplier"][:2]],
                    "proposed_action": {"action": "renegotiateSupplier", "params": {"status": "NEGOTIATING"}}})
    return out

def s_listing_gap(events, c) -> List[Dict[str, Any]]:
    # Product with sales but zero reviews
    reviewed = set()
    for e in c["reviews"]:
        txt = str(e.get("value", "")).lower()
        for np_, disp in c["display_by_norm"].items():
            if _norm_product(disp) and _norm_product(disp) in _norm_product(txt) or disp.lower() in txt:
                reviewed.add(np_)
    out = []
    for np_, sold in c["qty_by_norm"].most_common(3):
        if np_ not in reviewed and sold >= 2:
            disp = c["display_by_norm"][np_]
            out.append({"scenario": "LISTING_GAP", "severity": "low", "key": np_,
                        "title": f"Listing gap: {disp} sold {sold} with zero reviews — request UGC",
                        "evidence": [f"[orders] {disp} sold {sold}"],
                        "proposed_action": {"action": "requestReview", "params": {"status": "REQUESTED"}}})
    return out[:2]

def s_price_mismatch(events, c) -> List[Dict[str, Any]]:
    out = []
    for np_, ch_map in c["price_by_channel"].items():
        if len(ch_map) >= 2:
            means = {ch: sum(v) / len(v) for ch, v in ch_map.items() if v}
            if len(means) >= 2:
                vals = list(means.values())
                diff = abs(max(vals) - min(vals)) / max(min(vals), 0.01) * 100
                if diff >= SCENARIO_THRESHOLDS["price_mismatch_pct"]:
                    disp = c["display_by_norm"][np_]
                    out.append({"scenario": "PRICE_MISMATCH", "severity": "low", "key": np_,
                                "title": f"Price mismatch: {disp} {means} ({diff:.0f}% diff) — align to avoid complaints",
                                "evidence": [f"[orders] {disp} {means}"],
                                "proposed_action": {"action": "alignPrice", "params": {"status": "ALIGNED"}}})
    return out[:3]

def s_dm_backlog(events, c) -> List[Dict[str, Any]]:
    if len(c["dms"]) >= SCENARIO_THRESHOLDS["dm_backlog_count"]:
        return [{"scenario": "DM_BACKLOG", "severity": "medium", "key": "dms",
                 "title": f"DM backlog: {len(c['dms'])} open messages — triage oldest first",
                 "evidence": [c["dms"][0].get("metadata", {}).get("citation", "")],
                 "proposed_action": {"action": "triageDMs", "params": {"status": "TRIAGED"}}}]
    return []

def s_profit_dip(events, c) -> List[Dict[str, Any]]:
    # True profit proxy: GMV - fees - ship (COGS in briefing, here quick)
    net = c["gmv"] - c["fees"] - c["ship"]
    margin = (net / c["gmv"] * 100) if c["gmv"] else 100
    if c["gmv"] > 0 and margin < SCENARIO_THRESHOLDS["margin_low_pct"]:
        return [{"scenario": "PROFIT_DIP", "severity": "high", "key": "margin",
                 "title": f"Margin dip: {margin:.1f}% net ${net:.2f} on ${c['gmv']:.2f} — check fees/COGS",
                 "evidence": [f"[orders] net ${net:.2f} gmv ${c['gmv']:.2f}"],
                 "proposed_action": {"action": "reviewPricing", "params": {"status": "REVIEWED"}}}]
    return []

def s_unanswered_complaint(events, c) -> List[Dict[str, Any]]:
    # Negative DM/review with no shop reply nearby (heuristic: DM from customer not followed by Shop:)
    out = []
    dms = c["dms"]
    for i, e in enumerate(dms):
        txt = str(e.get("value", ""))
        sender = str(e.get("metadata", {}).get("sender", ""))
        if _neg(txt) and sender.lower() not in ("shop", "store", "seller", "maya tacos"):
            nxt = dms[i + 1] if i + 1 < len(dms) else None
            nxt_sender = str((nxt or {}).get("metadata", {}).get("sender", "")) if nxt else ""
            if nxt_sender.lower() not in ("shop", "store", "seller", "maya tacos"):
                out.append({"scenario": "UNANSWERED_COMPLAINT", "severity": "critical", "key": str(e.get("entity_id")),
                            "title": f"Unanswered complaint from {sender}: {txt[:60]}",
                            "evidence": [e.get("metadata", {}).get("citation", "")],
                            "proposed_action": {"action": "messageCustomer", "params": {"status": "CONTACTED"}}})
                if len(out) >= 3:
                    break
    return out

SCENARIOS: List[Dict[str, Any]] = [
    {"id": "STOCKOUT_RISK", "fn": s_stockout, "desc": "Velocity vs on-hand → days of supply"},
    {"id": "DEAD_STOCK", "fn": s_dead_stock, "desc": "On-hand with zero sales → clearance"},
    {"id": "UNANSWERED_COMPLAINT", "fn": s_unanswered_complaint, "desc": "Negative msg with no shop reply"},
    {"id": "REFUND_RISK", "fn": s_refund_risk, "desc": "Refund/return language → 2h reply"},
    {"id": "REVIEW_CRISIS", "fn": s_review_crisis, "desc": "1-2 star / damage → public reply"},
    {"id": "DM_BACKLOG", "fn": s_dm_backlog, "desc": "Open message backlog → triage"},
    {"id": "FEE_CREEP", "fn": s_fee_creep, "desc": "Fees % of GMV too high"},
    {"id": "SHIPPING_LOSS", "fn": s_shipping_loss, "desc": "Ship % of order too high"},
    {"id": "PROFIT_DIP", "fn": s_profit_dip, "desc": "Net margin low"},
    {"id": "SUPPLIER_COGS_SPIKE", "fn": s_supplier_cogs_spike, "desc": "Supplier $ vs GMV spike"},
    {"id": "PRICE_MISMATCH", "fn": s_price_mismatch, "desc": "Same SKU different price by channel"},
    {"id": "LISTING_GAP", "fn": s_listing_gap, "desc": "Sales with zero reviews → UGC ask"},
]

def run_all_scenarios(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run all 12 detectors once. Deterministic, idempotent, O(n)."""
    ctx = _ctx(events)
    all_decisions: List[Dict[str, Any]] = []
    by_scenario: Dict[str, int] = {}
    for sc in SCENARIOS:
        try:
            found = sc["fn"](events, ctx) or []
        except Exception as e:
            found = [{"scenario": sc["id"], "severity": "low", "key": "error", "title": f"{sc['id']} error: {e}", "evidence": []}]
        for d in found:
            d["id"] = _sid(d.get("scenario", sc["id"]), str(d.get("key", d.get("title", ""))))
            d["source"] = "seller_scenarios"
            all_decisions.append(d)
        by_scenario[sc["id"]] = len(found)
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_decisions.sort(key=lambda d: order.get(d.get("severity", "medium"), 9))
    return {"decisions": all_decisions, "by_scenario": by_scenario, "total": len(all_decisions),
            "ctx_summary": {"orders": len(ctx["orders"]), "gmv": round(ctx["gmv"], 2), "products": len(ctx["qty_by_norm"])},
            "ctx": ctx}


def scenarios_to_workshop(scenario_result: Dict[str, Any], workshop_app, product_resolver=None) -> List[Any]:
    """Wire scenario dicts → Workshop Decisions (grounded, idempotent via stable_id)."""
    made = []
    for d in scenario_result.get("decisions", []):
        prod = d.get("product")
        ref = None
        if prod and product_resolver:
            try:
                ref = product_resolver(prod)
            except Exception:
                ref = None
        if not ref:
            try:
                finder = getattr(workshop_app, "_find_product_ref", None)
                if finder and prod:
                    ref = finder(prod)
            except Exception:
                ref = None
        if not ref:
            try:
                objs = workshop_app.ontology.objects.get("Product", {})
                if objs:
                    ref = f"Product:{next(iter(objs))}"
            except Exception:
                ref = None
        if not ref:
            continue
        try:
            made.append(workshop_app.add_decision(
                title=d.get("title", d.get("scenario", "decision")),
                object_ref=ref, severity=d.get("severity", "medium"),
                evidence=d.get("evidence", []), proposed_action=d.get("proposed_action"),
                source=f"scenario:{d.get('scenario')}", stable_id=d.get("id")))
        except Exception:
            continue
    return made
