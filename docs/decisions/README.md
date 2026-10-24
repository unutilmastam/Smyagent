# Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-asgi-on-passenger-via-a2wsgi.md) | Run FastAPI on WSGI-only Passenger through a2wsgi | Accepted (pending hosting verification) |
| [0002](0002-mysql-primary-database.md) | MySQL/MariaDB is the primary production database | Accepted |
| [0003](0003-server-rendered-ui.md) | Jinja2 + HTMX mobile-first UI, no Node on server | Accepted |
| [0004](0004-cron-driven-db-job-queue.md) | DB-backed job queue drained by a bounded cron runner | Accepted |
| [0005](0005-mustafo-persona-ai-disclosure.md) | Client persona "Mustafo" always discloses it is an AI | Accepted |
| [0006](0006-agent-kill-switch.md) | Global and per-agent kill switch enforced at every external action | Accepted |
| [0007](0007-cost-optimized-ai.md) | All features at minimal cost: rules first, Haiku default, Sonnet opt-in, Batch, caching, free tier for internal tasks | Accepted |

Format: Context → Decision → Consequences. New ADRs get the next number; superseded ADRs are marked, never deleted.
