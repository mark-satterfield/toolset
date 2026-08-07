// The architecture panel is sized to the decision, not run at full width by reflex.
//
// It dispatched 23 agents unconditionally — five analysts, six challengers, a
// decider, authors, a SAD maintainer, a conformance reviewer — whether the
// question was genuinely open or already answered by an accepted ADR. For a
// routine variation on a settled pattern that is the single most expensive thing
// the pipeline does, and the phase most likely to make an operator abandon it.
//
// Scaling it introduces one risk worth guarding against: that "run fewer agents"
// quietly becomes "skip the independent check". These tests pin both halves —
// the panel shrinks, and segregation of duties does not.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const architecture = path.resolve(HERE, '..', '..', 'workflows', 'architecture.js')

const ALWAYS = [
  'agent-teams-workforce:architecture-decider',
  'agent-teams-workforce:sad-maintainer',
  'agent-teams-workforce:sad-conformance-reviewer',
]

/** Runs the mini, scripting the triage verdict and approving everything else. */
async function run({ args = {}, triage }) {
  return runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'chassis or not', context: 'c' }, ...args },
    workflowImpl: () => ({ verdict: 'pass', criteria: [], flags: [] }),
    agentImpl: (call) => {
      if (call.label === 'triage:classify') return triage
      if (call.label === 'sad:conformance') return { verdict: 'pass', conformant: true, findings: [] }
      return { summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r', verdict: 'pass', conformant: true }
    },
  })
}

function agentTypesUsed(calls) {
  return calls.filter((c) => c.kind === 'agent').map((c) => (c.opts && c.opts.agentType) || null)
}

test('a SETTLED question with a VERIFIED citation skips the analyst fan-out and the challenge wave', async () => {
  const { calls } = await runVerified({
    triage: {
      settled: true,
      rationale: 'ADR-014 already settles this',
      relevantDecisions: ['ADR-014'],
      dimensions: [],
    },
    verification: {
      confirmed: true,
      perReference: [{ reference: 'ADR-014', exists: true, current: true, onPoint: true }],
      reason: 'accepted, unsuperseded, on point',
    },
  })

  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.ok(
    !labels.some((l) => String(l).startsWith('proposals:')),
    `settled decisions must not re-derive proposals, saw: [${labels.filter((l) => String(l).startsWith('proposals:')).join(', ')}]`,
  )
  assert.ok(
    !labels.some((l) => String(l).startsWith('challenge:')),
    'settled decisions must not run the challenge wave over proposals that were never made',
  )
})

test('a settled question still reaches the decider and the independent conformance check', async () => {
  const { calls } = await runVerified({
    triage: { settled: true, rationale: 'settled', relevantDecisions: ['ADR-014'], dimensions: [] },
    verification: { confirmed: true, perReference: [], reason: 'ok' },
  })
  const used = agentTypesUsed(calls)
  for (const required of ALWAYS) {
    assert.ok(
      used.includes(required),
      `${required} must run whatever triage ruled — scaling the panel is a cost decision, not a licence to skip the independent check`,
    )
  }
})

test('an OPEN question runs only the dimensions triage named', async () => {
  const { calls } = await run({
    triage: {
      settled: false,
      rationale: 'genuinely open on persistence and cost',
      relevantDecisions: [],
      dimensions: ['persistence', 'cost'],
    },
  })

  const used = agentTypesUsed(calls)
  assert.ok(
    used.includes('agent-teams-workforce:persistence-architecture-specialist'),
    'the named dimensions must actually be analysed',
  )
  assert.ok(
    !used.includes('agent-teams-workforce:security-architecture-designer'),
    'an axis triage did not name must not be dispatched by reflex — that is the whole saving',
  )
})

test('triage classifies but never decides', async () => {
  const { calls } = await runVerified({
    triage: { settled: true, rationale: 'settled', relevantDecisions: ['ADR-1'], dimensions: [] },
    verification: { confirmed: true, perReference: [], reason: 'ok' },
  })
  const triageCall = calls.find((c) => c.label === 'triage:classify')
  assert.ok(triageCall, 'a triage step must run')
  assert.notEqual(
    triageCall.opts.agentType,
    'agent-teams-workforce:architecture-decider',
    'the agent that sizes the panel must not also be the one that rules — that is self-approval',
  )
})

test('a triage failure widens the panel rather than narrowing it', async () => {
  const { calls } = await run({ triage: null })
  const used = agentTypesUsed(calls)
  // Failing open matters: a triage error must never be indistinguishable from
  // "nothing to analyse", which would silently ship an unexamined decision.
  assert.ok(
    used.includes('agent-teams-workforce:security-architecture-designer'),
    'when triage cannot classify, the full panel must run — fail open, not quiet',
  )
})

