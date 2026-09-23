export const meta = {
  name: 'tdd-refactor',
  description:
    'Shared-tail mini — TDD Refactor. complexity-analyzer advises FIRST (read-only), and when it returns no recommendations the phase ENDS THERE — nothing is routed, edited, or reviewed, because the only agent qualified to judge has said the change needs no cleanup. The same read-only analysis names which optimizer specialties the change calls for; the code-refactoring-specialist and the selected optimizers apply behavior-preserving changes SEQUENTIALLY (tests stay green after each), then an independent code-correctness-reviewer confirms no regression. A null analysis means unknown, not nothing, and does not skip; a re-run carrying gate feedback always proceeds. The refactorer, the optimizers and the reviewer each receive pointers to the contract the change was built to — the spec documents and sections and the SAD decision ids — so a refactor stays inside the design. Advisor and checker are read-only — only the refactorer and selected optimizers edit code; no self-approval.',
  phases: [{ title: 'Refactor', detail: 'behavior-preserving cleanup + optimizer selection + independent review' }],
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

// args: { contract, green, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
// Agents start in the session's working directory, not in this repository, and many of the
// agents this phase dispatches run in an isolation worktree of that other repository. So every
// prompt pins the tree by absolute path rather than saying "work within" it.
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`
const changedFromGreen = (green.changedFiles || []).join(', ') || 'n/a'
const beadId = (c.bead && c.bead.id) || null

// ── THE CONTRACT THE CHANGE WAS BUILT TO ──────────────────────────────────────────
// A refactor preserves behavior AND stays inside the design the change was built to. That
// design travels on the contract — the spec documents, the sections defining the work, and
// the SAD decisions it was designed against — and is rendered here as pointers to those
// documents, so every agent that edits or reviews code reads the design rather than
// inferring it from the code in front of it.
const str = (v) => (typeof v === 'string' && v.trim() ? v.trim() : '')
const strList = (v) => (Array.isArray(v) ? v.map((x) => str(x)).filter(Boolean) : [])
const contractBlock = (() => {
  const s = c.spec && typeof c.spec === 'object' ? c.spec : null
  const docs = s ? [...new Set([str(s.specPath), ...strList(s.specPaths)].filter(Boolean))] : []
  const decisionIds = [...new Set([...strList(c.decisionIds), ...strList(s && s.decisionIds)])]
  const lines = [
    docs.length
      ? `Spec documents — THE CONTRACT this change was built to. A refactor stays inside it; this prompt is a pointer to them, not a substitute for them:\n${docs.map((d) => `  - ${d}`).join('\n')}`
      : '',
    s && strList(s.specSections).length ? `Spec sections defining this work: ${strList(s.specSections).join(', ')}` : '',
    decisionIds.length
      ? `Architecture decisions this work is designed against (SAD entry ids, cited by the spec documents): ${decisionIds.join(', ')}. A refactor never moves the code outside the design they rule.`
      : '',
  ].filter(Boolean)
  return lines.length ? `\n\n${lines.join('\n')}` : ''
})()

// ── A FAILED REFACTOR PUTS THE TREE BACK AT GREEN ──────────────────────────────
//
// Refactor edits code that has just passed Green, and nothing commits before settle, so a
// refactor that breaks the suite, or is rejected by the correctness reviewer, or dies half
// way, would otherwise leave its partial edits in the worktree for every later phase to
// build, test and deploy. So the Green state is snapshotted as a git tree BEFORE the first
// edit, and every failure below restores the tree to it.
//
// The restore covers every path that differs from the snapshot except documentation: the
// documentation track runs concurrently in the same worktree and writes only documentation,
// so its edits are left alone, and a refactor edit the agents did not report is still
// found and undone. Only the worktree path and the snapshot id are interpolated into the
// commands; both are validated here first.
const REPO_PATH_SHAPE = /^\/[A-Za-z0-9._/-]+$/
const repoPathOk = REPO_PATH_SHAPE.test(repo) && !repo.includes('//') && !repo.endsWith('/') && !repo.split('/').includes('..')
const TREE_ID = /^[0-9a-f]{40}([0-9a-f]{24})?$/
const DOC_PATHS = 'files ending in .md, .mdx, .rst or .adoc, and anything under a docs/ directory'

// The restore is ONE dispatch. `restored` is true only when the agent reports the tree back
// at the snapshot for every non-documentation path.
async function restoreGreen(tree, why) {
  const out = await settleAgent(
    `RESTORE this worktree to the snapshot taken before a refactor, because ${why}. Run these commands exactly, in order, and nothing else that writes:

1. git -C "${repo}" add -A
2. git -C "${repo}" diff --cached --no-renames --name-status ${tree}
   These are the paths that changed since the snapshot, each with its status letter. Set aside the documentation paths (${DOC_PATHS}) — a concurrent documentation step owns them. Every OTHER path is restored in step 3.
3. For each non-documentation path from step 2:
   - status A (the file did not exist at the snapshot): git -C "${repo}" rm -f -q -- <path>
   - any other status: git -C "${repo}" restore --source=${tree} --staged --worktree -- <path>
4. git -C "${repo}" diff --cached --name-only ${tree}
   Report restored=true only if this lists documentation paths and nothing else.

Do not edit any file by hand, do not run tests, and do not touch any other tree. Return the paths you restored and the output of step 4 as evidence.`,
    {
      label: 'refactor:restore-green',
      phase: 'Refactor',
      effort: 'low',
      agentType: 'agent-teams-workforce:code-refactoring-specialist',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['restored', 'restoredFiles', 'evidence'],
        properties: {
          restored: { type: 'boolean' },
          restoredFiles: { type: 'array', items: { type: 'string' } },
          evidence: { type: 'string' },
        },
      },
    }
  )
  const restored = !!(out && out.restored === true)
  log(`Refactor: restore to the Green snapshot ${restored ? 'SUCCEEDED' : 'FAILED'} (${why})`)
  return {
    restored,
    restoredFiles: (out && Array.isArray(out.restoredFiles) ? out.restoredFiles : []),
    restoreEvidence: (out && out.evidence) || null,
    ...(restored ? {} : { restoreReason: out ? `the restore agent reported the tree is not back at the snapshot: ${out.evidence || 'no evidence'}` : 'the restore dispatch returned nothing' }),
  }
}

// A failed attempt returns with the tree restored. When the restore itself failed the tree
// holds unverified edits, so the result is `phaseBlocked`: the caller's gate does not retry
// on top of them, and `restored: false` tells the composite not to build on the tree.
async function failRestored(tree, why, result) {
  const r = await restoreGreen(tree, why)
  return {
    ...result,
    ...r,
    ...(r.restored ? {} : { phaseBlocked: true, blockedReason: `${why}, and ${r.restoreReason}` }),
  }
}

phase('Refactor')

// A path the snapshot and restore commands cannot safely carry means a refactor could not
// be undone, so none is attempted and nothing is dispatched.
if (!repoPathOk) {
  return {
    phaseBlocked: true,
    blockedReason: `the contract repoPath ${JSON.stringify(repo)} is not an absolute path of plain characters, so no snapshot command can be issued and a refactor could not be undone`,
    testsGreen: false,
    behaviorPreserved: false,
    changedFiles: [],
    ledger: { phase: 'refactor', beadId, chosen: [], mode: 'refused', ok: false },
  }
}

// The optimizers this mini may dispatch, each an EDITOR that applies its change and reruns
// the suite. accessibility-validator is not one: it reports violations and never edits, so as
// an "optimizer" its findings were read by nothing and its testsGreen answer could only undo
// the refactor.
const OPTIMIZER_ROSTER = {
  'lambda-performance-optimizer': 'Lambda hot paths, cold start, memory sizing',
  'dynamodb-cost-optimizer': 'DynamoDB capacity, access patterns, index cost',
  'frontend-performance-optimizer': 'web/frontend bundle, render path, Core Web Vitals',
  'code-style-and-linting-enforcer': 'lint/format/style cleanup',
}

// 1) ADVISOR — complexity-analyzer reads the green-tested change and returns prioritized
// refactor recommendations, and names which optimizer specialties the change calls for.
// READ-ONLY: it makes no edits. Naming the optimizers here, from the same reading of the
// code, replaces a separate routing session that re-read the change to answer it.
const complexity = await settleAgent(
  `Analyze the code changed by the fix for complexity, duplication, and refactor opportunities. You are READ-ONLY — make NO edits. Return a prioritized list of refactor recommendations the downstream refactorer will act on; return an EMPTY list when the change needs no cleanup — that ends the phase.

${pinTree}

Changed files from the fix: ${changedFromGreen}

Also name, in \`optimizers\`, the FEWEST optimizer specialties whose work this change calls for, in the order they should run (each runs after the refactorer, one at a time), drawn ONLY from:
${Object.entries(OPTIMIZER_ROSTER).map(([name, what]) => `- ${name}: ${what}`).join('\n')}
Name none when none applies.`,
  {
    label: 'refactor:analyze-complexity',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:complexity-analyzer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['recommendations', 'optimizers'],
      properties: {
        recommendations: { type: 'array', items: { type: 'string' } },
        optimizers: { type: 'array', items: { type: 'string' } },
        hotspots: { type: 'array', items: { type: 'string' } },
        notes: { type: 'string' },
      },
    },
  }
)

