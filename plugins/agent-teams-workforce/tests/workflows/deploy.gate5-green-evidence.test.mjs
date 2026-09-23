// ssbd-1xcs D1 — unrun test suite reaches AWS (deploy.js).
// Encodes acceptance criteria D1-AC1 .. D1-AC6.
//
// Defect under test: deploy.js builds the Gate 5 prompt from the facilitator's
// prose inventory only; green.greenConfirmed / green.evidence (required fields
// produced by tdd-green.js) are never read, so "tests not run / not reported"
// falls into the "When genuinely uncertain, RULE READY" default and the change
// deploys to AWS dev account 616930583457.
//
// Gate 5 readiness is computed by deploy.js from facts it holds; no agent rules on it,
// so blocking must come from deploy.js itself.
// No test here can reach any AWS control plane: every dispatch is an in-process fake.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  runWorkflowScript,
  readWorkflowSource,
  agentCalls,
  agentCallIndex,
} from './helpers/run-workflow.mjs'

const DEPLOY_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', '..', 'workflows', 'deploy.js'
)

const CONTRACT = {
  repoPath: '/tmp/fixture-repo',
  bead: { id: 'ssbd-1xcs', title: 'gate evidence fixture' },
}

/** Scripted responses keyed by dispatch label; unknown labels get a generic artifact. */
function deployResponders(overrides = {}) {
  const base = {
    'deploy:smoke-author': { smokeTestFiles: ['smoke/test_fixed_behavior.py'] },
    'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    'deploy:rollout-dev': {
      deployed: true, stacks: ['DevStack'], smokePassed: true,
      smokeCases: [{ name: 'fixed behavior', passed: true, output: 'ok' }],
    },
    ...overrides,
  }
  return (call) =>
    Object.prototype.hasOwnProperty.call(base, call.label) ? base[call.label] : { summary: 'ok' }
}

// ─── D1-AC1 — evidence is read ────────────────────────────────────────────────
// Readiness is computed by deploy.js from the Green artifact; no agent rules on it.
test('D1-AC1: deploy.js reads green.greenConfirmed and green.evidence, and confirmed Green evidence lets the rollout proceed', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      green: { greenConfirmed: true, evidence: '12 passed, 0 failed (pytest -q)', changedFiles: ['svc/handler.py'] },
    },
    agentImpl: deployResponders({
      'deploy:cdk-validate': {
        applicable: false, synthValid: false, driftDetected: false,
        details: 'deploys via s3 sync; infrastructure owned by web-infra',
      },
    }),
  })
  assert.equal(result.readiness.ready, true, 'confirmed Green evidence plus a substantiated not-applicable CDK is ready')
  assert.equal(agentCalls(calls, 'deploy:rollout-dev').length, 1)

  const src = readWorkflowSource(DEPLOY_JS)
  assert.ok(src.includes('green.greenConfirmed'), 'deploy.js must read green.greenConfirmed')
  assert.ok(src.includes('green.evidence'), 'deploy.js must read green.evidence')
})

// ─── D1-AC2 — unconfirmed green blocks the ROLLOUT ────────────────────────────
// The blocked thing is AWS. Source control is not this mini's concern at all any more:
// deploying to dev and landing the work in git are separate steps, and landing belongs
// to the composite's Settle step, which runs on every exit path including this one. So
// nothing reaches AWS, ledger.ok stays false, the findings still name the unconfirmed
// tests, and no PR is opened or expected here either way.
test('D1-AC2: greenConfirmed=false blocks the rollout — no deploy, ledger not ok, findings name the unconfirmed tests', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      green: { greenConfirmed: false, evidence: 'suite not run', changedFiles: [] },
      // env unset — defaults to dev
    },
    agentImpl: deployResponders(),
  })

  assert.equal(
    agentCalls(calls, 'deploy:rollout-dev').length, 0,
    'no deploy:rollout-dev agent may be dispatched when green.greenConfirmed=false — an unrun test suite must never reach AWS'
  )
  assert.equal(
    agentCalls(calls, 'deploy:ship-pr').length, 0,
    'the deploy mini opens no pull request — landing is the composite Settle step, and a PR is not deploy evidence'
  )
  assert.equal(result.deployedToDev, false, 'deployedToDev must be false')
  assert.equal(result.ledger.ok, false, 'ledger.ok must be false')
  const findings = (result.readiness && result.readiness.findings) || []
  assert.ok(
    findings.some((f) => /test/i.test(f) && /(unconfirmed|not run|not reported|unreported)/i.test(f)),
    `readiness.findings must name unconfirmed/unreported test results as the blocking reason; got: ${JSON.stringify(findings)}`
  )
})

// ─── D1-AC3 — empty evidence blocks ───────────────────────────────────────────
test('D1-AC3: greenConfirmed=true with empty evidence is treated as absence of evidence — same blocked outcome as AC2', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      green: { greenConfirmed: true, evidence: '', changedFiles: [] },
    },
    agentImpl: deployResponders(),
  })

  assert.equal(
    agentCalls(calls, 'deploy:rollout-dev').length, 0,
    'no deploy:rollout-dev dispatch: a true greenConfirmed flag with no supporting evidence string is not confirmation'
  )
  assert.equal(result.deployedToDev, false, 'deployedToDev must be false')
  assert.equal(result.ledger.ok, false, 'ledger.ok must be false')
})

// ─── D1-AC4 — missing green artifact blocks ───────────────────────────────────
test('D1-AC4: omitting the green key entirely blocks the rollout — absent test evidence is not an absent process artifact', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      // a.green omitted entirely -> green resolves to {}
    },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    }),
  })

  assert.equal(
    agentCalls(calls, 'deploy:rollout-dev').length, 0,
    'no deploy:rollout-dev dispatch when the green artifact is entirely absent'
  )
  assert.equal(result.deployedToDev, false, 'deployedToDev must be false')
})

// ─── D1-AC6 — uncertainty default preserved for process artifacts (regression guard) ──
test('D1-AC6: valid green + zero process artifacts still rolls out — the light-gate calibration is unchanged', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      env: 'dev',
      green: { greenConfirmed: true, evidence: '48 passed', changedFiles: ['svc/handler.py'] },
    },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    }),
  })

  assert.equal(result.readiness && result.readiness.ready, true, 'readiness.ready must be true')
  const rolloutIdx = agentCallIndex(calls, 'deploy:rollout-dev')
  assert.ok(rolloutIdx >= 0, 'deploy:rollout-dev must be dispatched')
  assert.equal(result.deployedToDev, true, 'the change must reach AWS dev')
  assert.equal(result.smokePassed, true, 'and the deployed endpoints must pass their smoke tests')
  const findings = (result.readiness && result.readiness.findings) || []
  assert.ok(
    !findings.some((f) => /finops|slo|runbook|pipeline/i.test(f)),
    'no finding may cite the absent FinOps/SLO/runbook/pipeline artifacts as a block'
  )
})
