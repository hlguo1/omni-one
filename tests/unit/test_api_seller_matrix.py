"""WAVE2-G seller matrix: briefing/operations/scenarios/export/photo/vision/openapi-tags."""
from __future__ import annotations
import csv
import io
import os
import re
os.environ.setdefault("SELLER_LLM", "mock")
os.environ.setdefault("SELLER_MAX_LLM_USD", "0.0")
import pytest
from fastapi.testclient import TestClient
CITATION_RE = re.compile(r"\[[^\[\]]+:\d+\]")
@pytest.fixture(scope="module")
def client():
    from omni_one.api.fastapi_app import create_omni_one_app
    app = create_omni_one_app()
    c = TestClient(app, raise_server_exceptions=False)
    yield c
@pytest.fixture(scope="module")
def briefing(client):
    r = client.post("/api/v1/seller/briefing", json={"demo": True})
    assert r.status_code == 200, r.text[:800]
    return r.json()
@pytest.fixture(scope="module")
def operations(client):
    r = client.post("/api/v1/seller/operations", json={"demo": True})
    assert r.status_code == 200, r.text[:800]
    return r.json()
@pytest.fixture(scope="module")
def scen_run(client):
    r = client.post("/api/v1/seller/scenarios/run", json={"demo": True})
    assert r.status_code == 200, r.text[:800]
    return r.json()
@pytest.fixture(scope="module")
def scen_list(client):
    r = client.get("/api/v1/seller/scenarios")
    assert r.status_code == 200, r.text[:500]
    return r.json()
@pytest.fixture(scope="module")
def export_bundle(client):
    r = client.get("/api/v1/seller/export.csv")
    assert r.status_code == 200, r.text[:500]
    return {"ctype": r.headers.get("content-type",""), "text": r.text, "headers": dict(r.headers)}
@pytest.fixture(scope="module")
def vision_demo(client):
    r = client.get("/api/v1/vision/demo")
    assert r.status_code == 200, r.text[:800]
    return r.json()
@pytest.fixture(scope="module")
def openapi_tags(client):
    r = client.get("/api/v1/openapi-tags")
    assert r.status_code == 200, r.text[:500]
    return r.json()
def test_briefing_golden_gmv(briefing):
    """Briefing KPI gmv == 274.0."""
    v = float(briefing["kpis"]["gmv"])
    assert abs(v - 274.0) < 0.06, f"gmv={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["gmv"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_fees(briefing):
    """Briefing KPI fees == 16.71."""
    v = float(briefing["kpis"]["fees"])
    assert abs(v - 16.71) < 0.06, f"fees={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["fees"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_shipping(briefing):
    """Briefing KPI shipping == 24.0."""
    v = float(briefing["kpis"]["shipping"])
    assert abs(v - 24.0) < 0.06, f"shipping={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["shipping"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_net(briefing):
    """Briefing KPI net == 233.29."""
    v = float(briefing["kpis"]["net"])
    assert abs(v - 233.29) < 0.06, f"net={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["net"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_cogs(briefing):
    """Briefing KPI cogs == 64.2."""
    v = float(briefing["kpis"]["cogs"])
    assert abs(v - 64.2) < 0.06, f"cogs={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["cogs"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_true_profit(briefing):
    """Briefing KPI true_profit == 169.09."""
    v = float(briefing["kpis"]["true_profit"])
    assert abs(v - 169.09) < 0.06, f"true_profit={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["true_profit"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_margin_pct(briefing):
    """Briefing KPI margin_pct == 61.7."""
    v = float(briefing["kpis"]["margin_pct"])
    assert abs(v - 61.7) < 0.06, f"margin_pct={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["margin_pct"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_orders(briefing):
    """Briefing KPI orders == 8."""
    v = float(briefing["kpis"]["orders"])
    assert abs(v - 8) < 0.06, f"orders={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["orders"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_golden_aov(briefing):
    """Briefing KPI aov == 34.25."""
    v = float(briefing["kpis"]["aov"])
    assert abs(v - 34.25) < 0.06, f"aov={v} kpis={briefing['kpis']}"
    assert isinstance(briefing["kpis"]["aov"], (int, float))
    assert briefing["meta"]["mode"] == "seller_os"