// ── Nothing to refactor? Then the phase is done here. ─────────────────────────
//
// The analyzer is advisory and READ-ONLY, so an empty recommendation list is a
// real finding: this change carries no complexity, duplication, or cleanup worth
// making. Everything below — the refactoring specialist, each selected optimizer,
// the independent correctness reviewer, and the gate that judges them — is then
// pure cost on code that has just passed its tests.
//
// Two guards on the exit. A NULL analysis means UNKNOWN, not "nothing", and must
// never skip — an analyzer that died is not an analyzer that approved. And a
// re-run carrying gate feedback is rework that was explicitly demanded, so it
// proceeds no matter what the analyzer returns; skipping there would ignore the
// gate and loop until the budget is gone.
const recommendations =
  complexity && Array.isArray(complexity.recommendations)
    ? complexity.recommendations.filter((r) => String(r || '').trim())
    : null
if (recommendations && !recommendations.length && !a.feedback) {
  log('Refactor: complexity analysis found nothing to do — skipping the refactorer, the optimizers, and the review')
  return {
    refactor: null,
    optimizers: [],
    complexityAnalysis: complexity,
    review: null,
    changedFiles: [],
    alreadySatisfied: true,
    ledger: {
      phase: 'refactor',
      beadId: (c.bead && c.bead.id) || null,
      chosen: ['complexity-analyzer'],
      mode: 'nothing-to-refactor',
      ok: true,
    },
  }
}

