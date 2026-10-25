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

## Session 5 (cont.) — M5 Research & website audit

### Completed
- SSRF-safe fetcher (`app/infrastructure/http_fetcher/`): URL/port policy, full DNS answer validation (IPv4/IPv6, mapped/6to4/Teredo/NAT64), pinned-IP connection with SNI + certificate check against the name, no env proxy, manual redirects (max 5, re-validated), timeouts + budget, 2 MB limit, content-type allowlist, robots.txt, per-host throttle, honest User-Agent.
- Deterministic audit (`app/domain/audit.py`, pure): HTTPS, status, title, description, mobile viewport, response time, size, visible contacts, Telegram link, forms, image alt, lang, copyright year, site builder; weighted score (critical checks ×2); findings labeled **fact** (observed) or **inference** (with confidence).
- `website_audits` + `research_findings` (migration `0007`); no raw HTML stored.
- Research & Audit agent task: runs automatically for every NEW company (runner schedules up to 20 per run, NEW → RESEARCH_PENDING → RESEARCHED / RESEARCH_FAILED); no website / unreachable / robots-disallowed are recorded as findings; https → http fallback for connect/TLS/timeout; one site's failure never stops the batch.
- Company page: audit score, ✓/✗ checks with evidence, translated findings with kind, confidence, source and date.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 406 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 162 passed |
| same on MariaDB 10.11 | 162 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| Local TLS server (`smy.test` cert): pinned-IP fetch with SNI | 200, Host header correct; mismatched name rejected (`tls`) |
| Playwright 375×812: company page with audit | renders; no console errors; no horizontal scroll |
| `ruff`, `ruff format --check`, `mypy` | clean |

Not verified: auditing real public sites — this sandbox's proxy blocks direct connections; all fetch paths are covered with mocked transports and the local TLS test.

### Next task
**M6** — Opportunity & scoring: map findings to service categories (no website → website; not mobile → modernization; no online inquiry → Telegram bot / form; …), deterministic explainable score per company, owner-adjustable weights, create leads (`CANDIDATE` → `QUALIFIED`). Then M7 offers (no prices), M8/M9 conversation + order intake. **M5b**: AI research summary once an AI key is configured (Haiku, Batch API, ADR-0007).

## Session 5 (cont.) — M6 Opportunity & scoring

