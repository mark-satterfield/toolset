// The deterministic check DSL supported only `equals` and `nonEmpty` against a single
// top-level field — so it could not express a NEGATIVE CONTROL over captured output, and
// every such control had to be carried as prose for the enforcer to weigh. Prose is
// exactly what the model can weigh away; a regex is not.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const GATE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows', 'gate-enforce.js')

function run(artifact, checks, criteria = []) {
  return runWorkflowScript(GATE, {
    args: { gate: '2a', phaseName: 'TDD Red', criteria, checks, artifact, escalateTargets: ['triage'] },
    agentImpl: () => ({ verdict: 'pass', criteria: [], feedback: 'ok', flags: [] }),
  })
}

test('notMatches fails the gate when the forbidden pattern appears — with no model turn', async () => {
  const { result, calls } = await run(
    { evidence: 'E   fixture \'db_session\' not found' },
    [{ field: 'evidence', notMatches: 'fixture .{0,80} not found', label: 'the failure is a product failure, not a missing fixture' }],
    ['the test asserts real behavior'],
  )
  assert.equal(result.verdict, 'loop')
  assert.equal(result.deterministic, true)
  assert.equal(calls.length, 0, 'a mechanically-settled failure must not pay for adjudication')
  assert.match(result.feedback, /fixture/)
})

test('notMatches passes clean output through to the judge', async () => {
  const { result } = await run(
    { evidence: 'E   AssertionError: ConfigurationError not raised' },
    [{ field: 'evidence', notMatches: 'fixture .{0,80} not found' }],
    ['the test asserts real behavior'],
  )
  assert.equal(result.verdict, 'pass')
})

test('the narrow pattern deliberately lets a missing-capability red through', async () => {
  // For a defect whose fix INTRODUCES a symbol, the only failure obtainable at HEAD is
  // that symbol's absence, and pytest reports it as an import error with zero collected
  // items. Banning that shape would re-break the carve-out that cost 827k tokens.
  for (const evidence of [
    'ModuleNotFoundError: No module named \'skill_spoke.errors\'',
    'ImportError: cannot import name \'ConfigurationError\'',
    'collected 0 items / 1 error',
  ]) {
    const { result } = await run(
      { evidence },
      [{ field: 'evidence', notMatches: 'fixture .{0,80} not found' }],
      ['the test asserts real behavior'],
    )
    assert.equal(result.verdict, 'pass', `${evidence} is a legitimate missing-capability red`)
  }
})

test('matches requires the pattern to be present', async () => {
  const hit = await run({ evidence: 'FAILED tests/test_x.py::test_y' }, [{ field: 'evidence', matches: 'FAILED' }], ['c'])
  assert.equal(hit.result.verdict, 'pass')
  const miss = await run({ evidence: 'all good' }, [{ field: 'evidence', matches: 'FAILED' }], ['c'])
  assert.equal(miss.result.verdict, 'loop')
})

test('an array field is matched as text, so a list of files is checkable', async () => {
  const { result } = await run(
    { testFiles: ['tests/test_a.py', 'out/cdk.out/template.json'] },
    [{ field: 'testFiles', notMatches: 'cdk\\.out', label: 'no test reads a committed synth artifact' }],
    ['c'],
  )
  assert.equal(result.verdict, 'loop')
})

test('an unusable pattern FAILS CLOSED rather than silently passing', async () => {
  const { result } = await run({ evidence: 'x' }, [{ field: 'evidence', notMatches: '([unclosed' }], ['c'])
  assert.equal(result.verdict, 'loop', 'a check that cannot be evaluated must never be reported as met')
  assert.match(result.criteria[0].evidence, /not a valid regular expression/)
})

test('equals and nonEmpty are untouched', async () => {
  const ok = await run({ redConfirmed: true, evidence: 'e' }, [
    { field: 'redConfirmed', equals: true },
    { field: 'evidence', nonEmpty: true },
  ])
  assert.equal(ok.result.verdict, 'pass')
  assert.equal(ok.result.deterministic, true, 'all-mechanical gates still pass with no adjudication')
  const bad = await run({ redConfirmed: false, evidence: '' }, [
    { field: 'redConfirmed', equals: true },
    { field: 'evidence', nonEmpty: true },
  ])
  assert.equal(bad.result.verdict, 'loop')
})
