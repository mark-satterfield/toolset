export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy (Gate 5). DEPLOYS CODE TO AWS DEV; it does not open a pull request and never has one as a precondition. Smoke authoring (skipped on a redeploy, which re-runs the suite the previous iteration authored) and CDK synth/drift run concurrently, joined by the pipeline implementer only when the change touches .github/workflows; the build lane deploys exactly one repository per Task. Readiness is computed by the script from facts it holds — confirmed Green evidence, a valid CDK synth (or an evidenced not-applicable) and an authored smoke suite, without which a rollout could never be verified. On a go, it rolls out to dev and runs the smoke tests against the deployed endpoints — deploying to dev is how code reaches AWS and is not human-gated. LANDING the work (commit, push, PR) is a separate concern owned by the calling composite\'s Settle step, so this mini can run — repeatedly — with no PR in existence. qa/prod rollout is outward-facing, stays human-gated, and never happens from here.',
  phases: [{ title: 'Deploy-readiness', detail: 'synth + smoke authoring + computed readiness, then roll out to AWS dev and smoke-check the deployed endpoints' }],
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

// args: { contract, green, feedback?, smokeTestFiles?, leaseScope? }
//   smokeTestFiles?: string[] — a smoke suite an earlier iteration authored and ran. A
//     redeploy after a Green repair re-runs THIS suite, the one that proved the defect,
//     rather than re-authoring it from a prompt saying it failed.
//   leaseScope?: string — the repository identity the dev deployment lease is keyed on (the
//     worktree's git common dir). Absent, the lease is keyed on the contract repoPath.
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
// ── PATH SAFETY AT THIS MINI'S OWN BOUNDARY ─────────────────────────────────
//
// The contract repo path is interpolated below into `git -C "<path>"` command text inside
// prompts that agents are told to run exactly as written, and into the prompt PROSE those
// same agents read. Inside a composite the value arrives already validated by the
// workspace step — but this mini is separately dispatchable, and a contract handed
// straight to it has been through no workspace step at all. Then the unvalidated value is
// back, in the phases that WRITE CODE and DEPLOY.
//
// This is the argument 6.0.8 used to justify re-validating inside settle rather than
// trusting the composite, applied where it was left out. A guard that only exists on the
// composite path is a guard on one of the two ways in.
//
// The rule matches the workspace step's: an ALLOWLIST, not a blocklist of shell
// metacharacters. The target is a model reading a prompt as well as a shell parsing a
// line, and a path made only of permitted characters can still be a sentence addressed to
// the reader. No spaces and no colons — a worktree path this pipeline creates needs
// neither, and prose needs both. REFUSE, never sanitize: a rewritten path names a
// different tree and nobody would learn of the substitution.
//
// An ABSENT path is not a fault. It has always meant "no tree was established", the
// placeholder below is not attacker-controlled, and turning that into a refusal would
// change what this mini does rather than what it accepts.
const CONTRACT_PATH_SHAPE = /^\/[A-Za-z0-9._/-]+$/
const suppliedRepoPath = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
const contractPathFault = (() => {
  if (!suppliedRepoPath) return null
  if (!CONTRACT_PATH_SHAPE.test(suppliedRepoPath)) {
    const offending = Array.from(suppliedRepoPath).find((ch) => !/[A-Za-z0-9._/-]/.test(ch))
    return (
      `the contract repoPath ${JSON.stringify(suppliedRepoPath)} ` +
      (suppliedRepoPath.startsWith('/')
        ? `contains ${JSON.stringify(offending)}, which either reshapes the commands an agent is told to run verbatim or lets the path be read as a sentence addressed to that agent`
        : 'is not absolute, and every command in this phase runs as `git -C "<path>"`, which resolves a relative path against whatever tree the agent is standing in')
    )
  }
  if (suppliedRepoPath.includes('//') || suppliedRepoPath.endsWith('/')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} has an empty or trailing path segment; it is refused rather than normalized`
  }
  if (suppliedRepoPath.split('/').includes('..')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} contains a ".." segment, so the directory it names is not the directory it reads as`
  }
  return null
})()
if (contractPathFault) {
  // Refused identically on every retry, so the caller's gate is not run on it.
  return {
    ok: false,
    phaseBlocked: true,
    blockedReason: `${contractPathFault}.`,
    readiness: { ready: false },
    deployedToDev: false,
    smokePassed: false,
    // Answered on this exit path too, for the same reason `deployedToDev` and
    // `smokePassed` are: Gate 5 checks all four MECHANICALLY, and an absent field is
    // reported as `undefined` rather than as the refusal it actually was.
    cdkSynthOk: false,
    smokeTestFiles: [],
    deployedToProd: false,
    blocked: [
      `${contractPathFault}. This phase refuses the contract rather than dispatching it: the path would ` +
        'already be inside the prompt by the time anyone could object.',
    ],
    ledger: { phase: 'deploy', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'refused', ok: false },
  }
}

