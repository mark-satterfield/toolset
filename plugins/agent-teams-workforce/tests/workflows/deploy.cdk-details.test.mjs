// ssbd-1xcs D5 — cdk.details collected then discarded (deploy.js).
// Encodes acceptance criteria D5-AC1 .. D5-AC5 (numbered AC23-AC27 in the bead).
//
// Defect under test: the four-field cdk result (applicable, synthValid, driftDetected,
// details) was collapsed into one sentence and `details` had no reader, so a
// not-applicable claim counted with zero supporting evidence. Readiness is now computed
// by deploy.js, and a not-applicable claim counts only with its details.
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
    'deploy:smoke-author': { smokeTestFiles: ['smoke/test_site.py'] },
    'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    'deploy:rollout-dev': { deployed: true, stacks: [], smokePassed: true, smokeCases: [{ name: 'site', passed: true, output: 'ok' }] },
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

// ─── D5-AC1 (AC23) — a substantiated not-applicable counts as a valid synth ──
// Gate 5 readiness is computed by deploy.js; the details are the evidence that makes
// a not-applicable claim count.
test('D5-AC1: applicable=false with details — cdkSynthOk holds, readiness carries no CDK finding', async () => {
  const DETAILS =
    'No cdk.json or CDK app; deploys via `npm run build` then `aws s3 sync` to bucket skillspoke-web-dev plus a CloudFront invalidation; infrastructure is owned by SkillSpoke-web-infra'
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: false, synthValid: false, driftDetected: false, details: DETAILS },
    }),
  })
  assert.equal(result.cdkSynthOk, true)
  assert.equal(result.readiness.ready, true)
  assert.ok(!result.readiness.findings.some((f) => /CDK/.test(f)), 'no CDK finding for a substantiated not-applicable')
})

// ─── D5-AC2 (AC24) — unsubstantiated not-applicable is not absolution ─────────
test('D5-AC2: applicable=false with empty/omitted details blocks readiness with a finding naming the missing details', async () => {
  for (const cdkResult of [
    { applicable: false, synthValid: false, driftDetected: false, details: '' },
    { applicable: false, synthValid: false, driftDetected: false }, // details omitted
  ]) {
    const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
      args: { contract: CONTRACT, green: VALID_GREEN },
      agentImpl: deployResponders({ 'deploy:cdk-validate': cdkResult }),
    })
    const which = 'details' in cdkResult ? 'empty-string details' : 'omitted details'
    assert.equal(result.cdkSynthOk, false, `(${which}) an unsubstantiated not-applicable claim is not a valid synth`)
    assert.equal(result.readiness.ready, false, `(${which})`)
    assert.ok(
      result.readiness.findings.some((f) => /NOT APPLICABLE/.test(f) && /no supporting details/.test(f)),
      `(${which}) the finding must name the missing details; got ${JSON.stringify(result.readiness.findings)}`
    )
    assert.equal(agentCalls(calls, 'deploy:rollout-dev').length, 0, `(${which}) nothing rolls out`)
  }
})

// ─── D5-AC3 (AC25) — details reaches the rollout prompt ───────────────────────
test('D5-AC3: the rollout prompt carries the cdk details verbatim so the deployer is told the real deploy mechanism', async () => {
  const DETAILS =
    'Deploys via `npm run build` + `aws s3 sync` to skillspoke-web-dev; CloudFront invalidation required; infrastructure owned by SkillSpoke-web-infra'
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: false, synthValid: false, driftDetected: false, details: DETAILS },
    }),
  })
  const prompt = singlePrompt(calls, 'deploy:rollout-dev')

  assert.ok(
    prompt.includes(DETAILS),
    'the deploy:rollout-dev prompt must contain the cdk details string verbatim instead of asking the agent to rediscover the deploy path'
  )
})

