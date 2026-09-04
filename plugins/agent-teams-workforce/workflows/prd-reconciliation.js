export const meta = {
  name: 'prd-reconciliation',
  description:
    'Leaf mini — PRD Reconciliation. ONE independent read-only checker session performs both reconciliation checks (PRD-vs-reality, upstream dependency changes) — both are checks on a document authored upstream, so folding them into one session preserves segregation of duties while paying one session-start instead of two — then the script reduces the findings to ONE verdict: which requirements already shipped, which remain, and how big the REMAINING delta is. Every requirement status must be backed by a file:line or a live deployed endpoint — a status with no evidence behind it is not honoured and its requirement stays in the delta. Read-only apart from writing the delta PRD: it judges what is already built and authors no new requirement.',
  phases: [
    { title: 'Reconciliation checks', detail: 'one independent read-only checker session runs both checks' },
    { title: 'Delta', detail: 'the remaining requirements are written to a delta PRD and the work is sized by what is LEFT' },
  ],
}

// args: {
//   prd: {                      // the PRD being reconciled against reality (required)
//     id?: string,
//     title?: string,
//     body: string,             // the PRD text — required; a path alone cannot be read by a script
//     path?: string,            // where the PRD document lives (used to site the delta beside it)
//     repoPath?: string,        // the repo the PRD nominally targets
//   },
//   repos?: string[],           // every repo the PRD may span — informs the epic/story size call
//   deltaPath?: string,         // where to write the delta PRD; derived from prd.path when absent
//   dependencies?: string[],    // upstream contracts/schemas/libs the PRD assumes
//   awsProfile?: string,        // AWS profile for live-endpoint checks (default 'dev')
// }
//
// WHY THIS MINI EXISTS
//
// A PRD is a statement of what someone WANTED. It is not a statement of what is
// missing. Nothing upstream of specification establishes what already exists, so a
// PRD written against a capability that partly or largely shipped gets specified,
// decomposed and built a second time — over working code. An audit of 20 Epics in
// one project found ELEVEN written as greenfield against shipped behaviour: a
// 929-line MFA implementation that was merely disabled, a fully deployed passkey
// ceremony, three live OAuth providers, a shipped session dashboard.
//
// So the pipeline establishes reality FIRST, and everything downstream is specified
// against the DELTA — the requirements that are genuinely absent or partial — never
// against the original ambition.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = (typeof prdInput === 'string' ? '' : prdInput.id) || ''
const prdTitle = (typeof prdInput === 'string' ? '' : prdInput.title) || ''
const prdPath = (typeof prdInput === 'string' ? '' : prdInput.path) || ''
const repoPath = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || a.repoPath || ''
const repos = (Array.isArray(a.repos) && a.repos.length ? a.repos : [repoPath]).filter((r) => r)
const dependencies = Array.isArray(a.dependencies) ? a.dependencies : []
const awsProfile = a.awsProfile || 'dev'

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''
const hasText = (v) => typeof v === 'string' && v.trim().length > 0

// ── A DEAD DISPATCH ARRIVES AS A THROW, NOT AS A NULL ───────────────────────────
//
// This mini was written against one runtime behaviour and meets two. `agent()` hands
// back NULL when a subagent is skipped or dies on a terminal API error, and the
// `!reality` guard below was built for exactly that. But a subagent that RUNS and then
// finishes WITHOUT emitting its structured output THROWS, and the throw leaves the mini,
// leaves the composite, and aborts the whole run — the same crash bug-fix.js records at
// 1.13M tokens on ssbd-mqkq. Nothing catches it here, so every line below, including the
// entire `dispatchFailed` contract this mini owes its caller, is unreachable for the
// failure mode that actually happens. ssbd-nc8z died this way twice, at the same phase,
// and both times the supervisor was handed a bare abort with no classification.
//
// So dispatch through here. A throw and a null are the same event — "no account came
// back" — and both must reach the guards as null so the caller learns it was the
// ENVIRONMENT that failed and not the PRD.
//
// The single retry is the other half. A reconciliation cannot degrade: proceeding
// without knowing what already ships is precisely the greenfield assumption this phase
// exists to remove, so a dead dispatch has no fallback except to run again. One extra
// attempt is the difference between a coin-flip and a phase that completes; more than
// one turns a systematic failure into an expensive systematic failure.
const MAX_DISPATCH_ATTEMPTS = 2
const dispatchNotes = []