const repo = suppliedRepoPath || '(repo path not provided)'
// Agents start in the session's working directory, not in this repository, and many of the
// agents this phase dispatches run in an isolation worktree of that other repository. So every
// prompt pins the tree by absolute path rather than saying "work within" it.
const pinTree = `PIN YOURSELF TO THIS TREE. Your working directory is NOT the repository this work is in — you may be running in an isolation worktree of a different one — so a relative path, a bare \`git\` command or an unqualified test run reads, edits or runs the WRONG copy. Every file you read, write or run is under this absolute path; run shell commands as \`cd "${repo}" && …\` and git as \`git -C "${repo}" …\`, and report file paths relative to it:
${repo}`

// MACHINE-CHECKABLE GREEN EVIDENCE. tdd-green.js produces
// { greenConfirmed, evidence } precisely so this stage does not depend on any
// agent's prose account of the tests. Test evidence has THREE states, not two:
// confirmed green, confirmed failing, and NOT RUN / NOT REPORTED. The third
// state is a blocking gap, never "genuine uncertainty" — an unrun test suite
// must never reach AWS.
const greenEvidence = typeof green.evidence === 'string' ? green.evidence.trim() : ''
const greenEvidenceOk = green.greenConfirmed === true && greenEvidence !== ''
const greenStatusLine = greenEvidenceOk
  ? `Unit/integration tests CONFIRMED GREEN (machine-checked from the Green artifact) — evidence: ${greenEvidence}`
  : `Unit/integration tests UNCONFIRMED — ${
      green.greenConfirmed === true
        ? 'the Green artifact claims green but carries no supporting evidence; a bare flag with no evidence string is not confirmation'
        : 'the Green artifact reports no confirmed passing run (tests not run / not reported)'
    }. This is a blocking gap, not uncertainty.`

phase('Deploy-readiness')

// ── THE ONE READINESS ARTIFACT THAT CHANGES WHAT IS BUILT ─────────────────────
//
// A change to the deploy pipeline itself leaves the pipeline definition wrong, so the
// pipeline implementer runs when `.github/workflows/` changed. That is a lookup over the
// paths Green changed, not a routing session. Advisory documents (cost, SLOs, runbooks)
// are not produced here: nothing reads them and their absence never blocks a dev rollout.
const changedPaths = (green.changedFiles || []).map((f) => String(f || ''))
const touchesPipeline = changedPaths.some((f) => /(^|\/)\.github\/workflows\//i.test(f))
log(`Readiness: ${touchesPipeline ? 'the change touches .github/workflows, so the pipeline implementer runs' : 'no pipeline change — smoke authoring and CDK validation only'}`)

const priorSmokeFiles = (Array.isArray(a.smokeTestFiles) ? a.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)
if (priorSmokeFiles.length) log(`Smoke suite: re-running the ${priorSmokeFiles.length} file(s) the previous iteration authored — not re-authoring them`)

// Smoke authoring, CDK synth/drift and (when needed) the pipeline update run in ONE wave:
// none of them consumes another's output.
const [smoke, cdk, pipeline] = await parallel([
  () =>
    priorSmokeFiles.length
      ? Promise.resolve({ smokeTestFiles: priorSmokeFiles, reused: true })
      : settleAgent(
      `Author post-deployment smoke tests that verify the fixed behavior against a deployed endpoint. Do not deploy.

${pinTree}

Change: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}
Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}${feedback}`,
      {
        label: 'deploy:smoke-author',
        phase: 'Deploy-readiness',
        agentType: 'agent-teams-workforce:smoke-test-author',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['smokeTestFiles'],
          properties: {
            smokeTestFiles: { type: 'array', items: { type: 'string' } },
            notes: { type: 'string' },
          },
        },
      }
    ),
  () => cdkValidate(),
  () =>
    touchesPipeline
      ? settleAgent(
          `Ensure the GitHub Actions deploy pipeline (OIDC auth, build, test, deploy stages) is present and current for this change; author or update it as needed. Do NOT trigger a deploy.\n\nChange: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}\nChanged files: ${(green.changedFiles || []).join(', ') || 'n/a'}\n\n${pinTree}`,
          {
            label: 'deploy:pipeline',
            phase: 'Deploy-readiness',
            agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
            schema: {
              type: 'object',
              additionalProperties: false,
              required: ['summary'],
              properties: { summary: { type: 'string' }, paths: { type: 'array', items: { type: 'string' } } },
            },
          }
        )
      : Promise.resolve(null),
])

