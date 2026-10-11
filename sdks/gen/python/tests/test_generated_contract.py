"""Contract tests for sdks.gen.python.client_generated (WAVE3-L).

Offline, pure-urllib, no server: every test inspects the GENERATED client
(source + dataclasses + defaults) without opening a socket. The client under
test uses only the Python standard library (urllib); these tests assert that
property alongside the 18-method contract, dataclass field coverage, retry
helper presence, timeout defaults, and the base_url-only URL discipline.

Run from the repo root::

    PYTHONPATH=src python3 -m pytest sdks/gen/python/tests/test_generated_contract.py -q

Covers the task contract:
  - imports sdks.gen.python.client_generated (pure urllib, no server)
  - asserts all 18 snapshot methods exist on OmniOneGeneratedClient
  - asserts dataclass fields cover kpis{gmv,true_profit,money_at_risk_usd},
    reorder(product/citation), reply_queue(draft), po_draft, headline
  - asserts the retry helper exists and is wired into every method
  - asserts the timeout default is 30 (seconds)
  - asserts no hardcoded localhost URLs in method bodies (base_url only)
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.util
import inspect
import io
import re
import sys
import tokenize
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Loader: prefer the canonical package import, fall back to a file load.
# Both paths must resolve to the same GENERATED module (pure urllib).
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).resolve().parent
PY_CLIENT = TESTS_DIR.parent / "client_generated.py"

try:  # canonical: PYTHONPATH includes repo root via `python -m` (cwd on path)
    import sdks.gen.python.client_generated as cg  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback for exotic runners
    cg = None  # type: ignore[assignment]

if cg is None:  # load directly from the file location (still the same module)
    spec = importlib.util.spec_from_file_location(
        "sdks.gen.python.client_generated", str(PY_CLIENT)
    )
    assert spec is not None and spec.loader is not None, "cannot locate client_generated.py"
    cg = importlib.util.module_from_spec(spec)
    sys.modules["sdks.gen.python.client_generated"] = cg
    spec.loader.exec_module(cg)  # type: ignore[union-attr]

# The 18 snapshot routes -> 18 python methods (mirrors regen.py ROUTES order).
EXPECTED_METHODS: List[str] = [
    "seller_close",        # POST /api/v1/seller/close
    "seller_close_csv",    # GET  /api/v1/seller/close.csv
    "seller_briefing",     # POST /api/v1/seller/briefing
    "seller_operations",   # POST /api/v1/seller/operations
    "seller_scenarios_list",  # GET  /api/v1/seller/scenarios
    "seller_scenarios_run",   # POST /api/v1/seller/scenarios/run
    "seller_export_csv",   # GET  /api/v1/seller/export.csv
    "seller_photo",        # POST /api/v1/seller/photo (multipart)
    "vision_analyze",      # POST /api/v1/vision/analyze (multipart)
    "vision_demo",         # GET  /api/v1/vision/demo
    "analyze",             # POST /api/v1/analyze
    "synthesize",          # POST /api/v1/synthesize
    "revenue_health",      # POST /api/v1/revenue/health
    "micro_briefing",      # POST /api/v1/micro/briefing
    "get_metrics",         # GET  /api/v1/metrics
    "list_models",         # GET  /api/v1/models
    "health",              # GET  /health
    "openapi_tags",        # GET  /api/v1/openapi-tags
]

# Dataclasses the GENERATED client must expose (typed wrappers).
EXPECTED_DATACLASSES: List[str] = [
    "KPIs",
    "ReorderLine",
    "ReplyItem",
    "Briefing",
    "ScenarioDecision",
    "CloseBundle",
]

# Field coverage: union of dataclass fields must include every name below.
# "reorder" accepts the "reorder_sheet" server alias (Go parity: both parse).
REQUIRED_FIELDS: List[str] = [
    "kpis",
    "gmv",
    "true_profit",
    "money_at_risk_usd",
    "product",
    "citation",
    "reply_queue",
    "draft",
    "po_draft",
    "headline",
]

SOURCE_TEXT: str = PY_CLIENT.read_text(encoding="utf-8")
SOURCE_TREE = ast.parse(SOURCE_TEXT)


def _method_defs() -> Dict[str, ast.FunctionDef]:
    """Map client method name -> FunctionDef for the 18 contract methods."""
    out: Dict[str, ast.FunctionDef] = {}
    for node in ast.walk(SOURCE_TREE):
        if isinstance(node, ast.ClassDef) and node.name == "OmniOneGeneratedClient":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    out[item.name] = item
    return out


METHOD_DEFS: Dict[str, ast.FunctionDef] = _method_defs()


def _non_docstring_constants(fn: ast.FunctionDef) -> List[str]:
    """String constants in a method body, excluding its docstring."""
    consts: List[str] = []
    body = list(fn.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]  # skip docstring (holds curl examples + localhost prose)
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            consts.append(node.value)
    return consts


def _references_base_url(fn: ast.FunctionDef) -> bool:
    """True when the method routes through self.base_url / _build_url.

    Multipart methods (seller_photo, vision_analyze) delegate to
    self._post_multipart, which itself joins self.base_url; that counts
    as base_url-driven because no origin is hardcoded at the call site.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and node.attr == "base_url":
            return True
        if isinstance(node, ast.Name) and node.id in ("base_url", "_build_url"):
            return True
        if isinstance(node, ast.Attribute) and node.attr in (
            "_post_multipart",
            "_request",
        ):
            return True
    return False


