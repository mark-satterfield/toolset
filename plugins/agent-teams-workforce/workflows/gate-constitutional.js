export const meta = {
  name: 'gate-constitutional',
  description:
    'Constitutional phase gate (PRD-to-Spec pipeline Gate 2; the Spec-to-Deploy Gate 4 only when the adversarial packet is self-contradictory). The phase-gate-enforcer judges with constitutive criteria as HARD stops — security/validity findings cannot be downgraded or flagged-past. Novel conflicts the enforcer cannot resolve are escalated to the constitutional-agent for a binding ruling, and that ruling is WRITTEN DOWN: every ruling is persisted as precedent keyed on the conflicting-constraint pair, and a conflict matching a stored precedent is settled from it without convening the appeals court again. A self-contradictory packet skips the enforcer: the constitutional-agent rules which reading of each contradicted finding stands, and the script recounts the open constitutive findings from that ruling — pass at zero, escalate otherwise, never loop.',
  phases: [{ title: 'Gate (constitutional)', detail: 'hard-stop adjudication + appeals, over a persistent precedent store' }],
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

// args: { gate, phaseName, criteria: string[], artifact, escalateTargets?: string[] }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
// Every criterion here is constitutive, so a caller's `{ text, class }` entry (the
// gate-enforce shape) is read as its text rather than rendered as [object Object].
const criteria = (Array.isArray(a.criteria) ? a.criteria : [])
  .map((c) => (typeof c === 'string' ? c : c && typeof c.text === 'string' ? c.text : ''))
  .filter((c) => c.trim())
const artifactText =
  typeof a.artifact === 'string' ? a.artifact : JSON.stringify(a.artifact ?? {}, null, 2)

// ── A self-contradictory adjudication is a JUDGE failure, not a phase failure ──
//
// When the packet under review rules one fact two opposite ways, "loop" is the wrong
// verdict: nothing about the WORK changed between rounds, so no retry of the phase can
// repair it, and re-running the same adjudicator regenerates the contradiction. Escalating
// upstream is equally wrong — none of the producing phases caused the adjudicator to
// contradict itself.
//
// So it goes to a DIFFERENT AUTHORITY, the constitutional-agent, and nothing else runs:
// the enforcer is not dispatched, because the packet already carries the computed
// `constitutiveOpen` and every ruling, and the only open question is which of the two
// contradictory readings stands. The agent answers exactly that, per finding, and the
// verdict is computed here from its answer — so no session re-judges what the script
// already counted. No precedent is consulted or written on this path: a packet
// contradiction is a question about one finding in one run, and no other run's ruling
// is about the same finding.
//
// The packet is LOCATED before it is read: JSON strings are parsed, and the object is
// searched to a bounded depth for a `packetIntegrity` carrying contradictions, because it
// can arrive as a JSON string or nested a level down. Bounded, with a cycle-safe seen-set,
// because an unbounded walk over an agent-supplied object is a denial-of-service waiting
// to happen.

/** Parse a JSON-string packet; return objects unchanged; null for anything else. */
function asPacketObject(value) {
  if (value && typeof value === 'object') return value
  if (typeof value !== 'string') return null
  const text = value.trim()
  if (!text.startsWith('{') && !text.startsWith('[')) return null
  try {
    const parsed = JSON.parse(text)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null // an unparseable string is not a packet; it is not evidence of anything
  }
}

/**
 * The packet in `artifact` that carries contradictions, wherever it actually sits:
 * { node, contradictions }, or null. Searches to MAX_DEPTH, parsing JSON strings on the way.
 */
function findContradictedPacket(artifact) {
  const MAX_DEPTH = 4
  const MAX_NODES = 500
  const seen = new Set()
  let visited = 0
  const queue = [[asPacketObject(artifact), 0]]
  while (queue.length) {
    const [node, depth] = queue.shift()
    if (!node || typeof node !== 'object' || depth > MAX_DEPTH || visited++ > MAX_NODES) continue
    if (seen.has(node)) continue
    seen.add(node)

    const pi = asPacketObject(node.packetIntegrity)
    if (pi && Array.isArray(pi.contradictions) && pi.contradictions.length) {
      return { node, contradictions: pi.contradictions }
    }

    for (const value of Array.isArray(node) ? node : Object.values(node)) {
      const child = asPacketObject(value)
      if (child) queue.push([child, depth + 1])
    }
  }
  return null
}

const contradicted = findContradictedPacket(a.artifact)
const escalateTarget = (a.escalateTargets && a.escalateTargets[0]) || 'upstream'

if (contradicted) {
  phase('Gate (constitutional)')
  const { node, contradictions } = contradicted
  // One id per finding: three disagreeing rulings on one finding produce two contradiction
  // entries, and a repeated value in the schema enum below is an invalid schema.
  const ids = [...new Set(contradictions.map((cx) => cx && cx.findingId).filter(Boolean))]
  const idSet = new Set(ids)
  const findings = (Array.isArray(node.findings) ? node.findings : []).filter((f) => f && idSet.has(f.findingId))
  const adjudication = asPacketObject(node.adjudication)
  const rulings = adjudication && Array.isArray(adjudication.rulings) ? adjudication.rulings : null
  log(`Constitutional gate ${a.gate || '?'}: self-contradictory adjudication on ${ids.length} finding(s) — asking the constitutional-agent which reading stands`)

  const ruling = await settleAgent(
    `The adversarial adjudication for gate ${a.gate || '?'} (${a.phaseName || 'phase'}) ruled the same finding two opposite ways, with no new evidence between the two rulings. Rule, for EACH finding below, which reading stands: is the finding real, and is it constitutive (a security/validity hard stop) or competitive? Judge from the finding's reproduction. Where you cannot establish the softer reading, the more severe one stands — believing the softer round is how a genuine exposure gets waved through.

Contradictions:
${JSON.stringify(contradictions, null, 2)}

The findings they are about:
${findings.length ? JSON.stringify(findings, null, 2) : '(the packet carries no finding records for these ids — rule from the rulings above)'}

Return exactly one resolution per findingId: ${ids.join(', ')}.`,
    {
      label: `constitutional:${a.gate || 'gate'}`,
      effort: 'high',
      phase: 'Gate (constitutional)',
      agentType: 'agent-teams-workforce:constitutional-agent',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['resolutions', 'rationale'],
        properties: {
          resolutions: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['findingId', 'real', 'classification', 'rationale'],
              properties: {
                findingId: ids.length ? { type: 'string', enum: ids } : { type: 'string' },
                real: { type: 'boolean' },
                classification: { type: 'string', enum: ['constitutive', 'competitive'] },
                rationale: { type: 'string' },
              },
            },
          },
          rationale: { type: 'string' },
        },
      },
    }
  )

  if (!ruling) {
    const deaths = dispatchDeaths('Gate (constitutional)')
    const why =
      `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the adjudication contradicts itself and the constitutional-agent produced no ruling ` +
      '(it was skipped, or it died). The contradiction stands unresolved, and an unresolved contradiction at a constitutional gate is never a pass.'
    log(why)
    return {
      verdict: 'escalate',
      criteria: [],
      feedback: why,
      escalateTo: escalateTarget,
      unresolvedConstitutionalConflict: JSON.stringify(contradictions),
      ruledByConstitutionalAgent: false,
      packetContradiction: true,
      ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
    }
  }

  // Apply the resolutions to the packet's rulings and count what is still open. A
  // contradicted finding the agent did not resolve keeps the packet's own reading, which
  // adversarial.js already set to the more severe of the two.
  const resolved = {}
  for (const r of Array.isArray(ruling.resolutions) ? ruling.resolutions : []) {
    if (r && idSet.has(r.findingId)) resolved[r.findingId] = r
  }
  const unresolvedIds = ids.filter((id) => !resolved[id])
  if (!rulings) {
    const why = `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the contradicted packet carries no adjudication.rulings, so the open constitutive findings cannot be counted after the ruling — escalating rather than guessing.`
    log(why)
    return { verdict: 'escalate', criteria: [], feedback: why, escalateTo: escalateTarget, ruledByConstitutionalAgent: true, packetContradiction: true }
  }
  const finalRulings = rulings.map((r) => (r && resolved[r.findingId] ? { ...r, real: resolved[r.findingId].real, classification: resolved[r.findingId].classification } : r))
  const open = finalRulings.filter((r) => r && r.real === true && r.classification === 'constitutive')
  const detail = ids
    .map((id) => (resolved[id] ? `${id}: real=${resolved[id].real}/${resolved[id].classification} — ${resolved[id].rationale}` : `${id}: not resolved, the more severe reading stands`))
    .join('; ')
  log(`Constitutional gate ${a.gate || '?'}: contradiction ruled — ${open.length} constitutive finding(s) open. ${detail}`)
  // An open constitutive finding escalates rather than loops: a loop re-runs the attack over
  // the same tree, which cannot close a finding that is real.
  return {
    verdict: open.length ? 'escalate' : 'pass',
    criteria: finalRulings.map((r) => ({
      criterion: `finding ${r && r.findingId}`,
      met: !(r && r.real === true && r.classification === 'constitutive'),
      evidence: `real=${r && r.real}, classification=${r && r.classification}`,
    })),
    feedback: open.length
      ? `${open.length} constitutive finding(s) remain open after the constitutional ruling: ${open.map((r) => r.findingId).join(', ')}. ${ruling.rationale}`
      : `No constitutive finding remains open after the constitutional ruling. ${ruling.rationale}`,
    ...(open.length ? { escalateTo: escalateTarget } : {}),
    constitutiveOpen: open.length,
    // The rulings that stand after this ruling, so a later adversarial re-run is adjudicated
    // against them (its priorRulings) rather than against the contradictory packet.
    rulings: finalRulings,
    unresolvedFindings: unresolvedIds,
    ruledByConstitutionalAgent: true,
    ruledFromPrecedent: false,
    packetContradiction: true,
  }
}

