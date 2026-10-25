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

## SSRF-safe fetcher (M5) — `app/infrastructure/http_fetcher/`
- ✅ http/https only; ports 80/443/8080/8443; no credentials in URLs.
- ✅ DNS resolved by us; **every** answer must be public (`is_blocked_ip`: private, loopback, link-local incl. 169.254.169.254, CGNAT, multicast, reserved, unspecified, IPv6 ULA/link-local, IPv4-mapped, 6to4, Teredo and NAT64 judged by the embedded IPv4).
- ✅ Connection goes to the validated IP (Host header + TLS SNI keep the name; certificate verified against the name — tested locally with a self-signed CA); no env proxy (`trust_env=False`) so the name is never re-resolved.
- ✅ Redirects followed manually, max 5, each hop fully re-validated.
- ✅ Timeouts (5 s connect / 10 s read / 25 s budget), 2 MB body limit (header and streamed), content-type allowlist, 2 s per-host spacing, robots.txt respected, honest User-Agent.
- ✅ No raw HTML stored: extracted text excerpt + SHA-256 hash + checks only.

## Kill switch (M3b)
- ✅ Only the owner changes agent states (dashboard, API, owner bot); viewers and non-admin Telegram users get 403 / no effect. Every change is audit-logged with actor, previous/new state and reason.
- ✅ `ControlGate` re-reads the DB at every check: job claim, between steps, immediately before any outbound send (also blocked while `OUTBOUND_SENDING_ENABLED=false`), before any AI call. Missing control rows count as STOPPED (fail closed).
- ✅ Global STOP cancels queued `outbound.*` jobs and running jobs/runs; module STOP cancels that module's running work and leaves its queue for reactivation.
- ✅ STOP is always one tap away (top bar) with a confirmation dialog.

## Telegram owner bot
- ✅ Webhook accepted only with the correct `X-Telegram-Bot-Api-Secret-Token` (constant-time compare); 403 otherwise, nothing stored. Endpoint returns 404 while the bot is not configured.
- ✅ Authorization by numeric user ID (`TELEGRAM_ADMIN_IDS`) in private chats only; bots and groups ignored. Unauthorized senders get no reply and are audit-logged.
- ✅ Each `update_id` processed once (`inbound_events` unique `(channel, external_id)`), so Telegram retries never repeat an action.
- ✅ Payload size limit (256 KB); unparseable payloads acknowledged and dropped.
- ✅ Bot token only in env; client errors report the exception type, never the URL that contains the token; log redaction also masks `<digits>:<token>` patterns.
- ✅ Production refuses a bot token without a ≥32-char webhook secret and admin IDs.

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

## Review M11 (2026-10-25)

Checked in code and tests at the state of M11 (live at agent.itcode.uz):

| Area | Result |
|---|---|
| Auth | Argon2 hashes, login throttling, session cookies `HttpOnly` + `SameSite` + `Secure` (https), no default admin (CLI bootstrap) — ✅ |
| CSRF | Every state-changing form and JSON call requires the token (tests per page, incl. `/jobs` retry/cancel and Virtual Office controls) — ✅ |
| Redirects | `next` targets white-listed (`/control`, `/control/office`; login keeps local paths only) — ✅ fixed in M3c-office |
| Headers | CSP `'self'` (no inline script; JSON data blocks only), `frame-ancestors 'none'`, nosniff, Referrer-Policy, Permissions-Policy, HSTS in production — ✅ |
| Output | Jinja2 autoescape; office/JS sets server text with `textContent`/canvas only (test asserts no `innerHTML`) — ✅ |
| Webhooks | Constant-time secret compare, numeric admin IDs, idempotent updates, size limit — ✅ |
| Secrets | `.env` mode 600 outside Git; setup wizard never echoes secrets and flushes pending input; tokens redacted in logs; DB password via mysqldump/mysql option file (mode 600), never argv — ✅ |
| Backups | Mode 600 in `~/smyagent_data/backups` (outside the web root); verification + restore drill into a scratch DB that is emptied afterwards — ✅ M11 |
| Dependencies | `pip-audit`: no known vulnerabilities (2026-10-25); runs in CI — ✅ |
| API docs | `/docs` and `/openapi.json` disabled in production — ✅ |
| Open items | Optional TOTP for the owner (M3-totp) still not built — recommended now that the dashboard is public; Telegram tokens were rotated once after being shown on screen (done by the owner). |

## Reporting
Security issues: contact the owner directly (Telegram @ITcoDe_Uz). Do not open public issues with exploit details.
