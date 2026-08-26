export const meta = {
  name: 'bug-fix',
  description:
    'Composite — fixes a bug bead. Stitches the bug-triage front-end onto the shared build-and-ship tail (Red, Green, Refactor, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Workspace', detail: 'establishes the linked worktree every writing phase then operates in' },
    { title: 'Triage' },
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

// THE ONE deployed-red criterion, shared by BOTH Red gates (first and
// post-escalation). Duplicating the text at each call site meant a single-site
// edit silently diverged the two gates — prompt text is executable configuration
// here, so it gets a single source of truth. The anti-abuse clauses mirror the
// sibling carve-out in deploy.js (cdk-validate): the sufficiency grant is
// explicitly conditioned on its precondition so it cannot be read as surviving
// the precondition's failure.
// NOT exported. The runtime accepts exactly ONE top-level export — `meta` — and
// rejects the script outright on a second one, before any phase runs. Nothing
// imports this; it was exported by habit and it made bug-fix.js the only
// undispatchable workflow in the set.
const DEPLOYED_RED_CRITERION =
  'A test reproduces the defect — failing at HEAD, or failing at the pre-fix revision and passing at HEAD (differential red), or failing against the DEPLOYED environment while the source tree is already correct (deployed red). Deployed red is fully sufficient on its own ONLY WHEN its precondition actually holds: a failing run against the deployed environment was actually OBSERVED and reported, AND the source tree was checked and found already correct. Provided that both hold, do NOT additionally demand a source-level failure and do NOT reject the red because the working tree greps clean. Do NOT accept a deployed-red claim when no failing run against the deployed environment was observed, when the source tree was never checked for a source-level red, or merely because running a source-level test is inconvenient, the environment is unclear, or credentials are missing — each of those is a genuine failure to obtain red, not a deployed red.'

// args: { bead: { id, title, description, repoPath }, implementer?, maxLoops?, maxEscalations? }
//   bead.repoPath is REQUIRED and names the REPOSITORY. The tree the phases write in is
//   established by the Workspace step below and is NOT this value.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
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

// Decision ledger for over-time mining. Each instrumented mini returns a `ledger`
// on its artifact; the composite collects them and persists ONCE via run-ledger-writer
// (a project agent — scripts can't write files). Persisted in a finally so it runs
// on success, early-return, and throw alike.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'bug-fix', bead: { id: bead.id || null, title: bead.title || null }, outcome, runLedger })}`,
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