// Fail closed: constitutive criteria MUST be present. An empty set cannot pass —
// that would be a silent constitutional bypass.
if (!criteria.length) {
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: `Constitutional gate ${a.gate || '?'} (${a.phaseName || 'phase'}) was invoked with no constitutive criteria — refusing to adjudicate. Constitutive criteria must be present and non-empty.`,
    escalateTo: escalateTarget,
    needsConstitutionalRuling: false,
  }
}

// One judgment per criterion supplied, which is the honest limit; 60 when the caller
// supplied none to count. Raised from the flat 40 this used to be, and stated to the
// enforcer rather than bound in its schema — a gate that supplies 41 criteria should get
// 41 judgments back, not a destroyed verdict and a loop spent on a phase that passed.
const CRITERIA_JUDGMENT_MAX = criteria.length || 60

phase('Gate (constitutional)')

const verdict = await settleAgent(
  `You are the phase-gate-enforcer at a CONSTITUTIONAL gate. These criteria are constitutive — they define validity. There is NO pass-with-flag here: if a criterion fails, the verdict is "loop" or "escalate", never "pass". Producing agents (e.g. implementers) CANNOT downgrade a finding. You only judge; you do not modify.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}

Constitutive criteria (ALL must hold):
${criteria.length ? criteria.map((c, i) => `${i + 1}. ${c}`).join('\n') : '(none supplied)'}

Artifact under review:
${artifactText}

Verdicts:
- "pass": every constitutive criterion is met, with evidence.
- "loop": a criterion fails and is fixable within the phase — give precise feedback.
- "escalate": failure originates upstream${a.escalateTargets && a.escalateTargets.length ? ` (options: ${a.escalateTargets.join(', ')})` : ''}.
Return exactly one entry in \`criteria\` per criterion listed above, in the same order — at most ${CRITERIA_JUDGMENT_MAX} entries, and nothing past that will be read. Keep each \`evidence\` under 40 words and \`feedback\` under 200. Judgments, not essays — a loop's whole value is the precision of the feedback, never its length.

If you encounter a NOVEL conflict between constitutive objectives that you cannot resolve from the criteria alone, set needsConstitutionalRuling=true and describe the conflict.`,
  {
    label: `gate-const:${a.gate || a.phaseName || 'phase'}`,
    effort: 'high',
    phase: 'Gate (constitutional)',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['verdict', 'criteria', 'feedback', 'needsConstitutionalRuling'],
      properties: {
        verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
        criteria: {
          type: 'array',
          // One entry per criterion the caller supplied, and nothing else: the enforcer
          // judges the stated criteria, it does not invent more. That expectation is
          // stated in the prompt and counted below — never bound here, where an extra
          // entry would destroy the verdict along with it.
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['criterion', 'met', 'evidence'],
            properties: {
              criterion: { type: 'string' },
              met: { type: 'boolean' },
              evidence: { type: 'string' },
            },
          },
        },
        feedback: { type: 'string' },
        escalateTo: { type: 'string' },
        needsConstitutionalRuling: { type: 'boolean' },
        conflict: { type: 'string' },
      },
    },
  }
)

