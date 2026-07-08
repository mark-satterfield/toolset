# Manifest Schema

The manifest at `.polyrepo/manifest.yaml` is the steward's source of
truth. This file defines its schema. The schema is **descriptive, not
prescriptive** — its job is to capture whatever shape the project
actually has, not to force projects into a fixed mold.

## Top-level structure

```yaml
schema_version: 2
project:
  name: string                   # short kebab-case identifier
  purpose: string                # one sentence, what the project does
  owners: [string]               # human or team names
  # No created_at / last_updated — git history is the audit trail
  # (see "Dates and the audit trail" below).

topology:
  kind: enum                     # see Topology kinds below
  description: string            # the human's own words, verbatim
  layout_notes: string?          # how the repos are arranged on disk
  manifest_location: string      # absolute path of this file

repos: [Repo]                    # see Repo schema below
adjacent_repos: [Repo]?          # related but not part of the project

groups: [Group]?                 # named sets of repos, usable as
                                 # dependency endpoints and rule-scope
                                 # targets; see Group schema

relationships:
  dependencies: [Dependency]?    # see Dependency schema; each endpoint
                                 # may name a repo or a group:<name>
  shared_contracts: [Contract]?  # proto, openapi, schemas
  deploy_waves: [DeployWave]?    # tiered deploy stages; supersedes the
                                 # v1 flat deployment_order — see
                                 # DeployWave schema
  cycles: [Cycle]?               # known circular deps, with notes

conventions:
  naming: { repos, branches, commits, tags, releases }?
  branching_model: string?
  commit_format: string?
  pr_rules: string?
  versioning: string?
  code_style: { tools: [string], shared: bool }?

rules: [Rule]                    # see Rule schema — architectural,
                                 # security, deployment, soft rules

documentation:
  per_repo: string?              # convention, e.g., "each repo has /docs"
  project_level: [string]?       # paths or URLs
  adrs: string?
  runbooks: [string]?
  onboarding: [string]?

search_recipes: [SearchRecipe]?  # see SearchRecipe schema

ownership:
  contacts: { topic: owner }?    # e.g., { build: alice, infra: bob }
  codeowners_files: [string]?    # paths to CODEOWNERS in each repo

governance: [GovernanceEntry]?   # v3 — registry of the project's own
                                 # scripts/tools/procedures/knowledge-base
                                 # locations; see The `.polyrepo/` directory (v3)

open_questions: [string]?        # things the steward does not know yet

drift_log: [DriftEntry]?         # observations that the manifest may
                                 # be stale; resolved during refresh
```

## Topology kinds

The `topology.kind` field is the **steward's inference label** for the
project's shape. It is never picked by the human from a flat list. You
derive it from the discovery interview (and an optional filesystem scan,
with permission), propose it to the human with your reasoning, and they
confirm in their own words or redirect. See
`references/topology-recommendations.md` for the inference decision
tree and tradeoffs.

The category is for the steward's quick reasoning; the human's verbatim
description in `topology.description` is what truly defines the shape.

- `siblings_only` — repos are peers, no umbrella, often co-located in a
  parent directory.
- `meta_and_satellites` — one umbrella/meta repo plus member repos.
- `monorepo_plus_satellites` — one large monorepo plus a few outliers.
- `scattered` — no shared parent directory; repos live in unrelated
  filesystem locations.
- `remote_only` — repos do not share a local layout; only git remotes
  unify them.
- `hybrid` — combination; describe in `description`.
- `other` — does not fit any of the above; the human's description
  carries the meaning.

## Repo schema

```yaml
- name: string                   # the project-internal name
  purpose: string                # one sentence
  role: enum                     # service, library, infra, docs,
                                 # orchestrator, meta, app, mobile-app,
                                 # sdk, scripts, fork, other
  local_path: string?            # absolute, or null if not cloned
  remote_url: string?            # primary remote
  default_branch: string?        # main, master, develop, etc.
  owner: string?
  lifecycle: enum                # active, maintenance, deprecated,
                                 # archived, planned
  language: string?              # primary language
  notes: string?
```

Required: `name`, `purpose`, `role`, `lifecycle`. Everything else is
encouraged but optional — fill in what you can, mark the rest as
`unknown` or omit.

## Group schema

```yaml
- name: string                   # kebab-case, unique across groups
  description: string            # one sentence — what unites these repos
  members: [string]              # repo names; every entry must resolve
                                 # to a real repo
```

