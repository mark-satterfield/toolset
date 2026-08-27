export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy (Gate 5). DEPLOYS CODE TO AWS DEV; it does not open a pull request and never has one as a precondition. A read-only deployment-lead selects the readiness artifacts the change needs (FinOps, SLOs, runbook, pipeline) and the deployment-strategy-decider rules the rollout plan; smoke tests, CDK synth/drift, and the selected artifacts feed a readiness review that returns a go/no-go. On a go, it rolls out to dev and runs the smoke tests against the deployed endpoints — deploying to dev is how code reaches AWS and is not human-gated. LANDING the work (commit, push, PR) is a separate concern owned by the calling composite\'s Settle step, so this mini can run — repeatedly — with no PR in existence. qa/prod rollout is outward-facing, stays human-gated, and never happens from here.',
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

// deployment-lead (READ-ONLY) routes the readiness sequence and selects which optional
// readiness artifacts this change needs. It reports to Gate 5 and executes no deployment.
const plan = await agent(
  `You are the deployment-lead — a READ-ONLY router. Do NOT deploy or author artifacts. Select which optional readiness artifacts this change needs, from: finops (cost posture), slo (SLOs + error budgets), runbook (incident-response + rollback runbook), pipeline (CI/CD deploy pipeline). A net-new service typically needs all four; a small bug fix may need only finops or none. Return the selected artifact keys.

Change: ${c.bead ? `${c.bead.id} ${c.bead.title}` : 'feature'}
Changed files: ${(green.changedFiles || []).join(', ') || 'n/a'}
Work within: ${repo}`,
  {
    label: 'deploy:plan',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:deployment-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['artifacts'],
      properties: {
        artifacts: { type: 'array', items: { type: 'string', enum: ['finops', 'slo', 'runbook', 'pipeline'] } },
        rationale: { type: 'string' },
      },
    },
  }
)
const artifacts = (plan && Array.isArray(plan.artifacts) ? plan.artifacts : []).filter(Boolean)
const selectionMode = artifacts.length ? 'selected' : 'default'

// Fixed readiness core: smoke tests + CDK synth/drift (always; read-only validation).
const smoke = await agent(
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
)

