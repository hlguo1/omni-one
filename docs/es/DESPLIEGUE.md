# Despliegue (portátil → VPS, $0 → barato)

> Filosofía: primero el portátil (privado, offline, $0), luego un VPS barato con un solo servicio.
> Sin Kubernetes obligatorio. Un `api`, un volumen, una clave.

## Portátil (por defecto)

El modo diario del vendedor. Sin Docker, sin red, con LLM simulado.

```bash
pip install -r requirements-seller.txt && pip install -e .
omni-one close --folder /tmp/my_shop --out ./close_today
omni-one serve --port 5003
```

Comprueba:

- [ ] `omni-one doctor` en verde.
- [ ] `close.json` con `headline` dorada (`Profit $169.09`).
- [ ] API en `http://localhost:5003` con docs en `/api/docs`.
- [ ] Salud: `/health`, `/readiness`, `/status`, `/ping`. Métricas: `/metrics`.

Variables útiles en portátil:

- `SELLER_LLM=mock` (por defecto, $0).
- `ALLOWED_ROOT=/app/data/inbox` solo aplica en Docker/prod.

## Docker (servicio único)

Un solo servicio `api`, volumen `./data`, LLM simulado. Ideal para VPS pequeño.

```bash
docker build -t omni-one:latest .
docker compose up -d && curl -sf http://localhost:5003/health
```

`docker-compose.yml`: one `api` service, `./data` volume (`DUCKDB_PATH`, `AUDIT_PATH`,
`ALLOWED_ROOT=/app/data/inbox`), `SELLER_LLM=mock`. Drop seller files into `./data/inbox`.

Explicación en español:

- `docker-compose.yml` define un único servicio `api` (sin flota de microservicios).
- El volumen `./data` persiste base (`DUCKDB_PATH`), auditoría (`AUDIT_PATH`) e inbox.
- `ALLOWED_ROOT=/app/data/inbox` enjaula las carpetas: el cierre no lee fuera.
- `SELLER_LLM=mock` mantiene $0 (sin llamadas de pago).
- Suelta los archivos del vendedor en `./data/inbox` y corre el cierre contra ahí.
- Verifica con `curl -sf http://localhost:5003/health` tras `docker compose up -d`.

Reconstruir y ver logs:

```bash
docker compose up -d --build
docker compose logs -f api
docker compose ps
```

## Endurecimiento en producción

Genera dos secretos de 32 bytes (uno para API, otro para firma) y arranca en modo producción.

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # twice
ENVIRONMENT=production VALID_API_KEYS=<32+> SECRET_KEY=<32+> docker compose up -d
```

Demo keys (`demo-key/test-key`) are rejected in production; `/admin/*` needs key;
uploads capped (5MB, type-checked, 60/min); folders jailed to `ALLOWED_ROOT`;
audit `verify()` proves tamper-evidence. See `SECURITY.md`.

Lista de control en español:

- [ ] `ENVIRONMENT=production` activado (falla cerrado sin claves).
- [ ] `VALID_API_KEYS` de 32+ caracteres, distinta de demo.
- [ ] `SECRET_KEY` de 32+ caracteres, generada con `secrets.token_hex(32)`.
- [ ] Las claves demo (`demo-key`/`test-key`) se rechazan en producción.
- [ ] `/admin/*` exige `X-API-Key`/`Bearer` (ver `GET /api/v1/admin/services`, `POST /api/v1/admin/clear-cache`).
- [ ] Subidas limitadas (5MB, tipo verificado, 60/min).
- [ ] Auditoría `verify()` verificada. Ver `SECURITY.md`.

## Cron: cierre diario 7am

```cron
0 7 * * * cd /path/to/omni-one && PYTHONPATH=src python3 -m omni_one.cli close --folder ./data/inbox --out ./close_$(date +\%F) >> ./close_cron.log 2>&1
```

Notas:

- Cambia `/path/to/omni-one` por tu ruta real.
- `--folder ./data/inbox` debe estar bajo `ALLOWED_ROOT` en Docker.
- `--out ./close_$(date +\%F)` crea una carpeta por día (`close_2026-10-11`).
- Revisa `./close_cron.log` si una mañana no hay paquete.
- Combina con email en v1.2 (ver `docs/es/HOJA_DE_RUTA.md`).

## Monitorización

Scrape `GET /metrics` (briefings/scenarios/closes/vision counters + `omni_one_up`).

En español:

- Raspa `GET /metrics` con Prometheus cada 15–30s.
- Contadores: briefings, escenarios, cierres, visión + `omni_one_up`.
- Alerta si `omni_one_up == 0` o si `closes_total` no crece tras las 7am.
- Guarda `./close_cron.log` y rota los `close_*` viejos a frío/USB.

## Resumen de rutas por entorno

| Entorno | Comando | Coste |
|---|---|---|
| Portátil | `omni-one close --folder /tmp/my_shop --out ./close_today` | $0 |
| Docker | `docker compose up -d && curl -sf http://localhost:5003/health` | barato (1 VPS) |
| Prod | `ENVIRONMENT=production VALID_API_KEYS=<32+> SECRET_KEY=<32+> docker compose up -d` | barato + claves |

Ver también: `docs/es/API.md` (18 rutas), `docs/es/CLI.md` (9 comandos), `SECURITY.md`.
