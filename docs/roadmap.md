# Roadmap

Authoritative milestone definitions and acceptance criteria live in
`CLAUDE.md` §21. This file tracks status only.

| Milestone | Scope | Status |
|---|---|---|
| M0 | Inspection, architecture docs, ADRs, hosting check script | ✅ done (hosting verification pending owner run) |
| M1 | FastAPI foundation, settings, logging, health, WSGI bridge, tests, CI | ✅ done |
| M2 | SQLAlchemy, Alembic, core models, repositories, MariaDB in CI | ⏭ next |
| M3 | Auth, mobile dashboard, owner Telegram bot | planned |
| M3b | Agent Control Center (live graph, kill switch) | planned |
| M4 | Company discovery (manual, CSV, one provider) | planned |
| M5 | Research & SSRF-safe website audit | planned |
| M6 | Opportunity analysis & scoring | planned |
| M7 | Proposals & requirements | planned |
| M8 | Mustafo client bot (client-initiated) | planned |
| M9 | Outbound: automatic email, assisted Telegram | planned |
| M10 | Background automation hardening | planned |
| M11 | Analytics, budgets, backups, hardening | planned |
| M12 | Demo generation | planned |

## M2 breakdown (next)

1. `app/infrastructure/database/`: engine/session factory, portable `GUID` type, naming conventions.
2. Alembic setup with `env.py` reading `DATABASE_URL`.
3. Models: `companies`, `company_domains`, `company_sources`, `research_runs`, `leads`, `jobs`, `job_locks`, `workflow_events`, `audit_logs`, `agent_controls`.
4. Repositories with explicit transactions.
5. Tests on SQLite; CI job with MariaDB service running `alembic upgrade head` + repository tests.
6. `docs/database.md`.
