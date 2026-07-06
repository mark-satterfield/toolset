<!-- residue-lint:ignore-file (this is a shape reference; its field names quote the format) -->

# Decision-log entry shape

The `record_decision.py` script renders every entry in this shape and maintains the
file. This reference exists so you can see the target an entry lands in — it is
not something you write by hand. The script owns the identifiers, dates, and the
`Supersedes` / `Superseded By` back-pointers; you supply the field content.

## The file

```
# Decision Log

<!-- Newest entries on top. Append-only: never edit or delete a past
     decision. When one changes, add a new entry and mark the old one Superseded. -->

---

### D-001 · 2026-06-04 · [Decision Title]
- **Status:** Active            <!-- Active | Superseded | Retired -->
- **Decision:** [What was decided — one clear sentence]
- **Made By:** [Name] · [Role]
- **Context:** [Why this decision was needed — 2-3 sentences]
- **Options Considered:**
  - [Chosen option] — chosen
  - [Option B] — [one-line reason it lost]
  - [Option C] — [one-line reason it lost]
- **Why Chosen:** [Rationale behind the final choice]
- **Consequences:** [Expected trade-offs]
- **Revisit Conditions:** [Specific trigger, e.g. "if monthly users exceed 10,000"]
- **Supersedes:** [D-id · date · title, or —]
- **Superseded By:** [D-id · date · title, or —]
- (optional) **Impacted Repositories:**
  - [Repository Name](https://github.com/{org}/{repository})
  - [Directory Name](/path/to/directory/)
```

## The JSON you feed the script

```json
{
  "title": "Use DynamoDB for the event store",
  "decision": "The event store uses DynamoDB.",
  "made_by": "Mark · Architect",
  "context": "We must persist events before launch and cannot run a second stateful service on the team we have.",
  "options": [
    {"option": "DynamoDB"},
    {"option": "Redis", "reason": "added a second datastore to keep in sync"}
  ],
  "chosen": 0,
  "why_chosen": "DynamoDB carries the lowest operational cost — no instance to run, patch, or scale by hand.",
  "consequences": "Cross-entity queries now need pre-designed access patterns; ad-hoc SQL is gone.",
  "revisit_conditions": "If access patterns need more than three GSIs on a single table.",
  "supersedes": "D-003",
  "impacted_repositories": [
    {"name": "event-store", "target": "https://github.com/org/event-store"}
  ]
}
```

Required: `title`, `decision`, `context`, `why_chosen`, `consequences`,
`revisit_conditions`, and a non-empty `options` with exactly one winner (either a
`chosen` index or one option object carrying `"chosen": true`). Every losing
option needs a `reason`. Optional: `made_by` (left blank when unknown — never
guessed), `supersedes` (a bare D-id), `impacted_repositories`.
