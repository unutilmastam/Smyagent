# ADR-0011: Deterministic offer templates and a rules-based Quality Gate

**Context.** M7 needs offers for qualified leads before any AI provider key exists, and
CLAUDE.md §5 rule 5 / ADR-0008 forbid prices, amounts, deadlines and guarantees in
anything a client sees. ADR-0007 asks for no LLM call where rules suffice.

**Decision.**
1. First-contact offers are built deterministically from templates (UZ Latin, RU, EN)
   plus the company's recorded findings and opportunities. Facts are stated plainly;
   inferences are phrased as possibilities. Every offer starts with the Mustafo AI
   disclosure and ends with an opt-out and the signature. No number appears in the text.
2. The Quality Gate is a pure rules module (`app/domain/quality_gate.py`): prices,
   currency amounts (incl. Uzbek/Russian case endings), discounts, "free", guarantees,
   deadlines, contracts and prepayment → **rejected**; superlatives, claims about other
   clients, wrong script, excessive length → **needs_review**; missing disclosure,
   opt-out or evidence → **rejected**.
3. Default mode is owner approval for every offer (dashboard or Telegram inline
   buttons). Automatic sending of gate-clean offers is decided with M9 (outbound).
4. LLM-written or LLM-polished offers (Haiku, ADR-0007) can be added later behind the
   same gate; the gate never relies on the model to police itself.

**Consequences.** Offers cost nothing to produce and are reproducible; their wording
is generic until the AI layer exists. Uzbek Cyrillic offers fall back to Latin until
client language detection (M8). Pricing rules stay internal (M7b) and never reach
offer text.
