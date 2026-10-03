export const meta = {
  name: 'tdd-green',
  description:
    'Shared-tail mini — TDD Green. The implementation-lead selects the implementer(s) for the change unless the caller names one; the implementers write the minimum production code in sequence to make the failing tests pass, run the suite, and report Green. An implementer does not change tests: it names a test that contradicts the contract in testIssues, and a missing thing outside the Task in upstreamMissing.',
  phases: [{ title: 'Green', detail: 'minimum code to pass; confirm Green' }],
}
// ===== SHARED BLOCK fable — BEGIN (canonical: scripts/shared-blocks/fable.js; edit there, then: node scripts/shared-blocks.mjs --write) =====
// Runtime replay identifies calls by their unchanged prompt/options and start order.
// Recovery metadata stays in workflow arguments and never enters those options.
const fableInput = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const fableTypes = new Set((Array.isArray(fableInput.fableAgentTypes) ? fableInput.fableAgentTypes : []).map((name) => String(name).replace(/^agent-teams-workforce:/, '')))
const fablePath = fableInput.fableInvocationPath || 'root'
const fableRecovery = fableInput.fableRecovery && typeof fableInput.fableRecovery === 'object' ? fableInput.fableRecovery : null
let fableAgentOrdinal = 0
let fableChildOrdinal = 0
function fableEvent(event, identity, error = null) {
  log(`FABLE-CALL ${JSON.stringify({ event, ...identity, ...(error === null ? {} : { error }) })}`)
}
async function fableAgent(prompt, options) {
  const identity = { invocationPath: fablePath, ordinal: fableAgentOrdinal++, agentType: (options && options.agentType) || null, label: (options && options.label) || null }
  const isFable = fableTypes.has(String(identity.agentType || '').replace(/^agent-teams-workforce:/, ''))
  const cutoffs = (fableRecovery && fableRecovery.cutoffs) || {}
  const cutoff = Number.isInteger(cutoffs[fablePath]) && cutoffs[fablePath] >= 0 ? cutoffs[fablePath] : 0
  const call = isFable && fableRecovery && identity.ordinal >= cutoff ? { ...options, model: 'opus' } : options
  fableEvent('start', identity)
  try {
    const result = await agent(prompt, call)
    if (!result) fableEvent('failed', identity)
    return result
  } catch (error) {
    const message = String((error && error.message) || error)
    fableEvent('failed', identity, message)
    if (isFable && /out of (?:usage )?credits|seven_day_overage_included|fable.{0,40}(?:limit|allowance)/i.test(message)) return null
    throw error
  }
}
async function fableWorkflow(name, input) {
  const invocationPath = `${fablePath}/${fableChildOrdinal++}:${name}`
  return await workflow(name, {
    ...input,
    fableAgentTypes: fableInput.fableAgentTypes || [],
    fableInvocationPath: invocationPath,
    ...(fableRecovery ? { fableRecovery } : {}),
  })
}
// ===== SHARED BLOCK fable — END =====

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
    const out = await fableWorkflow(name, { ...input, ...(source.retryPolicy && !(input && input.retryPolicy) ? { retryPolicy: source.retryPolicy } : {}) })
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
      const out = await fableAgent(prompt, call)
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
  'cds:cds-ui-author',
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

// Implementers another plugin ships, dispatched by their plugin-qualified name.
const OTHER_PLUGIN_AGENTS = new Set(['cds:cds-ui-author'])

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

