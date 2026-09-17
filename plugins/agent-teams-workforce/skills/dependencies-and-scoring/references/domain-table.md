# Domain table — a starting point, known to be imperfect

Mark derived this from the PRD file names. It is a **starting grouping for the tiering
step, not an answer**, and its errors are to be corrected rather than trusted.

Two he named himself: `shell` and `mobile/shell` probably belong under `platform`, and
`mobile` could be a subdomain of platform rather than a domain of its own. Expect others.

A correction made here is a correction to the tiering, so record what changed and why
alongside the edge file — the next pass revises this grouping, not just the edges.

| Domain | Subdomain | Topics |
|---|---|---|
| platform | — | data residency and storage; idempotency; networking stacks; service chassis; state machine; type vault; web performance and seo |
| platform | event gateway | ledger; publication; routing |
| shell | — | alert system; navigation |
| mobile | — | app shell; offline and sync; push registration |
| mobile | shell | platform conformance; runtime app baseline; ui component library |
| identity | — | account recovery; acquisition gateway; bot mitigation; data portability; email verification; federated identity; legacy password signup; magic link auth; mfa enrollment; passkey webauthn; resolution; returning user routing; security notifications; session management |
| admin | — | activity and audit log; alert dispatch; authentication; iam roles and policies; ops dashboard; platform defaults config; runtime configuration management; shadow mode; user account management |
| settings | — | appearance preferences; automation and generation defaults; budget enforcement; cross service consumption; export import reset; modal and sections; notification preferences; onboarding tour state; privacy data controls; store canonical document |
| profile | — | canonical record; document foldin; enrichment; export; inference review; manual entry; record contract; resume ingestion; versioning; you page carousel |
| onboarding | — | ftue bootstrap |
| onboarding | interview | grounded questions; session lifecycle; softprofile extraction; topic navigation |
| ai chat | — | assistant persona tone; career counsellor mode; conversational control; onboarding greeting; profile extraction; runtime and privacy; search with ai accelerator; stage aware coaching |
| search | — | aggregation and dedup; definition and zones; entry points and model; intent capture; notifications and tiers; profile driven ranking; scheduling and execution |
| opportunity | — | aging automation; capture and lifecycle; detail drawer; documents section; interviews and assignments; kanban; live and runtime; notes and tags; reminders; row actions; source and dedup display; table |
| company | — | confidence and sourcing; explorer; profile schema |
| company | intel | cache freshness refresh; enrichment async research; runtime; store canonical record |
| match fit | — | gap report; knockout disqualifiers; preferences and override; verdict transparency |
| match fit | scoring | engine; runtime |
| listing credibility | — | evidence pipeline; runtime; verdict |
| documents | — | auto and batch generation; review and edit; storage and delivery; tailored generation; templates and ats; versioning; voice controls |
| notifications | — | center; digest and throttle; multichannel delivery; preferences and subscriptions; runtime; search events and calendar |
| career companion | — | contract; debrief and unexpected; interview prep; negotiation; offer evaluation |
| career explorer | — | data and provenance; graph constellation surface; historical labor market salary; path role intelligence; profile overlay; runtime |
| analytics | — | honesty and export |
| analytics pipeline | — | metric aggregation; performance view; pivot drilldown |
| pricing | — | billing plans; entitlement enforcement; payment and runtime; rate limits; trial and free; upgrade and billing changes; upgrade prompts |
| employer | — | job posting lifecycle |
| extension | — | opportunity capture popup |