// 2) SELECTION — the analyzer's named optimizers, filtered to the roster. None named (or a
// dead analyzer) means the refactoring-specialist runs alone: the 'default' mode.
const pickedOptimizers = [
  ...new Set(complexity && Array.isArray(complexity.optimizers) ? complexity.optimizers.filter((o) => Object.prototype.hasOwnProperty.call(OPTIMIZER_ROSTER, o)) : []),
]
const selectionMode = pickedOptimizers.length ? 'selected' : 'default'

// The Green snapshot. Taken here, after the read-only steps and before the first edit.
// Without it a failure could not be undone, so no refactor is attempted.
const snapshot = await settleAgent(
  `Record the current state of this worktree as a git tree object, so a refactor can be undone. Run exactly these two commands and nothing else:

1. git -C "${repo}" add -A
2. git -C "${repo}" write-tree

Return the id step 2 printed, verbatim, as \`tree\`. Do not edit any file.`,
  {
    label: 'refactor:snapshot-green',
    phase: 'Refactor',
    effort: 'low',
    agentType: 'agent-teams-workforce:code-refactoring-specialist',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['tree'],
      properties: { tree: { type: 'string' } },
    },
  }
)
const snapshotTree = snapshot && TREE_ID.test(String(snapshot.tree || '').trim()) ? String(snapshot.tree).trim() : null
if (!snapshotTree) {
  const why = snapshot ? `the snapshot step returned ${JSON.stringify(snapshot.tree)}, which is not a git tree id` : 'the snapshot step returned nothing'
  log(`Refactor: no Green snapshot (${why}) — no refactor is attempted, because a failure could not be undone`)
  return {
    ok: false,
    ...(snapshot ? { phaseBlocked: true, blockedReason: why } : { dispatchFailed: true, dispatchFailures: dispatchDeaths('Refactor'), reason: why }),
    testsGreen: false,
    behaviorPreserved: false,
    changedFiles: [],
    ledger: { phase: 'refactor', beadId, chosen: [], mode: selectionMode, ok: false },
  }
}

