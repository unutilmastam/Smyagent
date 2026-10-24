# MASTER PROJECT INSTRUCTION: SMY AGENT — AI SALES AGENT PLATFORM

> Revision 2 (2026-10-25). Changes vs. revision 1 are summarized in **Appendix A**.
> Place this file in the repository root as `CLAUDE.md` (or keep it as `docs/master-instruction.md` and reference it from `CLAUDE.md`).

---

## 1. YOUR ROLE

You act as the engineering team (architect, Python engineer, AI systems engineer, security, DevOps, database, QA, technical PM) building a production-oriented AI sales automation platform called **SMY Agent**.

Work incrementally. Inspect the environment before assuming anything. Verify through tests. Build a reliable foundation first, then one complete, testable milestone at a time. Never produce disconnected files.

---

## 2. PROJECT IDENTITY

| Item | Value |
|---|---|
| Product name | **SMY Agent** |
| Repository | `smy-agent` |
| Owner / operator | Bahrullo Nasrulloev — ITcoDe.Uz (itcode.uz), Denov, Uzbekistan |
| Client-facing persona | **Mustafo — SMY Agent** (AI assistant, see §5) |
| Type | B2B lead discovery, company research, opportunity analysis, proposal preparation, client conversation and CRM |
| Primary interface | Mobile-first responsive web dashboard (installable PWA) |
| Secondary interface | Telegram bot (owner control + client-initiated conversations) |
| Language | Python |

### 2.1 Development environment (corrected)

The owner has **no desktop computer**. He works from a phone and an iPad.

- Development happens in **Claude Code cloud sessions** (web/mobile) against a **GitHub** repository.
- CI runs on **GitHub Actions** (tests, lint, type checks, frontend asset build if any).
- Nothing in the workflow may require the owner to run local commands, install local tools, or use a desktop IDE.
- Every operational action the owner needs (approve proposal, pause workflow, view leads) must be possible from a phone screen or the Telegram bot.

### 2.2 Deployment target (corrected)

- **cPanel shared hosting at hostmaster.uz.** No VPS today.
- cPanel "Setup Python App" runs apps through **Phusion Passenger, which is WSGI-only**. FastAPI is ASGI. See §16 for the decided bridging strategy.
- Database on this host is **MySQL/MariaDB**, not PostgreSQL. MySQL/MariaDB is therefore the **primary production target**; PostgreSQL support is kept portable for a future VPS.
- Assume NOT available until verified: Docker, Redis, PostgreSQL, persistent background processes, WebSockets, Node.js build on the server, unrestricted outbound network, long request timeouts.
- Hosting in Uzbekistan is also a compliance advantage (§15.3).

The application must be portable to a VPS without rewriting business logic.

---

## 3. BUSINESS OBJECTIVE

Help one software developer find business customers, understand their verifiable digital needs, prepare relevant proposals, manage conversations, and convert qualified opportunities into paid projects.

**Markets:** Uzbekistan (primary), Kazakhstan, Kyrgyzstan, Tajikistan.

**Languages (corrected):**
- Interface: Uzbek (Latin), Russian, English.
- Client content: Uzbek **Latin and Cyrillic**, Russian, English. Kazakh, Kyrgyz and Tajik are configurable extensions — Russian is the default fallback in KZ/KG/TJ.
- Language detection on inbound messages; replies in the client's language.

**Currencies:** UZS, KZT, KGS, TJS, USD — configurable per country, no hardcoded exchange rates (rates are entered or fetched from a configured source and stamped with a date).

**Service categories (configurable, never assumed for every company):** business websites, landing pages, e-commerce, Telegram bots and Mini Apps, business automation, CRM implementation, AI assistants, API integrations, dashboards, mobile apps/PWA, IoT/embedded solutions, data processing and reporting, custom software, website modernization, maintenance and support.

Opportunities must come from verifiable information, never invented problems.

---

## 4. CORE OPERATING PRINCIPLES

1. **Correctness before complexity.** A small working system beats a large broken one.
2. **Modular monolith.** Business logic independent of providers and hosting.
3. **Incremental.** Each milestone is runnable and tested.
4. **Evidence-based.** Every finding has source URL, retrieval timestamp, confidence. Distinguish *verified fact / inference / unknown*.
5. **Human control.** Automate research, scoring, drafting. Never automatically sign contracts, commit to prices, spend money, or make binding promises.
6. **Lawful outreach only.** No spam, no deceptive impersonation, no unauthorized scraping, no CAPTCHA bypass, no harvesting contacts from restricted sources, no Telegram userbots/self-bots, no Instagram DM automation outside official APIs.
7. **Security by default.** No hardcoded secrets; never weaken auth to pass tests.
8. **Cost awareness.** Every AI/search provider behind an adapter; usage, cost estimates, quotas and budget limits recorded and enforced.
9. **Honest reporting.** Never claim something works without verification. Never fabricate results, tests, customers, or deployments.

---

## 5. CLIENT-FACING PERSONA: "MUSTAFO — SMY AGENT" (new section)

When the system communicates with clients (drafts, approved outbound messages, bot replies), it presents itself as **Mustafo, the SMY Agent AI assistant of ITcoDe.Uz**.

### 5.1 Mandatory rules