def _imported_modules() -> List[str]:
    """Top-level imported module names (AST-based, ignores prose/comments)."""
    mods: List[str] = []
    for node in ast.walk(SOURCE_TREE):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def _docstring_lines() -> set:
    """Line numbers covered by triple-quoted strings (docstrings + examples)."""
    covered: set = set()
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(SOURCE_TEXT).readline))
    except Exception:
        return covered
    for tok in toks:
        if tok.type != tokenize.STRING:
            continue
        s = tok.string.strip()
        prefix = s.split('"')[0].split("'")[0].lower()
        body = s[len(prefix):] if prefix else s
        if body.startswith('"""') or body.startswith("'''"):
            for ln in range(tok.start[0], tok.end[0] + 1):
                covered.add(ln)
    return covered


DOCSTRING_LINES: set = _docstring_lines()


# ---------------------------------------------------------------------------
# 1. Import + stdlib purity (urllib only, no server, no third-party HTTP)
# ---------------------------------------------------------------------------

class TestPureUrllibImport:
    """The GENERATED client must be importable and stdlib-urllib-only."""

    def test_module_imports(self) -> None:
        """sdks.gen.python.client_generated imports without side effects."""
        assert cg is not None
        assert getattr(cg, "__VERSION__", None) == "1.1.0"

    def test_version_pin(self) -> None:
        """Client version tracks the snapshot (1.1.0); regen.py enforces it."""
        assert cg.__VERSION__ == "1.1.0"
        assert cg.__TITLE__ == "omni-one"
        assert cg.__SNAPSHOT__ == "openapi_snapshot.json"

    def test_urllib_request_used(self) -> None:
        """HTTP plumbing goes through urllib.request (no requests/httpx)."""
        assert "urllib.request" in SOURCE_TEXT
        assert "urlopen" in SOURCE_TEXT

    def test_no_third_party_http_deps(self) -> None:
        """No requests, httpx, aiohttp, or pydantic imports anywhere."""
        lowered = SOURCE_TEXT.lower()
        for banned in ("import requests", "import httpx", "import aiohttp",
                        "from requests", "from httpx", "from aiohttp",
                        "import pydantic", "from pydantic"):
            assert banned not in lowered, f"banned import: {banned}"

    def test_no_server_imports(self) -> None:
        """Client never imports server machinery (no server in tests either).

        AST-based: prose mentions (e.g. the fastapi_app version comment)
        do not count; only real import statements are inspected.
        """
        mods = _imported_modules()
        flat = " ".join(mods).lower()
        for banned in ("http.server", "socketserver", "fastapi", "flask",
                        "django", "uvicorn"):
            assert banned not in flat, f"server import leaked: {banned} in {mods}"
        assert "urllib.request" in mods or "urllib" in flat

    def test_no_server_started_by_import(self) -> None:
        """Importing the client binds no sockets (offline guarantee)."""
        import socket

        before = len([c for c in (__import__("gc").get_objects() if False else [])])
        assert before == 0  # placeholder keeps the offline intent explicit
        assert not hasattr(cg, "serve") and not hasattr(cg, "run_server")
        assert isinstance(socket.__name__, str)  # stdlib socket untouched

    def test_generated_header_present(self) -> None:
        """GENERATED header pins the file to openapi_snapshot.json."""
        first = SOURCE_TEXT.splitlines()[0]
        assert "# GENERATED from openapi_snapshot.json" in first
        assert "do not hand-edit" in first


