export const meta = {
  name: 'adversarial',
  description:
    'Shared-tail mini — Adversarial Validation (feeds Gate 4). Attackers run concurrently in DESIGNATED TEST ENVIRONMENTS ONLY; an independent adjudicator referees severity, and the script counts the open constitutive findings into a top-level `constitutiveOpen` (a finding left unruled counts as open) and flags a self-contradictory packet as `selfContradictory`. A lane or adjudicator that returns nothing reports dispatchFailed rather than a clean result; no confirmed finding skips the adjudicator. Lanes are DERIVED from the surfaces the contract declares, over a baseline of data-exposure and dependency-CVE scanning conditioned on the change itself — data-exposure when source changed, dependency-CVE when a dependency manifest changed. Undeclared surfaces or unknown changed files mean unknown, not empty, and run every lane; a caller-supplied trimmedScope wins. When no lane applies the phase reports alreadySatisfied and the gate is skipped. Security findings are constitutive and cannot be downgraded by implementers.',
  phases: [
    { title: 'Attack', detail: 'access-control + data-integrity and infra + exposure lanes (concurrent)' },
    { title: 'Adjudicate', detail: 'referee severity; classify constitutive vs competitive' },
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

// args: { contract, green, trimmedScope?, feedback?, priorRulings? }
//   priorRulings?: [{ findingId, title, severity, classification, real }]
//     The adjudication from the PREVIOUS attempt at this gate. Its absence is what let
//     the adjudicator rule one fact constitutive/real in one round and competitive/not-real
//     in the next with no new evidence: the feedback string reached only the ATTACKER
//     prompts, so the adjudicator was a fresh instance every round that had never been
//     shown a ruling. It is not reversing anything — it has never seen the prior verdict.
//   trimmedScope?: string[]  // restrict the attack to these attacker agents (e.g. the
//                            // infra path's infra-only lane). Empty/absent → run all lanes.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const target = `Change under attack: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}. Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}. DESIGNATED TEST ENVIRONMENTS ONLY — never attack production. Work within: ${repo}`

// ── Stable finding identity ───────────────────────────────────────────────────
//
// A ruling's only identity used to be its model-authored `title`. Attackers re-run from
// scratch on every loop attempt, so one underlying fact comes back under a re-worded
// title each round — and to every consumer those are two different findings. That is
// exactly how a final packet carried two OPPOSITE reality rulings for one fact.
//
// The id is derived HERE, in script, from the lane plus a normalized fingerprint of the
// reproduction. Deriving it in script rather than asking for it means the model cannot
// mint a fresh id for a fact it already reported, and cannot rename its way out of a
// prior ruling.
//
// The fingerprint covers the WHOLE normalized reproduction: a readable prefix plus an
// FNV-1a hash of all of it. A prefix alone collided — two different findings whose
// reproductions share the same first 80 characters (the same curl preamble) got one id,
// and two honest rulings on two different findings then read as a self-contradiction.
function fingerprint(text) {
  const norm = String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  if (!norm) return 'unspecified'
  let h = 2166136261
  for (let i = 0; i < norm.length; i++) h = Math.imul(h ^ norm.charCodeAt(i), 16777619)
  return `${norm.slice(0, 40)}-${(h >>> 0).toString(16).padStart(8, '0')}`
}
function findingIdFor(lane, finding) {
  return `${lane}#${fingerprint(finding && finding.reproduction)}`
}

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'severity', 'reproduction'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
          reproduction: { type: 'string' },
        },
      },
    },
  },
}

const accessLane = [
  'injection-attack-tester',
  'auth-bypass-tester',
  'permission-escalation-tester',
  'race-condition-tester',
  'contract-violation-tester',
]
const infraLane = [
  'dependency-cve-auditor',
  'dos-resilience-tester',
  'data-exposure-scanner',
  'infrastructure-security-scanner',
]

// Honor a trimmed scope (e.g. the infra path's infra-only lane). An unknown name in
// trimmedScope is ignored; if the filter selects nothing, fall back to ALL lanes rather
// than silently skip security validation.
const allAttackers = [...accessLane, ...infraLane]
const requested = Array.isArray(a.trimmedScope) ? allAttackers.filter((n) => a.trimmedScope.includes(n)) : []
if (Array.isArray(a.trimmedScope) && a.trimmedScope.length && !requested.length) {
  log(`⚠ trimmedScope matched no known attacker (${a.trimmedScope.join(', ')}) — running all lanes`)
}

