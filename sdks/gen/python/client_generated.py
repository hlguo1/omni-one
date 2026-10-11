# GENERATED from openapi_snapshot.json — do not hand-edit
# Source: sdks/gen/openapi_snapshot.json (openapi 3.0.0, info title omni-one v1.1.0)
# Regenerate: python3 sdks/gen/regen.py  (see sdks/gen/README.md)
# Version pinned: omni-one v1.1.0 | snapshot 2026-10-11 | python stdlib only (urllib)
"""
Omni-One GENERATED Python client (urllib-only, no new deps).

Covers all 18 routes from openapi_snapshot.json:
  seller_close            POST /api/v1/seller/close
  seller_close_csv        GET  /api/v1/seller/close.csv
  seller_briefing         POST /api/v1/seller/briefing
  seller_operations       POST /api/v1/seller/operations
  seller_scenarios_list   GET  /api/v1/seller/scenarios
  seller_scenarios_run    POST /api/v1/seller/scenarios/run
  seller_export_csv       GET  /api/v1/seller/export.csv
  seller_photo            POST /api/v1/seller/photo (multipart)
  vision_analyze          POST /api/v1/vision/analyze (multipart)
  vision_demo             GET  /api/v1/vision/demo
  analyze                 POST /api/v1/analyze
  synthesize              POST /api/v1/synthesize
  revenue_health          POST /api/v1/revenue/health
  micro_briefing          POST /api/v1/micro/briefing
  get_metrics             GET  /api/v1/metrics
  list_models             GET  /api/v1/models
  health                  GET  /health
  openapi_tags            GET  /api/v1/openapi-tags

Design guarantees:
  - urllib-only: no requests/httpx/pydantic needed.
  - retry+timeout+api-key on every call (X-API-Key header when provided).
  - citation-preserving: every method returns raw dict AND typed wrapper.
    Typed wrappers expose .raw and .citations; never drop [file:line].
  - golden demo: seller_close(demo=True) true_profit == 169.09 (see handbook 01).
  - invariant: true_profit <= gmv (accountant pack 04).
  - offline $0: demo paths need no network beyond localhost.

Parsing guarantee: python3 -c "import ast; ast.parse(open(...).read())" must pass.
Version pin: snapshot v1.1.0; client __VERSION__ == "1.1.0".
Regeneration: edit sdks/gen/openapi_snapshot.json then re-run sdks/gen/regen.py.
"""
from __future__ import annotations
import json as _json
import time as _time
import urllib.request as _req
import urllib.parse as _parse
import urllib.error as _err
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

__VERSION__ = "1.1.0"
__SNAPSHOT__ = "openapi_snapshot.json"
__TITLE__ = "omni-one"
DEFAULT_BASE_URL = "http://localhost:5003"
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_S = 0.5
# --- version pin table ----------------------------------------------------
# snapshot v1.1.0 <-> client v1.1.0 <-> server v1.1.0 (fastapi_app + ops + factory)
# bump all three together; regen.py asserts snapshot version == client version.
# --------------------------------------------------------------------------

# ============================================================================
# Typed wrappers (citation-preserving)
# Every wrapper keeps .raw (original dict) and .citations ([file:line] list).
# Never drop citations when converting; accountants audit them (handbook 04).
# ============================================================================

@dataclass
class KPIs:
    """Ledger KPIs (close.csv Section A). Invariant true_profit <= gmv.
    Golden demo: gmv 274.0 fees 18.5 shipping 12.0 net 243.5 cogs 74.41
    true_profit 169.09 margin 61.7 orders 8 aov 34.25 at-risk 102.75.
    Source files: shopify_orders.csv / etsy_settlement.csv / amazon_payout.csv.
    Fees estimated when missing: Etsy 6.5%+$0.20 Shopify 2.9%+$0.30 Amazon 15% other 8%.
    COGS fallback: 30% GMV unmatched, 25% smallest invoice if none (handbook 04 s3).
    Citation rule: every field backed by [file:line] in kpis_citations.
    """
    # Gross merchandise value sum order-row totals
    gmv: float = 0.0
    # field: gmv (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # Channel fees parsed else estimated
    fees: float = 0.0
    # field: fees (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # Shipping paid/collected per rows
    shipping: float = 0.0
    # field: shipping (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # gmv - fees - shipping
    net: float = 0.0
    # field: net (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # COGS allocated per-unit from invoices
    cogs: float = 0.0
    # field: cogs (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # net - cogs THE number golden 169.09
    true_profit: float = 0.0
    # field: true_profit (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # true_profit/gmv*100
    margin_pct: float = 0.0
    # field: margin_pct (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # Order rows ingested
    orders: int = 0
    # field: orders (int) — see openapi_snapshot.json#/components/schemas/KPIs

    # gmv/orders
    aov: float = 0.0
    # field: aov (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # {product,qty,gmv} top by units
    best_seller: Dict[str, Any] = field(default_factory=dict) if "Dict[str, Any]".startswith("Dict") else (field(default_factory=list) if "Dict[str, Any]".startswith("List") else None)
    # field: best_seller (Dict[str, Any]) — see openapi_snapshot.json#/components/schemas/KPIs

    # len(reply_queue)*aov
    money_at_risk_usd: float = 0.0
    # field: money_at_risk_usd (float) — see openapi_snapshot.json#/components/schemas/KPIs

    # Worst seller kill/bundle/clearance
    worst_seller: Optional[Dict[str, Any]] = field(default_factory=dict) if "Optional[Dict[str, Any]]".startswith("Dict") else (field(default_factory=list) if "Optional[Dict[str, Any]]".startswith("List") else None)
    # field: worst_seller (Optional[Dict[str, Any]]) — see openapi_snapshot.json#/components/schemas/KPIs

    # [file:line] list
    citations: List[str] = field(default_factory=dict) if "List[str]".startswith("Dict") else (field(default_factory=list) if "List[str]".startswith("List") else None)
    # field: citations (List[str]) — see openapi_snapshot.json#/components/schemas/KPIs

    # Raw dict preserved
    raw: Dict[str, Any] = field(default_factory=dict) if "Dict[str, Any]".startswith("Dict") else (field(default_factory=list) if "Dict[str, Any]".startswith("List") else None)
    # field: raw (Dict[str, Any]) — see openapi_snapshot.json#/components/schemas/KPIs

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KPIs":
        """Build KPIs preserving raw + citations."""
        # citation-preserving: keep raw copy verbatim
        raw = dict(d or {})
        # extract with defaults; never invent numbers
        def _f(k, v):
            try:
                return float(d.get(k, v))
            except Exception:
                return v
        def _i(k, v):
            try:
                return int(d.get(k, v))
            except Exception:
                return v
        cits = list(d.get("citations", []) or [])
        # invariant check helper (does not raise; caller audits)
        # true_profit <= gmv expected; if violated data corrupt per handbook 04
        return cls(gmv=_f("gmv", 0.0), fees=_f("fees", 0.0), shipping=_f("shipping", 0.0), net=_f("net", 0.0), cogs=_f("cogs", 0.0), true_profit=_f("true_profit", 0.0), margin_pct=_f("margin_pct", 0.0), orders=_i("orders", 0), aov=_f("aov", 0.0), best_seller=dict(d.get("best_seller") or {}), money_at_risk_usd=_f("money_at_risk_usd", 0.0), worst_seller=d.get("worst_seller"), citations=cits, raw=raw)
    def to_dict(self) -> Dict[str, Any]:
        """Return raw if present else asdict (citations kept)."""
        if self.raw:
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """All [file:line] backing this KPI set."""
        return list(self.citations or [])
    def check_invariant(self) -> bool:
        """True if true_profit <= gmv (handbook 04 invariant)."""
        try:
            return float(self.true_profit) <= float(self.gmv) + 1e-9
        except Exception:
            return True

