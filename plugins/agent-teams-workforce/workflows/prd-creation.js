export const meta = {
  name: 'prd-creation',
  description:
    'Leaf mini — turns a raw stakeholder request into a template-conformant PRD paired with its Epic. Intake captures the request, then the persona and OKRs are authored in parallel, then the PRD is drafted (WHAT-not-HOW) and independently checked for alignment with the intake brief, persona, and OKRs. A PRD and its Epic are created at the same time, so the mini emits exactly one Epic per PRD: a container bead spec derived from the PRD itself in the same authoring pass — no acceptance criteria, no repo scope (one Epic may span repos) — which the caller writes with bd. Maker, checker, and decider are distinct agents; the maker is re-run with checker feedback on reject (bounded 2 passes) and a spec-decider rules on deadlock. Authors no judgment of its own work.',
  phases: [
    { title: 'Intake', detail: 'scope the request + capture a structured intake brief' },
    { title: 'Persona & OKR', detail: 'author the target persona and the OKRs in parallel' },
    { title: 'PRD Draft', detail: 'draft the PRD + independent alignment check (bounded loop)' },
  ],
}

// args: {
//   request: { id?, title?, description?, repoPath?, requestedBy? },  // raw stakeholder request
//   maxPasses?: number,   // bounded maker-checker passes for the PRD draft (default 2)
// }
// returns: {
//   ok, request, intakeBrief, persona, okrs, prd, alignmentVerdict, scope, decision, note,
//   epic: {                    // the Epic created together with the PRD — the caller writes it with bd
//     key:         'E1',       // stable local key; downstream parent links reference it
//     type:        'epic',     // literal — the bead face of the PRD; a container, never worked and never itself decomposed
//     title:       string,     // the PRD's title
//     description: string,     // one-paragraph scope statement derived from the PRD
//     prdRef:      string,     // the PRD's id (falls back to its title) — the pairing is the point
//   },
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const request = a.request || {}
const MAX_PASSES = a.maxPasses || 2
const repo = request.repoPath || '(repo path not provided — this is a docs/vault artifact)'
if (!request.title && !request.description) {
  return { ok: false, stage: 'input', error: 'no request.title/description supplied — refusing to run without a work item' }
}

const requestText = [
  request.id ? `Request ${request.id}` : null,
  request.title ? `Title: ${request.title}` : null,
  request.requestedBy ? `Requested by: ${request.requestedBy}` : null,
  request.description ? `Description:\n${request.description}` : null,
]
  .filter(Boolean)
  .join('\n') || '(no raw request text provided)'

// ── Intake ──────────────────────────────────────────────────────────────────
phase('Intake')