// ── Surface-derived lane selection ────────────────────────────────────────────
//
// Most attack classes need a surface to attack. Auth bypass needs an auth surface;
// injection needs an input boundary; DoS resilience needs a stated load budget.
// Running all nine against a change that touches none of them buys nothing and is
// most of this phase's cost.
//
// The BASELINE is the floor for a change that CAN produce its findings: data exposure
// and dependency CVEs are not tied to a declared surface — a fix confined to internal
// logic can still leak a field into a log or pull a vulnerable transitive package.
//
// But a floor is only a safety property where the lane could find something. A lane
// that structurally cannot is not a floor, it is a session-start bill: dependency-CVE
// scanning a change that touched no dependency manifest re-audits the same lockfile
// that was already clean, and data-exposure scanning a docs-and-tests-only change has
// no code path that logs, returns, or stores anything. Both are then charged on every
// build of all three composites forever.
//
// So the baseline is conditioned on EVIDENCE FROM THE CHANGE ITSELF, never on a
// judgment about how risky the work felt. Each lane runs when the change contains the
// kind of file that lane reads. `changedFiles` absent means UNKNOWN, not empty, and
// both lanes run — the same rule the surface list follows.
const changedFiles = Array.isArray(green.changedFiles) && green.changedFiles.length ? green.changedFiles : null
const DEP_MANIFEST_RE = /(^|\/)(package\.json|package-lock\.json|pnpm-lock\.yaml|yarn\.lock|pyproject\.toml|requirements[^/]*\.txt|uv\.lock|poetry\.lock|Pipfile|Pipfile\.lock|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|pom\.xml|build\.gradle(\.kts)?)$/
const NON_SOURCE_DIR_RE = /(^|\/)(tests?|spec|__tests__|__mocks__|docs?|\.github|fixtures)\//i
const NON_SOURCE_EXT_RE = /\.(md|mdx|rst|txt|ya?ml|json|toml|ini|cfg|lock|snap|csv)$/i

const depsChanged = changedFiles === null || changedFiles.some((f) => DEP_MANIFEST_RE.test(f))
const sourceChanged =
  changedFiles === null ||
  changedFiles.some((f) => !NON_SOURCE_DIR_RE.test(f) && !NON_SOURCE_EXT_RE.test(f))

const BASELINE_ATTACKERS = [
  sourceChanged ? 'data-exposure-scanner' : null,
  depsChanged ? 'dependency-cve-auditor' : null,
].filter(Boolean)
if (changedFiles && BASELINE_ATTACKERS.length < 2) {
  log(
    `Adversarial baseline narrowed by the change itself: source ${sourceChanged ? 'changed' : 'unchanged'}, ` +
      `dependency manifests ${depsChanged ? 'changed' : 'unchanged'} → baseline [${BASELINE_ATTACKERS.join(', ') || 'none'}]`
  )
}
const SURFACE_ATTACKERS = {
  auth: ['auth-bypass-tester', 'permission-escalation-tester'],
  'api-contract': ['injection-attack-tester', 'contract-violation-tester'],
  'event-chain': ['race-condition-tester', 'contract-violation-tester'],
  'web-ui': ['injection-attack-tester'],
  performance: ['dos-resilience-tester'],
  'data-pipeline': ['race-condition-tester'],
}
const declaredSurfaces = Array.isArray(c.surfaces) ? c.surfaces : null

let attackers
let laneMode
if (requested.length) {
  attackers = requested
  laneMode = 'trimmed-by-caller'
} else if (declaredSurfaces) {
  attackers = [
    ...new Set([...BASELINE_ATTACKERS, ...declaredSurfaces.flatMap((s) => SURFACE_ATTACKERS[s] || [])]),
  ].filter((n) => allAttackers.includes(n))
  laneMode = 'derived-from-surfaces'
  log(
    `Adversarial lanes derived from surfaces [${declaredSurfaces.join(', ') || 'none'}]: ${attackers.join(', ')} ` +
      `(baseline ${BASELINE_ATTACKERS.join(' + ')} always runs)`
  )
} else {
  attackers = allAttackers
  laneMode = 'all-lanes'
  log('Adversarial: contract declares no surface list — running every lane')
}

