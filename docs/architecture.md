# SMY Agent — Architecture

Status: Milestone 0 baseline (2026-10-25). Hosting facts marked **UNVERIFIED** until
`scripts/check_environment.py` output from hostmaster.uz is recorded in
`docs/deployment-cpanel.md`.

## 1. Shape

Modular monolith, one Python codebase, one database.

```
            ┌──────────── Presentation ────────────┐
            │ Jinja2+HTMX dashboard │ Telegram bots │
            └───────────────┬──────────────────────┘
                        API layer (FastAPI, /api/v1)
                            │
                  Application services (use cases)
                            │
     Domain (pure Python: entities, state machines, scoring, policies)
                            │
   Infrastructure (SQLAlchemy repos, AI/search/Telegram/email adapters,
                   SSRF-safe fetcher)
                            │
         Jobs: DB queue + bounded runner started by cron
```

Dependency rule: arrows point downward only. `domain/` imports nothing from
`infrastructure/`, `api/` or `web/`. Adapters implement interfaces (Protocols)
defined next to the domain/application code that uses them.

## 2. Runtime topology

| Concern | Shared hosting (now) | VPS (later) |
|---|---|---|
| HTTP | Passenger (WSGI) → a2wsgi → FastAPI | uvicorn/gunicorn (ASGI) |
| Background work | cron → `python -m app.jobs.runner` (bounded) | persistent worker, same queue interface |
| Live dashboard updates | polling every 3–5 s | SSE/WebSocket optional |
| Database | MySQL/MariaDB | PostgreSQL or MySQL |
| Telegram | webhook | webhook or polling |

Business code is identical in both columns; only `deployment/` and entry
points differ.

## 3. Modules (agents)

Seven modules, each with typed Pydantic input/output and declared permissions:
Orchestrator, Discovery, Research & Audit, Opportunity & Scoring,
Proposal & Requirements, Conversation (Mustafo), Quality Gate.
Analytics is a reporting service. Every module checks `agent_controls`
(ACTIVE/PAUSED/STOPPED) before claiming work and between steps; every
outbound send checks the global kill switch immediately before the provider
call. See CLAUDE.md §8 and §13A.

## 4. State machines

- Company research: `NEW → RESEARCH_PENDING → RESEARCHED → ANALYZED` (+ `RESEARCH_FAILED`, `ARCHIVED`).
- Deal pipeline: `CANDIDATE → QUALIFIED → PROPOSAL_DRAFTED → AWAITING_APPROVAL → APPROVED → CONTACTED → RESPONDED → MEETING → WON → CLOSED`
  (+ `LOST`, `DISQUALIFIED`, `DO_NOT_CONTACT`, `PAUSED`, `ERROR`).

Transitions are validated in the domain layer and recorded as
`workflow_events` with actor and reason.

## 5. Cross-cutting

- Config: `pydantic-settings`, env vars only; production validation at startup.
- Logging: JSON lines with request ID / job ID; secrets redacted.
- Errors: one JSON error envelope for the API.
- Security: see `docs/security.md`.

## 6. Decisions

See `docs/decisions/` (ADR-0001 … ADR-0006).