// ── THE `dispatchFailed` CONTRACT THIS GATE OWES ITS CALLER ──────────────────────
//
// A judge that DIED did not find the work wanting — it never ruled. This file built
// `dispatchFailures` and defined `dispatchDeaths` above and then called neither, so a dead
// enforcer returned null and every caller reads a null verdict as `ok:false, "gate N
// returned no verdict"` and ends the phase — discarding work that is complete and durable
// because the read-only judge hit an account limit, and filing it as a failure of the phase
// rather than of the environment. A death is reported AS a death so the caller can tell "the
// work is bad" from "nobody looked", and so no retry is spent on the same wall.
if (!verdict) {
  const deaths = dispatchDeaths('Gate (constitutional)')
  const why =
    `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): the phase-gate-enforcer returned no verdict — it was skipped, or it died. ` +
    'The work was NOT judged and this is not a finding against it.'
  log(why)
  return {
    verdict: 'escalate',
    criteria: [],
    feedback: why,
    escalateTo: (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    ...(deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}),
  }
}

// An observation, never a gate. The enforcer is told to return exactly one entry per
// criterion supplied; more than that means it judged something nobody asked about, which
// is worth seeing in the journal and is not a reason to throw the verdict away.
const judgedCriteria = Array.isArray(verdict.criteria) ? verdict.criteria : []
checkLimit(`Gate ${a.gate || '?'}`, 'criterion judgments', judgedCriteria, CRITERIA_JUDGMENT_MAX)
// Recorded on the verdict the caller receives, as well as logged. It rides along with the
// verdict and changes none of it: no path reads it, and no path branches on it.
if (limitFindings.length) verdict.limitFindings = limitFindings

