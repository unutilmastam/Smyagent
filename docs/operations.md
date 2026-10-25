# Operations — background jobs, monitoring, alerts (M10)

Everything here works from a phone: the dashboard (`/jobs`, `/control`) and the owner bot.

## How the background work runs

cPanel cron starts `python -m app.jobs.runner` every 5 minutes (command:
`docs/deployment-cpanel.md` §7). One invocation:

1. writes a `runner_runs` row (`RUNNING` → `OK | LOCKED | STOPPED | ERROR`) — proof that cron works;
2. takes the `job-runner` lock (an overlapping invocation records `LOCKED` and exits);
3. stale jobs (no heartbeat for 10 min — the process was killed): requeued if attempts
   remain, otherwise `FAILED` with `stale: …` and reported (a job that kills the process
   every time cannot loop forever);
4. schedules due work for ACTIVE agents;
5. runs at most `--max-jobs` jobs within `--max-seconds`; each job is cut after
   `--max-job-seconds` (default 120 s, SIGALRM) and retried with backoff;
6. once a day: retention cleanup (see `privacy-and-data-retention.md`);
7. releases the lock, finishes its `runner_runs` row, sends collected alerts.

Retries: exponential backoff with jitter (30 s × 2ⁿ, max 6 h) for retryable errors
(timeouts, HTTP 429/5xx); permanent errors (HTTP 4xx, bugs) fail at once. Deferred work
(daily email cap, spacing) is requeued without using an attempt.

## Is it working? (cron liveness)

| Where | Shows |
|---|---|
| `/jobs`, `/control` | "Cron is running: last run N min ago" — or red when no run for > 15 min |
| `/` (home) | the red/yellow warning only when something is wrong |
| owner bot `/status`, `/jobs` | `✅ ishlayapti` / `🛑 to'xtab qolgan` / `⏰ sozlanmagan` |
| `GET /api/v1/control/snapshot` | `cron_health`, `cron_minutes_ago` (used by the Virtual Office) |

The runner cannot report its own absence, so "late" is detected by the dashboard and bot
from the last `runner_runs.started_at` (threshold: 3 missed 5-minute runs).

## Alerts in the owner bot

- **Job failed for good** (attempts used up or permanent error): `⚠️ Vazifa bajarilmadi` with
  agent, job type, attempts, error class, and buttons 🔁 *Qayta urinish* (`job_retry:<id>`)
  and 🔎 *Ko'rish* (opens `/jobs/<id>`).
- **Runner crashed** (DB down, bug): `🛑 Fon ishlari … xato bilan to'xtadi` with the error class.
- Deduplicated by key (`job_failed:<type>:<error class>`, numbers and ids removed): at most one
  message per key per 6 hours; repeats are counted and reported with the next message.
- Retries in progress are **not** alerted. If the database itself is unreachable no alert can
  be recorded: the dashboard is down too, and the cron "late" warning appears once it is back.
- Alerts are sent after the transaction commits, never from inside it.

## Owner actions

| Action | Dashboard | Bot |
|---|---|---|
| See queue, filter by status/agent | `/jobs?status=FAILED&module=research_audit` | `/jobs` (counts + last 5 failures) |
| Job details: input, error, every run with step/cost | `/jobs/<id>` | 🔎 button |
| Retry a FAILED/CANCELLED job (fresh attempts) | `/jobs/<id>` → 🔁 | `/retry <id-prefix>` or 🔁 button |
| Cancel a QUEUED job | `/jobs/<id>` → ✕ | — |
| Stop a running job | Control Center (pause/stop the agent) | `/agent <name> off` |

Retry and cancel are owner-only, CSRF-protected and audit-logged (`job.retry`, `job.cancel`).

## Logs

- `~/smyagent_data/runner.log` — JSON lines, rotated at 1 MB × 3 (`--log-file`). Secrets are
  redacted by the formatter. Useful queries: `grep runner_finished`, `grep job_failed`.
- `~/smyagent_data/runner-errors.log` — only what is printed before logging starts
  (configuration errors). Normally empty.
- `~/smyagent_data/deploy.log`, `backup.log`.

## Troubleshooting

| Symptom | Check |
|---|---|
| "never ran" | cron entry missing; path to the virtualenv Python wrong (`ls ~/virtualenv/smyagent/`) |
| "late" after it worked | cPanel → Cron Jobs still there? `tail ~/smyagent_data/runner-errors.log`; host process limits (Resource Usage) |
| many `LOCKED` rows | an invocation runs longer than the cron interval: lower `--max-jobs` or `--max-seconds` |
| jobs failing with `timeout` | the provider/site is slow; raise `--max-job-seconds` (keep it < 600) |
| jobs failing with `stale` | the host killed the process (memory/CPU limit) during that job |

## On a VPS later

The same queue is served by a persistent worker looping `JobRunner.run()`; `runner_runs`,
alerts and retention work unchanged. The SIGALRM limit needs the job to run in the main
thread (or switch to a subprocess per job).
