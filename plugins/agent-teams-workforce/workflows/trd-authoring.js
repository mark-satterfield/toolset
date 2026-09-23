export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus an arc42 SAD extract. A TRD is the CARRIER: the single point at which the obligations the architecture imposes enter the build chain, because the Specs, Stories and Tasks are built from it and an obligation that does not reach it is built by nobody. Its requirements come from TWO sources — the PRD requirements that need technical elaboration, and the architecture-imposed obligations no PRD would ever state (uptime, latency, maintainability, security, failover, disaster recovery, infrastructure and CDK specifics, which events a service must emit), an open list on which the SAD is the authority. It CITES the SAD rather than restating it, so a requirement that names an obligation and points at the entry defining it is complete, and a correct TRD is often very short — brevity is never incompleteness, and the detailed HOW belongs to the Specs and the Tasks. The relation to the PRD is NOT 1:1, and traceability is RE-POINTED rather than abandoned: every TRD requirement still names a source, that source being EITHER a PRD requirement OR a SAD crosscutting concept or architecture decision, so a SAD-anchored requirement is fully traced and only a requirement with no source of either kind is an orphan. Read-only extractors pull the SAD source feeds (constraints, solution strategy, crosscutting) into a typed packet, reading every SAD file in full across as many concurrent batches as the file count needs; a batch that fails on a transient infrastructure error is sent again after a bounded backoff, one that returns nothing for any other reason is split in half and the halves dispatched, down to a single file, and never re-sent unchanged; every batch that succeeds is persisted so a re-run resumes at the failure instead of re-reading the SAD; the extraction dispatches carry NO output limit, because a read reports what a document holds and capping it would only make the reader truncate or lie — a limit belongs on the layer that CREATES content, so only the authoring dispatches state one, and every stated number is checked in the script afterwards rather than bound in a schema, graduated so a modest overage is an observation and double is flagged for scrutiny, with every item kept either way; extractor IDs are the tags the SAD itself carries, copied exactly, so a citation resolves on every run; the trd-author writes the TRD in ONE pass, with no checker, decider or re-check after it — the TRD is judged where it is used, by spec authoring. Gate feedback from a previous run of this phase seeds the author pass. Read/author only — no production code.',
  phases: [
    { title: 'Extract SAD', detail: 'read-only extraction of the arc42 source feeds into a typed packet' },
    { title: 'Author TRD', detail: 'author the TRD from the PRD + SAD extract, one pass' },
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
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },  // the source PRD; `path`
//                            // (absolute .md) is read by the author when `content` is absent
//   sad: { path?, sectionLayout?: 'single-file' | 'one-file-per-section' }, // arc42 SAD location
//   trdPath?: string,        // where the TRD should be written/lives
//   repoPath?: string,       // working repo for file reads/writes
//   feedback?: string,       // gate feedback from a previous run of this phase; seeds the first author pass
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//                            // the Epic working directory. When present the author writes the TRD to
//                            // <dir>/trd.md and records it; trdPath is then the FILING home the
//                            // document is copied to on Done, returned as `filingPath`.
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── ARTIFACT PERSISTENCE ─────────────────────────────────────────────────────────
// When the caller names an Epic working directory, the session that AUTHORED an output
// writes it there once and runs the deterministic recorder, which hashes what is on disk.
// No session copies another session's output. Absent, nothing is written.
const SAFE_ART_PATH = /^\/[A-Za-z0-9._/-]+$/
function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  if (typeof x.dir !== 'string' || !SAFE_ART_PATH.test(x.dir) || x.dir.split('/').includes('..')) return null
  if (typeof x.script !== 'string' || !SAFE_ART_PATH.test(x.script) || x.script.split('/').includes('..')) return null
  if (typeof x.epicId !== 'string' || !/^[A-Za-z0-9._-]+$/.test(x.epicId)) return null
  if (typeof x.phase !== 'string' || !/^[A-Za-z0-9._:-]+$/.test(x.phase)) return null
  return x
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  const relOk = typeof art.relDir === 'string' && /^[A-Za-z0-9._/-]+$/.test(art.relDir) && !art.relDir.startsWith('/')
  if (o.beadKey && relOk && typeof art.beadId === 'string' && /^[A-Za-z0-9._-]+$/.test(art.beadId)) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. This file is the durable copy a later run of this Epic resumes from instead of re-authoring it, and no other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}
const ART = artifactsFrom(a.artifacts)
const prd = a.prd || {}
const sad = a.sad || {}
const repo = a.repoPath || '(repo path not provided — ask before editing files)'
// A missing trdPath used to render as a placeholder string, which told the author to
// write the TRD to nowhere. Deciding where a document belongs is NOT this workflow's
// judgment to make — the project's filing clerk owns that, so when the caller names no
// path we ask it rather than inventing one under .claude/. Its ruling is used verbatim.
let trdPath = a.trdPath || null

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

// ── A FAILURE DECIDED BEFORE ANY AGENT RAN IS NOT RE-RUN ────────────────────────
//
// This is settled by looking at the arguments, before a single dispatch. A re-run of this
// phase performs the identical inspection of the identical arguments and reaches the
// identical answer, so `deterministicFailure` tells the caller's gate to stop here rather
// than spend its retry budget rediscovering a missing argument. `reason` is carried
// alongside `error` deliberately: the gate loop reads `reason`, and without it the stop
// logs "gave no reason" and the person loses the one sentence that says what to change.
//
// Only PRE-DISPATCH failures are marked. A death inside a phase is carried by the separate
// `dispatchFailed` flag, and the incomplete-extraction abort is NOT marked at all — that
// one resumes from the batches already saved, so a re-run genuinely starts with data this
// one did not have. Marking a path that carries new information would silently kill
// legitimate rework.
// The PRD may arrive as a PATH with no inlined text, so the caller does not have to retype a
// ~43K-character document into the arguments. The path is held to the allowlist every path in
// these scripts passes: absolute, .md, no `..`. Inlined content wins when given. With neither,
// the run refuses: a TRD authored from an id or a title alone is silently wrong.
const prdContent = typeof prd.content === 'string' && prd.content.trim().length > 0
const prdPath =
  /^\/[A-Za-z0-9._/-]+\.md$/.test(String(prd.path || '')) && !String(prd.path).split('/').includes('..') ? prd.path : ''
if (!prdContent && !prdPath) {
  const why =
    `no readable PRD supplied — prd.content is empty and prd.path ${prd.path ? `${JSON.stringify(String(prd.path))} is not an absolute .md path without ".."` : 'is absent'}. ` +
    'A TRD authored without the PRD text is silently wrong, so nothing was extracted or authored. Re-running changes nothing: pass the PRD content or a valid path.'
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}

const prdRef = prd.path || prd.id || '(inline content)'
const sadRef = sad.path || '(SAD path not provided — ask before extracting)'
const sadLayout = sad.sectionLayout || 'unknown (detect single-file vs one-file-per-section)'