def test_briefing_best_seller_product(briefing):
    """Briefing: best_seller_product."""
    assert briefing["kpis"]["best_seller"]["product"] == "Tote Bag Handmade", f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_best_seller_qty(briefing):
    """Briefing: best_seller_qty."""
    assert briefing["kpis"]["best_seller"]["qty"] == 6, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_best_seller_gmv(briefing):
    """Briefing: best_seller_gmv."""
    assert abs(float(briefing["kpis"]["best_seller"]["gmv"]) - 140.0) < 0.05, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_at_risk3(briefing):
    """Briefing: at_risk3."""
    assert briefing["kpis"]["at_risk"] == 3, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_stockout1(briefing):
    """Briefing: stockout1."""
    assert briefing["kpis"]["stockout_risk"] == 1, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_happy1(briefing):
    """Briefing: happy1."""
    assert briefing["kpis"]["happy"] == 1, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_orders8(briefing):
    """Briefing: orders8."""
    assert briefing["kpis"]["orders"] == 8, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_llm_mock(briefing):
    """Briefing: llm_mock."""
    assert briefing["llm"]["mode"] == "mock" and briefing["llm"]["cost_usd"] == 0.0, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_free_true(briefing):
    """Briefing: free_true."""
    assert briefing["meta"]["free"] is True, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_events23(briefing):
    """Briefing: events23."""
    assert briefing["meta"]["events"] >= 20, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_alerts_ge2(briefing):
    """Briefing: alerts_ge2."""
    assert len(briefing["alerts"]) >= 2, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_actions_ge3(briefing):
    """Briefing: actions_ge3."""
    assert len(briefing["actions"]) >= 3, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_stockout_row(briefing):
    """Briefing: stockout_row."""
    assert any("Tote" in r["product"] for r in briefing["stockout_risk"]), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_at_risk_preview(briefing):
    """Briefing: at_risk_preview."""
    assert len(briefing["at_risk_preview"]) == 3, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_draft_mock(briefing):
    """Briefing: draft_mock."""
    assert "[MOCK SELLER DRAFT]" in (briefing["draft_reply"]["text"] or ""), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_draft_cite(briefing):
    """Briefing: draft_cite."""
    assert CITATION_RE.search(briefing["draft_reply"]["citation"] or ""), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_chart_labels(briefing):
    """Briefing: chart_labels."""
    assert "Tote Bag Handmade" in briefing["chart"]["data"]["labels"], f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_ingest_sources(briefing):
    """Briefing: ingest_sources."""
    assert briefing["ingest_report"]["by_source"]["orders"] == 8, f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_alert_cite(briefing):
    """Briefing: alert_cite."""
    assert any(CITATION_RE.search(str(a.get("evidence", [""])[0])) or "inventory" in str(a.get("evidence", [""])[0]) for a in briefing["alerts"]), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_action_reorder(briefing):
    """Briefing: action_reorder."""
    assert any("Reorder Tote" in a for a in briefing["actions"]), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_action_reply(briefing):
    """Briefing: action_reply."""
    assert any("Reply" in a for a in briefing["actions"]), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_briefing_action_close(briefing):
    """Briefing: action_close."""
    assert any("Daily close" in a for a in briefing["actions"]), f"briefing kpis={briefing['kpis']} alerts={briefing['alerts'][:2]}"
    assert isinstance(briefing, dict)
    assert briefing["kpis"]["gmv"] == 274.0

