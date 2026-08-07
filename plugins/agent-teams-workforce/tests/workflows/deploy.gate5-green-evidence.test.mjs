// ssbd-1xcs D1 — unrun test suite reaches AWS (deploy.js).
// Encodes acceptance criteria D1-AC1 .. D1-AC6.
//
// Defect under test: deploy.js builds the Gate 5 prompt from the facilitator's
// prose inventory only; green.greenConfirmed / green.evidence (required fields
// produced by tdd-green.js) are never read, so "tests not run / not reported"
// falls into the "When genuinely uncertain, RULE READY" default and the change
// deploys to AWS dev account 616930583457.
//
// The fake Gate 5 agent in these tests deliberately returns ready:true — the
// miscalibrated-uncertainty case — so blocking must come from deploy.js itself.
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
    'deploy:plan': { artifacts: [] },
    'deploy:smoke-author': { smokeTestFiles: ['smoke/test_fixed_behavior.py'] },
    'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    'deploy:strategy': { rolloutStyle: 'rolling', riskLevel: 'low' },
    'deploy:readiness-packet': {
      inventory: ['smoke tests AUTHORED AND SOUND', 'documentation PRESENT'],
      concerns: [],
    },
    // Simulates the enforcer resolving "no test evidence" via the uncertainty default.
    'deploy:gate5-verdict': { ready: true, findings: [] },
    'deploy:ship-pr': { prOpened: true, prUrl: 'https://github.example/pr/1', gatesPassed: true },
    'deploy:rollout-dev': { deployed: true, stacks: ['DevStack'], smokePassed: true },
    ...overrides,
  }
  return (call) =>
    Object.prototype.hasOwnProperty.call(base, call.label) ? base[call.label] : { summary: 'ok' }
}

function gate5Prompt(calls) {
  const g5 = agentCalls(calls, 'deploy:gate5-verdict')
  assert.equal(g5.length, 1, 'expected exactly one deploy:gate5-verdict dispatch')
  return g5[0].prompt
}

// ─── D1-AC1 — evidence is read ────────────────────────────────────────────────
test('D1-AC1: Gate 5 prompt carries green.evidence verbatim and a CONFIRMED GREEN statement sourced from the green artifact', async () => {
  const EVIDENCE = '12 passed, 0 failed (pytest -q)'
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      green: { greenConfirmed: true, evidence: EVIDENCE, changedFiles: ['svc/handler.py'] },
    },
    agentImpl: deployResponders({
      'deploy:cdk-validate': {
        applicable: false, synthValid: false, driftDetected: false,
        details: 'deploys via s3 sync; infrastructure owned by web-infra',
      },
      // Inventory deliberately says NOTHING about unit/integration tests, so any
      // CONFIRMED GREEN statement in the prompt can only come from the green artifact.
      'deploy:readiness-packet': {
        inventory: ['smoke tests AUTHORED AND SOUND', 'documentation PRESENT'],
        concerns: [],
      },
    }),
  })

  const prompt = gate5Prompt(calls)
  assert.ok(
    prompt.includes(EVIDENCE),
    `Gate 5 prompt must contain the literal green.evidence string '${EVIDENCE}' — the enforcer is currently starved of test evidence`
  )
  assert.match(
    prompt,
    /CONFIRMED GREEN/i,
    'Gate 5 prompt must state that unit/integration tests are CONFIRMED GREEN, sourced from the green artifact (the fixture inventory mentions no tests)'
  )

  // Source-text clause of D1-AC1: deploy.js must actually read the machine-checkable fields.
  const src = readWorkflowSource(DEPLOY_JS)
  assert.ok(
    src.includes('green.greenConfirmed'),
    'deploy.js must read green.greenConfirmed (grep currently returns zero occurrences)'
  )
  assert.ok(
    src.includes('green.evidence'),
    'deploy.js must read green.evidence (grep currently returns zero occurrences)'
  )
})

