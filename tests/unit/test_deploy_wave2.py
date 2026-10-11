"""WAVE2-K deploy validation — ops overlays + dev env.

Pure file-content assertions. No cluster / docker / network needed.

Covers:
  * deploy/k8s/overlays/{dev,staging,prod}/kustomization.yaml
      - apiVersion/kind/resources non-empty, explicit ../../ file list,
        referenced files exist on disk, patches file exists.
  * deploy/k8s/overlays/*/*.patch.yaml
      - multi-doc YAML, kinds subset of known base kinds,
        per-env replica / HPA / PDB / ingress / resources / anti-affinity.
  * deploy/k8s/overlays/*/README.md
      - >=6 lines, kubectl apply -k command, hostname.
  * deploy/compose/docker-compose.dev.yml / .prod.yml
      - services.api + volumes + ports, dev hot-reload + debug env,
        prod restart always + limits + logging rotation.
  * deploy/compose/README.md — env mapping + volume backup note.
  * .devcontainer/devcontainer.json — valid JSON, forwardPorts has 5003,
      python 3.11 image, postCreate pip install, python+yaml extensions.
  * Tiltfile — docker_build + k8s_yaml + port_forward, live_update src,
      local_resource pytest subset, ~150 lines.
  * deploy/backup/*.sh — bash -n clean (no cluster needed).
  * deploy/grafana/dashboard.json — >=4 panels (regression guard).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

try:
    import yaml  # type: ignore

    HAS_YAML = True
except Exception:  # pragma: no cover - fallback string checks
    yaml = None  # type: ignore
    HAS_YAML = False


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
OVERLAYS = REPO / "deploy" / "k8s" / "overlays"
COMPOSE = REPO / "deploy" / "compose"
DEVCONTAINER = REPO / ".devcontainer" / "devcontainer.json"
TILTFILE = REPO / "Tiltfile"
BACKUP_SH = REPO / "deploy" / "backup" / "backup.sh"
RESTORE_SH = REPO / "deploy" / "backup" / "restore.sh"
DASHBOARD = REPO / "deploy" / "grafana" / "dashboard.json"

DEV_KUST = OVERLAYS / "dev" / "kustomization.yaml"
STAGING_KUST = OVERLAYS / "staging" / "kustomization.yaml"
PROD_KUST = OVERLAYS / "prod" / "kustomization.yaml"

DEV_PATCH = OVERLAYS / "dev" / "dev.patch.yaml"
STAGING_PATCH = OVERLAYS / "staging" / "staging.patch.yaml"
PROD_PATCH = OVERLAYS / "prod" / "prod.patch.yaml"

DEV_COMPOSE = COMPOSE / "docker-compose.dev.yml"
PROD_COMPOSE = COMPOSE / "docker-compose.prod.yml"

# Kinds present in the existing deploy/k8s/*.yaml base files. Overlay patches
# must only reference these (plus Kustomization itself is not a patch kind).
KNOWN_PATCH_KINDS = {
    "Deployment",
    "Service",
    "Ingress",
    "ConfigMap",
    "HorizontalPodAutoscaler",
    "PodDisruptionBudget",
    "NetworkPolicy",
    "Namespace",
    "SealedSecret",
}


def read_text(p: Path) -> str:
    assert p.is_file(), f"missing file: {p.relative_to(REPO)}"
    return p.read_text(encoding="utf-8")


def load_yaml(p: Path):
    """Load single-doc YAML; requires pyyaml in this repo."""
    assert HAS_YAML, "pyyaml required for deploy validation"
    with open(p, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_yaml_all(p: Path):
    """Load multi-doc YAML, skipping empty docs."""
    assert HAS_YAML, "pyyaml required for deploy validation"
    with open(p, encoding="utf-8") as fh:
        return [d for d in yaml.safe_load_all(fh) if d]


def kust_resources(kust_path: Path) -> list:
    d = load_yaml(kust_path)
    assert isinstance(d, dict), f"{kust_path.name} must be a mapping"
    res = d.get("resources")
    assert isinstance(res, list) and len(res) > 0, f"{kust_path}: resources non-empty"
    return res


def patch_docs(patch_path: Path) -> list:
    docs = load_yaml_all(patch_path)
    assert len(docs) > 0, f"{patch_path.name}: at least one YAML doc"
    return docs


def patch_kinds(patch_path: Path) -> set:
    return {d.get("kind") for d in patch_docs(patch_path) if isinstance(d, dict)}


def deployment_doc(patch_path: Path) -> dict:
    for d in patch_docs(patch_path):
        if isinstance(d, dict) and d.get("kind") == "Deployment":
            return d
    raise AssertionError(f"{patch_path.name}: no Deployment doc")


# ---------------------------------------------------------------------------
# kustomization shape (all overlays)
# ---------------------------------------------------------------------------


class TestKustomizationShape:
    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_file_exists(self, kust):
        assert kust.is_file(), f"missing {kust.relative_to(REPO)}"

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_api_version(self, kust):
        d = load_yaml(kust)
        assert "kustomize.config.k8s.io" in str(d.get("apiVersion", "")), kust

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_kind_is_kustomization(self, kust):
        d = load_yaml(kust)
        assert d.get("kind") == "Kustomization", kust

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_resources_non_empty(self, kust):
        assert len(kust_resources(kust)) >= 3, kust

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_resources_reference_parent_explicitly(self, kust):
        # Must reference ../../ (deploy/k8s/*.yaml) via explicit file list,
        # NOT a ../../base directory (which does not exist in this repo).
        text = read_text(kust)
        assert "../../" in text, f"{kust}: must reference ../../ base files"
        assert "base" not in text.lower().replace("database", "") or "../../base" not in text, (
            f"{kust}: must not reference ../../base directory"
        )
        for r in kust_resources(kust):
            assert isinstance(r, str) and r.startswith("../../"), f"{kust}: {r!r}"
            assert r.endswith(".yaml"), f"{kust}: {r!r} must name a yaml file"

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_resources_files_exist(self, kust):
        for r in kust_resources(kust):
            target = (kust.parent / r).resolve()
            assert target.is_file(), f"{kust.name}: resource {r} -> missing {target}"

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_core_base_files_covered(self, kust):
        joined = " ".join(kust_resources(kust))
        for base in ("deployment.yaml", "service.yaml", "configmap.yaml"):
            assert base in joined, f"{kust.name}: must list {base} explicitly"

    @pytest.mark.parametrize(
        "kust, patch",
        [(DEV_KUST, DEV_PATCH), (STAGING_KUST, STAGING_PATCH), (PROD_KUST, PROD_PATCH)],
        ids=["dev", "staging", "prod"],
    )
    def test_patches_key_points_at_existing_file(self, kust, patch):
        d = load_yaml(kust)
        blob = json.dumps(d)
        assert patch.name in blob, f"{kust.name}: must reference {patch.name}"
        assert patch.is_file(), f"missing patch {patch.relative_to(REPO)}"

    @pytest.mark.parametrize(
        "kust", [DEV_KUST, STAGING_KUST, PROD_KUST], ids=["dev", "staging", "prod"]
    )
    def test_fallback_string_check(self, kust):
        # Verifier fallback when pyyaml is absent: raw text must carry keys.
        text = read_text(kust)
        assert "resources:" in text, kust
        assert "apiVersion:" in text and "kind:" in text, kust


# ---------------------------------------------------------------------------
# patch kinds reference existing base kinds
# ---------------------------------------------------------------------------


class TestPatchKinds:
    @pytest.mark.parametrize(
        "patch", [DEV_PATCH, STAGING_PATCH, PROD_PATCH], ids=["dev", "staging", "prod"]
    )
    def test_patch_file_exists(self, patch):
        assert patch.is_file()

    @pytest.mark.parametrize(
        "patch", [DEV_PATCH, STAGING_PATCH, PROD_PATCH], ids=["dev", "staging", "prod"]
    )
    def test_patch_kinds_known(self, patch):
        kinds = patch_kinds(patch)
        assert len(kinds) > 0
        unknown = kinds - KNOWN_PATCH_KINDS
        assert not unknown, f"{patch.name}: unknown kinds {unknown}"

    @pytest.mark.parametrize(
        "patch", [DEV_PATCH, STAGING_PATCH, PROD_PATCH], ids=["dev", "staging", "prod"]
    )
    def test_patch_has_deployment_doc(self, patch):
        d = deployment_doc(patch)
        assert d["metadata"]["name"] == "omni-one"

    @pytest.mark.parametrize(
        "patch", [DEV_PATCH, STAGING_PATCH, PROD_PATCH], ids=["dev", "staging", "prod"]
    )
    def test_patch_has_configmap_doc(self, patch):
        assert "ConfigMap" in patch_kinds(patch), f"{patch.name} needs ConfigMap"

    @pytest.mark.parametrize(
        "patch", [DEV_PATCH, STAGING_PATCH, PROD_PATCH], ids=["dev", "staging", "prod"]
    )
    def test_patch_has_ingress_doc(self, patch):
        assert "Ingress" in patch_kinds(patch), f"{patch.name} needs Ingress"


# ---------------------------------------------------------------------------
# dev overlay specifics: 1 replica, debug log, no HPA
# ---------------------------------------------------------------------------


class TestDevOverlay:
    def test_one_replica(self):
        d = deployment_doc(DEV_PATCH)
        assert d["spec"]["replicas"] == 1

    def test_debug_log(self):
        text = read_text(DEV_PATCH).lower()
        assert "debug" in text, "dev patch must set debug log level"
        # also mirrored into the ConfigMap data block
        docs = patch_docs(DEV_PATCH)
        cm = [x for x in docs if x.get("kind") == "ConfigMap"][0]
        assert "debug" in json.dumps(cm).lower()

    def test_no_hpa_in_resources(self):
        joined = " ".join(kust_resources(DEV_KUST)).lower()
        assert "hpa" not in joined, "dev must not include hpa.yaml (no HPA)"

    def test_no_hpa_patch_doc(self):
        assert "HorizontalPodAutoscaler" not in patch_kinds(DEV_PATCH)

    def test_dev_hostname(self):
        assert "dev.omni-one.local" in read_text(DEV_PATCH)

    def test_dev_image_tag(self):
        assert "dev" in read_text(DEV_KUST)


# ---------------------------------------------------------------------------
# staging overlay specifics: 2 replicas, HPA, staging ingress host
# ---------------------------------------------------------------------------


class TestStagingOverlay:
    def test_two_replicas(self):
        d = deployment_doc(STAGING_PATCH)
        assert d["spec"]["replicas"] == 2

    def test_hpa_in_resources(self):
        joined = " ".join(kust_resources(STAGING_KUST)).lower()
        assert "hpa" in joined, "staging must include hpa.yaml"

    def test_hpa_patch_doc(self):
        kinds = patch_kinds(STAGING_PATCH)
        assert "HorizontalPodAutoscaler" in kinds
        docs = patch_docs(STAGING_PATCH)
        hpa = [x for x in docs if x.get("kind") == "HorizontalPodAutoscaler"][0]
        assert hpa["spec"]["minReplicas"] == 2

    def test_staging_ingress_host(self):
        text = read_text(STAGING_PATCH)
        assert "staging.omni-one.example.com" in text

    def test_staging_env_marker(self):
        assert "staging" in read_text(STAGING_PATCH).lower()

    def test_pdb_present_in_staging(self):
        joined = " ".join(kust_resources(STAGING_KUST)).lower()
        assert "pdb" in joined


# ---------------------------------------------------------------------------
# prod overlay specifics: 3 replicas, PDB 2, prod ingress + TLS,
# resources requests/limits, anti-affinity
# ---------------------------------------------------------------------------


class TestProdOverlay:
    def test_three_replicas(self):
        d = deployment_doc(PROD_PATCH)
        assert d["spec"]["replicas"] == 3

    def test_pdb_min_available_two(self):
        docs = patch_docs(PROD_PATCH)
        pdb = [x for x in docs if x.get("kind") == "PodDisruptionBudget"]
        assert len(pdb) == 1, "prod patch must carry exactly one PDB doc"
        assert pdb[0]["spec"]["minAvailable"] == 2

    def test_prod_ingress_host(self):
        text = read_text(PROD_PATCH)
        assert "omni-one.example.com" in text

    def test_prod_tls_block(self):
        docs = patch_docs(PROD_PATCH)
        ing = [x for x in docs if x.get("kind") == "Ingress"][0]
        assert "tls" in ing["spec"], "prod ingress must carry TLS block"
        hosts = json.dumps(ing["spec"]["tls"])
        assert "omni-one.example.com" in hosts

    def test_prod_resources_requests_limits(self):
        dep = deployment_doc(PROD_PATCH)
        containers = dep["spec"]["template"]["spec"]["containers"]
        assert len(containers) >= 1
        res = containers[0].get("resources", {})
        assert "requests" in res and "limits" in res, "prod needs requests+limits"
        assert "cpu" in res["requests"] and "memory" in res["requests"]
        assert "cpu" in res["limits"] and "memory" in res["limits"]

    def test_prod_anti_affinity(self):
        text = read_text(PROD_PATCH)
        assert "podAntiAffinity" in text, "prod needs pod anti-affinity"
        dep = deployment_doc(PROD_PATCH)
        podspec = dep["spec"]["template"]["spec"]
        assert "affinity" in podspec

    def test_prod_hpa_scaled(self):
        docs = patch_docs(PROD_PATCH)
        hpa = [x for x in docs if x.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpa) == 1
        assert hpa[0]["spec"]["minReplicas"] == 3

    def test_prod_resources_include_hpa_pdb(self):
        joined = " ".join(kust_resources(PROD_KUST)).lower()
        assert "hpa" in joined and "pdb" in joined


# ---------------------------------------------------------------------------
# overlay READMEs: 6 lines min, apply -k command, hostname
# ---------------------------------------------------------------------------


class TestOverlayReadmes:
    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_readme_exists_and_long_enough(self, env):
        p = OVERLAYS / env / "README.md"
        text = read_text(p)
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert len(lines) >= 6, f"{env}/README.md needs >=6 non-empty lines"

    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_readme_apply_command(self, env):
        p = OVERLAYS / env / "README.md"
        text = read_text(p)
        assert "kubectl apply -k" in text, f"{env}/README.md needs apply -k command"
        assert f"overlays/{env}" in text, f"{env}/README.md must name its overlay"

    @pytest.mark.parametrize(
        "env, host",
        [
            ("dev", "dev.omni-one.local"),
            ("staging", "staging.omni-one.example.com"),
            ("prod", "omni-one.example.com"),
        ],
    )
    def test_readme_hostname(self, env, host):
        p = OVERLAYS / env / "README.md"
        assert host in read_text(p), f"{env}/README.md must document {host}"


# ---------------------------------------------------------------------------
# compose files
# ---------------------------------------------------------------------------


def load_compose(p: Path) -> dict:
    assert p.is_file(), f"missing {p.relative_to(REPO)}"
    if HAS_YAML:
        with open(p, encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        assert isinstance(d, dict), f"{p.name} must be a mapping"
        return d
    text = p.read_text(encoding="utf-8")
    assert "services:" in text and "api:" in text
    return {}


class TestComposeShape:
    @pytest.mark.parametrize("p", [DEV_COMPOSE, PROD_COMPOSE], ids=["dev", "prod"])
    def test_file_exists(self, p):
        assert p.is_file()

    @pytest.mark.parametrize("p", [DEV_COMPOSE, PROD_COMPOSE], ids=["dev", "prod"])
    def test_services_api_present(self, p):
        d = load_compose(p)
        if not HAS_YAML:
            return
        assert "services" in d and "api" in d["services"], f"{p.name}: services.api"

    @pytest.mark.parametrize("p", [DEV_COMPOSE, PROD_COMPOSE], ids=["dev", "prod"])
    def test_volumes_present(self, p):
        d = load_compose(p)
        if not HAS_YAML:
            return
        api = d["services"]["api"]
        assert "volumes" in api and len(api["volumes"]) > 0, f"{p.name}: api.volumes"

    @pytest.mark.parametrize("p", [DEV_COMPOSE, PROD_COMPOSE], ids=["dev", "prod"])
    def test_ports_present(self, p):
        d = load_compose(p)
        if not HAS_YAML:
            return
        api = d["services"]["api"]
        assert "ports" in api and len(api["ports"]) > 0, f"{p.name}: api.ports"
        assert "5003" in json.dumps(api["ports"]), f"{p.name}: must expose 5003"

    @pytest.mark.parametrize("p", [DEV_COMPOSE, PROD_COMPOSE], ids=["dev", "prod"])
    def test_top_level_volumes(self, p):
        d = load_compose(p)
        if not HAS_YAML:
            return
        assert "volumes" in d and len(d["volumes"]) > 0, f"{p.name}: top-level volumes"


class TestComposeDev:
    def test_hot_reload_src_volume(self):
        text = read_text(DEV_COMPOSE)
        # live source mount: host ./src -> container /app/src
        assert "/app/src" in text, "dev needs /app/src mount"
        assert "src" in text and "volumes:" in text

    def test_debug_env(self):
        text = read_text(DEV_COMPOSE).lower()
        assert "debug" in text, "dev needs debug env (LOG_LEVEL=debug)"

    def test_reload_command(self):
        assert "--reload" in read_text(DEV_COMPOSE)

    def test_dev_does_not_force_restart_always(self):
        d = load_compose(DEV_COMPOSE)
        if not HAS_YAML:
            return
        assert d["services"]["api"].get("restart") != "always"


class TestComposeProd:
    def test_restart_always(self):
        d = load_compose(PROD_COMPOSE)
        text = read_text(PROD_COMPOSE)
        assert "always" in text, "prod needs restart: always"
        if HAS_YAML:
            assert d["services"]["api"].get("restart") == "always"

    def test_resource_limits(self):
        d = load_compose(PROD_COMPOSE)
        text = read_text(PROD_COMPOSE)
        assert "limits" in text, "prod needs deploy.resources.limits"
        if HAS_YAML:
            deploy = d["services"]["api"].get("deploy", {})
            assert "resources" in deploy
            assert "limits" in deploy["resources"]

    def test_logging_rotation(self):
        d = load_compose(PROD_COMPOSE)
        text = read_text(PROD_COMPOSE)
        assert "max-size" in text and "max-file" in text, "prod logging rotation"
        if HAS_YAML:
            logging = d["services"]["api"].get("logging", {})
            opts = logging.get("options", {})
            assert "max-size" in opts and "max-file" in opts


class TestComposeReadme:
    def test_exists(self):
        assert (COMPOSE / "README.md").is_file()

    def test_which_file_for_which_env(self):
        text = read_text(COMPOSE / "README.md").lower()
        assert "docker-compose.dev.yml" in text
        assert "docker-compose.prod.yml" in text
        assert "dev" in text and "prod" in text

    def test_data_volume_backup_note(self):
        text = read_text(COMPOSE / "README.md").lower()
        assert "backup" in text, "compose README needs backup note"
        assert "volume" in text, "compose README must mention data volume"


# ---------------------------------------------------------------------------
# devcontainer
# ---------------------------------------------------------------------------


class TestDevcontainer:
    def test_file_exists(self):
        assert DEVCONTAINER.is_file()

    def test_valid_json(self):
        d = json.loads(read_text(DEVCONTAINER))
        assert isinstance(d, dict)

    def test_forward_ports_contains_5003(self):
        d = json.loads(read_text(DEVCONTAINER))
        fps = d.get("forwardPorts", [])
        assert 5003 in fps, "forwardPorts must contain 5003"

    def test_python_311_image(self):
        d = json.loads(read_text(DEVCONTAINER))
        blob = json.dumps(d)
        assert "3.11" in blob, "image must be python 3.11"
        assert "image" in d

    def test_post_create_installs(self):
        d = json.loads(read_text(DEVCONTAINER))
        blob = json.dumps(d).lower()
        assert "pip install" in blob
        assert "requirements-seller" in blob
        assert "-e" in blob, "postCreate must pip install -e ."

    def test_extensions_python_yaml(self):
        d = json.loads(read_text(DEVCONTAINER))
        blob = json.dumps(d).lower()
        assert "python" in blob and "yaml" in blob

    def test_devcontainer_readme(self):
        p = REPO / ".devcontainer" / "README.md"
        assert p.is_file()
        assert len(read_text(p).splitlines()) >= 5


# ---------------------------------------------------------------------------
# Tiltfile
# ---------------------------------------------------------------------------


class TestTiltfile:
    def test_exists(self):
        assert TILTFILE.is_file()

    def test_mentions_docker_build(self):
        assert "docker_build" in read_text(TILTFILE)

    def test_mentions_k8s_yaml(self):
        assert "k8s_yaml" in read_text(TILTFILE)

    def test_mentions_port_forward(self):
        assert "port_forward" in read_text(TILTFILE)

    def test_kustomize_dev_overlay(self):
        text = read_text(TILTFILE)
        assert "kustomize" in text
        assert "overlays/dev" in text

    def test_port_5003(self):
        assert "5003" in read_text(TILTFILE)

    def test_live_update_src(self):
        text = read_text(TILTFILE)
        assert "live_update" in text
        assert "src" in text

    def test_trigger_tests_button(self):
        text = read_text(TILTFILE)
        assert "local_resource" in text
        assert "pytest" in text
        assert "unit" in text.lower()

    def test_docker_image_name(self):
        assert "omni-one" in read_text(TILTFILE)

    def test_reasonable_length(self):
        lines = read_text(TILTFILE).splitlines()
        assert len(lines) >= 100, f"Tiltfile ~150 lines, got {len(lines)}"


# ---------------------------------------------------------------------------
# backup scripts still bash -n clean + grafana regression guard
# ---------------------------------------------------------------------------


class TestBackupScripts:
    @pytest.mark.parametrize("sh", [BACKUP_SH, RESTORE_SH], ids=["backup", "restore"])
    def test_exists(self, sh):
        assert sh.is_file(), f"missing {sh.relative_to(REPO)}"

    @pytest.mark.parametrize("sh", [BACKUP_SH, RESTORE_SH], ids=["backup", "restore"])
    def test_bash_n_clean(self, sh):
        r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
        assert r.returncode == 0, f"bash -n {sh.name} failed: {r.stderr}"

    def test_backup_still_mentions_manifest(self):
        assert "sha256" in read_text(BACKUP_SH).lower()

    def test_restore_still_guards_overwrite(self):
        assert "RESTORE_OVERWRITE" in read_text(RESTORE_SH)


class TestGrafanaDashboard:
    def test_exists(self):
        assert DASHBOARD.is_file()

    def test_valid_json(self):
        d = json.loads(read_text(DASHBOARD))
        assert isinstance(d, dict)

    def test_at_least_four_panels(self):
        d = json.loads(read_text(DASHBOARD))
        panels = d.get("panels", [])
        assert isinstance(panels, list) and len(panels) >= 4, "dashboard >=4 panels"

    def test_panels_have_titles(self):
        d = json.loads(read_text(DASHBOARD))
        for panel in d["panels"]:
            assert panel.get("title"), "each panel needs a title"