// ── Front-end: triage ─────────────────────────────────────────────────────────
let result
try {
  result = await (async () => {
// ── Workspace: establish the tree every writing phase then operates in ─────────
// This is the structural mirror of the settle step above: settle LANDS the tree on
// every exit path, workspace ESTABLISHES it before the first write. Nothing else in
// this pipeline creates one, so without this step every writing phase edits whatever
// tree the caller pointed at — which twice meant `main` in a main working tree, the
// one place the project's own rules forbid, with no branch for settle to push.
phase('Workspace')
const workspace = await workflow('agent-teams-workforce:workspace', {
  repoPath: bead.repoPath,
  beadId: bead.id,
  branchPrefix: 'fix',
  purpose: bead.title || 'bug fix',
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
const workBead = { ...bead, repoPath: workRepoPath }

phase('Triage')
log(`Triaging ${bead.id || '(no id)'} — ${bead.title || ''}`)
const contract = await workflow('agent-teams-workforce:bug-triage', { bead: workBead })
if (!contract) return { ok: false, stage: 'triage', reason: 'triage produced nothing' }
// The composite owns the tree, not the mini. bug-triage echoes back whatever repoPath
// it was handed; pinning it here means no mini can substitute a different tree.
contract.repoPath = workRepoPath
settleRepoPath = workRepoPath

// Triage sizes the bug as well as diagnosing it. A defect whose honest remedy is a
// redesign does NOT continue down this path: the fix path has no PRD validation, no
// architecture ruling, and no spec, so building it here would ship an unreviewed
// architecture change on the authority of a bug ticket.
//
// Promotion to a PRD and an Epic is a HUMAN decision — whether to build it, and
// now — so this stops and reports rather than promoting itself.
if (contract.scope === 'needs-prd') {
  log(`Bug ${bead.id || ''} needs a PRD, not a fix — stopping before Red. ${contract.scopeRationale || ''}`)
  return {
    ok: false,
    stage: 'triage',
    outcome: 'needs-prd',
    bead: bead.id || null,
    reason: contract.scopeRationale || 'triage sized this defect as needing a PRD and an Epic',
    contractsTouched: contract.contractsTouched || [],
    diagnosis: {
      reproduction: contract.reproduction,
      rootCause: contract.rootCause,
      affectedFiles: contract.affectedFiles,
      blastRadius: contract.blastRadius,
    },
    note:
      'Nothing was built and nothing was deployed. The diagnosis above is the input a PRD ' +
      'would start from. Promote it when you want it built: /agent-teams-workforce:start-prd.',
  }
}

// ── Red (Gate 2a) ─────────────────────────────────────────────────────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    'Tests assert against freshly generated artifacts, not checked-in build output (a test reading a committed cdk.out template or similar passes forever regardless of the code)',
    // Red is satisfied by EITHER a failure at HEAD or a DIFFERENTIAL failure at the
    // pre-fix revision. A bead whose defect was already repaired cannot fail at HEAD;
    // demanding it there fails correct work and burns a full pipeline proving a bug is
    // gone. Differential red (same test, detached pre-fix worktree, fails there and
    // passes here) is equally strong evidence and is the ONLY form available for a
    // stale bead.
    // DEPLOYED-ARTIFACT CARVE-OUT. A defect can be real and live while the source tree is
    // already correct, because the fix was committed but never deployed. The artifact under
    // test is then the DEPLOYED bytes, not the working tree, and NO source-level red of any
    // kind — at HEAD or differential — is obtainable. ssbd-mqkq hit exactly this: commit
    // 924fd5c93 removed the third-party script, apps/web/app/layout.tsx and out/ both grep
    // clean, yet https://dev.myagent.skillspoke.ai served the script on every page load,
    // proven by a failing Playwright run AND an independent cache-busted curl. The gate
    // computed redConfirmed:false purely because the SOURCE was clean, and failed a run
    // whose evidence was airtight — 676k tokens to reject a correct finding.
    // Red against the deployed environment is the STRONGEST form of red available, not a
    // weaker one: it observes the defect in the artifact users actually receive.
    DEPLOYED_RED_CRITERION,
    // When red is deployed-only the remediation is a DEPLOY, not an implementation. Green
    // will correctly find no production code to write, so the verdict must name the real
    // action instead of sending Green hunting for a change that does not exist.
    'If red was obtained ONLY against the deployed environment, say so explicitly in the evidence and name the remediation as deploy-and-invalidate rather than a code change.',
    // MISSING-CAPABILITY CARVE-OUT. The older wording ("not a harness or import error")
    // was structurally unsatisfiable for any defect whose fix INTRODUCES a symbol. If the
    // bug is "ConfigurationError is never raised" and ConfigurationError does not exist
    // yet, the only failure obtainable at HEAD is that symbol's absence — which reads as
    // an import error. The gate then rejects a correct test, the writer cannot possibly
    // comply, and the loop exhausts. That cost 827k tokens on ssbd-cg27 alone, and this
    // is the same family of false rejection the differential-red carve-out above fixed.
    // The distinction that actually matters is WHOSE absence: the code under test
    // (legitimate red) versus the test's own scaffolding (a broken test).
    'The test fails for the intended reason. A failure caused by the absence of the very API the fix will introduce IS a valid intended reason for a missing-capability defect — do NOT reject it as an import error. Reject only a genuine harness fault: the test module itself failing to import, a broken fixture, a typo, a missing test dependency, or a failure in code unrelated to the defect.',
    'The test asserts the real post-fix behavior, not merely that a symbol is absent. Once the capability exists the test must still be meaningful — it must exercise the behavior (the raise, the log record, the persistence call), not just that an import now succeeds.',
    'No production code was changed to manufacture the failure',
  ],
  checks: [
    { field: 'redConfirmed', equals: true, label: 'the phase reports Red confirmed' },
    { field: 'evidence', nonEmpty: true, label: 'executed failing output was captured as evidence' },
    // Red proves a test fails NOW. It must also establish that a pass is REACHABLE:
    // a test pinned to a pre-fix import path fails correctly and can never go green,
    // and is otherwise indistinguishable from a correct Red (ssbd-vtnl).
    { field: 'greenReachable', equals: true, label: 'every authored test names the production file whose change makes it pass' },
    // NEGATIVE CONTROL over the captured output. Deliberately NARROW: a missing fixture
    // is always a harness fault and never a product failure. ModuleNotFoundError,
    // ImportError and "collected 0 items" are deliberately NOT in this pattern — for a
    // missing-capability defect the only failure obtainable at HEAD IS the absence of
    // the symbol the fix introduces, and pytest reports exactly that shape. Banning it
    // would re-break the carve-out that cost 827k tokens on ssbd-cg27 to learn.
    { field: 'evidence', notMatches: 'fixture .{0,80} not found', label: 'the captured failure is a product failure, not a missing fixture' },
  ],
  escalateTargets: ['triage'],
  // From attempt 2 the previous attempt's test is ON DISK. Discovery would re-find it,
  // report no gaps, and the confirm-existing branch would hand the gate back the very
  // test it just rejected — through a code path the gate's objection never reaches.
  // A re-run after a rejection authors; it does not shop for what it already wrote.
  phaseFn: (feedback, loop) => workflow('agent-teams-workforce:tdd-red', { contract, feedback, skipDiscovery: !!(loop && loop.attempt > 1) }),
})

// ── Red ⇄ Green with WORKING escalation ───────────────────────────────────────
// Escalation used to be a labelled exit, not control flow: gateLoop returned
// {escalate:'red'} and the caller immediately failed the run. So Green could name Red
// as its escalation target, Red would never re-run, and the run died — even though the
// composite's own description claims it "owns loop and escalate control flow".
//
// This bites hardest on a DEFECTIVE TEST, where the deadlock is total by design: the
// implementer is forbidden to modify a test, and the gate is right to fail a test that
// does not pass. Neither role may fix it, so nobody can. ssbd-ew3t hit exactly this —
// a test searched for a literal that its own variable name contained, so it could never
// pass no matter how correct the production change was. 683k tokens, correct deletions,
// zero regressions, run failed.
//
// Escalating to Red re-runs the TEST-AUTHORING phase with the gate's evidence, which is
// the only phase permitted to repair a test. Bounded so a Red/Green disagreement cannot
// ping-pong forever.
const MAX_ESCALATIONS = a.maxEscalations || 2
let redResult = red
let green = null
let escalations = 0

for (;;) {
  if (redResult.artifact && redResult.artifact.ledger) runLedger.push(redResult.artifact.ledger)
  if (!redResult.ok) return { ok: false, stage: 'red', bead: bead.id, detail: redResult }
  // Red found the expected behavior already asserted by PASSING tests: this defect
  // is already fixed, or was never real. Green would be asked to make a failing test
  // pass when none fails, and the Red⇄Green escalation below would ping-pong over a
  // test nobody can legitimately make fail. The run ends here — successfully, with
  // nothing built. Closing the bug is a human call.
  if (redResult.alreadySatisfied) {
    return {
      ok: true, stage: 'red', bead: bead.id, alreadySatisfied: true, built: false,
      reason: 'the expected behavior is already asserted by passing tests — the defect is already fixed or was never reproducible; no Red is obtainable and nothing was authored or changed',
      detail: redResult.artifact,
    }
  }

  phase('Green')
  green = await gateLoop({
    gate: '2b', phaseName: 'TDD Green',
    criteria: [
      'The previously-failing test now passes',
      'No other tests regressed',
      'The change is minimal and the test was not weakened',
      // Names the un-passable case so it reliably produces escalate:"red" instead of a
      // loop. The implementer may not modify a test and the gate is right to fail a test
      // that does not pass, so neither role can break the deadlock — only Red can.
      'If a test cannot be made to pass AS AUTHORED — it is pinned to a pre-fix import path, patches a symbol at a module path the fix does not use, or its own source defeats its assertion — that is a TEST defect, not an implementation failure. Escalate to red; do NOT loop Green over it and do NOT weaken the test to pass it.',
    ],
    checks: [
      { field: 'greenConfirmed', equals: true, label: 'the phase reports Green confirmed' },
      { field: 'evidence', nonEmpty: true, label: 'executed passing output was captured as evidence' },
    ],
    escalateTargets: ['triage', 'red'],
    phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-green', { contract, red: redResult.artifact, implementer: a.implementer, feedback }),
  })
  if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
  if (green.ok) break

  const canRetryRed = green.escalate === 'red' && escalations < MAX_ESCALATIONS
  if (!canRetryRed) return { ok: false, stage: 'green', bead: bead.id, detail: green }

  escalations += 1
  const why = (green.verdict && (green.verdict.feedback || (green.verdict.criteria || []).filter((c) => !c.met).map((c) => `${c.criterion}: ${c.evidence}`).join('\n'))) || 'Green gate escalated to Red without stated feedback.'
  log(`Green escalated to Red (${escalations}/${MAX_ESCALATIONS}) — re-authoring tests`)

  phase('Red')
  redResult = await gateLoop({
    gate: '2a', phaseName: `TDD Red (re-authored after Green escalation ${escalations})`,
    criteria: [
      // Same deployed-artifact carve-out as the first Red gate — the SHARED constant
      // guarantees the two gates can never diverge. See the comment at its definition.
      DEPLOYED_RED_CRITERION,
      'The test fails for the intended reason. A failure caused by the absence of the very API the fix will introduce IS a valid intended reason for a missing-capability defect — do NOT reject it as an import error. Reject only a genuine harness fault: the test module itself failing to import, a broken fixture, a typo, a missing test dependency, or a failure in code unrelated to the defect.',
      'The test asserts the real post-fix behavior, not merely that a symbol is absent.',
      'No production code was changed to manufacture the failure',
      'Any test the Green gate identified as UNPASSABLE BY CONSTRUCTION is repaired — a test whose own source defeats its assertion (for example a literal-search test whose variable name contains the literal it searches for, or an assertion that can never hold regardless of production code) is a test defect and MUST be fixed here. Repairing such a test is not weakening it.',
    ],
    // Same deterministic pair as the first Red gate — a phase that did not obtain
    // Red, or obtained it without capturing executed output, is rejected without
    // consulting the adjudicator at all.
    checks: [
      { field: 'redConfirmed', equals: true, label: 'the phase reports Red confirmed' },
      { field: 'evidence', nonEmpty: true, label: 'executed failing output was captured as evidence' },
      { field: 'greenReachable', equals: true, label: 'every authored test names the production file whose change makes it pass' },
    ],
    escalateTargets: ['triage'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:tdd-red', {
        contract,
        red: redResult.artifact,
        // The reuse branch is how a bad test survives a loop: discovery re-finds the
        // previous attempt's file, reports no gaps, and the confirm-existing branch
        // hands the gate back the identical un-passable test — through a code path the
        // gate's own objection never reaches. On a re-author, author.
        skipDiscovery: true,
        feedback: `The Green gate escalated back to test authoring. Green could not pass because of a defect in the TESTS THEMSELVES, not in the production change. Repair the test, then re-confirm it is still a genuine red.\n\nGreen gate evidence:\n${why}\n\n${feedback || ''}`,
      }),
  })
}

// Documentation runs ALONGSIDE the rest of the tail (started, awaited before deploy).
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
  criteria: ['Tests still green', 'Behavior preserved (no regression)', 'Complexity/duplication reduced'],
  escalateTargets: ['green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-refactor', { contract, green: green.artifact, feedback }),
})
if (refactor.artifact && refactor.artifact.ledger) runLedger.push(refactor.artifact.ledger)
// Refactor is BEHAVIOR-PRESERVING CLEANUP on already-green code. It must never be able
// to destroy a completed Red+Green. It previously could, twice over: a gate failure
// returned out of the whole composite, and a subagent that finished without emitting
// StructuredOutput THREW and killed the run outright — that crash cost 1.13M tokens on
// ssbd-mqkq, a one-line deletion, after Green had already succeeded.
// Degrade instead: keep the green code, record the finding, and carry on to Integration.
if (!refactor.ok) {
  log(`Refactor did not pass (${refactor.reason || 'gate failure'}) — keeping the green implementation and continuing. Cleanup is not a correctness gate.`)
  runLedger.push({ phase: 'refactor', beadId: bead.id || null, ok: false, degraded: true, reason: refactor.reason || 'gate failure' })
}

