# Index of the Epic pipeline's artifacts and bead writes

Step S01h. Every file, vault path and bead write the Epic flows produce, with the step that
produces it and the steps that consume it. A step is cited as `<spec>#<step number>`, the number
in that spec's Steps section; `driver` means the driver at `<control>/ops/sdlc-automation` as
`driver-contract.md` describes it. When a spec and this index disagree, the spec is right and this
index is stale.

Path placeholders:
- `<work>` = `<control>/.claude/workflow-runs/artifacts/<epic-id>/` (the Epic's artifact directory,
  `<art>` in some specs); `<arch-work>` = `<work>/architecture/`.
- `<arch>` = `$ATW_ARCH_PATH` (the architecture folder of the `skillspoke-docs` vault).
- `<slug>` = a span repository's artifact slug; `<subject>` = the target's folder name.
- `<workDir>` = the work directory of an owner-run portfolio flow (`wsjf-scoring`,
  `dependency-assessment`, `task-dependency-assessment`). None of them is part of the Epic
  pipeline: Epic scoring and Epic dependency assessment belong to the future readiness process
  (CONTEXT 7.17), and `task-dependency-assessment` is deleted in S08.

Open items live only in QUESTIONS.md.

Every `.meta.json` named below is written by `artifactio.record` beside its file and is read by
the same flow's reuse step (the one input-record format, `driver-contract.md` §8); where it has
another reader, the row says so.

The element status matrix (CONTEXT 7.25) is written by no Epic flow: only the build pipeline
writes it. The Epic flows read it in `architecture#32` (the Closure) and `repo-scoping#3`, `#5`,
`#6` (placement). Its storage and format are S02's item 10, so it has no row below.

The `prd-reconciliation` step and its files (`recon-<slug>.json`, `recon-<slug>.bundles.json`) are
removed (CONTEXT 7.10, 7.23).

## Artifacts

### `prd-to-spec` (the composite)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/delta-items.json` | `prd-to-spec#7` (`depscore.py arch-delta --save`) | `repo-scoping#1`, `#3` (input), `#5`, `#6`; `trd-authoring#2` (input), `#3`; `spec-authoring#1` (placed items joined to it), `#5`, `#8` (input); `task-decomposition#2` (input), `#5`, `#9`, `#10`; `prd-to-spec#11` (`closure-edges`) | JSON: `{ ok, refusals[], architectureChange, note, deltaExists, baselineValidated, implementationComplete, implementationWork, views[], items[{ id, element, views[], kind, state, requires[], ... }] }` |
| `<work>/closure-edges.json` | `prd-to-spec#11` (`depscore.py closure-edges --out`) | `prd-to-spec#12` (agent input), `#13` | JSON: `{ edges[{ from, to, reason }], summary.warnings }` |
| `<work>/candidates/task-deps.json` | `prd-to-spec#12` (agent `task-dependency-mapper`; required when the span has two or more repositories) | `prd-to-spec#12` (Python acceptance) | JSON: `{ edges[{ from, to, kind, reason }], acyclic, cycle[] }` |
| `<work>/task-deps.json` (+ `.meta.json`) | `prd-to-spec#12` (accepted copy) | `prd-to-spec#12` (reuse), `#13` | JSON, same shape |
| `<work>/task-edges/all.json` | `prd-to-spec#13` (`depscore.py write-all-task-edges --out`) | none: read by the incident-responder as run evidence | JSON: write summary `{ blockers, added, removed, standing, rejected }` |
| `<work>/STEPS.md` | after each phase: `prd-to-spec` (`artifactio.complete_step`), `spec-authoring#13` | `driver` (`artifactio.plan` -> the `resume` argument; `observe.py` accepted and stale steps; an open item in QUESTIONS.md) | text: one completed step id per line |
| `<work>/run.json` | `prd-to-spec#17` | none: read by the driver (handback `detailPath` -> incident evidence and human-action detail, `driver-contract.md` §4) and the owner | JSON: the run record (composite, Epic, PRD id, outcome, per-phase status, reused/stale/task-rerun events) |
| `<control>/ops/sdlc-automation/state/ledger.jsonl` (events appended) | `prd-to-spec#17` (event set: an open item in QUESTIONS.md) | `driver` (`outcomes.py`, `observe.py`, `runview.py`, `attemptview.py`, `failures.py`) | JSON lines |
| `<arch>/target/<subject>/` (deletion, committed in the vault) | `prd-to-spec#15` (`depscore.py arch-target-remove`) | none: the removal is the end state | git commit in the vault repository |

