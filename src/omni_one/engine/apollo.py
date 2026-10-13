"""
Apollo — Free alternative to Palantir Apollo (deployment)
=========================================================
Palantir Apollo: manages deploys across classified air-gapped envs, $M fees.
Free alternative: Docker Compose + FastAPI + health checks + versioned configs, $0.

This module generates:
  - docker-compose.yml (free orchestration, no Kubernetes fees for small)
  - .env (free config)
  - health manifest (like Apollo's health checks)

Tech: Docker (free), Python (free). Cheapest efficient: single compose file instead of K8s.

Use: `python -m omni_one.palantir_free.apollo --out /tmp/omni_apollo`
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
import json

COMPOSE_TEMPLATE = """# Omni-One Apollo-Free — Generated {at}
# Cost: $0 (vs Palantir Apollo licensed). Run: docker compose up
version: "3.9"
services:
  api:
    build: .
    ports: ["5003:5003"]
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5003/health"]
      interval: 10s
      retries: 3
    deploy:
      resources:
        limits: {{cpus: '1', memory: 1G}}
  duckdb:
    image: duckdb/duckdb:latest
    volumes: ["./data:/data"]
  # Optional: add weaviate local free instead of Pinecone fees
  # weaviate:
  #   image: semitechnologies/weaviate:1.25.0
  #   ports: ["8080:8080"]
"""

ENV_TEMPLATE = """# Free Apollo env — no Palantir license
ENVIRONMENT=production
GOOGLE_API_KEY=
# Leave empty for free mock LLM; set for live (SELLER_LLM=google + key)
SELLER_LLM=mock
SELLER_MAX_LLM_USD=0.0
# PROD: generate random keys — python3 -c "import secrets; print(secrets.token_hex(32))"
# demo-key is REJECTED in production by settings validator
VALID_API_KEYS=change-me-to-random-32-chars-min
SECRET_KEY=change-me-to-random-32-chars-minimum
# Free: use DuckDB file, no Snowflake fees
DUCKDB_PATH=/data/omni.duckdb
AUDIT_PATH=/data/audit.jsonl
ALLOWED_ROOT=/data/inbox
"""

def generate(out_dir: Path, with_weaviate: bool = False) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "docker-compose.yml").write_text(COMPOSE_TEMPLATE.format(at=datetime.now().isoformat()))
    (out / ".env").write_text(ENV_TEMPLATE)
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "free": True,
        "palantir_alternative": "Apollo -> Docker Compose (free)",
        "cost_usd": 0.0,
        "services": ["api", "duckdb"] + (["weaviate"] if with_weaviate else []),
        "health_endpoint": "/health",
        "note": "Run `docker compose up` — no Palantir fees. For air-gapped, `docker save` images.",
    }
    (out / "apollo_manifest.json").write_text(json.dumps(manifest, indent=2))
    return out

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate free Apollo alternative")
    parser.add_argument("--out", type=str, default="/tmp/omni_apollo")
    parser.add_argument("--with-weaviate", action="store_true")
    args = parser.parse_args()
    out = generate(Path(args.out), with_weaviate=args.with_weaviate)
    print(f"Generated free Apollo alternative in {out}")
    print((out / "docker-compose.yml").read_text()[:400])