// NOT-APPLICABLE CARVE-OUT. Not every deployable repo has a CDK surface. A static web app
// ships by `aws s3 sync` + a CloudFront invalidation and owns no CloudFormation stack at all.
// With only {synthValid, driftDetected} to report, such a repo could answer nothing but
// synthValid:false — "no CDK app here" was indistinguishable from "synth is broken" — and the
// readiness review then correctly refused to roll out. ssbd-mqkq died exactly there: the
// remaining work was one s3 sync, SkillSpoke-web has no cdk.json and no stack, and the run
// spent 293k tokens producing readiness artifacts for a deploy it then blocked.
// `applicable:false` is a clean NOT-APPLICABLE, never a failure. Guard it: a repo that HAS a
// CDK app must not escape a broken synth by claiming the stage does not apply.
const cdk = await agent(
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

// deployment-strategy-decider DECIDES the rollout PLAN (wave order, rollout style, risk)
// for the rollout below. It DECIDES only; the rollout itself is executed further down by
// cdk-stack-author (single repo) or wave-deployment-sequencer (multi-repo). Deciding the
// plan and executing it are separate agents on purpose — the decider never deploys.
// Only the outward-facing qa/prod rollout is human-gated, and it never happens from here.
const strategy = await agent(
  `You are the deployment-strategy-decider. Decide the rollout strategy for this change: wave order (cross-repo), rollout style (canary / rolling / blue-green), and the risk level — with rationale. You ONLY decide the plan; you do NOT execute the rollout (that is a separate human-gated action).

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

// THE DEPLOY COULD NEVER FIRE. This stage used to ask production-readiness-review-facilitator
// for a go/no-go — the one thing that agent's charter explicitly forbids ("facilitates only,
// never decides readiness"). It correctly refused, and its refusal collapsed into the schema's
// required boolean as ready:false. Rollout is gated on readiness.ready, so the gate could never
// open: deploy.js could not deploy anything, for any repo, ever. Observed on ssbd-mqkq run
// wf_773feccc-143 — readiness.ready=false with findings that begin "ROLE BOUNDARY: This agent's
// charter explicitly forbids declaring the feature ready or not ready ... the verdict request is
// declined and routed back as an escalation", deployedToDev=false, rollout=null.
// The facilitator was right and the script was wrong. Segregation of duties is the point: the
// facilitator ASSEMBLES the packet, and the Gate 5 verdict belongs to phase-gate-enforcer.
const readinessPacket = await agent(
  `ASSEMBLE the deployment readiness packet for this change. Do NOT issue a go/no-go and do NOT declare the change ready or not ready — that verdict is Gate 5's and belongs to the phase-gate-enforcer, not to you. Your job is to inventory the evidence and state, per item, whether it is PRESENT, MISSING, or NOT APPLICABLE, with what you actually verified.

Cover: unit/integration tests green, smoke tests AUTHORED AND SOUND, CDK synth/drift, documentation currency, the selected readiness artifacts, and the decided rollout strategy.

ON SMOKE TESTS, DO NOT ASK FOR RESULTS HERE. Smoke tests are POST-deployment: they assert what the deployed environment actually serves, so they cannot run — let alone pass — until the deploy that produces those bytes has happened. Demanding smoke results at this point is circular and deadlocks the pipeline. What you inventory now is that the suite EXISTS and is SOUND: it fails against the currently-broken environment, and it SKIPS rather than passes when its target URL is unset. Their passing run is Gate 5 evidence gathered AFTER rollout, not before it.

Smoke tests: ${(smoke && smoke.smokeTestFiles || []).join(', ') || 'none'}
${cdkStatus}
Documentation current: ${a.docCurrency ? a.docCurrency.docsCurrent : 'unknown'}
Readiness artifacts produced: ${artifacts.join(', ') || 'none'}
Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}${feedback}`,
  {
    label: 'deploy:readiness-packet',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:production-readiness-review-facilitator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['inventory'],
      properties: {
        inventory: { type: 'array', items: { type: 'string' } },
        concerns: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// Gate 5 verdict — the enforcer rules, and it is the only role permitted to.
let readiness = await agent(
  `GATE 5 — DEPLOY READINESS. Rule on whether this change may roll out to the ${(a.env || c.env || 'dev').toLowerCase()} environment. Return ready=true (proceed) or ready=false (block), with reasons.

CALIBRATION — read before ruling. The target is dev. Deploying to dev is how code reaches AWS at all; it is internal, pre-production alpha, and serves fewer than five users. It is NOT an outward-facing release, is NOT production, and is NOT human-gated. This is a LIGHT gate by design. The cost of a bad dev deploy is redeploying; the cost of blocking one is that nothing ever reaches AWS and no post-deployment evidence can ever be gathered. When genuinely uncertain, RULE READY — dev is where things are meant to be found out. That uncertainty default is scoped to PROCESS artifacts (absent FinOps, SLOs, runbook, pipeline authoring): it does not apply to unit/integration test evidence. Missing, unconfirmed, or unreported test results are a blocking gap, not uncertainty.

DEPLOYMENT IS NOT THE FINAL STATE, AND IT IS NOT A REWARD FOR PASSING EVERY TEST. It is the step that makes the remaining evidence obtainable. Some tests — every post-deployment smoke test — can only run against a deployed environment, so requiring them to pass BEFORE deploying is circular and permanently deadlocks the pipeline. Never do it.

BLOCK on: failing unit or integration tests, unit or integration tests NOT RUN or NOT REPORTED (an absent, unconfirmed, or evidence-free Green artifact is a third state distinct from pass and fail, and it blocks), a broken CDK synth where CDK applies, a security finding, or an unresolved drift this change would worsen.
DO NOT BLOCK on: smoke tests that have not run or are currently failing against the OLD deployed bytes — that is the defect being fixed and is the normal, expected pre-deploy state. Also do not block on absent FinOps analysis, absent SLO or error-budget design, absent runbook, absent pipeline authoring, a missing wave-execution log, or an artifact marked NOT APPLICABLE; those are process artifacts and their absence is a follow-up item, not a defect. A deploy-only remediation legitimately changes no files, so an empty changed-files list is not a defect either.

What you require of smoke tests HERE is only that a sound suite EXISTS to run afterwards. Their passing run is collected AFTER rollout, where a failing smoke DOES mean the rollout failed.

Readiness packet:
${(readinessPacket && readinessPacket.inventory || []).join('\n') || 'no inventory returned'}
Concerns raised: ${(readinessPacket && readinessPacket.concerns || []).join('; ') || 'none'}
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
// Wave sequencing is for GREENFIELD, cross-repo fleet deploys. A change confined to one
// repo/stack just deploys that stack — pass `multiRepo: true` to opt into wave ordering.
const targetEnv = (a.env || c.env || 'dev').toLowerCase()
const rolloutAllowed = targetEnv === 'dev'
const multiRepo = a.multiRepo === true || c.multiRepo === true

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
const deployedToDev = !!(rollout && rollout.deployed)
const smokePassed = !!(rollout && rollout.smokePassed)

const ledger = {
  phase: 'deploy',
  // The honest stage token. `deployed-to-dev` means the code is live in AWS dev — nothing
  // more and nothing less. It is never a claim about git.
  stage: deployedToDev ? 'deployed-to-dev' : 'not-deployed',
  beadId: (c.bead && c.bead.id) || null,
  chosen: ['deployment-lead', 'smoke-test-author', 'cdk-infrastructure-drift-detector', ...artifactSpecs.map((s) => s[0]), 'deployment-strategy-decider', 'production-readiness-review-facilitator', ...(rollout ? [multiRepo ? 'wave-deployment-sequencer' : 'cdk-stack-author'] : [])],
  mode: selectionMode,
  env: targetEnv,
  localGatesOk,
  deployedToDev,
  smokePassed,
  rolledOut: deployedToDev,
  ok: !!(readiness && readiness.ready) && (!rolloutAllowed || (deployedToDev && smokePassed)),
}

return { plan, smoke, cdk, readinessArtifacts, strategy, readiness, rollout, env: targetEnv, localGatesOk, deployedToDev, smokePassed, deployedToProd: false, ledger }
