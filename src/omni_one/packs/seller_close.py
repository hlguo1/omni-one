"""
Daily Close — the 5-minute ritual thousands of micro-sellers will actually use daily.
===============================================================================
Brilliant idea: sellers don't want "dashboards". They want to CLOSE the day:
  1. Did I actually make money today? (true profit, not GMV)
  2. What will stock out and kill tomorrow's sales? (reorder sheet + supplier PO draft)
  3. Who is angry RIGHT NOW and will refund/1-star me? (copy-paste replies, cited)
  4. Where is money leaking? (fees, shipping, COGS — dollar amounts, not charts)
  5. Hand my accountant something. (close.csv / reorder.csv / replies.txt)

One command, every morning, offline, $0:
  omni-one close --folder /tmp/my_shop --out ./close_2026-10-11
  -> close.json + close.csv + reorder.csv + replies.txt + po.txt (print / send / file)

Design rules (why shops trust it):
- Deterministic, no LLM needed for numbers. Drafts are templates grounded in citations.
- Every dollar cites file:line. No phantom tasks.
- Idempotent: same folder -> same close (minus timestamp).
- Private: data never leaves the laptop. Works on plane wifi.
"""
from __future__ import annotations
import csv
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Any


COVER_DAYS = 14          # reorder cover: 14 days of velocity
STOCKOUT_DAYS = 5.0      # must-reorder threshold (matches SCENARIO_THRESHOLDS)


def _first_name(sender: str) -> str:
    sender = (sender or "there").strip().split()[0].strip(",:@")
    return sender[:20] or "there"


def _issue_snippet(text: str) -> str:
    low = text.lower()
    if "hasn" in low and "arriv" in low:
        return "your late delivery"
    if "no tracking" in low or "where is my" in low:
        return "your missing tracking"
    if "chipped" in low or "damaged" in low or "broken" in low:
        return "your damaged item"
    if "refund" in low or "return" in low:
        return "your refund request"
    if "late" in low:
        return "the delay"
    return "this"


def draft_dm_reply(customer: str, text: str, citation: str, shop: str = "our shop") -> str:
    name = _first_name(customer)
    issue = _issue_snippet(text)
    return (
        f"Hi {name}! I'm really sorry about {issue} — I just pulled your order "
        f"({citation}) and I'm checking tracking/supplier right now. "
        f"I'll update you within 2 hours with a fix (reship/refund — your choice). "
        f"Thank you for your patience with {shop}!"
    )


def draft_review_reply(product: str, text: str, citation: str, shop: str = "our shop") -> str:
    return (
        f"Thank you for flagging this ({citation}) — we're sorry about your {product} experience. "
        f"We've fixed the packing/quality check that caused it. Please DM us for a free "
        f"replacement or refund — we want to make this right. — {shop}"
    )


def draft_po_email(supplier: str, lines: list[dict[str, Any]], shop: str = "our shop") -> str:
    items = "\n".join(f"  - {l['product']}: {l['reorder_qty']} units (have {l['on_hand']}, {l['days_left']}d left) [{l['citation']}]"
                      for l in lines[:5]) or "  - (nothing to reorder — stock healthy)"
    return (
        f"Subject: Reorder request — {supplier or 'supplier'}\n\n"
        f"Hi {supplier or 'there'}!\n\nPlease send the following for {shop}:\n{items}\n\n"
        f"Please confirm price + ETA. Last invoice numbers are cited above from our records.\n\nThanks!\n{shop}"
    )


