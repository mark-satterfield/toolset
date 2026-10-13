# The matrix: design

This document states how the matrix meets `blueprint/requirements/matrix.md`: what it holds,
how each lookup is answered, how it is seeded, which pipeline steps read and maintain it,
which discovery mechanisms it replaces, the check that keeps them replaced, and the slices
that move today's matrix to this design.

Paths are relative to the root of the `agent-teams-workforce` plugin unless they begin with
`ops/sdlc-automation/`, which is the driver in the control repository.

## 1. What is recorded

### 1.1 The file and the kinds registry

The matrix is one JSON file, `ops/sdlc-automation/matrix.json` in the control repository.
Sessions and scripts find it through the `ATW_MATRIX` variable and read and change it only
through `bin/atw-matrix`.

The file holds four members:

| Member | Holds |
|---|---|
| `version` | `4`. |
| `documentsSyncedAt` | `vaultCommit` and `dirtyPaths`: the vault commit the document entries mirror, and the documents that differed from it. |
| `entries` | A map from an entry id to one entry. |
| `relationships` | A list of relationships, each stored once, sorted by `from`, `kind`, `to`, `key`. |

What kinds exist is data, in `skills/artifact-handoff/schemas/matrix-kinds.json` (the kinds
registry). `skills/artifact-handoff/schemas/matrix.schema.json` validates the generic shape
of the file; `atw-matrix check` validates every entry and relationship against the
registry. `skills/artifact-handoff/scripts/matrix_contract.py` is generated from both.

The registry declares:

- for each entry kind: its id pattern, its attributes with their types and allowed values,
  which attributes are required, and `verifiable` (whether the kind carries the verified
  mark);
- for each relationship kind: its name, its reverse name, the entry kinds it starts from and
  ends at, its attributes, its `key` attributes (what distinguishes two relationships of one
  kind between the same two entries), its `family`, and `provedByBuild`;
- the controlled list of resource types;
- each `atw-matrix` command with the roles that run it (the `ATW_MATRIX_ROLE` variable).

A new kind of entry or relationship is one declaration in the registry. The store, `put`,
`link`, `node`, `find` and `check` work on any registered kind, so nothing already held is
restructured. A lookup that follows a whole group of relationships selects by `family`, so a
new dependency kind declared with `family: dependency` is followed by Q9 and Q15 with no
change to them.

### 1.2 Entries

Every entry has `id`, `kind`, `name`, `aliases` (other names it is known by) and `purpose`
(one or two sentences that identify it). An entry of a verifiable kind may carry `verified`
(section 1.4). Any entry may carry `claim` (section 1.5).

An id is the kind, a colon and the rest. The rest is the slug of the entry's name (lowercase
words joined by hyphens) unless the table says otherwise. No id contains a repository name.
An id stays when the name changes; `atw-matrix rename` re-keys an entry and both ends of its
relationships in one write.

