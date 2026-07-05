export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + expected-behavior contract' }],
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
- blastRadius: the callers, flows, and services impacted if the bug ships or the fix regresses.`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['reproduction', 'rootCause', 'affectedFiles', 'blastRadius'],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
      },
    },
  }
)

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
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  acceptanceCriteria: contract.acceptanceCriteria,
}
