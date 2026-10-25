# Owner setup status (hosting, domains, bots, keys)

What the **owner** has already done outside the code, from his phone, and what is still
open. Every Claude Code session reads this before planning deployment or integration
work (CLAUDE.md §22). Secrets are **never** written here — only whether they exist.

Last updated: 2026-10-25 18:20 (Asia/Tashkent 20:20) — written from the planning chat session.

## Done

| Item | Details | Date |
|---|---|---|
| Hosting check | `scripts/check_environment.py` run in cPanel Terminal on hosting1.hostmaster.uz, 0 internal errors. Results and decisions are in `docs/deployment-cpanel.md` §1 (Python 3.12 chosen; MySQL 8.0; all external APIs reachable; no Node/Docker/Redis; system python 3.9 has no `ensurepip` → use only the Setup Python App virtualenv). | 2026-10-25 |
| Subdomain | **`agent.itcode.uz`** created in cPanel → Domains, own document root (`~/agent.itcode.uz`, not shared with `public_html`). | 2026-10-25 |
| SSL | Let's Encrypt certificate for `agent.itcode.uz` requested in cPanel → SSL/TLS (status was "Adding certificate…" at 18:16). Confirm the green lock before setting the Telegram webhook (webhooks require valid HTTPS). | 2026-10-25 (in progress) |
| Owner bot | **@direktorsmybot** — display name *DIREKTOR-SMY*. Created in @BotFather; commands list set (`status, stop_all, resume_all, agent, proposals, approve, reject, help`); joining groups disabled. Token kept by the owner. | 2026-10-25 |
| Client bot | **@mustafosmybot** — display name *Mustafo SMY agent*; about text "ITcoDe.Uz AI yordamchisi • itcode.uz • @ITcoDe_Uz"; description with the AI disclosure. Token kept by the owner. | 2026-10-25 |
| Owner Telegram ID | Numeric ID obtained via @userinfobot and kept by the owner (goes into `TELEGRAM_ADMIN_IDS`). | 2026-10-25 |
| GitHub access | Claude GitHub App installed for `unutilmastam/Smyagent`; auto-merge on green CI authorized (CLAUDE.md §23). | 2026-10-25 |

## Not done yet (needed for go-live)

| Item | Where | Notes |
|---|---|---|
| MySQL database + user | cPanel → MySQL Databases (or Database Wizard) | utf8mb4. Gives `DATABASE_URL=mysql+pymysql://<user>:<pass>@localhost/<db>?charset=utf8mb4`. Also read the **server version** shown there. |
| Python app | cPanel → Setup Python App | Python **3.12**, app root e.g. `smyagent` (git clone, outside `public_html`), URL `agent.itcode.uz`, startup file `deployment/cpanel/passenger_wsgi.py` (if nested path is refused: root-level shim), entry point `application`. |
| Code on the server | cPanel → Git Version Control (clone `https://github.com/unutilmastam/Smyagent.git`) or Terminal `git clone` | Repo is public. |
| Environment variables | Setup Python App → Environment variables | `APP_ENV=production`, `APP_SECRET_KEY`, `APP_BASE_URL=https://agent.itcode.uz`, `DATABASE_URL`, `TELEGRAM_ADMIN_BOT_TOKEN`, `TELEGRAM_CLIENT_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_ADMIN_IDS`, later `SMTP_*`/`IMAP_*`, `AI_*`. Owner types the secret values himself. |
| Migrations + owner account | Terminal in the app virtualenv | `alembic upgrade head`, `python -m app.cli create-owner --username <name>`, `python -m app.cli check-config`. |
| Webhooks | Terminal | `python -m app.cli telegram-set-webhook`, `telegram-set-client-webhook`, check with `telegram-webhook-info`. |
| Cron jobs | cPanel → Cron Jobs | Job runner per `docs/deployment-cpanel.md` §7; read the minimum allowed interval. |
| Email for outreach | cPanel → Email Accounts + Email Deliverability | `agent@itcode.uz`, SPF/DKIM valid, DMARC TXT (§6c). Keep `OUTBOUND_SENDING_ENABLED=false` until the owner decides. |
| Anthropic API key | platform.claude.com | Needed for M5b (AI summaries). Owner was told: international Visa/Mastercard, set a spend limit; budget target ≤ $10/month (ADR-0007). |
| Resource limits | cPanel → Resource Usage | CPU / PMEM / EP / NPROC not yet reported. |

## Things on the account that must not be touched
- `smy.itcode.uz` with app **`smarthome-api`** mounted at `/api` (Python 3.10) — owner's Smart Home project.
- Virtualenv `smy-api` (3.10) — do not reuse unless the owner confirms it is unused.
- Other sites/subdomains (`usta.itcode.uz`, `jahonoro…`, `nbx…`, `master…`, `public_html`).

## Owner decisions made in the planning chat (already in CLAUDE.md / ADRs)
- Product name SMY Agent; client persona "Mustafo — SMY Agent", always disclosed as AI (ADR-0005).
- Agent never quotes prices; it interests the client, confirms an Order Brief and hands over "client X agrees to have Y built" (ADR-0008 amended).
- No Telegram userbots / unsolicited automated Telegram or SMS; email to public business addresses with caps; one-tap Telegram for the owner (CLAUDE.md §13.2a, M9).
- All features, minimal cost; Haiku default, Sonnet opt-in, Batch, caching, $10/month budget (ADR-0007).
- Virtual Office view wanted (ADR-0009). A visual demo was published as a claude.ai artifact ("SMY Ofis") to show the intended look; it uses simulated data only.
- Deploy target `agent.itcode.uz` (2026-10-25).

## How the owner works
Phone and iPad only, no computer. Every server step must be a short copy-paste for cPanel
Terminal or a tap path in cPanel, explained in Uzbek (Latin). He never pastes tokens into
chat or Git; ask him to type secrets directly into cPanel.

## Suggested next session task
Prepare a step-by-step **first deployment guide** in Uzbek (`docs/deploy-first-time-uz.md`)
plus `scripts/deploy.sh` (idempotent: pip install in the app venv, DB backup if tables exist,
`alembic upgrade head`, `touch tmp/restart.txt`, health check), following the "Not done yet"
table above. Then continue M10 → M11 → M3c-office → M5b.
