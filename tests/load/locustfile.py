"""Omni-One load profile — Seller OS Monday-morning shape + laptop selftest.

Works WITHOUT locust installed (import guard below defines stubs so plain
`python3 tests/load/locustfile.py --selftest` and `pytest --collect-only`
never break). With locust installed, run a real soak:

    locust -f tests/load/locustfile.py --host http://localhost:5003

Task mix mirrors a seller morning: briefings > health polls > scenarios > closes.
"""
from __future__ import annotations

import time

# task registry: name -> {weight, method, path, payload}. Single source of
# truth for both the Locust user and the --selftest runner.
TASKS = {
    "briefing_demo": {
        "weight": 4,
        "method": "POST",
        "path": "/api/v1/seller/briefing",
        "payload": {"demo": True, "seed": 42},
    },
    "scenarios": {
        "weight": 3,
        "method": "POST",
        "path": "/api/v1/seller/scenarios/run",
        "payload": {"demo": True, "seed": 42},
    },
    "close": {
        "weight": 2,
        "method": "POST",
        "path": "/api/v1/seller/close",
        "payload": {"demo": True, "seed": 42, "shop": "load shop"},
    },
    "health": {
        "weight": 5,
        "method": "GET",
        "path": "/health",
        "payload": None,
    },
}

try:  # optional import guard — locust is NOT a runtime/test dependency
    from locust import HttpUser, task, between  # type: ignore

    HAS_LOCUST = True
except ImportError:  # pragma: no cover - exercised on plain laptops/CI
    HAS_LOCUST = False

    class HttpUser:  # type: ignore
        """Stub so module import + --selftest work without locust."""

    def task(*args, **kwargs):  # type: ignore
        """Accept @task, @task(3), @task(weight=3); tag fn, return as-is."""
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        weight = args[0] if args else kwargs.get("weight", 1)

        def deco(fn):
            fn.locust_task_weight = weight
            return fn

        return deco

    def between(*args, **kwargs):  # type: ignore
        return lambda: 0


def _request(client, spec):
    """One registry-driven request; returns elapsed seconds. Raises on 5xx."""
    start = time.perf_counter()
    if spec["method"] == "GET":
        resp = client.get(spec["path"])
    else:
        resp = client.post(spec["path"], json=spec["payload"])
    elapsed = time.perf_counter() - start
    status = getattr(resp, "status_code", 200)
    if status >= 500:
        raise RuntimeError(f"{spec['path']} -> HTTP {status}")
    return elapsed


if HAS_LOCUST:

    class SellerUser(HttpUser):
        """Monday-morning seller mix. Weights mirror TASKS registry."""

        wait_time = between(0.1, 0.5)

        @task(4)
        def briefing_demo(self):
            self.client.post("/api/v1/seller/briefing", json={"demo": True, "seed": 42})

        @task(3)
        def scenarios(self):
            self.client.post("/api/v1/seller/scenarios/run", json={"demo": True, "seed": 42})

        @task(2)
        def close(self):
            self.client.post(
                "/api/v1/seller/close",
                json={"demo": True, "seed": 42, "shop": "load shop"},
            )

        @task(5)
        def health(self):
            self.client.get("/health")

else:

    class SellerUser(HttpUser):  # type: ignore
        """Stub user — documents the intended mix when locust is absent."""

        TASKS = TASKS


def _percentile(sorted_ms, pct):
    if not sorted_ms:
        return 0.0
    rank = (pct / 100.0) * (len(sorted_ms) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_ms) - 1)
    frac = rank - lo
    return sorted_ms[lo] * (1 - frac) + sorted_ms[hi] * frac


def run_selftest(n=20, p95_budget_ms=2000.0):
    """20 sequential TestClient calls cycling the registry; print p50/p95."""
    from fastapi.testclient import TestClient

    try:
        from omni_one.api.fastapi_app import create_omni_one_app
    except ImportError:  # PYTHONPATH=src fallback (repo-root checkout)
        from src.omni_one.api.fastapi_app import create_omni_one_app  # type: ignore

    client = TestClient(client_app := create_omni_one_app())
    del client_app
    names = ["health", "briefing_demo", "scenarios", "close"]
    lat_ms = []
    per_op = {}
    for i in range(n):
        name = names[i % len(names)]
        spec = TASKS[name]
        secs = _request(client, spec)
        ms = secs * 1000.0
        lat_ms.append(ms)
        per_op.setdefault(name, []).append(ms)
        print(f"  [{i + 1:02d}/{n}] {name:13s} {ms:8.1f}ms")
    lat_ms.sort()
    p50 = _percentile(lat_ms, 50)
    p95 = _percentile(lat_ms, 95)
    print(f"selftest: n={n} p50={p50:.1f}ms p95={p95:.1f}ms max={lat_ms[-1]:.1f}ms")
    for name, vals in per_op.items():
        vals.sort()
        print(f"  op={name:13s} n={len(vals)} p50={_percentile(vals, 50):.1f}ms p95={_percentile(vals, 95):.1f}ms")
    assert p95 < p95_budget_ms, f"p95 {p95:.1f}ms exceeds budget {p95_budget_ms:.0f}ms"
    print(f"selftest PASS: p95 {p95:.1f}ms < {p95_budget_ms:.0f}ms budget")
    return {"n": n, "p50_ms": p50, "p95_ms": p95}


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        run_selftest()
    else:
        print("usage: python3 tests/load/locustfile.py --selftest")
        print("   or: locust -f tests/load/locustfile.py --host http://localhost:5003")
        sys.exit(2)