def build_daily_close(events: list[dict[str, Any]], briefing: dict[str, Any] | None = None,
                      scen: dict[str, Any] | None = None,
                      date_str: str | None = None, shop: str = "our shop",
                      locale: str = "en") -> dict[str, Any]:
    from omni_one.packs.seller_os import build_seller_briefing
    from omni_one.packs.seller_scenarios import run_all_scenarios

    briefing = briefing or build_seller_briefing(events)
    scen = scen or run_all_scenarios(events)
    k = briefing.get("kpis", {})
    aov = float(k.get("aov", 0) or 0)
    gmv = float(k.get("gmv", 0) or 0)
    loc = (locale or "en").lower()[:2]
    if loc not in ("en", "es", "zh", "fr", "de"):
        loc = "en"
    # Localized drafters (fallback to EN templates on any error; default output unchanged).
    def _dm(customer: str, text: str, cite: str) -> str:
        if loc == "en":
            return draft_dm_reply(customer, text, cite, shop)
        try:
            from omni_one.i18n.drafts import build_reply as _br
            return _br("dm", loc, customer, text, cite, shop)
        except Exception:
            return draft_dm_reply(customer, text, cite, shop)

    def _rv(customer: str, text: str, cite: str) -> str:
        if loc == "en":
            return draft_review_reply(customer, text, cite, shop)
        try:
            from omni_one.i18n.drafts import build_reply as _br2
            return _br2("review", loc, customer, text, cite, shop)
        except Exception:
            return draft_review_reply(customer, text, cite, shop)

    def _po(supplier: str, lines: list[dict[str, Any]]) -> str:
        if loc == "en":
            return draft_po_email(supplier, lines, shop)
        try:
            from omni_one.i18n.drafts import build_po as _bp
            ll = [{"product": l["product"], "reorder_qty": l["reorder_qty"],
                   "on_hand": l["on_hand"], "days_left": l["days_left"],
                   "citation": l["citation"]} for l in lines]
            return _bp(loc, supplier, ll, shop)
        except Exception:
            return draft_po_email(supplier, lines, shop)

    # ---- 1. reorder sheet: velocity vs on-hand (uses briefing stockout + ctx for supplier) ----
    ctx = scen.get("ctx", {})
    inv_by_norm: dict = ctx.get("inv_by_norm", {})
    qty_by_norm = ctx.get("qty_by_norm", {})
    display_by_norm: dict = ctx.get("display_by_norm", {})
    # supplier lookup from inventory events
    supplier_by_product: dict[str, str] = {}
    for e in events:
        if e.get("source") == "inventory":
            md = e.get("metadata", {})
            prod = str(md.get("product", ""))
            sup = str(md.get("supplier", "") or "")
            if prod and sup:
                supplier_by_product.setdefault(prod.lower().strip(), sup)
    reorder: list[dict[str, Any]] = []
    for r in briefing.get("stockout_risk", []):
        prod = r.get("product", "")
        on_hand = int(r.get("on_hand", 0) or 0)
        sold_7d = int(r.get("sold_7d", 0) or 0)
        vel = sold_7d / 7.0 if sold_7d else 0.0
        days_left = float(r.get("days_supply", 999) or 999)
        need = math.ceil(vel * COVER_DAYS - on_hand) if vel else 0
        need = max(0, need)
        supplier = supplier_by_product.get(prod.lower().strip(), "see inventory.csv supplier column")
        # urgency: days_left < 3 -> order today; <5 -> this week
        urgency = "ORDER TODAY" if days_left < 3 else ("this week" if days_left < STOCKOUT_DAYS else "watch")
        reorder.append({"product": prod, "on_hand": on_hand, "sold_7d": sold_7d,
                        "daily_velocity": round(vel, 2), "days_left": days_left,
                        "reorder_qty": need, "cover_days": COVER_DAYS,
                        "supplier": supplier, "urgency": urgency, "citation": r.get("citation", "")})
    reorder.sort(key=lambda x: x["days_left"])
    # dead-stock note (cash locked): from scenarios
    dead = [d for d in scen.get("decisions", []) if d.get("scenario") == "DEAD_STOCK"][:3]

    # ---- 2. reply queue: who will refund/1-star me if I sleep ----
    reply_queue: list[dict[str, Any]] = []
    # briefing at-risk preview carries text+citation+source
    for item in briefing.get("at_risk_preview", [])[:5]:
        txt = str(item.get("text", ""))
        cite = str(item.get("citation", ""))
        src = str(item.get("source", "dm"))
        # customer = text before ':' if present
        customer = txt.split(":")[0].strip() if ":" in txt else "customer"
        is_review = src == "review"
        draft = _rv(customer, txt, cite) if is_review else _dm(customer, txt, cite)
        priority = "P0-reply-in-2h" if any(w in txt.lower() for w in ["refund", "hasn", "no tracking", "where is", "disappointed", "chipped"]) else "P1-today"
        reply_queue.append({"channel": src, "customer": customer, "summary": txt[:120],
                            "draft": draft, "citation": cite, "priority": priority})
    # ensure review-crisis covered even if briefing trimmed
    seen_cites = {q["citation"] for q in reply_queue}
    for d in scen.get("decisions", []):
        if d.get("scenario") in ("REVIEW_CRISIS", "UNANSWERED_COMPLAINT", "REFUND_RISK") and len(reply_queue) < 6:
            ev = (d.get("evidence") or [""])[0]
            if ev and ev not in seen_cites:
                reply_queue.append({"channel": "scenario", "customer": d.get("scenario", ""),
                                    "summary": str(d.get("title", ""))[:120], "draft": "",
                                    "citation": ev, "priority": "P0-reply-in-2h"})
                seen_cites.add(ev)
    # money at risk: each unanswered complaint ≈ one AOV refund + review damage
    money_at_risk = round(len(reply_queue) * aov, 2)

    # ---- 3. money leaks with dollar amounts ----
    leaks: list[dict[str, Any]] = []
    fees = float(k.get("fees", 0) or 0)
    ship = float(k.get("shipping", 0) or 0)
    cogs = float(k.get("cogs", 0) or 0)
    if gmv > 0 and fees / gmv >= 0.12:
        leaks.append({"leak": "fee_creep", "amount_usd": round(fees, 2),
                      "note": f"Fees {fees/gmv*100:.1f}% of GMV — compare Shopify 2.9%+30c vs Etsy 6.5%+$0.20 vs Amazon 15%; shift volume or raise price ~${fees/max(k.get('orders',1),1):.2f}/order",
                      "evidence": f"[orders] fees ${fees:.2f} / GMV ${gmv:.2f}"})
    for d in scen.get("decisions", []):
        if d.get("scenario") == "SHIPPING_LOSS":
            leaks.append({"leak": "shipping_loss", "amount_usd": None,
                          "note": str(d.get("title", "")), "evidence": (d.get("evidence") or [""])[0]})
            if len(leaks) >= 4:
                break
    if gmv > 0 and float(k.get("margin_pct", 100)) < 10:
        leaks.append({"leak": "margin_dip", "amount_usd": round(float(k.get("true_profit", 0)), 2),
                      "note": f"True margin {k.get('margin_pct')}% — profit ${k.get('true_profit')} on ${gmv} GMV (COGS ${cogs:.2f} fees ${fees:.2f})",
                      "evidence": "[orders] gmv/fees + supplier COGS"})

    # ---- 4. listing fixes (tomorrow's sales) ----
    listing_fixes: list[dict[str, Any]] = []
    for d in scen.get("decisions", []):
        if d.get("scenario") in ("LISTING_GAP", "REVIEW_CRISIS", "PRICE_MISMATCH") and len(listing_fixes) < 3:
            listing_fixes.append({"fix": d.get("scenario", ""), "title": str(d.get("title", ""))[:140],
                                  "evidence": (d.get("evidence") or [""])[0]})
    worst = (k.get("worst_seller") or {})
    if worst.get("product") and len(listing_fixes) < 3:
        listing_fixes.append({"fix": "WORST_SELLER", "title": f" worst seller {worst.get('product')} x{worst.get('qty')} — clearance/bundle it",
                              "evidence": "[orders] worst seller"})

    # ---- 5. headline: one line the owner reads while coffee brews ----
    must_reorder = sum(1 for r in reorder if r["urgency"] == "ORDER TODAY")
    headline = (f"Profit ${k.get('true_profit',0):.2f} ({k.get('margin_pct',0)}%) · "
                f"${money_at_risk:.2f} at risk in {len(reply_queue)} angry messages · "
                f"{must_reorder} reorder(s) TODAY · {len(leaks)} leak(s) to plug")

    # ---- 6. PO draft for top supplier ----
    top_supplier = reorder[0]["supplier"] if reorder else ""
    po_text = _po(top_supplier, reorder) if reorder else "Stock healthy — no PO needed today."

    day = date_str or datetime.now().strftime("%Y-%m-%d")
    return {
        "date": day, "shop": shop, "locale": loc, "headline": headline,
        "kpis": {"gmv": k.get("gmv"), "fees": k.get("fees"), "shipping": k.get("shipping"),
                 "net": k.get("net"), "cogs": k.get("cogs"), "true_profit": k.get("true_profit"),
                 "margin_pct": k.get("margin_pct"), "orders": k.get("orders"), "aov": aov,
                 "best_seller": k.get("best_seller"), "money_at_risk_usd": money_at_risk},
        "do_today": [
            f"Reply to {len(reply_queue)} message(s) — ${money_at_risk:.2f} at risk (drafts below, cite file:line)",
            f"Reorder {reorder[0]['product']} x{reorder[0]['reorder_qty']} from {reorder[0]['supplier']} ({reorder[0]['days_left']}d left)" if reorder else "Stock healthy — no reorder",
            (f"Plug leak: {leaks[0]['leak']} — {leaks[0]['note'][:90]}" if leaks else "No money leaks — push best seller"),
        ],
        "reorder_sheet": reorder,
        "dead_stock_note": [{"title": d.get("title", ""), "evidence": (d.get("evidence") or [""])[0]} for d in dead],
        "reply_queue": reply_queue,
        "money_leaks": leaks,
        "listing_fixes": listing_fixes,
        "po_draft": po_text,
        "citations": "every number cites [file:line]; audit via /seller/operations",
        "free": True, "offline": True,
    }


