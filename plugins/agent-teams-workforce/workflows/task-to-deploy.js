export const meta = {
  name: 'task-to-deploy',
  description:
    'Composite — drives an approved spec from freshness check through TDD (Red, Green, Refactor), Integration, Adversarial, and Deploy-to-dev. Stitches the spec-freshness front-end onto the shared build-and-ship tail via mini workflows, with an independent gate between phases and Documentation as a parallel track started after Green and awaited before deploy. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV and smoke-checks the deployed endpoints — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Workspace', detail: 'establishes the linked worktree every writing phase then operates in' },
    { title: 'Spec Freshness' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-to-dev' },
    { title: 'Settle', detail: 'lands the work — commit, push, PR — on EVERY exit path; never evidence a work phase completed' },
    { title: 'Run Ledger', detail: 'telemetry — runs on EVERY exit path, including failure; never evidence the run succeeded' },
  ],
}

// args: {
//   bead: {                      // the work item this run builds — REQUIRED
//     id,                        // required; the run refuses to start without it
//     title?, description?,
//     repoPath,                  // required; the REPOSITORY to work from. The worktree the
//                                // phases actually write in is established by the Workspace
//                                // step below and is NOT this value.
//     acceptanceCriteria?: [{ given, when, then }],  // testable AC the Red phase encodes
//     surfaces?: string[],       // declared surfaces; decides the specialist test writers
//     apiSpec?, eventContracts?: [], testStrategy?,
//     path?, dependencies?,      // identity/location of the spec document, if separate
//   },
//   spec?: {...},                // an explicitly separate spec document. Defaults to `bead`,
//                                // which is what /work-bead and /next-task actually send.
//   implementer?: string,        // override the Green-phase implementer agent (default chassis-extension-implementer)
//   maxLoops?: number,           // bounded retries per gate (default 2)
// }
//
// The header used to document `args.spec` while the body read `args.bead`, and two bare
// reads of an undeclared `spec` survived the rename that introduced `bead` — so EVERY
// caller shape died with `ReferenceError: spec is not defined` at Gate 1, before a single
// agent was dispatched. The identifier is bound once, here, and defaults to the bead.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2
if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied — refusing to run without a work item' }
// A code-writing composite with no repository cannot write anywhere it can later land
// from, and a run that proceeded blind then reported a phantom orphan at the end. Refuse
// at the input stage instead, the same way a missing bead.id is refused.
if (!String(bead.repoPath || '').trim()) {
  return { ok: false, stage: 'input', error: 'no bead.repoPath supplied — refusing to write code without a repository to establish a worktree in' }
}

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.//
// It gets its OWN phase, and that is load-bearing. This agent used to be tagged
// `phase: 'Deploy-to-dev'`, and because the finally runs on every exit path, a
// run that died at an early gate still ticked the terminal phase green — the
// progress panel reported a deploy for a run that never built anything.
// Telemetry must never be able to paint a work phase complete, so it reports
// under a phase that claims nothing about the work.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'task-to-deploy', bead: null, subject: bead.id || null, outcome, runLedger })}`,
      {
        label: 'ledger:persist',
        phase: 'Run Ledger',
        agentType: 'agent-teams-workforce:run-ledger-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['written'],
          properties: {
            written: { type: 'boolean' },
            path: { type: 'string' },
            lines: { type: 'number' },
            runId: { type: 'string' },
          },
        },
      }
    )
  } catch (e) {
    log(`ledger persist failed (non-fatal): ${e && e.message ? e.message : e}`)
  }
}

// The worktree the settle step lands. `contract.repoPath` is built inside the run's
// async body and is out of scope in the `finally`, so the resolved path is captured
// on this mutable as the run establishes it.
let settleRepoPath = bead.repoPath || null

