export const meta = {
  name: 'documentation',
  description:
    'Cross-cutting mini — Documentation. One read-only auditor names the docs the change leaves stale and the writer that owns each (a doc with no usable writer is assigned by its path); the writers update them in parallel in the worktree. A change confined to tests and fixtures skips the audit.',
  phases: [{ title: 'Documentation', detail: 'currency audit + assigned writes' }],
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

const dispatchFailures = []
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
        for (const entry of mine) { const at = dispatchFailures.indexOf(entry); if (at >= 0) dispatchFailures.splice(at, 1) }
        return out
      }
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing' })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160) }
      dispatchFailures.push(entry)
      mine.push(entry)
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

// args: { contract, green }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const beadId = (c.bead && c.bead.id) || null
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`
const changeLabel = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const changedFiles = (green.changedFiles || []).join(', ') || 'n/a'

phase('Documentation')

const DOC_INERT_RE = /(^|\/)(tests?|__tests__|__mocks__|fixtures)\//i
const changedList = (green.changedFiles || []).filter(Boolean)
if (changedList.length && changedList.every((f) => DOC_INERT_RE.test(f))) {
  log(`Documentation: change is confined to tests and fixtures (${changedList.length} files) — skipping the audit`)
  return dispatchOutcome({
    docsCurrent: true,
    audit: null,
    update: null,
    alreadySatisfied: true,
    reason: 'every changed file is a test or fixture',
    ledger: { phase: 'documentation', beadId, chosen: [], mode: 'no-documentable-change', ok: true },
  })
}

const WRITERS = ['api-documentation-writer', 'readme-writer', 'changelog-writer', 'user-guide-writer']

const audit = await settleAgent(
  `Audit whether this change leaves documentation stale (READMEs, API docs, changelog, user guides). READ-ONLY — you write no documentation. List exactly which docs need updating and why.

${pinTree}

Then ASSIGN each stale doc to the writer that owns its kind, drawn ONLY from this roster:
- api-documentation-writer — API reference / OpenAPI / GraphQL docs
- readme-writer — setup, onboarding, repo README, or a new repo
- changelog-writer — version bump / changelog entry derived from commits
- user-guide-writer — user-facing feature guide or walkthrough

Use the FEWEST writers that cover the stale docs, list the stale docs assigned to each, and assign no writer whose kind nothing changed.

Change: ${changeLabel}
Changed files: ${changedFiles}`,
  {
    label: 'docs:audit',
    phase: 'Documentation',
    agentType: 'agent-teams-workforce:documentation-currency-auditor',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['docsCurrent', 'staleDocs'],
      properties: {
        docsCurrent: { type: 'boolean' },
        staleDocs: { type: 'array', items: { type: 'string' } },
        assignments: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['writer', 'docs'],
            properties: {
              writer: { type: 'string', enum: WRITERS },
              docs: { type: 'array', items: { type: 'string' } },
            },
          },
        },
      },
    },
  }
)

const staleDocs = (audit && Array.isArray(audit.staleDocs) ? audit.staleDocs : []).filter(Boolean)
const needsWork = staleDocs.length > 0

// Returns the writer for a doc path: changelog, readme, API reference, otherwise user guide.
const writerForPath = (docPath) => {
  const p = String(docPath || '')
  if (/changelog/i.test(p)) return 'changelog-writer'
  if (/readme/i.test(p)) return 'readme-writer'
  if (/openapi|swagger|(^|\/)api(\/|\.|-|_)|\/api-reference/i.test(p)) return 'api-documentation-writer'
  return 'user-guide-writer'
}

let writerResults = []
let selectionMode = 'default'
let writersChosen = []

if (needsWork) {
  const assigned = new Set()
  const validAssignments = []
  const addDocs = (writer, docs) => {
    const existing = validAssignments.find((v) => v.writer === writer)
    if (existing) existing.docs.push(...docs)
    else validAssignments.push({ writer, docs })
  }
  for (const x of audit && Array.isArray(audit.assignments) ? audit.assignments : []) {
    if (!x || !WRITERS.includes(x.writer) || !Array.isArray(x.docs)) continue
    const docs = [...new Set(x.docs.filter(Boolean))].filter((doc) => !assigned.has(doc))
    for (const doc of docs) assigned.add(doc)
    if (docs.length) addDocs(x.writer, docs)
  }
  for (const doc of [...new Set(staleDocs)].filter((d) => !assigned.has(d))) addDocs(writerForPath(doc), [doc])

  selectionMode = audit && Array.isArray(audit.assignments) && audit.assignments.length ? 'assigned' : 'derived'
  writersChosen = validAssignments.map((x) => x.writer)

  const WRITE_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['updatedDocs'],
    properties: {
      updatedDocs: { type: 'array', items: { type: 'string' } },
      notes: { type: 'string' },
    },
  }

  writerResults = (await parallel(
    validAssignments.map((asg) => () =>
      settleAgent(
        `Update the stale documentation assigned to you so it matches shipped behavior. Author only the docs in your assignment; other writers own the rest.

${pinTree}

Change: ${changeLabel}
Changed files: ${changedFiles}
Docs assigned to you: ${asg.docs.join(', ')}`,
        {
          label: `docs:write:${asg.writer}`,
          phase: 'Documentation',
          agentType: `agent-teams-workforce:${asg.writer}`,
          schema: WRITE_SCHEMA,
        }
      )
    )
  )).filter(Boolean)
}

const allUpdatedDocs = []
for (const r of writerResults) {
  if (r && Array.isArray(r.updatedDocs)) allUpdatedDocs.push(...r.updatedDocs)
}
const update = needsWork ? { updatedDocs: allUpdatedDocs, writers: writerResults } : null
const docsCurrent = !!(audit && (!needsWork || writerResults.length === writersChosen.length))

const ledger = {
  phase: 'documentation',
  beadId,
  chosen: ['documentation-currency-auditor'].concat(writersChosen),
  mode: needsWork ? selectionMode : 'default',
  ok: docsCurrent,
}

return dispatchOutcome({
  docsCurrent,
  audit,
  update,
  ledger,
})