// Every criterion here is constitutive, so a `pass` cannot stand while the enforcer itself
// itemises one as unmet.
const unmetJudged = judgedCriteria.filter((cc) => cc && cc.met === false)
if (verdict.verdict === 'pass' && unmetJudged.length) {
  const detail = unmetJudged.map((cc) => `${cc.criterion}${cc.evidence ? ` — ${cc.evidence}` : ''}`).join('; ')
  log(`Constitutional gate ${a.gate || '?'}: the enforcer returned PASS with an unmet constitutive criterion — converting to LOOP: ${detail}`)
  verdict.verdict = 'loop'
  verdict.feedback = `A constitutive criterion is unmet, which is a hard stop: ${detail}. ${verdict.feedback || ''}`.trim()
  verdict.classOverride = 'pass-converted-to-loop: unmet constitutive criterion'
}

// ── Precedent store ─────────────────────────────────────────────────────────────
// The constitutional-agent is told its ruling "becomes reusable precedent", and its
// schema returns a `precedent` field — and nothing wrote that field anywhere, and
// nothing read it on a later run. So every ruling died with the run that produced
// it and the same conflict was re-adjudicated from nothing the next time it arose.
// Precedent CR-001 was re-argued from scratch this way.
//
// A ruling is now written to a durable store, and the store is consulted BEFORE the
// appeals court is convened. Scripts have no filesystem access, so both ends go
// through an agent. The store sits beside the run ledger, under the path that
// already exists and is already gitignored.
const PRECEDENT_STORE = '.claude/workflow-runs/constitutional-precedents.jsonl'

