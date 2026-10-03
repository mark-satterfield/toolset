export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Also SIZES the bug: a defect whose honest fix is a redesign is escalated as needing a PRD and Epic rather than being squeezed through the fix path, because a bug ticket is not a licence to rebuild a subsystem unreviewed. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + scope sizing + expected-behavior contract' }],
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

// Dispatch failures retain their identities and diagnostics; bounded retry policy is below.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
// Account exhaustion interrupts; transport failures use the caller's bounded retry policy.
function failureCause(err) { return dispatchFailureCause(err) }
function failureCauseFor(label) {
  const entry = dispatchFailures.slice().reverse().find((item) => item.label === label)
  return entry ? entry.cause || 'deterministic' : null
}
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
      dispatchFailures.push({ agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'skipped', cause: 'deterministic', attempt, message: null, note: name + ': returned nothing', schema: settleSchemaName(o), transcript: settleTranscript(null, name) })
      log(name + ': returned nothing')
      return null
    } catch (err) {
      const plan = dispatchRetry(err, name, attempt, waitedMs, policy, typeof setTimeout === 'function')
      const message = String((err && err.message) || err)
      const entry = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null, outcome: 'threw', cause: plan.cause, attempt, message: message.slice(0, 300), note: name + ': ' + message.slice(0, 160), schema: settleSchemaName(o), transcript: settleTranscript(err, name) }
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

// ── A LIMIT BELONGS WHERE THE DATA IS MADE, AND AN OVERAGE IS A FLAG ─────────────
//
// Two rules, and they are different rules.
//
// ONE: a limit is never a JSON-Schema maxItems/minItems/maxLength. A schema bound cannot
// trim an over-long answer — the runtime rejects the WHOLE result, the caller receives a
// bare null it cannot tell from a dead agent, and the run halts. One really did, on 61
// items against a bound of 60, claiming files were unread that had been read. So a limit
// is STATED in the prompt and COUNTED here, once the result is in hand.
//
// TWO, and it decides whether a limit may be stated at all: a limit belongs at the layer
// where the data is CREATED, not where it is read. A dispatch that AUTHORS its output —
// criteria, findings, a persona, a draft — chooses its own volume, so a ceiling stated to
// it is a real instruction it can honour. A dispatch that READS or EXTRACTS — an
// inventory of what exists, the evidence found in a repository, the ids it was handed,
// what git printed — has a volume that is a property of the source. Telling it "at most
// N" instructs it to truncate, which loses information, or to lie. Those dispatches get
// NO stated ceiling; bounding what they may DRAW ON (which repository, which files) is
// the guard that works, and it already lives in their prompts. Where a read's volume
// genuinely ought to be smaller, the fix belongs upstream, in whatever made the data.
//
// BOTH kinds are still counted here, because a wildly unexpected count is exactly the
// signal worth having, and nothing is ever truncated, dropped, reordered or summarised at
// any multiple. The count is a GRADUATED FLAG: modestly over the expected figure is
// ordinary variation and reads as an observation; at SCRUTINY_MULTIPLE times it or more,
// the shape is no longer variation — it is what padding, a misread assignment or
// duplicated entries look like — and it is logged prominently so a person looks. 2x is
// the threshold because a single band has to sit above the honest overshoots this
// pipeline actually produces (61 against 60 is 1.02x; the worst recorded lens overshoot
// is well under 1.5x) and below the runaway enumerations the limits exist to catch. It is
// a flag for a person, never a thing the code acts on: neither branch alters control flow.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const limitFindings = []
const SCRUTINY_MULTIPLE = 2
function checkLimit(where, what, value, expected, min) {
  const n = Array.isArray(value) ? value.length : typeof value === 'string' ? value.length : null
  if (n === null) return value
  if (typeof expected === 'number' && n > expected) {
    const ratio = expected > 0 ? n / expected : Infinity
    const scrutinise = ratio >= SCRUTINY_MULTIPLE
    limitFindings.push({ where, what, count: n, expected, ratio: Math.round(ratio * 100) / 100, severity: scrutinise ? 'scrutinise' : 'observation' })
    log(
      scrutinise
        ? `⚠ ${where}: ${what} returned ${n} where ${expected} was expected — ${Math.round(ratio * 10) / 10}x. Every item is kept and nothing downstream changes, but a count this far over is the shape of padding, a misread assignment or duplicated entries: worth a look.`
        : `${where}: ${what} returned ${n} where ${expected} was expected — over by ${n - expected}; every item is kept.`
    )
  }
  if (typeof min === 'number' && n < min) {
    limitFindings.push({ where, what, count: n, expected: min, severity: 'under' })
    log(`${where}: ${what} returned ${n}, under the ${min} this asked for — carried through as returned.`)
  }
  return value
}

