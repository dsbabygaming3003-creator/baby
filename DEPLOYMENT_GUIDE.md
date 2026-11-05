# Deployment Guide

## Verified local deployment

```bash
make setup
make migrate
make run
```

Bind is `0.0.0.0:8000`; web clients use same-origin relative URLs. Production must set `TITAN_ENVIRONMENT=production` and a strong `TITAN_API_KEY`; startup refuses production without it. Mock is disabled in production.

## PostgreSQL Compose reference

`deploy/docker-compose.yml` defines PostgreSQL 18 and a non-root backend image, health checks, persistent volumes and terminal disabled. Set `POSTGRES_PASSWORD`, `TITAN_API_KEY`, and optionally the three OpenAI-compatible variables. Run from `deploy/`:

```bash
docker compose up --build -d
```

**Not executed here:** Docker/PostgreSQL are absent. URL-encode special characters in the database password, place the API behind TLS, use a secret manager instead of shell history, back up before `alembic upgrade head`, and test restore/rollback.

## Production checklist

1. Replace single API key with SSO and scoped RBAC; configure tenant retention/RLS as needed.
2. Pin and scan the container/dependencies; generate SBOM and preserve license notices.
3. Keep terminal disabled until disposable sandbox workers exist.
4. Configure model endpoints/secrets server-side and run health/quality/cost evaluations.
5. Add managed Redis/Temporal only when their actual worker integration is deployed; current app does not claim them.
6. Configure reverse-proxy HTTPS, body/rate limits, observability, backups and incident response.
7. Build Android in a separate pinned JDK/SDK worker; distribute no APK without install/launch evidence.