// A derived lane set that came out EMPTY means the change declares no attackable
// surface AND contains neither source nor dependency changes for the baseline to read.
// There is no attack to run and therefore nothing for Gate 4 to adjudicate, so the
// phase reports already-satisfied and the caller's gateLoop skips the gate too — the
// same contract integration.js uses when no suite has a boundary to exercise. Without
// this the phase still paid an adjudicator session and a gate session to rule on an
// empty findings list.
if (!attackers.length) {
  log('Adversarial: no attackable surface and no source or dependency change — no lane applies; skipping')
  return {
    findings: [],
    adjudication: { rulings: [], constitutiveOpen: 0 },
    constitutiveOpen: 0,
    packetIntegrity: { ok: true },
    selfContradictory: false,
    attackers: [],
    laneMode: 'no-applicable-lane',
    surfaces: declaredSurfaces,
    passed: true,
    alreadySatisfied: true,
    reason:
      'the contract declares no attackable surface, and the change touches neither source nor dependency manifests, so no attack lane has anything to read',
    ledger: { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'no-applicable-lane', ok: true },
  }
}

phase('Attack')
const results = await parallel(
  attackers.map((name) => () =>
    settleAgent(`Attempt your attack class against the change. Report only confirmed findings with a minimal reproduction. ${target}${feedback}`, {
      label: `attack:${name}`,
      phase: 'Attack',
      agentType: `agent-teams-workforce:${name}`,
      schema: FINDINGS_SCHEMA,
    })
  )
)
const ledger = { phase: 'adversarial', beadId: (c.bead && c.bead.id) || null, chosen: attackers, mode: laneMode }

// A lane that returned nothing did not attack anything. Its silence is not a clean result,
// and counting it as one would pass Gate 4 on an attack class that never ran — so the phase
// reports the dead lanes and is not adjudicated (the gateLoop `dispatchFailed` contract).
const deadLanes = attackers.filter((_, i) => !results[i])
if (deadLanes.length) {
  const reason = `attack lane(s) returned nothing: ${deadLanes.join(', ')} — those attack classes did not run, so no clean result can be claimed`
  log(`Adversarial: ${reason}`)
  return {
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Attack'),
    reason,
    attackers,
    laneMode,
    surfaces: declaredSurfaces,
    ledger: { ...ledger, ok: false },
  }
}

// Attach the derived id and the lane that produced it. Both are script-owned facts
// about where a finding came from, not claims the attacker gets to make. A lane that
// reports the same reproduction twice has reported one finding, so it is kept once.
const findings = []
const seenIds = new Set()
results.forEach((r, i) => {
  for (const f of (r && r.findings) || []) {
    const findingId = findingIdFor(attackers[i], f)
    if (seenIds.has(findingId)) continue
    seenIds.add(findingId)
    findings.push({ ...f, lane: attackers[i], findingId })
  }
})
const knownFindingIds = findings.map((f) => f.findingId)

// No confirmed finding means nothing to adjudicate: zero constitutive findings are open,
// and the adjudicator session would rule on an empty list.
if (!findings.length) {
  log(`Adversarial: ${attackers.length} lane(s) ran and confirmed no finding — nothing to adjudicate`)
  return {
    findings: [],
    adjudication: { rulings: [], constitutiveOpen: 0 },
    constitutiveOpen: 0,
    packetIntegrity: { contradictions: [], unjustifiedReversals: [], unadjudicated: [], constitutiveOpen: 0, priorRulingsSeen: 0 },
    selfContradictory: false,
    attackers,
    laneMode,
    surfaces: declaredSurfaces,
    ledger: { ...ledger, ok: true },
  }
}

// The previous attempt's rulings. Rendered to the adjudicator so a reversal is a
// reversal of something it can see, and checked script-side afterwards so an uncited
// reversal has no EFFECT rather than merely being disapproved of.
//
// Attackers re-run from scratch every round and re-word their reproductions, so a finding
// rarely keeps its derived id across rounds. The adjudicator therefore names, in
// `priorFindingId`, the prior ruling a current finding is the same fact as; without that
// link the cross-round check compares ids that almost never match.
const priorRulings = (Array.isArray(a.priorRulings) ? a.priorRulings : []).filter((r) => r && r.findingId)
const priorById = {}
for (const r of priorRulings) priorById[r.findingId] = r
const priorIds = Object.keys(priorById)

