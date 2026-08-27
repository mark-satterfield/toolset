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
import { runWorkflowScript, readWorkflowSource, workflowCalls, agentCalls, journalDetail } from './helpers/run-workflow.mjs'

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

// ── The monitoring contract: answered on EVERY exit path, never omitted ───────
//
// `deployedToDev` is the only field the dashboard trusts as evidence that code is live in
// AWS dev. It deliberately refuses to derive that from `stage`, and it was right to: it had
// a live bug mapping stage `deploy-to-dev` to a green "live in dev" card, which under the
// PR-gated Gate 5 would have shown deployed work that never reached AWS.
//
// An ABSENT field is the dangerous answer, not the safe one — a consumer that finds nothing
// has to guess, and the guess a green run invites is "true". So every exit path answers.

test('every composite answers the deployment scalars from handback, not per-return', () => {
  for (const name of COMPOSITES) {
    const src = readWorkflowSource(path.join(WF, `${name}.js`))
    assert.match(
      src,
      /function handback\([^)]*\)\s*\{[\s\S]*?deployedToDev: false,[\s\S]*?smokePassed: false,[\s\S]*?deployIteration: 0,/,
      `${name}: all three deployment scalars must be defaulted in handback, where every return passes through`,
    )
    // The input refusals return before handback exists, so they are checked separately.
    for (const refusal of src.match(/return \{ ok: false, stage: 'input'[^}]*\}/g) || []) {
      for (const field of ['deployedToDev: false', 'smokePassed: false', 'deployIteration: 0']) {
        assert.ok(refusal.includes(field), `${name}: an input refusal omits ${field} — handback cannot cover this path`)
      }
    }
    assert.doesNotMatch(
      src,
      /deployedToDev: true,\s*\n\s*deployIteration: 0/,
      `${name}: nothing may default deployedToDev to true`,
    )
  }
})

test('a run that fails BEFORE the deploy phase still reports deployedToDev=false, not undefined', async () => {
  // Green fails, so the run never reaches Deploy. The dashboard must still get a definite
  // "not live in AWS" rather than an absent field it has to interpret.
  const { result, calls } = await runWorkflowScript(path.join(WF, 'bug-fix.js'), {
    args: { maxLoops: 1, bead: { id: 'ssbd-dep', title: 'x', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: false, branch: 'fix/x', prUrl: '' }
      if (call.label === 'ledger:persist') return { written: true, path: '/p.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/x', isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      if (call.name === 'agent-teams-workforce:tdd-red') return { testFiles: ['t.py'], redConfirmed: true, evidence: 'e', greenReachable: true }
      if (call.name === 'agent-teams-workforce:tdd-green') return { greenConfirmed: false, evidence: '' }
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        return { verdict: 'escalate', criteria: [], escalateTo: 'triage', flags: [] }
      }
      return {}
    },
  })

  assert.equal(result.ok, false)
  assert.equal(workflowCalls(calls, 'agent-teams-workforce:deploy').length, 0, 'the run never reached Deploy')
  assert.notEqual(result.deployedToDev, undefined, 'an omitted field forces the consumer to guess')
  assert.equal(result.deployedToDev, false, 'and the honest answer is that nothing reached AWS')
  assert.equal(result.smokePassed, false)
  assert.equal(result.deployIteration, 0, 'no deploy was attempted')
})