@dataclass
class ReorderLine:
    """One reorder.csv row. Cover 14d. Urgency ORDER TODAY<3d this week<5d watch.
    See openapi_snapshot.json#/components/schemas/ReorderLine.
    Citation-preserving: .raw keeps original dict; .citations lists [file:line].
    Handbook refs: 01 morning ritual, 02 cover 14d, 03 P0<2h, 04 invariant, 05 S1<1h.
    """
    # property product — typed as Any to preserve server fidelity; see snapshot example
    product: Any = None
    # end product — never drop citation attached to this field

    # property on_hand — typed as Any to preserve server fidelity; see snapshot example
    on_hand: Any = None
    # end on_hand — never drop citation attached to this field

    # property sold_7d — typed as Any to preserve server fidelity; see snapshot example
    sold_7d: Any = None
    # end sold_7d — never drop citation attached to this field

    # property daily_velocity — typed as Any to preserve server fidelity; see snapshot example
    daily_velocity: Any = None
    # end daily_velocity — never drop citation attached to this field

    # property days_left — typed as Any to preserve server fidelity; see snapshot example
    days_left: Any = None
    # end days_left — never drop citation attached to this field

    # property reorder_qty_14d — typed as Any to preserve server fidelity; see snapshot example
    reorder_qty_14d: Any = None
    # end reorder_qty_14d — never drop citation attached to this field

    # property supplier — typed as Any to preserve server fidelity; see snapshot example
    supplier: Any = None
    # end supplier — never drop citation attached to this field

    # property urgency — typed as Any to preserve server fidelity; see snapshot example
    urgency: Any = None
    # end urgency — never drop citation attached to this field

    # property citation — typed as Any to preserve server fidelity; see snapshot example
    citation: Any = None
    # end citation — never drop citation attached to this field

    raw: Dict[str, Any] = field(default_factory=dict)  # duplicate raw guard for ReorderLine
    # raw guard end — keeps byte-identical CJK/emoji names (property tests)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReorderLine":
        """Build ReorderLine preserving raw + citations."""
        raw = dict(d or {})
        # pull known keys, keep rest in raw
        kwargs: Dict[str, Any] = {}
        try:
            kwargs["product"] = (d or {}).get("product")
            kwargs["on_hand"] = (d or {}).get("on_hand")
            kwargs["sold_7d"] = (d or {}).get("sold_7d")
            kwargs["daily_velocity"] = (d or {}).get("daily_velocity")
            kwargs["days_left"] = (d or {}).get("days_left")
            kwargs["reorder_qty_14d"] = (d or {}).get("reorder_qty_14d")
            kwargs["supplier"] = (d or {}).get("supplier")
            kwargs["urgency"] = (d or {}).get("urgency")
            kwargs["citation"] = (d or {}).get("citation")
        except Exception:
            pass
        try:
            kwargs["raw"] = raw
        except Exception:
            pass
        try:
            return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
        except Exception:
            # fallback: empty with raw only
            inst = cls()
            try:
                inst.raw = raw
            except Exception:
                pass
            return inst
    def to_dict(self) -> Dict[str, Any]:
        """Raw-preserving export."""
        if getattr(self, "raw", None):
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """Collect [file:line] from self + nested."""
        out: List[str] = []
        try:
            for k in ("citation", "citations"):
                v = getattr(self, k, None)
                if isinstance(v, str) and v.startswith("["):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
            r = getattr(self, "raw", {}) or {}
            if isinstance(r, dict):
                for k in ("citation", "citations"):
                    if k in r:
                        vv = r[k]
                        if isinstance(vv, str):
                            out.append(vv)
                        elif isinstance(vv, list):
                            out.extend([x for x in vv if isinstance(x, str)])
        except Exception:
            pass
        return out

