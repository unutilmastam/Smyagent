# ADR-0004: DB-backed job queue drained by cron

**Context.** Shared hosting does not allow persistent workers, Redis or Celery.

**Decision.** Jobs live in the `jobs` table. Cron runs `python -m app.jobs.runner --max-jobs N --max-seconds S` every few minutes. A `job_locks` row with expiry prevents overlapping runners; each job is claimed with an optimistic `UPDATE ... WHERE status='queued'`. Runs are bounded and exit cleanly.

**Consequences.** Latency is up to one cron interval. On a VPS a long-running worker reuses the same queue interface.
