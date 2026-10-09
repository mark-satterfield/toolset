# Net-effect spec: `trd-authoring`

Source: `<plugin>/workflows/trd-authoring.js` (`meta.description`), its call site and replay in
`<plugin>/workflows/prd-to-spec.js` (`runTrdAuthoring`, `TRD_INPUTS`), agents
`<plugin>/agents/trd-author.md` and `<plugin>/agents/filing-clerk.md`, the driver's TRD filing
(`<driver>/workitems.py` `trd_path_for`, `dispatch_context`; `<driver>/lane.py`
`_file_artifacts`, `_vault_metadata`; `<driver>/artifactio.py` `file_in_vault`), CONTEXT sections 6
and 7. `<art>` below is the Epic's artifact directory,
`<control>/.claude/workflow-runs/artifacts/<epic-id>/`; `<artRel>` is the same path relative to
`$SKILLSPOKE_ROOT`.

## 1. Purpose

Author the Technical Requirements Document (TRD) for one PRD from the PRD and the approved target
and delta of its architecture, in one pass. The TRD is the single point at which the obligations
the architecture imposes enter the build chain: PRD business requirements that need technical
elaboration, plus the obligations the architecture imposes on the elements the delta adds or
changes (uptime, latency, security, failover, disaster recovery, infrastructure and CDK specifics,
observability, data, API contracts). Each requirement cites its source (a PRD requirement or a
view path) and names the element it applies to. A technical rule reaches the TRD only from the
architecture, never from the PRD. The run is refused when there is no approved target.

## 2. Produces and decides

After a successful run:

- `<art>/trd.md` exists, is non-empty UTF-8 Markdown, and opens with YAML frontmatter whose
  `decisionIds` lists every view a requirement depends on (effective views relative to `arc42/`,
  target and delta views relative to the architecture directory, with `#<heading>` where a
  requirement rests on one part). Every `decisionIds` entry resolves to a file under
  `$ATW_ARCH_PATH` (step 5).
- `<art>/trd.md.meta.json` records its sha256, bytes and input fingerprints.
- The Epic bead carries `artifact_trd_path=<artRel>/trd.md` and `artifact_trd_sha256=<sha256>`.
- arc42 section 2 (`arc42/02-architecture-constraints/`) is byte-identical to before the run (the
  session runner's guard, `driver-contract.md` §8).
- The flow's result carries `trdPath` (`<art>/trd.md`), `filingPath` (the vault destination, or
  null), and `decisionIds`.

The TRD is published to the vault later, by the driver's elaboration lane (`file_in_vault`), not by
this flow.

## 3. Inputs

| Input | Where it comes from |
|---|---|
| Epic id | the composite (bead id) |
| PRD path | the composite (`prd.path`, under `$ATW_PRD_DIR`) |
| Approved target | `targetDir`, `deltaDir` (partial change only), `architectureChange` (`partial`, `new`, `none`), `note`, from the composite's `depscore.py arch-delta` result |
| Build items | `<art>/delta-items.json` (`id`, `element`; the TRD names each requirement's `appliesTo` as the item's element is named here) |
| Architecture records | `<art>/architecture/decision.md`, `<art>/architecture/target.json`, `<art>/architecture/architecture-update.json`, `<art>/architecture/survey.json` (the saved survey, CONTEXT 7.13) |
| Architecture directory | `$ATW_ARCH_PATH` (`arc42/`, `target/`, `reference/`) in the vault `/Users/msat1971/projects/SkillSpoke/skillspoke-docs` |
| Owner's constraints | `$ATW_ARCH_PATH/arc42/02-architecture-constraints/` (read only) |
| Effective views of the delta's elements | the `arch-views:{dir, elements}` input kind of `artifactio.py`: views under `arc42/` whose catalog frontmatter (`subject`, `shows`) names a delta element |
| Filing destination | `trdPath` the driver puts in `extra_args` (`workitems.dispatch_context` → `trd_path_for`: `<prd dir>/../trds/<prd stem>-trd.md` when the PRD is in a `prds/` folder) |

## 4. Outputs

| Output | Format and key fields |
|---|---|
| `<art>/trd.md` | Markdown; YAML frontmatter with `decisionIds: [...]`; at most 40 requirements, each under 60 words, each with a stable ID, its source (PRD requirement or view path), `appliesTo` (the element), its view citations; a summary section naming departures from effective views, non-effective files relied on, and requirement/view disagreements. The summary lives only here: no summary is returned or passed on, and spec authoring reads `trd.md` by path. |
| `<art>/trd.md.meta.json` | `artifactio.py record <art>/trd.md --epic <epic> --phase trd --inputs <inputs>`: `sha256`, `bytes`, `inputs[]` |
| Epic bead metadata | `artifact_trd_path`, `artifact_trd_sha256`, written with `<plugin>/skills/beads-contract/scripts/beads-contract.py metadata set <epic> artifact_trd_path=<artRel>/trd.md artifact_trd_sha256=<sha256>` |
| Flow result to the composite | `{ok, trdPath, filingPath, decisionIds}`; on failure `{ok: false, stage, cause, reason}` |
| Downstream, not this flow | the composite reports `filing['trd.md'] = filingPath`; the lane copies `trd.md` to it and sets `artifact_trd_vault_path` on the Epic |

