# ADR-0009: "Virtual Office" view of the Control Center

**Context.** The owner wants to watch his agents as employees in an office: 7 desks with computers, a kitchen, a restroom; agents drink coffee or go to the restroom when "tired". The project rule is that monitoring must reflect real activity, never simulated animation.

**Decision.** Add a canvas-based office scene as a second Control Center view. Every visual state is a pure mapping from real snapshot data: working = running job with fresh heartbeat; coffee in the kitchen = idle (no queued work); restroom = waiting on rate limit/backoff/budget; lounge = paused; desk light off = stopped; red "!" = error; folder to the director = order confirmed. Original art only, vendored static assets, CSP unchanged, no server-side build. Details: CLAUDE.md §13A.3, milestone M3c-office.

**Consequences.** The fun view never misleads: "on a coffee break" literally means "nothing to do right now". The mapping function is unit-tested. Extra front-end work (~1–2 sessions), no extra running cost.