// args: { bead: { id, title, description, repoPath?, repoHints?, inventoryCommand? } }
//
// `repoPath` is the repository when the caller knows it. It is NOT required: a Bug is
// filed against a SYMPTOM, and which repository the defect lives in is a finding of the
// diagnosis — the blast radius names the code at fault, and the code at fault is in a
// repository. So when no repoPath is supplied the diagnosing agent is told to LOCATE it,
// from the symptom, the repository inventory (`inventoryCommand`) and any names the caller merely
// suspects (`repoHints`), and to report it CONFIRMED — an absolute path that exists and is
// a git repository — or to report that it could not. A guessed repository is not an
// answer: bug-fix validates what comes back and refuses what it cannot use.
const __a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = __a.bead || {}
const repoKnown = !!String(bead.repoPath || '').trim()
const repo = repoKnown ? bead.repoPath : '(NOT KNOWN — locating it is part of this diagnosis; see below)'

const repoHints = (Array.isArray(bead.repoHints) ? bead.repoHints : []).map((h) => String(h == null ? '' : h).trim()).filter(Boolean)
const inventoryCommand = String(bead.inventoryCommand || '').trim()
const LOCATE_REPO =
  repoKnown
    ? ''
    : `

THE REPOSITORY IS NOT KNOWN, AND FINDING IT IS PART OF THIS DIAGNOSIS. Locate the repository whose source contains the code at fault. Start from the symptom and the blast radius; list the repositories this project has and where each is checked out on this machine ${inventoryCommand ? `by running \`${inventoryCommand}\`` : 'by asking the polyrepo-steward'}${repoHints.length ? `; the caller suspects it may be one of: ${repoHints.join(', ')} — a suspicion, not an answer` : ''}. Report repoPath as the ABSOLUTE path of that repository — the repository itself, not a worktree beneath it and not a subdirectory — and only after you have CONFIRMED the directory exists and is a git repository. If you cannot confirm one, report repoPath as an empty string and say in repoResolution which repositories you examined and why none was confirmed. A guessed repository sends a pipeline that writes code, commits and opens a pull request into a tree nobody chose; an honest empty answer does not.`

phase('Triage')

// What a bug is EXPECTED to contain, used to flag a count worth a look and stated to
// nobody. How many distinct defects sit behind one symptom is a fact about the code, not
// a volume the analyst chooses, so capping it would only buy a shorter list than the
// truth. A bug that really does carry twenty has an answer already — the `needs-prd`
// sizing step below rules it a redesign — and that ruling needs the full enumeration to
// be made on. The MINIMUM is stated, because "at least one" demands completeness rather
// than brevity: a diagnosis with no enumerated defect leaves the contract with nothing
// to cover.
const DEFECTS_EXPECTED = 20

// 1) Diagnosis — read-only analyst. Separation of duties: this agent does not fix.
const analysis = await settleAgent(
  `Diagnose this bug. You are READ-ONLY — do not change code. Work within the repository at: ${repo}

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Deliver:
- reproduction: the minimal, concrete steps/conditions that trigger the defect.
- rootCause: the precise mechanism and code location (file:line where possible), as prose.
- defects: the SAME root cause, ENUMERATED — one entry per distinct defect, each with a short stable id (D1, D2, ...), its mechanism, and the file and line where it lives. One bead frequently contains several distinct defects, and returning them only as one paragraph of prose leaves everything downstream with nothing countable: the acceptance criteria are then written against a blob and cannot be bounded, indexed, or checked for coverage. Return exactly one entry per defect you would fix separately — not one per file, not one per symptom. AT LEAST ONE entry, always: a bug with no enumerated defect leaves the contract below with nothing to cover. There is no ceiling on the count — a bug that honestly contains fifteen distinct defects has fifteen, and the answer to that is the \`needs-prd\` sizing below, never a shorter list.
- affectedFiles: the files that must change to fix it (paths).
- blastRadius: the callers, flows, and services impacted if the bug ships or the fix regresses.
- surfaces: which surfaces from the CLOSED SET below the fix actually touches. This decides which specialist test writers run downstream, so it is a real decision, not a label:
    api-contract           a published REST/GraphQL/event schema that consumers depend on
    event-chain            the event delivery path between publisher and consumer
    auth                   authentication, authorization, or permission evaluation
    performance            a stated performance budget or latency/throughput requirement
    web-ui                 web user interface
    ios                    native iOS
    android                native Android
    cross-platform-mobile  React Native or other cross-platform mobile
    ml                     matching, recommendation, ranking, or embeddings
    data-pipeline          ETL, CDC, or stream processing
  Return ONLY surfaces the CHANGE touches — not surfaces the surrounding code happens to sit near. Return an empty list when the fix is confined to internal logic, which is the common case. Each surface you name costs a full additional test-authoring agent; each one you omit leaves that surface with no specialist coverage.
- repoPath: the ABSOLUTE path of the repository the defect lives in${repoKnown ? ' — echo the repository you were given' : ''}.
- repoResolution: how you confirmed the repository${repoKnown ? ' (one line; it was supplied)' : ', or why none could be confirmed'}.${LOCATE_REPO}`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      // The repository is REQUIRED when it is not known: it is the finding the caller builds
      // in, and an omitted field reads the same as an honest "could not locate" (empty string).
      required: ['reproduction', 'rootCause', 'defects', 'affectedFiles', 'blastRadius', 'surfaces', ...(repoKnown ? [] : ['repoPath', 'repoResolution'])],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        // At least one — stated in the brief above, and counted once the result is in
        // hand. Never bound here: a bound on this list answers a one-over enumeration by
        // destroying the reproduction, the root cause and the repository resolution along
        // with it, and triage then has nothing at all.
        defects: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'mechanism'],
            properties: {
              id: { type: 'string' },
              mechanism: { type: 'string' },
              file: { type: 'string' },
              line: { type: 'integer' },
            },
          },
        },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
        repoPath: { type: 'string' },
        repoResolution: { type: 'string' },
        surfaces: {
          type: 'array',
          items: {
            type: 'string',
            enum: [
              'api-contract',
              'event-chain',
              'auth',
              'performance',
              'web-ui',
              'ios',
              'android',
              'cross-platform-mobile',
              'ml',
              'data-pipeline',
            ],
          },
        },
      },
    },
  }
)

