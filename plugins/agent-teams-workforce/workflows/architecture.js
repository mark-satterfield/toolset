export const meta = {
  name: 'architecture',
  description:
    'Leaf mini — Architecture decision front-end. Turns an architecture question into a ruled decision and a current arc42 SAD. Analysts propose integration/security/cost options; independent challengers stress the patterns and tradeoffs; the architecture-decider rules; the sad-maintainer consolidates the ruling into the SAD source-feed sections (§2/§4/§8/§9) under an independent conformance check. Segregation of duties throughout — proposers never judge, the decider never analyzes or authors, the maintainer never reviews its own SAD edit.',
  phases: [
    { title: 'Proposals', detail: 'integration + security + cost + persistence + cdk options, with context-map + failure-mode analysis (concurrent)' },
    { title: 'Challenge', detail: 'pattern + tradeoff + boundary + ADR + cost-impact + ops-readiness panel (concurrent checkers)' },
    { title: 'Decide', detail: 'architecture-decider rules on proposals + challenges' },
    { title: 'Update SAD', detail: 'author ADRs/fitness/diagrams + selected design drafts from the ruling, then consolidate into arc42 §2/§4/§8/§9, conformance-checked' },
  ],
}

// args: {
//   decision: { id?, title, context, drivers?, repoPath? },  // the architecture question
//   sadPath?: string,        // path to the arc42 SAD (defaults to the vault arch42 tree)
//   feedback?: string,       // optional upstream gate feedback to fold in
//   maxLoops?: number,       // SAD maker-checker passes before decider deadlock (default 2)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const d = a.decision || {}
const sadPath = a.sadPath || 'tech/architecture/arch42/ (skillspoke-docs vault)'
const repo = d.repoPath || '(repo path not provided — ask before editing files)'
const MAX_SAD_LOOPS = a.maxLoops || 2
const upstream = a.feedback ? `\nUpstream gate feedback to fold in:\n${a.feedback}` : ''
if (!d.title) log('⚠ no decision.title supplied — running in dry/demo mode')

const decisionHeader = `Architecture decision ${d.id || ''}: ${d.title || '(untitled)'}
Context: ${d.context || 'n/a'}
Decision drivers: ${(Array.isArray(d.drivers) ? d.drivers : []).join('; ') || 'n/a'}
Work within the repository at: ${repo}${upstream}`

// Shared proposal shape — each maker proposes options with tradeoffs from its lens.
const PROPOSAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'options', 'recommendation'],
  properties: {
    lens: { type: 'string' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'approach', 'pros', 'cons'],
        properties: {
          name: { type: 'string' },
          approach: { type: 'string' },
          pros: { type: 'array', items: { type: 'string' } },
          cons: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    recommendation: { type: 'string' },
  },
}

// Analysis advisors with non-proposal output shapes — a domain context map and a
// failure-mode catalogue that feed the decider alongside the lens proposals.
const CONTEXT_MAP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['contexts', 'relationships'],
  properties: {
    contexts: { type: 'array', items: { type: 'string' } },
    relationships: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['from', 'to', 'kind'],
        properties: {
          from: { type: 'string' },
          to: { type: 'string' },
          kind: { type: 'string' },
        },
      },
    },
  },
}

const FAILURE_MODES_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['failureModes'],
  properties: {
    failureModes: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['failure', 'affects', 'blastRadius'],
        properties: {
          failure: { type: 'string' },
          affects: { type: 'string' },
          blastRadius: { type: 'string' },
        },
      },
    },
  },
}

// ── Phase 1: Proposals ─────────────────────────────────────────────────────────
// Five INDEPENDENT makers propose from their lens, plus two analysis advisors
// (context map, failure modes), all concurrently. The coordinator is a read-only
// router only — it frames the decisions and dispatches; it authors and rules nothing.
phase('Proposals')

