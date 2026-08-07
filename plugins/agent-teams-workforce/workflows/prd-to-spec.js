export const meta = {
  name: 'prd-to-spec',
  description:
    'Composite — drives a request (or an existing PRD) all the way to an emitted, WSJF-scored Beads task set. Stitches the leaf minis (optional PRD creation, PRD validation, architecture, TRD authoring, spec authoring, task decomposition) behind independent gates: G1 PRD validation, G2 constitutional architecture, G2b TRD, G3 spec, G4 task decomposition. The script owns loop (retry-in-phase) and escalate (upstream) control flow; producing minis never judge their own work — the gates do. One level only: this composite calls minis and gates, never another composite.',
  phases: [
    { title: 'PRD Creation', detail: 'optional — only when a raw request is supplied and no PRD exists' },
    { title: 'PRD Validation' },
    { title: 'Architecture' },
    { title: 'TRD Authoring' },
    { title: 'Spec Authoring' },
    { title: 'Task Decomposition' },
    { title: 'Emit Beads' },
  ],
}

// args: {
//   request?: { id?, title?, description?, repoPath?, requestedBy? },  // raw request — triggers optional PRD creation
//   prd?: { id?, title?, body?, content?, path?, repoPath?, acceptanceCriteria?[] }, // existing PRD; skips creation
//   context?: string,             // bounded-context / service-boundary notes for PRD validation
//   brd?: string,                 // BRD objectives text — WITHOUT it the traceability audit has nothing
//                                 // to audit against and every requirement reads as an orphan
//   decision?: { id?, title?, context?, drivers?[], repoPath? }, // the architecture question
//   sad?: { path?, sectionLayout? },  // arc42 SAD location for TRD extraction
//   sadPath?: string,             // arc42 SAD path for the architecture mini
//   spec?: { id?, title?, summary?, service?, repoPath? }, // spec-authoring context
//   accessPatterns?: string[],    // known data access patterns for the data-model spec
//   repoPath?: string,            // owning service/repo for downstream artifacts
//   trdPath?: string,             // where the TRD lives/should be written
//   maxLoops?: number,            // gate retry-in-phase bound (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const MAX_LOOPS = a.maxLoops || 3
const repoPath = a.repoPath || (a.request && a.request.repoPath) || (a.prd && a.prd.repoPath) || null
if (!a.request && !a.prd) log('⚠ neither request nor prd supplied — running in dry/demo mode')

