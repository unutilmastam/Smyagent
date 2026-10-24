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
