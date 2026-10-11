# Cron — the 7am Daily Close, every shop, every day

## One shop

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

## All shops (`close_all.sh`)

```bash
# layout: ./shops/<shop>/ contains that shop's messy CSVs/DMs/photos
./deploy/cron/close_all.sh              # closes every shop under ./shops
SHOPS_DIR=./data/shops OUT_BASE=./closes ./deploy/cron/close_all.sh
SHOP_LOCALE=es ./deploy/cron/close_all.sh   # Spanish drafts, same numbers
```

Writes `<out>/<shop>/close.json + close.csv + reorder.csv + replies.txt + po.txt`
plus `manifest.csv` (shop, profit, at-risk, reorders, leaks). Non-zero exit if any
shop fails to ingest — check `ingest_report.errors` in that shop's `close.json`.

## Language

`SHOP_LOCALE` ∈ `en es zh fr de` (default `en`). Only reply + PO drafts switch language;
KPIs, reorder math, citations identical (contract-tested in
`tests/unit/test_api_close_contract.py::test_close_locale_parity_api`).

## Retention

Keep 90 days of closes minimum (tax season wants 12 months). `deploy/backup/backup.sh`
covers `./closes` alongside DuckDB + audit log. POSIX sh throughout — runs on macOS
cron, Linux crontab, and GitHub Actions `schedule` alike.

## 7am template (`7am-close.cron`)

Copy the lines into `crontab -e`, replacing paths. Stagger multi-shop runs by 5 minutes
if the box is small (each close is seconds, but OCR photos spike CPU).

## Schedule sketch (single small box)

| Time | Job | Why |
|---|---|---|
| 07:00 | close_all.sh | owners read replies with coffee |
| 07:15 | backup.sh | closes + DB + audit snapshotted |
| 19:00 | close_all.sh (peak only) | evening triage in season |