A **group** is a named set of repos that share a role or constraint — a
*class* like "backend services", "mobile clients", or "infra repos".
Groups exist so dependencies and rules can name a class of repos instead
of hand-listing members or being forced project-wide. A shared library
consumed by every backend service is one `group:backend-services →
shared-types` edge, not N repo→repo edges that rot the moment a service
is added.

Groups are a *different partition* of the repo set than `deploy_waves`:
group membership is about **kind** (what a repo is), wave membership is
about **deploy timing** (when it ships). A repo typically belongs to one
group and one wave, and the two need not align — keep the sections
separate.

## Endpoint notation: a repo or a group

Several fields name a node in the project graph. A node may be either:

- a **repo name** — e.g., `auth-svc`
- a **group**, written with a `group:` prefix — e.g.,
  `group:backend-services`

The `group:` prefix is the only thing that distinguishes the two; a bare
string is always a repo name. The fields that accept this notation are:

- `relationships.dependencies[].from` and `.to`
- `rules[].applies_to[]`

Any `group:<name>` used in these fields must resolve to a group defined
in the top-level `groups` section. A group endpoint means "every member
of that group", expanded against `groups` at read time — so the manifest
stays correct as members are added or removed without editing every edge
or rule by hand.

## Dependency schema

```yaml
- from: endpoint                 # consumer — a repo name or group:<name>
  to: endpoint                   # producer — a repo name or group:<name>
  kind: enum                     # build, runtime, type, contract,
                                 # deployment, dev-tooling
  notes: string?
```

Dependencies are directed: `from` depends on `to`. Either endpoint may
be a repo name or a `group:<name>` (see *Endpoint notation* above); a
group endpoint expands to every member, which is the lossless way to
record that a whole *class* of repos consumes a shared producer. Cycles
are recorded in `relationships.cycles`, not by reversing the arrows.

## Contract schema

```yaml
- name: string                   # human-readable, e.g., "user-events"
  kind: enum                     # protobuf, openapi, jsonschema,
                                 # graphql, typescript-types, other
  source_repo: string            # where the contract is authored
  consumer_repos: [string]       # who consumes it
  path: string?                  # path within source_repo
```

## Deploy wave schema

`relationships.deploy_waves` replaces the v1 flat `deployment_order`. It
is an **ordered list of stages**. Stage order *is* list order: the first
element deploys first, the last deploys last — there is no separate
ordering field. Within a stage, the listed repos deploy in parallel; the
wave model exists precisely to record "these ship together" without
implying an order among them.

```yaml
- name: string                   # stage name, e.g., "foundation"
  description: string            # one sentence — what this stage lands
  repos:
    - name: string               # repo name; must resolve to a real repo
      gate: string?              # a deploy condition that must hold
                                 # before this repo ships, e.g.
                                 # "vpc_enabled=true"; omit for no gate
      deploy_task: string?       # override for how this repo deploys in
                                 # this wave; omit to use the repo's default
```

The model preserves three things the flat list could not:

- **Stage order** — across stages, list order is deploy order.
- **Within-stage parallelism** — repos in one stage have no ordering
  between them; they deploy together.
- **Per-repo gates** — a repo carries a precondition that must hold
  before it ships, independent of stage order.

A repo with no gate and no task override is still listed by name; an
empty wave entry is just `- name: <repo>` with `gate` and `deploy_task`
omitted.

## Rule schema

```yaml
- id: string                     # short slug, e.g., "no-fe-to-db"
  category: enum                 # architectural, security, compliance,
                                 # deployment, convention, soft
  statement: string              # the rule itself, declarative
  reason: string                 # WHY the rule exists
  applies_to: [endpoint]?        # repo names and/or group:<name> entries
                                 # (see Endpoint notation); omit for
                                 # project-wide
  origin: string?                # who introduced the rule, if known
                                 # (a provenance date inside this string is fine)
```

The `reason` field is non-negotiable. Rules without reasons rot — the
next agent or human will violate them and not understand why they
mattered.

Each `applies_to` entry may be a repo name or a `group:<name>` (see
*Endpoint notation*). Group scoping is the right tool when a rule governs
a *class* of repos: "backend services consume shared types only via the
published package" is `applies_to: [group:backend-services]`, which stays
correct as services join or leave the group — instead of a hand-listed
wall of repos that rots, or a wrongly project-wide rule that constrains
repos it was never meant to.

## SearchRecipe schema

```yaml
- intent: string                 # "find React components", "find API
                                 # routes that touch billing"
  command: string                # the actual command or query
  scope: [string]?               # repo names to run it across
  notes: string?
```

Recipes encode tribal search knowledge. Every time you find yourself
running a non-obvious command to locate something across repos, capture
it as a recipe.

