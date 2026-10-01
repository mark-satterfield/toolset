export const meta = {
  name: 'tdd-green',
  description:
    'Shared-tail mini — TDD Green. The implementation-lead selects the implementer(s) for the change unless the caller names one; the implementers write the minimum production code in sequence to make the failing tests pass, run the suite, and report Green.',
  phases: [{ title: 'Green', detail: 'minimum code to pass; confirm Green' }],
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

// Implementer agent types this mini may dispatch.
const IMPLEMENTER_ROSTER = [
  'chassis-extension-implementer',
  'power-tools-configuration-implementer',
  'api-gateway-cdk-implementer',
  'event-api-client-implementer',
  'event-driven-consumer-implementer',
  'dynamodb-access-layer-implementer',
  'cognito-lambda-trigger-implementer',
  'webauthn-implementer',
  'payments-integration-implementer',
  'email-notification-implementer',
  'mcp-server-implementer',
  'bedrock-integration-implementer',
  'matching-algorithm-implementer',
  'recommendation-engine-implementer',
  'vector-search-embeddings-implementer',
  'behavioral-signals-implementer',
  'llm-observability-implementer',
  'nextjs-component-implementer',
  'appsync-client-subscription-implementer',
  'ios-swiftui-implementer',
  'android-compose-implementer',
  'react-native-implementer',
  'appsync-cdk-implementer',
  'glue-etl-implementer',
  'kinesis-stream-implementer',
  'dynamodb-streams-cdc-implementer',
  's3-data-lake-implementer',
  'athena-redshift-analytics-implementer',
  'cdk-stack-author',
]

// Implementers that run from the user-level agents directory, dispatched by their plain name.
const USER_LEVEL_AGENTS = new Set([
  'api-gateway-cdk-implementer',
  'cdk-stack-author',
  'chassis-extension-implementer',
  'dynamodb-access-layer-implementer',
  'dynamodb-streams-cdc-implementer',
  'event-driven-consumer-implementer',
])

// args: { contract, red, implementer?: string, implementers?: string[], feedback?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const red = a.red || {}
const repo = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim() || '(repo path not provided)'
const beadId = (c.bead && c.bead.id) || null

const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])
const isBugContract = !!(c.reproduction || c.rootCause)
const beadDescription = c.bead ? str(c.bead.description) : ''
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const acLine = (x, i) => {
  if (typeof x === 'string') return `${i + 1}. ${x.trim()}`
  if (x && typeof x === 'object' && (x.given || x.when || x.then)) {
    return `${i + 1}. GIVEN ${x.given || 'n/a'} WHEN ${x.when || 'n/a'} THEN ${x.then || 'n/a'}`
  }
  return `${i + 1}. ${JSON.stringify(x)}`
}
const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(c.spec && c.spec.decisionIds)])]
const specBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  const docs = s ? [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))] : []
  const lines = [
    docs.length ? `Spec documents — read the sections named below in these files before writing code:\n${docs.map((d) => `  - ${d}`).join('\n')}` : '',
    s && strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    s && strList(s.requirementIds).length ? `Requirements satisfied: ${strList(s.requirementIds).join(', ')}` : '',
    decisionIds.length ? `Architecture views this work is designed against (paths relative to the arc42 folder): ${decisionIds.join(', ')}` : '',
    s && strList(s.definitionOfDone).length ? `Definition of Done:\n${strList(s.definitionOfDone).map((d) => `  - ${d}`).join('\n')}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const RED_EVIDENCE_CHARS = 4000
const redEvidence = str(red.evidence)

const infraBlock = (() => {
  const pi = c.provisioningIntent && typeof c.provisioningIntent === 'object' ? c.provisioningIntent : null
  const stacks = [...new Set([...strList(c.affectedStacks), ...strList(pi && pi.affectedStacks)])]
  const resources = pi && Array.isArray(pi.resources) ? pi.resources.filter((r) => r && typeof r === 'object') : []
  const refs = pi ? strList(pi.crossStackRefs) : []
  const lines = [
    stacks.length ? `Affected CDK stacks: ${stacks.join(', ')}` : '',
    resources.length
      ? `Provisioning intent — the resources to provision:\n${resources
          .map((r) => `  - ${str(r.logicalId) || '(resource)'} ${str(r.type)}${str(r.stack) ? ` in ${str(r.stack)}` : ''}${str(r.properties) ? `: ${str(r.properties)}` : ''}`)
          .join('\n')}`
      : '',
    refs.length ? `Cross-stack references:\n${refs.map((x) => `  - ${x}`).join('\n')}` : '',
    pi && str(pi.rationale) ? `Intent rationale: ${str(pi.rationale)}` : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature implementation'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
${ac.length ? `\nAcceptance criteria this change satisfies:\n${ac.map(acLine).join('\n')}\n` : ''}
Failing test(s) to satisfy: ${(red.testFiles || []).join(', ') || 'n/a'}
Red evidence${redEvidence.length > RED_EVIDENCE_CHARS ? ` (first ${RED_EVIDENCE_CHARS} characters)` : ''}: ${redEvidence.slice(0, RED_EVIDENCE_CHARS) || 'n/a'}`

const treeBlock = `Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}`

phase('Green')

let implementers
let selectionMode
const reused = Array.isArray(a.implementers) ? [...new Set(a.implementers.filter((i) => IMPLEMENTER_ROSTER.includes(i)))] : []
if (a.implementer) {
  implementers = [a.implementer]
  selectionMode = 'selected'
} else if (reused.length) {
  implementers = reused
  selectionMode = 'reused'
} else {
  const selection = await settleAgent(
    `You are the implementation-lead. Do NOT write code. Select the FEWEST implementer agent(s) whose specialty covers this change, drawn ONLY from: ${IMPLEMENTER_ROSTER.join(', ')}. A standard Python-Lambda service change is chassis-extension-implementer alone. Order them so earlier ones lay groundwork for later ones.

${treeBlock}

${taskBlock}`,
    {
      label: 'green:select-implementers',
      effort: 'low',
      phase: 'Green',
      agentType: 'agent-teams-workforce:implementation-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['implementers', 'rationale'],
        properties: {
          implementers: { type: 'array', items: { type: 'string' } },
          rationale: { type: 'string' },
        },
      },
    }
  )
  const picked = selection && Array.isArray(selection.implementers) ? selection.implementers.filter((i) => IMPLEMENTER_ROSTER.includes(i)) : []
  implementers = picked.length ? picked : ['chassis-extension-implementer']
  selectionMode = picked.length ? 'selected' : 'default'
}

