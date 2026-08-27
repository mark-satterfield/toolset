// ssbd-75nr — loop exhaustion HALTED instead of ruling, and ssbd-rhfx — composites
// returned their whole state to the caller.
//
// Exhaustion: spending the retry budget said nothing about whether the objection that
// REMAINED invalidated the work, yet the run died either way — identically for a security
// violation and for a reviewer's opinion that coverage was incomplete. ssbd-97as, a P0
// live outage, died at the Red gate with redConfirmed=true, 7 test files authored, 11
// correctly-failing tests captured and no production file touched, on "AC5 partially
// covered — two of three clauses unassessed". Nothing shipped.
//
// The fix routes the remaining findings to the EXISTING advantage-evaluator, whose whole
// purpose is ruling competitive versus constitutive and which "never halts the pipeline
// for non-invalidating findings". These tests pin all three outcomes: competitive
// proceeds under recorded flags, constitutive fails, and NO RULING fails closed — the last
// is the one that matters most, because reading silence as permission would turn every
// dispatch failure into a waived gate.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, journalDetail, agentCalls } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const BUG_FIX = path.join(WF, 'bug-fix.js')
const WORKTREE = '/repos/.worktrees/ssbd-75nr-chassis'

const LOOP_VERDICT = {
  verdict: 'loop',
  feedback: 'AC5 partially covered',
  criteria: [
    { criterion: 'A failing test encodes the contract', met: true, evidence: 'tests/test_x.py::test_y fails' },
    { criterion: 'Every acceptance criterion is covered', met: false, evidence: 'AC5: two of three clauses unassessed' },
  ],
  deterministicChecks: [{ criterion: 'the phase reports Red confirmed', met: true, evidence: 'observed redConfirmed = true' }],
}

const RED_ARTIFACT = { testFiles: ['tests/test_x.py'], redConfirmed: true, evidence: 'e', greenReachable: true }

/**
 * Exhaust the Red gate of bug-fix and let `ruling` answer the advantage-evaluator.
 * Everything after Red is scripted to pass so a competitive ruling can actually reach the
 * end of the run — the point of the fix is that the pipeline CONTINUES.
 */
async function runToExhaustion(ruling) {
  return runWorkflowScript(BUG_FIX, {
    args: { maxLoops: 2, bead: { id: 'ssbd-97as', title: 'settings 500', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
      if (call.label === 'advantage:exhausted-2a') return ruling
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: true, branch: 'fix/x', prUrl: 'https://github.com/o/r/pull/7' }
      if (call.label === 'ledger:persist') return { written: true, path: '/repos/.claude/workflow-runs/run.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-97as', isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        // Only the Red gate misbehaves; every later gate passes so the run can finish.
        return call.payload.gate === '2a' ? LOOP_VERDICT : { verdict: 'pass', criteria: [], flags: [] }
      }
      if (call.name === 'agent-teams-workforce:tdd-red') return RED_ARTIFACT
      if (call.name === 'agent-teams-workforce:tdd-green') return { greenConfirmed: true, evidence: 'passing', changedFiles: ['src/s.py'] }
      // Deploy reports the two facts Gate 5 asserts. It reports nothing about a pull
      // request — landing is the Settle step, and a PR is not deploy evidence.
      if (call.name === 'agent-teams-workforce:deploy') return { deployedToDev: true, smokePassed: true }
      return {}
    },
  })
}

const COMPETITIVE = {
  ruling: 'competitive',
  rationale: 'partial coverage of one acceptance criterion does not invalidate 11 correctly-failing tests',
  findings: [{ criterion: 'Every acceptance criterion is covered', classification: 'competitive', rationale: 'a completeness opinion' }],
}
const CONSTITUTIVE = {
  ruling: 'constitutive',
  rationale: 'the evidence does not support the claim',
  findings: [{ criterion: 'Every acceptance criterion is covered', classification: 'constitutive', rationale: 'nothing was actually produced' }],
}

