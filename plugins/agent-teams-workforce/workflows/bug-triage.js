export const meta = {
  name: 'bug-triage',
  description:
    'Bug front-end. Turns a symptom (a bug bead) into an implementation-ready contract: reproduction, root cause, blast radius, and the expected-behavior acceptance criteria the shared tail builds against. Also SIZES the bug: a defect whose honest fix is a redesign is escalated as needing a PRD and Epic rather than being squeezed through the fix path, because a bug ticket is not a licence to rebuild a subsystem unreviewed. Read-only — produces no code changes.',
  phases: [{ title: 'Triage', detail: 'root-cause analysis + scope sizing + expected-behavior contract' }],
}

// args: { bead: { id, title, description, repoPath?, repoHints?, manifestPath? } }
//
// `repoPath` is the repository when the caller knows it. It is NOT required: a Bug is
// filed against a SYMPTOM, and which repository the defect lives in is a finding of the
// diagnosis — the blast radius names the code at fault, and the code at fault is in a
// repository. So when no repoPath is supplied the diagnosing agent is told to LOCATE it,
// from the symptom, the polyrepo manifest (`manifestPath`) and any names the caller merely
// suspects (`repoHints`), and to report it CONFIRMED — an absolute path that exists and is
// a git repository — or to report that it could not. A guessed repository is not an
// answer: bug-fix validates what comes back and refuses what it cannot use.
const __a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = __a.bead || {}
const repoKnown = !!String(bead.repoPath || '').trim()
const repo = repoKnown ? bead.repoPath : '(NOT KNOWN — locating it is part of this diagnosis; see below)'

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof __a.standingRulings === 'string' ? __a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''
const repoHints = (Array.isArray(bead.repoHints) ? bead.repoHints : []).map((h) => String(h == null ? '' : h).trim()).filter(Boolean)
const manifestPath = String(bead.manifestPath || '').trim()
const LOCATE_REPO =
  repoKnown
    ? ''
    : `

THE REPOSITORY IS NOT KNOWN, AND FINDING IT IS PART OF THIS DIAGNOSIS. Locate the repository whose source contains the code at fault. Start from the symptom and the blast radius; consult the polyrepo manifest${manifestPath ? ` at ${manifestPath}` : ''} for the repositories this project has and where each is checked out on this machine${repoHints.length ? `; the caller suspects it may be one of: ${repoHints.join(', ')} — a suspicion, not an answer` : ''}. Report repoPath as the ABSOLUTE path of that repository — the repository itself, not a worktree beneath it and not a subdirectory — and only after you have CONFIRMED the directory exists and is a git repository. If you cannot confirm one, report repoPath as an empty string and say in repoResolution which repositories you examined and why none was confirmed. A guessed repository sends a pipeline that writes code, commits and opens a pull request into a tree nobody chose; an honest empty answer does not.`

phase('Triage')