// ─── D5-AC4 (AC26) — applicable=true reports the broken synth and drift with details ──
test('D5-AC4: applicable=true with a broken synth — the findings carry the details and the drift, and no NOT APPLICABLE language', async () => {
  const DETAILS = 'synth failed: missing context value vpc-id'
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: true, synthValid: false, driftDetected: true, details: DETAILS },
    }),
  })
  const findings = result.readiness.findings
  assert.equal(result.readiness.ready, false, 'a broken synth legitimately blocks')
  assert.ok(findings.some((f) => /CDK synth is not valid/.test(f) && f.includes(DETAILS)), 'the synth finding must carry the details')
  assert.ok(findings.some((f) => /drift detected/.test(f)), 'drift must be reported')
  assert.ok(!findings.some((f) => /NOT APPLICABLE/.test(f)), 'no NOT APPLICABLE language when applicable=true')
  assert.equal(result.cdkDriftDetected, true)
})

// ─── cdkSynthOk / smokeTestFiles are HOISTED so the outer Gate 5 can MEASURE them ──
//
// The composite's Gate 5 carries "CDK synth valid" and "Smoke tests present" as criteria.
// Both values existed here already but only nested inside `cdk` and `smoke`, where a flat
// deterministic check cannot reach — so both were adjudicated in prose by a full enforcer
// turn, per deploy iteration. This is the same fix already applied to `smokePassed`, and
// it is the SAFETY CONDITION for making that gate deterministic-only: a gate that stops
// asserting synth validity is worse than a slower gate.

test('cdkSynthOk and smokeTestFiles are top-level fields a flat gate check can read', async () => {
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders(),
  })
  assert.equal(result.cdkSynthOk, true, 'a valid synth must be readable without walking into result.cdk')
  assert.deepEqual(result.smokeTestFiles, ['smoke/test_site.py'], 'the smoke file list must be flat, not nested in result.smoke')
})

test('a broken synth is cdkSynthOk=false at the top level, and a not-applicable repo is true', async () => {
  const broken = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: true, synthValid: false, driftDetected: false },
    }),
  })
  assert.equal(broken.result.cdkSynthOk, false, 'a repo that HAS a CDK app and cannot synth must fail the check')

  const na = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({
      'deploy:cdk-validate': { applicable: false, synthValid: false, driftDetected: false, details: 'no cdk.json; deploys by s3 sync' },
    }),
  })
  assert.equal(na.result.cdkSynthOk, true, 'a repo that owns no CDK app cannot fail a synth it does not have')

  const missing = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({ 'deploy:cdk-validate': null }),
  })
  assert.equal(missing.result.cdkSynthOk, false, 'no cdk result at all is unknown, and unknown is never absolution')
})

// ─── The removed pre-rollout sessions ────────────────────────────────────────

test('no deployment-lead, no strategy decider, no readiness facilitator and no Gate 5 enforcer on a dev deploy', async () => {
  const { calls, result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders(),
  })
  for (const label of ['deploy:plan', 'deploy:strategy', 'deploy:readiness-packet', 'deploy:gate5-verdict']) {
    assert.equal(agentCalls(calls, label).length, 0, `${label} must not be dispatched — readiness is computed by the script`)
  }
  assert.equal(result.readiness.ready, true)
  assert.equal(result.deployedToDev, true, 'and the deploy still happens')
})

// ─── D5-AC5 (AC27) — no cdk result at all (regression guard) ─────────────────
test('D5-AC5: a null cdk result is reported as nothing, never as not-applicable absolution', async () => {
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: VALID_GREEN },
    agentImpl: deployResponders({ 'deploy:cdk-validate': null }),
  })
  const findings = result.readiness.findings
  assert.equal(result.readiness.ready, false)
  assert.ok(findings.some((f) => /CDK validation reported nothing/.test(f)), `got ${JSON.stringify(findings)}`)
  assert.ok(!findings.some((f) => /NOT APPLICABLE/.test(f)), 'no NOT APPLICABLE line for a missing cdk result')
})