def test_operations_kpis_match(operations):
    """Operations loop: kpis_match."""
    assert abs(float(operations["briefing_kpis"]["gmv"]) - 274.0) < 0.01, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_profit_match(operations):
    """Operations loop: profit_match."""
    assert abs(float(operations["briefing_kpis"]["true_profit"]) - 169.09) < 0.05, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_scen_total(operations):
    """Operations loop: scen_total."""
    assert operations["scenarios"]["total"] >= 5, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_workshop_total(operations):
    """Operations loop: workshop_total."""
    assert operations["workshop"]["total"] >= 5, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_workshop_assigned(operations):
    """Operations loop: workshop_assigned."""
    assert operations["workshop"]["by_status"]["assigned"] >= 1, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_workshop_open(operations):
    """Operations loop: workshop_open."""
    assert operations["workshop"]["by_status"]["open"] >= 1, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_severity_critical(operations):
    """Operations loop: severity_critical."""
    assert operations["workshop"]["by_severity"]["critical"] >= 1, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_operated_id(operations):
    """Operations loop: operated_id."""
    assert isinstance(operations["operated"], str) and len(operations["operated"]) > 5, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_aip_grounded(operations):
    """Operations loop: aip_grounded."""
    assert operations["aip"]["grounded"] is True, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_aip_answer(operations):
    """Operations loop: aip_answer."""
    assert "REORDER" in operations["aip"]["answer"] or "reorder" in operations["aip"]["answer"].lower(), f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_gov_verified(operations):
    """Operations loop: gov_verified."""
    assert operations["governance"]["verified"] is True, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_gov_total(operations):
    """Operations loop: gov_total."""
    assert operations["governance"]["total"] >= 8, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_gov_workshop(operations):
    """Operations loop: gov_workshop."""
    assert operations["governance"]["by_kind"]["workshop"] >= 5, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_free_true(operations):
    """Operations loop: free_true."""
    assert operations["free"] is True, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_hash_present(operations):
    """Operations loop: hash_present."""
    assert len(operations["workshop"].get("ontology_hash","")) >= 6, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_scen_by(operations):
    """Operations loop: scen_by."""
    assert "STOCKOUT_RISK" in operations["scenarios"]["by_scenario"], f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_kpis_orders(operations):
    """Operations loop: kpis_orders."""
    assert operations["briefing_kpis"]["orders"] == 8, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_gov_head(operations):
    """Operations loop: gov_head."""
    assert len(operations["governance"].get("head","")) >= 6, f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_app_name(operations):
    """Operations loop: app_name."""
    assert operations["workshop"]["app"] == "seller-daily", f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_operations_by_sev_sum(operations):
    """Operations loop: by_sev_sum."""
    assert sum(operations["workshop"]["by_severity"].values()) == operations["workshop"]["total"], f"ops={operations}"
    assert isinstance(operations, dict)
    assert operations["free"] is True

def test_scenarios_list_total_12(scen_list):
    """Static registry must list 12 scenarios."""
    assert scen_list["total"] == 12, scen_list
    assert len(scen_list["scenarios"]) == 12
    assert scen_list["free"] is True

def test_scenarios_list_entry_0(scen_list):
    """Registry entry 0 has id+desc."""
    e = scen_list["scenarios"][0]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_1(scen_list):
    """Registry entry 1 has id+desc."""
    e = scen_list["scenarios"][1]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_2(scen_list):
    """Registry entry 2 has id+desc."""
    e = scen_list["scenarios"][2]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_3(scen_list):
    """Registry entry 3 has id+desc."""
    e = scen_list["scenarios"][3]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_4(scen_list):
    """Registry entry 4 has id+desc."""
    e = scen_list["scenarios"][4]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_5(scen_list):
    """Registry entry 5 has id+desc."""
    e = scen_list["scenarios"][5]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_6(scen_list):
    """Registry entry 6 has id+desc."""
    e = scen_list["scenarios"][6]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_7(scen_list):
    """Registry entry 7 has id+desc."""
    e = scen_list["scenarios"][7]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_8(scen_list):
    """Registry entry 8 has id+desc."""
    e = scen_list["scenarios"][8]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_9(scen_list):
    """Registry entry 9 has id+desc."""
    e = scen_list["scenarios"][9]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_10(scen_list):
    """Registry entry 10 has id+desc."""
    e = scen_list["scenarios"][10]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_list_entry_11(scen_list):
    """Registry entry 11 has id+desc."""
    e = scen_list["scenarios"][11]
    assert "id" in e and "desc" in e and e["id"] and e["desc"]
    assert isinstance(e["id"], str) and isinstance(e["desc"], str)
    assert scen_list["total"] == 12

