# Authoring arc42 Section 8 — Crosscutting Concepts as a source feed

Section 8 (Crosscutting Concepts) holds the patterns and rules that apply across
many building blocks — the "how we do X everywhere" decisions. Code-generation
and review tooling reads this section as the canonical pattern set, so each
concept must be written as a present-tense rule the rest of the system follows,
not as background reading.

Write one subsection per concept. Each subsection states: the concept, the
canonical pattern, the rule code obeys, and a pointer to where it is enforced.
Below are the concepts to cover, with what "done" means for each.

## Domain model

**What to write:** the core entities, their key relationships, and the invariants
the model guarantees. A small class/ER diagram (UML class diagram — put the fence
in this references file, never in SKILL.md) plus a glossary cross-reference.

**Rule shape:** "An `Order` always has ≥1 `LineItem`; deleting the last line item
deletes the order." Invariants are stated so they can be checked.

## Persistence

**What to write:** the store(s) of record, the mapping strategy (ORM vs. hand
SQL), transaction boundaries, and the migration mechanism.

**Rules to state:**
- Every aggregate is persisted within a single transaction; no cross-aggregate
  transactions.
- Schema changes ship as forward-only, versioned migrations; no manual DDL in prod.
- Read models that may lag are explicitly marked eventually-consistent.

## Security (authentication & authorization)

**What to write:** how identity is established, how authorization decisions are
made, and how secrets are handled.

**Rules to state:**
- Every inbound request is authenticated at the gateway; services trust a signed
  identity token, never raw credentials.
- Authorization is checked at the domain-service boundary, deny-by-default.
- Secrets are read from KMS at runtime; none are committed or baked into images.
- All transport is TLS; data at rest is encrypted (tie back to a §2 constraint id).

## Error handling

**What to write:** the error taxonomy (domain errors vs. infrastructure failures),
how errors cross boundaries, and the user-facing contract.

**Rules to state:**
- Domain errors are typed and mapped to stable error codes; stack traces never
  reach the client.
- Infrastructure failures are retried with backoff only when the operation is
  idempotent (see Idempotency).
- Every error response carries a correlation id (see Observability).

## Logging & observability

**What to write:** structured logging format, the three pillars (logs, metrics,
traces), and the correlation strategy.

**Rules to state:**
- Logs are structured JSON with a `correlationId`, `service`, and `level`; no PII
  in logs.
- A `correlationId` is generated at the edge and propagated through every hop and
  every async message header.
- Each service emits RED metrics (Rate, Errors, Duration); SLO scenarios trace
  back to §10 quality scenarios.
- Distributed traces span service boundaries via W3C `traceparent`.

## Idempotency

**What to write:** which operations must be idempotent and the mechanism that
guarantees it — this is what makes safe retries possible.

**Rules to state:**
- All state-changing public endpoints accept an `Idempotency-Key`; a replayed key
  returns the original result without re-executing the side effect.
- Event consumers are idempotent: processing the same event twice has the same
  effect as once (dedup by event id or natural key).
- Idempotency keys are retained at least as long as the maximum retry window.

## Other concepts to add when relevant

Configuration management, internationalization, caching & invalidation,
concurrency/locking, rate limiting, multi-tenancy isolation, data
retention/deletion (GDPR). Add a subsection only when the concept genuinely cuts
across building blocks.

## Extraction shape rules

1. **One concept per subsection**, each with a stable id (`X-DOMAIN`, `X-PERSIST`,
   `X-SEC`, `X-ERR`, `X-OBS`, `X-IDEM`, …).
2. **Each rule is atomic, present-tense, and testable** — phrased so a reviewer or
   a generator can apply it to a single file.
3. **Cross-reference, don't duplicate.** A security rule that restates a §2
   constraint cites the constraint id rather than re-asserting it.
4. **No narrative.** State the rule, not the journey to it.

## Marking the section

```
## 8. Crosscutting Concepts
<!-- source-feed: crosscutting-concepts -->
### 8.x <Concept>  (id: X-…)
...
<!-- /source-feed -->
```

## Acceptance bar (mirrors section-templates.md)

- A subsection for each applicable concept: domain model, persistence, security,
  error handling, logging/observability, idempotency (plus any others that apply).
- Each subsection has an id and states atomic, present-tense, testable rules.
- Cross-references to §2 constraints and §10 scenarios instead of duplicating them.
- Any diagram fences live in this references file, never in SKILL.md.
- Wrapped in `source-feed: crosscutting-concepts` markers.
