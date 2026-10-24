# ADR-0005: "Mustafo — SMY Agent" persona discloses it is an AI

**Context.** The owner wants clients to interact with a named assistant. Presenting an AI as a human would be deceptive, damages trust when discovered, and conflicts with the project's no-impersonation rule.

**Decision.** The persona is named Mustafo, is always introduced as the AI assistant of ITcoDe.Uz in the first message, answers truthfully when asked whether it is a bot, and hands off to the owner on request. It can never commit to prices or contracts. Texts are configurable in `persona_settings`.

**Consequences.** Disclosure is enforced by tests and by the Quality Gate, not only by prompts.
