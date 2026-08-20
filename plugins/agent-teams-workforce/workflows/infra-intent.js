export const meta = {
  name: 'infra-intent',
  description:
    'Leaf mini — Infrastructure provisioning intent. A maker (cdk-infrastructure-designer) produces concrete, CDK-expressible provisioning intent; independent checkers then validate freshness (dependency changes) and review it (security scan + cost impact). On a blocking cost finding the maker re-runs with checker feedback (bounded 2 passes); deadlock escalates to the architecture-decider. Read-only review — no agent judges its own artifact.',
  phases: [
    { title: 'Provisioning intent', detail: 'cdk-infrastructure-designer authors the intent' },
    { title: 'Freshness', detail: 'dependency-change checks' },
    { title: 'Review', detail: 'independent security scan + cost-impact review' },
  ],
}

// args: {
//   change: { id?, title?, description?, repoPath? },  // the change driving provisioning
//   feedback?: string,                                  // gate feedback from a composite re-run
//   maxCostLoops?: number,                              // maker<->cost-reviewer passes (default 2)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const change = a.change || {}
const repo = change.repoPath || '(repo path not provided — ask before editing files)'
const MAX_COST_LOOPS = a.maxCostLoops || 2

const changeHeader = `${change.id ? `Change ${change.id}: ` : ''}${change.title || '(untitled change)'}
${change.description || ''}
Repository: ${repo}`

// ── Phase 1: Provisioning intent (maker) ──────────────────────────────────────
phase('Provisioning intent')

// Maker prompt is a factory so the cost loop can re-run it with feedback.
function intentPrompt(feedback) {
  return `Produce the concrete provisioning intent for the change below. You are the MAKER — author the intent only; you do not judge it. Work within the repository at: ${repo}

${changeHeader}
${a.feedback ? `\nUpstream gate feedback to address:\n${a.feedback}` : ''}
${feedback ? `\nCost-review feedback from the previous pass — revise the intent to address it without violating the S3 standard:\n${feedback}` : ''}

Deliver CDK-expressible provisioning intent:
- resources: each AWS resource to provision, with the CDK-expressible properties. Every s3.Bucket MUST set versioning enabled and SSE-S3 (S3_MANAGED) encryption — these are non-negotiable.
- stacks: the CDK stacks the resources belong to.
- crossStackRefs: cross-stack references expressed via SSM Parameter Store (never CloudFormation exports).
- affectedStacks: the stacks created or modified by this intent (names).
- rationale: why this shape, tied to the change.`
}

async function makeIntent(feedback) {
  return await agent(intentPrompt(feedback), {
    label: 'intent:author',
    phase: 'Provisioning intent',
    agentType: 'agent-teams-workforce:cdk-infrastructure-designer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['resources', 'stacks', 'crossStackRefs', 'affectedStacks', 'rationale'],
      properties: {
        resources: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['logicalId', 'type', 'stack', 'properties'],
            properties: {
              logicalId: { type: 'string' },
              type: { type: 'string' },
              stack: { type: 'string' },
              properties: { type: 'string' },
            },
          },
        },
        stacks: { type: 'array', items: { type: 'string' } },
        crossStackRefs: { type: 'array', items: { type: 'string' } },
        affectedStacks: { type: 'array', items: { type: 'string' } },
        rationale: { type: 'string' },
      },
    },
  })
}

let intent = await makeIntent('')

// ── Phase 2: Freshness (independent checkers, in parallel) ─────────────────────
phase('Freshness')

const intentText = JSON.stringify(intent, null, 2)

const dependencyChanges = await agent(
  `Detect dependency changes that would INVALIDATE this provisioning intent — CDK/construct-library version drift, removed or renamed constructs, deprecated properties, or upstream service changes. You are an independent checker — you did not author the intent and you do not modify it.

${changeHeader}

Provisioning intent under review:
${intentText}

Report each dependency change that affects the intent and whether it invalidates the intent as written.`,
  {
    label: 'freshness:dependency-changes',
    phase: 'Freshness',
    agentType: 'agent-teams-workforce:dependency-change-detector',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['invalidated', 'changes'],
      properties: {
        invalidated: { type: 'boolean' },
        changes: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['dependency', 'change', 'impact'],
            properties: {
              dependency: { type: 'string' },
              change: { type: 'string' },
              impact: { type: 'string' },
            },
          },
        },
      },
    },
  }
)

const fresh = dependencyChanges.invalidated !== true

// ── Phase 3: Review (independent checkers; cost can drive a bounded maker loop) ─
phase('Review')

