#!/bin/sh
# Omni-One production entrypoint (POSIX sh — runs as non-root appuser).
#   1. migrate/ensure data dir layout (duckdb, audit, inbox, parquet)
#   2. seed inbox with a .keep + README on first boot
#   3. exec uvicorn on $PORT
set -eu

DATA_DIR="${OMNI_DATA_DIR:-/app/data}"
INBOX_DIR="${SELLER_INBOX:-$DATA_DIR/inbox}"
PORT="${PORT:-5003}"
HOST="${HOST:-0.0.0.0}"

# 1. migrate data dir: create every path the store expects (idempotent)
mkdir -p "$DATA_DIR" "$INBOX_DIR" "$DATA_DIR/parquet" "$DATA_DIR/briefing_cache"
for f in "${AUDIT_PATH:-$DATA_DIR/audit.jsonl}" "${DUCKDB_PATH:-$DATA_DIR/omni.duckdb}"; do
  case "$f" in
    *.jsonl) [ -e "$f" ] || : >> "$f" ;;
    *) : ;;
  esac
done

# 2. seed inbox so first-run briefing/close has somewhere to drop CSVs
if [ ! -e "$INBOX_DIR/.keep" ] && [ -z "$(ls -A "$INBOX_DIR" 2>/dev/null)" ]; then
  : >> "$INBOX_DIR/.keep"
  cat > "$INBOX_DIR/README.txt" <<'EOF'
Drop seller CSVs here (shopify_orders.csv, inventory.csv, reviews.csv, ...).
Only this inbox dir is served — paths outside it are rejected (path-traversal guard).
EOF
fi

echo "omni-one entrypoint: data=$DATA_DIR inbox=$INBOX_DIR port=$PORT"
# 3. exec app (factory app; single worker — scale via k8s replicas/HPA)
exec uvicorn omni_one.api.fastapi_app:create_omni_one_app --factory \
  --host "$HOST" --port "$PORT"