async function dispatch(label, prompt, opts) {
  let why = null
  for (let attempt = 1; attempt <= MAX_DISPATCH_ATTEMPTS; attempt++) {
    let out = null
    try {
      out = await agent(prompt, opts)
    } catch (e) {
      out = null
      why = `threw: ${e && e.message ? e.message : String(e)}`
    }
    if (out) return out
    if (!why) why = 'returned nothing — skipped, or died on a terminal API error'
    dispatchNotes.push(`${label} attempt ${attempt}/${MAX_DISPATCH_ATTEMPTS} — ${why}`)
    if (attempt < MAX_DISPATCH_ATTEMPTS) log(`${label}: dispatch died (${why}) — dispatching once more.`)
    why = null
  }
  log(`${label}: dispatch failed on all ${MAX_DISPATCH_ATTEMPTS} attempt(s) — ${dispatchNotes[dispatchNotes.length - 1]}`)
  return null
}

// `extra` carries `dispatchFailed` when the failure is a dead agent rather than a
// finding — see the reconciler check below. The caller reads that field to decide
// whether it holds a verdict about the PRD or an account that never came back.
const fail = (reason, extra) => ({
  ok: false,
  reason,
  verdict: 'greenfield',
  requirements: [],
  deltaCount: 0,
  deltaPrdPath: null,
  sizeVerdict: 'close',
  infraOnly: false,
  ...(extra || {}),
})

if (!hasText(prdBody)) {
  // Refuse rather than report a zero delta. "No requirements remain" and "no PRD was
  // supplied" both reduce to deltaCount 0, and the caller closes the work item on the
  // first. Conflating them closes work nobody looked at.
  return fail('prd-reconciliation invoked with an empty PRD body — there is nothing to reconcile against reality.')
}

const prdHeader = `PRD ${prdId}${prdTitle ? `: ${prdTitle}` : ''}`.trim()
const prdBlock = `${prdHeader}\n\n${prdBody}`
const repoBlock = repos.length
  ? repos.map((r, i) => `${i + 1}. ${r}`).join('\n')
  : '(no repo paths supplied — discover the repositories this PRD touches from the PRD text)'

// ── Phase 1: Reconciliation checks — ONE independent checker session, both checks ──
// This used to be two parallel sessions, each paying a full session-start to read the
// same PRD and the same repositories. Both are read-only CHECKS on a document authored
// upstream — neither ever judged the other's output — so one session carrying both
// preserves segregation of duties, and the reduction below still judges no code: it
// applies a fixed rule to the typed findings.
phase('Reconciliation checks')