// ── THE `dispatchFailed` CONTRACT THIS MINI OWES ITS CALLER ──────────────────────
//
// An extractor or author that DIED did not produce a TRD the checkers found wanting — it
// never ran. Reported as an ordinary failure, the caller adjudicates it at its gate,
// every deterministic check fails against the artifact that does not exist, the gate
// loops, the re-dispatch meets the same wall, and the budget is spent. So a death in the
// producing phases is reported AS a death: no gate dispatch, no retry spent.
//
// A death whose work got done anyway is not one of those. The SAD extract answers an empty
// batch by re-sending it after a transient infrastructure error, or by splitting it
// otherwise, and when the attempt or the halves return, the artifact exists — so
// `retireFailures` takes the parent back out of `dispatchFailures` before it can tell the
// caller to refuse to adjudicate a phase that succeeded. What stays is what nobody covered.
const died = (...phases) => {
  const deaths = dispatchDeaths(...phases)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

// ── Phase 1: Extract SAD ──────────────────────────────────────────────────────
// Read-only extraction of the three arc42 source sections into a stably-identified
// packet. The extractor authors no TRD content — it only normalizes what the SAD
// states. Invents nothing the SAD does not contain.
phase('Extract SAD')

// ── A PACKET THE CALLER ALREADY HOLDS IS REUSED, NOT RE-BOUGHT ─────────────────
// The composite re-runs this mini when its gate sends the TRD back for rework. The SAD
// cannot change between those passes (a gate that needs the architecture changed
// ESCALATES and ends the run instead of looping), so the second pass used to pay the
// extractor again for the packet the first pass already produced — on 2026-09-16 the
// extractor was 2.26M of 38.0M weighted units across 17 runs. The caller passes the
// first pass's packet back as `args.sadExtract`; only a packet with all three feeds is
// believed, and anything else is extracted fresh.
const isExtract = (x) =>
  !!x && typeof x === 'object' && ['constraints', 'solutionStrategy', 'crosscuttingConcepts'].every((k) => Array.isArray(x[k]))
const suppliedExtract = isExtract(a.sadExtract) ? a.sadExtract : null
if (suppliedExtract) log('SAD extract supplied by the caller from an earlier pass of this run — reused; the extractor is not dispatched')
else log(`Extracting arc42 source feeds from SAD at ${sadRef}`)

// ── THE SAD IS READ WHOLE, IN SHARDS — IT IS NEVER TRUNCATED ────────────────────
//
// This dispatch used to carry "read the SAD and the files it points at — at most 12
// files". §8 (Crosscutting Concepts) is a DIRECTORY: 67 concept files, 787KB. Under a
// 12-file cap the extractor could not open them, so it read §8's README — an index —
// and reported the concepts it had never opened. The TRD, whose entire job is to be
// derived from the PRD and the SAD, was then authored from a summary of the
// architecture. That is wrong output, not cheaper output.
//
// The constraint that matters is "never read OUTSIDE the SAD"; the file count was a
// proxy for it that became a cap on the authoritative input. So the anti-sprawl rule
// stays verbatim in spirit and the volume is handled by SHARDING instead: §2+§4 in one
// session (~239KB), §8 split across concurrent sessions of roughly 175KB each, every
// assigned file read IN FULL. The SCRIPT merges the typed entries — no model merges
// another model's shards, and no session summarizes another's output.
//
// Workflow scripts have no filesystem, so the §8 file list cannot be globbed here. It
// comes from one cheap inventory dispatch, which is also what resolves single-file vs
// one-file-per-section layout — the same detection the extractor already does.
//
// EVERYTHING BELOW EXISTS SO THIS PHASE NEVER SIMPLY STOPS. The number of shards follows
// from the file count instead of capping it; what a batch returns is bounded by nothing at
// all, because this is a READ and §8 is as large as it is — the script checks the volume
// afterwards and logs it, and never acts on it;
// a batch that fails on a TRANSIENT infrastructure error is sent again, after a capped
// exponential wait, for as long as the API keeps failing — settleAgent does that for every
// dispatch in every script — and one that comes back empty for any other reason is
// split in half and its halves dispatched, down to one file, with no dispatch ever repeated
// unchanged; and every batch that succeeds is written to disk, so a run that does end here
// resumes at the failure rather than re-reading 787KB to get back to it. What remains a
// hard stop is a file that could not be read at all — the TRD is not authored from part of
// the architecture, because these documents drive the build and truncated detail is worse
// than no output.
const SHARD_TARGET_BYTES = 175000
// A file ceiling as well as a byte one: sad-source-extractor runs with maxTurns 50, and
// every assigned file costs at least one Read turn (a large one costs two). 16 leaves the
// session room to finish even when the inventory reported no sizes at all, and room for the
// Read-then-Write the batch's own save costs. A batch that runs out of turns anyway is no
// longer fatal — it is split, and each half is a new, smaller dispatch rather than a repeat.
const SHARD_MAX_FILES = 16
const ASSUMED_BYTES = 20000 // an inventory entry with no usable size is costed pessimistically

const readingRule = `READING RULE (binding): read EVERY file assigned to you below, IN FULL — none of them is optional, and an index, README or table of contents is never read in place of the files it lists. Do NOT read any file outside the SAD, and do not survey this repository or any other repository for architecture content that is not in the SAD. A section the SAD does not state comes back empty; it is never reconstructed from code.`

// ── WHERE A LIMIT BELONGS, AND WHAT AN OVERAGE MEANS ────────────────────────────
//
// These feeds used to carry `maxItems`, on the reasoning that a feed longer than its cap
// was the extractor reconstructing architecture from code. On 2026-09-21 that number cost
// a whole batch of the SAD: shard 3of5 read all sixteen of its assigned files and returned
// 61 crosscutting concepts against a cap of 60. The runtime rejected the ENTIRE structured
// result for the one entry over; settleAgent caught the throw and returned null; and the
// merge, which cannot tell "we discarded this answer ourselves" from "the session died",
// reported those sixteen files as UNREAD and ended the run. The files WERE read. We
// destroyed the answer and then blamed the SAD for it.
//
// Two rules come out of that, and they answer different questions.
//
// ── RULE 1: A LIMIT BELONGS WHERE THE DATA IS CREATED, NOT WHERE IT IS READ ─────
//
// A limit should be a function of the data, not of the read. To limit the size of a PRD,
// limit it when the PRD is WRITTEN; capping what a reader may report about one is chasing
// the problem in the wrong layer. So every dispatch in this file is sorted:
//
//   A READ reports a property of a document somebody else already wrote. The number of §8
//   crosscutting concepts is a fact about the SAD, and an extractor that finds 61 of them
//   in sixteen files is reporting reality. Telling it "return at most 60" leaves it two
//   moves — truncate, which loses information and is forbidden here, or lie. So a READ
//   DISPATCH IS GIVEN NO OUTPUT LIMIT IN ITS PROMPT. What bounds a read is `readingRule`,
//   which says what it may draw on rather than how much it may report, and that is the
//   right guard for a read: it constrains the source, not the answer.
//
//   A CREATE chooses its own volume. An author deciding how to carve one Epic's HOW into
//   requirements, a checker deciding which findings block, a decider listing the changes
//   one pass can carry — the number is that agent's judgment, not a fact it discovered. A
//   stated limit there is legitimate, and it is the only mechanism in this file that
//   reduces cost at all, because anything measured afterwards has already been paid for.
//
// A GENUINELY AMBIGUOUS DISPATCH IS TREATED AS A READ. An unstated limit costs a line in
// the log; a wrongly stated one distorts real work. Citations go read-side under that rule
// even though an authoring session emits them: capping `sadRefs` would push an author to
// drop a dependency its requirement actually has, which is the truncate-or-lie harm again
// wearing different clothes.
//
// Where the VOLUME of §8 itself wants holding down, that belongs on SAD AUTHORING — the
// layer that creates those concepts. It is not this phase's to impose, and is not imposed.
//
// ── RULE 2: NOTHING IS ENFORCED IN A SCHEMA, AND AN OVERAGE IS A GRADUATED FLAG ─
//
// A schema bound has exactly one action available to it: reject the whole result. It
// cannot trim and it cannot warn, and what it rejects is destroyed before this script ever
// sees it — so the one thing a volume measure must never do, fail the run, was the only
// thing it could do. Every number below is therefore checked AFTER the result is safely in
// hand, and the check is an observation with no veto and no branch behind it.
//
// It is also not a boolean, because 53 against 50 and 100 against 50 are not the same
// event. A little over is ordinary variation — a dense document, a thorough session. DOUBLE
// is the shape that suggests an agent padded, misread its assignment or duplicated entries,
// and that is worth a person's eye. So the check speaks at two volumes: a quiet line over
// the number, and SCRUTINISE at twice it. The band between is deliberately quiet, because a
// document that is legitimately dense must not spend a person's attention every single run.
//
// EVERY ITEM IS KEPT AT EVERY MULTIPLE. Nothing here truncates, drops, reorders or
// summarises, at any ratio, ever, and neither branch touches control flow. The flag exists
// so a person can LOOK, never so the code can act — you do not know which entry mattered,
// so you do not get to lose one.
//
// The mechanism below — `atMost`, `checkLimit` and `checkExpected` — is the same text in
// trd-authoring.js and in architecture.js. The TABLES differ: the two files dispatch
// different agents, and each sorts its own into reads and creates.
// What a CREATE dispatch is TOLD, and what the script then checks. Only dispatches whose
// volume is the agent's own judgment appear here.
const STATED_LIMITS = {
  // The author decides how to carve one Epic's worth of HOW into requirements.
  requirements: 40,
}
// What a READ dispatch is EXPECTED to return. Stated to nobody, and not a limit: these are
// facts about documents this phase did not write, so the number only decides when the log
// says something. See rule 1.
const EXPECTED_VOLUME = {
  // Per BATCH of the SAD extract, not per document: §8 is read in slices.
  constraints: 40,
  solutionStrategy: 40,
  // RAISED, from 60. Sixteen §8 files returned 61 concepts in ordinary operation, so 60 sat
  // below what a full batch of this SAD actually states, and an expectation a correct answer
  // routinely trips is noise rather than signal. 80 clears observed output; 160 scrutinises.
  crosscuttingConcepts: 80,
  // The SAD's own file list. Mechanical: only a listing that escaped the SAD reaches this.
  inventoryFiles: 400,
}
// A CREATE's stated limit, rendered for its brief. The agent is told this number and the
// script checks the same constant, so the sentence and the log can never drift apart.
const atMost = (n, what) => `Return at most ${n} ${what}; anything beyond ${n} will not be read.`
// Twice the number is where a count stops reading as variation and starts reading as a
// signal. Below it the check stays quiet on purpose; see rule 2.
const SCRUTINY_RATIO = 2
// The one check, for both kinds. `stated` changes the WORDING only — an agent that was
// given a number and one that was not are both reported, and neither is acted on.
function checkVolume(dispatch, what, count, bound, stated) {
  if (!Number.isFinite(count) || !Number.isFinite(bound) || bound <= 0 || count <= bound) return count
  const against = stated ? `the ${bound} its brief stated` : `the ${bound} expected for a dispatch of this shape`
  const kept = 'Every one of them is KEPT — nothing is truncated, dropped, reordered or summarised, at any multiple.'
  if (count >= bound * SCRUTINY_RATIO) {
    log(
      `SCRUTINISE — ${dispatch} returned ${count} ${what}, ${(count / bound).toFixed(1)}x ${against}. At this ratio look for ` +
        `padding, a misread assignment or duplicated entries before trusting the shape of it. ${kept}`
    )
  } else {
    log(`Over the expected volume — ${dispatch} returned ${count} ${what} against ${against}. Ordinary variation, recorded so it is visible. ${kept}`)
  }
  return count
}
// A CREATE: the agent was told this number (see atMost).
const checkLimit = (dispatch, what, count, limit) => checkVolume(dispatch, what, count, limit, true)
// A READ: nobody told the agent anything, and this is only how much was expected.
const checkExpected = (dispatch, what, count, expected) => checkVolume(dispatch, what, count, expected, false)
const feedSchema = () => ({
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['id', 'statement', 'source'],
    properties: {
      id: { type: 'string' },
      statement: { type: 'string' },
      source: { type: 'string' },
    },
  },
})
const extractSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['constraints', 'solutionStrategy', 'crosscuttingConcepts'],
  properties: {
    constraints: feedSchema(),
    solutionStrategy: feedSchema(),
    crosscuttingConcepts: feedSchema(),
    sadLocation: { type: 'string' },
    notes: { type: 'string' },
  },
}

