# The pipelines: deploy

Parent: [The pipelines: overview](pipelines.md)

The deploy pipeline runs once per Story. It takes in a Story whose Tasks are all built on the
Story's branch, and produces the Story's repository published and deployed to AWS dev and
verified, the record of what was built (the effective arc42 documents corrected to match the
code), and one merged pull request; when the pull request merges, the driver sets the matrix's
verified mark on what the Story built and closes the Story. The driver
(`ops/sdlc-automation/storydeploy.py`, composite `story-deploy`, runner `driver` in
`skills/pipeline-contracts/schemas/composites.json`) runs the steps of the Story's step journal
itself and dispatches three workflow scripts for the steps that need an agent:
`workflows/deploy-mechanism.js`, `workflows/story-deploy-fix.js` and
`workflows/built-version.js`; `workflows/settle.js` commits a fix, and the `shepherd-pr` skill
works the pull request until it qualifies for merging. The steps are defined in
`skills/pipeline-contracts/schemas/pipeline-steps.json` (pipeline `deploy`). The requirements are
`blueprint/requirements/pipelines.md` (the Deploy row, and "The matrix in the build and deploy
lanes", which makes the Deploy table D1 to D10 of section 4 of `blueprint/design/matrix.md` the
specification), requirements R24 to R26, R29, R39, R42 and R46 of
`blueprint/requirements/matrix.md`, and the owner's statements of 2026-10-19 quoted below.

## Legend

| Notation | Meaning |
|---|---|
| `->>` (sequence) | a call or a dispatch: the caller starts the work |
| `-->>` (sequence) | the return of that call |
| `-)` (sequence) | an asynchronous message, or a write to a store with no reply |
| `([...])` (activity) | start or end |
| `{...?}` (activity) | a decision; each outgoing edge is labelled with its guard |
| `fork` / `join` nodes (activity) | concurrent work starts / ends |
| `[*]` (state machine) | initial or terminal state; transitions read "event [guard] / effect" |
| "arc42 (vault)", "matrix", "beads", "vault", "git / GitHub" | the stores, named the same everywhere |
| note "differs from required" | the as-built behaviour differs from the requirement named |
| "assumption" | an element neither the requirements nor the code specifies |

The owner's statements of 2026-10-19 this document draws as required:

- "Once all of the tasks for all of the stories for and Epic have been built and tested (including CI (CDK), which means deployemen must also work), then all of the architecture and rellationships for the Epic can be set to verified."
- "The matrix does not include stories and tasks (it isn't a build tracker), and it doesn't care about what has actually been deployed."
- "I do prefer to spin up agents in headless claude sessions to do work, and then get out."
- "arc42 is both input and out. The matrix is both input and output."

## 1. The Story deploy, step by step

**Subject.** The steps of one Story's deploy journal, in the order they run, with the steps each
step's result adds.
**Scope.** One Story, from the dispatch that finds every Task closed to the Story's close.
**Purpose.** Show the control flow: which steps are planned up front, which a result adds, where
the fix loop and the waits are, and where the pipeline stops.
**Boundary.** Outside: how the driver selects the Story (see
[The pipelines: driver and routing](pipelines-driver.md)), and the inside of the three workflow
steps (sections 3, 4 and 5).
**Basis.** As built: `pipeline-steps.json` pipeline `deploy` (`plan`, `inner`, `kinds.*.adds`,
`limit`, `waits`); `storydeploy.py` `STEPS` and the step functions `_mechanism_step` (line 1164)
to `_close_step` (line 1508), `_failed_attempt` (line 1125, `MAX_FIX_ATTEMPTS = 3`, line 178),
`_run_journal` (line 1594). Required, by the parts that cite it: the Deploy row of
`requirements/pipelines.md`.