### Completed
- Pure domain `app/domain/scoring.py`: findings → service opportunities by explicit rules (no website → business website / Telegram bot; not mobile-friendly → modernization; no online inquiry → Telegram bot / automation; …). Independent signals combine as `1 − Π(1 − s)`; inferences are scaled by their confidence. No finding → no opportunity (nothing invented).
- Explainable score 0–100 from five components (service fit, evidence quality, geography, contactability, activity), weighted average over components **with data only** — missing components are listed, never imputed. Qualification needs an opportunity, a public business contact (personal emails don't count) and score ≥ threshold (default 55).
- Tables `opportunities`, `lead_scores`, `score_components`, `scoring_settings` (migration `0008`); every opportunity keeps the ids of the findings it rests on.
- Opportunity & Scoring agent task runs automatically after research (idempotent per research version): replaces opportunities, creates the lead (CANDIDATE → QUALIFIED when it qualifies), stores the score snapshot, company RESEARCHED → ANALYZED, owner gets one Telegram alert for a newly qualified lead with score ≥ 75.
- Dashboard: `/leads` (sorted by score, stage tabs, main need), company page shows opportunities with reasons and the score breakdown, `/settings/scoring` (owner, CSRF, audit-logged; weights clamped 0–10).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 429 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 174 passed |
| same on MariaDB 10.11 | 174 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Limitations
- Scoring rules and weights are a first version; the owner can tune weights/threshold, rule strengths are code (reviewed via PR).
- LLM explanations are not added yet (optional per CLAUDE.md; arrives with the AI layer, M5b).

### Next task
**M7** — offers without prices (ADR-0008): value-focused offer per qualified lead built from opportunities + evidence, Quality Gate (no price/commitment/unverified claim), versioning, owner approve/reject in dashboard and Telegram, Markdown export.

## Session 5 (cont.) — M7 Proposals & Quality Gate

### Completed
- Persona defaults (`app/domain/persona.py`): disclosure, signature and opt-out in UZ Latin / UZ Cyrillic / RU / EN; client language by country (UZ → uz, KZ/KG/TJ → ru).
- Offer builder (`app/domain/proposals.py`, pure): value-focused offer from recorded findings + opportunities only — facts plainly, inferences as possibilities, top 3 services with benefits, **no number at all** (no price, amount, deadline); AI disclosure first, opt-out and signature last. Owner-side assumptions and client questions per service.
- Quality Gate (`app/domain/quality_gate.py`, pure rules, ADR-0011): blocks prices/currency amounts (incl. "so'mdan", "долларов"), discounts, "free", guarantees, deadlines, contracts, prepayment, missing disclosure/opt-out/evidence; flags superlatives, claims about clients, wrong script, length for review.
- Tables `proposals`, `proposal_versions` (immutable versions with evidence finding ids and gate verdict), `approval_requests` (migration `0009`).
- Agents: Proposal (`proposal.draft`, scheduled for every QUALIFIED lead without an offer) → Quality Gate (`quality_gate.review`, separate job so its kill switch works) → lead `PROPOSAL_DRAFTED → AWAITING_APPROVAL`, approval request, one Telegram message to the owner with **✅ Tasdiqlayman / ❌ Rad etaman** inline buttons (+ edit link when `APP_BASE_URL` is https).
- Owner decisions: approve (lead APPROVED), reject (lead DISQUALIFIED, reason kept), edit (new version, re-checked immediately; a priced edit goes to NEEDS_EDIT and cannot be approved). All audit-logged. Owner bot: inline buttons, `/proposals`, `/approve <id>`, `/reject <id> [sabab]`.
- Dashboard: `/proposals` (status tabs), detail (offer text, gate issues, evidence with sources, assumptions, questions, history, approve/reject/edit), Markdown export, home counter "Tasdiq kutmoqda", proposal link on the company page.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 507 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 204 passed |
| same on MariaDB 10.11 | 204 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Limitations / decisions
- Offers are template-based (no AI key yet); wording is generic but evidence-specific. Uzbek Cyrillic offers fall back to Latin until M8 language detection.
- Nothing is sent yet: approved offers wait for M9 (outbound email / assisted Telegram).
- M7b (later): internal pricing rules (never shown to clients) and PDF export.

### Next task
**M8** — Mustafo client bot (client-initiated): disclosure, language detection, message classification, opt-out → suppression, owner-approved replies, **Order Brief interview → client confirmation → `ORDER_CONFIRMED` → "✅ Yangi buyurtma" to the owner**, Markdown project spec.

## Session 5 (cont.) — M7c Owner-editable agent settings

### Completed
- `/settings` hub (all 7 agents, locked rules) and `/settings/agents/{module}` per-agent form; ⚙ link on every Control Center card and on the home page.
- Editable: discovery results per search; research companies per run; hot-lead threshold; offered services, services per offer, minimum need strength, every offer text per language (UZ/RU/EN) incl. each service's pitch line; extra blocked / review words for the Quality Gate; free-text instructions for every agent (stored now, used once an AI key exists).
- Safety: bounds validated; only `{company}`/`{owner}` placeholders (plain replacement); a sample offer with all services is checked by the Quality Gate on save — priced/guaranteed text is refused; disclosure, opt-out and signature cannot be edited; owner words only add rules.
- Versions: every save versioned + audit-logged; restore and reset create new versions. Tables `agent_settings`, `agent_setting_versions` (migration `0010`), ADR-0012.
- Agents read the settings at run time (discovery, research scheduler, scoring alert, proposal drafting, Quality Gate).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 535 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 216 passed |
| same on MariaDB 10.11 | 216 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6) | no differences |
| Playwright 375×812: `/settings`, proposal settings | no horizontal scroll, no console errors |
| `ruff`, `ruff format --check`, `mypy` | clean |

### Next task
**M8** — Mustafo client bot + order intake (`ORDER_CONFIRMED`); its persona/FAQ settings join `/settings/agents/conversation`.