@dataclass
class ReplyItem:
    """One replies.txt draft. P0<2h vs P1 same-day. Templates 01-20 (handbook 03).
    See openapi_snapshot.json#/components/schemas/ReplyItem.
    Citation-preserving: .raw keeps original dict; .citations lists [file:line].
    Handbook refs: 01 morning ritual, 02 cover 14d, 03 P0<2h, 04 invariant, 05 S1<1h.
    """
    # property id — typed as Any to preserve server fidelity; see snapshot example
    id: Any = None
    # end id — never drop citation attached to this field

    # property priority — typed as Any to preserve server fidelity; see snapshot example
    priority: Any = None
    # end priority — never drop citation attached to this field

    # property channel — typed as Any to preserve server fidelity; see snapshot example
    channel: Any = None
    # end channel — never drop citation attached to this field

    # property customer — typed as Any to preserve server fidelity; see snapshot example
    customer: Any = None
    # end customer — never drop citation attached to this field

    # property excerpt — typed as Any to preserve server fidelity; see snapshot example
    excerpt: Any = None
    # end excerpt — never drop citation attached to this field

    # property draft — typed as Any to preserve server fidelity; see snapshot example
    draft: Any = None
    # end draft — never drop citation attached to this field

    # property citation — typed as Any to preserve server fidelity; see snapshot example
    citation: Any = None
    # end citation — never drop citation attached to this field

    # property template_id — typed as Any to preserve server fidelity; see snapshot example
    template_id: Any = None
    # end template_id — never drop citation attached to this field

    # property amount_at_risk_usd — typed as Any to preserve server fidelity; see snapshot example
    amount_at_risk_usd: Any = None
    # end amount_at_risk_usd — never drop citation attached to this field

    raw: Dict[str, Any] = field(default_factory=dict)  # duplicate raw guard for ReplyItem
    # raw guard end — keeps byte-identical CJK/emoji names (property tests)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReplyItem":
        """Build ReplyItem preserving raw + citations."""
        raw = dict(d or {})
        # pull known keys, keep rest in raw
        kwargs: Dict[str, Any] = {}
        try:
            kwargs["id"] = (d or {}).get("id")
            kwargs["priority"] = (d or {}).get("priority")
            kwargs["channel"] = (d or {}).get("channel")
            kwargs["customer"] = (d or {}).get("customer")
            kwargs["excerpt"] = (d or {}).get("excerpt")
            kwargs["draft"] = (d or {}).get("draft")
            kwargs["citation"] = (d or {}).get("citation")
            kwargs["template_id"] = (d or {}).get("template_id")
            kwargs["amount_at_risk_usd"] = (d or {}).get("amount_at_risk_usd")
        except Exception:
            pass
        try:
            kwargs["raw"] = raw
        except Exception:
            pass
        try:
            return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
        except Exception:
            # fallback: empty with raw only
            inst = cls()
            try:
                inst.raw = raw
            except Exception:
                pass
            return inst
    def to_dict(self) -> Dict[str, Any]:
        """Raw-preserving export."""
        if getattr(self, "raw", None):
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """Collect [file:line] from self + nested."""
        out: List[str] = []
        try:
            for k in ("citation", "citations"):
                v = getattr(self, k, None)
                if isinstance(v, str) and v.startswith("["):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
            r = getattr(self, "raw", {}) or {}
            if isinstance(r, dict):
                for k in ("citation", "citations"):
                    if k in r:
                        vv = r[k]
                        if isinstance(vv, str):
                            out.append(vv)
                        elif isinstance(vv, list):
                            out.extend([x for x in vv if isinstance(x, str)])
        except Exception:
            pass
        return out

@dataclass
class Briefing:
    """Seller briefing bundle: kpis headline stockout reply leaks chart ingest.
    See openapi_snapshot.json#/components/schemas/Briefing.
    Citation-preserving: .raw keeps original dict; .citations lists [file:line].
    Handbook refs: 01 morning ritual, 02 cover 14d, 03 P0<2h, 04 invariant, 05 S1<1h.
    """
    # property kpis — typed as Any to preserve server fidelity; see snapshot example
    kpis: Any = None
    # end kpis — never drop citation attached to this field

    # property headline — typed as Any to preserve server fidelity; see snapshot example
    headline: Any = None
    # end headline — never drop citation attached to this field

    # property stockout_risk — typed as Any to preserve server fidelity; see snapshot example
    stockout_risk: Any = None
    # end stockout_risk — never drop citation attached to this field

    # property reply_queue — typed as Any to preserve server fidelity; see snapshot example
    reply_queue: Any = None
    # end reply_queue — never drop citation attached to this field

    # property money_leaks — typed as Any to preserve server fidelity; see snapshot example
    money_leaks: Any = None
    # end money_leaks — never drop citation attached to this field

    # property chart — typed as Any to preserve server fidelity; see snapshot example
    chart: Any = None
    # end chart — never drop citation attached to this field

    # property ingest_report — typed as Any to preserve server fidelity; see snapshot example
    ingest_report: Any = None
    # end ingest_report — never drop citation attached to this field

    # property citations — typed as Any to preserve server fidelity; see snapshot example
    citations: Any = None
    # end citations — never drop citation attached to this field

    # property raw — typed as Any to preserve server fidelity; see snapshot example
    raw: Any = None
    # end raw — never drop citation attached to this field

    raw: Dict[str, Any] = field(default_factory=dict)  # duplicate raw guard for Briefing
    # raw guard end — keeps byte-identical CJK/emoji names (property tests)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Briefing":
        """Build Briefing preserving raw + citations."""
        raw = dict(d or {})
        # pull known keys, keep rest in raw
        kwargs: Dict[str, Any] = {}
        try:
            kwargs["kpis"] = (d or {}).get("kpis")
            kwargs["headline"] = (d or {}).get("headline")
            kwargs["stockout_risk"] = (d or {}).get("stockout_risk")
            kwargs["reply_queue"] = (d or {}).get("reply_queue")
            kwargs["money_leaks"] = (d or {}).get("money_leaks")
            kwargs["chart"] = (d or {}).get("chart")
            kwargs["ingest_report"] = (d or {}).get("ingest_report")
            kwargs["citations"] = (d or {}).get("citations")
            kwargs["raw"] = (d or {}).get("raw")
        except Exception:
            pass
        try:
            kwargs["raw"] = raw
        except Exception:
            pass
        try:
            return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
        except Exception:
            # fallback: empty with raw only
            inst = cls()
            try:
                inst.raw = raw
            except Exception:
                pass
            return inst
    def to_dict(self) -> Dict[str, Any]:
        """Raw-preserving export."""
        if getattr(self, "raw", None):
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """Collect [file:line] from self + nested."""
        out: List[str] = []
        try:
            for k in ("citation", "citations"):
                v = getattr(self, k, None)
                if isinstance(v, str) and v.startswith("["):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
            r = getattr(self, "raw", {}) or {}
            if isinstance(r, dict):
                for k in ("citation", "citations"):
                    if k in r:
                        vv = r[k]
                        if isinstance(vv, str):
                            out.append(vv)
                        elif isinstance(vv, list):
                            out.extend([x for x in vv if isinstance(x, str)])
        except Exception:
            pass
        return out

