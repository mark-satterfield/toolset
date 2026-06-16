# Authoring arc42 Section 4 — Solution Strategy as a source feed

Section 4 (Solution Strategy) is the architectural keystone: it records the
**fundamental decisions** — the few choices that, if reversed, would force a
rewrite. Downstream tooling reads it two ways: the decision rows seed the ADR
index (§9) and the technology rows seed a tech-radar feed. Write it so both
extractions are clean.

arc42 keeps section 4 deliberately short. It is a summary of the most important
solution ideas, not a design dump. Detail belongs in §5 (structure), §8
(concepts), and the ADRs. Aim for one page.

## The three things section 4 must state

### 1. Technology decisions

The stack-level choices: languages, frameworks, primary data stores, integration
style (sync REST vs. async events vs. RPC), deployment platform.

| Id | Decision | Chosen | Over (alternatives) | ADR |
|----|----------|--------|---------------------|-----|
| D-01 | Backend language | Kotlin on JVM 21 | Java, Go | ADR-0003 |
| D-02 | Primary store | PostgreSQL 16 | DynamoDB, MongoDB | ADR-0004 |
| D-03 | Service integration | Async events (Kafka) | Sync REST | ADR-0007 |

Each row that records a significant, hard-to-reverse choice references an **ADR
id that must exist in §9**. That cross-reference is the contract: §4 names the
decision, §9 indexes it, the ADR tooling holds the full record.

### 2. Top-level decomposition approach

State the organizing principle for §5's building blocks in one or two sentences:
layered, hexagonal / ports-and-adapters, modular monolith, microservices,
event-driven, etc. — and the single reason it was chosen. This is the seed §5
elaborates; do not draw the blocks here.

### 3. How each quality goal is achieved

This is the heart of section 4 and the part most often skipped. For **every**
quality goal listed in §1, state the architectural approach that delivers it.

| Quality goal (from §1) | Strategic approach |
|------------------------|--------------------|
| Availability (99.9%) | Stateless API, 3+ replicas, multi-AZ managed DB, health-checked rolling deploys |
| Modifiability | Hexagonal architecture isolates domain from adapters; new channels added as adapters |
| Security | Zero-trust: all calls authenticated at the gateway; secrets in KMS; least-privilege IAM |
| Time-to-market | Managed services over self-hosted; one deployable unit for the MVP |

No quality goal may be left without a row. If the approach is not yet decided,
the row's approach cell is an explicit `> TODO:` — visible, never silent.

## Extraction shape rules

1. **Decisions are atomic and IDed** (`D-<seq>`), ids stable across edits.
2. **Significant decisions carry an ADR id** that resolves in §9. Trivial choices
   do not need an ADR but still get a `D-` row.
3. **The quality-goal table is exhaustive** against §1 — this is what lets tooling
   verify goal coverage.
4. **Present tense, no narrative history.** Record the standing decision, not the
   debate that produced it (that lives in the ADR).

## Marking the section

```
## 4. Solution Strategy
<!-- source-feed: solution-strategy -->
... technology table, decomposition statement, quality-goal table ...
<!-- /source-feed -->
```

## Acceptance bar (mirrors section-templates.md)

- Technology decisions table present; each significant row references a §9 ADR id.
- Decomposition approach stated in ≤2 sentences with its driving reason.
- Quality-goal coverage table is exhaustive against §1 (every goal has a row).
- Section stays roughly one page — overflow detail is pushed to §5 / §8 / ADRs.
- Wrapped in `source-feed: solution-strategy` markers.
