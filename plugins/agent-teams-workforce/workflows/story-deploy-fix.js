export const meta = {
  name: 'story-deploy-fix',
  description:
    "Story deploy fix loop, one pass — the only agent step of a Story's deploy. The Story's package publish, `cdk synth`, `cdk deploy` to AWS dev, or the verification that every stack reached CREATE_COMPLETE or UPDATE_COMPLETE, failed. One cdk-stack-author session diagnoses the failure from its output, fixes the CDK (or whatever the deploy needs) in the Story's worktree, runs the repository's synth assertion tests and updates any test the fix proves wrong; then the fix is committed to the Story branch. A fix that changes no file returns stage no-change and commits nothing. It never deploys, never re-enters Green and opens no pull request: the caller redeploys and verifies. Returns { ok, stage, beadId, headline, detailPath, testsPassed, changedFiles, commit }.",
  phases: [
    { title: 'Fix', detail: 'diagnose the deploy failure and fix it on the Story branch; the synth assertion tests pass' },
    { title: 'Commit', detail: 'commits the fix to the Story branch' },
  ],
}

// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null on any other failure.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
const isTransient = (err) => {
  const e = err && typeof err === 'object' ? err : {}
  const text = String(e.message || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return false
  const status = Number(e.status || e.statusCode || (e.response && e.response.status))
  return TRANSIENT_STATUS.has(status) || TRANSIENT_ERROR_TEXT.test(text)
}
async function settleAgent(prompt, opts) {
  const call = opts || {}
  const name = call.label || call.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, call)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err)
      if (isTransient(err) && typeof setTimeout === 'function') {
        const wait = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
        log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s — ${message.slice(0, 160)}`)
        await new Promise((resolve) => setTimeout(resolve, wait))
        continue
      }
      log(`${name}: ended without a structured result — ${message.slice(0, 160)}`)
      return null
    }
  }
}

// args: {
//   beadId: string (the Story), story: { id, title? }, repoPath: string (the Story's worktree),
//   branch: string, defaultBranch?: string, attempt: number,
//   failure: { step: 'publish' | 'synth' | 'deploy' | 'verify', output: string, stacks?: [{ name, status, reason? }] }
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const story = a.story && typeof a.story === 'object' ? a.story : {}
const beadId = String(a.beadId || story.id || '').trim()
const repo = String(a.repoPath || '').trim().replace(/\/+$/, '')
const failure = a.failure && typeof a.failure === 'object' ? a.failure : {}
const attempt = Number(a.attempt) || 1
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'

const handback = (ok, stage, headline, extra) => ({ ok, stage, beadId: beadId || null, headline: String(headline || ''), detailPath: null, ...(extra || {}) })

if (!beadId) return handback(false, 'input', 'no Story id supplied')
if (!repo) return handback(false, 'input', `no worktree supplied for Story ${beadId}`)

const stacks = (Array.isArray(failure.stacks) ? failure.stacks : [])
  .filter((s) => s && typeof s === 'object')
  .map((s) => `  - ${s.name}: ${s.status || 'no status'}${s.reason ? ` — ${s.reason}` : ''}`)
  .join('\n')

phase('Fix')
const fix = await settleAgent(
  `The deploy of Story ${beadId}${story.title ? ` (${story.title})` : ''} to AWS dev failed, attempt ${attempt}. Diagnose the failure and fix it on the Story's branch. Do not deploy: the caller redeploys and verifies once you return.

PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}
Branch: ${a.branch || '(the branch checked out in that tree)'}

What failed: ${
  {
    verify: 'deployment verification — a stack did not reach CREATE_COMPLETE or UPDATE_COMPLETE',
    publish: "publishing the repository's package to CodeArtifact",
    synth: '`cdk synth`',
  }[failure.step] || '`cdk deploy`'
}
${stacks ? `Stacks:\n${stacks}\n` : ''}Output:
${String(failure.output || '(no output was captured)').slice(-12000)}

1. Find the cause in this output and in the CloudFormation stack events it points to (\`aws cloudformation describe-stack-events\`, read-only).
2. Fix the CDK, or whatever else the deploy needs, in this tree. A value one stack passes to another goes by the cross-stack mechanism the repository's stacks already use.
3. Run the repository's synth assertion tests. Where the fix proves a test wrong, correct the test so it asserts what the fixed template must contain; never weaken a test to make it pass.
4. Do not commit, push, deploy, publish a package or open a pull request, and never run \`cdk deploy\` or \`cdk destroy\`: the caller commits your change, then publishes and deploys.
5. When nothing in this tree can fix the failure (it lies outside the repository), change no file and say why in the cause; an empty changedFiles stops the deploy instead of repeating it.

Report the cause, the files you changed, whether the synth assertion tests pass, and their captured output.`,
  {
    label: 'story-deploy:fix',
    phase: 'Fix',
    agentType: 'cdk-stack-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['cause', 'changedFiles', 'testsPassed', 'evidence'],
      properties: {
        cause: { type: 'string' },
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsPassed: { type: 'boolean' },
        evidence: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)
if (!fix) return handback(false, DISPATCH_FAILED_STAGE, `the fixer for Story ${beadId} returned nothing`)
const changedFiles = Array.isArray(fix.changedFiles) ? fix.changedFiles.filter((f) => typeof f === 'string' && f.trim()) : []
if (!changedFiles.length) {
  return handback(false, 'no-change', `Story ${beadId}: the fixer changed no file, so a redeploy would fail the same way — ${String(fix.cause || 'no cause given').slice(0, 300)}`, {
    cause: fix.cause,
    changedFiles,
    testsPassed: fix.testsPassed === true,
  })
}

phase('Commit')
const committed = await workflow('agent-teams-workforce:settle', {
  repoPath: repo,
  commitOnly: true,
  branch: a.branch || null,
  defaultBranch: a.defaultBranch || null,
  message: `fix the deploy of Story ${beadId}: ${String(fix.cause || '').slice(0, 160)}`,
})
if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
  const why =
    (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
    'the commit step returned nothing'
  return handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `Story ${beadId}: the fix was not committed — ${why}`, {
    cause: fix.cause,
    changedFiles,
    testsPassed: fix.testsPassed === true,
  })
}

return handback(true, 'fixed', `Story ${beadId}: ${String(fix.cause || 'the deploy failure').slice(0, 300)} — fixed and committed (${committed.commit || 'no new commit'})${fix.testsPassed === true ? '; the synth assertion tests pass' : ''}`, {
  cause: fix.cause,
  changedFiles,
  testsPassed: fix.testsPassed === true,
  commit: committed.commit || null,
})
