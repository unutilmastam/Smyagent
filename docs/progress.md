# Progress

## Session 1 — 2026-10-25

### Completed
- **M0** — repository inspected (was empty except `CLAUDE.md`); architecture, roadmap, security, cPanel deployment, persona docs; ADR-0001…0006; `scripts/check_environment.py`.
- **M1** — Python project (`pyproject.toml`), settings with production validation, JSON logging with secret redaction, request-ID middleware, error envelope, `/api/v1/health`, `/api/v1/ready`, Passenger startup file via a2wsgi with 503 fallback on misconfiguration, tests, Ruff/Mypy config, GitHub Actions CI (Python 3.10 + 3.12, pip-audit, gitleaks).

### Files
`.env.example`, `.gitignore`, `README.md`, `pyproject.toml`, `.github/workflows/ci.yml`,
`app/__init__.py`, `app/main.py`, `app/core/{config,logging,exceptions,middleware}.py`,
`app/api/v1/health.py`, `deployment/cpanel/passenger_wsgi.py`, `scripts/check_environment.py`,
`docs/{architecture,roadmap,security,deployment-cpanel,persona,progress}.md`, `docs/decisions/*`,
`tests/conftest.py`, `tests/unit/{test_config,test_logging}.py`,
`tests/integration/{test_api,test_wsgi_bridge}.py`.

### Verification (run in Claude Code cloud, Python 3.13)
| Command | Result |
|---|---|
| `pytest` | 25 passed |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 32 files already formatted |
| `mypy` | no issues in 10 source files |
| `pip-audit --skip-editable` | No known vulnerabilities |
| `uvicorn app.main:create_app --factory` + `GET /api/v1/health` | `{"status":"ok","service":"SMY Agent"}` |
| `python3 scripts/check_environment.py` (sandbox, not the real host) | runs to completion |

CI on Python 3.10/3.12 runs on the PR; not executed locally for 3.10.

### CI fix
First CI run: tests passed on 3.10 and 3.12, but `pip-audit` failed on 3.10 — `filelock 4.1.0` (pulled in by pip-audit itself, a dev tool) has CVEs whose fix (4.2.1) requires Python ≥3.11. Runtime dependencies were audited separately on 3.10: no known vulnerabilities. CI now audits pinned runtime deps on every Python, and the full dev environment on 3.12 only.

### Process change
Owner authorized auto-merge: Claude squash-merges its own PRs once CI is fully green (CLAUDE.md §23).

### Bug found and fixed
Telegram bot tokens embedded in API URLs (`.../bot123:ABC.../`) were not redacted because of a word-boundary in the regex. Fixed; covered by `test_redacts_telegram_bot_token_in_message`.

### Known limitations
- Hosting facts in `docs/deployment-cpanel.md` are **unverified** until the owner runs `check_environment.py` on hostmaster.uz.
- `/ready` reports `database: skipped` until M2.
- Starlette warns that `httpx` in TestClient is deprecated (test-only, harmless for now).

### Open decisions
- Final Python version (depends on hosting check).
- Subdomain for the dashboard (e.g. `agent.itcode.uz`).
- AI provider and search provider accounts (needed from M4/M5).

### Next task
Owner: run `scripts/check_environment.py` in cPanel Terminal, paste output.
Claude: **M2** — SQLAlchemy engine, portable GUID type, Alembic, first models (companies, sources, research_runs, leads, jobs, job_locks, workflow_events, audit_logs, agent_controls), repositories, MariaDB service in CI.

## Session 2 — 2026-10-25 — post-merge review fixes

Review of the merged M0/M1 found:
- **Bug:** unhandled exceptions (500) lost the request ID — not in the response body, not in the `X-Request-ID` header, not in the error log line — because Starlette's `ServerErrorMiddleware` runs outside `RequestIdMiddleware`. Fixed in `app/core/middleware.py`; test `test_unhandled_error_keeps_request_id`.
- `scripts/check_environment.py` did not cover several CLAUDE.md §16.1 items. Rewritten (stdlib only, Python 3.5+): MySQL server version (via `~/.my.cnf` if present), cloudlinux-selector versions, throw-away venv + `pip download` test, resource limits, cron entry count (never contents), cPanel layout/log dirs, Passenger `.htaccess` directives, env var names only, home path/username masking, `--offline`, manual checklist. Runs in CI and in `tests/unit/test_check_environment.py`.
- `passenger_wsgi.py` now `chdir`s to the project root so `.env` is found regardless of Passenger's working directory.
- Production now requires `APP_BASE_URL` to be `https://`.
- `DAILY_AI_BUDGET_USD` is `Decimal`; `0` documented as "no AI spending", not unlimited.
- `.env.example` comments moved to their own lines (safe to copy values into cPanel UI).
- `tests/conftest.py` also clears `LOG_LEVEL`, `DEFAULT_TIMEZONE`, `OUTBOUND_SENDING_ENABLED`, `DAILY_*`.

