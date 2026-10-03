export const meta = {
  name: 'tdd-refactor',
  description:
    'Shared-tail mini — TDD Refactor. The code-refactoring-specialist refactors the code Green changed for clarity without changing behavior, keeps the suite green, and puts the tree back at its pre-refactor state when it cannot. Returns alreadySatisfied when nothing needed refactoring or the refactor was reverted, and dispatchFailed when the specialist returned nothing. With restoreTo (a snapshot tree id the refactor recorded) one session puts the tree back at that snapshot and returns { restored }.',
  phases: [{ title: 'Refactor', detail: 'behavior-preserving refactor; tests stay green' }],
}
// BEGIN bounded dispatch policy — identical in workflow consumers (no runtime imports).
let dispatchInterruption = null
function dispatchOutcome(result) {
  if (!dispatchInterruption) return result
  const out = result && typeof result === 'object' ? result : {}
  return { ...out, ok: false, dispatchFailed: true, paused: true, resumable: true,
    stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message,
    ...(typeof out.passed === 'boolean' ? { passed: false } : {}),
    ...(out.ledger ? { ledger: { ...out.ledger, ok: false } } : {}), dispatchInterruption }
}
function dispatchPolicy(options) {
  const input = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  const policy = (options && options.retryPolicy) || input.retryPolicy || {}
  return { maxAttempts: Number.isInteger(policy.maxAttempts) && policy.maxAttempts > 0 ? policy.maxAttempts : 3,
    maxWaitMs: Number.isFinite(policy.maxWaitMs) && policy.maxWaitMs >= 0 ? policy.maxWaitMs : 300000 }
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
function dispatchRetry(err, name, attempt, waitedMs, policy, canWait) {
  const cause = dispatchFailureCause(err)
  if (cause === 'deterministic') return { retry: false, cause }
  const e = err && typeof err === 'object' ? err : {}
  const headers = e.headers || (e.response && e.response.headers) || {}
  const rawRetryAfter = e.retryAfter !== undefined ? e.retryAfter : headers['retry-after']
  const retryAfter = e.retryAfterMs !== undefined ? Number(e.retryAfterMs) : Number(rawRetryAfter) * 1000
  // An HTTP-date without a supplied clock cannot be safely shortened to our backoff.
  const unknownRetryDate = rawRetryAfter !== undefined && !Number.isFinite(retryAfter)
  let hash = 2166136261
  for (const ch of `${name}#${attempt}`) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619)
  const scheduled = Math.round(Math.min(300000, 5000 * Math.pow(3, attempt - 1)) * (0.5 + 0.5 * ((hash >>> 0) / 4294967296)))
  const wait = Math.max(scheduled, Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : 0)
  if (cause === 'transient' && !unknownRetryDate && canWait && attempt < policy.maxAttempts && waitedMs + wait <= policy.maxWaitMs) return { retry: true, cause, wait }
  const stage = cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable'
  return { retry: false, cause, interruption: { stage, message: `${stage}: ${name}: ${String(e.message || err || cause)}`, attempt,
    retryAfterMs: Number.isFinite(retryAfter) && retryAfter >= 0 ? retryAfter : null, retryAfter: rawRetryAfter || null } }
}
async function settleWorkflow(name, input) {
  if (dispatchInterruption) return dispatchOutcome({})
  const source = (typeof args === 'string' ? JSON.parse(args) : args) || {}
  try {
    const out = await workflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
    if (out && out.paused && out.resumable && out.dispatchInterruption) dispatchInterruption = out.dispatchInterruption
    return out
  } catch (err) {
    const plan = dispatchRetry(err, name, 1, 0, dispatchPolicy(null), false)
    if (!plan.interruption) throw err
    dispatchInterruption = plan.interruption
    return dispatchOutcome({})
  }
}
// END bounded dispatch policy

function failureCause(err) { return dispatchFailureCause(err) }
async function settleAgent(prompt, opts) {
  if (dispatchInterruption) return null
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.retryPolicy
  delete call.schemaName
  delete call.rethrow
  const name = o.label || o.agentType || 'agent'
  const policy = dispatchPolicy(o)
  const mine = []
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    if (dispatchInterruption) return null
    try {
      const out = await agent(prompt, call)
      if (out) {

        return out
      }

      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)

      if (!plan.retry) {
        if (plan.interruption) dispatchInterruption = plan.interruption
        log(name + ': stopped (' + plan.cause + ') — ' + message)
        if (o.rethrow && !plan.interruption) throw err
        return null
      }
      waitedMs += plan.wait
      log(name + ': transient failure; retry ' + (attempt + 1) + '/' + policy.maxAttempts + ' in ' + Math.round(plan.wait / 1000) + 's — ' + message.slice(0, 160))
      await new Promise((resolve) => setTimeout(resolve, plan.wait))
    }
  }
}

// args: { contract, green, feedback?: string, restoreTo?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const beadId = (c.bead && c.bead.id) || null
const changedFromGreen = (green.changedFiles || []).join(', ') || 'n/a'