const combined = await dispatch(
  'reconcile:reality-and-dependencies',
  `${rulingsBlock}Reconcile this PRD against what is ALREADY BUILT AND DEPLOYED, and detect upstream changes that invalidate what it assumes. You are READ-ONLY over the codebase and the cloud account: read, search and query all you need, but change nothing anywhere. Two checks, one pass — return both.

═══ CHECK 1 — PRD vs reality ═══

${prdBlock}

Repositories in scope:
${repoBlock}

Enumerate EVERY requirement the PRD states, and for each one determine which of these is true NOW:
- shipped   — the behaviour the requirement asks for exists and works today.
- partial   — some of it exists; name precisely what is missing.
- absent    — none of it exists.
- obsolete  — the requirement no longer applies (the product moved past it, or something else supersedes it).

EVIDENCE IS MANDATORY AND IT IS THE WHOLE POINT OF THIS CHECK. Every status you return must cite concrete evidence: a \`file:line\` you actually read, or a live deployed endpoint you actually called. A requirement you call shipped with nothing behind it is the exact error this check exists to prevent, and it will be DISCARDED and treated as absent — costing the reader nothing but costing you the finding. Prefer several pieces of evidence over one.

You hold full AWS admin credentials. Checking a live endpoint is legitimate and is often the decisive evidence — a capability can be fully implemented in the repository and switched off in infrastructure, which reads as shipped from the code alone and as absent from the deployed system. Look for both. EVERY aws command you run MUST pass \`--profile ${awsProfile}\`; a command without it targets the wrong account.

Look specifically for the failure modes that make a shipped capability read as greenfield:
- an implementation that is complete but DISABLED by a feature flag, a commented-out construct, or an infrastructure switch — cite the file:line of the switch;
- a frontend that is fully scaffolded over a backend that does not exist, or the reverse;
- a capability live for some cases and not others (three of four identity providers, one of two flows);
- a route table, handler list, or CDK stack that already serves what the PRD asks for.

Also decide, for each requirement that is NOT already fully shipped:
- needsNewContract — true if closing the gap requires a NEW OR CHANGED contract: an HTTP route, an event, a schema, a public interface. False if the contract already exists and only its behaviour must change.
- behaviourExistsButWrong — true if the behaviour EXISTS but is wrong, broken, or switched off. False if it must be built.
- repos — the repositories the remaining work touches.

Finally judge, across the WHOLE remaining delta:
- deltaIsInfraOnly — true only if every remaining requirement is satisfied by an infrastructure change alone (a flag, a stack parameter, a permission, a provisioned resource) with no application code to write.
- unsettledTechnicalDecision — true if a technical decision that nobody has made yet still blocks the remaining work. An existing pattern in the codebase, or a decision already recorded, means FALSE.

Do not soften a finding to be agreeable in either direction. Claiming shipped work is absent causes it to be rebuilt; claiming absent work is shipped causes it never to be built at all.

═══ CHECK 2 — upstream dependency changes ═══

Upstream dependencies the PRD relies on:
${dependencies.length ? dependencies.map((d, i) => `${i + 1}. ${d}`).join('\n') : '(none declared in args — discover them from the PRD text and the repositories above)'}

Determine whether any upstream contract, shared schema, event, library version, or interface the PRD assumes has changed in a way that invalidates one of its assumptions. This is not a search for defects in the PRD's wording — it is a search for ground that moved. Return this check under \`dependencyChanges\`:
- current: true if no invalidating upstream change is found, false otherwise.
- changeFindings: each invalidating change (dependency, change describing what changed, invalidates describing which PRD assumption it breaks).
- evidence: how you verified the dependency state (one paragraph, under 60 words).

═══ YOUR BUDGET ═══

Your structured output IS the deliverable. Nothing you read reaches anybody except through it, so an exhaustive investigation that ends without it is worth exactly as much as no investigation at all — and it is how this phase has failed in practice: the reconciler explored until it ran out of room and returned nothing, so the whole run aborted and the work was re-dispatched from zero.

You have roughly 50 tool calls. Spend them breadth-first: cover EVERY requirement at least once before you deepen any of them, because a requirement you never looked at defaults to absent and gets rebuilt. By call 50, stop investigating and emit your structured output with whatever you have — a partial inventory with honest evidence is a usable result; a perfect inventory you never returned is not. Report thin coverage in \`evidenceSummary\` rather than spending more turns on it.`,
  {
    label: 'reconcile:reality-and-dependencies',
    phase: 'Reconciliation checks',
    agentType: 'agent-teams-workforce:prd-reality-reconciler',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['requirements', 'deltaIsInfraOnly', 'unsettledTechnicalDecision', 'evidenceSummary', 'dependencyChanges'],
      properties: {
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'status', 'evidence'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              status: { type: 'string', enum: ['shipped', 'partial', 'absent', 'obsolete'] },
              // minItems is load-bearing: a status with no evidence behind it is the
              // defect this mini exists to catch, so the schema refuses to express one.
              // The reduction below enforces the same rule again, because a schema
              // constrains what a model is ASKED for, not what it returns.
              evidence: { type: 'array', minItems: 1, items: { type: 'string' } },
              missing: { type: 'string' },
              needsNewContract: { type: 'boolean' },
              behaviourExistsButWrong: { type: 'boolean' },
              repos: { type: 'array', items: { type: 'string' } },
            },
          },
        },
        deltaIsInfraOnly: { type: 'boolean' },
        unsettledTechnicalDecision: { type: 'boolean' },
        decisionRationale: { type: 'string' },
        evidenceSummary: { type: 'string' },
        dependencyChanges: {
          type: 'object',
          additionalProperties: false,
          required: ['current', 'changeFindings', 'evidence'],
          properties: {
            current: { type: 'boolean' },
            changeFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['dependency', 'change', 'invalidates'],
                properties: {
                  dependency: { type: 'string' },
                  change: { type: 'string' },
                  invalidates: { type: 'string' },
                },
              },
            },
            evidence: { type: 'string' },
            notes: { type: 'string' },
          },
        },
      },
    },
  }
)