// Read-only router: scopes the effort and routes to the makers. Authors no content.
const scope = await agent(
  `You are the prd-creation-lead — a READ-ONLY router. Do NOT author PRD content, persona content, or OKRs. Read the raw stakeholder request below, scope the PRD effort, and route it to the maker agents.

Raw stakeholder request:
${requestText}

Working repository context: ${repo}

Deliver:
- scopeSummary: a one-paragraph framing of what this PRD must cover.
- inScope: the concerns this PRD owns (array).
- outOfScope: the concerns explicitly excluded (array).
- openQuestions: ambiguities the makers must resolve or flag (array).`,
  {
    label: 'intake:scope',
    phase: 'Intake',
    agentType: 'agent-teams-workforce:prd-creation-lead',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['scopeSummary', 'inScope', 'outOfScope', 'openQuestions'],
      properties: {
        scopeSummary: { type: 'string' },
        inScope: { type: 'array', items: { type: 'string' } },
        outOfScope: { type: 'array', items: { type: 'string' } },
        openQuestions: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// Maker: capture the raw request into a structured intake brief.
const intakeBrief = await agent(
  `Capture the raw stakeholder request into a structured intake brief. State the problem, the audience, and the desired outcome plainly — WHAT the job seeker needs, not HOW to build it. Do NOT write the PRD itself.

Raw stakeholder request:
${requestText}

Scope from the lead:
- Summary: ${scope.scopeSummary}
- In scope: ${(scope.inScope || []).join('; ') || 'n/a'}
- Out of scope: ${(scope.outOfScope || []).join('; ') || 'n/a'}
- Open questions: ${(scope.openQuestions || []).join('; ') || 'none'}

Deliver:
- problem: the job-seeker problem this addresses.
- audience: who is affected (the job-seeker segment).
- desiredOutcome: the outcome the feature must produce for that audience.
- constraints: known constraints or non-negotiables (array).
- openQuestions: unresolved ambiguities to carry forward (array).`,
  {
    label: 'intake:brief',
    phase: 'Intake',
    agentType: 'agent-teams-workforce:stakeholder-request-intake-writer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['problem', 'audience', 'desiredOutcome', 'constraints', 'openQuestions'],
      properties: {
        problem: { type: 'string' },
        audience: { type: 'string' },
        desiredOutcome: { type: 'string' },
        constraints: { type: 'array', items: { type: 'string' } },
        openQuestions: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// ── Persona & OKR (parallel makers) ───────────────────────────────────────────
phase('Persona & OKR')

const briefBlock = `Problem: ${intakeBrief.problem}
Audience: ${intakeBrief.audience}
Desired outcome: ${intakeBrief.desiredOutcome}
Constraints: ${(intakeBrief.constraints || []).join('; ') || 'none'}`

const [persona, okrs] = await parallel([
  () =>
    agent(
      `Author the target job-seeker persona this PRD serves. SkillSpoke serves the job seeker — the persona is a job seeker, never a recruiter. Ground the persona in the intake brief.

Intake brief:
${briefBlock}

Deliver:
- name: a short persona label.
- summary: a one-paragraph portrait of this job seeker.
- goals: what they are trying to achieve (array).
- frustrations: the pain points the feature must relieve (array).
- context: their situation/environment relevant to this feature.`,
      {
        label: 'persona:author',
        phase: 'Persona & OKR',
        agentType: 'agent-teams-workforce:persona-profile-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['name', 'summary', 'goals', 'frustrations', 'context'],
          properties: {
            name: { type: 'string' },
            summary: { type: 'string' },
            goals: { type: 'array', items: { type: 'string' } },
            frustrations: { type: 'array', items: { type: 'string' } },
            context: { type: 'string' },
          },
        },
      }
    ),
  () =>
    agent(
      `Author the objective and key results this feature must move. The objective is a qualitative, job-seeker-centered statement; each key result is a measurable signal that proves the objective was met. Ground them in the intake brief.

Intake brief:
${briefBlock}

Deliver:
- objective: the single qualitative objective this feature serves.
- keyResults: measurable results, each with a metric and a target (array).`,
      {
        label: 'okr:author',
        phase: 'Persona & OKR',
        agentType: 'agent-teams-workforce:okr-writer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['objective', 'keyResults'],
          properties: {
            objective: { type: 'string' },
            keyResults: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['metric', 'target'],
                properties: {
                  metric: { type: 'string' },
                  target: { type: 'string' },
                },
              },
            },
          },
        },
      }
    ),
])

// ── PRD Draft (maker-checker, bounded loop) ───────────────────────────────────
phase('PRD Draft')

const personaBlock = `Persona: ${persona.name} — ${persona.summary}
Goals: ${(persona.goals || []).join('; ') || 'n/a'}
Frustrations: ${(persona.frustrations || []).join('; ') || 'n/a'}`

const okrBlock = `Objective: ${okrs.objective}
Key results: ${(okrs.keyResults || [])
  .map((k) => `${k.metric} → ${k.target}`)
  .join('; ') || 'n/a'}`

// Maker: prd-writer authors the template-conformant PRD and, in the same pass,
// the one-paragraph scope statement for the Epic that is created alongside it.
// Authoring both together keeps the pairing literal and the Epic in sync when
// the draft loops on checker feedback — no separate analysis pass is needed,
// because the PRD already contains the scope.
async function draftPRD(feedback) {
  return agent(
    `Author the template-conformant Product Requirements Document (PRD) from the inputs below. Stay WHAT-not-HOW — describe the required behavior and outcomes, never the implementation. Follow the standard PRD template: required sections, P0 acceptance criteria, no leftover scaffolding.

Intake brief:
${briefBlock}
Open questions to resolve or flag: ${(intakeBrief.openQuestions || []).join('; ') || 'none'}

${personaBlock}

${okrBlock}

Deliver:
- title: the PRD title.
- prd: the full PRD body in Markdown, template-conformant.
- sections: the section headings present (array), to confirm template coverage.
- acceptanceCriteria: P0 acceptance criteria as given/when/then (array).
- epicScope: a one-paragraph scope statement for the Epic that pairs with this PRD — a container-level summary of the scope the PRD owns, with no acceptance criteria and no repository specifics (one Epic may span repos).${
      feedback
        ? `\n\nALIGNMENT FEEDBACK from the independent checker — address every point before resubmitting:\n${feedback}`
        : ''
    }`,
    {
      label: 'prd:draft',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:prd-writer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'prd', 'sections', 'acceptanceCriteria', 'epicScope'],
        properties: {
          title: { type: 'string' },
          prd: { type: 'string' },
          sections: { type: 'array', items: { type: 'string' } },
          epicScope: { type: 'string' },
          acceptanceCriteria: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['given', 'when', 'then'],
              properties: {
                given: { type: 'string' },
                when: { type: 'string' },
                then: { type: 'string' },
              },
            },
          },
        },
      },
    }
  )
}