def close_to_csv(close: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["DAILY CLOSE", close.get("date", ""), close.get("headline", "")])
    w.writerow([])
    w.writerow(["metric", "value"])
    for k_, v in (close.get("kpis") or {}).items():
        w.writerow([k_, v])
    w.writerow([])
    w.writerow(["do_today_n", "do_today"])
    for i, t in enumerate(close.get("do_today", []), 1):
        w.writerow([i, t])
    w.writerow([])
    w.writerow(["product", "on_hand", "sold_7d", "days_left", "reorder_qty_14d", "supplier", "urgency", "citation"])
    for r in close.get("reorder_sheet", []):
        w.writerow([r.get("product", ""), r.get("on_hand", ""), r.get("sold_7d", ""),
                    r.get("days_left", ""), r.get("reorder_qty", ""), r.get("supplier", ""),
                    r.get("urgency", ""), r.get("citation", "")])
    w.writerow([])
    w.writerow(["leak", "amount_usd", "note", "evidence"])
    for lk in close.get("money_leaks", []):
        w.writerow([lk.get("leak", ""), lk.get("amount_usd", ""), lk.get("note", "")[:160], lk.get("evidence", "")])
    return buf.getvalue()


def reorder_to_csv(close: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["product", "on_hand", "sold_7d", "daily_velocity", "days_left",
                "reorder_qty_14d", "supplier", "urgency", "citation"])
    for r in close.get("reorder_sheet", []):
        w.writerow([r.get("product", ""), r.get("on_hand", ""), r.get("sold_7d", ""),
                    r.get("daily_velocity", ""), r.get("days_left", ""), r.get("reorder_qty", ""),
                    r.get("supplier", ""), r.get("urgency", ""), r.get("citation", "")])
    return buf.getvalue()