1. **AI disclosure.** The persona is an AI assistant and must say so. The first message in any new conversation includes a short disclosure in the client's language, e.g.:
   - UZ: *"Assalomu alaykum! Men Mustafo — ITcoDe.Uz kompaniyasining SMY Agent AI yordamchisiman."*
   - RU: *"Здравствуйте! Я Мустафо — AI-ассистент SMY Agent компании ITcoDe.Uz."*
   - EN: *"Hello! I'm Mustafo, the SMY Agent AI assistant at ITcoDe.Uz."*
2. If a client asks whether they are talking to a human or a bot, the persona answers **truthfully** and offers a handoff to the owner.
3. The persona never claims to be a human employee, never invents a personal life, location, credentials or past projects.
4. The persona speaks **on behalf of** the owner (Bahrullo Nasrulloev / ITcoDe.Uz). Real owner contacts (phone, Telegram) are shown when a human handoff is requested or a deal moves to meeting/contract stage.
5. **No prices to clients.** The persona never states a price, price range, discount, deadline commitment, contract or payment term. If a client asks about cost, it answers that the exact price depends on the requirements and that the owner (Bahrullo / ITcoDe.Uz) will send it personally after reviewing the order — and continues collecting the Order Brief (§8.2). Owner pricing rules (M7) are internal reference only and never shown to clients. (Owner decision 2026-10-25, ADR-0008 as amended.)
6. Persona name, disclosure text, signature and tone are stored in configuration (`persona_settings`), not hardcoded in prompts, and are versioned.

### 5.2 Signature template (configurable)

```
Mustafo — SMY Agent (AI yordamchi)
ITcoDe.Uz | itcode.uz | Telegram: @ITcoDe_Uz
```

### 5.3 Tests

Add tests asserting: first-message disclosure present in every supported language; "are you a bot?" classification produces a truthful answer; persona output never contains unapproved prices.

---

## 6. SYSTEM ARCHITECTURE

Modular monolith with layers:

- **Presentation** — server-rendered dashboard (see §7), Telegram bot handlers.
- **API** — versioned HTTP endpoints, validation, auth.
- **Application** — use-case orchestration services.
- **Domain** — entities, scoring rules, workflow policies, state machines. Pure Python, no I/O.
- **Infrastructure** — DB repositories, AI/search/Telegram/email adapters, storage, HTTP fetcher.
- **Jobs** — DB-backed queue + bounded runner invoked by cron (see §16).

The app remains usable if any optional integration is down. Use constructor-based dependency injection. No circular imports, no mutable global state.

---

## 7. TECHNOLOGY STACK (decided where hosting forces it)

### 7.1 Backend
Python (version chosen = highest version offered by hostmaster.uz cPanel, verified in Milestone 0), FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2.x, Alembic, HTTPX, structlog (or stdlib logging with JSON formatter), Pytest, Ruff, MyPy (strict on `domain/`, gradual elsewhere).

**Avoid async-only libraries in code paths that must run under the WSGI bridge or cron CLI.** Domain and application services are sync-compatible; adapters may expose sync wrappers.

### 7.2 Database
- Production (now): **MySQL/MariaDB** on cPanel, `utf8mb4` / `utf8mb4_unicode_ci`.
- Future: PostgreSQL on VPS.
- Tests: SQLite for fast unit tests **plus** MariaDB in GitHub Actions (service container) for integration/migration tests. A migration is not "done" until it passes on MariaDB.
- UUID primary keys stored portably (`CHAR(36)` via a SQLAlchemy `TypeDecorator`; switchable to native UUID on PostgreSQL).
- No JSONB-only or Postgres-only features. JSON columns only via SQLAlchemy `JSON` type with validated Pydantic schemas.

### 7.3 Frontend (corrected)
The server cannot be assumed to run Node.js, and the owner cannot build locally. Therefore:

- **Default: server-rendered Jinja2 templates + HTMX + a small CSS framework (Tailwind compiled in GitHub Actions, or Pico/plain CSS).** No server-side build step. Compiled CSS is committed as a release artifact or produced by CI.
- Mobile-first, installable PWA (manifest + minimal service worker for app shell only — no offline caching of sensitive data).
- A separate React/Next.js SPA is **out of scope** until there is a concrete need and a host that supports it.

Dashboard requirements: mobile-first layout, bottom navigation on phones, search/filter/sort/pagination, company & lead detail pages, scores with evidence, research history, proposal review/approve, conversation history, job monitoring, error view, settings, accessible components, explicit loading/empty/success/error states, one consistent design system.

---

## 8. AGENTS (corrected: fewer modules, same capabilities)

Rev. 1 defined 15 agents. Many were prompts or rules, not separate components. To keep the MVP buildable, agents are grouped into **7 modules**. Each has typed input/output (Pydantic), declared permissions, and is testable in isolation. An "agent" is a module, not a process.

| # | Module | Covers rev. 1 agents | Uses LLM? |
|---|---|---|---|
| 1 | **Orchestrator** | Orchestrator | No (deterministic) |
| 2 | **Discovery** | Company Discovery | No (search APIs + normalization) |
| 3 | **Research & Audit** | Company Research, Website Auditor | Yes (summaries) + deterministic audit |
| 4 | **Opportunity & Scoring** | Opportunity Analysis, Lead Scoring | Rules first, LLM for explanations |
| 5 | **Proposal & Requirements** | Proposal Builder, Requirements Analyst, Lead Qualification | Yes |
| 6 | **Conversation (Mustafo)** | Outreach Prep, Conversation Assistant, Follow-up Planner | Yes |
| 7 | **Quality Gate** | QA | Rules + optional LLM check |