// A dead dispatch is not a diagnosis, a sizing or a contract. Each death returns the
// `dispatchFailed` shape every other mini returns, so the caller reports it under the
// environment stage and never checkpoints it as a contract.
const triageDied = (what) => {
  const deaths = dispatchDeaths('Triage')
  const reason = `the triage ${what} returned nothing — ${deaths.map((f) => f.note).join('; ') || 'no dispatch was recorded'}`
  log(`Triage: ${reason}`)
  return { ok: false, dispatchFailed: true, dispatchFailures: deaths, reason }
}
if (!analysis) return dispatchOutcome(triageDied('diagnosis'))

// 1b) SIZING — is this a fix, or a redesign wearing a bug ticket?
//
// The repository the fix is built in. A supplied one is the answer; otherwise it is what
// the diagnosis LOCATED, reported as a finding beside the blast radius. Never a guess made
// here: an empty string is carried as null and the caller refuses to write without one.
// Measured here so the count is observed on the needs-prd path too. An observation only:
// every defect is carried forward, and the `at least one` is the only thing asked for.
checkLimit('Triage', 'defects', Array.isArray(analysis.defects) ? analysis.defects : [], DEFECTS_EXPECTED, 1)
// A diagnosis that enumerated no defect still names a root cause, and that root cause is the
// one defect: it becomes D1, so the contract's coverage join has an id to resolve against
// instead of criteria pointing at a defect nobody listed.
const enumerated = (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id)
const defects = enumerated.length ? enumerated : [{ id: 'D1', mechanism: String(analysis.rootCause || 'the diagnosed root cause') }]
const resolvedRepoPath = repoKnown ? bead.repoPath : String((analysis && analysis.repoPath) || '').trim() || null
if (!repoKnown) log(`Triage: repository ${resolvedRepoPath ? `located at ${resolvedRepoPath}` : 'NOT located'} — ${(analysis && analysis.repoResolution) || 'no resolution reported'}`)