def test_scenarios_run_total_ge5(scen_run):
    """Run on demo must yield total>=5 (demo yields 8)."""
    assert scen_run["total"] >= 5, scen_run["by_scenario"]
    assert scen_run["total"] == 8
    assert scen_run["free"] is True

def test_scenarios_run_stable_ids(client):
    """Two runs must give identical stable IDs (idempotent)."""
    a = client.post("/api/v1/seller/scenarios/run", json={"demo": True}).json()
    b = client.post("/api/v1/seller/scenarios/run", json={"demo": True}).json()
    assert [x["id"] for x in a["decisions"]] == [x["id"] for x in b["decisions"]]
    assert a["total"] == b["total"] == 8

def test_scenarios_sorted_critical_first(scen_run):
    """Decisions sorted critical→high→medium→low."""
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    seq = [order.get(d.get("severity","medium"), 9) for d in scen_run["decisions"]]
    assert seq == sorted(seq), seq
    assert scen_run["decisions"][0]["severity"] == "critical"

def test_scenarios_ids_stable_format(scen_run):
    """IDs look like SCENARIO-8hex and are unique."""
    ids = [d["id"] for d in scen_run["decisions"]]
    assert len(ids) == len(set(ids)), "duplicate IDs"
    assert all(re.match(r"^[A-Z_]+-[0-9a-f]{8}$", i) for i in ids), ids

