# omni-one Helm chart (v1.1.0)

Installs the Seller OS API: Deployment + ClusterIP Service + Ingress +
HPA (CPU 60%) + PVC (`/app/data`) + ConfigMap (`SELLER_LLM`, `DUCKDB_PATH`, …).

## Install

```sh
helm lint deploy/helm/omni-one
helm install omni deploy/helm/omni-one -n omni-one --create-namespace
helm status omni -n omni-one   # prints NOTES.txt (close demo command)
```

## Common overrides

```sh
helm upgrade omni deploy/helm/omni-one -n omni-one --set replicaCount=3
helm upgrade omni deploy/helm/omni-one -n omni-one \
  --set image.tag=1.1.0 --set persistence.size=10Gi \
  --set env.SELLER_LLM=off
```

## Values

| Key | Default | Notes |
|---|---|---|
| `replicaCount` | `2` | ignored when `autoscaling.enabled` |
| `image.repository/tag` | `omni-one:1.1.0` | matches `deploy/docker/Dockerfile.prod` |
| `service` | `ClusterIP :80 → 5003` | |
| `ingress` | enabled, nginx, `omni-one.example.com` | set your host + TLS secret |
| `persistence` | enabled, `5Gi` → `/app/data` | DuckDB + audit + closes live here |
| `resources` | 250m/512Mi → 1/1Gi | |
| `env` | `SELLER_LLM=off`, `DUCKDB_PATH`, `PORT=5003` | secrets go in SealedSecret, NOT here |

Secrets: see `deploy/k8s/sealed-secret.example.yaml` — never put
`VALID_API_KEYS` in values; inject via `--set-file` or sealed secret.
