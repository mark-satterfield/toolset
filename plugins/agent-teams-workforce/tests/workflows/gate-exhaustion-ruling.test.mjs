// ssbd-75nr — loop exhaustion HALTED instead of ruling, and ssbd-rhfx — composites
// returned their whole state to the caller.
//
// Exhaustion is decided in code: whatever the final verdict still names as unmet blocks
// the run, which fails at the gate's stage and names the unmet criteria. No agent is
// consulted to rule the remainder competitive. The trimmed return (ssbd-rhfx) is pinned on
// that failing path.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, journalPayload } from './helpers/run-workflow.mjs'

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

/** Exhaust the Red gate of bug-fix; every later gate is scripted to pass. */
async function runToExhaustion() {
  return runWorkflowScript(BUG_FIX, {
    args: { maxLoops: 2, bead: { id: 'ssbd-97as', title: 'settings 500', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
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

test('an exhausted gate fails the run at its stage, naming what is still unmet', async () => {
  const { result, calls } = await runToExhaustion()
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'red')
  assert.equal(result.deployedToDev, false)
  assert.match(result.headline, /gate 2a exceeded 2 loop\(s\)/)
  assert.match(result.headline, /Every acceptance criterion is covered/, 'the headline names the unmet criterion')
  assert.ok(
    !calls.some((c) => c.kind === 'agent' && /advantage/.test(String(c.label))),
    'exhaustion is decided in code — no agent rules on it',
  )
})

test('the caller receives a headline and a journal path, never the phase artifacts', async () => {
  const { result, logs } = await runToExhaustion()
  // ssbd-rhfx: the success return carried the whole triage contract plus seven complete
  // phase artifacts, and single runs came back truncated. A campaign killed the session.
  // The detail is journaled by a RUN-JOURNAL log line the HOST persists (no model call), so
  // the script itself reports no path and the host fills detailPath in.
  assert.equal(result.detailPath, null, 'the script names no journal path; the host writes the journal and reports it')
  // A payload over the chunk size travels as `RUN-JOURNAL-PART i/n` lines, which the
  // host rejoins; `journalPayload` reads either form, as the host does.
  assert.ok(journalPayload({ logs }).detail, 'the detail must be reachable, in the journal line(s)')
  for (const gone of ['detail', 'results', 'contract']) {
    assert.equal(result[gone], undefined, `\`${gone}\` must not cross back to the caller — it is what filled the context window`)
  }
  assert.ok(result.headline.length > 0 && result.beadId === 'ssbd-97as', 'what remains must still identify the run and say what happened')
  // Small enough to survive hundreds of runs in one dispatching session.
  assert.ok(JSON.stringify(result).length < 2000, `the returned value is ${JSON.stringify(result).length} chars — a campaign of these must fit in one context`)
})

test('the landing verdict survives the trim — an orphaned worktree must be impossible to miss', async () => {
  const { result } = await runToExhaustion()
  assert.equal(result.landed, true)
  assert.equal(result.prUrl, 'https://github.com/o/r/pull/7', 'settle reports the run STATUS, not phase state, and it stays on the return')
})
