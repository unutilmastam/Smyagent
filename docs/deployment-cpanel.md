# Deployment — cPanel (hostmaster.uz)

> **Status: UNVERIFIED.** Nothing below has been checked on the real account yet.
> The owner runs `scripts/check_environment.py` once in cPanel Terminal and
> pastes the output into a Claude Code session; the results then replace the
> "Expected" column with "Verified (date)".

## 1. Hosting facts to verify

| Item | Expected / assumed | Verified |
|---|---|---|
| Python versions in "Setup Python App" | 3.10–3.12 | ☐ |
| App server | Phusion Passenger, WSGI only | ☐ |
| Env vars settable in Python App UI | yes | ☐ |
| Database | MySQL or MariaDB | ☐ |
| Outbound HTTPS to api.telegram.org, api.anthropic.com, search APIs | allowed | ☐ |
| Cron Jobs, minimum interval | available, ≥1–5 min | ☐ |
| Memory / process limits | small (≈512 MB–1 GB, few processes) | ☐ |
| Request timeout | ≈30–120 s | ☐ |
| `pip install` inside app virtualenv | works | ☐ |
| Git Version Control (pull from GitHub) | available | ☐ |
| Terminal | available | ☐ |

## 2. Running the check (owner, from phone)

1. cPanel → **Terminal**.
2. Paste:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/unutilmastam/Smyagent/main/scripts/check_environment.py -o ~/smy_check.py && python3 ~/smy_check.py
   ```
   (If the repo is private, use cPanel Git Version Control to clone it first and run `python3 scripts/check_environment.py` from the clone.)
3. Copy the whole output into Claude Code.

The script only reads information and makes unauthenticated HTTPS requests to public API hostnames; it changes nothing (a throw-away virtualenv is created in a temp dir to test `pip`, then deleted). Username and home path are masked in the output. Options: `--offline` skips network tests, `--no-redact` disables masking.

Some facts cannot be read from the shell (Python versions in the Setup Python App dropdown, Resource Usage limits, cron minimum interval, MySQL server version without credentials); the script prints a short checklist of these at the end.

## 3. Planned deployment layout (after verification)

```
~/smyagent/                 # cPanel Git Version Control clone (not in public_html)
~/smyagent/deployment/cpanel/passenger_wsgi.py   # Application startup file
~/smyagent_data/            # backups, logs outside the web root
```

"Setup Python App":
- Application root: `smyagent`
- Application URL: chosen subdomain, e.g. `agent.itcode.uz`
- Startup file: `deployment/cpanel/passenger_wsgi.py`
- Entry point: `application`
- Environment variables: from `.env.example`, with `APP_ENV=production`

## 4. Update flow

1. Claude Code opens PR → CI green → owner merges on phone.
2. cPanel → Git Version Control → **Update from Remote**.
3. Terminal: `bash scripts/deploy.sh` (added in a later milestone: installs deps, backs up DB, runs migrations, touches `tmp/restart.txt`).
   Until then, from the app virtualenv: `pip install .` → `mysqldump` backup → `alembic upgrade head` → `touch tmp/restart.txt`.
   Create the MySQL database in cPanel with collation `utf8mb4_unicode_ci`; `DATABASE_URL=mysql+pymysql://user:pass@localhost/dbname?charset=utf8mb4`.

Never deploy without explicit owner authorization.

## 5. Known limitations of the WSGI bridge

No WebSockets, no streaming responses, no reliance on FastAPI `BackgroundTasks`, host request timeout applies. See ADR-0001.
