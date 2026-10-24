# ADR-0003: Server-rendered Jinja2 + HTMX UI

**Context.** No Node.js on the server is assumed; the owner has no computer to build a SPA; the dashboard is used mainly from a phone.

**Decision.** Jinja2 templates served by FastAPI, HTMX for partial updates and polling, small CSS (compiled in CI if Tailwind is used). Mobile-first, installable PWA shell.

**Consequences.** Deploy = git pull, no build step on the server. Live graphs use client-side JS libraries loaded as static files (Cytoscape.js / Chart.js). A React SPA can be added later behind the same API.
