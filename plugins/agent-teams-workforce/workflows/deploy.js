export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deploy (Gate 5). A read-only deployment-lead selects the readiness artifacts the change needs (FinOps, SLOs, runbook, pipeline) and the deployment-strategy-decider rules the rollout plan; smoke tests, CDK synth/drift, and the selected artifacts feed a readiness review that returns a go/no-go. On a go, it DEPLOYS TO DEV via the wave sequencer and runs the smoke tests against the deployed endpoints — deploying to dev is how code reaches AWS and is not human-gated. qa/prod rollout is outward-facing, stays human-gated, and never happens from here.',
  phases: [{ title: 'Deploy-readiness', detail: 'synth + smoke + readiness review, then open the PR and roll out to dev' }],
}

// args: { contract, green, docCurrency?, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const feedback = a.feedback ? `\nPrior gate feedback to address:\n${a.feedback}` : ''
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'

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
// Collapse the three-state result into one line the readiness review cannot misread.
const cdkStatus = !cdk
  ? 'CDK: not reported'
  : cdk.applicable === false
    ? 'CDK: NOT APPLICABLE — this repo owns no CDK app or stack, so synth and drift are out of scope and MUST NOT count against readiness. Judge readiness on the tests and smoke evidence alone.'
    : `CDK: synthValid=${cdk.synthValid}, drift=${cdk.driftDetected}`

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
// for the human-gated rollout. It does NOT execute it — wave-deployment-sequencer performs
// the actual rollout and is deliberately NOT invoked here (rollout is human-gated).
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

