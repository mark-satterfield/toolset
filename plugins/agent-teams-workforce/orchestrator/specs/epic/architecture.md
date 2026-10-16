# Architecture: the steps of the Architecture container

Code: `orchestrator/flows/prd_to_spec.py` (the open-run step), `architecture.py`,
`architecture_check.py`, `architecture_review.py`, `architecture_promotion.py`,
`architecture_earlier.py`, `architecture_files.py` (names, the context file and readers).

One agent, `aws-solutions-architect`, is responsible for the solution: it decides the architecture
a PRD needs, starting from the effective architecture (the effective arc42 before this Epic runs, which
is approved as of now and never complete), until it is ready for review. The matrix is its map and
never shows that the architecture is complete, correct or good. Every conclusion it reaches,
`no-change-needed` included, goes through the check and the review. The script starts sessions, records steps and carries results. It decides nothing
about who the architect asks, in what order or how often. Every step is one step of the Epic's
journal, and the journal alone decides where a run begins. The script names agents by the `role`
their definitions state (`solutions-architect`, `design-specialist`, `diagram-author`,
`trd-author`, `document-maintainer`, `repository-steward`, `architecture-reviewer`,
`architecture-lead`, `decider`), never by name.

`<arch-work>` is `<work>/architecture/`.

## Open the run

Script `prd_to_spec.open_run`, the first outermost step. It fails when beads does not hold the
bead as an Epic. In one matrix change it brings the Epic's entry with its requirements
(`sync-epics --bead`) and the document entries (`sync-documents`) up to date. It writes the context file `<arch-work>/context.json`, which
names every path of the Epic's architecture work: the PRD, the architecture root, the
architect's state and result files, the TRD, and the folder for requests to helpers;
with the vault commit the document entries are synced to and the name of the matrix command. It
records the file `prd`, the value `matrix epic entry` and the file `context`, and plans, under the
Architecture container, the architect's step and the check that follows it. Those two plans are
also registered as what the lane plans under the container, so a check step planned under an
earlier key is replanned to the current key when the run opens the journal, even while the
architect's step is still pending and the open-run step plans nothing new.

Every later step of the container is handed the context file through the journal and derives no
path of its own.

## The architect and the agents it starts

Agent `aws-solutions-architect`, step "Decide what the architecture should be for this PRD".
Its brief (`agent-brief.schema.json`) names exactly the files its definition names: `prd`,
`context`, `state` (its state file), and, in a later step, the
`findings` (reviews and check results), `answer` and `ruling` files that step is handed. No file
is written from the matrix for it: the architect reads the Epic live, with
`atw-matrix epic <id>`, `atw-matrix epic <id> --realizers` and `atw-matrix epic <id> --constraints`
(what each returns is defined in `blueprint/design/matrix.md`, queries Q2 and Q4, Q26 and Q5), and runs
`atw-matrix impact --id <id>` itself for an entry it means to change. The session is granted the
work folder and no folder of the architecture or of the PRDs. The architect records its own entries and links in the matrix (`atw-matrix put`, `link`)
before it writes its result.
Its output is the architecture result at the path the context file names. The session's output
check validates the result against its schema, then runs `repo_scoping.story_build_problems` on the
result's `addedOrChangedElements` (what the Epic's Stories build): an id the matrix lacks, an entry
not on the architecture side, an event with no description, an entry built in no stack (for an
event, one none of whose producers is homed in a stack);
then it records the design in an in-memory copy of the matrix, which is never written, and compares
it with what `atw-matrix epic` returns from that copy: an entry the result names that the matrix does
not hold, a requirement the copy does not show as served by the feature the result names, a
requirement neither served by a feature nor listed under the result's `noFeature`. Each problem is
one sentence of the error the check raises, and goes to the architect as its correction (the
session's one corrective resume). The step that accepts the result then makes the write: it records
in the matrix what the result states of the Epic's features (`servedBy`, `realizedBy`,
`supportedBy`, and `covers` from each document heading that describes a feature), and fails only
when the matrix written does not hold it. It records the file `architecture result` and the values
`conclusion` and `requirements with no feature`.

