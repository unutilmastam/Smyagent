# ADR-0007: Cost-optimized AI — all features, minimal spend

**Context.** The owner wants every planned feature, with the lowest possible running cost. Estimated spend with Claude Sonnet for most text was $20–30/month; with Haiku everywhere $5–10; with a free provider for internal tasks close to $0.

**Decision.** Deterministic rules first; Claude Haiku as the default model; Claude Sonnet only for client-facing long text and only when enabled by a setting (off by default); optional Groq free tier for internal-only tasks; Batch API for non-urgent work; prompt caching; result caching by content hash; default budget $10/month enforced in code. Free tiers that may train on inputs are never used for client data. Details: CLAUDE.md §12.1.

**Consequences.** Running cost target ≤ $10/month at ~500 companies/month. Client-facing text quality can be raised later by flipping `AI_USE_LARGE_FOR_CLIENT_TEXT=true`. The provider abstraction must support a fallback chain and per-call usage accounting from M5.

**Implementation (M11a, 2026-10-25).** `MONTHLY_AI_BUDGET_USD` (default 10) is the hard cap; `DAILY_AI_BUDGET_USD=0` means automatic (monthly ÷ days of the month), any number is a stricter daily cap. Days and months are counted in `DEFAULT_TIMEZONE`. Every optional AI call goes through `TaskContext.ensure_may_call_ai()` (kill switch, then budget); when a window is used up the job becomes `BUDGET_DEFERRED` until the next local day/month (attempt not consumed) and the owner bot is told once per day. `TaskContext.record_usage()` writes `provider_usage` and adds tokens/cost to the agent run; crossing 80 % and 100 % of a window alerts once. Paid search providers (`paid = True`) are held to `DAILY_SEARCH_LIMIT`; OSM is free and only counted.
