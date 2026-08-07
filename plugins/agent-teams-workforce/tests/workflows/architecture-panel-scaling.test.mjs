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
      if (call.label === 'sad:conformance') return { conformant: true, findings: [] }
      return { summary: 's', findings: [], options: [], ruling: 'accept', rationale: 'r', conformant: true }
    },
  })
}

function agentTypesUsed(calls) {
  return calls.filter((c) => c.kind === 'agent').map((c) => (c.opts && c.opts.agentType) || null)
}

test('a SETTLED question skips the analyst fan-out and the challenge wave', async () => {
  const { calls } = await run({
    triage: {
      settled: true,
      rationale: 'ADR-014 already settles this',
      relevantDecisions: ['ADR-014'],
      dimensions: [],
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
  const { calls } = await run({
    triage: { settled: true, rationale: 'settled', relevantDecisions: ['ADR-014'], dimensions: [] },
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
  const { calls } = await run({
    triage: { settled: true, rationale: 'settled', relevantDecisions: ['ADR-1'], dimensions: [] },
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
  const { calls } = await run({
    args: { forceFullPanel: true },
    triage: { settled: true, rationale: 'would have skipped', relevantDecisions: [], dimensions: [] },
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