```mermaid
flowchart TD
  S(["Dispatch: Story has every Task closed"]) --> M["deploy:mechanism<br/>deploy-mechanism.js, polyrepo-steward"]
  M --> MQ{"mechanism ruled?"}
  MQ -->|"no ruling, or publishes with no command and no deploy"| STOP1(["Story fails at mechanism, item failure recorded"])
  MQ -->|"ruled"| W["deploy:workspace<br/>reuse or open .worktrees/STORY-REPO on branch story/STORY"]
  W --> WQ{"Tasks exist and no Story branch?"}
  WQ -->|"yes"| STOP2(["Story fails at workspace"])
  WQ -->|"no"| PQ{"publishes a package?"}
  PQ -->|"yes: add deploy:publish"| P["deploy:publish<br/>run publishCommand"]
  PQ -->|"no, deploys: add deploy:synth"| SY
  PQ -->|"neither"| CA
  P --> PO{"publish exit 0?"}
  PO -->|"yes and deploys: add deploy:synth"| SY["deploy:synth<br/>task install, cdk synth"]
  PO -->|"yes, no CDK"| CA
  PO -->|"no"| FL
  SY --> SO{"synth exit 0?"}
  SO -->|"yes: add deploy:ssm-check"| SSM["deploy:ssm-check<br/>aws ssm get-parameters"]
  SO -->|"no"| FL
  SSM --> SQ{"every parameter exists?"}
  SQ -->|"no"| WAIT1["step stays running, handback waiting-for-ssm<br/>driver probes every 300 s before the next dispatch"]
  WAIT1 -->|"next dispatch"| SSM
  SQ -->|"yes: add deploy:deploy"| DP["deploy:deploy<br/>cdk deploy --all"]
  DP -->|"always: add deploy:verify"| V["deploy:verify<br/>describe-stacks, git status"]
  V --> VQ{"every stack CREATE_COMPLETE or UPDATE_COMPLETE and tree clean?"}
  VQ -->|"no"| FL
  FL{"3 deploy:fix steps already done?"}
  FL -->|"yes"| STOP3(["step fails, deploy-fix-exhausted"])
  FL -->|"no: record deployFailure, add deploy:fix then publish when it publishes, then synth"| FX["deploy:fix<br/>story-deploy-fix.js, cdk-stack-author"]
  FX --> FQ{"fix ok?"}
  FQ -->|"no-change, or not committed"| STOP4(["deploy:fix fails, Story stops"])
  FQ -->|"fixed and committed"| AGAIN["the added publish or synth runs again"]
  AGAIN --> PQ2{"publishes?"}
  PQ2 -->|"yes"| P
  PQ2 -->|"no"| SY
  VQ -->|"yes"| CA["deploy:commits-ahead<br/>git rev-list --count base..HEAD"]
  CA --> CQ{"commits ahead of the default branch?"}
  CQ -->|"0"| CL
  CQ -->|"1 or more: add built-version, pull-request, merge-wait"| BV["deploy:built-version<br/>built-version.js"]
  BV --> BQ{"built-version ok?"}
  BQ -->|"no"| STOP5(["deploy:built-version fails"])
  BQ -->|"yes"| PR["deploy:pull-request<br/>skillspoke-pr, opens the PR, arms auto-merge, hands it to the shepherd"]
  PR --> MW["deploy:merge-wait<br/>gh pr view state"]
  MW --> MQ2{"MERGED?"}
  MQ2 -->|"no"| WAIT2["step stays running, handback pr-open<br/>driver probes every 120 s"]
  WAIT2 -->|"next dispatch"| MW
  MQ2 -->|"yes"| CL["deploy:close<br/>verified mark when a PR merged, bd close, remove worktree and branch"]
  CL --> E(["Story closed"])
```

Differences from the requirements:

- The Deploy row of `requirements/pipelines.md` takes in "A Story whose Tasks are all built" and
  produces "one merged pull request". As built, a Story whose branch holds no commit
  (`commits-ahead` 0) closes with no pull request and no built-version step, and a Story with no
  Task at all is deployed once its Epic's elaboration is done (`storyorder.startable_without_tasks`,
  line 116). Neither case is covered by a requirement; both are as built only.
- A repository that neither publishes nor deploys is not stopped: `mechanism_of` returns a
  mechanism with both false (`_nothing_to_ship`, line 949), and the Story goes on to
  commits-ahead, the built-version step, a pull request and the close. Only a repository that
  publishes with no publish command and does not deploy stops (`_no_mechanism`, line 943). As
  built only.

## 2. Where the deploy reads and writes the stores

**Subject.** The stores each deploy step reads and writes.
**Scope.** Every step of section 1, and the shepherd of the pull request.
**Purpose.** Show where arc42 (vault), the matrix, beads, the vault, git / GitHub, AWS dev and the
step journal are touched, and set the required matrix reads beside the as-built ones.
**Boundary.** Outside: the build pipeline's writes to the same Story branch.
**Basis.** Required: the Deploy table D1 to D10 of `blueprint/design/matrix.md` section 4, made
required by `requirements/pipelines.md` ("The matrix in the build and deploy lanes"); R29, R39,
R46. As built: `storydeploy.py`, `deploy-mechanism.js`, `story-deploy-fix.js`, `built-version.js`,
`scripts/portfolio/depscore.py` `_sync_documents` (line 243) and `_dispatch_arch_built_remove`
(line 1854), `ops/sdlc-automation/matrixmarks.py` `verified` (line 342).

| Step | git / GitHub | AWS dev | beads | step journal |
|---|---|---|---|---|
| deploy:mechanism | the repository's declarations, read by `polyrepo-steward` | none | none | done with `mechanism` |
| deploy:workspace | `git worktree add`, `rev-parse` | none | none | `worktree`, `branch` |
| deploy:publish | none | CodeArtifact through `publishCommand` | none | `publishedHead` or `deployFailure` |
| deploy:synth, deploy:ssm-check | none | SSM `get-parameters` | none | `assembly`, `ssmParameters` |
| deploy:deploy, deploy:verify | `git status` | `cdk deploy --all`, CloudFormation `describe-stacks` | none | `deployOutput`, `stacks` or `deployFailure` |
| deploy:fix | a commit on the Story branch | `describe-stack-events`, read only | none | `fix` and the child steps |
| deploy:built-version | the worktree at HEAD, read | none | none | `built` and the child steps |
| deploy:pull-request, deploy:merge-wait | push, pull request, `gh pr view` | none | none | `pullRequest`, `pullRequestState` |
| deploy:close | `gh pr view` merge commit, `worktree remove`, `branch -D`, push of `matrix.json` | none | `bd close` of the Story | `closed` |