test('the input refusals answer ALL THREE scalars, before handback even exists', async () => {
  // These six returns are the one path handback() cannot reach, so its defaulting does not
  // cover them and each scalar has to be carried explicitly. 6.2.1 carried two of the three
  // and its commit message claimed it carried them all — which is the same absent-field trap
  // that commit existed to close, one level down.
  for (const [name, composite] of [['task-to-deploy', 'task-to-deploy.js'], ['bug-fix', 'bug-fix.js'], ['infra-change', 'infra-change.js']]) {
    const run = (bead) => runWorkflowScript(path.join(WF, composite), { args: { bead }, agentImpl: () => null, workflowImpl: () => ({}) })

    for (const [label, bead] of [['no id', { repoPath: '/repos/chassis' }], ['no repoPath', { id: 'ssbd-x' }]]) {
      const { result } = await run(bead)
      assert.equal(result.stage, 'input', `${name} / ${label}`)
      for (const field of ['deployedToDev', 'smokePassed', 'deployIteration']) {
        assert.notEqual(result[field], undefined, `${name} / ${label}: ${field} must not be omitted`)
      }
      assert.equal(result.deployedToDev, false, `${name} / ${label}`)
      // An input refusal means no smoke test ran, so none passed. That is a definite
      // answer, not an unknown.
      assert.equal(result.smokePassed, false, `${name} / ${label}`)
      assert.equal(result.deployIteration, 0, `${name} / ${label}`)
    }
  }
})

test('the field names the dashboard reads do not move', async () => {
  // These four are read directly by the monitoring dashboard and were promised stable.
  // A rename or relocation here is a breaking change that must be coordinated, not shipped.
  const { result } = await runWithDeploys([DEPLOYED_SMOKE_PASSED])
  for (const field of ['deployedToDev', 'settled', 'prUrl', 'deployIteration']) {
    assert.ok(field in result, `${field} must remain a top-level field on the composite result`)
  }
  assert.equal(typeof result.deployedToDev, 'boolean', 'deployedToDev is a scalar, never an object to drill into')
  assert.equal(typeof result.deployIteration, 'number')
})

// ── A MEASURED FACT IS NOT OPEN TO A RULING ──────────────────────────────────
//
// gateLoop's exhaustion path asks the advantage-evaluator whether the remaining findings
// invalidate the work, and a `competitive` ruling returns ok:true carrying the artifact
// that failed. That is correct and deliberate for JUDGMENT criteria — halting a pipeline
// for a non-invalidating finding is the failure mode the evaluator exists to prevent.
//
// It was NOT correct for deterministic checks. A deterministic check did not form an
// opinion about the artifact; it measured it. The rule was stated only in the prompt sent
// to the evaluator, and a rule stated only in a prompt is a request. Nothing checked WHICH
// criteria were unmet, so a competitive ruling could emit ok:true with deployedToDev:false
// — the exact claim the Gate 5 rewrite exists to make impossible.
//
// These two tests are a pair, and the pair is the point: the guard must block the measured
// case WITHOUT disarming the judgment case.

/** Exhaust Gate 5 of bug-fix and let `ruling` answer the advantage-evaluator. */
async function runToGate5Exhaustion({ unmetCriterion, ruling, deterministicChecks }) {
  return runWorkflowScript(path.join(WF, 'bug-fix.js'), {
    args: { maxLoops: 1, bead: { id: 'ssbd-dep', title: 'x', description: 'd', repoPath: '/repos/chassis' } },
    agentImpl: (call) => {
      if (call.label === 'advantage:exhausted-5') return ruling
      if (call.label === 'settle:land-work') return { treeClean: true, hasWork: true, branch: 'fix/x', prUrl: 'https://github.com/o/r/pull/7' }
      if (call.label === 'ledger:persist') return { written: true, path: '/p.jsonl' }
      return null
    },
    workflowImpl: (call) => {
      if (call.name === 'agent-teams-workforce:workspace') {
        return { ok: true, repoPath: WORKTREE, branch: 'fix/x', isLinkedWorktree: true, independentlyVerified: true, defaultBranch: 'main' }
      }
      if (call.name === 'agent-teams-workforce:bug-triage') return { repoPath: WORKTREE, scope: 'fix', acceptanceCriteria: [], affectedFiles: [], surfaces: [] }
      if (call.name === 'agent-teams-workforce:tdd-red') return { testFiles: ['t.py'], redConfirmed: true, evidence: 'e', greenReachable: true }
      if (call.name === 'agent-teams-workforce:tdd-green') return { greenConfirmed: true, evidence: 'passing', changedFiles: ['s.py'] }
      if (call.name === 'agent-teams-workforce:deploy') return NEVER_DEPLOYED
      if (call.name.endsWith('gate-enforce') || call.name.endsWith('gate-constitutional')) {
        if (String(call.payload.gate) !== '5') return { verdict: 'pass', criteria: [], flags: [] }
        return {
          verdict: 'loop',
          feedback: 'unmet',
          criteria: [{ criterion: unmetCriterion, met: false, evidence: 'observed deployedToDev = false' }],
          ...(deterministicChecks ? { deterministicChecks } : {}),
        }
      }
      return {}
    },
  })
}