// ─── D1-AC2 — unconfirmed green blocks ────────────────────────────────────────
test('D1-AC2: greenConfirmed=false blocks the pipeline — no ship, no rollout, ledger not ok, findings name the unconfirmed tests', async () => {
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
    'no deploy:ship-pr agent may be dispatched when green.greenConfirmed=false'
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
      'deploy:readiness-packet': {
        inventory: ['smoke tests PRESENT', 'documentation PRESENT'],
        concerns: [],
      },
    }),
  })

  assert.equal(
    agentCalls(calls, 'deploy:rollout-dev').length, 0,
    'no deploy:rollout-dev dispatch when the green artifact is entirely absent'
  )
  assert.equal(result.deployedToDev, false, 'deployedToDev must be false')
})

// ─── D1-AC5 — the third state is named in the prompt ──────────────────────────
test('D1-AC5: the BLOCK clause names not-run/not-reported tests, and the RULE READY default is scoped away from test evidence', async () => {
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      green: { greenConfirmed: true, evidence: '12 passed, 0 failed (pytest -q)', changedFiles: ['svc/handler.py'] },
    },
    agentImpl: deployResponders(),
  })
  const prompt = gate5Prompt(calls)

  const blockIdx = prompt.search(/BLOCK on/i)
  assert.ok(blockIdx >= 0, 'Gate 5 prompt must contain a BLOCK enumeration')
  const doNotIdx = prompt.indexOf('DO NOT BLOCK', blockIdx)
  const blockClause = prompt.slice(blockIdx, doNotIdx > blockIdx ? doNotIdx : blockIdx + 500)
  assert.match(
    blockClause,
    /not run|not reported|unreported|unconfirmed/i,
    `the BLOCK clause must explicitly name the not-run/not-reported third state; BLOCK clause was: ${JSON.stringify(blockClause)}`
  )

  const idx = prompt.indexOf('When genuinely uncertain, RULE READY')
  assert.ok(idx >= 0, "the calibration sentence 'When genuinely uncertain, RULE READY' must be present (its scoping is under test, not its existence)")
  const window = prompt.slice(Math.max(0, idx - 400), idx + 400)
  assert.match(
    window,
    /(does not|do not|doesn't|never|not)\s+(apply|extend|cover)|except/i,
    'an adjacent clause must scope the uncertainty default (e.g. "does not apply ...")'
  )
  assert.match(
    window,
    /unit|integration|test/i,
    'the scoping clause must reference unit/integration test evidence'
  )
  assert.match(
    window,
    /missing|unconfirmed|unreported|not run|absent/i,
    'the scoping clause must exclude missing/unconfirmed test evidence from the uncertainty default'
  )
})

// ─── D1-AC6 — uncertainty default preserved for process artifacts (regression guard) ──
test('D1-AC6: valid green + zero process artifacts still ships and rolls out — the light-gate calibration is unchanged', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: {
      contract: CONTRACT,
      env: 'dev',
      green: { greenConfirmed: true, evidence: '48 passed', changedFiles: ['svc/handler.py'] },
    },
    agentImpl: deployResponders({
      'deploy:plan': { artifacts: [] }, // no FinOps, SLO, runbook, or pipeline authored
      'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    }),
  })

  assert.equal(result.readiness && result.readiness.ready, true, 'readiness.ready must be true')
  const shipIdx = agentCallIndex(calls, 'deploy:ship-pr')
  const rolloutIdx = agentCallIndex(calls, 'deploy:rollout-dev')
  assert.ok(shipIdx >= 0, 'deploy:ship-pr must be dispatched')
  assert.ok(rolloutIdx >= 0, 'deploy:rollout-dev must be dispatched')
  assert.ok(shipIdx < rolloutIdx, 'deploy:ship-pr must be dispatched before deploy:rollout-dev')
  const findings = (result.readiness && result.readiness.findings) || []
  assert.ok(
    !findings.some((f) => /finops|slo|runbook|pipeline/i.test(f)),
    'no finding may cite the absent FinOps/SLO/runbook/pipeline artifacts as a block'
  )
})