const frame = await agent(
  `You are the architecture-decision-workflow-coordinator — a READ-ONLY router. Do NOT author any option and do NOT rule on anything. Frame the decision so the analysts can each propose from their lens: state the sub-decisions to be made, the constraints that bound them, and which lens (integration/decomposition, security, cost) each analyst should focus on.

${decisionHeader}`,
  {
    label: 'proposals:frame',
    phase: 'Proposals',
    agentType: 'agent-teams-workforce:architecture-decision-workflow-coordinator',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['subDecisions', 'constraints', 'dispatch'],
      properties: {
        subDecisions: { type: 'array', items: { type: 'string' } },
        constraints: { type: 'array', items: { type: 'string' } },
        dispatch: { type: 'string' },
      },
    },
  }
)

const frameBlock = `Framing from the coordinator:
Sub-decisions: ${(frame.subDecisions || []).join('; ') || 'n/a'}
Constraints: ${(frame.constraints || []).join('; ') || 'n/a'}`

const makers = [
  {
    agentType: 'agent-teams-workforce:integration-pattern-architect',
    lens: 'integration/decomposition',
    ask: 'Propose the integration and service-decomposition approach: event-driven flows, service boundaries, and the tradeoffs of each option. Honor the platform constraints (event-driven only — no Step Functions; service isolation; SSM for cross-stack refs).',
  },
  {
    agentType: 'agent-teams-workforce:security-architecture-designer',
    lens: 'security',
    ask: 'Propose the security architecture: trust boundaries, authn/authz placement, data protection, and surface the security tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cost-architecture-reviewer',
    lens: 'cost',
    ask: 'Assess the cost-architecture tradeoffs of each option: cost drivers, scaling cost shape, and which option is most cost-efficient for the stated drivers.',
  },
  {
    agentType: 'agent-teams-workforce:persistence-architecture-specialist',
    lens: 'persistence',
    ask: 'Propose the persistence approach: DynamoDB single- vs multi-table design, key schema, GSI/LSI strategy, and the access-pattern tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cdk-infrastructure-designer',
    lens: 'cdk-infrastructure',
    ask: 'Propose the CDK construct topology: Lambda boundaries within the chassis, layer/packaging strategy, and the infrastructure tradeoffs of each option.',
  },
]

const proposalResults = await parallel([
  ...makers.map((m) => () =>
    agent(
      `${m.ask}\n\n${decisionHeader}\n\n${frameBlock}`,
      {
        label: `proposals:${m.lens}`,
        phase: 'Proposals',
        agentType: m.agentType,
        schema: PROPOSAL_SCHEMA,
      }
    )
  ),
  () =>
    agent(
      `You are the bounded-context-mapper. Map the domain boundaries and context relationships this decision touches: which bounded contexts are involved and how they relate (upstream/downstream, conformist, anti-corruption layer). Return the context map; do NOT rule or author options.

${decisionHeader}

${frameBlock}`,
      {
        label: 'proposals:context-map',
        phase: 'Proposals',
        agentType: 'agent-teams-workforce:bounded-context-mapper',
        schema: CONTEXT_MAP_SCHEMA,
      }
    ),
  () =>
    agent(
      `You are the failure-mode-analyst. Model the failure modes the proposed directions must withstand: DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages. For each, name the failure, what it affects, and its blast radius. Do NOT author options or rule.

${decisionHeader}

${frameBlock}`,
      {
        label: 'proposals:failure-modes',
        phase: 'Proposals',
        agentType: 'agent-teams-workforce:failure-mode-analyst',
        schema: FAILURE_MODES_SCHEMA,
      }
    ),
])
const proposals = proposalResults.slice(0, makers.length).filter(Boolean)
const contextMap = proposalResults[makers.length] || null
const failureModes = (proposalResults[makers.length + 1] && proposalResults[makers.length + 1].failureModes) || []
const proposalsText = JSON.stringify(proposals, null, 2)
const analysisText = JSON.stringify({ contextMap, failureModes }, null, 2)

