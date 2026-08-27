// ssbd-1xcs D5 — cdk.details collected then discarded (deploy.js).
// Encodes acceptance criteria D5-AC1 .. D5-AC5 (numbered AC23-AC27 in the bead).
//
// Defect under test: deploy.js:98-102 collapses the four-field cdk result
// (applicable, synthValid, driftDetected, details) into a single fixed sentence.
// `details` is demanded by the prompt (deploy.js:77) and defined in the schema
// (deploy.js:92) but has no reader, so Gate 5 receives "CDK: NOT APPLICABLE ...
// MUST NOT count against readiness" with zero supporting evidence — an unaudited
// claim that defeats the anti-spoofing guard at deploy.js:72-73.
//
// All dispatches are in-process fakes; nothing reaches AWS.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript, agentCalls } from './helpers/run-workflow.mjs'

const DEPLOY_JS = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', '..', 'workflows', 'deploy.js'
)

const CONTRACT = {
  repoPath: '/tmp/fixture-repo',
  bead: { id: 'ssbd-1xcs', title: 'cdk details fixture' },
}

// A VALID green artifact in every fixture: these tests isolate D5 and must keep
// working after the D1 fix adds a green-evidence guard upstream of Gate 5.
const VALID_GREEN = { greenConfirmed: true, evidence: '12 passed, 0 failed (pytest -q)', changedFiles: ['app/page.tsx'] }

function deployResponders(overrides = {}) {
  const base = {
    'deploy:plan': { artifacts: [] },
    'deploy:smoke-author': { smokeTestFiles: ['smoke/test_site.py'] },
    'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    'deploy:strategy': { rolloutStyle: 'rolling', riskLevel: 'low' },
    'deploy:readiness-packet': {
      inventory: ['unit/integration tests GREEN', 'smoke tests AUTHORED AND SOUND', 'documentation PRESENT'],
      concerns: [],
    },
    'deploy:gate5-verdict': { ready: true, findings: [] },
    'deploy:rollout-dev': { deployed: true, stacks: [], smokePassed: true },
    ...overrides,
  }
  return (call) =>
    Object.prototype.hasOwnProperty.call(base, call.label) ? base[call.label] : { summary: 'ok' }
}

function singlePrompt(calls, label) {
  const found = agentCalls(calls, label)
  assert.equal(found.length, 1, `expected exactly one ${label} dispatch`)
  return found[0].prompt
}

// ─── D5-AC1 (AC23) — details reaches Gate 5 ───────────────────────────────────
test('D5-AC1: applicable=false with details — Gate 5 prompt carries the details verbatim, adjacent to the NOT APPLICABLE line', async () => {
  const DETAILS =
    'No cdk.json or CDK app; deploys via `npm run build` then `aws s3 sync` to bucket skillspoke-web-dev plus a CloudFront invalidation; infrastructure is owned by SkillSpoke-web-infra'
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: false, synthValid: false, driftDetected: false, details: DETAILS },
    }),
  })
  const prompt = singlePrompt(calls, 'deploy:gate5-verdict')

  assert.ok(
    prompt.includes(DETAILS),
    'Gate 5 prompt must contain the cdk details string verbatim — it is currently collected then discarded'
  )
  const naIdx = prompt.indexOf('CDK: NOT APPLICABLE')
  assert.ok(naIdx >= 0, "Gate 5 prompt must contain the 'CDK: NOT APPLICABLE' line")
  const detIdx = prompt.indexOf(DETAILS)
  assert.ok(
    Math.abs(detIdx - naIdx) <= 800,
    `details must sit adjacent to the NOT APPLICABLE line so the claim travels with its evidence (distance was ${Math.abs(detIdx - naIdx)} chars)`
  )
})