### `architecture`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<arch-work>/arc42-revision.json` | `architecture#2` (`archrevision.check`), updated by `#21`, `#22`, `#28` (`archrevision.mark`) | `architecture#2` (next run); `driver` (`arc42-revision` input kind of the `architecture` step's record) | JSON: `{ archRoot, revision, files{}, views{}, integrating, recordedAt }` |
| `<work>/stale-<timestamp>/architecture/` | `architecture#2` (moves stale saved work aside) | none: kept, not deleted, for the owner and the incident-responder | the moved files |
| `<arch-work>/repositories.json` | `architecture#6` (agent `polyrepo-steward`) | `architecture#7` | JSON: `[{ name, path, role, lifecycle }]` |
| `<arch-work>/survey.json`, `survey.md` (+ `.meta.json`) | `architecture#7` (agent `prd-reality-reconciler`, SURVEY), accepted `#8` | `architecture#5`, `#9`, `#11`, `#12`, `#13`, `#15`, `#16`, `#17`, `#20`, `#23`; `trd-authoring#2` (input), `#3`; `prd-to-spec#5` (`saved-target`) | JSON (SURVEY_SCHEMA) and Markdown |
| `<arch-work>/survey.json.baseline-inputs.json` | `architecture#8` (`survey_freshness(seal=True)`) | `architecture#5` | JSON: `{ revision, surveySha256, contextSha, inputs[], repos[] }` |
| `<arch-work>/ledger.json` | `architecture#4` (`archresume.resume_facts`, after every saving step) | `architecture#11`, `#13`, `#15`, `#16`, `#17`, `#23`, `#25` | JSON (contract version 2) |
| `<arch-work>/plans/round<n>-plan-0.json` | `architecture#13` (agent coordinator), settled `#14` | `architecture#4`, `#14`, `#15`, `#16` | JSON (COORDINATOR_SCHEMA) |
| `<arch-work>/rounds/r<n>-<seq>-<role>-<agent>.json` | `architecture#11` (boundary guardian), `#15` (writers), `#16` (reviewers) | `architecture#4`, `#13`, `#17` | JSON (writer or review schema) |
| `<arch-work>/draft/` (views, `delta/`, `draft/baseline.json`) | `architecture#15` (writers); seed `#10` (`arch-target --seed`) | `architecture#16`, `#17`, `#20` | arc42 Markdown views, JSON baseline |
| `<arch-work>/target-check.json` | `architecture#9`, `#10` (dry-run check) | `architecture#9` (subject refusals, in-process); file: none, read by the incident-responder | JSON: dry-run report |
| `<arch-work>/decision.json`, `decision.md` (+ `.meta.json`) | `architecture#17` (agent `architecture-decider`) | `architecture#2` (cited views), `#13`, `#23`, `#25`; `repo-scoping#3` (input), `#5`; `trd-authoring#2` (input), `#3` | JSON (DECISION_SCHEMA) and Markdown |
| `<arch-work>/target.json` | `architecture#20` (`arch-target --out`) | `prd-to-spec#5` (`saved-target`); `repo-scoping#3` (input); `trd-authoring#2` (input); `spec-authoring#1` | JSON: target report |
| `<arch>/target/<subject>/` (views, `delta/`, `baseline.json`) | `architecture#20` (`write_target`) | `prd-to-spec#7` (`arch-delta`); `architecture#23`, `#25`, `#29`; `repo-scoping#5`; `trd-authoring#2` (input), `#3`; `spec-authoring#3`, `#4`; deleted by `prd-to-spec#15` | arc42 Markdown (`lifecycle_state: in-review`), JSON baseline |
| `<arch-work>/integrate-before.json` | `architecture#22` | `architecture#24` | JSON: tree hashes |
| `<arch-work>/tree-last.json` | `architecture#24` | `architecture#27` | JSON: tree hashes |
| `<arch-work>/integration-files.json` | `architecture#24` | `architecture#25`, `#26`, `#28` | JSON: `{ touched, deleted, all, unreported, section2, outside, changedSinceLast }` |
| `<arch-work>/architecture-update.json` (+ `.meta.json`) | `architecture#23`, `#27` (agent `architecture-maintainer`), or `#21` (publication receipt) | `architecture#24`, `#25`; `trd-authoring#2` (input) | JSON (MAINTAIN_SCHEMA) |
| `<arch-work>/conformance-<n>.json` | `architecture#25` (agent `architecture-conformance-reviewer`) | `architecture#26`, `#27`, `#28` | JSON (CONFORMANCE_SCHEMA) |
| `<arch>/arc42/**` except section 2 (edits, `lifecycle_state: effective`, commit and push) | `architecture#23`, `#27` (edits), `#21`, `#28` (`promote`, `commit_integration`) | every later reader of effective views: `trd-authoring#2` (`arch-views` input), `#3`; the makers of `spec-authoring#3`, `#4`; `architecture#31` (the Closure walk); the next run's `architecture#2` | arc42 Markdown; git commits in the vault |
| `<arch-work>/closure-roots.json` | `architecture#29` (`delta_items(with_closure=False)`) | `architecture#31` | JSON: build roots |
| `<arch-work>/closure-walk.json` | `architecture#31` (agent `prd-reality-reconciler`, CLOSURE walk) | `architecture#32` | JSON: `{ rootEdges[], elements[{ element, views, requiredBy, requires, evidence }], summary }` |
| `<arch-work>/closure.json` | `architecture#32` (Python: the walk joined to the element status matrix) | `architecture#32` (`write_closure`) | JSON (CLOSURE_SCHEMA) |
| `<arch>/target/<subject>/closure.json` | `architecture#32` (`archclosure.write_closure`) | `prd-to-spec#5` (`saved-target` `closureSaved`), `#7` (`arch-delta` lists prerequisites); `repo-scoping#5`; `trd-authoring#3`; `spec-authoring#1` (none-case build work) | JSON: `{ prerequisites[{ element, state: unknown, views, requiredBy, requires, evidence, repository }], rootEdges[], satisfied[{ element, state, repository, task, commit }], version, roots }` |
| `<arch-work>/tree-start.json`, `survey.json.receipt`, `candidates/` (legacy) | the JavaScript (not produced by the new flow) | `architecture` saved work read in place (CONTEXT 7.13; `candidates/` is an open item in QUESTIONS.md) | JSON |