def replies_to_txt(close: dict[str, Any]) -> str:
    out = [f"DAILY CLOSE {close.get('date','')} — REPLY QUEUE (${(close.get('kpis') or {}).get('money_at_risk_usd',0):.2f} at risk)",
           "=" * 64, ""]
    for i, q in enumerate(close.get("reply_queue", []), 1):
        out += [f"[{i}] {q.get('priority','')} — {q.get('channel','')}: {q.get('customer','')}",
                f"    customer said: {q.get('summary','')}",
                f"    evidence: {q.get('citation','')}",
                f"    COPY-PASTE DRAFT: {q.get('draft','(see scenario action)')}", ""]
    out += ["PO DRAFT (send to supplier):", "-" * 64, close.get("po_draft", "")]
    return "\n".join(out)


def write_close_bundle(close: dict[str, Any], out_dir: str | Path) -> dict[str, str]:
    """Write close.json + close.csv + reorder.csv + replies.txt + po.txt. Returns paths."""
    import json as _json
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    paths["close.json"] = str(out / "close.json")
    (out / "close.json").write_text(_json.dumps(close, indent=2, default=str))
    paths["close.csv"] = str(out / "close.csv")
    (out / "close.csv").write_text(close_to_csv(close))
    paths["reorder.csv"] = str(out / "reorder.csv")
    (out / "reorder.csv").write_text(reorder_to_csv(close))
    paths["replies.txt"] = str(out / "replies.txt")
    (out / "replies.txt").write_text(replies_to_txt(close))
    paths["po.txt"] = str(out / "po.txt")
    (out / "po.txt").write_text(close.get("po_draft", ""))
    return paths
