export const meta = {
  name: 'bug-fix',
  description:
    'Composite — fixes a bug bead. Stitches the bug-triage front-end onto the shared build-and-ship tail (Red, Green, Refactor, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy stops at readiness — production rollout is a separate human-gated action.',
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
  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    const artifact = await phaseFn(feedback)
    const verdict = await workflow(gateWorkflow || 'gate-enforce', {
      gate, phaseName, criteria, artifact, escalateTargets,
    })
    if (!verdict) return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
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
  return { ok: false, reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`, loopExhausted: true }
}

// ── Front-end: triage ─────────────────────────────────────────────────────────
let result
try {
  result = await (async () => {
phase('Triage')
log(`Triaging ${bead.id || '(no id)'} — ${bead.title || ''}`)
const contract = await workflow('bug-triage', { bead })
if (!contract) return { ok: false, stage: 'triage', reason: 'triage produced nothing' }

// ── Red (Gate 2a) ─────────────────────────────────────────────────────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: ['A failing test reproduces the defect', 'The test fails for the intended reason', 'No production code changed yet'],
  escalateTargets: ['triage'],
  phaseFn: (feedback) => workflow('tdd-red', { contract, feedback }),
})
if (red.artifact && red.artifact.ledger) runLedger.push(red.artifact.ledger)
if (!red.ok) return { ok: false, stage: 'red', bead: bead.id, detail: red }

// ── Green (Gate 2b) ───────────────────────────────────────────────────────────
phase('Green')
const green = await gateLoop({
  gate: '2b', phaseName: 'TDD Green',
  criteria: ['The previously-failing test now passes', 'No other tests regressed', 'The change is minimal and the test was not weakened'],
  escalateTargets: ['triage', 'red'],
  phaseFn: (feedback) => workflow('tdd-green', { contract, red: red.artifact, implementer: a.implementer, feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', bead: bead.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail (started, awaited before deploy).
const docTrack = workflow('documentation', { contract, green: green.artifact })

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
  phaseFn: (feedback) => workflow('tdd-refactor', { contract, green: green.artifact, feedback }),
})
if (refactor.artifact && refactor.artifact.ledger) runLedger.push(refactor.artifact.ledger)
if (!refactor.ok) return await failAfterDoc('refactor', refactor)

// ── Integration (Gate 3) ──────────────────────────────────────────────────────
phase('Integration')
const integration = await gateLoop({
  gate: '3', phaseName: 'Integration Testing',
  criteria: ['Integration/contract/E2E suites pass', 'Contracts valid across boundaries', 'Coverage met', 'No flaky tests'],
  escalateTargets: ['green', 'red', 'triage'],
  phaseFn: (feedback) => workflow('integration', { contract, green: green.artifact, feedback }),
})
if (integration.artifact && integration.artifact.ledger) runLedger.push(integration.artifact.ledger)
if (!integration.ok) return await failAfterDoc('integration', integration)

// ── Adversarial (Gate 4 — constitutional) ─────────────────────────────────────
phase('Adversarial')
const adversarial = await gateLoop({
  gate: '4', phaseName: 'Adversarial Validation', gateWorkflow: 'gate-constitutional',
  criteria: ['No open constitutive findings (no vulns, injection, auth bypass, or data exposure)', 'All confirmed findings adjudicated'],
  escalateTargets: ['green', 'triage'],
  phaseFn: (feedback) => workflow('adversarial', { contract, green: green.artifact, feedback }),
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
  phaseFn: (feedback) => workflow('deploy', { contract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-readiness', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: ['triage', 'red', 'green', 'refactor', 'integration', 'adversarial', 'deploy-readiness'],
  note: 'READY for deployment. Production rollout is a separate human-gated action — this composite does not deploy to prod.',
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