// bug-fix's own label for the deployedToDev check. Spelled exactly — a near-miss would make
// this test pass for the wrong reason, which is how the first version of it went green
// against a guard that had not fired.
const DEPLOYED_CHECK_LABEL = 'the fix was deployed to the AWS dev environment'
const COMPETITIVE_RULING = {
  ruling: 'competitive',
  rationale: 'incomplete readiness artifacts do not invalidate the build',
  findings: [{ criterion: 'x', classification: 'competitive', rationale: 'process gap' }],
}

test('a COMPETITIVE ruling cannot waive a failed DETERMINISTIC check', async () => {
  const { result, calls } = await runToGate5Exhaustion({
    unmetCriterion: DEPLOYED_CHECK_LABEL,
    ruling: COMPETITIVE_RULING,
    deterministicChecks: [{ criterion: DEPLOYED_CHECK_LABEL, met: false, evidence: 'observed deployedToDev = false' }],
  })

  assert.equal(result.ok, false, 'a measured failure is constitutive by construction — no ruling may waive it')
  assert.equal(result.deployedToDev, false)
  assert.equal(
    agentCalls(calls, 'advantage:exhausted-5').length, 0,
    'and no ruling is even requested: there is nothing to weigh, so the dispatch is skipped rather than made and overridden',
  )
})

test('the guard holds on the labels alone, even when the gate reports no deterministicChecks', async () => {
  // gate-constitutional reports no `deterministicChecks` at all. A guard resting only on
  // that field would silently do nothing the day `checks` are added to such a gate, so the
  // labels are also derived locally from the gate's own `checks`.
  const { result, calls } = await runToGate5Exhaustion({
    unmetCriterion: DEPLOYED_CHECK_LABEL,
    ruling: COMPETITIVE_RULING,
    deterministicChecks: null,
  })

  assert.equal(result.ok, false, 'the guard must not depend on the gate volunteering its own check results')
  assert.equal(agentCalls(calls, 'advantage:exhausted-5').length, 0)
})

test('a COMPETITIVE ruling on a JUDGMENT criterion still proceeds — the advantage path is narrowed, not removed', async () => {
  // This is the case the evaluator exists for. Narrowing the guard must not disarm it:
  // halting the pipeline for a non-invalidating finding is the failure mode it prevents.
  const { result, calls } = await runToGate5Exhaustion({
    unmetCriterion: 'the readiness packet inventories a rollback runbook',
    ruling: COMPETITIVE_RULING,
    deterministicChecks: [{ criterion: DEPLOYED_CHECK_LABEL, met: true, evidence: 'observed deployedToDev = true' }],
  })

  assert.equal(agentCalls(calls, 'advantage:exhausted-5').length, 1, 'a judgment criterion IS routed to the evaluator')
  assert.equal(result.ok, true, 'and a non-invalidating finding proceeds under a flag')
  assert.match(result.headline, /PROCEEDED UNDER 1 carried flag/)
})

