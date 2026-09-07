// A contract that admits no failing test is not a Red the gate can loop into existence.
//
// THE FAILURE THIS MODELS. A work item with no code deliverable — an account cleanup
// performed with a console operation — reached tdd-red twice. Both times every writer
// ran fine, authored nothing, and reported the same structural objection in prose:
// there is no software behavior here to assert. The only shape it had for that was
// `redConfirmed: false`, which is the identical shape to "I wrote tests and they did
// not fail" — an ordinary quality complaint the gate answers by looping. So it looped,
// the writer restated the objection verbatim, the budget was spent, and because a
// DETERMINISTIC check cannot be ruled competitive at exhaustion, the run died having
// judged nothing about any test. Twice, identically.
//
// The repair is a shape, not a persuasion: writers may declare `unauthorable`, and the
// script turns a unanimous declaration into a terminal `phaseBlocked` the composite
// reports up instead of re-dispatching.
//
// THE BAR MATTERS AS MUCH AS THE EXIT. `unauthorable` stops the work, so it must not
// become the cheap way out of writing a test. Every writer must say it, none may have
// authored a file, and each must give a reason — anything less is an ordinary Red
// failure the gate judges normally. The tests below assert both halves.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const tddRed = path.resolve(HERE, '..', '..', 'workflows', 'tdd-red.js')

// Two surfaces, so two writers run and unanimity is a real condition rather than a
// property of there being only one voice.
const CONTRACT = {
  repoPath: '/repo',
  bead: { id: 'ssbd-1', title: 'remove alpha test accounts from the Cognito pool', repoPath: '/repo' },
  acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }],
  surfaces: ['auth'],
}

const REASON = 'the contract names an AWS console account deletion; no production symbol changes, so no test can assert it'

// `writers` is keyed by the agent type suffix so each writer can answer differently.
async function run(writers) {
  return runWorkflowScript(tddRed, {
    args: { contract: CONTRACT, skipDiscovery: true },
    agentImpl: (call) => {
      if (call.label === 'red:coverage') return { gaps: [] }
      const label = String(call.label)
      if (label.startsWith('red:')) {
        const w = label.slice('red:'.length)
        return Object.prototype.hasOwnProperty.call(writers, w) ? writers[w] : writers.default
      }
      return null
    },
  })
}

const UNAUTHORABLE = { testFiles: [], redConfirmed: false, evidence: '', greenPath: [], unauthorable: true, unauthorableReason: REASON }

test('a unanimous unauthorable declaration ends the phase instead of failing it into a loop', async () => {
  const { result } = await run({ default: UNAUTHORABLE })
  assert.equal(result.phaseBlocked, true, 'the phase must report BLOCKED, not an ordinary Red failure')
  assert.equal(result.ok, false, 'nothing was built, so the phase does not pass')
  assert.notEqual(result.alreadySatisfied, true, 'nothing here claims the behavior exists')
  assert.notEqual(result.dispatchFailed, true, 'the agents worked fine — the contract is the problem')
  assert.deepEqual(result.testFiles, [])
  assert.match(result.blockedReason, /admits no failing test/)
  assert.ok(
    result.blockedReason.includes(REASON),
    'the reason the writers gave must survive to the caller — a bare "blocked" sends a human back to the journal',
  )
  assert.equal(result.ledger.blocked, 'contract-unauthorable')
  assert.equal(result.ledger.ok, false)
})

test('one writer authoring a test means the phase is judged normally, not blocked', async () => {
  const { result } = await run({
    'tdd-unit-test-generator': {
      testFiles: ['tests/test_x.py'],
      redConfirmed: true,
      evidence: 'FAILED tests/test_x.py::test_a',
      greenPath: [{ testFile: 'tests/test_x.py', targetFile: 'src/x.py', targetSymbol: 'f', assertionSubject: 'f returns 1' }],
    },
    default: UNAUTHORABLE,
  })
  assert.notEqual(result.phaseBlocked, true, 'a contract one writer could encode is not unauthorable')
  assert.deepEqual(result.testFiles, ['tests/test_x.py'])
})

test('a writer that declines to make the claim keeps the phase an ordinary Red failure', async () => {
  const { result } = await run({
    'tdd-unit-test-generator': UNAUTHORABLE,
    // Blocked in prose only — the exact shape that used to be looped to exhaustion.
    default: { testFiles: [], redConfirmed: false, evidence: 'STATUS: BLOCKED (escalating, not declaring Red)', greenPath: [] },
  })
  assert.notEqual(result.phaseBlocked, true, 'prose is not the declaration; unanimity is required')
  assert.equal(result.redConfirmed, false)
})

test('an unauthorable claim with no reason does not stop the work', async () => {
  const { result } = await run({ default: { testFiles: [], redConfirmed: false, evidence: '', greenPath: [], unauthorable: true, unauthorableReason: '   ' } })
  assert.notEqual(result.phaseBlocked, true, 'a claim that stops the work must say why it stops it')
})

test('the writer prompt names the declaration and forbids the bare-failure shape', async () => {
  const { calls } = await run({ default: UNAUTHORABLE })
  const writerPrompt = calls.find((c) => c.kind === 'agent' && String(c.label).startsWith('red:') && String(c.label) !== 'red:coverage')?.prompt || ''
  assert.match(writerPrompt, /unauthorable/, 'a writer that is never told the shape exists cannot use it')
  assert.match(writerPrompt, /NOT this declaration/, 'the prompt must rule out returning a bare failure with an explanation')
})
