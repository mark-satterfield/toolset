// ssbd-1xcs D3 — seeded feedback lost after attempt 1 (infra-change.js).
// Encodes acceptance criteria D3-AC1 .. D3-AC5 (numbered AC14-AC18 in the bead).
//
// Defect under test: gateLoop treats initialFeedback (seeded from a.priorFindings)
// as the initial value of a single mutable accumulator. On a G1 'loop' verdict,
// `feedback = verdict.feedback || ''` (infra-change.js:113) replaces the seed
// wholesale, so attempts 2..N re-author with only the latest gate verdict — and
// an empty verdict.feedback erases the seed entirely.
//
// Observation seam: the G1 phaseFn is workflow('agent-teams-workforce:infra-intent',
// { change, adrs, feedback }) — the feedback string handed to each attempt is captured
// from the fake workflow dispatcher.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const INFRA_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', '..', 'workflows', 'infra-change.js'
)

const SEED = 'PRIOR: bucket X lacks SSE-S3'

/**
 * Run infra-change.js with scripted G1 verdicts. The Red gate ('2a') always
 * escalates so the run terminates right after the G1 loop settles.
 * Returns the payloads of every infra-intent dispatch (one per G1 attempt).
 */
async function runInfra({ priorFindings, g1Verdicts, intentReturns } = {}) {
  const intentPayloads = []
  let g1Count = 0
  const { result } = await runWorkflowScript(INFRA_JS, {
    args: {
      // Pinned explicitly: this exercises loop MECHANICS (seed persistence,
      // artifact carrying), not the default budget, which is now 2.
      maxLoops: 3,
      bead: { id: 'ssbd-fixture', title: 'encrypt bucket', description: 'd', repoPath: '/tmp/fixture' },
      ...(priorFindings !== undefined ? { priorFindings } : {}),
    },
    agentImpl: () => ({ written: true }), // ledger:persist
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:infra-intent') {
        intentPayloads.push(call.payload)
        const i = intentPayloads.length - 1
        if (intentReturns) return intentReturns[Math.min(i, intentReturns.length - 1)]
        return { provisioningIntent: 'P', affectedStacks: ['S1'] }
      }
      if (call.name === 'agent-teams-workforce:gate-enforce') {
        if (call.payload.gate === 'G1') {
          const v = g1Verdicts && g1Verdicts[g1Count] !== undefined ? g1Verdicts[g1Count] : { verdict: 'pass' }
          g1Count += 1
          return v
        }
        // Terminate the tail at the Red gate.
        return { verdict: 'escalate', escalateTo: 'infra-intent' }
      }
      if (call.name === 'agent-teams-workforce:tdd-red') return { testFiles: ['t'], redConfirmed: true }
      return {}
    },
  })
  return { result, intentPayloads }
}

// ─── D3-AC1 (AC14) — seed survives one loop ───────────────────────────────────
test('D3-AC1: after one G1 loop, attempt 2 receives BOTH the seeded prior findings AND the gate feedback', async () => {
  const { intentPayloads } = await runInfra({
    priorFindings: SEED,
    g1Verdicts: [
      { verdict: 'loop', feedback: 'GATE: name the affected stack' },
      { verdict: 'pass' },
    ],
  })
  assert.equal(intentPayloads.length, 2, 'G1 must run exactly two attempts in this fixture')
  const fb2 = String(intentPayloads[1].feedback)
  assert.ok(
    fb2.includes(SEED),
    `attempt-2 feedback must still contain the seed '${SEED}' — the loop currently replaces it wholesale; got: ${JSON.stringify(fb2)}`
  )
  assert.ok(
    fb2.includes('GATE: name the affected stack'),
    `attempt-2 feedback must also contain the gate feedback; got: ${JSON.stringify(fb2)}`
  )
})

// ─── D3-AC2 (AC15) — seed survives to the last attempt ────────────────────────
test('D3-AC2: after two G1 loops, attempt 3 still receives the seed alongside the latest gate feedback', async () => {
  const { intentPayloads } = await runInfra({
    priorFindings: SEED,
    g1Verdicts: [
      { verdict: 'loop', feedback: 'GATE-1' },
      { verdict: 'loop', feedback: 'GATE-2' },
      { verdict: 'pass' },
    ],
  })
  assert.equal(intentPayloads.length, 3, 'G1 must run exactly three attempts in this fixture (MAX_LOOPS defaults to 3)')
  const fb3 = String(intentPayloads[2].feedback)
  assert.ok(fb3.includes(SEED), `attempt-3 feedback must contain the seed; got: ${JSON.stringify(fb3)}`)
  assert.ok(fb3.includes('GATE-2'), `attempt-3 feedback must contain the latest gate feedback 'GATE-2'; got: ${JSON.stringify(fb3)}`)
})

// ─── D3-AC3 (AC16) — empty gate feedback does not erase the seed ──────────────
test('D3-AC3: a loop verdict with undefined feedback must not erase the seed (and must not print "undefined")', async () => {
  const { intentPayloads } = await runInfra({
    priorFindings: SEED,
    g1Verdicts: [
      { verdict: 'loop' }, // feedback undefined
      { verdict: 'pass' },
    ],
  })
  assert.equal(intentPayloads.length, 2)
  const fb2 = String(intentPayloads[1].feedback)
  assert.ok(
    fb2.includes(SEED),
    `attempt-2 feedback must still contain the seed after an empty loop verdict — it is currently replaced with ''; got: ${JSON.stringify(fb2)}`
  )
  assert.ok(!fb2.includes('undefined'), 'feedback must not contain the literal "undefined"')
})

// ─── D3-AC4 (AC17) — no seed means no artifacts ───────────────────────────────
test('D3-AC4: with an empty seed, attempt-2 feedback is exactly the gate feedback — no separators, no empty section headers', async () => {
  const { intentPayloads } = await runInfra({
    priorFindings: '',
    g1Verdicts: [
      { verdict: 'loop', feedback: 'GATE-1' },
      { verdict: 'pass' },
    ],
  })
  assert.equal(intentPayloads.length, 2)
  assert.equal(
    intentPayloads[1].feedback,
    'GATE-1',
    'attempt-2 feedback must be exactly "GATE-1" when there is no seed — the merge must not add leading/trailing separator text or empty-section headers'
  )
})

// ─── D3-AC5 (AC18) — seed reaches attempt 1 unchanged ─────────────────────────
test('D3-AC5: the seed reaches attempt 1 (regression guard for the existing seeding path)', async () => {
  const { intentPayloads } = await runInfra({
    priorFindings: SEED,
    g1Verdicts: [{ verdict: 'pass' }],
  })
  assert.ok(intentPayloads.length >= 1)
  assert.ok(
    String(intentPayloads[0].feedback).includes(SEED),
    `attempt-1 feedback must contain the seed; got: ${JSON.stringify(intentPayloads[0].feedback)}`
  )
})
