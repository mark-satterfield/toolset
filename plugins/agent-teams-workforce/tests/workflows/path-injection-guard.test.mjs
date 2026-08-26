// A path is COMMAND TEXT in these prompts, and it was interpolated verbatim.
//
// workspace.js took the provisioner-supplied repoPath, ran .trim() on it, and dropped it
// straight into `git -C "${path}"` lines inside a prompt that a SECOND agent is told to
// run exactly as written. The three settle guards did the same with the worktree path, in
// a prompt whose commands COMMIT AND PUSH. A path carrying a double quote closes the
// quoting; a backtick, a `$(`, a `;` or a `&&` appends commands of the path author's
// choosing to a shell another agent then executes. The caller supplies the first path and
// a dispatched AGENT supplies the second, so neither is a trusted author of shell.
//
// The rule is refuse, never sanitize: a rewritten path names a different tree, it would
// still be interpolated, and nobody would learn of the substitution.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const WORKSPACE = path.join(WF, 'workspace.js')
const COMPOSITES = ['bug-fix.js', 'task-to-deploy.js', 'infra-change.js']

// Each one reshapes the command line it lands in. They are absolute and otherwise
// plausible on purpose — the guard must key on the character, not on the path looking odd.
const HOSTILE_PATHS = [
  { label: 'a double quote closes the -C argument', value: '/repos/chassis" && rm -rf / && echo "' },
  { label: 'a backtick opens a command substitution', value: '/repos/`id`/chassis' },
  { label: 'a dollar sign opens a command substitution', value: '/repos/$(id)/chassis' },
  { label: 'a semicolon starts a second command', value: '/repos/chassis; git push --force origin main' },
  { label: 'a newline starts a second command', value: '/repos/chassis\ngit push --force origin main' },
  { label: 'a pipe redirects the command', value: '/repos/chassis | sh' },
  { label: 'an ampersand backgrounds and chains', value: '/repos/chassis && curl http://x/y' },
  { label: 'a single quote reshapes the surrounding prompt', value: "/repos/chas'sis" },
]

const RELATIVE_PATHS = ['repos/chassis', './chassis', '../chassis', '~/repos/chassis']

// ── workspace.js: the CALLER's path ───────────────────────────────────────────

for (const { label, value } of HOSTILE_PATHS) {
  test(`workspace: refuses a caller repoPath where ${label} — and dispatches nothing`, async () => {
    const { result, calls } = await runWorkflowScript(WORKSPACE, {
      args: { repoPath: value, beadId: 'ssbd-1xcs', branchPrefix: 'fix' },
      agentImpl: () => ({ ok: true, repoPath: '/repos/.worktrees/ssbd-1xcs-chassis', branch: 'fix/ssbd-1xcs', reused: false, isLinkedWorktree: true }),
    })
    assert.equal(result.ok, false, 'a path that can reshape a command must never reach one')
    assert.equal(result.repoPath, null)
    assert.ok(Array.isArray(result.blocked) && result.blocked.length, 'the refusal must say what was wrong')
    assert.match(result.blocked[0], /repoPath/, 'and name the offending input')
    assert.deepEqual(calls, [], 'refusing AFTER dispatching is not refusing — the prompt would already carry it')
  })
}

for (const value of RELATIVE_PATHS) {
  test(`workspace: refuses the relative repoPath ${JSON.stringify(value)}`, async () => {
    const { result, calls } = await runWorkflowScript(WORKSPACE, {
      args: { repoPath: value, beadId: 'ssbd-1xcs' },
      agentImpl: () => ({ ok: true, repoPath: '/wt', branch: 'work/ssbd-1xcs', reused: false, isLinkedWorktree: true }),
    })
    assert.equal(result.ok, false, 'every command here is `git -C`, which resolves a relative path against the ambient directory')
    assert.match(result.blocked[0], /absolute/)
    assert.deepEqual(calls, [])
  })
}

test('workspace: refuses a beadId carrying shell metacharacters — it is command text too', async () => {
  // The bead id is interpolated into the branch name AND into the shell expression that
  // builds the worktree directory, so it is the same surface as the path.
  const { result, calls } = await runWorkflowScript(WORKSPACE, {
    args: { repoPath: '/repos/chassis', beadId: 'ssbd-1xcs"; rm -rf /; #' },
    agentImpl: () => ({ ok: true, repoPath: '/wt', branch: 'x', reused: false, isLinkedWorktree: true }),
  })
  assert.equal(result.ok, false)
  assert.match(result.blocked[0], /beadId/)
  assert.deepEqual(calls, [])
})

test('workspace: an ordinary absolute path still provisions — the guard bought no strictness by refusing everything', async () => {
  const { result, calls } = await runWorkflowScript(WORKSPACE, {
    args: { repoPath: '/repos/chassis', beadId: 'ssbd-1xcs', branchPrefix: 'fix' },
    agentImpl: (call) =>
      call.label === 'workspace:provision'
        ? { ok: true, repoPath: '/repos/.worktrees/ssbd-1xcs-chassis', branch: 'fix/ssbd-1xcs', reused: false, isLinkedWorktree: true }
        : {
            ok: true,
            gitDir: '/repos/chassis/.git/worktrees/ssbd-1xcs-chassis',
            gitCommonDir: '/repos/chassis/.git',
            branch: 'fix/ssbd-1xcs',
            callerCommonDir: '/repos/chassis/.git',
            callerDefaultBranch: 'main',
          },
  })
  assert.equal(result.ok, true)
  assert.equal(result.repoPath, '/repos/.worktrees/ssbd-1xcs-chassis')
  assert.equal(calls.length, 2, 'both dispatches must still happen for a legitimate path')
})

