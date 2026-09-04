export const meta = {
  name: 'documentation',
  description:
    'Cross-cutting mini — Documentation. Runs alongside the build (not as a phase): ONE read-only auditor names which docs the change leaves stale AND which writer owns each (it authors no documentation, so naming the writer is not judging its own work), the writers author in parallel, and an INDEPENDENT accuracy reviewer checks the result against shipped behavior. No routing session sits between the audit and the writers — an unusable or absent assignment falls back to a deterministic path-based mapping. Its currency result feeds the deployment readiness review. Code is not done until its documentation is current.',
  phases: [{ title: 'Documentation', detail: 'currency audit + assigned writes + accuracy review' }],
}

// args: { contract, green }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
const green = a.green || {}
const repo = c.repoPath || (c.bead && c.bead.repoPath) || '(repo path not provided)'
const changeLabel = c.bead ? `${c.bead.id || ''} ${c.bead.title || ''}`.trim() : 'feature'
const changedFiles = (green.changedFiles || []).join(', ') || 'n/a'

phase('Documentation')

// The four Documentation writers. Each owns one doc kind; sending a stale doc to the
// matching writer keeps authorship inside the writer's specialty.
const WRITERS = [
  'api-documentation-writer',
  'readme-writer',
  'changelog-writer',
  'user-guide-writer',
]

// Audit currency first (read-only) — only dispatch writers if something is actually stale.
//
// ── THE AUDITOR NAMES THE WRITER; NO ROUTER SESSION SITS BETWEEN ───────────────
//
// This used to be two sessions: `docs:audit` returned `staleDocs` — the documents and
// WHY each was stale — and `docs:route` then spent a whole documentation-lead session
// mapping those same strings onto four fixed names from an enum. The auditor has
// already read the change and the docs; the second session added no information, only
// a session-start, on every build run of all three composites.
//
// Segregation of duties is untouched: the auditor AUTHORS NO DOCUMENTATION, so naming
// which writer owns a stale doc is not judging its own work — and the writers are
// still checked afterwards by an independent accuracy reviewer, which is the
// maker/checker pair that actually matters here.
const audit = await agent(
  `Audit whether this change leaves documentation stale (READMEs, API docs, changelog, user guides). READ-ONLY — you write no documentation. List exactly which docs need updating and why. Work within: ${repo}

Then ASSIGN each stale doc to the writer that owns its kind, drawn ONLY from this roster:
- api-documentation-writer — API reference / OpenAPI / GraphQL docs
- readme-writer — setup, onboarding, repo README, or a new repo
- changelog-writer — version bump / changelog entry derived from commits
- user-guide-writer — user-facing feature guide or walkthrough

Use the FEWEST writers that cover the stale docs, list the stale docs assigned to each, and assign no writer whose kind nothing changed. Assigning a writer is not a judgment on any work — you author none of it, and an independent reviewer checks what the writers produce.

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
      },
    },
  }
)

const staleDocs = (audit && Array.isArray(audit.staleDocs) ? audit.staleDocs : []).filter(Boolean)
const needsWork = !!(audit && !audit.docsCurrent && staleDocs.length)

// Deterministic fallback mapping, used when the auditor assigned nothing usable. It is
// a lookup over the doc PATH, not a guess about meaning: these four filename shapes are
// what the four writer specialties are defined against.
const writerForPath = (docPath) => {
  const p = String(docPath || '')
  if (/(^|\/)changelog(\.[a-z]+)?$/i.test(p) || /changelog/i.test(p)) return 'changelog-writer'
  if (/(^|\/)readme(\.[a-z]+)?$/i.test(p) || /readme/i.test(p)) return 'readme-writer'
  if (/openapi|swagger|(^|\/)api(\/|\.|-|_)|\/api-reference/i.test(p)) return 'api-documentation-writer'
  return 'user-guide-writer'
}

let writerResults = []
let reviewResult = null
let selectionMode = 'default'
let writersChosen = []

if (needsWork) {
  // Normalize the auditor's assignments: keep only valid roster writers that were given docs.
  const validAssignments = (audit && Array.isArray(audit.assignments) ? audit.assignments : [])
    .filter((x) => x && WRITERS.includes(x.writer) && Array.isArray(x.docs) && x.docs.filter(Boolean).length)
    .map((x) => ({ writer: x.writer, docs: x.docs.filter(Boolean) }))

  // Every stale doc must reach a writer. An assignment set that covers only some of them
  // is not a reason to drop the rest — the auditor said they were stale, and the audit is
  // what `docsCurrent` is computed against below.
  const assigned = new Set()
  for (const asg of validAssignments) for (const doc of asg.docs) assigned.add(doc)
  const unassigned = staleDocs.filter((doc) => !assigned.has(doc))
  if (unassigned.length) {
    // Map the leftovers deterministically by path rather than paying a session to route
    // them. Merge into an existing assignment where the writer already has work.
    for (const doc of unassigned) {
      const writer = writerForPath(doc)
      const existing = validAssignments.find((x) => x.writer === writer)
      if (existing) existing.docs.push(doc)
      else validAssignments.push({ writer, docs: [doc] })
    }
    log(
      `${unassigned.length} stale doc(s) the audit did not assign were mapped by path: ` +
        unassigned.map((doc) => `${doc} -> ${writerForPath(doc)}`).join('; ')
    )
  }

  selectionMode = audit && Array.isArray(audit.assignments) && audit.assignments.length ? 'assigned' : 'derived'
  writersChosen = validAssignments.map((x) => x.writer)

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
// chosen = [currency-auditor, ...selected writers, accuracy-reviewer]. There is no
// documentation-lead in this list any more: the routing session it existed for is gone.
// mode 'assigned' = the auditor named the writers; 'derived' = it named none and the
// script mapped every stale doc by path; 'default' = docs already current, no writers run.
const chosen = ['documentation-currency-auditor']
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
