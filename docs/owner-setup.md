# Owner setup status (hosting, domains, bots, keys)

What the **owner** has already done outside the code, from his phone, and what is still
open. Every Claude Code session reads this before planning deployment or integration
work (CLAUDE.md §22). Secrets are **never** written here — only whether they exist.

Last updated: 2026-10-25 (Asia/Tashkent evening) — after the owner reported the first deploy.

## Status: **live** at https://agent.itcode.uz (first deploy done 2026-10-25)

## Done

| Item | Details | Date |
|---|---|---|
| Hosting check | `scripts/check_environment.py` on hosting1.hostmaster.uz; results in `docs/deployment-cpanel.md` §1 (Python 3.12, MySQL 8.0, external APIs reachable, no Node/Docker/Redis). | 2026-10-25 |
| Subdomain + SSL | **`agent.itcode.uz`**, own document root; Let's Encrypt certificate active (webhooks accepted). | 2026-10-25 |
| MySQL | Database **`itcode_smyagent`**, user **`itcode_smy`** with ALL PRIVILEGES. Password only in `~/smyagent/.env`. | 2026-10-25 |
| Python app | Setup Python App: **Python 3.12.12**, root `~/smyagent`, URL `agent.itcode.uz`, startup `passenger_wsgi.py`, entry `application`, no env vars in that screen. (First attempt was attached to `itcode.uz/` by the dropdown default; destroyed and recreated — guide §2 now warns.) | 2026-10-25 |
| Code | `git` checkout of `main` in `~/smyagent` (guide §3). Updates: `bash ~/smyagent/scripts/deploy.sh` ("SMY yangilash"). | 2026-10-25 |
| `.env` | Written by `scripts/setup_env.py` (mode 600): DB URL, both bot tokens, admin ID, generated `APP_SECRET_KEY` and `TELEGRAM_WEBHOOK_SECRET`, `OUTBOUND_SENDING_ENABLED=false`, `SEARCH_PROVIDER=osm`. | 2026-10-25 |
| Deploy | `deploy.sh`: 13 migrations applied, health ✅. First run failed at line 31 (`/dev/fd` missing on the host) — fixed in PR #26. | 2026-10-25 |
| Owner account | `python -m app.cli create-owner` done; dashboard login works. | 2026-10-25 |
| Owner bot | **@direktorsmybot** (*DIREKTOR-SMY*); webhook set, `last_error` empty. Token was shown on screen once → **revoked** in @BotFather, new token in `.env`, webhook re-set. | 2026-10-25 |
| Client bot | **@mustafosmybot** (*Mustafo SMY agent*), AI-disclosure description; webhook set, `last_error` empty. Token also revoked and replaced as above. | 2026-10-25 |
| Cron | `*/5` job runner with `--log-file ~/smyagent_data/runner.log`; `17 3 * * *` `db-backup`. | 2026-10-25 |
| Owner Telegram ID | In `TELEGRAM_ADMIN_IDS`. | 2026-10-25 |
| GitHub access | Claude GitHub App on `unutilmastam/Smyagent`; auto-merge on green CI authorized (CLAUDE.md §23). | 2026-10-25 |

## Not done yet

| Item | Where | Notes |
|---|---|---|
| Email for outreach | cPanel → Email Accounts + Email Deliverability | `agent@itcode.uz`, SPF/DKIM valid, DMARC TXT (`deployment-cpanel.md` §6c), then `setup_env.py --set SMTP_PASSWORD` etc. Keep `OUTBOUND_SENDING_ENABLED=false` until the owner decides. |
| Anthropic API key | platform.claude.com | For M5b (AI layer). International card, spend limit; budget ≤ $10/month (ADR-0007). Owner types it with `setup_env.py --set AI_API_KEY`. |
| Resource limits | cPanel → Resource Usage | CPU / PMEM / EP / NPROC not yet reported. |
| Bot command list | @BotFather → /setcommands for @direktorsmybot | Add `jobs` and `retry` (M10) to the existing list. |

## How the owner connects
SSH with **Termius** on the phone (pasting into cPanel Terminal is awkward). Long pasted
lines can lose their beginning in Termius: paste into the bottom input field, check, then
Enter (guide intro). Secrets are typed only at hidden prompts — paste first, then Enter.

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

## First deployment (done)
Guide: **`docs/deploy-first-time-uz.md`** (owner follows it on the phone),
`scripts/setup_env.py` (writes `~/smyagent/.env`, mode 600 — settings are **not** typed in
the Setup Python App screen, because those reach only the web app, not Terminal or cron) and
`scripts/deploy.sh` (idempotent update: pull → pip → check-config → backup → migrate →
restart → health). Update this file when the owner reports each step done.

## Suggested next session task
Owner order (2026-10-25): **M3c-office** Virtual Office (`/control/office`, one tap from the
home screen) → **M11** → **M5b** AI layer once the key exists. Each stage ships with only
"SMY yangilash" (`bash ~/smyagent/scripts/deploy.sh`) needed on the server.