```mermaid
flowchart LR
  MEC["deploy:mechanism"]
  DEP["deploy:deploy"]
  FIX["deploy:fix"]
  BV["deploy:built-version"]
  CLS["deploy:close"]
  MTX[("matrix")]
  ARC[("arc42 (vault)")]
  MEC -.->|"required D1, not read as built"| MTX
  DEP -.->|"required D4, not read as built"| MTX
  FIX -.->|"required D5, not read as built"| MTX
  BV -->|"reads built --story, story-scope"| MTX
  BV -->|"writes built views, corrects, sets effective, removes"| ARC
  BV ==>|"sync-documents, differs from required D7 and R46"| MTX
  CLS ==>|"verify --story, commit --bead"| MTX
```

In the diagram a dotted edge is a matrix read the requirements call for and the code does not make,
and a thick edge is a write.

Differences from the requirements:

- D1 (Mechanism) requires the stack's `executionUse`, `distributedAs`, `commands.publish` and
  `commands.deploy` to be read from the matrix, with the steward session run only when one is
  absent. As built the `polyrepo-steward` session runs on every Story and the matrix is not read
  (`deploy-mechanism.js` holds no `atw-matrix` call; `storydeploy.mechanism_of`, line 955).
- D2 (Publish) requires `distributedAs`; as built the publish runs the steward's `publishCommand`.
- D4 (Deploy) requires the stack's `commands.deploy`; as built the driver runs
  `cdk deploy --all --require-approval never` (`storydeploy.deploy`, line 551).
- D5 (Deploy fix) requires `node stack:<id>` and `deps --of` for the failed stacks; as built the
  fixer's brief carries the failed step, its output and the stack statuses, and no matrix read.
