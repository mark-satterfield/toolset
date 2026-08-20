# Setup Workflow

The setup workflow runs the first time the steward meets a project — or
when the human asks to restructure an existing setup. Its purpose is to
discover the project's actual topology and capture it in a manifest the
steward can rely on going forward.

The defining principle: **discover, do not dictate**. The shape of a
poly-repo project is whatever the human says it is. Your job is to ask
the right questions, listen carefully, and write down what you learn.

## When to run setup

Run setup when:

- The user explicitly asks to "set up polyrepo", "onboard the steward",
  or similar.
- The user is asking polyrepo-shaped questions and no manifest can be
  located by the pointer-walk procedure.
- The user says the existing setup is wrong or out of date and they
  want to redo it.

If a manifest already exists and seems healthy, do **not** run setup —
go to the consult flow instead. If you are unsure, ask.

## Phase 0 — greenfield or existing?

Before the interview proper, find out which mode you are in. Ask:

> Are the repositories that make up this project already created, or
> are we designing a new polyrepo project together?

If **existing** — repos exist on disk or as git remotes — proceed to
the interview below. The job is discovery.

If **greenfield** — no repos yet, or only a few — switch to mentor
mode. Read `references/topology-recommendations.md` (the *Greenfield
mentor patterns* section) and help the human think through:

1. Whether a polyrepo is the right call at all (vs. a monorepo).
2. What shape best fits their goals.
3. What the meta repo, if any, should contain.

Walk through the recommendations conversationally. End that
conversation by asking the human if they want to capture the agreed
design as a starting manifest now, even though the repos do not exist
yet — this gives the steward a target state to compare reality against
as the project gets built. If yes, proceed to the interview to fill
out as much of the manifest as the design allows; mark not-yet-existent
repos with `lifecycle: planned`.

## The interview

Run the interview as a conversation, not a form. Ask one or two
questions at a time, listen for context that answers other questions
implicitly, and adapt. The human knows the project; you do not. Below
is the full set of things you must end up knowing — order is flexible.

### Phase 1: project identity

- What does the user call this project? (one short name, kebab-case
  preferred)