const reality = combined
const dependencyChanges = (combined && combined.dependencyChanges) || null

// ── A DEAD AGENT IS NOT A FINDING ───────────────────────────────────────────────
//
// A dispatch dies in two ways — skipped or dead on a terminal API error (null), or run
// to completion without ever emitting its structured output (a throw). `dispatch()`
// above normalizes both to null and has already spent its retry. Neither is the same
// event as a reconciler that ran and returned a malformed inventory, and folding them
// together is what turned two of the five real prd-to-spec runs into work failures at
// stage 'prd-reconciliation': the supervisor charged the bead for an account limit.
// Both still stop the run — reading "we could not establish what exists" as "nothing
// exists" is the greenfield assumption this phase removes — but only one of them is
// anybody's fault, and the caller needs to be able to tell which.
if (!reality) {
  return fail(
    'the reality reconciler never came back with an account of what already ships, on any attempt, so no ' +
      `reconciliation was performed (${dispatchNotes.join('; ')}). This is a DISPATCH failure, not a verdict on ` +
      'the PRD or on what already ships.',
    { dispatchFailed: true, dispatchFailures: dispatchNotes.slice() }
  )
}
if (!Array.isArray(reality.requirements)) {
  return fail('the reality reconciler returned no requirement inventory — reconciliation cannot be reduced to a verdict.')
}

// ── Evidence enforcement ────────────────────────────────────────────────────────
// A schema constrains the REQUEST, not the response, so the rule is applied again
// here where it is deterministic and testable. The two directions of error are not
// symmetric: an unevidenced "absent" costs a rebuild of nothing, while an
// unevidenced "shipped" deletes real work from the delta and it is never built. So
// an unevidenced claim is never resolved in favour of the claim — it drops to
// 'absent', keeping the requirement in the delta, and the demotion is reported.
//
// Evidence for shipped/obsolete must also LOOK like evidence: a file:line, a URL, a
// named endpoint, or an AWS resource identifier. "I checked the code" is a claim
// about the checker, not about the system.
const strongEvidence = (s) =>
  /:\d+/.test(s) || /https?:\/\//i.test(s) || /\bendpoint\b/i.test(s) || /\barn:aws\b/i.test(s)

