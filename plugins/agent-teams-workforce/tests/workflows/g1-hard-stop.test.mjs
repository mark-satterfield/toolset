// G1 (PRD Validation) keeps exactly ONE hard stop, and that is what makes it able to LOOP.
//
// Making every unmarked criterion competitive left G1 with zero constitutive criteria and
// no deterministic checks, so gate-enforce's no-constitutive-criteria conversion turned the
// first `loop` verdict into a `pass`. There was never an attempt 2 — which made
// prd-to-spec's repairPrdForGate (invoked only at ctx.attempt > 1) dead code, and the stall
// it was written to fix silently un-fixed.
//
// A self-contradictory PRD cannot be specified. There is no "proceed under a flag" that
// yields a coherent spec: architecture, TRD and spec would each run on an incoherent input
// and fail expensively several phases later. So the contradiction criterion — and only that
// one — is constitutive. Its neighbours are completeness and clarity judgments and stay
// competitive by design.
//
// The criteria under test are read from prd-to-spec.js itself rather than restated here:
// a test that restates them would keep passing after someone flipped the real one back.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource } from './helpers/run-workflow.mjs'

const WORKFLOWS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const GATE = path.join(WORKFLOWS, 'gate-enforce.js')
const PRD_TO_SPEC = path.join(WORKFLOWS, 'prd-to-spec.js')

const CONTRADICTION =
  'No unresolved internal contradictions between requirements that cannot be built around (a genuine WHAT-level conflict)'

/** The G1 criteria exactly as prd-to-spec.js declares them. */
function g1Criteria() {
  const src = readWorkflowSource(PRD_TO_SPEC)
  const start = src.indexOf("gate: 'G1', phaseName: 'PRD Validation',")
  assert.notEqual(start, -1, 'the G1 gateLoop call must still be findable in prd-to-spec.js')
  const end = src.indexOf('escalateTargets:', start)
  assert.notEqual(end, -1, 'the G1 criteria block must be bounded by its escalateTargets')
  const block = src.slice(start, end)
  const criteria = []
  const entry = /\{\s*class:\s*'(constitutive|competitive)',\s*text:\s*'((?:[^'\\]|\\.)*)'\s*\}/g
  for (const m of block.matchAll(entry)) criteria.push({ class: m[1], text: m[2].replace(/\\'/g, "'") })
  assert.ok(criteria.length >= 3, `expected G1's criteria to parse; got ${criteria.length}`)
  return criteria
}

/** Drive gate-enforce as G1, with a scripted enforcer verdict. */
function runG1(criteria, verdict) {
  return runWorkflowScript(GATE, {
    args: { gate: 'G1', phaseName: 'PRD Validation', criteria, checks: [], artifact: { ok: true }, escalateTargets: [] },
    agentImpl: (call) =>
      call.label === 'advantage:G1' ? { dispositions: [{ flag: 'f', disposition: 'proceed-under-flag' }] } : verdict,
  })
}

test('G1 declares the contradiction criterion CONSTITUTIVE, and nothing else', () => {
  const criteria = g1Criteria()
  const hard = criteria.filter((c) => c.class === 'constitutive')
  assert.equal(hard.length, 1, 'exactly one hard stop at G1 — the rest are completeness judgments')
  assert.equal(
    hard[0].text,
    CONTRADICTION,
    'the hard stop must be the contradiction criterion, verbatim — its wording is load-bearing for the judge',
  )
})

test('a G1 LOOP over the unmet contradiction criterion is NOT converted to a pass', async () => {
  const { result, calls } = await runG1(g1Criteria(), {
    verdict: 'loop',
    criteria: [
      { criterion: CONTRADICTION, met: false, evidence: 'AC-3 and AC-7 demand opposite outcomes for the same input' },
    ],
    feedback: 'the PRD contradicts itself',
    flags: [],
  })
  assert.equal(result.verdict, 'loop', 'G1 must still be able to block — a contradictory PRD cannot be specified')
  assert.equal(
    result.classOverride,
    undefined,
    'the no-constitutive-criteria conversion must not fire: it is what removed attempt 2 and orphaned repairPrdForGate',
  )
  assert.ok(
    !calls.some((c) => c.label === 'advantage:G1'),
    'a constitutive failure is out of the advantage-evaluator\'s scope',
  )
})

test('a G1 PASS over the unmet contradiction criterion is converted to a LOOP', async () => {
  const { result } = await runG1(g1Criteria(), {
    verdict: 'pass',
    criteria: [{ criterion: CONTRADICTION, met: false, evidence: 'two requirements conflict' }],
    feedback: 'close enough',
    flags: [],
  })
  assert.equal(result.verdict, 'loop', 'a constitutive failure is never a pass, whichever direction the judge leans')
  assert.match(result.classOverride, /pass-converted-to-loop/)
})

test("G1's OTHER criteria stay competitive — a PASS over an unmet one is left alone", async () => {
  const criteria = g1Criteria()
  const soft = criteria.find((c) => c.class === 'competitive')
  const { result, calls } = await runG1(criteria, {
    verdict: 'pass',
    criteria: [
      { criterion: soft.text, met: false, evidence: 'one requirement omits its trigger' },
      { criterion: CONTRADICTION, met: true, evidence: 'no conflicts found' },
    ],
    feedback: 'thin, but coherent',
    flags: ['one requirement omits its trigger'],
  })
  assert.equal(result.verdict, 'pass', 'a thin PRD produces a thin spec, which the downstream gates then see')
  assert.equal(result.classOverride, undefined, 'only the CONTRADICTION criterion is a hard stop here')
  assert.ok(calls.some((c) => c.label === 'advantage:G1'), 'the flag routes to the advantage-evaluator, as before')
})

// The cost of the hard stop, asserted so it is not a surprise later. gate-enforce's
// loop-to-pass conversion is all-or-nothing per gate: it fires only when the gate declares
// NO constitutive criterion. G1 now declares one, so a judge that loops over a purely
// competitive concern is no longer mechanically overruled — only the prompt's "LOOPING ON A
// COMPETITIVE CRITERION IS WRONG" holds it back. That is survivable precisely because a G1
// loop is no longer a stall: attempt 2 repairs the document first (repairPrdForGate), so a
// spent loop buys an edited PRD rather than a re-run of the identical verdict.
test('a G1 loop over a competitive concern now STANDS — the conversion is per-gate, not per-criterion', async () => {
  const criteria = g1Criteria()
  const soft = criteria.find((c) => c.class === 'competitive')
  const { result } = await runG1(criteria, {
    verdict: 'loop',
    criteria: [{ criterion: soft.text, met: false, evidence: 'one requirement omits its trigger' }],
    feedback: 'name the trigger',
    flags: [],
  })
  assert.equal(result.verdict, 'loop')
  assert.equal(result.classOverride, undefined, 'a gate that declares a hard stop keeps its ability to block')
})
