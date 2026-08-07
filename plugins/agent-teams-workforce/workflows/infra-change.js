export const meta = {
  name: 'infra-change',
  description:
    'Composite — provisions or changes infrastructure. Stitches the infra-intent front-end onto a TRIMMED shared build-and-ship tail (Red, Green, Integration, Adversarial, Deploy) via mini workflows, with an independent gate between phases and Documentation as a parallel track. The Refactor phase is omitted on the infra path. Adversarial runs a TRIMMED lane (infra-security + dependency-CVE + data-exposure only) and is optional/skipped by default. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing agents never judge their own work. Deploy DEPLOYS TO DEV and smoke-checks the deployed endpoints — that is how code reaches AWS and is not human-gated; only outward-facing qa/prod rollout is.',
  phases: [
    { title: 'Infra Intent' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Integration' },
    { title: 'Adversarial' },
    { title: 'Deploy-to-dev' },
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

// Every adjudication goes to the ledger. Without the verdict and its per-criterion
// evidence, a run that stops at a gate records only `failed:<phase>` — which cannot
// distinguish a genuine defect from an over-strict criterion or a loop exhaustion.
// Module-scoped here (not nested in gateLoop) because this pipeline also has a
// standalone G1 gate call that must be recorded the same way.
function recordGate(gate, phaseName, attempt, verdict, extra) {
  return runLedger.push({
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
}

// Run a phase, judge it at an INDEPENDENT gate, apply the verdict.
async function gateLoop({ gate, phaseName, criteria, escalateTargets, phaseFn, gateWorkflow, initialFeedback }) {
  // Seed EVERY attempt with findings already known from a previous run. Without this a
  // re-dispatch after a gate failure starts blind and must spend a full expensive attempt
  // rediscovering what the prior gate already proved — which on infra-intent is the single
  // costliest thing this pipeline does. The seed is a persistent channel, not an initial
  // value: a later gate verdict replaces only the per-attempt gate feedback, never the seed.
  const seed = initialFeedback || ''
  let gateFeedback = ''
  let artifact
  for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
    const feedback = [seed, gateFeedback].filter(Boolean).join('\n')
    artifact = await phaseFn(feedback)
    const verdict = await workflow(gateWorkflow || 'agent-teams-workforce:gate-enforce', {
      gate, phaseName, criteria, artifact, escalateTargets,
    })
    if (!verdict) {
      recordGate(gate, phaseName, attempt, null, { terminal: 'no-verdict' })
      return { ok: false, reason: `gate ${gate} returned no verdict`, artifact }
    }
    recordGate(gate, phaseName, attempt, verdict)
    if (verdict.verdict === 'pass') {
      log(`Gate ${gate} (${phaseName}): PASS${verdict.flags && verdict.flags.length ? ` — flags: ${verdict.flags.join('; ')}` : ''}`)
      return { ok: true, artifact, verdict }
    }
    if (verdict.verdict === 'escalate') {
      log(`Gate ${gate} (${phaseName}): ESCALATE -> ${verdict.escalateTo || 'upstream'}`)
      return { ok: false, escalate: verdict.escalateTo || 'upstream', artifact, verdict }
    }
    log(`Gate ${gate} (${phaseName}): LOOP ${attempt}/${MAX_LOOPS} — ${verdict.feedback}`)
    gateFeedback = verdict.feedback || ''
  }
  recordGate(gate, phaseName, MAX_LOOPS, null, { verdict: 'loop-exhausted', terminal: 'loop-exhausted' })
  // Carry the last-authored artifact like every other non-ok exit does — loop exhaustion
  // is exactly where the caller most needs the final intent for diagnosis.
  return { ok: false, reason: `gate ${gate} exceeded ${MAX_LOOPS} loops`, loopExhausted: true, artifact }
}

// ── Front-end: infrastructure provisioning intent ───────────────────────────────
let result
try {
  result = await (async () => {
phase('Infra Intent')
log(`Infra change ${bead.id || '(no id)'} — ${bead.title || ''}`)
// ── Gate 1: Infra Intent (provisioning contract is concrete + fresh + clean) ─────
// G1 USED TO BE A STANDALONE GATE THAT COULD NOT LOOP. It called gate-enforce once and
// returned on anything but 'pass' — so a verdict of 'loop', which means "retry this phase
// with my feedback", ended the run instead. This is the same defect class as ssbd-wmtw
// (escalation as a labelled exit rather than control flow), which was repaired for the
// Red/Green pair but never here.
// It is expensive precisely because infra-intent is expensive. On ssbd-w1r9 the gate
// returned 'loop' with a detailed, reproducible feedback packet naming exactly what the
// maker had to change — and the run died anyway, 486k subagent tokens spent, the feedback
// salvageable only by hand. Route it through gateLoop so the maker re-authors against the
// gate's own findings, bounded by MAX_LOOPS.
const g1Loop = await gateLoop({
  gate: 'G1',
  phaseName: 'Infra Intent',
  criteria: [
    'Provisioning intent is concrete and CDK-expressible (S3 versioning+SSE-S3 where buckets exist, no banned constructs)',
    'Referenced ADRs are current and no dependency change invalidates the intent',
    'Security and cost reviewers raised no open blocking finding',
  ],
  escalateTargets: ['infra-intent'],
  initialFeedback: a.priorFindings || '',
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:infra-intent', {
      change: { id: bead.id, title: bead.title, description: bead.description, repoPath: bead.repoPath },
      adrs,
      feedback,
    }),
})
if (!g1Loop.ok) {
  return { ok: false, stage: 'infra-intent', bead: bead.id, gate: 'G1', detail: g1Loop, intent: g1Loop.artifact }
}
const intent = g1Loop.artifact
if (!intent) return { ok: false, stage: 'infra-intent', reason: 'infra-intent produced nothing' }

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
  phaseFn: (feedback) => workflow('agent-teams-workforce:tdd-red', { contract: tailContract, feedback }),
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
    workflow('agent-teams-workforce:tdd-green', { contract: tailContract, red: red.artifact, implementer: 'cdk-stack-author', feedback }),
})
if (green.artifact && green.artifact.ledger) runLedger.push(green.artifact.ledger)
if (!green.ok) return { ok: false, stage: 'green', bead: bead.id, detail: green }

// Documentation runs ALONGSIDE the rest of the tail (started after Green, awaited before deploy).
const docTrack = workflow('agent-teams-workforce:documentation', { contract: tailContract, green: green.artifact })

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
  phaseFn: (feedback) => workflow('agent-teams-workforce:integration', { contract: tailContract, green: green.artifact, feedback }),
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
    gate: 'G4', phaseName: 'Adversarial Validation', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
    criteria: [
      'No open constitutive findings (no infra misconfiguration, unpatched CVE, or data exposure)',
      'All confirmed findings adjudicated',
    ],
    escalateTargets: ['green', 'infra-intent'],
    phaseFn: (feedback) =>
      workflow('agent-teams-workforce:adversarial', {
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

// Documentation must be current before the deploy.
const docCurrency = await docTrack
if (docCurrency && docCurrency.ledger) runLedger.push(docCurrency.ledger)

// ── Deploy to dev (Gate 5) — dev IS deployed; only qa/prod is human-gated ───────
// Deploying to dev is how infrastructure reaches AWS and is part of the
// development lifecycle, not a release. A stack cannot be validated against AWS
// until it is IN AWS. Outward-facing qa/prod rollout never happens here.
phase('Deploy-to-dev')
const deployReady = await gateLoop({
  gate: 'G5', phaseName: 'Deploy to dev',
  criteria: [
    'CDK synth valid, no unresolved drift',
    'Smoke tests present',
    'Deployed to the dev environment',
    'Smoke tests pass against the deployed dev endpoints',
  ],
  escalateTargets: ['integration', 'green'],
  phaseFn: (feedback) => workflow('agent-teams-workforce:deploy', { contract: tailContract, green: green.artifact, docCurrency, feedback }),
})
if (deployReady.artifact && deployReady.artifact.ledger) runLedger.push(deployReady.artifact.ledger)
if (!deployReady.ok) return { ok: false, stage: 'deploy-to-dev', bead: bead.id, detail: deployReady }

return {
  ok: true,
  bead: bead.id,
  stagesComplete: [
    'infra-intent',
    'red',
    'green',
    'integration',
    ...(RUN_ADVERSARIAL ? ['adversarial'] : []),
    'deploy-to-dev',
  ],
  adversarialRun: RUN_ADVERSARIAL,
  note: 'DEPLOYED TO DEV and smoke-checked against the deployed endpoints. Outward-facing qa/prod rollout is a separate human-gated action and did not happen here. Refactor phase is omitted on the infra path.',
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