test('forceFullPanel skips triage and runs everything', async () => {
  const { calls } = await runVerified({
    args: { forceFullPanel: true },
    triage: { settled: true, rationale: 'would have skipped', relevantDecisions: [], dimensions: [] },
    verification: { confirmed: true, perReference: [], reason: 'ok' },
  })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.ok(
    !labels.includes('triage:classify'),
    'an explicit full-panel request must not spend an agent asking whether to scale',
  )
  assert.ok(
    labels.some((l) => String(l).startsWith('proposals:')),
    'a caller who knows the decision is contested must be able to say so and get the full panel',
  )
})

// ── "Already decided" is a claim, and a claim cannot skip work ────────────────
//
// This process was previously circumvented by a bead note reading "Decision
// already made" — untrue, and sufficient. Triage reintroduced the same shape:
// an agent asserting `settled: true` skipped five analysts and six challengers.
// The assertion must now survive an independent check before it buys anything.

/** Runs with a scripted triage verdict AND a scripted citation verification. */
async function runVerified({ triage, verification, args = {} }) {
  return runWorkflowScript(architecture, {
    args: { decision: { id: 'AD-1', title: 'chassis or not', context: 'c' }, ...args },
    workflowImpl: () => ({ verdict: 'pass', criteria: [], flags: [] }),
    agentImpl: (call) => {
      if (call.label === 'triage:classify') return triage
      if (call.label === 'triage:verify-citations') return verification
      return { summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r', verdict: 'pass', conformant: true }
    },
  })
}

const SETTLED_CLAIM = {
  settled: true,
  rationale: 'Decision already made',
  relevantDecisions: ['ADR-014'],
  dimensions: [],
}

test('a settled claim whose citation FAILS verification runs the full panel', async () => {
  const { calls } = await runVerified({
    triage: SETTLED_CLAIM,
    verification: {
      confirmed: false,
      perReference: [{ reference: 'ADR-014', exists: false, current: false, onPoint: false }],
      reason: 'ADR-014 does not exist',
    },
  })
  const used = agentTypesUsed(calls)
  assert.ok(
    used.includes('agent-teams-workforce:security-architecture-designer'),
    'a citation that does not check out must not skip the analysis — "already decided" is exactly how this was circumvented before',
  )
})

test('a settled claim citing NOTHING never reaches verification and runs the full panel', async () => {
  const { calls } = await runVerified({
    triage: { ...SETTLED_CLAIM, relevantDecisions: [] },
    verification: { confirmed: true, perReference: [], reason: 'should never be asked' },
  })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.ok(
    !labels.includes('triage:verify-citations'),
    'there is nothing to verify, so no agent should be spent asking',
  )
  assert.ok(
    agentTypesUsed(calls).includes('agent-teams-workforce:security-architecture-designer'),
    'an unevidenced claim must fail open to the full panel',
  )
})

test('a verifier that returns nothing is treated as failure, not as consent', async () => {
  const { calls } = await runVerified({ triage: SETTLED_CLAIM, verification: null })
  assert.ok(
    agentTypesUsed(calls).includes('agent-teams-workforce:security-architecture-designer'),
    'silence from the verifier must widen the panel — a missing verdict is not a passing one',
  )
})

test('only a VERIFIED citation skips the panel', async () => {
  const { calls } = await runVerified({
    triage: SETTLED_CLAIM,
    verification: {
      confirmed: true,
      perReference: [{ reference: 'ADR-014', exists: true, current: true, onPoint: true }],
      reason: 'ADR-014 is accepted, unsuperseded, and answers this question',
    },
  })
  const labels = calls.filter((c) => c.kind === 'agent').map((c) => c.label)
  assert.ok(!labels.some((l) => String(l).startsWith('proposals:')), 'a verified citation may skip the fan-out')
  for (const required of ALWAYS) {
    assert.ok(agentTypesUsed(calls).includes(required), `${required} must still run`)
  }
})

test('the verifier is a different agent from triage', async () => {
  const { calls } = await runVerified({
    triage: SETTLED_CLAIM,
    verification: { confirmed: true, perReference: [], reason: 'ok' },
  })
  const triageCall = calls.find((c) => c.label === 'triage:classify')
  const verifyCall = calls.find((c) => c.label === 'triage:verify-citations')
  assert.ok(verifyCall, 'a settled claim must be independently verified')
  assert.notEqual(
    verifyCall.opts.agentType,
    triageCall.opts.agentType,
    'the agent that made the claim must not be the one that confirms it',
  )
})