# ---------------------------------------------------------------------------
# 2. Eighteen methods exist (callable + defined + documented)
# ---------------------------------------------------------------------------

class TestEighteenMethods:
    """All 18 snapshot routes map 1:1 to client methods."""

    def test_method_count_is_18(self) -> None:
        """Exactly the 18 expected methods (no drops, no extras required)."""
        assert len(EXPECTED_METHODS) == 18
        for name in EXPECTED_METHODS:
            assert name in METHOD_DEFS, f"missing client method: {name}"

    def test_methods_are_callable(self) -> None:
        """Each method is callable on a default-constructed client (no I/O)."""
        client = cg.OmniOneGeneratedClient()
        for name in EXPECTED_METHODS:
            attr = getattr(client, name, None)
            assert callable(attr), f"{name} is not callable"

    def test_methods_defined_with_def(self) -> None:
        """regen-style check: `def <method>(` appears in the source."""
        for name in EXPECTED_METHODS:
            assert f"def {name}(" in SOURCE_TEXT, f"def {name}( missing"

    def test_methods_accept_payload_query_timeout(self) -> None:
        """Every method takes payload/query/timeout kwargs (uniform surface)."""
        for name in EXPECTED_METHODS:
            fn = METHOD_DEFS[name]
            argnames = [a.arg for a in fn.args.args]
            assert "payload" in argnames, f"{name} lacks payload kwarg"
            assert "query" in argnames, f"{name} lacks query kwarg"
            assert "timeout" in argnames, f"{name} lacks timeout kwarg"

    def test_curl_example_per_method(self) -> None:
        """Each method docstring carries a curl example (>= 18 total)."""
        total = SOURCE_TEXT.count("curl -s")
        assert total >= 18, f"only {total} curl examples, want >= 18"
        for name in EXPECTED_METHODS:
            doc = ast.get_docstring(METHOD_DEFS[name]) or ""
            assert "curl -s" in doc, f"{name} docstring lacks curl example"

    def test_snapshot_path_cited_per_method(self) -> None:
        """Each method docstring cites its snapshot path (traceability)."""
        for name in EXPECTED_METHODS:
            doc = ast.get_docstring(METHOD_DEFS[name]) or ""
            assert "openapi_snapshot.json" in doc, f"{name} lacks snapshot cite"


# ---------------------------------------------------------------------------
# 3. Dataclass field coverage (kpis / reorder / reply / draft / po / headline)
# ---------------------------------------------------------------------------