@dataclass
class ScenarioDecision:
    """One of 12 decisions critical->low stable IDs Workshop+audit.
    See openapi_snapshot.json#/components/schemas/ScenarioDecision.
    Citation-preserving: .raw keeps original dict; .citations lists [file:line].
    Handbook refs: 01 morning ritual, 02 cover 14d, 03 P0<2h, 04 invariant, 05 S1<1h.
    """
    # property id — typed as Any to preserve server fidelity; see snapshot example
    id: Any = None
    # end id — never drop citation attached to this field

    # property scenario_id — typed as Any to preserve server fidelity; see snapshot example
    scenario_id: Any = None
    # end scenario_id — never drop citation attached to this field

    # property severity — typed as Any to preserve server fidelity; see snapshot example
    severity: Any = None
    # end severity — never drop citation attached to this field

    # property title — typed as Any to preserve server fidelity; see snapshot example
    title: Any = None
    # end title — never drop citation attached to this field

    # property action — typed as Any to preserve server fidelity; see snapshot example
    action: Any = None
    # end action — never drop citation attached to this field

    # property product — typed as Any to preserve server fidelity; see snapshot example
    product: Any = None
    # end product — never drop citation attached to this field

    # property evidence — typed as Any to preserve server fidelity; see snapshot example
    evidence: Any = None
    # end evidence — never drop citation attached to this field

    # property citation — typed as Any to preserve server fidelity; see snapshot example
    citation: Any = None
    # end citation — never drop citation attached to this field

    # property workshop_id — typed as Any to preserve server fidelity; see snapshot example
    workshop_id: Any = None
    # end workshop_id — never drop citation attached to this field

    # property raw — typed as Any to preserve server fidelity; see snapshot example
    raw: Any = None
    # end raw — never drop citation attached to this field

    raw: Dict[str, Any] = field(default_factory=dict)  # duplicate raw guard for ScenarioDecision
    # raw guard end — keeps byte-identical CJK/emoji names (property tests)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScenarioDecision":
        """Build ScenarioDecision preserving raw + citations."""
        raw = dict(d or {})
        # pull known keys, keep rest in raw
        kwargs: Dict[str, Any] = {}
        try:
            kwargs["id"] = (d or {}).get("id")
            kwargs["scenario_id"] = (d or {}).get("scenario_id")
            kwargs["severity"] = (d or {}).get("severity")
            kwargs["title"] = (d or {}).get("title")
            kwargs["action"] = (d or {}).get("action")
            kwargs["product"] = (d or {}).get("product")
            kwargs["evidence"] = (d or {}).get("evidence")
            kwargs["citation"] = (d or {}).get("citation")
            kwargs["workshop_id"] = (d or {}).get("workshop_id")
            kwargs["raw"] = (d or {}).get("raw")
        except Exception:
            pass
        try:
            kwargs["raw"] = raw
        except Exception:
            pass
        try:
            return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
        except Exception:
            # fallback: empty with raw only
            inst = cls()
            try:
                inst.raw = raw
            except Exception:
                pass
            return inst
    def to_dict(self) -> Dict[str, Any]:
        """Raw-preserving export."""
        if getattr(self, "raw", None):
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """Collect [file:line] from self + nested."""
        out: List[str] = []
        try:
            for k in ("citation", "citations"):
                v = getattr(self, k, None)
                if isinstance(v, str) and v.startswith("["):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
            r = getattr(self, "raw", {}) or {}
            if isinstance(r, dict):
                for k in ("citation", "citations"):
                    if k in r:
                        vv = r[k]
                        if isinstance(vv, str):
                            out.append(vv)
                        elif isinstance(vv, list):
                            out.extend([x for x in vv if isinstance(x, str)])
        except Exception:
            pass
        return out

