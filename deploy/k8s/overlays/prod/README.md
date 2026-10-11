# omni-one — prod overlay

Production: 3 replicas, PDB minAvailable 2, HPA 3-10, anti-affinity, TLS.

Apply:
  kubectl apply -k deploy/k8s/overlays/prod
Verify:
  kubectl -n omni-one get deploy/omni-one hpa/omni-one pdb/omni-one
Hostname:
  https://omni-one.example.com (TLS secret omni-one-tls via letsencrypt-prod)
Notes:
  Base files live in deploy/k8s/*.yaml. Resources requests/limits + podAntiAffinity set.