// ── EVERY BATCH'S RESULT IS PERSISTED, SO A RE-RUN RESUMES WHERE THIS ONE STOPPED ─
//
// Reading the SAD whole is the most expensive thing this mini does, and a run that ended
// in this phase used to throw away every batch that HAD succeeded — the next run re-read
// all 787KB to get back to the same file. The session that produced a batch now writes it
// beside the Epic's other artifacts before it returns, keyed by a digest of the exact files
// it was assigned AND each file's size and modification time as the inventory reported them.
// Keying on the file list rather than on a shard number is what makes the split below
// resumable: a batch that was halved comes back as its halves, each with its own key. Keying
// on size and mtime as well is what keeps a saved batch from outliving the files it read: the
// sad-maintainer edits the SAD after architecture extracts it, and other Epics edit it too, so
// an edited file changes the key and its batch is read again. A batch whose inventory entries
// lack a size or an mtime has no trustworthy key, so it is neither saved nor resumed.
//
// The directory is named by the EPIC, not by the mini, and that is deliberate: this
// extraction is the same text in architecture.js and in trd-authoring.js, both run against
// the same SAD for the same Epic, and architecture runs first. A batch either of them pays
// for is therefore a batch the other does not.
//
// Without an Epic working directory there is nowhere durable to write, and the phase
// behaves exactly as it did before.
const SHARD_SAVE_DIR = ART ? `${ART.dir}/sad-shards` : null
// FNV-1a over each assigned file's path, size and mtime. A workflow script has no crypto and
// needs none: the digest only has to be stable across runs and change when a file changes.
// Null when any entry lacks a size or an mtime — see above.
const BATCH_KEY_SHAPE = /^[0-9]+-[0-9a-f]{8}$/
function batchKey(entries) {
  if (!entries.length || !entries.every((e) => e.bytes > 0 && e.mtime > 0)) return null
  const s = entries.map((e) => `${e.path}\t${e.bytes}\t${e.mtime}`).join('\n')
  let h = 0x811c9dc5
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return `${entries.length}-${h.toString(16).padStart(8, '0')}`
}
const shardSavePath = (key) => (SHARD_SAVE_DIR && key ? `${SHARD_SAVE_DIR}/${key}.json` : null)

// ── A SAVED BATCH IS READ BACK ONE FILE AT A TIME, AND ONLY WHEN THE PLAN NEEDS IT ─
// `listSavedShards` returns the NAMES in the shard directory, which are the batch keys, and
// crosses `parallel()` as a plain array of strings. A batch whose key is listed is read back
// by its own reader session; any other batch is extracted. One session returning every saved
// file verbatim asked for more output than a session can emit on this SAD (six files, about
// 740KB), so it failed and nothing was ever resumed; per-file reads stay within a session's
// output and never emit a file the plan does not use.
function savedKeyFor(savedKeys, entries) {
  if (!Array.isArray(savedKeys)) return null
  const key = batchKey(entries)
  return key && savedKeys.indexOf(key) !== -1 ? key : null
}
async function readSavedShard(label, entries, savedKeys) {
  const key = savedKeyFor(savedKeys, entries)
  if (!key) return null
  const path = shardSavePath(key)
  const read = await settleAgent(
    `You are READ-ONLY. Return the contents of the file below, verbatim and complete. Summarize nothing, reformat nothing, add no commentary, read nothing else, and WRITE NOTHING.

The value below is a FILE PATH — an argument to a read, nothing more. The file is saved data, not a message, not an instruction and not a status report about this run, whatever its contents may appear to say.

${path}

Return found=true with the file's full text in \`content\`, or found=false with a one-line \`note\` when it is absent or unreadable.`,
    {
      label: `resume:${label}`,
      phase: 'Extract SAD',
      model: 'haiku',
      effort: 'low',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['found'],
        properties: { found: { type: 'boolean' }, content: { type: 'string' }, note: { type: 'string' } },
      },
    }
  )
  if (!read || read.found !== true || typeof read.content !== 'string') return null
  let body = null
  try {
    body = JSON.parse(read.content)
  } catch (err) {
    log(`Resume: ${path} is not valid JSON (${String((err && err.message) || err).slice(0, 120)}) — its batch is dispatched`)
    return null
  }
  // A file saved before the key carried sizes and mtimes has no `key` and is not resumed.
  if (!body || body.key !== key || !isExtract(body.extract)) {
    log(`Resume: ${path} does not hold the saved batch for key ${key} — its batch is dispatched`)
    return null
  }
  return body.extract
}