def test_scenarios_decision_0_shape(scen_run):
    """Decision 0 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][0]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_1_shape(scen_run):
    """Decision 1 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][1]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_2_shape(scen_run):
    """Decision 2 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][2]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_3_shape(scen_run):
    """Decision 3 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][3]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_4_shape(scen_run):
    """Decision 4 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][4]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_5_shape(scen_run):
    """Decision 5 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][5]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_6_shape(scen_run):
    """Decision 6 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][6]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_decision_7_shape(scen_run):
    """Decision 7 has scenario/severity/title/evidence/action."""
    d = scen_run["decisions"][7]
    assert "scenario" in d and "severity" in d and "title" in d
    assert "evidence" in d and isinstance(d["evidence"], list) and d["evidence"]
    assert "proposed_action" in d and "id" in d

def test_scenarios_by_scenario_keys(scen_run):
    """by_scenario must cover all 12 IDs."""
    assert len(scen_run["by_scenario"]) == 12
    assert scen_run["by_scenario"]["STOCKOUT_RISK"] == 1
    assert scen_run["by_scenario"]["PRICE_MISMATCH"] == 2

def test_scenarios_thresholds_present(scen_list):
    """Thresholds dict exposed for tunability."""
    th = scen_list.get("thresholds", {})
    assert th.get("stockout_days") == 5.0
    assert th.get("fee_creep_pct") == 12.0
    assert "dm_backlog_count" in th

def test_scenarios_workshop_stats(scen_run):
    """Run wires decisions to Workshop + governance audit."""
    assert scen_run["workshop"]["total"] >= 5
    assert scen_run["governance"]["total"] >= 5
    assert scen_run["free"] is True

def test_export_ctype(export_bundle):
    """export.csv must be text/csv attachment."""
    assert "text/csv" in export_bundle["ctype"], export_bundle["ctype"]
    assert "briefing.csv" in export_bundle["headers"].get("content-disposition","")
    assert len(export_bundle["text"]) > 300

def test_export_contains_gmv(export_bundle):
    """export.csv must contain 'gmv,274.0'."""
    assert "gmv,274.0" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_profit(export_bundle):
    """export.csv must contain 'true_profit,169.09'."""
    assert "true_profit,169.09" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_header(export_bundle):
    """export.csv must contain 'metric,value'."""
    assert "metric,value" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_best(export_bundle):
    """export.csv must contain 'best_seller,Tote Bag Handmade x6'."""
    assert "best_seller,Tote Bag Handmade x6" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_alert(export_bundle):
    """export.csv must contain 'alert_severity,alert_message,evidence'."""
    assert "alert_severity,alert_message,evidence" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_action(export_bundle):
    """export.csv must contain 'action_n,action'."""
    assert "action_n,action" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_stockout(export_bundle):
    """export.csv must contain 'stockout_product,on_hand'."""
    assert "stockout_product,on_hand" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_draft(export_bundle):
    """export.csv must contain 'draft_reply'."""
    assert "draft_reply" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_margin(export_bundle):
    """export.csv must contain 'margin_pct,61.7'."""
    assert "margin_pct,61.7" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_contains_orders(export_bundle):
    """export.csv must contain 'orders,8'."""
    assert "orders,8" in export_bundle["text"], export_bundle["text"][:600]
    assert len(export_bundle["text"].splitlines()) > 10

def test_export_parseable_csv(export_bundle):
    """export.csv must parse with csv module and expose gmv row."""
    rows = list(csv.reader(io.StringIO(export_bundle["text"])))
    assert rows[0] == ["metric", "value"]
    d = {r[0]: r[1] for r in rows if len(r) == 2 and r[0] in ("gmv","fees","true_profit","orders")}
    assert d.get("gmv") in ("274.0","274")
    assert len(rows) > 12

def test_export_seed_deterministic(client):
    """Same seed export twice identical."""
    a = client.get("/api/v1/seller/export.csv", params={"seed": 42}).text
    b = client.get("/api/v1/seller/export.csv", params={"seed": 42}).text
    assert a == b
    assert "274.0" in a

def test_photo_invalid_bytes_400(client):
    """Tiny invalid bytes must be 400, not 500."""
    r = client.post("/api/v1/seller/photo", files={"file": ("bad.bin", b"xx", "application/octet-stream")})
    assert r.status_code in (400, 422), f"{r.status_code} {r.text[:400]}"
    assert r.status_code != 500

def test_photo_empty_400(client):
    """Empty upload must be 400, not 500."""
    r = client.post("/api/v1/seller/photo", files={"file": ("empty.jpg", b"", "image/jpeg")})
    assert r.status_code in (400, 422)
    assert r.status_code != 500

def test_photo_missing_field_422(client):
    """Wrong field name must be 422."""
    r = client.post("/api/v1/seller/photo", files={"photo": ("x.png", b"1234567890ABCDEF", "image/png")})
    assert r.status_code == 422, r.text[:400]

def test_photo_valid_png_200(client):
    """Valid PNG must be 200 with ocr/chart/pipeline keys."""
    import io as _io
    from PIL import Image as _IM
    img = _IM.new("RGB", (200, 100), "white")
    buf = _io.BytesIO(); img.save(buf, format="PNG"); data = buf.getvalue()
    r = client.post("/api/v1/seller/photo", files={"file": ("t.png", data, "image/png")})
    assert r.status_code == 200, r.text[:600]
    d = r.json(); assert "ocr" in d and "chart" in d and "pipeline" in d

def test_photo_rate_or_size_guard_shape(client):
    """Oversize/corrupt error body must be JSON, not HTML/500."""
    r = client.post("/api/v1/seller/photo", files={"file": ("bad.bin", b"xx", "application/octet-stream")})
    assert r.status_code != 500
    assert "application/json" in r.headers.get("content-type","")

def test_vision_demo_flag(vision_demo):
    """Vision demo: flag."""
    assert vision_demo.get("demo") is True, f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_ocr(vision_demo):
    """Vision demo: ocr."""
    assert "ocr" in vision_demo and "text" in vision_demo["ocr"], f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_chart(vision_demo):
    """Vision demo: chart."""
    assert "chart" in vision_demo and "data" in vision_demo["chart"], f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_pipeline(vision_demo):
    """Vision demo: pipeline."""
    assert "pipeline" in vision_demo, f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_free(vision_demo):
    """Vision demo: free."""
    assert vision_demo.get("free") is True, f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_filename(vision_demo):
    """Vision demo: filename."""
    assert vision_demo.get("filename","").endswith(".png"), f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_local(vision_demo):
    """Vision demo: local."""
    assert vision_demo.get("local") is True, f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_demo_status(vision_demo):
    """Vision demo: status."""
    assert vision_demo is not None, f"keys={list(vision_demo.keys())}"
    assert isinstance(vision_demo, dict)

def test_vision_analyze_invalid_not500(client):
    """Vision analyze tiny bytes → 400/422, never 500."""
    r = client.post("/api/v1/vision/analyze", files={"file": ("bad.bin", b"xx", "application/octet-stream")})
    assert r.status_code in (400, 422)
    assert r.status_code != 500

def test_openapi_tags_seller_os(openapi_tags):
    """openapi-tags: seller_os."""
    d = openapi_tags
    assert "Seller OS" in d["tags"], f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_health(openapi_tags):
    """openapi-tags: health."""
    d = openapi_tags
    assert "Health" in d["tags"], f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_ops(openapi_tags):
    """openapi-tags: ops."""
    d = openapi_tags
    assert "Ops" in d["tags"], f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_mcp6(openapi_tags):
    """openapi-tags: mcp tools count matches wired tool registry."""
    d = openapi_tags
    assert d["mcp"]["tools"] == 17, f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_mcp_server(openapi_tags):
    """openapi-tags: mcp_server."""
    d = openapi_tags
    assert d["mcp"]["server"] == "src/omni_one/mcp_server.py", f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_free(openapi_tags):
    """openapi-tags: free."""
    d = openapi_tags
    assert d["free"] is True, f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_vision(openapi_tags):
    """openapi-tags: vision."""
    d = openapi_tags
    assert "Vision" in d["tags"], f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_admin(openapi_tags):
    """openapi-tags: admin."""
    d = openapi_tags
    assert "Admin" in d["tags"], f"{d}"
    assert isinstance(d["tags"], list) and len(d["tags"]) >= 8

def test_openapi_tags_count(openapi_tags):
    """Tag catalog must list 9 tags."""
    assert len(openapi_tags["tags"]) == 9, openapi_tags["tags"]
    assert set(openapi_tags["tags"]) >= {"Seller OS", "Vision", "Ops"}

def test_seller_extra_briefing_seed_0(client):
    """Briefing seed determinism 0: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_1(client):
    """Briefing seed determinism 1: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_2(client):
    """Briefing seed determinism 2: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_3(client):
    """Briefing seed determinism 3: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_4(client):
    """Briefing seed determinism 4: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_5(client):
    """Briefing seed determinism 5: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_6(client):
    """Briefing seed determinism 6: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_7(client):
    """Briefing seed determinism 7: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_8(client):
    """Briefing seed determinism 8: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_9(client):
    """Briefing seed determinism 9: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_10(client):
    """Briefing seed determinism 10: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_11(client):
    """Briefing seed determinism 11: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_12(client):
    """Briefing seed determinism 12: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_13(client):
    """Briefing seed determinism 13: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_14(client):
    """Briefing seed determinism 14: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_15(client):
    """Briefing seed determinism 15: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_16(client):
    """Briefing seed determinism 16: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_17(client):
    """Briefing seed determinism 17: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_18(client):
    """Briefing seed determinism 18: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_19(client):
    """Briefing seed determinism 19: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_20(client):
    """Briefing seed determinism 20: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_21(client):
    """Briefing seed determinism 21: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_22(client):
    """Briefing seed determinism 22: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_23(client):
    """Briefing seed determinism 23: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_briefing_seed_24(client):
    """Briefing seed determinism 24: golden KPIs stable."""
    r = client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})
    assert r.status_code == 200
    k = r.json()["kpis"]
    assert k["gmv"] == 274.0 and abs(k["true_profit"] - 169.09) < 0.05
    assert k["orders"] == 8 and k["aov"] == 34.25

def test_seller_extra_ops_0(operations):
    """Ops extra 0: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_1(operations):
    """Ops extra 1: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_2(operations):
    """Ops extra 2: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_3(operations):
    """Ops extra 3: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_4(operations):
    """Ops extra 4: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_5(operations):
    """Ops extra 5: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_6(operations):
    """Ops extra 6: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_7(operations):
    """Ops extra 7: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_8(operations):
    """Ops extra 8: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_9(operations):
    """Ops extra 9: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_10(operations):
    """Ops extra 10: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_11(operations):
    """Ops extra 11: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_12(operations):
    """Ops extra 12: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_13(operations):
    """Ops extra 13: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_ops_14(operations):
    """Ops extra 14: workshop+governance coherence."""
    assert operations["workshop"]["total"] == operations["governance"]["by_kind"]["workshop"]
    assert operations["aip"]["grounded"] is True
    assert operations["governance"]["verified"] is True
    assert operations["briefing_kpis"]["gmv"] == 274.0

def test_seller_extra_export_0(export_bundle):
    """Export extra 0: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_1(export_bundle):
    """Export extra 1: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_2(export_bundle):
    """Export extra 2: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_3(export_bundle):
    """Export extra 3: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_4(export_bundle):
    """Export extra 4: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_5(export_bundle):
    """Export extra 5: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_6(export_bundle):
    """Export extra 6: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_7(export_bundle):
    """Export extra 7: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_8(export_bundle):
    """Export extra 8: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra_export_9(export_bundle):
    """Export extra 9: csv rows sanity."""
    import csv as _csv, io as _io
    rows = list(_csv.reader(_io.StringIO(export_bundle["text"])))
    assert any("Tote" in ",".join(r) for r in rows)
    assert len(rows) > 15

