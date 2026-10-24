# HTTP API

All private routes require a logged-in session (cookie `smy_session`); state-changing
requests also require the CSRF token (`X-CSRF-Token` header). Errors use one envelope:

```json
{"error": {"code": "unauthorized", "message": "Authentication required", "request_id": "…"}}
```

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/v1/health` | public | `{"status":"ok","service":"SMY Agent"}` |
| GET | `/api/v1/ready` | public | config + DB ping; 503 when not ready |
| GET | `/api/v1/companies` | session | `q`, `country` (ISO2), `state`, `sort` (`newest`\|`oldest`\|`name`), `page`, `per_page` (≤100). Returns `{items, meta:{page,per_page,total,pages}}`; each item has `is_fixture` |
| GET | `/api/v1/companies/{id}` | session | domains, sources (with `is_fixture`, `retrieved_at`), lead stage |
| POST | `/api/v1/telegram/webhook` | `X-Telegram-Bot-Api-Secret-Token` | owner bot; reply returned as a Bot API `sendMessage` call in the response body; 404 when not configured |

Invalid filter values are ignored (treated as "all"), not rejected. OpenAPI docs at
`/docs` exist only outside production.