### `repo-scoping`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/repo-scoping.inventory.json` | `repo-scoping#4` (`polyrepo.py inventory --json`) | `repo-scoping#5`, `#6` | JSON: live repository inventory |
| `<work>/candidates/repo-scoping.json` | `repo-scoping#5` (agent `polyrepo-steward`, placement only) | `repo-scoping#6` | JSON: ruling schema |
| `<work>/repo-scoping.json` (+ `.meta.json`) | `repo-scoping#7` | `repo-scoping#3`, `#8`, `#9`; `spec-authoring#1`, `#5`, `#8` (input); `task-decomposition#2` (input), `#5`, `#9`, `#10`; `prd-to-spec#11` (`closure-edges`, incl. `beadwrite._no_code`) | JSON: `{ placements[{ repoPath, repoName, itemIds[], frontend, rationale }], missingRepos[{ name, template, purpose, itemIds[] }], noCode[], spanRationale }` |
| `<work>/repo-creation.json` (+ `.meta.json`) | `repo-scoping#8` (deterministic, `polyrepo.py create`) | `repo-scoping#9`; `prd-to-spec` (`createdRepos` in the handback; `driver` `decisions.py`) | JSON: `{ created[{ name, repoPath, template, itemIds[], existed }], failures[{ name, template, itemIds[], error, ownerFact }] }` |
| a new repository (local checkout and GitHub; the steward's manifest, changelog and beads fleet list) | `repo-scoping#8` (`polyrepo.py create`, from the name and template the steward named) | `spec-authoring`, `task-decomposition` (as a span repository); the Task pipeline | git repository |

### `trd-authoring`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/trd.md` (+ `.meta.json`) | `trd-authoring#3` (agent `trd-author`), checked `#4`, `#5`, recorded `#6` | `spec-authoring#1`, `#3`, `#4`, `#5` (input), `#7`; `driver` (lane `artifactio.file_in_vault`; `observe.py` "TRD filed") | Markdown with YAML frontmatter `decisionIds` |
| `<prd dir>/../trds/<stem>-trd.md` in the vault | `driver` (lane `file_in_vault`, after `elaboration_state=done`, `driver-contract.md` §4) | none: read by the owner in the vault | Markdown |

### `spec-authoring`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/spec-<slug>.bundles.json` | `spec-authoring#2b` (`cdsbundles.list_bundles`; UI repositories only) | `spec-authoring#3`, `#6` (input) | JSON: supplied bundles |
| `<work>/candidates/spec-<slug>.ui.json` | `spec-authoring#3` (agent `api-specification-author`; UI repositories only) | `spec-authoring#6` | JSON: `{ uiItems[] }` |
| `<work>/spec-<slug>.ui.json` (+ `.meta.json`) | `spec-authoring#6` (checked against the bundles) | `spec-authoring#6` (`spec_ui_append`); `task-decomposition#2` (input), `#6`, `#9` | JSON: `{ uiItems[{ item, designSource, reason, artifact, bundle, buildSpec, sections }], mocksDir, warnings[] }` |
| `<work>/spec-<slug>.md` (+ `.meta.json`) | `spec-authoring#3` (agent `api-specification-author`); `## UI design sources` appended `#6` | `spec-authoring#5`, `#7`, `#9`, `#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown with YAML frontmatter `decisionIds` |
| `<work>/spec-<slug>.data-model.md` (+ `.meta.json`) | `spec-authoring#4` (agent `data-model-specification-author`) | `spec-authoring#5`, `#7`, `#9`, `#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown with YAML frontmatter `decisionIds` |
| `<work>/spec-<slug>.criteria.md` (+ `.meta.json`) | `spec-authoring#7` (agent `acceptance-criteria-writer`) | `spec-authoring#10`, `#11` (input); `task-decomposition#2` (input), `#6`, `#10`; `driver` (lane `file_in_vault`) | Markdown |
| `<work>/story-<slug>.draft.json` | `spec-authoring#10` (agent `user-story-writer`) | `spec-authoring#11` | JSON: `{ title, description }` |
| `<work>/story-<slug>.json` (+ `.meta.json`) | `spec-authoring#11` | `spec-authoring#12` (`write_story`); `task-decomposition#2` (input), `#6`, `#9`, `#10` | JSON: `{ title, description, decisionIds }` |
| the filed Spec documents in the vault | `driver` (lane `file_in_vault`) | none: read by the owner in the vault | Markdown |

### `task-decomposition`

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<work>/tasks-<slug>.items.json` | `task-decomposition#5` (from `repo-scoping.json` and `delta-items.json`) | `task-decomposition#6`, `#10` | JSON: `{ items[{ id, element, views, requires, kind }] }` |
| `<work>/tasks-<slug>.context.json` | `task-decomposition#5` (beads read) | `task-decomposition#6` | JSON: `{ existingTasks[], otherEpicTasks[] }` |
| `<work>/candidates/tasks-<slug>.json` | `task-decomposition#6` (agent `task-decomposer`) | `task-decomposition#7` | JSON: decomposition schema |
| `<work>/tasks-<slug>.json` (+ `.meta.json`) | `task-decomposition#7`, amended `#11`, recorded `#8` | `task-decomposition#2`, `#9`, `#10`, `#11`; `prd-to-spec#11` (`closure-edges`), `#12` (agent input and `task-deps` input), `#13` | JSON: `{ tasks[], testStrategy, rationale, edges[], scores[], notes }` |
| `<work>/candidates/tasks-<slug>.correction.json` | `task-decomposition#10` (agent `task-decomposer`) | `task-decomposition#10` (Python acceptance) | JSON: `{ tasks[], edges[], scores[] }` (no `noWork`; `scores` also for saved Task keys named as unsized) |
| `<work>/tasks-<slug>.correction.json` (+ `.meta.json`) | `task-decomposition#10` | `task-decomposition#11` (merged into `tasks-<slug>.json`); otherwise evidence for the incident-responder | JSON, same shape |

### Owner-run portfolio flows (not part of the Epic pipeline: future readiness process, CONTEXT 7.17; `task-dependency-assessment` deleted in S08)

| Path pattern | Producer | Consumers | Format |
|---|---|---|---|
| `<workDir>/score-plan.json` | `wsjf-scoring#1` (`scoring.plan`) | `wsjf-scoring#2`, `#3`, `#7` | JSON: `{ judge, adopt, fingerprints, summary }` |
| `<workDir>/judge-input-epic.json`, `judge-input-task.json` | `wsjf-scoring#2` (`scoring.judge_input`) | `wsjf-scoring#4`, `#5`, `#6` (input) | JSON: `{ level, items, referenceJobs, summary }` |
| `<workDir>/prd/<epic-id>.md` | `wsjf-scoring#2` | `wsjf-scoring#4`, `#6` (input) | Markdown: `# <title>` + bead description |
| `<workDir>/judgments/<level>/<key>.input.json` | `wsjf-scoring#3` | `wsjf-scoring#3` (reuse), `#6` (input) | JSON: `{ <id>: <judging fingerprint> }` |
| `<workDir>/judgments/epic/<id>.json`, `judgments/task/<key>.json` (+ `.meta.json`) | `wsjf-scoring#4`, `#5` (agent `wsjf-scorer`), recorded `#6` | `wsjf-scoring#3`, `#7` | JSON: `{ rubric, scores[], unscored[] }` |
| `<workDir>/record.json` | `wsjf-scoring#7` (`scoring.record`) | `wsjf-scoring#9` | JSON: `{ written, adopted, rejected, missing, unreadable, summary }` |
| `<workDir>/score.json` | `wsjf-scoring#8` (`scoring.score`) | `wsjf-scoring#9` | JSON: `{ epics[], tasks[], unscored, incomplete, cycles, summary }` |
| `<workDir>/assess-plan.json` | `dependency-assessment#1`; `task-dependency-assessment#1` | `dependency-assessment#8`; `task-dependency-assessment#8` | JSON: `{ level, scope, unassessed, fingerprints, summary }` |
| `<workDir>/context/prd/<id>.md`, `context/task/<id>.md`, `context/index.md` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#4`, `#7` | Markdown |
| `<workDir>/context.json` | `dependency-assessment#2`; `task-dependency-assessment#2` | the same flow's `#3` (input), `#4`, `#7` | JSON: `{ epic\|task, standing[], withdrawn[], corpusDir, indexPath, summary }` |
| `<workDir>/edges.json` (+ `.meta.json`) | `dependency-assessment#4`, `#7` (agent `epic-sequencer`); `task-dependency-assessment#4`, `#7` (agent `task-dependency-mapper`); recorded `#5` | the same flow's `#3`, `#6`, `#8` | JSON: `{ edges[], withdrawn[] }` |
| `<workDir>/reasoning.md` | the same agent steps (`#4`, `#7`) | none: read by the owner and the incident-responder | Markdown |
| `<workDir>/validation.json` | `dependency-assessment#6`; `task-dependency-assessment#6` | the same flow's `#7`, `#10` (Epic) / `#11` (Task) | JSON: `edgeset.validate` result |
| `<workDir>/apply-edges.json` (or `apply-edges-dry-run.json`) | `dependency-assessment#8`; `task-dependency-assessment#8` (with `storyEdges` from `#9`) | the same flow's `#10` (Epic) / `#11` (Task) | JSON: `edgeset.apply_edges` result |
| `<workDir>/scoring/` | `dependency-assessment#9`; `task-dependency-assessment#10` (the `wsjf-scoring` flow in-process) | as in the `wsjf-scoring` rows | as above |

`route-elaboration`, `prd-validation` and `gate-enforce` produce no artifact in the Epic pipeline.

## Bead writes

| Command | Fields and metadata keys | Writing step |
|---|---|---|
| `depscore.py elaboration-start --epic <id> --owner <token> [--reclaim]` | Epic: `elaboration_state=in_progress`, `elaboration_state_at`, `elaboration_state_cause=elaboration-started`, `elaboration_state_owner=<token>` | `prd-to-spec#3` |
| `beads-contract.py metadata set <epic> artifact_trd_path=... artifact_trd_sha256=...` | Epic: `artifact_trd_path`, `artifact_trd_sha256` | `trd-authoring#7` |
| `depscore.py write-story` (`beadwrite.write_story`): `bd create --type story --parent <epic>` or one `bd update` | Story: title, description, acceptance, notes `repoPath: <repo>`; metadata `elab_key=story:<slug>`, `repoPath`, `decision_ids`, `artifact_spec_path`, `artifact_spec_meta`, `artifact_spec_sha256`, `artifact_spec_data_model_path`, `artifact_spec_data_model_meta`, `artifact_spec_data_model_sha256`, `artifact_spec_criteria_path`, `artifact_spec_criteria_meta`, `artifact_spec_criteria_sha256`, `artifact_story_path`, `artifact_story_meta`, `artifact_story_sha256` | `spec-authoring#12` |
| `bd delete <ids...> --force` (`beadwrite.replace_tasks`) | the Story's unstarted, elaboration-written Task beads (and their edges) | `task-decomposition#4` (case `replaced` only) |
| `bd create --type task --parent <story> ... --metadata <json> [--deps blocked-by:...]`, `bd update <id> [--title --description] [--set-metadata ...]`, `bd dep add --file -` (`blocks`), `bd dep remove` (`beadwrite.write_task`), in build order, at least one Task per Story, every Task sized | Task: title, description (with the `## Spec contract` block), acceptance, notes `repoPath: <repo>`; metadata `elab_key`, `repoPath`, `wsjf_size_estimate`, `wsjf_size_low`, `wsjf_size_high`, `wsjf_size_confidence`, `wsjf_content_hash`, `decision_ids`, `spec_sections`, `acceptance_criteria`, `definition_of_done`, `requirement_ids`, `surfaces`, `test_strategy`, `cds_design_source`, `cds_artifact`, `cds_bundle_path`, `cds_build_specs`, `spec_path`, `spec_paths`, `spec_paths_verified`; same-Story `blocks` edges and `blockedByExternal` blockers | `task-decomposition#9` (again after `#11`) |
| `depscore.py write-all-task-edges --epic <id> --dir <work> --repos <span>` | `blocks` edges between Tasks of different Stories (closure edges and `task-deps.json`, cycle-closing edges dropped) | `prd-to-spec#13` |
| the `elaboration-finish` logic (`elaboration.finish`, `scoring.score`) with the write scope limited to the Epic's Tasks | the Epic's Tasks only: `wsjf`, `wsjf_calculated_at`, `wsjf_rubric`, `wsjf_rroe`, `wsjf_unblocks`, `wsjf_cod`, `wsjf_size`, `wsjf_size_source`, `wsjf_value_from` (the Epic's WSJF keys are not written, CONTEXT 7.17); once every Task is scored, Epic: `elaboration_state=done`, `elaboration_state_cause=decomposed-into-tasks`, `elaboration_state_at`, `elaboration_state_owner=""`; then `story-edges`: Story `blocks` edges, `story_owned_blockers`, `story_owned_blockers_at`, `story_edge_reasons` (Stories get no WSJF) | `prd-to-spec#14` |
| `depscore.py elaboration-release --epic <id> --owner <token>` | Epic: `elaboration_state_owner=""` (when still this run's token) | `prd-to-spec#16` |
| *Rows below to `storyedges.story_edges` belong to the owner-run portfolio flows, which are not part of the Epic pipeline (CONTEXT 7.17); `task-dependency-assessment` is deleted in S08.* | | |
| `scoring.record` (`depscore.py record`): `bd update --set-metadata` | Epic: `wsjf_ubv`, `wsjf_tc`, `wsjf_confidence`, `wsjf_size_estimate`, `wsjf_size_low`, `wsjf_size_high`, `wsjf_size_confidence`, `wsjf_content_hash`; Task: the size keys and `wsjf_content_hash`; adopted items: `wsjf_content_hash` only | `wsjf-scoring#7` |
| `scoring.score` (`depscore.py score`): `bd update --set-metadata` | the computed keys listed for `elaboration-finish`, on every open Epic and Task whose value changed | `wsjf-scoring#8` (also run by `dependency-assessment#9`, `task-dependency-assessment#10`) |
| `edgeset.apply_edges` (`depscore.py apply-edges`): `bd dep add --type tracks`, conversions, removals, `bd update --set-metadata` | Epic `tracks` edges touching the Epic; on each blocked Epic `seq_owned_blockers`, `seq_owned_blockers_at`, `seq_edge_reasons`, `seq_edge_withdrawn`; on the assessed Epic `seq_content_hash`, `seq_assessed_at` | `dependency-assessment#8` |
| `edgeset.apply_edges` with `level="task"` | Task `blocks` edges touching the Task and the same `seq_*` keys on Tasks | `task-dependency-assessment#8` |
| `storyedges.story_edges` | Story `blocks` edges, `story_owned_blockers`, `story_owned_blockers_at`, `story_edge_reasons` | `task-dependency-assessment#9` (and inside `prd-to-spec#14`) |
| `elabstate.hold_for_person` | Epic: `elaboration_state=""`, `elaboration_state_cause=awaiting-human-action`, `elaboration_state_owner=""` | `driver` (from `requiredHumanActions`, `driver-contract.md` §4); no Epic flow writes it |
| `artifactio.file_in_vault` bead metadata | Epic: `artifact_trd_vault_path`; each Story: `artifact_spec_vault_path`, `artifact_spec_data_model_vault_path`, `artifact_spec_criteria_vault_path` | `driver` (lane, after `elaboration_state=done`) |
| `elabmark.py --set=<state>` | Epic: `elaboration_state`, cause `human-ruling` | the owner's CLI (`driver-contract.md` §2) |

`architecture`, `repo-scoping`, `route-elaboration`, `prd-validation` and `gate-enforce` write
nothing to beads.