## 2026-10-25 — Hosting verified (hostmaster.uz)
Owner ran `scripts/check_environment.py` (0 internal errors). Findings and decisions recorded in `docs/deployment-cpanel.md`:
- Runtime: Python **3.12** via Setup Python App (3.10–3.13 available). System python 3.9 lacks `ensurepip` — never use it for the app.
- Database is **MySQL 8.0**, not MariaDB → CI gains a MySQL 8.0 job; `cryptography` added for PyMySQL `caching_sha2_password`.
- All external APIs reachable; no Node/Docker/Redis (as assumed).
- `smy.itcode.uz/api` is used by `smarthome-api` → owner chose a new subdomain **`agent.itcode.uz`** for SMY Agent.
- **Open:** LVE limits, cron minimum interval, MySQL server version, nested startup path still to read manually in cPanel.

## Session 5 (cont.) — M8 Mustafo client bot + order intake

### Completed
- Client bot webhook `/api/v1/telegram/client-webhook` (secret header, private text messages only, idempotent updates); CLI `telegram-set-client-webhook`.
- Rules (`app/domain/conversation.py`, ADR-0013): language UZ/UZ-Cyrl/RU/EN, intents (opt-out first, human request, "are you a bot?", price, interest, confirm/deny, spam), 7-question Order Brief, replies in all four languages, AI disclosure in the first message only.
- `ConversationService`: opt-out → suppression + blocked queue + lead `DO_NOT_CONTACT`; truthful bot answer + handoff with owner contact; price questions answered without figures; brief summary never echoes money/deadline figures; explicit confirmation → `ORDER_CONFIRMED` → one "✅ Yangi buyurtma" Telegram message with Qabul qilaman / Savol beraman / Rad etaman buttons.
- Reply modes in agent settings: approve every reply (default) or automatic safe replies; Quality Gate `client_reply` mode; `outbound.telegram_reply` send job with suppression + kill-switch check right before sending.
- Dashboard: 💬 Suhbatlar list/detail (chat bubbles, drafts with send/discard, owner reply → handoff, resume Mustafo, order card with decisions), Markdown project spec export, home "Yangi buyurtma" alert.
- Tables `conversations`, `conversation_messages`, `order_briefs`, `suppression_records` (migration `0011`).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 608 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 237 passed |
| same on MariaDB 10.11 | 237 passed |
| same on **MySQL 8.0** (production engine) | 237 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6 and MySQL 8.0) | no differences |
| Playwright 375×812: conversations list + full order chat | no horizontal scroll, no console errors |
| `ruff`, `ruff format --check`, `mypy` | clean |

Not verified: live Telegram delivery (sandbox has no Bot API access); all paths are tested with fake bots.

### Next task
**M9** — outbound to public business contacts: automatic email (caps, warm-up, opt-out link, SPF/DKIM/DMARC docs, bounce auto-pause) and assisted one-tap Telegram for approved offers.

## Session 5 (cont.) — M9 Outbound outreach

### Completed
- Rules (`app/domain/outreach.py`, ADR-0014): warm-up cap (10 → +5/day → 30), auto-pause on any spam complaint or > 5 % bounces (≥ 20 sends), follow-up once after ≥ 5 days, signed unsubscribe tokens, follow-up texts (UZ/RU/EN, gate-clean, no numbers), email footer with unsubscribe link + sender identity.
- Adapters: SMTP sender (verified TLS, SSL/STARTTLS, 5xx = permanent), RFC 8058 one-click unsubscribe headers, IMAP inbox + parser (replies, DSN bounces, `X-Failed-Recipients`, ARF complaints).
- `OutreachService`: one first contact per company on the best public channel (role email → Telegram task → phone task), follow-ups, sender jobs only when sending is enabled and email not paused, optional auto-approval of gate-clean offers, unsubscribe → suppression + blocked queue + lead `DO_NOT_CONTACT`, replies → `RESPONDED` + owner note (quoted text stripped), STOP by email.
- Jobs: `outbound.email` (SENDING committed before SMTP → never twice; UNKNOWN on interrupted runs; caps/spacing via `DeferTaskError` without using retries; cancelled by global STOP), `email.inbox` every 15 min when IMAP is set.
- UI: 📤 `/outreach` (today/cap, bounces, pause + resume, Telegram copy-and-open tasks, phone `tel:` tasks, email log, "they replied"), public `/u/<token>` (GET shows, POST unsubscribes), outreach settings in ⚙ Mustafo.
- Tables `outreach_events`, `channel_states` (migration `0012`); new env vars `SMTP_*`, `IMAP_*` in `.env.example`; cPanel steps incl. SPF/DKIM/DMARC in `deployment-cpanel.md` §6c.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.11 and 3.13) | 643 passed |
| `TEST_DATABASE_URL=…10.6… pytest tests/integration` | 259 passed |
| same on MariaDB 10.11 / MySQL 8.0 | 259 / 259 passed |
| `alembic downgrade base && upgrade head && check` (MariaDB 10.6, MySQL 8.0) | no differences |
| `ruff`, `ruff format --check`, `mypy` | clean |

