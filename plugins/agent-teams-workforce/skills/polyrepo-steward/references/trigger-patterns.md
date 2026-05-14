# Trigger Patterns

The steward is meant to be pervasive. It loses most of its value if it
sits silent while an agent makes a feature plan that ignores three
downstream repos, or while a human renames a service without updating
the dependents. This file lists the SDLC moments where the steward
should activate — even when not explicitly invoked.

The bias is toward firing. A short, well-targeted reminder is cheap;
a missed warning is expensive.

## How to use this file

When the user's prompt is ambiguous about whether the steward is
relevant, scan this list. If any pattern matches, activate. If
multiple match, activate once and address all of them in a single
focused reply. If you fire and the user signals it was unwanted (a
quick "not now" or "I know"), record that in
`steward_preferences` so the same pattern does not over-fire next
time.

## Always-fire patterns

These are unambiguous. Activate without hesitation.

- The user mentions setting up, onboarding, or restructuring a
  polyrepo project.
- The user explicitly invokes the steward by name, or asks for "the
  project map", "the polyrepo manifest", "the cross-repo picture".
- The user asks "what repos are there", "where does X live", "who
  owns X", "what depends on X", "what does X depend on", "what's
  the deployment order", "what are the rules", or any minor
  variation.
- The user asks about cross-repo search ("how do I find X across all
  repos", "where is the auth code", etc.).
- The user mentions adding, renaming, archiving, or splitting a
  repo.
- The user mentions a new dependency, contract, or shared schema
  between repos.
- The user mentions a new architectural rule, naming convention,
  branching rule, or release rule that should apply across the
  project.

## Likely-fire patterns

These warrant activation in most contexts. Confirm relevance briefly
if the conversation has been narrowly scoped to a single repo.

- **Feature planning.** "I want to add X" — ask whether the feature
  is likely to touch more than one repo, then surface the manifest
  view. Even single-repo features often have downstream consumers.
- **Refactoring.** "I'm going to refactor X" — refactors that look
  local often ripple through shared contracts. Surface dependents
  before the refactor starts.
- **Renaming.** Any rename — function, type, file, package, repo —
  that is exported or referenced elsewhere should trigger a
  cross-repo check.
- **Dependency upgrades.** "I'm bumping X" — surface other repos
  that consume X.
- **API or contract changes.** "I'm changing the response shape of
  X" — surface every consumer.
- **Deployment work.** "I'm deploying X" — surface deployment order
  and any rules that apply.
- **Onboarding.** "Where do I start" / "How do I set up my dev env"
  — give them the manifest's view of the project and the relevant
  documentation pointers.
- **Code review preparation.** "I'm reviewing PR #X" — if the PR
  touches a repo with known dependents or rules, surface them.
- **Retros and postmortems.** "Why did X fail" — the manifest often
  contains rules or constraints that explain why something is the
  way it is.

## Conditional-fire patterns

These warrant activation only when context suggests cross-repo
relevance.

- The user is in a directory that contains a `.polyrepo-pointer.json`
  or whose parent contains `.polyrepo/`. Filesystem context is a
  strong signal that polyrepo work is happening, even if the prompt
  does not say so.
- The user mentions a name that you can identify as a repo in the
  manifest, even in passing.
- The user is doing infrastructure work (Terraform, Kubernetes
  manifests, CI templates) that often spans repos.
- The user is asking about deployment, environments, or
  observability — these typically span repos.

## Do-not-fire patterns

Stay quiet in these cases unless the user explicitly invokes the
steward.

- The user is doing tightly scoped work in a single file (writing a
  test, fixing a typo, formatting code).
- The user has just dismissed the steward (a "not now" or "I know"
  in the recent conversation) and is continuing the same line of
  work.
- The user is doing something unambiguously local (running a script
  in their home directory, configuring their shell, etc.).

## On false positives and false negatives

You will sometimes be wrong in both directions. Record both:

- **False positive** (steward fired when it shouldn't have): if the
  user signals the trigger was unwanted, capture a
  `steward_preferences` entry so the same pattern does not over-fire
  next time. Example: "stop reminding me about cross-repo
  implications when I'm working on a feature inside the docs repo."
- **False negative** (steward should have fired but didn't): if the
  human explicitly tells you "you should have warned me about Y", add
  a trigger pattern entry to the steward's tuning notes and capture
  it as a learning event. Over time, the trigger patterns become
  more accurate for this project specifically.

## When firing, lead with the relevance

The first sentence of any unsolicited steward intervention should
make its relevance obvious. Bad: "I'd like to remind you about the
project's structure." Good: "Heads up — three other repos depend on
the type you're about to rename, so this rename will need
coordinated changes." Lead with what the human needs to know, then
unpack as needed.
