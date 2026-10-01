export const meta = {
  name: 'tdd-refactor',
  description:
    'Shared-tail mini — TDD Refactor. The code-refactoring-specialist refactors the code Green changed for clarity without changing behavior, keeps the suite green, and puts the tree back at its pre-refactor state when it cannot. Returns alreadySatisfied when nothing needed refactoring or the refactor was reverted, and dispatchFailed when the specialist returned nothing.',
  phases: [{ title: 'Refactor', detail: 'behavior-preserving refactor; tests stay green' }],
}
// settleAgent(prompt, opts): calls agent(); returns its result, or null when the agent returns nothing or fails deterministically. A transient API failure is retried with capped backoff until it clears.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  if (TRANSIENT_ERROR_TEXT.test(text)) return 'transient'
  return 'deterministic'
}
function transientWaitMs(name, attempt) {
  const scheduled = Math.min(300000, 5000 * Math.pow(3, Math.max(0, attempt - 1)))
  let h = 2166136261
  const key = `${name}#${attempt}`
  for (let i = 0; i < key.length; i++) h = Math.imul(h ^ key.charCodeAt(i), 16777619)
  return Math.round(scheduled * (0.5 + 0.5 * ((h >>> 0) / 4294967296)))
}
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const name = o.label || o.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, o)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err).slice(0, 300)
      if (failureCause(err) !== 'transient' || (!SETTLE_CAN_WAIT && attempt >= 3)) {
        log(`${name}: failed — ${message}`)
        return null
      }
      const wait = transientWaitMs(name, attempt)
      log(`${name}: transient failure on attempt ${attempt}, retrying in ${Math.round(wait / 1000)}s — ${message}`)
      if (SETTLE_CAN_WAIT) await new Promise((resolve) => setTimeout(resolve, wait))
    }
  }
}

// args: { contract, green, feedback?: string }
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

phase('Refactor')

const refactor = await settleAgent(
  `Refactor the code changed by the fix for clarity and to reduce complexity and duplication, WITHOUT changing behavior.

Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}

Changed files from the fix: ${changedFromGreen}${contractBlock}
${a.feedback ? `\nFeedback to address:\n${a.feedback}` : ''}

Steps:
1. Before editing, record the tree: \`git -C "${repo}" add -A\` then \`git -C "${repo}" write-tree\`; return that id as \`snapshotTree\`.
2. If these files need no refactoring, change nothing and return an empty \`changedFiles\`.
3. Otherwise refactor, then run the test suite.
4. If the suite is not green and you cannot make it green without changing behavior, put the tree back: \`git -C "${repo}" add -A\`, then for each path listed by \`git -C "${repo}" diff --cached --no-renames --name-status <snapshotTree>\` other than documentation (.md, .mdx, .rst, .adoc, anything under docs/): status A → \`git -C "${repo}" rm -f -q -- <path>\`, otherwise \`git -C "${repo}" restore --source=<snapshotTree> --staged --worktree -- <path>\`. Return reverted=true.

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
  return {
    ok: false,
    dispatchFailed: true,
    reason: 'the code-refactoring-specialist returned nothing',
    testsGreen: false,
    behaviorPreserved: false,
    changedFiles: [],
    ledger: ledgerOf('default', false),
  }
}

const snapshotTree = str(refactor.snapshotTree) || null
const changedFiles = Array.isArray(refactor.changedFiles) ? refactor.changedFiles : []

if (refactor.reverted === true) {
  log('Refactor: the refactor could not keep the suite green and was reverted')
  return {
    refactor,
    changedFiles: [],
    testsGreen: true,
    behaviorPreserved: true,
    alreadySatisfied: true,
    restored: true,
    snapshotTree,
    reason: `the refactor was reverted: ${str(refactor.notes) || str(refactor.evidence).slice(-500)}`,
    ledger: ledgerOf('reverted', true),
  }
}

if (!changedFiles.length && refactor.testsGreen === true) {
  return {
    refactor,
    changedFiles: [],
    testsGreen: true,
    behaviorPreserved: true,
    alreadySatisfied: true,
    snapshotTree,
    ledger: ledgerOf('nothing-to-refactor', true),
  }
}

const testsGreen = refactor.testsGreen === true
return {
  refactor,
  changedFiles,
  testsGreen,
  behaviorPreserved: testsGreen,
  snapshotTree,
  ...(testsGreen ? {} : { reason: str(refactor.evidence).slice(-1500) || 'the suite is not green after the refactor' }),
  ledger: ledgerOf('default', testsGreen),
}