| Kind | What one is | Id | Attributes beyond the common ones |
|---|---|---|---|
| `epic` | One Epic with its PRD. | `epic:<beads id>` | `prd` (`path` in the vault, `hash`), `expertise` (skill names). |
| `requirement` | One requirement of a PRD: one `####` heading under `## Requirements`. | `requirement:<epic beads id>/<key>`; the key is the identifier that opens the heading (`CHAT-001`), else the slug of the heading. | `group` (the `###` heading above it), `hash` (of the requirement's own text). `name` is the heading text. |
| `feature` | One capability, stated in general terms ("send an email to a person"). | `feature:<slug>` | `provides`: for a shared capability, a list of `id`, `behaviour`, `consumersMust`, `interface` (`kind`, `name`), `useSignals`, `duplicateSignals`. |
| `constraint` | One technical requirement or constraint. | `constraint:<slug>` | `statement`; `selector` (any of `app`, `stackType`, `resourceType`, `executionUse`) when it applies to everything of a class. |
| `document` | One arc42 document. | `document:<path under the architecture root>` | `lifecycle` (`effective`, `in-review`, `draft`), `section`, `viewType`, `scope`, `subject`, `headings` (the heading texts), `hash`. |
| `service` | One service the architecture describes. | `service:<slug>` | `executionUse`. |
| `component` | One component: a Lambda function, a module, a construct, a page. | `component:<slug>` | `resourceType`, `executionUse`. |
| `infrastructure` | One piece of infrastructure: a table, a queue, a rule, a parameter, a bus. | `infrastructure:<slug>` | `resourceType`. |
| `event` | One event type that code publishes or consumes. | `event:<detail type>` | none. |
| `stack` | The home in code of services, components and infrastructure. | `stack:<stack name>` | `repository`, `app` (`employer`, `marketing`, `personal-agent`, `shared`), `executionUse`, `commands` (`test`, `publish`, `deploy`). `purpose` is required and has the form requirements section 3.3 shows. |
| `package` | One Python package. | `package:<distribution name>` | `origin` (`project`, `third-party`). |
| `layer` | One AWS Lambda layer the project deploys. | `layer:<slug>` | none. |
| `story` | One open Story. | `story:<beads id>` | `epic` (beads id). |
| `task` | One open Task. | `task:<beads id>` | `epic`, `story` (beads ids). |
| `disagreement` | Two or more arc42 statements that disagree now. | `disagreement:<slug>` | `stands` (`document`, `heading`) and `rule` once ruled; `reason`. |

Notes on the kinds:

- A stack's type is the last token of its name, as `resource-naming-standard.md` in arc42
  section 8 defines `{type}`. It is computed when read and is not stored.
- `executionUse` is `executable` (a service, a Lambda, anything run or called) or `imported`
  (code other code imports). A library is a stack whose `executionUse` is `imported`.
- A `package` with `origin: third-party` exists only while a layer contains it and has only
  `contains` relationships ending at it.
- `repository` and `app` are attributes of a stack. No entry exists for a repository or an
  app. A lookup by either is a filter over stacks.
- Two things of one kind that would share a name are told apart by qualifying each name with
  the service or arc42 subject it belongs to.
- A `story` or `task` entry exists while its bead is open and is removed when the bead closes.

### 1.3 Relationships

A relationship has `kind`, `from`, `to`, the attributes its kind declares, and optionally
`verified` and `claim`. It is stored once and indexed from both ends: `atw-matrix node <id>`
returns the relationships that start at the entry under the kind's name and those that end
at it under the reverse name.

| Kind (reverse) | From → to | Meaning | Attributes |
|---|---|---|---|
| `hasRequirement` (`requirementOf`) | epic → requirement | The Epic's PRD states the requirement. | none |
| `servedBy` (`serves`) | requirement → feature | The feature is derived from the requirement and serves it. | none |
| `supportedBy` (`supports`) | feature → feature | The first feature relies on the second, a supporting capability. | `relies` (ids of the `provides` items relied on) |
| `realizedBy` (`realizes`) | feature → service, component, infrastructure, event, stack | The entry implements the feature or provides the capability. | none |
| `describedBy` (`describes`) | feature, constraint, service, component, infrastructure, event, stack, package, layer → document | The document describes the entry. | `heading` (key) |
| `covers` (`coveredBy`) | document → requirement | The document covers this requirement of this PRD. | `heading` (key), `via` (the feature that connects them, key) |
| `statedIn` (`states`) | constraint → document | The constraint comes from this document. | `heading` (key) |
| `appliesTo` (`constrainedBy`) | constraint → epic, feature, stack, service, component, infrastructure, event | The constraint binds the design of the entry. | none |
| `homeIn` (`holds`) | service, component, infrastructure, event, layer, package → stack | The stack is the entry's home in code. At most one per entry. | none |
| `partOf` (`hasPart`) | component, infrastructure → service | The entry is part of the service. | none |
| `distributedAs` (`distributes`) | stack → package | The stack's imported code is published to CodeArtifact as this package. | none |
| `contains` (`containedIn`) | layer → package | The layer carries the package. | none |
| `imports` (`importedBy`) | stack, service, component → stack | Code imports the library the target stack holds. | `through` (the package or layer id that brings it) |
| `usesLayer` (`layerUsedBy`) | component → layer | The Lambda attaches the layer. | none |
| `calls` (`calledBy`) | stack, service, component → service | Code calls the shared service. | `interface` (the operation or API) |
| `publishes` (`publishedBy`) | service, component → event | Code publishes the event. | none |
| `consumes` (`consumedBy`) | service, component → event | Code consumes the event. | none |
| `routes` (`routedBy`) | infrastructure → event | The rule routes the event. | `target` (the entry it routes to, key) |
| `reads` (`readBy`) | stack, service, component → infrastructure | Code reads a value another stack stored, such as an SSM parameter. | none |
| `runsIn` (`hosts`) | stack, service, component → infrastructure | Code runs in shared infrastructure, such as a VPC or a bus. | none |
| `placedIn` (`placements`) | story, task → stack | The work lands in the stack. | none |
| `builds` (`builtBy`) | story, task → stack, service, component, infrastructure, event, package, layer | The work makes the entry real or changes it. | none |
| `drives` (`drivenBy`) | epic → feature, document | The Epic's requirements shape this architecture decision. | `heading` for a document (key) |
| `restsOn` (`supportsEpic`) | epic → feature, document, stack, service, component, infrastructure | The Epic relies on this as settled architecture. | `heading` for a document (key) |
| `disputes` (`disputedBy`) | disagreement → document | The document holds one of the disagreeing statements. | `heading` (key), `text` |

`imports`, `usesLayer`, `calls`, `publishes`, `consumes`, `routes`, `reads` and `runsIn` have
`family: dependency`. `homeIn`, `partOf`, `distributedAs`, `contains` and the dependency
family have `provedByBuild: true`.

A dependency between two stacks is read, never stored: stack A depends on stack B when a
dependency relationship starts at A or at an entry whose home is A and ends at B or at an
entry whose home is B. A dependency found at stack level, with the entries not yet known, is
recorded with the stacks as its ends.

### 1.4 The verified mark

The matrix has one code mark, `verified`. It holds one field, `commit`.

- It is set when a Story's code has been built and tested and has passed, including its
  CI/CD and its CDK. The driver sets it when GitHub reports the Story's pull request merged,
  which is the first moment the tests, the CDK deploy and its verification, and the CI/CD
  checks have all passed. `commit` is the merge commit on the default branch.
- It is recorded on the stack the Story is placed in, on each entry the Story `builds`, and
  on each relationship with `provedByBuild` that starts at one of those entries.
- For a stack with no CDK app, the publish of its package to CodeArtifact stands where the
  CDK deploy does.
- A Story that closes with no pull request sets no mark: no code changed and no CI/CD ran.
- Absent means not verified. No other value exists, and nothing records deployed or merged.
- When verified code is changed by a later Story, the mark stays, with its commit, until
  that Story is verified and replaces the commit. The change in progress is the open Story's
  `builds` relationship to the entry. Entries and relationships the Story adds are not
  verified until then.

One command sets it: `atw-matrix verify --story <beads id> --commit <sha>`, run by the role
`build-driver`. It selects by the Story's `placedIn` and `builds` relationships and takes no
stack, element or repository name.

### 1.5 Claims

`claim` holds `epic` and `step`. An elaboration run claims each entry, relationship and
document heading it creates or changes. A claim means "this Epic is changing this now and it
is not yet reviewed". `atw-matrix review-scope --epic <id>` returns the Epic's claims; the
promotion step releases them. A claim never hides anything from a lookup.

### 1.6 What the matrix leaves out

- Past states: no retired, deprecated, archived or deferred entry, no status value, no
  change stamp, no review send-back, no approval record. Git holds history; the step journal
  holds the run.
- An approval decision: a document's `lifecycle` mirrors its arc42 front matter.
- Design content: a design fact stays under its arc42 heading; the matrix holds the heading.
- Words: no entry exists for a word that appears in a document.
- TRD and Spec files: their paths are on the Epic and Story beads.
- Live repository state (uncommitted files, ahead and behind, archived on GitHub): the
  `polyrepo` tool reads it.
- Bead status and Epic-to-Epic `tracks` edges: beads holds them.

## 2. How each lookup is answered

Every command prints one JSON object. Each returned entry and relationship carries `kind`
and, where set, `verified` and `claim`.

| # | Command | Traversal |
|---|---|---|
| Q1 | `atw-matrix epic <beads id>`; `find --kinds epic --prd <path>` | Read the `epic` entry: its `prd.path`. From a PRD path, the one epic whose `prd.path` equals it. |
| Q2 | `epic <id>` | epic → `hasRequirement` → each requirement → `servedBy` → features. A requirement with no `servedBy` is listed under `noFeature`. |
| Q3 | `find --kinds feature --text "<words>"` | Rank features by shared words across `name`, `aliases`, `purpose` and each `provides.behaviour`. Each match is returned with the Epics reached by `serves` → `requirementOf`. An empty result means no such feature exists. |
| Q4 | `epic <id>` | For each requirement: the `coveredBy` relationships, each with `document`, `heading` and `via`. A requirement and feature pair with no `covers` naming both is listed under `noDocument`. |
| Q5 | `epic <id> --constraints` | Collect the Epic's entries (Q12's set plus the epic and its features). Return each constraint with an `appliesTo` to one of them, and each constraint whose `selector` matches one of them, with its `statedIn` document and heading and the entries it reached. A constraint with no `statedIn` is listed under `noSource`. |
| Q6 | `node feature:<id>` | feature → `realizedBy` → entries, each → `homeIn` → stack. |
| Q7 | `node stack:<id>` | The stack's `purpose`. |
| Q8 | `find --kinds stack --text "<description>"` | Rank stacks by shared words across `purpose`, `name`, `aliases`, and the names and purposes of the entries each `holds` and the features those realize. |
| Q9 | `deps --of <id>` | From the entry (for a stack, also every entry it `holds`), follow the dependency family outward to any depth. Each result carries the relationship kind, its attributes (`through`, `interface`, `target`) and the stack that holds the target. For `imports`, `through` names the package or layer. |
| Q10 | `node stack:<id>` | The stack's `repository`. |
| Q11 | `node stack:<id>` | `type`: the last token of the stack's name. |
| Q12 | `epic <id> --closure` | epic → requirements → features, with `supportedBy` to any depth → `realizedBy` → entries → `homeIn` → stacks; then Q9 from those stacks. Group stacks by `repository`. Each repository is returned with its stacks and the features that lead to each; a stack holding an entry the Epic claims is marked `work`. |
| Q13 | `epic <id> --missing` | `noFeature` (Q2), `noDocument` (Q4), `noSource` (Q5), and `noStack`: entries reached in Q12 with no `homeIn`. |
| Q14 | any read | `verified` present with its commit, or absent, on each entry and relationship returned. |
| Q15 | `deps --on <id>` | From the entry (for a stack, also every entry it `holds`), follow the dependency family inward to any depth, with the same result shape as Q9. |
| Q16 | `layers` | Each `layer` → `contains` → packages, and → `layerUsedBy` → components. |
| Q17 | `node stack:<id>`; `stacks --app <app>` | The stack's `app`; the stacks whose `app` equals the value. |
| Q18 | `node <id>` | entry → `describedBy` → documents, each with `heading` and `lifecycle`. |
| Q19 | `node story:<id>` or `node task:<id>`; `work --stack <id>` | The work's `placedIn` stack with its `repository`, and what it `builds`. For a stack: `placements`, each with its `epic`. |
| Q20 | `impact --id <id>`; `impact --bead <task id>` | From the entry: `describes` (for a document), `realizes`, `constrainedBy`, Q15's dependents, then from every feature reached `serves` → requirements → Epics, then `builtBy` and `placements` for open Stories and Tasks. For a Task, start from what it `builds`. |
| Q21 | `related --epic <id>` | The Epics that reach any feature, document, stack, service, component or infrastructure this Epic reaches through Q12, `covers`, `drives` or `restsOn`. Each is returned with what is shared and through which relationship. |
| Q22 | `node stack:<id>` | `executionUse`, the `distributedAs` package, and `commands.test`, `commands.publish`, `commands.deploy`. |
| Q23 | `stacks --resource-type <type>` | The stacks that `holds` an entry with that `resourceType`. |
| Q24 | `expertise --epic <id>` | The epic's `expertise`. |
| Q25 | `stacks --repository <name>` | The stacks whose `repository` equals the name. |

Two further reads serve single steps: `uses --task <id>` returns the shared capabilities a
Task's work must use (task → `builds` → entries → `realizes` → features → `supportedBy` to any
depth → features with `provides`, each with its `realizedBy` provider and that provider's
stack), and `story-scope --bead <id>` returns in one object what a Story or Task builds, its
stack and repository, the documents and headings that describe each built entry (Q18), the
constraints that apply (Q5) and the shared capabilities (`uses`).

## 3. Seeding

Seeding is deterministic code except where the table names an agent. Every seeded entry and
relationship is unverified.