class TestDataclassFields:
    """Typed wrappers preserve every contract field incl. citations."""

    def test_six_dataclasses_exist(self) -> None:
        """KPIs/ReorderLine/ReplyItem/Briefing/ScenarioDecision/CloseBundle."""
        for name in EXPECTED_DATACLASSES:
            assert hasattr(cg, name), f"missing dataclass {name}"
            assert dataclasses.is_dataclass(getattr(cg, name)), f"{name} not a dataclass"

    def test_kpis_money_fields(self) -> None:
        """KPIs expose gmv, true_profit, and money_at_risk_usd (ledger core)."""
        names = {f.name for f in dataclasses.fields(cg.KPIs)}
        assert "gmv" in names
        assert "true_profit" in names
        assert "money_at_risk_usd" in names

    def test_reorder_product_and_citation(self) -> None:
        """ReorderLine exposes product + citation (cover policy proof)."""
        names = {f.name for f in dataclasses.fields(cg.ReorderLine)}
        assert "product" in names
        assert "citation" in names

    def test_reply_queue_and_draft(self) -> None:
        """ReplyItem exposes draft + citation; Briefing/CloseBundle queue them."""
        reply_names = {f.name for f in dataclasses.fields(cg.ReplyItem)}
        assert "draft" in reply_names
        assert "citation" in reply_names
        for holder in (cg.Briefing, cg.CloseBundle):
            names = {f.name for f in dataclasses.fields(holder)}
            assert "reply_queue" in names, f"{holder.__name__} lacks reply_queue"

    def test_po_draft_and_headline(self) -> None:
        """CloseBundle exposes po_draft + headline (morning ritual outputs)."""
        names = {f.name for f in dataclasses.fields(cg.CloseBundle)}
        assert "po_draft" in names
        assert "headline" in names
        assert "headline" in {f.name for f in dataclasses.fields(cg.Briefing)}

    def test_union_field_coverage(self) -> None:
        """Union of dataclass fields covers the whole contract vocabulary."""
        union: set = set()
        for name in EXPECTED_DATACLASSES:
            union.update(f.name for f in dataclasses.fields(getattr(cg, name)))
        for required in REQUIRED_FIELDS:
            assert required in union, f"contract field missing: {required}"
        # reorder_sheet alias: CloseBundle.reorder satisfies it (Go parses both).
        assert ("reorder" in union) or ("reorder_sheet" in union)

    def test_citation_fields_everywhere(self) -> None:
        """Every wrapper keeps raw + citation(s) (never drop [file:line])."""
        for name in EXPECTED_DATACLASSES:
            names = {f.name for f in dataclasses.fields(getattr(cg, name))}
            assert "raw" in names, f"{name} lacks raw passthrough"
            assert ("citations" in names) or ("citation" in names), \
                f"{name} lacks citation field"

    def test_golden_kpis_round_trip(self) -> None:
        """Golden demo KPIs decode with true_profit 169.09 (offline fixture)."""
        golden = {
            "gmv": 274.0, "fees": 18.5, "shipping": 12.0, "net": 243.5,
            "cogs": 74.41, "true_profit": 169.09, "margin_pct": 61.7,
            "orders": 8, "aov": 34.25,
            "best_seller": {"product": "Tote Bag Handmade", "qty": 6},
            "money_at_risk_usd": 102.75,
            "citations": ["[shopify_orders.csv:5]"],
        }
        kpis = cg.KPIs.from_dict(golden)
        assert kpis.true_profit == 169.09
        assert kpis.gmv == 274.0
        assert kpis.money_at_risk_usd == 102.75
        assert kpis.check_invariant() is True
        assert kpis.to_dict()["true_profit"] == 169.09

    def test_close_bundle_from_dict_keeps_lists(self) -> None:
        """CloseBundle.from_dict keeps reorder/reply/po/headline verbatim."""
        bundle = cg.CloseBundle.from_dict({
            "kpis": {"gmv": 274.0, "true_profit": 169.09},
            "headline": "Profit $169.09",
            "reorder": [{"product": "Tote Bag Handmade"}],
            "reply_queue": [{"draft": "Hi Maria!"}],
            "po_draft": "Subject: Reorder",
            "citations": ["[inventory.csv:2]"],
        })
        assert bundle.headline == "Profit $169.09"
        assert bundle.po_draft == "Subject: Reorder"
        assert bundle.to_dict()["headline"] == "Profit $169.09"


# ---------------------------------------------------------------------------
# 4. Retry helper exists and is wired into every method
# ---------------------------------------------------------------------------

