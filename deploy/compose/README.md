# omni-one — compose environments

Which file for which env:

- `docker-compose.dev.yml` — LOCAL DEV: hot-reload `src/` volume, `LOG_LEVEL=debug`,
  `--reload`, `restart: "no"`. Run: `docker compose -f deploy/compose/docker-compose.dev.yml up --build`.
- `docker-compose.prod.yml` — PROD: `restart: always`, CPU/mem `deploy.resources`
  limits+reservations, `json-file` log rotation (`max-size: 10m`, `max-file: 5`).
  Run: `docker compose -f deploy/compose/docker-compose.prod.yml up -d --build`.
- Root `docker-compose.yml` — SIMPLE single-service free deploy (laptop default).

Data volume backup note:

- Dev data lives in named volume `omni-dev-data`, prod in `omni-prod-data`
  (both mounted at `/app/data`: duckdb + `audit.jsonl` + closes).
- Back up BEFORE compose down -v: `bash deploy/backup/backup.sh` with
  `OMNI_DATA_DIR` pointing at the volume path, or `docker run --rm -v
  omni-prod-data:/app/data -v "$PWD/backups:/backups" ... tar -czf ...`.
- `docker compose down -v` DELETES named volumes — never use `-v` in prod
  without a verified `backups/omni-backup-*.tgz` + `.sha256` manifest.
- Restore with `bash deploy/backup/restore.sh <backups/omni-backup-TS.tgz>`.
