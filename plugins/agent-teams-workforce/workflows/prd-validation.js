export const meta = {
  name: 'prd-validation',
  description:
    'Leaf mini — PRD Validation. A read-only validation lead fans the raw PRD out to six independent analysts in parallel (ambiguity, completeness, conflict, constraints, domain boundaries, requirements clarification), then aggregates their findings into one validated-PRD package. A seventh, BRD traceability, is opt-in and runs only when args.brd is supplied. Read-only: it judges and packages the PRD but authors no PRD content.',
  phases: [
    { title: 'Validate', detail: 'parallel independent analysts inspect the raw PRD' },
    { title: 'Aggregate', detail: 'read-only lead consolidates findings into one package' },
  ],
}

// args: {
//   prd: { id?, title?, body, repoPath? } | string,  // the raw PRD under validation (required)
//   context?: string,                                 // optional bounded-context / service-boundary notes
//   brd?: string,                                     // optional BRD objectives — enables the traceability audit
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = typeof prdInput === 'string' ? '' : prdInput.id || ''
const prdTitle = typeof prdInput === 'string' ? '' : prdInput.title || ''
const repo = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || '(repo path not provided)'
const context = a.context || '(no bounded-context / service-boundary notes supplied)'
const brd = a.brd || (typeof prdInput === 'string' ? '' : prdInput.brd) || ''

if (!prdBody) {
  return {
    ok: false,
    reason: 'prd-validation invoked with an empty PRD body — nothing to validate.',
    validatedPrd: null,
    findings: [],
    ambiguities: [],
    conflicts: [],
    completenessGaps: [],
    nfrs: null,
    constraints: [],
    dependencyGraph: null,
    boundaryFindings: [],
  }
}

const prdHeader = `PRD ${prdId} ${prdTitle}`.trim()
const prdBlock = `${prdHeader ? prdHeader + '\n\n' : ''}${prdBody}`

// A finding-list schema reused across the analysts that emit flat findings.
const findingItems = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirement', 'issue', 'severity'],
    properties: {
      requirement: { type: 'string' },
      issue: { type: 'string' },
      severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
      suggestion: { type: 'string' },
    },
  },
}

phase('Validate')

