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
| [0008](0008-order-intake-and-price-list.md) | Agent takes orders: no prices to clients, Order Brief, client confirmation, handoff to owner | Accepted |
| [0009](0009-virtual-office-view.md) | Virtual Office view: office scene driven only by real agent state | Accepted |

Format: Context → Decision → Consequences. New ADRs get the next number; superseded ADRs are marked, never deleted.
| [0010](0010-openstreetmap-first-discovery-source.md) | OpenStreetMap (Overpass) as the free first discovery source; seeded UZ cities | Accepted |
| [0011](0011-deterministic-offers-and-quality-gate.md) | Deterministic price-free offer templates + rules-based Quality Gate; owner approves | Accepted |
| [0012](0012-owner-editable-agent-settings.md) | Owner-editable, versioned agent settings; hard rules stay locked | Accepted |
| [0013](0013-mustafo-deterministic-order-intake.md) | Rules-based Mustafo bot: opt-out first, gate-checked replies, explicit confirmation, owner handoff | Accepted |
| [0014](0014-outreach-email-and-assisted-telegram.md) | Capped email to business addresses, one-tap Telegram, never send twice, auto-pause | Accepted |
