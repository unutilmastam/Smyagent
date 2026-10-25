# Roadmap

Authoritative milestone definitions and acceptance criteria live in
`CLAUDE.md` §21. This file tracks status only.

| Milestone | Scope | Status |
|---|---|---|
| M0 | Inspection, architecture docs, ADRs, hosting check script | ✅ done (hosting verification pending owner run) |
| M1 | FastAPI foundation, settings, logging, health, WSGI bridge, tests, CI | ✅ done |
| M2 | SQLAlchemy, Alembic, core models, repositories, MariaDB in CI | ✅ done |
| M3 | Auth, mobile dashboard, owner Telegram bot | 🟡 M3-auth, M3-ui, M3-bot done; M3-totp open (optional) |
| M3b | Agent Control Center (live graph, kill switch) — CLAUDE.md §13A.1–2 | ✅ done |
| M3c-office | Virtual Office view — CLAUDE.md §13A.3, ADR-0009 | ⏭ next (or M4 first — see progress) |
| M4 | Company discovery (manual, CSV, one provider) | ✅ automatic via OpenStreetMap (ADR-0010) + manual + CSV |
| M5 | Research & SSRF-safe website audit | ✅ fetcher + deterministic audit + automatic research (AI summary → M5b, needs AI key) |
| M6 | Opportunity analysis & scoring | ✅ rules-based opportunities, explainable score, automatic leads (LLM explanations → M5b/AI layer) |
| M7 | Proposals & requirements | ✅ price-free offers, Quality Gate, owner approval (dashboard + Telegram), Markdown export; M7b: internal pricing rules + PDF export |
| M7c | Owner-editable agent settings (per agent, versioned, restorable; hard rules locked) | ✅ done |
| M8 | Mustafo client bot (client-initiated) | ✅ disclosure, UZ/UZ-Cyrl/RU/EN, intents, opt-out → suppression, owner-approved or safe auto replies, Order Brief → `ORDER_CONFIRMED` → owner, project spec export |
| M9 | Outbound: automatic email, assisted Telegram | ✅ email (caps, warm-up, spacing, opt-out link, auto-pause, inbox replies/STOP/bounces, follow-up once), one-tap Telegram + phone tasks |
| M10 | Background automation hardening | ✅ runner invocation records + cron liveness, per-job time limit, stale jobs capped by attempts, deduplicated owner alerts with retry button, `/jobs` monitoring + retry/cancel, `/jobs` `/retry` bot commands, daily retention cleanup, rotated runner log (`docs/operations.md`) |
| M11 | Analytics, budgets, backups, hardening | planned |
| M12 | Demo generation | planned |

## M2 — done
See `docs/database.md`. Deferred to the milestone that needs them: `company_locations`,
`research_findings`, `website_audits` (M5), `opportunities`/scores (M6), contacts and
phone normalization (M4).

## M3 breakdown

Sub-milestone labels inside M3 are `M3-auth`, `M3-ui`, `M3-bot`, `M3-totp`, so they do not
clash with CLAUDE.md's separate milestones **M3b** (Control Center) and **M3c-office**.
(Earlier progress entries call them M3a / M3b-ui / M3c.)

- ✅ **M3-auth** `users` (role column: owner/viewer), `sessions`, `login_attempts`; `create-owner` CLI; login/logout, CSRF, throttling, audit log, security headers; mobile-first base layout with bottom nav and a home page with counts.
- ✅ **M3-ui** Company list with search/filter/sort/pagination (HTMX), company detail page, UZ/RU/EN interface, installable PWA (app-shell-only service worker), read-only companies API.
- ✅ **M3-bot** Owner Telegram bot: webhook with `secret_token`, numeric-ID authorization (private chats only), idempotent updates, `/status`, `/help`; CLI `telegram-set-webhook` / `telegram-webhook-info`.
- **M3-totp** Optional TOTP for the owner (recommended before the dashboard is public).

## M3b — Agent Control Center (done)

1. `agent_runs` table (module, job_id, status, `current_step`, `progress_pct`, `heartbeat_at`, tokens/cost), migration.
2. `AgentControlService`: set state (owner only, audit-logged, reason), global EMERGENCY STOP (cancels queued outbound jobs, marks running jobs CANCELLED at next checkpoint); reactivation by owner only.
3. Enforcement helpers used by every future module: `ensure_may_claim()`, `checkpoint()`, `ensure_may_send()`, `ensure_may_call_ai()`.
4. `GET /api/v1/control/snapshot` (small cached JSON) + `/control` page: Cytoscape/Mermaid-free SVG graph of the 7 modules, node colors by state, activity feed, 3–5 s polling; always-visible STOP button.
5. Owner bot: `/stop_all`, `/agent <name> on|pause|off`; state changes pushed to the owner.
6. Tests per CLAUDE.md §13A.2 (stopped agent claims no jobs, global stop blocks a queued send, pause/resume keeps queue, non-owner cannot change state).

Decision: a `roles` table is not needed for two fixed roles; `users.role` is an enum
column. A table is introduced with full RBAC if it is ever needed.