Verification (local, Python 3.11 and 3.13): ruff, ruff format, mypy clean; pytest 28 passed. Python 3.10 covered by CI only.

## Session 3 — 2026-10-25 — M2 Database and core models

### Completed
- Domain (pure, MyPy strict): company research state machine + name/city/domain/country normalization (`app/domain/companies.py`), lead pipeline state machine with PAUSED/ERROR resume and DO_NOT_CONTACT override (`leads.py`), actors (`actors.py`), agent modules + kill-switch rules (`agents.py`), job statuses + backoff (`jobs.py`).
- Infrastructure: portable `GUID` and `UTCDateTime` types, naming conventions, `Database` (engine, sessions, `transaction()`, `ping()`), MySQL pool recycle for shared hosting.
- Models: `companies`, `company_domains`, `company_sources`, `research_runs`, `leads`, `workflow_events`, `audit_logs`, `jobs`, `job_locks`, `agent_controls`.
- Alembic (`alembic.ini`, `migrations/`), migration `0001` generated against MariaDB, explicit InnoDB/utf8mb4 options, seeds `agent_controls` (global + 7 modules, ACTIVE).
- Repositories: companies (dedup by domain and name+city), workflow events, audit log (redacted details), jobs (idempotent enqueue, atomic claim, retry/backoff, cancel, stale requeue), job locks, agent controls (fail-closed).
- `WorkflowService`: every company/lead transition validated and recorded with actor + reason.
- `/api/v1/ready` pings the database; returns 503 `not_ready` on failure.
- CI: new `DB tests (MariaDB 10.6 / 10.11)` job: repository + migration tests, `alembic downgrade base / upgrade head / check`.
- Docs: `docs/database.md`; roadmap, README, deployment updated.

### Bug caught by MariaDB testing
Autogenerated downgrade dropped FK-backing indexes before their tables — fine on SQLite, fails on MySQL (error 1553). Downgrade now drops tables only.

### Verification (local)
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 125 passed |
| `TEST_DATABASE_URL=…mariadb 10.6… pytest tests/integration/db` | 24 passed |
| same on MariaDB 10.11 | 24 passed |
| `alembic downgrade base && alembic upgrade head && alembic check` (MariaDB 10.6) | no differences |
| `ruff check .`, `ruff format --check .`, `mypy` | clean |

### Limitations / decisions
- Name+city duplicate detection is a lookup, not a unique constraint (same name in one city can be legitimate).
- Tables for findings, audits, opportunities, contacts deferred to the milestones that use them.
- Hosting facts still unverified (owner has not yet run `check_environment.py`).

### Next task
**M3** — users/roles/sessions, `create-owner` CLI, login + CSRF + rate limit, mobile Jinja2/HTMX dashboard with company list, owner Telegram bot webhook with `/status`.

## Session 3 (cont.) — M3a Authentication + dashboard shell

### Completed
- Tables `users`, `sessions`, `login_attempts` (migration `0002`).
- `migrations/env.py` now polishes autogenerated migrations: InnoDB/utf8mb4 options on every new table, no redundant index drops before table drops (the MySQL 1553 issue from M2 cannot recur).
- `AuthService`: owner bootstrap, login with DB-backed throttling, Argon2id, rehash on login, server-side sessions with hashed tokens, sliding idle expiry, logout; audit log entries.
- Web: `/login`, `/logout`, `/` (home with counts and global agent state), CSRF (session token + double-submit cookie on login), HTMX-aware login redirect, safe `next`.
- `SecurityHeadersMiddleware` (CSP, frame, nosniff, referrer, permissions, HSTS in production).
- CLI: `python -m app.cli create-owner`, `python -m app.cli check-config`.
- Mobile-first CSS (no build step), bottom navigation, dark mode.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 159 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 54 passed |
| same on MariaDB 10.11 | 54 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| Playwright, 375×740 viewport: login → home | works; no horizontal scroll; no console/CSP errors |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Limitations
- UI strings are Uzbek only; RU/EN interface (i18n) comes with the dashboard pages in M3b-ui.
- Viewer role exists but there is no UI to create viewers yet.
- TOTP is not implemented yet (M3d).