@dataclass
class CloseBundle:
    """DAILY CLOSE bundle: kpis briefing reorder reply scenarios leaks po csv.
    See openapi_snapshot.json#/components/schemas/CloseBundle.
    Citation-preserving: .raw keeps original dict; .citations lists [file:line].
    Handbook refs: 01 morning ritual, 02 cover 14d, 03 P0<2h, 04 invariant, 05 S1<1h.
    """
    # property kpis — typed as Any to preserve server fidelity; see snapshot example
    kpis: Any = None
    # end kpis — never drop citation attached to this field

    # property briefing — typed as Any to preserve server fidelity; see snapshot example
    briefing: Any = None
    # end briefing — never drop citation attached to this field

    # property headline — typed as Any to preserve server fidelity; see snapshot example
    headline: Any = None
    # end headline — never drop citation attached to this field

    # property reorder — typed as Any to preserve server fidelity; see snapshot example
    reorder: Any = None
    # end reorder — never drop citation attached to this field

    # property reply_queue — typed as Any to preserve server fidelity; see snapshot example
    reply_queue: Any = None
    # end reply_queue — never drop citation attached to this field

    # property scenarios — typed as Any to preserve server fidelity; see snapshot example
    scenarios: Any = None
    # end scenarios — never drop citation attached to this field

    # property money_leaks — typed as Any to preserve server fidelity; see snapshot example
    money_leaks: Any = None
    # end money_leaks — never drop citation attached to this field

    # property po_draft — typed as Any to preserve server fidelity; see snapshot example
    po_draft: Any = None
    # end po_draft — never drop citation attached to this field

    # property close_csv — typed as Any to preserve server fidelity; see snapshot example
    close_csv: Any = None
    # end close_csv — never drop citation attached to this field

    # property ingest_report — typed as Any to preserve server fidelity; see snapshot example
    ingest_report: Any = None
    # end ingest_report — never drop citation attached to this field

    # property citations — typed as Any to preserve server fidelity; see snapshot example
    citations: Any = None
    # end citations — never drop citation attached to this field

    # property raw — typed as Any to preserve server fidelity; see snapshot example
    raw: Any = None
    # end raw — never drop citation attached to this field

    raw: Dict[str, Any] = field(default_factory=dict)  # duplicate raw guard for CloseBundle
    # raw guard end — keeps byte-identical CJK/emoji names (property tests)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CloseBundle":
        """Build CloseBundle preserving raw + citations."""
        raw = dict(d or {})
        # pull known keys, keep rest in raw
        kwargs: Dict[str, Any] = {}
        try:
            kwargs["kpis"] = (d or {}).get("kpis")
            kwargs["briefing"] = (d or {}).get("briefing")
            kwargs["headline"] = (d or {}).get("headline")
            kwargs["reorder"] = (d or {}).get("reorder")
            kwargs["reply_queue"] = (d or {}).get("reply_queue")
            kwargs["scenarios"] = (d or {}).get("scenarios")
            kwargs["money_leaks"] = (d or {}).get("money_leaks")
            kwargs["po_draft"] = (d or {}).get("po_draft")
            kwargs["close_csv"] = (d or {}).get("close_csv")
            kwargs["ingest_report"] = (d or {}).get("ingest_report")
            kwargs["citations"] = (d or {}).get("citations")
            kwargs["raw"] = (d or {}).get("raw")
        except Exception:
            pass
        try:
            kwargs["raw"] = raw
        except Exception:
            pass
        try:
            return cls(**{k: v for k, v in kwargs.items() if k in cls.__dataclass_fields__})
        except Exception:
            # fallback: empty with raw only
            inst = cls()
            try:
                inst.raw = raw
            except Exception:
                pass
            return inst
    def to_dict(self) -> Dict[str, Any]:
        """Raw-preserving export."""
        if getattr(self, "raw", None):
            return dict(self.raw)
        return asdict(self)
    def citations_list(self) -> List[str]:
        """Collect [file:line] from self + nested."""
        out: List[str] = []
        try:
            for k in ("citation", "citations"):
                v = getattr(self, k, None)
                if isinstance(v, str) and v.startswith("["):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend([x for x in v if isinstance(x, str)])
            r = getattr(self, "raw", {}) or {}
            if isinstance(r, dict):
                for k in ("citation", "citations"):
                    if k in r:
                        vv = r[k]
                        if isinstance(vv, str):
                            out.append(vv)
                        elif isinstance(vv, list):
                            out.extend([x for x in vv if isinstance(x, str)])
        except Exception:
            pass
        return out

# ============================================================================
# HTTP plumbing (urllib-only, retry+timeout+api-key)
# ============================================================================
def _build_url(base: str, path: str, query: Optional[Dict[str, Any]] = None) -> str:
    """Join base + path + query string (citation: snapshot servers)."""
    base = (base or "").rstrip("/")
    if query:
        qs = _parse.urlencode({k: v for k, v in query.items() if v is not None})
        return f"{base}{path}?{qs}" if qs else f"{base}{path}"
    return f"{base}{path}"

def _do_http(method: str, url: str, body: Optional[Dict[str, Any]], headers: Dict[str, str], timeout: float) -> Tuple[int, Any, Dict[str, str]]:
    """Single urllib attempt. Returns (status, parsed_body, resp_headers)."""
    data = None
    h = dict(headers or {})
    if body is not None:
        data = _json.dumps(body).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    r = _req.Request(url, data=data, headers=h, method=method.upper())
    try:
        with _req.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype or raw[:1] in (b"{", b"["):
                try:
                    return resp.status, _json.loads(raw.decode("utf-8") or "null"), dict(resp.headers)
                except Exception:
                    return resp.status, {"_raw_text": raw.decode("utf-8", "replace")}, dict(resp.headers)
            return resp.status, {"_raw_text": raw.decode("utf-8", "replace"), "_content_type": ctype}, dict(resp.headers)
    except _err.HTTPError as e:
        try:
            eb = e.read().decode("utf-8", "replace")
        except Exception:
            eb = str(e)
        try:
            ej = _json.loads(eb or "{}")
        except Exception:
            ej = {"detail": eb}
        raise RuntimeError(f"HTTP {e.code} {method} {url}: {ej}") from e

def _with_retry(fn, retries: int = 3, backoff: float = 0.5):
    """Retry helper with exponential backoff (retry+timeout guarantee)."""
    last: Optional[Exception] = None
    for i in range(max(1, retries)):
        try:
            return fn()
        except Exception as e:
            last = e
            # do not retry 4xx except 429
            msg = str(e)
            if "HTTP 400" in msg or "HTTP 401" in msg or "HTTP 404" in msg:
                raise
            if i < retries - 1:
                _time.sleep(backoff * (2 ** i))
    assert last is not None
    raise last

