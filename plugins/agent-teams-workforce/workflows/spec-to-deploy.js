export const meta = {
  name: 'spec-to-deploy',
  description:
    'Composite — drives an approved spec from freshness check through TDD (Red, Green, Refactor), Integration, Adversarial, and Deploy-to-dev. Stitches the spec-freshness front-end onto the shared build-and-ship tail via mini workflows, with an independent gate between phases and Documentation as a parallel track started after Green and awaited before deploy. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV and smoke-checks the deployed endpoints — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Spec Freshness' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-to-dev' },
  ],
}

// args: {
//   spec: {                     // the approved, implementation-ready spec to build
//     id?, title?, path?,       // identity + location of the spec document
//     repoPath?,                // repo the spec governs (threaded to every tail mini as contract.repoPath)
//     adrRefs?: string[],       // ADRs the spec references (freshness checks their currency)
//     dependencies?: string[],  // upstream contracts/specs/libs the spec relies on
//     acceptanceCriteria?: [{ given, when, then }],  // testable AC the Red phase encodes
//   },
//   implementer?: string,        // override the Green-phase implementer agent (default chassis-extension-implementer)
//   maxLoops?: number,           // bounded retries per gate (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const spec = a.spec || {}
const MAX_LOOPS = a.maxLoops || 3
if (!spec.id) log('⚠ no spec.id supplied — running in dry/demo mode')

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'spec-to-deploy', bead: null, subject: spec.id || null, outcome, runLedger })}`,
      {
        label: 'ledger:persist',
        phase: 'Deploy-to-dev',
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

// ── Front-end: spec freshness (Gate 1) ─────────────────────────────────────────
// Validate the spec still matches reality before building against it. The freshness
// mini is read-only; the independent gate rules on its fresh/stale verdict.
let result
try {
  result = await (async () => {
phase('Spec Freshness')
log(`Validating freshness of ${spec.id || '(no id)'} — ${spec.title || ''}`)
const freshness = await gateLoop({
  gate: '1', phaseName: 'Spec Freshness',
  criteria: [
    'The spec still matches current reality (no spec-currency drift)',
    'Referenced ADRs are current (no superseded/stale ADR governs the build)',
    'No upstream dependency change invalidates the spec',
  ],
  escalateTargets: ['spec-authoring', 'architecture'],
  phaseFn: () => workflow('agent-teams-workforce:spec-freshness', { spec }),
})
if (freshness.artifact && freshness.artifact.ledger) runLedger.push(freshness.artifact.ledger)
if (!freshness.ok) return { ok: false, stage: 'spec-freshness', spec: spec.id, detail: freshness }

// The fresh, build-ready contract every downstream tail mini consumes. It carries
// the spec's repo path and acceptance criteria so Red/Green/etc. thread correctly.
const contract = {
  spec,
  repoPath: spec.repoPath || null,
  acceptanceCriteria: Array.isArray(spec.acceptanceCriteria) ? spec.acceptanceCriteria : [],
  freshness: freshness.artifact,
}

// ── Red (Gate 2a) ─────────────────────────────────────────────────────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    'A failing test encodes the spec contract',
    'The test fails for the intended reason',
    'No production code changed yet',
  ],
  escalateTargets: ['spec-freshness'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-red', { contract, feedback }),
})
if (red.artifact && red.artifact.ledger) runLedger.push(red.artifact.ledger)
if (!red.ok) return { ok: false, stage: 'red', spec: spec.id, detail: red }

// ── Green (Gate 2b) ───────────────────────────────────────────────────────────
phase('Green')
const green = await gateLoop({
  gate: '2b', phaseName: 'TDD Green',
  criteria: [
    'The previously-failing test now passes',
    'No other tests regressed',
    'The change is minimal and the test was not weakened',
  ],
  escalateTargets: ['spec-freshness', 'red'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-green', { contract, red: red.artifact, implementer: a.implementer, feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', spec: spec.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail — started here (after Green),
// awaited before deploy.
const docTrack = workflow('agent-teams-workforce:documentation', { contract, green: green.artifact })

// Settle the parallel documentation track before any early failure return, so a
// failed run never leaves docTrack as an unhandled rejection or orphaned work.
async function failAfterDoc(stage, detail) {
  await Promise.allSettled([docTrack])
  return { ok: false, stage, spec: spec.id, detail }
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
    'Coverage met',
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
  phaseFn: (feedback) => workflow('agent-teams-workforce:adversarial', { contract, green: green.artifact, feedback }),
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
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:deploy', { contract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-to-dev', spec: spec.id, detail: deployReady }

return {
  ok: true,
  spec: spec.id,
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
}
return result
