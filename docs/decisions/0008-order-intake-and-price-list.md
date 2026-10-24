# ADR-0008: Order intake and owner-approved price list

**Context.** The owner wants the system to find clients, engage them, make offers, take orders, and hand over clients who have agreed, so he only builds. Earlier rules forbade the persona from mentioning any price, which blocks offers.

**Decision.** (1) The persona may quote only prices from an owner-approved price list, phrased as "from …" with what is included; anything outside the list goes to owner approval. (2) A new order-intake step: Mustafo interviews an interested client, fills an Order Brief, asks the client to confirm it, and on confirmation the lead enters `ORDER_CONFIRMED` and the owner is notified once with the brief, conversation and proposal. The owner agrees final price, deadline and payment. The brief is exportable as a Markdown project spec for Claude Code. Details: CLAUDE.md §5 rule 5, §8.2, §9.2, M8.

**Consequences.** Offers can go out automatically when fully covered by the approved list. The agent still never makes binding commitments; payments stay out of scope until the owner asks.
