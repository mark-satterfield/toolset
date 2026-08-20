export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus an arc42 SAD extract. A read-only extractor pulls the SAD source feeds (constraints, solution strategy, crosscutting) into a typed packet; the trd-author writes the TRD; two independent checkers (structure/quality + bidirectional PRD<->TRD traceability) judge it. Maker never judges its own work; on a bounded maker-checker deadlock the trd-decider rules. Read/author only — no production code.',
  phases: [
    { title: 'Extract SAD', detail: 'read-only extraction of the arc42 source feeds into a typed packet' },
    { title: 'Author TRD', detail: 'author the TRD from the PRD + SAD extract (maker)' },
    { title: 'Verify & Traceability', detail: 'independent validation + PRD<->TRD traceability; decider on deadlock' },
  ],
}

// args: {
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },  // the source PRD
//   sad: { path?, sectionLayout?: 'single-file' | 'one-file-per-section' }, // arc42 SAD location
//   trdPath?: string,        // where the TRD should be written/lives
//   repoPath?: string,       // working repo for file reads/writes
//   maxLoops?: number,       // bounded maker-checker passes (default 2)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const prd = a.prd || {}
const sad = a.sad || {}
const repo = a.repoPath || '(repo path not provided — ask before editing files)'
const trdPath = a.trdPath || '(TRD path not provided)'
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2

if (!prd.id && !prd.path && !prd.content) {
  return { ok: false, stage: 'input', error: 'no PRD supplied (id/path/content all empty) — refusing to run without a work item' }
}

const prdRef = prd.path || prd.id || '(inline content)'
const sadRef = sad.path || '(SAD path not provided — ask before extracting)'
const sadLayout = sad.sectionLayout || 'unknown (detect single-file vs one-file-per-section)'

// ── Phase 1: Extract SAD ──────────────────────────────────────────────────────
// Read-only extraction of the four arc42 source sections into a stably-identified
// packet. The extractor authors no TRD content — it only normalizes what the SAD
// states. Invents nothing the SAD does not contain.
phase('Extract SAD')
log(`Extracting arc42 source feeds from SAD at ${sadRef}`)

const sadExtract = await agent(
  `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for the TRD author. Do NOT author requirements, do NOT change any file, and invent NOTHING the SAD does not state. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

Locate and normalize each source feed reliably across both single-file and one-file-per-section arc42 layouts:
- Section 2 — Constraints
- Section 4 — Solution Strategy
- Section 8 — Crosscutting Concepts

For every entry: assign a stable ID, capture the verbatim-grounded statement, and note its source location (file:section/anchor). If a section is absent, return it as an empty array — do not fabricate.`,
  {
    label: 'extract:sad',
    phase: 'Extract SAD',
    agentType: 'agent-teams-workforce:sad-source-extractor',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['constraints', 'solutionStrategy', 'crosscuttingConcepts'],
      properties: {
        constraints: { $ref: '#/$defs/feed' },
        solutionStrategy: { $ref: '#/$defs/feed' },
        crosscuttingConcepts: { $ref: '#/$defs/feed' },
        sadLocation: { type: 'string' },
        notes: { type: 'string' },
      },
      $defs: {
        feed: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'statement', 'source'],
            properties: {
              id: { type: 'string' },
              statement: { type: 'string' },
              source: { type: 'string' },
            },
          },
        },
      },
    },
  }
)
if (!sadExtract) return { ok: false, stage: 'extract', reason: 'SAD extraction produced nothing' }

const extractText = JSON.stringify(sadExtract, null, 2)
const prdText = prd.content
  ? prd.content
  : `PRD ${prd.id || ''}: ${prd.title || ''} (path: ${prd.path || 'n/a'})`

// ── Phases 2 + 3: bounded maker-checker loop ──────────────────────────────────
// The maker (trd-author) writes the TRD; two INDEPENDENT checkers judge it. Neither
// checker ever authored the TRD. On rejection the maker re-runs with the combined
// checker feedback. The script owns this loop in plain JS — no workflow() calls.
let trd = null
let trdValidation = null
let traceabilityMatrix = null
let decision = null
let feedback = ''

