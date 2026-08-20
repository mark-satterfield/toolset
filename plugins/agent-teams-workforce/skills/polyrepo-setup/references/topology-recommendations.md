# Topology Recommendations

This is the steward's mentor reference. Use it when:

- inferring a topology category after the discovery interview (so you
  can propose, not ask the human to pick from a list)
- recommending where `.polyrepo/` should live, given the topology
- advising a human who is designing a *new* polyrepo project and
  wants guidance on tradeoffs before any repos exist (greenfield mode)

The human never picks a topology kind from a flat enum. You ask
questions, optionally scan the filesystem with their permission, form
your own read of the shape, and then **propose** the category with
reasoning. The human confirms in their own words or redirects.

## Two modes

### Existing-project mode

The repos already exist. Your job is to discover the shape, label it,
and decide where to store the manifest. Use the inference rules and
storage recommendations below.

### Greenfield mentor mode

The human is *designing* a polyrepo setup and no repos (or only a few)
exist yet. Your job shifts from curator to mentor: help them think
through whether a polyrepo is even the right call, and if so, which
shape best serves their goals. Use the *Greenfield mentor patterns*
section.

## Inferring the topology kind

After the discovery interview (and optional filesystem scan), match
the answers against this decision tree. The first matching rule wins;
if multiple plausibly match, propose the most descriptive and let the
human redirect.

| If... | Propose `kind` |
|---|---|
| There is exactly one repo whose stated role is "meta", "orchestrator", "command-and-control", "umbrella", or that holds cross-repo deploy/CI/docs, plus N member repos | `meta_and_satellites` |
| Repos are peers with no umbrella, all clones live under one shared parent directory, and none knows about the others | `siblings_only` |
| There is a single large repo (10+ packages or services in it) plus a small number of separate repos | `monorepo_plus_satellites` |
| Repos do not share a parent directory and are spread across unrelated filesystem locations | `scattered` |
| The human has no consistent local layout — they treat the repos as a set of remote URLs and clone ad-hoc | `remote_only` |
| Multiple of the above apply (e.g., a monorepo + a meta repo + scattered libs) | `hybrid` — describe the pieces |
| None of the above descriptions fit | `other` — record the human's verbatim description |

Always also fill `topology.description` with the human's own words. The
`kind` is for fast reasoning; `description` is for accuracy.

## Optional filesystem scan

If the human consents, a quick scan can supplement the interview:

```bash
# repos under a common parent (depth 2 catches nested but not deep)
find <parent-dir> -maxdepth 2 -name .git -type d

# size of each repo (helps spot the "monorepo" in a hybrid setup)
du -sh <parent-dir>/*/

# remotes per repo (helps confirm the project boundary)
for d in <parent-dir>/*/.git; do
  echo "$d:"; git --git-dir="$d" remote -v | head -2
done
```

Never scan without asking. The human may have private or sensitive
repos in the same parent that are *not* part of this project; only
they can tell you the project boundary.

## Storage recommendations by topology

For each topology kind, here is the steward's recommendation for
where `.polyrepo/` should live, with tradeoffs. Always present the
recommendation **with reasoning** so the human can override on
informed grounds.

### `meta_and_satellites`

**Recommend:** `<meta-repo>/.polyrepo/`

Reasoning:
- The meta repo is already the cross-repo source of truth.
- It is version-controlled — every change to the manifest is captured
  in git history alongside the change that motivated it.
- A teammate cloning the meta repo inherits the manifest for free.
- The pointer files in satellite repos can use the meta repo's
  remote URL as a stable reference, even on machines that have not
  cloned every satellite locally.

Tradeoffs:
- The meta repo's commit history grows with manifest churn. Mitigated
  by keeping the manifest tidy (no auto-generated files, no
  reformatted YAML on every write).

Alternatives if the meta repo is unsuitable:
- A new tiny `<project>-polyrepo` repo dedicated to the manifest. Use
  this if the meta repo is restricted (different team owns it, or it
  is treated as production-critical and shouldn't accept
  documentation-style changes).

### `siblings_only`

The hard call. Two viable patterns:

**Option A — Shared parent directory:** `<parent-dir>/.polyrepo/`

- Simplest setup; no new repo required.
- **Not version-controlled** — the manifest lives outside any git
  repo, so it is local to the human's machine.
- Acceptable for solo projects or short-lived experiments.

**Option B — Dedicated meta repo:** create `<project>-polyrepo` and
store `.polyrepo/` inside it.

- Versions the manifest, makes it shareable, and gives a clear home
  for cross-repo concerns (the SAD, deploy scripts, runbooks) that
  otherwise have no obvious place to live.
- Requires creating one new repo. Often worth it the moment a second
  human or an agent on a different machine needs the manifest.

**Recommend Option B** if any of these are true:
- More than one human (or agent on more than one machine) will use
  the manifest.
- The project has lived more than ~3 months and is expected to keep
  growing.
- A cross-repo SAD or runbooks already exist (or are about to) and
  have no home.