- What does the project do, in one sentence? (this becomes the
  manifest's `purpose` field — it anchors every later decision)
- Is there a single human or team that owns the whole project? If so,
  who?

### Phase 2: topology

- What repos make up this project? Get a list — names only at first.
- For each repo, in turn:
  - What is its purpose, in one sentence?
  - What role does it play? (service, library, infra, docs,
    orchestrator, meta, app, mobile-app, sdk, scripts, other)
  - Where does it live locally? (absolute path, or "no local clone yet")
  - What is its remote URL? (or "no remote", "private mirror", etc.)
  - Who owns it?
  - What is its current lifecycle stage? (active, maintenance,
    deprecated, archived, planned)
- Are there repos that are not strictly part of this project but are
  closely related? (e.g., shared design system, shared CI templates,
  vendor forks) — capture them as `adjacent` if so.
- Do the repos fall into natural *groups* or classes — sets you would
  refer to collectively, like "the backend services", "the mobile
  clients", "the infra repos"? Capture each as a named group with its
  members. Groups matter because dependencies and rules often apply to a
  whole class rather than to named individuals (see Phase 3 and Phase 5).
  A repo can belong to a group and still deploy in its own wave — group
  membership is about *kind*, not deploy timing.
- How are the repos arranged on the human's filesystem?
  - All siblings under one parent directory?
  - Scattered across multiple parents?
  - Nested (one repo contains others as submodules or git subtrees)?
  - Some not cloned locally at all?
- Is there a meta-repo, orchestrator repo, or "umbrella" repo that
  knows about the others? If so, which one — and what does it
  actually contain?

Ask the human to **describe the topology in their own words** before
you propose a category. Then map their description to one of:

- `siblings_only` — flat layout, no umbrella
- `meta_and_satellites` — one umbrella + many service/library repos
- `monorepo_plus_satellites` — one big repo + a few outliers
- `scattered` — no shared parent directory
- `remote_only` — no consistent local layout; only git remotes are
  shared
- `hybrid` — some combination of the above
- `other` — capture the human's description verbatim

The category is descriptive, not prescriptive. Write the human's own
words alongside the category in the manifest's `topology_description`
field.

**Critical:** the human does not pick the kind from a flat list. You
infer it from the interview answers and (with permission) a brief
filesystem scan, then **propose** the category to the human with your
reasoning. They confirm in their own words or redirect. See
`references/topology-recommendations.md` for the inference decision
tree and the optional scan commands.

### Phase 3: relationships

- Which repos depend on which? (build-time, runtime, type-only,
  data-contract, deployment-order) — and does any dependency hold for a
  whole *group* rather than a single repo? "Every backend service
  depends on shared-types" is one group-level edge (`group:backend-services
  → shared-types`), not one edge per service that rots when a service is
  added.
- Are there any circular dependencies? (record them — do not silently
  flag them as problems unless the human says so)
- Are there shared contracts (proto files, OpenAPI specs, JSON schemas,
  shared types) that multiple repos consume? Where do they live?
- Is there a deploy order that must be honored? Capture it as *waves*
  (stages), not a flat list: which repos deploy first, which deploy
  together in parallel within a stage, and the order across stages. For
  each repo in a wave, is there a *gate* — a precondition that must hold
  before it ships (e.g., "the VPC must exist", "shared-types must be
  released")? Capture gates explicitly; they are exactly what a flat
  ordering silently loses.
- Are there infrastructure dependencies (databases, message brokers,
  third-party APIs) that span multiple repos? Where are they declared?

### Phase 4: conventions

- Naming: how are repos named? Branches? Commits? Tags? Releases?
- Branching model: trunk-based, gitflow, something custom?
- Commit format: conventional commits? Free-form? Issue-prefixed?
- PR rules: who reviews, how many approvals, required checks?
- Versioning: per-repo semver? Lockstep? Calver?
- Code style: language-specific tools, formatters, linters? Are these
  shared across repos or per-repo?

### Phase 5: rules and constraints

- Architectural rules (e.g., "frontend never talks to the database
  directly", "no circular deps between services X, Y, Z")
- Security or compliance rules (e.g., "PII never leaves repo X",
  "license-restricted code lives only in repo Y")
- Deployment rules (e.g., "shared-types must be released before the
  consumers", "infra changes require a 24h soak")
- Soft rules and conventions the human relies on but has not written
  down anywhere

For each rule, ask **who it applies to**: a single repo, a whole group
(a class captured in Phase 2, e.g. "all backend services"), or the
project as a whole. A rule that governs a class is scoped to that group
(`applies_to: [group:backend-services]`), which stays correct as repos
join or leave the class — far better than a hand-listed wall of repos or
a rule wrongly widened to the whole project.

These are gold. They are the things agents most often violate because
they are tribal knowledge. Capture them carefully and include the
*reason* for each rule, not just the rule itself.

### Phase 6: documentation

- Where does each repo's documentation live? (`README.md`, `/docs`,
  external wiki, Confluence, Notion, etc.)
- Is there project-level (cross-repo) documentation? Where?
- Are there RFCs or design docs? Where?
- Are there onboarding docs, runbooks, postmortems?

### Phase 7: search

- How does the human typically search across repos when they need to
  find something? (`grep -r`, `rg` across a parent dir, `gh search code`,
  Sourcegraph, IDE search?)
- Are there things that are *hard* to find that they wish were easier?

These answers turn into entries in `references/search-recipes.md` and
the manifest's `search_recipes` section.

### Phase 8: ownership and contact

- Who do you go to for X? (build issues, infra, security questions,
  release questions, on-call rotations)
- Are there teams or owners encoded in `CODEOWNERS` files? If so,
  reference them rather than copying.

## Choosing where the manifest lives

This is a recommendation conversation, not a multiple-choice question.
Once you understand the topology, look up the recommendation for that
topology kind in `references/topology-recommendations.md`, present it
to the human with the reasoning, surface the relevant tradeoffs, and
let them confirm or override on informed grounds.

Be opinionated. The human is asking for a steward, which means they
are asking you to know the answer. Hedging with three equally weighted
options is unhelpful — say what you would do and why, then listen for
constraints you did not know about and adjust.

Whatever the chosen location, it must be a real, persistent place the
steward can read and write to. Avoid `/tmp`. Avoid putting the
manifest inside a single member repo unless that repo is explicitly
the meta-repo or command-and-control repo.

## Dropping pointer files

After the manifest's location is decided, drop a `.polyrepo-pointer.json`
file at the root of each repo that has a local clone:

```json
{
  "manifest_path": "/abs/path/to/.polyrepo/manifest.yaml",
  "project": "<project-name>",
  "this_repo": "<this-repo-name>"
}
```

These pointers let the steward find the manifest from inside any repo,
without the human having to remember where it lives. Add
`.polyrepo-pointer.json` to each repo's `.gitignore` *unless* the human
explicitly wants it committed (some teams will, some will not — ask).

## Writing the manifest

Use `assets/manifest-template.yaml` as the starting scaffold. Fill in
every field you have learned. For fields you do not have answers for
yet, leave them as empty lists or `unknown`, and add a note to the
manifest's `open_questions` section so they can be filled in over time.

## Initial changelog entry

After writing the manifest, create `.polyrepo/changelog.md` with a
single initial entry of the form:

```markdown
# Polyrepo Steward Changelog

## YYYY-MM-DD — Initial setup
- Project: <name>
- Topology: <category> — <human's description>
- Repos captured: <count>
- Manifest location: <path>
- Pointers dropped in: <list of repos>
```

This is the first entry of the project's living memory. Every learning
event from now on appends here.

## When to stop

Setup is done when:

- the manifest is written and validates against
  `references/manifest-schema.md`
- pointer files are dropped (or explicitly skipped per the human's
  request)
- the changelog has its initial entry
- the human has confirmed the topology description matches their
  mental model

If something is genuinely unknown, leave it blank with a note in
`open_questions`. Do not block setup on perfection — the steward will
fill gaps over time through the learning flow.
