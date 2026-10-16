# Manifest Schema

The manifest at `.polyrepo/manifest.yaml` is the steward's private cache
of the repositories plus the few facts neither the repository folders nor
GitHub hold. The folders and GitHub are the source of truth; the
`polyrepo` tool keeps the manifest true to them. This file defines its
schema. The schema is **descriptive, not
prescriptive** — its job is to capture whatever shape the project
actually has, not to force projects into a fixed mold.

## What belongs in the manifest

The manifest records **structural facts about repositories** and **pointers to canonical
sources**. It never caches, restates, or duplicates a fact whose canonical home is another
document. This applies to every write the steward makes to the manifest, whether through the
`polyrepo` tool or by judgment (grouping). What a repository holds and why it exists is the
matrix's (its stacks and their purposes), never the manifest's.

### What belongs

Facts that are true of the repository *as a repository*, and that have no other home:

| Belongs | Example |
|---|---|
| Repo identity | `name`, `lifecycle` of a planned repo |
| Tier | `tier` (`product` or `tooling`) |
| Repo grouping | groups |
| Lifecycle dates | `deprecated_on` |
| Pointers | a path or link to the canonical document for anything else |

Local paths are derived live by the `polyrepo` tool from the repository folders and are not
stored. `remote_url` and the lifecycle of a deprecated or archived repo are copies kept so a lookup
need not call GitHub; `polyrepo reconcile` compares each with disk and GitHub and `reconcile --fix`
rewrites it. A copy with no such check is not kept.

### What does not belong

Any **derived fact** — anything decided, specified, or described somewhere else:

- Architecture and technology decisions (which datastore, which transport, which library). Canonical home: the architecture documentation.
- Requirements and behavior. Canonical home: the PRD.
- Interface and schema detail. Canonical home: the spec / OpenAPI document.
- Operational thresholds, limits, retention windows. Canonical home: the crosscutting concepts in the architecture documentation.
- Deployment waves — which repos deploy in which order. Canonical home: `deployment/waves.yaml` (the personal-agent app) and `deployment/waves.shared.yaml` (the shared platform, which deploys first), in the command-and-control repo.

### The test: identity versus claim

Naming a technology is not automatically a violation. Apply this test:

- **Identity — keep.** A statement of what *this* repo is. The manifest states no purpose, no `owns` and no `role`: what a repo holds and what it is for is the matrix's stacks.
- **Claim — remove.** A statement about how *another* system behaves, or which mechanism something uses. `Idempotency via RedisCachePersistenceLayer` on the `shared-chassis → SkillSpoke-sessionCache-infra` edge is a claim about the chassis's internals, and the architecture documentation owns it.

A **dependency** is between services, components and infrastructure, never between code
repositories: a repository is only where code lives, and repos can be combined or split while
service A still depends on service B. The manifest therefore stores no repo-to-repo dependency
edge. The canonical home of a dependency is the effective arc42 architecture in the
`skillspoke-docs` vault, and the matrix (`atw-matrix deps`) answers it; the matrix's stacks
map a question about a repo onto it.

### Why

A duplicated fact has no owner, so nothing updates it when the original changes, and nothing
detects that it has drifted. It then reads as authoritative because it sits in a
canonical-looking file.

The real case cuts both ways. The manifest recorded `Idempotency via RedisCachePersistenceLayer`
on the `shared-chassis → SkillSpoke-sessionCache-infra` edge. The architecture documentation
stated the opposite normatively — that the idempotency store must be a chassis-owned DynamoDB
store — so the manifest was corrected to match it. The architecture documentation was wrong:
idempotency runs on the shared ElastiCache for Redis cluster, and the manifest had been right.
Because the incorrect line in the architecture documentation was treated as settled canon, it was cited repeatedly to overturn the correct value. The lesson
is not that the manifest is always the defect. It is that **a duplicated fact drifts in
whichever copy is wrong**, and that a normatively-phrased sentence in a canonical-looking file
is not evidence that it is true. Check the decision, not the formatting.

### Precedence

The canonical document is where a claim BELONGS; that is a rule about location, not about who
is right. When the manifest disagrees with the architecture documentation, a PRD, or a spec, resolve it against the
**decision** — not against whichever file looks more canonical.

- If the canonical document reflects the decision, the manifest is the defect. Correct the manifest.
- If the canonical document contradicts a decision that was actually made, **the canonical document is the defect** and is corrected, in the same turn, everywhere it states the claim. The steward does not make that correction: a vault document goes to the `filing-clerk`, which corrects it or brings the conflict to the owner. A document never outranks a decision, and a self-authored MUST never outranks industry best practice or AWS Well-Architected.