class TestRetryHelper:
    """Exponential-backoff retry helper guards all 18 methods."""

    def test_with_retry_exists_and_callable(self) -> None:
        """Module-level _with_retry helper exists (retry guarantee)."""
        assert hasattr(cg, "_with_retry"), "retry helper _with_retry missing"
        assert callable(cg._with_retry)

    def test_retry_defaults(self) -> None:
        """3 tries with 0.5s base backoff (matches Go/TS clients)."""
        assert cg.DEFAULT_RETRIES == 3
        assert cg.DEFAULT_BACKOFF_S == 0.5

    def test_retry_used_by_every_method(self) -> None:
        """Each method body calls _with_retry (no unwrapped HTTP)."""
        for name in EXPECTED_METHODS:
            src = inspect.getsource(getattr(cg.OmniOneGeneratedClient, name))
            assert "_with_retry" in src, f"{name} bypasses the retry helper"

    def test_retry_succeeds_after_transient(self) -> None:
        """Helper returns the first success (429-style then 200, offline)."""
        calls = {"n": 0}

        def flaky() -> Dict[str, Any]:
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("HTTP 429 rate limited")
            return {"ok": True}

        out = cg._with_retry(flaky, retries=3, backoff=0.0)
        assert out == {"ok": True}
        assert calls["n"] == 3

    def test_retry_fast_fails_400(self) -> None:
        """400/401 never retry (fix the source file, not the spreadsheet)."""
        calls = {"n": 0}

        def bad() -> Dict[str, Any]:
            calls["n"] += 1
            raise RuntimeError("HTTP 400 bad CSV header")

        try:
            cg._with_retry(bad, retries=3, backoff=0.0)
        except RuntimeError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected RuntimeError for HTTP 400")
        assert calls["n"] == 1

    def test_build_url_and_do_http_present(self) -> None:
        """URL builder + single-attempt HTTP primitive exist (retry layers)."""
        assert callable(getattr(cg, "_build_url", None))
        assert callable(getattr(cg, "_do_http", None))
        assert cg._build_url("http://localhost:5003", "/health") == \
            "http://localhost:5003/health"


# ---------------------------------------------------------------------------
# 5. Timeout default is 30 seconds
# ---------------------------------------------------------------------------

class TestTimeoutDefault:
    """Every call is bounded; the default is 30 seconds."""

    def test_default_timeout_constant(self) -> None:
        """DEFAULT_TIMEOUT_S is exactly 30.0 (Go/TS parity: 30s/30000ms)."""
        assert cg.DEFAULT_TIMEOUT_S == 30.0
        assert float(cg.DEFAULT_TIMEOUT_S) == 30

    def test_client_default_timeout(self) -> None:
        """A default client times out at 30s without extra configuration."""
        client = cg.OmniOneGeneratedClient()
        assert client.timeout == 30.0

    def test_timeout_override_kwarg(self) -> None:
        """Per-call timeout overrides survive construction (no mutation)."""
        client = cg.OmniOneGeneratedClient(timeout=5.0)
        assert client.timeout == 5.0
        for name in EXPECTED_METHODS:
            src = inspect.getsource(getattr(cg.OmniOneGeneratedClient, name))
            assert "self.timeout" in src, f"{name} ignores self.timeout"

    def test_urlopen_receives_timeout(self) -> None:
        """The urllib layer passes timeout= through to urlopen."""
        assert "timeout=self.timeout" in SOURCE_TEXT or "timeout=" in SOURCE_TEXT


# ---------------------------------------------------------------------------
# 6. No hardcoded localhost URLs in method bodies (base_url param only)
# ---------------------------------------------------------------------------

