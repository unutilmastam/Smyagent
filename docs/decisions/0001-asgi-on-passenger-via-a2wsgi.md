# ADR-0001: FastAPI on Passenger via a2wsgi

**Context.** hostmaster.uz cPanel "Setup Python App" uses Phusion Passenger, which speaks WSGI. FastAPI is ASGI. No VPS is available.

**Decision.** Keep FastAPI. Expose it to Passenger with the `a2wsgi` ASGI→WSGI adapter in `deployment/cpanel/passenger_wsgi.py`. All request handlers are written so they work under the bridge: no WebSockets, no streaming responses, no reliance on `BackgroundTasks`. Long work goes to the job queue (ADR-0004).

**Consequences.** A CI test calls `/api/v1/health` through the WSGI callable to guarantee the bridge keeps working. On a VPS the same app runs under uvicorn with no code change. Fallback if the bridge proves unworkable on the real host: a thin Flask adapter over the same application layer.