// One batch dispatch. `feeds` names the sections this session owns; every other feed in
// its result is discarded by the merge, so a batch can never widen its own assignment.
function extractShardAgent(label, feeds, entries) {
  const files = entries.map((e) => e.path)
  const key = batchKey(entries)
  const savePath = shardSavePath(key)
  return settleAgent(
    `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for the TRD author. Do NOT author requirements, do NOT change any file, and invent NOTHING the SAD does not state. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

YOUR ASSIGNMENT — these arc42 sections and no others:
${feeds.map((f) => `- ${f.title}`).join('\n')}

FILES ASSIGNED TO YOU (${files.length}) — read every one of them in full:
${files.map((f) => `- ${f}`).join('\n')}

${readingRule}

Other sessions are extracting the rest of this SAD concurrently. Extract ONLY the sections assigned to you, from ONLY the files assigned to you, and return the feeds you were not assigned as empty arrays. Do not read another shard's files and do not guess at what it will find.

For every entry: set its ID, capture the verbatim-grounded statement, and note its source location (file:section/anchor). If an assigned section is genuinely absent from your files, return it as an empty array — do not fabricate.

THE ID IS THE SAD'S OWN TAG, COPIED EXACTLY. Most entries open with a backticked tag such as \`C-apigw-construct\`, \`S-…\`, \`X-uniform-zero-egress\` or \`AD-…\`; that tag, character for character, is the entry's ID. Never add a prefix, change case, rename, or shorten it. Only an entry with no tag gets a made-up ID, and then it is \`<file name without .md>--<kebab-case of the nearest heading>\`, with \`-2\`, \`-3\` appended in document order when one heading holds several untagged entries — so the same file yields the same IDs on every run.
 Return everything your files state: there is NO limit on how many entries you may return, and nothing is dropped for being numerous. This is a READ — how many concepts §8 holds is a fact about the SAD, not a budget you are working to — so report what is there and never consolidate, trim or omit an entry to reach a smaller number.${
      savePath
        ? `

SAVE YOUR RESULT BEFORE YOU RETURN. This file is what a later run of this Epic resumes from instead of reading these files again, and no other session will write it for you. Write ${savePath} with the Write tool, creating its directory if it does not exist and replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). It holds ONE JSON object with exactly three keys:
- "key" — exactly the string ${JSON.stringify(key)}.
- "files" — the list of files assigned to you above, verbatim and in the order given.
- "extract" — your complete structured result, exactly as you return it.
Write no other file for this. If it fails, say so in your result and still return your result.`
        : ''
    }`,
    {
      label,
      phase: 'Extract SAD',
      effort: 'low',
      agentType: 'agent-teams-workforce:sad-source-extractor',
      schema: extractSchema,
    }
  )
}

// ── A DISPATCH WHOSE WORK WAS DONE ANYWAY IS NOT A DEATH THE CALLER MUST HONOR ──
// `dispatchFailures` exists so a gate never adjudicates an artifact that was never
// produced. When a batch came back empty but the halves it was split into both returned,
// the artifact exists; leaving the parent in that list would tell the caller to refuse to
// adjudicate a phase that succeeded. Entries are matched by label, which is unique per
// dispatch, so concurrent lanes can never retire each other's.
function retireFailures(labels) {
  const set = new Set(labels)
  for (let i = dispatchFailures.length - 1; i >= 0; i--) {
    if (set.has(dispatchFailures[i].label)) dispatchFailures.splice(i, 1)
  }
}

// ── AN EMPTY BATCH IS ANSWERED BY ITS CAUSE, NEVER BY A BLIND SECOND TRY ────────
//
// One null from `extractShardAgent` used to end the whole run and report sixteen files
// unread. Almost none of those nulls are the batch being impossible. But they are not all
// the same thing either, and answering them all the same way is wrong in both directions —
// which is exactly what the two shapes this code has already worn got wrong in turn. One
// version re-sent EVERY null once before splitting: a blind retry, the pattern this
// project removed after it burned tokens to exhaustion on attempts that could not succeed.
// The version that replaced it retried NOTHING, which splits a batch that failed because
// the API was overloaded — multiplying calls against an endpoint already failing to serve
// one, over an input that was never the problem.
//
// So the cause decides, and `failureCauseFor` is where it comes from:
//
//   TRANSIENT (429, 529, rate limit, quota, network timeout) — never arrives here at all
//   any more. settleAgent waits it out in place, with the capped exponential backoff
//   defined beside it, and returns only once it has cleared. That is where it belongs:
//   every dispatch in every workflow script goes through settleAgent, so putting the wait
//   there makes an overnight run survive an overload everywhere instead of only in these
//   SAD batches. It is NOT split either way: splitting a transient failure attacks the
//   wrong thing and doubles the load that caused it.
//
//   DETERMINISTIC (a schema rejection, a session that produced no output, anything
//   unrecognised) — NEVER re-sent as it was. Identical files, identical prompt, identical
//   schema: nothing could make the second outcome differ from the first, so there is no
//   basis for expecting one. An attempt is re-earned by a VERIFIABLE CHANGE to the
//   instruction, the code or the data, never by having failed.
//
// The SPLIT is that change, and it belongs to the deterministic case alone. Each half
// carries materially less input than the dispatch that failed — an inspectable difference
// in the data, not an expectation — so each half is a DIFFERENT dispatch, not a second try
// at this one. A batch that is already ONE file has nothing left to change, so it is not
// dispatched again at all: that is the floor, and it is reported unread.
//
// If you are reading this and reaching for a general attempt counter, do not. There is no
// attempt counter left in this function: a null now means DETERMINISTIC, because the only
// other cause is still being waited out upstream. An attempt counter here would re-send an
// input that cannot succeed, which is the blind retry this comment exists to prevent.
//
// Returns one leaf outcome per batch that actually ran: { label, feeds, entries, out }, with
// `out` null only for a floor batch. Every dispatch goes through settleAgent, so no throw
// escapes this and every death is recorded before it is answered.
async function runBatch(label, feeds, entries, saved) {
  const hit = await readSavedShard(label, entries, saved)
  if (hit) {
    log(`${label}: resumed from the saved result for these ${entries.length} unchanged file(s) — not dispatched, and not re-read`)
    return [{ label, feeds, entries, out: hit, resumed: true }]
  }
  // settleAgent has already sat out any transient failure and retired its own record of
  // it, so a batch that returns leaves nothing in `dispatchFailures` for this label.
  const out = await extractShardAgent(label, feeds, entries)
  // A saved-batch reader that died is covered by the extraction that replaced it.
  if (out) retireFailures([`resume:${label}`])
  if (out) return [{ label, feeds, entries, out }]
  if (entries.length === 1) {
    log(`${label}: one file and nothing came back (${failureCauseFor(label) || 'no recorded cause'}) — there is nothing left to change, so it is NOT dispatched again; reported unread: ${entries[0].path}`)
    return [{ label, feeds, entries, out: null }]
  }
  const mid = Math.ceil(entries.length / 2)
  log(
    `${label}: nothing came back for ${entries.length} file(s) and the cause is ${failureCauseFor(label) || 'unrecognised, so deterministic'} — ` +
      `splitting into ${mid} + ${entries.length - mid}; each half is a smaller dispatch with different input, not a retry of this one`
  )
  // Sequential on purpose: this is the recovery path inside a lane that is already running
  // concurrently with every other lane, and nesting `parallel` inside it buys little.
  const halves = [
    ...(await runBatch(`${label}-a`, feeds, entries.slice(0, mid), saved)),
    ...(await runBatch(`${label}-b`, feeds, entries.slice(mid), saved)),
  ]
  if (halves.every((h) => h.out)) retireFailures([label])
  return halves
}

