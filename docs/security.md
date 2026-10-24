# Security

Implemented items are marked ✅; everything else is a requirement for the
milestone named in brackets.

## Secrets
- ✅ All secrets come from environment variables; `.env` and credential files are git-ignored.
- ✅ `.env.example` contains placeholders only.
- ✅ Production startup refuses a missing or weak `APP_SECRET_KEY`; error messages name the variable, never its value.
- ✅ Log processor redacts keys that look like secrets (`token`, `key`, `secret`, `password`, `authorization`, `cookie`).
- ✅ Secret scanning in CI (gitleaks).

## HTTP surface
- ✅ `/api/v1/health` and `/api/v1/ready` expose no versions, hostnames or paths.
- ✅ OpenAPI docs disabled when `APP_ENV=production`.
- ✅ Generic 500 response; details only in logs with the request ID.
- ✅ Passwords hashed with Argon2id (`app/core/security.py`); policy: ≥12 chars, not repetitive, no username inside. Hashes upgraded on login if parameters change.
- ✅ Server-side sessions: cookie `smy_session` holds a random 256-bit token; only its SHA-256 is stored. HttpOnly, SameSite=Lax, Secure when HTTPS/production. 30-day absolute, 7-day idle expiry.
- ✅ CSRF: per-session token required on every state-changing request (form field `csrf_token` or `X-CSRF-Token` header for HTMX). Login form uses a double-submit cookie (SameSite=Strict).
- ✅ Login throttling stored in the DB (works across Passenger processes): 5 failures per username or 20 per IP in 15 min → HTTP 429, even for the correct password. IPs stored only as an HMAC.
- ✅ Same error for unknown user and wrong password; a dummy Argon2 verification runs for unknown users (no timing oracle).
- ✅ Post-login redirect accepts local paths only (no open redirect).
- ✅ Audit log: login, failed login, throttled login, logout, owner creation.
- ✅ Security headers on every response: CSP (`'self'` only), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`; HSTS in production. Private pages send `Cache-Control: no-store`.
- ✅ No default admin; owner created once with `python -m app.cli create-owner` (refuses if an owner exists).
- Optional TOTP for the owner [M3d].

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