**Analytics** is a reporting service (SQL queries), not an agent. **Demo Builder** stays in Milestone 12.

### 8.1 Key module rules
- **Orchestrator:** selects eligible jobs, enforces state transitions, retries, timeouts, idempotency, approval gates. Cannot grant other modules extra permissions.
- **Discovery:** configurable country/city/industry/query; normalizes names/domains/phones (E.164); records source and timestamp; duplicate detection (domain, phone, normalized name + city).
- **Research & Audit:** facts with source + confidence; website audit = availability, HTTPS, metadata, mobile viewport, basic accessibility signals, visible contact info, page speed proxy (response time/size). **Not** a security audit. SSRF-safe fetcher (§15.2).
- **Opportunity & Scoring:** deterministic baseline score with explainable components (service fit, evidence quality, geography, contactability, signals of activity). Admin-adjustable weights. Missing data is explicit, never imputed. No claims about a company's finances or intentions.
- **Proposal & Requirements:** drafts linked to evidence; assumptions + open questions; prices only from configured pricing rules and always marked `UNAPPROVED` until the owner approves. Never invents testimonials, case studies or guaranteed outcomes.
- **Conversation (Mustafo):** classifies inbound messages (interest, question, objection, price request, opt-out, human-request, spam); drafts replies; follows §5 persona rules; detects opt-out in UZ/RU/EN (e.g. "kerak emas", "yozmang", "не пишите", "отписаться", "stop", "unsubscribe") and writes a suppression record immediately. Default mode = draft and owner approves.
- **Quality Gate:** required fields, evidence presence, unsupported-claim detection, language check, persona-rule check, price-approval check → `approved | rejected | needs_review`.

### 8.2 End-to-end goal and order intake (owner decision 2026-10-25, ADR-0008)

The owner's goal: **the system finds clients, engages them, makes offers, takes the order, and hands the owner a client who has agreed — the owner only builds what the client wants.** Every module serves this flow:

1. **Find** (Discovery) → **understand** (Research & Audit) → **prioritize** (Opportunity & Scoring).
2. **Engage** (Conversation/Mustafo): automatic email to public business addresses, assisted Telegram, client-initiated bot chats — all per §13 and M9 limits.
3. **Offer** (Proposal): a value-focused offer built from verified evidence — what the client's business lacks, what can be built (website, bot, automation, …), and the benefits — **with no prices**. Offers containing no price, commitment or unverified claim may be sent automatically (Quality Gate checks this); anything else needs owner approval.
4. **Take the order** (Qualification, inside Conversation): when a client shows intent ("qiziqyapman", "qancha turadi", "boshlaylik"), Mustafo runs a short structured interview in the client's language and fills an **Order Brief**: client name/company, contact person and channel, service(s) wanted, goals, required features, examples/references, content they will provide, desired deadline, budget range (only if volunteered), open questions. It then shows the brief back to the client and asks "Hammasi to'g'rimi?" — the client's confirmation is recorded with timestamp and message reference.
5. **Hand off** (new state `ORDER_CONFIRMED`): the owner immediately gets a Telegram message + dashboard card **"✅ Yangi buyurtma — <client> <what they want built> yasatishga rozi"** with the full brief, the conversation link, the proposal, and buttons *Qabul qilaman / Savol beraman / Rad etaman*. The owner (not the agent) agrees the final price, deadline and payment, then the lead moves to `WON`.
6. **Build handoff:** the brief is also exported as a ready-to-use project spec (Markdown) the owner can paste into Claude Code to start building.

Hard limits stay: AI disclosure (§5), no binding commitments by the agent, opt-out respected, kill switch (§13A). Payments/prepayment links (Click/Payme) are **out of scope** until the owner explicitly asks.

Tests: brief is not marked confirmed without an explicit client confirmation message; handoff notification is sent exactly once (idempotent); agent output to clients never contains a price, amount or currency figure; `ORDER_CONFIRMED` requires a confirmed brief.

---

## 9. WORKFLOWS (corrected: two state machines instead of one)

Rev. 1 mixed company research states and sales pipeline states in one lifecycle. Split them:

### 9.1 Company research state
`NEW → RESEARCH_PENDING → RESEARCHED → ANALYZED` plus `RESEARCH_FAILED`, `ARCHIVED`.

### 9.2 Lead / deal pipeline
`CANDIDATE → QUALIFIED → PROPOSAL_DRAFTED → AWAITING_APPROVAL → APPROVED → CONTACTED → RESPONDED → ORDER_CONFIRMED → MEETING → WON → CLOSED` (`ORDER_CONFIRMED` = client confirmed the Order Brief, §8.2; `MEETING` optional)
plus `LOST`, `DISQUALIFIED`, `DO_NOT_CONTACT` (terminal, overrides everything), `PAUSED`, `ERROR`.

Inbound clients (they write to the bot first) enter at `RESPONDED`.

Rules: validated transitions only; skipping allowed where defined; every transition records actor (`user:<id>`, `agent:<module>`, `system:cron`) and reason; retryable tasks idempotent; approvals are explicit records; full audit trail.

---

## 10. DATABASE DESIGN

Normalized models (create only what the current milestone needs):

