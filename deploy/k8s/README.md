# omni-one on Kubernetes

> **WARNING — never commit real secrets.** API keys live ONLY in a
> cluster-side `Secret`/`SealedSecret`. This repo ships
> `sealed-secret.example.yaml` as a shape reference; generate the real one
> with YOUR cluster's `kubeseal` cert (command in that file) and keep
> `.env`/`sealed-secret.yaml` (real) out of git.

## Deploy (no cluster needed to review; `kubectl apply` needs one)

```sh
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
# create the REAL secret with kubeseal first, then:
kubectl apply -f deploy/k8s/
kubectl -n omni-one rollout status deploy/omni-one
```

## What each file does

| File | Purpose |
|---|---|
| `namespace.yaml` | `omni-one` namespace |
| `configmap.yaml` | non-secret env: `SELLER_LLM`, `DUCKDB_PATH`, `AUDIT_PATH`, inbox, `PORT` |
| `deployment.yaml` | 2 replicas, non-root, liveness `/health` + readiness `/readiness`, PVC mount `/app/data` |
| `service.yaml` | `ClusterIP` :80 → pod :5003 |
| `ingress.yaml` | nginx ingress + TLS + rate-limit annotations |
| `hpa.yaml` | CPU 60%, 2–6 replicas |
| `pdb.yaml` | `minAvailable: 1` so closes survive drains |
| `networkpolicy.yaml` | ingress allow-list (nginx + self), egress DNS+443 only |
| `sealed-secret.example.yaml` | EXAMPLE shape only — see warning above |

## Ops

```sh
# daily close demo through the cluster
kubectl -n omni-one exec deploy/omni-one -- \
  python -m omni_one.cli close --demo --shop "demo shop" --out /app/data/closes/demo
kubectl -n omni-one port-forward svc/omni-one 5003:80
curl localhost:5003/health && curl localhost:5003/metrics | head
```

Persistence: the Deployment mounts PVC `omni-one-data` (see Helm
`templates/pvc.yaml`; for raw k8s, create a matching PVC or change the
volume to `emptyDir` for throwaway review).
