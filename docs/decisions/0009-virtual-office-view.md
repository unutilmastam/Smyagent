# ADR-0009: "Virtual Office" view of the Control Center

**Context.** The owner wants to watch his agents as employees in an office: 7 desks with computers, a kitchen, a restroom; agents drink coffee or go to the restroom when "tired". The project rule is that monitoring must reflect real activity, never simulated animation.

**Decision.** Add a canvas-based office scene as a second Control Center view. Every visual state is a pure mapping from real snapshot data: working = running job with fresh heartbeat; coffee in the kitchen = idle (no queued work); restroom = waiting on rate limit/backoff/budget; lounge = paused; desk light off = stopped; red "!" = error; folder to the director = order confirmed. Original art only, vendored static assets, CSP unchanged, no server-side build. Details: CLAUDE.md §13A.3, milestone M3c-office.

**Implementation (2026-10-25).** `app/domain/office.py` (pure `character_state`, one unit test per table row; extra state *queued* = due jobs waiting for the next cron, shown at the desk with the monitor off), `app/application/office.py` + `GET /api/v1/control/office` (per-agent facts, stats today, events: email sent, order confirmed, workflow hand-offs), `/control/office` + `app/web/static/office.js` (vanilla Canvas 2D, ~27 KB, no images/fonts, 30 fps cap, paused when hidden, `prefers-reduced-motion` → no walking). Events are animated once per id and never replayed after a reload. The director's red button and the side-sheet buttons submit the same CSRF-protected, audit-logged forms as the Control Center.

**Consequences.** The fun view never misleads: "on a coffee break" literally means "nothing to do right now". The mapping function is unit-tested. Extra front-end work (~1–2 sessions), no extra running cost.
