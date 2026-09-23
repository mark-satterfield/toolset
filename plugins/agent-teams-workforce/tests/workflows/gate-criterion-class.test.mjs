// Gate criteria carry a CLASS, and the class decides what an unmet criterion costs.
//
// The defect: gate-enforce.js told the judge "Pass criteria (ALL must hold)" and,
// separately, "constitutive criteria are hard stops" — while `criteria` arrived as a flat
// list of strings with nothing marking which ones were constitutive. Told hard stops exist
// and given no way to identify them, a judge defaults to strict and every criterion
// behaves as one.
//
// The two behaviours that matter are asserted here:
//   1. a COMPETITIVE criterion is never adjudicated: it rides out as a flag and the gate passes
//   2. an unmet CONSTITUTIVE criterion yields `loop` or `escalate`, never `pass`
//
// Plus the default that makes the whole thing passive-by-design: a PLAIN STRING is
// competitive, so a criterion is a hard stop only when someone deliberately said so.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const GATE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows', 'gate-enforce.js')

/**
 * Drive gate-enforce with a scripted enforcer verdict.
 *
 * @param {object} opts
 * @param {any[]} opts.criteria     the criteria the caller declares (string or {text,class})
 * @param {object} opts.verdict     what the phase-gate-enforcer returns
 * @param {any[]} [opts.checks]     deterministic checks
 * @param {object} [opts.artifact]  the artifact under review
 * @param {string} [opts.calibration]
 */
function run({ criteria, verdict, checks = [], artifact = { ok: true }, calibration }) {
  return runWorkflowScript(GATE, {
    args: { gate: 'X', phaseName: 'Some Phase', criteria, checks, artifact, calibration, escalateTargets: ['upstream'] },
    agentImpl: () => verdict,
  })
}

const gatePrompt = (calls) => calls.find((c) => c.kind === 'agent' && c.label === 'gate:X').prompt

// ─── The passive default ──────────────────────────────────────────────────────

test('a PLAIN STRING criterion is COMPETITIVE — a hard stop only exists when someone said so', async () => {
  const { result, calls } = await run({
    criteria: ['the change is minimal and the test was not weakened'],
    verdict: { verdict: 'loop', criteria: [], feedback: 'never consulted', flags: [] },
  })
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0, 'a competitive criterion cannot block, so no judge is paid for it')
  assert.equal(result.verdict, 'pass', 'nothing may become a hard stop by default')
  assert.ok(result.flags.some((f) => /competitive criterion, not adjudicated: the change is minimal/.test(f)))
})

test('the plain-string form and the classed form may be mixed in one array', async () => {
  const { result, calls } = await run({
    criteria: [
      'plain and therefore competitive',
      { text: 'explicitly competitive', class: 'competitive' },
      { text: 'explicitly constitutive', class: 'constitutive' },
    ],
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  const prompt = gatePrompt(calls)
  assert.match(prompt, /1\. explicitly constitutive/, 'only the constitutive criterion is adjudicated')
  assert.doesNotMatch(prompt, /plain and therefore competitive/)
  assert.doesNotMatch(prompt, /explicitly competitive/)
  assert.ok(result.flags.some((f) => /not adjudicated: plain and therefore competitive/.test(f)))
  assert.ok(result.flags.some((f) => /not adjudicated: explicitly competitive/.test(f)))
})

test('an UNRECOGNISED class falls back to competitive rather than inventing a hard stop', async () => {
  const { result, calls } = await run({
    criteria: [{ text: 'mystery class', class: 'mandatory' }],
    verdict: { verdict: 'loop', criteria: [], feedback: 'never consulted', flags: [] },
  })
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0)
  assert.equal(result.verdict, 'pass')
  assert.ok(result.flags.some((f) => /not adjudicated: mystery class/.test(f)))
})

// ─── Behaviour 1: an unmet COMPETITIVE criterion passes with a flag ───────────

test('an unmet COMPETITIVE criterion yields PASS with a flag — never a loop', async () => {
  const { result, calls } = await run({
    criteria: ['complexity/duplication reduced', 'behavior preserved (no regression)'],
    // Were a judge consulted it would loop; competitive criteria never reach one.
    verdict: { verdict: 'loop', criteria: [], feedback: 'clean it up and try again', flags: [] },
  })
  assert.equal(result.verdict, 'pass', 'looping on a competitive criterion stops work that should have proceeded under a flag')
  assert.ok(result.flags.some((f) => /complexity\/duplication reduced/.test(f)), 'the criterion survives as a flag')
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0, 'no adjudication and no advantage-evaluator')
})

test('ESCALATE is left alone — it routes bad UPSTREAM input and composites depend on it', async () => {
  const { result } = await run({
    criteria: [{ text: 'the inputs are usable', class: 'constitutive' }, 'everything else here is competitive'],
    verdict: {
      verdict: 'escalate',
      criteria: [{ criterion: 'the inputs are usable', met: false, evidence: 'bad inputs' }],
      feedback: 'bad inputs',
      escalateTo: 'upstream',
      flags: [],
    },
  })
  assert.equal(result.verdict, 'escalate', 'converting an escalate would break Green escalating an unpassable test back to Red')
})

// ─── Behaviour 2: an unmet CONSTITUTIVE criterion never passes ────────────────