Either way the fact ends up in exactly one place: the canonical document.

### Compliance criteria

- No manifest field asserts a technology, mechanism, threshold, or behavior that the architecture documentation, a PRD, or a spec also states.
- Where such context is useful, the manifest carries a pointer (document path or section reference), not the content.

## Top-level structure

```yaml
schema_version: 5
project:
  name: string                   # short kebab-case identifier
  # No purpose and no owners: what the project is, and who owns it, is the root AGENTS.md.
  # No created_at / last_updated — git history is the audit trail
  # (see "Dates and the audit trail" below).

repos: [Repo]                    # see Repo schema below
deprecations: [Repo]?            # repositories deprecated on GitHub with no local folder
adjacent_repos: [Repo]?          # related but not part of the project

groups: [Group]?                 # named sets of repos chosen by judgment; see Group schema

governance: [GovernanceEntry]?   # v3 — registry of the project's own
                                 # scripts/tools/procedures/knowledge-base
                                 # locations; see The `.polyrepo/` directory (v3)
```

The manifest holds no questions and no open items: there is no `drift_log` and no
`open_questions`. `reconcile` reports either section as an `open-items` finding. It holds no
`relationships`, `conventions` or `ownership` section either: the shared contracts are the matrix's
and the arc42 documents', the conventions are the control repository's root `AGENTS.md` and
`.claude/rules/`, and the owners are the root `AGENTS.md`. `reconcile` reports each as a
`retired-section` finding, and removes it under `--fix`. Deployment order is `deployment/waves*.yaml`
in the control repository.

There is no `topology` section, no top-level `rules`, no `documentation`,
no `search_recipes`, and no `conventions` — see *Schema version history* for what replaced each of
them and why.

## Repo schema

```yaml
- name: string                   # the project-internal name
  remote_url: string?            # primary remote; a copy of GitHub's, checked by reconcile
  lifecycle: enum                # active, maintenance, deprecated,
                                 # archived, planned
  tier: enum                     # whether the repository holds product code: product or
                                 # tooling. The definition of the tiers and what each does
                                 # with a change are the control repository's root AGENTS.md
                                 # and .claude/rules/git-conventions.md.
  deprecated_on: date?           # the day the repo was deprecated; starts the clock to archiving
```

No `local_path`. A repo's location on disk is a live fact the steward's
tool derives from the project's repo-root environment variable plus this
`name` — recording it in the manifest is exactly the kind of hardcoded,
machine-specific path that goes stale on every re-clone or new machine.
No `default_branch`, `language`, `owner` or `notes` either: the repository and GitHub hold the
first two, the root `AGENTS.md` holds ownership, and what a repository is for is the matrix's.

Required: `name`, `lifecycle`, `tier`. An entry that still carries `purpose`, `purpose_head`, `owns`,
`role`, `owner`, `language`, `notes` or `default_branch` loses them at the tool's next write of the manifest.

## Group schema

```yaml
- name: string                   # kebab-case, unique across groups
  members: [string]              # repo names; every entry must resolve
                                 # to a real repo
```

A **group** is a named set of repos the steward chose by judgment. A set that a repository's
type (the last token of its name) gives is not stored: `search name~-service$` answers it
live. A set that its imports or dependencies would give is not stored either: a dependency is
between services, components and infrastructure, and the matrix answers it.

## Dependencies are not stored

A dependency is between services, components and infrastructure, never between repos. The
manifest has no dependency field and no `group:<name>` endpoint notation. `polyrepo
reconcile --fix` removes a stored `relationships.dependencies` (finding
`repo-dependency-stored`).

## Dates and the audit trail

The manifest does **not** carry manual metadata-tracking date fields — no
`created_at`, `last_updated`, `recorded_at`, `observed_at`, or `retired_at`. An
unautomated date field goes stale and lies. **Git history is the audit trail**:
it records what changed, when, and why. Provenance dates embedded inside an
`origin` string (who introduced something, and when they say they did) are fine —
those are content, not metadata the steward must keep current.

## Validation rules

When writing or updating the manifest, ensure:

- `schema_version` is present and is `5`.
- Every `repos[].name` is unique.
- Every `groups[].name` is unique, and every `groups[].members[]` entry
  resolves to a real repo (in `repos`, or an adjacent repo).
- No `relationships`, `conventions` or `ownership` section, and no `project.purpose` or
  `project.owners`.
- No `repos[].local_path`, `topology`, top-level `rules`,
  `documentation`, or `search_recipes` field — see *Schema version
  history (v4)*.