const evidenceViolations = []
const requirements = reality.requirements.map((r, i) => {
  const id = hasText(r && r.id) ? r.id : `R${i + 1}`
  const evidence = (Array.isArray(r && r.evidence) ? r.evidence : []).filter((e) => hasText(e)).map((e) => e.trim())
  const claimed = (r && r.status) || 'absent'
  let status = claimed
  if (!evidence.length) {
    status = 'absent'
    evidenceViolations.push({ id, claimedStatus: claimed, reason: 'no evidence supplied' })
  } else if ((claimed === 'shipped' || claimed === 'obsolete') && !evidence.some(strongEvidence)) {
    status = 'absent'
    evidenceViolations.push({
      id,
      claimedStatus: claimed,
      reason: 'no file:line, deployed endpoint, URL, or AWS resource identifier among the evidence',
    })
  }
  return {
    id,
    requirement: (r && r.requirement) || '',
    status,
    evidence,
    missing: (r && r.missing) || null,
    needsNewContract: !!(r && r.needsNewContract),
    behaviourExistsButWrong: !!(r && r.behaviourExistsButWrong),
    repos: Array.isArray(r && r.repos) ? r.repos.filter((x) => hasText(x)) : [],
    claimedStatus: claimed,
  }
})

if (evidenceViolations.length) {
  log(
    `Evidence enforcement: ${evidenceViolations.length} requirement status claim(s) had no evidence behind them and were ` +
      `demoted to 'absent' — they stay in the delta rather than being written off as built.`
  )
}

// ── Reduction: verdict, delta, size ─────────────────────────────────────────────
// All three are computed HERE, from the typed findings, rather than asked of a model.
// A size class is a rule, not a judgement, once the requirement statuses are known,
// and a rule can be tested.
const delta = requirements.filter((r) => r.status === 'absent' || r.status === 'partial')
const deltaCount = delta.length
const anyBuilt = requirements.some((r) => r.status === 'shipped' || r.status === 'partial' || r.status === 'obsolete')
const verdict = deltaCount === 0 ? 'shipped' : anyBuilt ? 'partial' : 'greenfield'

const deltaRepos = []
for (const r of delta) {
  for (const x of r.repos) if (deltaRepos.indexOf(x) === -1) deltaRepos.push(x)
}
const spansMultipleRepos = deltaRepos.length > 1
const unsettledDecision = !!reality.unsettledTechnicalDecision
const needsContract = delta.some((r) => r.needsNewContract)
const allExistingBehaviour = deltaCount > 0 && delta.every((r) => r.behaviourExistsButWrong)
const infraOnly = deltaCount > 0 && !!reality.deltaIsInfraOnly

// Sized by what is LEFT, never by the original ambition. The PRD that asked for a
// whole authentication system is a bug ticket when the only thing left is a flag.
let sizeVerdict
if (deltaCount === 0) sizeVerdict = 'close'
else if (spansMultipleRepos && unsettledDecision) sizeVerdict = 'epic'
else if (needsContract) sizeVerdict = 'story'
else if (allExistingBehaviour) sizeVerdict = 'bug'
else sizeVerdict = 'task'

log(
  `Reconciliation: ${verdict} — ${deltaCount} of ${requirements.length} requirement(s) remain; sized '${sizeVerdict}'` +
    `${infraOnly ? ' (infrastructure only)' : ''}.`
)

// ── Phase 2: Delta — the PRD rewritten to ONLY what is left ─────────────────────
// Nothing is written when nothing remains: a closed item costs no authoring pass.
phase('Delta')

