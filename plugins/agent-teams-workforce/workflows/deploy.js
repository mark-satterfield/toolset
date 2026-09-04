export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy (Gate 5). DEPLOYS CODE TO AWS DEV; it does not open a pull request and never has one as a precondition. The readiness artifacts the change needs (FinOps, SLOs, runbook, pipeline) are DERIVED from the contract\'s declared surfaces and the changed paths rather than routed by a lead; smoke authoring and CDK synth/drift run concurrently; the rollout plan is ruled by the deployment-strategy-decider only when it has more than one legal answer (a multi-repo span or a non-dev target), and is otherwise stated by the script. The script assembles the readiness inventory from the fields it already holds and the phase-gate-enforcer — the only role permitted to rule — returns the go/no-go. On a go, it rolls out to dev and runs the smoke tests against the deployed endpoints — deploying to dev is how code reaches AWS and is not human-gated. LANDING the work (commit, push, PR) is a separate concern owned by the calling composite\'s Settle step, so this mini can run — repeatedly — with no PR in existence. qa/prod rollout is outward-facing, stays human-gated, and never happens from here.',
  phases: [{ title: 'Deploy-readiness', detail: 'synth + smoke authoring + readiness review, then roll out to AWS dev and smoke-check the deployed endpoints' }],
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
    agent(
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
  return agent(
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
      agent(`${ask}\n\nChange: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}\nChanged files: ${(green.changedFiles || []).join(', ') || 'n/a'}\nWork within: ${repo}`, {
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
  strategy = await agent(
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
let readiness = await agent(
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
let rollout = null
if (readiness && readiness.ready && rolloutAllowed && localGatesOk) {
  rollout = await agent(
    `Deploy this change to the DEV environment (AWS account 616930583457, us-east-1).

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

HARD LIMITS: dev ONLY — never qa, never prod. Do not delete or replace data. If a deploy errors, stop and report exactly where and why. Report literal deploy output; never claim a deployment you did not observe succeed.`,
    {
      label: 'deploy:rollout-dev',
      phase: 'Deploy-readiness',
      agentType: multiRepo
        ? 'agent-teams-workforce:wave-deployment-sequencer'
        : 'agent-teams-workforce:cdk-stack-author',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['deployed', 'stacks', 'smokePassed'],
        properties: {
          deployed: { type: 'boolean' },
          stacks: { type: 'array', items: { type: 'string' } },
          smokePassed: { type: 'boolean' },
          stoppedAtWave: { type: 'string' },
          evidence: { type: 'string' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
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
  deployedToDev,
  smokePassed,
  rolledOut: deployedToDev,
  ok: !!(readiness && readiness.ready) && (!rolloutAllowed || (deployedToDev && smokePassed)),
}

return { artifactsSelected: artifacts, smoke, cdk, readinessArtifacts, strategy, readinessInventory: inventory, readiness, rollout, env: targetEnv, localGatesOk, cdkSynthOk, cdkApplicable: !!(cdk && cdk.applicable === true), cdkDriftDetected, smokeTestFiles, deployedToDev, smokePassed, deployedToProd: false, ledger }
