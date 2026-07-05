export const meta = {
  name: 'deploy',
  description:
    'Shared-tail mini — Deployment readiness (Gate 5). A read-only deployment-lead selects the readiness artifacts the change needs (FinOps, SLOs, runbook, pipeline) and the deployment-strategy-decider rules the rollout plan; smoke tests, CDK synth/drift, and the selected artifacts feed a production-readiness review that returns a go/no-go. It does NOT run `cdk deploy` to production and does NOT invoke the wave sequencer — the actual rollout is a human-gated, outward-affecting action triggered separately.',
  phases: [{ title: 'Deploy-readiness', detail: 'synth + smoke + readiness review (no prod rollout)' }],
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

const cdk = await agent(
  `Validate the service's CDK: run synth and check for drift between the stacks and deployed infrastructure. READ-ONLY — do not deploy. Report whether synth succeeds and whether drift exists. Work within: ${repo}`,
  {
    label: 'deploy:cdk-validate',
    phase: 'Deploy-readiness',
    agentType: 'agent-teams-workforce:cdk-infrastructure-drift-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['synthValid', 'driftDetected'],
      properties: {
        synthValid: { type: 'boolean' },
        driftDetected: { type: 'boolean' },
        details: { type: 'string' },
      },
    },
  }
)

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
CDK: synthValid=${cdk && cdk.synthValid}, drift=${cdk && cdk.driftDetected}
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

const ledger = {
  phase: 'deploy',
  beadId: (c.bead && c.bead.id) || null,
  chosen: ['deployment-lead', 'smoke-test-author', 'cdk-infrastructure-drift-detector', ...artifactSpecs.map((s) => s[0]), 'deployment-strategy-decider', 'production-readiness-review-facilitator'],
  mode: selectionMode,
  ok: !!(readiness && readiness.ready),
}

return { plan, smoke, cdk, readinessArtifacts, strategy, readiness, deployedToProd: false, ledger }