// ── Phase 2: Challenge ─────────────────────────────────────────────────────────
// Six INDEPENDENT checkers stress the proposals concurrently — pattern, tradeoff,
// boundary coupling, ADR conformance, cost-at-scale, and operational readiness.
// Different agents than the makers — no proposer challenges its own proposal.
phase('Challenge')

const challengeResults = await parallel([
  () =>
    agent(
      `You are the architecture-pattern-challenger. Challenge the proposed patterns against SkillSpoke platform constraints and known anti-patterns. Name each pattern that conflicts with a constraint or is a known anti-pattern, with the reason and the constraint it violates. Do NOT author replacement patterns — only challenge.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:patterns',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:architecture-pattern-challenger',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['challenges'],
          properties: {
            challenges: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['target', 'objection', 'severity'],
                properties: {
                  target: { type: 'string' },
                  objection: { type: 'string' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are the architecture-tradeoff-skeptic. Independently stress the stated tradeoffs and expose UNSTATED risk: tradeoffs the proposers understated, hidden coupling, operational cost not accounted for, failure modes glossed over. Do NOT author replacement options — only surface the gaps.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:tradeoffs',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:architecture-tradeoff-skeptic',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['unstatedRisks'],
          properties: {
            unstatedRisks: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['risk', 'affects', 'severity'],
                properties: {
                  risk: { type: 'string' },
                  affects: { type: 'string' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are the architecture-boundary-guardian. Validate each proposed design against bounded-context boundaries and integration constraints. Flag cross-context coupling: where a proposal makes this context own behavior another owns, reaches across a boundary it should respect, or violates service isolation. Do NOT author replacement designs — only flag violations.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:boundaries',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:architecture-boundary-guardian',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['boundaryViolations'],
          properties: {
            boundaryViolations: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['target', 'coupling', 'severity'],
                properties: {
                  target: { type: 'string' },
                  coupling: { type: 'string' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are the adr-completeness-reviewer. Check each proposal against the existing ADR inventory (arc42 SAD §9 and the repo). Flag any proposal that contradicts an accepted ADR without a superseding draft — name the ADR it conflicts with and whether a superseding ADR is required. Do NOT author ADRs — only flag conflicts. SAD location: ${sadPath}.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:adr-conformance',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:adr-completeness-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['adrConflicts'],
          properties: {
            adrConflicts: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['target', 'conflictsWith', 'severity'],
                properties: {
                  target: { type: 'string' },
                  conflictsWith: { type: 'string' },
                  needsSupersedingDraft: { type: 'boolean' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are the cost-impact-reviewer — an adversary to the cost proposal. Stress each option's cost at 10x, 100x, and 1000x the stated load. Find where each option's cost breaks first (the scale at which a cost cliff, throttle, or quota makes it non-viable) and the bottleneck that causes it. Do NOT author replacement options — only expose the breakpoints.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:cost-impact',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:cost-impact-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['scaleBreakpoints'],
          properties: {
            scaleBreakpoints: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['option', 'breaksAt', 'bottleneck', 'severity'],
                properties: {
                  option: { type: 'string' },
                  breaksAt: { type: 'string', enum: ['10x', '100x', '1000x', 'beyond'] },
                  bottleneck: { type: 'string' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are the operational-readiness-reviewer. Evaluate each proposal's operational burden: monitoring, alerting, runbooks, on-call load, failure recovery. Flag readiness gaps — operations the proposal would require but does not account for. Do NOT author the operational design — only flag gaps.

${decisionHeader}

Proposals under challenge:
${proposalsText}`,
      {
        label: 'challenge:ops-readiness',
        phase: 'Challenge',
        agentType: 'agent-teams-workforce:operational-readiness-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['readinessGaps'],
          properties: {
            readinessGaps: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['target', 'concern', 'severity'],
                properties: {
                  target: { type: 'string' },
                  concern: { type: 'string' },
                  severity: { type: 'string', enum: ['blocking', 'major', 'minor'] },
                },
              },
            },
          },
        },
      }
    ),
])

