# Tiltfile — omni-one local K8s dev loop (WAVE2-K).
#
# What this file does:
#   1. Builds the `omni-one` docker image from the repo Dockerfile.
#   2. Renders the DEV kustomize overlay (deploy/k8s/overlays/dev).
#   3. Deploys to the current kubectl context + sets up port_forward :5003.
#   4. Live-updates ./src without full rebuilds (hot reload).
#   5. Exposes a trigger-tests button (local_resource running pytest unit subset).
#
# Usage:
#   tilt up            # start dev loop (Ctrl-C to stop, `tilt down` to clean)
#   tilt down          # delete Tilt-managed resources
#
# Prereqs:
#   - Docker + a local cluster (kind / minikube / docker-desktop).
#   - kubectl pointing at that cluster: `kubectl cluster-info`.
#   - Tilt installed: https://docs.tilt.dev/install.html
#
# Conventions:
#   - Image name is `omni-one` everywhere (Dockerfile, k8s deployment, compose).
#   - API serves on container port 5003 (see deploy/k8s/deployment.yaml).
#   - Dev overlay = 1 replica, LOG_LEVEL=debug, no HPA.
#
# Troubleshooting:
#   - If kustomize render fails, run:
#       kubectl kustomize deploy/k8s/overlays/dev
#   - If the port is busy, change the host side of port_forward below.
#   - For full test suite use: PYTHONPATH=src python3 -m pytest tests/ -q

# ---------------------------------------------------------------------------
# 0. Config knobs (edit these for your laptop)
# ---------------------------------------------------------------------------

# Docker image tag for local dev. Keep `:dev` so prod (`:1.1.0`) is untouched.
DEV_TAG = "dev"

# Host port for the API. Container always listens on 5003.
HOST_PORT = 5003
CONTAINER_PORT = 5003

# Unit-test subset the dashboard button runs (fast, no cluster/docker needed).
UNIT_SUBSET = "tests/unit/test_deploy_wave2.py tests/unit/test_daily_close.py"

# Source + asset dirs synced into the running container via live_update.
LIVE_SYNC_SRC = "./src"
LIVE_SYNC_WEB = "./web"

# ---------------------------------------------------------------------------
# 1. Build the dev image
# ---------------------------------------------------------------------------

# docker_build builds `omni-one:dev` from the repo root Dockerfile and wires
# the result into the Deployment image reference `omni-one` (see overlay
# images.newTag). live_update below makes ./src edits instant.
docker_build(
    "omni-one",
    ".",
    dockerfile="Dockerfile",
    live_update=[
        # Sync python sources live so uvicorn --reload picks them up.
        sync(LIVE_SYNC_SRC, "/app/src"),
        # Sync web assets live (no backend rebuild needed for static edits).
        sync(LIVE_SYNC_WEB, "/app/web"),
        # Restart the container process after a sync batch completes.
        run("pkill -f uvicorn || true", trigger=[LIVE_SYNC_SRC]),
    ],
)

# ---------------------------------------------------------------------------
# 2. Render + deploy the DEV overlay with kustomize
# ---------------------------------------------------------------------------

# k8s_yaml with kustomize() renders deploy/k8s/overlays/dev/kustomization.yaml
# (1 replica, debug log, no HPA, host dev.omni-one.local) into raw manifests
# and feeds them to Tilt. Equivalent manual render:
#   kubectl kustomize deploy/k8s/overlays/dev
k8s_yaml(kustomize("deploy/k8s/overlays/dev"))

# ---------------------------------------------------------------------------
# 3. Wire resources: port_forward, names, dependencies
# ---------------------------------------------------------------------------

# Main API workload. port_forward exposes pod :5003 as localhost:5003 so
# `curl localhost:5003/health` works without `kubectl port-forward`.
k8s_resource(
    "omni-one",
    port_forwards=port_forward(HOST_PORT, CONTAINER_PORT, name="api"),
    labels=["backend"],
)

# Optional: surface the ConfigMap as its own Tilt resource for visibility.
# (No-op if the object name changes; Tilt ignores missing extra resources.)
k8s_resource(
    "omni-one-config",
    labels=["config"],
    resource_deps=["omni-one"],
)

# ---------------------------------------------------------------------------
# 4. Trigger-tests button: local_resource running pytest unit subset
# ---------------------------------------------------------------------------

# local_resource runs on YOUR laptop (not in the cluster). Tilt shows it as a
# dashboard button with a play icon; clicking re-runs the fast unit subset.
# `auto_init=False` keeps it manual-only so `tilt up` stays quiet.
local_resource(
    "unit-tests",
    "PYTHONPATH=src python3 -m pytest %s -q" % UNIT_SUBSET,
    labels=["tests"],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# Companion: lint the kustomize output on demand (catches bad patches early).
local_resource(
    "kustomize-lint",
    "kubectl kustomize deploy/k8s/overlays/dev > /dev/null && echo OK dev; " +
    "kubectl kustomize deploy/k8s/overlays/staging > /dev/null && echo OK staging; " +
    "kubectl kustomize deploy/k8s/overlays/prod > /dev/null && echo OK prod",
    labels=["tests"],
    auto_init=False,
    trigger_mode=TRIGGER_MODE_MANUAL,
)

# ---------------------------------------------------------------------------
# 5. Version / sanity echo (runs once at `tilt up`)
# ---------------------------------------------------------------------------

local_resource(
    "tilt-hello",
    "echo 'omni-one tilt ready: image=omni-one:%s host=localhost:%s overlay=dev' | tee /dev/stderr" % (DEV_TAG, HOST_PORT),
    labels=["setup"],
)

# ---------------------------------------------------------------------------
# 6. Notes for operators (no-op docs block to keep intent explicit)
# ---------------------------------------------------------------------------
#
# - Switching overlays: change the kustomize() path above from
#     deploy/k8s/overlays/dev
#   to
#     deploy/k8s/overlays/staging
#   then `tilt up` again. Prod is NOT recommended under Tilt (use CI/CD).
# - Data persistence: the Deployment mounts PVC `omni-one-data`; Tilt
#   restarts preserve it. Back up with `bash deploy/backup/backup.sh`.
# - API endpoints once port_forward is up:
#     curl localhost:5003/health
#     curl localhost:5003/metrics
# - To tail logs in a second terminal:
#     kubectl -n omni-one logs -f deploy/omni-one
# - End of Tiltfile.
