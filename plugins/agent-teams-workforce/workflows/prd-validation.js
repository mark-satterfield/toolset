export const meta = {
  name: 'prd-validation',
  description:
    'Leaf mini — PRD Validation. One read-only analyst session inspects a PRD through seven lenses (requirement class, ambiguity, completeness, conflict, constraints, domain boundaries, clarifications), plus an informational BRD traceability mapping when args.brd is supplied; the script consolidates the findings and fails the PRD only on a blocker finding. The requirement-class lens classifies every requirement as business or technical and, given args.archPath, whether the architecture already describes each technical rule; a technical requirement is a major finding, since a PRD keeps business requirements only.',
  phases: [{ title: 'Validate', detail: 'one analyst session inspects the PRD through every lens' }],
}
const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: { prd: { id?, title?, body?, path?, repoPath?, brd? } | string, context?, brd?,
//         archPath?, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what) {
  if (!art) return ''
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.\n2. Then run exactly this command:\n   ${record}\nIf a step fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const prdInput = a.prd || {}
const prdBody = typeof prdInput === 'string' ? prdInput : prdInput.body || ''
const prdId = typeof prdInput === 'string' ? '' : prdInput.id || ''
const prdTitle = typeof prdInput === 'string' ? '' : prdInput.title || ''
const repo = (typeof prdInput === 'string' ? '' : prdInput.repoPath) || '(repo path not provided)'
const context = a.context || '(no bounded-context / service-boundary notes supplied)'
const brd = a.brd || (typeof prdInput === 'string' ? '' : prdInput.brd) || ''


const prdPath = typeof prdInput === 'string' ? '' : String(prdInput.path || '')
const archPath = typeof a.archPath === 'string' ? a.archPath.trim() : ''

const prdHeader = `PRD ${prdId} ${prdTitle}`.trim()
const prdBlock = prdBody.trim() || !prdPath
  ? `${prdHeader ? prdHeader + '\n\n' : ''}${prdBody}`
  : `${prdHeader ? prdHeader + '\n\n' : ''}The PRD is the document at ${prdPath}. Read it in full before you apply any lens.`

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

const requirementClassItems = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['id', 'requirement', 'class', 'reason', 'governs', 'rule', 'archCoverage', 'archRefs'],
    properties: {
      id: { type: 'string' },
      requirement: { type: 'string' },
      class: { type: 'string', enum: ['business', 'technical'] },
      reason: { type: 'string' },
      governs: { type: 'string' },
      rule: { type: 'string' },
      archCoverage: { type: 'string', enum: ['covered', 'absent', 'unchecked', 'n/a'] },
      archRefs: { type: 'array', items: { type: 'string' } },
    },
  },
}

const classLens = `REQUIREMENT CLASS (return in \`requirementClasses\`): classify EVERY requirement the PRD states, once each, as \`business\` or \`technical\`, with a one-line \`reason\`.
- business: what a user, the business or a regulation needs, stated as an outcome that holds however the system is built ("a job seeker's data is stored only in the EU" is business).
- technical: a rule about HOW the system is built — a named technology, resource, configuration, construct, network path or engineering standard ("every S3 bucket is versioned and SSE-S3 encrypted", "PII traffic uses VPC endpoints"). A technical requirement belongs in the architecture — a view of the element it governs, or a crosscutting concept in section 8 — not in a PRD.
A requirement that states both is recorded as two entries with the same \`id\`: the business outcome and the technical rule.
For a technical requirement, name in \`governs\` the kind of thing the rule governs ("S3 bucket", "Lambda function", "VPC endpoint"), and state it in \`rule\` as a condition on that thing: "where the design has an S3 bucket, the bucket is versioned and SSE-S3 encrypted". ${archPath
  ? `Then look for the rule in the architecture at ${archPath}, whose \`arc42/\` folder is the effective version: read the owner's constraints in \`arc42/02-architecture-constraints/README.md\`, and find the views that show the kind of thing the rule governs through the catalog — each view's frontmatter names its \`subject\` and every element it \`shows\` — including the crosscutting concepts in \`arc42/08-crosscutting-concepts\`. Read only the views a search points at. Set \`archCoverage\` to "covered", with the path of each view that describes the rule, relative to the arc42 folder, in \`archRefs\`, when a view already describes it; "absent" when none does.`
  : 'No architecture location was supplied: set `archCoverage` to "unchecked" on every technical requirement.'}