// Decision ledger for over-time mining (see run-ledger-writer). Each instrumented
// mini returns a `ledger` on its artifact; collected here and persisted ONCE in a
// finally so it runs on success, early-return, and throw alike.
const runLedger = []
async function persistRun(outcome) {
  if (!runLedger.length) return
  try {
    await agent(
      `Persist this SDLC workflow run's decision ledger. JSON payload:\n${JSON.stringify({ composite: 'prd-to-spec', bead: null, subject: (a.prd && a.prd.id) || (a.request && a.request.id) || null, outcome, runLedger })}`,
      {
        label: 'ledger:persist',
        phase: 'Emit Beads',
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

// ── PRD Creation (optional) ────────────────────────────────────────────────────
// Only when a raw request is supplied and no PRD already exists. The created PRD
// becomes the input to validation; otherwise the supplied PRD is used directly.
let result
try {
  result = await (async () => {
phase('PRD Creation')
let creation = null
let prd = a.prd || null
if (!prd && a.request) {
  log(`Creating PRD from request ${a.request.id || '(no id)'} — ${a.request.title || ''}`)
  creation = await workflow('agent-teams-workforce:prd-creation', { request: a.request })
  if (!creation || !creation.ok) {
    return { ok: false, stage: 'prd-creation', reason: 'PRD creation did not produce an aligned PRD', detail: creation }
  }
  // Thread the created PRD forward as the validation input.
  prd = {
    id: (creation.prd && creation.prd.title) || (a.request && a.request.id) || null,
    title: creation.prd && creation.prd.title,
    body: creation.prd && creation.prd.prd,
    acceptanceCriteria: creation.prd && creation.prd.acceptanceCriteria,
    repoPath,
  }
} else {
  log(prd ? 'PRD supplied — skipping creation' : 'No request and no PRD — nothing to create')
}
if (!prd) return { ok: false, stage: 'prd-creation', reason: 'no PRD available to validate (supply args.prd or args.request)' }

// ── PRD Validation (Gate 1) ─────────────────────────────────────────────────────
phase('PRD Validation')
const validation = await gateLoop({
  gate: 'G1', phaseName: 'PRD Validation',
  criteria: [
    'No unresolved internal contradictions between requirements that cannot be built around (a genuine WHAT-level conflict)',
    'Every requirement states an actor, a trigger, and an observable user outcome, with acceptance criteria expressed as observable behavior — mechanism/HOW (algorithms, thresholds, schemas, quantified NFRs) is out of scope at PRD altitude and is defined later in the spec',
    'Quality intent the feature implies (privacy, security, accessibility, abuse-resistance) is named where the WHAT requires it, WITHOUT demanding quantified targets, SLOs, or implementation detail',
    'Scope is bounded: each requirement sits in one feature/context and its external dependencies are named (dependency readiness and fallback mechanics are spec/delivery concerns, not PRD defects)',
  ],
  escalateTargets: ['prd-creation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:prd-validation', {
      prd,
      // The BRD must be threaded through explicitly. prd-validation reads args.brd and hands it
      // to the traceability auditor; when it is absent the auditor has no objectives to map to
      // and reports every requirement as an orphan, which reads as a PRD defect but is not one.
      brd: a.brd,
      context: feedback ? `${a.context || ''}\n\nGate feedback:\n${feedback}` : a.context,
    }),
})
if (validation.artifact && validation.artifact.ledger) runLedger.push(validation.artifact.ledger)
if (!validation.ok) return { ok: false, stage: 'prd-validation', detail: validation, prd }
const validatedPrd = (validation.artifact && validation.artifact.validatedPrd) || prd

// ── Architecture (Gate 2 — constitutional) ──────────────────────────────────────
// Consumes the validated PRD; produces the ruled decision + arc42 SAD source feed.
phase('Architecture')
const architecture = await gateLoop({
  gate: 'G2', phaseName: 'Architecture', gateWorkflow: 'agent-teams-workforce:gate-constitutional',
  criteria: [
    'The chosen architecture honors all platform constitutive bans (no Step Functions, no HTTP API v2, no FastAPI/Flask/Django, REST v1 only, Powertools-only, service isolation, SSM-not-CFN-exports, dot-only event naming)',
    'Every significant decision is ruled by the decider and recorded in the SAD/arc42 source feed',
    'No security or data-isolation finding is left open or downgraded',
  ],
  escalateTargets: ['prd-validation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:architecture', {
      decision: a.decision || {
        id: prd.id,
        title: `Architecture for ${prd.title || prd.id || 'PRD'}`,
        context: (validation.artifact && validation.artifact.summary) || prd.body || '',
        repoPath,
      },
      sadPath: a.sadPath,
      feedback,
    }),
})
if (architecture.artifact && architecture.artifact.ledger) runLedger.push(architecture.artifact.ledger)
if (!architecture.ok) return { ok: false, stage: 'architecture', detail: architecture, prd: validatedPrd }
const sadExtract = architecture.artifact && architecture.artifact.sadUpdate

// ── TRD Authoring (Gate 2b) ──────────────────────────────────────────────────────
// Consumes PRD + SAD extract; produces the TRD + bidirectional traceability matrix.
phase('TRD Authoring')
const trdAuthoring = await gateLoop({
  gate: 'G2b', phaseName: 'TRD Authoring',
  criteria: [
    'The TRD derives only from the PRD and the SAD source extract (no invented requirements)',
    'Every PRD requirement maps to a TRD entry and back (bidirectional traceability holds)',
    'The TRD validator and traceability verifier both pass',
  ],
  escalateTargets: ['architecture', 'prd-validation'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:trd-authoring', {
      prd: {
        id: prd.id,
        title: prd.title,
        content: validatedPrd.body || prd.body,
        acceptanceCriteria: prd.acceptanceCriteria,
      },
      sad: a.sad || { path: a.sadPath },
      trdPath: a.trdPath,
      repoPath,
      maxLoops: 2,
      feedback,
    }),
})
if (trdAuthoring.artifact && trdAuthoring.artifact.ledger) runLedger.push(trdAuthoring.artifact.ledger)
if (!trdAuthoring.ok) return { ok: false, stage: 'trd-authoring', detail: trdAuthoring, prd: validatedPrd }
const trd = trdAuthoring.artifact && trdAuthoring.artifact.trd

// ── Spec Authoring (Gate 3) ──────────────────────────────────────────────────────
// Consumes TRD + SAD extract; produces API/data/event/error specs + AC + DoD.
phase('Spec Authoring')
const specAuthoring = await gateLoop({
  gate: 'G3', phaseName: 'Spec Authoring',
  criteria: [
    'API/data-model/event/error specs are internally consistent and spec-first (OpenAPI before handlers)',
    'Each spec passed its independent checker; deadlocks were ruled by the spec-decider',
    'Acceptance criteria and Definition of Done are present and testable',
    'Event names are dot-form and schemas validate',
  ],
  escalateTargets: ['trd-authoring', 'architecture'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:spec-authoring', {
      spec: a.spec || {
        id: prd.id,
        title: prd.title,
        summary: (trdAuthoring.artifact && trdAuthoring.artifact.trd && trdAuthoring.artifact.trd.summary) || prd.body || '',
        service: a.spec && a.spec.service,
        repoPath,
      },
      trd,
      accessPatterns: a.accessPatterns,
      maxLoops: 2,
      constraints: feedback ? [feedback] : undefined,
    }),
})
if (specAuthoring.artifact && specAuthoring.artifact.ledger) runLedger.push(specAuthoring.artifact.ledger)
if (!specAuthoring.ok) return { ok: false, stage: 'spec-authoring', detail: specAuthoring, prd: validatedPrd }
const specSet = specAuthoring.artifact

// ── Task Decomposition (Gate 4) ──────────────────────────────────────────────────
// Consumes the specs; produces a sized, sequenced (DAG), WSJF-scored bead set.
phase('Task Decomposition')
const decomposition = await gateLoop({
  gate: 'G4', phaseName: 'Task Decomposition',
  criteria: [
    'Tasks are atomic and each traces to a spec element',
    'The dependency DAG is acyclic and sequencing is valid',
    'Every task is WSJF-scored and the scoring passed independent review',
    'Beads format validates for every emitted task',
  ],
  escalateTargets: ['spec-authoring'],
  phaseFn: (feedback) =>
    workflow('agent-teams-workforce:task-decomposition', {
      spec: {
        id: prd.id,
        title: prd.title,
        description:
          (specSet && specSet.apiSpec && specSet.apiSpec.summary) ||
          (trd && trd.summary) ||
          prd.body ||
          '',
        source: feedback ? `spec-authoring output (gate feedback: ${feedback})` : 'spec-authoring output',
        repoPath,
      },
      maxScoringPasses: 2,
    }),
})
if (decomposition.artifact && decomposition.artifact.ledger) runLedger.push(decomposition.artifact.ledger)
if (!decomposition.ok) return { ok: false, stage: 'task-decomposition', detail: decomposition, prd: validatedPrd }

// ── Emit Beads ───────────────────────────────────────────────────────────────────
// The validated, sequenced, scored bead set is ready for `bd` emission from the main
// repo path. This composite surfaces the set; it does not write to .beads itself
// (never from a worktree/runtime context).
phase('Emit Beads')
const beadSet = (decomposition.artifact && decomposition.artifact.beadSet) || []
log(`Task set READY: ${beadSet.length} Beads-valid task(s), sequenced and WSJF-scored. Emit via bd from the main repo path.`)

return {
  ok: true,
  prd: validatedPrd,
  stagesComplete: [
    creation ? 'prd-creation' : 'prd-supplied',
    'prd-validation',
    'architecture',
    'trd-authoring',
    'spec-authoring',
    'task-decomposition',
    'emit-beads',
  ],
  note: 'PRD validated, architecture ruled into the SAD, TRD + specs authored, tasks decomposed/sequenced/WSJF-scored and Beads-format valid. Emit the bead set via bd from the main repo path — this composite does not write to .beads.',
  beadSet,
  results: {
    creation,
    validation: validation.artifact,
    architecture: architecture.artifact,
    trdAuthoring: trdAuthoring.artifact,
    specAuthoring: specAuthoring.artifact,
    decomposition: decomposition.artifact,
  },
}
  })()
} finally {
  await persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
}
return result
