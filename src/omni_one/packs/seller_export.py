"""
Seller export — briefing -> CSV / JSON for sheets, accounting, sharing.
Deterministic, $0, no LLM. Every number traceable to file:line via citations.
"""
from __future__ import annotations
import csv
import io
from typing import Any


def briefing_to_csv(briefing: dict[str, Any]) -> str:
    k = briefing.get("kpis", {})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric", "value"])
    for key in ["gmv", "fees", "shipping", "net", "cogs", "true_profit", "margin_pct",
                "orders", "aov", "at_risk", "stockout_risk"]:
        w.writerow([key, k.get(key, "")])
    best = k.get("best_seller", {}) or {}
    w.writerow(["best_seller", f"{best.get('product','')} x{best.get('qty','')}"])
    w.writerow([])
    w.writerow(["alert_severity", "alert_message", "evidence"])
    for a in briefing.get("alerts", []):
        ev = (a.get("evidence") or [""])[0]
        w.writerow([a.get("severity", ""), a.get("message", ""), ev])
    w.writerow([])
    w.writerow(["action_n", "action"])
    for i, act in enumerate(briefing.get("actions", []), 1):
        w.writerow([i, act])
    w.writerow([])
    w.writerow(["stockout_product", "on_hand", "sold_7d", "days_supply", "citation"])
    for r in briefing.get("stockout_risk", []):
        w.writerow([r.get("product", ""), r.get("on_hand", ""), r.get("sold_7d", ""),
                    r.get("days_supply", ""), r.get("citation", "")])
    draft = (briefing.get("draft_reply") or {})
    w.writerow([])
    w.writerow(["draft_reply", draft.get("text", "")])
    w.writerow(["draft_citation", draft.get("citation", "")])
    return buf.getvalue()


def scenarios_to_csv(scen: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["scenario_id", "severity", "title", "evidence", "workshop_action"])
    for d in scen.get("decisions", []):
        ev = (d.get("evidence") or [""])[0]
        w.writerow([d.get("scenario_id", ""), d.get("severity", ""),
                    d.get("title", "")[:160], str(ev)[:160], d.get("action", "")])
    return buf.getvalue()