// A bug can be worked directly, or it can turn out to need a PRD and an Epic. The
// difference matters: the fix path has no PRD validation, no architecture ruling,
// and no spec — so a defect whose honest remedy is "redesign how this service
// stores its data" would get that redesign built by an implementer, unreviewed,
// on the authority of a bug ticket. That is how an architecture decision gets made
// by accident, which is the failure this workforce exists to prevent.
//
// A DIFFERENT agent sizes it — the diagnostician has just invested in a root cause
// and is the worst-placed judge of whether fixing it is too big.
const sizing = await settleAgent(
  `Size this bug. It has been diagnosed; decide whether its honest remedy is a FIX or a REDESIGN. You are READ-ONLY and you are NOT proposing the remedy — only sizing it.

Answer "needs-prd" when the honest fix would: change a public contract or event schema, alter the data model, cross a service boundary, require an architecture decision the effective architecture does not cover, or amount to rebuilding a component rather than correcting it.

Answer "fix" when the defect is a mistake in existing behavior that can be corrected within the current design — the common case. Do not inflate a real bug into a project; most bugs are bugs.

The cost of each error is not symmetric. Calling a redesign a "fix" ships an unreviewed architecture change on a bug ticket. Calling a fix a "redesign" costs a PRD nobody needed. Prefer "fix" when genuinely balanced, and "needs-prd" when the remedy touches a contract, a schema, or a boundary.

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Root cause found: ${analysis.rootCause}
Files that must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}
Blast radius: ${analysis.blastRadius}`,
  {
    label: 'triage:sizing',
    phase: 'Triage',
    agentType: 'architecture-boundary-guardian',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['scope', 'rationale'],
      properties: {
        scope: { type: 'string', enum: ['fix', 'needs-prd'] },
        rationale: { type: 'string' },
        contractsTouched: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// A missing verdict must not silently become "fix" — that is the expensive error — and it
// is not a "needs-prd" ruling either, so a dead sizing stops the run as a dispatch death.
if (!sizing) return dispatchOutcome(triageDied('sizing'))
const scope = sizing.scope || 'needs-prd'
const scopeRationale = sizing.rationale || 'sizing returned no rationale'
if (scope === 'needs-prd') {
  log(`Bug ${bead.id || ''} sized as NEEDS-PRD: ${scopeRationale}`)
  return dispatchOutcome({
    bead,
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    contractsTouched: sizing.contractsTouched || [],
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects,
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: [],
    ...(limitFindings.length ? { limitFindings } : {}),
    note:
      'This defect needs a PRD and an Epic, not a fix. Its honest remedy changes a contract, ' +
      'schema, or boundary, and the fix path has no PRD validation, no architecture ruling, and ' +
      'no spec to review it against. Promote it: /agent-teams-workforce:start-prd, or dispatch ' +
      'prd-to-spec with { request } built from the diagnosis above. Promotion is a human decision.',
  })
}

// 2) Expected-behavior contract — the "spec-lite" a bug lacks, as testable AC.
//    A different agent than the diagnostician (no self-authoring of its own contract).
//
// SCOPED BY CONSTRUCTION. This step used to receive a prose root cause with no expected
// range, no defect index, and no scope rule — and a four-defect bug produced eighteen-plus
// criteria, several of them repo-wide greps. The downstream coverage reviewer then
// blocked on partial coverage of criteria Red could never legitimately turn red, and the
// Red gate exhausted without one line of production code being written.
//
// The defect index is what fixed that: coverage becomes an exact join — every defectId
// resolves, every defect has at least one criterion — instead of a judgment call, and it
// is computed below from the result. The range is stated to the writer and OBSERVED
// afterwards; it is never a schema bound, because a bound does not trim an over-long
// list, it destroys the whole contract and halts the bug fix at triage.
// Unique, because they become a schema enum below and a repeated enum value is an invalid
// schema: a diagnosis that reused an id would otherwise kill the contract writer's dispatch.
const defectIds = [...new Set(defects.map((d) => String(d.id)))]
const AC_MIN = Math.max(1, defectIds.length)
const AC_MAX = Math.max(2, defectIds.length * 2)
log(`Triage: ${defectIds.length} defect(s) — acceptance criteria expected in the range ${AC_MIN}..${AC_MAX}`)

const contractSchema = (ids) => ({
  type: 'object',
  additionalProperties: false,
  required: ['acceptanceCriteria'],
  properties: {
    acceptanceCriteria: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['defectId', 'given', 'when', 'then'],
        properties: {
          defectId: ids.length ? { type: 'string', enum: ids } : { type: 'string' },
          given: { type: 'string' },
          when: { type: 'string' },
          then: { type: 'string' },
        },
      },
    },
    // Sibling output, deliberately NOT passed to tdd-red. A repo-wide invariant is a
    // lint rule or a pre-commit hook, landed by the path that already commits — the
    // coverage reviewer never sees it and therefore structurally cannot block the
    // Red gate on a criterion Red can never turn red.
    lintRules: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['pattern', 'rationale'],
        properties: {
          pattern: { type: 'string' },
          rationale: { type: 'string' },
          scope: { type: 'string' },
        },
      },
    },
  },
})
const contract = await settleAgent(
  `Write the expected-behavior contract for this bug fix as testable given/when/then acceptance criteria — the correct behavior the fix must satisfy and that a failing test will encode. Do NOT write code.

ONE OR TWO CRITERIA PER DEFECT, and every criterion carries the id of the defect it covers. Every defect below must have at least one. Between ${AC_MIN} and ${AC_MAX} criteria in total — if you are heading past ${AC_MAX} you are enumerating variants of one behaviour, and every criterion you write is one Red must encode.

A CRITERION DESCRIBES AN EXECUTION, NOT THE REPOSITORY. Apply this test to everything you are about to write: **if it would still be checkable with the change reverted, it is not an acceptance criterion.** "No occurrence of \`redis://\` anywhere in the repo" passes that test trivially — it is checkable before, during and after the fix, against code nobody touched — which is exactly what makes it a LINT RULE wearing an acceptance-criterion costume. Return those in \`lintRules\` instead. They are real and they are worth enforcing; they are just not something a failing test can encode, and putting them here blocks the build on a grep no Red phase can legitimately make fail.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}
Files the fix must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}

Defects to cover (use these ids exactly):
${defects.map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n')}`,
  {
    label: 'triage:expected-behavior',
    phase: 'Triage',
    agentType: 'acceptance-criteria-writer',
    schema: contractSchema(defectIds),
  }
)