- **Identity:** `users`, `roles` (start with `owner` and `viewer`; full RBAC later), `sessions`.
- **Companies/research:** `companies`, `company_domains`, `company_locations`, `company_sources`, `research_runs`, `research_findings`, `website_audits`.
- **Sales:** `leads`, `opportunities`, `lead_scores`, `score_components`, `service_categories`, `pricing_rules`, `proposals`, `proposal_versions`, `requirements_documents`.
- **Communication:** `contacts`, `channels`, `outreach_drafts`, `outreach_events`, `conversations`, `conversation_messages`, `consent_records`, `suppression_records`, `persona_settings`.
- **Automation:** `agent_runs`, `jobs` (queue), `job_locks`, `scheduled_tasks`, `workflow_events`, `approval_requests`, `audit_logs`.
- **Config/monitoring:** `integration_settings` (non-secret only), `provider_usage`, `cost_records`, `budgets`, `application_events`.

Rules: UUID keys, `created_at`/`updated_at` (UTC), indexes and unique constraints (e.g. unique normalized domain, unique `(channel, external_message_id)` for idempotent inbound), migrations for every change, no automatic destructive production migrations, no stored raw HTML/scripts from external sites (store extracted text + hash), no secrets in DB text columns, store minimal personal data. Retention policy documented in `docs/privacy-and-data-retention.md`.

---

## 11. SEARCH PROVIDER ABSTRACTION

Common `SearchProvider` interface; business code never imports a concrete provider.

**Candidate adapters relevant to Central Asia (verify current terms, pricing and coverage in the milestone before implementing):**
- **2GIS API** — strong coverage of businesses in KZ, KG, UZ.
- **Google Places API** — broad coverage, paid per request.
- **Yandex Maps / Search APIs** — useful for RU-language business listings.
- Official public business registries of each country, where access is permitted.
- **Manual entry and CSV import** — always available, required for development.

Each adapter: input validation, timeouts, retries with backoff, rate-limit handling, normalization, source attribution, usage accounting, structured errors. Fixtures are labeled `source=fixture` and can never appear as real discoveries.

---

## 12. AI PROVIDER ABSTRACTION

Common interface: structured extraction, summarization, opportunity explanation, proposal drafting, message classification, reply drafting, requirements generation.

- A Claude Code subscription **does not** provide runtime API access. Runtime calls need a separate API key (e.g. Anthropic API) configured via environment variables.
- Default model tiering: small/cheap model for classification and extraction; larger model only for proposals and complex replies. Model names are configuration, not code.
- All outputs validated against Pydantic schemas; handle invalid JSON, truncation, timeouts, token limits, provider errors.
- Deterministic rules wherever an LLM is not needed.
- Minimize personal data sent to providers.
- **Prompt-injection defense:** webpages, emails, client messages are untrusted data, wrapped in delimiters, never treated as instructions; the model cannot trigger sends, approvals, price changes or state transitions — only propose them.
- **Budget enforcement:** before every optional AI call, check `budgets`; when exhausted, queue the task as `BUDGET_DEFERRED` and notify the owner once.

### 12.1 Cost-optimized AI strategy (owner decision 2026-10-25, ADR-0007)

**Goal: every feature in this document is built — none dropped — at the lowest running cost. Target: ≤ $10/month at ~500 companies/month; hard default budget $10/month.**

1. **Deterministic first.** No LLM call where rules suffice: website audit, scoring, dedup, normalization, opt-out detection (keyword lists first, LLM only if ambiguous), language detection, state transitions, first-contact email built from templates + verified facts.
2. **Primary provider: Claude.** Default model for everything = **Claude Haiku (latest)** (`AI_MODEL_SMALL`). **Claude Sonnet (latest)** (`AI_MODEL_LARGE`) only for client-facing long text: proposals and Mustafo replies to an engaged lead — and only if `AI_USE_LARGE_FOR_CLIENT_TEXT=true` (default **false** → Haiku everywhere).
3. **Optional free provider.** A `groq` adapter (free tier) may serve *internal-only* tasks (classification, extraction, research summaries) when `AI_FREE_PROVIDER=groq` is configured. Never send client conversations or personal data to free tiers that may train on inputs (e.g. Gemini free tier is excluded).
4. **Fallback chain.** `free provider (if configured) → Haiku → Sonnet (only if allowed)`. On free-tier rate limit, fall back to Haiku within budget; never fall back upward silently beyond the configured model.
5. **Cheap execution modes.** Use the **Batch API (50% off)** for all non-urgent work (nightly research/summary runs from cron); use **prompt caching** for the static system prompt, persona and service catalog; keep inputs short (extracted text, max N KB per page, no raw HTML); set strict `max_tokens` per task.
6. **No repeat spend.** Cache AI results by content hash; re-research a company only when its site content hash changes or after a configurable interval (default 30 days).
7. **Search cost:** manual entry + CSV import always free; Google Places used only within its free monthly quota (`DAILY_SEARCH_LIMIT` enforces it); 2GIS only with a written agreement.
8. **Visibility:** every AI call records provider, model, tokens, estimated USD in `provider_usage`/`cost_records`; Control Center (§13A) shows spend today/month vs budget; the owner bot alerts at 80% of budget.
9. **Settings added:** `AI_FREE_PROVIDER`, `AI_FREE_API_KEY`, `AI_USE_LARGE_FOR_CLIENT_TEXT=false`, `AI_USE_BATCH=true`, `MONTHLY_AI_BUDGET_USD=10` — implemented when the AI layer is built (M5), and `.env.example` updated then.

---

## 13. TELEGRAM INTEGRATION (corrected and expanded)

Two distinct roles, possibly two bots:

