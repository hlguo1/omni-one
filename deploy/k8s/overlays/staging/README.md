# omni-one — staging overlay

Pre-prod mirror with HPA enabled (2 replicas, autoscale 2-4 on CPU 60%).

Apply:
  kubectl apply -k deploy/k8s/overlays/staging
Verify:
  kubectl -n omni-one get deploy/omni-one hpa/omni-one
Hostname:
  https://staging.omni-one.example.com (TLS secret omni-one-tls-staging)
Notes:
  Base files live in deploy/k8s/*.yaml. Patch sets ENVIRONMENT=staging, LOG_LEVEL=info.