// The design source of a web-ui Task: bundle (a cds bundle the owner supplied), cds (designed with the
// CDS design system) or none (no design change); a contract naming none takes bundle when it names a
// bundle and is otherwise left to the surfaces.
const cdsBundle = str(c.cdsBundlePath)
const cdsSpecs = strList(c.cdsBuildSpecs)
const designSource = ['bundle', 'cds', 'none'].includes(str(c.cdsDesignSource)) ? str(c.cdsDesignSource) : cdsBundle ? 'bundle' : ''
const cdsBlock = (() => {
  if (designSource === 'bundle') {
    const lines = [
      'Design source: bundle. This Task builds web UI from the cds bundle the owner supplied, the only source of its visual design: its tokens, components and stylesheets as the bundle packages them. The code defines no colors, spacing, typography, radii, motion or component styles of its own.',
      cdsBundle ? `cds bundle: ${cdsBundle}` : '',
      cdsSpecs.length ? `cds build-spec items this Task implements:\n${cdsSpecs.map((x) => `  - ${x}`).join('\n')}` : '',
    ].filter(Boolean)
    return `\n\n${lines.join('\n')}`
  }
  if (designSource === 'cds') {
    return '\n\nDesign source: cds. No mockup was supplied for this Task\'s UI, and it changes design: design it with the Configurable Design System (cds) — the project\'s design system config and the cds plugin skills — using the system\'s tokens, components and stylesheets. The code defines no colors, spacing, typography, radii, motion or component styles of its own.'
  }
  if (designSource === 'none') {
    return '\n\nDesign source: none. This Task\'s UI change has no design impact (copy, or data wired into an existing element): keep the existing markup, classes and styles as they are and change no stylesheet.'
  }
  return ''
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

// Consumed by both selector and implementer prompts; only an explicit caller grants this scope.
const scopeBlock = c.baselineRepairScope === 'affected-repository'
  ? `\n\nASSIGNED REPAIR SCOPE: repair ALL baseline suite failures in the affected repository ${repo}, even outside this Task's feature. Diagnose and fix repository code/configuration needed for those failures; this is authorized work, not scope expansion. Preserve accepted behavior and published contracts. Test changes remain owned by Red through testIssues. Do not do unrelated cleanup or modify other repositories. Missing external resources or authority remain upstreamMissing with evidence.`
  : ''

const taskBlock = `${c.bead ? `${isBugContract ? 'Bug' : 'Task'} ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature implementation'}${
  beadDescription ? `\n\n${beadDescription}` : ''
}${isBugContract ? `\n\nReproduction: ${c.reproduction || 'n/a'}\nRoot cause: ${c.rootCause || 'n/a'}` : ''}${specBlock}${cdsBlock}${infraBlock}

Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
${ac.length ? `\nAcceptance criteria this change satisfies:\n${ac.map(acLine).join('\n')}\n` : ''}
Failing test(s) to satisfy: ${(red.testFiles || []).join(', ') || 'n/a'}
Red evidence${redEvidence.length > RED_EVIDENCE_CHARS ? ` (first ${RED_EVIDENCE_CHARS} characters)` : ''}: ${redEvidence.slice(0, RED_EVIDENCE_CHARS) || 'n/a'}${scopeBlock}`

const suiteCommand = str(c.suiteCommand)
const suiteBlock = suiteCommand
  ? `\n\nThe run judges green by running exactly \`cd "${repo}" && ${suiteCommand}\` itself, and green means it exits 0: the whole suite, including any test that was already failing before this Task. Run that command before you report.`
  : ''

const treeBlock = `Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}`

phase('Green')

// Routing is a required contract, never an implicit chassis default.
function validImplementers(value) {
  return Array.isArray(value) && value.length > 0 && value.every((name) => IMPLEMENTER_ROSTER.includes(name))
    ? [...new Set(value)] : null
}
function routingFailure(reason) {
  return { ok: false, dispatchFailed: true, reason: `Implementer routing failed: ${reason}`, changedFiles: [],
    ledger: { phase: 'green', beadId, chosen: [], mode: 'invalid', ok: false } }
}
let implementers
let selectionMode
if (a.implementer !== undefined && a.implementer !== null && a.implementer !== '') {
  implementers = validImplementers([a.implementer])
  if (!implementers) return dispatchOutcome(routingFailure(`unsupported explicit implementer ${String(a.implementer)}; select from the implementation roster`))
  selectionMode = 'selected'
} else if (a.implementers !== undefined && a.implementers !== null) {
  implementers = validImplementers(a.implementers)
  if (!implementers) return dispatchOutcome(routingFailure('saved implementer selection is empty or contains unsupported names; supply a valid selection'))
  selectionMode = 'reused'
} else {
  const selection = await settleAgent(
    `You are the implementation-lead. Do NOT write code. Select the FEWEST implementer agent(s) whose specialty covers this change, drawn ONLY from: ${IMPLEMENTER_ROSTER.join(', ')}. Read each implementer's specialty in its agent description; when one covers the whole change, select it alone. Web UI component and page work that changes design (anything newly rendered, styled or laid out) goes to cds:cds-ui-author, which builds with the cds design system; nextjs-component-implementer takes the non-visual React work (state, data fetching, routing) and a change with design source none (copy, or data wired into an existing element). Order them so earlier ones lay groundwork for later ones.

${treeBlock}

${taskBlock}${a.feedback ? `\n\nKnown suite failures and prior rulings to cover in your selection:\n${a.feedback}` : ''}`,
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
  implementers = validImplementers(selection && selection.implementers)
  if (!implementers) return dispatchOutcome(routingFailure('the selector returned no valid complete selection; inspect its failure and supply supported implementers'))
  selectionMode = 'selected'
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
    testIssues: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testId', 'kind', 'reason'],
        properties: {
          testId: { type: 'string' },
          kind: { type: 'string', enum: ['obsolete-by-contract', 'defect', 'missing-config'] },
          reason: { type: 'string' },
          contractRef: { type: 'string' },
        },
      },
    },
    upstreamMissing: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['what', 'evidence'],
        properties: {
          what: { type: 'string' },
          evidence: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

let green = null
const changedFiles = []
const testIssues = []
const upstreamMissing = []
const deadImplementers = []
for (const impl of implementers) {
  green = await settleAgent(
    `Make the failing test pass with the MINIMUM production change. Then run the test suite and confirm the target test passes (Green) and nothing else regressed.${suiteBlock}

${treeBlock}

${taskBlock}${implementers.length > 1 ? `\n\nYou are '${impl}', one of ${implementers.length} implementers on this task — make only the part matching your specialty; prior implementers' changes are already applied.` : ''}${impl === 'cds:cds-ui-author' ? `\n\nYou work in the app repo (direct-build) context: consult the design system, build with the system classes and tokens ${designSource === 'bundle' && cdsBundle ? `the cds bundle at ${cdsBundle} ships` : 'the live cds design system (the project\'s design system config) defines'}, and run audit-against-system on the files you changed before you report.` : ''}
${a.feedback ? `\nFeedback from the previous attempt — address it:\n${a.feedback}` : ''}

Build to the contract above; do not modify the tests. When a test stands between the code and the contract — it encodes behaviour the contract removes (obsolete-by-contract), it is wrong on its own terms (defect), or its fixtures lack configuration the contract now requires (missing-config) — leave it as it is and name it in \`testIssues\` with the contract reference; the test author rules on it. When the code cannot pass because a genuinely external dependency or resource does not exist yet (a package, stack, parameter, table or service outside the assigned repair scope), name each such thing in \`upstreamMissing\` with the evidence. A fixable defect or configuration inside explicitly authorized repository baseline repair is not upstreamMissing merely because it predates this Task. Deliver the changed files, whether Green is confirmed (the target test passes), whether the full suite shows no regression (\`noRegressions\`), and the captured output of both runs.`,
    {
      label: `green:${impl}`,
      phase: 'Green',
      agentType: USER_LEVEL_AGENTS.has(impl) || OTHER_PLUGIN_AGENTS.has(impl) ? impl : `agent-teams-workforce:${impl}`,
      schema: GREEN_SCHEMA,
    }
  )
  if (!green) {
    deadImplementers.push(impl)
    break
  }
  if (Array.isArray(green.changedFiles)) changedFiles.push(...green.changedFiles)
  if (Array.isArray(green.testIssues)) testIssues.push(...green.testIssues.filter((x) => x && str(x.testId)))
  if (Array.isArray(green.upstreamMissing)) upstreamMissing.push(...green.upstreamMissing.filter((x) => x && str(x.what)))
}

const ledger = {
  phase: 'green',
  beadId,
  chosen: implementers,
  mode: selectionMode,
  ok: !!(green && green.greenConfirmed),
}

if (deadImplementers.length) {
  return dispatchOutcome({
    ok: false,
    dispatchFailed: true,
    reason: `implementer(s) ${deadImplementers.join(', ')} returned nothing`,
    changedFiles,
    ledger: { ...ledger, ok: false },
  })
}

const stoppedAt =
  green.greenConfirmed !== true || green.noRegressions !== true ? [str(green.notes), str(green.evidence).slice(-1500)].filter(Boolean).join(' | ') : ''
return dispatchOutcome({ ...green, changedFiles, testIssues, upstreamMissing, ...(stoppedAt ? { reason: stoppedAt } : {}), ledger })
