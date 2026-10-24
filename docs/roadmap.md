# Roadmap

Authoritative milestone definitions and acceptance criteria live in
`CLAUDE.md` §21. This file tracks status only.

| Milestone | Scope | Status |
|---|---|---|
| M0 | Inspection, architecture docs, ADRs, hosting check script | ✅ done (hosting verification pending owner run) |
| M1 | FastAPI foundation, settings, logging, health, WSGI bridge, tests, CI | ✅ done |
| M2 | SQLAlchemy, Alembic, core models, repositories, MariaDB in CI | ✅ done |
| M3 | Auth, mobile dashboard, owner Telegram bot | ⏭ next |
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

## M2 — done
See `docs/database.md`. Deferred to the milestone that needs them: `company_locations`,
`research_findings`, `website_audits` (M5), `opportunities`/scores (M6), contacts and
phone normalization (M4).

## M3 breakdown (next)

1. `users`, `roles` (`owner`, `viewer`), `sessions` tables + migration.
2. `python -m app.cli create-owner` (one-time bootstrap, Argon2 hashing).
3. Login/logout with HTTP-only SameSite cookie sessions, login rate limit, CSRF tokens, audit log.
4. Jinja2 + HTMX base layout, mobile-first (bottom nav), company list with search/filter/pagination, company detail.
5. Owner Telegram bot: webhook with `secret_token`, numeric-ID authorization, `/status`.
6. Optional TOTP for the owner.
