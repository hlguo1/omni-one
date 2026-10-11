#!/bin/sh
# omni-one restore — verify sha256 manifest, then restore DUCKDB + AUDIT + closes.
# POSIX sh (no bashisms). Usage: restore.sh <backups/omni-backup-TS.tgz>
# Refuses to overwrite live data without RESTORE_OVERWRITE=1.
set -eu

ARCHIVE="${1:-}"
[ -n "$ARCHIVE" ] || { echo "usage: $0 <omni-backup-TS.tgz>" >&2; exit 2; }
[ -f "$ARCHIVE" ] || { echo "error: not found: $ARCHIVE" >&2; exit 1; }
[ -f "$ARCHIVE.sha256" ] || { echo "error: missing manifest: $ARCHIVE.sha256" >&2; exit 1; }

# 1. verify manifest (must match before anything is touched)
if command -v sha256sum >/dev/null 2>&1; then
  (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$ARCHIVE").sha256") || { echo "error: checksum FAILED" >&2; exit 1; }
elif command -v shasum >/dev/null 2>&1; then
  (cd "$(dirname "$ARCHIVE")" && shasum -a 256 -c "$(basename "$ARCHIVE").sha256") || { echo "error: checksum FAILED" >&2; exit 1; }
else
  echo "error: need sha256sum or shasum" >&2; exit 1
fi
echo "checksum OK: $ARCHIVE"

DATA_DIR="${OMNI_DATA_DIR:-./data}"
DUCKDB_PATH="${DUCKDB_PATH:-$DATA_DIR/omni.duckdb}"
AUDIT_PATH="${AUDIT_PATH:-$DATA_DIR/audit.jsonl}"
CLOSES_DIR="${CLOSES_DIR:-./close_today}"

if [ "${RESTORE_OVERWRITE:-0}" != "1" ]; then
  if [ -e "$DUCKDB_PATH" ] || [ -e "$AUDIT_PATH" ]; then
    echo "error: live data exists; re-run with RESTORE_OVERWRITE=1 to replace" >&2
    exit 1
  fi
fi

STAGE="$(mktemp -d "${TMPDIR:-/tmp}/omni-restore.XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT INT TERM
tar -xzf "$ARCHIVE" -C "$STAGE"

mkdir -p "$(dirname "$DUCKDB_PATH")" "$(dirname "$AUDIT_PATH")" "$CLOSES_DIR"
[ -f "$STAGE/omni.duckdb" ] && cp "$STAGE/omni.duckdb" "$DUCKDB_PATH"
[ -f "$STAGE/audit.jsonl" ] && cp "$STAGE/audit.jsonl" "$AUDIT_PATH"
if [ -d "$STAGE/closes" ]; then
  mkdir -p "$CLOSES_DIR"
  cp -r "$STAGE/closes/." "$CLOSES_DIR/"
fi
echo "restored -> DUCKDB=$DUCKDB_PATH AUDIT=$AUDIT_PATH CLOSES=$CLOSES_DIR"