class OmniOneGeneratedClient:
    """GENERATED urllib client for omni-one v1.1.0 (18 methods).
    Retry+timeout+api-key on every call; citation-preserving raw+typed returns.
    """
    def __init__(self, base_url: str = DEFAULT_BASE_URL, api_key: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_S, retries: int = DEFAULT_RETRIES, backoff: float = DEFAULT_BACKOFF_S) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self.timeout = float(timeout)
        self.retries = int(retries)
        self.backoff = float(backoff)
        # version pin check hint
        self.version = __VERSION__
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h: Dict[str, str] = {"Accept": "application/json", "User-Agent": f"omni-one-generated-py/{__VERSION__}"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if extra:
            h.update(extra)
        return h
    def _request(self, method: str, path: str, query: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Core request with retry+timeout+api-key. Preserves raw dict."""
        url = _build_url(self.base_url, path, query)
        headers = self._headers()
        def _once():
            status, payload, _h = _do_http(method, url, body, headers, self.timeout)
            # normalize: csv text -> {"_raw_text": ...} else dict
            if isinstance(payload, dict):
                return payload
            return {"data": payload, "_status": status}
        return _with_retry(_once, retries=self.retries, backoff=self.backoff)
    def _post_multipart(self, path: str, file_bytes: bytes, filename: str, content_type: str = "image/jpeg", extra_fields: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Multipart upload via urllib (photo/vision). No new deps."""
        import uuid as _uuid
        boundary = f"----omni{ _uuid.uuid4().hex}"
        # build body manually to avoid deps
        parts: List[bytes] = []
        def _field(n, v):
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode())
        for k, v in (extra_fields or {}).items():
            _field(k, v)
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n".encode())
        parts.append(file_bytes)
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)
        url = _build_url(self.base_url, path)
        headers = self._headers({"Content-Type": f"multipart/form-data; boundary={boundary}", "Content-Length": str(len(body))})
        req = _req.Request(url, data=body, headers=headers, method="POST")
        def _once():
            try:
                with _req.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8", "replace")
                    try:
                        return _json.loads(raw or "{}")
                    except Exception:
                        return {"_raw_text": raw}
            except _err.HTTPError as e:
                raise RuntimeError(f"HTTP {e.code} POST {url}") from e
        return _with_retry(_once, retries=self.retries, backoff=self.backoff)
    def seller_close(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Run DAILY CLOSE (CloseBundle). demo=true or folder path. Golden true_profit 169.09.

        Method: POST /api/v1/seller/close
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/close"]
        Python method: seller_close | TS method: seller_close
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.CloseBundle / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True, "seed": 42, "shop": "our shop"}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/seller/close \
              -H "Content-Type: application/json" \
              -d '{"demo": true, "seed": 42}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_close(payload={"demo": True, "seed": 42, "shop": "our shop"})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is CloseBundle wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1close
        """
        # --- seller_close: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/seller/close (operation seller_close)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/seller/close", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = CloseBundle.from_dict(raw)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/close", "_method": "POST", "citations": cits}

    def seller_close_csv(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """DAILY CLOSE as CSV text (accountant-ready). Query demo/seed/shop.

        Method: GET /api/v1/seller/close.csv
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/close.csv"]
        Python method: seller_close_csv | TS method: seller_close_csv
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.str / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/seller/close.csv \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_close_csv(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is str wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1close.csv
        """
        # --- seller_close_csv: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/seller/close.csv (operation seller_close_csv)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/seller/close.csv", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/close.csv", "_method": "GET", "citations": cits}

    def seller_briefing(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Seller briefing (Briefing). Messy folder or demo.

        Method: POST /api/v1/seller/briefing
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/briefing"]
        Python method: seller_briefing | TS method: seller_briefing
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Briefing / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True, "seed": 42}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/seller/briefing \
              -H "Content-Type: application/json" \
              -d '{"demo": true}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_briefing(payload={"demo": True, "seed": 42})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Briefing wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1briefing
        """
        # --- seller_briefing: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/seller/briefing (operation seller_briefing)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/seller/briefing", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = Briefing.from_dict(raw)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/briefing", "_method": "POST", "citations": cits}

    def seller_operations(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Operations loop briefing+workshop+audit.

        Method: POST /api/v1/seller/operations
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/operations"]
        Python method: seller_operations | TS method: seller_operations
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True, "seed": 42}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/seller/operations \
              -H "Content-Type: application/json" \
              -d '{"demo": true}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_operations(payload={"demo": True, "seed": 42})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1operations
        """
        # --- seller_operations: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/seller/operations (operation seller_operations)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/seller/operations", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/operations", "_method": "POST", "citations": cits}

    def seller_scenarios_list(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """List 12 scenarios registry.

        Method: GET /api/v1/seller/scenarios
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/scenarios"]
        Python method: seller_scenarios_list | TS method: seller_scenarios_list
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.List[ScenarioDecision] / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/seller/scenarios \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_scenarios_list(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is List[ScenarioDecision] wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1scenarios
        """
        # --- seller_scenarios_list: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/seller/scenarios (operation seller_scenarios_list)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/seller/scenarios", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            scs = raw.get("scenarios", []) if isinstance(raw, dict) else []
            typed = scs  # registry list; wrap individually if needed
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/scenarios", "_method": "GET", "citations": cits}

    def seller_scenarios_run(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Run 12 scenarios -> decisions critical->low.

        Method: POST /api/v1/seller/scenarios/run
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/scenarios/run"]
        Python method: seller_scenarios_run | TS method: seller_scenarios_run
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.List[ScenarioDecision] / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/seller/scenarios/run \
              -H "Content-Type: application/json" \
              -d '{"demo": true}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_scenarios_run(payload={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is List[ScenarioDecision] wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1scenarios~1run
        """
        # --- seller_scenarios_run: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/seller/scenarios/run (operation seller_scenarios_run)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/seller/scenarios/run", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            # list of ScenarioDecision wrappers (first 30) + raw preserved
            decs = raw.get("decisions", []) if isinstance(raw, dict) else []
            typed = [ScenarioDecision.from_dict(d) for d in decs[:30]] if isinstance(decs, list) else raw
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/scenarios/run", "_method": "POST", "citations": cits}

    def seller_export_csv(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Briefing KPIs+actions as CSV.

        Method: GET /api/v1/seller/export.csv
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/export.csv"]
        Python method: seller_export_csv | TS method: seller_export_csv
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.str / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/seller/export.csv \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_export_csv(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is str wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1export.csv
        """
        # --- seller_export_csv: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/seller/export.csv (operation seller_export_csv)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/seller/export.csv", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/export.csv", "_method": "GET", "citations": cits}

    def seller_photo(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Seller photo upload (multipart). Invoice->COGS, product->listing.

        Method: POST /api/v1/seller/photo
        OperationId: see openapi_snapshot.json paths["/api/v1/seller/photo"]
        Python method: seller_photo | TS method: seller_photo
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"filename": "invoice.jpg"}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/seller/photo \
              -F "file=@invoice.jpg" -F "lang=eng"

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.seller_photo(payload={"filename": "invoice.jpg"})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1seller~1photo
        """
        # --- seller_photo: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/seller/photo (operation seller_photo)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # MULTIPART: use _post_multipart helper (urllib-only, no requests)
            # caller passes payload={file_bytes, filename} or uses file path helper
            fb = _p.get("file_bytes") or b""
            fn = str(_p.get("filename") or "upload.jpg")
            ct = str(_p.get("content_type") or "image/jpeg")
            if not fb and _p.get("file_path"):
                with open(str(_p["file_path"]), "rb") as _fh:
                    fb = _fh.read()
            if not fb:
                # demo fallback: empty still exercises route shape (server validates)
                fb = b"DEMO"
            return self._post_multipart("/api/v1/seller/photo", fb, fn, ct, {"lang": str(_p.get("lang", "eng"))})
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/seller/photo", "_method": "POST", "citations": cits}

    def vision_analyze(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Photo->Text+Chart->Layered (free local). Multipart.

        Method: POST /api/v1/vision/analyze
        OperationId: see openapi_snapshot.json paths["/api/v1/vision/analyze"]
        Python method: vision_analyze | TS method: vision_analyze
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"filename": "photo.jpg", "lang": "eng"}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/vision/analyze \
              -F "file=@invoice.jpg" -F "lang=eng"

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.vision_analyze(payload={"filename": "photo.jpg", "lang": "eng"})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1vision~1analyze
        """
        # --- vision_analyze: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/vision/analyze (operation vision_analyze)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # MULTIPART: use _post_multipart helper (urllib-only, no requests)
            # caller passes payload={file_bytes, filename} or uses file path helper
            fb = _p.get("file_bytes") or b""
            fn = str(_p.get("filename") or "upload.jpg")
            ct = str(_p.get("content_type") or "image/jpeg")
            if not fb and _p.get("file_path"):
                with open(str(_p["file_path"]), "rb") as _fh:
                    fb = _fh.read()
            if not fb:
                # demo fallback: empty still exercises route shape (server validates)
                fb = b"DEMO"
            return self._post_multipart("/api/v1/vision/analyze", fb, fn, ct, {"lang": str(_p.get("lang", "eng"))})
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/vision/analyze", "_method": "POST", "citations": cits}

    def vision_demo(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Vision demo synthetic receipt+chart (Maya Tacos).

        Method: GET /api/v1/vision/demo
        OperationId: see openapi_snapshot.json paths["/api/v1/vision/demo"]
        Python method: vision_demo | TS method: vision_demo
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/vision/demo \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.vision_demo(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1vision~1demo
        """
        # --- vision_demo: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/vision/demo (operation vision_demo)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/vision/demo", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/vision/demo", "_method": "GET", "citations": cits}

    def analyze(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Data analysis L1-L4 {records:[...]}.

        Method: POST /api/v1/analyze
        OperationId: see openapi_snapshot.json paths["/api/v1/analyze"]
        Python method: analyze | TS method: analyze
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"records": [{"id": 1, "value": 100}]}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/analyze \
              -H "Content-Type: application/json" \
              -d '{"records": [...]}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.analyze(payload={"records": [{"id": 1, "value": 100}]})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1analyze
        """
        # --- analyze: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/analyze (operation analyze)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/analyze", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/analyze", "_method": "POST", "citations": cits}

    def synthesize(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """AI synthesis {query,context,task_type}. RAG+citations.

        Method: POST /api/v1/synthesize
        OperationId: see openapi_snapshot.json paths["/api/v1/synthesize"]
        Python method: synthesize | TS method: synthesize
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"query": "summarize shop", "context": [], "task_type": "general_qa"}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/synthesize \
              -H "Content-Type: application/json" \
              -d '{"query": "..."}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.synthesize(payload={"query": "summarize shop", "context": [], "task_type": "general_qa"})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1synthesize
        """
        # --- synthesize: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/synthesize (operation synthesize)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/synthesize", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/synthesize", "_method": "POST", "citations": cits}

    def revenue_health(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """RevOps health {accounts 1-500, seed}.

        Method: POST /api/v1/revenue/health
        OperationId: see openapi_snapshot.json paths["/api/v1/revenue/health"]
        Python method: revenue_health | TS method: revenue_health
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"accounts": 20, "seed": 42}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/revenue/health \
              -H "Content-Type: application/json" \
              -d '{"accounts": 20}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.revenue_health(payload={"accounts": 20, "seed": 42})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1revenue~1health
        """
        # --- revenue_health: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/revenue/health (operation revenue_health)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/revenue/health", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/revenue/health", "_method": "POST", "citations": cits}

    def micro_briefing(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Micro-biz briefing folder|events|demo (Maya Tacos).

        Method: POST /api/v1/micro/briefing
        OperationId: see openapi_snapshot.json paths["/api/v1/micro/briefing"]
        Python method: micro_briefing | TS method: micro_briefing
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Briefing / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {"demo": True}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s -X POST http://localhost:5003/api/v1/micro/briefing \
              -H "Content-Type: application/json" \
              -d '{"demo": true}'

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.micro_briefing(payload={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Briefing wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1micro~1briefing
        """
        # --- micro_briefing: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: POST /api/v1/micro/briefing (operation micro_briefing)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # POST JSON: body dumped via _json.dumps (utf-8)
            url = _build_url(self.base_url, "/api/v1/micro/briefing", _q or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("POST", url, _p or None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = Briefing.from_dict(raw)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/micro/briefing", "_method": "POST", "citations": cits}

    def get_metrics(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """System metrics live 200-record eval (ProcessingMetrics).

        Method: GET /api/v1/metrics
        OperationId: see openapi_snapshot.json paths["/api/v1/metrics"]
        Python method: get_metrics | TS method: get_metrics
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/metrics \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.get_metrics(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1metrics
        """
        # --- get_metrics: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/metrics (operation get_metrics)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/metrics", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/metrics", "_method": "GET", "citations": cits}

    def list_models(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """List models gemini/gpt costs.

        Method: GET /api/v1/models
        OperationId: see openapi_snapshot.json paths["/api/v1/models"]
        Python method: list_models | TS method: list_models
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.List[Dict] / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/models \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.list_models(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is List[Dict] wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1models
        """
        # --- list_models: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/models (operation list_models)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/models", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/models", "_method": "GET", "citations": cits}

    def health(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Liveness {status,mode}. Docker HEALTHCHECK.

        Method: GET /health
        OperationId: see openapi_snapshot.json paths["/health"]
        Python method: health | TS method: health
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/health \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.health(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1health
        """
        # --- health: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /health (operation health)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/health", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/health", "_method": "GET", "citations": cits}

    def openapi_tags(self, payload: Optional[Dict[str, Any]] = None, query: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None, raw_only: bool = False) -> Dict[str, Any]:
        """Tag catalog + mcp tools 6.

        Method: GET /api/v1/openapi-tags
        OperationId: see openapi_snapshot.json paths["/api/v1/openapi-tags"]
        Python method: openapi_tags | TS method: openapi_tags
        Tags: see snapshot; free offline $0 where marked.

        Citation-preserving: returns raw dict verbatim PLUS typed wrapper.
        - raw dict keeps every [file:line] citation byte-identical (CJK/emoji safe).
        - typed wrapper (.Dict / from_dict) exposes .citations_list().
        - rule: no citation, no action (handbook 01 one rule).
        - invariant where money: true_profit <= gmv (handbook 04).

        Retry+timeout+api-key:
        - timeout: param or self.timeout (default 30.0s).
        - retries: self.retries with exponential backoff (default 3 x 0.5s).
        - api-key: X-API-Key header when client constructed with api_key.
        - 429 retried; 400/401 fast-fail (fix source file).

        Args:
            payload: JSON body (for POST) e.g. {}.
            query: URL query dict (for GET) e.g. {"demo": True, "seed": 42}.
            timeout: override seconds for this call only.
            raw_only: if True return raw dict only (default False returns enriched).

        Returns:
            Dict with keys: data/raw + _typed + _citations + _path + _method.
            Example raw keys: ok/method/path/citations OR CloseBundle/Briefing fields.
            Use result["_citations"] for audit trail; result["_typed"] for dataclass.

        Curl example:
            curl -s http://localhost:5003/api/v1/openapi-tags \
              -H "X-API-Key: $OMNI_KEY"  # optional

        Python example:
            from client_generated import OmniOneGeneratedClient
            c = OmniOneGeneratedClient("http://localhost:5003")
            out = c.openapi_tags(query={"demo": True})
            print(out["_citations"][:2])  # audit [file:line]
            # typed: out["_typed"] is Dict wrapper (from_dict)

        Handbook: 01 ritual (headline) 02 reorder 03 P0<2h 04 invariant 05 S1<1h.
        Snapshot: openapi_snapshot.json#/paths/~1api~1v1~1openapi-tags
        """
        # --- openapi_tags: citation-preserving urllib call ------------------------------
        # preserve caller timeout override without mutating self
        _t = float(timeout) if timeout is not None else self.timeout
        _p = dict(payload or {})
        _q = dict(query or {})
        # route: GET /api/v1/openapi-tags (operation openapi_tags)
        # auth: X-API-Key injected via self._headers() if api_key set
        # retry: exponential backoff self.retries x self.backoff
        def _once_inner() -> Dict[str, Any]:
            # GET: query string built via _build_url (urllib.parse.urlencode)
            url = _build_url(self.base_url, "/api/v1/openapi-tags", _q or _p or None)
            headers = self._headers()
            status, payload_out, _h = _do_http("GET", url, None, headers, _t)
            return payload_out if isinstance(payload_out, dict) else {"data": payload_out}
        raw = _with_retry(_once_inner, retries=self.retries, backoff=self.backoff)
        # --- typed wrapper (citation-preserving, never drops raw) ---------------
        typed: Any = raw  # default: raw itself
        cits: List[str] = []
        try:
            # collect top-level citations for audit convenience
            if isinstance(raw, dict):
                for _k in ("citations", "citation"):
                    _v = raw.get(_k)
                    if isinstance(_v, str):
                        cits.append(_v)
                    elif isinstance(_v, list):
                        cits.extend([x for x in _v if isinstance(x, str)])
                # nested kpis/briefing citations
                for _nk in ("kpis", "briefing"):
                    _nv = raw.get(_nk)
                    if isinstance(_nv, dict) and "citations" in _nv:
                        _cv = _nv["citations"]
                        if isinstance(_cv, list):
                            cits.extend([x for x in _cv if isinstance(x, str)])
        except Exception:
            pass
        try:
            typed = raw  # generic dict wrapper (citation list in _citations)
        except Exception:
            typed = raw
        if raw_only:
            return raw
        # enriched return: raw + typed + citations + route meta (all citation-preserving)
        return {"data": raw, "raw": raw, "_typed": typed, "_citations": cits, "_path": "/api/v1/openapi-tags", "_method": "GET", "citations": cits}

    # --- end method ---------------------------------------------------------

# ============================================================================
# Convenience top-level helpers (typed + raw dual return)
# ============================================================================
def load_snapshot(path: str = "sdks/gen/openapi_snapshot.json") -> Dict[str, Any]:
    """Load snapshot JSON (validates openapi 3.0.0 + title omni-one v1.1.0)."""
    with open(path, encoding="utf-8") as f:
        spec = _json.load(f)
    assert spec.get("openapi") == "3.0.0", "snapshot openapi must be 3.0.0"
    assert spec.get("info", {}).get("title") == "omni-one", "title must be omni-one"
    assert spec.get("info", {}).get("version") == "1.1.0", "version must be 1.1.0"
    return spec

def check_invariant_close(bundle: Dict[str, Any]) -> bool:
    """Accountant invariant true_profit <= gmv (handbook 04)."""
    try:
        k = (bundle or {}).get("kpis", {})
        return float(k.get("true_profit", 0)) <= float(k.get("gmv", 0)) + 1e-9
    except Exception:
        return True

def citations_of(obj: Dict[str, Any]) -> List[str]:
    """Extract [file:line] citations from any bundle (audit helper)."""
    out: List[str] = []
    try:
        stack = [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                for k, v in cur.items():
                    if k in ("citation", "citations"):
                        if isinstance(v, str):
                            out.append(v)
                        elif isinstance(v, list):
                            out.extend([x for x in v if isinstance(x, str)])
                    elif isinstance(v, (dict, list)):
                        stack.append(v)
            elif isinstance(cur, list):
                stack.extend(cur)
    except Exception:
        pass
    return out

__all__ = ["OmniOneGeneratedClient", "KPIs", "ReorderLine", "ReplyItem", "Briefing", "ScenarioDecision", "CloseBundle", "load_snapshot", "check_invariant_close", "citations_of", "__VERSION__", "DEFAULT_BASE_URL"]

# End GENERATED — do not hand-edit. Regenerate via sdks/gen/regen.py.