Otherwise, recommend Option A and note in `open_questions` that
upgrading to a meta repo should be revisited.

### `monorepo_plus_satellites`

**Recommend:** inside the monorepo at `<monorepo>/.polyrepo/`, *if*
the monorepo is the de facto source of truth for the project.

Reasoning:
- Most contributors already work in the monorepo. The manifest is
  closest to where the work happens.
- A satellite-first storage location risks staleness, because
  satellites may be touched only occasionally.

Alternative: a dedicated meta repo, especially if the monorepo is
itself a single product (e.g., a frontend) and the satellites are
genuinely peer (e.g., a separate API and a separate mobile app).

### `scattered`

**Recommend:** create a dedicated `<project>-meta` repo and store
`.polyrepo/` there.

Reasoning:
- Without a shared parent directory, there is no neutral filesystem
  location.
- A dedicated repo makes the manifest portable, versioned, and
  explicitly owned.

Fallback if creating a repo is undesirable:
`~/.polyrepo/<project-name>/` on the human's machine. Note that this
is a local-only manifest and the steward will not be able to read it
on any other machine until the human chooses a sharable location.

### `remote_only`

**Recommend:** a dedicated `<project>-meta` repo.

Reasoning:
- This is by definition a setup where local layout cannot be relied
  on. The manifest must be addressable by URL.

Fallback: `~/.polyrepo/<project-name>/` for a single-human, local-only
arrangement.

### `hybrid`

Choose the strongest "anchor" piece — usually whichever sub-shape has
a meta or umbrella repo — and apply that kind's recommendation. Note
the hybridity in `topology.description` so it is not lost.

### `other`

No standard recommendation. Walk through the storage tradeoffs with the
human in plain language: version-controlled vs not, shareable vs local,
inside an existing repo vs a new repo. Let them decide.

## Greenfield mentor patterns

When the project is greenfield — repos do not yet exist or only a few
do — the steward's job is to help the human think through the design
before writing any of it down. Use these prompts.

**Question 1 — is a polyrepo even the right call?**

Polyrepo is appropriate when:
- multiple teams or owners need independent release cadences
- the components have genuinely different deploy lifecycles or runtime
  environments (e.g., a mobile app, a backend service, a public SDK,
  an ML model)
- one component is open-source and others are private
- the components have meaningfully different language toolchains and
  forcing them into one monorepo would require a heavy build system

A monorepo is often better when:
- the components share types, libraries, or build tooling extensively
- the same humans work across all of them
- atomic cross-component changes are common

If the human's situation pulls toward monorepo, say so. Recommending
*against* polyrepo when polyrepo is wrong is a service to them.

**Question 2 — if polyrepo, what shape?**

For a small project (2–5 repos): start `siblings_only` with a tiny
meta repo holding the manifest + the SAD. Cheap, flexible, easy to
restructure later.

For a medium project (5–20 repos): `meta_and_satellites` with a real
meta repo that holds deploy scripts, CI templates, the SAD, and the
manifest. The meta repo earns its keep.

For a large project (20+ repos): `meta_and_satellites` is almost
always right. Without a meta repo at this scale, knowledge becomes
tribal and undiscoverable.

For a project with one dominant component: consider
`monorepo_plus_satellites`, where the dominant component is the
monorepo and the satellites are anything that genuinely cannot live
inside it.

**Question 3 — what should the meta repo contain?**

Recommend the meta repo hold:
- `.polyrepo/manifest.yaml` (the steward's manifest)
- `adrs/` — architecture decision records
- `runbooks/` — operational docs that span repos
- `deploy/` — cross-repo deploy scripts, environment definitions
- `ci/` — shared CI templates (or links to where they live)
- `docs/` — onboarding, project-level architecture docs

This keeps the meta repo small, focused, and useful — not a dumping
ground.

## Walkthrough — Mark's example

> "1 command-and-control repository and ~63 repos. They share a
> common parent folder, separate from other local repos."

Inferred topology: `meta_and_satellites`. The C&C repo is the meta
repo; the 63 are satellites.

Recommended storage: `<C&C-repo>/.polyrepo/`. Reasoning:

- The C&C repo is already the place that knows about the others —
  its very purpose is cross-repo coordination.
- It is version-controlled. Every manifest change is committed
  alongside the change that motivated it (a new satellite, a renamed
  service, a deprecated repo).
- A new teammate or a new machine clones C&C and inherits the full
  project map for free, without first having to clone all 63
  satellites.
- The shared parent folder is a viable alternative but is unversioned
  and machine-local — every machine would have to be set up
  independently, and the manifest would silently drift.

Pointer files: drop `.polyrepo-pointer.json` at the root of every
satellite (and the C&C repo itself) pointing at the C&C
manifest path. This way, if the agent is invoked from inside any of
the 63 satellites, it can find the manifest with one read.

Recommend committing the pointer file unless the human prefers to
gitignore it — at this scale, committing means new clones are
immediately steward-aware.

This example is canonical: any time the human has a single
coordination hub plus many members, the recommendation is the same.
