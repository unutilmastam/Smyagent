# ADR-0012: Owner-editable agent settings inside locked hard rules

**Context.** The owner wants to change what each agent does from his phone, without a
developer. Some rules (AI disclosure, no prices to clients, opt-out, kill switch,
lawful sources, owner-only commitments) protect him legally and must never be
switched off by configuration.

**Decision.**
1. One validated Pydantic model per agent (`app/domain/agent_settings.py`) with safe
   bounds; stored as JSON in `agent_settings`, every save snapshotted in
   `agent_setting_versions` and audit-logged. Restore re-saves an old version; reset
   saves defaults. Invalid stored data falls back to defaults.
2. Editable now: discovery results per search; research companies per run; hot-lead
   threshold (plus the existing scoring weights page); offered services, services per
   offer, minimum need strength and all offer texts per language; extra blocked/review
   words for the Quality Gate; free-text instructions for every agent.
3. Owner texts use only `{company}` / `{owner}` placeholders, substituted by plain
   replacement (never `str.format`). A sample offer with every service is run through
   the Quality Gate on save; a price, guarantee or deadline refuses the save.
   Disclosure, opt-out and signature are not editable and are always added.
4. Owner word lists only add to the gate's built-in rules.
5. Free-text instructions are stored now and used by AI-backed steps once an AI key is
   configured (ADR-0007); they are untrusted guidance below the hard rules.

**Consequences.** Behaviour changes need no deploy. Settings for Mustafo (M8) and
outreach (M9) join the same mechanism.
