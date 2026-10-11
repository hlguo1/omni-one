"""Payout reconciliation: match payout rows to order GMVs."""
from __future__ import annotations
from typing import Dict, List, Any

try:
    from ._common import parse_money_abs, norm_header
except Exception:
    from omni_one.connectors._common import parse_money_abs, norm_header  # type: ignore


def _order_id_of(ev: Dict[str, Any]) -> str:
    try:
        md = ev.get("metadata") or {}
        oid = str(md.get("order_id") or "").strip()
        if oid and oid != "line1":
            return oid
        eid = str(ev.get("entity_id") or "")
        # entity_id format order:{channel}:{oid}:{line}
        parts = eid.split(":")
        if len(parts) >= 3:
            # join middle parts (oid may contain -)
            return ":".join(parts[2:-1]) if len(parts) > 3 else parts[2]
        return eid
    except Exception:
        return ""


def _gmv_of(ev: Dict[str, Any]) -> float:
    try:
        if "metadata" in ev and isinstance(ev.get("metadata"), dict):
            md = ev["metadata"]
            for k in ("gmv", "net"):
                if k in md and isinstance(md[k], (int, float)):
                    return float(md[k])
            v = ev.get("value")
            if isinstance(v, (int, float)):
                return float(v)
            return parse_money_abs(str(v or ""))
        # raw payout row
        norm = {norm_header(str(k)): ("" if v is None else str(v)) for k, v in ev.items()}
        for k in ("gmv", "net", "amount", "total", "gross", "price"):
            if k in norm and norm[k].strip():
                val = parse_money_abs(norm[k])
                if val:
                    return val
        # fallback: largest money in row
        best = 0.0
        for v in ev.values():
            m = parse_money_abs(str(v or ""))
            if m > best:
                best = m
        return best
    except Exception:
        return 0.0


def _fees_of(ev: Dict[str, Any]) -> float:
    try:
        if "metadata" in ev and isinstance(ev.get("metadata"), dict):
            f = ev["metadata"].get("fees", 0)
            if isinstance(f, (int, float)):
                return float(f)
            return parse_money_abs(str(f or ""))
        norm = {norm_header(str(k)): ("" if v is None else str(v)) for k, v in ev.items()}
        for k in ("fees", "fee", "commission"):
            if k in norm and norm[k].strip():
                return parse_money_abs(norm[k])
        return 0.0
    except Exception:
        return 0.0


def _payout_id_of(row: Dict[str, Any]) -> str:
    try:
        if "metadata" in row and isinstance(row.get("metadata"), dict):
            return _order_id_of(row)
        norm = {norm_header(str(k)): ("" if v is None else str(v)).strip() for k, v in row.items()}
        for k in ("order_id",):
            if k in norm and norm[k]:
                return norm[k]
        # try keys containing order/id
        for raw, v in row.items():
            low = str(raw).lower()
            if "order" in low and v and str(v).strip():
                return str(v).strip()
            if "transaction" in low and v and str(v).strip():
                return str(v).strip()
            if low.strip() in ("id", "charge id", "invoice id") and v and str(v).strip():
                return str(v).strip()
        return ""
    except Exception:
        return ""


def reconcile(orders: List[Dict[str, Any]], payouts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Match payout rows to order GMVs.

    orders: canonical order events (with metadata gmv/fees/order_id)
    payouts: canonical events OR raw row dicts (with order ref + amount/net/fees)
    Returns {matched, unmatched, fee_delta, ...} deterministically. Never raises.
    """
    try:
        orders = list(orders or [])
        payouts = list(payouts or [])
        # index payouts by order id
        payout_by_id: Dict[str, Dict[str, Any]] = {}
        payout_amounts: List[float] = []
        for p in payouts:
            try:
                pid = _payout_id_of(p) if isinstance(p, dict) else ""
                if pid:
                    payout_by_id[pid] = p
                payout_amounts.append(_gmv_of(p) if isinstance(p, dict) else 0.0)
            except Exception:
                continue
        matched: List[str] = []
        unmatched: List[str] = []
        order_total = 0.0
        order_fees = 0.0
        for o in orders:
            try:
                oid = _order_id_of(o) if isinstance(o, dict) else ""
                gmv = _gmv_of(o) if isinstance(o, dict) else 0.0
                fees = _fees_of(o) if isinstance(o, dict) else 0.0
                order_total += gmv
                order_fees += fees
                hit = False
                if oid and oid in payout_by_id:
                    hit = True
                else:
                    # amount match within 1 cent (abs comparison for refunds)
                    for pa in payout_amounts:
                        try:
                            if abs(abs(gmv) - abs(pa)) < 0.011 and abs(gmv) > 0:
                                hit = True
                                break
                        except Exception:
                            continue
                # fee/shipping adjustments: emit conceptually via fee_delta (no new events needed)
                if hit:
                    matched.append(oid or str(gmv))
                else:
                    unmatched.append(oid or str(gmv))
            except Exception:
                continue
        payout_total = 0.0
        payout_fees = 0.0
        for p in payouts:
            try:
                payout_total += _gmv_of(p) if isinstance(p, dict) else 0.0
                payout_fees += _fees_of(p) if isinstance(p, dict) else 0.0
            except Exception:
                continue
        fee_delta = round(order_fees - payout_fees, 2)
        return {
            "matched": sorted(matched),
            "unmatched": sorted(unmatched),
            "fee_delta": fee_delta,
            "order_total": round(order_total, 2),
            "payout_total": round(payout_total, 2),
            "order_fees": round(order_fees, 2),
            "payout_fees": round(payout_fees, 2),
            "matched_count": len(matched),
            "unmatched_count": len(unmatched),
        }
    except Exception:
        return {"matched": [], "unmatched": [], "fee_delta": 0.0,
                "order_total": 0.0, "payout_total": 0.0,
                "order_fees": 0.0, "payout_fees": 0.0,
                "matched_count": 0, "unmatched_count": 0}
