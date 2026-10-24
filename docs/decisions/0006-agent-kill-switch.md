# ADR-0006: Global and per-agent kill switch

**Context.** Agents act autonomously (research, AI calls, outbound email). The owner must be able to stop everything instantly from a phone.

**Decision.** `agent_controls` stores ACTIVE/PAUSED/STOPPED for each module plus a global row. The state is checked (1) before the runner claims a job, (2) between agent steps, (3) immediately before every outbound provider call, (4) before every AI call. Controls are available in the dashboard and the owner Telegram bot. Built in M3b, before any external sending exists.

**Consequences.** One extra indexed read per check; acceptable. Stop is effective within one step, not mid-HTTP-call.