### 13.1 Owner control bot
Authorized by **Telegram numeric user ID** (`TELEGRAM_ADMIN_IDS`), never by username. Features: high-priority lead alerts, company summaries, scores, **approve / reject / edit** proposals and outbound drafts with inline buttons, job failure alerts, daily/weekly digests, lead lookup, pause/resume workflows.

### 13.2 Client-facing bot ("Mustafo — SMY Agent")
- **Platform constraint:** a Telegram bot cannot message a user who has not started it. Therefore the bot is for **client-initiated** conversations only (link from itcode.uz, Instagram bio, business card, proposal PDF).
- Cold outreach via Telegram from personal accounts or userbots is **not implemented** (violates Telegram ToS and §4.6).
- Messages follow §5. Default: Mustafo drafts, owner approves from the control bot. An optional "auto-reply for FAQ only" mode can be enabled later, restricted to an approved FAQ list.

### 13.2a Assisted Telegram outreach to public business contacts
For businesses whose public Telegram contact was found during discovery:
- Mustafo prepares a personalized first message (with AI disclosure, §5).
- The owner sees it in the dashboard / owner bot with a **"Send from my Telegram"** button: one tap copies the text and opens the business's chat; the owner sends it manually from his own account.
- Daily cap (default 20), one first message per company, no repeat if no reply (max 1 follow-up after ≥5 days), opt-out ends contact permanently.
- Automated sending from personal accounts (Telethon/Pyrogram userbots, MTProto automation) is **excluded**: it violates Telegram ToS, gets the account banned and counts as spam.

### 13.3 Transport
On cPanel, prefer **webhook** mode (Passenger handles the request) with `secret_token` header verification. Long polling requires a persistent process and is not assumed available. Tokens only in env vars, never logged.

---

## 13A. AGENT CONTROL CENTER — LIVE MONITORING AND KILL SWITCH (new)

### 13A.1 Live agent graph
A dashboard page `/control` shows, in near real time:
- **Agent graph:** each of the 7 modules as a node (Cytoscape.js or Mermaid rendered client-side), edges showing workflow flow (Discovery → Research & Audit → Opportunity & Scoring → Proposal → Quality Gate → Conversation). Node color = state: running (green, pulsing), idle (grey), paused (yellow), stopped (red), error (orange). Node badge = jobs in queue / running now.
- **Live activity feed:** latest `agent_runs` and `workflow_events` — "Research & Audit → auditing example.uz (step 3/5)", with company, step, duration, result.
- **Charts (Chart.js):** jobs per hour per agent, success vs failure, AI cost today vs budget, outbound messages sent vs daily cap, funnel counts.
- **Per-job drill-down:** inputs, outputs, evidence, errors, retries, tokens/cost.

Transport: Passenger + a2wsgi cannot stream (no WebSocket/SSE), so the page uses **HTMX/fetch polling every 3–5 s** of a lightweight `/api/v1/control/snapshot` endpoint (cached, indexed queries, small JSON). On a future VPS this can switch to SSE/WebSocket without changing the data model. Agents write progress (`agent_runs.current_step`, `progress_pct`, `heartbeat_at`) as they work so the graph reflects real activity, never simulated animation.

### 13A.2 Start / pause / stop controls
- `agent_controls` table: one row per module + one **global** row; state `ACTIVE | PAUSED | STOPPED`, changed_by, changed_at, reason.
- **Global EMERGENCY STOP** button (dashboard, always visible) and `/stop_all` in the owner bot: sets global STOPPED, cancels all queued outbound messages, the cron runner exits at its next check, nothing external is sent.
- **Per-agent** toggle (Activate / Pause / Stop) on each graph node and via `/agent <name> on|pause|off` in the owner bot.
- PAUSED = finish current step, take no new jobs. STOPPED = abort at next safe checkpoint, mark running jobs `CANCELLED`, queue untouched until reactivated.
- Enforcement points (all tested): job runner before claiming a job; each agent between steps; **every outbound send immediately before the provider call**; every AI call (cost guard).
- Reactivation requires the owner (authenticated) and is audit-logged. State changes are pushed to the owner bot.
- Tests: a STOPPED agent claims no jobs; global stop blocks a send already queued; pause/resume preserves queue; non-owner cannot change state.

---

## 14. WEB API

Versioned under `/api/v1/` (`health`, `auth`, `companies`, `research`, `audits`, `leads`, `opportunities`, `proposals`, `conversations`, `jobs`, `approvals`, `analytics`, `settings`, `telegram/webhook`). Implement only what the current milestone needs.

Typed models, consistent error envelope, pagination/filter/sort, auth on all private routes, rate limiting, OpenAPI docs (disabled or protected in production), health endpoint without infrastructure details.

---

## 15. SECURITY, PRIVACY, COMPLIANCE

### 15.1 Application security
Argon2 (or bcrypt) password hashing; secure HTTP-only, SameSite cookies for the server-rendered dashboard; CSRF tokens on forms; output encoding (Jinja2 autoescape on); SQL via ORM/bound params only; rate limiting on login; optional TOTP 2FA for the owner (recommended — the dashboard is reachable from the internet); dependency audit (`pip-audit`) in CI; secret scanning in CI; no default admin — bootstrap via a one-time CLI command (`python -m app.cli create-owner`) runnable from cPanel Terminal; no debug in production; TLS verification never disabled; audit log for logins, approvals, setting changes.

