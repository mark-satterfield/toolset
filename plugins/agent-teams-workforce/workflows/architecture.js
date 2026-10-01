export const meta = {
  name: 'architecture',
  description:
    'Leaf mini — turns an architecture question into a ruled decision integrated into the effective architecture. The sessions read the architecture themselves: the constraints in section 2, and the views of the elements the question touches, found through the catalog frontmatter. It takes the analysis dimensions from the caller or from a read-only triage session, collects proposals from the selected analysts unless triage rules the question settled, has the architecture-decider rule, and has the architecture-maintainer integrate the ruling into every view that shows a changed element, writing nothing in section 2 (resuming once when the first pass returns nothing). lifecycle_state is per document: an entry in an effective document is used as given and never re-decided; an entry in any other state is best-effort evidence the decider reviews and approves as it stands, updates or replaces. Triage rules the question settled only when every SAD document it relies on is effective. The decider names every entry the ruling relies on (reliedOn); a reviewFiles document the caller names and the ruling omits gets one more decider pass naming it, and a second omission fails the run with omittedFiles; returns approvedFiles, the SAD files holding them, beside sadUpdate.changedFiles; the caller sets both to effective. A ruling with no admissible option writes nothing to the SAD and returns ok:false with the blocking rules as requiredHumanActions.',
  phases: [
    { title: 'Triage', detail: 'classify the decision and select the analysis dimensions, unless the caller supplied them' },
    { title: 'Proposals', detail: 'the selected analysts propose options concurrently; skipped when triage rules the question settled' },
    { title: 'Decide', detail: 'the architecture-decider rules on the proposals, or by citing the SAD when the question is settled, and names every SAD entry the ruling relies on: effective ones used as given, the others reviewed and approved as they stand or changed' },
    { title: 'Update SAD', detail: 'the architecture-maintainer integrates the ruling into every view that shows a changed element' },
  ],
}

const dispatchFailures = []

async function run(prompt, opts) {
  let message = 'returned nothing'
  try {
    const out = await agent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err).slice(0, 300)
  }
  dispatchFailures.push({ label: opts.label, agentType: opts.agentType || null, phase: opts.phase, message })
  log(`${opts.label}: no structured result — ${message}`)
  return null
}

function died(phaseName) {
  const deaths = dispatchFailures.filter((f) => f.phase === phaseName)
  return deaths.length
    ? { dispatchFailed: true, dispatchFailures: deaths, reason: deaths.map((f) => `${f.label}: ${f.message}`).join('; ') }
    : {}
}

// args: { decision: { id?, title, context, drivers?, repoPath? }, sadPath, feedback?,
//   dimensions?, forceFullPanel?, standingRulings?, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

