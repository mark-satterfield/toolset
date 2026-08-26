export const meta = {
  name: 'tdd-green',
  description:
    'Shared-tail mini — TDD Green. A read-only implementation-lead selects the implementer(s) matching the affected subsystem (unless the caller pre-specifies one); the selected implementers write the minimum production code in sequence to make the failing test pass, run the suite, and confirm Green without regressing other tests.',
  phases: [{ title: 'Green', detail: 'minimum code to pass; confirm Green' }],
}

// The implementer roster this mini may dispatch. Every name the lead returns is
// filtered against this list before it becomes an agentType — an unfiltered name
// would dispatch a nonexistent agent type in the phase that writes production
// code. Mirrors OPTIMIZER_ROSTER in tdd-refactor.js.
const IMPLEMENTER_ROSTER = [
  'chassis-extension-implementer',
  'power-tools-configuration-implementer',
  'api-gateway-cdk-implementer',
  'event-api-client-implementer',
  'event-driven-consumer-implementer',
  'dynamodb-access-layer-implementer',
  'cognito-lambda-trigger-implementer',
  'webauthn-implementer',
  'payments-integration-implementer',
  'email-notification-implementer',
  'mcp-server-implementer',
  'bedrock-integration-implementer',
  'matching-algorithm-implementer',
  'recommendation-engine-implementer',
  'vector-search-embeddings-implementer',
  'behavioral-signals-implementer',
  'llm-observability-implementer',
  'nextjs-component-implementer',
  'appsync-client-subscription-implementer',
  'ios-swiftui-implementer',
  'android-compose-implementer',
  'react-native-implementer',
  'appsync-cdk-implementer',
  'glue-etl-implementer',
  'kinesis-stream-implementer',
  'dynamodb-streams-cdc-implementer',
  's3-data-lake-implementer',
  'athena-redshift-analytics-implementer',
  // Selected by the infra path, which pre-specifies args.implementer.
  'cdk-stack-author',
]

// args: { contract, red, implementer?, feedback? }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const red = a.red || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'

// The task context every implementer receives.
const taskBlock = `${c.bead ? `Bug ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature implementation'}
Root cause: ${c.rootCause || 'n/a'}
Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}
Failing test(s) to satisfy: ${(red.testFiles || []).join(', ') || 'n/a'}
Red evidence: ${red.evidence || 'n/a'}`

phase('Green')

// implementation-lead SELECTS the implementer(s) whose specialty matches the affected
// subsystem — a READ-ONLY router that writes no code. A caller may pre-specify
// args.implementer to skip selection (e.g. the infra path fixes 'cdk-stack-author').
let implementers
let selectionMode
if (a.implementer) {
  if (!IMPLEMENTER_ROSTER.includes(a.implementer)) {
    throw new Error(
      `tdd-green: caller pre-specified implementer '${a.implementer}', which is not on the implementer roster. ` +
        `Dispatching it would resolve to a nonexistent agent type. Roster: ${IMPLEMENTER_ROSTER.join(', ')}`
    )
  }
  implementers = [a.implementer]
  selectionMode = 'selected'
} else {
  const selection = await agent(
    `You are the implementation-lead — a READ-ONLY router. Do NOT write code. Select the FEWEST implementer agent(s) whose specialty covers this change, drawn ONLY from the SkillSpoke implementer roster: ${IMPLEMENTER_ROSTER.join(', ')}. Any name outside this list is discarded. A standard Python-Lambda service change is chassis-extension-implementer alone. Order them so earlier ones lay groundwork for later ones. Enforce the hard architectural constraints (event API only, service isolation, chassis extension) in your rationale.

Work within the repository at: ${repo}

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}`,
    {
      label: 'green:select-implementers',
      phase: 'Green',
      agentType: 'agent-teams-workforce:implementation-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['implementers', 'rationale'],
        properties: {
          implementers: { type: 'array', items: { type: 'string' } },
          rationale: { type: 'string' },
        },
      },
    }
  )
  const picked =
    selection && Array.isArray(selection.implementers)
      ? selection.implementers.filter((i) => IMPLEMENTER_ROSTER.includes(i))
      : []
  implementers = picked.length ? picked : ['chassis-extension-implementer']
  selectionMode = picked.length ? 'selected' : 'default'
}

const GREEN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'greenConfirmed', 'evidence'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    greenConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    notes: { type: 'string' },
  },
}

// Run the selected implementer(s) in sequence — each builds on the prior's changes so
// they never edit the same files concurrently. The final pass confirms the suite is Green.
let green = null
const changedFiles = []
for (const impl of implementers) {
  green = await agent(
    `Make the failing test pass with the MINIMUM production change. Then run the test suite and confirm the target test passes (Green) and nothing else regressed. Work within the repository at: ${repo}

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

${taskBlock}${implementers.length > 1 ? `\n\nYou are '${impl}', one of ${implementers.length} implementers on this task — make only the part matching your specialty; prior implementers' changes are already applied.` : ''}
${a.feedback ? `\nGate feedback from the previous attempt — address it:\n${a.feedback}` : ''}

Constraints: minimum change to pass; do not modify the test to make it pass; honor SkillSpoke code-quality rules (timeouts, backoff, idempotency, explicit error handling). Deliver the changed files, whether Green is confirmed, and the captured passing output.`,
    {
      label: `green:${impl}`,
      phase: 'Green',
      agentType: `agent-teams-workforce:${impl}`,
      schema: GREEN_SCHEMA,
    }
  )
  if (green && Array.isArray(green.changedFiles)) changedFiles.push(...green.changedFiles)
}

// Decision ledger — what this phase actually did, for over-time mining.
// mode 'selected' = implementation-lead (or the caller) chose the implementer(s);
// mode 'default'  = selection produced nothing and the mini fell back to the chassis default.
const ledger = {
  phase: 'green',
  beadId: (c.bead && c.bead.id) || null,
  chosen: implementers,
  mode: selectionMode,
  ok: !!(green && green.greenConfirmed),
}

return { ...(green || {}), changedFiles, ledger }
