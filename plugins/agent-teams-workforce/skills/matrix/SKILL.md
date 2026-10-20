---
name: matrix
description: >-
  The one guide to the matrix, the graph of entries (Epics, requirements, features, constraints,
  documents, services, components, infrastructure, events, stacks, packages, layers, files,
  disagreements) and typed relationships read and written only through `atw-matrix`. Load it
  before any `atw-matrix` call, and whenever you ask which Epics, features, documents, services,
  stacks or repositories relate to something, what an Epic needs, what depends on an entry, or
  what is approved or verified, or record, rename or remove a fact in the matrix. It holds the
  model, which command answers which question, the direct-versus-transitive trap, the rule of
  reach, ready scripts for the transitive questions, the approved and verified flags, and the
  rules for writing.
user-invocable: false
allowed-tools: [Bash, Read]
---

# The matrix

The matrix is one JSON file (`ops/sdlc-automation/matrix.json` in the control repository) that
records how Epics, their requirements, features, constraints, arc42 documents, services,
components, infrastructure, events, stacks, packages, layers and repositories relate, so that no
step scans documents or code to find out. It is read and written **only** through
`${CLAUDE_PLUGIN_ROOT}/bin/atw-matrix <sub-command>`, which prints one JSON object. The file is
found from `--matrix`, else `ATW_MATRIX`, else `ATW_CONTROL_REPO`. Every sub-command lists its
options with `--help`.

What the code does outranks this page: the kinds are
`skills/artifact-handoff/schemas/matrix-kinds.json`, the commands `scripts/portfolio/matrix.py`
and `matrixcli.py`, the full design `blueprint/design/matrix.md`.

## The model

Every entry has `id` (`<kind>:<slug>`), `kind`, `name`, `aliases`, `purpose`, `side` and the
attributes of its kind. Every relationship has `kind`, `from`, `to`, `side` and the attributes of
its kind. **`side`** says where a fact came from: `architecture` (beads, a PRD, an arc42 document
or the architect; the authority) or `repository` (what a repository holds today; a hint, never a
finding when it differs). Any entry may link to any other; a relationship kind names no entry
kinds, and an undeclared lowerCamelCase kind is accepted with no attributes.

The chain from an Epic to a repository:

```text
epic --hasRequirement--> requirement --servedBy--> feature (many-to-many across Epics)
feature --describedBy--> document <--describedBy-- service | component | infrastructure | event
feature --realizedBy--> service | component | infrastructure | event | stack
service | component | infrastructure --homeIn--> stack   (stack.repository names its repository)
stack --imports|calls|publishes|reads|runsIn|usesLayer...--> what it depends on (any depth)
document --covers{heading, via: feature}--> requirement
```

A feature reaches an Epic only through the requirements it serves. A repository is an attribute
of a stack (`repository`), never an entry. The full lists of entry kinds and relationship kinds,
with direction and meaning, are in [references/model.md](references/model.md).

## Which command answers which question

| Question | Command |
|---|---|
| The PRD of an Epic; its requirements, their features and covering documents | `atw-matrix epic <beads id>` |
| The Epic of a PRD | `atw-matrix find --kinds epic --prd <vault path>` |
| Does a feature, stack, document or constraint for this behaviour exist? | `atw-matrix find --kinds feature,stack --text "<words>"` (empty result = none exists) |
| One entry with its **direct** relationships, both directions | `atw-matrix node <id>` |
| Everything an Epic reaches, by repository | `atw-matrix epic <beads id> --closure` (huge: query by script) |
| The Epic's links with nothing at the other end | `atw-matrix epic <beads id> --unlinked` |
| Constraints that bind an Epic; what realizes each feature | `epic <id> --constraints`; `epic <id> --realizers` |
| What an entry depends on / what depends on it (dependency family, any depth) | `atw-matrix deps --of <id>` / `deps --on <id>` |
| What rests on an entry before you change it (**direct** features, constraints, dependents) | `atw-matrix impact --id <id>` |
| Other Epics that share what this Epic reaches | `atw-matrix related --epic <beads id>` |
| AWS resources an Epic reaches, with stacks and repositories | `atw-matrix resources --epic <beads id>` |
| Stacks of an app, a repository, or holding a resource type | `atw-matrix stacks --app <a>` / `--repository <r>` / `--resource-type <t>` |
| SSM parameters a stack writes and reads | `atw-matrix parameters --stack stack:<id>` |
| Every document related to an entry (and its parts) | `atw-matrix documents --id <id>` |
| Follow links to any depth, either direction, chosen kinds | `atw-matrix links --id <id> --direction in --kinds describedBy,servedBy` |
| Layers, their packages and users | `atw-matrix layers` |
| Shared capabilities the work on some entries must use | `atw-matrix uses --ids <id> ...` |
| What a Story building some entries of a stack must be handed | `atw-matrix story-scope --stack stack:<id> --ids <id> ...` |
| Documents an Epic reaches that are not effective | `atw-matrix review-scope --epic <beads id>` |
| Which of an Epic's content is approved | `atw-matrix approval --epic <beads id>` |
| Open Tasks that name an entry / that a change affects / what a Story built | `atw-matrix work --id <id>` / `affected --id <id>` / `built --story <id>` |
| Counts; repository-side entries with no architecture counterpart | `atw-matrix summary [--unlinked]` |
| Does the file meet its contract? | `atw-matrix check` |

