export const meta = {
  name: 'bug-fix',
  description:
    'Composite — fixes a bug bead. Stitches the bug-triage front-end onto the shared build-and-ship tail (Red, Green, Refactor, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Triage' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-to-dev' },
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

// args: { bead: { id, title, description, repoPath }, implementer?, maxLoops? }
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

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, checks, escalateTargets, phaseFn, gateWorkflow }) {
  let feedback = ''
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
    const artifact = await phaseFn(feedback)
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
  recordGate(MAX_LOOPS, null, { verdict: 'loop-exhausted', terminal: 'loop-exhausted' })
  return { ok: false, reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`, loopExhausted: true }
}

// ── Front-end: triage ─────────────────────────────────────────────────────────
let result
try {
  result = await (async () => {
phase('Triage')
log(`Triaging ${bead.id || '(no id)'} — ${bead.title || ''}`)
const contract = await workflow('agent-teams-workforce:bug-triage', { bead })
if (!contract) return { ok: false, stage: 'triage', reason: 'triage produced nothing' }

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
  ],
  escalateTargets: ['triage'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-red', { contract, feedback }),
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
    criteria: ['The previously-failing test now passes', 'No other tests regressed', 'The change is minimal and the test was not weakened'],
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
    ],
    escalateTargets: ['triage'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:tdd-red', {
        contract,
        red: redResult.artifact,
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
  phaseFn: (feedback) => workflow('agent-teams-workforce:adversarial', { contract, green: green.artifact, feedback }),
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
}
return result
