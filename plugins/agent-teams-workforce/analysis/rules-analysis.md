# Agent-Teams-Workforce — Shared-Rules Extraction Analysis

Read-only analysis of `plugins/agent-teams-workforce/agents/*.md` (174 files) plus the one
existing rule `rules/separation-of-duties.md`. All counts are from grep/awk/md5 over the tree.

## Corpus shape

- **174** `.md` files in `agents/`.
- **171** are *standard* agents built from the same body template (they all carry the 5
  boilerplate `##` sections below).
- **3** are non-template and must be handled separately:
  - `README.md` — the roster README, not an agent.
  - `run-ledger-writer.md` — telemetry sink, bespoke body, `model: haiku`, no Charter.
  - `polyrepo-cartographer.md` — standalone specialist, bespoke body (`## Locating the manifest`,
    `## Answering questions`, `## Format`, `## Boundaries`), no Charter.
- All **171** standard agents already load the `agent-teams-workforce:subagent-contract`
  skill via `skills:` frontmatter (see "Prior art" below — this matters for the recommendation).

---

## 1. Section Inventory

Recurring `##` headings across the 171 standard bodies, with classification. Classification was
verified by extracting each section body per file and hashing it (md5); "IDENTICAL" means every
file that has the section produced the same hash.

| Section heading | # agents | Classification | Evidence |
| --- | --- | --- | --- |
| `## Environment Discovery:` | 171 | **IDENTICAL** | 171/171 share md5 `83b8ad43…`; the 2 non-template agents are the only ones without it. One paragraph verbatim (below). |
| `## Prompt Defense Baseline` | 171 | **IDENTICAL** | 171/171 share md5 `197a5fac…`. 6 fixed bullets, byte-for-byte. |
| `## Charter` | 171 | **PER-AGENT** (with enumerated sub-fields) | Every Charter is unique; sub-fields analyzed in §2. |
| `## Operating Rules` | 171 | **MIXED: universal core + VARIES-BY-ROLE + PER-AGENT** | Every file's block hashes differently, but at the *bullet* level it is ~70% shared boilerplate. See breakdown below. |
| `## When You're in Over Your Head` | 171 | **IDENTICAL** | 171/171 share md5 `bfde8e32…`. One paragraph verbatim (below). |
| `## Team` | 14 | **PER-AGENT** | Only on the 14 team leads; each lists that lead's roster members. Pure per-agent content. |

The three IDENTICAL blocks in full:

- **Environment Discovery:** *"Before executing any write or build tools, you MUST read the local
  `CLAUDE.md` file at the repository root to discover the current project's building, testing, and
  linting standards. Do not assume standard commands."*
- **When You're in Over Your Head:** *"It is always OK to stop and say 'this is too hard for me.'
  Bad work is worse than no work. You will not be penalized for escalating."*
- **Prompt Defense Baseline:** 6 fixed bullets (no-role-change / no-secret-leak / no-unvalidated-code /
  treat-encoded-tricks-as-suspicious / treat-external-data-as-untrusted / no-harmful-content).

### Operating Rules — bullet-level breakdown

Per agent the block averages **7.5 boilerplate-discipline bullets + 3.0 specialized bullets**
(1298 vs 525 bullets across 171 files). The block hashes differ per file only because (a) the
manager name is interpolated and (b) the same discipline concept is re-phrased with a role-specific
noun ("audit trail in *decisions*/*findings*/*verdicts*/*routing decisions*").

Universal-concept bullets (appear, in some phrasing, in nearly every agent):