Not verified: real SMTP/IMAP delivery and deliverability (sandbox has no mail server access); fake sender/inbox cover all paths.

### Next task
**M10** background-automation hardening (runner observability, failure alerts deduplicated, cron docs) → **M11** analytics, budgets, backups → **M3c-office** Virtual Office view; **M5b** AI layer once an AI key is configured.

## Session 6 — First deployment tooling (cPanel, phone)

### Completed
- `docs/deploy-first-time-uz.md`: Uzbek step-by-step for the owner (MySQL DB/user, Git clone before Python App, Setup Python App values, `.env` wizard, deploy, owner account, both webhooks + test, two cron jobs, checklist, troubleshooting table).
- `scripts/setup_env.py` (stdlib only): asks DB name/user/password, both bot tokens, Telegram ID; generates `APP_SECRET_KEY` + `TELEGRAM_WEBHOOK_SECRET`; production defaults (`OUTBOUND_SENDING_ENABLED=false`); hidden input; percent-encoded DB URL; single-quotes non-plain values; rejects `'` and `${` (the dotenv reader expands `${…}` even in quotes — found by test); atomic write, mode 600; `--set KEY`, `--database`.
- `scripts/deploy.sh`: lock, venv/.env checks, `git merge --ff-only` (aborts on server-side edits, restores a cPanel-rewritten `passenger_wsgi.py`), pip, `check-config`, backup, `alembic upgrade head`, restart, health + ready with retries; Uzbek output to `~/smyagent_data/deploy.log`; body in `main()` so a pull can't corrupt the running script.
- `python -m app.cli db-backup`: gzip'd mysqldump via a 600 option file (password never in argv), `--single-transaction --no-tablespaces`, streamed, rotation (14), skipped while no tables; sqlite copy for dev.
- Root `passenger_wsgi.py` shim (startup file `passenger_wsgi.py`), loads the real entry by path.
- Decision: one `.env` in the app folder is the configuration source (web, Terminal, cron).

### Verification
| Check | Result |
|---|---|
| Dry run in a fake cPanel home: fresh clone + venv (Python 3.13) + MySQL 8.0 user with password `P@ss#w0rd$x/1`, `setup_env.py` via stdin | `.env` mode 600, production config OK, DB reachable |
| `deploy.sh` 1st run (empty DB) | backup skipped, 12 migrations, exit 0 |
| `deploy.sh` 2nd run | real mysqldump (35 tables) gz mode 600, no migration, exit 0 |
| pull path + cPanel-overwritten `passenger_wsgi.py` | restored, exit 0; edited tracked file → aborted, nothing changed |
| health step against the real root `passenger_wsgi.py` (WSGI server) | `/ready` ready, deploy exit 0 |
| `shellcheck scripts/deploy.sh`, `bash -n` | clean |
| `pytest` (SQLite, Python 3.13 / 3.11) | 665 passed / 664 passed + 1 skipped (no shellcheck in that venv) |

Bug found and fixed during the dry run: the EXIT trap referenced a `local` variable → `unbound variable` at the end under `set -u`.

### Next task
Owner runs `docs/deploy-first-time-uz.md`; then M10 → M11 → M3c-office → M5b.

## Session 6 (cont.) — M10 Background automation hardening

