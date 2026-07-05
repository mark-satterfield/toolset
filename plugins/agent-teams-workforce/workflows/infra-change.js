export const meta = {
  name: 'infra-change',
  description:
    'Composite — provisions or changes infrastructure. Stitches the infra-intent front-end onto a TRIMMED shared build-and-ship tail (Red, Green, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The Refactor phase is omitted on the infra path. Adversarial runs a TRIMMED lane (infra-security + dependency-CVE + data-exposure only) and is optional/skipped by default. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy stops at readiness — production rollout is a separate human-gated action.',
  phases: [
    { title: 'Infra Intent' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-readiness' },
  ],
}

// args: {
//   bead: { id, title, description, repoPath },  // the infra change bead
//   adrs?: string[],                              // ADR ids/paths the intent relies on
//   runAdversarial?: boolean,                     // run the TRIMMED adversarial lane (default false)
//   maxLoops?: number,                            // gate retry budget per phase (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const adrs = Array.isArray(a.adrs) ? a.adrs : []
const RUN_ADVERSARIAL = a.runAdversarial === true
const MAX_LOOPS = a.maxLoops || 3
if (!bead.id) log('⚠ no bead.id supplied — running in dry/demo mode')

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'infra-change', bead: { id: bead.id || null, title: bead.title || null }, outcome, runLedger })}`,
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

// ── Front-end: infrastructure provisioning intent ───────────────────────────────
let result
try {
  result = await (async () => {
phase('Infra Intent')
log(`Infra change ${bead.id || '(no id)'} — ${bead.title || ''}`)
const intent = await workflow('infra-intent', {
  change: { id: bead.id, title: bead.title, description: bead.description, repoPath: bead.repoPath },
  adrs,
})
if (!intent) return { ok: false, stage: 'infra-intent', reason: 'infra-intent produced nothing' }

// ── Gate 1: Infra Intent (provisioning contract is concrete + fresh + clean) ─────
const g1 = await workflow('gate-enforce', {
  gate: 'G1',
  phaseName: 'Infra Intent',
  criteria: [
    'Provisioning intent is concrete and CDK-expressible (S3 versioning+SSE-S3 where buckets exist, no banned constructs)',
    'Referenced ADRs are current and no dependency change invalidates the intent',
    'Security and cost reviewers raised no open blocking finding',
  ],
  artifact: intent,
  escalateTargets: ['infra-intent'],
})
if (!g1 || g1.verdict !== 'pass') {
  return { ok: false, stage: 'infra-intent', bead: bead.id, gate: 'G1', detail: g1, intent }
}

// Tail-facing contract: carries the repo + a change descriptor the tail prompts
// render, plus the provisioning intent and the infra assertion the Red test encodes.
const tailContract = {
  bead: { id: bead.id, title: bead.title || 'infra change' },
  repoPath: bead.repoPath || null,
  affectedStacks: intent.affectedStacks || [],
  provisioningIntent: intent.provisioningIntent || null,
  acceptanceCriteria: [
    {
      given: `the provisioning intent for ${bead.title || 'this infra change'} on stacks ${(intent.affectedStacks || []).join(', ') || '(affected stacks)'}`,
      when: 'cdk synth runs against the changed stacks',
      then: 'the synthesized template asserts the intended resources/properties (incl. S3 versioning + SSE-S3 where buckets exist) and no banned constructs are present',
    },
  ],
}

// ── Red (Gate 2a) — author the FAILING infra synth/policy assertion ──────────────
phase('Red')
const red = await gateLoop({
  gate: '2a', phaseName: 'TDD Red',
  criteria: [
    'A failing infra test/synth assertion encodes the provisioning intent',
    'The assertion fails for the intended reason (the intent is not yet expressed in CDK)',
    'No production CDK code changed yet — tests/assertions only',
  ],
  escalateTargets: ['infra-intent'],
  phaseFn: (feedback) => workflow('tdd-red', { contract: tailContract, feedback }),
})
if (red.artifact && red.artifact.ledger) runLedger.push(red.artifact.ledger)
if (!red.ok) return { ok: false, stage: 'red', bead: bead.id, detail: red }

// ── Green (Gate 2b) — make synth/test pass via the CDK stack author ──────────────
phase('Green')
const green = await gateLoop({
  gate: 'G2b', phaseName: 'TDD Green',
  criteria: [
    'The previously-failing infra test/synth assertion now passes',
    'No other stacks regressed',
    'cdk synth succeeds with the change',
  ],
  escalateTargets: ['infra-intent', 'red'],
  phaseFn: (feedback) =>
    workflow('tdd-green', { contract: tailContract, red: red.artifact, implementer: 'cdk-stack-author', feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', bead: bead.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail (started after Green, awaited before deploy).
const docTrack = workflow('documentation', { contract: tailContract, green: green.artifact })

// Settle the parallel documentation track before any early failure return, so a
// failed run never leaves docTrack as an unhandled rejection or orphaned work.
async function failAfterDoc(stage, detail) {
  await Promise.allSettled([docTrack])
  return { ok: false, stage, bead: bead.id, detail }
}

// ── Integration (Gate 3) — infra contract/drift checks across stacks ─────────────
phase('Integration')
const integration = await gateLoop({
  gate: 'G3', phaseName: 'Integration Testing',
  criteria: [
    'Infra integration/contract checks pass',
    'No drift introduced across stacks',
    'Cross-stack SSM references resolve (no CloudFormation exports)',
  ],
  escalateTargets: ['green', 'red', 'infra-intent'],
  phaseFn: (feedback) => workflow('integration', { contract: tailContract, green: green.artifact, feedback }),
})
if (integration.artifact && integration.artifact.ledger) runLedger.push(integration.artifact.ledger)
if (!integration.ok) return await failAfterDoc('integration', integration)

// ── Adversarial (Gate 4 — constitutional) — TRIMMED lane, optional ───────────────
// Trimmed to infra-relevant attack classes; full attack lanes are skipped by
// default. Security findings are constitutive — judged at a constitutional gate.
let adversarial = { skipped: true }
if (RUN_ADVERSARIAL) {
  phase('Adversarial')
  const adv = await gateLoop({
    gate: 'G4', phaseName: 'Adversarial Validation', gateWorkflow: 'gate-constitutional',
    criteria: [
      'No open constitutive findings (no infra misconfiguration, unpatched CVE, or data exposure)',
      'All confirmed findings adjudicated',
    ],
    escalateTargets: ['green', 'infra-intent'],
    phaseFn: (feedback) =>
      workflow('adversarial', {
        contract: tailContract,
        green: green.artifact,
        trimmedScope: ['infrastructure-security-scanner', 'dependency-cve-auditor', 'data-exposure-scanner'],
        feedback,
      }),
  })
  if (!adv.ok) return await failAfterDoc('adversarial', adv)
  adversarial = adv.artifact
} else {
  log('Adversarial lane skipped (runAdversarial=false) — trimmed infra path')
}

// Documentation must be current before readiness.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy readiness (Gate 5) — NO autonomous prod rollout ───────────────────────
phase('Deploy-readiness')
const deployReady = await gateLoop({
  gate: 'G5', phaseName: 'Deployment readiness',
  criteria: [
    'CDK synth valid, no unresolved drift',
    'Smoke tests present',
    'Documentation current',
    'Readiness review is go',
  ],
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('deploy', { contract: tailContract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-readiness', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: [
    'infra-intent',
    'red',
    'green',
    'integration',
    ...(RUN_ADVERSARIAL ? ['adversarial'] : []),
    'deploy-readiness',
  ],
  adversarialRun: RUN_ADVERSARIAL,
  note: 'READY for deployment. Production rollout is a separate human-gated action — this composite does not deploy to prod. Refactor phase is omitted on the infra path.',
  contract: tailContract,
  results: {
    intent,
    red: red.artifact,
    green: green.artifact,
    integration: integration.artifact,
    adversarial,
    deployReadiness: deployReady.artifact,
    documentation: docCurrency,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
}
return result
