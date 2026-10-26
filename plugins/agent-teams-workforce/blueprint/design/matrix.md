# The matrix: design

This document states how the matrix meets `blueprint/requirements/matrix.md`: what it holds,
how each lookup is answered, how it is seeded, which pipeline steps read and maintain it,
which discovery mechanisms it replaces, and the slices
that build it and seed it.

Paths are relative to the root of the `agent-teams-workforce` plugin unless they begin with
`ops/sdlc-automation/`, which is the driver in the control repository.

## 1. What is recorded

### 1.1 The file and the kinds registry

The matrix is one JSON file, `ops/sdlc-automation/matrix.json` in the control repository.
Sessions and scripts find it through the `ATW_MATRIX` variable and read and change it only
through `bin/atw-matrix`.

The file holds three members:

| Member | Holds |
|---|---|
| `version` | `4`. |
| `entries` | A map from an entry id to one entry. |
| `relationships` | A list of relationships, each stored once for each side that states it, sorted by `from`, `kind`, `to`, `key`, `side`. |

What kinds exist is data, in `skills/artifact-handoff/schemas/matrix-kinds.json` (the kinds
registry). `skills/artifact-handoff/schemas/matrix.schema.json` validates the generic shape
of the file; `atw-matrix check` validates every entry and relationship against the
registry, and reports every relationship whose `heading` is not a heading its document entry
holds (`matrixstore.heading_problems`). Writes do not run the heading check, because a
document change leaves such relationships behind until whoever recorded them corrects them.
`skills/artifact-handoff/scripts/matrix_contract.py` is generated from both.

The registry declares:

- for each entry kind: its id pattern, its attributes with their types and allowed values,
  and which attributes are required;
- for each declared relationship kind: its name, its reverse name, its attributes, its `key`
  attributes (what distinguishes two relationships of one kind between the same two
  entries), its `family`, its `side` and its `maxPerStart`. No kind names the entry kinds it
  may join: any entry may link to any other (requirement R58);
- `resourceType` (`$defs/resourceType`): the form of the name of one AWS resource kind,
  lowercase words joined by hyphens, checked by the form and not by a list (requirement R61);
- each `atw-matrix` command with the roles that run it (the `ATW_MATRIX_ROLE` variable).

A new kind of entry is one declaration in the registry. A relationship kind is checked by its
form (`matrix.schema.json` `$defs/kindName`, lowerCamelCase letters): one the registry
declares carries its declaration, and any other of that form is accepted with no attributes
and is reported from its end under its name followed by `Reverse` (`matrix_contract`
`relationship_kind`, `relationship_rule`). A reverse name of a declared kind is refused, so the
link is stated from its other end. The store, `put`, `link`, `node`, `find` and `check` work on
any kind, so nothing already held is restructured. A lookup that follows a whole group of relationships selects by `family`, so a
new dependency kind declared with `family: dependency` is followed by Q9 and Q15 with no
change to them.

### 1.2 Entries

Every entry has `id`, `kind`, `name`, `aliases` (other names it is known by) and `purpose`
(one or two sentences that identify it). Any entry may carry `approved` and `verified`, and
none must (section 1.4).

Every entry and every relationship carries `side`, which shows which of the two sides the
fact came from (requirements section 4.1, R43, R45, R50). It is one common field with no
exception by kind. `put` and `link` require it, and every lookup returns it.

- `architecture`: beads, a PRD or an arc42 document states the fact, or the architect
  designed it. This side is the authority. An `epic`, a `requirement`, a `feature` and the
  relationships among them always carry it.
- `repository`: the fact was read from what is in a repository today. It is a hint. It is
  never verified by seeding, and it never replaces or changes an architecture-side fact.

The two sides are kept apart. A thing arc42 describes and the thing found in a repository
are two entries, joined by `correspondsTo` where one corresponds to the other (section 1.3).
A `stack` and a `package` are named by a name both sides use, so each exists once: its
`side` is `architecture` when an arc42 document states it or the architect designed it, and
`repository` otherwise, and a stack's `repository` attribute shows whether a repository
holds it.

An id is the kind, a colon and the rest. The rest is the slug of the entry's name (lowercase
words joined by hyphens) unless the table says otherwise. A repository-side entry of kind
`component`, `infrastructure` or `layer` has the rest `<stack name>/<slug>`, so that it never
takes the id of the architecture-side entry it corresponds to. No id contains a repository
name. An id stays when the name changes; `atw-matrix rename` re-keys an entry and both ends
of its relationships in one write, and for a stack also the repository-side entries it
holds.