### Completed
- **Cron liveness:** every runner invocation writes a `runner_runs` row (`OK | LOCKED | STOPPED | ERROR`, counts, error class). Dashboard `/`, `/control`, `/jobs` and the owner bot (`/status`, `/jobs`) show "last run N min ago", red after 15 min without a run, a setup hint if it never ran. Snapshot API gains `cron_health`, `cron_minutes_ago` (for the Virtual Office).
- **Per-job time limit:** `--max-job-seconds` (default 120 s, SIGALRM in the cron process) cuts a hanging handler → retried with backoff; the DB pool is reset after an interrupt. Lock TTL covers the job limit.
- **Stale jobs** (process killed): requeued only while attempts remain, otherwise `FAILED` (`stale: …`) — no endless loop on a job that kills the process.
- **Owner alerts** (`owner_alerts`): final job failures and runner crashes go to the owner bot with 🔁 *Qayta urinish* / 🔎 *Ko'rish* buttons; one message per key (job type + error class) per 6 h, repeats counted; sent after commit. Retries are not alerted.
- **Job monitoring:** `/jobs` (filter by status/agent, pagination, error class), `/jobs/<id>` (input, error, every run with step/cost), owner-only CSRF-protected retry (FAILED/CANCELLED) and cancel (QUEUED), audit-logged. Bot: `/jobs`, `/retry <id>`, `job_retry:` button.
- **Retention:** daily cleanup after the jobs — finished jobs and agent runs > 30 days, runner rows > 14 days, idle alert rows; FAILED jobs are kept. Documented in `privacy-and-data-retention.md`.
- **Logs:** `--log-file` (rotating 1 MB × 3); cron line updated in both deploy guides; `docs/operations.md` (how it runs, alerts, owner actions, troubleshooting).
- Fixed a time-of-day dependent test (`test_daily_cap_and_spacing_defer` failed near Tashkent midnight).
- Migration `0013` (`runner_runs`, `owner_alerts`).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.13) | 698 passed, 1 skipped (shellcheck not in this venv) |
| `TEST_DATABASE_URL=… pytest tests/integration` on MariaDB 10.6 / 10.11 / MySQL 8.0 | 281 / 281 / 281 passed |
| `alembic check` (MySQL 8.0); `downgrade 0012` + `upgrade head` (MariaDB 10.6) | no differences; both directions OK |
| `python -m app.jobs.runner --log-file …` (SQLite) | exit 0, JSON lines in the log, `runner_runs` row `OK`, cleanup ran |
| `ruff check`, `ruff format --check`, `mypy app` | clean |

Not verified: SIGALRM behaviour under the real cPanel cron (expected to work: plain Linux process); real Telegram delivery of alerts (notifier is the existing, tested owner-bot client).

### Next task
**M11** analytics (funnel), budgets, provider usage, backup restore drill, deployment smoke test → **M3c-office** Virtual Office → **M5b** AI layer once the key is configured.

## 2026-10-25 — First deploy done (owner) + guide fixes

### Owner report
agent.itcode.uz is live: MySQL `itcode_smyagent`/`itcode_smy`, Python 3.12.12 app at `~/smyagent`, `.env` via `setup_env.py`, `deploy.sh` (13 migrations, health ✅; the `/dev/fd` failure on the first run is fixed in #26), owner account, both webhooks set (no `last_error`), cron runner (`--log-file`) and 03:17 backup. Bot tokens were shown on screen once and were revoked and replaced. Email and AI key are not set up yet. Details: `docs/owner-setup.md`.

### Fixed from the owner's findings
- `setup_env.py`: an empty **or invalid** answer is asked again (3 times) instead of exiting; on exit the pending terminal input is discarded (`tcflush`) so a token pasted next cannot run as a bash command or land in the history. `--set` uses the same loop. Tests added.
- `deploy-first-time-uz.md`: big warning in §2 that the Application URL dropdown defaults to `itcode.uz` — choose `agent.itcode.uz`; "paste first, then Enter" and the token-revoke recipe in §4; Termius tip (paste into the bottom input field, check the start of long lines); "SMY yangilash" = `bash ~/smyagent/scripts/deploy.sh`.

### Verification
| Command | Result |
|---|---|
| `pytest tests/unit/test_setup_env.py` | 15 passed |
| `ruff`, `mypy scripts/setup_env.py` | clean |

### Next task
**M3c-office** Virtual Office → **M11** → **M5b**.

## Session 6 (cont.) — M3c-office Virtual Office

### Completed
- **Scene mapping** `app/domain/office.py`: pure `character_state(facts, now)` → work / idle / queued / wait / pause / stop / error, exactly the §13A.3 table (STOP wins; fresh heartbeat = work, also while PAUSED finishing a step; stale heartbeat = "not responding", never work; failed job ≤ 10 min = "!" with the error class and job link; due jobs without a run = at the desk "next cron"; not-yet-due jobs = restroom with the real reason and retry time; else coffee). Wait kinds: rate limit / backoff / AI budget / daily cap. Workflow hand-offs → paper between desks.
- **API** `GET /api/v1/control/office`: per-agent facts and stats today (done, failed, AI cost), events of the last 3 min (email sent → envelope to the mail desk; ORDER_CONFIRMED → folder to the director + "✅ Yangi buyurtma" toast; hand-offs), today's funnel on the meeting-room board, night flag in `DEFAULT_TIMEZONE`, cron health.
- **Page** `/control/office` (home → "🏢 Virtual ofis", tabs Ofis / Grafik / Vazifalar): canvas office drawn in code from the owner's "SMY Ofis" demo (7 desks, kitchen, restroom, director's room with the big red STOP, meeting room, mail desk, day/night); text list of employees as accessible alternative; tap a character or list row → side sheet with live stats, job link, settings link and Activate / Pause / Stop (owner only, same audit-logged forms, return to the office). Director's STOP and resume ask for confirmation.
- Vanilla JS (`static/office.js`, 27 KB, no inline code, CSP unchanged), polling every 4 s only while visible, 30 fps cap, `prefers-reduced-motion` → no walking/flying, 375 px (scroll the building) and iPad layouts, dark mode.
- Service worker: static shell now **network-first** (cache only offline) and cache `v3` — before, CSS/JS changes did not reach phones that had the old cache.
- `[hidden]` always hides (a `display` rule had overridden it).

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.13) | 729 passed, 1 skipped |
| integration on MariaDB 10.6 / 10.11 / MySQL 8.0 | 291 / 291 / 291 passed |
| `ruff`, `ruff format --check`, `mypy app`, `node --check office.js` | clean |
| Playwright (Chromium) 375 px phone, 1024 px iPad, dark, reduced motion, seeded real states | no console errors, no horizontal page scroll, every row of the table visible; sheet Pause and director STOP → `/control/office?changed=1`, two `agent_control.set` audit rows, everyone walks to the exit with lights dimmed |