// ── workspace.js: the PROVISIONER's path, which is agent-supplied ─────────────

for (const { label, value } of HOSTILE_PATHS) {
  test(`workspace: refuses a PROVISIONED repoPath where ${label} — the verifier prompt never carries it`, async () => {
    const { result, calls } = await runWorkflowScript(WORKSPACE, {
      args: { repoPath: '/repos/chassis', beadId: 'ssbd-1xcs', branchPrefix: 'fix' },
      agentImpl: (call) => {
        if (call.label === 'workspace:provision') {
          return { ok: true, repoPath: value, branch: 'fix/ssbd-1xcs', reused: false, isLinkedWorktree: true }
        }
        throw new Error('the independent verifier must never be dispatched with a path that can reshape its commands')
      },
    })
    assert.equal(result.ok, false, 'the second dispatch is where the provisioner would be writing another agent\'s shell')
    assert.equal(result.repoPath, null)
    assert.ok(result.blocked.some((b) => /provisioned repoPath/.test(b)), `expected a refusal naming the provisioned path, got ${JSON.stringify(result.blocked)}`)
    const verify = calls.filter((c) => c.label === 'workspace:independent-verify')
    assert.deepEqual(verify, [], 'the verify dispatch must not happen at all')
    for (const c of calls) {
      assert.ok(!c.prompt.includes(value), 'no dispatched prompt may carry the hostile path')
    }
  })
}

// ── the three settle guards ───────────────────────────────────────────────────

/** Drive a composite to its settle step with a scripted workspace result. */
function runComposite(file, workspaceResult) {
  return runWorkflowScript(path.join(WF, file), {
    args: { bead: { id: 'ssbd-1xcs', title: 's', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: () => ({ written: true }),
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') return workspaceResult
      if (call.name === 'agent-teams-workforce:bug-triage') {
        return { repoPath: workspaceResult.repoPath, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      }
      if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (call.payload.gate === '1' || call.payload.gate === 'G1') return { verdict: 'pass', criteria: [], flags: [] }
        return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
      }
      return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true }
    },
  })
}

for (const file of COMPOSITES) {
  for (const { label, value } of HOSTILE_PATHS) {
    test(`${file}: settle REFUSES a worktree path where ${label} — it never becomes a commit-and-push prompt`, async () => {
      const { result, calls } = await runComposite(file, {
        ok: true,
        repoPath: value,
        branch: 'fix/ssbd-1xcs',
        reused: false,
        isLinkedWorktree: true,
        independentlyVerified: true,
        defaultBranch: 'main',
      })
      assert.equal(result.ok, false)
      assert.equal(result.landed, false, 'nothing may be reported as landed through a path nobody could safely name')
      assert.ok(result.orphaned, 'the work is named and left where a human can find it')
      assert.match(
        result.orphaned.blocked.join(' '),
        /refused to act on the worktree path/,
        `expected the path refusal, got ${JSON.stringify(result.orphaned.blocked)}`,
      )
      const settle = calls.filter((c) => c.kind === 'agent' && c.label === 'settle:land-work')
      assert.deepEqual(settle, [], 'the settle agent must never be dispatched with it')
      for (const c of calls) {
        if (c.kind === 'agent') assert.ok(!c.prompt.includes(value), 'no dispatched prompt may carry the hostile path')
      }
    })
  }

  test(`${file}: settle still LANDS through an ordinary worktree path`, async () => {
    // The positive control. A guard that blocks every path blocks every run.
    const WT = '/repos/.worktrees/ssbd-1xcs-chassis'
    const { result, calls } = await runWorkflowScript(path.join(WF, file), {
      args: { bead: { id: 'ssbd-1xcs', title: 's', description: 'd', repoPath: '/repos/chassis' } },
      agentImpl: (call) =>
        call.label === 'settle:land-work'
          ? { treeClean: true, hasWork: true, branch: 'fix/ssbd-1xcs', prUrl: 'https://github.com/o/r/pull/7' }
          : { written: true },
      workflowImpl: (call) => {
        if (call.name === 'agent-teams-workforce:workspace') {
          return { ok: true, repoPath: WT, branch: 'fix/ssbd-1xcs', reused: false, isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
        }
        if (call.name === 'agent-teams-workforce:bug-triage') {
          return { repoPath: WT, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
        }
        if (call.name === 'agent-teams-workforce:infra-intent') return { provisioningIntent: 'p', affectedStacks: ['S'] }
        if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
          if (call.payload.gate === '1' || call.payload.gate === 'G1') return { verdict: 'pass', criteria: [], flags: [] }
          return { verdict: 'escalate', escalateTo: 'upstream', criteria: [] }
        }
        return { ok: true, testFiles: ['t'], redConfirmed: true, evidence: 'e', greenReachable: true }
      },
    })
    assert.equal(result.landed, true)
    assert.equal(result.prUrl, 'https://github.com/o/r/pull/7')
    const settle = calls.filter((c) => c.kind === 'agent' && c.label === 'settle:land-work')
    assert.equal(settle.length, 1, 'the settle agent must still be dispatched for a legitimate path')
    assert.ok(settle[0].prompt.includes(WT))
  })
}