// Production-readiness review aggregates ALL evidence into a go/no-go. It assesses only.
const readiness = await agent(
  `Run a production-readiness review for this change and return a go/no-go. Consider: tests green, smoke tests present, CDK synth valid, no unresolved drift, documentation current, the selected readiness artifacts, and the decided rollout strategy. You do NOT trigger the deploy — you assess readiness only.

Smoke tests: ${(smoke && smoke.smokeTestFiles || []).join(', ') || 'none'}
${cdkStatus}
Documentation current: ${a.docCurrency ? a.docCurrency.docsCurrent : 'unknown'}
Readiness artifacts produced: ${artifacts.join(', ') || 'none'}
Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}${feedback}`,
  {
    label: 'deploy:readiness',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:production-readiness-review-facilitator',
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

// ── Ship: open the PR ─────────────────────────────────────────────────────────
// Until 2026-08-07 NO script in this pipeline set opened a PR. Every composite run
// ended with committed work stranded on a branch, silently violating the definition
// of done ("a PR is opened with skillspoke-pr") — which is why callers kept hand-
// rolling PR creation into ad-hoc agent prompts beside the pipeline.
// MERGE IS NOT THIS STAGE'S JOB. The PR flow owns it: skillspoke-pr posts the
// CodeRabbit review request, shepherd-pr iterates the findings, and the merge lands
// through that flow. This stage must never run `gh pr merge` behind it.
const shipEnabled = a.ship !== false && rolloutAllowed
let ship = null
if (readiness && readiness.ready && shipEnabled) {
  ship = await agent(
    `Open a pull request for this change. Repo: ${repo}

SEQUENCE
1. Confirm the work is committed on a feature branch IN A WORKTREE and pushed to origin. Never branch in a main working tree. If work is uncommitted, commit it as \`type(scope): description\` with NO \`Co-Authored-By\` header.
2. Run the repo's gates LOCALLY FIRST: the test suite, \`ruff check\`, and \`npx cdk synth\`. This fleet has NO CI — no repo has \`.github/workflows\`, so the only PR checks are CodeRabbit and Socket Security, neither of which runs tests, lint, or synth. Your local run is the ONLY real gate. If any gate fails, STOP and report; do not open the PR on known-broken work.
3. Open the PR with \`/Users/msat1971/.local/bin/skillspoke-pr\`. NEVER \`gh pr create\` — CodeRabbit does not scan PRs opened under an agent token, so \`gh pr create\` yields an unreviewed PR.
   KNOWN QUIRK: \`skillspoke-pr\` exits 1 AFTER successfully creating the PR, because its follow-up CodeRabbit comment call fails. DO NOT read exit 1 as failure. Confirm the real outcome in \`~/.claude/pr-daemon.log\`, which records every created PR and its URL.

DO NOT MERGE. Do not run \`gh pr merge\`. Merging is owned by the PR flow (CodeRabbit review, then shepherd-pr iteration), not by this pipeline. Opening the PR is where your job ends.

HARD LIMITS
- NEVER bypass a quality gate. \`--no-verify\` is forbidden in every form. If a hook fails, fix findings, restage, retry; if they cannot be fixed, abort with no commit and report.
- Report the literal PR URL. Never claim a PR you did not observe created in the daemon log.`,
    {
      label: 'deploy:ship-pr',
      phase: 'Deploy-readiness',
      agentType: 'agent-teams-workforce:deployment-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['prOpened', 'gatesPassed'],
        properties: {
          prOpened: { type: 'boolean' },
          prUrl: { type: 'string' },
          gatesPassed: { type: 'boolean' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
}

// Rollout targets dev, which is NOT mainline-gated — dev is how code reaches AWS for
// fast feedback, and the PR merges asynchronously through the review flow. So rollout
// does not wait on the merge; it does require the local gates to have passed.
let rollout = null
if (readiness && readiness.ready && rolloutAllowed && (!shipEnabled || (ship && ship.gatesPassed))) {
  rollout = await agent(
    `Deploy this change to the DEV environment (AWS account 616930583457, us-east-1).

Repo: ${c.repoPath || '(unspecified)'}
Rollout strategy: style=${strategy && strategy.rolloutStyle}, risk=${strategy && strategy.riskLevel}
${
  multiRepo
    ? `This change spans MULTIPLE repos/stacks — deploy in approved wave order per /Users/msat1971/projects/SkillSpoke/apps/personal-agent/SkillSpoke/deployment/waves.yaml and waves.shared.yaml, checking each wave's preconditions first. On failure STOP at that wave and do not continue.`
    : `This change is confined to a SINGLE repo/stack — do NOT use wave sequencing and do NOT read waves.yaml. Deploy just this repo against dev, USING THE MECHANISM THIS REPO ACTUALLY DEPLOYS BY. Do not assume it is CDK: ${
        cdk && cdk.applicable === false
          ? 'CDK validation already reported that this repo owns NO CDK app or stack, so `cdk deploy` does not exist here and will fail. Find the real deploy path — check the Taskfile, package.json scripts, and any deploy script — and run that. For a static site this is typically a build followed by `aws s3 sync` and a CloudFront invalidation; you MUST wait for the invalidation to report Completed before smoke-testing, or you will read stale cached bytes and wrongly report success.'
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

const ledger = {
  phase: 'deploy',
  beadId: (c.bead && c.bead.id) || null,
  chosen: ['deployment-lead', 'smoke-test-author', 'cdk-infrastructure-drift-detector', ...artifactSpecs.map((s) => s[0]), 'deployment-strategy-decider', 'production-readiness-review-facilitator', ...(rollout ? [multiRepo ? 'wave-deployment-sequencer' : 'cdk-stack-author'] : [])],
  mode: selectionMode,
  env: targetEnv,
  prOpened: !!(ship && ship.prOpened),
  prUrl: (ship && ship.prUrl) || null,
  rolledOut: !!(rollout && rollout.deployed),
  ok: !!(readiness && readiness.ready) && (!shipEnabled || !!(ship && ship.prOpened)) && (!rolloutAllowed || !!(rollout && rollout.deployed && rollout.smokePassed)),
}

return { plan, smoke, cdk, readinessArtifacts, strategy, readiness, ship, rollout, env: targetEnv, prOpened: !!(ship && ship.prOpened), prUrl: (ship && ship.prUrl) || null, deployedToDev: !!(rollout && rollout.deployed), deployedToProd: false, ledger }