const challenges = {
  patterns: (challengeResults[0] && challengeResults[0].challenges) || [],
  unstatedRisks: (challengeResults[1] && challengeResults[1].unstatedRisks) || [],
  boundaryViolations: (challengeResults[2] && challengeResults[2].boundaryViolations) || [],
  adrConflicts: (challengeResults[3] && challengeResults[3].adrConflicts) || [],
  scaleBreakpoints: (challengeResults[4] && challengeResults[4].scaleBreakpoints) || [],
  readinessGaps: (challengeResults[5] && challengeResults[5].readinessGaps) || [],
}
const challengesText = JSON.stringify(challenges, null, 2)

// ── Phase 3: Decide ─────────────────────────────────────────────────────────────
// The decider ONLY rules — it does not analyze or author. Distinct from makers and
// checkers.
phase('Decide')

const decision = await agent(
  `You are the architecture-decider. Rule on the architecture given the proposals, the analysis, and the challenges. You ONLY rule — do not re-analyze, do not author new options, do not write the SAD. Choose the approach, state the ruling as a decision (not a discussion), and list the constraints the ruling imposes downstream. Also report \`surfaces\` — which design surfaces the ruling creates: events, restApi, graphql, newDomain (any subset, empty if none). Blocking challenges must be resolved by the ruling or the ruling is invalid.

${decisionHeader}

Proposals:
${proposalsText}

Analysis (context map + failure modes):
${analysisText}

Challenges:
${challengesText}`,
  {
    label: 'decide:ruling',
    phase: 'Decide',
    agentType: 'agent-teams-workforce:architecture-decider',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['ruling', 'chosenApproach', 'imposedConstraints', 'resolvedChallenges', 'surfaces'],
      properties: {
        ruling: { type: 'string' },
        chosenApproach: { type: 'string' },
        imposedConstraints: { type: 'array', items: { type: 'string' } },
        resolvedChallenges: { type: 'array', items: { type: 'string' } },
        surfaces: { type: 'array', items: { type: 'string', enum: ['events', 'restApi', 'graphql', 'newDomain'] } },
      },
    },
  }
)

// ── Phase 4: Update SAD ──────────────────────────────────────────────────────────
// Maker-checker bounded loop: sad-maintainer authors the SAD edit, an INDEPENDENT
// sad-conformance-reviewer judges it. On reject, re-run the maker with feedback
// (bounded MAX_SAD_LOOPS passes). On deadlock, the architecture-decider rules.
phase('Update SAD')

// Author the decision artifacts FROM the ruling — ADRs, fitness functions, diagrams —
// concurrently and before SAD consolidation, so the maintainer references rather than
// recreates them. The decider authored none of these.
const decisionContext = `Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}`

const authored = await parallel([
  () => agent(
    `You are the adr-writer. Draft the ADR(s) recording this architecture decision: context, decision, consequences, status (proposed). One ADR per discrete decision. Write FROM the ruling — do NOT re-decide. ADR/SAD location: ${sadPath}.\n\n${decisionContext}`,
    { label: 'author:adr', phase: 'Update SAD', agentType: 'agent-teams-workforce:adr-writer',
      schema: { type: 'object', additionalProperties: false, required: ['adrs'], properties: { adrs: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['title', 'status'], properties: { title: { type: 'string' }, status: { type: 'string' }, path: { type: 'string' } } } } } } }
  ),
  () => agent(
    `You are the architecture-fitness-function-author. Define testable fitness functions from the ruling — mechanically checkable assertions such as "all events publish through the event API" or "all Lambdas extend the chassis". Write FROM the ruling — do NOT re-decide.\n\n${decisionContext}`,
    { label: 'author:fitness', phase: 'Update SAD', agentType: 'agent-teams-workforce:architecture-fitness-function-author',
      schema: { type: 'object', additionalProperties: false, required: ['fitnessFunctions'], properties: { fitnessFunctions: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['assertion', 'check'], properties: { assertion: { type: 'string' }, check: { type: 'string' } } } } } } }
  ),
  () => agent(
    `You are the architecture-diagram-author. Produce the architecture diagram(s) of the decided design in the project's standard Mermaid format. Draw FROM the ruling — do NOT re-decide. SAD location: ${sadPath}.\n\n${decisionContext}`,
    { label: 'author:diagram', phase: 'Update SAD', agentType: 'agent-teams-workforce:architecture-diagram-author',
      schema: { type: 'object', additionalProperties: false, required: ['diagrams'], properties: { diagrams: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['kind', 'summary'], properties: { kind: { type: 'string' }, summary: { type: 'string' }, path: { type: 'string' } } } } } } }
  ),
])
const authoredArtifacts = {
  adrs: (authored[0] && authored[0].adrs) || [],
  fitnessFunctions: (authored[1] && authored[1].fitnessFunctions) || [],
  diagrams: (authored[2] && authored[2].diagrams) || [],
}

