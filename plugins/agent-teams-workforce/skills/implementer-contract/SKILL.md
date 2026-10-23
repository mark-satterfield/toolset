---
name: implementer-contract
description: How an implementer works a Task in TDD Green, the same for every implementer - the brief it is given, the minimum change that makes the failing tests pass, building to what the Task and the architecture record, the shared capabilities it must use, the tests it never changes (testIssues), what is missing outside the Task (upstreamMissing), an assigned baseline repair scope, working beside other implementers on one Task, the suite run that proves Green, and the result it returns. Loaded by every implementer; its own definition holds its specialty.
user-invocable: false
---

# How an implementer works a Task

The tdd-green workflow starts you for one Task whose failing tests already exist. It sends a brief
that holds only this Task's data; how to do the job is here and in your own definition.

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
- The affected files, the acceptance criteria, the failing tests and the Red evidence.
- The suite command, when the repository declares one.
- The shared capabilities this Task must use, when it has any.
- The implementers on this Task in build order, when there is more than one.
- An assigned repair scope, when the caller grants one.
- Feedback from a previous attempt, when there was one: address every point of it.

## The change

1. Make the failing tests pass with the minimum production change. Write nothing the tests and the
   acceptance criteria do not require.
2. Build to the contract. What the Task, its spec, the architecture views and the matrix record is
   decided: use every name and decision they give as given, read by the paths the brief names, and
   decide only a pure build detail none of them records. Never build, convert or change a name they
   give.
3. A value known only at deploy time, such as the account, the region or the environment, is resolved
   at deploy time (a CDK prop or deploy-time reference, or an environment variable the stack sets).
   Write no literal for it and never name it in `upstreamMissing`.
4. When the change alters what a deliverable imports, declares or packages, follow the
   `python-lambda-packaging` skill, which states when it applies, and put its packaging record in
   `notes`.
5. The constraints are the owner's, in arc42 section 2; everything else in the architecture is the
   design so far, followed as established patterns unless a design states a reason and evidence to
   change it.

## Shared capabilities

Each behaviour the brief lists under the shared capabilities comes from the shared library, layer,
chassis or service named, through the interface named. The repository holds none of it: no copy, no
local equivalent, and no direct call to the AWS service or provider the capability wraps. Do what the
"You must" text of each entry says. When a capability lacks something the Task needs, write nothing in
its place and name it in `upstreamMissing` with the evidence. After the suite is green,
`atw-matrix check-reuse` checks the files you changed against the list.

## Tests you never change

Never modify, weaken, skip or delete a test. When a test stands between the code and the contract,
leave it as it is and name it in `testIssues` with the contract reference (`contractRef`), and carry on
with the rest of the work:

- `obsolete-by-contract`: it encodes behaviour the contract removes.
- `defect`: it is wrong on its own terms.
- `missing-config`: its fixtures lack configuration the contract now requires.

## What is missing outside the Task

When the code cannot pass because a genuinely external dependency or resource does not exist yet (a
package, stack, parameter, table or service outside the assigned repair scope), name each such thing
in `upstreamMissing` with the evidence. A fixable defect or configuration inside an assigned repair
scope is not `upstreamMissing` merely because it predates this Task.

## An assigned repair scope

`affected-repository` means: repair every baseline suite failure in the affected repository, even
outside this Task's feature. Diagnose and fix the repository code and configuration those failures
need; this is authorized work, not scope expansion. Preserve accepted behaviour and published
contracts. Test changes still go through `testIssues`. Do no unrelated cleanup and change no other
repository. Missing external resources or authority remain `upstreamMissing`, with evidence.

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
- `greenConfirmed`: whether the target tests pass.
- `noRegressions`: whether the full suite shows no regression.
- `evidence`: the captured output of both runs.
- `testIssues` and `upstreamMissing`, as above.
- `notes`: anything else the result needs, such as a runtime or provisioning assumption the code
  makes (job parameters, stream names, batch sizes, workgroups, bucket expectations).