For a business requirement set \`governs\` and \`rule\` to "", \`archCoverage\` to "n/a" and \`archRefs\` to [].
Use each requirement's id as the PRD writes it; where the PRD gives none, number them R1, R2, … in document order.`

/** Returns the classification entries of a structured result, each with its fields normalized. */
function classesOf(result) {
  const list = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim()) : [])
  return (result && Array.isArray(result.requirementClasses) ? result.requirementClasses : [])
    .filter((r) => r && typeof r.id === 'string' && r.id.trim())
    .map((r) => {
      const technical = r.class === 'technical'
      return {
        id: r.id.trim(),
        requirement: r.requirement || '',
        class: technical ? 'technical' : 'business',
        reason: r.reason || '',
        governs: technical ? r.governs || '' : '',
        rule: technical ? r.rule || '' : '',
        archCoverage: technical ? (['covered', 'absent'].includes(r.archCoverage) ? r.archCoverage : 'unchecked') : 'n/a',
        archRefs: technical ? list(r.archRefs) : [],
      }
    })
}

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
  required: ['requirementClasses', 'ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'summary'],
  properties: {
    requirementClasses: requirementClassItems,
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
  ...(brd ? { required: ['requirementClasses', 'ambiguities', 'completenessGaps', 'conflicts', 'constraints', 'boundaryFindings', 'clarifications', 'traceability', 'summary'] } : {}),
}

const analysis = await settleAgent(
  `You are an INDEPENDENT PRD validation analyst. You did not author this PRD and you never rewrite it — you only inspect it, applying EVERY lens below in one pass. Shared ground rules for all lenses:
- This is a WHAT-level PRD. A requirement that names a desired outcome without naming its implementation mechanism is NOT defective — never flag absent mechanism, thresholds, schemas, or quantified NFRs.
- This PRD is one slice of a decomposed set: its \`Specified Elsewhere\` section names the sibling PRD that owns each requirement listed there. A requirement owned by a sibling is not a gap, a cross-PRD contract is not a conflict, and naming a sibling's behavior is not a boundary violation — flag a violation only where this PRD claims to OWN behavior a sibling owns.
- The product is built ITERATIVELY: an absence that may legitimately arrive as its own later PRD is scheduling, not a defect — report it at INFO severity only.
- Keep every issue/question/detail field under 40 words. Report findings, not essays, and do not restate one finding as several.

Lens 0 — ${classLens}
Lens 1 — AMBIGUITY (return in \`ambiguities\`): requirements whose intended user-observable behavior is genuinely unclear, internally contradictory, or open to two incompatible readings, each with a concrete clarification.
Lens 2 — COMPLETENESS (return in \`completenessGaps\`): each requirement should name an actor, a trigger, and an observable user outcome, with acceptance criteria as observable behavior; flag missing user-observable paths (cancel, error, empty/limit states) described as behavior.
Lens 3 — CONFLICT (return in \`conflicts\`): pairs (or sets) of requirements whose WHAT cannot both hold, citing the requirements in tension.
Lens 4 — CONSTRAINTS (return in \`constraints\`): the explicit AND implied constraints the PRD imposes (regulatory, business, platform, policy), each with its source, kind, and explicit/implied.
Lens 5 — DOMAIN BOUNDARIES (return in \`boundaryFindings\`): requirements that make this feature own behavior another feature or service owns, or that sit in more than one bounded context.
Lens 6 — CLARIFICATION REQUESTS (return in \`clarifications\`): the open questions the author must answer before this PRD can be specified — do not resolve them.
${brd ? `Lens 7 — BRD TRACEABILITY (return in \`traceability\`) — INFORMATIONAL ONLY, NOT A JUDGMENT OF THE PRD: map each PRD requirement to the BRD objective(s) it serves. List in orphanRequirements those that map to no objective, and in unimplementedObjectives those objectives no requirement serves (only where this single PRD could plausibly have served them). Set \`traceable\` to say whether a mapping could be built at all — it is NOT a verdict on the PRD. A requirement mapping to a stated objective or guiding principle is traced; the BRD states objectives, not features.

THIS LENS NEVER PRODUCES A DEFECT. A requirement that traces to no BRD objective must NOT be reported as a problem, a gap, an ambiguity, or a conflict through this or any other lens.

BRD objectives:
${brd}
` : ''}
Also return \`summary\`: a plain-language readout (under 120 words) of the PRD's readiness for downstream specification.

Bounded-context / service-boundary notes:
${context}

Repository under consideration: ${repo}

PRD under validation:
${prdBlock}

READING BUDGET: the PRD is the entire object of every lens. Read nothing else unless a lens turns on a specific sibling PRD named in \`Specified Elsewhere\`, and then read only that document, or Lens 0 checks the architecture, and then read only the views its searches point at. Do not survey the repository or the polyrepo.${persistBrief(ART, 'prd-validation.json', 'your complete structured result — every key you return, exactly as you return it — as ONE JSON object')}`,
  {
    label: 'validate:all-lenses',
    effort: 'low',
    phase: 'Validate',
    schema: analysisSchema,
  }
)

if (!analysis) {
  const why = 'the validation analyst session returned nothing; the PRD was not judged'
  return {
    ok: false,
    stage: 'agent-dispatch-failed',
    error: why,
    headline: why,
    reason: why,
    dispatchFailed: true,
    dispatchFailures: dispatchDeaths('Validate'),
    validatedPrd: null,
    findings: [],
    requirementClasses: [],
    ambiguities: [],
    conflicts: [],
    completenessGaps: [],
    constraints: [],
    boundaryFindings: [],
  }
}

const ambiguities = analysis.ambiguities || []
const completenessGaps = analysis.completenessGaps || []
const conflicts = analysis.conflicts || []
const constraints = analysis.constraints || []
const boundaryFindings = analysis.boundaryFindings || []
const clarifications = analysis.clarifications || []
const traceability = (brd && analysis.traceability) || { traceable: false, matrix: [], orphanRequirements: [], unimplementedObjectives: [] }
const requirementClasses = classesOf(analysis)
const technical = requirementClasses.filter((r) => r.class === 'technical')
const archGaps = technical.filter((r) => r.archCoverage === 'absent')

const findings = []
for (const r of technical) {
  const home = r.archCoverage === 'covered' ? `the architecture describes it in ${r.archRefs.join(', ') || 'a view'}` : r.archCoverage === 'absent' ? 'the architecture does not describe it yet' : 'the architecture was not checked'
  findings.push({ source: 'requirement-class', requirement: r.id, issue: `technical requirement (${r.governs || 'unnamed subject'}): ${home}; a PRD keeps business requirements only`, severity: 'major' })
}
for (const f of ambiguities) findings.push({ source: 'ambiguity', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of completenessGaps) findings.push({ source: 'completeness', requirement: f.requirement, issue: f.issue, severity: f.severity })
for (const f of conflicts) findings.push({ source: 'conflict', requirement: (f.requirements || []).join(' + '), issue: f.contradiction, severity: f.severity })
for (const f of boundaryFindings) findings.push({ source: 'domain-boundary', requirement: f.requirement, issue: `crosses boundary: ${f.boundaryCrossed}${f.detail ? ` — ${f.detail}` : ''}`, severity: f.severity })
for (const c of clarifications) findings.push({ source: 'clarification', requirement: c.requirement, issue: c.question, severity: 'info' })
const rank = { blocker: 0, major: 1, minor: 2, info: 3 }
const sevRank = (s) => (rank[s] === undefined ? 4 : rank[s])
findings.sort((x, y) => sevRank(x.severity) - sevRank(y.severity))
const blockers = findings.filter((f) => f.severity === 'blocker').length
const validationVerdict = blockers ? 'fail' : 'pass'

return {
  ok: validationVerdict === 'pass',
  stage: validationVerdict === 'pass' ? 'done' : 'Validate',
  headline: validationVerdict === 'pass' ? `PRD validated: ${findings.length} finding(s), none blocking` : `PRD validation failed: ${blockers} blocker finding(s)`,
  ...(validationVerdict === 'pass' ? {} : { error: `PRD validation failed: ${blockers} blocker finding(s)` }),
  validationVerdict,
  summary: analysis.summary,
  validatedPrd: {
    id: prdId || null,
    title: prdTitle || null,
    body: prdBody,
    verdict: validationVerdict,
  },
  findings,
  requirementClasses,
  technical,
  archGaps,
  ambiguities,
  conflicts,
  completenessGaps,
  constraints,
  boundaryFindings,
  clarifications,
  traceability,
  ledger: {
    phase: 'prd-validation',
    beadId: null,
    subject: prdId || null,
    chosen: ['validation-analyst-combined' + (brd ? '+brd-traceability' : '')],
    mode: 'combined',
    ok: validationVerdict === 'pass',
  },
}