for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
  // ── Phase 2: Author TRD (maker) ──────────────────────────────────────────────
  phase('Author TRD')
  log(`Authoring TRD (attempt ${attempt}/${MAX_LOOPS}) at ${trdPath}`)

  trd = await agent(
    `Author the Technical Requirements Document (TRD). The TRD translates the PRD's product requirements into testable technical requirements, grounded in and consistent with the SAD extract below. Write the TRD; do not write production code. Work within the repository at: ${repo}

Target TRD path: ${trdPath}

PRD (source of product requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

SAD extract (architecture constraints/strategy/crosscutting the TRD must honor; cite by stable ID):
${extractText}
${feedback ? `\nChecker feedback from the previous attempt — address every point:\n${feedback}` : ''}

Each technical requirement must have a stable ID, trace upward to a PRD requirement, cite any SAD source IDs it depends on, and be verifiable. Deliver the TRD file path(s) you wrote, the structured requirements, and the upstream PRD/SAD references each requirement carries.`,
    {
      label: 'author:trd',
      phase: 'Author TRD',
      agentType: 'agent-teams-workforce:trd-author',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['trdPath', 'requirements'],
        properties: {
          trdPath: { type: 'string' },
          requirements: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['id', 'requirement', 'prdRefs', 'sadRefs', 'verification'],
              properties: {
                id: { type: 'string' },
                requirement: { type: 'string' },
                prdRefs: { type: 'array', items: { type: 'string' } },
                sadRefs: { type: 'array', items: { type: 'string' } },
                verification: { type: 'string' },
              },
            },
          },
          summary: { type: 'string' },
          notes: { type: 'string' },
        },
      },
    }
  )
  if (!trd) return { ok: false, stage: 'author', reason: 'TRD authoring produced nothing', sadExtract }

  const trdText = JSON.stringify(trd, null, 2)

  // ── Phase 3: Verify & Traceability (independent checkers, run in parallel) ───
  phase('Verify & Traceability')

  const [validation, traceability] = await parallel([
    () =>
      agent(
        `You are an INDEPENDENT validator. You did NOT author this TRD; you only judge it. Do not modify it. Validate the TRD's structure and quality: required sections present, every requirement has a stable ID and a concrete verification method, requirements are unambiguous and testable, and the TRD is internally consistent with the SAD extract it cites.

TRD under review:
${trdText}

SAD extract the TRD must stay consistent with:
${extractText}

Return verdict "pass" only if every check holds. Otherwise "reject" with feedback specific enough that the author can fix it without interpretation. List each finding with its severity.`,
        {
          label: 'verify:trd-validation',
          phase: 'Verify & Traceability',
          agentType: 'agent-teams-workforce:trd-validator',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'findings', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              findings: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['issue', 'severity'],
                  properties: {
                    issue: { type: 'string' },
                    severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
                    location: { type: 'string' },
                  },
                },
              },
              feedback: { type: 'string' },
            },
          },
        }
      ),
    () =>
      agent(
        `You are an INDEPENDENT traceability verifier. You did NOT author this TRD. Verify BIDIRECTIONAL PRD<->TRD traceability: every PRD requirement maps forward to at least one TRD requirement (no coverage gaps), and every TRD requirement maps back to a PRD requirement (no orphans). Build the traceability matrix and report gaps in both directions.

PRD (source requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

TRD under review:
${trdText}

Return verdict "pass" only if traceability is complete in BOTH directions with no unexplained gaps or orphans.`,
        {
          label: 'verify:traceability',
          phase: 'Verify & Traceability',
          agentType: 'agent-teams-workforce:prd-trd-traceability-verifier',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'links', 'prdGaps', 'trdOrphans', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              links: {
                type: 'array',
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['prdRef', 'trdRef'],
                  properties: {
                    prdRef: { type: 'string' },
                    trdRef: { type: 'string' },
                  },
                },
              },
              prdGaps: { type: 'array', items: { type: 'string' } },
              trdOrphans: { type: 'array', items: { type: 'string' } },
              feedback: { type: 'string' },
            },
          },
        }
      ),
  ])

  trdValidation = validation
  traceabilityMatrix = traceability

  const validationPass = validation && validation.verdict === 'pass'
  const traceabilityPass = traceability && traceability.verdict === 'pass'

  if (validationPass && traceabilityPass) {
    log(`TRD accepted on attempt ${attempt}: validation PASS, traceability PASS`)
    decision = { verdict: 'pass', ruledByDecider: false, rationale: 'Both independent checkers passed.' }
    break
  }

  // Combine the rejecting checkers' feedback for the next maker pass.
  const parts = []
  if (!validationPass) parts.push(`[Structure/quality] ${(validation && validation.feedback) || 'rejected (no feedback)'}`)
  if (!traceabilityPass) parts.push(`[Traceability] ${(traceability && traceability.feedback) || 'rejected (no feedback)'}`)
  feedback = parts.join('\n\n')
  log(`TRD rejected on attempt ${attempt}/${MAX_LOOPS}: ${parts.join(' | ')}`)

  // On deadlock (final pass exhausted while still rejected), the trd-decider rules.
  // The decider only rules — it never authored or analyzed the TRD itself.
  if (attempt === MAX_LOOPS) {
    log('Maker-checker loop exhausted — escalating to trd-decider for a binding ruling')
    const ruling = await agent(
      `The TRD author and the independent checkers reached a deadlock across the bounded retry loop. You ONLY rule — you did not author the TRD and you do not re-analyze it from scratch. Decide whether the TRD ships as-is, returns to the author for a final targeted change, or is rejected, and state the binding rationale.

TRD:
${JSON.stringify(trd, null, 2)}

Structure/quality verdict: ${(trdValidation && trdValidation.verdict) || 'n/a'}
Structure/quality feedback: ${(trdValidation && trdValidation.feedback) || 'n/a'}

Traceability verdict: ${(traceabilityMatrix && traceabilityMatrix.verdict) || 'n/a'}
Traceability feedback: ${(traceabilityMatrix && traceabilityMatrix.feedback) || 'n/a'}`,
      {
        label: 'decide:trd',
        phase: 'Verify & Traceability',
        agentType: 'agent-teams-workforce:trd-decider',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['verdict', 'rationale'],
          properties: {
            verdict: { type: 'string', enum: ['accept', 'reject', 'revise'] },
            rationale: { type: 'string' },
            requiredChanges: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    decision = ruling
      ? { verdict: ruling.verdict, ruledByDecider: true, rationale: ruling.rationale, requiredChanges: ruling.requiredChanges || [] }
      : { verdict: 'reject', ruledByDecider: true, rationale: 'trd-decider returned no ruling.' }
  }
}

const accepted = decision && (decision.verdict === 'pass' || decision.verdict === 'accept')

return {
  ok: !!accepted,
  trdPath: (trd && trd.trdPath) || trdPath,
  sadExtract,
  trd,
  trdValidation,
  traceabilityMatrix,
  decision,
}