let deltaPrdPath = null
let deltaPrdBody = null
if (deltaCount > 0) {
  const suggestedPath = a.deltaPath || (hasText(prdPath) ? `${prdPath.replace(/\.md$/i, '')}.delta.md` : '')
  const written = await dispatch(
    'delta:write',
    `${rulingsBlock}Write the DELTA PRD: this PRD rewritten to contain ONLY the requirements that are still absent or partial. Everything downstream of here — validation, architecture, the TRD, the specs, the tasks — reads THIS document and never the original, so a requirement you carry across is a requirement that gets built again.

Original PRD:
${prdBlock}

Requirements that REMAIN (these, and only these, belong in the delta PRD):
${JSON.stringify(delta.map((r) => ({ id: r.id, requirement: r.requirement, status: r.status, missing: r.missing, evidence: r.evidence })), null, 2)}

Requirements that are ALREADY SATISFIED and MUST NOT appear as work (carry them only as a short "Already shipped" note so the reader knows they were considered):
${JSON.stringify(requirements.filter((r) => r.status === 'shipped' || r.status === 'obsolete').map((r) => ({ id: r.id, requirement: r.requirement, status: r.status, evidence: r.evidence })), null, 2)}

Write it to: ${suggestedPath || 'a path you choose beside the original PRD, or in the repository under reconciliation'}

Rules:
- Keep the original PRD's structure and its voice. This is the same document, narrowed — not a new one.
- Requirements stay at the WHAT altitude. Do not add mechanism, thresholds, or schemas.
- A 'partial' requirement is rewritten to ask for ONLY the part that is missing, and cites the evidence of what already exists.
- Invent no requirement that the original does not state.
- Return the full text you wrote in \`body\` and the path you wrote it to in \`path\`.`,
    {
      label: 'delta:write',
      phase: 'Delta',
      agentType: 'agent-teams-workforce:prd-reality-reconciler',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['ok', 'path', 'body'],
        properties: {
          ok: { type: 'boolean' },
          path: { type: 'string' },
          body: { type: 'string' },
          error: { type: 'string' },
        },
      },
    }
  )
  if (!written || written.ok !== true || !hasText(written.path) || !hasText(written.body)) {
    // An author that never came back is an environment failure, exactly as a reconciler
    // that never came back is. An author that RAN and reported it could not write is a
    // finding about the work. Same stop, different owner — so they are classified apart.
    const authorDied = !written
    return fail(
      `${deltaCount} requirement(s) remain but the delta PRD was not written` +
        `${authorDied ? ` — the author never came back on any attempt (${dispatchNotes.join('; ')})` : ''}` +
        `${written && written.error ? `: ${written.error}` : ''}. ` +
        'Downstream phases must never be handed the original PRD, so the run stops here rather than specifying shipped behaviour.',
      authorDied ? { dispatchFailed: true, dispatchFailures: dispatchNotes.slice() } : undefined
    )
  }
  deltaPrdPath = written.path
  deltaPrdBody = written.body
  log(`Delta PRD written to ${deltaPrdPath} (${deltaPrdBody.length} chars, ${deltaCount} requirement(s)).`)
}

const ledger = {
  phase: 'prd-reconciliation',
  beadId: null,
  subject: prdId || prdTitle || null,
  chosen: ['prd-reality-reconciler (both checks, one session)'],
  mode: 'combined', // one checker session carries both reconciliation checks
  verdict,
  deltaCount,
  sizeVerdict,
  evidenceViolations: evidenceViolations.length,
  ok: true,
}

return {
  ok: true,
  verdict,
  requirements,
  deltaCount,
  deltaPrdPath,
  sizeVerdict,
  // The delta TEXT, not only its path: a workflow script has no filesystem, so a
  // caller handed a path alone would have to spend an agent to read back a document
  // that was just authored in this run.
  deltaPrd: deltaPrdPath ? { path: deltaPrdPath, body: deltaPrdBody } : null,
  // Needed by the caller to reroute an infrastructure-only delta away from the
  // product pipeline; it is a property of the delta, so this mini is where it is known.
  infraOnly,
  evidenceViolations,
  dependencyChanges,
  sizing: {
    deltaRepos,
    spansMultipleRepos,
    unsettledDecision,
    needsContract,
    allExistingBehaviour,
    rationale: (reality && reality.decisionRationale) || null,
  },
  evidenceSummary: (reality && reality.evidenceSummary) || null,
  ledger,
}
