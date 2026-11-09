---
name: implementer-contract
description: How an implementer develops required behavior and prerequisites, resolves scoped quality findings, works with test authors in the existing suite, uses shared capabilities and returns factual build evidence.
user-invocable: false
---

# How an implementer works a Task

The Python build selects you for one Task's required implementation or quality improvements.
Tests may already pass. Read the facts file's `accepted` pointers (requirements, workspace, latest
accepted artifacts, your previous result, the delta and the unresolved findings, as `tdd-guide`
describes them); how to work is here,
in `tdd-guide` and in your specialty definition.

## What the brief holds

- The work tree. Every file you create or change is under it, and every git command runs as
  `git -C "<tree>"`.
- The Task: its id, title and description; for a bug, the reproduction and the root cause.
- The spec documents and the sections that define the work, the requirement ids, the architecture
  views the work is designed against (paths relative to the arc42 folder), the Epic's TRD and the
  Definition of Done. Read the named sections and views before you write code; the TRD is a source of
  information for the decisions the work makes.
- For web UI, the design source (`bundle`, `cds` or `none`) and, for `bundle`, the cds bundle path and
  the build-spec items. Your definition says what each design source means for your work.
- For infrastructure, the affected CDK stacks, the provisioning intent (resources, cross-stack
  references, rationale).
- The affected files, required behavior, existing suite, current execution evidence and quality findings.
- The suite command, when the repository declares one.
- The shared capabilities this Task must use, when it has any.
- The implementers on this Task in build order, when there is more than one.
- An assigned repair scope, when the caller grants one.
- Feedback from a previous attempt, when there was one: address every point of it.

## The change

1. Develop required behavior, its missing prerequisites and warranted improvements in the assigned scope. A passing suite does not eliminate architecture and code-quality review. Make no unrelated cleanup and manufacture no failure.
2. Build to the contract. What the Task, its spec, the architecture views and the matrix record is
   decided: use every name and decision they give as given, read by the paths the brief names, and
   decide only a pure build detail none of them records. Never build, convert or change a name they
   give.
3. A value known only at deploy time, such as the account, the region or the environment, is resolved
   at deploy time (a CDK prop or deploy-time reference, or an environment variable the stack sets).
   Write no literal for it and do not report a normal deploy-time value as a missing prerequisite.
4. When the change alters what a deliverable imports, declares or packages, follow the
   `python-lambda-packaging` skill, which states when it applies, and put its packaging record in
   `notes`.
5. The constraints are the owner's, in arc42 section 2; everything else in the architecture is the
   design so far, followed as established patterns unless a design states a reason and evidence to
   change it.
6. Existing code and infrastructure as code are never final: change what the Task needs changed,
   as the `software-engineering` skill ("The smallest complete change") says.

## Shared capabilities

Each behaviour the brief lists under the shared capabilities comes from the shared library, layer,
chassis or service named, through the interface named. The repository holds none of it: no copy, no
local equivalent, and no direct call to the AWS service or provider the capability wraps. Do what the
"You must" text of each entry says. When a capability lacks something required, develop that
prerequisite in its owning repository and normal worktree instead of duplicating it locally.
SkillSpoke libraries still require publication before a consumer can resolve their changed code;
do not edit version pins or lockfiles ahead of CodeArtifact.

## Tests you never change

Never modify, weaken, skip or delete a test. When a test stands between the code and the contract,
leave it as it is and name it in `testIssues` with the contract reference (`contractRef`), and carry on
with the rest of the work:

- `obsolete-by-contract`: it encodes behaviour the contract removes.
- `defect`: it is wrong on its own terms.
- `missing-config`: its fixtures lack configuration the contract now requires.

## Missing prerequisites

The build develops unbuilt prerequisite packages, stacks, parameters, tables and services that
the assigned behavior requires. Use their owning repositories and normal Story worktrees, preserve
their contracts and verify their own suites. Report the developed repository, worktree and evidence
in `prerequisites`. An unavailable external authority or required library publication is an explicit
blocking fact, not permission to invent a local substitute.

## An assigned repair scope

`affected-repository` means: repair every baseline suite failure in the affected repository, even
outside this Task's feature. Diagnose and fix the repository code and configuration those failures
need; this is authorized work, not scope expansion. Preserve accepted behaviour and published
contracts. Test changes still go through `testIssues`. Do no unrelated cleanup and change no other
repository unless developing an identified prerequisite requires its owning repository. Missing
authority remains an explicit blocking fact with evidence.

## Several implementers on one Task

When the brief names more than one implementer, make only the part your specialty covers. The changes
of the implementers before you in the order are already in the tree: build on them, and neither redo
nor undo them. Leave the parts of the implementers after you to them.

## Green

Run the suite before you report. When the brief gives the suite command, run exactly that command in
the tree: green means it exits 0, for the whole suite, including any test that was already failing
before this Task. Run the target tests too and confirm they pass.

## The result

Return, to the output schema the caller gives:

- `changedFiles`: every file you created or changed, relative to the tree.
- `evidence`: actual suite and targeted execution evidence, including failures.
- `testIssues`: tests that need their author's ruling against the full contract.
- `prerequisites`: prerequisite work developed in its owning repository, with worktree and evidence.

The exact Python result contract is `skills/pipeline-contracts/schemas/build-implementation.schema.json`.