// All seven analysts are INDEPENDENT checkers. None authors the PRD; each only
// inspects the raw input. They run concurrently — no analyst depends on another.
const [
  ambiguity,
  completeness,
  conflict,
  constraint,
  boundary,
  clarification,
  traceability,
] = await parallel([
  () =>
    agent(
      `You are an INDEPENDENT validator. Flag only requirements whose intended user-observable behavior is genuinely unclear, internally contradictory, or open to two incompatible readings. A requirement that names a desired outcome without naming its implementation mechanism is NOT ambiguous at this altitude — do not flag it. Do NOT rewrite the PRD. For each genuine WHAT-level ambiguity, name the requirement, the ambiguity, its severity, and a concrete clarification.

${prdBlock}`,
      {
        label: 'validate:ambiguity',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:ambiguity-detector',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['ambiguities'],
          properties: { ambiguities: findingItems },
        },
      }
    ),
  () =>
    agent(
      `You are an INDEPENDENT validator. Inspect the PRD for completeness of the WHAT: each requirement should name an actor, a trigger, and an observable user outcome, with acceptance criteria expressed as observable behavior. Flag missing user-observable paths — cancel, error, empty/limit states — described as behavior. Do NOT flag acceptance criteria for lacking mechanism, numeric thresholds, or unit-test precision; observable-behavior acceptance criteria are complete at this altitude. Do NOT author the missing content. For each gap, name the location, what observable behavior is missing, and its severity. This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. A requirement owned by a sibling is NOT a gap in this PRD — do not report it as missing. The product is built ITERATIVELY. A PRD is a business requirement, not a finished description of its feature area. Anything this PRD does not cover may legitimately arrive later as its own PRD, and its absence today is scheduling, NOT a defect. Report such an absence at INFO severity only, named as a candidate future PRD — never as a blocker and never as major.

${prdBlock}`,
      {
        label: 'validate:completeness',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:completeness-checker',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['completenessGaps'],
          properties: { completenessGaps: findingItems },
        },
      }
    ),
  () =>
    agent(
      `You are an INDEPENDENT validator. Detect mutually contradictory requirements in the PRD below — pairs (or sets) whose WHAT cannot both hold. Do NOT manufacture conflicts from absent implementation mechanism. Do NOT resolve them by editing the PRD. For each conflict, cite the two (or more) requirements in tension, explain the contradiction, and rate its severity. This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. A requirement that states what this PRD's behavior means for behavior a sibling owns is a CONTRACT with that sibling, not a contradiction. Do not report a cross-PRD contract as a conflict.

${prdBlock}`,
      {
        label: 'validate:conflict',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:requirements-conflict-detector',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['conflicts'],
          properties: {
            conflicts: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['requirements', 'contradiction', 'severity'],
                properties: {
                  requirements: { type: 'array', items: { type: 'string' } },
                  contradiction: { type: 'string' },
                  severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are an INDEPENDENT analyst. Extract the explicit AND implied constraints the PRD below imposes (regulatory, business, platform, policy). Do NOT author the PRD. For each constraint, give its source in the PRD, its kind, and whether it is explicit or implied.

${prdBlock}`,
      {
        label: 'validate:constraints',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:constraint-extractor',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['constraints'],
          properties: {
            constraints: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['constraint', 'kind', 'explicit'],
                properties: {
                  constraint: { type: 'string' },
                  kind: { type: 'string' },
                  explicit: { type: 'boolean' },
                  source: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are an INDEPENDENT validator. Validate that the requirements in the PRD below respect feature / bounded-context boundaries — no requirement makes this feature own behavior that another feature or service owns, and each requirement sits in exactly one context. Do NOT author the PRD. Flag boundary violations with the requirement and the boundary it crosses. This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. Naming behavior a sibling owns, and stating what this PRD's behavior means for it, is the correct structure of the set — not scope creep and not a boundary violation. Flag a violation only where this PRD claims to OWN behavior a sibling owns.

Bounded-context / service-boundary notes:
${context}

Repository under consideration: ${repo}

PRD under validation:
${prdBlock}`,
      {
        label: 'validate:domain-boundary',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:domain-boundary-validator',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['boundaryFindings'],
          properties: {
            boundaryFindings: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['requirement', 'boundaryCrossed', 'severity'],
                properties: {
                  requirement: { type: 'string' },
                  boundaryCrossed: { type: 'string' },
                  severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
                  detail: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
  () =>
    agent(
      `You are an INDEPENDENT analyst (requirements-clarifier). Identify PRD requirements that are ambiguous, incomplete, or mutually conflicting and return structured CLARIFICATION REQUESTS — the open questions the author must answer before this PRD can be specified. Do NOT resolve them, do NOT rewrite the PRD, and do NOT raise the mere absence of implementation mechanism, thresholds, or schemas at this WHAT altitude. For each, name the requirement, the open question, and why it blocks specification.

${prdBlock}`,
      {
        label: 'validate:clarify',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:requirements-clarifier',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['clarifications'],
          properties: {
            clarifications: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['requirement', 'question'],
                properties: {
                  requirement: { type: 'string' },
                  question: { type: 'string' },
                  reason: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
  // BRD traceability is OPT-IN: it runs only when a BRD is actually supplied.
  // Running it without one produced every requirement as an "orphan", which the
  // aggregator then folded in as major findings — noise that reads as PRD defects.
  // A team with stakeholder-traceability obligations passes args.brd and gets the
  // audit; a team without one pays nothing for a check it did not ask for.
  !brd
    ? () => ({
        traceable: false,
        matrix: [],
        orphanRequirements: [],
        unimplementedObjectives: [],
      })
    : () =>
    agent(
      `You are an INDEPENDENT validator (brd-traceability-auditor). Build a traceability matrix mapping each PRD requirement to the BRD objective(s) it serves. Flag orphanRequirements (PRD requirements tracing to NO BRD objective) and unimplementedObjectives (BRD objectives no PRD requirement serves). Do NOT rewrite the PRD.

A BRD states business objectives, not features. A PRD requirement that maps to a stated objective or guiding principle is traced — do NOT report it as an orphan merely because the BRD names no objective at this feature's altitude. Report unimplementedObjectives only where a BRD objective is one this single PRD could plausibly have served.

BRD objectives:
${brd}

PRD under validation:
${prdBlock}`,
      {
        label: 'validate:brd-traceability',
        phase: 'Validate',
        agentType: 'agent-teams-workforce:brd-traceability-auditor',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['traceable', 'matrix', 'orphanRequirements', 'unimplementedObjectives'],
          properties: {
            traceable: { type: 'boolean' },
            matrix: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['requirement', 'objectives'],
                properties: {
                  requirement: { type: 'string' },
                  objectives: { type: 'array', items: { type: 'string' } },
                },
              },
            },
            orphanRequirements: { type: 'array', items: { type: 'string' } },
            unimplementedObjectives: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    ),
])

phase('Aggregate')

// The same read-only validation lead consolidates the analysts' findings into a
// single package. It is a ROUTER: it aggregates and annotates the existing PRD,
// authoring no new requirements — so it never judges work it produced.
const aggregateInput = {
  prd: { id: prdId, title: prdTitle, body: prdBody },
  ambiguities: ambiguity.ambiguities,
  completenessGaps: completeness.completenessGaps,
  conflicts: conflict.conflicts,
  constraints: constraint.constraints,
  dependencyGraph: null,
  boundaryFindings: boundary.boundaryFindings,
  clarifications: clarification.clarifications,
  traceability: traceability,
}

const aggregate = await agent(
  `You are the prd-validation-lead — a READ-ONLY router. Consolidate the analyst findings below into one validation package. Do NOT author or rewrite PRD requirements; only assemble, deduplicate, and rank what the analysts reported. Do NOT introduce findings of your own — in particular, raise NO concern about missing inputs, severity thresholds, delegation packets, or process/configuration; if something seems missing from your own instructions, ignore it and judge only the PRD. This is a WHAT-level PRD: never treat the absence of implementation mechanism, thresholds, schemas, or quantified NFRs as a finding.

Produce:
- findings: one flat, deduplicated, severity-ranked list of every issue raised across all analysts (carry each finding's source analyst). Fold each brd-traceability-auditor orphanRequirement in as a 'major' finding and each requirements-clarifier clarification in as an 'info' finding (its open question is the issue); these alone do NOT fail the gate.
- validationVerdict: "fail" only if at least one analyst reported a genuine blocker-severity defect in the PRD's WHAT; major, minor, and info findings are recorded for the author but do NOT fail the gate; otherwise "pass".
- summary: a short plain-language readout of the PRD's readiness for downstream specification.

Analyst inputs (already structured — do not re-judge, just consolidate):
${JSON.stringify(aggregateInput, null, 2)}`,
  {
    label: 'aggregate:consolidate',
    phase: 'Aggregate',
    agentType: 'agent-teams-workforce:prd-validation-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['validationVerdict', 'findings', 'summary'],
      properties: {
        validationVerdict: { type: 'string', enum: ['pass', 'fail'] },
        findings: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['source', 'issue', 'severity'],
            properties: {
              source: { type: 'string' },
              requirement: { type: 'string' },
              issue: { type: 'string' },
              severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'info'] },
            },
          },
        },
        summary: { type: 'string' },
      },
    },
  }
)

const ledger = {
  phase: 'prd-validation',
  beadId: null,
  subject: prdId || null,
  chosen: [
    'ambiguity-detector', 'completeness-checker', 'requirements-conflict-detector',
    'constraint-extractor', 'domain-boundary-validator', 'requirements-clarifier',
    ...(brd ? ['brd-traceability-auditor'] : []),
    'prd-validation-lead',
  ],
  mode: 'fixed', // design-mandated full fan-out — all 9 analysts wired
  ok: aggregate.validationVerdict === 'pass',
}

return {
  ok: aggregate.validationVerdict === 'pass',
  validationVerdict: aggregate.validationVerdict,
  summary: aggregate.summary,
  // The validated PRD package: the original PRD plus its consolidated findings.
  validatedPrd: {
    id: prdId || null,
    title: prdTitle || null,
    body: prdBody,
    verdict: aggregate.validationVerdict,
  },
  findings: aggregate.findings,
  ambiguities: ambiguity.ambiguities,
  conflicts: conflict.conflicts,
  completenessGaps: completeness.completenessGaps,
  nfrs: null,
  constraints: constraint.constraints,
  dependencyGraph: null,
  boundaryFindings: boundary.boundaryFindings,
  clarifications: clarification.clarifications,
  traceability,
  ledger,
}
