// ssbd-nhcx — task-to-deploy.js threw before reaching its own Gate 5.
//
// The file read an identifier named `spec` at two places and declared it nowhere. The
// rename that turned the entry argument from `spec` into `bead` left both reads and the
// whole header comment behind, so the composite /next-task routes ordinary Tasks to died
// with `ReferenceError: spec is not defined` at Gate 1 — before a single agent was
// dispatched — for EVERY caller shape. It was born broken and shipped identically in
// 6.0.3 and 6.0.4, because the syntax checker only PARSES and a free variable is valid
// syntax.
//
// Adjacent, same edit, same class: the contract carried no `bead` key, so tdd-red
// rendered "Feature under test" and adversarial rendered "feature" — the id and title
// were dropped from every Red and Adversarial prompt on the Task path.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const T2D = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows', 'task-to-deploy.js')
const WORKTREE = '/repos/.worktrees/ssbd-nhcx-web'

function run(args) {
  return runWorkflowScript(T2D, {
    args,
    agentImpl: () => ({ written: true, treeClean: true, hasWork: false, branch: 'b', prUrl: '' }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'feat/ssbd-nhcx', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:spec-freshness') return { fresh: true }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === '1') return { verdict: 'pass', criteria: [], flags: [] }
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true }
    },
  })
}

const BEAD = { id: 'ssbd-nhcx', title: 'route the thing', description: 'd', repoPath: '/repos/web' }

test('the composite the routers actually call reaches its phases instead of throwing', async () => {
  // The exact shape commands/work-bead.md and commands/next-task.md dispatch.
  const { result, calls } = await run({ bead: BEAD })
  assert.ok(result, 'the run must produce a result at all — it used to throw ReferenceError at Gate 1')
  const names = calls.filter((c) => c.kind === 'workflow').map((c) => c.name)
  assert.ok(names.includes('agent-teams-workforce:spec-freshness'), 'Gate 1 must actually run')
  assert.ok(names.includes('agent-teams-workforce:tdd-red'), 'and the run must get past it')
})

test('spec defaults to the bead — the only shape any caller sends', async () => {
  const { calls } = await run({ bead: BEAD })
  const freshness = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:spec-freshness')
  assert.ok(freshness, 'spec-freshness must be dispatched')
  assert.equal(freshness.payload.spec.id, 'ssbd-nhcx', 'with no separate spec document, the bead IS the spec')
})

test('an explicitly-supplied spec document still wins', async () => {
  // The header documented args.spec for two releases. A caller that followed it must
  // keep working rather than being silently ignored.
  const { calls } = await run({ bead: BEAD, spec: { id: 'SPEC-9', title: 'the spec', path: 'docs/spec.md' } })
  const freshness = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:spec-freshness')
  assert.equal(freshness.payload.spec.id, 'SPEC-9')
})

test('the contract carries the bead, so Red and Adversarial know what they are working on', async () => {
  const { calls } = await run({ bead: BEAD })
  const red = calls.find((c) => c.kind === 'workflow' && c.name === 'agent-teams-workforce:tdd-red')
  assert.ok(red.payload.contract.bead, 'task-to-deploy was the only composite whose contract had no bead')
  assert.equal(red.payload.contract.bead.id, 'ssbd-nhcx')
  assert.equal(red.payload.contract.bead.title, 'route the thing')
  assert.equal(red.payload.contract.bead.repoPath, WORKTREE, 'the bead on the contract points at the worktree, not the caller path')
})

test('the header comment documents the argument the body actually reads', async () => {
  const { readFileSync } = await import('node:fs')
  const src = readFileSync(T2D, 'utf8')
  const header = src.slice(0, src.indexOf('const a = ('))
  assert.match(header, /bead: \{/, 'the documented entry argument must be the one the code reads')
  assert.match(header, /repoPath,\s+\/\/ required/, 'repoPath is required and the header must say so')
})