// SELECTED design drafts — only the surfaces the ruling actually creates. Each design
// executor produces a concrete draft for the downstream spec phase to elaborate.
const surfaces = Array.isArray(decision.surfaces) ? decision.surfaces : []
const designSpecs = []
if (surfaces.includes('events')) {
  designSpecs.push(['event-schema-designer', 'design:event-schema', 'Design the event schema(s) within the event API envelope format for the decided events.'])
  designSpecs.push(['domain-event-modeler', 'design:domain-events', 'Model the domain events, flows, and contracts the ruling introduces.'])
}
if (surfaces.includes('restApi')) designSpecs.push(['api-contract-designer', 'design:api-contract', 'Produce the OpenAPI contract proposal for the decided REST surface.'])
if (surfaces.includes('graphql')) designSpecs.push(['graphql-schema-designer', 'design:graphql', 'Design the GraphQL schema proposal for the decided AppSync surface.'])
if (surfaces.includes('newDomain')) designSpecs.push(['ubiquitous-language-writer', 'design:ubiquitous-language', 'Capture the ubiquitous language — terms, definitions, usage rules — for the new or affected bounded context.'])
const designDrafts = designSpecs.length
  ? (await parallel(designSpecs.map(([at, label, ask]) => () =>
      agent(`${ask}\n\nDraw FROM the ruling — do NOT re-decide.\n\n${decisionContext}`, {
        label, phase: 'Update SAD', agentType: `agent-teams-workforce:${at}`,
        schema: { type: 'object', additionalProperties: false, required: ['summary'], properties: { summary: { type: 'string' }, path: { type: 'string' } } },
      })
    ))).filter(Boolean)
  : []

const SAD_UPDATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['updatedSections', 'changedFiles', 'summary'],
  properties: {
    updatedSections: { type: 'array', items: { type: 'string' } },
    changedFiles: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}

const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'reject'] },
    findings: { type: 'array', items: { type: 'string' } },
  },
}

async function authorSad(reviewerFeedback) {
  return await agent(
    `You are the sad-maintainer. Consolidate the ruling below into the living arc42 SAD, editing ONLY the source-feed sections it touches: §2 Constraints, §4 Solution Strategy, §8 Crosscutting Concepts, §9 Architecture Decisions. Keep those sections mutually consistent. Edit the living document in place — no changelog narrative, no rewriting history. SAD location: ${sadPath}.

Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}
Resolved challenges: ${(decision.resolvedChallenges || []).join('; ') || 'none'}

Decision artifacts already authored (consolidate references into the SAD; do NOT recreate them):
${JSON.stringify({ adrs: authoredArtifacts.adrs, fitnessFunctions: authoredArtifacts.fitnessFunctions, diagrams: authoredArtifacts.diagrams, designDrafts }, null, 2)}
${reviewerFeedback ? `\nConformance findings from the previous pass — address each:\n${reviewerFeedback}` : ''}

Deliver: which §2/§4/§8/§9 sections you changed, the file paths edited, and a one-line summary of the change.`,
    {
      label: 'sad:maintain',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:sad-maintainer',
      schema: SAD_UPDATE_SCHEMA,
    }
  )
}