| Kind | What one is | Id | Attributes beyond the common ones |
|---|---|---|---|
| `epic` | One Epic with its PRD. | `epic:<beads id>` | `prd` (`path` in the vault, `hash`). |
| `requirement` | One requirement of a PRD: one `####` heading under `## Requirements`. | `requirement:<epic beads id>/<key>`; the key is the identifier that opens the heading (`CHAT-001`), else the slug of the heading. | `group` (the `###` heading above it), `hash` (of the requirement's own text). `name` is the heading text. |
| `feature` | One discrete capability of the product, stated as something it can do ("send an email"), recorded once and unique (requirements section 3.1.1). | `feature:<slug>` | `provides`: for a shared capability, a list of `id`, `behaviour`, `consumersMust`, `interface` (`kind`, `name`), `useSignals`, `duplicateSignals`. |
| `constraint` | One technical requirement or constraint. | `constraint:<slug>` | `statement`; `selector` when the rule applies to every entry of a class. A selector is a set of attribute values (any of `app`, `stackType`, `resourceType`, `executionUse`) that names every entry having those values. |
| `document` | One arc42 document. | `document:<path under the architecture root>` | `lifecycle` (`effective`, `in-review`, `draft`), `section`, `viewType`, `scope`, `subject`, `headings` (the heading texts), `hash`. |
| `service` | One service the architecture describes. | `service:<slug>` | `executionUse`. |
| `component` | One component: a Lambda function, a module, a construct, a page. | `component:<slug>` | `resourceType` when it is one AWS resource (a Lambda function, an AgentCore runtime), `executionUse`. |
| `infrastructure` | One piece of infrastructure: a table, a queue, a rule, an SSM parameter, a bus. An SSM parameter is one entry, named by its path, with `resourceType` `ssm-parameter` and `homeIn` the stack that writes it (requirement R59). | `infrastructure:<slug>` | `resourceType` when it is one AWS resource. |
| `event` | One event type: a fact with a meaning, its name, the services or components that publish it (`publishes`) and its description. On the architecture side its `purpose` is the description the event catalog in arc42 section 6 gives it and its publishers are the catalog's producers, both written by `atw-matrix sync-events`. It has no `homeIn`: its stack is its publisher's architecture-side stack. | `event:<detail type>` | `externalSource`: the system outside SkillSpoke that publishes it (for example Stripe), only for an event no SkillSpoke service or component publishes. |
| `stack` | The home in code of services, components and infrastructure. | `stack:<stack name>` | `repository`, `app` (an open token: lowercase words joined by hyphens, for example `personal-agent`), `executionUse`, `commands` (`test`, `publish`, `deploy`), `epicDriver` (`none`: the owner's decision that the stack is deployed in advance, so no shared item realized or homed in it orders Epics, read by `epicorder.py`). `purpose` is required: why the stack exists, in the form of the example in requirements section 3.3, or the statement that the purpose is not stated. |
| `package` | One Python package. | `package:<distribution name>` | `origin` (`project`, `third-party`). |
| `layer` | One AWS Lambda layer the project deploys. | `layer:<slug>` | none. |
| `file` | A file in a repository that the architecture or design names and that is not a document in the vault, such as a service's saved OpenAPI document. | `file:<stack name>/<path in the stack's repository>` | `path` (required); `homeIn` the stack. |
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

### 1.3 Relationships

A relationship has `kind`, `from`, `to`, the attributes its kind declares, `side`
(section 1.2), and optionally `approved` and `verified` (section 1.4). Any entry may link to
any other; the From → to column below says what each declared kind usually joins and limits
nothing (requirement R58). It is stored once for each side that
states it and indexed from both ends: `atw-matrix node <id>`
returns the relationships that start at the entry under the kind's name and those that end
at it under the reverse name.

| Kind (reverse) | From → to | Meaning | Attributes |
|---|---|---|---|
| `hasRequirement` (`requirementOf`) | epic → requirement | The Epic's PRD states the requirement. | none |
| `servedBy` (`serves`) | requirement → feature | The feature serves the requirement. One feature commonly serves several requirements, of one Epic or of several, and reaches each Epic through them. A feature derived from the architecture that no requirement names has none. | none |
| `supportedBy` (`supports`) | feature → feature | The first feature relies on the second, a supporting capability. | `relies` (ids of the `provides` items relied on) |
| `realizedBy` (`realizes`) | feature → service, component, infrastructure, event, layer, package, stack | The entry implements the feature or provides the capability. | none |
| `describedBy` (`describes`) | feature, constraint, service, component, infrastructure, event, stack, package, layer → document | The document describes the entry. | `heading` (key) |
| `covers` (`coveredBy`) | document → requirement | The document covers this requirement of this PRD. | `heading` (key), `via` (the feature that connects them, key) |
| `statedIn` (`states`) | constraint → document | The constraint comes from this document. | `heading` (key) |
| `appliesTo` (`constrainedBy`) | constraint → epic, feature, stack, service, component, infrastructure, event | The constraint binds the design of the entry. | none |
| `homeIn` (`holds`) | service, component, infrastructure, layer, package → stack | The stack is the entry's home in code. At most one per entry. | none |
| `partOf` (`hasPart`) | component, infrastructure → service | The entry is part of the service. | none |
| `correspondsTo` (`correspondedBy`) | service, component, infrastructure, event, layer → component, infrastructure, layer, stack | The second entry, on the repository side, is what is in a repository today for the first, which arc42 describes. Its `side` is `repository`. | none |
| `distributedAs` (`distributes`) | stack → package | The stack's imported code is published to CodeArtifact as this package. | none |
| `contains` (`containedIn`) | layer → package | The layer carries the package. | none |
| `imports` (`importedBy`) | stack, service, component → stack | Code imports the library the target stack holds. | `through` (the package or layer id that brings it) |
| `usesLayer` (`layerUsedBy`) | component → layer | The Lambda attaches the layer. | none |
| `calls` (`calledBy`) | stack, service, component → service | Code calls the shared service. | `interface` (the operation or API) |
| `publishes` (`publishedBy`) | service, component → event | Code publishes the event. | none |
| `onBus` (`busFor`) | infrastructure → infrastructure | The EventBridge rule (`resourceType` `eventbridge-rule`) belongs to this one event bus (`eventbridge-bus`). At most one per rule. | none |
| `matches` (`matchedBy`) | infrastructure → event | The rule's event pattern matches the event type. A rule whose pattern matches every event on its bus states the attribute `matchesAllEvents` instead. | none |
| `routesTo` (`targetOf`) | infrastructure → service, component, infrastructure | The rule delivers every event it matches to this target. At most five per rule, the EventBridge limit. | none |
| `reads` (`readBy`) | stack, service, component → infrastructure | Code reads a value another stack stored, such as an SSM parameter: an entry of `resourceType` `ssm-parameter` whose home is the stack that writes it. | none |
| `runsIn` (`hosts`) | stack, service, component → infrastructure | Code runs in shared infrastructure, such as a Lambda function in its VPC, subnets and security groups, which another stack holds. | none |
| `drives` (`drivenBy`) | epic → feature, service, component, infrastructure, event, stack, package, layer | On the architecture side, the judgment that the Epic goes first on a shared item, which `epicorder.py` reads: `basis` `owns` (the Epic builds and owns it; the others use it) or `shared` (the Epics share it independently; the Epic merely goes first) and `reason`; at most one with a basis ends at an item. One with no basis is the owner's decision for a whole stack: the Epic owns every shared item realized or homed in it. | `basis` (`owns` or `shared`; required on every `drives` but the owner's decision for a stack), `reason` (required with `basis`) |
| `restsOn` (`supportsEpic`) | epic → feature, document, stack, service, component, infrastructure | The Epic relies on this as settled architecture. | `heading` for a document (key) |
| `specifiedBy` (`specifies`) | infrastructure, component, service → file, document | The entry, such as an API Gateway API, is specified by this file or document heading, such as its saved OpenAPI document. | `heading` for a document (key) |
| `disputes` (`disputedBy`) | disagreement → document | The document holds one of the disagreeing statements, under the heading; the statement's text stays in the document. | `heading` (key) |

`imports`, `usesLayer`, `calls`, `publishes`, `onBus`, `matches`, `routesTo`, `reads` and
`runsIn` have `family: dependency`. A producer publishes through the events API and knows
nothing of rules or targets; a consumer is reached as the target of a rule.

A dependency between two stacks is read, never stored: stack A depends on stack B when a
dependency relationship starts at A or at an entry whose home is A and ends at B or at an
entry whose home is B. A dependency found at stack level, with the entries not yet known, is
recorded with the stacks as its ends.

The matrix records two sides of implementation structure and keeps them apart (requirements
R43 to R46). The architecture side is what arc42 states: the stacks and what each holds, the
layers and the Lambdas that use them, the infrastructure of each resource type in a stack,
and every dependency that crosses a stack boundary. arc42 is the authority for all of it.
The repository side is what is in each stack today: the code, packages, layers and
CDK-defined infrastructure. It is recorded for every stack, with `side: repository` and no
verified flag, as a hint. It never replaces or contradicts an architecture-side fact, and a
difference between the two sides is not a finding and is recorded nowhere. Seeding records
both sides (section 3), and elaboration records what the architect designs or reads
(section 4). No command reads a synthesized CDK assembly, and no build or deploy step adds an
entry or a relationship.

### 1.4 The approved and verified marks

The matrix has two marks, `approved` and `verified`, as requirements section 3.5 and R24 to
R26 and R57 define them. Each is a common member of an entry and of a relationship in
`skills/artifact-handoff/schemas/matrix.schema.json` (`$defs/Approved`, `$defs/Verified`),
not an attribute of a kind, and `Entry.approved`, `Entry.verified`, `Relationship.approved`
and `Relationship.verified` in the generated `matrix_contract.py`. Each is a plain boolean:
an entry or relationship carries `"approved": true` or `"verified": true`, or omits the member,
and absent means not approved and not verified. Neither records who set it: no Epic, stack,
commit or owner. Both are marks on the architecture (architecture entries and the
relationships between them), never on an Epic, a Story or a Task, and architecture moves in
and out of them as it changes. Nothing is seeded with either: a seed result that states one is refused
(`matrixseed._attributes`). No deployed mark and no merged mark exists.

arc42's `effective` is a third thing. A document's `lifecycle` mirrors its front matter
(requirement R22), and `effective` there means the architecture agent responsible for
approving the architecture has approved the document as of now. The approved flag is
similar to it and is not the same: what was seeded from effective arc42 documents is not
approved.

### 1.4.1 The approved mark

`approved: true` says the solutions architect approved the architecture for a feature: an
Epic's architecture and design are approved and the matrix and arc42 are filled out or
corrected for it.

- **What it covers.** The architecture the Epic's elaboration reaches,
  `matrixtraverse.approval_scope(matrix, epic)` without the Epic itself: its requirements, and what
  `rule_reach` reaches from them by the rule of reach that the architecture side states (the
  features that serve the requirements, the entries a serving feature's `realizedBy` names,
  the stack each is or has its home in, and the direct far end of each dependency from those,
  one hop), with every architecture-side relationship that joins two
  of those. The closure (`epic_reach`) is not used: it makes every Epic reach every service.
  The architecture pack lists the same scope (`reach_rows`, each entry with whether it is
  approved, how it is reached and the Epics that share it), and the check holds the
  architect's verdicts to it, so what is reviewed and what is approved are one set.
  Repository-side facts are hints and are not approved.
- **Who sets it.** Only `matrixwrite.approve(matrix, scope, role)`, which refuses every role
  but `script` (`APPROVING_ROLE`) and marks every entry of the scope but an Epic, with the
  relationships between them. The promotion step (`orchestrator/flows/architecture_promotion.py`
  `_promote`) runs it on `approval_scope(matrix, epic)` once the Epic's reviews pass, in the same matrix change that brings the
  promoted documents' entries up to date and removes the settled disagreements, so the
  matrix and arc42 are corrected first. `put` and `link` take attributes only, and no
  `atw-matrix` option states a mark. No session sets it. Two Epics are never elaborated at
  the same time on the same unapproved architecture, because the dependency edges
  `epicorder.py` sets in advance order them, so the promotion runs no check for that case.
- **When it clears.** `Matrix.put` and `Matrix.link` clear it on an entry or relationship
  replaced by one that differs in anything but its flags, and keep it when nothing else
  differs (so `sync-epics` leaves an unchanged requirement approved, and setting `verified`
  leaves `approved` as it is). A change to a stack's `repository` or `epicDriver` attribute alone keeps it: the
  `span` step names the repository after promotion, and the name changes no approved design;
  the owner's decision that a stack is deployed in advance orders Epics and changes no design either. When a document's text changes, only the entries whose
  describing text changed lose it: each `describedBy` names the heading that describes its
  entry, the document entry records a hash per heading (`headingHashes`, the front matter under
  none), and an entry loses the flag when the text under its heading changed; a `describedBy`
  that names no heading is described by the whole document, so any heading's change reaches it.
  The other entries the document describes keep it, and the
  move of a document that was not effective to effective changes no heading text. An
  architecture-side relationship added, changed or removed clears it on the entry it starts
  from. It returns when an Epic that reaches the
  content has its architecture and design approved again.
- **Where it shows.** Every read that returns an entry or a relationship returns it where
  set; `summary` counts it by kind (`approvedByKind`, `approvedRelationshipsByKind`);
  `approval --epic` lists the entries the Epic reaches, approved (under `approved`) and not
  approved (`notApproved`), with the count of the
  relationships between them and of those approved.

### 1.4.2 The verified mark

`verified: true` says the architecture was verified correct because it was built and its test
passed: the entry or relationship was built and tested, the CI checks and the test that its
CDK deployment works included. The deployment may be removed again after that test.

- **When it is set.** The driver runs `atw-matrix verify --story <beads id>`, as the role
  `build-driver`, when the Story's test passes: its deploy to AWS dev was verified working
  (D4) and the CI checks on the Story's branch pass. It runs before, and apart from, the merge of the Story's pull request,
  which follows as a separate step: no merge and no branch decides the flag.
- **What it covers.** Each stack and entry the Story built, as the Task script's `built` read
  returns them for the Story (section 1.5), and every relationship, of any kind and either
  side, that starts at one of them. `built` lists as built the stacks and the entries of the
  kinds a Task builds (`matrixtasks.BUILT_KINDS`: service, component, infrastructure, event,
  package, layer, file); any other id a Task names, such as a shared capability it uses, is
  listed under `notBuilt` and takes no flag, because what a Task only uses was verified when it
  was itself built and tested. The flag belongs to the entry or relationship and holds for
  every Epic that relates to it: it is not set per Epic and waits for no other Story.
- For a stack with no CDK app, the publish of its package to CodeArtifact stands where the
  CDK deploy does. A Story that closes with no pull request runs no `verify`.
- **When it clears.** A known change to what the item must be built as clears it on that item
  alone, as a dirty bit, settled separately from `approved` (one clearing never implies the
  other): `Matrix.put` and `Matrix.link` clear it on an architecture-side entry or relationship
  replaced by one that differs in anything but its flags; a change to the text under the
  heading a `describedBy` names clears it on that entry only; an architecture-side relationship
  added, changed or removed clears it on the entry it starts from. Setting `approved` neither
  sets nor clears it. The next `verify` that covers the item sets it again.
- Entries and relationships an Epic adds are not verified until the build that builds them passes its test. The spec step reads the flag of each
  entry a Story builds to decide what the spec covers (`spec_authoring.entry_scope`).
- `verify` takes no stack, element or repository name. It adds, changes and removes no entry
  and no relationship: the flag is the only thing the build pipeline writes in the matrix
  (requirement R46).

### 1.5 Stories and Tasks

The matrix holds no Story and no Task; beads is the authority for both (R40). The `repoPath`
and `matrix_elements` keys stay on the beads.

A Task states in full what it builds, using the matrix's ids for the stack, the components
and the shared capabilities (R41). Elaboration reads the matrix and writes those ids into
the Task's text and its `matrix_elements` key (section 4, E13).

One script, `scripts/portfolio/matrixtasks.py` (the Task script), answers the three
questions R42 names. It reads Task beads through `bd`: the ids in each Task's
`matrix_elements` key, the Task's status, and its parent Story and Epic. It matches those
ids against the matrix's entries and stores nothing. It runs as three `atw-matrix` commands:

| Command | Task beads read | Returns |
|---|---|---|
| `built --story <beads id>` | The Story's Tasks. | The stacks and entries the Story built, for the verified flag. An id that matches no entry is listed under `unmatched`. |
| `work --id <entry id>` | The open Tasks of every Epic. | The open Tasks that name the entry or, for a stack, an entry the stack holds, each with its Story and Epic. `--not-epic <beads id>` leaves out that Epic's own Tasks, which gives the open work from other Epics. |
| `affected --id <entry id>` | The open Tasks of every Epic. | The open Tasks a change to the entry affects: those that name the entry or anything `impact --id` returns for it (Q19). |

### 1.6 What the matrix leaves out

- Past states: no retired, deprecated, archived or deferred entry, no status value, no
  change stamp, no review send-back, no approval record beyond the approved flag as it stands
  now (section 1.4.1). Git holds history; the step journal holds the run.
- An approval decision on a document: a document's `lifecycle` mirrors its arc42 front matter.
- Design content: a design fact stays under its arc42 heading; the matrix holds the heading.
- Words: no entry exists for a word that appears in a document.
- TRD and Spec files: their paths are on the Epic and Story beads.
- Live repository state (uncommitted files, ahead and behind, archived on GitHub): the
  `polyrepo` tool reads it.
- Stories, Tasks, bead status and Epic-to-Epic `tracks` edges: beads holds them.

## 2. How each lookup is answered

Every command prints one JSON object. Each returned entry and relationship carries `kind`,
`side` and, where set, `approved` and `verified`. A traversal follows the
relationships of both sides, so a result shows what arc42 states and what is in a repository
today, each marked with its side.

| # | Command | Traversal |
|---|---|---|
| Q1 | `atw-matrix epic <beads id>`; `find --kinds epic --prd <path>` | Read the `epic` entry: its `prd.path`. From a PRD path, the one epic whose `prd.path` equals it. |
| Q2 | `epic <id>` | epic → `hasRequirement` → each requirement → `servedBy` → features. A requirement with no `servedBy` is listed under `noFeature`. |
| Q3 | `find --kinds feature --text "<words>"` | Rank features by shared words across `name`, `aliases`, `purpose` and each `provides.behaviour`. Each match is returned with the Epics reached by `serves` → `requirementOf`. An empty result means no such feature exists. Every `find` prints the 10 best matches and `total`, the number that matched; `--limit <n>` prints more, and `--limit 0` prints all. |
| Q4 | `epic <id>` | For each requirement: the `coveredBy` relationships, each with `document`, `heading` and `via`. A requirement and feature pair with no `covers` naming both is listed under `noDocument`. |
| Q5 | `epic <id> --constraints` | Collect the epic, its features and their realizers (Q26's set). Return each constraint with an `appliesTo` to one of them, and each constraint whose `selector` matches one of them, with its id, name, side, `statement` (or `trd`, the pointer to a TRD requirement) and `selector`, its `statedIn` document and heading, and the entries it names with `appliesTo`; then `selections`: each selector those constraints state, once, with the entries it matches and the constraints that state it. A constraint with no `statedIn` is listed under `noSource`. An entry the closure reaches only through a dependency is not asked about: Q19 names its constraints (`constrainedBy`). The solutions architect and trd-author read this one set. |
| Q6 | `node feature:<id>` | feature → `realizedBy` → entries, each → `homeIn` → stack. |
| Q7 | `node stack:<id>` | The stack's `purpose`. |
| Q8 | `find --kinds stack --text "<description>"` | Rank stacks by shared words across `purpose`, `name`, `aliases`, and the names and purposes of the entries each `holds` and the features those realize. |
| Q9 | `deps --of <id>` | From the entry (for a stack, also every entry it `holds`), follow the dependency family outward to any depth. Each result carries the relationship kind, its attributes (`through`, `interface`, `target`) and the stack that holds the target. For `imports`, `through` names the package or layer. |
| Q10 | `node stack:<id>` | The stack's `repository`. |
| Q11 | `node stack:<id>` | `type`: the last token of the stack's name. |
| Q12 | `epic <id> --closure` | epic → requirements → features, with `supportedBy` to any depth. From each feature, the entries reached by `realizedBy` and those reached by `describedBy` → document → `describes`. From each entry, `homeIn` → stack, and `correspondsTo` → what is in a repository for it. Then Q9 from those stacks. Group stacks by `repository`. Each repository is returned with its stacks and the features that lead to each. |
| Q13 | `epic <id> --unlinked` | The links of the Epic with nothing recorded at the other end: `noFeature` (Q2), `noDocument` (Q4), `noSource` (Q5), `noStack` (architecture-side entries reached in Q12 with no holder: no architecture-side `homeIn`; an event is not among them, because its stack is its publisher's), `noRepository` (stacks reached in Q12 with no `repository`) and `noCounterpart` (architecture-side entries reached in Q12 with no `correspondsTo`). |
| Q12/Q13 holders | `Matrix.home(id, side=)`, `matrixtraverse.authority_holder`, `matrixtraverse.holder` | `Matrix.home` reads the architecture side by default and has no fallback; `side=None` reads the architecture side and then the repository side, and only readers that report what the repositories hold pass it. `Matrix.publisher_stacks(event)` maps the event's architecture-side publishers to their architecture-side homes: the one place an event's stack is decided. `authority_holder` is the stack a step that decides what is built reads: for an event, the one publisher stack (none when there are none or several); for any other kind, the architecture-side home. `holder` is the reporting reader: the architecture-side home, then the repository side, then the stack an id names; for an event, `authority_holder`. |
| Q14 | any read | `approved: true` or absent, and `verified: true` or absent, on each entry and relationship returned. |
| Q15 | `deps --on <id>` | From the entry (for a stack, also every entry it `holds`), follow the dependency family inward to any depth, with the same result shape as Q9. |
| Q16 | `layers` | Each `layer` → `contains` → packages, and → `layerUsedBy` → components. |
| Q17 | `node stack:<id>`; `stacks --app <app>` | The stack's `app`; the stacks whose `app` equals the value. |
| Q18 | `node <id>` | entry → `describedBy` → documents, each with `heading` and `lifecycle`. |
| Q19 | `impact --id <id>` | From the entry (for a stack, also every entry it `holds`): `describes` (for a document), `realizes`, `supports` to any depth (for a feature), `constrainedBy`, `supportsEpic`, Q15's dependents, then from every feature reached `serves` → requirements → Epics. For a component, each requirement is returned with its PRD. |
| Q20 | `related --epic <id>` | The Epics that reach any feature, document, stack, service, component or infrastructure this Epic reaches through Q12, `covers`, `drives` or `restsOn`. Each is returned with what is shared and through which relationship. |
| Q21 | `node stack:<id>` | `executionUse`, the `distributedAs` package, and `commands.test`, `commands.publish`, `commands.deploy`. |
| Q22 | `stacks --resource-type <type>` | The stacks that `holds` an entry with that `resourceType`. The type is checked by its form (`matrix_contract.definition_problems`), not by a list. |
| Q24 | `stacks --repository <name>` | The stacks whose `repository` equals the name. |
| Q27 | `resources --epic <id>` | Q12's walk (`epic_reach`): the entries the Epic's features lead to, what is in a repository for each, and the far end of every dependency of their stacks, with every entry the Epic links to itself. Each entry that states `resourceType` is returned with its stack (`holder`) and that stack's `repository`; `stacks` groups them by stack; `noStack` lists those no stack holds. |
| Q28 | `parameters --stack <id>` | `writes`: each entry the stack holds whose `resourceType` is `ssm-parameter`, with each `readBy` relationship and the reader's stack and repository. `reads`: each `ssm-parameter` the stack or an entry it holds reads, with the stack that writes it. |
| Q29 | `documents --id <id>` | The entry, every entry that is `partOf` it to any depth and, for a stack, what it holds; every `document` or `file` any relationship of either direction joins to one of them, once, with its `lifecycle` and the relationships that join it. |
| Q30 | `links --id <id> [--depth <n>] [--direction out\|in\|both] [--kinds <k,...>]` | Breadth first from the entry over every relationship (or the kinds named), outward by default, to any depth unless `--depth` bounds it; each entry is reached once and each relationship followed is returned with its depth, the direction and the far end. |
| Q25 | `summary --unlinked` | `noArchitecture`: over the whole matrix, the entries with `side: repository`, of the kinds read from a repository (`matrixquery.FOUND_KINDS`: component, infrastructure, layer, stack), that no `correspondsTo` ends at. It is the other direction of Q13's `noCounterpart`. |
| Q26 | `epic <id> --realizers` | For each feature that serves one of the Epic's requirements, the ends of its `realizedBy` relationships; a feature reached only through `supportedBy` is not listed. Each realizer is returned once with its stack (`holder`: the architecture-side home, else the repository-side home), that stack's `repository`, its `resourceType` when it has one and, for an event, its publishers; `noStack` lists the realizers with no stack on either side. |
| Approval | `approval --epic <id>` | `matrixtraverse.approval_scope`: the Epic, its requirements and every architecture-side entry it reaches by the rule of reach, with the architecture-side relationships between them. Each entry is returned under `approved` (with `kind` and `name`) when it carries `approved`, otherwise under `notApproved`; `relationships` and `approvedRelationships` count the relationships (section 1.4.1). |
| Shared items | `shared-items [--epic <id>]` | `matrixshared.shared_items`: every feature that serves a requirement of two or more Epics and every architecture-side service, component, infrastructure, event, stack, package or layer entry two or more Epics reach by the rule of reach, walked per requirement (`matrixtraverse.requirement_reach`), each with the Epics that need it and the requirements through which each does, whether its architecture is approved, its stack, whether that stack is deployed in advance (`epicDriver: none`), and its decision: the judgment (`drives` with a basis to the item) or the owner's decision for its stack (`drives` with no basis to the stack). |
| Judging batches | `shared-items --batches <folder> [--batch-size <n>]` | `matrixshared.write_batches`: the unapproved shared items no record decides and no stack deployed in advance holds, grouped by identical sets of Epics, packed into batches of about `n` items (25 by default) without splitting a group, each item with its id, kind, name, purpose, stack and Epics with their requirement ids, each batch with the text of every requirement it names once (read from the PRDs under the vault of `--prd-dir`), and `index.json` with the counts. It reads the matrix only. |

`record-judgments --file <path>` (role `script` or `operator`) records a judgment file
(`shared-item-judgments.schema.json`) in one locked update: each judgment becomes the one
architecture-side `drives` with a basis from its Epic to its item, replacing another Epic's
earlier judgment for the item; the whole file is refused when an item is not shared, its Epic
does not need it, or the owner's decision for its stack decides it. `Matrix.problems` refuses
two `drives` with a basis to one item, a `drives` with a basis and no reason, and a `drives`
with no basis that does not end at a stack. A change to the item leaves its `drives` as it is,
since a relationship that ends at an entry is neither cleared nor removed when the entry changes.

Three further reads serve single steps. `uses --ids <entry ids>` returns the shared
capabilities the work that builds those entries must use (entries → `realizes` → features →
`supportedBy` to any depth → features with `provides`, each with its `realizedBy` provider
and that provider's stack). `story-scope --stack <id> --ids <entry ids>` returns in one
object the stack and its repository, the documents and headings that describe each entry
(Q18), the constraints that apply (Q5) and the shared capabilities (`uses`).
`review-scope --epic <id>` returns the documents the Epic's requirements and features reach
through `covers` and `describedBy` whose `lifecycle` is not `effective`, each with the
headings reached (Q4, Q18).

The three questions about Stories and Tasks are answered by the Task script (section 1.5)
and by no lookup in this table.

Every lookup reads the matrix file and nothing else. What Q6, Q9, Q12, Q15, Q16 and Q22
return about stacks, layers, infrastructure and cross-stack dependencies is what seeding and
elaboration recorded on the two sides: what arc42 states, which is the authority
(requirement R43), and what is in a repository today, which is a hint (requirement R45).
Each result carries its side. No lookup reads a repository's code or a synthesized assembly.

## 3. Seeding

Seeding fills an empty version 4 file from four sources: beads, the PRDs, the effective arc42
documents and the repositories. It records the four things requirement R47 names, on both
sides (requirements R43, R45, R50), with every link between them that can be established now
(requirement R48). A link that cannot be established from what exists today is left out, and
Q13 returns it as having nothing at the other end; nothing is invented to fill it
(requirement R49). Every seeded entry and relationship is unverified (requirement R51).
Seeding deploys nothing, runs no `cdk` command and reads no synthesized assembly. It is
complete before the first pipeline run uses the matrix (requirement R27).

Work that needs no reasoning is one script over all the files (section 3.1). Reasoning work
is done by the fewest agents that keep each under about 30% of its context, in parallel
across different inputs (section 3.2). An agent records nothing with `put` or `link`
itself: it writes one result file for its batch, and a script step records the file and
confirms the writes (decision 26). Two agents that describe the same thing under the same
name then land on one entry, and no agent spends a turn per entry.

What seeding reads, measured on 2026-10-13 with read-only commands:

| Source | Count | Size |
|---|---|---|
| Open Epics in beads | 127, every one with a `prd:` label that names a PRD file in the vault | The 127 PRDs are 2.48 MB, 20 KB each on average, and hold 1,103 requirement headings. |
| arc42 documents | 179, every one effective; none in review or draft | 2.07 MB: section 5 has 48 documents, section 6 has 27, section 7 has 15, section 8 has 80, and the other sections have 9. 174 state a `subject`, and 139 subjects are distinct. |
| Repositories in `polyrepo inventory` | 65: 54 active, 9 planned, 2 deprecated. By app: 41 `personal-agent`, 17 `shared`, 4 `marketing`, 3 `employer`. | 24 of the 63 that are not deprecated hold under 20 KB of source. |

`polyrepo inventory` lists repositories. It lists no stack: a repository's record holds its
name, its app (`space`), its path and its lifecycle, and `owns` is empty in every record. A
stack is therefore taken from the repository's name (P4).

An agent's reading allowance is taken as 240 KB of text (about 60,000 tokens, 30% of a
200,000-token context). The batch counts below follow from the measured sizes and that
allowance, and `seed-inputs` computes them again from the sizes it finds.

The repositories under `apps/marketing` are read like every other known repository, so that
their stacks are recorded. No seeding script or agent edits a repository.

### 3.1 Script steps

`atw-matrix seed` (`scripts/portfolio/matrixseed.py`) runs P1 to P6 once, in order, each
over all of its inputs. P7 is the same script's recording step, and P8 (`seed-realizers`) writes
the batches of G4 once G1 and G3 are recorded.

| Step | Reads | Records |
|---|---|---|
| P1 Empty file | Nothing. | A version 4 file with no entry and no relationship. |
| P2 `sync-epics` | Every open Epic in beads and its PRD file, found by the Epic's `prd:` label: the `####` headings under `## Requirements`. | One `epic` with its `prd` path and hash, one `requirement` per heading, and `hasRequirement`. An open Epic with no PRD file gets no `prd` and is listed in the result. |
| P3 `sync-documents` | Every arc42 document in the vault that is effective, in review or draft: front matter and headings. | One `document` with `lifecycle`, `section`, `viewType`, `scope`, `subject`, `headings` and `hash`, with `side: architecture`. It reports under `staleHeadings` each relationship that names a heading an added or changed document no longer has, and leaves it in place. |
| P4 `seed-stacks` | `polyrepo inventory`: the name, app and lifecycle of every known repository. | One `stack` per repository that is not deprecated and whose name ends in a type `resource-naming-standard.md` lists. The stack takes the repository's name as its `name`, with `repository`, `app` and `executionUse` (`imported` when the type is `lib`, otherwise `executable`), `side: repository` and the purpose not stated. A repository whose name ends in no listed type gets no stack and is listed in the result. |
| P5 `seed-packages` | `[project].name` and `[project].dependencies` of the `pyproject.toml` of each stack's repository. | One `package` (`origin: project`) with `distributedAs` from each stack whose `executionUse` is `imported`, and one `imports` from a stack to the stack that holds each project package it depends on, with `through` naming the package. All carry `side: repository`. A third-party dependency is not recorded (requirement R17). |
| P6 `seed-inputs` | The entries P2 to P5 recorded and the sizes of the files behind them. | No entry. It writes the batch files for section 3.2, each filled up to the reading allowance. The arc42 documents are grouped by `subject`, so that every document about one subject is in one batch, and then by arc42 section. The PRDs are packed to two thirds of the allowance, which leaves room for what `find` returns. A stack counts as its source size up to 40 KB, because a session reads a stack's CDK app, its handler entry points and its file listing and not every source file. |
| P7 `seed-apply` | The result files the sessions of section 3.2 write. | Every entry and relationship in each file, through the store's `put` and `link`, with the side the step states. It adds to an entry that already exists. It is run after each agent step and reports each write it could not make. |
| P8 `seed-realizers` | The features G3 recorded with their requirements, document headings and current `realizedBy`, the architecture-side entries the same headings describe, and the sizes of those documents. | No entry. It writes the batch files of G4, the features grouped by the first document that describes each and filled up to the reading allowance. It runs after G1 and G3 are recorded, because it lists what they recorded. |

### 3.2 Agent steps

Each step is run by `aws-solutions-architect` sessions, one per batch file, in parallel. A
session reads only what its batch names and what the matrix returns for it, and writes one
result file. `seed-apply` (P7) records the result files of a step when its sessions are
done. The Agents column is the number of sessions at the measured sizes.

| Step | Runs after | One agent per | Agents | Reads | Result file, which `seed-apply` records |
|---|---|---|---|---|---|
| G1 Architecture side | P6 | batch of effective arc42 documents: about 20 documents and 230 KB | 9 | The documents of the batch, and `stacks` for the stack names P4 recorded. | All with `side: architecture`: every `service`, `component`, `infrastructure`, `event` and `layer` each document describes, with `resourceType` and `executionUse`; `describedBy` with the heading for each; `homeIn` to the stack the document says each is in; that stack when P4 did not record it, and `side: architecture` on a stack a document states; a `feature`, with `describedBy` and its heading, for each discrete capability a document states the product has (requirements section 3.1.1), named as something the product can do, whether or not a requirement names it; the stack's `purpose`, why the stack exists, in the form of the example in requirements section 3.3, where a document says it; `partOf`; `contains` and `package` (`origin: third-party`) for what a layer carries, and `usesLayer`; every dependency across a stack boundary the document states, under its kind (`imports`, `calls`, `publishes`, `onBus`, `matches`, `routesTo`, `reads`, `runsIn`); one `constraint` per rule in arc42 section 2 and section 8, with `statedIn`, its heading, and its `selector` or `appliesTo`; a `disagreement` with `disputes` where two statements in the batch disagree. A thing whose stack the document does not say gets no `homeIn`. |
| G2 Feature proposals | P6 | batch of PRDs: 8 PRDs, about 160 KB and 70 requirements | 16 | The PRDs of the batch; `find --kinds feature --text` for a feature the matrix already holds; `find --kinds document --text` for each feature, which returns each matching document with its subject and headings. A document is opened only where its headings do not settle whether it covers the feature. | One proposal file per PRD, which `seed-apply` does not record: for each requirement, the feature or features that serve it, each a discrete capability as requirements section 3.1.1 defines one, with a name that states what the product can do and a purpose, and for each feature the arc42 documents and headings that cover it. A feature the matrix already holds (`find --kinds feature --text`) is proposed under that feature's name. A requirement that states a condition, quality or rule about how capabilities behave (empty, loading and error states, accessibility, who may see data, confidence grading, latency, privacy, security, retention, audit) is given the feature of each capability it constrains and no feature of its own, and a name that joins two capabilities different parts of the architecture provide is proposed as two features (`matrixseed.FEATURE_IS`, `PROPOSAL_HOLDS`). A requirement for which no feature is found, and a feature for which no document is found, is written with none. |
| G3 Features recorded once | G1, G2 | all proposal files | 1 | One line for each proposed feature, its name and its purpose, which `seed-features --list` prints from every proposal file; `find --kinds feature --text` for the features the matrix already holds. | A merge file that maps each proposed feature to the feature it is, by the working test of requirements section 3.1.1 (`matrixseed.MERGE_HOLDS`): proposals that name the same capability, one the same part of the architecture provides, are one feature, and a shared subject, screen, channel, document or Epic is no reason to merge; a proposal that bundles capabilities different parts of the architecture provide is split, listed under `proposed` of each feature it bundles; a proposal that is a condition, quality or rule is listed under `proposed` of the feature of each capability it constrains. A proposed feature that is a feature the matrix already holds, from G1 or an earlier run, takes that feature's name, so that it is recorded once. `seed-apply` then records from the proposal files and the merge file: each `feature` once; `servedBy` from every requirement it serves, across PRDs, a split proposal serving its requirements through each feature it is split into; `describedBy` from the feature to each covering document and heading; `covers` from the document to the requirement, with `heading` and `via`. |
| G4 Realizers | G1, G3 | batch of features, grouped by the first document that describes each and filled to the reading allowance; `seed-realizers` writes the batches once G1 and G3 are recorded | 6 | Each feature of the batch with the requirements it serves, the document headings that describe it, its candidates (the architecture-side entries the same headings describe) and what already realizes it; the documents named; `find --kinds service,component,infrastructure,event,layer,package,stack --text` and `node` for the entries that realize each feature (`matrixseed.REALIZER_HOLDS`). | `realizedBy` from each feature to every architecture-side service, component, infrastructure entry, event, layer, package or stack that provides its capability, alone or with others; no entry. `seed-apply --step realizers` records each with `side: architecture` and refuses any other relationship and any entry. |
| G5 Repository side | G1 | batch of stacks: about 9 stacks | 7 | `node stack:<id>` for each stack of the batch, and in the stack's repository its CDK app, its handler entry points, its `pyproject.toml` and its file listing. | All with `side: repository`: what is in the stack today, at the grain arc42 describes things, as `component` entries for its Lambda functions and pages, `layer` entries with `contains`, and `infrastructure` entries for what its CDK code defines, each with `homeIn`; the dependencies across a stack boundary that its code shows, under their kinds; `correspondsTo` from each architecture-side entry of the stack to the thing found for it, where one exists. On the stack entry: the `commands` the repository itself declares, a command it does not declare staying empty. No entry is recorded for a module or a construct. README files are not accurate and are not a source. |
| G6 Close | G4, G5 | none; a script step | 0 | Nothing. | `atw-matrix check`, then `atw-matrix commit`. |

Seeding uses 39 agent sessions in all. A stack no arc42 document gives a purpose for keeps
the purpose not stated.

`supportedBy` and `appliesTo` to an Epic are judgments of elaboration and are not seeded.

## 4. Where the matrix is read and maintained

A step that records does so with `atw-matrix` in the step itself. Where the fact comes from
an agent's result file, a script step of the flow or workflow reads the file and makes the
calls, and the step is done only when `atw-matrix` confirms them. The matrix file is
committed and pushed with `atw-matrix commit --bead <id>` at the end of E9, D8, every
steward operation and seeding.

Elaboration, assessment and repository work record facts. Elaboration and assessment record with `side: architecture`, and repository work with `side: repository` (section 1.2). The build and deploy steps read
the matrix and record nothing in it except the verified flag at D8 (requirement R46). A
build or deploy step that finds the code different from what the matrix states reports the
difference in its result and the step journal; the built comparison (D6, D7) corrects the
arc42 documents, the next run's E1 mirrors them, and the architect records what they state
(E2).

### Elaboration (`prd-to-spec`, `orchestrator/flows/`)

| Step | Where | Reads | Records |
|---|---|---|---|
| E1 Run start | `prd_to_spec.py` `open_run()`, `_sync_matrix()`; `scripts/portfolio/matrix.py` `_run_sync_prds`, `_run_sync_documents` | none | `sync-epics --bead`: the epic with its PRD path and hash, one requirement per heading, `hasRequirement`. `sync-documents`: document entries with lifecycle and headings, `describedBy` from `shows`, removal of entries for removed documents. |
| E2 Architect | `architecture.py` `architect()` accept; `agents/aws-solutions-architect.md`; `depscore.py` `arch-closure`; `archcoverage.py` `coverage_facts` | The agent reads the PRD it is handed in full; the matrix and arc42 are its starting point, input and output, possibly incomplete or wrong and normally empty for an Epic no earlier step has reached. The brief hands no file from the matrix: the agent reads the Epic live, `epic <id>` (Q2, Q4), `epic <id> --realizers` (Q26, with `noStack`) and `epic <id> --constraints` (Q5), so nothing it reads drifts from the matrix it writes to. The agent runs `find --kinds feature` (Q3), `find --kinds stack` (Q8), `node`, `deps` (Q6, Q9, Q15). Before it designs a change to something that exists it runs `impact --id <id>` for what rests on it (Q19) and `related --epic <id>` for the other Epics that share it (Q20). The links with nothing recorded at the other end (Q13) are one input to its judgment and are not the design task. | What the architect decides the architecture should be, so that it does everything the current architecture does and also meets the Epic's requirements. That is its design judgment and no command computes it. For a given requirement the outcome is nothing (what exists already meets it), something new, or a change to something that exists. Per requirement: `servedBy` to each feature, and `covers` with document, heading and `via`. Each new feature, `supportedBy`, `realizedBy`. Each service, component, infrastructure and layer the architect designs or changes, or reads in an effective arc42 document when the matrix does not hold it, with `homeIn`, `partOf`, `contains` and its dependency relationships. Each event, after it and its producers are written into the arc42 event catalog, with `atw-matrix sync-events` (its purpose and its `publishes`), or with `put event --external-source` for an event published outside SkillSpoke; never `homeIn`. A `disagreement` with `disputes`. The result's `addedOrChangedElements` and `unchangedWorkElements` name what the Stories build: the elements the design adds or changes, and the existing elements it leaves unchanged where the Epic has work. The accept step compares the result file with `epic <id>` and fails the step on a requirement that is neither served nor listed as having no feature, when both lists are empty, and on each problem `repo_scoping.story_build_problems` reports for each of the two lists. |
| E3 Document maintainer | `architecture.py` `maintainer()` accept; `skills/arc42-author/SKILL.md` steps 7 to 9; `depscore.py` `arch-target`, `arch-commit`, `arch-target-remove`, `arch-built-remove` | `node` for the documents and headings to change (Q18). | `sync-documents --paths <files> --bead <epic>` run by the accept step and by each `depscore.py` command: the new or changed document entries and headings, `describedBy` from `shows`, removal of entries for removed files. |
| E4 Placement and repository work | `agents/aws-solutions-architect.md` "Placing each element in a stack and a repository"; `orchestrator/flows/repo_scoping.py` `span` | After the detailed design: `epic <id> --realizers` for `noStack` (Q26), `find --kinds stack` (Q8), `node stack:<id>` (Q7, Q10, Q11, Q17). | The solutions architect, on the architecture side: a new stack with `name`, `app`, `executionUse`, `repository` (only when the repository that holds it exists; left out for one yet to be created, which `span` names with the naming command) and `purpose`, then `homeIn` for each service, component, piece of infrastructure and layer the design adds or changes that has no stack, and for each in `noStack`, so that E10 finds none. No event is placed: its stack is its publisher's. The `span` step then creates each repository that does not exist with `polyrepo create`, which records no second stack. |
| E5 TRD author | `architecture.py` `trd_author()` accept; `agents/trd-author.md` | `epic <id>` (Q2: the PRD requirement headings it reads) and `epic <id> --constraints` (Q5), the set the architect reads; for the TRD initial write, before the architect starts, `find --kinds document,constraint` and `node document:<path>` for the requirements pre-written in arc42. | One `constraint` per technical requirement, recorded from trd-author's answer: its `trd` pointer (the Epic and the requirement id, a heading of the TRD) in place of a statement, so the text stays in the TRD alone, with `statedIn` and `appliesTo`; a removed requirement's constraint is removed. An obligation with no source document is a constraint with no `statedIn`, which Q13 returns under `noSource`. |
| E6 TRD and Spec filed | `trd_authoring.py` `confirm()`, `_mark_trd()`, `document()`; `ops/sdlc-automation/lane.py` `_file_artifacts`, `_vault_metadata` | `document()` checks each cited path and heading with `node document:<path>`. | Nothing. The TRD and Spec paths and digests stay on the Epic and Story beads. |
| E7 Architecture check | `architecture_check.py` `check()`, `_open_review()` | `check`; `review-scope --epic` (Q4, Q18); `epic <id> --unlinked` (Q13). | Nothing. |
| E8 Ruling | `architecture_ruling.py` `lead()`, `decider()`, `_disagreements()`; `agents/architecture-team-lead.md`; `agents/architecture-decider.md` | The check step plans the lead only when the architect's result lists a matter it could not settle; nothing reviews the architect's work, which the architect reviews and approves itself. The lead reads the architect's result. The decider reads `node disagreement:<id>` for the statements a disagreement disputes and `node document:<path>` for a document's `lifecycle`. | `settle --id <disagreement> --stands <document> <heading> --rule <rule>`, by the decider. Its accept step reads back the disagreements the question is about and fails the step when `stands` is unset. The lead's routing is in the step journal only. |
| E9 Promotion | `architecture_promotion.py` `promote()`, `_promote()`; `matrixwrite.approve`; `depscore.py` `arch-approve` | `review-scope --epic`. | The documents are set effective in their front matter, then `sync-documents --paths` mirrors `lifecycle`. `remove` for each disagreement settled in this run whose losing statement is corrected. The Epic's review log is filed in the vault at `<architectureRoot>/review-logs/<epic>.json`, and in the same matrix change the Epic entry's `reviewLog` attribute records its path and hash. Then, in the same matrix change, the approved mark on the architecture the Epic reaches (section 1.4.1). `commit --bead` commits and pushes. |
| E10 Repository scoping | `repo_scoping.py` `span()`, `story_builds()`, `story_build_problems()`, `repository_name()`, `_ruling()`, `shared_capabilities()` | The architect's result (`addedOrChangedElements` and `unchangedWorkElements`, the existing elements the architect names as where the Epic's work that leaves them unchanged lands); per entry its `authority_holder` and that stack's `repository`, its `describedBy`, an event's architecture-side publishers, and the architecture-side dependency relationships between the entries; the stack type (Q11); the naming rules for a stack with no `repository`; `uses`. | The `repository` the naming rules give a stack a Story builds in that names none (architecture side), which keeps the stack's approved flag; then `commit --bead` commits and pushes. The step fails on each `story_build_problems` sentence. |
| M1 Event checks | `matrixstore.Matrix._event_problems()` in `problems()` (`atw-matrix check` and every write); `matrixwrite._side_kept`, `matrixwrite.unlink` | Each architecture-side event. | Nothing. A problem for an architecture-side event that states `externalSource` and has an architecture-side publisher; that has neither; or whose publishers are homed in more than one stack, unless one is in a stack whose `executionUse` is `imported` (skipped until the owner rules). A repository-side put that states `externalSource` on an architecture-side event is refused, and unlinking the last architecture-side publisher of an event with no `externalSource` is refused. |
| E11 Repository creation | `repo_scoping.py` `create_repositories()`, `_create()` | The stack's `repository` (Q10) and `purpose` (Q7); `polyrepo inventory --name` for the clone path. | `put stack --repository` when the created repository's name differs from the one recorded. `polyrepo create` records the rest (S1). |
| E12 Story and Spec | `spec_authoring.py` `context()`, `story_bead()`, `spec_document()` accept, `story_document()`; `agents/story-bead-writer.md`; `depscore.py` `write-story` | `story-scope` for the stack and the entries the Story builds: documents and headings, constraints, shared capabilities. `documents --id` (Q29) for every architecture and design document of the stacks and entries, which every spec links to. Each entry's verified flag (Q14) for what the spec covers: a verified entry needs no work to match its architecture; a not-verified entry needs the work that brings its build, from the code already there, up to the approved architecture. The stacks outside the Story come from `epic <id> --closure`. | One `describedBy` per document heading the Spec cites for an entry the Story builds, where absent. Nothing for the Story itself: beads holds it (R40). |
| E13 Tasks | `task_decomposition.py` `context()`, `write_task()`, `retire()`; `agents/task-decomposer.md`; `depscore.py` `write-task` | `work --id <stack id> --not-epic <epic id>` for other Epics' open Tasks that touch the stack (R42); `uses --ids` for the shared capabilities of the entries each Task builds. | Nothing in the matrix. `write-task` writes into each Task the ids of its stack, its components and its shared capabilities, in its text and its `matrix_elements` key (R41). |
| E14 Task edges | `task_edges.py` `closure()`, `mapper()` accept, `write()` | The dependency relationships between what the Tasks build (Q9). | A dependency the mapper finds between two stacks that the matrix lacks: `link` of its kind between the stacks. |

### PRD work and assessment

| Step | Where | Reads | Records |
|---|---|---|---|
| A1 PRD and Epic created | `workflows/prd-creation.js` final result; `agents/prd-writer.md` | none | `sync-epics --bead <id> --prd <path>` once the Epic bead exists: the pair and its requirements (Q1). |
| A2 PRD validation | `workflows/prd-validation.js` requirement-class lens (`agents/requirement-classifier.md`) | `find --kinds constraint,document --text` and `node` for whether the architecture states a technical rule (Q4, Q5). | A technical rule no document states: a `constraint` with `appliesTo` the epic and no `statedIn`. |
| A3 Epic dependency assessment | `workflows/dependency-assessment.js`; `agents/epic-dependency-assessor.md`; `skills/epic-sequencing/SKILL.md`; `assesscontext.py` `assess_context`; `depscore.py` `apply-edges`, `withdraw-edge` | `epic` for the features the Epic needs; `related --epic` (Q20); `node` for the requirements each feature serves and whether its realizers carry the `approved` mark. | Nothing. The Epic-to-Epic edge is a beads `tracks` edge. |
| A4 Task dependency assessment | `workflows/task-dependency-assessment.js`; `assesscontext.py` `task_context` | The ids the Task states; `work --id`, `deps --of` and `deps --on` for the Task's stack (R42, Q9, Q15). | The stack and entry ids written into a Task that states none (R41). A dependency between stacks the matrix lacks. |

### Build (`task-to-deploy` and the driver's build lane)

The Build table and the Deploy table are the specification the rewrite of the build and
deploy lanes follows (`blueprint/requirements/pipelines.md`). The matrix build changes
those lanes only as far as slices 29 and 31 of section 6 state.

| Step | Where | Reads | Records |
|---|---|---|---|
| B1 Workspace | `workflows/task-to-deploy.js` `stepWorkspace` | The stack id the Task states, then `node stack:<id>` for its `repository` (Q10). | Nothing. A Task that states no stack fails the step. |
| B2 Infrastructure intent | `workflows/task-to-deploy.js` `stepInfraIntent`; `workflows/infra-intent.js` | `node stack:<id>` with what it holds, `deps --of` (Q6, Q9, Q11). | Nothing. The intent provisions what the matrix states the stack holds and depends on. |
| B3 Implementers and Green | `stepSelectImplementers`; `workflows/tdd-green.js`; `agents/cdk-stack-author.md` and the implementer agents | The shared capability ids the Task states (R41); `node` for each provider and its stack (Q6). | Nothing. The implementer result's `upstreamMissing` and `dependencies` are in the step journal. |
| B4 Regression | `workflows/task-to-deploy.js` `regressionBrief`, `regressionReviewBrief`; `agents/regression-impact-assessor.md`; `skills/cumulative-regression/SKILL.md` | `impact --id` for each entry the Task states (Q19, Q15). | Nothing. The per-repository `regression.json` holds test mappings and execution evidence only. |
| B5 Reuse audit | `stepReuseAudit`, `judgeReuse` | `check-reuse --ids <ids> --worktree <path>` with the shared capability ids the Task states. | Nothing. A signal the reviewer rules wrong is in the step's result. |
| B6 Suite run | `workflows/suite-run.js` `resolvePrompt` | The stack's `commands.test` (Q21). The resolving session runs only when it is empty. | Nothing. |
| B7 Commit and Task close | `stepCommit`; `ops/sdlc-automation/lane.py` `_settle_build` | none | Nothing. No flag is set before the Story's test passes (D8). |

### Deploy (the driver's `storydeploy.py` and its workflows)

| Step | Where | Reads | Records |
|---|---|---|---|
| D1 Mechanism | `storydeploy.py` `_mechanism_step`, `mechanism_of`, `_usable`; `workflows/deploy-mechanism.js` | none. `mechanism_of` reads nothing from the matrix: unless the repository is the control repository or the repository that holds the architecture documentation (`_excluded_repositories`), which publish and deploy nothing, it always starts one `polyrepo-steward` session, which rules whether the repository publishes and deploys and names its publish command. | Nothing in the matrix. The ruling is recorded in the Story's step journal. |
| D2 Publish | `storydeploy.py` `_publish_step`, `_library_tests_fail`; `matrixmarks.shared_library` | Only the shared-library check: the repository's stacks (`atw-matrix stacks --repository`), whether one has `executionUse` `imported`, and that stack's `commands.test`. The publish command is the steward's ruling from D1, not read from the matrix. | Nothing. |
| D3 Synth and SSM check | `storydeploy.py` `_synth_step`, `_ssm_check_step`, `stacks_in`, `ssm_reads` | none; the assembly is the build's own output, read to deploy and check this Story. | Nothing. A missing parameter fails the step. |
| D4 Deploy and stack verification | `workflows/deploy.js`; `storydeploy.py` `_verify_step` | The stack's `commands.deploy` (Q21) and the stacks D3 synthesized. | Nothing. Passing is a condition of D8 and is in the step journal. |
| D5 Deploy fix | `storydeploy.py` `_fix_step`; `workflows/story-deploy-fix.js` | `node stack:<id>` and `deps --of` for the failed stacks (Q9). | Nothing. |
| D6 Built comparison | `workflows/built-version.js` `stepCompare`; `agents/built-architecture-comparer.md`; `storydeploy.py` `_built_subject`, `built_args` | `built --story <id>`, then `story-scope` for those entries: the documents and headings that describe each (Q18). | Nothing. A difference is a file under `built/<subject>/` until D7 corrects the documents in the same run. |
| D7 Built correction | `workflows/built-version.js` correct, conformance and approve steps; `agents/architecture-maintainer.md`; `skills/arc42-maintain/SKILL.md` step 8; `storydeploy.py` `_built_version_step` | `node <entry>` for every document that describes a changed entry (Q18). | Nothing. The corrected documents are effective in the vault; the next run's E1 `sync-documents` mirrors them. |
| D8 Verify, merge and close | `storydeploy.py` `_mark_verified_step` (journal step `deploy:mark-verified`), `_merge_wait_step`, `_close_step`; `ops/sdlc-automation/matrixmarks.py`; `scripts/portfolio/matrixcode.py` | none | `verify --story <id>` once every check on the pull request's head commit has passed (the deploy test, D4, passed before the pull request opened), then `commit --bead`, both before and apart from the merge. `verify` sets the verified mark on what this Story built (section 1.4.2). The step is done only when both calls have succeeded; the merge wait and the close write nothing in the matrix. |
| D9 Close with no pull request | `storydeploy.py` `_close_step` | none | Nothing; no flag. |
| D10 Driver dispatch and dashboard | `ops/sdlc-automation/workitems.py`, `reposcope.py`, `storyorder.py`, `decisions.py` | `epic <id>` for the PRD (Q1); the stack id a Story's Tasks state, then `node stack:<id>` for the repository (Q10); `epic <id> --closure` for the repository view (Q12). | Nothing. |

### Repository work (`polyrepo-steward`, `skills/polyrepo-repo/scripts/polyrepo.py`)

| Step | Where | Reads | Records |
|---|---|---|---|
| S1 Repository created | `polyrepo.py` `cmd_create`, `_create_records` | `stacks --repository` (Q24). | `put stack` for each stack the repository holds: `name`, `app`, `executionUse`, `repository`. A stack the matrix does not yet hold is recorded with the purpose not stated. The tool makes the call. |
| S2 Repository renamed | `polyrepo.py` `cmd_rename`, `_rename_record` | `stacks --repository <old>`. | `move-repository --from <old> --to <new>`: the `repository` attribute of each stack. No id changes. |
| S3 Repository deprecated or archived | `polyrepo.py` `cmd_deprecate`, `apply_fixes` | `stacks --repository`. | The tool proceeds when the result is empty. The steward first moves each stack (`put stack --repository`) or removes it (`remove stack:<id> --held`). |
| S4 Grouping | `agents/polyrepo-steward.md` Judgment | `node stack:<id>`. | `link` and `unlink` of `homeIn` for a corrected home. |
| S5 Stack created, moved, renamed or removed | `skills/polyrepo-repo/SKILL.md` "The matrix" | `node stack:<id>`. | `put stack` with `name`, `app`, `executionUse`, `repository` and the `commands` the repository declares; `rename`; `remove`. |
| S6 Health check | `skills/polyrepo-doctor/SKILL.md`; `polyrepo.py` `cmd_doctor` | `stacks`, `check`. | Findings: a code repository that is the `repository` of no stack; a stack whose `repository` is not an active repository; a failing `check`. With `--fix`, the `put` or `remove` that corrects each. |
| S7 Knowledge scan | `skills/polyrepo-tribal-knowledge/SKILL.md`; `skills/polyrepo-info/SKILL.md` | `find --kinds stack`. | Where functionality lives: an alias or a `homeIn`. The steward keeps pointers to procedures and non-architecture documents only. |
| S8 Answering questions | `agents/polyrepo-steward.md`; `skills/polyrepo-router/SKILL.md`; `commands/polyrepo-steward.md` | Q7 to Q11, Q15, Q17, Q22, Q24. Live git and GitHub state comes from the `polyrepo` tool. | A correction to whatever the answer shows wrong. |

### Every session

| Step | Where | Reads | Records |
|---|---|---|---|
| I1 Shared instruction text | `skills/subagent-contract/SKILL.md`, `agents/aws-solutions-architect.md`, `agents/built-architecture-comparer.md`, `agents/polyrepo-steward.md`, `skills/polyrepo-repo/SKILL.md`, and the preamble bundled into each `workflows/*.js` | The text states the approved and verified flags as section 1.4 does. | Nothing; no agent sets a flag. |
| I2 How an agent uses the matrix | `skills/matrix/SKILL.md`, loaded by every agent whose definition calls `atw-matrix` and pointed to from `skills/graphrag-lookup/SKILL.md`; `skills/matrix/scripts/matrix-reach` | The model, which command answers which question (section 2), that `node` and `impact` are direct only, and the three transitive reads `matrix-reach` makes for every Epic by the rule of reach, `matrixtraverse.rule_reach` (a document covers one of the Epic's requirements under the heading that describes the entry, or a feature is realized by it; a stack through what is reached in it; the far end of a dependency from those, one hop only): the Epics that reach an entry, what an Epic reaches with its gaps, and the entries no Epic reaches. | Nothing. |

## 5. Replacement list

Each row is one mechanism that finds by scanning something the matrix holds. The change that
introduces the lookup removes what the last column names. For a site in a build workflow, a
deploy workflow or the driver's deploy code, that change is the rewrite of the build and
deploy lanes: rows R20, R23, R24, R25 and R26 whole, and the `built-version.js` sites of row
R14.

| # | Sites | Does today | Matrix lookup | Removed |
|---|---|---|---|---|
| R1 | `ops/sdlc-automation/workitems.py` `prd_index`, `epic_named_by`, `prds_naming_epics`, `prd_labelled_by`, `find_prd`, `prd_epic_coverage`; `skills/epic-ready/SKILL.md` condition 1 and its two commands; `scripts/portfolio/prds.py` `write_prds`, `write_index` | Globs the PRD folders, reads every PRD for an `**Epic:**` line, reads `prd:` labels, guesses from bead text, or takes the bead description as the PRD. | Q1: `epic <id>`. PRD files no epic names come from the `sync-epics` result. | The glob, the line and label reads, the guess, `prds.py`, and the `**Epic:**` line and `prd:` label as records. |
| R2 | `ops/sdlc-automation/reposcope.py` `repo_hint`, `_hint_sources`; `storyorder.py` `repository_of`; `matrixmarks.py` `_elements`, `_built_mark`; `scripts/portfolio/storyedges.py` `repository_of`, `_story_repositories` | Guesses a bead's repository from a regular expression over bead text and from the ancestor Story and Epic, and selects matrix rows by repository basename. | The stack id the Task states, then Q10: `node stack:<id>`. For the entries a Story built: `built --story <id>` (R42). | The text patterns, the ancestor walk, the basename selection. The `repoPath` and `matrix_elements` keys stay on the beads. |
| R3 | `orchestrator/flows/architecture.py` `architect()` brief with `ARCHITECT_REQUEST`, `_handed_files()`, `add_dirs`, and `specialist()`, `trd_author()`, `maintainer()` through `_helper_dirs()`; `architecture_files.py` `new_context()` `constraintsFolder`; `spec_authoring.py` `author_files()`, `author_dirs()`; `ops/sdlc-automation/workitems.py` `elaboration_args`, `arch_args`, `dispatch_context`; `ops/sdlc-automation/atw.py` `_resolve`, `values`, `environment` | Opens the whole architecture root, the PRD folder, the section 2 folder, a whole repository and the fleet directory for a session to read and decide what is relevant. | Q2, Q4, Q5, Q12, Q13, Q26: the session runs the Epic's reads itself (`epic <id>`, `--realizers`, `--constraints`), or the script step writes `story-scope` to a file and the brief names the documents and headings in it. | The directory grants beyond the named files, `constraintsFolder`, the request to "establish the state of the architecture", the fleet directory as a place to read. |
| R4 | `orchestrator/flows/repo_scoping.py` `_work_elements()` | Drops elements whose code state is built or deployed. | Q12 and Q14: a stack in the Epic's closure that holds an entry, or starts a relationship, that is not verified may still have to be built. | The `CODE_BUILT` and `CODE_DEPLOYED` test. |
| R5 | `orchestrator/flows/repo_scoping.py` `_repository_kind()` and the `frontend` flag in `_ruling()` | Matches the repository name against the name patterns of the steward's templates. | Q11: the stack's type. | The name match on a repository. |
| R6 | `orchestrator/flows/trd_authoring.py` `document()` | Resolves each cited path against the architecture root on disk. | `node document:<path>`: the entry, its headings and lifecycle. | The disk resolution. |
| R7 | `skills/graphrag-lookup/SKILL.md` "Before designing" (loaded by 39 agents); `agents/aws-solutions-architect.md` "Find and reuse before you design" step 1 fallback | Searches every repository and the architecture repository for whether a capability exists. | Q3 and Q8: `find --kinds feature`, `find --kinds stack`. An empty result is the answer. | The search as the way to learn whether a feature or a stack exists. The skill section and the architect's step state the matrix lookup first, and GraphRAG for what the matrix does not record. The skill, the `mcp__mcp-graphrag-server` grants and the server stay. |
| R8 | `skills/graphrag-lookup/SKILL.md` "Before any change or refactor" | Searches all repositories, then `get_graph` or `find_path` and `git grep` in each. | Q15: `deps --on <id>`, then GitNexus and `git grep` inside the repositories of the stacks returned. | The all-repositories search as the way to find what depends on an entry the matrix records. The section states the matrix lookup first. |
| R9 | `agents/aws-solutions-architect.md` "Existing code is a clue and nothing more" and "Decide what the architecture should be" | Reads code for hints with no bound on which repositories. | Q6 then Q10: code is opened in the repository of a stack the matrix names for an entry the Epic reaches. | The unbounded instruction. |
| R10 | `agents/polyrepo-steward.md` Ownership and "placing an element"; `skills/polyrepo-info/SKILL.md` "Search — always by precedence" and the search operation; `skills/polyrepo-info/references/search-recipes.md`; `skills/polyrepo-router/SKILL.md` answers list and question table; `skills/polyrepo-repo/SKILL.md` Operations, search; `skills/polyrepo-tribal-knowledge/SKILL.md`; `commands/polyrepo-steward.md`; `agents/root-cause-analyst.md` Scope and Inputs Required | Finds where functionality lives, or which repository owns it, by live search: AGENTS.md, Obsidian, GraphRAG, GitNexus, NotebookLM, ripgrep, `git grep`, `gh`, `polyrepo grep`; keeps pointers to what it finds. | Q8 then Q10; Q22 for a resource type. | The precedence ladder for these questions, the steward's where-it-lives pointers, the routing of these questions to `polyrepo grep` and `inventory`. |
| R11 | `agents/polyrepo-steward.md` "What depends on what"; `skills/polyrepo-repo/SKILL.md` paragraph "A record has no dependencies" | Reads effective arc42, maps through the `owns` the steward records for each repository, then GraphRAG. | Q9 and Q15: `deps`. | The instruction. |
| R12 | `agents/polyrepo-steward.md` Grouping and placement with `skills/polyrepo-repo/SKILL.md` record fields; `polyrepo.py` `mentions`, `State.confirm_all`; `polyrepo.py` `cmd_inventory`, `cmd_search`, `cmd_list` fields `purpose`, `role`, `owns`, `groups` | Keeps what a repository owns and its purpose in the steward's records, and confirms `owns` with `git grep`. | Q24, Q6, Q7: `stacks --repository` with what each holds and its purpose. | The steward's `owns`, `owns-unconfirmed`, `purpose`, `purpose_head` and `role`, and the `git grep` confirmation. `polyrepo inventory` prints the matrix's values. |
| R13 | `agents/epic-dependency-assessor.md` step 3 with `skills/epic-sequencing/SKILL.md`; `workflows/dependency-assessment.js` step 3; `commands/dependency-assessment.md`; `workflows/prd-validation.js` requirement-class lens (`agents/requirement-classifier.md`) | Searches the arc42 catalog front matter and section 2 for a view or rule and reads `lifecycle_state`. | Q4, Q5: `find --kinds document,constraint,feature`, then `node`. | The catalog search, the lifecycle read, the section 2 read, the `ARCH_VAR` precondition. |
| R14 | `workflows/built-version.js` `stepCompare` prompt step 1 with `ARCH_MODEL`, `correctTask`, and the conformance review prompt; `skills/c4-diagramming/SKILL.md` "Search the catalog" | Searches every view's `subject` and `shows` in every arc42 section, and `git grep` in the worktree, for the views that show an element. | Q18: `node <entry>`. | The catalog search in the three prompts and the skill. |
| R15 | `scripts/portfolio/archstate.py` `_effective_elements`; `archmatrix.py` `catalog_elements` | Globs `arc42/` and parses `shows` and `subject` of each file. | Q6, Q18: the `describes` relationships. | The glob and `read_catalog` calls. |
| R16 | `scripts/portfolio/archmatrix.py` `row_of`, `satisfied`; `archcoverage.py` `coverage_facts`; `ops/sdlc-automation/decisions.py` step label `scope:repository-survey` and `_scoping` | Consumes `survey.json`, an agent's survey of code and arc42, fingerprints the repositories it read, and reads a matrix snapshot in an older shape that is never passed. | Q4, Q12, Q13, Q14: `epic <id> --closure --unlinked`. | `survey.json`, the fingerprints, the snapshot parameter, `satisfied`, the survey step and its rendering. |
| R17 | `scripts/portfolio/assesscontext.py` `assess_context`; `workflows/dependency-assessment.js` steps 4 and 5; `agents/epic-dependency-assessor.md` steps 4 and 5 with `skills/epic-sequencing/SKILL.md` step 4 | Writes a corpus of every open Epic's PRD and an index, greps it, then reads related PRDs. | Q20: `related --epic`, and `find --kinds requirement,feature` for an Epic with no features yet. The named PRDs are then read in full. | The corpus, the index, the grep. |
| R18 | `scripts/portfolio/assesscontext.py` `task_context`, `write_tasks`, `write_task_index`; `workflows/task-dependency-assessment.js` steps 3 and 4; `orchestrator/flows/task_decomposition.py` `context()` with `beadwrite.other_epic_tasks` | Writes every open Task to a file with an index, or loads the whole beads graph, and filters by repository path. | R42 with Q9 and Q15: `work --id`, `deps`. | The Task corpus and index, the graph load filtered by `repoPath`. |
| R19 | `agents/architecture-impact-analyst.md` Operating Rules | Lists open Epics and children, reads `decisionIds` and catalog front matter, greps the spec tree. | Q19: `impact --id document:<path>`, then `affected --id` for the open Tasks (R42). | The listing, the front matter reads, the grep. |
| R20 | `skills/cumulative-regression/SKILL.md` "Establish the affected requirements"; `workflows/task-to-deploy.js` `regressionBrief`, `regressionReviewBrief` | Follows component and consumer references through PRDs, specs, architecture, the vault and `regression.json`. | Q19: `impact --id` for each entry the Task states. | The reference following, the component-to-requirement map in `regression.json`. |
| R22 | `agents/story-bead-writer.md` `outOfRepoFindings` | Judges which work lies outside the Story's repository by reading the spec set. | Q12: `epic <id> --closure`. | The judgment by reading. |
| R23 | `workflows/infra-intent.js` provisioning intent prompt; `workflows/deploy.js` deploy prompt; `workflows/story-deploy-fix.js` fix prompt | Works out the stacks, the deploy mechanism and the cross-stack references by reading the repository's CDK code and stack events. | Q6, Q9, Q11, Q21: `node stack:<id>`, `deps --of`. | The instructions to derive them from the repository. |
| R24 | `workflows/deploy-mechanism.js` ask phase; `ops/sdlc-automation/storydeploy.py` `mechanism_of`, `_mechanism_step`, `_usable` | Starts one `polyrepo-steward` session per Story deploy to rule what the repository publishes and deploys. | Q21. | The session when the values are recorded; the mechanism in the step journal as the record. |
| R25 | `ops/sdlc-automation/storydeploy.py` `_built_subject`, `_target_subject`, `built_args`, `_built_items` | Reads the Epic's target file and `recon-<slug>.json` for a subject and items, and passes the whole architecture root. | `built --story <id>`, then `story-scope`. | The target and recon reads, the root as an argument. |
| R26 | `workflows/suite-run.js` `resolvePrompt` | One session reads AGENTS.md, CLAUDE.md and the Taskfile for the test command whenever the caller names none. | Q21: `commands.test`. | The session when the command is recorded. |

Sites that stay, each with its reason:

1. `orchestrator/flows/repo_scoping.py` `inventory()`, `_ruling()`, `_ensure_repository()`: the clone path and existence on GitHub are machine facts the `polyrepo` tool holds; the call is one lookup by the name the matrix gives.
2. `orchestrator/flows/prd_to_spec.py` `open_run()`, `_sync_matrix()`: this is the matrix's own upkeep; it reads the vault and beads so later steps read the matrix.
3. `orchestrator/flows/task_edges.py` `mapper()`: ordering of Tasks inside an entry is finer than the matrix holds; what it finds between stacks is recorded (E14).
4. `agents/polyrepo-steward.md` rows for repository count, uncommitted files, last update and currency with main: live git state.
5. `skills/polyrepo-setup/SKILL.md`: a one-time bootstrap of the steward's records.
6. `agents/spec-currency-validator.md`: it checks files and interfaces inside one repository, below what the matrix holds.
7. `agents/filing-clerk.md`: glossary and general vault documents are outside the matrix's kinds.
8. `workflows/documentation.js` audit prompt: READMEs, changelogs and API references are repository documents, not arc42.
9. `ops/sdlc-automation/inventory.py` `_spec_paths`, `_trd_facts`, `_item_documents`, `_filed_documents`: TRD and Spec files are not matrix kinds; their paths are on the beads.
10. `ops/sdlc-automation/mcpconfig.py` `ALLOWED_SERVERS` entries `mcp-graphrag-server` and GitNexus, the `mcp__mcp-graphrag-server` grants in the agents, and the `graphrag-lookup` skill: GraphRAG indexes the `skillspoke-docs` vault, arc42 and SDLC documents included, and the repositories, for search by meaning; GitNexus indexes each repository's call graph for change impact and renames. Agents go to the matrix first for what it records and use these two for what it does not.
11. `ops/sdlc-automation/storydeploy.py` `stacks_in`, `_assembly_reads`, `ssm_reads`, `verify`: they read the assembly this deploy synthesized, to deploy and check this Story; nothing they find is recorded in the matrix (D3).
12. `ops/sdlc-automation/storydeploy.py` `_excluded_repositories`: two fixed project locations that hold no stack.
13. `scripts/portfolio/archevidence.py` `load_repository_paths`: it reads one handed file of checkout paths; the file's producer is under R3.
14. `skills/polyrepo-repo/scripts/polyrepo.py` `discover`, `gather`, `GitHub`: live reconcile of disk, GitHub and the steward's records; it feeds S6.
15. `skills/polyrepo-repo/scripts/polyrepo.py` `cmd_grep`: a general text search for steward upkeep; where-it-lives questions go to R10.

## 6. Building and seeding the matrix

The matrix is built to this design and then seeded fresh (section 3). Nothing held in
`ops/sdlc-automation/matrix.json` before seeding is a source: the matrix holds only what is
current (requirement R20), and the first seeding step writes an empty version 4 file. Each
slice below is one file group for one agent, except the seeding slices: slices 10 and 15
are script runs with no agent, and slices 11, 12 and 14 are one agent per batch, in the
numbers the Slice column gives (section 3.2). The last column names the slices a slice runs
after. Slices whose earlier slices are done run in parallel.

The build and deploy lanes are rewritten, and their use of the matrix as section 4
specifies it is done in that rewrite (`blueprint/requirements/pipelines.md`). Slices 29 and
31 make only the changes those lanes need now.

The agent that changes pipeline tooling sanity-checks its own change once before committing:
it imports the module and calls the changed function or entry point once with a realistic
input, as a throwaway probe scoped to what changed, plus lint and strict type checking on
the changed files and the generators' `--check` when a schema or shared block changed. No
test or check suite exists for the pipeline tooling and none is written; a sanity check is
not kept, committed, wired into a hook or run again by a later step. The owner's pipeline
run is the test.
The Proof column names the command of a slice's sanity check where one fits.

| # | Slice | Files | Proof | Runs after |
|---|---|---|---|---|
| 1 | Kinds registry and schema, with `side` on every entry and relationship and the `correspondsTo` relationship | `skills/artifact-handoff/schemas/matrix-kinds.json`, `matrix.schema.json`, `skills/artifact-handoff/scripts/generate_matrix_contract.py`, `matrix_contract.py` | `python3 skills/artifact-handoff/scripts/generate_matrix_contract.py --check` | none |
| 2 | Store: generic entries and relationships, one relationship per side, both-end index, registry validation, `rename`, `remove` | `scripts/portfolio/matrixstore.py` | The sanity check, lint and strict type checking on the changed files | 1 |
| 3 | Reads: `epic` with `--closure`, `--constraints` and `--unlinked`, `find`, `node`, `deps`, `stacks`, `layers`, `impact`, `related`, `story-scope`, `uses`, `summary`; every result carries `side` | `scripts/portfolio/matrixquery.py`, new `matrixtraverse.py` | The sanity check, lint and strict type checking on the changed files | 2 |
| 4 | Changes: `put` and `link` with `side`, `unlink`, `settle`, `move-repository`, `commit`; `apply --file`, a change file (`matrix-change.schema.json`) of `put`, `link`, `unlink` and `settle` applied in one locked update, all or nothing, each failed operation reported by index (`apply_change_file`) | `scripts/portfolio/matrixwrite.py`, `matrixcli.py` | The sanity check, lint and strict type checking on the changed files | 2 |
| 5 | `verify`; the Task script's `built`, `work` and `affected`; the three older marks and `story-built` leave | `scripts/portfolio/matrixcode.py`, new `matrixtasks.py` | The sanity check, lint and strict type checking on the changed files | 2 |
| 6 | `sync-epics` with requirements; `sync-documents` with `describedBy`, removal and `--paths` | `scripts/portfolio/matrixsync.py` | `atw-matrix check` | 2 |
| 7 | `seed` and its steps: the empty file, `seed-stacks`, `seed-packages`, `seed-inputs`, `seed-features --list`, `seed-realizers`, `seed-apply`; none runs a `cdk` command; `matrixcarry.py` leaves | new `scripts/portfolio/matrixseed.py`; `matrixcarry.py` | The sanity check, lint and strict type checking on the changed files | 2 |
| 8 | `review-scope`, `check-reuse` | `scripts/portfolio/matrixreview.py`, `matrixreuse.py` | The sanity check, lint and strict type checking on the changed files | 2 |
| 9 | Command table and roles | `scripts/portfolio/matrixcli.py`, `matrix.py`, `matrixcall.py`, `bin/atw-matrix` | `bin/atw-matrix --help` lists the commands of sections 1 to 4 and none of the removed ones | 3 to 8 |
| 10 | Seed, script steps P1 to P6, no agent: one run of `atw-matrix seed` writes the empty file, the 127 open Epics with their 1,103 requirements, the 179 arc42 documents, one stack for each of the 63 repositories that are not deprecated and whose name ends in a listed type, their packages, and the batch files | `ops/sdlc-automation/matrix.json` through `atw-matrix`; the batch files | `atw-matrix check`; `atw-matrix summary` counts the Epics, requirements, documents, stacks and packages | 9 |
| 11 | Seed, architecture side (G1), 9 agents: one `aws-solutions-architect` per batch of about 20 effective arc42 documents writes what each document describes, the stack it says each is in, the stack's purpose, the dependencies and the constraints; `seed-apply` records the result files | The result files; `ops/sdlc-automation/matrix.json` through `atw-matrix` | `atw-matrix check`; `atw-matrix layers` returns the layers arc42 states | 10 |
| 12 | Seed, feature proposals (G2), 16 agents: one `aws-solutions-architect` per batch of 8 PRDs writes, per requirement, the features that serve it and the documents that cover each | The proposal files, one per PRD | Every requirement of every open Epic is in a proposal file | 10 |
| 13 | Seed, features recorded once (G3), 1 agent: one `aws-solutions-architect` writes the merge file; `seed-apply` records the features, `servedBy`, `describedBy` and `covers` | The merge file; `ops/sdlc-automation/matrix.json` through `atw-matrix` | `atw-matrix check`; `atw-matrix epic <id>` returns the features of each open Epic | 12 |
| 14 | Seed, repository side (G5), 7 agents: one `aws-solutions-architect` per batch of about 9 stacks writes what is in each stack today, `correspondsTo` and the stack's `commands`; `seed-apply` records the result files. The repositories are read and none is edited, those under `apps/marketing` included | The result files; `ops/sdlc-automation/matrix.json` through `atw-matrix` | `atw-matrix check`; `atw-matrix stacks` returns what each stack holds on the repository side | 11 |
| 15 | Seed close (G6), no agent: `atw-matrix check`, then `atw-matrix commit` | `ops/sdlc-automation/matrix.json` | `atw-matrix check` | 13, 14 |
| 16 | Elaboration: architect, helpers and context (R3; E2 to E5) | `orchestrator/flows/architecture.py`, `architecture_files.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 17 | Elaboration: check, ruling, promotion (E7 to E9) | `orchestrator/flows/architecture_check.py`, `architecture_ruling.py`, `architecture_promotion.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 18 | Elaboration: scoping (R4, R5; E10, E11) | `orchestrator/flows/repo_scoping.py`, `repo_placement.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 19 | Elaboration: Story, Spec and TRD (R3, R6; E6, E12) | `orchestrator/flows/spec_authoring.py`, `trd_authoring.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 20 | Elaboration: Tasks and edges (R18; E13 to E15) | `orchestrator/flows/task_decomposition.py`, `task_edges.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 21 | Portfolio architecture scripts (R15, R16) | `scripts/portfolio/archmatrix.py`, `archstate.py`, `archcoverage.py`, `resumefacts.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 22 | Portfolio assessment scripts (R1, R2, R17, R18) | `scripts/portfolio/prds.py`, `assesscontext.py`, `storyedges.py`, `hierarchy.py`, `beadwrite.py`, `scoring.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 23 | `depscore.py` command wiring for slices 21 and 22 | `scripts/portfolio/depscore.py` | `python3 scripts/portfolio/depscore.py --help` | 21, 22 |
| 24 | Instruction text (I1): the paragraph that states the one mark replaces the paragraph that states four code states, in the files that carry it; the existing `node scripts/shared-blocks.mjs --write` writes it into the workflow preambles | `skills/subagent-contract/SKILL.md`, `agents/aws-solutions-architect.md`, `built-architecture-comparer.md`, `polyrepo-steward.md`, `skills/polyrepo-repo/SKILL.md`, workflow preambles | `node scripts/shared-blocks.mjs`; `node scripts/check-agent-types.mjs` | 9 |
| 25 | Architecture instructions and the `graphrag-lookup` skill (R7, R8, R9, R14 for `c4-diagramming`; E2 to E5); the architect's instructions state its question and its lookups as requirements R4 and R52 to R55 do, with the commands of section 2, and the skill's two sections state the matrix lookup first | `agents/aws-solutions-architect.md`, `trd-author.md`, `architecture-maintainer.md`, `architecture-decider.md`, `skills/arc42-author`, `arc42-maintain`, `arc42-verify`, `arc42/references/finding-views.md`, `c4-diagramming`, `graphrag-lookup` | The sanity check, lint and strict type checking on the changed files | 24 |
| 26 | Steward instructions (R10, R11, R12; S4 to S8); the steward removes the where-it-lives pointers from its knowledge store | `agents/polyrepo-steward.md`, `skills/polyrepo-repo`, `polyrepo-info`, `polyrepo-router`, `polyrepo-tribal-knowledge`, `polyrepo-doctor` SKILL.md files, `search-recipes.md`, `commands/polyrepo-steward.md` | The sanity check, lint and strict type checking on the changed files | 24 |
| 27 | The `polyrepo` tool (R12; S1 to S3, S6): it keeps no `owns`, `purpose`, `purpose_head` or `role`, and its next write of its records drops them; the plugin version rises in `plugin.json` and `marketplace.json` in this change | `skills/polyrepo-repo/scripts/polyrepo.py` | `polyrepo doctor` | 9 |
| 28 | Sequencing and readiness instructions (R1, R2, R13, R17, R19, R22) | `agents/epic-dependency-assessor.md`, `architecture-impact-analyst.md`, `story-bead-writer.md`, `task-decomposer.md`, `root-cause-analyst.md`, `prd-writer.md`, `skills/epic-sequencing`, `epic-ready`, `task-ready` | The sanity check, lint and strict type checking on the changed files | 24 |
| 29 | Build and deploy workflows, the minimum needed now: each call to an `atw-matrix` command that no longer exists is removed, or changed to the command of section 2 that returns the same thing, and every statement of the three older code marks is removed. Everything else in the Build and Deploy tables of section 4 is done in the rewrite of those lanes | The files under `workflows/` that call a removed command or state an older mark, among `task-to-deploy.js`, `tdd-green.js`, `infra-intent.js`, `suite-run.js`, `deploy-mechanism.js`, `deploy.js`, `story-deploy-fix.js`, `built-version.js` | `node scripts/check-workflow-syntax.mjs` | 24 |
| 30 | Assessment workflows and commands (R13, R17, R18; A1 to A4) | `workflows/dependency-assessment.js`, `task-dependency-assessment.js`, `prd-validation.js`, `prd-creation.js`, `commands/dependency-assessment.md` | `node scripts/check-workflow-schemas.mjs` | 24 |
| 31 | Driver deploy code, the minimum needed now: the three older code marks and the calls to `atw-matrix` commands that no longer exist are removed, and the one verified mark is set when the Story's test passes, before its merge, with `verify --story`, then `commit --bead` (D8, D9). Everything else in the Build and Deploy tables of section 4 is done in the rewrite of those lanes | `ops/sdlc-automation/matrixmarks.py`, `lane.py`, `storydeploy.py` | `python3 orchestrator/check_driver_contracts.py` | 9 |
| 32 | Driver: work items (R1, R2; D10) | `ops/sdlc-automation/workitems.py`, `reposcope.py`, `storyorder.py`, `selection.py`, `storyview.py`, `startup.py` | The sanity check, lint and strict type checking on the changed files | 9 |
| 33 | Driver: environment, decisions (R3, R16) | `ops/sdlc-automation/atw.py`, `decisions.py`, `CLAUDE.md` | The sanity check, lint and strict type checking on the changed files | 9 |
| 34 | Second records and close, one script run once and not kept: the `prd:` labels on the open Epics and the `**Epic:**` lines in their PRDs are removed; the plugin version rises | beads, the vault PRDs, `plugin.json`, `marketplace.json` | `atw-matrix epic <id>` returns the PRD of every open Epic | 1 to 33 |

In the Slice column, an R number in parentheses is a row of the replacement list in
section 5, and an E, A, B, D, S or I number is a step of section 4.

The installed plugin is updated and running sessions, the pipeline included, are restarted
after slice 34 for the change to take effect. The first pipeline run follows slice 34.

## 7. Decisions

1. **Storage.** One JSON file with a generic `entries` map and `relationships` list, and the
   kinds in a registry file. Readers are agents and scripts on one machine. R37 requires
   that a new kind restructures nothing already held: with the registry a new kind is one
   declaration, and a lookup that selects by `family` (Q9, Q15) follows it unchanged.
2. **Identifiers.** Kind plus the slug of the thing's own name; the beads id for an Epic;
   the path under the architecture root for a document. A thing designed before it has a
   stack needs an id that depends on neither stack nor repository.
3. **Repository and app.** Attributes of a stack, with no entries of their own. A rename or
   a move is then one attribute, which is what requirement R15 requires.
4. **Library.** A stack with `executionUse: imported`; no library kind. Requirements R19 and
   R33 make "library" an execution use, so it is recorded as that attribute of a stack.
5. **How a PRD requirement is identified.** One `####` heading under `## Requirements`,
   keyed by the identifier that opens it or by the slug of the heading, under the Epic's
   beads id. The PRDs already have this structure, so a deterministic parse yields the same
   ids on every run. When one requirement leaves a group and one arrives, its relationships
   carry over; any other change is reported by `sync-epics` and corrected in that run.
6. **How a similar feature is found.** `find` ranks features by shared words over name,
   aliases, purpose and provided behaviours, and the architect judges the short list. The
   words that led to a match by judgment are added as an alias, so the next lookup is exact.
   Ranking is deterministic, which requirement R2 requires, and needs no added service.
7. **A stack's purpose.** Why the stack exists, not what it contains, in the form of the
   example in requirements section 3.3 (requirement R16). The `aws-solutions-architect`
   drafts it from the effective arc42 documents; where arc42 does not say why a stack
   exists, the entry says the purpose is not stated. The `polyrepo-steward` does not hold
   this and README files are not accurate, so neither is a source. No marker distinguishes
   a checked purpose, because no lookup needs one.
8. **Constraints are entries.** Q5 and requirement R10 need each constraint returned with
   the document it comes from and what it applies to, and one constraint applies to many
   things. A `selector` covers a rule that binds a whole class: Q5 has to return such a rule
   for a stack an Epic adds, which has no relationship to the rule yet.
9. **A verified flag when verified code changes.** An architecture change to verified content
   clears the flag on that item alone, as a dirty bit settled separately from approved, and the next build and test that covers the
   content sets it again, because verified says the current architecture of the item is built
   and tested. The owner: "Now when the spec is written for an Epic, it sees that the
   architecture for that service is no longer verified."
10. **When and on what the verified flag is set.** On the stacks and entries a Story built, as
    the Task script returns them (R42), and the build-proved relationships that start at them,
    when the Story's test passes: its CI checks and the test that its CDK deployment works
    (requirements section 3.5, R25). The test passing is the trigger; the merge that follows is
    a separate step and decides nothing, and no branch is named, so the flag holds whatever
    branching the project uses. The flag is the entry's own, valid for every Epic that relates
    to it, because an Epic owns no stack or component.
11. **Concurrent changes.** Every change is one locked read-modify-write of the file, so two
    runs that write at the same moment both land.
12. **Disagreements between documents.** An entry while the documents disagree, with the
    ruling once made; removed when the losing statement is corrected. It is not raised again
    because the documents then agree.
13. **Design facts.** No kind. A fact's home is the heading a `describedBy` relationship
    names; its content stays in arc42 (requirement R13).
14. **Approval.** Two things, kept apart. A document's `lifecycle` mirrors arc42 (requirement
    R22): what is in review for an Epic is the documents it reaches whose `lifecycle` is not
    `effective`. The approved flag (requirement R57) is the one record of approval in the
    matrix, on the architecture an Epic reaches, set when the Epic's architecture and design are
    approved. It is a plain yes that names no Epic, because it records that the architecture is
    approved, not who approved it. It replaces the earlier `architectureApproved` attribute on requirements and
    features: the owner named two flags, "one for verified, and one for approved", and a
    third would be a second record of approval. It is a common member of every entry and
    relationship, like `verified`; `approve` sets it on the architecture of the scope and never
    on an Epic.
15. **Stack types.** The matrix stores none and reads the last token. `check` reports a
    token `resource-naming-standard.md` does not list, and the list is extended there.
16. **A Task's shared capabilities.** Elaboration derives them with `uses` from the entries
    the Task builds and writes their ids into the Task (R41). The build checks the changed
    files against them with `check-reuse`; the deterministic check catches a duplicate
    before a reviewer is asked.
17. **Stories and Tasks.** No entries; beads is the authority for both (R40). A Task states
    what it builds in the matrix's ids (R41), and the Task script answers from the Task
    beads which entries a Story built, which open work from other Epics touches an entry and
    which open Tasks a change affects (R42). The `repoPath` and `matrix_elements` keys stay
    on the beads.
18. **TRD and Spec files.** Outside the matrix; their paths stay on the beads. The technical
    requirements a TRD states are constraints.
19. **Epic-to-Epic order.** The edge is a beads `tracks` edge, and the matrix records no
    relationship between Epics. An Epic has requirements, served by features, realized by
    architecture entries that depend on other entries; an item is shared when two or more
    Epics need it, whatever repository or name it has. Edges exist so that an Epic waits for
    the Epic that builds and owns something it uses, and so that two Epics never work on the
    same unapproved shared item at the same time. Who goes first on a shared item is a
    judgment from the Epics' requirements, recorded as an architecture-side `drives` from that
    Epic to the item with `basis` `owns` or `shared` and a `reason`; the owner's records stay
    in force (a `drives` with no basis to a stack: that Epic owns every shared item realized or
    homed in the stack; `epicDriver: none`: the stack's items make no edge). `epicorder.py`
    never infers who goes first from counts or names: for each unapproved shared item with a
    decision, every other Epic that needs it waits for the Epic that goes first; an item with
    no decision makes no edge and is listed as unjudged. While the edges hold a loop it drops
    first an edge only `shared` items made, then one an `owns` item made, the edge made by the
    fewest items first, a tie to the lower bead id, and reports each with both Epics and the
    items. It reads everything from the matrix, and its `--apply` removes every Epic-to-Epic
    dependency edge in beads and writes the transitively reduced computed edges as `tracks`
    edges.
20. **Events.** Entries. Q9 and requirement R17 need an event a stack publishes, and the
    EventBridge rule that matches it and the targets the rule routes it to, returned as
    things the stack depends on. A publisher and a consumer meet only at the event: the
    publisher calls the events API, and the target's stack owns the rule that delivers to it.
21. **Third-party packages.** Entries only while a layer contains them, with no other
    relationship, so Q16 is one traversal.
22. **Commands of a stack.** The test, publish and deploy commands are attributes, because
    Q21 returns the three commands. Seeding records them from what the repository declares
    (section 3.2, G5), and the `polyrepo-steward` records them in its repository work; no
    build or deploy step records one (requirement R46).
23. **Two sides of implementation structure.** arc42 is the authority (requirements R43 to
    R46), and what is in a repository today is recorded beside it as a hint. One field,
    `side`, on every entry and relationship shows which side a fact came from, and every
    lookup returns it (requirement R50): it is the simplest means the generic store allows,
    a common field with no exception by kind. What beads and the PRDs state carries
    `architecture`, because the only thing the field separates is a hint read from a
    repository from everything else. The two sides are separate entries joined by
    `correspondsTo`, so neither overwrites the other and no comparison of the two is stored.
    Seeding records both sides (Q9, Q15, Q16, Q22), and elaboration records what the
    architect designs or reads. No command reads a synthesized assembly: the repositories'
    CDK, built by hand and mostly empty, proves nothing (requirement R44), and no lookup in
    requirements section 2 needs one (requirement R31). The build and deploy steps record
    only the verified flag.
24. **Search beyond the matrix.** GraphRAG and GitNexus both stay in pipeline sessions.
    GraphRAG indexes the `skillspoke-docs` vault, arc42 and SDLC documents included, and the
    repositories, for search by meaning. GitNexus indexes each repository's call graph for
    change impact and renames. Agents go to the matrix first for what it records and use
    these two for what it does not.
25. **Committing the file.** `atw-matrix commit` commits and pushes the matrix alone at the
    end of promotion, verification, steward operations and seeding. Requirement R20 leaves
    history to git, and git holds it only when the file is committed.
26. **Recording by scripts.** Facts in an agent's result file are recorded by a script step
    that confirms the write, so recording does not depend on an agent remembering.
27. **The comparison of built code with architecture.** Not recorded. The same run corrects
    the documents, and the step journal holds a run in progress.
28. **Seeding fresh.** The matrix is seeded into an empty file from beads, the PRDs, the
    effective arc42 documents and the repositories. No earlier matrix file is a source,
    because the matrix holds only what is current (requirement R20). The deterministic
    reads are one script. The three judgments (what a document describes, which features
    serve a requirement and which documents cover them, what a stack's code holds) are
    agents in parallel batches, 33 sessions at the measured sizes (section 3). Each session
    writes a result file and the seed script records it, so no session spends a turn on
    each entry. A stack is taken from a repository's name, because `polyrepo inventory`
    lists repositories and no stacks. Features come from both sources
    (requirements section 3.1.1): the architecture step records the capabilities the arc42
    documents provide, and features are proposed per PRD for its requirements and merged by
    one session before they are recorded, so that a feature is recorded once across Epics
    (requirements R7, R8, R47).
29. **What the architect reads.** No file is written from the matrix for the architect: it
    reads the Epic live with `epic <id>`, `epic <id> --realizers` and `epic <id> --constraints`
    (Q2, Q4, Q26, Q5), so nothing it reads drifts from the matrix it writes to, and trd-author
    reads the same constraint set. The architect runs `impact --id` itself for an entry it
    means to change. What the architecture should be is the architect's judgment, and no
    command computes it (requirements R4, R52). The `noStack` of `--realizers` is one input to
    that judgment (requirements R54, R55). What the Stories build is the result's `addedOrChangedElements`
    (requirement R56 for events).
30. **Links.** Any entry may link to any other, and a relationship kind is checked by its
    form, never by a list of the kinds it may join (requirement R58). The owner said "A node
    can link to anything else. That lonkage can also have a type.", and a fixed list refuses
    tomorrow's link while a checked form still catches a misspelt type. The registry still
    declares the named kinds, so each has one reverse name, its attributes and its family.
31. **SSM parameters.** Each is its own `infrastructure` entry of `resourceType`
    `ssm-parameter`, named by its path, with `homeIn` the stack that writes it and `reads` from
    each reader (requirement R59). A stack then finds another stack's parameter by following
    links, which an attribute on another entry cannot give, and the writer is the parameter's
    home, so no second link records it. A set of parameters whose paths no source states is
    kept as an entry with no `resourceType` until its parameters are known.
32. **Resource types.** `resourceType` names one actual AWS resource and is checked by its
    form (requirement R61). A value that named a bundle (alarms, subnets, endpoints, a set of
    parameters), a code construct, a module, a package, a data set or a database inside a
    cluster was removed from its entry; a value that named one AWS resource under another word
    was re-typed to it (an AgentCore agent to `bedrock-agentcore-runtime`, an Aurora cluster to
    `rds-db-cluster`, a queue recorded with its dead-letter queue to `sqs-queue`, the queue it
    names). The entries themselves stay.
