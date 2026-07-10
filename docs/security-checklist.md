# Security checklist

Baseline controls for deploying Lead CRM as a multi-tenant SaaS.

## Authentication & access

- [ ] **HTTPS only** — `SECURE_SSL_REDIRECT=True`, TLS terminated at the load balancer or reverse proxy.
- [ ] **Secure cookies** — `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` enabled in production (`djcrm/settings/prod.py`).
- [ ] **Session lifetime** — `SESSION_COOKIE_AGE` (default 12h) and `SESSION_EXPIRE_AT_BROWSER_CLOSE` match your policy.
- [ ] **Rate limits** — auth (`/login/`, `/signup/`, `/reset-password/`) and webhooks (`/webhooks/*`) are IP-limited via `security.middleware.RateLimitMiddleware`. Tune `AUTH_*_RATE_LIMIT` and `WEBHOOK_RATE_LIMIT` in env.
- [ ] **Owner 2FA** — owners can enable TOTP at **Settings → Security**. Require 2FA for all owners in your org policy.
- [ ] **Django admin** — keep `DJANGO_ADMIN_ENABLED=False` in production unless staff need `/admin/`; when enabled, only `is_staff` users can access it.

## Application hardening

- [ ] **CSP & headers** — `SecurityHeadersMiddleware` sets Content-Security-Policy, `X-Content-Type-Options`, `Referrer-Policy`, and `Permissions-Policy`. Adjust `CONTENT_SECURITY_POLICY` if you add third-party scripts.
- [ ] **CSRF** — all browser POST forms use `{% csrf_token %}`; API uses Bearer tokens (no session).
- [ ] **Tenant isolation** — verify `TenantMiddleware` and queryset scoping on every new view; never trust client-supplied `organisation_id`.
- [ ] **Public capture** — honeypot + per-IP rate limits on `/f/<public_key>/` (see `capture` app).
- [ ] **Webhook signatures** — Stripe (`STRIPE_WEBHOOK_SECRET`) and email provider secrets validated before processing events.

## Secrets & infrastructure

- [ ] **Environment variables** — `SECRET_KEY`, database URL, Stripe keys, email tokens, and `SENTRY_DSN` stored in a secrets manager, not in git.
- [ ] **Database** — PostgreSQL with least-privilege DB user; follow [postgres-backup.md](./postgres-backup.md) for backups and restore drills.
- [ ] **Redis** — restrict network access to Celery broker; use TLS/password in production if exposed beyond localhost.
- [ ] **Dependency updates** — pin versions in `requirements.txt`; review Django security releases promptly.

## Monitoring & incident response

- [ ] **Sentry** — `SENTRY_DSN` configured; alerts on 5xx and auth anomalies.
- [ ] **Structured logs** — ship `LOGGING` console output to your log aggregator; retain audit trail (`/app/audit/`).
- [ ] **Runbook** — document who rotates API tokens, revokes compromised owner accounts, and restores from backup.

## Pre-launch smoke tests

1. Confirm login rate limit returns HTTP 429 after repeated failures.
2. Enable owner 2FA, log out, and complete login with TOTP code.
3. Verify `/admin/` returns 404 when `DJANGO_ADMIN_ENABLED=False`.
4. POST unsigned webhook payloads and confirm rejection.
5. Run `python manage.py test` in CI before each deploy.
