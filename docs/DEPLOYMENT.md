# Deployment (laptop → VPS, $0 → cheap)

## Laptop (default)

```bash
pip install -r requirements-seller.txt && pip install -e .
omni-one close --folder /tmp/my_shop --out ./close_today
omni-one serve --port 5003
```

## Docker (single service)

```bash
docker build -t omni-one:latest .
docker compose up -d && curl -sf http://localhost:5003/health
```

`docker-compose.yml`: one `api` service, `./data` volume (`DUCKDB_PATH`, `AUDIT_PATH`,
`ALLOWED_ROOT=/app/data/inbox`), `SELLER_LLM=mock`. Drop seller files into `./data/inbox`.

## Production hardening

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # twice
ENVIRONMENT=production VALID_API_KEYS=<32+> SECRET_KEY=<32+> docker compose up -d
```

Demo keys (`demo-key/test-key`) are rejected in production; `/admin/*` needs key;
uploads capped (5MB, type-checked, 60/min); folders jailed to `ALLOWED_ROOT`;
audit `verify()` proves tamper-evidence. See `SECURITY.md`.

## Cron: 7am Daily Close

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

## Monitoring

Scrape `GET /metrics` (briefings/scenarios/closes/vision counters + `omni_one_up`).
