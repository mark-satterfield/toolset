# Section 8 — crosscutting concepts

Section 8 describes the patterns used across many services: one file per concept,
`arc42/08-crosscutting-concepts/<concept>.md`, named for the concept, with the section `README.md`
listing them. Each concept is a view at `scope: concept`: its structure and its behaviour, as
diagrams and prose.

An established pattern is followed by the next design unless that design states a reason and evidence
to change it, and then the architecture changes. A concept is not a rule and is not enforced; it is
the description of how the system does something everywhere it does it.

## What a concept file holds

- **What the concept is and where it applies** — the problem it solves and the services or elements
  that use it, listed in `shows`.
- **Its structure** — a class, component or package diagram of the parts involved (an event envelope
  and its fields, the layers of a handler, the components that carry identity).
- **Its behaviour** — a sequence or activity diagram of how it works at runtime (a retried event
  delivery, a token check, an idempotent write).
- **The prose a reader needs** — the reasons, the limits, what the diagrams cannot show, and links to
  the service views that apply it.

## Concepts to consider

Domain model, persistence, identity and authorisation, error handling, logging and observability,
idempotency, event contracts, configuration, caching, concurrency, data retention. Write a concept
when the pattern is used across services; a pattern used by one service belongs in that service's
views in sections 5 and 6.

## How a concept is written

1. **Describe, do not command.** "Event consumers deduplicate by event id and store the id for the
   retry window" describes the design. "Consumers MUST deduplicate" is a rule and does not belong.
2. **Show it.** Choose the structural and behavioural views the MODEL makes applicable, using the
   MENU to construct them. A declared diagram has actual diagram content; any prose-only model
   exception follows the MODEL and is justified in the caller's assessment.
3. **Link rather than repeat.** A concept refers to a constraint in section 2 or a service view by
   link, without restating it.
4. **No tags or ids.** The catalog frontmatter (`subject`, `shows`) is how a phase finds the concept.
5. **No history.** The concept as it is now, not the path to it.