The same launch builder serves every step the architect performs: the first, its "Finish", a
correction after the mechanical check or after findings, and a competing design the lead plans.
The architect writes its result as the work goes (`architecture-result.schema.json`), and every
step keeps a result already at the result path, so a session that starts again continues from
the partial result. A step after the first updates the result file in place and continues the
architect's session: the "Finish" step continues the session of the step above it, and any other
later step continues the nearest earlier session the agent holds in the journal.

The architect starts the agents a gap in the PRD needs inside its own session: design specialists,
diagram authors, the repository steward, the TRD author and the document maintainer. It records
each as a child step of its own step with `atw-step-journal`, with the request file it wrote, and
adds a last child step "Finish", by the protocol in `helper-steps.schema.json`. When its session
ends, the runner reads the journal again:

- every child step is done: the runner closes the architect's step;
- a helper was left running: the runner launches that agent as its own session from the request
  file the step holds, and records the request and what the agent wrote;
- "Finish" is not done: the runner launches the architect again, continuing its session.

| Helper left running | Request artifact | Output | Records |
|---|---|---|---|
| a design specialist, a diagram author, the repository steward | `request` or `question` | the answer path the request names | the request, file `answer`; for the repository steward, which records each stack and each `homeIn` itself, also the value `entries with no stack` (what `atw-matrix epic <id> --unlinked` still lists under `noStack`; an event has no home and is never in it) |
| `trd-author` | `request` | the answer path the request names; the TRD at the path the request names is kept and updated in place | the request, file `TRD`, file `answer`, value `obligations with no source`, value `constraints recorded`. The step records one `constraint` for each requirement the answer lists under `requirements` (every requirement that write added or changed), as a pointer `trd` (the Epic and the requirement id, a heading of the TRD) with no copy of its text, with `statedIn` and `appliesTo`, removes the constraint of each id the answer lists under `removed`, and records one with no `statedIn` for each `noSource` obligation; it fails when the matrix refuses one |
| `architecture-maintainer` | `write request` or `request` | the result path the request names | the request, file `what was written`, value `documents synced`. The session is granted the architecture root, where it writes; the step sets each document written that exists `in-review` in its front matter (`matrixsync.set_lifecycle`), so the check, the review and the promotion of this run reach it, then runs `sync-documents --paths` on the documents written |

The TRD is drafted early by `trd-author` at the architect's request and updated in place.

## Earlier work on this PRD

A journal that `orchestrator/port_journal.py` builds for an Epic with saved run data holds, under
the Architecture container, a step "Earlier work on this PRD" (`architecture_earlier.carry`). It
contains one done step per piece of that work, each holding its files as artifacts named
`earlier work: <what the file is>`, so the journal records what was done. The architect's step is
planned after it and is not handed those files: they are unapproved copies and summaries from a
pipeline that no longer runs, and the matrix and the arc42 documents are the architect's sources.
Such a step has the script `architecture.earlier_work`, which records nothing when it runs: it runs only
after the owner asks for a start at or before it.

## The check

Script `atw-matrix check; atw-matrix review-scope`. It follows the architect's first step, each
correction of a mechanical defect, and the lead's step for a matter the architect could not
settle. It records nothing in the matrix. It checks what code can check: the matrix file, the
Epic's entry, and an answer in the architect's result for every architecture and
technical-requirement criterion. It writes `<arch-work>/checks/<step id>/check.json` (the folder is the check step's own, so a
later check never overwrites an earlier one) and records it as the file `check result`. It then plans what follows by
rule over the matrix, the criteria file and the architect's result:

| What the check finds | What it plans |
|---|---|
| a mechanical defect | a correction step for the architect, handed the check result, and a new check; after 3 corrections a defect fails the step |
| no defect, the result's conclusion is `unsettled`, and no lead has run in the container | the step of `architecture-team-lead` and a new check |
| otherwise, whatever the conclusion | one step for each reviewer the criteria file selects, and the promotion step after them |

