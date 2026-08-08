export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Also SIZES the bug: a defect whose honest fix is a redesign is escalated as needing a PRD and Epic rather than being squeezed through the fix path, because a bug ticket is not a licence to rebuild a subsystem unreviewed. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + scope sizing + expected-behavior contract' }],
}

// args: { bead: { id, title, description, repoPath } }
const bead = ((typeof args === 'string' ? JSON.parse(args) : args) || {}).bead || {}
const repo = bead.repoPath || '(repo path not provided — ask before editing files)'

phase('Triage')

// 1) Diagnosis — read-only analyst. Separation of duties: this agent does not fix.
const analysis = await agent(
  `Diagnose this bug. You are READ-ONLY — do not change code. Work within the repository at: ${repo}

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Deliver:
- reproduction: the minimal, concrete steps/conditions that trigger the defect.
- rootCause: the precise mechanism and code location (file:line where possible).
- affectedFiles: the files that must change to fix it (paths).
- blastRadius: the callers, flows, and services impacted if the bug ships or the fix regresses.
- surfaces: which surfaces from the CLOSED SET below the fix actually touches. This decides which specialist test writers run downstream, so it is a real decision, not a label:
    api-contract           a published REST/GraphQL/event schema that consumers depend on
    event-chain            the event API -> EventBridge -> SQS -> Lambda delivery path
    auth                   authentication, authorization, or permission evaluation
    performance            a stated performance budget or latency/throughput requirement
    web-ui                 web user interface
    ios                    native iOS
    android                native Android
    cross-platform-mobile  React Native or other cross-platform mobile
    ml                     matching, recommendation, ranking, or embeddings
    data-pipeline          ETL, CDC, or stream processing
  Return ONLY surfaces the CHANGE touches — not surfaces the surrounding code happens to sit near. Return an empty list when the fix is confined to internal logic, which is the common case. Each surface you name costs a full additional test-authoring agent; each one you omit leaves that surface with no specialist coverage.`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['reproduction', 'rootCause', 'affectedFiles', 'blastRadius', 'surfaces'],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
        surfaces: {
          type: 'array',
          items: {
            type: 'string',
            enum: [
              'api-contract',
              'event-chain',
              'auth',
              'performance',
              'web-ui',
              'ios',
              'android',
              'cross-platform-mobile',
              'ml',
              'data-pipeline',
            ],
          },
        },
      },
    },
  }
)

// 1b) SIZING — is this a fix, or a redesign wearing a bug ticket?
//
// A bug can be worked directly, or it can turn out to need a PRD and an Epic. The
// difference matters: the fix path has no PRD validation, no architecture ruling,
// and no spec — so a defect whose honest remedy is "redesign how this service
// stores its data" would get that redesign built by an implementer, unreviewed,
// on the authority of a bug ticket. That is how an architecture decision gets made
// by accident, which is the failure this workforce exists to prevent.
//
// A DIFFERENT agent sizes it — the diagnostician has just invested in a root cause
// and is the worst-placed judge of whether fixing it is too big.
const sizing = await agent(
  `Size this bug. It has been diagnosed; decide whether its honest remedy is a FIX or a REDESIGN. You are READ-ONLY and you are NOT proposing the remedy — only sizing it.

Answer "needs-prd" when the honest fix would: change a public contract or event schema, alter the data model, cross a service boundary, require an architecture decision that no ADR covers, or amount to rebuilding a component rather than correcting it.

Answer "fix" when the defect is a mistake in existing behavior that can be corrected within the current design — the common case. Do not inflate a real bug into a project; most bugs are bugs.

The cost of each error is not symmetric. Calling a redesign a "fix" ships an unreviewed architecture change on a bug ticket. Calling a fix a "redesign" costs a PRD nobody needed. Prefer "fix" when genuinely balanced, and "needs-prd" when the remedy touches a contract, a schema, or a boundary.

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Root cause found: ${analysis.rootCause}
Files that must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}
Blast radius: ${analysis.blastRadius}`,
  {
    label: 'triage:sizing',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:architecture-boundary-guardian',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['scope', 'rationale'],
      properties: {
        scope: { type: 'string', enum: ['fix', 'needs-prd'] },
        rationale: { type: 'string' },
        contractsTouched: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// A missing verdict must not silently become "fix" — that is the expensive error.
const scope = (sizing && sizing.scope) || 'needs-prd'
const scopeRationale = (sizing && sizing.rationale) || 'sizing returned no verdict — defaulting to needs-prd rather than assuming a fix is safe'
if (scope === 'needs-prd') {
  log(`Bug ${bead.id || ''} sized as NEEDS-PRD: ${scopeRationale}`)
  return {
    bead,
    repoPath: bead.repoPath || null,
    scope,
    scopeRationale,
    contractsTouched: (sizing && sizing.contractsTouched) || [],
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    affectedFiles: analysis.affectedFiles,
    blastRadius: analysis.blastRadius,
    acceptanceCriteria: [],
    note:
      'This defect needs a PRD and an Epic, not a fix. Its honest remedy changes a contract, ' +
      'schema, or boundary, and the fix path has no PRD validation, no architecture ruling, and ' +
      'no spec to review it against. Promote it: /agent-teams-workforce:start-prd, or dispatch ' +
      'prd-to-spec with { request } built from the diagnosis above. Promotion is a human decision.',
  }
}

// 2) Expected-behavior contract — the "spec-lite" a bug lacks, as testable AC.
//    A different agent than the diagnostician (no self-authoring of its own contract).
const contract = await agent(
  `Write the expected-behavior contract for this bug fix as testable given/when/then acceptance criteria — the correct behavior the fix must satisfy and that a failing test will encode. Do NOT write code.

Bug ${bead.id || ''}: ${bead.title || ''}
Root cause: ${analysis.rootCause}
Reproduction: ${analysis.reproduction}`,
  {
    label: 'triage:expected-behavior',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:acceptance-criteria-writer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['acceptanceCriteria'],
      properties: {
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

return {
  bead,
  repoPath: bead.repoPath || null,
  scope,
  scopeRationale,
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  // Consumed by tdd-red to DERIVE its test writers. Empty means unit tests only,
  // which is the correct answer for a fix confined to internal logic.
  surfaces: analysis.surfaces || [],
  acceptanceCriteria: contract.acceptanceCriteria,
}
