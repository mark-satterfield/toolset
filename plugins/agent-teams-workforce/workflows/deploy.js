export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy (Gate 5). DEPLOYS CODE TO AWS DEV; it does not open a pull request and never has one as a precondition. The readiness artifacts the change needs (FinOps, SLOs, runbook, pipeline) are DERIVED from the contract\'s declared surfaces and the changed paths rather than routed by a lead; smoke authoring and CDK synth/drift run concurrently; the rollout plan is ruled by the deployment-strategy-decider only when it has more than one legal answer (a multi-repo span or a non-dev target), and is otherwise stated by the script. The script assembles the readiness inventory from the fields it already holds and the phase-gate-enforcer — the only role permitted to rule — returns the go/no-go. On a go, it rolls out to dev and runs the smoke tests against the deployed endpoints — deploying to dev is how code reaches AWS and is not human-gated. LANDING the work (commit, push, PR) is a separate concern owned by the calling composite\'s Settle step, so this mini can run — repeatedly — with no PR in existence. qa/prod rollout is outward-facing, stays human-gated, and never happens from here.',
  phases: [{ title: 'Deploy-readiness', detail: 'synth + smoke authoring + readiness review, then roll out to AWS dev and smoke-check the deployed endpoints' }],
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
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// args: { contract, green, docCurrency?, feedback? }
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
  return {
    ok: false,
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

// MACHINE-CHECKABLE GREEN EVIDENCE (ssbd-1xcs D1). tdd-green.js produces
// { greenConfirmed, evidence } precisely so this stage does not depend on the
// facilitator's prose inventory — the facilitator is forbidden from ruling and
// is not required to run anything. Test evidence has THREE states, not two:
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

// ── READINESS ARTIFACTS ARE DERIVED, NOT ROUTED ──────────────────────────────
//
// This used to be a `deploy:plan` dispatch: a READ-ONLY deployment-lead session whose
// entire output was 0–4 keys picked from a fixed enum. That is the "lead that only
// routes" shape this codebase has already replaced three times — tdd-red derives its
// writers from `contract.surfaces`, integration.js derives its suites from
// SURFACE_SUITES, adversarial.js derives its lanes from SURFACE_ATTACKERS — and it is
// the same trade every time: one session-start spent to save at most one session-start,
// on the critical path of the phase that puts code in AWS.
//
// The mapping below is a lookup over facts the run already holds: the surfaces the
// contract DECLARED (a semantic judgment made once upstream, by the agent that read the
// code) and the paths the Green phase actually changed.
//
// WHY AN UNDECLARED SURFACE LIST DOES NOT FAN OUT HERE, unlike adversarial.js. There, an
// unrun attacker is a vulnerability nobody looked for, so unknown means run everything.
// These four are PROCESS artifacts, and Gate 5's own calibration says in terms that their
// absence is "a follow-up item, not a defect" and must never block a dev rollout. Running
// all four on an unclassified change would pay four sessions for artifacts the gate is
// forbidden to require. So unknown surfaces fall back to the file-path signals alone, and
// the mode is logged either way.
const declaredSurfaces = Array.isArray(c.surfaces)
  ? c.surfaces.map((s) => String(s || '').trim().toLowerCase()).filter(Boolean)
  : null
const changedPaths = (green.changedFiles || []).map((f) => String(f || ''))
const touches = (re) => changedPaths.some((f) => re.test(f))
// A change to infrastructure-as-code: it provisions or alters resources, so it has both
// a cost posture and an incident/rollback story.
const touchesInfra =
  touches(/(^|\/)(cdk|infra|infrastructure|stacks?)(\/|[._-])/i) ||
  touches(/(^|\/)cdk\.json$/i) ||
  touches(/(^|\/)template\.ya?ml$/i)
// The deploy pipeline itself changed, so the pipeline artifact is about to be wrong.
const touchesPipeline = touches(/(^|\/)\.github\/workflows\//i)
const surfaceIn = (names) => !!(declaredSurfaces && declaredSurfaces.some((s) => names.includes(s)))
const artifacts = []
// finops — provisioning, or a surface whose cost scales with traffic or data volume.
if (touchesInfra || surfaceIn(['ml', 'data-pipeline'])) artifacts.push('finops')
// slo — an externally-reachable surface is the only thing an SLI can be defined against.
if (surfaceIn(['api-contract', 'event-chain', 'web-ui', 'performance'])) artifacts.push('slo')
// runbook — an incident-response and rollback procedure is for infrastructure, not code.
if (touchesInfra) artifacts.push('runbook')
// pipeline — author or refresh it only when the change touches it.
if (touchesPipeline) artifacts.push('pipeline')
const selectionMode = declaredSurfaces
  ? artifacts.length ? 'derived' : 'derived-none'
  : artifacts.length ? 'derived-from-paths' : 'derived-from-paths-none'
log(
  `Readiness artifacts (${selectionMode}) from surfaces [${(declaredSurfaces || []).join(', ') || 'undeclared'}] ` +
    `and ${changedPaths.length} changed file(s): ${artifacts.join(', ') || 'none — their absence never blocks a dev rollout'}`
)

// Fixed readiness core: smoke tests + CDK synth/drift (always; read-only validation).
// They are dispatched CONCURRENTLY: smoke authoring reads the bead and the changed
// files, CDK validation reads the repo, and neither consumes the other's output. They
// were sequential for no reason, on the longest stretch of the phase.
const [smoke, cdk] = await parallel([
  () =>
    settleAgent(
      `Author post-deployment smoke tests that verify the fixed behavior against a deployed endpoint. Do not deploy. Work within: ${repo}

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
])

// NOT-APPLICABLE CARVE-OUT. Not every deployable repo has a CDK surface. A static web app
// ships by `aws s3 sync` + a CloudFront invalidation and owns no CloudFormation stack at all.
// With only {synthValid, driftDetected} to report, such a repo could answer nothing but
// synthValid:false — "no CDK app here" was indistinguishable from "synth is broken" — and the
// readiness review then correctly refused to roll out. ssbd-mqkq died exactly there: the
// remaining work was one s3 sync, SkillSpoke-web has no cdk.json and no stack, and the run
// spent 293k tokens producing readiness artifacts for a deploy it then blocked.
// `applicable:false` is a clean NOT-APPLICABLE, never a failure. Guard it: a repo that HAS a
// CDK app must not escape a broken synth by claiming the stage does not apply.
// Declared as a hoisted function so the concurrent wave above can dispatch it while the
// carve-out and its incident history stay next to the prompt they are about: a `function`
// declaration binds before the body runs, so the call site reads above its definition.
function cdkValidate() {
  return settleAgent(
  `Validate the service's CDK: run synth and check for drift between the stacks and deployed infrastructure. READ-ONLY — do not deploy. Work within: ${repo}

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
// Collapse the result into one line the readiness review cannot misread — WITHOUT
// discarding `details`. The anti-spoofing guard in the prompt above only works if a
// false applicable=false is catchable, so a NOT APPLICABLE claim travels with the
// validator's evidence, and a claim with NO evidence is flagged, not absolved.
const cdkDetails = cdk && typeof cdk.details === 'string' ? cdk.details.trim() : ''
const cdkStatus = !cdk
  ? 'CDK: not reported'
  : cdk.applicable === false
    ? cdkDetails
      ? `CDK: NOT APPLICABLE — this repo owns no CDK app or stack, so synth and drift are out of scope and MUST NOT count against readiness. Judge readiness on the tests and smoke evidence alone. Validator evidence for the not-applicable claim: ${cdkDetails}`
      : 'CDK: the validator claims NOT APPLICABLE but supplied no supporting details. The claim is UNSUBSTANTIATED — treat it as unverified, and do not absolve synth and drift on an unevidenced claim.'
    : `CDK: synthValid=${cdk.synthValid}, drift=${cdk.driftDetected}${cdkDetails ? ` — details: ${cdkDetails}` : ''}`

// Selected readiness artifacts — concurrent, distinct concerns. finops/slo are advisory;
// runbook/pipeline author operational artifacts (none of them deploy).
const ARTIFACT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['summary'],
  properties: {
    summary: { type: 'string' },
    paths: { type: 'array', items: { type: 'string' } },
    concerns: { type: 'array', items: { type: 'string' } },
  },
}
const artifactSpecs = []
if (artifacts.includes('finops')) artifactSpecs.push(['finops-analyst', 'deploy:finops', 'Analyze the pre-deployment cost posture: unit economics, scaling cost curve, budget impact. Recommend only — do not decide.'])
if (artifacts.includes('slo')) artifactSpecs.push(['slo-error-budget-designer', 'deploy:slo', 'Design the SLOs and error budgets for this change: SLIs, targets, burn-rate alerts, budget policy.'])
if (artifacts.includes('runbook')) artifactSpecs.push(['incident-response-runbook-designer', 'deploy:runbook', 'Produce the incident-response and rollback runbook for this change.'])
if (artifacts.includes('pipeline')) artifactSpecs.push(['github-actions-pipeline-implementer', 'deploy:pipeline', 'Ensure the GitHub Actions deploy pipeline (OIDC auth, build, test, deploy stages) is present and current for this change; author or update it as needed. Do NOT trigger a deploy.'])
const readinessArtifacts = artifactSpecs.length
  ? (await parallel(artifactSpecs.map(([at, label, ask]) => () =>
      settleAgent(`${ask}\n\nChange: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}\nChanged files: ${(green.changedFiles || []).join(', ') || 'n/a'}\nWork within: ${repo}`, {
        label, phase: 'Deploy-readiness', agentType: `agent-teams-workforce:${at}`, schema: ARTIFACT_SCHEMA,
      })
    ))).filter(Boolean)
  : []

// Rollout target and span. Hoisted above the strategy decision because they are what
// decides whether that decision has more than one legal answer.
const targetEnv = (a.env || c.env || 'dev').toLowerCase()
const rolloutAllowed = targetEnv === 'dev'
// Wave sequencing is for GREENFIELD, cross-repo fleet deploys. A change confined to one
// repo/stack just deploys that stack — pass `multiRepo: true` to opt into wave ordering.
const multiRepo = a.multiRepo === true || c.multiRepo === true

// deployment-strategy-decider DECIDES the rollout PLAN (wave order, rollout style, risk)
// for the rollout below. It DECIDES only; the rollout itself is executed further down by
// cdk-stack-author (single repo) or wave-deployment-sequencer (multi-repo). Deciding the
// plan and executing it are separate agents on purpose — the decider never deploys.
// Only the outward-facing qa/prod rollout is human-gated, and it never happens from here.
//
// ── IT IS ONLY ASKED WHEN THERE IS SOMETHING TO DECIDE ───────────────────────
//
// The two questions it answers are wave ORDER and rollout STYLE. For a SINGLE-REPO
// deploy to DEV both are already settled by the branch below: the rollout prompt tells
// the deployer in terms not to use wave sequencing and not to read waves.yaml, and dev
// serves fewer than five internal users, so there is no traffic to shift gradually and
// no canary population to shift it to. Asking a decider a question with one legal answer
// costs a session on the critical path and returns prose that is then interpolated into
// two prompts as `style=..., risk=...`.
//
// So it runs when the answer is genuinely open — a multi-repo span, which is what wave
// order exists for, or a non-dev target, which is outward-facing and where canary versus
// rolling is a real choice. Otherwise the script states the one legal plan and says, in
// the plan itself, that it was not decided by an agent.
let strategy
if (multiRepo || !rolloutAllowed) {
  strategy = await settleAgent(
    `You are the deployment-strategy-decider. Decide the rollout strategy for this change: wave order (cross-repo), rollout style (canary / rolling / blue-green), and the risk level — with rationale. You ONLY decide the plan; you do NOT execute the rollout (that is a separate human-gated action).

Target environment: ${targetEnv}
Span: ${multiRepo ? 'MULTIPLE repos/stacks — wave order is a real decision here' : 'a single repo/stack'}
Change: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}
Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}`,
    {
      label: 'deploy:strategy',
      phase: 'Deploy-readiness',
      agentType: 'agent-teams-workforce:deployment-strategy-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['rolloutStyle', 'riskLevel'],
        properties: {
          waveOrder: { type: 'array', items: { type: 'string' } },
          rolloutStyle: { type: 'string' },
          riskLevel: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    }
  )
} else {
  strategy = {
    waveOrder: [],
    rolloutStyle: 'single-stack, no wave ordering and no canary',
    riskLevel: 'low (internal dev environment)',
    rationale:
      'Set by the workflow, not decided by an agent: this change is confined to one repo/stack and targets dev, ' +
      'so there is no wave order to rule and no traffic population to canary across. The rollout step below is ' +
      'told the same thing directly.',
    decidedBy: 'workflow',
  }
  log(`Rollout strategy: single-repo deploy to ${targetEnv} — one legal plan, so no strategy session was dispatched`)
}

// ── THE READINESS INVENTORY IS ASSEMBLED BY THE SCRIPT, NOT BY A FACILITATOR ──
//
// THE DEPLOY COULD NEVER FIRE. This stage used to ask production-readiness-review-facilitator
// for a go/no-go — the one thing that agent's charter explicitly forbids ("facilitates only,
// never decides readiness"). It correctly refused, and its refusal collapsed into the schema's
// required boolean as ready:false. Rollout is gated on readiness.ready, so the gate could never
// open: deploy.js could not deploy anything, for any repo, ever. Observed on ssbd-mqkq run
// wf_773feccc-143 — readiness.ready=false with findings that begin "ROLE BOUNDARY: This agent's
// charter explicitly forbids declaring the feature ready or not ready ... the verdict request is
// declined and routed back as an escalation", deployedToDev=false, rollout=null.
// The facilitator was right and the script was wrong. The verdict belongs to
// phase-gate-enforcer, and it always did.
//
// That left the facilitator ASSEMBLING a packet — and every line it was asked to inventory
// is a structured field this script already holds: `smoke.smokeTestFiles`, `cdkStatus`,
// `greenEvidenceOk`, `a.docCurrency`, `artifacts`, `strategy`. It was a restatement layer
// between the script and the enforcer, on the critical path, re-run on every deploy
// iteration. So the script states the inventory and the enforcer reads it directly.
//
// No segregation of duties is lost: the facilitator was never a maker whose work was being
// judged, and it was charter-forbidden from ruling on any of it. The only agent that rules
// here is the one that always did.
const inventory = [
  `Unit/integration tests: ${greenEvidenceOk ? 'GREEN (machine-checked)' : 'NOT CONFIRMED'} — ${greenEvidenceOk ? greenEvidence : 'no confirmed passing run reported'}`,
  `Smoke tests AUTHORED: ${(smoke && smoke.smokeTestFiles || []).length ? `PRESENT — ${(smoke.smokeTestFiles || []).join(', ')}` : 'MISSING — no smoke test file was authored'}`,
  cdkStatus,
  `Documentation currency: ${a.docCurrency ? (a.docCurrency.docsCurrent ? 'CURRENT' : 'STALE') : 'unknown — the documentation track reported nothing'}`,
  `Readiness artifacts produced: ${artifacts.join(', ') || 'none (derived: this change needs none)'}`,
  `Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}${strategy && strategy.decidedBy === 'workflow' ? ' (set by the workflow — a single-repo dev deploy has one legal plan)' : ''}`,
].join('\n')

// Gate 5 verdict — the enforcer rules, and it is the only role permitted to.
let readiness = await settleAgent(
  `GATE 5 — DEPLOY READINESS. Rule on whether this change may roll out to the ${(a.env || c.env || 'dev').toLowerCase()} environment. Return ready=true (proceed) or ready=false (block), with reasons.

CALIBRATION — read before ruling. The target is dev. Deploying to dev is how code reaches AWS at all; it is internal, pre-production alpha, and serves fewer than five users. It is NOT an outward-facing release, is NOT production, and is NOT human-gated. This is a LIGHT gate by design. The cost of a bad dev deploy is redeploying; the cost of blocking one is that nothing ever reaches AWS and no post-deployment evidence can ever be gathered. When genuinely uncertain, RULE READY — dev is where things are meant to be found out. That uncertainty default is scoped to PROCESS artifacts (absent FinOps, SLOs, runbook, pipeline authoring): it does not apply to unit/integration test evidence. Missing, unconfirmed, or unreported test results are a blocking gap, not uncertainty.

DEPLOYMENT IS NOT THE FINAL STATE, AND IT IS NOT A REWARD FOR PASSING EVERY TEST. It is the step that makes the remaining evidence obtainable. Some tests — every post-deployment smoke test — can only run against a deployed environment, so requiring them to pass BEFORE deploying is circular and permanently deadlocks the pipeline. Never do it.

BLOCK on: failing unit or integration tests, unit or integration tests NOT RUN or NOT REPORTED (an absent, unconfirmed, or evidence-free Green artifact is a third state distinct from pass and fail, and it blocks), a broken CDK synth where CDK applies, a security finding, or an unresolved drift this change would worsen.
DO NOT BLOCK on: smoke tests that have not run or are currently failing against the OLD deployed bytes — that is the defect being fixed and is the normal, expected pre-deploy state. Also do not block on absent FinOps analysis, absent SLO or error-budget design, absent runbook, absent pipeline authoring, a missing wave-execution log, or an artifact marked NOT APPLICABLE; those are process artifacts and their absence is a follow-up item, not a defect. A deploy-only remediation legitimately changes no files, so an empty changed-files list is not a defect either.

What you require of smoke tests HERE is only that a sound suite EXISTS to run afterwards. Their passing run is collected AFTER rollout, where a failing smoke DOES mean the rollout failed.

Readiness inventory — assembled by the workflow from the artifacts this phase produced, so every line below is a fact the run holds rather than an agent's account of one:
${inventory}
${greenStatusLine}
${cdkStatus}
Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}${feedback}`,
  {
    label: 'deploy:gate5-verdict',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:phase-gate-enforcer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['ready', 'findings'],
      properties: {
        ready: { type: 'boolean' },
        findings: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// MACHINE-CHECK BACKSTOP (ssbd-1xcs D1). The enforcer's prose verdict cannot
// overrule the machine-checkable Green artifact: without confirmed test evidence
// the gate stays shut no matter what was ruled, because "not run / not reported"
// must resolve as a blocking gap, never through the uncertainty default above.
if (!greenEvidenceOk) {
  readiness = {
    ...(readiness || {}),
    ready: false,
    findings: [
      ...((readiness && readiness.findings) || []),
      'BLOCKED: unit/integration test results are unconfirmed (not run / not reported) — green.greenConfirmed=true with a non-empty green.evidence string is required before any rollout.',
    ],
  }
}

// ── Rollout ───────────────────────────────────────────────────────────────────
// Deploying to dev is how code gets into AWS at all — it is the point of the pipeline,
// not an outward-facing action, and it is NOT human-gated. `dev` is the default target.
// Only qa/prod rollout is human-gated; the sequencer is invoked for those only when a
// caller explicitly asks, and prod never rolls out from here.
// `targetEnv`, `rolloutAllowed` and `multiRepo` are established above the strategy step,
// because they are what decides whether that step has a question worth dispatching.

// ── DEPLOYING IS NOT LANDING, AND NEITHER ONE IS A PRECONDITION OF THE OTHER ──
//
// This mini used to open a pull request here, immediately BEFORE the rollout, and then
// make the rollout conditional on that PR step having reported `gatesPassed`. Both halves
// were wrong, and they were wrong in the same way: a pull request is a migration proposed
// in GitHub. It says nothing about any environment, and it is not evidence that anything
// was deployed anywhere.
//
// The ordering it produced was backwards for what this pipeline is actually for. The goal
// is to get code into the AWS dev environment, which sits squarely inside the TESTING part
// of the lifecycle — and the honest shape of that work is deploy, test, fix, deploy, test,
// possibly several times over, BEFORE a pull request is ever a sensible thing to open. A
// PR opened at deploy time proposes work that the deploy is about to prove is not finished.
//
// So the PR step is gone from here. Landing — commit, push, open the PR — belongs to the
// calling composite's Settle step, which already does exactly that, runs on every exit path
// including this one, and is the only place in the pipeline that touches git. Before this
// change git was touched twice per run, from two different steps, with two different
// agents; now there is one landing step and it is not this one.
//
// WHAT THE ROLLOUT ACTUALLY REQUIRES is the GATES, not the PR agent. The gates the deleted
// step ran were the test suite and `cdk synth` — and both are already established here as
// evidence rather than as an agent's self-report:
//   - the test suite, by the machine-checked Green artifact (`greenEvidenceOk` above), which
//     the Gate 5 backstop already refuses to let a prose verdict overrule;
//   - `cdk synth`, by the cdk-infrastructure-drift-detector's own read-only validation run.
// `ruff check` was the third, and it is a LANDING gate, not a deploy-safety gate: it is
// enforced by the pre-commit hooks that Settle must satisfy to commit at all. Lint does not
// decide whether bytes may reach dev.
// Both conditions are read off artifacts this mini produced, so the rollout depends on
// measured results and not on whether some other step happened to run first.
const cdkSynthOk = !cdk ? false : cdk.applicable === false ? true : cdk.synthValid === true
const localGatesOk = greenEvidenceOk && cdkSynthOk

// Rollout targets dev, which is NOT mainline-gated — dev is how code reaches AWS for fast
// feedback, and it deliberately does not wait on a branch being merged, reviewed, or even
// proposed. It requires only the readiness verdict and the gates above.

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
const leaseScope = suppliedRepoPath || '(unscoped)'
const leaseKey = `${DEV_ACCOUNT}/${DEV_REGION}/${leaseScope}`

const wantsRollout = !!(readiness && readiness.ready && rolloutAllowed && localGatesOk)
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
     died holding it. Break it: remove the directory and acquire it yourself by the same
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

Repo: ${c.repoPath || '(unspecified)'}
Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}
${
  multiRepo
    ? `This change spans MULTIPLE repos/stacks — deploy in approved wave order per /Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke/deployment/waves.yaml and waves.shared.yaml, checking each wave's preconditions first. On failure STOP at that wave and do not continue.`
    : `This change is confined to a SINGLE repo/stack — do NOT use wave sequencing and do NOT read waves.yaml. Deploy just this repo against dev, USING THE MECHANISM THIS REPO ACTUALLY DEPLOYS BY. Do not assume it is CDK: ${
        cdk && cdk.applicable === false
          ? `CDK validation already reported that this repo owns NO CDK app or stack, so \`cdk deploy\` does not exist here and will fail. ${
              cdkDetails ? `The validator reported how this repo actually deploys: ${cdkDetails}. ` : ''
            }Find the real deploy path — check the Taskfile, package.json scripts, and any deploy script — and run that. For a static site this is typically a build followed by \`aws s3 sync\` and a CloudFront invalidation; you MUST wait for the invalidation to report Completed before smoke-testing, or you will read stale cached bytes and wrongly report success.`
          : 'this repo has a CDK app, so run `cdk deploy` for the affected stack(s) against dev.'
      } Beware a task NAMED cdk:deploy that runs no CDK operation — read what it actually executes before trusting the name.`
}

Then RUN the smoke tests (${(smoke && smoke.smokeTestFiles || []).join(', ') || 'none authored'}) against the deployed endpoints and report their literal output — a deploy that succeeds while its smoke test fails is a FAILED rollout, not a successful one.

EVIDENCE IS REQUIRED, NOT OPTIONAL. \`deployed\` and \`smokePassed\` are your own booleans about your own work, so the schema demands the observations behind them and the dispatch FAILS without them. Report, for this rollout:
- \`commands\`: every deploy and smoke command you ran, each with the exit code the shell returned. A command you did not run has no row; a row with no exit code is not a result.
- \`commitSha\`: the full SHA of the commit you deployed, read from the tree you deployed FROM (\`git -C "${c.repoPath || '.'}" rev-parse HEAD\`). This is what binds the deployment to a revision; without it nothing can say WHICH bytes are live.
- \`stacks\`, \`account\`, \`region\`: the stack (or distribution/bucket) name you changed, and the AWS account id and region you changed it in. Say what you actually targeted, not what you were told to target.
- \`smokeCases\`: one row per smoke case, with its name, whether it passed, and its literal output. A smoke suite you did not run is an empty list and \`smokePassed: false\` — never a pass by default.

HARD LIMITS: dev ONLY — never qa, never prod. Do not delete or replace data. If a deploy errors, stop and report exactly where and why, with the failing command and its exit code in \`commands\`. Report literal deploy output; never claim a deployment you did not observe succeed.`,
    {
      label: 'deploy:rollout-dev',
      phase: 'Deploy-readiness',
      agentType: multiRepo
        ? 'agent-teams-workforce:wave-deployment-sequencer'
        : 'agent-teams-workforce:cdk-stack-author',
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
          stoppedAtWave: { type: 'string' },
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
const smokePassed = !!(rollout && rollout.smokePassed)

// ── TWO MORE FACTS HOISTED, FOR THE SAME REASON AND WITH THE SAME CONSEQUENCE ─
//
// The composite's outer Gate 5 carries four criteria, and two of them — "CDK synth
// valid, no unresolved drift" and "Smoke tests present" — were adjudicated in prose
// because the values behind them were nested inside `cdk` and `smoke`, where a flat
// deterministic check cannot reach. That is the same defect `smokePassed` had.
//
// `cdkSynthOk` is already the exact boolean the criterion asks about, INCLUDING the
// not-applicable carve-out: a repo that owns no CDK app cannot fail a synth it does not
// have, so applicable=false reads as true here. A missing cdk result reads as false —
// unknown is not absolution.
//
// `smokeTestFiles` is the flat list, so "present" is a length check rather than a
// reading of the smoke author's prose.
//
// The remaining half of the first criterion — "no UNRESOLVED drift" — is deliberately
// NOT hoisted as a check. `cdk.driftDetected` is a raw observation, and whether drift is
// unresolved and worsened BY THIS CHANGE is a judgment; the criterion says "unresolved",
// not "absent". That judgment still happens, at this mini's own Gate 5 verdict, which
// is told to block on "an unresolved drift this change would worsen" and whose ruling
// gates the rollout. So a deployedToDev:true artifact has already had drift adjudicated
// by an independent enforcer — the outer gate is not the only thing standing between
// drift and a deploy, and it never was.
const cdkDriftDetected = !!(cdk && cdk.applicable !== false && cdk.driftDetected === true)
const smokeTestFiles = (smoke && Array.isArray(smoke.smokeTestFiles) ? smoke.smokeTestFiles : []).filter(Boolean)

const ledger = {
  phase: 'deploy',
  // The honest stage token. `deployed-to-dev` means the code is live in AWS dev — nothing
  // more and nothing less. It is never a claim about git.
  stage: deployedToDev ? 'deployed-to-dev' : 'not-deployed',
  beadId: (c.bead && c.bead.id) || null,
  // No deployment-lead and no production-readiness-review-facilitator: the artifact
  // selection is derived by the script and the readiness inventory is assembled by it.
  // The strategy decider appears only when it was actually dispatched.
  chosen: ['smoke-test-author', 'cdk-infrastructure-drift-detector', ...artifactSpecs.map((s) => s[0]), ...(strategy && strategy.decidedBy === 'workflow' ? [] : ['deployment-strategy-decider']), ...(rollout ? [multiRepo ? 'wave-deployment-sequencer' : 'cdk-stack-author'] : [])],
  mode: selectionMode,
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
  ok: !!(readiness && readiness.ready) && (!rolloutAllowed || (deployedToDev && smokePassed)),
}

return { artifactsSelected: artifacts, smoke, cdk, readinessArtifacts, strategy, readinessInventory: inventory, readiness, rollout, env: targetEnv, localGatesOk, cdkSynthOk, cdkApplicable: !!(cdk && cdk.applicable === true), cdkDriftDetected, smokeTestFiles, deployedToDev, smokePassed, deployedToProd: false, lease, leaseKey, leaseHeld, leaseBlocked: leaseBlockedReason || null, leaseReleased: !!(leaseReleased && leaseReleased.released === true), ledger }
