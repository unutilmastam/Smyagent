# ADR-0014: Outreach — capped email to business addresses, assisted Telegram, never twice

**Context.** M9 sends approved offers. Spam, double sends and contacting people who opted
out would damage the owner's domain and reputation and break the law (CLAUDE.md §4.6,
§15.3). Hosting is cPanel: SMTP/IMAP via a domain mailbox, cron every few minutes, no
background workers.

**Decision.**
1. One first contact per company (`first:<company>`) on its best public channel — role
   email (info@, sales@ …) if SMTP is configured, else a Telegram one-tap task, else a
   phone task — and at most one follow-up (`follow_up:<company>`) after ≥ 5 days without
   a reply. Personal addresses are never used.
2. Email is sent by the cron runner within a warm-up cap (10/day +5/day up to 30 by
   default), a minimum randomized gap, the email pause and the kill switch. Cap/gap waits
   requeue the job (`DeferTaskError`) without consuming retries.
3. **No double send:** an event is committed as SENDING before the SMTP call; a run that
   finds SENDING marks it UNKNOWN and never resends. Temporary SMTP errors before
   delivery return it to QUEUED; 5xx refusals are bounces.
4. Every email is plain text with disclosure, "reply STOP", a signed one-click unsubscribe
   link (`List-Unsubscribe` + `List-Unsubscribe-Post`) and sender identification. No
   tracking pixels.
5. IMAP (optional) reads replies (quoted text stripped before classification), STOP →
   suppression, DSN bounces and ARF complaints. Auto-pause on any complaint or > 5 %
   bounces (≥ 20 sends in 30 days); only the owner resumes.
6. Owner approval of an offer is the approval to send it. With "email clean offers
   without my approval" on, gate-clean offers (verdict *approved*) for companies with a
   business email are approved by `system:outreach_auto_send` (audit-logged);
   *needs_review* always waits for the owner. Telegram/phone stay manual.

**Consequences.** Sending speed is bounded by caps and cron; email to companies without
SPF/DKIM on the sender domain will mostly land in spam, so the deployment doc requires
them first. UNKNOWN sends need a human look at the mailbox.