// Appeals court: only on a novel unresolved constitutive conflict, and only when no
// precedent already settles it.
if (verdict.needsConstitutionalRuling) {
  const conflict = verdict.conflict || '(unspecified)'

  // Look first. A precedent that answers this conflict IS the ruling — re-arguing a
  // settled question is exactly what precedent exists to prevent, and it costs a
  // constitutional-agent call every time the same tension recurs.
  const found = await settleAgent(
    `Search the constitutional precedent store for a ruling that already settles the conflict below.

Store: ${PRECEDENT_STORE} (JSON Lines; each line is one ruling with keys: key, gate, phaseName, conflict, verdict, rationale, precedent). If the file does not exist, that is not an error — it means no precedent has been recorded yet; return matched=false.

Conflict to settle:
${conflict}

A stored ruling MATCHES only when it is about the SAME PAIR OF CONFLICTING CONSTRAINTS as this one — not merely the same gate, the same phase, or a similar-sounding subject. Two conflicts about the same subject that pull in different directions are DIFFERENT conflicts. When in doubt, return matched=false: convening the appeals court needlessly costs one agent call, whereas applying the wrong precedent silently imposes a binding ruling nobody made about this question.

When you match, return the stored ruling's verdict, rationale and precedent VERBATIM. Do not re-reason it, do not improve it, and do not soften it.`,
    {
      label: `precedent:lookup:${a.gate || 'gate'}`,
      // No agentType, so without a pinned model it runs on the run's own. Matching a stored
      // conflict pair is a small judgment over one file.
      model: 'sonnet',
      effort: 'low',
      phase: 'Gate (constitutional)',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['matched'],
        properties: {
          matched: { type: 'boolean' },
          key: { type: 'string' },
          verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
          rationale: { type: 'string' },
          precedent: { type: 'string' },
          escalateTo: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    }
  )

  if (found && found.matched === true && found.verdict) {
    log(`Constitutional gate ${a.gate}: conflict SETTLED BY PRECEDENT ${found.key || '(unkeyed)'} — appeals court not convened`)
    return {
      verdict: found.verdict,
      criteria: verdict.criteria,
      feedback: found.rationale || found.precedent || 'settled by recorded precedent',
      escalateTo:
        found.escalateTo || verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
      ruledByConstitutionalAgent: true,
      ruledFromPrecedent: true,
      precedentKey: found.key || null,
      precedent: found.precedent,
    }
  }

  log(
    `Constitutional gate ${a.gate}: novel conflict — no precedent on file` +
      `${found && found.reason ? ` (${found.reason})` : ''} — escalating to constitutional-agent`
  )
  const ruling = await settleAgent(
    `A constitutional gate hit a novel conflict between constitutive objectives that the enforcer could not resolve. Rule on it by consulting the system's founding objectives. Your ruling is binding and becomes reusable precedent.

Gate ${a.gate || '?'} — ${a.phaseName || 'phase'}
Conflict: ${verdict.conflict || '(unspecified)'}
Enforcer feedback: ${verdict.feedback || ''}`,
    {
      label: `constitutional:${a.gate}`,
      effort: 'high',
      phase: 'Gate (constitutional)',
      agentType: 'agent-teams-workforce:constitutional-agent',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'rationale'],
        properties: {
          verdict: { type: 'string', enum: ['pass', 'loop', 'escalate'] },
          rationale: { type: 'string' },
          precedent: { type: 'string' },
          escalateTo: { type: 'string' },
        },
      },
    }
  )
  if (ruling) {
    // Record it. A ruling that is not written down is not precedent — it is an
    // opinion that happened once. Persisting is best-effort: a store that cannot be
    // written must not overturn a ruling that was properly made, so a failure here
    // is logged and the ruling still stands for this run.
    const written = await settleAgent(
      `Append one ruling to the constitutional precedent store, then confirm what you wrote.

Store: ${PRECEDENT_STORE} (JSON Lines — one compact JSON object per line, no surrounding array, no pretty-printing). Create the file with the Write tool if it does not exist — it makes any missing parent directories itself, so do NOT run mkdir or any other shell command (an unmatched command blocks on an approval prompt no one is there to answer). APPEND ONLY: never rewrite, reorder, deduplicate or remove existing lines — a superseded ruling is part of the record.

Write exactly this object as the new final line:
${JSON.stringify({
  key: null,
  gate: a.gate || null,
  phaseName: a.phaseName || null,
  conflict,
  verdict: ruling.verdict,
  rationale: ruling.rationale,
  precedent: ruling.precedent || null,
})}

Set \`key\` yourself before writing, to a short stable identifier for THE PAIR OF CONFLICTING CONSTRAINTS this ruling settles — not for this run, this gate, or this phase, because the whole point is that a different run hitting the same pair finds this line. Use the form CR-NNN, continuing the highest CR number already in the file (CR-001 if the file is new or has none).`,
      {
        label: `precedent:persist:${a.gate || 'gate'}`,
        // An append of a line the prompt already spells out.
        model: 'haiku',
        effort: 'low',
        phase: 'Gate (constitutional)',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['written'],
          properties: {
            written: { type: 'boolean' },
            key: { type: 'string' },
            path: { type: 'string' },
            error: { type: 'string' },
          },
        },
      }
    )
    if (written && written.written === true) {
      log(`Constitutional gate ${a.gate}: ruling recorded as precedent ${written.key || '(unkeyed)'} in ${written.path || PRECEDENT_STORE}`)
    } else {
      log(
        `Constitutional gate ${a.gate}: ruling made but NOT recorded as precedent` +
          `${written && written.error ? ` — ${written.error}` : ''}. The ruling stands for this run; the next run will re-adjudicate.`
      )
    }
    return {
      verdict: ruling.verdict,
      criteria: verdict.criteria,
      feedback: ruling.rationale,
      escalateTo:
        ruling.escalateTo || verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
      ruledByConstitutionalAgent: true,
      ruledFromPrecedent: false,
      precedentKey: (written && written.key) || null,
      precedentRecorded: !!(written && written.written === true),
      precedent: ruling.precedent,
    }
  }
}