// Security scan is independent of the maker and does not change between cost passes.
const securityFindings = await agent(
  `Independently scan this provisioning intent for security misconfiguration — public exposure, missing encryption, over-broad IAM, unencrypted/unversioned buckets, insecure defaults. You are an independent scanner — you did not author the intent and you do not modify it.

${changeHeader}

Provisioning intent under review:
${intentText}

Report each finding with a severity. Encryption/versioning omissions on any S3 bucket and any public-exposure or over-broad-IAM issue are blocking.`,
  {
    label: 'review:security',
    phase: 'Review',
    agentType: 'agent-teams-workforce:infrastructure-security-scanner',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['blocking', 'findings'],
      properties: {
        blocking: { type: 'boolean' },
        findings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['resource', 'issue', 'severity'],
            properties: {
              resource: { type: 'string' },
              issue: { type: 'string' },
              severity: { type: 'string', enum: ['info', 'low', 'medium', 'high', 'critical'] },
            },
          },
        },
      },
    },
  }
)

// Cost review may reject; on a blocking finding re-run the MAKER (segregation of
// duties: the cost reviewer never edits the intent) up to MAX_COST_LOOPS passes.
async function reviewCost(currentIntent, pass) {
  return await agent(
    `Independently review the COST IMPACT of this provisioning intent. You are an independent reviewer — you did not author the intent and you do not modify it.

${changeHeader}

Provisioning intent under review (pass ${pass}):
${JSON.stringify(currentIntent, null, 2)}

Estimate the recurring + one-time cost drivers and flag anything materially over-provisioned. Set blocking=true ONLY for a material, avoidable cost increase. If blocking, give precise feedback the maker can act on WITHOUT weakening the S3 versioning/encryption standard.`,
    {
      label: `review:cost:pass-${pass}`,
      phase: 'Review',
      agentType: 'agent-teams-workforce:cost-impact-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['blocking', 'estimate', 'feedback', 'findings'],
        properties: {
          blocking: { type: 'boolean' },
          estimate: { type: 'string' },
          feedback: { type: 'string' },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['driver', 'concern', 'severity'],
              properties: {
                driver: { type: 'string' },
                concern: { type: 'string' },
                severity: { type: 'string', enum: ['info', 'low', 'medium', 'high'] },
              },
            },
          },
        },
      },
    }
  )
}

let costFindings = await reviewCost(intent, 1)
let costResolved = costFindings.blocking !== true
let costDecision = null

for (let pass = 2; pass <= MAX_COST_LOOPS && !costResolved; pass++) {
  log(`Cost review blocking — re-running cdk-infrastructure-designer (pass ${pass}/${MAX_COST_LOOPS})`)
  intent = await makeIntent(costFindings.feedback || '')
  costFindings = await reviewCost(intent, pass)
  costResolved = costFindings.blocking !== true
}

// Deadlock after the bounded loop -> architecture-decider rules (decider only rules).
if (!costResolved) {
  log('Cost review still blocking after bounded passes — escalating to architecture-decider')
  costDecision = await agent(
    `The cost-impact reviewer and the cdk-infrastructure-designer are deadlocked on this provisioning intent after ${MAX_COST_LOOPS} maker passes. Rule on it. You only rule — you do not author or re-analyze the intent.

${changeHeader}

Final provisioning intent:
${JSON.stringify(intent, null, 2)}

Latest blocking cost feedback:
${costFindings.feedback || '(none captured)'}

Rule: "accept" the intent as-is (cost justified), "revise" with a binding directive the maker must follow, or "reject" the intent. The S3 versioning/encryption standard may not be waived.`,
    {
      label: 'review:cost-deadlock',
      phase: 'Review',
      agentType: 'agent-teams-workforce:architecture-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['ruling', 'rationale'],
        properties: {
          ruling: { type: 'string', enum: ['accept', 'revise', 'reject'] },
          rationale: { type: 'string' },
          directive: { type: 'string' },
        },
      },
    }
  )
  costResolved = !!costDecision && costDecision.ruling === 'accept'
}

// ── Contract: one object threading every phase output ──────────────────────────
const contract = {
  ready:
    fresh &&
    securityFindings.blocking !== true &&
    costResolved,
  change: change.id || null,
  repoPath: change.repoPath || null,
  affectedStacks: intent.affectedStacks,
  fresh,
}

return {
  provisioningIntent: intent,
  affectedStacks: intent.affectedStacks,
  dependencyChanges,
  securityFindings,
  costFindings,
  costDecision,
  fresh,
  contract,
}
