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
uses, and so that two Epics never work on the same unapproved shared item at the same time. For
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
| Shared capabilities the work on some entries must use | `atw-matrix uses --ids <id> ...` |
| What a Story building some entries of a stack must be handed | `atw-matrix story-scope --stack stack:<id> --ids <id> ...` |
| Documents an Epic reaches that are not effective | `atw-matrix review-scope --epic <beads id>` |
| The text of document headings, as the vault's last commit holds them | `atw-matrix heading '<path>#<heading>' ...` (a path alone prints the whole document) |
| Which of an Epic's content is approved, by the rule of reach | `atw-matrix approval --epic <beads id>` |
| The shared items (two or more Epics need them), each with its Epics, the requirements through which each needs it, and what decides who goes first | `atw-matrix shared-items [--epic <beads id>]` |
| The unapproved shared items no record decides, in batches for judging | `atw-matrix shared-items --batches <folder> [--batch-size 25]` |
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

**The rule of reach.** An Epic reaches an entry when a feature serving one of its
requirements is `realizedBy` the entry. It reaches a stack when an entry so reached is the
stack or has its home in it (`homeIn` on the architecture side, else on the repository side).
It reaches the direct far end of each dependency that starts at such an entry or stack, one
hop, never the dependency family outward. Document headings (`covers`, `describedBy`) and
`supportedBy` carry no reach. This is the Epic's approval scope
(`matrixtraverse.approval_scope`): what `atw-matrix approval --epic` lists, what the architect
reviews and what promotion approves. `atw-matrix epic <id> --realizers` lists, for each feature
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
| `approved: true` | any architecture entry or relationship (never an Epic) | The solutions architect approved the architecture for a feature: the architecture and design an Epic's elaboration reached are approved, and the matrix and arc42 are filled out or corrected for it. A plain yes or no: it records no Epic, stack, commit or owner, and absent means not approved. An entry goes through the same states by the same actions as a document (the `effective-architecture` skill, "Lifecycle, the baseline and iteration"): a change clears the mark, and the entry stays unapproved until an architect approves it again. The baseline carries no mark on purpose: no architect has reviewed it yet. | Only the promotion step of elaboration (`orchestrator/flows/architecture_promotion.py`, calling `matrixwrite.approve` as role `script`) on the Epic's approval scope without the Epic itself, its reach by the rule of reach in the corrected matrix (`atw-matrix approval --epic <id>` shows it), once its reviews pass. No `atw-matrix` command and no session sets it. Any later change to the entry or relationship, or to the heading text that describes it, clears it on that item alone; the next approval that covers it sets it again. Two Epics are never elaborated at the same time on the same unapproved architecture: the dependency edges `epicorder.py` sets in advance order them, and the driver's elaboration lane starts no Epic whose approval scope shares an entry with no approved mark with an Epic being elaborated, until that Epic's promotion approves it or its elaboration ends. |
| `verified: true` | any entry or relationship | The architecture was built and its test passed, so it is verified correct: the CI checks and the test that its CDK deployment works (the deployment may be removed again after the test). A plain yes or no: it records no Epic, stack, commit or owner, and absent means not verified. A property of the stack or component itself, valid for every Epic that relates to it. Verified = real, its code trusted; not verified = still to be made real, used like anything else. | Only the build driver (`ops/sdlc-automation/matrixmarks.py`), when a Story's test passes: `atw-matrix verify --story <id>` as role `build-driver`, on every stack and entry the Story's Tasks state they built (`built`) and every relationship starting there. A merge never sets it; the merge is a separate step after the test. A known change to what the item must be built as (the entry or relationship itself, the heading text that describes it, or an architecture-side relationship starting at it) clears it on that item alone; the next build and test sets it again. |
| `lifecycle` | `document` | Mirrors the document's `lifecycle_state`: `effective` (approved) or `in-review`, or another vault value such as `draft` or `superseded`. What the states and the approve action mean: the `effective-architecture` skill, "Lifecycle, the baseline and iteration". | `atw-matrix sync-documents`; the promotion step after `depscore.py arch-approve`. |
| `side` | everything | `architecture` (authority) or `repository` (hint). | Whoever records the fact: `put` and `link` take `--side`. |

Nothing is seeded approved or verified, and nothing in the live matrix is either yet. No
deployed or merged mark exists. Neither mark ever blocks reading, linking or designing on an
entry.

The verified mark, as [the matrix requirements](../../blueprint/requirements/matrix.md)
section 3.5 and R25 state it:

- It is set when an item has been built and tested, the CDK deployment test included. The
  test passing is the trigger. No merge and no branch sets or clears it.
- It belongs to the stack or component, not to an Epic. An Epic owns no stack and no
  component; it is a vehicle for requirements, and many Epics relate to many stacks and
  components. So never read verified as "this Epic's architecture is done".
- At the start nothing is verified, so the first builds verify everything they build. After
  that, only changes are not verified, and only changes become Tasks.
- What a stack or Task only uses (a shared library, a layer, a chassis) was verified when it
  was itself built and tested; using it verifies nothing.

Both marks are dirty bits on individual items, at the finest grain the matrix records: a known
change clears a flag on the item it touches and nothing else; approval sets `approved` again,
and building and testing the Story's Tasks (the CDK deployment test included) sets `verified`
again. They are separate marks: each clears on a change that affects it, independently of the
other; one change may clear only `approved`, only `verified`, or each at a different time.
Never infer one mark from the other. Naming the repository that holds a stack (its `repository`
attribute alone), or the owner's decision that no Epic drives it (its `epicDriver` attribute
alone), changes no approved design, so it keeps `approved`.

Reading the marks to decide what is planned and what exists:

- Verified: it exists as recorded, at its current architecture. Build on it and trust its code;
  it needs no work.
- Approved, not verified: it is the agreed design but is not built and tested yet, or the
  architecture changed it since it was (a change clears verified, as it clears approved). Plan
  the work that brings the build, from the code already there, up to the approved design.
- Neither: a planned or seeded fact, or a repository-side hint. Use it, check it, and do not
  count on code for it existing.

## Writing

- Read and write only through `atw-matrix`. Never edit, `jq`, `sed` or rewrite the JSON file;
  `atw-matrix` takes a lock, checks every write against the kinds registry and keeps the two
  sides apart.
- Writing needs a role in `ATW_MATRIX_ROLE` (unset means `operator`). `put`, `link` and `unlink`:
  `solutions-architect`, `repository-steward`, `script`. `settle`: `solutions-architect`,
  `decider`. `rename` and `remove`: `solutions-architect`, `repository-steward`, `operator`
  (`remove` also `script`). `record-judgments`: `script`, `operator`. `move-repository`:
  `repository-steward`, `operator`. `commit`:
  `script`, `repository-steward`, `build-driver`, `operator`. `apply`: `solutions-architect`,
  `repository-steward`, `script`, `decider`, and each operation of the file needs the role its
  own sub-command needs. Reads need none.
- Record a new fact:
  `atw-matrix put <kind> --side architecture --name "<name>" --purpose "<one or two sentences>" [kind options]`,
  then `atw-matrix link <kind> --from <id> --to <id> --side architecture [--heading ...]`. A
  repository-side component, infrastructure or layer takes `--stack stack:<id>`. Look the entry
  up with `find` first so one capability is one feature.
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
- Many changes in one step: write them to one change file
  (`skills/artifact-handoff/schemas/matrix-change.schema.json`: `{"operations": [{"op": "put" | "link" | "unlink" | "settle", ...}]}`,
  each operation with the arguments of its sub-command, attributes under `attributes`) and run
  `atw-matrix apply --file <path>`: one locked update, all or nothing, every failed operation
  reported with its index.
- Commit the file alone with `atw-matrix commit --bead <id>` (it pushes).
- A seeding or session result file is recorded by a script step (`seed-apply`), never entry by
  entry by the session.
- The solutions architect and its helpers write no entry by command: they record each `put`,
  `link`, `unlink` and `settle` as an operation in the run's change file (`matrix-changes.json`,
  to `matrix-change.schema.json`), which the step that accepts the architect's result applies in
  one update.

## Reconciling and seeding

| Need | Command |
|---|---|
| Epics and requirements from beads and the PRDs | `atw-matrix sync-epics [--bead <id> --prd <path>]` |
| Document entries, headings, lifecycle and `describedBy` from the vault | `atw-matrix sync-documents [--paths <files>] [--bead <id>]` |
| Events, purposes and publishers from the event catalog (arc42 section 6) | `atw-matrix sync-events` |
| Stacks against the repositories | the `polyrepo-doctor` `matrix` check (`atw-matrix stacks`, `check`) |
| Validate the file | `atw-matrix check` |
| Remove an alias from an entry (clears its approved flag) | `atw-matrix put <kind> --id <id> --side <side> --remove-aliases "<alias>"` |

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
6. `atw-matrix check`, then `atw-matrix commit`.