// ── Integration (Gate 3) ──────────────────────────────────────────────────────
phase('Integration')
const integration = await gateLoop({
  gate: '3', phaseName: 'Integration Testing',
  criteria: [
    'Integration/contract/E2E suites pass',
    'Contracts valid across boundaries',
    // "Coverage met" was unsatisfiable for two legitimate change classes, and rejected
    // correct work at 1.88M tokens on ssbd-ew3t alone.
    //   1. A DELETION. Its correct test asserts ABSENCE — repo-wide greps, path checks,
    //      SHA freezes. It never imports the deleted code, because the code is gone.
    //      Coverage is necessarily 0% and "no data was collected" is the RIGHT result.
    //   2. A repo with NO integration suite at all. Demanding coverage of a suite that
    //      does not exist fails the change for a pre-existing gap it did not cause.
    // Judge coverage against what the change could possibly cover, not an absolute.
    'Coverage is adequate FOR THIS CHANGE CLASS. A deletion whose tests assert absence (greps, path checks, hash freezes) cannot produce code coverage and MUST NOT be failed for 0% — verify instead that the absence assertions are real and complete. A repo with no integration suite is a pre-existing gap: report it, do not fail the change for it. Demand real coverage only where the change ADDS or MODIFIES executable paths.',
    'No flaky tests',
  ],
  escalateTargets: ['green', 'red', 'triage'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:integration', { contract, green: green.artifact, feedback }),
})
if (integration.artifact && integration.artifact.ledger) runLedger.push(integration.artifact.ledger)
if (!integration.ok) return await failAfterDoc('integration', integration)

// ── Adversarial (Gate 4 — constitutional) ─────────────────────────────────────
phase('Adversarial')
const adversarial = await gateLoop({
  gate: '4', phaseName: 'Adversarial Validation', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
  criteria: ['No open constitutive findings (no vulns, injection, auth bypass, or data exposure)', 'All confirmed findings adjudicated'],
  escalateTargets: ['green', 'triage'],
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
if (adversarial.artifact && adversarial.artifact.ledger) runLedger.push(adversarial.artifact.ledger)
if (!adversarial.ok) return await failAfterDoc('adversarial', adversarial)

// Documentation must be current before the deploy.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy to dev (Gate 5) — dev IS deployed; only qa/prod is human-gated ─────
// Deploying to dev is how the fix reaches AWS and is part of the development
// lifecycle, not a release. Naming this phase "readiness" is what made every
// other composite report a completed deploy as merely ready — the same defect,
// missed here because bug-fix already deployed correctly and only its LABEL lied.
phase('Deploy-to-dev')
const deployReady = await gateLoop({
  gate: '5', phaseName: 'Deploy to dev',
  criteria: ['CDK synth valid, no unresolved drift', 'Smoke tests present', 'Deployed to the dev environment', 'Smoke tests pass against the deployed dev endpoints'],
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
  stagesComplete: ['triage', 'red', 'green', 'refactor', 'integration', 'adversarial', 'deploy'],
  deployedToDev: !!(deployReady.artifact && deployReady.artifact.deployedToDev),
  note: 'Deployed to DEV and smoke-tested. Outward-facing qa/prod rollout remains a separate human-gated action.',
  contract,
  results: {
    red: redResult.artifact, green: green.artifact, refactor: refactor && refactor.artifact,
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