const ART = a.artifacts && typeof a.artifacts === 'object' && typeof a.artifacts.dir === 'string' && a.artifacts.dir ? a.artifacts : null
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(name, what, opts) {
  if (!ART) return ''
  const o = opts || {}
  const file = `${ART.dir}/${name}`
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${ART.script} record ${file} --epic ${ART.epicId} --phase ${ART.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  if (o.beadKey && typeof ART.relDir === 'string' && ART.relDir && typeof ART.beadId === 'string' && ART.beadId) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${ART.beadId} --set-metadata artifact_${o.beadKey}_path=${ART.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}

const d = a.decision || {}
const sadPath = typeof a.sadPath === 'string' ? a.sadPath.trim() : ''
const repo = d.repoPath || '(repo path not provided)'
const upstream = a.feedback ? `\nUpstream gate feedback to fold in:\n${a.feedback}` : ''

if (!sadPath) {
  const why = "no sadPath supplied (the project's ATW_SAD_PATH) — there is no SAD to rule against or write the ruling into. Set ATW_SAD_PATH for the run, or pass sadPath to this mini."
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}

const decisionHeader = `Architecture decision ${d.id || ''}: ${d.title || '(untitled)'}
Context: ${d.context || 'n/a'}
Decision drivers: ${(Array.isArray(d.drivers) ? d.drivers : []).join('; ') || 'n/a'}
Work within the repository at: ${repo}${upstream}`

const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim() : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output.

${rulingsText}

END STANDING RULINGS

`
  : ''

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
        properties: { from: { type: 'string' }, to: { type: 'string' }, kind: { type: 'string' } },
      },
    },
  },
}

const FAILURE_MODES_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['failure', 'affects', 'blastRadius'],
    properties: { failure: { type: 'string' }, affects: { type: 'string' }, blastRadius: { type: 'string' } },
  },
}

const ALL_DIMENSIONS = ['integration', 'security', 'cost', 'persistence', 'cdk', 'bounded-context', 'failure-mode']

const TRIAGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['settled', 'rationale', 'relevantDecisions', 'dimensions', 'reliedOn'],
  properties: {
    settled: { type: 'boolean' },
    rationale: { type: 'string' },
    relevantDecisions: { type: 'array', items: { type: 'string' } },
    dimensions: { type: 'array', items: { type: 'string' } },
    reliedOn: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'state'],
        properties: { file: { type: 'string' }, state: { type: 'string' } },
      },
    },
  },
}

const sadHome = sadPath
const APPROVED_STATE = 'effective'
const APPROVAL_RULE = `\`lifecycle_state\` IS PER FILE. A file whose frontmatter reads \`${APPROVED_STATE}\` has itself been reviewed and approved: its content is used as given and never re-decided. That says nothing about any other file. A file in any other state (\`in-review\`) is not yet trusted: its content is input to check, may well be correct, and is reviewed before anything rests on it. Read the field in every file you open.`

const ARCH_WHERE = `THE ARCHITECTURE AS IT STANDS is at ${sadHome}. It is not inside the product repository ${repo}; do not look for it there.
- The \`02-architecture-constraints\` section holds the owner's constraints. Read its README.md in full.
- The \`04-solution-strategy\` section holds the enterprise-level strategy. Read its README.md.
- Every other section is the design so far, as views. Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of every element this decision touches by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, at every scope the element appears in, and read those views in full.
- Open targets in the \`target/\` folder beside the arc42 folder that show the same elements are designs in progress; read them, so this decision does not contradict them.
- Cite what you rely on by the file's absolute path and the heading inside it.`

const sadBlock = `${ARCH_WHERE}
${APPROVAL_RULE}`

const analystSadBlock = `${ARCH_WHERE}
${APPROVAL_RULE} Your options take every effective file as given; content in any other state is open, and an option may keep, refine or replace it.`

phase('Triage')

const forcedDimensions = Array.isArray(a.dimensions) ? a.dimensions.filter((x) => ALL_DIMENSIONS.includes(x)) : []
let triage = null
let activeDimensions = ALL_DIMENSIONS
if (a.forceFullPanel !== true && forcedDimensions.length) {
  activeDimensions = forcedDimensions
  log(`Triage skipped: the caller selected ${activeDimensions.join(', ')}`)
} else if (a.forceFullPanel !== true) {
  triage = await run(
    `${rulingsBlock}You are the architecture-boundary-guardian acting as the READ-ONLY triage step. Classify this decision against the existing arc42 SAD — do NOT rule on it, do NOT author options, do NOT edit anything. SAD location: ${sadPath}.

List in reliedOn every SAD file whose entries this question rests on, with the \`lifecycle_state\` its frontmatter reads (open the file and copy the field exactly; an empty string when it has none). Return settled=true ONLY when every file in reliedOn reads \`${APPROVED_STATE}\` and those files answer the question as given; otherwise settled=false. A file in any other state answers nothing until the architecture-decider reviews it, however well it is worded, and a question the SAD does not cover at all is not settled. Cite in relevantDecisions the SAD sections that bear on it, and explain the classification in rationale. In dimensions, name ONLY the axes that genuinely bear on the choice, drawn from ${JSON.stringify(ALL_DIMENSIONS)}.

${decisionHeader}`,
    { label: 'triage:classify', effort: 'low', phase: 'Triage', agentType: 'architecture-boundary-guardian', schema: TRIAGE_SCHEMA }
  )
  const picked = triage && Array.isArray(triage.dimensions) ? triage.dimensions.filter((x) => ALL_DIMENSIONS.includes(x)) : []
  if (picked.length) activeDimensions = picked
}
const triageRelied = triage && Array.isArray(triage.reliedOn) ? triage.reliedOn.filter((r) => r && typeof r.file === 'string' && r.file.trim()) : []
const unsettledBy = triageRelied.filter((r) => String(r.state || '').trim() !== APPROVED_STATE)
if (triage && triage.settled === true && (!triageRelied.length || unsettledBy.length)) {
  triage.settled = false
  triage.rationale = `${triage.rationale || ''} — not settled: ${triageRelied.length ? `it relies on SAD file(s) not at ${APPROVED_STATE}: ${unsettledBy.map((r) => r.file).join(', ')}` : 'triage named no SAD file it relies on'}`
  log(`Triage: overruled to not settled — ${triage.rationale}`)
}
const settled = !!(triage && triage.settled === true)
if (settled) {
  activeDimensions = []
  log(`Triage: SETTLED — ${triage.rationale}`)
} else {
  log(`Analysts selected: ${activeDimensions.join(', ')}`)
}

const SURVEY_BOUND = `READING BUDGET — this is a bounded proposal, not a codebase audit.
Your inputs are the framing above and the architecture it points to: section 2's constraints, and the views of the elements this decision touches, found through the catalog. Reason from them first, and cite the files you rely on by path. The architecture lives in a different repository from the product repo named above.
Beyond those views, open files ONLY to resolve a specific question the framing leaves unanswered. Do not survey the repository and do not enumerate services or repositories. Roughly ten tool calls is the expected shape.

Return at most 3 options with honest tradeoffs. Keep every tradeoff, failure mode and assumption under 30 words.`

const makers = [
  {
    agentType: 'integration-pattern-architect',
    dim: 'integration',
    lens: 'integration/decomposition',
    ask: 'Propose the integration and service-decomposition approach: event-driven flows, service boundaries, and the tradeoffs of each option. Honor the platform constraints (event-driven only — no Step Functions; service isolation; SSM for cross-stack refs).',
  },
  {
    agentType: 'security-architecture-designer',
    dim: 'security',
    lens: 'security',
    ask: 'Propose the security architecture: trust boundaries, authn/authz placement, data protection, and surface the security tradeoffs of each option.',
  },
  {
    agentType: 'cost-architecture-reviewer',
    dim: 'cost',
    lens: 'cost',
    ask: 'Assess the cost-architecture tradeoffs of each option: cost drivers, scaling cost shape, and which option is most cost-efficient for the stated drivers.',
  },
  {
    agentType: 'persistence-architecture-specialist',
    dim: 'persistence',
    lens: 'persistence',
    ask: 'Propose the persistence approach: DynamoDB single- vs multi-table design, key schema, GSI/LSI strategy, and the access-pattern tradeoffs of each option.',
  },
  {
    agentType: 'cdk-infrastructure-designer',
    dim: 'cdk',
    lens: 'cdk-infrastructure',
    ask: 'Propose the CDK construct topology: Lambda boundaries within the chassis, layer/packaging strategy, and the infrastructure tradeoffs of each option.',
  },
]

let proposals = []
let contextMap = null
let failureModes = []
if (!settled) {
  phase('Proposals')
  const frameBlock = `Panel framing:
Analysis axes on this decision: ${activeDimensions.join(', ')}
Propose from YOUR lens only. The other axes are covered by the analysts dispatched alongside you, and the architecture-decider composes one ruling from all of them.`
  const activeMakers = makers.filter((m) => activeDimensions.includes(m.dim))
  const wantsContextMap = activeDimensions.includes('bounded-context')
  const wantsFailureModes = activeDimensions.includes('failure-mode')

  const jobs = activeMakers.map((m) => () =>
    run(`${rulingsBlock}${m.ask}\n\n${decisionHeader}\n\n${analystSadBlock}\n\n${frameBlock}\n\n${SURVEY_BOUND}`, {
      label: `proposals:${m.lens}`,
      phase: 'Proposals',
      agentType: m.agentType,
      schema: PROPOSAL_SCHEMA,
      effort: 'low',
    })
  )
  if (wantsContextMap || wantsFailureModes) {
    jobs.push(() =>
      run(
        `${rulingsBlock}You are a read-only architecture analysis advisor. Produce the analysis artifact(s) named below in one pass, each under its own key. Do NOT rule or author options.
${wantsContextMap ? `
- \`contextMap\`: map the domain boundaries and context relationships this decision touches — which bounded contexts are involved and how they relate (upstream/downstream, conformist, anti-corruption layer).` : ''}${wantsFailureModes ? `
- \`failureModes\`: model the failure modes the proposed directions must withstand — DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages. For each, name the failure, what it affects, and its blast radius.` : ''}

${decisionHeader}

${analystSadBlock}

${frameBlock}

${SURVEY_BOUND}`,
        {
          label: 'proposals:analysis-advisors',
          phase: 'Proposals',
          effort: 'low',
          agentType: wantsContextMap ? 'bounded-context-mapper' : 'failure-mode-analyst',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: [...(wantsContextMap ? ['contextMap'] : []), ...(wantsFailureModes ? ['failureModes'] : [])],
            properties: {
              ...(wantsContextMap ? { contextMap: CONTEXT_MAP_SCHEMA } : {}),
              ...(wantsFailureModes ? { failureModes: FAILURE_MODES_ITEMS } : {}),
            },
          },
        }
      )
    )
  }
  const results = await parallel(jobs)
  proposals = results.slice(0, activeMakers.length).filter(Boolean)
  const advisors = wantsContextMap || wantsFailureModes ? results[activeMakers.length] : null
  if (advisors) {
    contextMap = advisors.contextMap || null
    failureModes = advisors.failureModes || []
  }
}

phase('Decide')

const evidenceBlock = settled
  ? `Triage classified this decision as SETTLED by the existing SAD, so no analyst panel ran.
Triage rationale: ${triage.rationale}
Relevant prior decisions: ${(Array.isArray(triage.relevantDecisions) ? triage.relevantDecisions : []).join('; ') || '(none)'}

Rule by CITING those prior decisions as the SAD states them. If they do not answer this question, say so in the ruling.`
  : `Proposals:
${JSON.stringify(proposals, null, 2)}

Analysis (context map + failure modes):
${JSON.stringify({ contextMap, failureModes }, null, 2)}`

const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['admissible', 'ruling', 'imposedConstraints', 'resolvedChallenges', 'blockingRules', 'ruleChallenges', 'reliedOn'],
  properties: {
    admissible: { type: 'boolean' },
    reliedOn: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'file', 'disposition'],
        properties: {
          id: { type: 'string' },
          file: { type: 'string' },
          disposition: { type: 'string', enum: ['used-as-given', 'approved', 'changed'] },
        },
      },
    },
    ruling: { type: 'string' },
    chosenApproach: { type: 'string' },
    imposedConstraints: { type: 'array', items: { type: 'string' } },
    resolvedChallenges: { type: 'array', items: { type: 'string' } },
    blockingRules: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'whyBlocking', 'classification'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          whyBlocking: { type: 'string' },
          classification: { type: 'string', enum: ['constitutive', 'convention'] },
        },
      },
    },
    ruleChallenges: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'recommendedChange', 'rationale'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          recommendedChange: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    },
  },
}

const DECIDER_CHARTER = `You are the architecture-decider. Rule on the architecture given the evidence below. You do not analyze and you do not write the architecture.

YOU HAVE THE ARCHITECTURE. Where it is, and how to find the views this ruling touches, is below. Your ruling is integrated into those views and becomes effective architecture, so rule AGAINST what they already show: an option that differs from an effective view states its reason and evidence, and you name the view it changes. Read the views of the elements this ruling touches; do not survey the rest.

EFFECTIVE DOCUMENTS ARE USED AS GIVEN; EVERY OTHER DOCUMENT THIS RULING RELIES ON, YOU REVIEW.
- \`lifecycle_state\` is per document. An entry whose file reads \`${APPROVED_STATE}\` is approved: rule with it as given (disposition \`used-as-given\`); this ruling never re-decides it. Where the PRD cannot be served without changing one, record a ruleChallenge naming it.
- An entry whose file is in any other state (\`in-review\`, \`draft\`) is not yet trusted, but it is evidence, not something to discard, and it may already be right. Every such entry this ruling relies on, you review, reading it in full, against AWS best practice, the AWS Well-Architected Framework and price (use the AWS MCP Server documentation tools where the entry names an AWS service): approve it as it stands (disposition \`approved\`), or update or replace it in the ruling (disposition \`changed\`). "It already answers the PRD" is a reason to approve it, never a reason to leave it unreviewed.
- List in \`reliedOn\` EVERY part of the architecture this ruling relies on, in any state, with its id (the heading of the part relied on), the absolute path of the file that holds it, and its disposition. This list is the record of the architecture the PRD rests on.
- Once the ruling is integrated, every file in \`reliedOn\` and every file the ruling changes or creates is set to \`lifecycle_state: ${APPROVED_STATE}\`.

YOUR AUTHORITY, AND ITS LIMITS:
- Normally you CHOOSE among the options proposed and state the ruling as a decision, not a discussion. Set admissible=true and fill chosenApproach.
- If NO proposed option can be ruled on, set admissible=false, leave chosenApproach empty, and populate blockingRules with the specific rules that eliminated every option.
- Classify every blocking rule as "constitutive" or "convention".
- CONSTITUTIVE is a real external constraint — an AWS service limit, a security fundamental, a legal or contractual obligation — AND the platform bans this project holds constitutive: no Step Functions, no HTTP API v2 (REST API v1 only), no FastAPI/Flask/Django, Powertools-only Lambdas, service isolation, SSM Parameter Store rather than CloudFormation exports for cross-stack refs, and dot-only event naming.
- CONVENTION is any other rule this project wrote for itself — a naming convention, a curated allowlist, a house pattern, a self-authored MUST in our own SAD.
- A convention MUST NOT be the reason delivery halts. If a convention is the only thing eliminating an otherwise sound design, rule it admissible and record a ruleChallenge against the convention.
- Where a CONVENTION conflicts with industry best practice or an AWS Well-Architected principle, BEST PRACTICE WINS. Record it in ruleChallenges with the change you recommend.
- A CONSTITUTIVE rule is never overridden. Rule on the options that honor it; if you believe the rule itself is wrong, honor it and record a ruleChallenge.
- ruleChallenges go to the human owner; they are never applied by this run.

ACCOUNT FOR EVERY SECURITY AND DATA-ISOLATION FINDING raised in the evidence, item by item: MITIGATED, with the mitigation stated as an entry in imposedConstraints; ACCEPTED RESIDUAL, with the remaining mitigations and the rationale stated as an entry in imposedConstraints; or OUT OF SCOPE, naming the requirement that owns it.

EVERY POINT ENDS RULED, OUT OF SCOPE (naming the requirement that owns it), or BLOCKING (admissible=false). Never write "referred", "to be determined", "pending" or "open question": your ruling is integrated into the architecture, which holds the current design only. A rule challenge goes in ruleChallenges, never into the ruling, the chosen approach or the imposed constraints.`

const decisionPrompt = (brief) => `${rulingsBlock}${DECIDER_CHARTER}

${decisionHeader}

${sadBlock}

${evidenceBlock}${brief}${persistBrief('architecture-decision.md', 'your ruling as ONE markdown document: whether an option is admissible, the ruling, the chosen approach, the imposed constraints, the challenges it resolves, every part of the architecture it relies on with its file and disposition, any blocking rules and rule challenges, and the rationale — the same content as your structured result', { beadKey: 'architecture_decision' })}`
let decision = await run(decisionPrompt(''), { label: 'decide:ruling', effort: 'high', phase: 'Decide', agentType: 'architecture-decider', schema: DECISION_SCHEMA })

const sadParts = String(sadHome || '').split('/').filter(Boolean)
if (sadParts.length && sadParts[sadParts.length - 1].endsWith('.md')) sadParts.pop()
const sadBase = sadParts.length ? sadParts[sadParts.length - 1] : ''
const sadKey = (f) => {
  const p = String(f || '').trim()
  const cut = sadBase ? p.split(`/${sadBase}/`) : [p]
  return cut.length > 1 ? cut.pop() : p
}
const reviewFiles = Array.isArray(a.reviewFiles) ? [...new Set(a.reviewFiles.filter((f) => typeof f === 'string' && f.trim()).map((f) => f.trim()))] : []
const omittedBy = (dec) => {
  const got = new Set(
    (dec && Array.isArray(dec.reliedOn) ? dec.reliedOn : [])
      .filter((x) => x && typeof x === 'object')
      .map((x) => sadKey((typeof x.file === 'string' && x.file) || ''))
  )
  return reviewFiles.filter((f) => !got.has(sadKey(f)))
}
if (decision && decision.admissible === true && omittedBy(decision).length) {
  const omitted = omittedBy(decision)
  log(`Decide: the ruling omitted ${omitted.length} relied-on SAD document(s) the caller named for review; the decider rules again`)
  const again = await run(
    decisionPrompt(`

YOUR PREVIOUS RULING OMITTED RELIED-ON SAD DOCUMENTS. The PRD relies on these documents, which are not effective, and your ruling did not account for them:
${omitted.map((f) => `- ${f}`).join('\n')}
Review each one in full: approve its entries as they stand, or update or replace them in the ruling. Return your COMPLETE ruling again, with every entry of these documents in \`reliedOn\` beside the entries you already relied on.`),
    { label: 'decide:ruling-omitted', effort: 'high', phase: 'Decide', agentType: 'architecture-decider', schema: DECISION_SCHEMA }
  )
  if (again) decision = again
}

if (!decision) {
  return { ok: false, stage: 'decide', error: 'the architecture-decider returned nothing', ...died('Decide'), proposals }
}

const admissible = decision.admissible === true
const stillOmitted = admissible ? omittedBy(decision) : []
if (stillOmitted.length) {
  const why = `the ruling did not review ${stillOmitted.length} relied-on SAD document(s) that are not effective: ${stillOmitted.join(', ')}`
  log(`Decide: ${why}`)
  return { ok: false, stage: 'decide', reason: why, error: why, omittedFiles: stillOmitted, panelDimensions: activeDimensions, proposals, decision }
}
const ruleChallenges = decision.ruleChallenges || []
const decisionName = d.id || d.title
const humanActions = ruleChallenges
  .filter((rc) => rc && typeof rc === 'object')
  .map((rc) => `RULE CHALLENGE from the architecture ruling on ${decisionName}: ${rc.rule} (${rc.source}) — recommended change: ${rc.recommendedChange}. Why: ${rc.rationale}`)

if (!admissible) {
  const blockingText = (decision.blockingRules || []).map((b) => `[${b.classification}] ${b.rule} (${b.source})`).join('; ')
  const why =
    `no admissible option — every option was eliminated by: ${blockingText || '(no blocking rule named)'}.` +
    (ruleChallenges.length ? ` ${ruleChallenges.length} rule challenge(s) are raised for the owner.` : '') +
    ' A person must change the PRD or the blocking rule before this architecture can be ruled.'
  log(`Decide: ${why}`)
  return {
    ok: false,
    stage: 'decide',
    admissible: false,
    deterministicFailure: true,
    reason: why,
    error: why,
    requiredHumanActions: [`ARCHITECTURE BLOCKED for ${decisionName}: ${why}`, ...humanActions],
    blockingRules: decision.blockingRules || [],
    ruleChallenges,
    panelDimensions: activeDimensions,
    proposals,
    decision,
  }
}

phase('Update SAD')

const reliedOn = (Array.isArray(decision.reliedOn) ? decision.reliedOn : [])
  .filter((x) => x && typeof x === 'object')
  .map((x) => ({ ...x, file: typeof x.file === 'string' && x.file.trim().startsWith('/') ? x.file.trim() : '' }))
const approvedFiles = [...new Set(reliedOn.map((x) => x.file).filter(Boolean))]
log(`Decide: the ruling relies on ${reliedOn.length} part(s) of the architecture in ${approvedFiles.length} file(s)`)

const SAD_UPDATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['updatedSections', 'changedFiles', 'approvedFiles', 'summary'],
  properties: {
    updatedSections: { type: 'array', items: { type: 'string' } },
    changedFiles: { type: 'array', items: { type: 'string' } },
    approvedFiles: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    openItems: { type: 'array', items: { type: 'string' } },
    collisions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'where', 'collision'],
        properties: { rule: { type: 'string' }, where: { type: 'string' }, collision: { type: 'string' } },
      },
    },
  },
}

const priorPassRefs = [
  ART ? `the file ${ART.dir}/sad-update.json, when it exists — the report an earlier pass wrote, whose \`changedFiles\` name the views it changed` : '',
  `\`git status --short\` and \`git diff --stat\` in the repository holding ${sadPath}`,
].filter(Boolean)
const PRIOR_PASS_BRIEF = `
AN EARLIER PASS OF THIS SAME RULING MAY ALREADY BE IN THE ARCHITECTURE. Before you write, look for its changes: ${priorPassRefs.join('; ')}.
- A view an earlier pass of this ruling changed or added is this ruling's own draft. Update it in place; do not add a second view or passage for the same element, because two descriptions of one element contradict each other as soon as either changes.
- Content from other rulings is integrated architecture like any other.`

const SAD_SAVE_WHAT = 'your complete structured result (updatedSections, changedFiles, approvedFiles, openItems, summary — exactly as you return them) as ONE JSON object'
const APPROVED_FILES_BRIEF = `
THE RULING RELIES ON THESE ARCHITECTURE FILES; EACH IS APPROVED ONCE THE RULING IS INTEGRATED. Return this list, exactly as written, as \`approvedFiles\`:
${approvedFiles.length ? approvedFiles.map((f) => `- ${f}`).join('\n') : '- (none: return an empty list)'}
Leave the \`lifecycle_state\` frontmatter field of every file as you find it: the run sets it on the files this ruling covers after you return.`
const SAD_SAVE_OPTS = { extraInputs: 'the absolute path of EVERY architecture file changed, created or deleted, each in single quotes' }
const rulingLines = `Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach || '(not stated separately — see the ruling)'}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}
Resolved challenges: ${(decision.resolvedChallenges || []).join('; ') || 'none'}`
const SECTION_2_RULE = `Write nothing under \`02-architecture-constraints/\`: section 2 holds the owner's constraints, and only the owner changes them. A constraint you believe should change goes in \`openItems\`, with the constraint, the conflicting content and the reason.`

let sadUpdate = await run(
  `You are the architecture-maintainer. Integrate the ruling below into the effective architecture at ${sadPath}. For each element the ruling adds, changes or removes, find every view that shows it through the catalog (the \`subject\` and \`shows\` frontmatter of each view), at every scope it appears in, and update or delete each one; where the ruling adds an element no view shows, add a view in the section folder the architecture documentation model names, named for its subject, with its catalog frontmatter. Keep every touched view's \`view_type\`, \`scope\`, \`subject\` and \`shows\` true to what it now shows. Edit in place — no changelog narrative, and no content the ruling supersedes left beside the new.
${SECTION_2_RULE}

READING BUDGET. Open and edit ONLY the views the catalog lists for the elements this ruling changes, and the views that link to them. Do not read the architecture end to end and do not print whole files.

A COLLISION WITH OLDER CONTENT this ruling does not own is reported under \`collisions\`, naming the older content and where it lives — never written into the architecture.

THE ARCHITECTURE HOLDS NO OPEN ITEMS. Never write into it an open question, an unresolved marker, a required action, a rule challenge, a referral, a "pending" or "TBD", or anything addressed to the owner. Everything still open goes in \`openItems\` in your result.

Never label the adopted option with a bare proposal letter; write its descriptive name.
${PRIOR_PASS_BRIEF}
${APPROVED_FILES_BRIEF}

${rulingLines}

Deliver: which sections you changed, the file paths changed, created or deleted, the approved files, and a one-line summary of the change.${persistBrief('sad-update.json', SAD_SAVE_WHAT, SAD_SAVE_OPTS)}`,
  { label: 'architecture:maintain', effort: 'medium', phase: 'Update SAD', agentType: 'architecture-maintainer', schema: SAD_UPDATE_SCHEMA }
)
if (!sadUpdate) {
  sadUpdate = await run(
    `You are the architecture-maintainer, RESUMING an interrupted pass. A previous architecture-maintainer session integrated the ruling below into the effective architecture at ${sadPath} but ended before it returned its result. Its edits are already in the working tree.

Do NOT start over and do NOT re-read the whole architecture. Run \`git status --short\` and \`git diff --stat\` in the repository holding ${sadPath} to see what was changed, open only the changed files you need, finish any view the previous pass left inconsistent with the ruling or with the other views of the same element, and return. No changelog narrative.
${SECTION_2_RULE}
${PRIOR_PASS_BRIEF}
${APPROVED_FILES_BRIEF}

${rulingLines}

Deliver: which sections were changed (by either pass), the file paths changed, created or deleted, the approved files, and a one-line summary of the change.${persistBrief('sad-update.json', SAD_SAVE_WHAT, SAD_SAVE_OPTS)}`,
    { label: 'architecture:maintain-resume', effort: 'medium', phase: 'Update SAD', agentType: 'architecture-maintainer', schema: SAD_UPDATE_SCHEMA }
  )
}

return {
  ok: !!sadUpdate,
  ...(sadUpdate ? {} : { stage: 'update-sad', error: 'the architecture-maintainer returned no result', ...died('Update SAD') }),
  admissible,
  ruleChallenges,
  ...(humanActions.length ? { requiredHumanActions: humanActions } : {}),
  openItems: sadUpdate && Array.isArray(sadUpdate.openItems) ? sadUpdate.openItems : [],
  decisionRef: d.id || null,
  panelDimensions: activeDimensions,
  proposals,
  tradeoffs: proposals.map((p) => ({ lens: p.lens, recommendation: p.recommendation, options: p.options })),
  contextMap,
  failureModes,
  decision,
  decisionPath: ART ? `${ART.dir}/architecture-decision.md` : null,
  sadUpdate,
  reliedOn,
  approvedFiles,
}
