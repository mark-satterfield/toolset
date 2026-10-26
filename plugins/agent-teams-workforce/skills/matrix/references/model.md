# The matrix model: entry kinds and relationship kinds

The source of truth is `skills/artifact-handoff/schemas/matrix-kinds.json` (the kinds registry);
`blueprint/design/matrix.md` sections 1.2 and 1.3 explain each. "From → to" says what a kind
usually joins and limits nothing: any entry may link to any other.

## Entry kinds

| Kind | Id form | One entry is |
|---|---|---|
| `epic` | `epic:<beads id>` | One Epic with its PRD (`prd.path`, `prd.hash`) and, once promoted, its architecture `reviewLog`. Always `side: architecture`. |
| `requirement` | `requirement:<beads id>/<slug>` | One requirement heading of the Epic's PRD (`group` is the `###` above it; `hash` its text). Always architecture. |
| `feature` | `feature:<slug>` | One discrete capability of the product, recorded once and shared across Epics; `provides` lists what a shared capability gives its consumers. Always architecture. |
| `constraint` | `constraint:<slug>` | A rule that binds entries: a `statement` (from arc42 or a PRD) or a `trd` pointer to an Epic's TRD requirement; an optional `selector` (`app`, `stackType`, `resourceType`, `executionUse`) names every entry it binds. |
| `document` | `document:<path under the architecture root>` | One arc42 or detailed-design document: `lifecycle` (`effective`, `in-review`, `draft`), `section`, `viewType`, `scope`, `subject`, `headings`, `hash`. |
| `service` | `service:<slug>` | A service arc42 describes; `executionUse`. |
| `component` | `component:<slug>`, repository side `component:<stack>/<slug>` | A part of a service, a Lambda, a page or other code unit; `resourceType` when it is one AWS resource, `executionUse`. |
| `infrastructure` | `infrastructure:<slug>`, repository side `infrastructure:<stack>/<slug>` | One AWS resource (`resourceType`, for example `dynamodb-table`, `eventbridge-rule`, `ssm-parameter`); an EventBridge rule may state `matchesAllEvents`. |
| `event` | `event:<event type>` | An event type: a fact with a meaning, its publishers (`publishes`) or `externalSource`. It has no `homeIn`; its stack is its publisher's. |
| `stack` | `stack:<name>` | The home in code of services, components and infrastructure: `purpose` (required), `repository`, `app`, `executionUse`, `commands` (`test`, `publish`, `deploy`), `epicDriver` (`none`: the owner's decision that the stack is deployed in advance, so no shared item realized or homed in it orders Epics); its type is the last token of its name. |
| `package` | `package:<name>` | A Python package: `origin` `project` (published to CodeArtifact) or `third-party`. |
| `layer` | `layer:<slug>`, repository side `layer:<stack>/<slug>` | One AWS Lambda layer. |
| `file` | `file:<stack>/<path>` | A file in a stack's repository that the design names, such as a saved OpenAPI document (`path`). |
| `disagreement` | `disagreement:<slug>` | Two document statements that disagree; once ruled, `stands` (document and heading), `rule`, `reason`. |

## Relationship kinds

Each is listed as `kind` (reverse name): from → to, meaning. `node` shows a relationship under
its kind at its start and under its reverse name at its end.

| Kind (reverse) | From → to | Meaning |
|---|---|---|
| `hasRequirement` (`requirementOf`) | epic → requirement | The Epic's PRD states the requirement. |
| `servedBy` (`serves`) | requirement → feature | The feature serves the requirement; one feature serves requirements of many Epics. |
| `supportedBy` (`supports`) | feature → feature | The first feature relies on the second, a supporting capability (`relies`: the `provides` ids relied on). |
| `realizedBy` (`realizes`) | feature → service, component, infrastructure, event, layer, package, stack | The entry implements the feature. |
| `describedBy` (`describes`) | feature, constraint, service, component, infrastructure, event, stack, package, layer → document | The document describes the entry, under `heading`. A feature and a service described by one document are joined through it. |
| `covers` (`coveredBy`) | document → requirement | The document heading covers the requirement, `via` the feature that connects them. |
| `statedIn` (`states`) | constraint → document | The constraint comes from this document heading. |
| `appliesTo` (`constrainedBy`) | constraint → epic, feature, stack, service, component, infrastructure, event | The constraint binds the entry's design. |
| `homeIn` (`holds`) | service, component, infrastructure, layer, package, file → stack | The stack is the entry's home in code; at most one per entry. |
| `partOf` (`hasPart`) | component, infrastructure → service | The entry is part of the service. |
| `correspondsTo` (`correspondedBy`) | architecture-side entry → repository-side entry | What a repository holds today for what arc42 describes; always `side: repository`. |
| `distributedAs` (`distributes`) | stack → package | The stack's imported code is published as the package. |
| `contains` (`containedIn`) | layer → package | The layer carries the package. |
| `imports` (`importedBy`) | stack, service, component → stack | Code imports the library the target stack holds (`through`: the package or layer). Dependency family. |
| `usesLayer` (`layerUsedBy`) | component → layer | The Lambda attaches the layer. Dependency family. |
| `calls` (`calledBy`) | stack, service, component → service | Code calls the service (`interface`: the operation or API). Dependency family. |
| `publishes` (`publishedBy`) | service, component → event | Code publishes the event through the events API. Dependency family. |
| `onBus` (`busFor`) | infrastructure → infrastructure | The EventBridge rule belongs to this one bus. Dependency family. |
| `matches` (`matchedBy`) | infrastructure → event | The rule's pattern matches the event type. Dependency family. |
| `routesTo` (`targetOf`) | infrastructure → service, component, infrastructure | The rule delivers what it matches to this target; at most five. Dependency family. |
| `reads` (`readBy`) | stack, service, component → infrastructure | Code reads a value another stack stored, such as an SSM parameter. Dependency family. |
| `runsIn` (`hosts`) | stack, service, component → infrastructure | Code runs in shared infrastructure, such as a Lambda in a VPC, subnets and security groups. Dependency family. |
| `drives` (`drivenBy`) | epic → feature, service, component, infrastructure, event, stack, package, layer | On the architecture side, the judgment that the Epic goes first on a shared item, which `epicorder.py` reads: `basis` `owns` (the Epic builds and owns it; the others use it) or `shared` (the Epics share it independently; the Epic merely goes first) and `reason`; at most one with a basis ends at an item. One with no basis is the owner's decision for a whole stack: the Epic owns every shared item realized or homed in it. |
| `restsOn` (`supportsEpic`) | epic → feature, document, stack, service, component, infrastructure | The Epic relies on this as settled architecture (`heading` for a document). |
| `specifiedBy` (`specifies`) | infrastructure, component, service → file, document | The entry is specified by this file or document heading, such as a saved OpenAPI document. |
| `disputes` (`disputedBy`) | disagreement → document | The document holds one of the disagreeing statements, under `heading`. |

A dependency between two stacks is read, never stored: stack A depends on stack B when a
dependency-family relationship starts at A or an entry A holds and ends at B or an entry B holds.
`deps --of` and `deps --on` follow the family to any depth.

## The approved and verified marks

Any entry or relationship may carry `"approved": true` and `"verified": true`; absent means not
approved and not verified. Both are plain yes/no marks on the architecture (architecture entries
and the relationships between them) and record no Epic, stack, commit or owner. Approved: the
solutions architect approved the architecture for a feature (`matrixwrite.approve`, run by
promotion; an Epic never carries it). Verified: that architecture was built and its test passed
(`atw-matrix verify --story <id>`). A change to an entry or relationship clears its marks. The
`matrix` skill, "Approved, verified, effective and side", says who sets each and how to read them.