### Next task
**M3b-ui** — company list (search/filter/sort/pagination via HTMX), company detail, PWA manifest.

## Session 3 (cont.) — M3b-ui Company list, detail, i18n, PWA

### Completed
- `CompanyQueryService`: search by name or domain (LIKE wildcards escaped), country/state filters, sort (newest/oldest/name), pagination with totals; detail with domains, sources, research runs, lead and workflow history.
- Pages `/companies` (HTMX live search with 350 ms debounce, URL kept in sync, works without JS) and `/companies/{id}`; 404 page for unknown or malformed IDs.
- Fixture (test) companies carry a "TEST DATA" badge in the list, the detail page and the API (`is_fixture`) — CLAUDE.md §11.
- Interface languages UZ (default) / RU / EN: cookie, otherwise `Accept-Language`; `/lang/{code}`; test asserts no missing translation.
- PWA: manifest, SVG + PNG icons, service worker caching only static shell assets (never pages or API data).
- HTMX 2.0.4 vendored (from the npm registry tarball, SHA-512 integrity verified); configured for strict CSP (no injected styles, no eval).
- Explicit loading (indicator), empty and error (toast on network/5xx) states.
- Read-only JSON API `/api/v1/companies[/{id}]`; `docs/api.md`.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 182 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 77 passed |
| same on MariaDB 10.11 | 77 passed |
| Playwright 375×800: login → home → list → live search "denov" (1 result, URL updated) → detail → Russian | works; 0 console/CSP errors; service worker registered; no horizontal scroll |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Next task
**M3c** — owner Telegram bot (webhook + `secret_token`, numeric-ID authorization, `/status`).

## Session 3 (cont.) — ORDER_CONFIRMED + M3c owner Telegram bot

### ORDER_CONFIRMED (PR #9)
New lead stage from ADR-0008: `RESPONDED → ORDER_CONFIRMED → MEETING (optional) / WON`, or back to `RESPONDED`; no migration needed (VARCHAR without check constraint; `alembic check` clean).

### M3c completed
- `POST /api/v1/telegram/webhook`: secret header check (constant time), 256 KB limit, tolerant Pydantic parsing, reply returned in the webhook response (no outbound call from Passenger).
- Numeric-ID authorization, private chats only; unauthorized senders ignored + audit-logged.
- `inbound_events` table (migration `0003`) with unique `(channel, external_id)`: each `update_id` handled once.
- Commands `/status` (companies, leads, jobs, global + per-agent control state), `/help`, `/start`.
- `TelegramClient` (setWebhook/getWebhookInfo/sendMessage) whose errors never include the token; CLI `telegram-set-webhook`, `telegram-webhook-info`.
- Config: webhook secret charset validated; production requires a ≥32-char secret and admin IDs when a bot token is set.
- Phone-friendly setup guide in `docs/deployment-cpanel.md` §6.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 227 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 92 passed |
| same on MariaDB 10.11 | 92 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| `ruff`, `ruff format --check`, `mypy` | clean |

