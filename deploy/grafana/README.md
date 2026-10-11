# omni-one Grafana + Prometheus

Dashboard `dashboard.json` (import via Grafana UI → Dashboards → Import):
panels for `omni_one_requests{op}` — briefings / scenarios / closes /
vision — plus a latency-histogram placeholder and an `omni_one_up` gauge.

Alerts `prometheus-rules.yaml` (`PrometheusRule` CRD, kube-prometheus):
`ClosesMissing24h` (closes_total flat for 24h → 7am cron broken) and
`UpDown` (`omni_one_up == 0` → process down).

## Scrape config snippet (`prometheus.yml`)

```yaml
scrape_configs:
  - job_name: omni-one
    scrape_interval: 15s
    static_configs:
      - targets: ["omni-one.omni-one.svc.cluster.local:80"]
    metrics_path: /metrics
```

For docker-compose / single-box, replace the target with `<host>:5003`.
No auth on `/metrics` (in-process counters, reset on restart — see
`src/omni_one/api/ops.py`).

## Apply alerts

```sh
kubectl apply -f deploy/grafana/prometheus-rules.yaml
kubectl -n monitoring get prometheusrules omni-one-alerts
```