## The trap: direct is not transitive, and the closure reaches everything

`atw-matrix node <id>` and `atw-matrix impact --id <id>` return only what is linked **directly**
to the entry. A service is joined to an Epic through requirement → document heading → service,
so `node` and `impact` on a service show no Epic even when many Epics reach it. Never answer
"which Epics reach X" or "no Epic needs X" from `node` or `impact`.

The opposite trap: `atw-matrix epic <id> --closure` follows stack dependencies and every document
that describes a feature, so broad documents (READMEs, crosscutting concepts) and shared services
make every Epic reach every service. `related --epic` and `resources --epic` walk the same
closure. Never answer "which Epics reach X" from the closure either.

**The rule of reach.** An Epic reaches an entry when a document `covers` one of the Epic's
requirements under the same heading that the entry's `describedBy` names, or when a feature
serving one of its requirements is `realizedBy` the entry. It reaches a stack when an entry so
reached is the stack, has its home in it (`homeIn`), or `correspondsTo` an entry that does.
`atw-matrix epic <id> --realizers` applies the same heading match per feature.

Example: Epic `ssbd-mx3vn` reaches `service:skillspoke-push-service` because
`arc42/05-building-block-view/messaging-and-realtime/README.md` covers its requirements under
"Building blocks" and "Per-channel delivery services", the headings that describe the service.

- `atw-matrix epic <id>` (no flag) returns `requirements[]` (each with `features` and
  `coveredBy`), `noFeature` and `noDocument`. `noStack`, `noRepository`, `noCounterpart` and
  `noSource` appear only with `--unlinked` (or `--closure`).
- `--closure` output is over a megabyte for one Epic. Never read it raw.

## Ready scripts for the transitive questions

`${CLAUDE_PLUGIN_ROOT}/skills/matrix/scripts/matrix-reach` applies the rule of reach to every
Epic in one process and prints a short answer (`--json`, placed before the query, prints one
object). It reads only. Each run takes a few seconds.

```bash
R="${CLAUDE_PLUGIN_ROOT}/skills/matrix/scripts/matrix-reach"
"$R" epics-reaching service:skillspoke-push-service   # the Epics that reach it, each with the document#heading or realizedBy feature
"$R" epics-reaching stack:skillSpoke-push-service     # a stack: via names the reached entries that place it
"$R" epic-needs ssbd-mx3vn            # services, stacks, repositories it reaches, and gaps; --full lists components and infrastructure
"$R" unreached --kinds service,stack,repository   # entries of those kinds (repository = names stacks hold) no Epic reaches
```

`epic-needs` gaps: `noFeature` (requirement no feature serves), `noDocument` (requirement and
feature with no covering document), `requirementsReachNothing`, `requirementsNoStack`,
`requirementsNoRepository` (with the stacks that name none), `entriesNoStack`,
`stacksNoRepository`.

## Approved, verified, effective and side