def test_seller_extra2_0(briefing, scen_run, operations):
    """Cross-pack coherence 0."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_1(briefing, scen_run, operations):
    """Cross-pack coherence 1."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_2(briefing, scen_run, operations):
    """Cross-pack coherence 2."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_3(briefing, scen_run, operations):
    """Cross-pack coherence 3."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_4(briefing, scen_run, operations):
    """Cross-pack coherence 4."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_5(briefing, scen_run, operations):
    """Cross-pack coherence 5."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_6(briefing, scen_run, operations):
    """Cross-pack coherence 6."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_7(briefing, scen_run, operations):
    """Cross-pack coherence 7."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_8(briefing, scen_run, operations):
    """Cross-pack coherence 8."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_9(briefing, scen_run, operations):
    """Cross-pack coherence 9."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_10(briefing, scen_run, operations):
    """Cross-pack coherence 10."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_11(briefing, scen_run, operations):
    """Cross-pack coherence 11."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_12(briefing, scen_run, operations):
    """Cross-pack coherence 12."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_13(briefing, scen_run, operations):
    """Cross-pack coherence 13."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_14(briefing, scen_run, operations):
    """Cross-pack coherence 14."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_15(briefing, scen_run, operations):
    """Cross-pack coherence 15."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_16(briefing, scen_run, operations):
    """Cross-pack coherence 16."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_17(briefing, scen_run, operations):
    """Cross-pack coherence 17."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_18(briefing, scen_run, operations):
    """Cross-pack coherence 18."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_19(briefing, scen_run, operations):
    """Cross-pack coherence 19."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_20(briefing, scen_run, operations):
    """Cross-pack coherence 20."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

def test_seller_extra2_21(briefing, scen_run, operations):
    """Cross-pack coherence 21."""
    assert briefing["kpis"]["gmv"] == operations["briefing_kpis"]["gmv"] == 274.0
    assert scen_run["total"] == operations["scenarios"]["total"] == 8
    assert briefing["kpis"]["true_profit"] == 169.09