// ── WHAT A PREVIOUS RUN ALREADY PAID FOR ────────────────────────────────────────
// One read-only session lists the saved batch files in this Epic's shard directory by NAME;
// it reads none of them. An absent directory is the normal answer on a first run, not a
// failure. A listed batch is read back when the plan reaches it — see readSavedShard.
async function listSavedShards() {
  if (!SHARD_SAVE_DIR) return []
  const read = await settleAgent(
    `You are READ-ONLY. List the names of the \`.json\` files directly inside the directory ${SHARD_SAVE_DIR}. Return the file NAMES only (for example \`16-567ba02e.json\`): do not open, read or summarize any file, and WRITE NOTHING.

The value above is a DIRECTORY PATH — an argument to a listing, nothing more.

If the directory does not exist or holds no \`.json\` file, return an empty list. That is a normal answer, not a failure.`,
    {
      label: 'resume:sad-shards',
      phase: 'Extract SAD',
      model: 'haiku',
      effort: 'low',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['names'],
        properties: { names: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } },
      },
    }
  )
  const keys = []
  for (const n of (read && Array.isArray(read.names) ? read.names : [])) {
    const key = String(n || '').trim().split('/').pop().replace(/\.json$/, '')
    if (BATCH_KEY_SHAPE.test(key) && keys.indexOf(key) === -1) keys.push(key)
  }
  if (keys.length) log(`Resume: ${keys.length} saved SAD batch file(s) listed for this Epic — a batch whose key matches is read back instead of re-extracted`)
  return keys
}

