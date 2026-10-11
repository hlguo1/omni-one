"""
Omni-One Python SDK — $0 local-first client.
Works against live API (httpx) or in-process (no server needed).

  from omni_one.client import OmniOneClient
  c = OmniOneClient.local()          # in-process, no HTTP
  print(c.briefing_demo()["kpis"])   # GMV 274.00 / profit 169.09

  c = OmniOneClient("http://localhost:5003")
  c.briefing_demo(); c.scenarios_run(demo=True); c.health()
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


class OmniOneClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def local(cls) -> "OmniOneClient":
        c = cls(base_url="")
        c._local = True  # type: ignore
        return c

    @property
    def is_local(self) -> bool:
        return not self.base_url

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def _post(self, path: str, payload: dict) -> dict:
        import httpx
        with httpx.Client(timeout=self.timeout) as h:
            r = h.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
            r.raise_for_status()
            return r.json()

    def _get(self, path: str) -> dict:
        import httpx
        with httpx.Client(timeout=self.timeout) as h:
            r = h.get(f"{self.base_url}{path}", headers=self._headers())
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return {"text": r.text}

    # ---- Seller OS ----
    def briefing_demo(self, seed: int = 42) -> dict:
        if self.is_local:
            import tempfile
            from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
            with tempfile.TemporaryDirectory() as tmp:
                d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
                events, _ = ingest_seller_folder(d)
                return build_seller_briefing(events)
        return self._post("/api/v1/seller/briefing", {"demo": True, "seed": seed})

    def briefing_folder(self, folder: str | Path, seed: int = 42) -> dict:
        if self.is_local:
            from omni_one.packs.seller_os import ingest_seller_folder, build_seller_briefing
            events, report = ingest_seller_folder(Path(folder))
            b = build_seller_briefing(events)
            b["ingest_report"].update(report)
            return b
        return self._post("/api/v1/seller/briefing", {"folder": str(folder), "seed": seed})

    def scenarios_run(self, demo: bool = True, folder: str | None = None, seed: int = 42) -> dict:
        if self.is_local:
            import tempfile
            from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder
            from omni_one.packs.seller_scenarios import run_all_scenarios
            if demo or not folder:
                with tempfile.TemporaryDirectory() as tmp:
                    d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
                    events, _ = ingest_seller_folder(d)
                    return run_all_scenarios(events)
            from omni_one.packs.seller_os import ingest_seller_folder as _ing
            events, _ = _ing(Path(str(folder)))
            return run_all_scenarios(events)
        return self._post("/api/v1/seller/scenarios/run", {"demo": demo, "folder": folder, "seed": seed})

    def operations(self, seed: int = 42) -> dict:
        if self.is_local:
            # reuse CLI logic without printing
            import tempfile
            from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
            from omni_one.palantir_free.ontology import Ontology, ObjectTypeDef, PropertyDef, ObjectInstance
            from omni_one.palantir_free.workshop import WorkshopApp
            from omni_one.palantir_free.governance import AuditLog, ingest_workshop
            with tempfile.TemporaryDirectory() as tmp:
                d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
                events, _ = ingest_seller_folder(d)
                b = build_seller_briefing(events)
                onto = Ontology("sdk")
                onto.define_object_type(ObjectTypeDef(api_name="Product", display_name="Product",
                    primary_key="sku", title_property="name",
                    properties=[PropertyDef(name="sku", type="string", required=True)]))
                wapp = WorkshopApp(onto, "sdk")
                audit = AuditLog("sdk")
                ingest_workshop(audit, wapp)
                return {"briefing_kpis": b["kpis"], "workshop": wapp.stats(), "governance": audit.stats()}
        return self._post("/api/v1/seller/operations", {"demo": True, "seed": seed})

    def analyze(self, records: list) -> dict:
        if self.is_local:
            from omni_one.core.data_processing_pipeline import MultiLayerDataPipeline
            from omni_one.core.cache import SemanticCache
            from omni_one.core.model_router import ModelRouter
            pipe = MultiLayerDataPipeline(model_router=ModelRouter(), cache=SemanticCache())
            results, _ = pipe.process_batch(records)
            return {"records_processed": len(records), "metrics": pipe.get_metrics_summary()}
        return self._post("/api/v1/analyze", {"records": records})

    def health(self) -> dict:
        if self.is_local:
            return {"status": "alive", "mode": "local", "service": "omni-one"}
        return self._get("/health")

    def export_csv(self, demo: bool = True, folder: str | None = None, seed: int = 42) -> str:
        b = self.briefing_demo(seed) if (demo or not folder) else self.briefing_folder(str(folder), seed)
        from omni_one.packs.seller_export import briefing_to_csv
        return briefing_to_csv(b)

    def close(self, demo: bool = True, folder: str | None = None, seed: int = 42,
              shop: str = "our shop", locale: str = "en") -> dict:
        """Daily Close bundle (profit, reorder+PO, reply drafts, leaks). Local or HTTP."""
        if self.is_local:
            import tempfile
            from omni_one.packs.seller_os import make_seller_demo_folder, ingest_seller_folder, build_seller_briefing
            from omni_one.packs.seller_scenarios import run_all_scenarios
            from omni_one.packs.seller_close import build_daily_close
            if demo or not folder:
                with tempfile.TemporaryDirectory() as tmp:
                    d = make_seller_demo_folder(Path(tmp) / "d", seed=seed)
                    events, _ = ingest_seller_folder(d)
                    b = build_seller_briefing(events)
                    scen = run_all_scenarios(events)
                    return build_daily_close(events, b, scen, shop=shop, locale=locale)
            from omni_one.packs.seller_os import ingest_seller_folder as _ing, build_seller_briefing as _b
            events, _ = _ing(Path(str(folder)))
            b = _b(events)
            scen = run_all_scenarios(events)
            return build_daily_close(events, b, scen, shop=shop, locale=locale)
        return self._post("/api/v1/seller/close", {"demo": demo, "folder": folder, "seed": seed, "shop": shop, "locale": locale})