test('an exhausted gate consults the EXISTING advantage-evaluator — it is never simply fatal', async () => {
  const { calls } = await runToExhaustion(COMPETITIVE)
  const ruling = agentCalls(calls, 'advantage:exhausted-2a')
  assert.equal(ruling.length, 1, 'the exhausted gate must dispatch exactly one ruling')
  assert.equal(
    ruling[0].opts.agentType,
    'agent-teams-workforce:advantage-evaluator',
    'the authority already exists — a new decider must not be invented for this',
  )
  // The three inputs the ruling cannot be made without.
  assert.match(ruling[0].prompt, /AC5: two of three clauses unassessed/, 'the unmet criteria and their evidence must reach the decider')
  assert.match(ruling[0].prompt, /observed redConfirmed = true/, "the gate's deterministic-check results must reach it")
  assert.match(ruling[0].prompt, /redConfirmed/, 'and the artifact the phase produced')
})

test('a COMPETITIVE ruling proceeds, with the unmet criterion recorded as a carried flag', async () => {
  const { result, calls } = await runToExhaustion(COMPETITIVE)
  assert.equal(result.ok, true, 'the pipeline must not halt for a non-invalidating finding — this is ssbd-97as')
  assert.equal(result.stage, 'deployed-to-dev', 'and it must run all the way to the end, not stop where the gate objected')
  assert.equal(result.deployedToDev, true, 'the terminal stage token names a deployment, so a deployment must have happened')
  assert.match(
    result.headline,
    /PROCEEDED UNDER 1 carried flag/,
    'a run that proceeded past an unmet criterion is not the same run as one that met every criterion, and the headline must say so',
  )
  assert.match(result.headline, /AC5: two of three clauses unassessed/, 'the flag must name the finding, not just its count')
  const journal = journalDetail(calls)
  assert.deepEqual(journal.carriedFlags.length, 1, 'and it is recorded in the journal alongside the phase detail')
})

test('a CONSTITUTIVE ruling still fails the run', async () => {
  const { result } = await runToExhaustion(CONSTITUTIVE)
  assert.equal(result.ok, false, 'a finding that invalidates the work is a hard stop — that distinction is the point')
  assert.equal(result.stage, 'red')
  assert.match(result.headline, /ruled constitutive/, 'and the headline must say it was RULED, not merely that the budget ran out')
})

test('NO ruling fails closed — silence is never permission', async () => {
  for (const [label, ruling] of [['nothing at all', null], ['a result naming no ruling', { findings: [], rationale: 'x' }]]) {
    const { result } = await runToExhaustion(ruling)
    assert.equal(result.ok, false, `${label}: an evaluator that did not rule has not ruled the findings competitive`)
    assert.match(
      result.headline,
      /by default — the advantage-evaluator returned no ruling/,
      `${label}: the run must say the ruling was DEFAULTED, so a dispatch failure is never mistaken for a waived gate`,
    )
  }
})

test('the caller receives a headline and a journal path, never the phase artifacts', async () => {
  const { result } = await runToExhaustion(COMPETITIVE)
  // ssbd-rhfx: the success return carried the whole triage contract plus seven complete
  // phase artifacts, and single runs came back truncated. A campaign killed the session.
  assert.equal(result.detailPath, '/repos/.claude/workflow-runs/run.jsonl', 'the detail must be reachable, by path')
  for (const gone of ['detail', 'results', 'contract']) {
    assert.equal(result[gone], undefined, `\`${gone}\` must not cross back to the caller — it is what filled the context window`)
  }
  assert.ok(result.headline.length > 0 && result.beadId === 'ssbd-97as', 'what remains must still identify the run and say what happened')
  // Small enough to survive hundreds of runs in one dispatching session.
  assert.ok(JSON.stringify(result).length < 2000, `the returned value is ${JSON.stringify(result).length} chars — a campaign of these must fit in one context`)
})

test('the landing verdict survives the trim — an orphaned worktree must be impossible to miss', async () => {
  const { result } = await runToExhaustion(COMPETITIVE)
  assert.equal(result.landed, true)
  assert.equal(result.prUrl, 'https://github.com/o/r/pull/7', 'settle reports the run STATUS, not phase state, and it stays on the return')
})
