export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy. Refuses a contract with no repoPath. The smoke-test-author writes a smoke suite (or the smokeTestFiles passed in are reused), then one cdk-stack-author session deploys the one repository the contract names to AWS dev and runs the smoke tests against the deployed endpoints. Returns { deployedToDev, smokePassed, smokeTestFiles, rollout, deployedToProd: false, ledger }, with dispatchFailed when a session returned nothing. Opens no pull request; never deploys to qa or prod.',
  phases: [{ title: 'Deploy-readiness', detail: 'author smoke tests, deploy to AWS dev, run the smoke tests' }],
}
const dispatchFailures = []
// Returns the recorded dispatch failures of the named phases, or all of them when none is named.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
// Returns 'transient' for an API overload, rate limit or network error, otherwise 'deterministic'.
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  return TRANSIENT_ERROR_TEXT.test(text) ? 'transient' : 'deterministic'
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const settleSleep = (ms) => (SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve())
// Returns the wait before retry `attempt`: 5s tripled per attempt, capped at 300s, scaled into [50%, 100%) by a hash of the dispatch.
function transientWaitMs(name, attempt) {
  const key = `${name}#${attempt}`
  let h = 2166136261
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  const scheduled = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
// Calls agent() and returns its result. A transient failure is retried with backoff until it clears
// (three attempts when no timer exists); any other failure returns null and is recorded in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, o)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      const entry = {
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        note: `${name} ended without a structured result (${cause}): ${message.slice(0, 160)}`,
      }
      dispatchFailures.push(entry)
      mine.push(entry)
      log(entry.note)
      if (cause !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) return null
      const wait = transientWaitMs(name, attempt)
      waitedMs += wait
      log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s (${Math.round(waitedMs / 1000)}s waited)`)
      await settleSleep(wait)
      continue
    }
    if (out) {
      for (const entry of mine) {
        const at = dispatchFailures.indexOf(entry)
        if (at >= 0) dispatchFailures.splice(at, 1)
      }
      return out
    }
    dispatchFailures.push({ ...who, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: `${name} returned nothing` })
    log(`${name} returned nothing`)
    return null
  }
}

// args: { contract, green?, feedback?, smokeTestFiles?, leaseScope? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const beadId = (c.bead && c.bead.id) || null
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
if (!repo) {
  const why = 'the contract names no repoPath, so there is no tree to deploy from'
  return {
    ok: false,
    phaseBlocked: true,
    blockedReason: why,
    deployedToDev: false,
    smokePassed: false,
    smokeTestFiles: [],
    deployedToProd: false,
    blocked: [why],
    ledger: { phase: 'deploy', beadId, chosen: [], mode: 'refused', ok: false },
  }
}
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`
const changeLabel = c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'
const DEV_ACCOUNT = '616930583457'
const DEV_REGION = 'us-east-1'

phase('Deploy-readiness')

const priorSmokeFiles = (Array.isArray(a.smokeTestFiles) ? a.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)
const smoke = priorSmokeFiles.length
  ? { smokeTestFiles: priorSmokeFiles, reused: true }
  : await settleAgent(
      `Author post-deployment smoke tests that verify the fixed behavior against a deployed endpoint. Do not deploy.

${pinTree}

Change: ${changeLabel}
Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}${feedback}`,
      {
        label: 'deploy:smoke-author',
        phase: 'Deploy-readiness',
        agentType: 'agent-teams-workforce:smoke-test-author',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['smokeTestFiles'],
          properties: {
            smokeTestFiles: { type: 'array', items: { type: 'string' } },
            notes: { type: 'string' },
          },
        },
      }
    )
if (!smoke) {
  return {
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Deploy-readiness'),
    reason: 'the smoke-test author returned nothing, so nothing was deployed',
    env: 'dev',
    smokeTestFiles: [],
    deployedToDev: false,
    smokePassed: false,
    deployedToProd: false,
    ledger: { phase: 'deploy', stage: 'not-deployed', beadId, chosen: ['smoke-test-author'], mode: 'fixed', env: 'dev', ok: false },
  }
}
const smokeTestFiles = (Array.isArray(smoke.smokeTestFiles) ? smoke.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)

const rollout = await settleAgent(
  `Deploy this change to the DEV environment (AWS account ${DEV_ACCOUNT}, ${DEV_REGION}).

${pinTree}

Deploy just this repo against dev, using the mechanism this repo actually deploys by: \`cdk deploy\` of the affected stack(s) when the repo has a CDK app; otherwise the repo's own deploy path (Taskfile, package.json scripts, deploy script). For a static site that is a build, \`aws s3 sync\` and a CloudFront invalidation; wait for the invalidation to report Completed before smoke-testing. A task NAMED cdk:deploy may run no CDK operation — read what it executes.

Then RUN the smoke tests (${smokeTestFiles.join(', ') || 'none were authored'} — paths relative to the tree above) against the deployed endpoints and report their literal output. A deploy that succeeds while its smoke test fails is a FAILED rollout.

Report \`deployed\`, \`smokePassed\`, and \`smokeCases\`: one row per smoke case with its name, whether it passed, and its literal output. Also report the stacks you changed and the commit SHA you deployed (\`git -C "${repo}" rev-parse HEAD\`).

HARD LIMITS: dev ONLY — never qa, never prod. Do not delete or replace data. If a deploy errors, stop and report where and why.`,
  {
    label: 'deploy:rollout-dev',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:cdk-stack-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['deployed', 'smokePassed', 'smokeCases'],
      properties: {
        deployed: { type: 'boolean' },
        smokePassed: { type: 'boolean' },
        smokeCases: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['name', 'passed', 'output'],
            properties: { name: { type: 'string' }, passed: { type: 'boolean' }, output: { type: 'string' } },
          },
        },
        stacks: { type: 'array', items: { type: 'string' } },
        commitSha: { type: 'string' },
        evidence: { type: 'string' },
        findings: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

const deployedToDev = !!(rollout && rollout.deployed === true)
const smokePassed = !!(rollout && rollout.smokePassed === true)
const ledger = {
  phase: 'deploy',
  stage: deployedToDev ? 'deployed-to-dev' : 'not-deployed',
  beadId,
  chosen: [...(priorSmokeFiles.length ? [] : ['smoke-test-author']), 'cdk-stack-author'],
  mode: 'fixed',
  env: 'dev',
  deployedToDev,
  smokePassed,
  rolledOut: deployedToDev,
  ok: deployedToDev && smokePassed,
}
const dispatchFailure = rollout
  ? {}
  : { dispatchFailed: true, dispatchFailures: dispatchDeaths('Deploy-readiness'), reason: 'the dev rollout returned nothing' }

return {
  ...dispatchFailure,
  smoke,
  rollout,
  env: 'dev',
  smokeTestFiles,
  deployedToDev,
  smokePassed,
  deployedToProd: false,
  ledger,
}