async function reviewSad(sadUpdate) {
  return await agent(
    `You are the sad-conformance-reviewer — INDEPENDENT of the sad-maintainer. Check the SAD edit for arc42 conformance and living-document hygiene: are §2/§4/§8/§9 internally consistent, does the edit reflect the ruling without introducing changelog narrative, and is the source feed still valid for downstream TRD/Spec consumers? You only judge — do not edit the SAD. Verdict "pass" only if every finding is non-blocking; otherwise "reject" with specific, actionable findings.

Ruling consolidated: ${decision.ruling}

SAD edit under review:
${JSON.stringify(sadUpdate, null, 2)}`,
    {
      label: 'sad:conformance',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:sad-conformance-reviewer',
      schema: CONFORMANCE_SCHEMA,
    }
  )
}

let sadUpdate = null
let conformanceVerdict = null
let reviewerFeedback = ''
for (let pass = 1; pass <= MAX_SAD_LOOPS; pass++) {
  sadUpdate = await authorSad(reviewerFeedback)
  conformanceVerdict = await reviewSad(sadUpdate)
  if (!conformanceVerdict) {
    log(`SAD conformance pass ${pass}: reviewer returned no verdict`)
    break
  }
  if (conformanceVerdict.verdict === 'pass') {
    log(`SAD conformance: PASS on pass ${pass}/${MAX_SAD_LOOPS}`)
    break
  }
  log(`SAD conformance: REJECT pass ${pass}/${MAX_SAD_LOOPS} — ${(conformanceVerdict.findings || []).join('; ')}`)
  reviewerFeedback = (conformanceVerdict.findings || []).join('\n')
}

// Deadlock: maker-checker exhausted without a pass → the decider rules (never the maker).
if (!conformanceVerdict || conformanceVerdict.verdict !== 'pass') {
  log('SAD maker-checker deadlock — escalating to architecture-decider for a binding ruling')
  const deadlockRuling = await agent(
    `You are the architecture-decider acting as the deadlock authority. The sad-maintainer and sad-conformance-reviewer could not converge within ${MAX_SAD_LOOPS} passes. Rule on how the SAD must read so the source feed (§2/§4/§8/§9) is valid. You ONLY rule — do not author or re-review.

Ruling being consolidated: ${decision.ruling}
Last SAD edit attempted:
${JSON.stringify(sadUpdate, null, 2)}
Unresolved conformance findings:
${(conformanceVerdict && conformanceVerdict.findings || []).join('\n') || '(none captured)'}`,
    {
      label: 'sad:deadlock-ruling',
      phase: 'Update SAD',
      agentType: 'agent-teams-workforce:architecture-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'directive'],
        properties: {
          verdict: { type: 'string', enum: ['accept', 'reject'] },
          directive: { type: 'string' },
        },
      },
    }
  )
  conformanceVerdict = {
    verdict: deadlockRuling && deadlockRuling.verdict === 'accept' ? 'pass' : 'reject',
    findings: deadlockRuling ? [deadlockRuling.directive] : (conformanceVerdict && conformanceVerdict.findings) || [],
    ruledByDecider: true,
  }
}

// ── Return: one object threading every phase output ──────────────────────────────
return {
  ok: !!conformanceVerdict && conformanceVerdict.verdict === 'pass',
  decisionRef: d.id || null,
  proposals,
  tradeoffs: proposals.map((p) => ({ lens: p.lens, recommendation: p.recommendation, options: p.options })),
  contextMap,
  failureModes,
  challenges,
  decision,
  authoredArtifacts,
  designDrafts,
  sadUpdate,
  conformanceVerdict,
}
