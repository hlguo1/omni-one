"""
Ops-loop Close — deterministic operations bundle (PACK E).
===============================================================================
The full operations loop, closed daily, offline:

    foundry -> ontology -> scenarios -> workshop -> aip -> governance -> bundle

    FOUNDRY (version products + join, or skip+reason)
      -> ONTOLOGY twin (Product/Order/Shipment seeded from briefing)
      -> SCENARIOS x12 (stable md5 IDs, idempotent)
      -> WORKSHOP queue FROM ontology (no phantoms)
      -> AIP seller_stockout on first SKU + evaluate() harness
      -> GOVERNANCE audit chain (verify(), head, by_kind)
      -> BUNDLE: close.json + decisions.csv + audit.json

What this pack proves (the engine surrounding core tech):
  - Foundry feeds the Ontology (versioned datasets, lineage-tracked).
  - The Workshop queue is built FROM the ontology, never from raw tables.
  - AIP answers are grounding-checked, with an evaluate() harness that
    must stay green before close.
  - Governance hash-chains every workshop + ontology write; verify()
    detects tampering.
  - The bundle (close.json + decisions.csv + audit.json) is what the
    operator files every morning — deterministic, mock-only, offline.

NO-PHANTOMS RULE (load-bearing):
  Every ``decisions[]`` entry carries ``object_ref`` (``Type:pk``) that
  MUST resolve to a twin object built in the same run. Ungroundable
  scenario decisions fall back to the first Product; references are
  NEVER invented. Tests check each ``object_ref`` against
  ``ontology.refs``.

APPROVAL FLOW (human-in-the-loop):
  1. ``add_decision`` queues (``open``) with a ``proposed_action``.
  2. Lead runs ``assign(decision_id, "ops-1")`` to own it.
  3. Lead runs ``approve(decision_id, "lead")`` — propose + approve
     through the ontology (respects ``requires_approval``) -> ``approved``.
  4. ``resolve(decision_id, "lead")`` closes it; every step is hash-chained.
  This pack queues + reports; it does NOT auto-approve.

Determinism contract:
  - Same ``events`` -> same decision ``stable_id`` list + same counts
    (scenario IDs are md5(type+key); workshop upserts are idempotent).
  - Foundry versions and audit ``at`` timestamps are wall-clock and are
    EXCLUDED from the idempotency contract (same logic, new tx id).
  - Mock only: no network, no LLM keys, works on plane wifi.

Intended wiring (NOT implemented here — see docs/OPS_CLOSE.md):
  - CLI: ``omni-one ops-close --demo --out ./ops_close_today``
  - API: ``POST /api/v1/ops/close`` -> same ``build_ops_close`` result.

Free: stdlib + repo-local packs only. Runs offline.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# --- constants ---

#: Namespace default for the daily ops loop (workshop app + audit log names
#: derive from this so parallel loops never collide).
DEFAULT_NAMESPACE = "ops-daily"

#: Twin digest caps (operator's digest, not a warehouse).
MAX_PRODUCTS = 6
MAX_ORDERS = 8
MAX_SHIPMENTS = 4

#: AIP eval case name for the headline stockout check.
EVAL_CASE_NAME = "stockout-grounded"

#: CSV columns for decisions.csv (stable contract — sheets/accounting read it).
DECISION_CSV_COLUMNS = ["stable_id", "title", "severity", "status",
                        "object_ref", "evidence", "source"]

#: Severity rank used for human-readable ordering (critical first).
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# --- small deterministic helpers ---

def _utcnow_iso() -> str:
    """Wall-clock timestamp (audit/foundry metadata ONLY, never compared)."""
    return datetime.now().isoformat()


def _sku_for(product: str, taken: set) -> str:
    """Deterministic SKU from a product name (repo convention).

    Alphanumerics, 8 chars, numeric suffix on collision. Same name ->
    same SKU across runs (seeding order is sorted upstream).
    """
    base = "".join(c for c in (product or "") if c.isalnum())[:8] or "P"
    sku = base
    n = 2
    while sku in taken:
        sku = f"{base[:7]}{n}"
        n += 1
    taken.add(sku)
    return sku


def _short_hash(text: str, length: int = 12) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def _evid_str(evidence: Any) -> str:
    """Join evidence list into a single CSV-safe string."""
    if not evidence:
        return ""
    if isinstance(evidence, str):
        return evidence
    try:
        return " | ".join(str(e) for e in list(evidence)[:4])
    except Exception:
        return str(evidence)[:200]


def _ensure_briefing(events: List[Dict[str, Any]],
                     briefing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the seller briefing unless the caller supplied one (DI seam)."""
    if briefing is not None:
        return briefing
    from omni_one.packs.seller_os import build_seller_briefing
    return build_seller_briefing(events or [])