// 3) MAKER — the code-refactoring-specialist applies the behavior-preserving refactor first,
// keeping every test green. This is the segregation invariant's writer half; it pairs with
// the read-only correctness reviewer at the end.
const refactor = await settleAgent(
  `Refactor the code changed by the fix for clarity and to reduce complexity/duplication, WITHOUT changing behavior. Address the complexity analysis where it applies. Keep every test green — run the suite after your changes.

${pinTree}

Changed files from the fix: ${changedFromGreen}
Complexity recommendations: ${(complexity && complexity.recommendations || []).join('; ') || 'n/a'}${contractBlock}
${a.feedback ? `\nReviewer feedback to address:\n${a.feedback}` : ''}

Deliver the files you touched, whether tests are still green, and the captured test output.`,
  {
    label: 'refactor:apply',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-refactoring-specialist',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['changedFiles', 'testsGreen', 'evidence'],
      properties: {
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsGreen: { type: 'boolean' },
        evidence: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)

// A refactorer that returned nothing never ran, so there is nothing to review or judge.
// Reported as a dispatch failure: the composite spends no gate retry on it.
// It may still have edited the tree before it died, so the tree is restored first.
if (!refactor) {
  return await failRestored(snapshotTree, 'the code-refactoring-specialist returned nothing', {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Refactor'),
    reason: 'the code-refactoring-specialist returned nothing — skipped, or died on a terminal API error',
    testsGreen: false,
    behaviorPreserved: false,
    changedFiles: [],
    snapshotTree,
    ledger: { phase: 'refactor', beadId, chosen: ['code-refactoring-specialist'], mode: selectionMode, ok: false },
  })
}

const OPTIMIZER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'testsGreen', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    testsGreen: { type: 'boolean' },
    evidence: { type: 'string' },
    notes: { type: 'string' },
  },
}

// 4) OPTIMIZERS — run the selected optimizers SEQUENTIALLY after the refactor, each building
// on the prior change so no two writers touch the tree concurrently. Each must keep the
// suite green; the captured output proves it before the next one runs.
const optimizerRuns = []
const changedFiles = [...(refactor.changedFiles || [])]
// A writer that reports the suite red has already failed the phase: no later writer and no
// reviewer can make it pass, so the tree is restored and the phase ends there.
const writerRed = (who, run) =>
  failRestored(snapshotTree, `${who} reported the test suite is no longer green`, {
    refactor,
    optimizers: optimizerRuns,
    complexityAnalysis: complexity,
    review: null,
    findings: [`${who} reported the suite red after its change: ${String((run && run.evidence) || 'no evidence').slice(0, 2000)}`],
    changedFiles,
    testsGreen: false,
    behaviorPreserved: false,
    snapshotTree,
    ledger: { phase: 'refactor', beadId, chosen: ['code-refactoring-specialist', ...optimizerRuns.map((o) => o.optimizer)], mode: selectionMode, ok: false },
  })
