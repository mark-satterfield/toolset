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
    { title: 'Deploy-readiness' },
  ],
}

// args: { bead: { id, title, description, repoPath }, implementer?, maxLoops? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const MAX_LOOPS = a.maxLoops || 3
if (!bead.id) log('⚠ no bead.id supplied — running in dry/demo mode')

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
        phase: 'Deploy-readiness',
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
async function gateLoop({ gate, phaseName, criteria, escalateTargets, phaseFn, gateWorkflow }) {
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
    const artifact = await phaseFn(feedback)
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, artifact, escalateTargets,
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

// ── Red (Gate 2a) ─────────────────────────────────────────────────────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    // Red is satisfied by EITHER a failure at HEAD or a DIFFERENTIAL failure at the
    // pre-fix revision. A bead whose defect was already repaired cannot fail at HEAD;
    // demanding it there fails correct work and burns a full pipeline proving a bug is
    // gone. Differential red (same test, detached pre-fix worktree, fails there and
    // passes here) is equally strong evidence and is the ONLY form available for a
    // stale bead.
    'A test reproduces the defect — failing at HEAD, or failing at the pre-fix revision and passing at HEAD (differential red)',
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

  phase('Green')
  green = await gateLoop({
    gate: '2b', phaseName: 'TDD Green',
    criteria: ['The previously-failing test now passes', 'No other tests regressed', 'The change is minimal and the test was not weakened'],
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
      'A test reproduces the defect — failing at HEAD, or failing at the pre-fix revision and passing at HEAD (differential red)',
      'The test fails for the intended reason. A failure caused by the absence of the very API the fix will introduce IS a valid intended reason for a missing-capability defect — do NOT reject it as an import error. Reject only a genuine harness fault: the test module itself failing to import, a broken fixture, a typo, a missing test dependency, or a failure in code unrelated to the defect.',
      'The test asserts the real post-fix behavior, not merely that a symbol is absent.',
      'No production code was changed to manufacture the failure',
      'Any test the Green gate identified as UNPASSABLE BY CONSTRUCTION is repaired — a test whose own source defeats its assertion (for example a literal-search test whose variable name contains the literal it searches for, or an assertion that can never hold regardless of production code) is a test defect and MUST be fixed here. Repairing such a test is not weakening it.',
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
if (!refactor.ok) return await failAfterDoc('refactor', refactor)

// ── Integration (Gate 3) ──────────────────────────────────────────────────────
phase('Integration')
const integration = await gateLoop({
  gate: '3', phaseName: 'Integration Testing',
  criteria: ['Integration/contract/E2E suites pass', 'Contracts valid across boundaries', 'Coverage met', 'No flaky tests'],
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

// Documentation must be current before readiness.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy readiness (Gate 5) — NO autonomous prod rollout ────────────────────
phase('Deploy-readiness')
const deployReady = await gateLoop({
  gate: '5', phaseName: 'Deployment readiness',
  criteria: ['CDK synth valid, no unresolved drift', 'Smoke tests present', 'Documentation current', 'Readiness review is go'],
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:deploy', { contract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-readiness', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: ['triage', 'red', 'green', 'refactor', 'integration', 'adversarial', 'deploy'],
  deployedToDev: !!(deployReady.artifact && deployReady.artifact.deployedToDev),
  note: 'Deployed to DEV and smoke-tested. Outward-facing qa/prod rollout remains a separate human-gated action.',
  contract,
  results: {
    red: red.artifact, green: green.artifact, refactor: refactor.artifact,
    integration: integration.artifact, adversarial: adversarial.artifact,
    deployReadiness: deployReady.artifact, documentation: docCurrency,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
}
return result
