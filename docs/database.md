# Database

Status: M2. Production target MySQL/MariaDB (ADR-0002); tests run on SQLite and
on MariaDB 10.6 + 10.11 in CI.

## Conventions

| Rule | How |
|---|---|
| Primary keys | UUID via `GUID` TypeDecorator → `CHAR(36)` (native `UUID` on PostgreSQL) |
| Timestamps | `UTCDateTime`: aware UTC in Python, naive UTC `DATETIME(6)` on MySQL; naive input rejected |
| Enums | Stored as `VARCHAR(32)` of the enum value (no native ENUM types) |
| JSON | SQLAlchemy `JSON` only; validated by Pydantic/repositories before writing |
| Indexed strings | ≤ 191 chars (utf8mb4 index limit on older InnoDB) |
| Table options (MySQL) | `InnoDB`, `utf8mb4`, `utf8mb4_unicode_ci` set explicitly in every migration |
| Constraint names | Deterministic naming convention (`app/infrastructure/database/base.py`) |
| Schema changes | Alembic only. Never `create_all` in production. Every migration must pass on SQLite and MariaDB |
| Transactions | Repositories never commit; the caller (service / `Database.transaction()`) does |

## Tables (M2)

| Table | Purpose | Key constraints |
|---|---|---|
| `companies` | Discovered/entered companies, research state (§9.1) | index (normalized_name, normalized_city), (country, research_state) |
| `company_domains` | Normalized bare hosts | **unique** `domain`; FK → companies (cascade) |
| `company_sources` | Where/when a company was found; `is_fixture` flag | FK → companies |
| `research_runs` | Research attempts per company | FK → companies |
| `leads` | Deal pipeline (§9.2), `resume_stage` for PAUSED/ERROR | **unique** `company_id` (one lead per company) |
| `workflow_events` | Append-only state transitions with actor + reason | index (entity_type, entity_id, created_at) |
| `audit_logs` | Logins, approvals, settings/control changes; `details` redacted | index created_at, (entity_type, entity_id) |
| `jobs` | DB-backed queue (ADR-0004) | **unique** `idempotency_key`; index (status, run_after) |
| `job_locks` | Named locks with expiry (cron overlap prevention) | PK `name` |
| `contacts` | Public business phones (E.164), emails (role flag), Telegram | unique (company, kind, value); index (kind, value) for cross-company dedup |
| `discovery_targets` | Cities × categories the Discovery agent searches; seeded with 6 UZ cities (migration 0006) | unique (country, city) |
| `website_audits` | Homepage audit: status, timing, size, title, score, checks (JSON), text excerpt + hash, error category — never raw HTML | index (company, fetched_at) |
| `research_findings` | Facts / inferences with confidence, source URL and retrieval time | index (company, retrieved_at), key |
| `agent_controls` | Kill switch: `global` + 7 modules (ADR-0006) | PK `module`; seeded ACTIVE by migration 0001 |

Duplicate detection (CLAUDE.md §8.1): by normalized domain (unique constraint) and
by normalized name + city (lookup, not a constraint — same name in one city may be
legitimate, so the second one is reported as a duplicate for review). Since M4 a shared phone,
email or Telegram contact is also a hard duplicate.

## Concurrency (portable, no `SKIP LOCKED`)

- **Job claim:** select a few due candidates, then `UPDATE jobs SET status='RUNNING' … WHERE id=? AND status='QUEUED'`; success only if `rowcount == 1`. Tested with two sessions.
- **Locks:** `INSERT` the lock row; on conflict `UPDATE … WHERE name=? AND (expires_at < now OR holder = me)`.
- **Stale jobs:** `requeue_stale()` returns RUNNING jobs without a recent heartbeat to the queue.
- **Kill switch:** `AgentControlRepository.effective()` combines global + module state (stricter wins) and treats a missing row as STOPPED (fail closed).

## Commands

```bash
# Uses DATABASE_URL from env / .env
alembic upgrade head          # apply migrations
alembic downgrade -1          # roll back one (never automatically in production)
alembic check                 # fails if models and migrations differ
alembic revision --autogenerate -m "describe change"   # then review by hand

# Tests
pytest                                             # SQLite
TEST_DATABASE_URL=mysql+pymysql://root:pw@127.0.0.1:3306/smy_test pytest tests/integration/db
```

Production: back up first (`mysqldump`), then `alembic upgrade head` — see
`deployment-cpanel.md`. Destructive migrations require an explicit owner-approved step.