Not verified: a real Telegram round trip (this sandbox's proxy blocks api.telegram.org, and no bot token exists yet). The owner does it once via §6 of the deployment guide.

### Next task
**M3b (Agent Control Center)**: `/control` page, live graph via polling, global emergency stop and per-agent toggles in dashboard and bot.

## Session 4 — 2026-10-25 — M3b Agent Control Center

### Completed
- `agent_runs` table (migration `0004`): module, job, status, `current_step`, `progress_pct`, heartbeat, tokens, cost.
- `ControlGate` enforcement helpers: `eligible_modules()` (job claim), `checkpoint()`, `ensure_may_send()`, `ensure_may_call_ai()`; fail closed.
- `AgentControlService.set_state()`: audit-logged; STOP cancels running jobs/runs; global STOP also cancels queued `outbound.*` jobs.
- Pure `node_status()` mapping (running only with a fresh heartbeat; stalled, paused, stopped, error, idle) + `ControlSnapshotService` (counts, current step/progress, activity feed, AI cost today in `DEFAULT_TIMEZONE`).
- `/control` page: SVG pipeline graph (CSS-only styling, reduced-motion aware), module cards with Activate/Pause/Stop, activity feed, 4 s polling only while the tab is visible; always-visible ⛔ STOP in the top bar with confirmation.
- API `GET /api/v1/control/snapshot`, `POST /api/v1/control/{key}`; `DomainError` → 400 (not 500).
- Owner bot: `/stop_all`, `/resume_all`, `/agent <name> on|pause|off`; dashboard/API changes are pushed to the owner bot (best effort).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 258 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 111 passed |
| same on MariaDB 10.11 | 111 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| Playwright 375×812: progress written to DB appears as a running node | after 3.3 s (requirement ≤ 5 s) |
| Playwright: STOP ALL with confirm dismissed / accepted | unchanged / all 7 nodes stopped |
| Console/CSP errors, horizontal scroll | none |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Next task
Two options (owner's choice; default **M4** because it produces real value first):
- **M4** — company discovery: manual entry form, CSV import, normalization, dedup review.
- **M3c-office** — Virtual Office canvas view (ADR-0009); characters would only show idle/coffee until agents exist.

## Session 4 (cont.) — M4 Company discovery

### Completed
- `contacts` table (migration `0005`): public business phone (E.164), email (role-address flag), Telegram; unique per company, indexed for cross-company duplicate detection.
- Contact normalization (pure, tested): UZ/KZ/KG/TJ national formats incl. trunk prefixes, explicit international numbers, emails, `@telegram` / `t.me/...`.
- `DiscoveryService.ingest()` — single intake path for manual entry, CSV and search providers: validation, duplicate detection (domain, phone, email, Telegram = hard; name + city = soft, owner can override), workflow event `NEW`, never auto-merges.
- CSV import: UTF-8/BOM or Windows-1251, `,` `;` tab auto-detected, UZ/RU/EN headers, `|` for multiple values, 1 MB / 2000 rows; dry run executes the real intake in a rolled-back savepoint (so duplicates inside the same file show up in the preview); per-row report; sources `csv` with `file#row`; audit log.
- `SearchProvider` interface + `FixtureSearchProvider` (results always stored `is_fixture=True`).
- Pages `/companies/new` and `/companies/import` (owner only, CSRF), contacts and notes on the detail page.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 307 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 136 passed |
| same on MariaDB 10.11 | 136 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| Playwright 375×812: manual entry → detail shows `+998915554433`; Russian-header CSV → "2 ta yangi · 0 ta dublikat · 1 ta xato" | works; no console errors; no horizontal scroll |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Open
- A real search provider (Google Places within free quota per ADR-0007, 2GIS with an agreement) needs the owner's API key/agreement.

### Next task
**M5** — SSRF-safe fetcher + deterministic website audit (+ LLM summary later, Haiku per ADR-0007), or **M3c-office** if the owner prefers.

## Session 5 — 2026-10-25 — M4b Autonomous discovery (owner: "I won't enter companies myself")

### Completed
- `OverpassSearchProvider` (OpenStreetMap, free, no key; ADR-0010): city area inside the country, 9 business categories mapped to OSM tags, honest User-Agent, timeouts, 429/5xx/timeouts retryable, 4xx not; collects name, website, phones, emails, Telegram, industry, OSM URL as source; ODbL attribution in UI.
- `discovery_targets` (migration `0006`) seeded with Denov, Termiz, Toshkent, Samarqand, Buxoro, Qarshi × all categories, every 7 days — works with zero setup.
- Job runner `python -m app.jobs.runner --max-jobs N --max-seconds S`: overlap lock, stale job/run recovery, schedules due targets (idempotent per day), claims only ACTIVE modules, live progress in `agent_runs`, checkpoint between companies (PAUSE → job back to queue, STOP → cancelled), retry with backoff for rate limits, exits on global STOP.
- Discovery task: search → `DiscoveryService.ingest` per company (dedup, events) → summary step.
- `/discovery` page: targets with found counts, last run, enable/disable, "search now", add city with categories; recent searches.
- `SEARCH_PROVIDER` defaults to `osm`; `check_environment.py` now also checks `overpass-api.de`.
- Docs: ADR-0010, `privacy-and-data-retention.md`, cron setup (`deployment-cpanel.md` §7).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 336 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 152 passed |
| same on MariaDB 10.11 | 152 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| `python -m app.jobs.runner --max-jobs 3` on MariaDB, `SEARCH_PROVIDER=fixture` | 54 jobs scheduled (6 cities × 9 categories), 3 executed, 51 left queued, progress in `agent_runs` |
| `ruff`, `ruff format --check`, `mypy` | clean |

Not verified: a live Overpass query — this sandbox's proxy blocks `overpass-api.de`. The adapter is tested with mocked HTTP using real response shapes; the host's reachability shows in `check_environment.py`.

### Next task
**M5** — SSRF-safe fetcher + deterministic website audit, run automatically by the Research & Audit agent for every newly discovered company with a website (then M6 scoring, M7 offers, M8/M9 conversation and outreach).