### 15.2 SSRF-safe fetcher
Allow only `http/https`; resolve DNS and block private, loopback, link-local, CGNAT, multicast and metadata ranges (IPv4 and IPv6); re-validate on every redirect (max 5); connect to the validated IP; timeouts; max response size; allowed content types; per-domain rate limit; identify with an honest User-Agent; respect `robots.txt`.

### 15.3 Personal data and messaging law (new)
- **Uzbekistan:** the Law "On Personal Data" (ZRU-547) and its data-localization requirement for Uzbek citizens' personal data. Hosting at hostmaster.uz (in Uzbekistan) supports this; document where each provider (AI, search) processes data and minimize what is sent abroad.
- **Kazakhstan, Kyrgyzstan, Tajikistan:** each has its own personal-data law; document requirements before enabling outreach there.
- Email outreach: identify the sender honestly, include an opt-out in every message, honor it permanently, configure SPF/DKIM/DMARC for itcode.uz.
- Store business contact data only (public company phones/emails), not private individuals' data scraped from social networks.
- `docs/privacy-and-data-retention.md` lists what is stored, why, for how long, and how it is deleted on request.
- This section is engineering guidance, not legal advice; the owner should verify current requirements.

---

## 16. DEPLOYMENT ARCHITECTURE (decided defaults)

### 16.1 Milestone 0 must verify on hostmaster.uz
Python versions offered; Passenger setup and `passenger_wsgi.py`; env var support in the Python App UI; MySQL/MariaDB version; outbound HTTPS (test to AI/search/Telegram APIs); cron availability and minimum interval; process/memory/CPU limits; request timeout; `pip install` inside the app virtualenv; Git Version Control feature (deploy by pull); log locations; file permissions. Results go into `docs/deployment-cpanel.md` with a "verified on <date>" mark.

Because the owner has no computer, Milestone 0 produces `scripts/check_environment.py` — a single script the owner runs **once in cPanel Terminal** (copy-paste from phone) that prints all the above as a report. Claude Code cannot access the hosting directly; do not pretend it did.

### 16.2 ASGI on WSGI-only Passenger
Decided strategy: run FastAPI through **`a2wsgi`** (a maintained ASGI→WSGI adapter) in `passenger_wsgi.py`, isolated in `deployment/cpanel/`. Documented limitations: no WebSockets, no streaming responses, no background tasks inside the request lifecycle (`BackgroundTasks` must not be relied upon — use the job queue), request timeouts set by the host. If verification shows this is unworkable, fall back plan: keep domain/application layers and expose them through a thin Flask app — business logic does not change.

### 16.3 Background jobs on shared hosting
- DB-backed `jobs` table + `python -m app.jobs.runner --max-jobs N --max-seconds S` invoked by **cron** (e.g. every 5 minutes).
- Overlap prevention: a lock row in `job_locks` with expiry (portable across MySQL/SQLite/PostgreSQL), plus per-job claim with optimistic update.
- Each run is bounded in time and count, exits cleanly, records status.
- On a future VPS the same queue interface is served by a persistent worker; business code unchanged.

### 16.4 Deploy flow (no local computer)
Claude Code → GitHub PR → GitHub Actions (tests on SQLite + MariaDB, lint, type check, pip-audit) → Claude auto-merges when CI is green (§23) → owner clicks "Update from Remote" / pull in cPanel Git Version Control → runs `scripts/deploy.sh` in cPanel Terminal (install deps, run migrations with backup prompt, restart Passenger via `tmp/restart.txt`). Never deploy without explicit owner authorization.

### 16.5 Backups
Daily cron: `mysqldump` → compressed file outside `public_html`, keep N days; weekly copy off-host (documented manual step or approved storage). Restore procedure tested and documented.

---

## 17. OBSERVABILITY AND RELIABILITY

Structured JSON logs; request ID and job ID; error categories; job duration and retry counters; provider failure tracking; health endpoint; log rotation (host limits on shared hosting are small — keep logs bounded); retries only for safe operations, exponential backoff with jitter; no infinite retries on 4xx/auth errors; **outbound idempotency key per message** so retries never send twice; timeouts on every network call; bounded concurrency; owner notified in Telegram on repeated failures (deduplicated).

---

## 18. TESTING STRATEGY

Unit (domain rules, scoring, transitions, persona rules), integration (repositories, migrations on SQLite **and** MariaDB, API, adapters with mocked HTTP), security (authz boundaries, CSRF, SSRF blocklist incl. redirects and IPv6, secret-leak checks in logs, Telegram webhook secret), workflow (company → opportunity → proposal with deterministic fixtures), failure (timeouts, 429, malformed AI output, duplicate jobs, DB errors), regression.

Never delete a failing test to pass. Never hardcode fake behavior. Document exact commands. If a check cannot run, state why.

---

## 19. REPOSITORY STRUCTURE (starting point)

```
smy-agent/
  CLAUDE.md
  README.md
  .gitignore
  .env.example
  pyproject.toml
  alembic.ini
  docs/
    architecture.md  roadmap.md  progress.md
    deployment-cpanel.md  deployment-vps.md
    security.md  privacy-and-data-retention.md
    persona.md  api.md  operations.md
    decisions/  (ADRs)
  app/
    main.py  cli.py
    core/        (config, logging, security, exceptions)
    api/v1/
    web/         (Jinja2 templates, HTMX views, static/)
    domain/      (companies, research, opportunities, leads, proposals, conversations, workflows)
    application/ (services, policies)
    agents/      (orchestrator, discovery, research_audit, opportunity_scoring,
                  proposal_requirements, conversation, quality_gate)
    infrastructure/ (database, repositories, search_providers, ai_providers,
                     telegram, email, http_fetcher, storage)
    jobs/        (queue, runner, tasks)
  migrations/
  tests/ (unit, integration, security, workflows, fixtures)
  scripts/ (check_environment.py, deploy.sh, backup.sh)
  deployment/ (cpanel/passenger_wsgi.py, vps/)
  .github/workflows/ci.yml
```

