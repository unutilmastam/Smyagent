# Roadmap

Authoritative milestone definitions and acceptance criteria live in
`CLAUDE.md` §21. This file tracks status only.

| Milestone | Scope | Status |
|---|---|---|
| M0 | Inspection, architecture docs, ADRs, hosting check script | ✅ done (hosting verification pending owner run) |
| M1 | FastAPI foundation, settings, logging, health, WSGI bridge, tests, CI | ✅ done |
| M2 | SQLAlchemy, Alembic, core models, repositories, MariaDB in CI | ✅ done |
| M3 | Auth, mobile dashboard, owner Telegram bot | 🟡 M3a, M3b-ui, M3c done; M3d (TOTP) next |
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

## M3 breakdown

- ✅ **M3a** `users` (role column: owner/viewer), `sessions`, `login_attempts`; `create-owner` CLI; login/logout, CSRF, throttling, audit log, security headers; mobile-first base layout with bottom nav and a home page with counts.
- ✅ **M3b-ui** Company list with search/filter/sort/pagination (HTMX), company detail page, UZ/RU/EN interface, installable PWA (app-shell-only service worker), read-only companies API.
- ✅ **M3c** Owner Telegram bot: webhook with `secret_token`, numeric-ID authorization (private chats only), idempotent updates, `/status`, `/help`; CLI `telegram-set-webhook` / `telegram-webhook-info`.
- ⏭ **M3d** Optional TOTP for the owner.

Decision: a `roles` table is not needed for two fixed roles; `users.role` is an enum
column. A table is introduced with full RBAC if it is ever needed.
