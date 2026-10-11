#!/bin/sh
# omni-one backup — tar DUCKDB + AUDIT + closes with timestamp + sha256 manifest.
# POSIX sh (no bashisms). Idempotent; keeps last 14 backups (retention note below).
#
# Retention: daily use keeps 14 archives (~small: duckdb + jsonl + close CSVs).
#   Old archives are pruned with: find "$BACKUP_DIR" -name 'omni-backup-*.tgz' -mtime +14 -delete
#   Adjust BACKUP_KEEP_DAYS for your shop (accountants usually want 90d of closes —
#   keep closes/ separately, see README.md).
set -eu

DATA_DIR="${OMNI_DATA_DIR:-./data}"
DUCKDB_PATH="${DUCKDB_PATH:-$DATA_DIR/omni.duckdb}"
AUDIT_PATH="${AUDIT_PATH:-$DATA_DIR/audit.jsonl}"
CLOSES_DIR="${CLOSES_DIR:-./close_today}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/omni-backup.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT INT TERM

[ -e "$DUCKDB_PATH" ] || echo "warn: missing $DUCKDB_PATH (fresh install?)" >&2
[ -e "$AUDIT_PATH" ] || echo "warn: missing $AUDIT_PATH (fresh install?)" >&2
[ -d "$CLOSES_DIR" ] || echo "warn: missing $CLOSES_DIR (no closes yet?)" >&2

[ -e "$DUCKDB_PATH" ] && cp "$DUCKDB_PATH" "$STAGE/omni.duckdb"
[ -e "$AUDIT_PATH" ] && cp "$AUDIT_PATH" "$STAGE/audit.jsonl"
if [ -d "$CLOSES_DIR" ]; then
  mkdir -p "$STAGE/closes"
  cp -r "$CLOSES_DIR/." "$STAGE/closes/"
fi

ARCHIVE="$BACKUP_DIR/omni-backup-$TS.tgz"
tar -czf "$ARCHIVE" -C "$STAGE" .

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$BACKUP_DIR" && sha256sum "$(basename "$ARCHIVE")" > "$ARCHIVE.sha256")
elif command -v shasum >/dev/null 2>&1; then
  (cd "$BACKUP_DIR" && shasum -a 256 "$(basename "$ARCHIVE")" > "$ARCHIVE.sha256")
else
  echo "error: need sha256sum or shasum" >&2; exit 1
fi

echo "backup: $ARCHIVE"
cat "$ARCHIVE.sha256"

# retention prune
find "$BACKUP_DIR" -name 'omni-backup-*.tgz' -mtime +"$BACKUP_KEEP_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name 'omni-backup-*.tgz.sha256' -mtime +"$BACKUP_KEEP_DAYS" -delete 2>/dev/null || true