- D7 (Built correction) and R46 require that the deploy records nothing in the matrix except the
  verified mark ("A deploy adds no new facts to the matrix"; R29 "changes nothing but the verified
  mark"). As built `depscore.py arch-approve` and `arch-built-remove`, which the built-version
  step runs, also bring the matrix's `document` entries of the files they touch up to date
  (`_sync_documents`, which writes the matrix through `update_matrix`).
- R30 and R38 require a step to look up what the matrix holds rather than rediscover it; the
  mechanism ruling rediscovers from the repository's own files what the matrix's stack records
  would answer.

## 3. deploy:mechanism (`workflows/deploy-mechanism.js`)

**Subject.** The ruling of what the Story's repository publishes and deploys.
**Scope.** The `deploy:mechanism` step.
**Purpose.** Show the agent the step starts, what it receives and what it returns.
**Boundary.** Outside: the publish and deploy commands themselves (section 4).
**Basis.** As built: `storydeploy.py` `_mechanism_step` (line 1164), `mechanism_of` (line 955),
`_usable` (line 1001), `_excluded_repositories` (line 924); `deploy-mechanism.js` (the
`polyrepo-steward` call, line 290; arguments `DeployMechanismArgs` in the `story-deploy-args`
shared block). Required: D1 of the Deploy table (see section 2).

```mermaid
sequenceDiagram
  autonumber
  participant DRV as Driver storydeploy.py
  participant WF as deploy-mechanism.js headless Workflow session
  participant PS as polyrepo-steward
  box rgb(235,240,245) Stores
    participant GIT as git / GitHub repository files
    participant MTX as matrix
    participant JRN as step journal
  end
  DRV-)JRN: start deploy:mechanism
  alt the repository is the control repository or the repository holding the architecture
    DRV-)JRN: done, mechanism publishes false, deploys false
  else any other repository
    DRV->>WF: dispatch deploy-mechanism with story, repoPath
    WF->>PS: brief - the repository path, rule publishes, publishCommand, deploys, reason, read only
    PS->>GIT: read AGENTS.md or CLAUDE.md, CI workflows, package manifest, CDK app
    GIT-->>PS: the declarations
    PS-->>WF: repository, publishes, publishCommand, deploys, reason
    WF-->>DRV: handback ok, stage ask, mechanism
    Note over DRV,MTX: differs from required D1 - the stack's executionUse, distributedAs and commands are not read from the matrix, and the steward runs every time
    alt no ruling
      DRV-)JRN: fail deploy:mechanism
    else publishes with no publishCommand and no deploy
      DRV-)JRN: fail deploy:mechanism, stage no-deploy-mechanism
    else publishes with no publishCommand and deploys
      DRV-)JRN: done, mechanism with publishes set false, deploy only
    else ruled
      DRV-)JRN: done, artifact mechanism
    end
  end
```

## 4. Workspace, publish, synth, SSM check, deploy and verify

**Subject.** The steps the driver runs itself, with no agent.
**Scope.** `deploy:workspace`, `deploy:publish`, `deploy:synth`, `deploy:ssm-check`,
`deploy:deploy`, `deploy:verify`, and the failure that adds a fix.
**Purpose.** Show the commands, what each records in the journal, and the two kinds of stop: a
wait and a fix.
**Boundary.** Outside: the fix itself (section 5).
**Basis.** As built: `storydeploy.py` `_workspace_step` (line 1177), `open_worktree` (line 717),
`_publish_step` (line 1204), `publish` (line 423), `_synth_step` (line 1223), `synth` (line 440,
`task install` when the Taskfile declares it, then `cdk synth --quiet --output cdk.out`),
`_ssm_check_step` (line 1256), `ssm_reads` (line 488, parameters of type
`AWS::SSM::Parameter::Value<...>`), `missing_parameters` (line 513), `_deploy_step` (line 1275),
`_verify_step` (line 1290), `verify` (line 592), `_failed_attempt` (line 1125), `wait_of`
(line 1798). Required: the Deploy row of `requirements/pipelines.md` ("published and deployed to
the development environment and verified").

```mermaid
sequenceDiagram
  autonumber
  participant DRV as Driver storydeploy.py
  box rgb(235,240,245) Stores and services
    participant GIT as git / GitHub Story repository
    participant CA as AWS dev CodeArtifact
    participant SSM as AWS dev SSM Parameter Store
    participant CFN as AWS dev CloudFormation
    participant JRN as step journal
  end
  DRV->>GIT: existing worktree for the Story, else worktree add .worktrees/STORY-REPO on story/STORY
  GIT-->>DRV: worktree path, branch
  DRV-)JRN: done deploy:workspace, artifacts worktree, branch, adds publish or synth
  opt the mechanism publishes
    DRV->>CA: run publishCommand in the worktree, 1800 s limit
    CA-->>DRV: exit status
    DRV-)JRN: done deploy:publish, publishedHead, adds synth when it deploys
  end
  opt the mechanism deploys with CDK
    DRV->>DRV: task install when declared, cdk synth into cdk.out
    DRV-)JRN: done deploy:synth, assembly, adds ssm-check
    DRV->>SSM: get-parameters for every SSM parameter the templates read, per region, 10 at a time
    SSM-->>DRV: InvalidParameters
    alt a parameter is missing
      DRV-->>DRV: handback waiting-for-ssm, the step stays running
      Note over DRV,SSM: before each later dispatch wait_of probes the parameters again, every 300 s at most
    else all present
      DRV-)JRN: done deploy:ssm-check, ssmParameters, adds deploy
      DRV->>CFN: cdk deploy --all --require-approval never, 7200 s limit
      CFN-->>DRV: exit status, output tail
      DRV-)JRN: done deploy:deploy, deployOutput, adds verify
      DRV->>CFN: describe-stacks for every stack in the assembly
      CFN-->>DRV: StackStatus, StackStatusReason
      DRV->>GIT: git status --porcelain --untracked-files=no
      GIT-->>DRV: uncommitted files
      alt every stack CREATE_COMPLETE or UPDATE_COMPLETE, and the tree clean
        DRV-)JRN: done deploy:verify, stacks
      else fewer than 3 fixes done
        DRV-)JRN: done with deployFailure, adds deploy:fix with the failure, then publish when it publishes, then synth
      else 3 fixes done
        DRV-)JRN: fail the step, deploy-fix-exhausted
      end
    end
  end
  Note over DRV,JRN: a failed publish or synth takes the same branch as a failed verify, with the publish or synth named as the failed step
```

Assumptions: none.

Differences from the requirements: none beyond D2 and D4 in section 2. No requirement says how
"verified" is judged for a deploy; as built it is CloudFormation stack status plus a clean
worktree. The workflow `workflows/deploy.js` (a `smoke-test-author` suite run against the deployed
endpoints, then a `cdk-stack-author` deploy) is not declared in `composites.json` and nothing
dispatches it, so no smoke test runs in the deploy pipeline.

## 5. deploy:fix (`workflows/story-deploy-fix.js`)

**Subject.** The fix of a failed publish, synth, deploy or verification.
**Scope.** The `deploy:fix` step and its three child steps.
**Purpose.** Show the agent, what it receives, what is measured rather than taken from its report,
and how the commit lands on the Story branch.
**Boundary.** Outside: the redeploy after the fix (section 4 runs again).
**Basis.** As built: `storydeploy.py` `_fix_step` (line 1338); `story-deploy-fix.js` `stepAuthor`
(the `cdk-stack-author` call, line 1134), `stepVerify` (the `TREE_PY` git status read and the
synth test run through `relayrun.py`), `stepCommit` (`settle` with `commitOnly`); `settle.js`
`commitRun` (the `github-actions-pipeline-implementer` commit session); `pipeline-steps.json`
`inner["deploy:fix"]`.

```mermaid
sequenceDiagram
  autonumber
  participant DRV as Driver storydeploy.py
  participant WF as story-deploy-fix.js headless Workflow session
  participant RR as relayrun.py
  participant CSA as cdk-stack-author
  participant ST as settle.js commitOnly
  participant GAI as github-actions-pipeline-implementer
  box rgb(235,240,245) Stores
    participant GIT as git / GitHub Story worktree
    participant JRN as step journal
  end
  DRV-)JRN: start deploy:fix
  DRV->>WF: dispatch with journal path, run, step, story, tree, failed step, output, stacks, pluginRoot, relay
  WF->>RR: atw-step-journal read
  RR-->>WF: the journal
  opt deploy:fix has no child steps
    WF-)DRV: STEP-JOURNAL add fix-author, fix-verify, fix-commit
  end
  WF-)DRV: STEP-JOURNAL start deploy:fix-author
  WF->>CSA: brief - tree, branch, what failed, stacks, last 12000 characters of output. Find the cause, fix in the tree, run the synth assertion tests, never deploy, commit or push
  CSA->>GIT: read the code, aws cloudformation describe-stack-events read only, edit
  CSA-->>WF: cause, changedFiles, testCommand, evidence
  WF-)DRV: STEP-JOURNAL done fix-author, fixCause, fixTestCommand
  WF-)DRV: STEP-JOURNAL start deploy:fix-verify
  WF->>RR: git status --porcelain in the tree
  RR-->>WF: the changed files
  alt no file changed
    WF-)DRV: STEP-JOURNAL fail fix-verify, no-change
    WF-->>DRV: handback not ok, stage no-change
  else files changed
    opt the fixer named a test command
      WF->>RR: /bin/sh -c testCommand in the tree, 540 s limit
      RR-->>WF: exit status, tail
    end
    WF-)DRV: STEP-JOURNAL done fix-verify, fixChangedFiles, fixTestsPassed
    WF-)DRV: STEP-JOURNAL start deploy:fix-commit
    WF->>ST: commit the tree, message fix the deploy of Story STORY - cause
    ST->>GAI: commit every change, type(scope) message, no --no-verify, no push
    GAI->>GIT: git add -A, git commit
    GAI-->>ST: blocked list
    ST-->>WF: status reported, commit head
    WF-)DRV: STEP-JOURNAL done fix-commit, fixCommit
    WF-->>DRV: handback ok, stage fixed, cause, changedFiles, testsPassed, commit
  end
  DRV->>DRV: apply every STEP-JOURNAL line with journal_lines.py
  alt fixed
    DRV-)JRN: done deploy:fix, artifact fix
  else not fixed
    DRV-)JRN: fail deploy:fix, the Story stops
  end
```

Differences from the requirements: D5 (section 2). The fix is committed whether the synth
assertion tests passed or not: `testsPassed` false, or no test command named, does not stop the
fix (`stepVerify`); the redeploy and verification decide. No requirement covers this; as built
only.

## 6. deploy:built-version (`workflows/built-version.js`)

The built-version step is drawn twice: the control flow of its child steps (6.1) and the agents,
stores and commands of each child step (6.2).

### 6.1 The child steps

**Subject.** The child steps of `deploy:built-version` and the correction and review loop.
**Scope.** One Story's built-version step.
**Purpose.** Show when a comparison writes nothing, when a correction runs, and how the review
loop ends.
**Boundary.** Outside: the agents' prompts (6.2).
**Basis.** As built: `pipeline-steps.json` `inner["deploy:built-version"]` and the
`deploy:built-*` kinds; `built-version.js` `stepSnapshot`, `stepCompare`, `stepCorrect`,
`stepReview` (`MAX_CORRECTIONS = 2`), `stepApprove`, `stepRemove`; `storydeploy.py`
`_built_version_step` (line 1403), `built_args` (line 795). Required: D6 and D7 of the Deploy
table.

```mermaid
flowchart TD
  A(["deploy:built-version starts, the driver dispatches built-version.js"]) --> SN["deploy:built-snapshot<br/>fingerprint and copy section 2, fingerprint arc42/, target/, built/"]
  SN --> CMP["deploy:built-compare"]
  CMP --> Q1{"the Story's Tasks state a stack or an entry of the matrix?"}
  Q1 -->|"neither"| OK1(["done, nothing compared, stage matches"])
  Q1 -->|"entries but no stack"| F1(["step fails"])
  Q1 -->|"a stack"| CC["built-architecture-comparer writes a view per difference in built/ELEMENT/"]
  CC --> Q2{"section 2 unchanged and every write under built/?"}
  Q2 -->|"no"| F2(["step fails, section 2 put back"])
  Q2 -->|"yes"| Q3{"differences recorded?"}
  Q3 -->|"none"| OK2(["done, stage matches"])
  Q3 -->|"some, every built view in-review: add correct and review"| COR["deploy:built-correct<br/>architecture-maintainer"]
  COR --> Q4{"wrote only under arc42/ and outside section 2, and a pass answering findings changed a file?"}
  Q4 -->|"no"| F3(["step fails"])
  Q4 -->|"yes"| REV["deploy:built-review<br/>architecture-conformance-reviewer"]
  REV --> Q5{"conforms, and every corrected file reviewed?"}
  Q5 -->|"no, fewer than 2 corrections answered findings: add correct and review"| COR
  Q5 -->|"no, 2 corrections answered findings"| F4(["step fails"])
  Q5 -->|"yes, section 2 unchanged: add approve and remove"| APP["deploy:built-approve<br/>depscore.py arch-approve sets the corrected files effective"]
  APP --> REM["deploy:built-remove<br/>depscore.py arch-built-remove deletes matched built views and commits"]
  REM --> Q6{"a built view left that the effective version does not match?"}
  Q6 -->|"yes"| F5(["step fails, the view stays in built/"])
  Q6 -->|"no"| OK3(["done, stage recorded"])
```

### 6.2 The agents and stores of the built-version step

**Subject.** What each built-version child step sends to its agent or command and what comes back.
**Scope.** The child steps of 6.1.
**Purpose.** Show where the matrix is read, where arc42 (vault) is written, and what is measured.
**Boundary.** Outside: the step journal changes, which follow the pattern of section 5.
**Basis.** As built: `built-version.js` (`matrixCommand`, `depscore`, `treeSnapshot`,
`constraintsGuard`, and the step functions of 6.1); `depscore.py` `arch-constraints`,
`arch-snapshot`, `arch-state`, `arch-approve`, `arch-built-remove`, `_sync_documents` (line 243).
Required: D6 (`built --story`, then `story-scope`), D7, R29, R46.

```mermaid
sequenceDiagram
  autonumber
  participant WF as built-version.js headless Workflow session
  participant DS as depscore.py through relayrun.py
  participant AM as atw-matrix through relayrun.py
  participant BAC as built-architecture-comparer
  participant MAI as architecture-maintainer
  participant ACR as architecture-conformance-reviewer
  box rgb(235,240,245) Stores
    participant ARC as arc42 (vault)
    participant MTX as matrix
    participant GIT as git / GitHub Story worktree
  end
  WF->>DS: arch-constraints --keep, arch-snapshot --save tree-start
  DS->>ARC: hash section 2 and every file of arc42/, target/, built/
  WF->>AM: built --story STORY
  AM->>MTX: match the Story's Tasks' matrix_elements ids against entries
  AM-->>WF: stacks, entries
  loop each stack the Story built
    WF->>AM: story-scope --stack STACK --ids ENTRIES
    AM-->>WF: documents and headings that describe each entry
  end
  WF->>BAC: brief - the worktree at HEAD, the stacks and entries with their approved headings, where arc42 and built/ are, the documentation model
  BAC->>GIT: git grep, git show HEAD
  BAC->>ARC: read the headings, write one built view per difference, lifecycle_state in-review
  BAC-->>WF: differences with citations file and line, files written
  WF->>DS: arch-constraints, arch-snapshot --against tree-start, arch-state of the built views
  opt differences recorded
    loop until the review conforms, at most 2 corrections answering findings
      WF->>MAI: brief - the built views, correct arc42/ to match, nothing in section 2, findings of the last review
      MAI->>ARC: edit and add effective views
      MAI-->>WF: changed, created, deleted, matched, constraintIssues, contradictions
      WF->>DS: arch-snapshot --against the earlier fingerprints
      WF->>ACR: brief - the built views, the corrected files, the previous findings
      ACR->>ARC: read
      ACR-->>WF: conforms, findings, reviewedFiles, matchedBuiltViews
    end
    WF->>DS: arch-approve --arch-files corrected --reviewed-files reviewed
    DS->>ARC: set lifecycle_state effective
    DS-)MTX: sync-documents of those files
    WF->>DS: arch-built-remove --files matched --message
    DS->>ARC: delete the matched built views and commit the removal
    DS-)MTX: sync-documents of those files
    Note over DS,MTX: differs from required D7 and R46 - the deploy records nothing in the matrix but the verified mark
  end
  WF-->>WF: handback matches or recorded, counts to the driver
```

Differences from the requirements: the matrix write of D7 and R46 (section 2). The built-version
step corrects arc42 and writes no other matrix fact, which matches R29 ("A build or deploy run
reports what it finds wrong and changes nothing but the verified mark") except for that
document sync.

## 7. Pull request, shepherd and merge

**Subject.** The Story's one pull request from open to merged.
**Scope.** `deploy:pull-request` and `deploy:merge-wait`, and the shepherd that runs beside them.
**Purpose.** Show who opens the pull request, who works it until it qualifies, who merges it, and
how the driver learns it merged.
**Boundary.** Outside: the inside of one `fix-pr` pass (`commands/fix-pr.md`).
**Basis.** As built: `storydeploy.py` `_pull_request_step` (line 1429), `open_pr` (line 643, the
command `atw.pr_command()`, which is `skillspoke-pr`; exit 3 means the pull request is open and
auto-merge is not armed), `_merge_wait_step` (line 1460), `wait_of` (line 1798);
`/Users/msat1971/.local/bin/skillspoke-pr` (CodeRabbit review comment, auto-merge, the shepherd
hand-off); `ops/shepherd-prs.sh` (lock, `gitutils.py provision`, the headless session,
`gitutils.py cleanup-merged-pr`); `skills/shepherd-pr/SKILL.md` and `scripts/shepherd-pr.sh`;
`commands/fix-pr.md`. Required: the Deploy row of `requirements/pipelines.md` ("one merged pull
request").

```mermaid
sequenceDiagram
  autonumber
  participant DRV as Driver storydeploy.py
  participant SPR as skillspoke-pr
  participant SH as shepherd-prs.sh
  participant SK as shepherd-pr skill loop, headless session
  participant FP as fix-pr pass, headless session
  box rgb(235,240,245) Stores
    participant GH as git / GitHub pull request
    participant JRN as step journal
  end
  DRV->>SPR: --title feat(REPO) Story title --body Tasks, stacks deployed and verified, run in the worktree
  SPR->>GH: push story/STORY, open the PR, comment @coderabbitai full review
  SPR->>GH: gh pr merge --auto with the method the repository allows
  SPR-)SH: nohup shepherd-prs.sh PR, detached
  SPR-->>DRV: PR URL, exit 0, or 3 when auto-merge is not armed
  DRV-)JRN: done deploy:pull-request, pullRequest
  SH->>SH: per-PR lock, gitutils.py provision reuses the worktree registered for the branch
  SH->>SK: one headless claude session runs the shepherd-pr skill
  loop until the PR qualifies for merging, or 3 passes change nothing, or 7200 s of waiting
    SK->>GH: read checks, threads, reviews, merge state
    alt something keeps the PR from qualifying
      SK->>FP: claude --print /agent-teams-workforce:fix-pr PR in the worktree
      FP->>GH: fix checks and conflicts, reply, resolve threads, push, audit comment
    else checks still running or merge state blocked
      SK->>SK: wait and poll, no session spent
    end
  end
  SK-->>SH: ending qualifies, merged, closed or could-not-fix
  GH->>GH: auto-merge merges the qualifying PR
  SH->>SH: gitutils.py cleanup-merged-pr --worktree --wait
  DRV-)JRN: start deploy:merge-wait
  DRV->>GH: gh pr view state
  alt not MERGED
    DRV-->>DRV: handback ok, stage pr-open, the step stays running
    Note over DRV,GH: before each later dispatch wait_of reads the state again, every 120 s at most
  else MERGED
    DRV-)JRN: done deploy:merge-wait, pullRequestState MERGED
  end
```

Assumptions: none. The shepherd never merges (`Bash(gh pr merge:*)` is denied in every pass);
GitHub auto-merge merges.

## 8. deploy:close and the verified mark

### 8.1 What the close does

**Subject.** The close of a Story and the one matrix write of the deploy.
**Scope.** `deploy:close`.
**Purpose.** Show where the verified mark is set, on what, and what else the close does.
**Boundary.** Outside: the Epic, which the deploy never closes.
**Basis.** As built: `storydeploy.py` `_close_step` (line 1508), `_mark_verified` (line 898),
`merge_commit` (line 875), `_remove_workspace` (line 1476); `matrixmarks.py` `verified`
(line 342, role `build-driver` in `ATW_MATRIX_ROLE`); `blueprint/design/matrix.md` 1.4 and 1.5
(`atw-matrix verify`, `built --story`). Required: R24, R25, R39, R42, R46; the owner statement of
2026-10-19 on verified, and item 1.8 of the approved naming follow-ups
(`claude-inbox/naming-followups-2026-10-17.md`, lines 172 to 193).

```mermaid
sequenceDiagram
  autonumber
  participant DRV as Driver storydeploy.py
  participant MM as matrixmarks.py
  participant AM as atw-matrix, role build-driver
  box rgb(235,240,245) Stores
    participant GH as git / GitHub
    participant MTX as matrix
    participant BDS as beads
    participant JRN as step journal
  end
  DRV-)JRN: start deploy:close
  opt a pull request was opened
    DRV->>GH: gh pr view --json mergeCommit
    GH-->>DRV: merge commit
    DRV->>MM: verified STORY, merge commit
    MM->>AM: verify --story STORY --commit SHA
    AM->>BDS: read the Story's Tasks and their matrix_elements ids
    AM-)MTX: verified with the commit on each stack and entry the Story built, and on each provedByBuild relationship starting at one
    AM-->>MM: entries, unmatched
    MM->>AM: commit --bead STORY
    AM-)GH: commit and push matrix.json in the control repository
    Note over DRV,MTX: differs from required - the owner sets verified for all of an Epic's architecture and relationships once all Tasks of all its Stories are built and tested, as built it is per Story at its merge
  end
  DRV-)BDS: bd close STORY, reason pull request merged, or verified with no change
  DRV-)GH: git worktree remove --force, git branch -D story/STORY
  DRV-)JRN: done deploy:close, closed true
```

### 8.2 The verified mark, required and as built

**Subject.** When the matrix's verified mark is set.
**Scope.** The architecture an Epic's elaboration reaches, and the entries one Story's Tasks name.
**Purpose.** Set the owner's per-Epic rule beside the per-Story mark the code sets.
**Boundary.** Outside: the approved mark (`architectureApproved`), which the elaboration
pipeline's promotion sets.
**Basis.** The first machine is required: the owner statement of 2026-10-19 ("Once all of the
tasks for all of the stories for and Epic have been built and tested (including CI (CDK), which
means deployemen must also work), then all of the architecture and rellationships for the Epic can
be set to verified."), item 1.8 of the naming follow-ups, R24 and R25. The second is as built:
`storydeploy._close_step`, `matrixmarks.verified`, `design/matrix.md` 1.4.

```mermaid
stateDiagram-v2
  direction LR
  state "Required - one Epic's architecture and relationships" as REQ {
    [*] --> NotVerified
    NotVerified --> NotVerified : a Story of the Epic merges [another Task of the Epic is not built and tested]
    NotVerified --> Verified : last Task of the last Story built and tested [CI and CDK passed, deploy worked] / set verified on all of the Epic's architecture and relationships
    Verified --> NotVerified : a later change to that architecture [assumption - the owner states no reset]
  }
  state "As built - one stack or entry" as BUILT {
    [*] --> Absent
    Absent --> Marked : a Story whose Task names it merges / verify --story with the merge commit
    Marked --> Marked : a later Story naming it merges / commit replaced
    Absent --> Absent : the Story closes with no pull request / no mark
  }
```

Differences from the requirements:

- Granularity: the owner requires the mark for all of an Epic's architecture and relationships at
  once, when all Tasks of all its Stories are built and tested; as built the mark is set per
  Story, at its merge, on the stacks and entries its own Tasks name (`built --story`) and on the
  `provedByBuild` relationships that start at them. A Story of an Epic merges and marks its
  entries while other Stories of the same Epic are unbuilt.
- Scope: "all of the architecture and rellationships for the Epic" is wider than the Task-named
  entries; architecture the Epic's elaboration reached that no Task names is never marked, and a
  relationship without `provedByBuild` is never marked.
- R25 says "The build pipeline sets the verified mark"; as built the deploy pipeline's
  `deploy:close` sets it (the role is still named `build-driver`).
- The owner's second statement ("it doesn't care about what has actually been deployed") holds
  as built: the mark records the merge commit and no deployed state, and the matrix holds no
  Story or Task (R40, R42: the Task script reads the beads).

Assumptions: the transition from Verified back to NotVerified in the required machine. The owner's
statements do not say what happens to the mark when a later Epic changes the architecture;
`design/matrix.md` 1.4 keeps the mark until the changing Story is verified.

## 9. A deploy step's states in the Story's journal

**Subject.** The status of one step of a Story's deploy journal.
**Scope.** Every step kind of pipeline `deploy`.
**Purpose.** Show how a dispatch begins where the last one stopped, how a wait keeps a step
running, and how a failure is retried.
**Boundary.** Outside: the journal's container steps, whose status follows their children (see
[The pipelines: driver and routing](pipelines-driver.md), section 8).
**Basis.** As built: `skills/pipeline-contracts/schemas/step-journal.schema.json`
(`stepStatus`: planned, running, done, failed); `orchestrator/core/step_journal.py`
(`start_step` refuses a done step, `fail_step`, `next_step` returns the first step that is not
done, `unclosed_steps`); `ops/sdlc-automation/deployjournal.py` `upcoming` (line 367);
`storydeploy.py` `_run_journal`, `_ssm_check_step`, `_merge_wait_step`, `_failed_attempt`,
`_stopped`, `_run_step`; `elabmark.py --start-at` (the owner's reset).

```mermaid
stateDiagram-v2
  [*] --> planned : up-front plan, or added by a result
  planned --> running : dispatch reaches it / start
  running --> done : step function succeeded / artifacts, adds
  running --> done : publish, synth or verify failed [fewer than 3 fixes done] / deployFailure, adds fix and reruns
  running --> failed : step error or a stop [no-deploy-mechanism, no-change, fix limit, workflow failure] / failure text, item failure recorded
  running --> running : ssm-check missing parameter, or merge-wait not merged / handback, no change
  failed --> running : a later dispatch reaches it / start again from its beginning
  done --> planned : owner runs elabmark --start-at / reset
  failed --> planned : owner runs elabmark --start-at / reset
  done --> [*]
```

Differences from the requirements: none; no requirement covers the journal states. As built
only.