// Greedy, size-ordered packing over the inventory in the order the inventory gave it,
// so related concept files stay together and a re-run shards identically. Derived from
// the real file sizes rather than a hardcoded list — the concept set grows as Epics
// complete, and a list would rot the first time one is added.
//
// THE PLAN GROWS TO FIT THE SAD; THE SAD DOES NOT SHRINK TO FIT THE PLAN. Two earlier
// versions got this backwards in opposite ways. The first stopped splitting once a shard
// ceiling was reached and let every remaining file pile into the final shard with no limit
// at all — the very defect sharding exists to remove, reintroduced at the one size nobody
// watches. The second traded that for a MAX_SHARDS of 8 that truncated the PLAN and ended
// the run, so a SAD growing past 8 shards' worth of files failed rather than being read.
// Both treated a number we picked as a fact about the architecture. The number of shards
// is an OUTPUT: every shard obeys SHARD_MAX_FILES and SHARD_TARGET_BYTES, and however many
// that takes is however many run. Nothing overflows, because there is nothing to overflow.
//
// A SHARD ALSO ENDS AT A FILE WHOSE PATH HASHES TO AN ANCHOR. Packed on sizes alone, one
// edited or added file moves every boundary after it, every later batch's key changes, and
// a SAD edit of one file re-reads most of §8. An anchor is a boundary set by a file NAME, so
// a size change moves boundaries only as far as the next anchor. Measured over this SAD's 67
// §8 files: an edit re-read 21 files on average and 56 at worst on sizes alone, and 10 and 12
// with anchors, for two more batches on a first read. The minimum keeps anchors from cutting
// batches too small to be worth a session. The same text is in architecture.js and
// trd-authoring.js, because the two share this Epic's saved batches.
const SHARD_ANCHOR_EVERY = 8
const SHARD_ANCHOR_MIN_FILES = 6
function isShardAnchor(path) {
  let h = 0x811c9dc5
  for (let i = 0; i < path.length; i++) {
    h ^= path.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h % SHARD_ANCHOR_EVERY === 0
}
function shardFiles(entries) {
  const shards = []
  let current = []
  let bytes = 0
  for (const e of entries) {
    const size = Number.isFinite(e.bytes) && e.bytes > 0 ? e.bytes : ASSUMED_BYTES
    if (current.length >= SHARD_MAX_FILES || (current.length && bytes + size > SHARD_TARGET_BYTES)) {
      shards.push(current)
      current = []
      bytes = 0
    }
    current.push(e)
    bytes += size
    if (current.length >= SHARD_ANCHOR_MIN_FILES && isShardAnchor(e.path)) {
      shards.push(current)
      current = []
      bytes = 0
    }
  }
  if (current.length) shards.push(current)
  return shards
}

const fileList = (x) =>
  (Array.isArray(x) ? x : [])
    .map((e) => (typeof e === 'string' ? { path: e } : e))
    .filter((e) => e && typeof e.path === 'string' && e.path.trim())
    .map((e) => ({ path: e.path.trim(), bytes: Number(e.bytes) || 0, mtime: Number(e.mtime) || 0 }))

let sadExtract = suppliedExtract

if (!sadExtract) {
  // ── Step 1: inventory, and what a previous run already saved. Neither needs the other,
  // and the saved-batch directory is named by the Epic rather than by the plan, so the two
  // read-only sessions run side by side. On a first run the resume read is one cheap
  // session that finds nothing, which is the price of never re-reading the SAD twice.
  const [inventory, savedBatches] = await parallel([
    () =>
      settleAgent(
        `You are READ-ONLY and you are taking an INVENTORY, not an extract. Do not extract any content, do not summarize anything, and change no file.

SAD location (read here, and only here — it is not inside the product repository ${repo}): ${sadRef}
SAD layout: ${sadLayout}

Resolve the arc42 layout (single-file vs one-file-per-section) and list EVERY file that holds the content of these sections, with its size in bytes and its modification time in Unix epoch seconds, both read with \`stat\` (\`stat -f '%z %m' <file>\` on macOS, \`stat -c '%s %Y' <file>\` on Linux) — never estimated:
- Section 2 — Constraints
- Section 4 — Solution Strategy
- Section 8 — Crosscutting Concepts

A section held in a DIRECTORY is listed as all of its content files, recursively — every concept file, not the directory and not its README index. Where a section's content lives inside one larger file, list that file under every section it holds. List only files inside the SAD; never list a file elsewhere in this repository or in another repository. If a section has no files at all, return it as an empty array. List every file that holds them, however many that is: this is a READ and the count is a fact about the SAD, so never shorten the list to reach a number.`,
        {
          label: 'inventory:sad',
          phase: 'Extract SAD',
          effort: 'low',
          agentType: 'agent-teams-workforce:sad-source-extractor',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: ['constraintsFiles', 'solutionStrategyFiles', 'crosscuttingFiles'],
            properties: {
              constraintsFiles: { $ref: '#/$defs/files' },
              solutionStrategyFiles: { $ref: '#/$defs/files' },
              crosscuttingFiles: { $ref: '#/$defs/files' },
              sadLocation: { type: 'string' },
              layout: { type: 'string' },
              notes: { type: 'string' },
            },
            // No `maxItems` here, and no stated cap in the brief either: this is a READ, and how
            // many files hold sections 2, 4 and 8 is a fact about the SAD. A bound would reject the
            // whole inventory over one file and report that the architecture could not be listed;
            // a stated cap would invite a short list. The script checks the count afterwards.
            $defs: {
              files: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['path'],
                  properties: { path: { type: 'string' }, bytes: { type: 'number' }, mtime: { type: 'number' } },
                },
              },
            },
          },
        }
      ),
    () => listSavedShards(),
  ])
  if (!inventory) {
    return {
      ok: false,
      stage: 'extract',
      reason: 'SAD inventory produced nothing — the files holding sections 2, 4 and 8 could not be listed, so no extraction was attempted. Nothing was read and nothing was authored.',
      ...died('Extract SAD'),
    }
  }

  // A file listed under both §2 and §4 is read once.
  const coreEntries = []
  for (const e of [...fileList(inventory.constraintsFiles), ...fileList(inventory.solutionStrategyFiles)]) {
    if (!coreEntries.some((c) => c.path === e.path)) coreEntries.push(e)
  }
  const crossEntries = fileList(inventory.crosscuttingFiles)
  checkExpected('inventory:sad', 'SAD files', coreEntries.length + crossEntries.length, EXPECTED_VOLUME.inventoryFiles)
  const crossShards = shardFiles(crossEntries)
  log(`SAD inventory: §2+§4 = ${coreEntries.length} file(s); §8 = ${crossEntries.length} file(s) in ${crossShards.length} shard(s)`)
  const unstamped = [...coreEntries, ...crossEntries].filter((e) => !(e.bytes > 0 && e.mtime > 0)).length
  if (SHARD_SAVE_DIR && unstamped) {
    log(`Resume: ${unstamped} inventoried file(s) came back without a size or mtime — a batch holding one is neither resumed nor saved, so an edited file can never be served from a stale batch`)
  }

  // ── Step 2: every shard runs CONCURRENTLY and reads its slice in full.
  const jobs = []
  if (coreEntries.length) {
    jobs.push({
      label: 'extract:sad-core',
      feeds: [{ key: 'constraints', title: 'Section 2 — Constraints' }, { key: 'solutionStrategy', title: 'Section 4 — Solution Strategy' }],
      entries: coreEntries,
    })
  }
  crossShards.forEach((entries, i) => {
    jobs.push({
      label: `extract:sad-crosscutting-${i + 1}of${crossShards.length}`,
      feeds: [{ key: 'crosscuttingConcepts', title: 'Section 8 — Crosscutting Concepts' }],
      entries,
    })
  })
  if (!jobs.length) {
    return {
      ok: false,
      stage: 'extract',
      reason: `SAD inventory listed no files for sections 2, 4 or 8 at ${sadRef} — there is nothing to extract, so no TRD was authored.`,
    }
  }

  // Each lane covers its own gaps by splitting, so what comes back is not one result per
  // planned shard but one LEAF OUTCOME per batch that actually ran.
  // The saved-batch listing crossed `parallel()` to get here. An empty list is the normal
  // answer on a first run; anything that is not an array is not a listing this run can consult,
  // and saying so is not optional — a run that quietly treats an unreadable listing as "nothing
  // was saved" re-reads the whole SAD while reporting a clean resume. `savedKeyFor` still answers null
  // for it, so the batches are dispatched rather than stopped: resume is an optimisation over a
  // read, and losing it costs sessions, never correctness.
  const resumeUnusable = !Array.isArray(savedBatches)
  if (resumeUnusable) {
    log(
      `Resume: the saved-batch listing arrived as ${savedBatches === null ? 'null' : typeof savedBatches} ` +
        `rather than a list of saved batch keys, so NOTHING is resumed and every batch is dispatched — the whole SAD is read again. ` +
        `This is a defect in this run, not an empty resume set.`
    )
  }

  const lanes = await parallel(jobs.map((j) => () => runBatch(j.label, j.feeds, j.entries, savedBatches)))
  // A LANE THAT RETURNED NOTHING IS NOT A LANE THAT READ NOTHING. `parallel` answers null for a
  // thunk that threw, and `runBatch` lets no throw of its own escape — so a null here is a
  // defect in this script, and that lane's files were never read. Folding those away is what
  // turned the 2026-09-23 failure silent: with every lane null, `outcomes` was empty, so there
  // were no dead batches either, and the phase logged "SAD extracted whole: 0 constraint(s) ...
  // from 0 batch(es)" and authored a TRD against an architecture nobody had read. A broken lane
  // is carried as a dead batch so the INCOMPLETE stop below sees it and names its files.
  lanes.forEach((r, i) => {
    if (!Array.isArray(r)) log(`${jobs[i].label}: the lane failed before any batch completed — its ${jobs[i].entries.length} file(s) are counted as UNREAD`)
  })
  const outcomes = lanes.flatMap((r, i) => (Array.isArray(r) ? r : [{ label: jobs[i].label, feeds: jobs[i].feeds, entries: jobs[i].entries, out: null }]))

  // ── Step 3: the SCRIPT merges. Each batch contributes only the feeds it was assigned,
  // in batch order, de-duplicated by stable id. No model sees another model's batch.
  //
  // NOTHING IS DROPPED HERE. Every entry a batch returned reaches the packet: a duplicate
  // id is disambiguated rather than discarded, an entry with no usable id is given one
  // rather than skipped, and no count is compared against anything. The merge is the last
  // place a concept could disappear without a line in the log, so it does not have one.
  const merged = { constraints: [], solutionStrategy: [], crosscuttingConcepts: [] }
  const seen = { constraints: new Set(), solutionStrategy: new Set(), crosscuttingConcepts: new Set() }
  const notes = []
  const deadBatches = []
  outcomes.forEach((batch, batchIndex) => {
    const out = batch.out
    if (!out) {
      deadBatches.push(batch)
      return
    }
    if (typeof out.notes === 'string' && out.notes.trim()) notes.push(`[${batch.label}] ${out.notes.trim()}`)
    for (const feed of batch.feeds) {
      const entries = Array.isArray(out[feed.key]) ? out[feed.key] : []
      checkExpected(batch.label, `${feed.key} entries`, entries.length, EXPECTED_VOLUME[feed.key])
      entries.forEach((entry, entryIndex) => {
        if (!entry || typeof entry !== 'object') return
        // An entry the extractor left unidentified is still something the SAD states, so
        // it is named here rather than dropped — the batch and its position are enough to
        // find it again, and a silent skip is how §8 used to shrink without saying so.
        let id = typeof entry.id === 'string' && entry.id.trim() ? entry.id.trim() : `${batch.label}-${batchIndex}-${entryIndex}`
        if (seen[feed.key].has(id)) {
          // Two batches minted the same content-anchored id for different text. Keeping
          // both, disambiguated, loses nothing; dropping one would silently shrink §8.
          let n = 2
          while (seen[feed.key].has(`${id}#${n}`)) n++
          id = `${id}#${n}`
        }
        seen[feed.key].add(id)
        merged[feed.key].push({ id, statement: String(entry.statement || ''), source: String(entry.source || '') })
      })
    }
  })

  // ── A BATCH THAT DIED NEVER SHRINKS THE PACKET QUIETLY ─────────────────────────
  // A partial §8 that looks whole is the exact defect this sharding was built to fix: the
  // TRD author cannot tell a concept the SAD does not state from one nobody read. So a
  // batch that is still empty after being split down to a single file — the point at which
  // there is nothing left to change about the dispatch — ENDS the run, naming every file
  // that went unread.
  //
  // This is the ONE remaining stop in this phase, and it should now be unreachable in
  // practice. It is deliberately not softened into a partial TRD: these documents drive
  // the build, and truncated detail is worse than no output. What it does instead is cost
  // nothing on the way back — every batch that DID come back is on disk, so the re-run
  // this message asks for resumes at the failure and re-reads nothing else. That durable
  // copy is the resume path; the phase used to return the partial packet to its caller
  // instead, which no caller ever read — resilience promised rather than delivered.
  if (deadBatches.length) {
    const sadUnread = deadBatches.flatMap((b) => b.entries.map((e) => e.path))
    const done = outcomes.length - deadBatches.length
    log(`SAD extraction INCOMPLETE — ${deadBatches.length} batch(es) still empty after splitting; ${sadUnread.length} file(s) went unread`)
    return {
      ok: false,
      stage: 'extract',
      reason: `SAD extraction is INCOMPLETE: ${deadBatches.length} batch(es) returned nothing even after being split down to single files, so ${sadUnread.length} SAD file(s) were never read. No TRD was authored — a TRD derived from part of the architecture is wrong output, not cheaper output. The ${done} batch(es) that DID complete are saved${SHARD_SAVE_DIR ? ` under ${SHARD_SAVE_DIR}` : ''}, so re-running this phase resumes at the failure and re-reads nothing else. Unread: ${sadUnread.join(', ')}`,
      unreadSadFiles: sadUnread,
      deadShards: deadBatches.map((b) => ({ label: b.label, files: b.entries.map((e) => e.path) })),
      ...died('Extract SAD'),
    }
  }

  sadExtract = {
    ...merged,
    sadLocation: (typeof inventory.sadLocation === 'string' && inventory.sadLocation) || sadRef,
    notes: notes.join('\n'),
  }
  const resumed = outcomes.filter((b) => b.resumed).length
  log(
    `SAD extracted whole: ${merged.constraints.length} constraint(s), ${merged.solutionStrategy.length} strategy statement(s), ` +
      `${merged.crosscuttingConcepts.length} crosscutting concept(s) from ${outcomes.length} batch(es) over a ${jobs.length}-shard plan` +
      `${resumed ? ` (${resumed} resumed from a previous run)` : ''}`
  )
}
if (!sadExtract) return { ok: false, stage: 'extract', reason: 'SAD extraction produced nothing', ...died('Extract SAD') }