Not verified: real devices (only Chromium emulation); frame rate on a mid-range phone.

### Next task
**M11** analytics (funnel), budgets, provider usage, restore drill → **M5b** AI layer once the key exists. Deploy: "SMY yangilash" (`bash ~/smyagent/scripts/deploy.sh`), nothing else.

## Session 6 (cont.) — M11a AI budget, usage accounting, analytics

### Completed
- **Budget** (`app/domain/budget.py`, `app/application/budget.py`): `MONTHLY_AI_BUDGET_USD=10` (new), `DAILY_AI_BUDGET_USD=0` = automatic (monthly ÷ days in month); local-time day/month windows; `ensure_may_spend()` raises `BudgetExhaustedError` → the runner sets the job `BUDGET_DEFERRED` until the next day/month without using an attempt and releases it when the window turns; owner bot told once per day; 80 % and 100 % alerts once per window. Hook for the AI layer: `ctx.ensure_may_call_ai()` before, `ctx.record_usage()` after every call.
- **Usage** table `provider_usage` (migration `0014`): kind (ai/search), provider, model, module, job, requests, tokens, estimated USD — no texts. Discovery records every search; paid search providers obey `DAILY_SEARCH_LIMIT` (deferred to tomorrow).
- Control Center / Virtual Office show the effective daily budget.
- **📈 `/analytics`** (home link): period Today / 7 / 30 days / all; AI budget month/day meters; funnel found → researched → qualified → offer → approved → contacted → replied → order → won with each rate's denominator printed, inbound bot clients separate from outreach replies, "how is this counted" definition; outreach (emails, Telegram, replies %, bounces %); agent success per module; AI cost by module and model; search requests.

### Verification
| Command | Result |
|---|---|
| `pytest` (SQLite, Python 3.13, SQLAlchemy 2.0.55 as in CI) | 740 passed, 1 skipped |
| integration on MariaDB 10.6 / 10.11 / MySQL 8.0; `alembic check` (MySQL 8.0) | 298 / 298 / 298 passed; no differences |
| Playwright 375 px `/analytics` | no horizontal scroll, no errors |

### Server change for the owner
None required: `MONTHLY_AI_BUDGET_USD` defaults to 10 when missing from `.env`. "SMY yangilash" applies migration `0014`.

### Next task
**M11b**: backup verification + restore drill into a scratch DB, post-deploy smoke test, security review.
