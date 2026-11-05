# The pipelines: build

Parent: [The pipelines: overview](pipelines.md)

The build takes a Task under a Story and produces code and tests committed in the Story's
worktree, with its complete repository suite passing. The Python orchestrator owns ordering,
subprocesses, artifacts, correction bounds and journal transitions. Headless agent sessions do
reasoning, code, test and documentation work. No model session relays a command or parses its
exit status.

## Execution and resumption

`orchestrator/flows/task_to_deploy.py` is the `task-to-deploy` composite. The driver dispatches it
through `orchestrator/run.py`. `pipeline-steps.json` defines the up-front build plan and its
script keys. The shared journal reader/writer and `JournalRunner` preserve each step's UUID,
accepted artifacts and failure. Existing `build:*` keys remain valid across the Python cutover.
An interrupted build begins at its first unfinished step; accepted work is not discarded.

The driver validates transport arguments for the selected flow, then the shared
`task-build-args.schema.json` validates the build leaf. Its Task brief keeps the Story under
`bead.story` and the design choice under `bead.cdsDesignSource`, matching the actual producer.
Story deploy leaves use their own exact argument definitions. Host execution identity is
separate from leaf fields; obsolete relay and PR-command settings are not sent to Python builds.
The producer-contract checker includes the real dispatch builder/parser and checks the projected
Task fields against the canonical bead metadata.

Regression preparation includes the Task's supplied Spec and PRD paths as well as journal
source artifacts. Final verification names the source seal beside the accepted
`regressionScope` artifact with `--bindings`, so another step or resumed dispatch reads the
same approval evidence. Each verification keeps its own execution-output directory.

`build_workspace.py` calls the existing git utilities directly to create or reuse the Story's
worktree and independently confirm its repository and branch. Every command pins its working
directory. A Task cannot commit on the default branch or detached HEAD.

`build_sessions.py` plans actual reasoning agents as journal children. Their shared schemas,
facts file and current journal are passed by path. The journal runner owns session IDs,
resumption, output validation and acceptance. A missing dynamically selected specialist is an
item failure; a missing fixed contract is a pipeline defect.

## One Task

```mermaid
flowchart TD
    start([Task under its Story]) --> workspace[Create or reuse and verify Story worktree]
    workspace --> scope[Assess and independently review cumulative regression scope]
    scope --> setup[Apply reviewed setup and record whole-suite baseline]
    setup --> tests[Select specialists; review, update, refactor or add suite tests]
    tests --> suite[Run the whole suite directly]
    suite --> judgment{Trustworthy behavioral evidence?}
    judgment -->|Poor tests or setup| tests
    judgment -->|Environment prevents verification| stop[Record failure and preserve accepted work]
    judgment -->|Passing behavior or valid product failure| review[Review architecture, correctness, code and test quality]
    review --> needed{Required implementation or warranted improvement?}
    needed -->|Yes| code[Select specialists and develop behavior and prerequisites]
    code --> suite
    needed -->|No| checkpoint[Record Green checkpoint and snapshot]
    checkpoint --> refactor[Review and apply worthwhile scoped code and test refactoring]
    refactor --> regression{Whole suite still passes?}
    regression -->|No| restore[Restore Green snapshot and verify]
    regression -->|Yes| audits[Shared capability and applicable CDS review]
    restore --> audits
    audits --> docs[Update documentation made stale by the change]
    docs --> finalreview[Independent review of resulting code and test diff]
    finalreview --> final[Whole suite and mapped regression evidence verified]
    final --> commit[Commit through normal hooks on Story branch]
    commit --> done([Task built; driver closes Task])
```

Correction work is bounded within a dispatch. Implementation and suite-quality correction have
three rounds, and regression scope/mapping review permits two correction rounds. A later
dispatch does not inherit the earlier dispatch's consumed allowance. An unresolved correction
records its evidence and stops; no quality gate is bypassed.

## Tests and existing behavior

The PRD and TRD state requirements. Stories, specs, architecture and Task activities provide
implementation detail. Tests reflect that full contract in the existing suite; a Task is not
itself a replacement requirements document.

Test specialists consider happy paths, negative cases, edge cases and boundaries. They may
review, update and refactor existing tests as well as add new tests. Tests are code, and newly
written tests can be poor. A failing suite therefore receives a quality judgment before its
failure is treated as missing product behavior. The accepted route distinguishes test repair,
product implementation and environment failure.

Passing required behavior is valid evidence. The build manufactures no Red, performs no
sabotage and requires no test-the-test demonstration. Passing tests still leave architecture
conformance, correctness, quality and best practices to review. Refactoring receives an
opportunity every time; a justified no-change result is valid when no improvement is warranted.
Changes stay within the assigned behavior and its prerequisites.

`build_suite.py` uses an already recorded suite command or the repository's explicit Taskfile
`test` task. A genuinely unstructured or conflicting declaration receives one configuration
judgment, whose result is recorded and reused. No test framework command is guessed. Commands
execute through `Tools.command`; full stdout, stderr and exit status remain in evidence files.
A zero exit alone does not establish behavioral coverage. The approved regression mapping and
fresh execution evidence remain required.

## Prerequisites and shared capabilities

The build develops missing prerequisite services, libraries and infrastructure in their owning
repositories and normal worktrees. It does not merely stop because a prerequisite has not yet
been built, and it does not duplicate a shared capability locally. Required external authority
and unpublished SkillSpoke library changes remain explicit blocking facts under their existing
rules; a consumer pin or lockfile is never changed ahead of publication.

Shared-capability review considers the capabilities named by the Task's matrix IDs. UI work is
reviewed against the Task's stated supplied bundle or live CDS source. Blocking and warranted
improvement findings receive bounded implementation and re-review.

## Commit and completion

The build checkpoints a verified Green state before refactoring. A regressing refactor restores
that snapshot and verifies the suite again. Before final commit, an independent reviewer inspects
the resulting code and test diff, the complete suite passes, and the cumulative regression tools
verify the mapped evidence. Repository hooks run normally at commit. A rejected hook or dirty
post-hook tree is a recorded work failure, never a reason to bypass hooks.

The Task's build sets no matrix approval or verified gate. The Story's deployment follows only
when its Tasks are built, as described in [deploy](pipelines-deploy.md).
