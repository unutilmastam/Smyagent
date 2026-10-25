# SMY Agent

AI sales agent platform by **ITcoDe.Uz** — finds business clients in Central Asia,
researches them with evidence, scores opportunities, drafts proposals, and talks to
clients through the **"Mustafo — SMY Agent"** AI assistant (always disclosed as AI).

Project rules and full specification: [`CLAUDE.md`](CLAUDE.md).
Status: [`docs/progress.md`](docs/progress.md) · Plan: [`docs/roadmap.md`](docs/roadmap.md).

## Stack
FastAPI · Pydantic v2 · SQLAlchemy/Alembic (M2) · Jinja2 + HTMX (M3) · MySQL/MariaDB ·
cPanel Passenger via a2wsgi · cron-driven job queue.

## Development (Claude Code cloud session or any shell)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # optional, defaults work for development
uvicorn app.main:create_app --factory --reload
# → http://localhost:8000/api/v1/health  and /docs
```

## Checks (same as CI)

```bash
ruff check . && ruff format --check . && mypy && pytest && pip-audit --skip-editable
```

## Database
Migrations: `alembic upgrade head` (uses `DATABASE_URL`). Details: [`docs/database.md`](docs/database.md).

## Deployment
cPanel at hostmaster.uz — see [`docs/deployment-cpanel.md`](docs/deployment-cpanel.md).
First run `scripts/check_environment.py` in cPanel Terminal and share the output.

## Endpoints (so far)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | liveness |
| GET | `/api/v1/ready` | readiness incl. database ping (503 if not ready) |
| GET/POST | `/login`, POST `/logout` | owner login (CSRF-protected) |
| GET | `/` | dashboard home (login required) |
| GET | `/companies`, `/companies/{id}` | company list (search/filter/sort/pages) and detail (audit, opportunities, score) |
| GET | `/leads` | leads sorted by score, stage filter, main need |
| GET/POST | `/settings/scoring` | score weights + qualification threshold (owner) |
| GET/POST | `/companies/new`, `/companies/import` | manual entry, CSV import with dry run (owner) |
| GET/POST | `/discovery` | automatic discovery: cities, categories, search now (owner) |

Agents run automatically: Discovery (OpenStreetMap) → Research & Audit (website audit + findings) → Opportunity & Scoring (needs, score, lead).
Background agents: `python -m app.jobs.runner --max-jobs 5 --max-seconds 240` from cron (see `docs/deployment-cpanel.md` §7).
| GET | `/api/v1/companies`, `/api/v1/companies/{id}` | same data as JSON (session auth) |
| GET | `/lang/{uz,ru,en}` | interface language |
| POST | `/api/v1/telegram/webhook` | owner bot webhook (secret header) |
| GET | `/control` | Agent Control Center: live graph (4 s polling), activity feed, controls |
| GET | `/api/v1/control/snapshot` | live state JSON |
| POST | `/control/{key}`, `/api/v1/control/{key}` | ACTIVE / PAUSED / STOPPED (owner, CSRF) |
| GET | `/manifest.webmanifest`, `/sw.js` | PWA |

CLI: `python -m app.cli create-owner --username <name>`, `check-config`, `telegram-set-webhook`, `telegram-webhook-info`.