A result whose conclusion is `no-change-needed` is reviewed like any other: the reviewers are
handed, besides what is in review, the effective documents and headings the result's criteria
answers cite as meeting the Epic, and the headings kind counts as present, so the reviewers of
headings are selected. Those documents go into each reviewer's narrowed scope only, not into
`review-scope.json`, so the promotion does not touch them.

With no defect it reads what is in review for the Epic, the documents the Epic reaches that are
not effective with the headings reached (`atw-matrix review-scope --epic`), and
writes `review-scope.json` (file `review scope`) and `unlinked.json` (file
`links with nothing recorded at the other end`, from `atw-matrix epic <id> --unlinked`). The
reviewers are selected by the
`appliesWhen` rule of each reviewer group in the criteria file: the kinds of content in review
(a heading, a scenario fact, which is a document in review of arc42 section 6, a TRD requirement;
the TRD of an elaboration always counts) and the
review signals the architect's result lists. Each selected reviewer gets its own narrowed scope,
`review-scope.<reviewer>.json` (to `reviewer-scope.schema.json`), each in the check step's own
`<arch-work>/checks/<step id>/` folder. The step records the value
`reviewers selected by rule`. A rule that selects no reviewer fails the step.

It judges nothing.

## Review

Each reviewer is handed only the documents in review its criteria apply to, in its scope file
(its contract is `reviewer-scope.schema.json`). Its brief names `review scope` (its own
narrowed scope, to `reviewer-scope.schema.json`), `architecture result`, `prd` when the scope
names the PRD, and `trd` when its
group covers the TRD's requirements. The reviewers' steps are consecutive agent steps whose inputs
are done, so their sessions run together. Each writes `<arch-work>/reviews/<reviewer>.json` and
records it as the file `review`, with the value `findings`, the number of findings it kept. A finding about an item outside the
reviewer's scope is taken out of the review file and counted (value
`findings outside the scope`); the review as returned is kept beside it as `.as-returned.json`.

The first review that returns a finding, or asks for alternatives, plans one step for
`architecture-team-lead` after the last reviewer and before the promotion step. The lead is handed
the reviews that raised something as `findings` and the `architecture result`; it reads the
design specialists from the agent definitions whose role is design-specialist. It writes its routing
(`<arch-work>/routing-<step>.json`) and adds the steps its routing calls for under its own step,
with a last child step "Finish": a correction by the architect with a re-check by the reviewer
that raised the finding, a specialist's opinion, a competing design, or a ruling. A re-check is a
step of the reviewer that continues the reviewer's session with the same narrowed scope. A routing
that rejects every item adds no step. When nothing remains, the lead records the value
`every item is resolved`.

`architecture-decider` rules only where the lead sends a matter to it. It is handed one question
file and writes one ruling (`<arch-work>/ruling-<step>.json`, file `ruling`, value `stands`), and
settles each disagreement the question's evidence cites with `atw-matrix settle`. The step that
accepts the ruling reads each of those disagreements back and fails when `stands` is unset; it
records the value `disagreements settled`. A review send-back is in the step journal only. A
ruling that raises an owner concern fails the step at stage `requires-human-action`, with the
concerns as its evidence.

## Promotion

Script `atw-matrix sync-documents; atw-matrix commit`. It runs when no review returned a finding
or asked for alternatives,
or the lead recorded that every item is resolved; anything else fails the step with a structured
cause. It sets the documents of the review scope effective in their front matter, mirrors their
lifecycle in the matrix (`sync-documents --paths`), removes each disagreement settled in this run
whose losing statement a maintainer step corrected, commits and pushes those documents in the
vault, and commits and pushes the matrix file (`atw-matrix commit --bead`). It writes
`<arch-work>/promoted.json` and records it as the file
`promoted documents`, with the values `vault commit` and `matrix commit` when a commit was made. A
document that could not be set effective fails the step, naming each with the reason.

## After the container

The outermost step "TRD" (`trd.confirm`, `trd-authoring.md`) follows, then the repository span
(`repo-scoping.md`).
