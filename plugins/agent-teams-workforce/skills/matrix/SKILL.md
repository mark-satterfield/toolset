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
  reach, ready scripts for the transitive questions, the approved and verified marks, and the
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
options with `--help`. This is machine-local current state, ignored by git; it is neither
committed nor pushed. Worktree sessions use the same resolved file.

The matrix is a best guess, not a requirement. Where a built Task's code diverges from it (the code
does not use a shared capability the matrix guessed, uses one the matrix does not record, or the
Task names an id the matrix lacks), that is never a build failure, a finding that blocks, or work
for an implementer: the build corrects the matrix from the code (`follow-code`, below).

What the code does outranks this page: the kinds are
`skills/artifact-handoff/schemas/matrix-kinds.json`, the commands `scripts/portfolio/matrix.py`
and `matrixcli.py`, the full design `blueprint/design/matrix.md`.

## The model

Every entry has `id` (`<kind>:<slug>`), `kind`, `name`, `aliases`, `purpose`, `side` and the
attributes of its kind. Every relationship has `kind`, `from`, `to`, `side` and the attributes of
its kind. **`side`** says where a fact came from: `architecture` (beads, a PRD, an arc42 document
or the architect; the planned design, which the build corrects from the code it commits) or
`repository` (what a repository holds today; a hint, never a finding when it differs). Any entry may link to any other; a relationship kind names no entry
kinds, and an undeclared lowerCamelCase kind is accepted with no attributes.

The chain from an Epic to a repository:

```text
epic --hasRequirement--> requirement --servedBy--> feature (many-to-many across Epics)
feature --describedBy--> document <--describedBy-- service | component | infrastructure | event
feature --realizedBy--> service | component | infrastructure | event | layer | package | stack
service | component | infrastructure --homeIn--> stack   (stack.repository names its repository)
stack --imports|calls|publishes|reads|runsIn|usesLayer...--> what it depends on (any depth)
document --covers{heading, via: feature}--> requirement
```

A feature reaches an Epic only through the requirements it serves. No Epic relates directly to
another Epic.