const GREEN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'greenConfirmed', 'noRegressions', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    greenConfirmed: { type: 'boolean' },
    noRegressions: { type: 'boolean' },
    evidence: { type: 'string' },
    notes: { type: 'string' },
  },
}

let green = null
const changedFiles = []
const deadImplementers = []
for (const impl of implementers) {
  green = await settleAgent(
    `Make the failing test pass with the MINIMUM production change. Then run the test suite and confirm the target test passes (Green) and nothing else regressed.

${treeBlock}

${taskBlock}${implementers.length > 1 ? `\n\nYou are '${impl}', one of ${implementers.length} implementers on this task — make only the part matching your specialty; prior implementers' changes are already applied.` : ''}
${a.feedback ? `\nFeedback from the previous attempt — address it:\n${a.feedback}` : ''}

Build to the contract above; do not modify the tests. Deliver the changed files, whether Green is confirmed (the target test passes), whether the full suite shows no regression (\`noRegressions\`), and the captured output of both runs.`,
    {
      label: `green:${impl}`,
      phase: 'Green',
      agentType: USER_LEVEL_AGENTS.has(impl) ? impl : `agent-teams-workforce:${impl}`,
      schema: GREEN_SCHEMA,
    }
  )
  if (!green) {
    deadImplementers.push(impl)
    break
  }
  if (Array.isArray(green.changedFiles)) changedFiles.push(...green.changedFiles)
}

const ledger = {
  phase: 'green',
  beadId,
  chosen: implementers,
  mode: selectionMode,
  ok: !!(green && green.greenConfirmed),
}

if (deadImplementers.length) {
  return {
    ok: false,
    dispatchFailed: true,
    reason: `implementer(s) ${deadImplementers.join(', ')} returned nothing`,
    changedFiles,
    ledger: { ...ledger, ok: false },
  }
}

const stoppedAt =
  green.greenConfirmed !== true || green.noRegressions !== true ? [str(green.notes), str(green.evidence).slice(-1500)].filter(Boolean).join(' | ') : ''
return { ...green, changedFiles, ...(stoppedAt ? { reason: stoppedAt } : {}), ledger }
