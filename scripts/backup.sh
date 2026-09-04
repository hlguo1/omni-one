#!/bin/bash
# Free backup: tar DuckDB + Parquet + audit JSONL. No cloud needed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"
OUT="${1:-$ROOT/backup-$(date +%F).tar.gz}"
mkdir -p "$DATA" "$DATA/inbox" "$DATA/parquet"
tar -czf "$OUT" -C "$ROOT" data/omni.duckdb data/audit.jsonl data/parquet data/kv.json data/workshop.json data/ontology_objects.json data/briefing_cache 2>/dev/null || \
tar -czf "$OUT" -C "$ROOT" data 2>/dev/null || true
echo "Backup -> $OUT"
ls -lh "$OUT"