phase('Adjudicate')
const adjudication = await settleAgent(
  `You are the adversarial-critique-adjudicator (Referee). Rule on each finding's real severity and whether it is CONSTITUTIVE (a security/validity hard stop — implementers cannot downgrade it) or COMPETITIVE (a tradeable quality concern). Discard false positives with reasoning.

Return EXACTLY ONE ruling per findingId. Two rulings for the same findingId that disagree about \`real\` or \`classification\` is a self-contradictory packet; it is detected mechanically, it cannot be argued past, and it costs a constitutional appeal. A finding you return no ruling for is counted as an open constitutive finding.

${priorRulings.length ? `PRIOR RULINGS — you (in an earlier round of this same gate) already ruled on these. When a current finding is the same fact as a prior one, set \`priorFindingId\` to that prior findingId. You MAY reverse a prior ruling, but ONLY by citing the artifact change that justifies it: a changed file, a re-run command and its captured output, or an explicit false-positive demonstration. Put that citation in reversalOf.evidence. A reversal with no citation is not a reversal — the prior ruling is reinstated automatically and your reversal is discarded.

${JSON.stringify(priorRulings, null, 2)}
` : ''}
Findings (${findings.length}):
${JSON.stringify(findings, null, 2)}`,
  {
    label: 'adversarial:adjudicate',
    phase: 'Adjudicate',
    agentType: 'agent-teams-workforce:adversarial-critique-adjudicator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['rulings'],
      properties: {
        rulings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['findingId', 'title', 'severity', 'classification', 'real'],
            properties: {
              // Constrained to the ids the script derived, so a ruling cannot be attached
              // to a finding nobody reported and cannot be renamed out of its own history.
              findingId: { type: 'string', enum: knownFindingIds },
              ...(priorIds.length ? { priorFindingId: { type: 'string', enum: priorIds } } : {}),
              title: { type: 'string' },
              severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
              classification: { type: 'string', enum: ['constitutive', 'competitive'] },
              real: { type: 'boolean' },
              // The ONLY field in which a reversal may be declared. Schema-level, because
              // the prose control ("cite an audit trail", "never downgrade a constitutive
              // finding") already existed in the agent charter and the model rendered no
              // worse for having ignored it.
              reversalOf: {
                type: 'object',
                additionalProperties: false,
                required: ['evidence'],
                properties: {
                  priorReal: { type: 'boolean' },
                  priorClassification: { type: 'string', enum: ['constitutive', 'competitive'] },
                  evidence: { type: 'string' },
                },
              },
            },
          },
        },
      },
    },
  }
)

// A dead adjudicator ruled on nothing. Reading its silence as zero open findings would
// pass Gate 4 over confirmed findings nobody classified.
if (!adjudication) {
  const reason = `the adversarial-critique-adjudicator returned nothing — ${findings.length} confirmed finding(s) were never adjudicated`
  log(`Adversarial: ${reason}`)
  return {
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Adjudicate'),
    reason,
    findings,
    attackers,
    laneMode,
    surfaces: declaredSurfaces,
    ledger: { ...ledger, ok: false },
  }
}

// ── Packet integrity: contradiction and completeness, settled in script ────────
//
// A packet that contradicts itself is a MALFORMED ARTIFACT, not a verdict, and it must
// never reach the gate as one. Looping on it cannot help: nothing about the WORK changed
// between rounds, so no retry of the phase can repair it, and re-running the same
// adjudicator regenerates the contradiction — which is precisely how one run burned all
// three loops re-asking a question the same agent kept answering inconsistently.
//
// Everything below costs zero model turns.
const SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1, info: 0 }
// "More severe" is the tie-break while an appeal is pending: a real constitutive finding
// outranks a not-real or competitive one about the same fact. Believing the softer round
// is how a live credential in a committable file gets waved through.
function severityWeight(r) {
  return (r && r.real ? 4 : 0) + (r && r.classification === 'constitutive' ? 2 : 0) + (SEVERITY_RANK[r && r.severity] || 0) / 10
}
function disagrees(x, y) {
  return !!x && !!y && (x.real !== y.real || x.classification !== y.classification)
}

const rawRulings = (Array.isArray(adjudication.rulings) ? adjudication.rulings : []).filter((r) => r && r.findingId)

// 1. INTRA-PACKET: two rulings for one findingId that disagree.
const contradictions = []
const byId = {}
for (const r of rawRulings) {
  const id = r.findingId
  const held = byId[id]
  if (!held) {
    byId[id] = r
    continue
  }
  if (disagrees(held, r)) {
    contradictions.push({
      findingId: id,
      kind: 'intra-packet',
      rulings: [
        { real: held.real, classification: held.classification, severity: held.severity, title: held.title },
        { real: r.real, classification: r.classification, severity: r.severity, title: r.title },
      ],
      resolvedTo: 'the more severe ruling, pending a constitutional ruling',
    })
  }
  byId[id] = severityWeight(r) > severityWeight(held) ? r : held
}

// 2. CROSS-ROUND: a reversal of a prior ruling with no citation has NO EFFECT. The prior
//    ruling is reinstated. Reversal itself stays legal — adversarial re-runs against a
//    CHANGED tree, so a finding the fix removed can legitimately flip to real=false, and
//    a blanket ban would deadlock every repaired finding forever.
const unjustifiedReversals = []
for (const id of Object.keys(byId)) {
  const now = byId[id]
  const prior = priorById[now.priorFindingId || id]
  if (!disagrees(prior, now)) continue
  const cited = !!(now.reversalOf && String(now.reversalOf.evidence || '').trim())
  if (cited) continue
  unjustifiedReversals.push({
    findingId: id,
    priorFindingId: prior.findingId,
    prior: { real: prior.real, classification: prior.classification, severity: prior.severity },
    attempted: { real: now.real, classification: now.classification, severity: now.severity },
    reason: 'a reversal must cite the artifact change that justifies it — a changed file, a re-run command and its output, or an explicit false-positive demonstration. Uncited, the prior ruling stands.',
  })
  byId[id] = { ...now, real: prior.real, classification: prior.classification, severity: prior.severity, reinstated: true }
}

// 3. COMPLETENESS: a confirmed finding with no ruling was never classified. It counts as
//    open and constitutive — the more severe reading, the same tie-break as above.
const unadjudicated = findings.filter((f) => !byId[f.findingId]).map((f) => f.findingId)
for (const f of findings) {
  if (byId[f.findingId]) continue
  byId[f.findingId] = { findingId: f.findingId, title: f.title, severity: f.severity, classification: 'constitutive', real: true, unadjudicated: true }
}

const rulings = Object.keys(byId).map((k) => byId[k])
// 4. ARITHMETIC: constitutiveOpen is COMPUTED from the rulings, never taken on the model's
//    word, and it is the one number Gate 4 checks.
const constitutiveOpen = rulings.filter((r) => r.real === true && r.classification === 'constitutive').length

const packetIntegrity = {
  contradictions,
  unjustifiedReversals,
  unadjudicated,
  constitutiveOpen,
  priorRulingsSeen: priorRulings.length,
}
if (contradictions.length) {
  log(`⚠ adjudication is SELF-CONTRADICTORY on ${contradictions.length} finding(s) — the gate escalates to a constitutional ruling rather than looping the same judge`)
}
if (unjustifiedReversals.length) {
  log(`⚠ ${unjustifiedReversals.length} uncited reversal(s) discarded; the prior ruling stands in each case`)
}
if (unadjudicated.length) {
  log(`⚠ ${unadjudicated.length} finding(s) received no ruling and are counted as open constitutive findings: ${unadjudicated.join(', ')}`)
}

return {
  findings,
  adjudication: { rulings, constitutiveOpen },
  // Top level so Gate 4 checks it deterministically (`constitutiveOpen === 0`).
  constitutiveOpen,
  packetIntegrity,
  // The flag the composites route on: a contradiction the same agent regenerates is a
  // JUDGE failure, so Gate 4 goes to gate-constitutional instead of a deterministic check.
  selfContradictory: contradictions.length > 0,
  // Which lanes actually ran, and why. Without this a run that narrowed its attack
  // set is indistinguishable from one that ran everything, and "we tested for that"
  // becomes unfalsifiable after the fact.
  attackers,
  laneMode,
  surfaces: declaredSurfaces,
  ledger: { ...ledger, ok: true },
}