// Checker: an INDEPENDENT verifier — never the prd-writer.
async function verifyAlignment(prd) {
  return agent(
    `You are an INDEPENDENT alignment verifier. You did NOT write this PRD — you only judge it. Do NOT rewrite the PRD. Verify the drafted PRD aligns with the intake brief, the persona, and the OKRs, and that it is template-conformant and WHAT-not-HOW.

Intake brief:
${briefBlock}

${personaBlock}

${okrBlock}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "aligned": the PRD covers the intake problem/outcome, serves the named persona, and its acceptance criteria trace to the OKRs.
- "misaligned": one or more of those hold false. Return feedback specific enough that the prd-writer can fix it without interpretation.

For each dimension (intake, persona, okr, template), state whether it is satisfied with evidence.`,
    {
      label: 'prd:alignment-check',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:prd-alignment-verifier',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'dimensions', 'feedback'],
        properties: {
          verdict: { type: 'string', enum: ['aligned', 'misaligned'] },
          dimensions: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['dimension', 'satisfied', 'evidence'],
              properties: {
                dimension: { type: 'string', enum: ['intake', 'persona', 'okr', 'template'] },
                satisfied: { type: 'boolean' },
                evidence: { type: 'string' },
              },
            },
          },
          feedback: { type: 'string' },
        },
      },
    }
  )
}

let prd = null
let alignmentVerdict = null
let feedback = ''
let deadlocked = false
for (let pass = 1; pass <= MAX_PASSES; pass++) {
  prd = await draftPRD(feedback)
  alignmentVerdict = await verifyAlignment(prd)
  if (!alignmentVerdict) {
    return { ok: false, stage: 'prd-draft', reason: 'alignment check returned no verdict', prd }
  }
  if (alignmentVerdict.verdict === 'aligned') {
    log(`PRD draft: ALIGNED on pass ${pass}/${MAX_PASSES}`)
    break
  }
  log(`PRD draft: MISALIGNED pass ${pass}/${MAX_PASSES} — ${alignmentVerdict.feedback}`)
  feedback = alignmentVerdict.feedback || ''
  if (pass === MAX_PASSES) deadlocked = true
}

// Deadlock: the maker and checker could not converge — the spec-decider rules.
let decision = null
if (deadlocked) {
  log('PRD draft: maker-checker deadlock — escalating to spec-decider for a binding ruling')
  decision = await agent(
    `The prd-writer and the independent prd-alignment-verifier could not converge after ${MAX_PASSES} passes. Rule on the standoff. Your ruling is binding.

Latest checker feedback: ${alignmentVerdict.feedback || '(none)'}

PRD under review (title: ${prd.title}):
${prd.prd}

Decide exactly one verdict:
- "accept": the PRD is acceptable as-is despite the checker's objection — explain why the objection does not block.
- "reject": the PRD must not proceed — state the blocking gap the next attempt must close.`,
    {
      label: 'prd:deadlock-ruling',
      phase: 'PRD Draft',
      agentType: 'agent-teams-workforce:spec-decider',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'rationale'],
        properties: {
          verdict: { type: 'string', enum: ['accept', 'reject'] },
          rationale: { type: 'string' },
        },
      },
    }
  )
}

const aligned = alignmentVerdict && alignmentVerdict.verdict === 'aligned'
const ruledAccept = decision && decision.verdict === 'accept'
const ok = Boolean(aligned || ruledAccept)

// A PRD and its Epic are created at the same time — the Epic is the bead-side
// half of that pairing, assembled here from the maker's own output rather than
// a fresh analysis pass. It is a CONTAINER: no acceptance criteria and no repo
// scope, because one Epic may span repos and its Stories (one per repo) are
// minted later, each alongside its Spec. Exactly one epic is emitted per PRD;
// this mini never writes to .beads — the caller writes the bead with bd.
const epic = prd
  ? {
      key: 'E1',
      type: 'epic',
      title: prd.title,
      description: prd.epicScope,
      // Inside this mini the PRD has no bead id or file path yet, so the ref is
      // the originating request id when supplied, else the PRD's own title.
      prdRef: request.id || prd.title,
    }
  : null

return {
  ok,
  request: request.id ? request.id : null,
  intakeBrief,
  persona,
  okrs,
  prd,
  epic,
  alignmentVerdict,
  scope,
  decision,
  note: ok
    ? 'PRD is intake/persona/OKR-aligned and template-conformant.'
    : 'PRD did not reach alignment within the bounded passes; see decision for the binding ruling.',
}
