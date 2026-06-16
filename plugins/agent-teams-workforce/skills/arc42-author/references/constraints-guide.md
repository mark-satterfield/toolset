# Authoring arc42 Section 2 — Constraints as an extractable source feed

Section 2 (Constraints) is not just prose for humans. Downstream drift-detection
and compliance tooling reads it as a list of **rules to enforce against the
codebase and the running system**. So it must be written to be machine-parsable,
not just readable. This guide pins the shape.

## What a constraint is (and is not)

A constraint is a boundary that is **given to** the architecture, not chosen by
it. It limits the solution space.

- Constraint (goes in §2): "Backend must run on the JVM (corporate platform standard)."
- Decision (goes in §4, not §2): "We chose Kotlin over Java for null-safety."

If the team could have decided otherwise within the project, it is a decision,
not a constraint. Keep the two apart so the §4 feed and the §2 feed stay clean.

## The three required groups

arc42 splits constraints into three groups; author all three, even if a group is
short. Mark an empty group with an explicit `> TODO:` — never drop it.

1. **Technical constraints** — fixed technology, platform, protocol, library,
   hardware, or interface requirements.
2. **Organizational & political constraints** — team, process, schedule, budget,
   org-structure, and standards-compliance limits.
3. **Conventions** — coding standards, naming conventions, documentation rules,
   language/locale rules — anything mandated for consistency.

## Extraction shape — every constraint is one atomic, IDed, testable rule

Write each constraint as one row with a stable id. The id is what downstream
tooling keys on, so ids never get reused or renumbered.

| Id | Group | Constraint (present-tense, testable) | Source / rationale |
|----|-------|--------------------------------------|--------------------|
| C-T-01 | Technical | All services run on the JVM (Java 21 LTS). | Corporate platform standard |
| C-T-02 | Technical | All data at rest is encrypted with AES-256 via the platform KMS. | InfoSec policy SEC-114 |
| C-T-03 | Technical | External calls go through the corporate API gateway; no direct egress. | Network policy |
| C-O-01 | Organizational | A production release requires two-person change approval. | SOC 2 CC8.1 |
| C-O-02 | Organizational | The MVP must ship by end of Q3. | Board commitment |
| C-C-01 | Convention | Public APIs follow the company REST style guide v3. | API guild standard |

Id scheme: `C-<group letter>-<2-digit seq>` (T = technical, O = organizational,
C = convention). Stable forever once assigned.

## Rules for writing each constraint so it is extractable

1. **One rule per row.** Split compound statements ("X and Y") into two rows.
2. **Present tense, declarative, testable.** Phrase it as a state of the world a
   checker could verify, not an aspiration. "Should aim to be secure" is not a
   constraint; "Secrets are never committed to git" is.
3. **No solution leakage.** State the limit, not how you satisfy it. The "how"
   belongs in §4 / §8.
4. **Quantify where the constraint is quantitative.** "Low cost" → "Monthly cloud
   spend ≤ $5k."
5. **Cite the source.** Every constraint traces to a policy, a standard, a person,
   or a contract. An unsourced constraint is suspect and should be queried.

## Marking the section

Wrap the section so extraction tooling can locate it deterministically:

```
## 2. Constraints
<!-- source-feed: constraints -->
... constraint tables ...
<!-- /source-feed -->
```

## Acceptance bar (mirrors section-templates.md)

- All three groups present (or an explicit `> TODO:` for an empty one).
- Every constraint is one atomic, IDed, present-tense, testable row with a source.
- No decisions masquerading as constraints.
- Section is wrapped in the `source-feed: constraints` markers.