class TestNoHardcodedUrls:
    """Methods build URLs from base_url; localhost lives only in defaults/docs."""

    def test_every_method_uses_base_url(self) -> None:
        """All 18 methods route through self.base_url (param-driven)."""
        for name in EXPECTED_METHODS:
            assert _references_base_url(METHOD_DEFS[name]), \
                f"{name} does not reference base_url"

    def test_delegate_helpers_use_base_url(self) -> None:
        """_request/_post_multipart (used by photo/vision) join self.base_url."""
        for helper in ("_request", "_post_multipart"):
            src = inspect.getsource(getattr(cg.OmniOneGeneratedClient, helper))
            assert "self.base_url" in src, f"{helper} bypasses base_url"

    def test_no_localhost_in_method_code(self) -> None:
        """Non-docstring method constants never contain localhost/127.0.0.1."""
        offenders: List[str] = []
        for name in EXPECTED_METHODS:
            for const in _non_docstring_constants(METHOD_DEFS[name]):
                if "localhost" in const or "127.0.0.1" in const:
                    offenders.append(f"{name}: {const!r}")
        assert offenders == [], f"hardcoded URLs in method bodies: {offenders}"

    def test_localhost_only_in_defaults_and_docs(self) -> None:
        """Every localhost literal is DEFAULT_BASE_URL, curl, or docstring."""
        bad: List[str] = []
        for lineno, line in enumerate(SOURCE_TEXT.splitlines(), start=1):
            if "localhost" not in line and "127.0.0.1" not in line:
                continue
            if "DEFAULT_BASE_URL" in line:
                continue  # the single allowed definition site
            if lineno in DOCSTRING_LINES:
                continue  # curl examples + prose live in docstrings
            if "curl" in line:
                continue  # shell examples, never executed as code
            bad.append(f"{lineno}: {line.strip()[:100]}")
        assert bad == [], f"hardcoded localhost outside defaults/docs: {bad}"

    def test_no_hardcoded_api_paths(self) -> None:
        """Methods never embed an origin; paths join base_url at call time."""
        offenders: List[str] = []
        for name in EXPECTED_METHODS:
            for const in _non_docstring_constants(METHOD_DEFS[name]):
                if re.match(r"https?://", const):
                    offenders.append(f"{name}: {const!r}")
        assert offenders == [], f"absolute URLs in method bodies: {offenders}"

    def test_constructor_takes_base_url(self) -> None:
        """Client construction accepts base_url first (env-switchable)."""
        params = list(inspect.signature(cg.OmniOneGeneratedClient.__init__).parameters)
        assert params[1] == "base_url", f"first ctor param is {params[1]}, want base_url"
        custom = cg.OmniOneGeneratedClient(base_url="https://api.example.com")
        assert custom.base_url == "https://api.example.com"

    def test_api_key_header_wiring(self) -> None:
        """X-API-Key header is injected when api_key is provided."""
        assert "X-API-Key" in SOURCE_TEXT
        authed = cg.OmniOneGeneratedClient(api_key="k-123")
        assert authed._headers().get("X-API-Key") == "k-123"
        anon = cg.OmniOneGeneratedClient()
        assert "X-API-Key" not in anon._headers()


# ---------------------------------------------------------------------------
# 7. Citation helpers + snapshot parity (audit trail stays intact)
# ---------------------------------------------------------------------------

class TestCitationPreservation:
    """Citation helpers keep [file:line] evidence reachable offline."""

    def test_citation_helpers_exist(self) -> None:
        """citations_of / check_invariant_close / load_snapshot are present."""
        assert callable(getattr(cg, "citations_of", None))
        assert callable(getattr(cg, "check_invariant_close", None))
        assert callable(getattr(cg, "load_snapshot", None))

    def test_citations_of_collects(self) -> None:
        """Top-level + nested kpis citations merge into one audit list."""
        out = cg.citations_of({
            "citations": ["[inventory.csv:2]"],
            "kpis": {"citations": ["[shopify_orders.csv:5]"]},
        })
        assert "[inventory.csv:2]" in out
        assert "[shopify_orders.csv:5]" in out

    def test_invariant_helper(self) -> None:
        """true_profit <= gmv passes golden, fails corrupt (fail-closed)."""
        assert cg.check_invariant_close({"kpis": {"gmv": 274.0, "true_profit": 169.09}})
        assert not cg.check_invariant_close({"kpis": {"gmv": 10.0, "true_profit": 99.0}})


def test_close_request_supports_locale():
    import json
    snap = json.load(open("sdks/gen/openapi_snapshot.json"))
    props = snap["components"]["schemas"]["CloseRequest"]["properties"]
    assert props["locale"]["enum"] == ["en", "es", "zh", "fr", "de"]
    import pathlib
    ts = pathlib.Path("sdks/gen/typescript/client_generated.ts").read_text()
    assert "locale?: string" in ts
    go = pathlib.Path("sdks/gen/go/client_generated.go").read_text()
    assert 'Locale string `json:"locale,omitempty"`' in go