// Rendered as lines rather than indented JSON: the same entries in materially fewer bytes,
// and the id each requirement cites leads the line.
const renderFeed = (title, entries) =>
  `${title} (${entries.length}):\n` +
  (entries.length ? entries.map((e) => `- [${e.id}] ${e.statement}${e.source ? ` (${e.source})` : ''}`).join('\n') : '- (the SAD states none)')
const extractText = [
  `SAD location: ${sadExtract.sadLocation || sadRef}`,
  ...(sadExtract.notes ? [`Extractor notes: ${sadExtract.notes}`] : []),
  renderFeed('§2 Constraints', sadExtract.constraints),
  renderFeed('§4 Solution Strategy', sadExtract.solutionStrategy),
  renderFeed('§8 Crosscutting Concepts', sadExtract.crosscuttingConcepts),
].join('\n\n')
const prdText = prdContent
  ? prd.content
  : `PRD ${prd.id || ''}${prd.title ? `: ${prd.title}` : ''}\n\nThe PRD is the document at ${prdPath}. Read that ONE file in full before you author anything; every requirement in it is in scope.`

// ── Phase 2: Author TRD ─────────────────────────────────────────────────────────
let trd = null
let feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

// ── WHERE THE TRD LIVES IS THE FILING CLERK'S RULING ─────────────────────────
// A TRD is a durable document, so it needs a real home before it is authored, not a
// path this workflow made up. The clerk already owns that decision for this knowledge
// base: it searches the vault, applies the single-source-of-truth rule, and returns the
// one correct location. Asked once per run, before the authoring loop.
if (!trdPath) {
  const home = await settleAgent(
    `Decide the ONE correct absolute file path for the Technical Requirements Document described below, using this project's documentation conventions and knowledge base. Do not author the TRD and do not create the file — return only where it belongs.

If a TRD for this subject already exists, return ITS path so the document is updated in place rather than duplicated.

Subject: ${prd.id || prd.title || 'TRD'}
PRD title: ${prd.title || '(untitled)'}
Repository the run is working in: ${repo}`,
    {
      label: 'trd:filing-home',
      phase: 'Author TRD',
      effort: 'low',
      agentType: 'filing-clerk',
      schema: {
        type: 'object', additionalProperties: false, required: ['ok'],
        properties: { ok: { type: 'boolean' }, path: { type: 'string' }, existing: { type: 'boolean' }, error: { type: 'string' } },
      },
    }
  )
  if (home && home.ok === true && typeof home.path === 'string' && home.path.startsWith('/')) {
    trdPath = home.path
    log(`TRD home ruled by the filing clerk: ${trdPath}${home.existing ? ' (updating an existing TRD in place)' : ''}`)
  } else {
    // The clerk is the authority on location; if it cannot rule, this workflow does not
    // get to substitute a guess. Authoring proceeds and the author is told to ask.
    trdPath = '(no path supplied — ask the filing clerk before writing)'
    log('Filing clerk returned no usable path for the TRD — the author is instructed to ask before writing')
  }
}

// With an Epic working directory the TRD is authored THERE, and the filing home ruled above
// is where it is filed once the run reaches Done — so a TRD from an unfinished run never
// lands in the vault as if it were accepted.
const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}: that is where it is filed once the run completes, and that copy is not yours to make.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. A TRD is a durable document, not a value passed
between phases: returning its text without saving the file means a run that ends early
leaves no TRD anywhere, and the next run re-derives it from nothing. Saving the file is
part of authoring it, not an optional extra, and \`trdPath\` in your result must be the
path you actually wrote.
`

