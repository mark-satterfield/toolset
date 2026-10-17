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

### Phase 2: topology

- What repos make up this project? Get a list — names only at first.
- For each repo, in turn:
  - Where does it live locally? (absolute path, or "no local clone yet"; the tool derives it, the
    answer only helps you find the repository)
  - What is its remote URL? (or "no remote", "private mirror", etc.)
  - What is its current lifecycle stage? (active, maintenance,
    deprecated, archived, planned)
  - Does it hold product code? (`product`: part of what ships; its product
    files are built in worktrees and change through pull requests, its
    `AGENTS.md`, `CLAUDE.md` and `.claude/` are tier 2; `tooling`: the machinery
    that builds the product, all of it committed on `main` in the primary
    working tree). Record the answer in `tier`; a repository outside the
    repository root goes in the config's `tiers.external` instead.
- Are there repos that are not strictly part of this project but are
  closely related? (e.g., shared design system, shared CI templates,
  vendor forks) — capture them as `adjacent` if so.
- Do the repos fall into natural *groups* or classes — sets you would
  refer to collectively, like "the backend services", "the mobile
  clients", "the infra repos"? Capture each as a named group with its
  members. Do not record a class that a repository's type (the last token of its
  name) already gives, or one that its imports or dependencies would give: those are
  answered live.
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

### Phase 3: what is not recorded

The interview ends with the repositories. Everything else a project says about itself has a canonical
home, and the manifest records none of it:

- Dependencies are between services, components and infrastructure, never between repos; they are
  answered from the effective architecture and the matrix.
- Shared contracts, rules, constraints and conventions belong in the architecture documentation and in
  the control repository's `AGENTS.md` and `.claude/rules/`. When the human states one, hand it to the
  `filing-clerk`, with the reason, to file it in its one home.
- The deploy order is the control repository's `deployment/waves*.yaml`.
- Where documentation lives, and how the human searches, are pointers in `.polyrepo/knowledge.yaml`
  (`polyrepo-info`).
- Owners and contacts are the root `AGENTS.md`, and `CODEOWNERS` files in the repositories.

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

## Finding the manifest

No file outside the steward's folder names the manifest: drop nothing
into the member repos. The `polyrepo` tool finds its config through
`--config`, `$POLYREPO_CONFIG`, the nearest `.polyrepo/config.yaml`
above the working directory, or the command-and-control repo's
environment variable, so it works from inside any repo.

## Writing the manifest

Use `assets/manifest-template.yaml` as the starting scaffold. Fill in
every field you have learned. For fields you do not have answers for
yet, leave them as empty lists, and ask the human about them in your
reply; the manifest itself carries no questions.

## Committing the manifest

Commit the manifest with the tool's `commit --message`, the message stating the project, the
topology the human described, how many repositories were captured and where the manifest is.
Git history is the record of every change from then on; the steward keeps no changelog.

## When to stop

Setup is done when:

- the manifest is written and validates against
  `references/manifest-schema.md`
- the manifest is committed and pushed
- the human has confirmed the topology description matches their
  mental model

If something is genuinely unknown, leave it blank and ask the human in
your reply. Do not block setup on perfection — the steward will fill
gaps over time through the learning flow.