| Kind | Source | Done by |
|---|---|---|
| `stack`: `name`, `repository` | Today's stack entries; `polyrepo inventory` for every repository that holds code; the stack names `cdk list` prints in each repository that has a CDK app. A code repository with no CDK app gets one stack named by `atw-naming`. | `atw-matrix seed-stacks` |
| `stack`: `app` | The app sub-folder the repository's clone sits in, from `polyrepo inventory`. | `seed-stacks` |
| `stack`: `executionUse` | `imported` when the repository's `pyproject.toml` declares a distributable package and the stack synthesizes no resources; otherwise `executable`. | `seed-stacks` |
| `stack`: `purpose` | `atw-matrix purpose-input --stack <id>` writes one input file per stack: the entries the stack holds with their resource types, the handler and public module names on the default branch, the package description, and the arc42 headings that describe its services and components. The `polyrepo-steward` drafts the purpose from that file; the `aws-solutions-architect` checks each draft against the effective arc42 headings named in the file and the two settle a difference by what the code on the default branch does. | `purpose-input`, then the two agents, then `put` |
| `stack`: `commands` | Empty. The first build or deploy that resolves a command records it (section 4, B6 and D1). | the pipeline |
| `package` (`origin: project`), `distributedAs` | `[project].name` of each library repository's `pyproject.toml`. | `atw-matrix seed-packages` |
| `layer`, `contains`, `package` (`origin: third-party`), `usesLayer` | The synthesized cloud assembly: each `AWS::Lambda::LayerVersion`, the layer's requirements file, and the `Layers` property of each `AWS::Lambda::Function`. | `atw-matrix record-assembly --tree <repository>` |
| `infrastructure`, `component` for Lambda functions, their `homeIn`, `reads`, `routes` | The same assembly: resources of the controlled resource types by physical name, SSM parameter reads matched to the `AWS::SSM::Parameter` that stores each, and each `AWS::Events::Rule` pattern and target. A resource that matches no entry by name or alias is added and returned under `unmatched` for the `polyrepo-steward` to merge with a designed entry by alias. | `record-assembly` |
| `service`, `component`, `infrastructure` the documents describe | Today's entries, converted (section 7, slice 11), and the `shows` list of each effective arc42 document. | the conversion script; `atw-matrix sync-documents` |
| `homeIn`, `partOf` | Today's `stack` and `repository` fields and `contains` links: an entry with a stack takes it; an entry with only a repository takes that repository's stack when it has exactly one, and is otherwise left without a home and listed. | the conversion script |
| `document`, `describedBy` | Every arc42 document in the vault that is effective, in review or draft: front matter, headings, and one `describedBy` per name in `shows` and `subject` that resolves to an entry. | `atw-matrix sync-documents` |
| `epic`, `requirement`, `hasRequirement` | Every open Epic in beads with its PRD file; the `####` headings under `## Requirements`. | `atw-matrix sync-epics` |
| `feature`, `supportedBy`, `realizedBy` | Today's 19 feature entries and their `providedBy`, `realizedBy` and `uses` links, converted. Features derived from PRD requirements are recorded by elaboration. | the conversion script |
| `constraint`, `statedIn`, selectors | arc42 section 2 and the rules in section 8. The `aws-solutions-architect` records one constraint per rule with its heading and selector. | the agent, with `put` and `link` |
| `event`, `publishes`, `consumes`, `imports`, `calls`, `runsIn` | Today's `dependsOn` links, converted to `imports` where the target is held by a stack with `executionUse: imported` and to `calls` where it is a service; the rest are listed for the `aws-solutions-architect`, who records each under its kind. Elaboration and build record the others as they are designed and found. | the conversion script; the agent |
| `servedBy`, `covers`, `appliesTo`, `drives`, `restsOn` | None at seeding. | elaboration and assessment |
| `story`, `task`, `placedIn`, `builds` | Open Story and Task beads: the `repoPath` and `matrix_elements` metadata keys, resolved to a stack through `stacks --repository`. | the second-records script (section 7, slice 33) |
| `disagreement`, `disputes` | Today's disagreement entries whose status is open or settled and not applied. | the conversion script |

## 4. Where the matrix is read and maintained

A step that records does so with `atw-matrix` in the step itself. Where the fact comes from
an agent's result file, a script step of the flow or workflow reads the file and makes the
calls, and the step is done only when `atw-matrix` confirms them. The matrix file is
committed and pushed with `atw-matrix commit --bead <id>` at the end of E9, D8, D9, every
steward operation and seeding.

### Elaboration (`prd-to-spec`, `orchestrator/flows/`)