// NOT-APPLICABLE CARVE-OUT. Not every deployable repo has a CDK surface. A static web app
// ships by `aws s3 sync` + a CloudFront invalidation and owns no CloudFormation stack at all.
// With only {synthValid, driftDetected} to report, such a repo could answer nothing but
// synthValid:false — "no CDK app here" was indistinguishable from "synth is broken" — and the
// readiness review then refused to roll out a change whose remaining work was one s3 sync
// in a repo with no cdk.json and no stack.
// `applicable:false` is a clean NOT-APPLICABLE, never a failure. Guard it: a repo that HAS a
// CDK app must not escape a broken synth by claiming the stage does not apply.
// Declared as a hoisted function so the concurrent dispatch above can dispatch it while the
// carve-out and its incident history stay next to the prompt they are about: a `function`
// declaration binds before the body runs, so the call site reads above its definition.
function cdkValidate() {
  return settleAgent(
  `Validate the service's CDK: run synth and check for drift between the stacks and deployed infrastructure. READ-ONLY — do not deploy.

${pinTree}

FIRST, determine whether this repo has a CDK surface at all. If there is no cdk.json, no CDK app entrypoint, and no CloudFormation stack owned by this repo, then CDK validation DOES NOT APPLY: return applicable=false with synthValid=false and driftDetected=false, and name in \`details\` how the repo actually deploys (for example an S3 sync plus CloudFront invalidation) and which repo owns its infrastructure, if any. Do NOT report applicable=false merely because synth is inconvenient, the environment is unclear, or you lack credentials — that is a genuine failure and must be reported as applicable=true with synthValid=false.

If the repo DOES have a CDK app, return applicable=true and report whether synth succeeds and whether drift exists. Beware a task or script NAMED cdk:deploy that runs no CDK operation; check what it actually executes before treating it as evidence of a CDK surface.`,
  {
    label: 'deploy:cdk-validate',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:cdk-infrastructure-drift-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['applicable', 'synthValid', 'driftDetected'],
      properties: {
        applicable: { type: 'boolean' },
        synthValid: { type: 'boolean' },
        driftDetected: { type: 'boolean' },
        details: { type: 'string' },
      },
    },
  }
  )
}
const cdkDetails = cdk && typeof cdk.details === 'string' ? cdk.details.trim() : ''

// Rollout target. This mini deploys exactly the one repository the contract names, and only
// to dev; a qa/prod rollout is human-gated and never happens from here, so no rollout plan
// is ruled for one. Dev is internal with no traffic to shift, so it has one legal plan.
const targetEnv = (a.env || c.env || 'dev').toLowerCase()
const rolloutAllowed = targetEnv === 'dev'
const strategy = { rolloutStyle: 'single-stack, no canary', riskLevel: 'low (internal dev environment)' }

// ── GATE 5 READINESS IS COMPUTED, NOT RULED ──────────────────────────────────
//
// Every condition that blocks a dev rollout is a fact this script already holds:
//   - the test suite, by the machine-checked Green artifact (`greenEvidenceOk`) — tests not
//     run or not reported are a blocking gap, never uncertainty;
//   - `cdk synth`, by the drift detector's own read-only run. A repo that owns no CDK app
//     cannot fail a synth, but a not-applicable claim counts only with the validator's
//     evidence for it in `details`. A missing cdk result is unknown, not absolution.
//   - a smoke suite to run. Passing smoke tests are not a precondition — they can only run
//     against a deployed environment — but a rollout with NO suite can never show that it
//     works, and Gate 5 requires one, so it would be an AWS deploy spent on a certain failure.
// Drift is reported, not blocking: the rollout reconciles the stack with this code. The
// security gate (Gate 4) has already passed before this mini runs.
const cdkSynthOk = !cdk ? false : cdk.applicable === false ? cdkDetails !== '' : cdk.synthValid === true
const smokeTestFiles = (smoke && Array.isArray(smoke.smokeTestFiles) ? smoke.smokeTestFiles : []).map((f) => String(f || '').trim()).filter(Boolean)
const localGatesOk = greenEvidenceOk && cdkSynthOk
const readiness = {
  ready: localGatesOk && smokeTestFiles.length > 0,
  findings: [
    ...(greenEvidenceOk ? [] : [`BLOCKED: ${greenStatusLine}`]),
    ...(smokeTestFiles.length ? [] : [smoke ? 'BLOCKED: the smoke-test author named no smoke test file, so a rollout could not be verified' : 'BLOCKED: the smoke-test author returned nothing']),
    ...(cdkSynthOk
      ? []
      : [
          !cdk
            ? 'BLOCKED: CDK validation reported nothing'
            : cdk.applicable === false
              ? 'BLOCKED: the CDK validator claims NOT APPLICABLE but supplied no supporting details'
              : `BLOCKED: CDK synth is not valid${cdkDetails ? ` — ${cdkDetails}` : ''}`,
        ]),
    ...(cdk && cdk.applicable !== false && cdk.driftDetected === true ? [`drift detected (not blocking)${cdkDetails ? ` — ${cdkDetails}` : ''}`] : []),
  ],
}
log(`Gate 5 readiness: ${readiness.ready ? 'READY' : 'NOT READY'}${readiness.findings.length ? ` — ${readiness.findings.join('; ')}` : ''}`)