// ─── D5-AC2 (AC24) — unsubstantiated not-applicable is marked ─────────────────
test('D5-AC2: applicable=false with empty/omitted details is marked UNSUBSTANTIATED and gets no absolution', async () => {
  for (const cdkResult of [
    { applicable: false, synthValid: false, driftDetected: false, details: '' },
    { applicable: false, synthValid: false, driftDetected: false }, // details omitted
  ]) {
    const { calls } = await runWorkflowScript(DEPLOY_JS, {
      args: { contract: CONTRACT, green: VALID_GREEN },
      agentImpl: deployResponders({ 'deploy:cdk-validate': cdkResult }),
    })
    const prompt = singlePrompt(calls, 'deploy:gate5-verdict')
    const which = 'details' in cdkResult ? 'empty-string details' : 'omitted details'

    assert.match(
      prompt,
      /UNSUBSTANTIATED/i,
      `(${which}) the CDK line must state the not-applicable claim is UNSUBSTANTIATED when no details are supplied`
    )
    assert.match(
      prompt,
      /unverified/i,
      `(${which}) the prompt must instruct the enforcer to treat the claim as unverified`
    )
    assert.ok(
      !prompt.includes('MUST NOT count against readiness'),
      `(${which}) the absolving phrase 'MUST NOT count against readiness' must not be emitted for an unsubstantiated claim`
    )
  }
})

// ─── D5-AC3 (AC25) — details reaches the rollout prompt ───────────────────────
test('D5-AC3: single-repo rollout prompt carries the cdk details verbatim so the deployer is told the real deploy mechanism', async () => {
  const DETAILS =
    'Deploys via `npm run build` + `aws s3 sync` to skillspoke-web-dev; CloudFront invalidation required; infrastructure owned by SkillSpoke-web-infra'
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN }, // multiRepo not set -> false
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: false, synthValid: false, driftDetected: false, details: DETAILS },
    }),
  })
  const prompt = singlePrompt(calls, 'deploy:rollout-dev')

  assert.ok(
    !prompt.includes('MULTIPLE repos/stacks'),
    'fixture must exercise the single-repo branch'
  )
  assert.ok(
    prompt.includes(DETAILS),
    'the deploy:rollout-dev prompt must contain the cdk details string verbatim instead of asking the agent to rediscover the deploy path'
  )
})

// ─── D5-AC4 (AC26) — applicable=true still reports synth, drift, and details ──
test('D5-AC4: applicable=true reports synthValid/drift AND the details string, with no NOT APPLICABLE language', async () => {
  const DETAILS = 'synth failed: missing context value vpc-id'
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: true, synthValid: false, driftDetected: true, details: DETAILS },
      'deploy:gate5-verdict': { ready: false, findings: ['broken synth'] }, // a broken synth legitimately blocks
    }),
  })
  const prompt = singlePrompt(calls, 'deploy:gate5-verdict')

  assert.ok(prompt.includes('synthValid=false'), "prompt must report 'synthValid=false'")
  assert.ok(prompt.includes('drift=true'), "prompt must report 'drift=true'")
  assert.ok(
    prompt.includes(DETAILS),
    'prompt must carry the details string for the applicable=true arm as well'
  )
  assert.ok(
    !prompt.includes('CDK: NOT APPLICABLE'),
    'no NOT APPLICABLE language may be emitted when applicable=true'
  )
})

// ─── D5-AC5 (AC27) — no cdk result at all (regression guard) ─────────────────
test('D5-AC5: a null cdk result yields the CDK: not reported line and no NOT APPLICABLE absolution', async () => {
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({ 'deploy:cdk-validate': null }),
  })
  const prompt = singlePrompt(calls, 'deploy:gate5-verdict')

  assert.ok(prompt.includes('CDK: not reported'), "prompt must contain 'CDK: not reported'")
  assert.ok(
    !prompt.includes('CDK: NOT APPLICABLE'),
    'no NOT APPLICABLE line for a missing cdk result'
  )
  assert.ok(
    !prompt.includes('MUST NOT count against readiness'),
    'no absolution for a missing cdk result'
  )
})
