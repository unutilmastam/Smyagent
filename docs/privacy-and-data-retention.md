# Privacy and data retention

Engineering guidance, not legal advice (CLAUDE.md §15.3). Data is stored in the MySQL
database on hostmaster.uz (Uzbekistan).

| Data | Source | Why | Retention | Deletion |
|---|---|---|---|---|
| Company name, country, city, industry, domain | OpenStreetMap (ODbL), CSV, manual entry | find and research potential clients | while relevant; archived companies reviewed yearly | delete company (cascades to domains, sources, contacts) |
| Public **business** contacts: company phone, role email (info@, sales@ …), business Telegram | the same public sources | first contact with the business (M9) | as above | removed with the company; an opt-out also writes a suppression record (M8/M9) so the contact is never used again |
| Source records (`company_sources`) | provider + URL + retrieval time | evidence and attribution | as long as the company | with the company |
| Owner account, sessions, login attempts (IP stored only as HMAC) | owner | authentication, security | sessions ≤ 30 days; login attempts pruned (15-min window used) | automatic expiry |
| Audit log | system | accountability | 2 years | manual, by the owner |

Rules:
- Only **business** contact data is collected; no private individuals' data from social networks.
- Emails that look personal (not a role address) are flagged `is_role_address = false` and are not used for automatic outreach (M9).
- No raw HTML of external sites is stored (M5 stores extracted text + hash).
- Data sent abroad: AI providers (from M5) receive only minimal business text, never client conversations on free tiers (ADR-0007). Overpass queries contain only city and category names.
- A deletion request for a company is handled by deleting the company record; the suppression list keeps only the normalized contact value needed to never contact it again.