// ── Rollout ───────────────────────────────────────────────────────────────────
// Deploying to dev is how code gets into AWS at all — it is the point of the pipeline,
// not an outward-facing action, and it is NOT human-gated. Only qa/prod rollout is
// human-gated, and prod never rolls out from here.
//
// DEPLOYING IS NOT LANDING. No pull request is opened or required here: landing — commit,
// push, PR — is the calling composite's Settle step. Lint is a landing gate enforced by the
// pre-commit hooks Settle must satisfy; it does not decide whether bytes may reach dev.

// ── DEV IS ONE SHARED ENVIRONMENT, AND TWO TASKS CAN REACH IT AT ONCE ────────
//
// Nothing in this pipeline stopped two Tasks rolling out to the same stack in the same
// account and region at the same time. Each one runs its own composite, in its own
// worktree, with its own bead — so neither can see the other, and the only thing that
// serialized them was luck. When they collide the second deploy hits a stack that is
// already UPDATE_IN_PROGRESS, fails on an error that has nothing to do with the change,
// and that failure is then read as a defect in the code: a smoke failure against a
// half-updated environment sends a correct change back into Green repair.
//
// So a rollout takes a LEASE first and releases it after the smoke run. The key is the
// thing actually being contended — account, region, and the stack scope — because two
// Tasks deploying different stacks in the same account contend for nothing and must not
// wait on each other.
//
// THE STACK SCOPE IS THE REPO, not the stack names. The stack list is reported BY the
// rollout, which is to say after the contention would already have happened, so it cannot
// be the key. The repo that owns the stacks is known here and is the unit a deploy
// actually takes, so it is what the lease is keyed on.
const DEV_ACCOUNT = '616930583457'
const DEV_REGION = 'us-east-1'
// ── WHEN A LEASE MAY BE BROKEN, AND WHY IT MUST BE BREAKABLE ────────────────
//
// A run can die holding this lease — killed, quota-walled, or quit out from under — and a
// lease that nothing can break is strictly worse than no lease at all: the first casualty
// wedges that stack for every future deploy, permanently, and the only repair is a human
// deleting a file they have never heard of. That is a worse failure than the collision
// this exists to prevent, because the collision is transient and the wedge is not.
//
// So a lease older than the window below is a CORPSE and is broken. The window is chosen
// to exceed the longest plausible rollout-plus-smoke by a wide margin: 45 minutes, the
// same figure the checkpoint lease in prd-to-spec.js uses, for the same reason.
//
// The two errors are NOT symmetric, and the asymmetry is what sets the direction:
//   * Breaking a LIVE lease costs one failed deploy. CloudFormation serializes updates to
//     a stack itself and refuses the second one, so the blast radius is an error message
//     and a retry — the very outcome that would have happened with no lease at all.
//   * Refusing to break a DEAD lease costs every deploy of that stack, forever.
// The first is recoverable by the pipeline; the second is not recoverable at all without
// a person. Hence breakable, and hence generous rather than tight.
const LEASE_STALE_MINUTES = 45
// How long the SECOND Task waits before giving up. It waits rather than failing fast
// because the holder is usually minutes from releasing, and a deploy that fails for
// "someone else was deploying" would be re-entered as a code defect by the caller's
// correction loop. It gives up rather than waiting forever because a phase that never
// returns is indistinguishable from a hung one.
const LEASE_WAIT_MINUTES = 20
// A worktree path is per Task, so keying on it serialized nothing between two Tasks of one
// repository. The caller's `leaseScope` (the repository's git common dir) is the key when
// it is a plain absolute path; otherwise the contract path is.
const suppliedLeaseScope = String(a.leaseScope || '').trim()
const leaseScope =
  (CONTRACT_PATH_SHAPE.test(suppliedLeaseScope) && !suppliedLeaseScope.includes('//') && !suppliedLeaseScope.split('/').includes('..') ? suppliedLeaseScope.replace(/\/+$/, '') : '') ||
  suppliedRepoPath ||
  '(unscoped)'
const leaseKey = `${DEV_ACCOUNT}/${DEV_REGION}/${leaseScope}`