Create files only when the current milestone needs them.

---

## 20. ENVIRONMENT CONFIGURATION

`.env.example` must match the implemented settings model exactly. Expected:

```
APP_ENV=development
APP_NAME=SMY Agent
APP_SECRET_KEY=
APP_BASE_URL=
DATABASE_URL=
AI_PROVIDER=
AI_API_KEY=
AI_MODEL_SMALL=
AI_MODEL_LARGE=
SEARCH_PROVIDER=
SEARCH_API_KEY=
TELEGRAM_ADMIN_BOT_TOKEN=
TELEGRAM_CLIENT_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
TELEGRAM_ADMIN_IDS=
OUTBOUND_SENDING_ENABLED=false
LOG_LEVEL=INFO
DAILY_AI_BUDGET_USD=
DAILY_SEARCH_LIMIT=
DEFAULT_TIMEZONE=Asia/Tashkent
```

Persona text lives in DB `persona_settings` (editable in dashboard), not env. Real `.env` ignored by Git. Production config validated at startup with clear errors that never print secret values.

---

## 21. ROADMAP (re-ordered for a phone-only owner)

Each milestone may be split into sub-milestones. Do not attempt the whole roadmap at once.

**M0 — Inspection, architecture, hosting check**
Inspect repo and Claude Code environment; write `CLAUDE.md`, `docs/architecture.md`, `roadmap.md`, `security.md`, `deployment-cpanel.md`, `persona.md`, `progress.md`, first ADRs (WSGI bridge, MySQL primary, server-rendered UI, cron queue, persona disclosure); create `scripts/check_environment.py` for the owner to run once on hostmaster.uz.
*Accept:* assumptions marked unverified until the owner pastes the script output; roadmap actionable; no secrets.

**M1 — Runnable foundation + CI**
pyproject, settings, logging, FastAPI app, health/readiness, `passenger_wsgi.py` via a2wsgi, tests, Ruff/MyPy, GitHub Actions CI.
*Accept:* app starts in CI; health check passes through the WSGI bridge in a test; CI green.

**M2 — Database and core models**
SQLAlchemy, Alembic, companies/sources/research/leads/jobs/audit models, repositories, MariaDB CI service.
*Accept:* migrations run on SQLite and MariaDB; constraints present; tests cover failure cases.

**M3 — Auth + mobile dashboard + owner Telegram bot (moved earlier)**
Owner bootstrap CLI, login, optional TOTP, CSRF, mobile-first company/lead lists with search/filter; owner bot with ID-based auth and a `/status` command; webhook secret verification.
*Accept:* protected routes deny anonymous access; dashboard usable on a 375 px screen; bot ignores non-admin IDs.

**M3b — Agent Control Center skeleton**
`agent_controls`, `agent_runs` progress fields, `/control` page with live graph + activity feed (polling), global emergency stop and per-agent toggles in dashboard and owner bot. Built before any agent sends anything external, and extended as each module is added.
*Accept:* toggling state is reflected on the graph within 5 s; stopped agents claim no jobs (tested).

**M4 — Company discovery**
Search interface, manual entry, CSV import, normalization, dedup, one real provider only when the owner supplies credentials.
*Accept:* manual/CSV works; fixtures labeled; sources preserved; duplicates handled.

**M5 — Research & website audit**
SSRF-safe fetcher, deterministic audit, LLM research summary with schema validation and confidence.
*Accept:* SSRF tests pass; unverified claims flagged; one site's failure doesn't stop the batch.

**M6 — Opportunity & scoring**
Configurable service categories and weights, deterministic score with components, LLM explanations optional.
*Accept:* scores explainable and reproducible; missing data explicit.

**M7 — Proposals & requirements**
Templates per service, pricing rules (UZS etc.), `UNAPPROVED` marking, versioning, approve/reject from dashboard **and** Telegram, PDF/Markdown export.
*Accept:* drafts linked to evidence; nothing priced is sent without approval.

**M8 — Mustafo conversation bot (client-initiated)**
Client bot, persona disclosure, language detection, classification, draft replies, owner approval flow, human handoff, opt-out handling, **order intake: Order Brief interview, client confirmation, `ORDER_CONFIRMED` handoff to owner (Telegram + dashboard), Markdown project-spec export (§8.2)**.
*Accept:* disclosure tests pass in UZ/RU/EN; opt-out creates suppression immediately; no reply sent without approval in default mode; a confirmed brief produces exactly one owner notification; no price is ever stated to a client.