if (refactor.testsGreen !== true) return await writerRed('the code-refactoring-specialist', refactor)
for (const opt of pickedOptimizers) {
  const run = await settleAgent(
    `Apply your optimization to the refactored code WITHOUT changing behavior, then run the test suite and confirm every test is still green.

${pinTree}

You are '${opt}', running after the code-refactoring-specialist and any earlier optimizers — their changes are already applied. Make only the part matching your specialty.
Files changed so far: ${changedFiles.join(', ') || 'n/a'}
Complexity recommendations: ${(complexity && complexity.recommendations || []).join('; ') || 'n/a'}${contractBlock}

Constraints: preserve behavior; stay inside the contract above; do not modify tests to make them pass. Deliver the files you touched, whether tests are still green, and the captured test output.`,
    {
      label: `refactor:${opt}`,
      phase: 'Refactor',
      agentType: `agent-teams-workforce:${opt}`,
      schema: OPTIMIZER_SCHEMA,
    }
  )
  // A dead optimizer is optional cleanup that did not happen. Whatever it may have edited
  // before it died is still in the tree, and the independent review below runs the suite
  // over exactly that tree, so the phase carries on — but the run says it happened.
  if (!run) log(`⚠ Refactor: '${opt}' returned nothing — skipped, or died on a terminal API error; the review below judges the tree as it stands`)
  optimizerRuns.push({ optimizer: opt, ...(run || { dispatchFailed: true }) })
  if (run && Array.isArray(run.changedFiles)) changedFiles.push(...run.changedFiles)
  if (run && run.testsGreen !== true) return await writerRed(`the ${opt}`, run)
}

// 5) CHECKER — independent correctness review LAST. A different, READ-ONLY agent confirms the
// test suite is still green and behavior is preserved across the refactor + all optimizers.
// No producer judges its own work.
const review = await settleAgent(
  `Review the refactor and optimizer changes below for correctness regressions and behavioral drift. You are READ-ONLY. Verify the test suite is still green and that behavior is preserved across ALL changes.

${pinTree}

Files changed (refactor + optimizers): ${changedFiles.join(', ') || 'n/a'}
Refactorer's evidence: ${refactor.evidence || 'n/a'}
Optimizers run: ${pickedOptimizers.join(', ') || 'none'}${contractBlock}`,
  {
    label: 'refactor:review',
    phase: 'Refactor',
    agentType: 'agent-teams-workforce:code-correctness-reviewer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['behaviorPreserved', 'testsGreen', 'findings'],
      properties: {
        behaviorPreserved: { type: 'boolean' },
        testsGreen: { type: 'boolean' },
        findings: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// Decision ledger — what this phase actually did, for over-time mining.
// chosen = the writers + checker that ran, in order. mode 'selected' = the complexity-analyzer
// named optimizers; mode 'default' = no optimizer applied and only the fixed pair ran.
const ledger = {
  phase: 'refactor',
  beadId,
  chosen: ['code-refactoring-specialist', ...pickedOptimizers, 'code-correctness-reviewer'],
  mode: selectionMode,
  ok: !!(review && review.testsGreen && review.behaviorPreserved),
}

// An unreviewed refactor is not kept: nobody confirmed it preserves behavior.
if (!review) {
  return await failRestored(snapshotTree, 'the code-correctness-reviewer returned nothing', {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Refactor'),
    reason: 'the code-correctness-reviewer returned nothing — skipped, or died on a terminal API error',
    refactor,
    optimizers: optimizerRuns,
    changedFiles,
    testsGreen: false,
    behaviorPreserved: false,
    snapshotTree,
    ledger,
  })
}

// Gate 2c checks these two booleans directly, so they sit at the top level.
const reviewed = {
  refactor,
  optimizers: optimizerRuns,
  complexityAnalysis: complexity,
  review,
  findings: Array.isArray(review.findings) ? review.findings : [],
  changedFiles,
  testsGreen: review.testsGreen === true,
  behaviorPreserved: review.behaviorPreserved === true,
  snapshotTree,
  ledger,
}
if (reviewed.testsGreen && reviewed.behaviorPreserved) return reviewed
return await failRestored(snapshotTree, 'the code-correctness-reviewer rejected the refactor', reviewed)
