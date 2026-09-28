export const meta = {
  name: 'documentation',
  description:
    'Cross-cutting mini — Documentation. One read-only auditor names the docs the change leaves stale and the writer that owns each (a doc with no usable writer is assigned by its path); the writers update them in parallel in the worktree. A change confined to tests and fixtures skips the audit.',
  phases: [{ title: 'Documentation', detail: 'currency audit + assigned writes' }],
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
  return {
    docsCurrent: true,
    audit: null,
    update: null,
    alreadySatisfied: true,
    reason: 'every changed file is a test or fixture',
    ledger: { phase: 'documentation', beadId, chosen: [], mode: 'no-documentable-change', ok: true },
  }
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
const docsUnjudged = !audit || writerResults.length < writersChosen.length

const ledger = {
  phase: 'documentation',
  beadId,
  chosen: ['documentation-currency-auditor'].concat(writersChosen),
  mode: needsWork ? selectionMode : 'default',
  ok: docsCurrent,
}

return {
  docsCurrent,
  audit,
  update,
  ledger,
  ...(docsUnjudged
    ? {
        dispatchFailed: true,
        dispatchFailures: dispatchDeaths('Documentation'),
        reason: !audit
          ? 'the documentation auditor returned nothing'
          : `${writersChosen.length - writerResults.length} of ${writersChosen.length} documentation writer(s) returned nothing`,
      }
    : {}),
}
