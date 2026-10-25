# ADR-0013: Deterministic Mustafo conversations and order intake

**Context.** M8 needs a client bot that discloses it is an AI, detects opt-outs, never
states prices, collects an Order Brief and hands a confirmed order to the owner — before
any AI provider key exists (ADR-0007), on WSGI hosting without background workers.

**Decision.**
1. Rules, not an LLM: script-based language detection (UZ Latin / UZ Cyrillic / RU / EN;
   a mid-chat switch only on a script change), keyword intents in priority order with
   **opt-out first**, a fixed 7-question interview, explicit "ha/да/yes" confirmation
   only (anything else is kept as a correction and the brief is shown again).
2. Every reply passes the Quality Gate in `client_reply` mode (prices, commitments,
   owner words). The brief summary shown to the client never echoes money or deadline
   figures; the client's budget words are kept for the owner only.
3. Reply modes (agent settings): **approve_all** (default, CLAUDE.md §8.1) — each reply
   is a draft with ✅/❌ buttons in the owner bot; **auto_safe** — gate-clean replies go
   out in the webhook response if `OUTBOUND_SENDING_ENABLED` and the kill switch allow
   it, otherwise they fall back to drafts.
4. Approved drafts and owner replies are sent by an `outbound.telegram_reply` job (cron),
   which re-checks suppression and the kill switch right before the Bot API call and is
   cancelled by the global STOP.
5. Opt-out writes a suppression record immediately, blocks queued messages, cancels the
   brief and moves the lead to `DO_NOT_CONTACT`; Mustafo never writes again.
6. `ORDER_CONFIRMED` is entered only from a confirmed brief with the confirmation message
   recorded; the owner notification is guarded by `notified_at` (exactly once). The owner
   decides: accept (WON), questions (handoff), decline (LOST).

**Consequences.** Free to run and fully testable; wording is fixed until the AI layer.
Approved replies wait up to one cron interval. A webhook-response send is best effort
(Telegram does not confirm it); the message is still recorded.