const wantsRollout = readiness.ready && rolloutAllowed
let lease = null
if (wantsRollout) {
  lease = await settleAgent(
    `Acquire the shared DEV deployment lease before a rollout, and report what happened. This is a MUTEX over one AWS environment, not a deploy: do NOT deploy anything, do not run cdk, do not touch any AWS resource.

The lease directory is \`$HOME/.claude/agent-teams-workforce/deploy-leases\`. Create it if it does not exist (\`mkdir -p\`).

The lease for this rollout is the single directory:
  $HOME/.claude/agent-teams-workforce/deploy-leases/${leaseKey.replace(/[^A-Za-z0-9._-]+/g, '_')}

ACQUIRE IT ATOMICALLY. Use \`mkdir\` on that exact path — NOT \`mkdir -p\`, and never a
test-then-create, which races. \`mkdir\` on an existing directory fails, and that failure IS
the lock: exactly one of two concurrent Tasks can win it. On success, write a file
\`holder\` inside it containing the bead id (${(c.bead && c.bead.id) || 'unknown'}), the repo
(${leaseScope}), the epoch seconds you read, and a token you mint (for example from the
shell's own PID and the epoch seconds). Report that token as \`holderToken\`.

IF THE DIRECTORY ALREADY EXISTS, another Task is deploying this scope. Then:
  1. Read its \`holder\` file and work out the lease's age in minutes from the epoch
     seconds recorded in it against the epoch seconds now.
  2. If the lease is OLDER THAN ${LEASE_STALE_MINUTES} MINUTES it belongs to a run that
     died holding it — and so does a lease whose holder bead id is THIS work item
     (${(c.bead && c.bead.id) || 'unknown'}), whatever its age: one work item is never deployed
     by two runs at once, so that lease was left by an earlier dispatch of this same work
     that died holding it. Break it: remove the directory and acquire it yourself by the same
     atomic \`mkdir\`. Report \`brokeStale: true\` and the age you measured in \`staleAgeMinutes\`.
  3. Otherwise WAIT. Poll every 30 seconds, for up to ${LEASE_WAIT_MINUTES} MINUTES total,
     retrying the atomic \`mkdir\` each time, until you either acquire it or the wait is
     spent. Report the seconds you actually waited in \`waitedSeconds\`.
  4. If the wait is spent and you still do not hold it, report \`acquired: false\` and put
     the holder's bead id in \`blockedBy\`. Do not break a lease that is not stale, and do
     not deploy without the lease.

Report literally what happened — an \`acquired: true\` you did not observe would let two
rollouts run against one stack, which is the exact failure this step exists to prevent.`,
    {
      label: 'deploy:lease-acquire',
      // A scripted mkdir protocol with a fixed report; no judgment beyond the stated rules.
      effort: 'low',
      phase: 'Deploy-readiness',
      // The agent that serializes access to a shared environment. Its charter is
      // environment state — provisioning, resetting, and confirming readiness of a shared
      // environment — and it is explicitly an `execute`-category agent that "orchestrates
      // infrastructure state, never agents or work". Holding the mutex that says whose
      // turn it is to mutate dev is that same job. It rules on nothing and deploys nothing.
      agentType: 'agent-teams-workforce:test-environment-orchestrator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['acquired'],
        properties: {
          acquired: { type: 'boolean' },
          holderToken: { type: 'string' },
          leasePath: { type: 'string' },
          waitedSeconds: { type: 'integer' },
          brokeStale: { type: 'boolean' },
          staleAgeMinutes: { type: 'integer' },
          blockedBy: { type: 'string' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
}
const leaseHeld = !!(lease && lease.acquired === true)
// ── ONLY AN EXPLICIT REFUSAL BLOCKS A ROLLOUT ────────────────────────────────
//
// `leaseRefused` is NOT `!leaseHeld`, and the difference is the same asymmetry that makes
// the lease breakable in the first place.
//
// A lease step that reported nothing usable — the dispatch failed, the schema came back
// empty, the step was never run because a caller invoked this mini without one — has told
// us nothing about contention. Treating that silence as "someone else is deploying" would
// mean an unavailable lease MECHANISM stops every deploy in the fleet, which is a strictly
// worse outcome than the collision the lease exists to prevent: the collision is transient
// and CloudFormation itself refuses concurrent updates to a stack, while a wedged mechanism
// is total and needs a person.
//
// So silence falls back to the behaviour that shipped before the lease existed — deploy,
// unserialized — and says so out loud. Only an agent that actually looked and reported
// `acquired: false` blocks the rollout, because only that is evidence of a real holder.
const leaseRefused = !!(lease && lease.acquired === false)
if (wantsRollout && !lease) {
  log(
    `No usable result from the deployment-lease step for ${leaseKey}, so the shared-dev mutex was NOT established. ` +
      'Proceeding with the rollout unserialized — the same behaviour as before the lease existed. A lease step that ' +
      'cannot report is not evidence that another Task is deploying, and treating it as such would stop every deploy.'
  )
}
// THE NAMED REASON. A rollout that did not happen because another Task held the
// environment must say so in those words. Without it the run reports only that it did not
// deploy, and every consumer — the gate, the dashboard, a person reading the journal —
// reads a contention wait as a failed deploy and looks for a defect that is not there.
const leaseBlockedReason = wantsRollout && leaseRefused
  ? `ROLLOUT NOT ATTEMPTED — another Task holds the shared dev deployment lease for ${leaseKey}` +
    `${lease && lease.blockedBy ? ` (held by ${lease.blockedBy})` : ''}. This run waited ` +
    `${(lease && lease.waitedSeconds) || 0}s, up to a bound of ${LEASE_WAIT_MINUTES} minutes, and the holder ` +
    'did not release it. Nothing was deployed and nothing is wrong with the change: dev is one shared ' +
    'environment and two rollouts against one stack corrupt each other. Re-running this phase once the ' +
    'holder finishes is the whole remedy.'
  : ''
if (leaseBlockedReason) log(leaseBlockedReason)
if (lease && lease.brokeStale === true) {
  log(
    `Shared dev deployment lease for ${leaseKey} was BROKEN as stale: it was ${lease.staleAgeMinutes || '?'} minutes ` +
      `old against a ${LEASE_STALE_MINUTES}-minute window, so it belonged to a run that died holding it. A lease ` +
      'nothing can break wedges the stack for every later deploy, so a corpse is cleared rather than waited on.'
  )
}
if (leaseHeld) log(`Holding the shared dev deployment lease for ${leaseKey}${lease.waitedSeconds ? ` after waiting ${lease.waitedSeconds}s` : ''}`)

let rollout = null
if (wantsRollout && !leaseRefused) {
  rollout = await settleAgent(
    `Deploy this change to the DEV environment (AWS account ${DEV_ACCOUNT}, ${DEV_REGION}).

${pinTree}
Rollout strategy: style=${strategy.rolloutStyle}, risk=${strategy.riskLevel}
Deploy just this repo against dev, USING THE MECHANISM THIS REPO ACTUALLY DEPLOYS BY. Do not assume it is CDK: ${
        cdk && cdk.applicable === false
          ? `CDK validation already reported that this repo owns NO CDK app or stack, so \`cdk deploy\` does not exist here and will fail. ${
              cdkDetails ? `The validator reported how this repo actually deploys: ${cdkDetails}. ` : ''
            }Find the real deploy path — check the Taskfile, package.json scripts, and any deploy script — and run that. For a static site this is typically a build followed by \`aws s3 sync\` and a CloudFront invalidation; you MUST wait for the invalidation to report Completed before smoke-testing, or you will read stale cached bytes and wrongly report success.`
          : 'this repo has a CDK app, so run `cdk deploy` for the affected stack(s) against dev.'
} Beware a task NAMED cdk:deploy that runs no CDK operation — read what it actually executes before trusting the name.

Then RUN the smoke tests (${smokeTestFiles.join(', ')} — paths relative to the tree above, so run them from inside it) against the deployed endpoints and report their literal output — a deploy that succeeds while its smoke test fails is a FAILED rollout, not a successful one.

EVIDENCE IS REQUIRED, NOT OPTIONAL. \`deployed\` and \`smokePassed\` are your own booleans about your own work, so the schema demands the observations behind them and the dispatch FAILS without them. Report, for this rollout:
- \`commands\`: every deploy and smoke command you ran, each with the exit code the shell returned. A command you did not run has no row; a row with no exit code is not a result.
- \`commitSha\`: the full SHA of the commit you deployed, read from the tree you deployed FROM (\`git -C "${repo}" rev-parse HEAD\`). This is what binds the deployment to a revision; without it nothing can say WHICH bytes are live.
- \`stacks\`, \`account\`, \`region\`: the stack (or distribution/bucket) name you changed, and the AWS account id and region you changed it in. Say what you actually targeted, not what you were told to target.
- \`smokeCases\`: one row per smoke case, with its name, whether it passed, and its literal output. A smoke suite you did not run is an empty list and \`smokePassed: false\` — never a pass by default.

HARD LIMITS: dev ONLY — never qa, never prod. Do not delete or replace data. If a deploy errors, stop and report exactly where and why, with the failing command and its exit code in \`commands\`. Report literal deploy output; never claim a deployment you did not observe succeed.`,
    {
      label: 'deploy:rollout-dev',
      phase: 'Deploy-readiness',
      agentType: 'agent-teams-workforce:cdk-stack-author',
      // ── THE ROLLOUT REPORTS ITS OBSERVATIONS, NOT JUST ITS CONCLUSIONS ────────
      //
      // This schema used to require three fields, two of which were the agent's own
      // booleans about its own work, and `evidence` — the only thing that could ground
      // either of them — was OPTIONAL. So the strongest claim in the pipeline, "the code
      // is live in AWS dev", rested on a self-report the schema did not ask to justify,
      // and a rollout that reported `deployed: true` with nothing else was structurally
      // indistinguishable from one that had deployed.
      //
      // The five additions are the observations a deploy necessarily produces if it
      // happened at all: the commands and their exit codes, the commit that was deployed,
      // the stack/account/region that received it, and the per-case smoke output. None is
      // a judgment, so none can be argued; an agent that did not deploy cannot fill them
      // in without fabricating a shell transcript, which is a materially harder lie than
      // flipping a boolean. That does not make `deployed` a measurement — see the comment
      // below, which still stands — it makes the claim falsifiable by a reader.
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['deployed', 'stacks', 'smokePassed', 'commands', 'commitSha', 'account', 'region', 'smokeCases'],
        properties: {
          deployed: { type: 'boolean' },
          stacks: { type: 'array', items: { type: 'string' } },
          smokePassed: { type: 'boolean' },
          // Every command run, with the code the shell returned. A deploy nobody can
          // point at a command for did not happen.
          commands: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['command', 'exitCode'],
              properties: { command: { type: 'string' }, exitCode: { type: 'integer' } },
            },
          },
          // What was deployed, as a revision rather than as a description of one.
          commitSha: { type: 'string' },
          account: { type: 'string' },
          region: { type: 'string' },
          // Per-case smoke results. `smokePassed` is a summary of these; the outputs are
          // what the composite quotes back into a Green repair when one fails.
          smokeCases: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['name', 'passed', 'output'],
              properties: { name: { type: 'string' }, passed: { type: 'boolean' }, output: { type: 'string' } },
            },
          },
          evidence: { type: 'string' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
}

// ── RELEASE, AFTER THE SMOKE RUN AND NOT BEFORE ──────────────────────────────
//
// The rollout dispatch above deploys AND runs the smoke tests, so releasing once it
// returns releases after the smoke run — which is the point. Releasing at rollout-success
// instead would hand the environment to the next Task while this one was still asserting
// against it, and the two would read each other's deployments.
//
// This is deliberately NOT a `finally`. If the rollout dispatch throws, the phase dies and
// the lease is left behind — and that case is already answered by the staleness window
// above, which is the whole reason the lease is breakable. A crashed run costs the next
// deploy of that scope a wait, bounded by ${LEASE_STALE_MINUTES} minutes, rather than
// wedging it forever.
let leaseReleased = null
if (leaseHeld) {
  leaseReleased = await settleAgent(
    `Release the shared DEV deployment lease. This is lock bookkeeping, not a deploy: do NOT deploy anything and do not touch any AWS resource.

The lease directory is:
  $HOME/.claude/agent-teams-workforce/deploy-leases/${leaseKey.replace(/[^A-Za-z0-9._-]+/g, '_')}

RELEASE IT ONLY IF IT IS STILL OURS. Read the \`holder\` file inside it and compare the token it records with the token this run holds: ${(lease && lease.holderToken) || '(none reported)'}.

  * Tokens MATCH — remove the directory (\`rm -rf\` on that exact path) and report \`released: true\`.
  * Tokens DIFFER, or the directory is already gone — report \`released: false\` with the reason
    in \`findings\`, and remove NOTHING. A differing token means our lease was judged stale and
    broken by another Task, which is now holding it and deploying: deleting that directory
    would release SOMEONE ELSE'S lock and let a third Task deploy on top of them. An
    already-absent directory is the same situation one step later.

Never remove a lease whose token you did not match.`,
    {
      label: 'deploy:lease-release',
      // One token comparison and one rm: lock bookkeeping, priced as such.
      model: 'haiku',
      effort: 'low',
      phase: 'Deploy-readiness',
      agentType: 'agent-teams-workforce:test-environment-orchestrator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['released'],
        properties: {
          released: { type: 'boolean' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
  log(
    leaseReleased && leaseReleased.released === true
      ? `Released the shared dev deployment lease for ${leaseKey}`
      : `Did NOT release the shared dev deployment lease for ${leaseKey} — it is no longer ours to release ` +
        '(it was broken as stale and another Task holds it now), so it was left alone.'
  )
}

// THE TWO FACTS THIS MINI IS ANSWERABLE FOR, hoisted to the top level of the result so a
// gate can check them MECHANICALLY rather than reading prose. `deployedToDev` is whether
// the bytes reached AWS dev; `smokePassed` is whether the suite that runs only against a
// deployed environment then passed there. Gate 5 asserts both, and the monitoring
// dashboard reads `deployedToDev` for AWS truth — so both names are load-bearing and stay.
// `smokePassed` used to live only inside `rollout`, where a flat deterministic check could
// not see it, which is how a gate came to assert a PR URL instead.
// Nothing about a pull request is reported here any more, because this mini no longer
// performs one. Git truth comes from the composite's Settle step (`settled`, `prUrl`).
// ── THESE TWO ARE NOT EQUALLY STRONG EVIDENCE, AND THE WEAKER ONE IS FIRST ────
//
// `deployedToDev` is SELF-REPORTED. It is the deploying agent's own boolean about its own
// work: nothing in this script observed a stack, an endpoint, or a byte. Read it as a
// claim, not a measurement.
//
// `smokePassed` is the stronger of the two, and materially so — a passing smoke suite had
// to reach a live endpoint over the network and get an answer it accepted. An agent can
// set `deployed:true` for free; it cannot make a failing HTTP call succeed. Where the two
// disagree, believe `smokePassed`.
//
// The residual, stated rather than papered over: a smoke suite proves SOMETHING is live at
// that endpoint, not that THIS CHANGE is what is live. A suite that asserts nothing new
// passes just as happily against the previous deployment. So the pair establishes "a
// working environment is serving", and neither field on its own establishes "the new bytes
// are serving".
//
// WHY THIS IS NOT SIMPLY FIXED HERE. A workflow script cannot observe anything. The runner
// injects exactly seven globals — args, agent, workflow, phase, log, parallel, budget —
// with no filesystem, no network, no process and no way to spawn one. "Observed rather
// than asserted" therefore cannot mean the script checked; it can only ever mean a
// DIFFERENT agent than the one that did the work reported the raw facts, and the script
// ruled on the two accounts. That is segregation of duties, and workspace.js already does
// exactly this with its independent worktree verifier.
//
// So the grounding that would work here is a second read-only dispatch after the rollout —
// told nothing about what the deployer claimed — reporting the stack's own
// `LastUpdatedTime` (or the CloudFront invalidation's completion) for comparison against
// the run's start time. That is a real improvement and it is not free: one extra agent
// dispatch and one AWS call per deploy iteration, on a path that already iterates up to
// three times. It is deliberately NOT done here, and this comment exists so the next
// reader knows the value is a claim rather than discovering it the hard way.
const deployedToDev = !!(rollout && rollout.deployed)
// The summary boolean holds only when the per-case rows agree with it: at least one case
// ran and none failed. A `smokePassed: true` beside a failing or empty case list is the
// rollout contradicting its own observations, and the observations win.
const smokeCases = rollout && Array.isArray(rollout.smokeCases) ? rollout.smokeCases.filter(Boolean) : []
const smokePassed = !!(rollout && rollout.smokePassed === true && smokeCases.length && smokeCases.every((sc) => sc.passed === true))

// Two more facts hoisted for Gate 5's flat checks: `cdkSynthOk` (computed above, with the
// not-applicable carve-out) and `smokeTestFiles`, so "present" is a length check.
const cdkDriftDetected = !!(cdk && cdk.applicable !== false && cdk.driftDetected === true)

const ledger = {
  phase: 'deploy',
  // The honest stage token. `deployed-to-dev` means the code is live in AWS dev — nothing
  // more and nothing less. It is never a claim about git.
  stage: deployedToDev ? 'deployed-to-dev' : 'not-deployed',
  beadId: (c.bead && c.bead.id) || null,
  // Readiness is computed by the script; no lead, facilitator, decider or enforcer runs.
  chosen: [...(priorSmokeFiles.length ? [] : ['smoke-test-author']), 'cdk-infrastructure-drift-detector', ...(touchesPipeline ? ['github-actions-pipeline-implementer'] : []), ...(rollout ? ['cdk-stack-author'] : [])],
  mode: touchesPipeline ? 'pipeline-change' : 'fixed',
  env: targetEnv,
  localGatesOk,
  // The lease is ledgered because "why did this Task not deploy" is otherwise unanswerable
  // after the fact: a contention wait and a blocked readiness verdict both land as
  // deployedToDev:false, and only this row tells them apart.
  leaseKey,
  leaseHeld,
  leaseWaitedSeconds: (lease && lease.waitedSeconds) || 0,
  leaseBrokeStale: !!(lease && lease.brokeStale === true),
  leaseReleased: !!(leaseReleased && leaseReleased.released === true),
  deployedToDev,
  smokePassed,
  rolledOut: deployedToDev,
  ok: readiness.ready && (!rolloutAllowed || (deployedToDev && smokePassed)),
}

// A PRODUCING dispatch that died leaves nothing to gate: the smoke author and the CDK
// validator always, and the rollout when one was wanted and not refused by the lease. The
// caller reports that under its environment stage instead of judging an absent artifact.
const producerDied = !smoke || !cdk || (wantsRollout && !leaseRefused && !rollout)
const deaths = producerDied ? dispatchDeaths('Deploy-readiness') : []
const dispatchFailure = deaths.length
  ? { dispatchFailed: true, dispatchFailures: deaths, reason: `${deaths.length} producing dispatch(es) in the deploy phase returned nothing: ${deaths.map((d) => d.label || d.agentType).join(', ')}` }
  : {}

return { ...dispatchFailure, smoke, cdk, pipeline, strategy, readiness, rollout, env: targetEnv, localGatesOk, cdkSynthOk, cdkApplicable: !!(cdk && cdk.applicable === true), cdkDriftDetected, smokeTestFiles, deployedToDev, smokePassed, deployedToProd: false, lease, leaseKey, leaseHeld, leaseBlocked: leaseBlockedReason || null, leaseReleased: !!(leaseReleased && leaseReleased.released === true), ledger }