## DriftEntry schema

```yaml
- what: string                   # what looks stale
  evidence: string               # how you noticed
  status: enum                   # open, resolved, false-alarm
  resolution: string?            # how it was reconciled
```

Drift entries are how the steward keeps itself honest. Every reconcile
pass that turns up something unexpected appends here.

## Dates and the audit trail

The manifest does **not** carry manual metadata-tracking date fields — no
`created_at`, `last_updated`, `recorded_at`, `observed_at`, or `retired_at`. An
unautomated date field goes stale and lies. **Git history is the audit trail**:
it records what changed, when, and why. Provenance dates embedded inside an
`origin` string (who introduced something, and when they say they did) are fine —
those are content, not metadata the steward must keep current.

## Validation rules

When writing or updating the manifest, ensure (all v1 invariants still
hold; the group and wave rules are new in v2):

- `schema_version` is present and is `2`.
- Every `repos[].name` is unique.
- Every `groups[].name` is unique, and every `groups[].members[]` entry
  resolves to a real repo (in `repos`, or an adjacent repo).
- Every dependency endpoint (`from` and `to`) is either a real repo (or
  adjacent repo) or a `group:<name>` that resolves to a defined group.
- Every `rules[].applies_to[]` entry is either a real repo (or adjacent
  repo) or a `group:<name>` that resolves to a defined group.
- Every `relationships.deploy_waves[].repos[].name` resolves to a real
  repo (or adjacent repo).
- `relationships.deploy_waves` stage order **is the list order** — the
  first stage deploys first. No separate ordering field exists or is
  implied; do not add one.
- `topology.manifest_location` matches the actual on-disk path.
- All paths in `local_path` and `manifest_location` are absolute.

If a write would violate any of these, fix the violation before
saving — do not write a partially valid manifest.

## Migration from v1 to v2

v2 is additive in spirit — a v1 manifest becomes a valid v2 manifest
with two changes:

1. **`relationships.deployment_order` is superseded by
   `relationships.deploy_waves`.** For a literal translation, make each
   repo its own one-repo stage to preserve the total order:

   ```yaml
   # v1
   deployment_order: [infra, shared-types, auth-svc]

   # v2 — literal translation (preserves total order)
   deploy_waves:
     - name: sequential
       description: Direct translation of the v1 deployment_order list.
       repos:
         - name: infra
         - name: shared-types
         - name: auth-svc
   ```

   In practice you collapse repos that actually deploy together into
   shared stages and add gates — that is the whole point of the new
   model. Drop the old `deployment_order` field once `deploy_waves` is
   in place.

2. **`groups` is new and optional.** Repo-only dependency and rule
   endpoints remain valid exactly as written in v1 — `group:<name>` is
   an *additional* endpoint kind, never a required one. Introduce a
   group only when a dependency or rule genuinely targets a class of
   repos.

Bump `schema_version` to `2`, record the migration in the project's
`.polyrepo/changelog.md`, and add a line to *Schema version history*
below, per *Evolving the schema*.

## Worked example (v2)

A small project — a shared types library, two backend services, a web
app, and an infra repo — exercising every v2 addition: one group, one
`group:`-scoped rule, one `group:` → repo dependency edge, and a
two-stage `deploy_waves` block with a gated repo.

```yaml
schema_version: 2

# ... project, topology omitted for brevity ...

repos:
  - { name: infra,        purpose: "AWS CDK stacks",      role: infra,   lifecycle: active }
  - { name: shared-types, purpose: "Published TS types",  role: library, lifecycle: active }
  - { name: auth-svc,     purpose: "Authentication API",  role: service, lifecycle: active }
  - { name: billing-svc,  purpose: "Billing API",         role: service, lifecycle: active }
  - { name: web-app,      purpose: "Customer web client",  role: app,     lifecycle: active }

groups:
  - name: backend-services
    description: Services that run server-side and share the chassis.
    members: [auth-svc, billing-svc]

relationships:
  dependencies:
    # A group → repo edge: the whole class of backend services consumes
    # shared-types. One edge, not one-per-service.
    - from: group:backend-services
      to: shared-types
      kind: type
      notes: Consumed as a published package, never by path import.

  deploy_waves:
    - name: foundation
      description: Shared infrastructure and contracts land first.
      repos:
        - name: infra
        - name: shared-types
    - name: services
      description: Backend services and the web client ship together.
      repos:
        - name: auth-svc
          gate: vpc_enabled=true        # waits for the VPC from wave 1
        - name: billing-svc
        - name: web-app

rules:
  - id: backend-types-via-package
    category: architectural
    statement: >-
      Backend services consume shared-types only via its published
      package, never by relative path or git submodule.
    reason: >-
      Path imports couple deploy timing and break the published-contract
      boundary the package version guarantees.
    applies_to: [group:backend-services]   # scoped to the class, not project-wide
```