// A contract with no criteria gives Red nothing to encode, so a dead writer stops here.
if (!contract) return dispatchOutcome(triageDied('expected-behavior writer'))

// Coverage is an exact join, not a judgment: every enumerated defect must have at least
// one criterion pointing at it.
const authoredAc = (Array.isArray(contract.acceptanceCriteria) ? contract.acceptanceCriteria : []).filter(Boolean)
const coveredIds = () => new Set(authoredAc.map((x) => String(x.defectId || '')))
// A defect with no criterion gets no test and no fix, so the writer is asked ONCE more, for
// those defects only — a re-dispatch with materially different input, not a blind retry.
const firstUncovered = defectIds.filter((id) => !coveredIds().has(id))
if (firstUncovered.length) {
  log(`Triage: defect(s) with no acceptance criterion: ${firstUncovered.join(', ')} — asking the writer to cover them`)
  const gap = await settleAgent(
    `The expected-behavior contract for this bug fix covers every defect below EXCEPT the ones listed. Write one or two testable given/when/then acceptance criteria for EACH listed defect, and nothing else — no criterion for a defect not listed, no repo-wide grep (return one in \`lintRules\` if you find one). Do NOT write code.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}

Defects still uncovered (use these ids exactly):
${defects.filter((d) => firstUncovered.includes(String(d.id))).map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n')}`,
    {
      label: 'triage:expected-behavior-uncovered',
      phase: 'Triage',
      agentType: 'acceptance-criteria-writer',
      schema: contractSchema(firstUncovered),
    }
  )
  // Defects with no criterion would ship with no test and no fix, so a dead follow-up is a
  // dispatch death like any other triage step, not a contract to build on.
  if (!gap) return dispatchOutcome(triageDied('expected-behavior writer (uncovered defects)'))
  authoredAc.push(...(Array.isArray(gap.acceptanceCriteria) ? gap.acceptanceCriteria : []).filter(Boolean))
  if (Array.isArray(gap.lintRules)) {
    contract.lintRules = [...(Array.isArray(contract.lintRules) ? contract.lintRules : []), ...gap.lintRules]
  }
}
const uncoveredDefects = defectIds.filter((id) => !coveredIds().has(id))
// Asked twice and still uncovered: those defects would get no test and no fix while the run
// reported the bug fixed, so the contract is refused rather than built. The writer answered
// both times, so this is not a dispatch death; it is reported under triage, naming the defects.
if (uncoveredDefects.length) {
  const reason = `the expected-behavior contract still covers no criterion for defect(s) ${uncoveredDefects.join(', ')} after the writer was asked for exactly those — a fix built on it would leave them untested and unfixed`
  log(`⚠ Triage: ${reason}`)
  return dispatchOutcome({
    ok: false,
    contractIncomplete: true,
    reason,
    uncoveredDefects,
    bead,
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects,
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: authoredAc,
    ...(limitFindings.length ? { limitFindings } : {}),
  })
}
// The range is an expectation, not a gate: every criterion is carried through either way.
checkLimit('Triage', `acceptance criteria for ${defectIds.length} defect(s)`, authoredAc, AC_MAX, AC_MIN)
const lintRules = (Array.isArray(contract.lintRules) ? contract.lintRules : []).filter(Boolean)
if (lintRules.length) log(`Triage: ${lintRules.length} repo-wide invariant(s) routed to lint, not to the Red phase`)

return dispatchOutcome({
  bead,
  repoPath: resolvedRepoPath,
  repoResolution: (analysis && analysis.repoResolution) || null,
  scope,
  scopeRationale,
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  defects,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  // Consumed by tdd-red to DERIVE its test writers. Empty means unit tests only,
  // which is the correct answer for a fix confined to internal logic.
  surfaces: analysis.surfaces || [],
  acceptanceCriteria: authoredAc,
  uncoveredDefects: [],
  ...(limitFindings.length ? { limitFindings } : {}),
  // Repo-wide invariants the writer routed out of the acceptance criteria. Recorded in the
  // run journal; no phase reads them, and they are never handed to the Red phase.
  lintRules,
})