// ── Settle: land the work, or name what stopped it ────────────────────────────
// The telemetry `finally` below is the ONE construct that observes every exit path —
// every failure return and the success return alike. Persisting a ledger there while
// the change sat unlanded in a worktree is how finished work went missing: no mini in
// this pipeline touches git before the deploy mini's ship step, so a run that dies at
// Integration or Adversarial leaves the work UNCOMMITTED — not merely unpushed, but
// with no commit to find later. This lands it or reports exactly why it could not be
// landed, and it can never report success over an orphan.
//
// It gets its OWN phase for the same reason the ledger does: running on every exit
// path, it must never be able to tick a work phase green.
// Three worlds, three answers. A run with no repo path, a settle agent that threw, and a
// genuine orphan used to be indistinguishable — all three returned null, and the first two
// then flipped a successful run to ok:false and blamed a PR URL that was never withheld
// because the agent never ran.
async function settleRun() {
  const wt = settleRepoPath
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written through the contract' }
  try {
    const reported = await agent(
      `Land every change in this worktree, or say exactly why it could not be landed. Worktree: ${wt}\n` +
        `Run every git command as \`git -C "${wt}"\`, and \`cd "${wt}"\` before skillspoke-pr — it has no -C flag and must run inside the tree.\n` +
        `1. \`git -C "${wt}" status --porcelain\`. Commit anything uncommitted as \`type(scope): description\` with NO Co-Authored-By header. Run the repo's gates first. \`--no-verify\` is forbidden in every form; if a hook finding cannot be fixed, abort with NO commit and name it in \`blocked\` — that is the only sanctioned way work stays local.\n` +
        `2. If \`git -C "${wt}" rev-parse --abbrev-ref --symbolic-full-name @{u}\` resolves to origin/main, run \`git -C "${wt}" branch --unset-upstream\`. Never push to main.\n` +
        `3. Report \`hasWork\`: true if the tree was dirty or the branch has commits not reachable from origin/main.\n` +
        `4. If hasWork, \`cd "${wt}" && /Users/msat1971/.local/bin/skillspoke-pr --title "<type(scope): description>" --body "<what changed and why>"\`. It pushes the branch itself. NEVER open the PR any other way — CodeRabbit does not scan PRs opened under an agent token, so the raw \`gh\` PR-create path yields an unreviewed PR. NEVER \`gh pr merge\`. If a PR already exists for this head skillspoke-pr returns that PR's URL — success, not failure.\n` +
        `5. Report the literal PR URL, the branch, and whether the tree is clean.`,
      {
        label: 'settle:land-work',
        phase: 'Settle',
        agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['treeClean', 'hasWork', 'branch', 'prUrl'],
          properties: {
            treeClean: { type: 'boolean' },
            hasWork: { type: 'boolean' },
            branch: { type: 'string' },
            prUrl: { type: 'string' },
            blocked: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    if (!reported) return { status: 'error', error: 'the settle agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

// Translate a settle report into the run's landing verdict. Three worlds:
//   not-applicable — no repo path was ever established, so nothing could be written
//                    through the contract and nothing can be orphaned. It does NOT
//                    touch result.ok; forcing a successful run to false here reported
//                    failure over correct work and taught the operator to disbelieve
//                    the orphan signal that exists to be believed.
//   error          — the settle agent threw or returned nothing. The run is unlanded,
//                    but say WHY, and never claim a URL was withheld by an agent that
//                    never ran.
//   reported       — the only world in which "orphaned" is an honest word.
function applySettle(res, settle) {
  const status = (settle && settle.status) || 'error'
  if (status === 'not-applicable') {
    res.landed = false
    res.settled = 'not-applicable'
    res.settleNote = (settle && settle.reason) || 'no repo path was established'
    log(`Settle: not applicable — ${res.settleNote}`)
    return
  }
  if (status === 'error') {
    res.landed = false
    res.ok = false
    res.settleFailed = { error: (settle && settle.error) || 'the settle step failed without an error message' }
    return
  }
  const PR_OK = /^https:\/\/github\.com\/[^/]+\/[^/]+\/pull\/\d+$/.test(String(settle.prUrl || '').trim())
  const landed = settle.treeClean === true && (settle.hasWork === false || PR_OK)
  res.landed = landed
  res.prUrl = PR_OK ? String(settle.prUrl).trim() : null
  res.settled = 'reported'
  if (!landed) {
    res.ok = false
    res.orphaned = {
      worktree: settleRepoPath,
      branch: settle.branch || null,
      blocked: (settle.blocked && settle.blocked.length ? settle.blocked : null) || ['settle returned no verifiable PR URL'],
    }
  }
}

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, checks, escalateTargets, phaseFn, gateWorkflow }) {
  let feedback = ''
  // Carried across attempts so loop exhaustion can say WHAT was unmet and on what
  // evidence, instead of a bare count. Both are computed at every attempt already;
  // the exhaustion path simply never saw them.
  let lastVerdict = null
  let lastArtifact = null
  const attempts = []
  // Every adjudication goes to the ledger. Without the verdict and its per-criterion
  // evidence, a run that stops at a gate records only `failed:<phase>` — which cannot
  // distinguish a genuine defect from an over-strict criterion or a loop exhaustion.
  const recordGate = (attempt, verdict, extra) =>
    runLedger.push({
      phase: `gate:${gate}`,
      gate,
      gatePhase: phaseName,
      attempt,
      maxLoops: MAX_LOOPS,
      verdict: (verdict && verdict.verdict) || 'no-verdict',
      criteria: ((verdict && verdict.criteria) || []).map((c) => ({
        criterion: c.criterion,
        met: c.met,
        evidence: c.evidence,
      })),
      unmetCriteria: ((verdict && verdict.criteria) || [])
        .filter((c) => !c.met)
        .map((c) => c.criterion),
      feedback: (verdict && verdict.feedback) || null,
      escalateTo: (verdict && verdict.escalateTo) || null,
      flags: (verdict && verdict.flags) || [],
      ...(extra || {}),
    })

  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    // Announce the START of the attempt. The progress panel cannot tick this phase:
    // its work happens inside a nested workflow(), whose agents the engine puts in
    // their own "▸ <mini>" group rather than counting toward the parent phase. So
    // without this line a phase that is actively running reads as "Not started yet",
    // and only its verdict — logged below, after the fact — ever proves it ran.
    log(`Gate ${gate} (${phaseName}): running attempt ${attempt}/${MAX_LOOPS}`)
    // The second argument is the STRUCTURED loop channel. A free-text string cannot
    // carry which criteria were unmet, nor what the phase produced last time — and a
    // phase re-judged with no memory of the prior round regenerates the prior round's
    // contradiction. Existing call sites that take only `feedback` are unaffected.
    const artifact = await phaseFn(feedback, {
      attempt,
      maxLoops: MAX_LOOPS,
      feedback,
      priorArtifact: lastArtifact,
      priorVerdicts: attempts.map((x) => x.verdict).filter(Boolean),
      unmetCriteria: lastVerdict ? ((lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence }))) : [],
    })
    lastArtifact = artifact
    // A phase may report that its work was ALREADY DONE — Red finding the contract
    // satisfied by passing tests, for instance. There is nothing for the gate to
    // judge and no rework that could change the answer, so gating it would fail a
    // criterion nothing can meet and burn the entire loop budget proving it.
    if (artifact && artifact.alreadySatisfied === true) {
      log(`${phaseName}: ALREADY SATISFIED — nothing to build; gate ${gate} skipped`)
      return { ok: true, artifact, alreadySatisfied: true }
    }
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, checks, artifact, escalateTargets,
    })
    if (!verdict) {
      recordGate(attempt, null, { terminal: 'no-verdict' })
      return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
    }
    recordGate(attempt, verdict)
    lastVerdict = verdict
    attempts.push({
      attempt,
      verdict,
      feedback: verdict.feedback || null,
      unmetCriteria: (verdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence })),
    })
    if (verdict.verdict === 'pass') {
      log(`Gate ${gate} (${phaseName}): PASS${verdict.flags && verdict.flags.length ? ` — flags: ${verdict.flags.join('; ')}` : ''}`)
      return { ok: true, artifact, verdict }
    }
    if (verdict.verdict === 'escalate') {
      log(`Gate ${gate} (${phaseName}): ESCALATE -> ${verdict.escalateTo || 'upstream'}`)
      return { ok: false, escalate: verdict.escalateTo || 'upstream', artifact, verdict }
    }
    log(`Gate ${gate} (${phaseName}): LOOP ${attempt}/${MAX_LOOPS} — ${verdict.feedback}`)
    feedback = verdict.feedback || ''
  }
  // Record the REAL final verdict, not null. A terminal ledger row with `criteria: []`
  // cannot distinguish a genuine defect from an over-strict criterion — which is the one
  // question anyone asks about an exhausted gate.
  recordGate(MAX_LOOPS, lastVerdict, { verdict: 'loop-exhausted', terminal: 'loop-exhausted' })
  return {
    ok: false,
    reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`,
    loopExhausted: true,
    artifact: lastArtifact,
    verdict: lastVerdict,
    unmetCriteria: lastVerdict ? (lastVerdict.criteria || []).filter((cc) => !cc.met).map((cc) => ({ criterion: cc.criterion, evidence: cc.evidence })) : [],
    attempts,
  }
}

// ── Front-end: spec freshness (Gate 1) ─────────────────────────────────────────
// Validate the spec still matches reality before building against it. The freshness
// mini is read-only; the independent gate rules on its fresh/stale verdict.
let result
try {
  result = await (async () => {
// ── Workspace: establish the tree every writing phase then operates in ─────────
// This is the structural mirror of the settle step below: settle LANDS the tree on
// every exit path, workspace ESTABLISHES it before the first write. Nothing else in
// this pipeline creates one, so without this step every writing phase edits whatever
// tree the caller pointed at — which twice meant `main` in a main working tree, the
// one place the project's own rules forbid, with no branch for settle to push.
phase('Workspace')
const workspace = await workflow('agent-teams-workforce:workspace', {
  repoPath: bead.repoPath,
  beadId: bead.id,
  branchPrefix: 'feat',
  purpose: bead.title || 'task',
})
if (!workspace || workspace.ok !== true || !workspace.repoPath) {
  return {
    ok: false,
    stage: 'workspace',
    bead: bead.id,
    reason: 'no verified worktree was established — refusing to write into the tree the caller pointed at',
    detail: workspace || null,
  }
}
// THE tree, from here on. Not the caller's path: the caller supplies a repository,
// this step supplies the worktree, and every downstream phase inherits THIS value.
const workRepoPath = workspace.repoPath
settleRepoPath = workRepoPath
if (workspace.ledger) runLedger.push(workspace.ledger)

phase('Spec Freshness')
log(`Validating freshness of ${bead.id || '(no id)'} — ${bead.title || ''}`)
const freshness = await gateLoop({
  gate: '1', phaseName: 'Spec Freshness',
  criteria: [
    'The spec still matches current reality (no spec-currency drift)',
    'No upstream dependency change invalidates the spec',
  ],
  escalateTargets: ['spec-authoring', 'architecture'],
  phaseFn: () => workflow('agent-teams-workforce:spec-freshness', { spec }),
})
if (freshness.artifact && freshness.artifact.ledger) runLedger.push(freshness.artifact.ledger)
if (!freshness.ok) return { ok: false, stage: 'spec-freshness', bead: bead.id, detail: freshness }

// The fresh, build-ready contract every downstream tail mini consumes. It carries
// the spec's repo path and acceptance criteria so Red/Green/etc. thread correctly.
// Surfaces DECIDE which specialist test writers tdd-red runs, so they are derived
// here rather than re-judged per task. Two sources, both evidence rather than guess:
// an explicit list the spec declares, and the structure of the authored spec set
// itself — an API spec means there is an API contract to verify, event contracts
// mean there is a delivery chain to verify. Anything not structurally evident must
// be declared by the spec; this does not infer surfaces from file paths or names.
// An empty result means unit tests only, which is correct for internal-only work.
const declaredSurfaces = Array.isArray(bead.surfaces) ? bead.surfaces : []
const structuralSurfaces = [
  bead.apiSpec ? 'api-contract' : null,
  Array.isArray(bead.eventContracts) && bead.eventContracts.length ? 'event-chain' : null,
].filter(Boolean)
const contractSurfaces = [...new Set([...declaredSurfaces, ...structuralSurfaces])]

const contract = {
  spec,
  // task-to-deploy was the only composite whose contract carried no `bead`, so tdd-red
  // rendered "Feature under test" and adversarial rendered "feature" — the id and title
  // were dropped from every Red and Adversarial prompt on the Task path.
  bead: { id: bead.id, title: bead.title || null, description: bead.description || null, repoPath: workRepoPath },
  repoPath: workRepoPath,
  acceptanceCriteria: Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria : [],
  surfaces: contractSurfaces,
  // Pyramid shape, coverage threshold, and environment matrix belong to the spec,
  // not to each task built from it. Carried when the spec states one; absent when
  // it does not — tdd-red does not invent a per-task substitute.
  testStrategy: bead.testStrategy || null,
  freshness: freshness.artifact,
}
// contract.repoPath IS the workspace step's return value; nothing downstream may
// substitute the caller's path for it.
settleRepoPath = contract.repoPath
if (contractSurfaces.length) log(`Contract surfaces: ${contractSurfaces.join(', ')} — specialist test writers will be derived from these`)

// ── Red (Gate 2a) ─────────────────────────────────────────────────────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    'Tests assert against freshly generated artifacts, not checked-in build output (a test reading a committed cdk.out template or similar passes forever regardless of the code)',
    'A failing test encodes the spec contract',
    'The test fails for the intended reason',
    'No production code changed yet',
  ],
  checks: [
    { field: 'redConfirmed', equals: true, label: 'the phase reports Red confirmed' },
    { field: 'evidence', nonEmpty: true, label: 'executed failing output was captured as evidence' },
    // Red proves a test fails NOW. It must also establish that a pass is REACHABLE:
    // a test pinned to a pre-fix import path fails correctly and can never go green,
    // and is otherwise indistinguishable from a correct Red.
    { field: 'greenReachable', equals: true, label: 'every authored test names the production file whose change makes it pass' },
    // NEGATIVE CONTROL over the captured output. Deliberately NARROW: a missing fixture
    // is always a harness fault and never a product failure. ModuleNotFoundError,
    // ImportError and "collected 0 items" are deliberately NOT in this pattern — for a
    // missing-capability defect the only failure obtainable at HEAD IS the absence of
    // the symbol the fix introduces, and pytest reports exactly that shape. Banning it
    // would re-break the carve-out that cost 827k tokens on ssbd-cg27 to learn.
    { field: 'evidence', notMatches: 'fixture .{0,80} not found', label: 'the captured failure is a product failure, not a missing fixture' },
  ],
  escalateTargets: ['spec-freshness'],
  // From attempt 2 the previous attempt's test is ON DISK. Discovery would re-find it,
  // report no gaps, and the confirm-existing branch would hand the gate back the very
  // test it just rejected — through a code path the gate's objection never reaches.
  // A re-run after a rejection authors; it does not shop for what it already wrote.
  phaseFn: (feedback, loop) => workflow('agent-teams-workforce:tdd-red', { contract, feedback, skipDiscovery: !!(loop && loop.attempt > 1) }),
})
if (red.artifact && red.artifact.ledger) runLedger.push(red.artifact.ledger)
if (!red.ok) return { ok: false, stage: 'red', bead: bead.id, detail: red }
// Red found the contract already encoded by PASSING tests: the behavior exists.
// Green would be asked to make a failing test pass when none fails, so the run
// ends here — successfully, with nothing built. Closing the work item is a human
// call, not something this composite does on its own.
if (red.alreadySatisfied) {
  return {
    ok: true, stage: 'red', bead: bead.id, alreadySatisfied: true, built: false,
    reason: 'the spec contract is already satisfied by passing tests — no Red is obtainable and nothing was authored or changed',
    detail: red.artifact,
  }
}

// ── Green (Gate 2b) ───────────────────────────────────────────────────────────
phase('Green')
const green = await gateLoop({
  gate: '2b', phaseName: 'TDD Green',
  criteria: [
    'The previously-failing test now passes',
    'No other tests regressed',
    'The change is minimal and the test was not weakened',
  ],
  checks: [
    { field: 'greenConfirmed', equals: true, label: 'the phase reports Green confirmed' },
    { field: 'evidence', nonEmpty: true, label: 'executed passing output was captured as evidence' },
  ],
  escalateTargets: ['spec-freshness', 'red'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-green', { contract, red: red.artifact, implementer: a.implementer, feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', bead: bead.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail — started here (after Green),
// awaited before deploy.
const docTrack = workflow('agent-teams-workforce:documentation', { contract, green: green.artifact })

// Settle the parallel documentation track before any early failure return, so a
// failed run never leaves docTrack as an unhandled rejection or orphaned work.
async function failAfterDoc(stage, detail) {
  await Promise.allSettled([docTrack])
  return { ok: false, stage, bead: bead.id, detail }
}

// ── Refactor (Gate 2c) ────────────────────────────────────────────────────────
phase('Refactor')
const refactor = await gateLoop({
  gate: '2c', phaseName: 'TDD Refactor',
  criteria: [
    'Tests still green',
    'Behavior preserved (no regression)',
    'Complexity/duplication reduced',
  ],
  escalateTargets: ['green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-refactor', { contract, green: green.artifact, feedback }),
})
if (refactor.artifact && refactor.artifact.ledger) runLedger.push(refactor.artifact.ledger)
if (!refactor.ok) return await failAfterDoc('refactor', refactor)

// ── Integration (Gate 3) ──────────────────────────────────────────────────────
phase('Integration')
const integration = await gateLoop({
  gate: '3', phaseName: 'Integration Testing',
  criteria: [
    'Integration/contract/E2E suites pass across the event chain',
    'Contracts valid across service boundaries',
    // "Coverage met" is unsatisfiable for two legitimate change classes and rejected
    // correct work at 1.88M tokens on ssbd-ew3t. bug-fix.js learned this; this gate
    // still carried the bare version.
    'Coverage is adequate FOR THIS CHANGE CLASS. A deletion whose tests assert absence (greps, path checks, hash freezes) cannot produce code coverage and MUST NOT be failed for 0% — verify instead that the absence assertions are real and complete. A repo with no integration suite is a pre-existing gap: report it, do not fail the change for it. Demand real coverage only where the change ADDS or MODIFIES executable paths.',
    'No flaky tests',
  ],
  escalateTargets: ['green', 'red', 'spec-freshness'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:integration', { contract, green: green.artifact, feedback }),
})
if (integration.artifact && integration.artifact.ledger) runLedger.push(integration.artifact.ledger)
if (!integration.ok) return await failAfterDoc('integration', integration)

// ── Adversarial (Gate 4 — constitutional) ─────────────────────────────────────
phase('Adversarial')
const adversarial = await gateLoop({
  gate: '4', phaseName: 'Adversarial Validation', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
  criteria: [
    'No open constitutive findings (no vulns, injection, auth bypass, permission escalation, or data exposure)',
    'All confirmed findings adjudicated; security findings not downgraded by implementers',
  ],
  escalateTargets: ['green', 'spec-freshness'],
  // priorRulings is what makes a re-run adjudication accountable to the one before it.
  // Without it the adjudicator is a fresh instance every round with no knowledge that it
  // ever ruled — it is not reversing a ruling, it has never been shown one.
  phaseFn: (feedback, loop) => workflow('agent-teams-workforce:adversarial', {
    contract,
    green: green.artifact,
    feedback,
    priorRulings: (loop && loop.priorArtifact && loop.priorArtifact.adjudication && loop.priorArtifact.adjudication.rulings) || [],
  }),
})
if (!adversarial.ok) return await failAfterDoc('adversarial', adversarial)

// Documentation must be current before the deploy.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy to dev (Gate 5) — dev IS deployed; only qa/prod is human-gated ─────
// Deploying to dev is how code reaches AWS and is part of the development
// lifecycle, not a release. A change cannot be integration-tested in AWS until
// it is IN AWS. This phase runs deploy.js, which deploys to dev and smoke-tests
// the deployed endpoints. Outward-facing qa/prod rollout never happens here.
phase('Deploy-to-dev')
const deployReady = await gateLoop({
  gate: '5', phaseName: 'Deploy to dev',
  criteria: [
    'CDK synth valid, no unresolved drift',
    'Smoke tests present',
    'Deployed to the dev environment',
    'Smoke tests pass against the deployed dev endpoints',
  ],
  checks: [
    { field: 'prOpened', equals: true, label: 'a pull request was opened for this work' },
    { field: 'prUrl', nonEmpty: true, label: 'the PR URL was reported' },
  ],
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:deploy', { contract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-to-dev', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: ['spec-freshness', 'red', 'green', 'refactor', 'integration', 'adversarial', 'deploy-to-dev'],
  note: 'DEPLOYED TO DEV and smoke-checked against the deployed endpoints. Outward-facing qa/prod rollout is a separate human-gated action and did not happen here.',
  contract,
  results: {
    freshness: freshness.artifact, red: red.artifact, green: green.artifact, refactor: refactor.artifact,
    integration: integration.artifact, adversarial: adversarial.artifact,
    deployReadiness: deployReady.artifact, documentation: docCurrency,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  const settle = await settleRun()
  if (result) applySettle(result, settle)
}
return result
