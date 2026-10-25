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
| GET | `/proposals`, `/proposals/{id}` | offers with Quality Gate verdict, evidence, questions, history |
| POST | `/proposals/{id}/approve`, `/reject`, `/edit` | owner decisions (CSRF); edit = new version, re-checked |
| GET | `/proposals/{id}/export.md` | offer + evidence as Markdown |
| GET | `/settings`, `/settings/agents/{module}` | agent settings hub and per-agent form, versions |
| GET | `/conversations`, `/conversations/{id}` | Mustafo chats: messages, drafts, Order Brief, decisions |
| POST | `/conversations/messages/{id}/send\|discard`, `/conversations/{id}/reply\|resume`, `/orders/{id}/decide` | owner actions (CSRF) |
| GET | `/conversations/{id}/brief.md` | confirmed order as a Markdown project spec |
| POST | `/api/v1/telegram/client-webhook` | Mustafo client bot webhook (secret header) |
| GET | `/outreach` | email queue/caps/bounces, one-tap Telegram tasks, phone tasks |
| POST | `/outreach/events/{id}/done\|skip\|replied`, `/outreach/email/resume` | owner actions (CSRF) |
| GET/POST | `/u/{token}` | public one-click unsubscribe (signed token; GET never changes anything) |
| POST | `/settings/agents/{module}`, `/reset`, `/restore/{version}` | save / reset / restore (owner, CSRF, audit-logged) |
| GET/POST | `/companies/new`, `/companies/import` | manual entry, CSV import with dry run (owner) |
| GET/POST | `/discovery` | automatic discovery: cities, categories, search now (owner) |

Agents run automatically: Discovery (OpenStreetMap) → Research & Audit (website audit + findings) → Opportunity & Scoring (needs, score, lead) → Proposal (price-free offer) → Quality Gate → owner approval in the dashboard or Telegram. Clients who write to the Mustafo bot are interviewed, confirm an Order Brief and are handed to the owner ("✅ Yangi buyurtma"). Approved offers go out by email to public business addresses (caps, opt-out, auto-pause) or as one-tap Telegram / phone tasks.
Background agents: `python -m app.jobs.runner --max-jobs 5 --max-seconds 240` from cron (see `docs/deployment-cpanel.md` §7).
| GET | `/api/v1/companies`, `/api/v1/companies/{id}` | same data as JSON (session auth) |
| GET | `/lang/{uz,ru,en}` | interface language |
| POST | `/api/v1/telegram/webhook` | owner bot webhook (secret header) |
| GET | `/control` | Agent Control Center: live graph (4 s polling), activity feed, controls |
| GET | `/api/v1/control/snapshot` | live state JSON |
| POST | `/control/{key}`, `/api/v1/control/{key}` | ACTIVE / PAUSED / STOPPED (owner, CSRF) |
| GET | `/manifest.webmanifest`, `/sw.js` | PWA |

CLI: `python -m app.cli create-owner --username <name>`, `check-config`, `telegram-set-webhook`, `telegram-webhook-info`, `telegram-set-client-webhook`.
