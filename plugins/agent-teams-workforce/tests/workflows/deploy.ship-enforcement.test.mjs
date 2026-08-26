// Ship enforcement — the PR step must be able to run, must run, and must be believed
// only when it produces a real PR URL.
//
// Three defects made "work is shipped" unfalsifiable, and each gets a test here:
//   1. the only PR-opening step in the pipeline was dispatched to `deployment-lead`,
//      whose frontmatter denies it Bash and Write — it could only refuse or fabricate;
//   2. the step was switched off by the deploy TARGET (`env !== 'dev'`) and by a failed
//      readiness review — precisely the moments work is most likely to strand;
//   3. `prOpened` was the shipping agent's own boolean about its own work, with nothing
//      checking it, so a hallucinated `true` satisfied every downstream consumer.
//
// Every dispatch below is an in-process fake; no test here reaches GitHub or AWS.

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
  bead: { id: 'ssbd-ship', title: 'ship enforcement fixture' },
}

const GREEN = { greenConfirmed: true, evidence: '42 passed', changedFiles: ['a.py'] }

function responders(overrides = {}) {
  const base = {
    'deploy:plan': { artifacts: [] },
    'deploy:smoke-author': { smokeTestFiles: ['smoke/test_x.py'] },
    'deploy:cdk-validate': { applicable: true, synthValid: true, driftDetected: false },
    'deploy:strategy': { rolloutStyle: 'rolling', riskLevel: 'low' },
    'deploy:readiness-packet': { inventory: ['smoke tests AUTHORED AND SOUND'], concerns: [] },
    'deploy:gate5-verdict': { ready: true, findings: [] },
    'deploy:ship-pr': {
      prOpened: true,
      prUrl: 'https://github.com/satteritsik/fixture/pull/7',
      gatesPassed: true,
    },
    'deploy:rollout-dev': { deployed: true, stacks: ['DevStack'], smokePassed: true },
    ...overrides,
  }
  return (call) =>
    Object.prototype.hasOwnProperty.call(base, call.label) ? base[call.label] : { summary: 'ok' }
}

const shipCall = (calls) => agentCalls(calls, 'deploy:ship-pr')[0]

// ── 1. the step must go to an agent that can actually perform it ───────────────
test('the ship step is dispatched to a Bash-capable agent, never to deployment-lead', async () => {
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders(),
  })

  const ship = shipCall(calls)
  assert.ok(ship, 'the ship step must be dispatched')
  assert.notEqual(
    ship.opts.agentType, 'agent-teams-workforce:deployment-lead',
    'deployment-lead has no Bash and no Write — it cannot run git, ruff, cdk synth or skillspoke-pr'
  )
  assert.equal(
    ship.opts.agentType, 'agent-teams-workforce:github-actions-pipeline-implementer',
    'the ship step needs an agent on the Deployment team that carries Bash'
  )
})

// ── 2. shipping is not a function of the deploy target ────────────────────────
test('a non-dev target still opens the PR — shipping has no environment dimension', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN, env: 'qa' },
    agentImpl: responders(),
  })

  assert.equal(agentCalls(calls, 'deploy:ship-pr').length, 1, 'the PR must still be opened')
  assert.equal(
    agentCalls(calls, 'deploy:rollout-dev').length, 0,
    'and nothing outward-facing may roll out from here'
  )
  assert.equal(result.prOpened, true)
})

test('a failed readiness review still opens the PR, and still blocks the rollout', async () => {
  const { result, calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders({ 'deploy:gate5-verdict': { ready: false, findings: ['drift'] } }),
  })

  assert.equal(agentCalls(calls, 'deploy:ship-pr').length, 1)
  assert.equal(agentCalls(calls, 'deploy:rollout-dev').length, 0)
  assert.equal(result.deployedToDev, false)
  assert.equal(result.ledger.ok, false, 'a failed readiness review is still a failed run')
})

// ── 3. prOpened is derived from the URL, not taken on the agent's word ────────
test('prOpened:true with no URL is not a PR', async () => {
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders({ 'deploy:ship-pr': { prOpened: true, gatesPassed: true } }),
  })

  assert.equal(result.prOpened, false, 'a boolean an agent reports about its own work is not evidence')
  assert.equal(result.prUrl, null)
  assert.equal(result.ledger.ok, false, 'and the ledger must not call that run ok')
})

test('prOpened:true with a URL that is not a PR URL is not a PR', async () => {
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders({
      'deploy:ship-pr': {
        prOpened: true,
        prUrl: 'https://github.com/satteritsik/fixture/tree/feat/x',
        gatesPassed: true,
      },
    }),
  })

  assert.equal(result.prOpened, false, 'a branch URL is not a pull request')
  assert.equal(result.prUrl, null)
})

test('a real PR URL is reported verbatim and trimmed', async () => {
  const { result } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders({
      'deploy:ship-pr': {
        prOpened: true,
        prUrl: '  https://github.com/satteritsik/fixture/pull/7  ',
        gatesPassed: true,
      },
    }),
  })

  assert.equal(result.prOpened, true)
  assert.equal(result.prUrl, 'https://github.com/satteritsik/fixture/pull/7')
  assert.equal(result.ledger.prUrl, 'https://github.com/satteritsik/fixture/pull/7')
})

// ── the prompt must be runnable in the tree the composite pointed at ──────────
test('the ship prompt pins the agent to contract.repoPath and forbids the unreviewed PR path', async () => {
  const { calls } = await runWorkflowScript(DEPLOY_JS, {
    args: { contract: CONTRACT, green: GREEN },
    agentImpl: responders(),
  })

  const { prompt } = shipCall(calls)
  assert.match(prompt, /git -C "\/tmp\/fixture-repo"/, 'every git command must be pinned to the contract repo path')
  assert.match(prompt, /skillspoke-pr/, 'the PR must be opened with the sanctioned wrapper')
  assert.match(prompt, /--no-verify/, 'the no-bypass rule must still be stated')
  assert.doesNotMatch(
    prompt, /KNOWN QUIRK/,
    'the exit-status workaround must be gone once the wrapper is fixed — exit status is evidence again'
  )
  assert.doesNotMatch(
    prompt, /no repo has/,
    'the stale fleet-wide CI assertion must not be restated as fact'
  )
})