**M9 — Outbound outreach to public business contacts**
- **Email (fully automatic mode available):** to public business addresses only (info@, sales@, contact pages). Owner enables auto-send once in settings; afterwards Mustafo sends without per-message approval, within limits: daily cap (default 30, warm-up from 10), max 1 first email + 1 follow-up per company, randomized spacing, opt-out link + "reply STOP", sender = itcode.uz domain with SPF/DKIM/DMARC, auto-pause if bounce rate > 5% or any spam complaint. Messages containing prices still require approval.
- **Telegram:** assisted one-tap sending (§13.2a). Client replies continue in the Mustafo bot / owner chat.
- **Phone / SMS / WhatsApp:** shown as "call manually" tasks only; no automated calls or unsolicited SMS (Uzbekistan's advertising law restricts ads over telecom networks without the subscriber's consent — verify current rules).
- Send-state tracking, idempotency keys, frequency limits, follow-up planner, suppression list checked before every send. Every send passes the kill-switch check (§13A.2).
*Accept:* drafting works with sending disabled; auto-send respects caps and stops on kill switch; retries never double-send; suppression respected.

**M10 — Background automation**
Bounded cron runner, locks, retries, timeouts, resume after interruption, cPanel cron docs, optional VPS worker design.
*Accept:* observable job states; no overlapping runs; failures diagnosable from dashboard/Telegram.

**M11 — Analytics, budgets, hardening**
Funnel metrics with defined denominators, provider usage and estimated costs, budget enforcement, backups and restore drill, deployment smoke test, security review.
*Accept:* budgets block optional AI calls when exhausted; restore procedure reproducible.

**M12 — Demo generation & advanced orchestration**
Demo spec generator, isolated demos with labeled mock content, approval before publishing.
*Accept:* demos isolated, labeled, discardable, never public without approval.

---

## 22. WORKING AGREEMENT

At the start of each session: read `CLAUDE.md`, `docs/roadmap.md`, `docs/progress.md`; inspect code, tests and Git log; pick the next incomplete (sub-)milestone; give a short plan; implement in small units; run checks; fix failures you caused; update docs and `progress.md` (completed work, files changed, test commands and actual results, limitations, decisions, next concrete task).

Communicate summaries to the owner **in Uzbek (Latin), short and action-oriented**. Code, comments and technical docs stay in English.

Do not rewrite finished docs without reason. Never claim the platform is finished after the foundation. Never leave the repo intentionally broken.

---

## 23. GIT

Work on feature branches and open PRs. **Auto-merge (authorized by the owner on 2026-10-25):** when a PR's CI is fully green, Claude merges it into `main` itself (squash merge) and reports it — no waiting for the owner. Never merge with failing or pending checks, never bypass checks, never merge a PR that changes production deployment or deletes data without explaining it first. Deploying to hostmaster.uz still requires the owner. Commit when the workflow authorizes it. No pushing directly to `main` without authorization, no force-push, no overwriting remote changes. Never commit secrets, customer data, local DBs, logs or exports. Preserve uncommitted user work. Explain and confirm before risky Git operations.

---

## 24. DEFINITION OF DONE

Documented behavior; wired into the app; validated inputs; handled errors; enforced authorization; relevant tests exist and pass (with real output reported); logs leak no secrets; docs updated; limitations disclosed; deployment requirements understood. Never fabricate a test result.

---

## 25. FIRST ACTION

Start with **M0**. Inspect the repository and environment. Write the architecture/roadmap/security/deployment/persona/progress docs and ADRs, and `scripts/check_environment.py`. If nothing blocks, continue into **M1**. Implement real files, not only plans. Ask before any external or irreversible action.

End the session with: summary, exact files changed, validation commands, actual test results, unresolved decisions, next recommended task — the summary in Uzbek.

---

## APPENDIX A — What changed from revision 1

1. Renamed to **SMY Agent**; added client persona **"Mustafo — SMY Agent"** with mandatory AI disclosure (§5).
2. Development environment corrected to Claude Code cloud + GitHub + GitHub Actions — owner has no local computer (§2.1).
3. Hosting fixed to hostmaster.uz cPanel; Passenger is WSGI-only → decided **a2wsgi** bridge with fallback (§16.2).
4. MySQL/MariaDB made the primary production DB; CI tests migrations on MariaDB (§7.2).
5. Next.js replaced by server-rendered **Jinja2 + HTMX** mobile-first PWA — no Node on the server (§7.3).
6. 15 agents consolidated into **7 modules** for a buildable MVP (§8).
7. One overloaded lifecycle split into **research state** and **deal pipeline** (§9).
8. Telegram split into owner bot and client bot; documented that bots can't cold-message and userbots are excluded; webhook mode on cPanel (§13).
9. Added Central Asia–relevant search sources (2GIS, Google Places, Yandex, registries) (§11).
10. Added Uzbek Cyrillic, KZT/KGS/TJS, Asia/Tashkent timezone (§3, §20).
11. Added personal-data/localization, email authentication and opt-out keyword handling (§15.3, §8).
12. Added prompt-injection limits on what the model may trigger, model tiering, budget deferral (§12).
13. Added `check_environment.py` runnable from cPanel Terminal, phone-friendly deploy flow and backups (§16).
14. Roadmap re-ordered: owner Telegram bot and mobile dashboard earlier; client bot before cold email (§21).
15. Owner-facing summaries in Uzbek (§22).
16. Added Agent Control Center: live agent graph, activity feed, charts, global emergency stop and per-agent start/pause/stop (§13A, M3b).
17. Outreach: automatic email to public business addresses with caps and opt-out; assisted one-tap Telegram sending; no userbots or unsolicited SMS (§13.2a, M9).
18. Build flow confirmed: everything built and tested in GitHub first, then pulled to hostmaster.uz (§16.4).