**Shared items.** An item is shared when two or more Epics need it, whatever repository or name
it has (`shared-` names what is sharable at enterprise level, but `SkillSpoke-*` things are often
shared too): a feature that serves a requirement of each, or an architecture entry each reaches by
the rule of reach (below). Architecture is not fixed: later Epics may change shared architecture.
Epic-to-Epic edges exist so that an Epic waits for the Epic that builds and owns something it
uses, and so that two Epics never work on the same ordered shared item at the same time. For
each shared item, either one Epic builds and owns it and the others use it, or the Epics share it
independently (like two Epics whose Lambdas both need the VPC). That is a judgment from the
Epics' requirements, recorded as a `drives` from the Epic that goes first to the item (see
"Writing"); `epicorder.py` never infers it from counts or names. `epicorder.py` orders one
release at a time (`--release`, for example `mvp-1`): only the Epics whose PRD is in
`docs/sdlc/<release>/prds/` count as needing a shared item, and no edge is computed to or from an
Epic of another release. A repository is an attribute
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
| Shared capabilities the matrix guesses the work on some entries relies on | `atw-matrix uses --ids <id> ...` |
| What a Story building some entries of a stack must be handed | `atw-matrix story-scope --stack stack:<id> --ids <id> ...` |
| Documents an Epic reaches that are not effective | `atw-matrix review-scope --epic <beads id>` |
| The text of document headings, as the vault's last commit holds them | `atw-matrix heading '<path>#<heading>' ...` (a path alone prints the whole document) |
| Whether named features and architecture items are approved | `atw-matrix approval --ids <entry id> ...` |
| The shared items (two or more Epics need them), each with its Epics, the requirements through which each needs it, and what decides who goes first | `atw-matrix shared-items [--epic <beads id>]` |
| The ordered shared items no record decides, in batches for judging | `atw-matrix shared-items --batches <folder> [--batch-size 25]` |
| Open Tasks that name an entry / that a change affects / what a Story built | `atw-matrix work --id <id>` / `affected --id <id>` / `built --story <id>` |
| Which Epic builds an entry (its owner), and the Tasks that build it | `atw-matrix builders --ids <id> ... [--epic <beads id>]`: per id, `ownerEpic`, `builtBy` (the owner Epic's Tasks; empty when `--epic` is the owner) and every builder, from one read of beads |
| Open Tasks that name each of several entries, from one read of beads and the matrix | `atw-matrix work --ids <id> ... [--not-epic <beads id>]`: one read per id under `reads`, each id that is not an entry's under `failures` (the others are still answered; any failure exits 1) |
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

**The rule of reach.** An Epic reaches an entry when a feature serving one of its
requirements is `realizedBy` the entry. It reaches a stack when an entry so reached is the
stack or has its home in it (`homeIn` on the architecture side, else on the repository side).
It reaches the direct far end of each dependency that starts at such an entry or stack, one
hop, never the dependency family outward. Document headings (`covers`, `describedBy`) and
`supportedBy` carry no reach. This identifies the architecture the architect must review for
the requirements in hand. Review reach never makes approval an Epic property: promotion
records approval on the individual architecture items reviewed. `atw-matrix epic <id> --realizers` lists, for each feature
that serves the Epic's requirements, the ends of its `realizedBy`, each with its stack.

Example: Epic `ssbd-mb689` reaches `component:chat-turn-worker` because
`feature:hold-a-conversation-with-the-agent` serves its requirements and is `realizedBy` the
component, and reaches `stack:SkillSpoke-chat-service` because the component has its home there.

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
"$R" epics-reaching stack:SkillSpoke-push-service     # a stack: via names the reached entries that place it
"$R" epic-needs ssbd-mx3vn            # services, stacks, repositories it reaches, and gaps; --full lists components and infrastructure
"$R" unreached --kinds service,stack,repository   # entries of those kinds (repository = names stacks hold) no Epic reaches
```

`epic-needs` gaps: `noFeature` (requirement no feature serves), `noDocument` (requirement and
feature with no covering document), `requirementsReachNothing`, `requirementsNoStack`,
`requirementsNoRepository` (with the stacks that name none), `entriesNoStack`,
`stacksNoRepository`.

## Who builds an entry

An entry is built once. The Tasks that build it are the Tasks whose `builds_entries` key names it
(a Task without that key: the ids of its `matrix_elements` of a kind a Task builds; never the
stack or the shared capabilities `matrix_elements` also names). Among every Task of every Epic
that builds it, any status, closed included, the owner Task is the one whose build started, else
the earliest written, else the lowest id; its Epic owns the entry (`buildowner.py`). Every other
Epic uses the entry: elaboration marks its item `builtBy` with the owner's Tasks, plans no Task
to build it, specifies and builds only that Epic's addition to it (`adds_to_entries`), and blocks
the Tasks that need it by the owner's Tasks. Which Epic owns an entry is decided by this rule
when an Epic is planned, whatever a `drives` judgment says; `drives` orders Epics, nothing more.

## Approved, verified, effective and side

`approved` means the architecture agent has vetted the architecture for a feature or
component, including arc42 and the architecture and design documents that describe it.
Approval belongs to that item and remains valid for every Epic that overlaps it. A new Epic
alone never withdraws approval. Only a change to that specific architecture requires
architect reapproval; over time the mark should rarely change. Removed approvals are
reapproved by the architect, never restored by hand.

`verified` means the build pipeline has completed for the feature. Its architecture exists
in code or infrastructure as code in a repository, rather than only on paper.

Neither mark holds back an Epic or determines Epic order. Dependencies established ahead
of time order shared work independently of both marks. A missing dependency on shared work
is a dependency gap, not a reason to invent an approval hold.

| Field | On | Meaning | Who sets it, when, how |
|---|---|---|---|
| `approved: true` | architecture for individual features and components, never an Epic | The architecture agent vetted the item's architecture and design. The mark remains valid across overlapping Epics and changes only when the specific architecture changes and needs reapproval. | Promotion records the architect's approval after reviews pass. Acceptance of an architect's changed design withdraws approval only for the affected architecture. No session restores a mark by hand. |
| `verified: true` | completed architecture items and features | The feature's build pipeline completed and its architecture exists in code or infrastructure as code. The mark belongs to the item across all Epics. | The build driver records completion through `verify --story`. Unfinished contributing Stories defer an item. Features require all recorded architecture realizers verified; missing realizers remain unknown. No-PR completion uses the same rule. Known implementation changes clear only the affected item's mark. |
| `lifecycle` | `document` | Mirrors the document's `lifecycle_state`: `effective` (approved) or `in-review`, or another vault value such as `draft` or `superseded`. What the states and the approve action mean: the `effective-architecture` skill, "Lifecycle, the baseline and iteration". | `atw-matrix sync-documents`; the promotion step after `depscore.py arch-approve`. |
| `side` | everything | `architecture` (the planned design, corrected from built code) or `repository` (hint). | Whoever records the fact: `put` and `link` take `--side`. |

Seeding sets neither mark. Neither mark blocks reading, linking, designing or Epic work.

Both marks sit on individual items and change independently. Approval changes only when that
specific architecture changes and needs reapproval. Verification changes when the item's
required implementation changes and its build completes. Naming a repository or adding an
Epic alone changes neither. Reused verified components keep their marks.

The driver marks only completed Task contributions. A component shared by two unfinished
Stories waits for both contributions. A feature is verified only when its explicit
architecture-side realizers all exist and are verified. No recorded realizers means unknown;
broad reach and mere code presence never prove feature completion.

Reading the marks to decide what is planned and what exists:

- Verified: it exists as recorded, at its current architecture. Build on it and trust its code;
  it needs no work.
- Approved, not verified: it is the agreed design but is not built and tested yet, or the
  architecture changed it since it was. Plan
  the work that brings the build, from the code already there, up to the approved design.
- Neither: a planned or seeded fact, or a repository-side hint. Use it, check it, and do not
  count on code for it existing.

## Writing

The pipeline or an explicit owner-directed status correction records exact marks with
`atw-matrix approve-reviewed --ids <entry ids>` or
`atw-matrix approve-reviewed --kind <relationship kind> --from <source id> --to <destination id>`.
Only the script role may do this; the command grants no independent architecture judgment authority.
Each target must already exist on the
architecture side; Epic and requirement entries are excluded. A relationship tuple must identify
exactly one relationship. No endpoint or incident-relationship approval is inferred. All targets
are validated before the locked write; existing verified marks are preserved.

- Read and write only through `atw-matrix`. Never edit, `jq`, `sed` or rewrite the JSON file;
  `atw-matrix` takes a lock, checks every write against the kinds registry and keeps the two
  sides apart.
- Writing needs a role in `ATW_MATRIX_ROLE` (unset means `operator`). `put`, `link` and `unlink`:
  `solutions-architect`, `repository-steward`, `script`. `settle`: `solutions-architect`,
  `decider`. `rename` and `remove`: `solutions-architect`, `repository-steward`, `operator`
  (`remove` also `script`). `record-judgments`: `script`, `operator`. `follow-code`:
  `build-workflow`. `move-repository`:
  `repository-steward`, `operator`. `apply`: `solutions-architect`,
  `repository-steward`, `script`, `decider`, and each operation of the file needs the role its
  own sub-command needs. Reads need none.
- Record a new fact:
  `atw-matrix put <kind> --side architecture --name "<name>" --purpose "<one or two sentences>" [kind options]`,
  then `atw-matrix link <kind> --from <id> --to <id> --side architecture [--heading ...]`. A
  repository-side component, infrastructure or layer takes `--stack stack:<id>`. Look the entry
  up with `find` first so one capability is one feature.
- A stack holds at most one entry, on each side, of each resource type the kinds registry lists
  in `onePerStack` (`rds-db-cluster`: a service's own database cluster). A new entry of such a
  type put with `--stack` of a stack that already holds one, or homed (`homeIn`) in it by `link`,
  a change file or `seed-apply`, is merged into the held entry: its name joins the held entry's
  aliases and its relationships move to it. Use the held entry's id from then on.
- A resource that a shared construct creates in each stack that uses it (for example an SSM
  parameter or a CloudWatch metric filter a shared CDK construct writes into every consuming
  service's stack) gets no entry of its own: it has no one home, and an entry has at most one.
  State it as a fact of the construct's component, in the component's documents and its
  `purpose`, and record and name only the component; a change to what the construct creates is a
  change to the component.
- The judgment of which Epic goes first on a shared item is one architecture-side `drives`
  from that Epic to the item (a feature or any architecture entry) with `basis` `owns` (the Epic
  builds and owns it; the others use it) or `shared` (the Epics share it independently; the Epic
  merely goes first) and a one-sentence `reason`. At most one `drives` with a basis ends at an
  item, and a change to the item leaves it as it is. Judgments are recorded from a judgment file
  (`skills/artifact-handoff/schemas/shared-item-judgments.schema.json`) with
  `atw-matrix record-judgments --file <path>` (role `script` or `operator`), which refuses the
  whole file when an item is not shared, its Epic does not need it, or the owner's decision for
  its stack already decides it, and replaces another Epic's earlier judgment for the item.
- The owner's decisions for a whole stack: a `drives` with no basis from `epic:<beads id>` to
  `stack:<id>` says that Epic owns every shared item realized or homed in the stack;
  `atw-matrix put stack --id stack:<id> --side architecture --epic-driver none` says the stack is
  deployed in advance, so no shared item realized or homed in it orders Epics. A stack carries at
  most one of the two, and only the owner decides either. A `drives` with no basis ends only at a
  stack.
- Keep it current in the same piece of work: `rename --from <id> --to <id>`,
  `remove <id> [--held]`, `move-repository --from <repo> --to <repo>`, `unlink ...`.
- Many changes in one step: write them to one change file, whose shape is
  `skills/artifact-handoff/schemas/matrix-change.schema.json` (write exactly the shape that
  schema defines, and no other fields; each operation takes the arguments of its sub-command),
  and run `atw-matrix apply --file <path>`: one locked update, all or nothing, every failed
  operation reported with its index.
- The matrix is machine-local state, ignored by git. A successful locked write completes
  the operation; no matrix commit or push follows it. Every session reads the file resolved
  by `matrixstore.matrix_path`, including sessions working in a git worktree.
- A seeding or session result file is recorded by a script step (`seed-apply`), never entry by
  entry by the session.
- The solutions architect and its helpers write no entry by command: they record each `put`,
  `link`, `unlink` and `settle` as an operation in the run's change file (`matrix-changes.json`,
  to `matrix-change.schema.json`), which the step that accepts the architect's result applies in
  one update.

## The build corrects the matrix from the code

After `build:commit` commits a Task, the build fetches the repository's `origin` and runs
`build:matrix-follow`, which calls `follow-code` in process (`scripts/portfolio/matrixfollow.py`;
on the command line, which fetches first:
`atw-matrix follow-code --task <beads id> --ids <id> ... --worktree <path> --files <path> ...`)
with the ids in the Task's `matrix_elements`, its Story worktree and the files its own commits
changed. A wrong removal is worse than a stale guess, so
what cannot be judged safely is deferred, never written. It corrects the architecture-side
`supportedBy` relationships of the features the Task builds:

- Only features wholly in the worktree's repository are judged: every entry realizing the feature
  is held by a stack whose `repository` is the repository the worktree is a clone of. A Task whose
  ids span two repositories judges nothing of the other one.
- A relied `provides` item whose use signals occur nowhere is dropped from `relies`; the
  relationship is unlinked when no item is left. Nowhere means: not in the Story worktree's
  tracked source, and not in the committed source of the integration branch (`origin/HEAD`) or of
  any Story branch, local or on the remote. It is written only when no other Task still builds
  the feature in that repository: an open Task, or a closed Task of another Story that is not
  closed yet.
- A capability item whose code-shaped use signals occur in the code of the Task's changed product
  files (comments and docstrings left out), and which no relationship from what the Task reaches
  records, is added to `relies` of the relationship from the one feature the Task builds wholly
  in its repository, or linked from that feature when it has none. A use shown only by a prose
  signal (words and spaces, such as `central event API`) is deferred: too weak on its own.
- Anything else that diverges is recorded as `deferred` with its reason, and ids the matrix lacks as
  `unknownIds`; neither is written. Items with no use signal are kept.

The step records the `matrixFollow` value (`repository`, `refs`, `removed`, `narrowed`,
`widened`, `linked`, `deferred`, `unknownIds`). The build's reuse audit (`check-reuse`) records
divergence as notes only. A changed relationship clears the start feature's `verified` mark;
`verify --story` at Story close sets it again on the corrected matrix.

## Reconciling and seeding

| Need | Command |
|---|---|
| Epics and requirements from beads and the PRDs | `atw-matrix sync-epics [--bead <id> --prd <path>]` |
| Document entries, headings, lifecycle and `describedBy` from the vault | `atw-matrix sync-documents [--paths <files>] [--bead <id>]` |
| Events, purposes and publishers from the event catalog (arc42 section 6) | `atw-matrix sync-events` |
| Stacks against the repositories | the `polyrepo-doctor` `matrix` check (`atw-matrix stacks`, `check`) |
| Validate the file | `atw-matrix check` |
| Remove an alias from an entry | `atw-matrix put <kind> --id <id> --side <side> --remove-aliases "<alias>"` |

Seeding fills an empty matrix in this order (`blueprint/design/matrix.md` section 3):

1. `atw-matrix seed`: an empty file, then beads and PRD requirements (`sync-epics`), the arc42
   documents (`sync-documents`), one stack per repository (`seed-stacks`), project packages and
   imports (`seed-packages`), and the session batch files (`seed-inputs`).
2. Architecture-side sessions read the arc42 batches (services, components, infrastructure,
   events, layers, stacks, dependencies, constraints); `seed-apply --step architecture`.
3. Feature sessions read the PRD batches and propose the features of each requirement;
   `seed-features --list`, one merge session, then `seed-apply --step features` records each
   feature once with `servedBy`, `describedBy` and `covers`.
4. `seed-realizers` writes the feature batches; realizer sessions name what realizes each
   feature; `seed-apply --step realizers` records each `realizedBy`.
5. Repository-side sessions read each stack's repository; `seed-apply --step repository`.
6. `atw-matrix check`.