No git commit. No vault write by this flow.

## 5. Steps

1. **Refuse missing inputs** (deterministic, Python). No PRD path, or no `targetDir` → fail at
   stage `input`, cause `other`.
2. **Fingerprint the inputs and look for saved work** (deterministic, Python). Inputs: PRD,
   `delta-items.json`, `decision.md`, `target.json`, `architecture-update.json`, `survey.json`,
   `targetDir`, `arc42/02-architecture-constraints`, and
   `arch-views:{"dir": "<archPath>/arc42", "elements": [sorted delta elements]}`, hashed as
   `artifactio.hashed_inputs` does (this list is the single source; `prd-to-spec.md` refers here).
   If every input recorded in `<art>/trd.md.meta.json` hashes as recorded, reuse `trd.md`: go to
   step 4 with no session.
3. **Author the TRD** (agent `trd-author`), inside the session runner's section 2 guard
   (`driver-contract.md` §8): the runner fingerprints and copies section 2 before the session and
   restores it and fails the step if the session changed it. Inputs, as paths only: the PRD file, `targetDir`,
   `deltaDir` and the `architectureChange` case with its documents (CONTEXT 7.7: partial = target
   plus the delta of the change; new = the target views are the delta, no delta folder; none = one
   set, the effective views `baseline.json` cites, build work from its `implementationWork` and
   `closure.json`), `delta-items.json`, `decision.md`, `survey.json`, `$ATW_ARCH_PATH`, and the
   output path `<art>/trd.md` with the filing destination named as "not to be written". The brief
   carries the rules of the current prompt, which are the agent's job, not the script's: the two
   requirement sources; an obligation binds only what the delta adds or changes and names that
   element in `appliesTo`; effective files are the design so far and are cited, not redesigned
   (departures go in the summary); the target and delta views read `in-review` but are approved;
   other non-effective files are checked before being relied on; cite, do not restate; read section
   2's and section 4's README in full, every delta view, the target views of changed elements,
   their effective views at every scope, and the applicable section 8 concepts; other open targets
   are read so the TRD does not contradict them; a UI design reference a view selects is carried
   with its identity and scope; reuse the survey's evidence refs, with targeted reads only where
   the recorded revision changed; the limits of 40 requirements, 60 words each, about 25,000
   characters; the `decisionIds` frontmatter. The agent writes the file and nothing else. Model and
   effort: the agent definition's `fable` with `effort: medium`, which the workflow also passes.
   Keep them. Runs in parallel with `repo-scoping` (the composite starts both after Architecture).
4. **Verify and read the TRD** (deterministic, Python). Read `<art>/trd.md`: it must exist, be
   non-empty and decode as UTF-8; compute sha256 and bytes. Parse the YAML frontmatter and take
   `decisionIds` (empty list when absent, with a warning). A missing or empty file after a normal
   session end gets one corrective re-dispatch of step 3 naming the missing path (CONTEXT 7.4,
   specific gap feedback); still missing or empty → fail at stage `document`, cause `other`.
5. **Check the citations** (deterministic, Python). Every `decisionIds` entry, with any
   `#<heading>` removed, must name an existing file: relative to `$ATW_ARCH_PATH/arc42/` for an
   effective view, or relative to `$ATW_ARCH_PATH/` for a target or delta view. The heading is not
   checked. Unresolved entries get one corrective re-dispatch of step 3 naming the exact entries;
   any still unresolved → fail at stage `document`, cause `other`. Runs on a reused `trd.md` too
   (no session unless an entry no longer resolves).
6. **Record** (deterministic). `artifactio.record` the file with the step 2 inputs (one call,
   same process as step 4, so the hash recorded is the hash verified).
7. **Mark the Epic** (deterministic). `beads-contract.py metadata set` with `artifact_trd_path` and
   `artifact_trd_sha256`. Skipped on reuse when the bead already carries the same sha256.
8. **Return** `{ok: true, trdPath, filingPath, decisionIds}`. The composite records the `trd` step
   (`artifactio.complete_step(<work>, "trd")`), as `prd-to-spec.md` says.

**Agent dropped: `filing-clerk`.** The current script starts a filing-clerk session to name the
TRD's vault path when the caller passes no `trdPath`. The driver already derives that path
deterministically (`workitems.trd_path_for`) and passes it for every PRD in a `prds/` folder; the
lane falls back to the same function at filing time. When neither applies the lane records "trd.md
not filed" as a visible lane failure, and no wrong file reaches the vault. So the session adds no
outcome. (See QUESTIONS.md.)

