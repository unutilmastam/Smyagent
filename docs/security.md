# Security

Implemented items are marked ✅; everything else is a requirement for the
milestone named in brackets.

## Secrets
- ✅ All secrets come from environment variables; `.env` and credential files are git-ignored.
- ✅ `.env.example` contains placeholders only.
- ✅ Production startup refuses a missing or weak `APP_SECRET_KEY`; error messages name the variable, never its value.
- ✅ Log processor redacts keys that look like secrets (`token`, `key`, `secret`, `password`, `authorization`, `cookie`).
- Secret scanning in CI [M1 follow-up: gitleaks action].

## HTTP surface
- ✅ `/api/v1/health` and `/api/v1/ready` expose no versions, hostnames or paths.
- ✅ OpenAPI docs disabled when `APP_ENV=production`.
- ✅ Generic 500 response; details only in logs with the request ID.
- Auth: Argon2 hashing, HTTP-only SameSite cookies, CSRF tokens, login rate limit, optional TOTP [M3].
- No default admin; owner created with `python -m app.cli create-owner` [M3].

## Outbound requests
- SSRF-safe fetcher: scheme allow-list, DNS resolution with private/loopback/link-local/CGNAT/multicast/metadata blocking (IPv4+IPv6), re-validation per redirect, size/time/content-type limits, robots.txt [M5].
- TLS verification is never disabled.

## AI safety
- External content is data, never instructions; the model can only *propose* sends, approvals, price changes or state transitions [M5+].
- Budget guard before every optional AI call [M11, skeleton earlier].

## Messaging
- Mustafo persona always discloses it is an AI (`docs/persona.md`).
- Suppression list checked before every send; global kill switch checked immediately before every provider call [M3b, M9].
- No Telegram userbots, no unsolicited SMS/WhatsApp, no Instagram DM automation.

## Supply chain
- ✅ Dependencies declared with lower bounds in `pyproject.toml`; `pip-audit` runs in CI.
- Pin exact versions in a lock/constraints file once hosting Python version is verified [M2].

## Reporting
Security issues: contact the owner directly (Telegram @ITcoDe_Uz). Do not open public issues with exploit details.
