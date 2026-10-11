# Load tests (locust optional)

`locustfile.py` imports cleanly **without** locust installed (stub
`HttpUser`/`task`/`between` guard) and ships a laptop selftest that needs
only the app deps:

```sh
PYTHONPATH=src python3 tests/load/locustfile.py --selftest
# 20 sequential TestClient calls (health/briefing/scenarios/close cycle),
# prints p50/p95 and asserts p95 < 2000ms.
```

## Real soak (needs `pip install locust`)

```sh
# terminal 1: serve
PYTHONPATH=src python3 -m uvicorn omni_one.api.fastapi_app:create_omni_one_app \
  --factory --port 5003
# terminal 2: soak
locust -f tests/load/locustfile.py --host http://localhost:5003
```

Task weights (`TASKS` registry in the file): health 5, briefing_demo 4,
scenarios 3, close 2 — the Monday-morning seller mix. `/metrics`
(`omni_one_requests{op}`) is the cheap way to watch the soak server-side;
alerts live in `deploy/grafana/prometheus-rules.yaml`.