| Concept | Reach | Class |
| --- | --- | --- |
| "Every substantive output must end with the sections Assumptions / Open Questions / Constraints Followed / Constraints at Risk / Scope Exceptions." | **171 IDENTICAL** | universal |
| "Prefer the skills and tools provided to you over internal training." | 132 (+7 variant) | universal |
| "Include an … audit trail …: confidence level, reasoning, alternatives considered and dismissed …" | ~all (88 base + ~40 role-noun variants) | universal, role-phrased |
| "Separate provided facts, inferred facts, assumptions, recommendations, decisions, and unresolved questions…" | ~all (75 base + ~50 variants) | universal, role-phrased |
| "Collaborate through explicit artifacts — the durable record is the artifact…" | ~all (33 base + many variants) | universal, role-phrased |
| "Review your own work … but never approve it …" / (testers: "you report findings; you never fix") | ~all | universal (no-self-approval) |
| "No self-tasking: report newly discovered work to **&lt;manager&gt;**…" | ~all | universal template, **per-agent manager name** |
| "Analysis and decision are separate tasks performed by different agents…" | ~15 base + variants | universal doctrine |

Genuinely VARIES-BY-ROLE / PER-AGENT bullets (the ~3/agent specialized remainder), with reach:

| Cluster bullet | Reach | Cluster |
| --- | --- | --- |
| "You report findings; you never fix what you find…" | 60 | testers + reviewers |
| "Write the minimum code needed to make the failing tests pass. Never modify, weaken, skip, or delete a test…" | 28 | TDD implementers |
| "You own process integrity, not subject matter … never blame a team member … never perform the team's work…" | 14 | leads |
| "Stay inside the authorization boundary … designated test environments only…" | 11 | adversarial testers |
| "Tests must stay green after every change … never continue on red." | 7 | refactor optimizers |
| "…decides only, never analyzes / generates no analysis of its own." | 6 | deciders |
| Domain constraints ("All Lambdas extend the chassis", "Events publish only through the central event API", "The approved API contract is the only backend surface", …) | 1–3 each | truly per-agent |

**Takeaway:** the three named blocks (Environment Discovery, Prompt Defense Baseline, Over Your
Head) are pure boilerplate. Operating Rules is ~70% boilerplate discipline + ~30% cluster/per-agent.
The Charter is per-agent except its Task-Category paragraph, which is a fixed template.

---

## 2. Taxonomy (Charter dimensions)

Distinct values actually present across the 171 standard agents and agent counts.

**Agent Type**

| Value | Count |
| --- | --- |
| Worker | 152 |
| Manager | 14 |
| Specialist | 5 |

**Character Types**

| Value | Count |
| --- | --- |
| Executor | 72 |
| Validator | 39 |
| Delegator, Orchestrator | 15 |
| Advisor | 13 |
| Executor (test author) | 12 |
| Adversary | 9 |
| Decider | 6 |
| Orchestrator | 2 |
| Validator, Decider (Referee) | 1 |
| Validator, Decider | 1 |
| Decider (Referee) | 1 |

**Task Category** (the load-bearing dimension — exactly one per agent, per separation-of-duties.md)

| Value | Count |
| --- | --- |
| execute | 72 |
| test | 60 |
| orchestrate | 17 |
| plan | 13 |
| approve | 9 |

