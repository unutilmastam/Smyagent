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

## Deployment
cPanel at hostmaster.uz — see [`docs/deployment-cpanel.md`](docs/deployment-cpanel.md).
First run `scripts/check_environment.py` in cPanel Terminal and share the output.

## Endpoints (so far)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | liveness |
| GET | `/api/v1/ready` | readiness (DB check added in M2) |