def _ensure_scen(events: List[Dict[str, Any]],
                 scen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Run the 12-scenario library unless the caller supplied it (DI seam)."""
    if scen is not None:
        return scen
    from omni_one.packs.seller_scenarios import run_all_scenarios
    return run_all_scenarios(events or [])


# --- foundry stage: version products (+ join when the engine allows) ---

def _product_rows(briefing: Dict[str, Any],
                  scen: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pure-data product rows shared by the foundry + ontology stages.

    1. briefing ``chart.data.labels`` (top 6 sellers),
    2. scenario decisions' ``product`` fields (every scenario product gets
       a twin object to ground to), enriched with on_hand / sold_7d from
    briefing ``stockout_risk``. Sorted by name for determinism.
    """
    risk_by_norm = {}
    for r in briefing.get("stockout_risk", []) or []:
        key = str(r.get("product", "")).strip().lower()
        risk_by_norm[key] = r

    names: List[str] = []
    seen_norm = set()

    def _add(name: Any) -> None:
        s = str(name or "").strip()
        if not s:
            return
        n = s.lower()
        if n in seen_norm:
            return
        seen_norm.add(n)
        names.append(s)

    chart = ((briefing.get("chart", {}) or {}).get("data", {}) or {})
    for label in (chart.get("labels", []) or [])[:MAX_PRODUCTS]:
        _add(label)
    # Guarantee every scenario product is twin-able (no-phantoms rule).
    for d in (scen.get("decisions", []) or []):
        if d.get("product"):
            _add(d.get("product"))

    best = ((briefing.get("kpis", {}) or {}).get("best_seller", {}) or {})
    rows: List[Dict[str, Any]] = []
    taken: set = set()
    for name in sorted(names)[: max(MAX_PRODUCTS, len(names))]:
        r = risk_by_norm.get(name.strip().lower(), {})
        on_hand = int(r.get("on_hand", 10) or 0)
        sold_7d = int(r.get("sold_7d", 0) or 0)
        if sold_7d == 0 and best.get("product") == name:
            try:
                sold_7d = int(best.get("qty", 1) or 1)
            except Exception:
                sold_7d = 1
        if sold_7d == 0:
            sold_7d = 1
        rows.append({
            "sku": _sku_for(name, taken),
            "name": name,
            "on_hand": on_hand,
            "sold_7d": sold_7d,
        })
    return rows


def _order_rows(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pure-data order rows (capped, sorted by entity id for determinism)."""
    orders = [e for e in (events or []) if e.get("source") == "orders"]
    orders = sorted(orders, key=lambda e: str(e.get("entity_id", "")))
    rows: List[Dict[str, Any]] = []
    for i, e in enumerate(orders[:MAX_ORDERS]):
        md = e.get("metadata", {}) or {}
        try:
            qty = int(float(md.get("qty", 1) or 1))
        except Exception:
            qty = 1
        try:
            gmv = float(md.get("gmv", 0) or 0)
        except Exception:
            gmv = 0.0
        rows.append({
            "order_id": str(e.get("entity_id", f"O-{i:04d}")),
            "product": str(md.get("product", "unknown") or "unknown"),
            "qty": qty,
            "gmv": round(gmv, 2),
        })
    return rows


def _run_foundry_stage(events: List[Dict[str, Any]],
                       briefing: Dict[str, Any],
                       scen: Dict[str, Any],
                       namespace: str) -> Dict[str, Any]:
    """Version product/order datasets; SQL-join when DuckDB is present.

    Returns ``status == "ok"`` (versions + join row count) OR a recorded
    skip (``status == "skipped"`` + human ``reason``). A skip never
    crashes the loop.
    """
    products = _product_rows(briefing, scen)
    orders = _order_rows(events)
    stage: Dict[str, Any] = {
        "namespace": namespace,
        "status": "ok",
        "products_rows": len(products),
        "orders_rows": len(orders),
        "products_version": None,
        "orders_version": None,
        "join": {"status": "skipped", "reason": "not attempted yet"},
        "datasets_path": None,
    }
    try:
        from omni_one.engine.foundry import FoundryDataset
    except Exception as e:  # pragma: no cover - import guard
        stage["status"] = "skipped"
        stage["reason"] = f"foundry import failed: {e}"[:200]
        return stage
    if not products and not orders:
        stage["status"] = "skipped"
        stage["reason"] = "no product/order rows to version (empty events)"
        return stage
    try:
        base = Path(tempfile.mkdtemp(prefix=f"foundry-{namespace}-"))
        stage["datasets_path"] = str(base)
        lineage = f"ops-close:{namespace} products={len(products)} orders={len(orders)}"
        if products:
            pds = FoundryDataset(base / "products", "products")
            stage["products_version"] = pds.write(products, lineage=lineage)
        if orders:
            ods = FoundryDataset(base / "orders", "orders")
            stage["orders_version"] = ods.write(orders, lineage=lineage)
        # Join products x orders on normalized name when possible.
        try:
            from omni_one.engine.foundry import sql_join
            import pandas as _pd
            pdf = _pd.DataFrame(products) if products else _pd.DataFrame([{"sku": "NONE", "name": "none", "on_hand": 0, "sold_7d": 0}])
            odf = _pd.DataFrame(orders) if orders else _pd.DataFrame([{"order_id": "NONE", "product": "none", "qty": 0, "gmv": 0.0}])
            joined = sql_join(
                {"products": pdf, "orders": odf},
                "SELECT p.sku, p.name, p.on_hand, o.order_id, o.qty "
                "FROM products p LEFT JOIN orders o "
                "ON lower(p.name) = lower(o.product)",
            )
            stage["join"] = {"status": "ok", "sql": "products LEFT JOIN orders ON lower(name)=lower(product)", "rows": int(len(joined))}
        except Exception as e:
            stage["join"] = {"status": "skipped", "reason": f"sql_join unavailable: {e}"[:200]}
    except Exception as e:
        stage["status"] = "skipped"
        stage["reason"] = f"foundry build failed: {e}"[:200]
        stage["join"] = {"status": "skipped", "reason": stage.get("reason", "build failed")[:200]}
    return stage


# --- ontology stage: Product / Order / Shipment twin + seeds ---

def _define_ops_ontology(onto: Any) -> None:
    """Define the minimal ops twin: Product, Order, Shipment + actions.

    Actions cover every ``proposed_action`` the 12-scenario library can
    emit, so propose -> approve -> resolve works for any queued decision.
    """
    from omni_one.engine.ontology import (
        ActionDef, ObjectTypeDef, PropertyDef,
    )

    onto.define_object_type(ObjectTypeDef(
        api_name="Product", display_name="Product", primary_key="sku",
        title_property="name",
        properties=[
            PropertyDef(name="sku", type="string", required=True),
            PropertyDef(name="name", type="string", required=True),
            PropertyDef(name="on_hand", type="integer"),
            PropertyDef(name="sold_7d", type="integer"),
            PropertyDef(name="status", type="string"),
        ]))
    onto.define_object_type(ObjectTypeDef(
        api_name="Order", display_name="Order", primary_key="order_id",
        title_property="order_id",
        properties=[
            PropertyDef(name="order_id", type="string", required=True),
            PropertyDef(name="product", type="string"),
            PropertyDef(name="qty", type="integer"),
            PropertyDef(name="gmv", type="double"),
            PropertyDef(name="status", type="string"),
        ]))
    onto.define_object_type(ObjectTypeDef(
        api_name="Shipment", display_name="Shipment", primary_key="shipment_id",
        title_property="shipment_id",
        properties=[
            PropertyDef(name="shipment_id", type="string", required=True),
            PropertyDef(name="supplier", type="string"),
            PropertyDef(name="status", type="string"),
            PropertyDef(name="total", type="double"),
        ]))

    # Links (best-effort enrichment; the twin works without them).
    try:
        from omni_one.engine.ontology import LinkTypeDef
        onto.define_link_type(LinkTypeDef(
            api_name="ORDER_CONTAINS", display_name="Order contains",
            from_type="Order", to_type="Product",
            cardinality="MANY_TO_MANY"))
        onto.define_link_type(LinkTypeDef(
            api_name="SHIPMENT_FULFILLS", display_name="Shipment fulfills",
            from_type="Shipment", to_type="Order",
            cardinality="MANY_TO_MANY"))
    except Exception:
        pass  # links are enrichment; the twin works without them.

    # One action per scenario proposed_action name (all lead-approved).
    _actions: List[Tuple[str, str, str, str]] = [
        ("reorderProduct", "Reorder product", "Product", "REORDERED"),
        ("markDownProduct", "Mark down product", "Product", "CLEARANCE"),
        ("reviewPricing", "Review pricing", "Product", "REVIEWED"),
        ("alignPrice", "Align price", "Product", "ALIGNED"),
        ("requestReview", "Request review", "Product", "REQUESTED"),
        ("renegotiateSupplier", "Renegotiate supplier", "Product", "NEGOTIATING"),
        ("messageCustomer", "Message customer", "Product", "CONTACTED"),
        ("replyReview", "Reply to review", "Product", "REPLIED"),
        ("triageDMs", "Triage DMs", "Product", "TRIAGED"),
        ("adjustShipping", "Adjust shipping", "Order", "ADJUSTED"),
        ("rerouteShipment", "Reroute shipment", "Shipment", "REROUTED"),
    ]
    for api_name, display, obj_type, allowed in _actions:
        try:
            onto.define_action(ActionDef(
                api_name=api_name, display_name=display,
                object_type=obj_type,
                parameters=[PropertyDef(name="status", type="string")],
                checks=[{"field": "status", "allowed": [allowed]}],
                requires_approval=True,
                allowed_approvers=["lead"],
            ))
        except Exception:
            continue


def _resolve_product_pk(onto: Any, product_name: str) -> Optional[str]:
    """Best-effort Product pk for an order/supplier line (exact, then fuzzy)."""
    try:
        objs = onto.objects.get("Product", {}) or {}
    except Exception:
        return None
    if not objs:
        return None
    want = str(product_name or "").strip().lower()
    for pk, obj in objs.items():
        title = str(obj.properties.get("name", "") or "").strip().lower()
        if title == want:
            return pk
    try:
        from difflib import SequenceMatcher as _SM
        best, best_score = None, 0.0
        for pk, obj in objs.items():
            title = str(obj.properties.get("name", "") or pk)
            s = _SM(None, title.lower(), want).ratio()
            if s > best_score:
                best, best_score = pk, s
        if best is not None and best_score >= 0.6:
            return best
    except Exception:
        pass
    return None


def _seed_ops_ontology(onto: Any,
                       events: List[Dict[str, Any]],
                       briefing: Dict[str, Any],
                       scen: Dict[str, Any],
                       namespace: str) -> Dict[str, Any]:
    """Seed Product/Order/Shipment objects from briefing + supplier lines.

    Products: chart labels + scenario product fields (shares
    ``_product_rows`` with foundry so both stages agree on SKUs).
    Orders: raw ``orders`` events. Shipments: raw ``supplier`` events.
    Returns counts plus ``refs`` — the full ``Type:pk`` inventory used
    by the no-phantoms test.
    """
    from omni_one.engine.ontology import ObjectInstance

    lineage = f"ops-close:{namespace}:briefing"
    counts = {"products": 0, "orders": 0, "shipments": 0}

    # --- Products (shared rows => foundry/ontology agree) ---
    for row in _product_rows(briefing, scen):
        try:
            onto.create_object(ObjectInstance(
                object_type="Product", primary_key=row["sku"],
                properties={"sku": row["sku"], "name": row["name"],
                            "on_hand": int(row["on_hand"]),
                            "sold_7d": int(row["sold_7d"])},
            ), lineage=lineage)
            counts["products"] += 1
        except Exception:
            continue

    # --- Orders (from raw order events) ---
    for row in _order_rows(events):
        try:
            onto.create_object(ObjectInstance(
                object_type="Order", primary_key=row["order_id"],
                properties={"order_id": row["order_id"],
                            "product": row["product"],
                            "qty": int(row["qty"]),
                            "gmv": float(row["gmv"])},
            ), lineage=f"ops-close:{namespace}:orders")
            counts["orders"] += 1
        except Exception:
            continue

    # --- Shipments (from raw supplier lines) ---
    supplier_events = sorted(
        [e for e in (events or []) if e.get("source") == "supplier"],
        key=lambda e: str(e.get("entity_id", "")),
    )
    for i, e in enumerate(supplier_events[:MAX_SHIPMENTS]):
        md = e.get("metadata", {}) or {}
        sid = str(e.get("entity_id", f"S-{i:04d}"))
        supplier = str(md.get("supplier", "") or "")[:60]
        if not supplier:
            raw = str(md.get("raw", "") or e.get("value", ""))
            supplier = " ".join(raw.split()[:2])[:60] or "supplier"
        try:
            total = float(e.get("value", 0) or 0)
        except Exception:
            total = 0.0
        try:
            onto.create_object(ObjectInstance(
                object_type="Shipment", primary_key=sid,
                properties={"shipment_id": sid, "supplier": supplier,
                            "status": "IN_TRANSIT", "total": round(total, 2)},
            ), lineage=f"ops-close:{namespace}:supplier")
            counts["shipments"] += 1
        except Exception:
            continue

    # --- Links (best-effort enrichment; never fail the loop) ---
    try:
        for o_pk, o in list((onto.objects.get("Order", {}) or {}).items()):
            prod_pk = _resolve_product_pk(
                onto, str(o.properties.get("product", "")))
            if prod_pk:
                try:
                    onto.link("Order", o_pk, "ORDER_CONTAINS", prod_pk)
                except Exception:
                    continue
    except Exception:
        pass
    try:
        order_pks = list((onto.objects.get("Order", {}) or {}).keys())
        for s_pk in list((onto.objects.get("Shipment", {}) or {}).keys()):
            if order_pks:
                try:
                    onto.link("Shipment", s_pk, "SHIPMENT_FULFILLS",
                              order_pks[0])
                except Exception:
                    continue
    except Exception:
        pass

    refs: List[str] = []
    try:
        for t, mp in (onto.objects or {}).items():
            for pk in mp:
                refs.append(f"{t}:{pk}")
    except Exception:
        pass
    refs = sorted(set(refs))
    return {"products": counts["products"], "orders": counts["orders"],
            "shipments": counts["shipments"], "refs": refs}


# --- workshop stage: queue FROM ontology (grounded, idempotent) ---

def _build_workshop_queue(onto: Any,
                          briefing: Dict[str, Any],
                          scen: Dict[str, Any],
                          namespace: str) -> Tuple[Any, List[Any], str]:
    """Build the Workshop queue via scenarios (stable IDs), with fallback.

    Primary: ``scenarios_to_workshop`` — scenario ``id`` values (md5 of
    type+key) pass as ``stable_id`` so re-runs upsert, never duplicate.
    Fallback: ``build_seller_queue`` (recorded in ``via``).
    Returns ``(app, decisions, via)``.
    """
    from omni_one.engine.workshop import WorkshopApp
    app = WorkshopApp(onto, f"{namespace}-queue")
    via = "scenarios_to_workshop"
    try:
        from omni_one.packs.seller_scenarios import scenarios_to_workshop
        made = scenarios_to_workshop(scen, app)
    except Exception:
        via = "build_seller_queue(fallback)"
        try:
            made = app.build_seller_queue(briefing)
        except Exception:
            made = []
    return app, list(made or []), via


def _decision_to_dict(d: Any) -> Dict[str, Any]:
    """Serialize one Workshop Decision (JSON-safe, phantom-checkable)."""
    try:
        dd = d.to_dict() if hasattr(d, "to_dict") else dict(d)
    except Exception:
        dd = {"id": str(getattr(d, "id", "?")),
              "title": str(getattr(d, "title", ""))}
    return {
        "stable_id": str(dd.get("id", "")),
        "title": str(dd.get("title", "")),
        "severity": str(dd.get("severity", "medium")),
        "status": str(dd.get("status", "open")),
        "object_ref": str(dd.get("object_ref", "")),
        "evidence": list(dd.get("evidence", []) or []),
        "evidence_str": _evid_str(dd.get("evidence", [])),
        "proposed_action": dd.get("proposed_action"),
        "source": str(dd.get("source", "")),
    }


# --- aip stage: grounded run on first SKU + evaluate() harness ---

def _run_aip_stage(onto: Any, namespace: str) -> Dict[str, Any]:
    """Run ``seller_stockout`` on the first SKU + the eval harness.

    The eval case asserts the answer contains the SKU and requires
    grounding, so ``pass_rate`` is 1.0 whenever the twin has a Product.
    With zero Products the stage records a skip (with reason) and a
    vacuous 1.0 eval — the loop never crashes on empty.
    """
    from omni_one.engine.aip import AIPLogic
    logic = AIPLogic(onto, f"{namespace}-aip")
    try:
        first_sku = sorted((onto.objects.get("Product", {}) or {}).keys())[0]
    except Exception:
        first_sku = None
    if not first_sku:
        return {
            "sku": None, "status": "skipped",
            "reason": "no Product objects in ontology twin (empty events?)",
            "grounded": False, "grounded_count": 0, "grounded_total": 0,
            "grounded_rate": 0.0, "answer": "",
            "eval": {"name": EVAL_CASE_NAME, "passed": 0, "total": 0,
                     "pass_rate": 1.0, "details": [], "free": True,
                     "note": "vacuous pass: nothing to evaluate"},
            "pass_rate": 1.0,
        }
    try:
        res = logic.run_registered("seller_stockout", sku=first_sku)
    except Exception as e:
        return {
            "sku": first_sku, "status": "error",
            "reason": f"seller_stockout failed: {e}"[:200],
            "grounded": False, "grounded_count": 0, "grounded_total": 1,
            "grounded_rate": 0.0, "answer": "",
            "eval": {"name": EVAL_CASE_NAME, "passed": 0, "total": 1,
                     "pass_rate": 0.0, "details": [], "free": True},
            "pass_rate": 0.0,
        }
    grounded = bool(res.get("grounded"))
    evaluation = logic.evaluate([{
        "name": EVAL_CASE_NAME,
        "fn_name": "seller_stockout",
        "inputs": {"sku": first_sku},
        "expect_contains": [str(first_sku)],
        "require_grounded": True,
    }])
    return {
        "sku": first_sku, "status": "ok",
        "grounded": grounded,
        "grounded_count": 1 if grounded else 0,
        "grounded_total": 1,
        "grounded_rate": 1.0 if grounded else 0.0,
        "answer": str(res.get("answer", ""))[:240],
        "citations": list(res.get("citations", []) or [])[:4],
        "eval": evaluation,
        "pass_rate": float(evaluation.get("pass_rate", 0.0)),
    }


# --- governance stage: hash-chained audit of workshop + ontology ---

def _run_governance_stage(app: Any, onto: Any,
                          namespace: str) -> Tuple[Any, Dict[str, Any]]:
    """Ingest workshop decisions + ontology edits; verify the chain.

    Returns ``(audit_log, audit_summary)``; the summary is JSON-safe:
    ``{"head", "verified", "by_kind", "total", "verify"}``.
    """
    from omni_one.engine.governance import (
        AuditLog, ingest_ontology_edits, ingest_workshop,
    )
    audit = AuditLog(f"{namespace}-audit")
    n_workshop = 0
    n_ontology = 0
    try:
        n_workshop = int(ingest_workshop(audit, app) or 0)
    except Exception:
        n_workshop = 0
    try:
        n_ontology = int(ingest_ontology_edits(audit, onto) or 0)
    except Exception:
        n_ontology = 0
    try:
        verify_res = audit.verify()
    except Exception:
        verify_res = {"ok": False, "checked": 0, "total": 0}
    verified = bool(verify_res.get("ok", False))
    try:
        stats = audit.stats()
    except Exception:
        stats = {"total": len(getattr(audit, "events", [])),
                 "by_kind": {}, "head": "GENESIS", "verified": verified}
    summary = {
        "head": str(stats.get("head", "GENESIS")),
        "verified": bool(stats.get("verified", verified)),
        "by_kind": dict(stats.get("by_kind", {}) or {}),
        "total": int(stats.get("total", 0)),
        "ingested": {"workshop": n_workshop, "ontology": n_ontology},
        "verify": {"ok": verified,
                  "checked": int(verify_res.get("checked", 0)),
                  "total": int(verify_res.get(
                      "total", stats.get("total", 0)))},
    }
    # Belt-and-braces: the summary flag always equals verify()["ok"].
    summary["verified"] = verified
    return audit, summary


# --- headline + kpis + operator plan ---

def _build_headline(namespace: str, total: int, n_open: int, n_resolved: int,
                    g_count: int, g_total: int,
                    verified: bool, head: str) -> str:
    """One line the owner reads while coffee brews (golden-tested)."""
    return (
        f"OPS CLOSE {namespace}: {total} decisions "
        f"({n_open} open, {n_resolved} resolved) · "
        f"grounded {g_count}/{g_total} · "
        f"audit verified {verified} · head {head}"
    )


def _build_do_today(decisions: List[Dict[str, Any]],
                    pass_rate: float) -> List[str]:
    """Exactly three operator steps: approve X, assign Y, re-run eval."""
    if not decisions:
        return [
            "No decisions queued — verify the demo folder ingested events "
            "(chart + supplier lines), then re-run the loop",
            "Assign nothing: queue empty — spot-check ontology refs "
            "(Product/Order/Shipment) before close",
            f"Re-run eval: AIPLogic.evaluate seller_stockout pass_rate "
            f"{pass_rate:.2f} — must stay 1.0 before close",
        ]
    first = decisions[0]
    second = decisions[1] if len(decisions) > 1 else decisions[0]
    return [
        f"Approve {first['stable_id']} ({first['title'][:70]}) via lead — "
        f"WorkshopApp.approve, then resolve",
        f"Assign {second['stable_id']} ({second['title'][:70]}) to ops-1 — "
        f"work oldest critical first",
        f"Re-run eval: AIPLogic.evaluate seller_stockout pass_rate "
        f"{pass_rate:.2f} — must stay 1.0 before close",
    ]


# --- main entry: the flagship loop ---

def build_ops_close(events: List[Dict[str, Any]],
                    briefing: Optional[Dict[str, Any]] = None,
                    scen: Optional[Dict[str, Any]] = None,
                    namespace: str = DEFAULT_NAMESPACE) -> Dict[str, Any]:
    """Run foundry -> ontology -> scenarios -> workshop -> aip -> governance.

    Args:
        events: raw seller events (as ingested by ``seller_os``).
        briefing: prebuilt briefing (DI seam; built when None).
        scen: prebuilt scenario result (DI seam; run when None).
        namespace: isolates workshop/audit names for parallel loops.

    Returns a JSON-safe dict with ``headline``, ``kpis``, ``decisions``,
    ``audit``, ``do_today`` plus per-stage detail. Deterministic and
    mock-only; empty events return a valid (empty) close, never raise.
    """
    from omni_one.engine.ontology import Ontology

    events = list(events or [])
    ns = (namespace or DEFAULT_NAMESPACE).strip() or DEFAULT_NAMESPACE

    briefing = _ensure_briefing(events, briefing)
    scen = _ensure_scen(events, scen)

    # 1. Foundry: version products (+ join when DuckDB allows).
    foundry = _run_foundry_stage(events, briefing, scen, ns)

    # 2. Ontology twin: Product / Order / Shipment + seeded objects.
    onto = Ontology(f"{ns}-twin")
    _define_ops_ontology(onto)
    seed = _seed_ops_ontology(onto, events, briefing, scen, ns)
    try:
        ontology_hash = onto.lineage_hash()
    except Exception:
        ontology_hash = "unknown"
    try:
        type_counts = {t: len(mp) for t, mp in (onto.objects or {}).items()}
    except Exception:
        type_counts = {}

    # 3. Workshop queue FROM ontology (stable IDs; fallback noted).
    app, made, via = _build_workshop_queue(onto, briefing, scen, ns)
    # Severity-ranked for humans; stable_id order is deterministic too.
    try:
        ranked = app.list()
    except Exception:
        ranked = list(made)
    decisions = [_decision_to_dict(d) for d in ranked]

    n_open = sum(1 for d in decisions if d["status"] == "open")
    n_resolved = sum(1 for d in decisions if d["status"] == "resolved")

    # 4. AIP grounded run on the first SKU + eval harness.
    aip = _run_aip_stage(onto, ns)
    g_count = int(aip.get("grounded_count", 0))
    g_total = int(aip.get("grounded_total", 0))
    pass_rate = float(aip.get("pass_rate", 0.0))
    grounded_rate = round(g_count / g_total, 3) if g_total else 0.0

    # 5. Governance: hash-chain workshop + ontology, verify.
    _audit_log, audit = _run_governance_stage(app, onto, ns)
    verified = bool(audit.get("verified", False))
    head = str(audit.get("head", "GENESIS"))

    # Headline / kpis / operator plan.
    headline = _build_headline(ns, len(decisions), n_open, n_resolved,
                               g_count, g_total, verified, head)
    kpis = {
        "decisions": len(decisions),
        "open": n_open,
        "resolved": n_resolved,
        "grounded_rate": grounded_rate,
        "audit_events": int(audit.get("total", 0)),
        "verified": verified,
    }
    do_today = _build_do_today(decisions, pass_rate)

    try:
        workshop_stats = app.stats()
    except Exception:
        workshop_stats = {"app": f"{ns}-queue", "total": len(decisions),
                          "by_status": {}, "by_severity": {}}

    bkpis = briefing.get("kpis", {}) if isinstance(briefing, dict) else {}
    return {
        "namespace": ns,
        "headline": headline,
        "generated_at": _utcnow_iso(),
        "kpis": kpis,
        "decisions": decisions,
        "audit": audit,
        "do_today": do_today,
        "foundry": foundry,
        "ontology": {
            "name": getattr(onto, "name", f"{ns}-twin"),
            "hash": ontology_hash,
            "counts": type_counts,
            "seeded": {k: v for k, v in seed.items() if k != "refs"},
            "refs": seed.get("refs", []),
        },
        "workshop": {
            "stats": workshop_stats,
            "total": int(workshop_stats.get("total", len(decisions))),
            "via": via,
        },
        "aip": aip,
        "briefing_kpis": {
            "gmv": bkpis.get("gmv"), "true_profit": bkpis.get("true_profit"),
            "orders": bkpis.get("orders"),
            "best_seller": bkpis.get("best_seller"),
        },
        "scenarios": {
            "total": int((scen or {}).get("total", 0) or 0),
            "by_scenario": dict((scen or {}).get("by_scenario", {}) or {}),
        },
        "free": True,
        "offline": True,
    }


# --- csv + bundle writers (the artifacts the operator files) ---

def decisions_to_csv(close: Dict[str, Any]) -> str:
    """Render ``close["decisions"]`` as CSV (stable columns, csv-parseable)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=DECISION_CSV_COLUMNS,
                       extrasaction="ignore")
    w.writeheader()
    for d in (close or {}).get("decisions", []) or []:
        row = {
            "stable_id": d.get("stable_id", ""),
            "title": d.get("title", ""),
            "severity": d.get("severity", ""),
            "status": d.get("status", ""),
            "object_ref": d.get("object_ref", ""),
            "evidence": d.get("evidence_str",
                              _evid_str(d.get("evidence", []))),
            "source": d.get("source", ""),
        }
        w.writerow(row)
    return buf.getvalue()


def audit_to_jsonable(close: Dict[str, Any]) -> Dict[str, Any]:
    """Copy of the audit stats + head (what audit.json contains)."""
    audit = (close or {}).get("audit", {}) or {}
    return {
        "namespace": (close or {}).get("namespace", DEFAULT_NAMESPACE),
        "headline": (close or {}).get("headline", ""),
        "head": audit.get("head", "GENESIS"),
        "verified": bool(audit.get("verified", False)),
        "by_kind": dict(audit.get("by_kind", {}) or {}),
        "total": int(audit.get("total", 0)),
        "ingested": dict(audit.get("ingested", {}) or {}),
        "verify": dict(audit.get("verify", {}) or {}),
    }


def write_close_bundle(close: Dict[str, Any],
                       out_dir: str | Path) -> Dict[str, str]:
    """Write close.json + decisions.csv + audit.json. Returns str paths.

    The operator's morning file-set: ``close.json`` (full close),
    ``decisions.csv`` (queue for sheets/accounting), ``audit.json``
    (copy of audit stats + head, tamper-evidence).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, str] = {}

    close_path = out / "close.json"
    close_path.write_text(json.dumps(close, indent=2, default=str),
                          encoding="utf-8")
    paths["close.json"] = str(close_path)

    csv_path = out / "decisions.csv"
    csv_path.write_text(decisions_to_csv(close), encoding="utf-8")
    paths["decisions.csv"] = str(csv_path)

    audit_path = out / "audit.json"
    audit_path.write_text(json.dumps(audit_to_jsonable(close), indent=2,
                                     default=str),
                          encoding="utf-8")
    paths["audit.json"] = str(audit_path)
    return paths