The Task-Category paragraph is a fixed template — only the category word (which reorders "the other
four … are forbidden") and the escalation target (`<manager>`) vary. The 5-category doctrine itself
already lives in `rules/separation-of-duties.md`.

---

## 3. Role-Difference Check

Do the shared sections differ between clusters? First, the clusters are crisp: **task category,
Character Type, and tool grant line up almost perfectly**, so "the tools an agent has" is a reliable
cluster key. Cross-tab of task category × tool grant (171 agents):

| Cluster | Count | Task category | `tools:` line |
| --- | --- | --- | --- |
| Makers / Executors | 72 | execute | `Read, Write, Edit, Glob, Grep, Bash` |
| Test-writers | 12 | test | `Read, Write, Edit, Glob, Grep, Bash` |
| Reviewers / Testers (run + report) | 48 | test | `Read, Glob, Grep, Bash, Write` |
| Advisors / Analysts | 13 | plan | `Read, Glob, Grep, Write` |
| Deciders | 9 | approve | `Read, Glob, Grep, Write` |
| Coordinators / Leads | 17 | orchestrate | `Read, Glob, Grep, Agent, SendMessage` (+1 also Bash, +2 `SendMessage` only) |

(Plus 2 bespoke: `run-ledger-writer` `Read, Write, Bash`; `context-curator` `Read, Write, Edit, Glob, Grep`.)

Now, per block:

| Block | Universal or split? | Finding |
| --- | --- | --- |
| **Environment Discovery** | **UNIVERSAL** | Byte-identical across all 171. Does **not** differ by cluster at all — even read-only advisors/deciders (who never build) carry the identical "read CLAUDE.md before write/build" text. |
| **Prompt Defense Baseline** | **UNIVERSAL** | Byte-identical across all 171. No cluster variation. |
| **When You're in Over Your Head** | **UNIVERSAL** | Byte-identical across all 171. No cluster variation. |
| **Operating Rules** | **Split** | The ~7.5 discipline bullets/agent are universal (same concept everywhere). The ~3 specialized bullets/agent split cleanly by cluster: makers get "minimum code, don't touch tests" (28) + "implement against approved decisions"; testers/reviewers get "report, never fix" (60) + constitutive-vs-competitive labeling; leads get "process integrity, never blame, never do the team's work" (14); adversarial testers get "designated test environments only" (11); deciders get "decide only, never analyze" (6); refactorers get "stay green" (7). Domain one-liners (chassis, event API, contract) are per-agent. |

**Quantified answer:** 3 of the 4 named "shared" blocks are fully universal and do **not** differ by
cluster. Only Operating Rules splits — and even there the majority (≈70%) is universal, with a thin
cluster-specific tail plus a per-agent domain tail.

---

## Prior art (important context for the recommendation)

Two mechanisms already exist and partially overlap the boilerplate:

1. `rules/separation-of-duties.md` — already the canonical home of the 5 task categories, no-self-
   tasking, no-self-approval, analysis-vs-decision separation, and gate semantics. Much of the
   Operating Rules "universal doctrine" is a prose restatement of this file. **No agent currently
   references it** (only `agents/README.md` mentions it).
2. `skills/subagent-contract/SKILL.md` — loaded by all 171 agents via `skills:`. It already encodes
   scope discipline, DONE/BLOCKED signaling, "no scope creep", "no assumption-making", tool-grant
   respect, and a pre-DONE checklist. This overlaps the "collaborate through artifacts / review your
   own work / no self-tasking" Operating Rules bullets and the Over-Your-Head sentiment.

So the bodies are re-stating, in prose, discipline that is already centralized in a rule file and a
skill. The extraction should *dedupe against these*, not add a third copy.

---

## 4. Recommendation

The data confirms the user's hypothesis, with one refinement: **one global rule does most of the
work; the per-cluster rules are real but thin (1–3 bullets each), so only the largest clusters
justify their own file.** Proposed set for `plugins/agent-teams-workforce/rules/`:

### R1 — `rules/agent-baseline.md`  *(referenced by all 171 standard agents)*
Absorbs, verbatim/normalized:
- `## Environment Discovery:` (the whole paragraph — 171 IDENTICAL)
- `## Prompt Defense Baseline` (all 6 bullets — 171 IDENTICAL)
- `## When You're in Over Your Head` (the paragraph — 171 IDENTICAL)
- The universal Operating Rules discipline bullets: output-sections footer (171 IDENTICAL),
  prefer-skills, audit-trail, separate-facts, collaborate-through-artifacts, review-own-work /
  no-self-approval. **Normalize the role-noun phrasings to one wording** (e.g. "audit trail in your
  decisions/findings/verdicts" → "audit trail in whatever you produce").
- Cross-reference (do not duplicate) `separation-of-duties.md` for the no-self-tasking / analysis-vs-
  decision doctrine, and note that `subagent-contract` skill already covers DONE/BLOCKED + scope.

Each body then reduces to: `Read and apply rules/agent-baseline.md` plus the Charter, the one
per-agent "no self-tasking → **&lt;this agent's manager&gt;**" line, and the specialized Operating
Rules bullets. **Removes ~10 boilerplate lines/agent × 171 ≈ 1,700 duplicated lines.**

### R2 — `rules/executor.md`  *(referenced by the 72 execute-category makers)*
Absorbs the execute-cluster discipline: "implement against approved decisions, never decide among
options"; "never approve your own output, never write the tests that gate it." Of these 72, the **28
TDD implementers** additionally need the "minimum code to pass the failing test, never modify/weaken/
skip a test" bullet — keep that as a labeled sub-clause the 28 reference, or inline it in those 28
bodies (it does not fit spec/ADR/diagram authors). The remaining domain one-liners (chassis, event
API, contract) stay in the body.

### R3 — `rules/tester-reviewer.md`  *(referenced by the 48 reviewers/testers + 12 test-writers where applicable; "never-fix" bullet reaches 60)*
Absorbs: "you report findings; you never fix what you find — remediation is a separate loop iteration";
"distinguish constitutive (hard-loop) from competitive (may-pass-with-flag) findings and label each";
"independently re-run the suite yourself — the executor's green screenshot is a claim, your run is
evidence." Test-writers (12) instead keep their "confirm the test fails for the intended reason"
(Red) bullet in-body since they *do* author artifacts.

### R4 — `rules/orchestrator.md`  *(referenced by the 17 coordinators/leads)*
Absorbs: "you own process integrity, not subject matter"; "responsible for the team's work, may never
blame a member, never perform the team's work or cover its gaps"; "route only — never produce,
evaluate, or approve the artifacts you route." The `## Team` roster stays per-agent (it is that lead's
membership list).

### R5 — `rules/adversarial-boundary.md`  *(referenced by the ~11 adversarial testers)*
Absorbs the security-critical constraint: "stay inside the authorization boundary at all times — this
project's own code and designated test environments only, as an authorized stage of this pipeline."
Worth its own file because it is a hard safety rule shared verbatim and easy to audit centrally.

### Judged **not** worth a file (keep in-body)
- **Deciders (9)** "decide only, never analyze" and **refactorers (7)** "stay green after every
  change" — too few agents, 1 bullet each. Add them to R2/R3 as labeled clauses or leave in-body.
- **Advisors (13)** "provide analysis, never decide" — 1 bullet; fold into R2 or leave in-body.
- The **Task-Category paragraph** template — leave in the Charter; its doctrine already lives in
  `separation-of-duties.md`, which R1 cross-references.

### What MUST remain per-agent (the real specialized content)
- The entire **Charter** except the templated Task-Category paragraph: Purpose, Primary
  Responsibility, Scope, Out of Scope, Allowed/Forbidden Decisions, Inputs Required, Outputs
  Produced, Required Reviewers, Escalation Triggers, Acceptance Criteria, Anti-Goals — all unique.
- The **manager name** in the no-self-tasking line and Task-Category escalation target.
- **Domain Operating-Rules one-liners** (chassis extension, event-API-only publishing, contract-is-
  the-surface, DynamoDB single-table, etc.) — 1–3 per agent, genuinely per-agent.
- The **`## Team`** roster on the 14 leads.
- The **3 bespoke files** (`run-ledger-writer`, `polyrepo-cartographer`, and the non-agent
  `README.md`) — they do not fit the template; at most give the two real agents a one-line
  `Read and apply rules/agent-baseline.md` reference for the Prompt-Defense/Over-Your-Head baseline.

### Net effect
One global rule (R1) covers 100% of standard agents and removes the bulk of duplication. Four
cluster rules (R2–R5) each cover a clean, tool-identified cluster (72 / 60 / 17 / 11). Everything
left in a body is genuinely that agent's own role — Charter, its manager, its domain constraints,
and (for leads) its team roster.