// 1) Diagnosis — read-only analyst. Separation of duties: this agent does not fix.
const analysis = await agent(
  `${rulingsBlock}Diagnose this bug. You are READ-ONLY — do not change code. Work within the repository at: ${repo}

Bug ${bead.id || ''}: ${bead.title || ''}
${bead.description || ''}

Deliver:
- reproduction: the minimal, concrete steps/conditions that trigger the defect.
- rootCause: the precise mechanism and code location (file:line where possible), as prose.
- defects: the SAME root cause, ENUMERATED — one entry per distinct defect, each with a short stable id (D1, D2, ...), its mechanism, and the file and line where it lives. One bead frequently contains several distinct defects, and returning them only as one paragraph of prose leaves everything downstream with nothing countable: the acceptance criteria are then written against a blob and cannot be bounded, indexed, or checked for coverage. Return exactly one entry per defect you would fix separately — not one per file, not one per symptom.
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
  Return ONLY surfaces the CHANGE touches — not surfaces the surrounding code happens to sit near. Return an empty list when the fix is confined to internal logic, which is the common case. Each surface you name costs a full additional test-authoring agent; each one you omit leaves that surface with no specialist coverage.
- repoPath: the ABSOLUTE path of the repository the defect lives in${repoKnown ? ' — echo the repository you were given' : ''}.
- repoResolution: how you confirmed the repository${repoKnown ? ' (one line; it was supplied)' : ', or why none could be confirmed'}.${LOCATE_REPO}`,
  {
    label: 'triage:diagnosis',
    phase: 'Triage',
    agentType: 'agent-teams-workforce:root-cause-analyst',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['reproduction', 'rootCause', 'defects', 'affectedFiles', 'blastRadius', 'surfaces'],
      properties: {
        reproduction: { type: 'string' },
        rootCause: { type: 'string' },
        defects: {
          type: 'array',
          minItems: 1,
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'mechanism'],
            properties: {
              id: { type: 'string' },
              mechanism: { type: 'string' },
              file: { type: 'string' },
              line: { type: 'integer' },
            },
          },
        },
        affectedFiles: { type: 'array', items: { type: 'string' } },
        blastRadius: { type: 'string' },
        repoPath: { type: 'string' },
        repoResolution: { type: 'string' },
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
// The repository the fix is built in. A supplied one is the answer; otherwise it is what
// the diagnosis LOCATED, reported as a finding beside the blast radius. Never a guess made
// here: an empty string is carried as null and the caller refuses to write without one.
const resolvedRepoPath = repoKnown ? bead.repoPath : String((analysis && analysis.repoPath) || '').trim() || null
if (!repoKnown) log(`Triage: repository ${resolvedRepoPath ? `located at ${resolvedRepoPath}` : 'NOT located'} — ${(analysis && analysis.repoResolution) || 'no resolution reported'}`)

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
  `${rulingsBlock}Size this bug. It has been diagnosed; decide whether its honest remedy is a FIX or a REDESIGN. You are READ-ONLY and you are NOT proposing the remedy — only sizing it.

Answer "needs-prd" when the honest fix would: change a public contract or event schema, alter the data model, cross a service boundary, require an architecture decision the SAD does not cover, or amount to rebuilding a component rather than correcting it.

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
    repoPath: resolvedRepoPath,
    repoResolution: (analysis && analysis.repoResolution) || null,
    scope,
    scopeRationale,
    contractsTouched: (sizing && sizing.contractsTouched) || [],
    reproduction: analysis.reproduction,
    rootCause: analysis.rootCause,
    defects: (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id),
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
//
// BOUNDED BY CONSTRUCTION. This step used to receive a prose root cause with no cap, no
// defect index, and no scope rule — and a four-defect bug produced eighteen-plus
// criteria, several of them repo-wide greps. The downstream coverage reviewer then
// blocked on partial coverage of criteria Red could never legitimately turn red, and the
// Red gate exhausted without one line of production code being written.
//
// The cap is a SCHEMA bound, not a sentence in a prompt: the runtime enforces the first
// and merely requests the second, which is the lesson from every prose control in this
// pipeline that has already failed. Coverage then becomes an exact join — every defectId
// resolves, every defect has at least one criterion — instead of a judgment call.
const defects = (Array.isArray(analysis.defects) ? analysis.defects : []).filter((d) => d && d.id)
const defectIds = defects.map((d) => String(d.id))
const AC_MIN = Math.max(1, defectIds.length)
const AC_MAX = Math.max(2, defectIds.length * 2)
log(`Triage: ${defectIds.length || 'unenumerated'} defect(s) — acceptance criteria bounded to ${AC_MIN}..${AC_MAX}`)

const contract = await agent(
  `${rulingsBlock}Write the expected-behavior contract for this bug fix as testable given/when/then acceptance criteria — the correct behavior the fix must satisfy and that a failing test will encode. Do NOT write code.

ONE OR TWO CRITERIA PER DEFECT, and every criterion carries the id of the defect it covers. Every defect below must have at least one. Between ${AC_MIN} and ${AC_MAX} criteria in total — this is enforced by the schema, not requested.

A CRITERION DESCRIBES AN EXECUTION, NOT THE REPOSITORY. Apply this test to everything you are about to write: **if it would still be checkable with the change reverted, it is not an acceptance criterion.** "No occurrence of \`redis://\` anywhere in the repo" passes that test trivially — it is checkable before, during and after the fix, against code nobody touched — which is exactly what makes it a LINT RULE wearing an acceptance-criterion costume. Return those in \`lintRules\` instead. They are real and they are worth enforcing; they are just not something a failing test can encode, and putting them here blocks the build on a grep no Red phase can legitimately make fail.

Bug ${bead.id || ''}: ${bead.title || ''}
Reproduction: ${analysis.reproduction}
Root cause: ${analysis.rootCause}
Files the fix must change: ${(analysis.affectedFiles || []).join(', ') || 'n/a'}

Defects to cover (use these ids exactly):
${defects.length ? defects.map((d) => `- ${d.id}: ${d.mechanism}${d.file ? ` [${d.file}${d.line ? `:${d.line}` : ''}]` : ''}`).join('\n') : '(the diagnosis enumerated none — derive minimal coverage from the root cause above and use the id D1)'}`,
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
          minItems: AC_MIN,
          maxItems: AC_MAX,
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['defectId', 'given', 'when', 'then'],
            properties: {
              defectId: defectIds.length ? { type: 'string', enum: defectIds } : { type: 'string' },
              given: { type: 'string' },
              when: { type: 'string' },
              then: { type: 'string' },
            },
          },
        },
        // Sibling output, deliberately NOT passed to tdd-red. A repo-wide invariant is a
        // lint rule or a pre-commit hook, landed by the path that already commits — the
        // coverage reviewer never sees it and therefore structurally cannot block the
        // Red gate on a criterion Red can never turn red.
        lintRules: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['pattern', 'rationale'],
            properties: {
              pattern: { type: 'string' },
              rationale: { type: 'string' },
              scope: { type: 'string' },
            },
          },
        },
      },
    },
  }
)

// Coverage is an exact join, not a judgment: every enumerated defect must have at least
// one criterion pointing at it.
const authoredAc = (contract && Array.isArray(contract.acceptanceCriteria) ? contract.acceptanceCriteria : []).filter(Boolean)
const covered = new Set(authoredAc.map((x) => String(x.defectId || '')))
const uncoveredDefects = defectIds.filter((id) => !covered.has(id))
if (uncoveredDefects.length) log(`⚠ Triage: defect(s) with no acceptance criterion: ${uncoveredDefects.join(', ')}`)
const lintRules = (contract && Array.isArray(contract.lintRules) ? contract.lintRules : []).filter(Boolean)
if (lintRules.length) log(`Triage: ${lintRules.length} repo-wide invariant(s) routed to lint, not to the Red phase`)

return {
  bead,
  repoPath: resolvedRepoPath,
  repoResolution: (analysis && analysis.repoResolution) || null,
  scope,
  scopeRationale,
  reproduction: analysis.reproduction,
  rootCause: analysis.rootCause,
  defects,
  affectedFiles: analysis.affectedFiles,
  blastRadius: analysis.blastRadius,
  // Consumed by tdd-red to DERIVE its test writers. Empty means unit tests only,
  // which is the correct answer for a fix confined to internal logic.
  surfaces: analysis.surfaces || [],
  acceptanceCriteria: authoredAc,
  uncoveredDefects,
  // Carried on the contract for the settle/deploy path to land as a repo gate. NOT
  // acceptance criteria and never handed to the Red phase.
  lintRules,
}