This validates against the rules above: every `backend-services` member
resolves to a real repo; the `group:backend-services` used in the
dependency edge and the rule resolves to the defined group; every
`deploy_waves` repo name resolves to a real repo; and the two stages
deploy in list order (`foundation`, then `services`) with `auth-svc`
gated on `vpc_enabled=true`.

## The `.polyrepo/` directory (v3)

The manifest does not stand alone. The steward's state lives in a `.polyrepo/`
directory (located during setup — see the setup workflow), containing:

| File / dir | Holds |
|---|---|
| `manifest.yaml` | The structural spine — this schema. |
| `changelog.md` | Append-only learning log; every change appends here. |
| `knowledge.yaml` | The knowledge store — durable, non-structural facts, mostly *where to find things*. Owned by the `polyrepo-info` skill. |
| `procedures/` | Local procedures/scripts the steward writes for this project (not pushed to the plugin), registered in `governance`. |

### Governance schema (v3)

The top-level `governance` section is the registry of the project's own operational
resources — the scripts, tools, procedures, and knowledge-base locations it provides.
Managed by the `polyrepo-governance` skill.

```yaml
governance:
  - id: string                   # short slug
    type: enum                   # script | tool | procedure | knowledge-base
    name: string
    location: string             # path or URL
    invoke: string?              # how to run/use it (scripts/tools)
    notes: string?
```

### Knowledge store (v3, separate file)

`.polyrepo/knowledge.yaml` is a *separate* file, not part of `manifest.yaml`. It caches
durable facts the manifest's structure does not hold — heavily "where to find things." It
is **not** a pre-computed answer to every question; derived facts are searched live.
Managed by `polyrepo-info`; populated in bulk by `polyrepo-tribal-knowledge`.

```yaml
schema_version: 1
knowledge:
  - id: string
    topic: string                # e.g. "repository naming convention"
    kind: enum                   # location | fact | pointer
    value: string                # the fact, or where/how to find it
    source: string               # how it was learned
```

### `steward_preferences` decomposition (v3)

`steward_preferences` had become a catch-all of preferences, rules, and knowledge. Under v3
it is decomposed: behavioural preferences move to the steward *agent* (its system prompt);
genuine constraints move to `rules[]`; and "where to find it" knowledge moves to
`knowledge.yaml`. Any remaining project-specific behavioural preference the agent must read
may still live in `steward_preferences`.

## Evolving the schema

If a project needs a field that does not exist here, do not invent one
silently. Add the field, increment `schema_version` if the change is
breaking, and record the schema change in *both* the project's
`.polyrepo/changelog.md` and the *Schema version history* section below.
Future versions of the steward read the schema version to know what to
expect.

## Schema version history

This section is the schema's own changelog. *Evolving the schema*
requires every version bump to be recorded here, so a future steward can
read `schema_version` and know exactly what changed between versions.

- **v1** — initial schema. Flat `relationships.deployment_order`
  (`[string]`); dependency endpoints and `rules[].applies_to` were
  repo-only.
- **v2** — added the top-level `groups` section; replaced flat
  `deployment_order` with tiered `relationships.deploy_waves` (ordered
  stages, within-stage parallelism, per-repo gates and `deploy_task`
  overrides); made dependency endpoints (`from`/`to`) and
  `rules[].applies_to` polymorphic — each entry may be a repo name or a
  `group:<name>`. Backward-compatible: repo-only endpoints remain valid
  and groups are additive. See *Migration from v1 to v2*.
- **v3** — added the top-level `governance` section (registry of the
  project's own scripts/tools/procedures/knowledge-base locations);
  introduced a separate `.polyrepo/knowledge.yaml` knowledge store
  (durable non-structural facts, mostly "where to find things", searched
  live rather than pre-computed); documented the `.polyrepo/` directory
  contents; and decomposed the `steward_preferences` catch-all (behaviour →
  the steward agent, constraints → `rules[]`, knowledge → `knowledge.yaml`).
  Also removed the manual metadata date fields (`created_at` / `last_updated` /
  `recorded_at` / `observed_at` / `retired_at`) — git history is the audit trail.
  Backward-compatible: the additions are optional and the date fields were advisory.
