---
name: log-architecture-review
description: >-
  The review log of one Epic's architecture: the proof that each AWS resource the design defines
  was reviewed with the AWS tools, MCP servers, skills and specialists, that best practices and
  security best practices were followed, that the design had a Well-Architected review, and that
  every decision between two or more options states the options considered and the reason for the
  choice. Holds the log's schema and the command that writes and checks it. Use while designing an
  Epic's architecture, whenever a resource is reviewed, a choice between options is made or the
  Well-Architected review is done.
allowed-tools: [Bash, Read]
---

# Log the architecture review

No architecture decision is made by instinct. The solutions architect reviews and approves its
own architecture against the criteria of `effective-architecture/review-standard.md` (P10 among
them), and the review log is the record of that review. It is written beside the result, at the
architecture context's `reviewLogPath`, while the work goes: an entry when a resource has been
reviewed, an entry when a choice is made, the Well-Architected review when the design is settled.

## The contract

`schemas/review-log.schema.json` is the log's one contract. It holds:

| Member | What it records |
|---|---|
| `resources` | One entry per AWS resource the design adds or changes (each entry of the result's `addedOrChangedElements` whose matrix entry has a `resourceType`): `reviewedWith`, each MCP tool (by its full tool name), skill (plugin-qualified) and specialist agent that reviewed it, what it was asked and what it returned; `bestPractices` and `securityPractices`, each practice with where it is stated and how the design follows it |
| `wellArchitected` | The Well-Architected review of the design: what carried it out (for example the `aws-core:aws-well-architected-review` skill), and one assessment per pillar, each of the six once, with its risks and actions. Null only when the design defines no AWS resource |
| `decisions` | Every decision between two or more options: the question, the entries it concerns, each option with its tradeoffs, the option chosen, the reason it was chosen over each other option, and the evidence the reason rests on |

## Writing it

Each command prints one JSON document; an entry is given inline or as `@<file>`, and is checked
against its definition before it is written. A rejected entry changes nothing.

```bash
LOG="python3 ${CLAUDE_PLUGIN_ROOT}/skills/log-architecture-review/scripts/review_log.py"
$LOG init --log <reviewLogPath> --bead <epic id>
$LOG resource --log <reviewLogPath> --entry @<resource review file>
$LOG decision --log <reviewLogPath> --entry @<decision file>
$LOG well-architected --log <reviewLogPath> --entry @<review file>
$LOG check --log <reviewLogPath> --bead <epic id> --resource <matrix id>=<resourceType> ...
```

`resource` replaces the entry with the same `element`, `decision` the one with the same `id`;
`decision` refuses a choice that is not one of its options. `check` reports every problem the
check step of the pipeline will report; run it, with every AWS resource the design adds or
changes, before you write your result.

## How it is used

- The check step of the architecture part runs the same check on the finished log, with the AWS
  resources taken from the matrix, and sends every problem back to the architect for correction:
  a missing or malformed log, a decision without two options, its choice or its reason, an AWS
  resource with no entry, and a design with an AWS resource and no Well-Architected review.
- The promotion step commits the log in the vault with the Epic's architecture and links it from
  the Epic's matrix entry (`reviewLog`).
- A specialist that reviewed a resource is recorded as an `agent` entry naming the specialist,
  with its answer file among the entry's `sources`; the answer's `reasons` cite what the
  specialist's tools and skills returned.