The relay calls of the current script map as follows: `relayKit.documentReceipt` (jsonartifact.py
`--document`) → step 4 in Python; `relayKit.inline` (`FRONTMATTER_IDS_PY`) → step 4 in Python;
`relayKit.run ... artifactio.py record` → step 6 called directly; `relayKit.run ...
beads-contract.py metadata set` → step 7 called directly. No `workflow-command-runner` session
remains.

## 6. Checks

**Checks kept**

- No target → refuse (step 1). Without it the TRD carries no architecture obligations, and spec
  authoring builds from it; nothing later re-reads the architecture for obligations.
- Section 2 unchanged: the session runner's guard around step 3 (`driver-contract.md` §8). Hard
  limit (CONTEXT 6). The `trd-author` holds Write and Edit tools and reads section 2. The current
  script has no such guard; the runner's one guard covers this flow, with no copy of its own.
- `trd.md` exists and is non-empty UTF-8 (step 4). Without it spec authoring and the vault filing
  get an empty or missing TRD; spec authoring does not refuse one.
- Every `decisionIds` entry resolves to a file (step 5). Without it a citation of a view that does
  not exist reaches the vault with the TRD, and spec authoring and the Tasks inherit it; no later
  step checks it.

**Checks dropped**

- "trd.md changed between its check and its record" sha comparison: steps 4 and 6 run in one
  Python process on the same bytes.
- The `summary` the author returned and the composite passed to spec authoring as `trd.summary`:
  the summary is a section of `trd.md`.
- Rejecting a run without `ART` or `RELAY_RUNNER`, `dispatchInterruption`, `dispatchOutcome`,
  `settleAgent` failure bookkeeping, relay-file sequencing: sandbox and relay workarounds.
- The `feedback` argument ("Gate feedback from the previous run"): no caller passes it;
  `prd-to-spec` runs no gate on the TRD.
- `repoPath` ("work within the repository at"): the TRD is a document in `<art>`, not product code;
  the composite passes the control repository, which the author must not treat as a work tree.
- Pasting `prd.content` and `prd.acceptanceCriteria` into the prompt: replaced by the PRD path
  (CONTEXT 5: paths, never pasted data). The criteria are in the PRD file.

## 7. Failure causes

| Failure point | Cause | Retry reasonable? |
|---|---|---|
| No PRD path or no `targetDir` | `other` | No; incident-responder. |
| `trd-author` session: API error or overload | `api` | Yes, through `breaker.py`. |
| `trd-author` session: usage or quota limit | `quota` | Yes, through `breaker.py`. |
| Session ends and `trd.md` is missing or empty | `other` | Once, with "the file at `<art>/trd.md` is missing or empty" as feedback; then no. |
| `decisionIds` entries that name no file | `other` | Once, with the exact entries as feedback; then no. |
| Section 2 changed (the runner's guard) | `other` | No; restored, then incident-responder. |
| `artifactio.record` fails | `other` | No. |
| `beads-contract.py metadata set` times out or hits a Dolt lock | `bd-timeout` or `contention`, from the structured fact S02 settles (QUESTIONS.md) | Yes, backoff from 30 s, doubling, capped at 30 minutes. |

Causes come from exit statuses, the session's structured result and exception types, never from
error text. `relay` has no producer in this flow.

## 8. Resume points

| Saved result | Fingerprint inputs | A rerun after it redoes |
|---|---|---|
| `<art>/trd.md` + `.meta.json` | PRD, `delta-items.json`, `decision.md`, `target.json`, `architecture-update.json`, `survey.json`, `targetDir`, section 2 folder, `arch-views` digest of the delta elements' effective views | steps 4, 5 and 7 (deterministic; step 7 only when the bead lacks the metadata); no session |

An interrupted session leaves no accepted `trd.md.meta.json`, so the rerun authors again; a
partial `trd.md` without a matching `.meta.json` is overwritten. A rerun of `repo-scoping` alone
does not redo the TRD: the span is not a TRD input.

## 9. Requirements that apply

- 7.7: the three cases decide which documents are the TRD's architecture source, and something
  reaches the TRD in every case (with no architecture change, the obligations on the gaps
  `baseline.json` and `closure.json` name).
- 7.20: the prerequisites the Closure lists are build items, so the TRD states the obligations on
  them like on any other element the delta adds or changes.
- Section 2 hard limit (CONTEXT 6): the session runner's guard around step 3.
- 7.13: the saved `survey.json` is handed to the author by path, so the survey is not redone.
- 7.4: only API, quota and `bd` contention are retried; a missing file is retried once with the
  exact gap; structured causes.
- 7.11: fingerprinting, verification, frontmatter parsing, recording and bead metadata are code.
- 7.14: the brief states facts (paths, the case, the rules), not theories about what the TRD will
  contain.

## 10. Open items

See QUESTIONS.md
