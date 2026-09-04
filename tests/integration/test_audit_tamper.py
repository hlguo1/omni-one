"""Audit tamper: flipping a byte must fail verify()."""
from omni_one.palantir_free.governance import AuditLog


def test_audit_tamper():
    log = AuditLog("tamper")
    log.append("pipeline", "r1", {"stage": "ml_feature"})
    log.append("workshop", "D-0001", {"status": "open"})
    assert log.verify()["ok"] is True
    # Tamper
    log.events[0]["payload"]["stage"] = "HACKED"
    v = log.verify()
    assert v["ok"] is False and v["first_bad"] == 0
