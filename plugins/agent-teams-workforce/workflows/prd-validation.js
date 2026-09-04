export const meta = {
  name: 'prd-validation',
  description:
    'Leaf mini — PRD Validation. ONE independent validation analyst session inspects the raw PRD through six read-only lenses (ambiguity, completeness, conflict, constraints, domain boundaries, requirements clarification) — plus BRD traceability when args.brd is supplied — and the script consolidates the lens findings into one validated-PRD package deterministically. The lenses are all CHECKS on a document authored upstream, so folding them into one checker session preserves segregation of duties (no maker judges its own work) while paying one session-start instead of seven. Read-only: it judges and packages the PRD but authors no PRD content.',
  phases: [
    { title: 'Validate', detail: 'one independent analyst session inspects the raw PRD through every lens' },
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

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

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

// A finding-list schema reused across the lenses that emit flat findings.
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

// ── One session, every lens ──────────────────────────────────────────────────────
// This used to be six (seven with a BRD) separate analyst sessions plus an
// aggregator — eight session-starts to read ONE document. Every lens is an
// independent CHECK on a PRD authored upstream, so segregation of duties is about
// maker-vs-checker, not checker-vs-checker: one session that applies every lens
// judges nothing it produced. The consolidation the aggregator used to do is now
// DETERMINISTIC script code below — folding orphans and clarifications into the
// flat findings list and deriving the verdict are rules, not judgements.
const traceabilitySchema = {
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
}

const analysisSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'summary'],
  properties: {
    ambiguities: findingItems,
    completenessGaps: findingItems,
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
    ...(brd ? { traceability: traceabilitySchema } : {}),
    summary: { type: 'string' },
  },
  ...(brd ? { required: ['ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'traceability', 'summary'] } : {}),
}

const analysis = await agent(
  `${rulingsBlock}You are an INDEPENDENT PRD validation analyst. You did not author this PRD and you never rewrite it — you only inspect it, applying EVERY lens below in one pass. Shared ground rules for all lenses:
- This is a WHAT-level PRD. A requirement that names a desired outcome without naming its implementation mechanism is NOT defective — never flag absent mechanism, thresholds, schemas, or quantified NFRs.
- This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. A requirement owned by a sibling is not a gap, a cross-PRD contract is not a conflict, and naming a sibling's behavior is not a boundary violation — flag a violation only where this PRD claims to OWN behavior a sibling owns.
- The product is built ITERATIVELY: an absence that may legitimately arrive as its own later PRD is scheduling, not a defect — report it at INFO severity only.
- Keep every issue/question/detail field under 40 words. Report findings, not essays.

Lens 1 — AMBIGUITY (return in \`ambiguities\`): requirements whose intended user-observable behavior is genuinely unclear, internally contradictory, or open to two incompatible readings, each with a concrete clarification.
Lens 2 — COMPLETENESS (return in \`completenessGaps\`): each requirement should name an actor, a trigger, and an observable user outcome, with acceptance criteria as observable behavior; flag missing user-observable paths (cancel, error, empty/limit states) described as behavior.
Lens 3 — CONFLICT (return in \`conflicts\`): pairs (or sets) of requirements whose WHAT cannot both hold, citing the requirements in tension.
Lens 4 — CONSTRAINTS (return in \`constraints\`): the explicit AND implied constraints the PRD imposes (regulatory, business, platform, policy), each with its source, kind, and explicit/implied.
Lens 5 — DOMAIN BOUNDARIES (return in \`boundaryFindings\`): requirements that make this feature own behavior another feature or service owns, or that sit in more than one bounded context.
Lens 6 — CLARIFICATION REQUESTS (return in \`clarifications\`): the open questions the author must answer before this PRD can be specified — do not resolve them.
${brd ? `Lens 7 — BRD TRACEABILITY (return in \`traceability\`): map each PRD requirement to the BRD objective(s) it serves; flag orphanRequirements (tracing to NO objective) and unimplementedObjectives (objectives no requirement serves, only where this single PRD could plausibly have served them). A requirement mapping to a stated objective or guiding principle is traced — the BRD states objectives, not features.

BRD objectives:
${brd}
` : ''}
Also return \`summary\`: a plain-language readout (under 120 words) of the PRD's readiness for downstream specification.

Bounded-context / service-boundary notes:
${context}

Repository under consideration: ${repo}

PRD under validation:
${prdBlock}`,
  {
    label: 'validate:all-lenses',
    phase: 'Validate',
    schema: analysisSchema,
  }
)

// ── A DEAD AGENT IS NOT A VERDICT ───────────────────────────────────────────────
//
// `agent()` returns null when the subagent was skipped or died on a terminal API error
// after the runtime's own retries. The PRD was not found wanting; nobody looked at it.
// Without `dispatchFailed` the caller's gate treats this as a failed validation, spends
// its retry budget re-dispatching into the same wall, and hands the supervisor a work
// failure at stage 'prd-validation' — which charges the bead for an account limit.
if (!analysis) {
  return {
    ok: false,
    dispatchFailed: true,
    dispatchFailures: ['validate:all-lenses (validation analyst)'],
    reason:
      'the validation analyst session returned nothing — it was skipped or died on a terminal API error, so the PRD ' +
      'was not judged. This is a DISPATCH failure, not a finding against the PRD.',
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

const ambiguities = analysis.ambiguities || []
const completenessGaps = analysis.completenessGaps || []
const conflicts = analysis.conflicts || []
const constraints = analysis.constraints || []
const boundaryFindings = analysis.boundaryFindings || []
const clarifications = analysis.clarifications || []
const traceability = brd
  ? analysis.traceability || { traceable: false, matrix: [], orphanRequirements: [], unimplementedObjectives: [] }
  : { traceable: false, matrix: [], orphanRequirements: [], unimplementedObjectives: [] }

// ── Deterministic consolidation ─────────────────────────────────────────────────
// The flat findings list and the verdict are RULES over the typed lens outputs, so
// they are computed here rather than asked of a second session. The folding rules
// are unchanged: each BRD orphan folds in as 'major', each clarification as 'info'
// (its open question is the issue), and neither of those alone fails the gate —
// only a blocker-severity defect in the PRD's WHAT does.
const findings = []
for (const f of ambiguities) findings.push({ source: 'ambiguity', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of completenessGaps) findings.push({ source: 'completeness', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of conflicts) findings.push({ source: 'conflict', requirement: (f.requirements || []).join(' + '), issue: f.contradiction, severity: f.severity })
for (const f of boundaryFindings) findings.push({ source: 'domain-boundary', requirement: f.requirement, issue: `crosses boundary: ${f.boundaryCrossed}${f.detail ? ` — ${f.detail}` : ''}`, severity: f.severity })
for (const o of traceability.orphanRequirements || []) findings.push({ source: 'brd-traceability', requirement: o, issue: 'traces to no BRD objective', severity: 'major' })
for (const c of clarifications) findings.push({ source: 'clarification', requirement: c.requirement, issue: c.question, severity: 'info' })
const rank = { blocker: 0, major: 1, minor: 2, info: 3 }
const sevRank = (s) => (rank[s] === undefined ? 4 : rank[s])
findings.sort((x, y) => sevRank(x.severity) - sevRank(y.severity))
const validationVerdict = findings.some((f) => f.severity === 'blocker') ? 'fail' : 'pass'

const ledger = {
  phase: 'prd-validation',
  beadId: null,
  subject: prdId || null,
  chosen: ['validation-analyst-combined' + (brd ? '+brd-traceability' : '')],
  mode: 'combined', // one checker session carries every lens; consolidation is deterministic
  ok: validationVerdict === 'pass',
}

return {
  ok: validationVerdict === 'pass',
  validationVerdict,
  summary: analysis.summary,
  // The validated PRD package: the original PRD plus its consolidated findings.
  validatedPrd: {
    id: prdId || null,
    title: prdTitle || null,
    body: prdBody,
    verdict: validationVerdict,
  },
  findings,
  ambiguities,
  conflicts,
  completenessGaps,
  nfrs: null,
  constraints,
  dependencyGraph: null,
  boundaryFindings,
  clarifications,
  traceability,
  ledger,
}
