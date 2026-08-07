// ssbd-1xcs D4 — `intent: undefined` on G1 loop exhaustion (infra-change.js).
// Encodes acceptance criteria D4-AC1 .. D4-AC4 (numbered AC19-AC22 in the bead).
//
// Defect under test: the loop-exhausted exit at infra-change.js:116 returns
// { ok:false, reason, loopExhausted:true } WITHOUT an `artifact` key, while the
// caller at line 154 returns `intent: g1Loop.artifact` — undefined. The two
// sibling non-ok exits (no-verdict, escalate) both carry `artifact`; the defect
// is specific to the loop-exhausted path, which is exactly where the caller most
// needs the last-authored intent for diagnosis.
//
// Observation seam: the composite's non-ok return exposes the gateLoop result as
// `detail` (line 154: detail: g1Loop), so gateLoop's return shape is asserted there.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const INFRA_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', '..', 'workflows', 'infra-change.js'
)

async function runInfra({ g1Verdicts, intentReturns }) {
  const intentPayloads = []
  let g1Count = 0
  const { result } = await runWorkflowScript(INFRA_JS, {
    args: { bead: { id: 'ssbd-fixture', title: 'encrypt bucket', description: 'd', repoPath: '/tmp/fixture' } },
    agentImpl: () => ({ written: true }), // ledger:persist
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:infra-intent') {
        const i = intentPayloads.length
        intentPayloads.push(call.payload)
        return intentReturns[Math.min(i, intentReturns.length - 1)]
      }
      if (call.name === 'agent-teams-workforce:gate-enforce' && call.payload.gate === 'G1') {
        const v = g1Verdicts[g1Count] !== undefined ? g1Verdicts[g1Count] : { verdict: 'pass' }
        g1Count += 1
        return v
      }
      // Any other gate escalates so a run that unexpectedly passes G1 still terminates fast.
      if (call.name === 'agent-teams-workforce:gate-enforce') return { verdict: 'escalate', escalateTo: 'infra-intent' }
      return {}
    },
  })
  return { result, intentPayloads }
}

const LOOP3 = [
  { verdict: 'loop', feedback: 'F1' },
  { verdict: 'loop', feedback: 'F2' },
  { verdict: 'loop', feedback: 'F3' },
]

// ─── D4-AC1 (AC19) — loop-exhausted carries the artifact ──────────────────────
test('D4-AC1: the loop-exhausted gateLoop result carries `artifact` === the final phaseFn return', async () => {
  const FINAL_INTENT = { provisioningIntent: 'INTENT-N', affectedStacks: ['S1'] }
  const { result } = await runInfra({
    g1Verdicts: LOOP3,
    intentReturns: [
      { provisioningIntent: 'INTENT-1', affectedStacks: ['S1'] },
      { provisioningIntent: 'INTENT-2', affectedStacks: ['S1'] },
      FINAL_INTENT,
    ],
  })

  assert.equal(result.ok, false)
  const d = result.detail
  assert.ok(d, 'the composite must expose the gateLoop result as detail')
  assert.equal(d.ok, false)
  assert.equal(d.loopExhausted, true, 'loopExhausted must be true')
  assert.match(String(d.reason), /exceeded \d+ loops/, 'reason must match /exceeded \\d+ loops/')
  assert.ok(
    Object.prototype.hasOwnProperty.call(d, 'artifact'),
    "the loop-exhausted return must have an own property 'artifact' — it is currently the only exit that drops it"
  )
  assert.equal(
    d.artifact, FINAL_INTENT,
    'artifact must be STRICTLY the object returned by the final phaseFn call (identity, not a copy)'
  )
  assert.equal(d.artifact && d.artifact.provisioningIntent, 'INTENT-N')
})

// ─── D4-AC2 (AC20) — the composite propagates it ──────────────────────────────
test('D4-AC2: the composite non-ok result at infra-intent carries intent === the final authored artifact, not undefined', async () => {
  const FINAL_INTENT = { provisioningIntent: 'INTENT-N', affectedStacks: ['S1'] }
  const { result } = await runInfra({
    g1Verdicts: LOOP3,
    intentReturns: [
      { provisioningIntent: 'INTENT-1', affectedStacks: ['S1'] },
      { provisioningIntent: 'INTENT-2', affectedStacks: ['S1'] },
      FINAL_INTENT,
    ],
  })

  assert.equal(result.stage, 'infra-intent')
  assert.equal(result.gate, 'G1')
  assert.notEqual(result.intent, undefined, 'result.intent must not be undefined on loop exhaustion')
  assert.equal(result.intent, FINAL_INTENT, 'result.intent must be the final authored artifact')
  assert.equal(result.intent && result.intent.provisioningIntent, 'INTENT-N')
})

// ─── D4-AC3 (AC21) — null artifact is explicit, not absent ────────────────────
test('D4-AC3: when the final phaseFn returned null, the loop-exhausted result carries artifact: null as an OWN property', async () => {
  const { result } = await runInfra({
    g1Verdicts: LOOP3,
    intentReturns: [null, null, null],
  })

  const d = result.detail
  assert.ok(d && d.loopExhausted === true, 'fixture must reach the loop-exhausted exit')
  assert.equal(
    Object.prototype.hasOwnProperty.call(d, 'artifact'), true,
    "consumers must be able to distinguish 'phase produced nothing' (artifact: null) from 'the shape omitted the field' (no artifact key)"
  )
  assert.equal(d.artifact, null, 'artifact must be explicitly null')
})

// ─── D4-AC4 (AC22) — sibling exits unchanged (regression guard) ───────────────
test('D4-AC4: the no-verdict and escalate exits still carry artifact === the attempt-1 phaseFn result', async () => {
  // (a) gate returns no verdict on attempt 1
  const A1 = { provisioningIntent: 'A1', affectedStacks: ['S1'] }
  const noVerdict = await runInfra({ g1Verdicts: [null], intentReturns: [A1] })
  const dNo = noVerdict.result.detail
  assert.ok(dNo, 'no-verdict run must expose detail')
  assert.match(String(dNo.reason), /returned no verdict/, 'no-verdict reason must match /returned no verdict/')
  assert.equal(dNo.artifact, A1, 'no-verdict exit must carry artifact === attempt-1 phaseFn result')

  // (b) gate escalates on attempt 1
  const A2 = { provisioningIntent: 'A2', affectedStacks: ['S1'] }
  const escalated = await runInfra({
    g1Verdicts: [{ verdict: 'escalate', escalateTo: 'infra-intent' }],
    intentReturns: [A2],
  })
  const dEsc = escalated.result.detail
  assert.ok(dEsc, 'escalate run must expose detail')
  assert.equal(dEsc.escalate, 'infra-intent', "escalate exit must carry escalate === 'infra-intent'")
  assert.equal(dEsc.artifact, A2, 'escalate exit must carry artifact === attempt-1 phaseFn result')
})
