export const meta = {
  name: 'documentation',
  description:
    'Cross-cutting mini — Documentation. Runs alongside the build (not as a phase): audits whether the change leaves docs stale, then a READ-ONLY documentation-lead routes each stale doc to the matching writer (API, README, changelog, user-guide), the writers author in parallel, and an INDEPENDENT accuracy reviewer checks the result against shipped behavior. Its currency result feeds the deployment readiness review. Code is not done until its documentation is current.',
  phases: [{ title: 'Documentation', detail: 'currency audit + routed writes + accuracy review' }],
}

// args: { contract, green }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const changeLabel = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const changedFiles = (green.changedFiles || []).join(', ') || 'n/a'

phase('Documentation')

// Audit currency first (read-only) — only route writers if something is actually stale.
const audit = await agent(
  `Audit whether this change leaves documentation stale (READMEs, API docs, changelog, user guides). READ-ONLY. List exactly which docs need updating and why. Work within: ${repo}

Change: ${changeLabel}
Changed files: ${changedFiles}`,
  {
    label: 'docs:audit',
    phase: 'Documentation',
    agentType: 'agent-teams-workforce:documentation-currency-auditor',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['docsCurrent', 'staleDocs'],
      properties: {
        docsCurrent: { type: 'boolean' },
        staleDocs: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

const staleDocs = (audit && Array.isArray(audit.staleDocs) ? audit.staleDocs : []).filter(Boolean)
const needsWork = !!(audit && !audit.docsCurrent && staleDocs.length)

// The four Documentation writers the lead routes to. Each owns one doc kind; routing
// to the matching writer keeps authorship inside the writer's specialty.
const WRITERS = [
  'api-documentation-writer',
  'readme-writer',
  'changelog-writer',
  'user-guide-writer',
]

let routing = null
let writerResults = []
let reviewResult = null
let selectionMode = 'default'
let writersChosen = []

if (needsWork) {
  // documentation-lead SELECTS which writer handles each stale doc — a READ-ONLY router
  // that authors no documentation itself. Segregation of duties: the lead routes, the
  // writers write, an independent reviewer validates.
  routing = await agent(
    `You are the documentation-lead — a READ-ONLY router. Do NOT write any documentation. Route each stale doc to the matching writer, drawn ONLY from this Documentation writer roster:
- api-documentation-writer — API reference / OpenAPI / GraphQL docs changed
- readme-writer — setup, onboarding, repo README, or a new repo
- changelog-writer — version bump / changelog entry derived from commits
- user-guide-writer — user-facing feature guide or walkthrough

Return the FEWEST writers that cover the stale docs. For each chosen writer, list the stale docs assigned to it. A doc kind with no matching change is not assigned. Work within: ${repo}

Change: ${changeLabel}
Changed files: ${changedFiles}
Stale docs to route: ${staleDocs.join(', ')}`,
    {
      label: 'docs:route',
      phase: 'Documentation',
      agentType: 'agent-teams-workforce:documentation-lead',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['assignments', 'rationale'],
        properties: {
          assignments: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['writer', 'docs'],
              properties: {
                writer: { type: 'string', enum: WRITERS },
                docs: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          rationale: { type: 'string' },
        },
      },
    }
  )

  // Normalize the lead's assignments: keep only valid roster writers that were given docs.
  const validAssignments = (routing && Array.isArray(routing.assignments) ? routing.assignments : [])
    .filter((x) => x && WRITERS.includes(x.writer) && Array.isArray(x.docs) && x.docs.filter(Boolean).length)
    .map((x) => ({ writer: x.writer, docs: x.docs.filter(Boolean) }))

  if (validAssignments.length) {
    selectionMode = 'selected'
    writersChosen = validAssignments.map((x) => x.writer)
  } else {
    // The lead routed nothing usable — fall back to the README writer on every stale doc,
    // so stale docs are never left unwritten.
    selectionMode = 'default'
    validAssignments.push({ writer: 'readme-writer', docs: staleDocs })
    writersChosen = ['readme-writer']
  }

  const WRITE_SCHEMA = {
    type: 'object',
    additionalProperties: false,
    required: ['updatedDocs'],
    properties: {
      updatedDocs: { type: 'array', items: { type: 'string' } },
      notes: { type: 'string' },
    },
  }

  // Run the selected writers in PARALLEL — different doc kinds are different files,
  // so there is no write contention between them.
  writerResults = (await parallel(
    validAssignments.map((asg) => () =>
      agent(
        `Update the stale documentation assigned to you so it matches shipped behavior. Author only the docs in your assignment; other writers own the rest. Work within: ${repo}

Change: ${changeLabel}
Changed files: ${changedFiles}
Docs assigned to you: ${asg.docs.join(', ')}`,
        {
          label: `docs:write:${asg.writer}`,
          phase: 'Documentation',
          agentType: `agent-teams-workforce:${asg.writer}`,
          schema: WRITE_SCHEMA,
        }
      )
    )
  )).filter(Boolean)

  // INDEPENDENT accuracy review — a different agent than any writer checks the written
  // docs against actual shipped behavior. The writer never reviews its own doc.
  const writtenDocs = []
  for (const r of writerResults) {
    if (r && Array.isArray(r.updatedDocs)) writtenDocs.push(...r.updatedDocs)
  }
  reviewResult = await agent(
    `Review the updated documentation against ACTUAL shipped behavior for accuracy and completeness. READ-ONLY — report findings, do not edit. State whether the docs accurately reflect the change. Work within: ${repo}

Change: ${changeLabel}
Changed files: ${changedFiles}
Docs to review: ${writtenDocs.join(', ') || 'n/a'}`,
    {
      label: 'docs:accuracy-review',
      phase: 'Documentation',
      agentType: 'agent-teams-workforce:documentation-accuracy-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['accurate', 'findings'],
        properties: {
          accurate: { type: 'boolean' },
          findings: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )
}

// Aggregate writer output into the same `update` shape composites consumed before:
// the union of updated docs plus per-writer notes.
const allUpdatedDocs = []
for (const r of writerResults) {
  if (r && Array.isArray(r.updatedDocs)) allUpdatedDocs.push(...r.updatedDocs)
}
const update = needsWork
  ? {
      updatedDocs: allUpdatedDocs,
      writers: writerResults,
      review: reviewResult,
    }
  : null

// Docs are current if the audit found them current, or the writers updated every stale
// doc AND the independent accuracy review confirms they match shipped behavior.
const docsCurrent = !!(
  audit &&
  (
    audit.docsCurrent ||
    (
      needsWork &&
      allUpdatedDocs.length >= staleDocs.length &&
      reviewResult &&
      reviewResult.accurate
    )
  )
)

// Decision ledger — what this phase actually did, for over-time mining.
// chosen = [currency-auditor, lead (when it routed), ...selected writers, accuracy-reviewer].
// mode 'selected' = the lead routed to specific writers; 'default' = docs already current
// (no writers run) OR the lead routed nothing usable and the mini fell back to readme-writer.
const chosen = ['documentation-currency-auditor']
  .concat(needsWork ? ['documentation-lead'] : [])
  .concat(writersChosen)
  .concat(needsWork ? ['documentation-accuracy-reviewer'] : [])

const ledger = {
  phase: 'documentation',
  beadId: (c.bead && c.bead.id) || null,
  chosen,
  mode: needsWork ? selectionMode : 'default',
  ok: !!docsCurrent,
}

return { docsCurrent, audit, update, ledger }