test('ok:true from the deploy phase now IMPLIES a confirmed deployment', async () => {
  // The invariant the guard establishes. Before it, ok:true could carry deployedToDev:false
  // through a competitive ruling; now the only routes to ok:true are a passing verdict
  // (whose deterministic checks held) or a competitive ruling on judgment criteria only
  // (which cannot be reached while a deterministic check is failing).
  for (const [label, ruling] of [['competitive', COMPETITIVE_RULING], ['constitutive', { ruling: 'constitutive', rationale: 'r', findings: [] }]]) {
    const { result } = await runToGate5Exhaustion({
      unmetCriterion: DEPLOYED_CHECK_LABEL,
      ruling,
      deterministicChecks: [{ criterion: DEPLOYED_CHECK_LABEL, met: false, evidence: 'observed deployedToDev = false' }],
    })
    assert.ok(!(result.ok === true && result.deployedToDev !== true), `${label}: ok:true must never accompany an unconfirmed deployment`)
  }
})

test('every composite enforces the deterministic rule in CODE, not only in prompt prose', () => {
  for (const name of COMPOSITES) {
    const src = readWorkflowSource(path.join(WF, `${name}.js`))
    assert.match(src, /const measuredFailures = \[/, `${name}: the measured-failure set must be computed`)
    assert.match(
      src,
      /const ruling = measuredFailures\.length \? null : await ruleExhaustion\(/,
      `${name}: no ruling may be requested while a deterministic check is failing`,
    )
    assert.match(src, /deterministicFailure: true/, `${name}: the failure must name itself as a measured one`)
  }
})

// ── Log lines must actually interpolate ──────────────────────────────────────
//
// 6.2.3 shipped `Gate ${gate} ({PHASE}): budget spent …` in all three composites — the
// literal text `{PHASE}` instead of `${phaseName}`. It printed only on the
// deterministic-failure path, which is exactly when someone is debugging a failed measured
// check, so the log was least informative at the moment it mattered most.
//
// It was a GENERATION bug, not a typo: the patch was written with a Python f-string in
// which `{{PHASE}}` collapses to `{PHASE}` before the intended `.replace()` ever ran, so
// the substitution matched nothing and failed silently. A placeholder that survives into
// shipped source is invisible to every check that does not look for it — hence this one.
test('no composite ships an uninterpolated placeholder in a template literal', () => {
  for (const name of COMPOSITES) {
    const src = readWorkflowSource(path.join(WF, `${name}.js`))
    // Inside a backticked line, a bare {WORD} in caps is a placeholder that lost its `$`.
    // The `$` matters: `${MAX_LOOPS}` is correct, a bare `{MAX_LOOPS}` is the bug.
    const suspects = (src.match(/`[^`\n]*(?<!\$)\{[A-Z_]{2,}\}[^`\n]*`/g) || [])
    assert.deepEqual(suspects, [], `${name}: template literal(s) contain an uninterpolated placeholder: ${suspects.join(' | ')}`)
    assert.doesNotMatch(src, /\{PHASE\}/, `${name}: {PHASE} must be \${phaseName}`)
  }
})

test('the deterministic-failure log names the gate AND the phase', async () => {
  const { logs } = await runToGate5Exhaustion({
    unmetCriterion: DEPLOYED_CHECK_LABEL,
    ruling: COMPETITIVE_RULING,
    deterministicChecks: [{ criterion: DEPLOYED_CHECK_LABEL, met: false, evidence: 'observed deployedToDev = false' }],
  })

  const line = (logs || []).find((l) => /DETERMINISTIC check\(s\) failed/.test(l))
  assert.ok(line, 'the deterministic-failure path must log why no ruling was requested')
  assert.doesNotMatch(line, /\{PHASE\}/, 'the placeholder must be interpolated, not printed')
  assert.match(line, /Gate 5 \(Deploy to dev \(iteration 1\/3\)\)/, 'the real phase name must appear')
  assert.match(line, new RegExp(DEPLOYED_CHECK_LABEL), 'and the measured criterion must be named')
})
