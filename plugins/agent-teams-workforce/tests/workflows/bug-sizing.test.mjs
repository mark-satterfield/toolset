// A bug can be worked, or it can turn out to need a PRD and an Epic.
//
// The fix path has no PRD validation, no architecture ruling, and no spec. So a
// defect whose honest remedy is "redesign how this service stores its data" would
// get that redesign built by an implementer, unreviewed, on the authority of a bug
// ticket — an architecture decision made by accident, which is the failure this
// workforce exists to prevent.

import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = path.resolve(HERE, '..', '..', 'workflows')
const bugTriage = path.join(WORKFLOWS, 'bug-triage.js')
const bugFix = path.join(WORKFLOWS, 'bug-fix.js')

const DIAGNOSIS = {
  reproduction: 'call the endpoint',
  rootCause: 'env var mismatch at handler.py:12',
  affectedFiles: ['handler.py'],
  blastRadius: 'one service',
}

function triageAgents(sizing) {
  return (call) => {
    if (call.label === 'triage:diagnosis') return DIAGNOSIS
    if (call.label === 'triage:sizing') return sizing
    if (call.label === 'triage:contract') return { acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }] }
    return { acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }] }
  }
}

async function triage(sizing) {
  const { result } = await runWorkflowScript(bugTriage, {
    args: { bead: { id: 'ssbd-1', title: 'a bug', description: 'd', repoPath: '/repo' } },
    agentImpl: triageAgents(sizing),
  })
  return result
}

test('a plain defect is sized as a fix and carries its acceptance criteria', async () => {
  const r = await triage({ scope: 'fix', rationale: 'correctable within the current design' })
  assert.equal(r.scope, 'fix')
  assert.ok(r.acceptanceCriteria.length > 0, 'a fixable bug still gets its contract')
})

test('a defect needing a redesign is sized as needs-prd and authors no contract', async () => {
  const r = await triage({
    scope: 'needs-prd',
    rationale: 'the fix changes the event schema and crosses a service boundary',
    contractsTouched: ['events.document.rendered'],
  })
  assert.equal(r.scope, 'needs-prd')
  assert.deepEqual(r.acceptanceCriteria, [], 'no build contract is authored for something that must not be built here')
  assert.match(r.note, /start-prd/, 'the escalation must name how to promote it')
})

test('a missing sizing verdict defaults to needs-prd, not to fix', async () => {
  // The errors are not symmetric. Calling a redesign a "fix" ships an unreviewed
  // architecture change; calling a fix a "redesign" costs a PRD nobody needed.
  const r = await triage(null)
  assert.equal(r.scope, 'needs-prd', 'silence must not be read as permission to build')
})

test('the sizer is a different agent from the diagnostician', async () => {
  const { calls } = await runWorkflowScript(bugTriage, {
    args: { bead: { id: 'ssbd-1', title: 'a bug', description: 'd', repoPath: '/repo' } },
    agentImpl: triageAgents({ scope: 'fix', rationale: 'r' }),
  })
  const diag = calls.find((c) => c.label === 'triage:diagnosis')
  const size = calls.find((c) => c.label === 'triage:sizing')
  assert.ok(size, 'a sizing step must run')
  assert.notEqual(
    size.opts.agentType,
    diag.opts.agentType,
    'the agent that found the root cause is the worst-placed judge of whether fixing it is too big',
  )
})

test('bug-fix STOPS at triage on needs-prd — nothing is built or deployed', async () => {
  const { result, calls } = await runWorkflowScript(bugFix, {
    args: { bead: { id: 'ssbd-1', title: 'a bug', description: 'd', repoPath: '/repo' } },
    workflowImpl: (call) => {
      // The composite's first phase is `workspace` — it OWNS the worktree every writing
      // phase then operates in, so a fixture must supply one or the run correctly
      // refuses to write anywhere (ssbd-mz1w).
      if (String(call.name).endsWith('workspace')) {
        return { ok: true, repoPath: '/repo/../.worktrees/ssbd-1-repo', branch: 'fix/ssbd-1', reused: false, isLinkedWorktree: true }
      }
      if (String(call.name).endsWith('bug-triage')) {
        return { ...DIAGNOSIS, scope: 'needs-prd', scopeRationale: 'changes the event schema', contractsTouched: ['e'] }
      }
      return { verdict: 'pass', criteria: [], flags: [] }
    },
    agentImpl: () => null,
  })

  assert.equal(result.ok, false)
  assert.equal(result.outcome, 'needs-prd')
  assert.ok(result.diagnosis.rootCause, 'the diagnosis survives as the input a PRD starts from')

  const ran = calls.filter((c) => c.kind === 'workflow').map((c) => String(c.name))
  for (const phase of ['tdd-red', 'tdd-green', 'deploy']) {
    assert.ok(
      !ran.some((n) => n.endsWith(phase)),
      `${phase} must not run for a defect that needs a PRD — the fix path has no architecture review`,
    )
  }
})

test('bug-fix proceeds normally when triage sizes it as a fix', async () => {
  const { calls } = await runWorkflowScript(bugFix, {
    args: { bead: { id: 'ssbd-1', title: 'a bug', description: 'd', repoPath: '/repo' } },
    workflowImpl: (call) => {
      const n = String(call.name)
      // The composite's first phase is `workspace` — it OWNS the worktree every writing
      // phase then operates in, so a fixture must supply one or the run correctly
      // refuses to write anywhere (ssbd-mz1w).
      if (n.endsWith('workspace')) {
        return { ok: true, repoPath: '/repo/../.worktrees/ssbd-1-repo', branch: 'fix/ssbd-1', reused: false, isLinkedWorktree: true }
      }
      if (n.endsWith('bug-triage')) {
        return { ...DIAGNOSIS, scope: 'fix', acceptanceCriteria: [{ given: 'g', when: 'w', then: 't' }] }
      }
      if (n.endsWith('gate-enforce') || n.endsWith('gate-constitutional')) return { verdict: 'pass', criteria: [], flags: [] }
      return { ok: true, greenConfirmed: true, changedFiles: ['handler.py'], evidence: 'e', testFiles: ['t'] }
    },
    agentImpl: () => null,
  })
  const ran = calls.filter((c) => c.kind === 'workflow').map((c) => String(c.name))
  assert.ok(ran.some((n) => n.endsWith('tdd-red')), 'a fixable bug must still reach Red')
})