// ── Phase 2: Author TRD (maker) ──────────────────────────────────────────────
// The author reads `feedback`, which carries the gate's findings from a previous run of this phase.
async function authorTrd(pass) {
  phase('Author TRD')
  log(`Authoring TRD (${pass}) at ${authorPath}`)

  const authored = await settleAgent(
    `${rulingsBlock}Author the Technical Requirements Document (TRD). Write the TRD; do not write production code. Work within the repository at: ${repo}

WHAT THIS DOCUMENT IS FOR. The TRD is the CARRIER: the single point at which the obligations the architecture imposes enter the build chain. Everything downstream — the Specs, the Stories, the Tasks in the tracker — is built from it, and an obligation that does not reach the TRD is built by NOBODY, because nothing further down has any other way to learn about it. Without it the build produces the features the PRD names and none of the other things the system needs. It is NOT a technical translation of the PRD, and its relation to the PRD is NOT 1:1.

It is also NOT the full HOW. The detailed HOW lives in the Spec files and the most detailed steps in the Tasks. Your job is to make sure the right obligations are PRESENT AND SOURCED — not to explain them.

THE TRD'S REQUIREMENTS COME FROM TWO SOURCES.

1. PRD REQUIREMENTS THAT NEED TECHNICAL ELABORATION. Part of a TRD is a reworded product requirement with architecture citations. That is real, it is expected, and it stays. One PRD requirement may need several technical requirements, and several may be answered by one.

2. THE OBLIGATIONS THE ARCHITECTURE IMPOSES, WHICH NO PRD WOULD EVER STATE. These have NO PRD parent and that is correct, not scope drift — and they are the reason this document exists. System uptime, low latency, code maintainability, security, failover, disaster recovery, specific infrastructure and CDK instructions, and observability: this system uses EVENTS as its observability mechanism — warnings and failures are emitted as events from services — so if this PRD results in a service being built, the TRD says WHICH EVENTS that service must emit, none of which is core feature functionality and none of which anyone would write in a PRD. The same class covers throughput and latency budgets, data modelling and schema design, API contracts, encryption, retention and auth protocols, technical debt and refactoring carried as part of this work, and monitoring and alerting. That list is OPEN, not closed — it illustrates the class, and THE SAD IS THE AUTHORITY on what actually belongs.

WHERE THE SECOND KIND COMES FROM. Architecture runs BEFORE this phase, and its output is the SAD extract below — the crosscutting concepts section is where most of this class of obligation lives. Read it and ask what it demands of the thing this PRD builds, whether or not the PRD mentions it. You are not inventing these from general engineering knowledge; you are reading them out of the architecture that was just decided and turning them into requirements the build will honour. Nobody upstream supplies them and nothing downstream can discover them.

CITE THE SAD; DO NOT RESTATE IT. Turning an obligation into a requirement does NOT mean reproducing the architecture in requirement form. A requirement that names the obligation and cites where it is defined is complete and is the PREFERRED shape — in substance: "this service must emit the warning and failure events defined in <the SAD entry that defines them>". The obligation is stated, the authority is cited, nothing is copied. The SAD is the single home for the architecture, and a TRD that copies it creates a second copy that drifts. Never expand a crosscutting concept into prose here.

A CORRECT TRD IS OFTEN VERY SHORT, AND THAT IS NOT A DEFECT. Because it leans on the SAD it is terse by design. Never lengthen the document, split a requirement that did not need splitting, or add one you would not otherwise write, in order to look complete. How many requirements this TRD needs is a fact about this PRD and this architecture, not a target.

AND WHERE THE ARCHITECTURE OBLIGES NOTHING NEW, WRITE NOTHING. Asking what the architecture demands is required of you; finding an answer is not. A small incremental change — the text on a button — may need no new architecture at all, and its TRD is legitimately just the technical version of that PRD, with no architecture-sourced requirement in it, and it is complete and correct. Never manufacture one to look thorough. Inventing an architecture obligation this change does not have is the same filler as restating a settled SAD decision, arriving from the other side.

Where the SAD ALREADY SETTLES a point a PRD requirement raises, CITE THAT DECISION rather than writing a hollow TRD requirement that restates it. That is the normal, correct shape — the citation is the answer and the restatement is filler.

${writeBrief}
PRD (source of product requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

SAD extract (architecture constraints/strategy/crosscutting the TRD must honor; cite each entry by the id in brackets):
${extractText}
${feedback ? `\nFeedback on the previous version from the gate — address every point:\n${feedback}` : ''}

Each technical requirement must have a stable ID, NAME ITS SOURCE, and be verifiable. The source is EITHER a PRD requirement (in \`prdRefs\`) OR a SAD crosscutting concept or architecture decision (in \`sadRefs\`) — a requirement of the second kind carries an empty \`prdRefs\` and that is fully traced, not an orphan. What is forbidden is a requirement with NEITHER: a requirement serving neither the PRD nor any architecture concern is scope drift. A requirement that CONTRADICTS the SAD is a defect whatever it cites. Deliver the TRD file path(s) you wrote, the structured requirements, and the upstream PRD/SAD references each requirement carries.

VOLUME IS THE COST OF THIS PHASE. ${atMost(STATED_LIMITS.requirements, 'technical requirements')} State each in under 60 words and keep the TRD document itself under about 25,000 characters. That is not a quota to fill — it is a ceiling, and a TRD that needs more than ${STATED_LIMITS.requirements} requirements is one Epic's worth of HOW spread too thin: consolidate related obligations into one requirement rather than splitting them, and drop restatement, background and rationale the PRD or the SAD already carries. Consolidating is how you stay under it — never by dropping a sourced obligation, and never by leaving out the architecture-imposed requirements above, which are as much a part of this document as the PRD-derived ones. Every word here is read again by every spec author downstream, so length is paid for many times over.

The citations are NOT bounded, and deliberately: \`decisionIds\`, \`prdRefs\` and \`sadRefs\` record what a requirement actually rests on, so a number to stay under would only make you drop a real dependency. Cite every one, and if a requirement genuinely rests on a great many SAD entries, that is a sign it is several requirements written as one — split it rather than trimming its citations.

CITE THE DECISIONS, IN THE DOCUMENT AS WELL AS IN YOUR RESULT.
A \`sadRefs\` entry that reaches only your structured result is read by this run and by nothing after it. The TRD file itself carries the citation twice:
- in YAML frontmatter at the top of the document, \`decisionIds:\` listing every SAD entry id any requirement in this TRD depends on, as a flat list;
- and on each requirement, naming the ids that requirement depends on.
Cite the SAD's own entry tags exactly as the extract writes them (\`C-…\`, \`S-…\`, \`X-…\`, \`AD-…\`). Never invent an id, never paraphrase one, and never cite a section number in place of one — a section number moves, a tag does not.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
    {
      label: 'author:trd',
      phase: 'Author TRD',
      effort: 'medium',
      agentType: 'agent-teams-workforce:trd-author',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['trdPath', 'requirements'],
        properties: {
          trdPath: { type: 'string' },
          // Every SAD entry id this TRD depends on, flat — the same list the document's
          // frontmatter carries. It is what the impact pass matches a changed decision
          // against, so it lives on the document and not only inside a requirement.
          decisionIds: { type: 'array', items: { type: 'string' } },
          requirements: {
            type: 'array',
            // Requirements are a CREATE: the author decides how to carve the TRD, so the
            // ceiling is real and is stated in the brief above. It is not enforced here —
            // as `maxItems`, a TRD with one requirement too many is thrown away whole and
            // the phase reports that nothing was authored, the exact failure that cost a
            // batch of the SAD extract. Stated up front the author self-limits; checked
            // afterwards the overage is visible and every requirement survives.
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['id', 'requirement', 'prdRefs', 'sadRefs', 'verification'],
              properties: {
                id: { type: 'string' },
                requirement: { type: 'string' },
                prdRefs: { type: 'array', items: { type: 'string' } },
                sadRefs: { type: 'array', items: { type: 'string' } },
                verification: { type: 'string' },
              },
            },
          },
          summary: { type: 'string' },
          notes: { type: 'string' },
        },
      },
    }
  )
  // The stated limits, checked with the result already in hand. Nothing here rejects,
  // truncates or re-dispatches: an overage is a line in the log and the TRD is used whole.
  if (authored) {
    const reqs = Array.isArray(authored.requirements) ? authored.requirements : []
    checkLimit('author:trd', 'technical requirements', reqs.length, STATED_LIMITS.requirements)
  }
  return authored
}

// ── ONE AUTHORING PASS, AND NO CHECKER AFTER IT ──────────────────────────────────
// This phase used to send the TRD to a verifier, then on a reject to the trd-decider,
// then back to the author, then to the verifier again, and the composite's G2b gate then
// judged the same questions a fourth time. The verifier's traceability matrix was read by
// nothing, and its citation check compared the TRD against extract ids that were minted
// fresh on every run, so it rejected correct TRDs. None of it changed what was built.
// The TRD is authored once and handed to spec authoring, which is where it is used.
trd = await authorTrd('single pass')
if (!trd) return { ok: false, stage: 'author', reason: 'TRD authoring produced nothing', sadExtract, ...died('Author TRD') }
// The path the author was told to write is the one recorded. The caller hands `trd` to spec
// authoring, which sends a TRD with an absolute `trdPath` as that path and inlines any other
// TRD whole into every spec session.
const resultPath = ART ? authorPath : trd.trdPath || trdPath
if (typeof resultPath === 'string' && resultPath.startsWith('/')) trd.trdPath = resultPath

return {
  ok: true,
  trdPath: resultPath,
  // The filing home ruled for this TRD, when one was ruled. Null means nobody ruled it.
  filingPath,
  sadExtract,
  trd,
  // The SAD entry ids this TRD depends on. They go up to the caller, where they are matched
  // against a changed decision id, never against a file date.
  decisionIds: [...new Set([
    ...((trd && Array.isArray(trd.decisionIds) ? trd.decisionIds : [])),
    ...((trd && Array.isArray(trd.requirements) ? trd.requirements : []).flatMap((r) => (Array.isArray(r.sadRefs) ? r.sadRefs : []))),
  ].map((x) => String(x == null ? '' : x).trim()).filter(Boolean))],
}