If a write would violate any of these, fix the violation before
saving — do not write a partially valid manifest.

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
    invoke: string?              # how to run/use it (scripts/tools); the script's own --help says the rest
```

An entry is a pointer: it holds no copy of what the script does or how to operate it. That is the
script's own header and `--help`, or the vault document the `filing-clerk` files it in.

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
    kind: enum                   # location | pointer | fact
    value: string                # where/how to find the answer; for a fact, only what exists nowhere else
    resolves: string|[string]?   # location, pointer: the path the entry points at (environment variables allowed)
    source: string               # how it was learned
```

### `steward_preferences` decomposition (v3)

`steward_preferences` had become a catch-all of preferences, rules, and knowledge. Under v3
it was decomposed: behavioural preferences move to the steward *agent* (its system prompt);
genuine constraints moved to `rules[]`; and "where to find it" knowledge moves to
`knowledge.yaml`. **v4 removed `rules[]` itself** (see *Schema version history*) — a
constraint's canonical home is the project's own architecture documentation or convention doc, never
the manifest, so a constraint that would have gone to `rules[]` under v3 now goes there
instead, and the manifest carries a pointer only if one is genuinely useful. Any remaining
project-specific behavioural preference the agent must read may still live in
`steward_preferences`.

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
  and groups are additive.
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
- **v4** — removed every field whose canonical home is another document, per the
  identity-vs-claim test (a manifest field is fine when it states what a repo *is*;
  it is a defect when it restates a claim another document already owns). Removed:
  `topology` (a repo's location is a live fact the tool derives from the repo-root
  environment variable plus its name, not a fact worth freezing into the manifest);
  `repos[].local_path` (same reason, per repo — a stored path goes stale on every
  re-clone or new machine); `conventions.naming` (the project's own naming-standard
  document is canonical); top-level `rules[]` (architectural/security/deployment
  constraints belong in the project's architecture documentation, AGENTS.md, or crosscutting-concerns doc —
  a rule copied into the manifest drifts the moment the canonical doc changes and
  nothing updates the copy); `documentation` and `search_recipes` (both are "where
  to find it" pointers, which is exactly what `.polyrepo/knowledge.yaml` — the
  `polyrepo-info` knowledge store — exists to hold; restating them here duplicated
  that store's one job). Not backward-compatible: a v3 manifest carrying any of
  these fields must have them removed (and, where the fact is still worth keeping,
  moved to its real canonical home or to `knowledge.yaml`) to become valid v4.
- **v5 addition (no version bump, backward-compatible)** - `repos[].tier`, `product` or `tooling`:
  whether a repository holds product code (`product`) or is the machinery that builds the product (`tooling`);
  the tier of a change is decided by what the file is, not by the repository (AI-tooling files are tier 2 in every repository). Every entry records one; `reconcile --fix`
  records the default (`tooling` for the control repo, `product` otherwise) on an entry that has none, and
  `set-tier` changes it. The repositories outside the repository root (the toolset repo and the
  `skillspoke-docs` vault) have no entry: the config's `tiers.external` records their tier. The
  `repository-tiers.json` export derived from both is what the main-worktree guard hook reads.
- **v5** - removed repo-to-repo dependencies: `relationships.dependencies`, its
  `Dependency` schema, the `group:<name>` endpoint notation and `relationships.cycles`.
  A dependency is between services, components and infrastructure, never between code
  repositories, so its canonical home is the effective arc42 architecture. (`owns`, `purpose`,
  `purpose_head` and `role` have since left the manifest: the matrix's stacks hold what a repo
  holds and why it exists, and the tool drops the four fields at its next write.) Not backward-compatible: a v4 manifest
  carrying `relationships.dependencies` must drop it to become valid v5.
- **v5 removal (no version bump)** - every field and section of the manifest that restated a canonical
  source: `project.purpose` and `project.owners` (the root `AGENTS.md`), `repos[].owner` and `ownership`
  (the root `AGENTS.md`; also a person's name in a record), `repos[].language` (GitHub), `repos[].notes`
  (what a repo is for is the matrix's), `repos[].default_branch` (the repository's own; the config keeps the
  tool's), `conventions` (the control repository's `AGENTS.md` and `.claude/rules/`), `relationships`
  (`shared_contracts`, `cycles`, `deploy_waves`: the matrix, the arc42 documents and `deployment/waves*.yaml`),
  `governance[].notes` (the script's own header and the vault runbook), and the groups that restated
  a repository's type or its imports. The tool drops the entry fields at its next write and reports a
  retired section as `retired-section`.