| Field | On | Meaning | Who sets it, when, how |
|---|---|---|---|
| `approved: {epic}` | any entry or relationship | The architecture and design of that Epic are approved, and the matrix and arc42 are filled out or corrected for it. Similar to, not the same as, `effective`. | Only the promotion step of elaboration (`orchestrator/flows/architecture_promotion.py`, calling `matrixwrite.approve` as role `script`) on the Epic's approval scope (`atw-matrix approval --epic <id>` shows it), once its reviews pass. No `atw-matrix` command and no session sets it. Any later change to the entry or relationship, or to a document that describes it, clears it. |
| `verified: {commit, changedBy?}` | any entry or relationship | Every Task of every Story of the Epic that built it was built and tested, CI/CD and CDK included, with the deploy working. Verified = real, its code trusted; not verified = still to be made real, used like anything else. | Only the build driver (`ops/sdlc-automation/matrixmarks.py`, at the Story's `deploy:close`) when GitHub reports a Story's PR merged: `atw-matrix verify --story <id> --commit <sha>` as role `build-driver`, then `atw-matrix commit --bead <id>`. It writes only when that merge completes the Epic (all its Tasks and other Stories closed), on what the Stories' Tasks state they built (`built`) and the relationships starting there. A first approved change by another Epic keeps it with `changedBy`; a second clears it. |
| `lifecycle` | `document` | Mirrors the arc42 front matter: `effective` (approved as of now), `in-review`, `draft`. | `atw-matrix sync-documents`; the promotion step after `depscore.py arch-approve`. |
| `side` | everything | `architecture` (authority) or `repository` (hint). | Whoever records the fact: `put` and `link` take `--side`. |

Nothing is seeded approved or verified, and nothing in the live matrix is either yet. No
deployed or merged mark exists. Neither flag ever blocks reading, linking or designing on an
entry.

## Writing

- Read and write only through `atw-matrix`. Never edit, `jq`, `sed` or rewrite the JSON file;
  `atw-matrix` takes a lock, checks every write against the kinds registry and keeps the two
  sides apart.
- Writing needs a role in `ATW_MATRIX_ROLE` (unset means `operator`). `put`, `link` and `unlink`:
  `solutions-architect`, `repository-steward`, `script`. `settle`: `solutions-architect`,
  `decider`. `rename` and `remove`: `solutions-architect`, `repository-steward`, `operator`
  (`remove` also `script`). `move-repository`: `repository-steward`, `operator`. `commit`:
  `script`, `repository-steward`, `build-driver`, `operator`. Reads need none.
- Record a new fact:
  `atw-matrix put <kind> --side architecture --name "<name>" --purpose "<one or two sentences>" [kind options]`,
  then `atw-matrix link <kind> --from <id> --to <id> --side architecture [--heading ...]`. A
  repository-side component, infrastructure or layer takes `--stack stack:<id>`. Look the entry
  up with `find` first so one capability is one feature.
- Keep it current in the same piece of work: `rename --from <id> --to <id>`,
  `remove <id> [--held]`, `move-repository --from <repo> --to <repo>`, `unlink ...`.
- Commit the file alone with `atw-matrix commit --bead <id>` (it pushes).
- A seeding or session result file is recorded by a script step (`seed-apply`), never entry by
  entry by the session.

## Reconciling and seeding

| Need | Command |
|---|---|
| Epics and requirements from beads and the PRDs | `atw-matrix sync-epics [--bead <id> --prd <path>]` |
| Document entries, headings, lifecycle and `describedBy` from the vault | `atw-matrix sync-documents [--paths <files>] [--bead <id>]` |
| Events, purposes and publishers from the event catalog (arc42 section 6) | `atw-matrix sync-events` |
| Stacks against the repositories | the `polyrepo-doctor` `matrix` check (`atw-matrix stacks`, `check`) |
| Validate the file | `atw-matrix check` |

Seeding fills an empty matrix in this order (`blueprint/design/matrix.md` section 3):

1. `atw-matrix seed`: an empty file, then beads and PRD requirements (`sync-epics`), the arc42
   documents (`sync-documents`), one stack per repository (`seed-stacks`), project packages and
   imports (`seed-packages`), and the session batch files (`seed-inputs`).
2. Architecture-side sessions read the arc42 batches (services, components, infrastructure,
   events, layers, stacks, dependencies, constraints); `seed-apply --step architecture`.
3. Feature sessions read the PRD batches and propose the features of each requirement;
   `seed-features --list`, one merge session, then `seed-apply --step features` records each
   feature once with `servedBy`, `describedBy` and `covers`.
4. Repository-side sessions read each stack's repository; `seed-apply --step repository`.
5. `atw-matrix check`, then `atw-matrix commit`.