| Step | Where | Reads | Records |
|---|---|---|---|
| E1 Run start | `prd_to_spec.py` `open_run()`, `_sync_matrix()`; `scripts/portfolio/matrix.py` `_run_sync_prds`, `_run_sync_documents` | none | `sync-epics --bead`: the epic with its PRD path and hash, one requirement per heading, `hasRequirement`. `sync-documents`: document entries with lifecycle and headings, `describedBy` from `shows`, removal of entries for removed documents. `expertise --epic`. |
| E2 Architect | `architecture.py` `architect()` accept; `agents/aws-solutions-architect.md`; `depscore.py` `arch-delta`, `arch-closure`; `archcoverage.py` `coverage_facts` | The brief hands the file `epic <id> --closure --constraints --missing` printed (Q2, Q4, Q5, Q12, Q13). The agent runs `find --kinds feature` (Q3), `find --kinds stack` (Q8), `node`, `deps` (Q6, Q9, Q15). | Per requirement: `servedBy` to each feature, and `covers` with document, heading and `via`. Each new feature, `supportedBy`, `realizedBy`. Each designed service, component, infrastructure and event with `homeIn`, `partOf` and its dependency relationships. A `disagreement` with `disputes`. A claim on each. The accept step compares the result file with `epic <id>` and fails the step on a requirement that is neither served nor listed as having no feature. The delta and closure are read from the matrix and no delta or closure file holds them. |
| E3 Document maintainer | `architecture.py` `maintainer()` accept; `skills/arc42-author/SKILL.md` steps 7 to 9; `depscore.py` `arch-target`, `arch-commit`, `arch-target-remove`, `arch-built-remove` | `story-scope` or `node` for the documents and headings to change (Q18). | `sync-documents --paths <files> --bead <epic>` run by the accept step and by each `depscore.py` command: the new or changed document entries and headings, `describedBy` from `shows`, a claim on each changed heading, removal of entries for removed files. |
| E4 Specialist and placement | `architecture.py` `specialist()` accept, repository-steward role; `agents/polyrepo-steward.md` "placing an element" | `find --kinds stack` (Q8), `node stack:<id>` (Q7, Q10, Q11, Q17). | `homeIn` for the placed entry. A new stack with `name`, `purpose`, `app`, `executionUse`, `repository`. The stack's `purpose` extended when the entry adds to what the stack does. A designed component with its home. |
| E5 TRD author | `architecture.py` `trd_author()` accept; `agents/trd-author.md` | `epic <id> --constraints` (Q5). | One `constraint` per technical requirement with `statedIn` and `appliesTo`. An obligation with no source document is a constraint with no `statedIn`, which Q13 returns under `noSource`. |
| E6 TRD and Spec filed | `trd_authoring.py` `confirm()`, `_mark_trd()`, `document()`; `ops/sdlc-automation/lane.py` `_file_artifacts`, `_vault_metadata` | `document()` checks each cited path and heading with `node document:<path>`. | Nothing. The TRD and Spec paths and digests stay on the Epic and Story beads. |
| E7 Architecture check | `architecture_check.py` `check()`, `_open_review()` | `check`; `review-scope --epic` (the Epic's claims); `epic <id> --missing` (Q13). | Nothing; the claims exist from E2 to E5. |
| E8 Review and ruling | `architecture_review.py` `reviewer()`, `lead()`, `decider()`; `agents/architecture-decider.md`; `agents/architecture-team-lead.md` | The reviewer scope file narrowed from `review-scope`. | `settle --id <disagreement> --stands <document> <heading> --rule <rule>`. The accept step reads the disagreement back and fails the step when `stands` is unset. A review send-back is in the step journal only. |
| E9 Promotion | `architecture_promotion.py` `promote()`, `_approve()`; `depscore.py` `arch-approve` | `review-scope --epic`. | The documents are set effective in their front matter, then `sync-documents --paths` mirrors `lifecycle`. `release --epic` removes the Epic's claims and each disagreement whose losing statement is corrected. `commit --bead` commits and pushes. |
| E10 Repository scoping | `repo_scoping.py` `span()`, `span_items()`, `_work_elements()`, `_ruling()`, `shared_capabilities()` | `epic <id> --closure` (Q12, Q6, Q9, Q14); the stack type (Q11); `uses`. Work for the Epic is the set of entries the Epic claims. | Nothing. An entry with no stack is already in `noStack` (Q13); the step fails naming it and E4 places it. |
| E11 Repository creation | `repo_scoping.py` `create_repositories()`, `_create()` | The stack's `repository` (Q10) and `purpose` (Q7); `polyrepo inventory --name` for the clone path. | `put stack --repository` when the created repository's name differs from the one recorded. `polyrepo create` records the rest (S1). |
| E12 Story and Spec | `spec_authoring.py` `context()`, `story_bead()`, `spec_document()` accept, `story_document()`; `agents/user-story-writer.md`; `depscore.py` `write-story` | `story-scope` for the stack: built entries, documents and headings, constraints, shared capabilities. The stacks outside the Story come from `epic <id> --closure`. | `place --bead <story> --level story --epic <id> --stack <id> --builds <ids>`. One `describedBy` per document heading the Spec cites for a built entry, where absent. |
| E13 Tasks | `task_decomposition.py` `context()`, `write_task()`, `retire()`; `agents/task-decomposer.md`; `depscore.py` `write-task` | `work --stack <id>` (Q19) for other Epics' open work in the stack; `uses`. | `place --bead <task> --level task --story <id> --stack <id> --builds <ids>`, which also adds the ids to the Story's `builds`. `unplace --bead <task>` for each retired Task. |
| E14 Task edges | `task_edges.py` `closure()`, `mapper()` accept, `write()` | The dependency relationships between what the Tasks build (Q9). | A dependency the mapper finds between two stacks that the matrix lacks: `link` of its kind between the stacks. |
| E15 Session setup | `orchestrator/core/skills.py` `epic_expertise()` | `expertise --epic` (Q24) through `atw-matrix`. | Nothing. |

### PRD work and assessment

| Step | Where | Reads | Records |
|---|---|---|---|
| A1 PRD and Epic created | `workflows/prd-creation.js` final result; `agents/prd-writer.md` | none | `sync-epics --bead <id> --prd <path>` once the Epic bead exists: the pair and its requirements (Q1). |
| A2 PRD validation | `workflows/prd-validation.js` Lens 0 | `find --kinds constraint,document --text` and `node` for whether the architecture states a technical rule (Q4, Q5). | A technical rule no document states: a `constraint` with `appliesTo` the epic and no `statedIn`. |
| A3 Epic dependency assessment | `workflows/dependency-assessment.js`; `agents/epic-sequencer.md`; `skills/epic-sequencing/SKILL.md`; `assesscontext.py` `assess_context`; `depscore.py` `apply-edges`, `withdraw-edge` | `related --epic` (Q21); `find --kinds feature,document` for what settles a decision; the named related PRDs. | `drives` and `restsOn` from the epic to the feature or document heading for each decision judged. The Epic-to-Epic edge stays a beads `tracks` edge. |
| A4 Task dependency assessment | `workflows/task-dependency-assessment.js`; `assesscontext.py` `task_context` | `node task:<id>`, `work --stack`, `deps --of` and `deps --on` for the Task's stack (Q19, Q9, Q15). | `place` for a Task that has no placement. A dependency between stacks the matrix lacks. |

### Build (`task-to-deploy` and the driver's build lane)

| Step | Where | Reads | Records |
|---|---|---|---|
| B1 Workspace | `workflows/task-to-deploy.js` `stepWorkspace` | `node task:<id>`: the stack, then its `repository` (Q19, Q10). | Nothing. A Task with no placement fails the step with the `place` call that corrects it. |
| B2 Infrastructure intent | `workflows/task-to-deploy.js` `stepInfraIntent`; `workflows/infra-intent.js` | `node stack:<id>` with what it holds, `deps --of` (Q6, Q9, Q11). | From the intent's result: each new `infrastructure` with `homeIn`, a new stack, and each cross-stack reference as `reads` or `runsIn`. |
| B3 Implementers and Green | `stepSelectImplementers`; `workflows/tdd-green.js`; `agents/cdk-stack-author.md` and the implementer agents | `uses --task` (Q9). | From the implementer result's `upstreamMissing` and `dependencies`: the dependency relationship from the Task's stack or built entry, and an entry with no `homeIn` for a thing that does not exist. |
| B4 Regression | `workflows/task-to-deploy.js` `regressionBrief`, `regressionReviewBrief`; `agents/regression-impact-assessor.md`; `skills/cumulative-regression/SKILL.md` | `impact --bead <task>` (Q20, Q15). | A `realizedBy` the assessor proves missing between a changed component and a feature. The per-repository `regression.json` holds test mappings and execution evidence only. |
| B5 Reuse audit | `stepReuseAudit`, `judgeReuse` | `check-reuse --task --worktree`. | The dependency relationship to each provider the changed files use, where absent. Corrected `useSignals` or `duplicateSignals` on the feature when the reviewer rules the signal wrong. |
| B6 Suite run | `workflows/suite-run.js` `resolvePrompt` | The stack's `commands.test` (Q22). | `commands.test` when the resolving session names it. |
| B7 Commit and Task close | `stepCommit`; `ops/sdlc-automation/lane.py` `_settle_build` | none | Nothing. No mark precedes the Story's verification. |

### Deploy (the driver's `storydeploy.py` and its workflows)

| Step | Where | Reads | Records |
|---|---|---|---|
| D1 Mechanism | `storydeploy.py` `_mechanism_step`, `mechanism_of`; `workflows/deploy-mechanism.js` | The stack's `executionUse`, `distributedAs`, `commands.publish`, `commands.deploy` (Q22). The steward session runs only when one is absent. | The values the steward rules, on the stack. |
| D2 Publish | `storydeploy.py` `_publish_step` | `distributedAs`. | The `package` and `distributedAs`, where absent. |
| D3 Synth and SSM check | `storydeploy.py` `_synth_step`, `_ssm_check_step`, `stacks_in`, `ssm_reads` | none; the assembly is the build's own output. | `record-assembly --tree <worktree> --story <id>`: each stack with its `repository`, infrastructure and Lambda components with `homeIn`, layers with `contains` and `usesLayer`, `routes`, and `reads` for each SSM parameter (a missing parameter is an `infrastructure` entry with no `homeIn`). An entry this Story `builds` that the assembly no longer has is removed. A stack the Story is not placed in is added to its placement. |
| D4 Deploy and stack verification | `workflows/deploy.js`; `storydeploy.py` `_verify_step` | The stack's `commands.deploy` and the stacks of the Story's placement. | Nothing. Passing is a condition of D8 and is in the step journal. |
| D5 Deploy fix | `storydeploy.py` `_fix_step`; `workflows/story-deploy-fix.js` | `node stack:<id>` and `deps --of` for the failed stacks (Q9). | Nothing in the fix itself; the synth that follows runs D3 again, which records added, renamed and removed stacks and infrastructure. |
| D6 Built comparison | `workflows/built-version.js` `stepCompare`; `agents/built-architecture-comparer.md`; `storydeploy.py` `_built_subject`, `built_args` | `story-scope --bead <story>`: what the Story builds and the documents and headings that describe each (Q18). | Nothing. A difference is a file under `built/<subject>/` until D7 corrects the documents in the same run. |
| D7 Built correction | `workflows/built-version.js` correct, conformance and approve steps; `agents/architecture-maintainer.md`; `skills/arc42-maintain/SKILL.md` step 8; `storydeploy.py` `_built_version_step` | `node <entry>` for every document that describes a changed entry (Q18). | `sync-documents --paths <changed files>` by the workflow's script step after approval: the changed and new documents, headings and `describedBy`. |
| D8 Merge and close | `storydeploy.py` `_merge_wait_step`, `_close_step`; `ops/sdlc-automation/matrixmarks.py`; `scripts/portfolio/matrixcode.py` | none | `verify --story <id> --commit <merge commit>`, then `unplace --bead <story> --with-tasks`, then `commit --bead`. A Story with no placement is first placed from the stacks its assembly synthesized. The close step is done only when the three calls succeed. |
| D9 Close with no pull request | `storydeploy.py` `_close_step` | none | `unplace --bead <story> --with-tasks`; no mark. |
| D10 Driver dispatch and dashboard | `ops/sdlc-automation/workitems.py`, `reposcope.py`, `storyorder.py`, `decisions.py` | `epic <id>` for the PRD (Q1); `node story:<id>` and `node task:<id>` for the stack and repository (Q19, Q10); `epic <id> --closure` for the placement view (Q12). | Nothing. |

### Repository work (`polyrepo-steward`, `skills/polyrepo-repo/scripts/polyrepo.py`)

| Step | Where | Reads | Records |
|---|---|---|---|
| S1 Repository created | `polyrepo.py` `cmd_create`, `_create_records` | `stacks --repository` (Q25). | `put stack` for each stack the repository holds: `name`, `purpose`, `app`, `executionUse`, `repository`. The tool makes the call. |
| S2 Repository renamed | `polyrepo.py` `cmd_rename`, `_rename_record` | `stacks --repository <old>`. | `move-repository --from <old> --to <new>`: the `repository` attribute of each stack. No id changes. |
| S3 Repository deprecated or archived | `polyrepo.py` `cmd_deprecate`, `apply_fixes` | `stacks --repository`. | The tool proceeds when the result is empty. The steward first moves each stack (`put stack --repository`) or removes it (`remove stack:<id> --held`). |
| S4 Purpose and grouping | `polyrepo.py` `cmd_purpose`; `agents/polyrepo-steward.md` Judgment | `node stack:<id>`. | `put stack --purpose`; `link` and `unlink` of `homeIn` for a corrected home. |
| S5 Stack created, moved, renamed or removed | `skills/polyrepo-repo/SKILL.md` "The matrix" | `node stack:<id>`. | `put stack` with all five attributes; `rename`; `remove`. |
| S6 Health check | `skills/polyrepo-doctor/SKILL.md`; `polyrepo.py` `cmd_doctor` | `stacks`, `check`. | Findings: a code repository that is the `repository` of no stack; a stack whose `repository` is not an active repository; a failing `check`. With `--fix`, the `put` or `remove` that corrects each. |
| S7 Knowledge scan | `skills/polyrepo-tribal-knowledge/SKILL.md`; `skills/polyrepo-info/SKILL.md` | `find --kinds stack`. | Where functionality lives: a corrected `purpose`, an alias, or a `homeIn`. `.polyrepo/knowledge.yaml` holds pointers to procedures and non-architecture documents only. |
| S8 Answering questions | `agents/polyrepo-steward.md`; `skills/polyrepo-router/SKILL.md`; `commands/polyrepo-steward.md` | Q7 to Q11, Q15, Q17, Q23, Q25. Live git and GitHub state comes from the `polyrepo` tool. | A correction to whatever the answer shows wrong. |

### Every session

| Step | Where | Reads | Records |
|---|---|---|---|
| I1 Shared instruction text | `skills/subagent-contract/SKILL.md`, `agents/aws-solutions-architect.md`, `agents/built-architecture-comparer.md`, `agents/polyrepo-steward.md`, `skills/polyrepo-repo/SKILL.md`, and the preamble bundled into each `workflows/*.js` | The text states the one mark as section 1.4 does, from one shared block under `scripts/shared-blocks`. | Nothing; no agent sets the mark. |

## 5. Replacement list

Each row is one mechanism that finds by scanning something the matrix holds. The change that
introduces the lookup removes what the last column names.

| # | Sites | Does today | Matrix lookup | Removed |
|---|---|---|---|---|
| R1 | `ops/sdlc-automation/workitems.py` `prd_index`, `epic_named_by`, `prds_naming_epics`, `prd_labelled_by`, `find_prd`, `prd_epic_coverage`; `skills/epic-ready/SKILL.md` condition 1 and its two commands; `scripts/portfolio/prds.py` `write_prds`, `write_index` | Globs the PRD folders, reads every PRD for an `**Epic:**` line, reads `prd:` labels, guesses from bead text, or takes the bead description as the PRD. | Q1: `epic <id>`. PRD files no epic names come from the `sync-epics` result. | The glob, the line and label reads, the guess, `prds.py`, and the `**Epic:**` line and `prd:` label as records. |
| R2 | `ops/sdlc-automation/reposcope.py` `recorded_repo`, `repo_hint`, `_hint_sources`; `storyorder.py` `repository_of`; `matrixmarks.py` `_elements`, `_built_mark`; `skills/task-ready/SKILL.md` repoPath marker; `scripts/portfolio/storyedges.py` `repository_of`, `_story_repositories` | Reads the `repoPath` and `matrix_elements` bead metadata keys, a regular expression over bead text, the ancestor Story and Epic, and selects matrix rows by repository basename. | Q19 then Q10: `node story:<id>` or `node task:<id>`. | Both metadata keys, the text patterns, the ancestor walk, the basename selection. |
| R3 | `orchestrator/flows/architecture.py` `architect()` brief with `ARCHITECT_REQUEST`, `_handed_files()`, `add_dirs`, and `specialist()`, `trd_author()`, `maintainer()` through `_helper_dirs()`; `architecture_files.py` `new_context()` `constraintsFolder`; `spec_authoring.py` `author_files()`, `author_dirs()`; `ops/sdlc-automation/workitems.py` `elaboration_args`, `arch_args`, `dispatch_context`; `ops/sdlc-automation/atw.py` `_resolve`, `values`, `environment` | Opens the whole architecture root, the PRD folder, the section 2 folder, a whole repository and the fleet directory for a session to read and decide what is relevant. | Q2, Q4, Q5, Q12, Q13: the script step writes the result of `epic <id> --closure --constraints --missing` or `story-scope` to a file and the brief names the documents and headings in it. | The directory grants beyond the named files, `constraintsFolder`, the request to "establish the state of the architecture", the fleet directory as a place to read. |
| R4 | `orchestrator/flows/repo_scoping.py` `_work_elements()` | Drops elements whose code state is built or deployed. | Q14 and the claim: work is what the Epic claims. | The `CODE_BUILT` and `CODE_DEPLOYED` test. |
| R5 | `orchestrator/flows/repo_scoping.py` `_repository_kind()` and the `frontend` flag in `_ruling()` | Matches the repository name against `templates.kinds[*].name_regex` of `.polyrepo/config.yaml`. | Q11: the stack's type. | The name match on a repository. |
| R6 | `orchestrator/flows/trd_authoring.py` `document()` | Resolves each cited path against the architecture root on disk. | `node document:<path>`: the entry, its headings and lifecycle. | The disk resolution. |
| R7 | `skills/graphrag-lookup/SKILL.md` "Before designing" (loaded by 39 agents); `agents/aws-solutions-architect.md` "Find and reuse before you design" step 1 fallback; the `mcp__mcp-graphrag-server` grant in 20 agents (`agents/api-contract-designer.md` and others) and the `graphrag-lookup` skill in the roster embedded in `workflows/*.js`; `ops/sdlc-automation/mcpconfig.py` `ALLOWED_SERVERS` entry `mcp-graphrag-server` | Searches every repository and the architecture repository for whether a capability exists. | Q3 and Q8: `find --kinds feature`, `find --kinds stack`. An empty result is the answer. | The skill section, the fallback, the tool grants, the skill in agent and roster lists, the server in `ALLOWED_SERVERS`. |
| R8 | `skills/graphrag-lookup/SKILL.md` "Before any change or refactor" | Searches all repositories, then `get_graph` or `find_path` and `git grep` in each. | Q15: `deps --on <id>`, then `git grep` inside the repositories of the stacks returned. | The search, and with R7 the skill; `skills/matrix-lookup/SKILL.md` takes its place in the agents' skill lists. |
| R9 | `agents/aws-solutions-architect.md` "Existing code is a clue and nothing more" and "Build out what remains" | Reads code for hints with no bound on which repositories. | Q6 then Q10: code is opened in the repository of a stack the matrix names for an entry the Epic reaches. | The unbounded instruction. |
| R10 | `agents/polyrepo-steward.md` Ownership and "placing an element"; `skills/polyrepo-info/SKILL.md` "Search — always by precedence" and the search operation; `skills/polyrepo-info/references/search-recipes.md`; `skills/polyrepo-router/SKILL.md` answers list and question table; `skills/polyrepo-repo/SKILL.md` Operations, search; `skills/polyrepo-tribal-knowledge/SKILL.md`; `commands/polyrepo-steward.md`; `agents/root-cause-analyst.md` Scope and Inputs Required | Finds where functionality lives, or which repository owns it, by live search: AGENTS.md, Obsidian, GraphRAG, GitNexus, NotebookLM, ripgrep, `git grep`, `gh`, `polyrepo grep`; stores pointers in `.polyrepo/knowledge.yaml`. | Q8 then Q10; Q23 for a resource type. | The precedence ladder for these questions, the where-it-lives pointers in `knowledge.yaml`, the routing of these questions to `polyrepo grep` and `inventory`. |
| R11 | `agents/polyrepo-steward.md` "What depends on what"; `skills/polyrepo-repo/SKILL.md` paragraph "A record has no dependencies" | Reads effective arc42, maps through the manifest's `owns`, then GraphRAG. | Q9 and Q15: `deps`. | The instruction. |
| R12 | `agents/polyrepo-steward.md` Grouping and placement with `skills/polyrepo-repo/SKILL.md` record fields; `polyrepo.py` `mentions`, `State.confirm_all`; `polyrepo.py` `cmd_inventory`, `cmd_search`, `cmd_list` fields `purpose`, `role`, `owns`, `groups` | Keeps what a repository owns and its purpose in the manifest, and confirms `owns` with `git grep`. | Q25, Q6, Q7: `stacks --repository` with what each holds and its purpose. | The manifest's `owns`, `owns-unconfirmed`, `purpose`, `purpose_head` and `role`, and the `git grep` confirmation. `polyrepo inventory` prints the matrix's values. |
| R13 | `agents/epic-sequencer.md` step 3 with `skills/epic-sequencing/SKILL.md`; `workflows/dependency-assessment.js` step 3; `commands/dependency-assessment.md`; `workflows/prd-validation.js` Lens 0 | Searches the arc42 catalog front matter and section 2 for a view or rule and reads `lifecycle_state`. | Q4, Q5: `find --kinds document,constraint,feature`, then `node`. | The catalog search, the lifecycle read, the section 2 read, the `ARCH_VAR` precondition. |
| R14 | `workflows/built-version.js` `stepCompare` prompt step 1 with `ARCH_MODEL`, `correctTask`, and the conformance review prompt; `skills/c4-diagramming/SKILL.md` "Search the catalog" | Searches every view's `subject` and `shows` in every arc42 section, and `git grep` in the worktree, for the views that show an element. | Q18: `node <entry>`. | The catalog search in the three prompts and the skill. |
| R15 | `scripts/portfolio/archstate.py` `_effective_elements`; `archmatrix.py` `catalog_elements` | Globs `arc42/` and parses `shows` and `subject` of each file. | Q6, Q18: the `describes` relationships. | The glob and `read_catalog` calls. |
| R16 | `scripts/portfolio/archmatrix.py` `row_of`, `satisfied`; `archbaseline.py` `baseline_facts`, `_assess_entry`, `survey_freshness`, `_fingerprint_repositories`, `_fingerprint_paths`; `archcoverage.py` `coverage_facts`; `ops/sdlc-automation/decisions.py` step label `scope:repository-survey` and `_scoping` | Consumes `survey.json`, an agent's survey of code and arc42, fingerprints the repositories it read, and reads a matrix snapshot in an older shape that is never passed. | Q4, Q12, Q13, Q14: `epic <id> --closure --missing`. | `survey.json`, the fingerprints, the snapshot parameter, `satisfied`, the survey step and its rendering. |
| R17 | `scripts/portfolio/assesscontext.py` `assess_context`; `workflows/dependency-assessment.js` steps 4 and 5; `agents/epic-sequencer.md` steps 4 and 5 with `skills/epic-sequencing/SKILL.md` step 4 | Writes a corpus of every open Epic's PRD and an index, greps it, then reads related PRDs. | Q21: `related --epic`, and `find --kinds requirement,feature` for an Epic with no features yet. The named PRDs are then read in full. | The corpus, the index, the grep. |
| R18 | `scripts/portfolio/assesscontext.py` `task_context`, `write_tasks`, `write_task_index`; `workflows/task-dependency-assessment.js` steps 3 and 4; `orchestrator/flows/task_decomposition.py` `context()` with `beadwrite.other_epic_tasks` | Writes every open Task to a file with an index, or loads the whole beads graph, and filters by repository path. | Q19 with Q9 and Q15: `work --stack`, `deps`. | The Task corpus and index, the graph load filtered by `repoPath`. |
| R19 | `agents/architecture-impact-analyst.md` Operating Rules | Lists open Epics and children, reads `decisionIds` and catalog front matter, greps the spec tree. | Q20: `impact --id document:<path>`. | The listing, the front matter reads, the grep. |
| R20 | `skills/cumulative-regression/SKILL.md` "Establish the affected requirements"; `workflows/task-to-deploy.js` `regressionBrief`, `regressionReviewBrief` | Follows component and consumer references through PRDs, specs, architecture, the vault and `regression.json`. | Q20: `impact --bead <task>`. | The reference following, the component-to-requirement map in `regression.json`. |
| R21 | `agents/dependency-graph-extractor.md` Scope | Checks each dependency of a PRD against repository contents and service catalogs. | Q3, Q6: `find`, `node`. | The repository and catalog checks. |
| R22 | `agents/user-story-writer.md` `outOfRepoFindings` | Judges which work lies outside the Story's repository by reading the spec set. | Q12: `epic <id> --closure`. | The judgment by reading. |
| R23 | `workflows/infra-intent.js` provisioning intent prompt; `workflows/deploy.js` deploy prompt; `workflows/story-deploy-fix.js` fix prompt | Works out the stacks, the deploy mechanism and the cross-stack references by reading the repository's CDK code and stack events. | Q6, Q9, Q11, Q22: `node stack:<id>`, `deps --of`. | The instructions to derive them from the repository. |
| R24 | `workflows/deploy-mechanism.js` ask phase; `ops/sdlc-automation/storydeploy.py` `mechanism_of`, `_mechanism_step`, `_usable` | Starts one `polyrepo-steward` session per Story deploy to rule what the repository publishes and deploys. | Q22. | The session when the values are recorded; the mechanism in the step journal as the record. |
| R25 | `ops/sdlc-automation/storydeploy.py` `_built_subject`, `_target_subject`, `built_args`, `_built_items` | Reads the Epic's target file and `recon-<slug>.json` for a subject and items, and passes the whole architecture root. | `story-scope --bead <story>`. | The target and recon reads, the root as an argument. |
| R26 | `workflows/suite-run.js` `resolvePrompt` | One session reads AGENTS.md, CLAUDE.md and the Taskfile for the test command whenever the caller names none. | Q22: `commands.test`. | The session when the command is recorded. |

Sites that stay, each with its reason:

1. `orchestrator/flows/repo_scoping.py` `inventory()`, `_ruling()`, `_ensure_repository()`: the clone path and existence on GitHub are machine facts the `polyrepo` tool holds; the call is one lookup by the name the matrix gives.
2. `orchestrator/flows/prd_to_spec.py` `open_run()`, `_sync_matrix()`: this is the matrix's own upkeep; it reads the vault and beads so later steps read the matrix.
3. `orchestrator/flows/task_edges.py` `mapper()`: ordering of Tasks inside an entry is finer than the matrix holds; what it finds between stacks is recorded (E14).
4. `agents/polyrepo-steward.md` rows for repository count, uncommitted files, last update and currency with main: live git state.
5. `skills/polyrepo-setup/SKILL.md` (listed twice in the inventory): a one-time bootstrap of `.polyrepo/manifest.yaml`.
6. `agents/spec-currency-validator.md`: it checks files and interfaces inside one repository, below what the matrix holds.
7. `agents/filing-clerk.md`: glossary and general vault notes are outside the matrix's kinds.
8. `workflows/documentation.js` audit prompt: READMEs, changelogs and API references are repository documents, not arc42.
9. `ops/sdlc-automation/inventory.py` `_spec_paths`, `_trd_facts`, `_item_documents`, `_filed_documents`: TRD and Spec files are not matrix kinds; their paths are on the beads.
10. `ops/sdlc-automation/mcpconfig.py` GitNexus entry: symbol impact inside the one repository a Task builds in.
11. `ops/sdlc-automation/storydeploy.py` `stacks_in`, `_assembly_reads`, `ssm_reads`, `verify`: they read the assembly this deploy synthesized; what they find is recorded (D3).
12. `ops/sdlc-automation/storydeploy.py` `_excluded_repositories`: two fixed project locations that hold no stack.
13. `scripts/portfolio/archevidence.py` `load_repository_paths`: it reads one handed file of checkout paths; the file's producer is under R3.
14. `skills/polyrepo-repo/scripts/polyrepo.py` `discover`, `gather`, `GitHub`: live reconcile of disk, GitHub and the manifest; it feeds S6.
15. `skills/polyrepo-repo/scripts/polyrepo.py` `cmd_grep`: a general text search for steward upkeep; where-it-lives questions go to R10.

Four sites the inventory marked to stay are on the replacement list, because the matrix
holds what they find: `agents/epic-sequencer.md` steps 4 and 5 (R17), `storyedges.py`
`repository_of` (R2), `task_decomposition.py` `context()` (R18) and `suite-run.js`
`resolvePrompt` (R26).

## 6. The check

`orchestrator/checks/check_matrix_discovery.py` is a deterministic check that
`orchestrator/checks/run_all.py` runs. Its rules are data in
`orchestrator/checks/matrix_discovery.json`. It takes `--driver <path>` (default: the
control repository named by `ATW_CONTROL_REPO` or `SKILLSPOKE_CC`, joined with
`ops/sdlc-automation`) and `--rule <id>` to run one rule. It exits non-zero and prints one
line per finding: rule id, file, line, the matched text.

| Rule group | Inspects | Fails when |
|---|---|---|
| Sites | For each row R1 to R26: the files the row names. Each row lists `absent` patterns: a function or constant name for code, a phrase for instruction text, a key for data. | A pattern is present. A deleted file passes. |
| Scanning instructions | `agents/*.md`, `skills/**/*.md`, `commands/*.md`, the prompt text in `workflows/*.js`, `ops/sdlc-automation/prompts.py`. Two word lists in the data: discovery verbs (search, grep, scan, sweep, glob, "read every", "across every repository", "catalog front matter") and matrix subjects (which repository, where it lives, owns, depends on, `shows`, `subject`, every view, the PRD folder, `prd:` label, `repoPath`). | A sentence contains a verb and a subject and its file and heading are absent from the data's `kept` list. |
| Search grants | Front matter of `agents/*.md`; the roster embedded in `workflows/*.js`; `ops/sdlc-automation/mcpconfig.py`. | `mcp__mcp-graphrag-server` or the `graphrag-lookup` skill is granted. |
| Scanning code | Python under `scripts/portfolio/`, `orchestrator/flows/`, `orchestrator/core/` and the driver, by syntax tree: calls to `glob`, `rglob`, `walk`, `scandir`, and subprocess argument lists that start with `rg`, `grep` or `git grep`. | A call is outside the modules that keep the matrix (`matrixsync.py`, `matrixseed.py`, `matrixassembly.py`) and its file and function are absent from `kept`. |
| Matrix vocabulary | Every file in the plugin and the driver. | Any of these is present: `mark-built`, `mark-deployed`, `mark-merged`, `story-built`, `carry-over`, `CODE_BUILT`, `CODE_DEPLOYED`, a code state of `legacy`, `none`, `built` or `deployed`, `matrix_elements`, `repoPath`, a `repository:` or `term:` entry id, an entry id whose rest begins with a repository name from `stacks`. |
| Direct reads | Every file in the plugin and the driver outside `scripts/portfolio/matrix*.py`. | The matrix file is opened or parsed other than through `atw-matrix` or the `matrixstore` functions. |

`kept` in the data file holds the sites that stay (section 5), each with its file, function
or heading, and reason. A new exemption is a new line there with its reason.

## 7. Moving from today's matrix to this design

Today's file is version 3 with 1,766 entries, ids that embed repository names, an approval
record and a four-state code marker on each row, and no requirement, constraint, event,
package, Story or Task. Each slice below is one file group for one agent. Slices with the
same letter run in parallel once the slices before the letter are done. Python slices prove
themselves with `ruff check`, `ruff format --check` and `mypy --strict` on their files plus
the command shown.

| # | Slice | Files | Proof | Parallel |
|---|---|---|---|---|
| 1 | Kinds registry and schema | `skills/artifact-handoff/schemas/matrix-kinds.json`, `matrix.schema.json`, `skills/artifact-handoff/scripts/generate_matrix_contract.py`, `matrix_contract.py` | `python3 skills/artifact-handoff/scripts/generate_matrix_contract.py --check` | |
| 2 | The check and its rule data, with every rule of section 6 | `orchestrator/checks/check_matrix_discovery.py`, `matrix_discovery.json`, `run_all.py` | The check runs and lists findings for every row R1 to R26. | with 1 |
| 3 | Store: generic entries and relationships, both-end index, registry validation, `rename`, `remove` | `scripts/portfolio/matrixstore.py` | `python3 orchestrator/checks/check_matrix.py` | |
| 4 | Reads: `epic`, `find`, `node`, `deps`, `stacks`, `layers`, `work`, `impact`, `related`, `story-scope`, `uses`, `summary` | `scripts/portfolio/matrixquery.py`, new `matrixtraverse.py` | `check_matrix.py` on a fixture with one of each kind | A |
| 5 | Changes: `put`, `link`, `unlink`, `claim`, `release`, `settle`, `place`, `unplace`, `move-repository`, `commit` | `scripts/portfolio/matrixwrite.py` | `check_matrix.py` | A |
| 6 | `verify`; the three older marks and `story-built` leave | `scripts/portfolio/matrixcode.py` | `check_matrix_discovery.py --rule vocabulary` on the file | A |
| 7 | `sync-epics` with requirements; `sync-documents` with `describedBy`, removal and `--paths` | `scripts/portfolio/matrixsync.py` | `atw-matrix sync-documents` on a scratch matrix, then `check` | A |
| 8 | `record-assembly`, `seed-stacks`, `seed-packages`, `purpose-input`; `matrixcarry.py` leaves | new `scripts/portfolio/matrixassembly.py`, `matrixseed.py`; `matrixcarry.py` | `check_matrix.py` | A |
| 9 | `review-scope` from claims, `check-reuse`, `expertise` | `scripts/portfolio/matrixreview.py`, `matrixreuse.py`, `matrixexpertise.py` | `check_matrix.py` | A |
| 10 | Command table and roles | `scripts/portfolio/matrixcli.py`, `matrix.py`, `matrixcall.py`, `bin/atw-matrix` | `bin/atw-matrix --help` lists the commands of sections 1 to 4 and none of the removed ones | |
| 11 | Convert the data, one script over the whole file: ids without repository names; `repository` rows become the `repository` attribute; `library` rows become stacks with `executionUse: imported` and packages; `prd` rows become `epic`; links become relationships of the new kinds; `legacy`, `none`, approval, status and change fields dropped; retired, deprecated, deferred, `term` and applied `disagreement` rows dropped. Then `seed-stacks`, `seed-packages`, `sync-epics`, `sync-documents`, and `record-assembly` for each repository with a CDK app. | new `scripts/portfolio/matrixconvert.py`; `ops/sdlc-automation/matrix.json` | `atw-matrix check`; `atw-matrix summary` shows no `term` or `repository` kind and no id that contains a repository name | |
| 12 | Stack purposes, in batches of ten stacks; constraints from arc42 sections 2 and 8; the listed `dependsOn` leftovers | `ops/sdlc-automation/matrix.json` through `atw-matrix` | `atw-matrix check`; every stack has a `purpose` | B, one agent per batch |
| 13 | Elaboration: architect, helpers and context (R3; E2 to E5) | `orchestrator/flows/architecture.py`, `architecture_files.py` | `check_matrix_discovery.py --rule R3`; `orchestrator/checks/check_architecture_flow.py` | B |
| 14 | Elaboration: check, review, promotion (E7 to E9) | `orchestrator/flows/architecture_check.py`, `architecture_review.py`, `architecture_promotion.py` | `check_architecture_flow.py` | B |
| 15 | Elaboration: scoping (R4, R5; E10, E11) | `orchestrator/flows/repo_scoping.py`, `repo_placement.py` | `check_matrix_discovery.py --rule R4 --rule R5` | B |
| 16 | Elaboration: Story, Spec and TRD (R3, R6; E6, E12) | `orchestrator/flows/spec_authoring.py`, `trd_authoring.py` | `check_matrix_discovery.py --rule R6`; `orchestrator/checks/check_repo_trd.py` | B |
| 17 | Elaboration: Tasks, edges, expertise (R18; E13 to E15) | `orchestrator/flows/task_decomposition.py`, `task_edges.py`, `orchestrator/core/skills.py` | `check_matrix_discovery.py --rule R18` | B |
| 18 | Portfolio architecture scripts (R15, R16) | `scripts/portfolio/archmatrix.py`, `archstate.py`, `archbaseline.py`, `archcoverage.py`, `resumefacts.py` | `check_matrix_discovery.py --rule R15 --rule R16` | B |
| 19 | Portfolio assessment scripts (R1, R2, R17, R18) | `scripts/portfolio/prds.py`, `assesscontext.py`, `storyedges.py`, `hierarchy.py`, `beadwrite.py`, `scoring.py` | `check_matrix_discovery.py --rule R1 --rule R2 --rule R17` | B |
| 20 | `depscore.py` command wiring for slices 18 and 19 | `scripts/portfolio/depscore.py` | `python3 scripts/portfolio/depscore.py --help`; `orchestrator/checks/check_portfolio_boundaries.py` | |
| 21 | Instruction text, one script over all agent, skill and workflow files: the search grants and the `graphrag-lookup` skill leave every list; the one-mark paragraph replaces the four-state paragraph from one shared block; `matrix-lookup` enters the skill lists | new `scripts/matrix-instructions.mjs`; `agents/*.md`, `scripts/shared-blocks`, workflow preambles | `check_matrix_discovery.py --rule grants --rule vocabulary`; `node scripts/check-agent-types.mjs` | B |
| 22 | The `matrix-lookup` skill: Q1 to Q25 with their commands; `graphrag-lookup` leaves (R7, R8) | new `skills/matrix-lookup/SKILL.md`; `skills/graphrag-lookup/` | `check_matrix_discovery.py --rule R7 --rule R8` | B |
| 23 | Architecture instructions (R9, R14; E2 to E5, D6, D7) | `agents/aws-solutions-architect.md`, `trd-author.md`, `architecture-maintainer.md`, `built-architecture-comparer.md`, `architecture-decider.md`, `skills/arc42-author`, `arc42-maintain`, `arc42-verify`, `arc42/references/finding-views.md`, `c4-diagramming` | `check_matrix_discovery.py --rule R9 --rule R14 --rule instructions` on these files | C, after 21 |
| 24 | Steward instructions (R10, R11, R12; S4 to S8) | `agents/polyrepo-steward.md`, `skills/polyrepo-repo`, `polyrepo-info`, `polyrepo-router`, `polyrepo-tribal-knowledge`, `polyrepo-doctor` SKILL.md files, `search-recipes.md`, `commands/polyrepo-steward.md` | `check_matrix_discovery.py --rule R10 --rule R11` | C, after 21 |
| 25 | The `polyrepo` tool (R12; S1 to S3, S6); the plugin version rises in `plugin.json` and `marketplace.json` in this change | `skills/polyrepo-repo/scripts/polyrepo.py` | `check_matrix_discovery.py --rule R12`; `polyrepo doctor` | C |
| 26 | Sequencing, readiness and regression instructions (R1, R2, R13, R17, R19 to R22) | `agents/epic-sequencer.md`, `architecture-impact-analyst.md`, `dependency-graph-extractor.md`, `user-story-writer.md`, `task-decomposer.md`, `root-cause-analyst.md`, `regression-impact-assessor.md`, `prd-writer.md`, `skills/epic-sequencing`, `epic-ready`, `task-ready`, `cumulative-regression` | `check_matrix_discovery.py --rule R13 --rule R19 --rule R20 --rule R21 --rule R22` | C, after 21 |
| 27 | Build workflows (R20, R23, R26; B1 to B7) | `workflows/task-to-deploy.js`, `tdd-green.js`, `infra-intent.js`, `suite-run.js` | `node scripts/check-workflow-syntax.mjs`; `check_matrix_discovery.py --rule R26` | C, after 21 |
| 28 | Deploy workflows (R14, R23, R24; D1, D4 to D7) | `workflows/deploy-mechanism.js`, `deploy.js`, `story-deploy-fix.js`, `built-version.js` | `node scripts/check-workflow-syntax.mjs`; `check_matrix_discovery.py --rule R23 --rule R24` | C, after 21 |
| 29 | Assessment workflows and commands (R13, R17, R18; A1 to A4) | `workflows/dependency-assessment.js`, `task-dependency-assessment.js`, `prd-validation.js`, `prd-creation.js`, `commands/dependency-assessment.md` | `node scripts/check-workflow-schemas.mjs` | C, after 21 |
| 30 | Driver: verify and Story deploy (R2, R24, R25; B7, D1 to D3, D8, D9) | `ops/sdlc-automation/matrixmarks.py`, `lane.py`, `storydeploy.py` | `python3 orchestrator/check_driver_contracts.py`; `check_matrix_discovery.py --rule R24 --rule R25` | B |
| 31 | Driver: work items (R1, R2; D10) | `ops/sdlc-automation/workitems.py`, `reposcope.py`, `storyorder.py`, `selection.py`, `storyview.py`, `startup.py` | `python3 ops/sdlc-automation/check_entry.py <plugin root>` | B |
| 32 | Driver: environment, MCP configuration, decisions (R3, R7, R16) | `ops/sdlc-automation/atw.py`, `mcpconfig.py`, `decisions.py`, `CLAUDE.md` | `check_matrix_discovery.py --rule R3 --rule R7 --rule R16` | B |
| 33 | Second records, one script: open Story and Task beads placed from `repoPath` and `matrix_elements`, then those keys, the `prd:` labels, the `**Epic:**` lines, the manifest's `owns`, `purpose`, `purpose_head` and `role`, the where-it-lives pointers in `knowledge.yaml` and the component map in each `regression.json` removed | new `scripts/portfolio/matrixrecords.py`; beads, vault PRDs, `.polyrepo/manifest.yaml`, `.polyrepo/knowledge.yaml` | `check_matrix_discovery.py --rule vocabulary`; `atw-matrix work --stack` lists every open Task | after 19, 25, 26, 31 |
| 34 | Close: `matrixconvert.py`, `matrixrecords.py` and `matrix-instructions.mjs` leave; the plugin version rises; the whole check passes | `scripts/portfolio/`, `scripts/`, `plugin.json`, `marketplace.json` | `python3 orchestrator/checks/run_all.py` | |

The installed plugin is updated and running sessions, the pipeline included, are restarted
after slice 34 for the change to take effect.

## 8. Decisions

1. **Storage.** One JSON file with a generic `entries` map and `relationships` list, and the
   kinds in a registry file. Readers are agents and scripts on one machine; a registry makes
   a new kind one declaration and leaves existing data untouched.
2. **Identifiers.** Kind plus the slug of the thing's own name; the beads id for an Epic,
   Story and Task; the path under the architecture root for a document. A thing designed
   before it has a stack needs an id that depends on neither stack nor repository.
3. **Repository and app.** Attributes of a stack, with no entries of their own. A rename or
   a move is then one attribute, which is what R15 requires.
4. **Library.** A stack with `executionUse: imported`; no library kind. Execution use is a
   fact about a stack, so it is recorded as one.
5. **How a PRD requirement is identified.** One `####` heading under `## Requirements`,
   keyed by the identifier that opens it or by the slug of the heading, under the Epic's
   beads id. The PRDs already have this structure, so a deterministic parse yields the same
   ids on every run. When one requirement leaves a group and one arrives, its relationships
   carry over; any other change is reported by `sync-epics` and corrected in that run.
6. **How a similar feature is found.** `find` ranks features by shared words over name,
   aliases, purpose and provided behaviours, and the architect judges the short list. The
   words that led to a match by judgment are added as an alias, so the next lookup is exact.
   Ranking is deterministic, which R2 requires, and needs no added service.
7. **How a stack's purpose is established.** A script collects the facts, the
   `polyrepo-steward` drafts from the code side, and the `aws-solutions-architect` checks
   against the effective architecture. Two independent sources agreeing is what makes it
   trusted; any run that finds it wrong corrects it. No marker distinguishes a checked
   purpose, because no lookup needs one.
8. **Constraints are entries.** One constraint comes from one document and applies to many
   things, and Q5 returns it from either end. A `selector` covers a rule that binds a whole
   class, so section 2 rules need no relationship per stack.
9. **A verified mark when verified code changes.** The mark stays until the next verified
   Story replaces its commit. The code still exists; clearing the mark would tell the
   pipeline it may have to be built.
10. **What a verified Story marks.** The Story's stack, the entries it builds and the
    build-proved relationships that start at them, at the merge commit. A Story is the unit
    that passes CI/CD and CDK, and R24 marks each piece separately.
11. **Concurrent Epics.** Every change is one locked read-modify-write of the file. A change
    to an entry or heading another Epic claims is refused with the holder's id; the step
    records a beads `tracks` edge to the holder and the run resumes after the holder's
    promotion. Adding a relationship to a claimed entry is allowed, because it changes
    nothing the holder designed.
12. **Words in documents.** Dropped, and nothing replaces them. A name a document uses is an
    alias of an entry or a described thing with no stack, which Q13 returns; `find` searches
    real entries.
13. **Disagreements between documents.** An entry while the documents disagree, with the
    ruling once made; removed when the losing statement is corrected. It is not raised again
    because the documents then agree.
14. **Design facts.** No kind. A fact's home is the heading a `describedBy` relationship
    names; its content stays in arc42 (R13).
15. **Approval markers.** Two: the mirrored `lifecycle` and the `claim`. In review for an
    Epic is its claim; nothing is stored after promotion.
16. **Stack types.** The matrix stores none and reads the last token. `check` reports a
    token `resource-naming-standard.md` does not list, and the list is extended there.
17. **A Task's shared capabilities.** Derived by `uses` from what the Task builds, and the
    build checks the changed files with `check-reuse`. Deriving keeps one record; the
    deterministic check catches a duplicate before a reviewer is asked.
18. **Stories and Tasks.** Entries while open, with `placedIn` and `builds`. Verification
    selects by them, and they replace the `repoPath` and `matrix_elements` bead keys.
19. **TRD and Spec files.** Outside the matrix; their paths stay on the beads. The technical
    requirements a TRD states are constraints.
20. **Epic-to-Epic order.** The edge stays a beads `tracks` edge. The matrix records what
    each Epic drives and rests on, from which related Epics are read.
21. **Events.** Entries, so publishers, consumers and rules are found with `node` like
    anything else.
22. **Third-party packages.** Entries only while a layer contains them, with no other
    relationship, so Q16 is one traversal.
23. **Commands of a stack.** The test, publish and deploy commands are attributes, recorded
    by the first run that resolves them. A stable fact is then read, not asked of a session
    for every Story.
24. **CDK facts.** `record-assembly` is the one reader of a synthesized assembly, at seeding
    and at every Story deploy, so stacks, layers, parameter reads and rules are recorded
    with no reasoning.
25. **Cross-repository search.** GraphRAG leaves every pipeline session. The matrix answers
    what exists and what depends on it; text search runs inside the repositories it names.
26. **Committing the file.** `atw-matrix commit` commits and pushes the matrix alone at the
    end of promotion, verification, steward operations and seeding.
27. **Recording by scripts.** Facts in an agent's result file are recorded by a script step
    that confirms the write, so recording does not depend on an agent remembering.
28. **The comparison of built code with architecture.** Not recorded. The same run corrects
    the documents, and the step journal holds a run in progress.
