// Deploy iterates, and Gate 5 asserts a DEPLOYMENT.
//
// Two defects, one root cause: the pipeline treated "a pull request was opened" as the
// terminal fact of the delivery tail.
//
//   1. Gate 5's deterministic checks were `prOpened === true` and a non-empty `prUrl`.
//      A pull request is a migration proposed in GitHub; it is not a deployment to any
//      environment. `deployedToDev` was computed by deploy.js, returned to the composite,
//      and asserted by nothing at all — so a run could report success having deployed
//      nothing, and the success headline claimed the work was "built and DEPLOYED TO DEV,
//      smoke-checked against the deployed endpoints" on evidence nobody ever checked.
//
//   2. Deploy was one-shot. Smoke tests can only run against a DEPLOYED environment, so a
//      smoke failure is a defect that environment has just proved — and the only response
//      available was to fail the artifact. The honest cycle is deploy, test, fix, deploy,
//      test, and it happens entirely before a pull request is a sensible thing to open.
//
// These tests pin both, across all three composites. Every dispatch is an in-process fake;
// nothing here reaches GitHub or AWS.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, readWorkflowSource, workflowCalls, journalDetail } from './helpers/run-workflow.mjs'

const WF = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'workflows')
const COMPOSITES = ['task-to-deploy', 'bug-fix', 'infra-change']
const WORKTREE = '/repos/.worktrees/ssbd-dep-chassis'

// ── The Gate 5 contract, read off the source of every composite ───────────────
test('no composite gates deployment on a pull request', () => {
  for (const name of COMPOSITES) {
    const src = readWorkflowSource(path.join(WF, `${name}.js`))
    assert.doesNotMatch(
      src,
      /field: 'prOpened'/,
      `${name}: a pull request is not deploy evidence and must not be a Gate 5 check`,
    )
    assert.doesNotMatch(
      src,
      /field: 'prUrl'/,
      `${name}: the presence of a PR URL says nothing about whether anything was deployed`,
    )
    assert.match(
      src,
      /field: 'deployedToDev', equals: true/,
      `${name}: Gate 5 must mechanically assert that the change reached AWS dev`,
    )
    assert.match(
      src,
      /field: 'smokePassed', equals: true/,
      `${name}: Gate 5 must mechanically assert the smoke tests passed against the deployed endpoints`,
    )
  }
})

// ── The iteration loop ────────────────────────────────────────────────────────

/**
 * Drive bug-fix to its Deploy phase and let `deployResults` answer, in order, each
 * dispatch of the deploy mini. Everything before Deploy is scripted to pass so the run
 * reaches the phase under test.
 */
async function runWithDeploys(deployResults, args = {}) {
  const greenCalls = []
  return {
    greenCalls,
    ...(await runWorkflowScript(path.join(WF, 'bug-fix.js'), {
      // maxLoops:1 isolates the DEPLOY-ITERATION loop from the gate-retry loop. They are
      // different mechanisms — a gate retry asks for a better artifact, a deploy iteration
      // responds to a verdict reality handed down — and with both running a deploy count
      // measures neither one.
      args: { maxLoops: 1, bead: { id: 'ssbd-dep', title: 'smoke defect', description: 'd', repoPath: '/repos/chassis' }, ...args },
      agentImpl: (call) => {
        if (call.label === 'settle:land-work') {
          return { treeClean: true, hasWork: true, branch: 'fix/x', prUrl: 'https://github.com/o/r/pull/7' }
        }
        if (call.label === 'ledger:persist') return { written: true, path: '/repos/.claude/workflow-runs/run.jsonl' }
        return null
      },
      workflowImpl: (call) => {
        if (call.name === 'agent-teams-workforce:workspace') {
          return { ok: true, repoPath: WORKTREE, branch: 'fix/ssbd-dep', isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
        }
        if (call.name === 'agent-teams-workforce:bug-triage') {
          return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
        }
        if (call.name === 'agent-teams-workforce:tdd-red') {
          return { testFiles: ['tests/test_x.py'], redConfirmed: true, evidence: 'e', greenReachable: true }
        }
        if (call.name === 'agent-teams-workforce:tdd-green') {
          greenCalls.push(call.payload || {})
          return { greenConfirmed: true, evidence: 'passing', changedFiles: ['src/s.py'] }
        }
        if (call.name === 'agent-teams-workforce:deploy') {
          // Keyed on which Green produced the artifact, not on a call counter: a redeploy
          // is a response to a FIX, so the response changes when the fix does.
          return deployResults[Math.min(greenCalls.length - 1, deployResults.length - 1)]
        }
        if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
          // Gate 5's deterministic checks are the thing under test, so that gate is judged
          // for real against the artifact; every other gate is scripted to pass.
          if (String(call.payload.gate) !== '5') return { verdict: 'pass', criteria: [], flags: [] }
          const art = call.payload.artifact || {}
          const met = art.deployedToDev === true && art.smokePassed === true
          return met
            ? { verdict: 'pass', criteria: [], flags: [] }
            : { verdict: 'loop', feedback: 'deployment evidence missing', criteria: [], deterministic: true }
        }
        return {}
      },
    })),
  }
}