// ── A DECLARED CONSTITUTIONAL CONFLICT NEVER EXITS AS A PASS ─────────────────────
//
// This is the worst failure shape the system can produce, and it was reachable. The enforcer
// returns `pass` WITH `needsConstitutionalRuling: true` — a real combination: no criterion is
// itemised as unmet, but the judge has declared that two constitutive constraints conflict
// and it cannot settle which binds. If the precedent lookup found nothing and the
// constitutional-agent dispatch then returned null, control fell past the appeals block to
// `return verdict` — a clean
// PASS on a security or validity conflict that NOBODY RULED ON.
//
// A flag that says "this needs a ruling" and no ruling is not a pass. The conflict is
// unresolved, and unresolved at a CONSTITUTIONAL gate means the work is not established as
// valid — so it escalates, naming the conflict, whatever the enforcer's own verdict was.
if (verdict.needsConstitutionalRuling) {
  const conflict = verdict.conflict || '(unspecified)'
  const why =
    `Gate ${a.gate || '?'} (${a.phaseName || 'phase'}): a constitutive conflict was DECLARED and no ruling was obtained — ` +
    'the precedent store settled nothing and the constitutional-agent produced no ruling (it was skipped, or it died). ' +
    `The conflict stands unresolved: ${conflict}. ` +
    'An unresolved constitutive conflict is never a pass: this gate defines whether the work is valid at all, and passing ' +
    'here would wave through exactly the security or validity question that was escalated because nobody could settle it.'
  log(why)
  return {
    ...verdict,
    verdict: 'escalate',
    feedback: why,
    escalateTo: verdict.escalateTo || (a.escalateTargets && a.escalateTargets[0]) || 'upstream',
    unresolvedConstitutionalConflict: conflict,
    ruledByConstitutionalAgent: false,
    ...(dispatchDeaths('Gate (constitutional)').length
      ? { dispatchFailed: true, dispatchFailures: dispatchDeaths('Gate (constitutional)') }
      : {}),
  }
}

return verdict
