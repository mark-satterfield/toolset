// A phase that reports BLOCKED is reported up, not re-dispatched.
//
// The composite's gateLoop already had two ways for a phase to end an attempt without
// being judged: `alreadySatisfied` (the work was already done — pass, skip the gate) and
// `dispatchFailed` (the producing agents died — not a verdict about anything). Neither
// covers the third case, which is what killed a run twice on the same item: the agents
// worked fine, and the WORK THEY WERE GIVEN admits no artifact at all. tdd-red met a
// contract naming an AWS console account deletion — no production symbol changes, so no
// failing test exists to write.
//
// Looping that cannot repair it. The re-dispatch puts the identical question to the
// identical contract, gets the identical answer, the budget is spent, and at exhaustion
// a DETERMINISTIC check cannot be ruled competitive — so the run dies having judged
// nothing. Twice, with byte-identical handbacks.
//
// So `phaseBlocked` is terminal: the gate is not dispatched, no retry is spent, and the
// reason the phase gave travels to the caller. These tests pin that in all three
// composites, because the gateLoop is copy-pasted between them and has diverged before.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const WORKTREE = '/repos/.worktrees/ssbd-4qzi-chassis'

const BLOCKED_REASON =
  'every Red writer reports this contract admits no failing test and authored none — the item is an AWS console ' +
  'account deletion; it needs a human to re-scope or re-route the work item.'

// Every composite reaches tdd-red through its own entry gate; `entry` is the gate that
// must pass for the run to get that far.
const CASES = [
  { file: 'bug-fix.js', entry: null },
  { file: 'task-to-deploy.js', entry: '1' },
  { file: 'infra-change.js', entry: 'G1' },
]

async function runBlockedRed(file, entry) {
  return runWorkflowScript(path.join(WF, file), {
    args: { maxLoops: 2, bead: { id: 'ssbd-4qzi', title: 'x', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: () => ({ written: true, treeClean: true, hasWork: false, branch: 'b', prUrl: '' }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-4qzi', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name === 'agent-teams-workforce:tdd-red') {
        return { ok: false, phaseBlocked: true, blockedReason: BLOCKED_REASON, redConfirmed: false, testFiles: [], evidence: '', greenReachable: false }
      }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (entry && call.payload.gate === entry) return { verdict: 'pass', criteria: [], flags: [] }
        // Any OTHER gate reaching a verdict is the bug: a blocked phase must not be judged.
        return { verdict: 'loop', feedback: 'should never be asked', criteria: [] }
      }
      return { ok: true }
    },
  })
}

for (const { file, entry } of CASES) {
  test(`${file}: a BLOCKED Red is not judged and not retried`, async () => {
    const { result, calls } = await runBlockedRed(file, entry)
    assert.equal(result.ok, false, 'nothing was built, so the run does not succeed')

    const redRuns = calls.filter((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:tdd-red')
    assert.equal(redRuns.length, 1, 'a blocked phase must be dispatched ONCE — a retry meets the same contract and returns the same answer')

    const gate2a = calls.filter(
      (c) => c.kind === 'workflow' && /gate-(enforce|constitutional)/.test(c.name) && String(c.payload?.gate) === '2a',
    )
    assert.equal(gate2a.length, 0, 'there is nothing for the gate to judge; dispatching it spends a turn to fail a criterion nothing can meet')
  })

  test(`${file}: the blocked reason reaches the caller`, async () => {
    const { result } = await runBlockedRed(file, entry)
    const surfaced = JSON.stringify(result)
    assert.ok(
      surfaced.includes('re-scope or re-route') || surfaced.includes('admits no failing test'),
      `a bare "red failed" sends a human to the journal to learn anything at all; got: ${surfaced.slice(0, 300)}`,
    )
  })
}