const DEPLOYED_SMOKE_FAILED = {
  deployedToDev: true,
  smokePassed: false,
  rollout: { deployed: true, smokePassed: false, evidence: 'smoke/test_health.py::test_health FAILED 502' },
}
const DEPLOYED_SMOKE_PASSED = { deployedToDev: true, smokePassed: true, rollout: { deployed: true, smokePassed: true } }
const NEVER_DEPLOYED = { deployedToDev: false, smokePassed: false, readiness: { ready: false, findings: ['drift'] } }

test('a smoke failure in the DEPLOYED dev environment re-enters Green and redeploys', async () => {
  const { result, calls, greenCalls } = await runWithDeploys([DEPLOYED_SMOKE_FAILED, DEPLOYED_SMOKE_PASSED])

  assert.equal(workflowCalls(calls, 'agent-teams-workforce:deploy').length, 2, 'it must deploy a second time')
  assert.equal(greenCalls.length, 2, 'and Green must be re-entered between the two deploys to fix the defect')
  assert.match(
    String(greenCalls[1].feedback || ''),
    /DID reach the AWS dev environment, and the smoke tests then FAILED/,
    'the fix must be told what the deployed environment actually proved',
  )
  assert.match(String(greenCalls[1].feedback || ''), /test_health FAILED 502/, 'including the literal smoke output')
  assert.equal(result.ok, true)
  assert.equal(result.stage, 'deployed-to-dev')
  assert.equal(result.deployedToDev, true)
  assert.equal(result.smokePassed, true)
  assert.equal(result.deployIteration, 2)
})

test('each iteration emits its own telemetry row so a monitor can show "deploy #2"', async () => {
  const { calls } = await runWithDeploys([DEPLOYED_SMOKE_FAILED, DEPLOYED_SMOKE_PASSED])
  const journal = journalDetail(calls)
  const rows = journal.deployIterations || []
  assert.deepEqual(
    rows.map((r) => r.stage),
    ['deploy-to-dev#1', 'deploy-to-dev#2'],
    'a single opaque deploy phase cannot tell an operator which attempt they are watching',
  )
  assert.equal(rows[0].smokePassed, false)
  assert.equal(rows[1].smokePassed, true)
})

test('exhausting the iteration bound FAILS, with a headline naming the smoke failure', async () => {
  const { result, calls } = await runWithDeploys([DEPLOYED_SMOKE_FAILED])

  assert.equal(workflowCalls(calls, 'agent-teams-workforce:deploy').length, 3, 'the default bound is three iterations')
  assert.equal(result.ok, false, 'a deployed environment that still fails its smoke tests is not a successful run')
  assert.equal(result.deployedToDev, true, 'the bytes did reach AWS — that much is true and is reported')
  assert.equal(result.smokePassed, false)
  assert.match(result.headline, /smoke tests FAILED against the deployed dev endpoints/)
  assert.match(result.headline, /test_health FAILED 502/, 'the headline must name the failure, not just its existence')
  assert.match(result.headline, /budget of 3 iteration\(s\) is spent/)
})

test('the bound is configurable', async () => {
  const { calls } = await runWithDeploys([DEPLOYED_SMOKE_FAILED], { maxDeployIterations: 2 })
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:deploy').length, 2)
})

test('a deploy that never reached AWS does NOT iterate — redeploying the same artifact cannot help', async () => {
  const { result, calls, greenCalls } = await runWithDeploys([NEVER_DEPLOYED])

  // The readiness verdict blocked the rollout. Nothing was deployed, so there is no
  // deployed environment whose verdict a fix could be responding to; iterating would
  // burn two more AWS rollouts proving the same thing.
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:deploy').length, 1, 'exactly one deploy attempt')
  assert.equal(greenCalls.length, 1, 'Green is not re-entered — there is no deployed defect to fix')
  assert.equal(result.ok, false)
  assert.equal(result.stage, 'deploy-to-dev')
  assert.equal(result.deployedToDev, false)
})

// ── The headline may only claim what the gate measured ────────────────────────
test('the success headline claims a deployment and a passing smoke, both of which Gate 5 asserted', async () => {
  const { result } = await runWithDeploys([DEPLOYED_SMOKE_PASSED])
  assert.match(result.headline, /DEPLOYED TO AWS DEV/)
  assert.match(result.headline, /PASSING against the deployed dev endpoints/)
  assert.match(
    result.headline,
    /Landing the work in git .* is the separate Settle step/,
    'and it must not let a reader mistake a deployment for a merge, or vice versa',
  )
})

test('landing is reported separately from deployment, under its own stage token', async () => {
  const { result } = await runWithDeploys([DEPLOYED_SMOKE_PASSED])
  assert.equal(result.deployedToDev, true, 'AWS truth')
  assert.equal(result.landingStage, 'landed', 'git truth')
  assert.equal(result.prUrl, 'https://github.com/o/r/pull/7')
  assert.equal(result.settled, 'reported')
})
