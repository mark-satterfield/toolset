# Manifest Schema

The manifest at `.polyrepo/manifest.yaml` is the steward's source of
truth. This file defines its schema. The schema is **descriptive, not
prescriptive** — its job is to capture whatever shape the project
actually has, not to force projects into a fixed mold.

## Top-level structure

```yaml
schema_version: 1
project:
  name: string                   # short kebab-case identifier
  purpose: string                # one sentence, what the project does
  owners: [string]               # human or team names
  created_at: ISO-8601 date      # when the manifest was first written
  last_updated: ISO-8601 date    # bumped by every learning event

topology:
  kind: enum                     # see Topology kinds below
  description: string            # the human's own words, verbatim
  layout_notes: string?          # how the repos are arranged on disk
  manifest_location: string      # absolute path of this file

repos: [Repo]                    # see Repo schema below
adjacent_repos: [Repo]?          # related but not part of the project

relationships:
  dependencies: [Dependency]?    # see Dependency schema
  shared_contracts: [Contract]?  # proto, openapi, schemas
  deployment_order: [string]?    # repo names in deploy order, if relevant
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

## Dependency schema

```yaml
- from: string                   # repo name (consumer)
  to: string                     # repo name (producer)
  kind: enum                     # build, runtime, type, contract,
                                 # deployment, dev-tooling
  notes: string?
```

Dependencies are directed: `from` depends on `to`. Cycles are recorded
in `relationships.cycles`, not by reversing the arrows.

## Contract schema

```yaml
- name: string                   # human-readable, e.g., "user-events"
  kind: enum                     # protobuf, openapi, jsonschema,
                                 # graphql, typescript-types, other
  source_repo: string            # where the contract is authored
  consumer_repos: [string]       # who consumes it
  path: string?                  # path within source_repo
```

## Rule schema

```yaml
- id: string                     # short slug, e.g., "no-fe-to-db"
  category: enum                 # architectural, security, compliance,
                                 # deployment, convention, soft
  statement: string              # the rule itself, declarative
  reason: string                 # WHY the rule exists
  applies_to: [string]?          # repo names, or omit for project-wide
  origin: string?                # who introduced the rule, if known
  recorded_at: ISO-8601 date
```

The `reason` field is non-negotiable. Rules without reasons rot — the
next agent or human will violate them and not understand why they
mattered.

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
- observed_at: ISO-8601 date
  what: string                   # what looks stale
  evidence: string               # how you noticed
  status: enum                   # open, resolved, false-alarm
  resolution: string?            # how it was reconciled
```

Drift entries are how the steward keeps itself honest. Every reconcile
pass that turns up something unexpected appends here.

## Validation rules

When writing or updating the manifest, ensure:

- `schema_version` is present and matches the current schema
  (currently `1`).
- Every `repos[].name` is unique.
- Every `from` and `to` in dependencies references a real repo (or an
  adjacent repo).
- `last_updated` is always the date of the most recent change.
- `topology.manifest_location` matches the actual on-disk path.
- All paths in `local_path` and `manifest_location` are absolute.

If a write would violate any of these, fix the violation before
saving — do not write a partially valid manifest.

## Evolving the schema

If a project needs a field that does not exist here, do not invent one
silently. Add the field, increment `schema_version` if the change is
breaking, and record the schema change in the changelog. Future versions
of the steward read the schema version to know what to expect.