const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])
const contractBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  const docs = s ? [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))] : []
  const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(s && s.decisionIds)])]
  const lines = [
    docs.length ? `Spec documents this change was built to; the refactor stays inside them:\n${docs.map((d) => `  - ${d}`).join('\n')}` : '',
    s && strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    decisionIds.length ? `Architecture views this work is designed against (paths relative to the arc42 folder): ${decisionIds.join(', ')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const restoreCommands = (tree) => `\`git -C "${repo}" add -A\`, then for each path listed by \`git -C "${repo}" diff --cached --no-renames --name-status ${tree}\` other than documentation (.md, .mdx, .rst, .adoc, anything under docs/): status A → \`git -C "${repo}" rm -f -q -- <path>\`, otherwise \`git -C "${repo}" restore --source=${tree} --staged --worktree -- <path>\``

phase('Refactor')

const restoreTo = str(a.restoreTo)
if (restoreTo) {
  const restore = await settleAgent(
    `Put this tree back at the snapshot tree ${restoreTo}, then report. Change nothing else.

Run ${restoreCommands(restoreTo)}. Then run \`git -C "${repo}" add -A\` and \`git -C "${repo}" diff --cached --no-renames --name-only ${restoreTo}\`; restored is true when that prints only documentation paths or nothing.`,
    {
      label: 'refactor:restore',
      phase: 'Refactor',
      model: 'haiku',
      effort: 'low',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['restored', 'evidence'],
        properties: {
          restored: { type: 'boolean' },
          evidence: { type: 'string' },
        },
      },
    }
  )
  if (!restore) {
    return dispatchOutcome({ ok: false, dispatchFailed: true, restored: false, reason: 'the restore session returned nothing', ledger: { phase: 'refactor', beadId, chosen: ['restore'], mode: 'restore', ok: false } })
  }
  return dispatchOutcome({
    restored: restore.restored === true,
    evidence: str(restore.evidence),
    ledger: { phase: 'refactor', beadId, chosen: ['restore'], mode: 'restore', ok: restore.restored === true },
  })
}

const suiteCommand = str(c.suiteCommand)
const refactor = await settleAgent(
  `Refactor the code changed by the fix for clarity and to reduce complexity and duplication, WITHOUT changing behavior.

Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}

Changed files from the fix: ${changedFromGreen}${contractBlock}
${a.feedback ? `\nFeedback to address:\n${a.feedback}` : ''}

Steps:
1. Before editing, record the tree: \`git -C "${repo}" add -A\` then \`git -C "${repo}" write-tree\`; return that id as \`snapshotTree\`.
2. If these files need no refactoring, change nothing and return an empty \`changedFiles\`.
3. Otherwise refactor, then run the test suite${suiteCommand ? ` with exactly \`cd "${repo}" && ${suiteCommand}\`, the command the run judges the suite by` : ''}.
4. If the suite is not green and you cannot make it green without changing behavior, put the tree back: ${restoreCommands('<snapshotTree>')}. Return reverted=true.

Deliver the files you touched, whether tests are green, whether you reverted, and the captured test output.`,
  {
    label: 'refactor:apply',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-refactoring-specialist',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['changedFiles', 'testsGreen', 'reverted', 'evidence'],
      properties: {
        snapshotTree: { type: 'string' },
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsGreen: { type: 'boolean' },
        reverted: { type: 'boolean' },
        evidence: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)

const ledgerOf = (mode, ok) => ({ phase: 'refactor', beadId, chosen: ['code-refactoring-specialist'], mode, ok })

if (!refactor) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    reason: 'the code-refactoring-specialist returned nothing',
    testsGreen: false,
    behaviorPreserved: false,
    changedFiles: [],
    ledger: ledgerOf('default', false),
  })
}

const snapshotTree = str(refactor.snapshotTree) || null
const changedFiles = Array.isArray(refactor.changedFiles) ? refactor.changedFiles : []

if (refactor.reverted === true) {
  log('Refactor: the refactor could not keep the suite green and was reverted')
  return dispatchOutcome({
    refactor,
    changedFiles: [],
    testsGreen: true,
    behaviorPreserved: true,
    alreadySatisfied: true,
    restored: true,
    snapshotTree,
    reason: `the refactor was reverted: ${str(refactor.notes) || str(refactor.evidence).slice(-500)}`,
    ledger: ledgerOf('reverted', true),
  })
}

if (!changedFiles.length && refactor.testsGreen === true) {
  return dispatchOutcome({
    refactor,
    changedFiles: [],
    testsGreen: true,
    behaviorPreserved: true,
    alreadySatisfied: true,
    snapshotTree,
    ledger: ledgerOf('nothing-to-refactor', true),
  })
}

const testsGreen = refactor.testsGreen === true
return dispatchOutcome({
  refactor,
  changedFiles,
  testsGreen,
  behaviorPreserved: testsGreen,
  snapshotTree,
  ...(testsGreen ? {} : { reason: str(refactor.evidence).slice(-1500) || 'the suite is not green after the refactor' }),
  ledger: ledgerOf('default', testsGreen),
})
