# omni-one — dev overlay

Local single-replica debug overlay. No HPA (omitted from resources).

Apply:
  kubectl apply -k deploy/k8s/overlays/dev
Verify:
  kubectl -n omni-one get deploy/omni-one
Hostname:
  http://dev.omni-one.local (see dev.patch.yaml Ingress rule)
Notes:
  1 replica, LOG_LEVEL=debug, image tag dev. Base files live in deploy/k8s/*.yaml.