test('an unmet CONSTITUTIVE criterion yields LOOP — a pass over one is converted', async () => {
  const { result, calls } = await run({
    criteria: [
      { text: 'No production code was changed to manufacture the failure', class: 'constitutive' },
      'the test asserts real behavior',
    ],
    verdict: {
      verdict: 'pass',
      criteria: [
        { criterion: 'No production code was changed to manufacture the failure', met: false, evidence: 'src/handler.py was edited' },
      ],
      feedback: 'close enough',
      flags: [],
    },
  })
  assert.equal(result.verdict, 'loop', 'a constitutive failure is never a pass')
  assert.match(result.feedback, /src\/handler\.py was edited/, 'the feedback must name what failed')
  assert.match(result.classOverride, /pass-converted-to-loop/)
})

test('a constitutive LOOP stands as a loop, and the presence of one disables the passive conversion', async () => {
  const { result } = await run({
    criteria: [
      { text: 'The previously-failing test now passes', class: 'constitutive' },
      { text: 'the change is minimal', class: 'competitive' },
    ],
    verdict: {
      verdict: 'loop',
      criteria: [{ criterion: 'The previously-failing test now passes', met: false, evidence: 'still red' }],
      feedback: 'make it pass',
      flags: [],
    },
  })
  assert.equal(result.verdict, 'loop')
  assert.equal(result.classOverride, undefined, 'a gate that declares a hard stop keeps its ability to block')
})

test('a PASS over an unmet criterion the caller marked COMPETITIVE is left alone', async () => {
  const { result } = await run({
    criteria: [{ text: 'complexity/duplication reduced', class: 'competitive' }],
    verdict: {
      verdict: 'pass',
      criteria: [{ criterion: 'complexity/duplication reduced', met: false, evidence: 'unchanged' }],
      feedback: 'flagged',
      flags: ['duplication unchanged'],
    },
  })
  assert.equal(result.verdict, 'pass')
  assert.equal(result.classOverride, undefined)
})

// ─── The decision rule reaches the judge, not just the script ─────────────────

test('the enforcer is told every criterion it receives is a hard stop', async () => {
  const { calls } = await run({
    criteria: [{ text: 'c', class: 'constitutive' }],
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  const prompt = gatePrompt(calls)
  assert.match(prompt, /every one is CONSTITUTIVE/)
  assert.match(prompt, /An unmet criterion is a HARD STOP/)
  assert.match(prompt, /a concern that is not one of them is a flag/)
  assert.doesNotMatch(prompt, /Pass criteria \(ALL must hold\)/, 'the ambiguous instruction that caused the defect must be gone')
})

test('a gate declaring NO constitutive criterion passes on its checks with no session', async () => {
  const { result, calls } = await run({
    criteria: ['all competitive here'],
    verdict: { verdict: 'loop', criteria: [], feedback: 'never consulted', flags: [] },
  })
  assert.equal(calls.filter((c) => c.kind === 'agent').length, 0)
  assert.equal(result.verdict, 'pass')
  assert.equal(result.deterministic, true)
  assert.match(result.feedback, /declares no constitutive criterion/)
})

// ─── Per-gate calibration ────────────────────────────────────────────────────

test('calibration is rendered prominently when a gate supplies one, and absent when it does not', async () => {
  const withIt = await run({
    criteria: [{ text: 'c', class: 'constitutive' }],
    calibration: 'BLOCK on: a failing suite. DO NOT BLOCK on: an absent runbook.',
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  assert.match(gatePrompt(withIt.calls), /CALIBRATION FOR THIS GATE/)
  assert.match(gatePrompt(withIt.calls), /DO NOT BLOCK on: an absent runbook\./)

  const without = await run({ criteria: [{ text: 'c', class: 'constitutive' }], verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] } })
  assert.doesNotMatch(gatePrompt(without.calls), /CALIBRATION FOR THIS GATE/)
})

// ─── Deterministic checks stay hard — that is what makes the rest safe ────────

test('a failed deterministic CHECK still loops with no model turn, even when every criterion is competitive', async () => {
  const { result, calls } = await run({
    criteria: ['everything here is competitive'],
    checks: [{ field: 'greenConfirmed', equals: true, label: 'the phase reports Green confirmed' }],
    artifact: { greenConfirmed: false },
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  assert.equal(result.verdict, 'loop', 'a MEASURED failure is not a matter of opinion and the passive default never reaches it')
  assert.equal(result.deterministic, true)
  assert.equal(calls.length, 0, 'and it costs no adjudication')
})

test('an all-mechanical gate with no criteria is unaffected by the classification', async () => {
  const { result } = await run({
    criteria: [],
    checks: [{ field: 'deployedToDev', equals: true }],
    artifact: { deployedToDev: true },
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  assert.equal(result.verdict, 'pass')
  assert.equal(result.deterministic, true)
})

test('a gate with neither criteria nor checks still fails closed', async () => {
  const { result } = await run({ criteria: [], verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] } })
  assert.equal(result.verdict, 'escalate')
  assert.match(result.flags[0], /gate-misconfiguration/)
})

test('a malformed criterion entry is dropped rather than rendered as [object Object]', async () => {
  const { result, calls } = await run({
    criteria: [null, 42, { class: 'constitutive' }, { text: 'the one real criterion', class: 'constitutive' }],
    verdict: { verdict: 'pass', criteria: [], feedback: 'ok', flags: [] },
  })
  assert.equal(result.verdict, 'pass')
  const prompt = gatePrompt(calls)
  assert.doesNotMatch(prompt, /\[object Object\]/)
  assert.match(prompt, /1\. the one real criterion/, 'the surviving criterion is renumbered from 1')
})
