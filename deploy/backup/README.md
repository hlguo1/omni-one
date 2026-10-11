# omni-one backups

`backup.sh` tars `DUCKDB_PATH` + `AUDIT_PATH` + `CLOSES_DIR` into
`backups/omni-backup-<timestamp>.tgz` plus a `.sha256` manifest.
`restore.sh` verifies the manifest FIRST, then restores (refuses to
overwrite live data unless `RESTORE_OVERWRITE=1`).

```sh
sh deploy/backup/backup.sh                      # -> backups/omni-backup-*.tgz
RESTORE_OVERWRITE=1 sh deploy/backup/restore.sh backups/omni-backup-<ts>.tgz
```

Env overrides: `OMNI_DATA_DIR`, `DUCKDB_PATH`, `AUDIT_PATH`,
`CLOSES_DIR`, `BACKUP_DIR`, `BACKUP_KEEP_DAYS` (default 14).

## Retention note

Default keeps **14 daily archives** (`find -mtime +14 -delete` at the end
of `backup.sh`). The DuckDB + audit tarball is small; the thing that grows
is `closes/` history — keep 90 days of close CSVs for the accountant by
archiving `close_today/` (or `data/closes/`) to cheap storage separately
and letting the 14-day rolling window cover disaster recovery only.
Sync `backups/` off-box (S3/rsync) — a backup on the same disk is a hope,
not a backup.
