# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.x     | Yes       |

## Reporting a vulnerability

**Do not open a public issue for vulnerabilities.** Instead:

1. Open a draft GitHub Security Advisory on this repo, or
2. Open an issue titled `[SECURITY] <short>` with minimal detail and ask for a contact — a maintainer will follow up.

We aim to acknowledge within 72h and ship a fix + regression test promptly.

## Built-in posture

- API keys required on `/admin/*` (fail closed; demo keys rejected in `ENVIRONMENT=production`).
- Seller folder access is jailed to `ALLOWED_ROOT` (`resolve_seller_folder`); path traversal → 400.
- Uploads: extension + magic-byte + size cap (`max_upload_mb`, default 5) + 60/min rate limit.
- Audit: hash-chained `AuditLog.verify()` across pipeline/ontology/workshop/AIP/foundry.
- No secrets in repo: `.env` is gitignored; copy `.env.example`.

## Hardening checklist for production

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"  # VALID_API_KEYS + SECRET_KEY
ENVIRONMENT=production VALID_API_KEYS=<random-32+> SECRET_KEY=<random-32+>
```

See `src/omni_one/infra/security.py`.
