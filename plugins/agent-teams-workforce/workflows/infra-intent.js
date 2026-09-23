export const meta = {
  name: 'infra-intent',
  description:
    'Leaf mini — Infrastructure provisioning intent. A maker (cdk-infrastructure-designer) produces concrete, CDK-expressible provisioning intent; independent checkers then review it in parallel (security scan + cost impact). On a blocking cost finding the maker re-runs with checker feedback (bounded 2 passes), and security is re-checked on the rewritten intent; a cost finding still blocking after that leaves the intent not ready. Returns a top-level `ready`. Read-only review — no agent judges its own artifact.',
  phases: [
    { title: 'Provisioning intent', detail: 'cdk-infrastructure-designer authors the intent' },
    { title: 'Review', detail: 'independent security scan + cost-impact review' },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// Each `dispatchFailures` entry ALSO carries the CAUSE — see failureCause below — because
// a caller that can only see THAT a dispatch produced nothing cannot tell the one failure
// worth sending again from the many that are not. `failureCauseFor(label)` is how a call
// site reads it back, and a TRANSIENT cause is waited out inside settleAgent itself, so
// every dispatch in every script survives an API overload rather than only some of them.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
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
// ── WHY A DISPATCH FAILED DECIDES WHETHER ANYTHING MAY BE SENT AGAIN ─────────────
//
// settleAgent used to collapse every failure into a single null, and that conflation is
// the same defect that let a destroyed answer look like a dead agent: a call site could
// see THAT a dispatch produced nothing and never WHY. Two causes need opposite answers,
// and getting them the same way round is what makes this a classification and not a
// retry loop wearing a hat.
//
// TRANSIENT — an Anthropic API overload (529), a rate limit (429), a quota or token
// limit, a network timeout. The cause is EXTERNAL and TIME-VARYING, the input was never
// the problem, and the call that failed produced nothing to pay for. Waiting and sending
// the same dispatch again therefore has a real reason to come out differently, which is
// the only thing that ever justifies a second attempt. This is the one case retried here,
// and it is retried until it clears — see the backoff below. It is never answered by
// splitting the input: the input was fine, and splitting multiplies calls against an
// endpoint that is already failing to serve the first one.
//
// DETERMINISTIC — a schema rejection, an agent that finished without producing output,
// anything settled by arithmetic. Re-issuing the identical dispatch against the identical
// input has NO reason to produce a different result; it is a hope with a token cost, and
// this project removed exactly those blind retries after they burned tokens to exhaustion
// on attempts that could not succeed. The only sanctioned re-dispatch is one with
// materially CHANGED input — for the SAD batches, the split.
//
// ANYTHING UNRECOGNISED IS DETERMINISTIC, and that direction is deliberate rather than
// defensive. Guessing "transient" on an unknown error invents a retry that is forbidden
// and pays for it on every unfamiliar failure; guessing "deterministic" at worst declines
// a retry that might have worked, and the caller still has its split and its report. The
// cheap mistake is the one to take.
//
// This block is identical in every workflow script, on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text.
const DETERMINISTIC_ERROR_TEXT =
  /completed without calling structuredoutput|structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
function failureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = String((e && e.message) || err || '')
  // Deterministic markers are matched FIRST, on purpose: a schema rejection whose text
  // happens to quote a number that also reads as a status code is a schema rejection, and
  // reading it as an overload would hand it the one retry it must never get.
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return 'deterministic'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((v) => Number(v))
    .find((v) => Number.isFinite(v) && v >= 100 && v < 600)
  if (Number.isFinite(status) && TRANSIENT_STATUS.has(status)) return 'transient'
  if (TRANSIENT_ERROR_TEXT.test(text)) return 'transient'
  return 'deterministic'
}
// The cause recorded for the most recent failure of THIS dispatch. Labels are unique per
// dispatch — retireFailures already depends on that — so a lane can never read another
// lane's cause. Null means this label has no recorded failure at all.
function failureCauseFor(label) {
  for (let i = dispatchFailures.length - 1; i >= 0; i--) {
    if (dispatchFailures[i].label === label) return dispatchFailures[i].cause || 'deterministic'
  }
  return null
}
// ── A TRANSIENT FAILURE IS WAITED OUT, NOT COUNTED DOWN ─────────────────────────
//
// An API overload is a server-side condition with its own clock. It clears in thirty
// seconds, or five minutes, or fifteen; nothing this script does shortens it, and a failed
// call costs nothing, so there is nothing here to conserve by giving up. A run started in
// the evening must still be running in the morning, having sat out whatever happened at
// 3am and carried on by itself. So there is NO attempt ceiling and no elapsed-time budget:
// the wait grows, flattens at five minutes, and repeats at five minutes for as long as the
// endpoint keeps failing. If you are about to add a maximum, you are re-introducing the
// defect this replaced — a two-attempt budget that guaranteed a back-to-back second
// failure and then quit.
//
// The schedule: 5s, then triple each time, capped at 300s — 5, 15, 45, 135, 300, 300, …
// Five seconds is short enough that a brief blip costs seconds rather than minutes; a
// factor of three reaches the cap on the fifth wait, about eight minutes in, so a genuine
// outage is at the polite five-minute cadence quickly instead of hammering the endpoint
// for an hour of doublings.
//
// JITTER exists because these lanes run concurrently. Identical waits make every lane that
// failed together return together, which is the thundering herd arriving at an endpoint
// that is already struggling. Each wait is therefore 50–100% of the scheduled interval:
// the growth shape survives, and the lanes spread out.
//
// The offset is DERIVED, never drawn. A workflow script cannot draw a random number — a
// resumed run would draw a different one — and it does not need to: what jitter has to
// vary across is LANES, not runs. Hashing the dispatch's own identity together with the
// attempt number gives concurrent lanes different offsets, which is the whole requirement,
// and gives a resumed run the same one, which is the house rule.
//
// THE WAIT IS LOGGED, and that is the point of it being allowed to be this long. Every
// retry prints the attempt number, the wait about to be taken and the TOTAL time spent
// waiting so far, so someone reading a log at 3am can tell a run patiently sitting out an
// outage from a run that is hung.
const TRANSIENT_BACKOFF_BASE_MS = 5000
const TRANSIENT_BACKOFF_FACTOR = 3
const TRANSIENT_BACKOFF_CAP_MS = 300000
const TRANSIENT_BACKOFF_JITTER = 0.5
// FNV-1a over the dispatch identity, normalised to [0, 1). Any stable spread would do; this
// one is four lines and needs nothing the sandbox withholds.
function settleSpread(text) {
  let h = 2166136261
  for (let i = 0; i < text.length; i++) {
    h = Math.imul(h ^ text.charCodeAt(i), 16777619)
  }
  return (h >>> 0) / 4294967296
}
function transientWaitMs(name, attempt) {
  const scheduled = Math.min(
    TRANSIENT_BACKOFF_CAP_MS,
    TRANSIENT_BACKOFF_BASE_MS * Math.pow(TRANSIENT_BACKOFF_FACTOR, Math.max(0, attempt - 1))
  )
  const spread = settleSpread(`${name}#${attempt}`)
  return Math.round(scheduled * (1 - TRANSIENT_BACKOFF_JITTER + TRANSIENT_BACKOFF_JITTER * spread))
}
// Workflow scripts are a sandbox with no Node API, and the runner guarantees only its seven
// injected globals, so a timer is probed for rather than assumed.
//
// THE NO-CEILING RULE IS CONDITIONAL ON BEING ABLE TO WAIT. Without a timer there is no
// backoff at all, and an unbounded loop with no wait is not patience — it is a hot loop
// hammering an endpoint that is already failing, which is worse than stopping. So on a host
// with no timer the transient retry falls back to a few immediate attempts and then reports
// the failure, saying in the log exactly why it stopped. Every host this runs on today
// provides setTimeout; this branch exists so that if one ever does not, the failure mode is
// a reported stop rather than a spin.
const SETTLE_CAN_WAIT = typeof setTimeout === 'function'
const TRANSIENT_ATTEMPTS_WITHOUT_WAIT = 3
const settleSleep = (ms) =>
  SETTLE_CAN_WAIT ? new Promise((resolve) => setTimeout(resolve, ms)) : Promise.resolve()
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  // The failures THIS call recorded. A dispatch that finally returns after sitting out an
  // overload did not die, and leaving its transient entries in `dispatchFailures` would
  // tell the caller's gate that a phase which produced its artifact must not be
  // adjudicated. They are removed by identity, so a concurrent lane's entries are safe.
  const mine = []
  const fail = (entry) => {
    dispatchFailures.push(entry)
    mine.push(entry)
  }
  const retireMine = () => {
    for (const entry of mine) {
      const at = dispatchFailures.indexOf(entry)
      if (at >= 0) dispatchFailures.splice(at, 1)
    }
    mine.length = 0
  }
  let waitedMs = 0
  for (let attempt = 1; ; attempt++) {
    let out = null
    try {
      out = await agent(prompt, call)
    } catch (err) {
      const message = String((err && err.message) || err)
      const cause = failureCause(err)
      fail({
        ...who,
        outcome: 'threw',
        cause,
        attempt,
        message: message.slice(0, 300),
        transcript: settleTranscript(err, name),
        note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''} (${cause}): ${message.slice(0, 160)}`,
      })
      log(`${name}: session ended without a structured result (${cause}, attempt ${attempt}) — ${message.slice(0, 160)}`)
      if (cause === 'transient' && !SETTLE_CAN_WAIT && attempt >= TRANSIENT_ATTEMPTS_WITHOUT_WAIT) {
        log(
          `${name}: TRANSIENT infrastructure failure on attempt ${attempt}, and this host provides no timer, so the dispatch ` +
            `cannot be spaced out. Stopping rather than spinning against a failing endpoint — re-run once the API has recovered.`
        )
        if (o.rethrow) throw err
        return null
      }
      if (cause === 'transient') {
        const wait = transientWaitMs(name, attempt)
        waitedMs += wait
        log(
          `${name}: TRANSIENT infrastructure failure — attempt ${attempt} failed; waiting ${Math.round(wait / 1000)}s ` +
            `before sending the same dispatch again (${Math.round(waitedMs / 1000)}s spent waiting so far). ` +
            `This is a server-side condition with no attempt limit here: it keeps retrying, at five minutes apart once the backoff caps, until it clears.`
        )
        await settleSleep(wait)
        continue
      }
      // A caller that owns its own failure reporting asks for the throw back, so the real
      // reason reaches its catch instead of being flattened to "returned no result". Only
      // a DETERMINISTIC failure ever gets here — a transient one is still being waited out.
      if (o.rethrow) throw err
      return null
    }
    if (out) {
      if (waitedMs > 0) {
        log(`${name}: returned on attempt ${attempt} after ${Math.round(waitedMs / 1000)}s of waiting out a transient failure`)
      }
      retireMine()
      return out
    }
    fail({
      ...who,
      outcome: 'skipped',
      // A null with no error text carries no evidence of anything, and an unrecognised cause
      // is deterministic. It is also the right answer on the merits here: the runtime has
      // ALREADY exhausted its own retries before it hands back a null, so sending the same
      // dispatch again is the blind retry, not the recovery.
      cause: 'deterministic',
      attempt,
      message: null,
      transcript: settleTranscript(null, name),
      note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
    })
    log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
    return null
  }
}

// args: {
//   change: { id?, title?, description?, repoPath? },  // the change driving provisioning
//   feedback?: string,                                  // gate feedback from a composite re-run
//   maxCostLoops?: number,                              // maker<->cost-reviewer passes (default 2)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const change = a.change || {}
const repo = change.repoPath || '(repo path not provided — ask before editing files)'
const MAX_COST_LOOPS = a.maxCostLoops || 2

const changeHeader = `${change.id ? `Change ${change.id}: ` : ''}${change.title || '(untitled change)'}
${change.description || ''}
Repository: ${repo}`

// ── Phase 1: Provisioning intent (maker) ──────────────────────────────────────
phase('Provisioning intent')

// Maker prompt is a factory so the cost loop can re-run it with feedback.
function intentPrompt(feedback) {
  return `Produce the concrete provisioning intent for the change below. You are the MAKER — author the intent only; you do not judge it. Work within the repository at: ${repo}

${changeHeader}
${a.feedback ? `\nUpstream gate feedback to address:\n${a.feedback}` : ''}
${feedback ? `\nCost-review feedback from the previous pass — revise the intent to address it without violating the S3 standard:\n${feedback}` : ''}

Deliver CDK-expressible provisioning intent:
- resources: each AWS resource to provision, with the CDK-expressible properties. Every s3.Bucket MUST set versioning enabled and SSE-S3 (S3_MANAGED) encryption — these are non-negotiable.
- stacks: the CDK stacks the resources belong to.
- crossStackRefs: cross-stack references expressed via SSM Parameter Store (never CloudFormation exports).
- affectedStacks: the stacks created or modified by this intent (names).
- rationale: why this shape, tied to the change.`
}

// Each dispatch carries its own label, so a death is attributable to the pass that died.
async function makeIntent(feedback, pass) {
  return await settleAgent(intentPrompt(feedback), {
    label: pass > 1 ? `intent:author:pass-${pass}` : 'intent:author',
    phase: 'Provisioning intent',
    agentType: 'agent-teams-workforce:cdk-infrastructure-designer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['resources', 'stacks', 'crossStackRefs', 'affectedStacks', 'rationale'],
      properties: {
        resources: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['logicalId', 'type', 'stack', 'properties'],
            properties: {
              logicalId: { type: 'string' },
              type: { type: 'string' },
              stack: { type: 'string' },
              properties: { type: 'string' },
            },
          },
        },
        stacks: { type: 'array', items: { type: 'string' } },
        crossStackRefs: { type: 'array', items: { type: 'string' } },
        affectedStacks: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  })
}

let intent = await makeIntent('', 1)

// A dead dispatch has no artifact to review or gate, so it is reported as itself and the
// composite's gate spends no retry on it.
const dispatchFailedResult = (who) => ({
  ok: false,
  dispatchFailed: true,
  dispatchFailures: dispatchDeaths(),
  reason: `${who} returned nothing — skipped, or died on a terminal API error`,
  ready: false,
})
if (!intent) return dispatchFailedResult('the cdk-infrastructure-designer')

// ── Phase 2: Review (independent checkers; cost can drive a bounded maker loop) ─
phase('Review')

// Security scan is independent of the maker and does not change between cost passes.
const scanSecurity = (currentIntent, label) =>
  settleAgent(
  `Independently scan this provisioning intent for security misconfiguration — public exposure, missing encryption, over-broad IAM, unencrypted/unversioned buckets, insecure defaults. You are an independent scanner — you did not author the intent and you do not modify it.

${changeHeader}

Provisioning intent under review:
${JSON.stringify(currentIntent, null, 2)}

Report each finding with a severity. Encryption/versioning omissions on any S3 bucket and any public-exposure or over-broad-IAM issue are blocking.`,
  {
    label: label || 'review:security',
    phase: 'Review',
    agentType: 'agent-teams-workforce:infrastructure-security-scanner',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['blocking', 'findings'],
      properties: {
        blocking: { type: 'boolean' },
        findings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['resource', 'issue', 'severity'],
            properties: {
              resource: { type: 'string' },
              issue: { type: 'string' },
              severity: { type: 'string', enum: ['info', 'low', 'medium', 'high', 'critical'] },
            },
          },
        },
      },
    },
  }
)

// Cost review may reject; on a blocking finding re-run the MAKER (segregation of
// duties: the cost reviewer never edits the intent) up to MAX_COST_LOOPS passes.
async function reviewCost(currentIntent, pass) {
  return await settleAgent(
    `Independently review the COST IMPACT of this provisioning intent. You are an independent reviewer — you did not author the intent and you do not modify it.

${changeHeader}

Provisioning intent under review (pass ${pass}):
${JSON.stringify(currentIntent, null, 2)}

Estimate the recurring + one-time cost drivers at the load this change and the project actually state, and flag anything materially over-provisioned for that load. Set blocking=true ONLY for a material, avoidable cost increase at that stated load — a cost that only becomes material under a hypothetical growth multiplier is a finding, never blocking. If blocking, give precise feedback the maker can act on WITHOUT weakening the S3 versioning/encryption standard.`,
    {
      label: `review:cost:pass-${pass}`,
      phase: 'Review',
      agentType: 'agent-teams-workforce:cost-impact-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['blocking', 'estimate', 'feedback', 'findings'],
        properties: {
          blocking: { type: 'boolean' },
          estimate: { type: 'string' },
          feedback: { type: 'string' },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['driver', 'concern', 'severity'],
              properties: {
                driver: { type: 'string' },
                concern: { type: 'string' },
                severity: { type: 'string', enum: ['info', 'low', 'medium', 'high'] },
              },
            },
          },
        },
      },
    }
  )
}

// The two independent first-pass checkers, dispatched together. Each reads the intent as
// `makeIntent` returned it and nothing else; the cost LOOP below is sequential because every
// pass after the first reads an intent the maker has since rewritten.
//
// There is no separate freshness check. The intent is authored in this same run by a maker
// that reads the repository's CDK code and dependency versions, so a dependency-change check
// on it had no time gap to find drift in; construct and property errors surface in the synth
// that Red, Green and Deploy each run.
let [securityFindings, costFindings] = await parallel([() => scanSecurity(intent), () => reviewCost(intent, 1)])
if (!securityFindings || !costFindings) {
  return dispatchFailedResult('an independent intent checker')
}

let costResolved = costFindings.blocking !== true
let rewritten = false

for (let pass = 2; pass <= MAX_COST_LOOPS && !costResolved; pass++) {
  log(`Cost review blocking — re-running cdk-infrastructure-designer (pass ${pass}/${MAX_COST_LOOPS})`)
  // A blocking security finding on the intent being rewritten is fixed in the same pass;
  // otherwise the rewrite is re-scanned, blocks again, and the whole mini re-runs at G1.
  const securityBlock =
    securityFindings.blocking === true
      ? `\n\nThe security scan also blocked this intent — fix these in the same revision:\n${JSON.stringify(securityFindings.findings || [])}`
      : ''
  const revised = await makeIntent(`${costFindings.feedback || ''}${securityBlock}`, pass)
  if (!revised) return dispatchFailedResult('the cdk-infrastructure-designer')
  intent = revised
  rewritten = true
  costFindings = await reviewCost(intent, pass)
  if (!costFindings) return dispatchFailedResult('the cost-impact-reviewer')
  costResolved = costFindings.blocking !== true
}

// The security verdict above was about the FIRST intent. When the cost loop rewrote it, the
// scan is re-run on the intent that is actually returned.
if (rewritten) {
  securityFindings = await scanSecurity(intent, 'review:security:rescan')
  if (!securityFindings) return dispatchFailedResult('the infrastructure-security-scanner')
}

// A cost finding still blocking after the bounded maker loop leaves the intent not ready.
if (!costResolved) log(`Cost review still blocking after ${MAX_COST_LOOPS} maker pass(es) — the intent is not ready`)

// `ready` is at the top level: infra-change Gate 1 checks it directly.
const ready = securityFindings.blocking !== true && costResolved

return {
  ready,
  provisioningIntent: intent,
  affectedStacks: intent.affectedStacks,
  securityFindings,
  costFindings,
}
