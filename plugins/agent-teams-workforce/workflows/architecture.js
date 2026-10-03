export const meta = {
  name: 'architecture',
  description:
    "Leaf mini — designs the architecture for one Epic's PRD as a target and a delta version, and integrates the approved target into the effective version. Its inputs are the PRD, the effective version in arc42 (every section and view, found through the catalog frontmatter), the open targets that show the same elements, the code on each relevant repository's main, the open beads, and the AWS documentation through the AWS MCP tools; never what is deployed. A prd-reality-reconciler session writes survey.md and survey.json, with repository facts from the polyrepo-steward. Then rounds: the architecture-decision-workflow-coordinator names the proposers, reviewers, diagram authors and cost reviewers each round and the script runs them; proposers write the target and delta views into a draft, reviewers mark every claim verified, unsupported or wrong with evidence, and every finding is answered by its owner, up to maxRounds (default 6). Every session treats anything in the PRD about how the system works as no requirement: the team decides every technical aspect itself. The script holds the decision until every proposer has stated claims, every claim has a verdict, the required reviewers and a cost reviewer have reviewed the design (the pattern challenger, for targeted critique only when needed), every finding is answered, and depscore.py arch-target accepts the draft; a resumed run reads its saved work through depscore.py arch-resume, which folds the saved round results into the claim and finding ledger on disk (ledger.json, which the sessions read) and returns only the facts the run branches on, and it stops, keeping the saved work, when that work cannot be read. The architecture-decider, given artifact paths only, approves the team's result, choosing where the team left competing solutions, or returns it to a named proposer; anything else it escalates goes back to the team, and only two business requirements that no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, reach the owner. On approval depscore.py arch-target writes target/<subject>/ and its delta/ as in-review, the architecture-maintainer integrates the target into arc42, the architecture-conformance-reviewer checks it (at most 2 correction passes), and depscore.py arch-approve sets the integrated files the review covered to effective; depscore.py arch-commit then commits the files the integration changed, staging only those paths, and pushes the branch. A write under arc42 section 2 fails the run and is undone: depscore.py arch-constraints fingerprints that folder before and after and copies it aside, and depscore.py arch-constraints-restore puts it back. depscore.py arch-snapshot fingerprints arc42/, target/ and built/: a write there before the target is approved fails the run, and the integration's files are measured from it, not taken from the maintainer's report, so every file the integration wrote is reviewed before arch-approve sets it to effective. Returns { ok, stage, subject, targetDir, deltaDir, deltaFiles, decision, architectureUpdate, conformance, approval, vaultCommit } or, for conflicting business requirements or a contradiction in the architecture, ok:false at stage owner-concern with requiredHumanActions.",
  phases: [
    { title: 'Survey', detail: 'the polyrepo-steward names the repositories; a prd-reality-reconciler session surveys the effective views, code on main, open beads and open targets for each capability the PRD needs' },
    { title: 'Rounds', detail: 'the coordinator names each round of proposers, reviewers, diagram authors and cost reviewers; the script runs them and tracks every claim and finding' },
    { title: 'Decide', detail: 'after the team has designed, challenged and settled the target, the architecture-decider approves it, choosing where the team left competing solutions, or returns it to a named proposer; only two business requirements no design can satisfy together, or an architecture that contradicts itself where common sense cannot settle it, reach the owner' },
    { title: 'Target', detail: 'depscore.py arch-target writes the approved draft to target/<subject>/ and its delta/ as in-review' },
    { title: 'Integrate', detail: 'the architecture-maintainer integrates the target into arc42; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the reviewed files to effective; depscore.py arch-commit commits and pushes the integrated files' },
  ],
}

let dispatchInterruption = null
function dispatchOutcome(result) {
  return dispatchInterruption ? { ...result, ok: false, paused: true, resumable: true, dispatchFailed: true, stage: dispatchInterruption.stage, reason: dispatchInterruption.message, headline: dispatchInterruption.message, dispatchInterruption } : result
}
function dispatchFailureCause(err) {
  const e = err && typeof err === 'object' ? err : {}
  const text = [e.message || err || '', e.type, e.code, e.error && e.error.type].join(' ')
  if (/structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i.test(text)) return 'deterministic'
  if (/insufficient_quota|quota|usage[ _-]?limit|spend[ _-]?limit|session[ _-]?limit|credit balance|out of credits|hit your limit|token limit|account.quota.exhausted/i.test(text)) return 'exhausted'
  const status = [e.status, e.statusCode, e.code, e.response && e.response.status]
    .map((value) => Number(value)).find((value) => Number.isFinite(value) && value >= 100 && value < 600)
  return [408, 425, 429, 500, 502, 503, 504, 529].includes(status) || /overload|rate[ _-]?limit|too many requests|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i.test(text) ? 'transient' : 'deterministic'
}
const dispatchFailures = []

async function run(prompt, opts) {
  if (dispatchInterruption) return null
  let message = 'returned nothing'
  try {
    const out = await agent(prompt, opts)
    if (out) return out
  } catch (err) {
    message = String((err && err.message) || err)
    const cause = dispatchFailureCause(err)
    if (cause !== 'deterministic') dispatchInterruption = { stage: cause === 'exhausted' ? 'account-quota-exhausted' : 'api-unavailable', message }
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

return dispatchOutcome(await (async () => {
// args: { prd: { id?, title?, path?, body? }, epic: { id }, archPath, subject?, repoPath?, seedRepos?,
//   maxRounds?, depscore: { script, repo },
//   artifacts: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const hasText = (v) => typeof v === 'string' && v.trim().length > 0
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const listed = (x) => (Array.isArray(x) ? x.filter(hasText).map((s) => s.trim()) : [])

const prd = a.prd && typeof a.prd === 'object' ? a.prd : {}
const epicId = String((a.epic && (a.epic.id || a.epic.beadId)) || '').trim()
const archPath = hasText(a.archPath) ? a.archPath.trim().replace(/\/+$/, '') : ''
const ART = a.artifacts && typeof a.artifacts === 'object' && hasText(a.artifacts.dir) && hasText(a.artifacts.script) ? a.artifacts : null
const DS = a.depscore && typeof a.depscore === 'object' && hasText(a.depscore.script) && hasText(a.depscore.repo) ? a.depscore : null
const MAX_ROUNDS = Number.isInteger(a.maxRounds) && a.maxRounds > 0 ? a.maxRounds : 6
const MAX_CORRECTIONS = 2

function refuse(why) {
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}
if (!archPath) return refuse("no archPath supplied (the project's ATW_ARCH_PATH) — there is no architecture to design from or integrate into. Set ATW_ARCH_PATH for the run, or pass archPath to this mini.")
if (!hasText(prd.path) && !hasText(prd.body)) return refuse('no PRD supplied: pass prd.path (or prd.body)')
if (!epicId) return refuse('no Epic supplied: pass epic.id')
if (!ART) return refuse("no artifacts directory or recorder supplied: the architecture step saves its survey, round results and decision under the Epic's working directory, so a stopped run resumes from them")
if (!DS) return refuse('no depscore script and beads repository supplied: the target write, the section 2 check and the approval run through depscore.py')

const ARC42 = `${archPath}/arc42`
const CONSTRAINTS = `${ARC42}/02-architecture-constraints`
const MENU = `${archPath}/reference/diagram-and-model-types.md`
const MODEL = `${archPath}/reference/architecture-documentation-model.md`
const WORK = `${ART.dir}/architecture`
const DRAFT = `${WORK}/draft`
const ROUNDS_DIR = `${WORK}/rounds`
const SURVEY_MD = `${WORK}/survey.md`
const SURVEY_JSON = `${WORK}/survey.json`
const DECISION_MD = `${WORK}/decision.md`
const DECISION_JSON = `${WORK}/decision.json`
const TARGET_JSON = `${WORK}/target.json`
const UPDATE_JSON = `${WORK}/architecture-update.json`
const LEDGER_JSON = `${WORK}/ledger.json`
const TREE_START = `${WORK}/tree-start.json`
const TREE_LAST = `${WORK}/tree-last.json`
const TARGET_CHECK = `${WORK}/target-check.json`
const prdRef = hasText(prd.path) ? `the document at ${prd.path}. Read it in full: every requirement in it is in scope.` : `\n${prd.body}`
const prdBase = hasText(prd.path) ? String(prd.path).split('/').pop().replace(/\.md$/i, '') : ''
const beadPrefix = epicId.includes('-') ? `${epicId.split('-')[0]}-` : ''
const FORBID = [epicId, beadPrefix, prd.id, prdBase].filter(hasText)


/** Returns the save-and-record instruction for files a session writes under the architecture working directory. */
function persistBrief(files, what) {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  const record = (file) => `python3 ${shq(ART.script)} record ${shq(file)} --epic ${shq(ART.epicId)} --phase ${shq(ART.phase)}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session writes it for you.
1. Write ${what} with the Write tool, replacing the whole file if it exists (Read it first if the Write tool asks you to):
${files.map((f) => `   - ${f}`).join('\n')}
2. Then run, for each file, exactly this command:
${files.map((f) => `   ${record(f)}`).join('\n')}
If a step fails, say so in your result and still return your result. Never improvise another way to write, move or record a file.`
}

const RUN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'output'],
  properties: { exitCode: { type: 'integer' }, output: { type: 'object' } },
}
/** Runs one depscore.py command in a runner session; returns its JSON output or { error }. */
async function depscore(label, phaseName, commandArgs) {
  const command = `python3 ${shq(DS.script)} -C ${shq(DS.repo)} ${commandArgs}`
  const out = await run(
    `Run exactly this one shell command, once, in the FOREGROUND (never set run_in_background) with the Bash tool's \`timeout\` parameter set to 600000, and change nothing else:

${command}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label, phase: phaseName, model: 'haiku', effort: 'low', schema: RUN_SCHEMA }
  )
  if (!out) return { error: `the ${label} runner returned no result` }
  if (out.exitCode !== 0 || !out.output || out.output.error) {
    const raw = String((out.output && out.output.error) || `depscore.py exited ${out.exitCode}`)
    const exception = exceptionOf(raw)
    return { error: exception ? `${exception} (depscore.py exited ${out.exitCode}; full output: ${raw})` : raw, exception, output: out.output || null }
  }
  return out.output
}
/** Returns the exception line a Python traceback in `text` ends with (e.g. "ValueError: ..."), or '' when it holds none. */
function exceptionOf(text) {
  const s = String(text || '')
  if (!/Traceback \(most recent call last\)/.test(s)) return ''
  const lines = s.split('\n').map((l) => l.trim()).filter(Boolean)
  return [...lines].reverse().find((l) => /^[A-Za-z_][\w.]*(Error|Exception|Exit|Interrupt)(:|$)/.test(l)) || lines[lines.length - 1] || ''
}
/** Records files a session wrote without a shell, with the artifact recorder. */
async function recordFiles(label, phaseName, files) {
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter(hasText)
  const commands = files.map((f) => `python3 ${shq(ART.script)} record ${shq(f)} --epic ${shq(ART.epicId)} --phase ${shq(ART.phase)}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`)
  const out = await run(
    `Run exactly these shell commands, one at a time, in order, and change nothing else:

${commands.join('\n')}

Return the exit code of the last command that ran as \`exitCode\` and, as \`output\`, an object { "failed": [<each command that exited non-zero, with its stderr>] }. Do not retry, do not repair, do not run any other command.`,
    { label, phase: phaseName, model: 'haiku', effort: 'low', schema: RUN_SCHEMA }
  )
  if (!out || out.exitCode !== 0) log(`${label}: the recorder did not record ${files.join(', ')}`)
}


const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective version: the approved architecture. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints; read it in full. \`arc42/04-solution-strategy/README.md\` holds the enterprise-level strategy; read it. Every other section is the design so far, as views.
- The constraints are the owner's; everything else in the architecture is the design so far, followed as established patterns unless a design states a reason and evidence to change it.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`target/<subject>/\` folders are open targets (designs in progress) and \`built/<subject>/\` folders record builds that differ from the effective version. Read every open target that shows an element this PRD touches, so the designs do not contradict each other.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.
- \`lifecycle_state\` is per file: \`effective\` was reviewed and approved; \`in-review\` is input to check, never assumed vetted.`

const INPUTS_RULE = `YOUR INPUTS are the PRD, the effective version and the open targets above, the code on each relevant repository's \`main\` (read it as committed there: \`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`), the open beads (other Epics' Stories and Tasks planned but not built), and the AWS documentation through the AWS MCP tools and skills. What is deployed in AWS is not an input: run no AWS describe, list or get call against an account. Repository code is input to check, never evidence that a design is right. Cite what you rely on: a view by its absolute path and heading, code by repository, path and line on \`main\`, AWS behaviour by the documentation URL you read.`

const PRD_RULE = `THE PRD STATES WHAT, NEVER HOW. It holds the business and end-user requirements: what the seeker and the business get, and the results someone outside the system could observe. Anything in it about how the system works — mechanisms, services, technologies, response shapes and codes, contracts, telemetry, release mechanics, engineering numbers such as latencies, limits and thresholds — is not a requirement: ignore it, and never treat it as a defect. The architecture team decides every technical aspect itself, from the effective architecture, the code and the AWS documentation through the AWS MCP tools and skills. Where the PRD leaves a technical value open, the team chooses it and states the reason and evidence. Where two requirements seem to pull against each other, the team designs the solution that best satisfies both, putting the seeker's privacy and data protection first, and records that as a design decision with its reason. None of this is a question for the owner.`

const BUSINESS_CONFLICT_RULE = `List in \`businessConflicts\` only two BUSINESS requirements of the PRD that no design whatsoever could satisfy together (each with the requirement and why no design can satisfy both). A technical gap, an open value, a "how" in the PRD, or a tension a design can resolve is never one: the team resolves those. This list is almost always empty.`

const DRAFT_RULES = `THE DRAFT TARGET is the folder ${DRAFT}. It has the arc42 section layout (\`05-building-block-view/…\`, \`06-runtime-view/…\`, \`07-deployment-view/…\`, \`08-crosscutting-concepts/…\`, and \`03-context-and-scope/\` or \`04-solution-strategy/\` only when the change reaches them) and a \`delta/\` folder beside them.
- A target view is the view as it will read once approved: a changed copy of each effective view that shows a changed element, at every scope where the element appears, and coverage for new elements according to the applicable obligations in ${MODEL}. Extend a sufficient shared view when it answers the required reader question; create a new view only when no existing or shared view supplies the required coverage. Catalog every covered element in \`shows\`. Copy an effective view into the draft before you change it, at the same relative path.
- \`delta/\` holds the views that show only what changes between the effective version and the target. Specs and Tasks are made from it.
- Every view is Markdown with catalog frontmatter (\`view_type\` from ${MENU}, \`scope\`, \`subject\`, \`shows\`, \`lifecycle_state: in-review\`), a Mermaid diagram where the view type has one, and prose.
- Nothing goes under \`02-architecture-constraints/\`: section 2 holds the owner's constraints.
- Name files and folders for their subject, never for the PRD, the Epic, a bead or a date. Write no history, decision record, rule or open item into a view.
- Write nothing in ${archPath}: the target reaches the architecture only after approval.`

const AGENT_PREFIX = 'agent-teams-workforce:'
const USER_LEVEL_AGENTS = new Set([
  'integration-pattern-architect',
  'persistence-architecture-specialist',
  'security-architecture-designer',
  'cdk-infrastructure-designer',
  'event-schema-designer',
  'domain-event-modeler',
  'bounded-context-mapper',
  'architecture-pattern-challenger',
  'architecture-tradeoff-skeptic',
  'architecture-boundary-guardian',
  'operational-readiness-reviewer',
  'failure-mode-analyst',
  'cost-architecture-reviewer',
  'cost-impact-reviewer',
])
const dispatchName = (name) => (USER_LEVEL_AGENTS.has(name) ? name : `${AGENT_PREFIX}${name}`)

const ROSTER = {
  proposer: {
    'integration-pattern-architect': 'integration between services: event and API patterns, sync or async, service boundaries',
    'persistence-architecture-specialist': 'persistence: table, key and index design from the access patterns',
    'security-architecture-designer': 'security: trust boundaries, identity and access, encryption, threat model',
    'cdk-infrastructure-designer': 'infrastructure: CDK stacks and constructs, function boundaries, packaging',
    'event-schema-designer': 'event schemas within the event envelope the architecture establishes',
    'api-contract-designer': 'REST API contracts',
    'graphql-schema-designer': 'GraphQL schemas',
    'domain-event-modeler': 'domain events, their flows and contracts',
    'bounded-context-mapper': 'domain boundaries and the relationships between contexts',
  },
  diagram: {
    'architecture-diagram-author': 'views of any type in the list of view types, at any scope',
    'c4-diagram-author': 'C4 views: system context, container, component',
    'uml-diagram-author': 'UML views: sequence, state, activity, class',
  },
  reviewer: {
    'architecture-pattern-challenger': 'critiques concrete structural weaknesses in the retained design without authoring another proposal',
    'architecture-tradeoff-skeptic': 'hidden assumptions and optimistic estimates behind a tradeoff',
    'architecture-boundary-guardian': 'coupling across contexts; conflicts with the constraints; departures from established patterns without reason and evidence',
    'operational-readiness-reviewer': 'operational burden: monitoring, alerting, runbooks',
    'failure-mode-analyst': 'failure modes: throttling, duplicate delivery, downstream unavailability, poison messages',
  },
  cost: {
    'cost-architecture-reviewer': 'the cost of the design, with the unit math shown',
    'cost-impact-reviewer': 'where the cost of the design changes shape as usage grows',
  },
}
const WRITER_ROLES = ['proposer', 'diagram']
const REVIEW_ROLES = ['reviewer', 'cost']
const roleOf = (name) => Object.keys(ROSTER).find((role) => Object.prototype.hasOwnProperty.call(ROSTER[role], name)) || null
const rosterText = Object.keys(ROSTER)
  .map((role) => `${role}:\n${Object.entries(ROSTER[role]).map(([n, w]) => `  - ${n} — ${w}`).join('\n')}`)
  .join('\n')
const ROSTER_ARG = Object.keys(ROSTER).map((role) => `${role}=${Object.keys(ROSTER[role]).join(',')}`).join(';')

/** The owner the coordinator assigned to each finding that had none: finding id -> writer. */
const assigned = new Map()
/**
 * Reads the step's saved work on disk with depscore.py arch-resume, which folds every saved round
 * result into the claim and finding ledger, writes it to ledger.json for the sessions that read
 * it, and prints only the facts the control flow branches on. No saved content comes back here:
 * sessions get file paths. Returns the facts or { error }.
 */
async function readFacts(label, phaseName, proposalTeam = null, roundPlan = null) {
  const assign = [...assigned].map(([id, w]) => `${id}=${w}`).join(',')
  const out = await depscore(label, phaseName, `arch-resume --work-dir ${shq(WORK)} --roster ${shq(ROSTER_ARG)}${assign ? ` --assign ${shq(assign)}` : ''}${proposalTeam ? ` --proposal-team ${shq(JSON.stringify(proposalTeam))}` : ''}${roundPlan ? ` --round-plan ${shq(JSON.stringify(roundPlan))}` : ''}`)
  if (!out || out.error || !out.rounds || typeof out.rounds !== 'object' || !out.integration) {
    return { error: (out && out.error) || 'depscore.py arch-resume printed no facts', exception: (out && out.exception) || '' }
  }
  for (const w of listed(out.rounds.overlapWarnings)) log(`Rounds: ${w}`)
  return out
}

const CONFLICT_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirements', 'why'],
    properties: { requirements: { type: 'array', items: { type: 'string' } }, why: { type: 'string' } },
  },
}
const REPOS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['repositories'],
  properties: {
    repositories: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'path', 'role', 'lifecycle'],
        properties: { name: { type: 'string' }, path: { type: 'string' }, role: { type: 'string' }, lifecycle: { type: 'string' } },
      },
    },
  },
}
// Consumed by: archresume coverage folding and architecture.js decisionGaps — stable
// ids preserve absent obligations; MODEL evidence supplies semantics, not a plugin menu.
// Consumed by archevidence: local section/main revision binding and external provenance.
const EVIDENCE_REFS = { type: 'array', items: { type: 'object', additionalProperties: false,
  required: ['path', 'heading', 'repo', 'revision', 'url'], properties: {
    path: { type: 'string' }, heading: { type: 'string' }, repo: { type: 'string' },
    revision: { type: 'string' }, url: { type: 'string' },
  } } }
const COVERAGE_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'subject', 'scope', 'obligation', 'sources', 'views', 'status', 'action', 'reason', 'evidenceRefs', 'disposition', 'dispositionReason'],
    properties: {
      id: { type: 'string' }, subject: { type: 'string' }, scope: { type: 'string' },
      obligation: { type: 'string' }, sources: { type: 'array', items: { type: 'string' } },
      views: { type: 'array', items: { type: 'string' } }, status: { type: 'string', enum: ['Present and sufficient', 'Present but incomplete', 'Required and absent', 'Not yet applicable', 'Not assessed'] },
      action: { type: 'string', enum: ['create', 'update', 'unchanged', 'remove', 'not-applicable', 'unresolved'] },
      reason: { type: 'string' },
      evidenceRefs: EVIDENCE_REFS, disposition: { type: 'string', enum: ['required', 'unrelated-debt'] }, dispositionReason: { type: 'string' },
    },
  },
}
// Consumed by: archresume — only an independent check of the current generated
// row/content revision satisfies coverage; reviewer prose is read by the decider.
const COVERAGE_CHECKS_SCHEMA = {
  type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['id', 'revision', 'verdict', 'evidence'],
    properties: {
      id: { type: 'string' }, revision: { type: 'string' },
      verdict: { type: 'string', enum: ['verified', 'unsupported', 'wrong'] }, evidence: { type: 'string' },
    },
  },
}
const COVERAGE_RULE = `COVERAGE is evidence in the existing survey/round results and ${LEDGER_JSON}, not another architecture version. Read ${MODEL} for applicable obligations and ${MENU} for selection/construction. Inventory relevant subjects from the design, repositories and contracts independently of catalog hits. Include required views that do not exist, every affected scope and horizontal concern; unrelated historical debt is non-blocking and is reported in your summary.
Each coverage row has a stable id, subject, scope, obligation (MODEL path and heading), sources (inventory/design evidence), views (absolute paths, including expected missing paths), status (the MODEL's assessment result), action and reason. Preserve ids across rounds; omitted ids remain in the ledger. Writers replace only their assigned rows; use draft paths for created/updated views, draft/delta descriptions for removals (not the canonical file being deleted), and canonical paths only for unchanged views. Keep removal evidence stable through integration. After completing work, update status to Present and sufficient; Not yet applicable pairs only with action not-applicable. Incomplete, absent and Not assessed statuses cannot pass approval. An unknown relevant obligation uses action unresolved. Not-applicable and unchanged need concrete reasons and evidence; no-change targets still assess applicable coverage. Never invent design to fill diagrams. Diagram declarations require actual diagrams; verify rendering, readability, semantics, links and metadata as the MODEL requires, reporting limitations honestly.
The ledger supplies each row's revision from its evidence and current view content. Reviewers copy that revision exactly into coverageChecks, with an independent verdict and evidence. A missing view or obligation can be a finding without an author claim. Recheck revised rows; old checks cannot approve new content.
Set disposition=required by default. For mistakenly inventoried unrelated historical debt, use unrelated-debt with dispositionReason proving it does not affect this change or dependencies; preserve its honest MODEL status. Only an independent verified current revision makes that disposition nonblocking. Retain the row and summarize it; never erase IDs.
EvidenceRefs bind relevant views by absolute path and unique heading (empty means whole file), repository code by absolute repo, main commit revision and repository-relative path, or external docs by url and version/retrieval revision. Unused fields are empty strings. Include relevant dependencies. Source movement requires refreshed evidence; reading test source is not a test run.`

const SURVEY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['subject', 'subjectReason', 'capabilities', 'openTargets', 'businessConflicts', 'coverage', 'summary'],
  properties: {
    subject: { type: 'string' },
    subjectReason: { type: 'string' },
    coverage: COVERAGE_SCHEMA,
    capabilities: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'requirements', 'effectiveViews', 'code', 'openBeads', 'openTargets'],
        properties: {
          name: { type: 'string' },
          requirements: { type: 'array', items: { type: 'string' } },
          effectiveViews: { type: 'array', items: { type: 'string' } },
          code: { type: 'array', items: { type: 'string' } },
          openBeads: { type: 'array', items: { type: 'string' } },
          openTargets: { type: 'array', items: { type: 'string' } },
          notes: { type: 'string' },
        },
      },
    },
    openTargets: { type: 'array', items: { type: 'string' } },
    businessConflicts: CONFLICT_ITEMS,
    summary: { type: 'string' },
  },
}
// Consumed by maker, checker and decider prompts: one shared completion standard.
const DESIGN_REVIEW_STANDARD = `Use the same acceptance basis throughout: applicable PRD outcomes, settled owner decisions and section-2 constraints, the relevant MODEL obligations, existing source evidence, and the retained target/delta. The lead reconciles the combined design before handing it to reviewers: contracts, event publishers, ownership, security and failure behavior must agree across its views. Inspect cited implementation and tests; distinguish evidence read from behavior actually verified. Do this within the existing authoring pass, not a new agent or audit pass.
Review is an independent safety net against that same basis, not a source of new requirements or preferred redesigns. Each finding identifies the violated requirement/constraint/contract or concrete correctness defect, its evidence and the bounded repair. Do not reopen a settled mechanism just to offer another design. On later rounds review the changed claims/views and their affected dependencies, retaining still-valid evidence; do not demand fresh unrelated proposals. New evidence of a real defect must still be reported. Neither this shared standard nor the proposer cap guarantees approval.`

const COORDINATOR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['readyForDecision', 'reason', 'proposalTeam', 'dispatches', 'overlaps'],
  properties: {
    // Consumed by arch-resume and runRound: persist and enforce the effort-wide proposal budget.
    proposalTeam: {
      type: 'object', additionalProperties: false,
      required: ['lead', 'second', 'unresolvedIssue', 'evidence', 'whySecond'],
      properties: {
        lead: { type: 'string' }, second: { type: 'string' },
        unresolvedIssue: { type: 'string' }, evidence: { type: 'string' }, whySecond: { type: 'string' },
      },
    },
    readyForDecision: { type: 'boolean' },
    reason: { type: 'string' },
    dispatches: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'role', 'task', 'files', 'answers', 'claimIds', 'claimFiles'],
        properties: {
          agentType: { type: 'string' },
          role: { type: 'string', enum: Object.keys(ROSTER) },
          task: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          answers: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } }, claimFiles: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    // Consumed by: unjustifiedOverlaps before the plan is saved, and archrounds.overlap_justified on resume.
    // One entry per overlap: the coordinator decides it once, with one reason.
    overlaps: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['files', 'claimIds', 'agentTypes', 'reason'],
        properties: {
          files: { type: 'array', items: { type: 'string' } },
          claimIds: { type: 'array', items: { type: 'string' } },
          agentTypes: { type: 'array', items: { type: 'string' } },
          reason: { type: 'string' },
        },
      },
    },
  },
}
const WRITER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['files', 'claims', 'answers', 'businessConflicts', 'coverage', 'summary'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    coverage: COVERAGE_SCHEMA,
    claims: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claimId', 'claim', 'file', 'citation', 'supersedes', 'evidenceRefs'],
        properties: { claimId: { type: 'string' }, claim: { type: 'string' }, file: { type: 'string' }, citation: { type: 'string' }, supersedes: { type: 'array', items: { type: 'string' } }, evidenceRefs: EVIDENCE_REFS },
      },
    },
    answers: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['findingId', 'response', 'evidence'],
        properties: { findingId: { type: 'string' }, response: { type: 'string', enum: ['fixed', 'disputed'] }, evidence: { type: 'string' } },
      },
    },
    businessConflicts: CONFLICT_ITEMS,
    summary: { type: 'string' },
  },
}
const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings', 'coverageChecks', 'resolutions', 'summary'],
  properties: {
    coverageChecks: COVERAGE_CHECKS_SCHEMA,
    resolutions: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['findingId', 'revision', 'verdict', 'evidence'], properties: { revision: { type: 'string' }, findingId: { type: 'string' }, verdict: { type: 'string', enum: ['accepted', 'rejected'] }, evidence: { type: 'string' } } } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claimId', 'claimRevision', 'claim', 'file', 'verdict', 'evidence', 'owner'],
        properties: {
          claimId: { type: 'string' }, claimRevision: { type: 'string' },
          claim: { type: 'string' },
          file: { type: 'string' },
          verdict: { type: 'string', enum: ['verified', 'unsupported', 'wrong'] },
          evidence: { type: 'string' },
          owner: { type: 'string' },
        },
      },
    },
    estimates: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const OWNER_CONCERN_KINDS = ['business-conflict', 'architecture-conflict']
const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['round', 'verdict', 'diligence', 'choices', 'returnTo', 'ownerConcerns', 'coverageRevision', 'summary'],
  properties: {
    round: { type: 'integer' },
    coverageRevision: { type: 'string' },
    verdict: { type: 'string', enum: ['approve', 'return', 'owner-concern'] },
    diligence: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['check', 'present', 'where'],
        properties: { check: { type: 'string' }, present: { type: 'boolean' }, where: { type: 'string' } },
      },
    },
    returnTo: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'missing'],
        properties: { agentType: { type: 'string' }, missing: { type: 'string' } },
      },
    },
    choices: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['dispute', 'chosen', 'why'],
        properties: { dispute: { type: 'string' }, chosen: { type: 'string' }, why: { type: 'string' } },
      },
    },
    ownerConcerns: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['kind', 'concern', 'evidence'],
        properties: { kind: { type: 'string', enum: OWNER_CONCERN_KINDS }, concern: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}
const MAINTAIN_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['changedFiles', 'createdFiles', 'deletedFiles', 'viewsChecked', 'constraintIssues', 'contradictions', 'summary'],
  properties: {
    changedFiles: { type: 'array', items: { type: 'string' } },
    createdFiles: { type: 'array', items: { type: 'string' } },
    deletedFiles: { type: 'array', items: { type: 'string' } },
    viewsChecked: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['element', 'view', 'action'],
        properties: { element: { type: 'string' }, view: { type: 'string' }, action: { type: 'string', enum: ['updated', 'deleted', 'added', 'unaffected'] } },
      },
    },
    constraintIssues: { type: 'array', items: { type: 'string' } },
    contradictions: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
}
const CONFORMANCE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['conforms', 'reviewedFiles', 'findings', 'coverageRevision', 'coverageChecks', 'summary'],
  properties: {
    conforms: { type: 'boolean' },
    coverageChecks: COVERAGE_CHECKS_SCHEMA,
    coverageRevision: { type: 'string' },
    reviewedFiles: { type: 'array', items: { type: 'string' } },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['file', 'finding', 'evidence'],
        properties: { file: { type: 'string' }, finding: { type: 'string' }, evidence: { type: 'string' } },
      },
    },
    summary: { type: 'string' },
  },
}

/** Returns the section 2 fingerprint, or { error }; with `keep`, section 2 is also copied aside for a restore. */
const constraintsSnapshot = (label, phaseName, keep) => depscore(label, phaseName, `arch-constraints --arch-root ${shq(archPath)}${keep ? ' --keep' : ''}`)
const sameSnapshot = (x, y) =>
  !!x && !!y && !x.error && !y.error && x.exists === y.exists && x.digest === y.digest && JSON.stringify(x.gitStatus || []) === JSON.stringify(y.gitStatus || [])
/** Returns null when section 2 is unchanged since `before`, else puts section 2 back from the copy and returns the failure. */
async function constraintsGuard(before, label, phaseName) {
  const after = await constraintsSnapshot(label, phaseName)
  if (sameSnapshot(before, after)) return null
  const restored = after && after.error ? null : await depscore(`${label}:restore`, phaseName, `arch-constraints-restore --arch-root ${shq(archPath)} --kept ${shq(before.kept)}`)
  const restoreNote = !restored ? '' : restored.error ? `; section 2 could not be put back: ${restored.error}` : `; section 2 was put back as it was (${listed(restored.written).length} file(s) written back, ${listed(restored.deleted).length} deleted)`
  const why = after && after.error
    ? `section 2 could not be fingerprinted after ${phaseName}: ${after.error}`
    : `a session wrote under ${CONSTRAINTS} during ${phaseName}; section 2 holds the owner's constraints and the pipeline never writes there (git status now: ${JSON.stringify((after && after.gitStatus) || [])})${restoreNote}`
  log(`Section 2: ${why}`)
  return { ok: false, stage: 'constraints-written', deterministicFailure: true, reason: why, error: why, before, after, restored }
}

/**
 * Fingerprints every file of arc42/, target/ and built/ with depscore.py arch-snapshot. The per-file
 * hashes stay on disk: `save` writes them to that file, and each file in `against` (a fingerprint
 * saved earlier) yields the files created, changed and deleted since it, in `diffs`, in that order.
 * Returns the result or { error }.
 */
async function treeSnapshot(label, phaseName, { save, against = [] } = {}) {
  const out = await depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)}${save ? ` --save ${shq(save)}` : ''}${against.map((f) => ` --against ${shq(f)}`).join('')}`)
  if (!out || out.error) return out || { error: 'no result' }
  if (against.length && (!Array.isArray(out.diffs) || out.diffs.length !== against.length)) return { error: 'depscore.py arch-snapshot printed no difference for a saved fingerprint' }
  return out
}
/** Returns diff `i` of a snapshot as absolute paths: { created, changed, deleted }. */
function treeDiff(snap, i) {
  const d = (snap && Array.isArray(snap.diffs) && snap.diffs[i]) || {}
  const abs = (rel) => `${archPath}/${rel}`
  return { created: listed(d.created).map(abs), changed: listed(d.changed).map(abs), deleted: listed(d.deleted).map(abs) }
}
const diffFiles = (d) => [...d.created, ...d.changed, ...d.deleted]

const before = await constraintsSnapshot('constraints:before', 'Survey', true)
if (!before || before.error || !hasText(before.kept)) {
  const why = `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}
const treeBefore = await treeSnapshot('tree:before', 'Survey', { save: TREE_START })
if (!treeBefore || treeBefore.error) {
  const why = `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}

let facts = await readFacts('resume:read-saved', 'Survey')
if (facts.error) {
  const why = `depscore.py arch-resume failed: ${facts.error}. The saved work of this step in ${WORK} could not be read; the step stops rather than redo finished work, and the saved files stay on disk for the next attempt (a file named above that is damaged can be deleted, and only its work is redone).`
  return {
    ok: false,
    stage: 'resume',
    headline: facts.exception ? `Architecture resume failed: ${facts.exception}` : `Architecture could not read its saved work in ${WORK}: ${facts.error}`,
    reason: why,
    error: why,
    // A Python exception is deterministic: every re-dispatch meets it again, so the owner is told.
    ...(facts.exception ? { deterministicFailure: true, requiredHumanActions: [`depscore.py arch-resume raised ${facts.exception} reading the saved architecture work in ${WORK}; every run of this Epic meets it again. Fix the cause (the script or the saved file it names), then re-run the Epic.`] } : {}),
    ...died('Survey'),
  }
}
const resumedFacts = facts

// ---------------------------------------------------------------- Survey
phase('Survey')
const savedSurvey = facts.survey && facts.survey.coverageSaved === true && facts.survey.saved === true && hasText(facts.survey.subject) ? facts.survey : null
let survey = savedSurvey ? { subject: savedSurvey.subject, capabilities: savedSurvey.capabilities } : null
if (survey) {
  log(`Survey: reused ${SURVEY_JSON}`)
} else {
  const repos = await run(
    `List every repository of this project: its name, the absolute path of its local checkout, its role (what it is for) and its lifecycle (for example active, deprecated, archived). Answer from your records and the live repositories. Change nothing.`,
    { label: 'survey:repositories', phase: 'Survey', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'low', schema: REPOS_SCHEMA }
  )
  if (!repos) return { ok: false, stage: 'survey', reason: 'the polyrepo-steward named no repositories', ...died('Survey') }
  const surveyed = await run(
    `You are the prd-reality-reconciler, SURVEYING for the architecture step. The architecture team designs from your survey; you design nothing. If the survey already exists, preserve its facts and subject and supplement only missing coverage evidence; do not discard prior work.

PRD: ${prdRef}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

THE REPOSITORIES, from the polyrepo-steward (use these facts as given; do not look for repositories yourself):
${JSON.stringify(repos.repositories, null, 2)}

THE OPEN BEADS are in the beads database of ${DS.repo}. Read them with \`bd\` run from that directory, read-only (\`bd list\`, \`bd show\`, \`bd search\`); write nothing to beads.

For EACH capability the PRD needs, report:
- \`effectiveViews\`: the absolute paths of the effective views (under ${ARC42}) that show it, found through the catalog;
- \`code\`: the code that implements it on \`main\`, as \`<repo>:<path>:<line>\`;
- \`openBeads\`: the ids of open Stories and Tasks of other Epics that plan work on it;
- \`openTargets\`: the paths of open targets under ${archPath}/target/ that change it;
- \`requirements\`: the PRD requirement headings it serves.
An empty list is an answer: say in \`notes\` where you looked.

Name the \`subject\` the target will describe: the feature, service, component or layer this PRD changes, named as the glossary and the repositories name it — never the PRD, the Epic, a bead id or a date — and say why in \`subjectReason\`. Give the name as it is written (\`Company Intelligence\` and \`company-intelligence\` are both fine): the run derives the \`target/<subject>/\` folder name from it (lower-case, every run of other characters one hyphen).
${PRD_RULE}
${BUSINESS_CONFLICT_RULE}
Write survey.md as the readable survey and survey.json as your structured result.${persistBrief([SURVEY_MD, SURVEY_JSON], 'the survey: survey.md as one Markdown document, and survey.json as your complete structured result, exactly as you return it')}`,
    { label: 'survey:reality', phase: 'Survey', agentType: 'prd-reality-reconciler', effort: 'medium', schema: SURVEY_SCHEMA }
  )
  if (!surveyed) return { ok: false, stage: 'survey', reason: 'the prd-reality-reconciler returned no survey', ...died('Survey') }
  survey = { subject: surveyed.subject, capabilities: Array.isArray(surveyed.capabilities) ? surveyed.capabilities.length : 0 }
}
facts = await readFacts('survey:coverage-facts', 'Survey')
if (facts.error) return { ok: false, stage: 'survey', reason: facts.error }
/** Where the survey is; failures name the files, never carry the survey. */
const surveyPaths = { surveyPath: SURVEY_MD, surveyJsonPath: SURVEY_JSON }
// The subject as named; depscore.py arch-target derives the folder name every later step uses.
const subjectName = hasText(a.subject) ? a.subject.trim() : hasText(survey.subject) ? survey.subject.trim() : ''
/** Checks the draft with depscore.py arch-target --dry-run; the full report goes to TARGET_CHECK and only its summary comes back. Returns the summary or { error }. */
async function checkDraft(label, phaseName, subjectArg) {
  const out = await depscore(label, phaseName, `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subjectArg)} --forbid ${shq(FORBID.join(','))} --dry-run --out ${shq(TARGET_CHECK)}`)
  if (!out || out.error) return out || { error: 'no result' }
  return out.summary && typeof out.summary === 'object' ? out.summary : { error: 'depscore.py arch-target printed no summary' }
}
const subjectCheck = await checkDraft('target:check-subject', 'Survey', subjectName || '-')
const subjectRefusals = subjectCheck && !subjectCheck.error ? listed(subjectCheck.subjectRefusals) : []
const subject = subjectCheck && !subjectCheck.error && hasText(subjectCheck.subject) ? subjectCheck.subject.trim() : ''
if (!subjectName || subjectRefusals.length || !subjectCheck || subjectCheck.error || !subject) {
  const why = !subjectName
    ? 'the survey named no subject for the target'
    : subjectRefusals.length
      ? `the target subject cannot name a target: ${subjectRefusals.join('; ')}`
      : `the target subject could not be checked: ${(subjectCheck && subjectCheck.error) || 'no folder name returned'}`
  return { ok: false, stage: 'survey', deterministicFailure: subjectRefusals.length > 0, reason: why, error: why, ...surveyPaths }
}
log(`Survey: subject ${subjectName} (folder target/${subject}/); ${Number(survey.capabilities) || 0} capabilit(ies)`)

// ---------------------------------------------------------------- Rounds
// The claim and finding ledger lives on disk: depscore.py arch-resume folds every saved round result
// into ledger.json and returns only the facts below. Sessions read the ledger by its path.
let lastRound = Number(facts.rounds.last) || 0
/** Every re-dispatch after a failed or empty result, with what changed in its input. */
const retries = []
/** Each finding id handed to a writer to answer: { agentType, round, clarified }. */
const asked = new Map()
let silentLast = []
/** The reviewers that check every design before a decision, with one cost reviewer; the pattern challenger provides targeted critique only when needed. */
const ON_DEMAND_REVIEWERS = ['architecture-pattern-challenger']
const REQUIRED_CHALLENGERS = Object.keys(ROSTER.reviewer).filter((r) => !ON_DEMAND_REVIEWERS.includes(r))
const ledgerFacts = () => facts.rounds
const writersSoFar = () => listed(ledgerFacts().writers)
const openFindings = () => (Array.isArray(ledgerFacts().openFindings) ? ledgerFacts().openFindings : []).filter((f) => f && hasText(f.id))
/** The number of claims without a reviewer verdict, by writer. */
const unreviewedByWriter = () => Object.entries(ledgerFacts().unreviewedClaims || {}).filter(([, k]) => Number(k) > 0)
const unreviewedCount = () => unreviewedByWriter().reduce((t, [, k]) => t + Number(k), 0)
const ledgerLine = () => `${Number(ledgerFacts().claims) || 0} claim(s), ${Number(ledgerFacts().findings) || 0} finding(s), ${openFindings().length} open, ${unreviewedCount()} claim(s) without a reviewer verdict`
if (lastRound) log(`Rounds: resumed after round ${lastRound} — ${ledgerLine()}`)

/** Returns what still stands between the draft and a decision. */
async function decisionGaps(label) {
  const gaps = [...listed(facts.coverage && facts.coverage.gaps)]
  const proposed = writersSoFar().some((w) => roleOf(w) === 'proposer')
  if (!proposed) gaps.push('no proposer has written the target yet')
  for (const f of openFindings()) gaps.push(`finding ${f.id} (${f.verdict}) on ${f.file || 'the draft'} ${f.answered ? 'awaits independent resolution of its answer' : 'needs a bounded evidenced repair'}; owner ${f.owner || 'not known — assign it to a writer'}`)
  for (const [w, k] of unreviewedByWriter()) gaps.push(`${k} claim(s) by ${w} have no reviewer verdict (the claims by ${w} in ${LEDGER_JSON} whose \`verdicts\` list is empty)`)
  for (const w of listed(ledgerFacts().proposersWithoutClaims)) gaps.push(`proposer ${w} stated no claims: a design with no claims cannot be reviewed; it states the claims a reviewer checks`)
  if (proposed) {
    const reviewed = listed(ledgerFacts().reviewers)
    for (const r of REQUIRED_CHALLENGERS) if (!reviewed.includes(r)) gaps.push(`reviewer ${r} has not reviewed the design`)
    if (!Object.keys(ROSTER.cost).some((r) => reviewed.includes(r))) gaps.push('no cost reviewer has reviewed the design')
  }
  const check = await checkDraft(label, 'Rounds', subject)
  if (!check || check.error) gaps.push(`the draft could not be checked: ${(check && check.error) || 'no result'}`)
  else for (const r of listed(check.refusals)) gaps.push(`draft: ${r}`)
  return gaps
}

/** The saved decision's facts: { verdict, round, returnTo: [agent], ownerConcerns: count, ownerConcernKinds, ownerOnly }. */
const savedDecision = facts.decision && typeof facts.decision === 'object' && hasText(facts.decision.verdict) ? facts.decision : null
const savedCoverageValid = !!(savedDecision && !facts.rounds.pendingPlan && !openFindings().length && !unreviewedCount() && facts.coverage && !facts.coverage.gaps.length && savedDecision.coverageRevision === facts.coverage.revision)
let decision = savedDecision && savedDecision.verdict === 'approve' && savedCoverageValid ? savedDecision : null
// Legacy approval gets one bounded supplemental round, retaining its prior work.
const roundLimit = MAX_ROUNDS + (savedDecision && savedDecision.verdict === 'approve' && (!savedDecision.coverageRevision || resumedFacts.contractVersion !== 2) ? 1 : 0)
/** Returns the proposers a decision returned the target to, each { agentType }; what is missing is in the decision file they read. */
const returnedTo = (dec) =>
  (dec && Array.isArray(dec.returnTo) ? dec.returnTo : [])
    .map((r) => (typeof r === 'string' ? r : r && r.agentType))
    .filter((r) => hasText(r) && roleOf(r.trim().replace(AGENT_PREFIX, '')) === 'proposer')
    .map((r) => ({ agentType: r.trim().replace(AGENT_PREFIX, '') }))
let forced = savedDecision && savedDecision.verdict === 'return' && !(lastRound > (savedDecision.round || 0)) ? returnedTo(savedDecision) : []
let rejected = []
let pendingGaps = []

/** Returns the owner-concern result that holds the Epic for the owner. A decision read back from disk carries only the count and kinds; the owner reads the concerns in the decision file. */
function ownerConcern(dec) {
  const concerns = Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns.filter((c) => c && hasText(c.concern)) : null
  const count = concerns ? concerns.length : Number(dec.ownerConcerns) || 0
  return {
    ok: false,
    stage: 'owner-concern',
    reason: `the architecture-decider raised ${count} owner concern(s) on ${subject}`,
    ...(concerns ? { ownerConcerns: concerns } : { ownerConcernKinds: listed(dec.ownerConcernKinds) }),
    requiredHumanActions: [
      ...(concerns
        ? concerns.map((c) => `${c.kind === 'architecture-conflict' ? 'CONTRADICTION IN THE ARCHITECTURE' : 'CONFLICTING BUSINESS REQUIREMENTS'} on ${subject}: ${c.concern} — evidence: ${c.evidence}`)
        : [`The architecture-decider raised ${count} owner concern(s) on ${subject} (${listed(dec.ownerConcernKinds).join(', ')}): read them in ${DECISION_MD}.`]),
      `Once the PRD or the architecture says which side holds, delete ${DECISION_JSON}: while it holds these concerns, every run of the architecture step holds the Epic again.`,
    ],
    decision: dec,
    decisionPath: DECISION_MD,
    subject,
    ...surveyPaths,
  }
}
/** True when the last decision escalated issues the team resolves itself; the coordinator reads them in the decision file. */
let teamNotes = false
/** True when every owner concern of a decision is one of the two cases that reach the owner: irreconcilable business requirements, or an architecture that contradicts itself where common sense cannot settle it. */
const businessOnly = (dec) => {
  if (typeof dec.ownerOnly === 'boolean') return dec.ownerOnly
  const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
  return concerns.length > 0 && concerns.every((c) => OWNER_CONCERN_KINDS.includes(c.kind))
}
if (savedDecision && savedDecision.verdict === 'owner-concern') {
  if (businessOnly(savedDecision)) {
    log('Decide: the saved decision holds conflicting business requirements; the Epic is held again')
    return ownerConcern(savedDecision)
  }
  log('Decide: the saved decision escalated what the team decides itself; it is set aside and the team resolves it')
  teamNotes = Number(savedDecision.ownerConcerns) > 0
}

/** Returns the prompt for one writer or reviewer dispatch. */
function dispatchPrompt(n, d, file) {
  const answersBlock = d.answers.length
    ? `\nFINDINGS YOU ANSWER THIS ROUND: ${d.answers.join(', ')}. Read each in the \`findings\` list of the ledger ${LEDGER_JSON} (its verdict, the claim, the file and the reviewer's evidence), and answer every one in \`answers\` by its id: \`fixed\` (name the change you made) or \`disputed\` (with your evidence).\n`
    : ''
  const shared = `PRD: ${prdRef}

${PRD_RULE}

${ARCH_WHERE}

${INPUTS_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}

THE SURVEY is ${SURVEY_MD} (readable) and ${SURVEY_JSON} (structured): read it first. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
EARLIER RESULTS of this step are in ${ROUNDS_DIR}; read the ones that touch your work.`
  if (WRITER_ROLES.includes(d.role)) {
    const work = d.role === 'proposer'
      ? `Consolidate the retained target across all affected concerns, using your expertise (${ROSTER.proposer[d.agentType]}), existing source evidence and the settled mechanism. Revise the existing design; do not reopen settled choices or create a proposal per concern. Work from the effective version, at every scope the change reaches (system, domain, service, component, concept), as views of the types in ${MENU}: diagrams and prose. Write the target views and the delta views for it into the draft. A design that departs from an established pattern states its reason and evidence in the view's prose.`
      : `Draw the views your task names (${ROSTER.diagram[d.agentType]}) into the draft, from the design the proposers wrote there. Depict nothing that design does not contain.`
    return `You are the ${d.agentType}, a writer on the architecture team for this PRD, round ${n}. ${work}

YOUR TASK THIS ROUND, from the coordinator: ${d.task}
${d.files.length ? `THE DRAFT FILES YOU OWN THIS ROUND, relative to ${DRAFT} (write only these; other sessions may be writing the rest):\n${d.files.map((f) => `- ${f}`).join('\n')}` : 'You were named no draft files this round: change no view another writer owns, and name every file you write in `files`.'}
${answersBlock}
${shared}

${DRAFT_RULES}

Use claimId="" for a new claim or the existing ledger id for an explicit revision. Keep unchanged ids; supersedes lists only deliberately replaced claims you own. Cite evidenceRefs and do not silently discard findings. A writer answer proposes a fix/dispute; independent resolution is still required. Return in \`files\` every draft file you wrote, relative to ${DRAFT}. Return in \`claims\` every claim your views make that a reviewer must check — about AWS (cite the documentation page you read), the code (cite repository, path and line on \`main\`), or the architecture (cite the view path and heading) — each with the draft file it is in. A design with no claims cannot be reviewed and cannot be approved: state every claim a reviewer must check. ${BUSINESS_CONFLICT_RULE}${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
  }
  const assignedClaims = Array.isArray(d.assignedClaims) ? d.assignedClaims : []
  return `You are the ${d.agentType}, a ${d.role === 'cost' ? 'cost reviewer' : 'reviewer'} on the architecture team for this PRD, round ${n}: ${ROSTER[d.role][d.agentType]}.

YOUR TASK THIS ROUND, from the coordinator: ${d.task}

THE DRAFT TARGET is ${DRAFT} (target views in the arc42 section layout, the change alone in \`delta/\`). Read it; write nothing in it and nothing in ${archPath}.

${shared}

THE LEDGER is ${LEDGER_JSON}: every claim the writers stated (\`claims\`, each with its \`id\`, writer, draft file, citation and the \`verdicts\` given so far) and every finding. Read it; write nothing in it.
YOUR ASSIGNED CLAIM REVISIONS: ${JSON.stringify(assignedClaims)}. Check exactly these claims against their citations with independent evidence and copy id/revision into claimId/claimRevision. Do not repeat unrelated verified claims. When none are assigned, answer only your coordinator's bounded domain question and affected dependencies; do not start a blanket audit.
Return verified, unsupported or wrong with evidence. Check coverage IDs named in your task at their current ledger revisions. For answered findings within your assigned scope, return resolutions with findingId, the ledger finding's current resolutionRevision as revision, accepted/rejected and independent evidence: accept fixed only after verifying the changed evidence/view, and disputed only when evidence refutes the original finding. An unsupported assertion never resolves a finding. A new concrete uncovered problem uses empty claimId/claimRevision and names its writer as owner.${d.role === 'cost' ? ' State your estimates, with the unit math, in `estimates`; a cost the design does not support is a finding like any other.' : ''}${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
}

/** Groups writers so no two in one wave own the same draft file; a writer naming no file runs alone. */
function writerWaves(list) {
  const waves = []
  for (const d of list) {
    const wave = d.files.length ? waves.find((w) => !w.solo && d.files.every((f) => !w.files.has(f))) : null
    if (wave) {
      wave.items.push(d)
      d.files.forEach((f) => wave.files.add(f))
    } else {
      waves.push({ solo: !d.files.length, items: [d], files: new Set(d.files) })
    }
  }
  return waves
}

const cleanFile = (f) => String(f || '').trim().replace(/^\/+/, '')
const agentName = (x) => String(x || '').trim().replace(AGENT_PREFIX, '')
/** The plan's overlap entries that state a reason, normalized as they are saved. */
const planOverlaps = (plan) =>
  (Array.isArray(plan && plan.overlaps) ? plan.overlaps : [])
    .filter((o) => o && hasText(o.reason))
    .map((o) => ({ files: listed(o.files).map(cleanFile), claimIds: listed(o.claimIds), agentTypes: listed(o.agentTypes).map(agentName), reason: o.reason.trim() }))
/**
 * Returns, for each claim id or draft file that two or more review dispatches of the plan share,
 * a refusal when no `overlaps` entry with a reason names it (and, when the entry names agentTypes,
 * every reviewer sharing it). An empty list means the plan states a reason for every overlap.
 */
function unjustifiedOverlaps(plan) {
  const holders = new Map()
  for (const d of Array.isArray(plan && plan.dispatches) ? plan.dispatches : []) {
    const name = agentName(d && d.agentType)
    if (!REVIEW_ROLES.includes(roleOf(name)) || roleOf(name) !== d.role) continue
    const items = [...listed(d.claimIds).map((i) => `claim ${i}`), ...listed(d.claimFiles).map(cleanFile).filter(Boolean).map((f) => `draft file ${f}`)]
    for (const item of items) {
      const names = holders.get(item) || new Set()
      names.add(name)
      holders.set(item, names)
    }
  }
  const entries = planOverlaps(plan)
  const refusals = []
  for (const [item, names] of holders) {
    if (names.size < 2) continue
    const sharing = [...names]
    const covered = entries.some((o) =>
      (!o.agentTypes.length || sharing.every((x) => o.agentTypes.includes(x))) &&
      (item.startsWith('claim ') ? o.claimIds.includes(item.slice(6)) : o.files.includes(item.slice(11))))
    if (!covered) refusals.push(`${item} is assigned to ${sharing.join(', ')} and no \`overlaps\` entry names it with a reason`)
  }
  return refusals
}
const MAX_PLAN_FIXES = 2

/** Validates the coordinator's dispatches and adds those the ledger requires; returns { dispatches, rejected, stuck }. */
function settleDispatches(plan, n) {
  const out = []
  const bad = []
  for (const d of Array.isArray(plan.dispatches) ? plan.dispatches : []) {
    const name = d && hasText(d.agentType) ? d.agentType.trim().replace(AGENT_PREFIX, '') : ''
    const role = roleOf(name)
    if (!role || role !== d.role) {
      bad.push(`${name || '(no agent)'} as ${d && d.role}: not that role's roster`)
      continue
    }
    const files = WRITER_ROLES.includes(role) ? listed(d.files).map(cleanFile) : []
    const badFile = files.find((f) => !f || f.split('/').includes('..') || f.split('/').includes('02-architecture-constraints'))
    if (badFile !== undefined) {
      bad.push(`${name}: draft file ${JSON.stringify(badFile)} is outside the draft or in section 2`)
      continue
    }
    const answers = WRITER_ROLES.includes(role) ? listed(d.answers) : []
    for (const id of answers) {
      const f = openFindings().find((x) => x.id === id && !x.owner)
      if (f) {
        f.owner = name
        assigned.set(id, name)
      }
    }
    const same = out.find((x) => x.agentType === name)
    if (same) {
      same.task = `${same.task}\n${d.task}`
      same.files = [...new Set([...same.files, ...files])]
      same.answers = [...new Set([...same.answers, ...answers])]
      same.claimIds = [...new Set([...same.claimIds, ...listed(d.claimIds)])]
      same.claimFiles = [...new Set([...same.claimFiles, ...listed(d.claimFiles).map(cleanFile)])]
    } else {
      out.push({ agentType: name, role, task: String(d.task || ''), files, answers, claimIds: listed(d.claimIds), claimFiles: listed(d.claimFiles).map(cleanFile) })
    }
  }
  const legacyMissing = listed(ledgerFacts().legacyProposersWithoutClaims)
  if (legacyMissing.length) {
    const lead = facts.proposalTeam.lead
    const task = `Consolidate the retained drafts and results from ${legacyMissing.join(', ')}: they stated no reviewable claims. Inspect their existing work and its evidence, repair gaps, and state the consolidated claims for independent review; do not merely repeat earlier claims.`
    const same = out.find((d) => d.agentType === lead)
    if (same) same.task += `\n${task}`
    else out.push({ agentType: lead, role: 'proposer', task, files: [], answers: [] })
  }
  for (const d of out) d.answers = d.answers.filter((id) => openFindings().some((f) => f.id === id && f.owner === d.agentType))
  for (const r of forced) {
    const role = roleOf(r.agentType)
    if (!role || !WRITER_ROLES.includes(role)) continue
    const recipient = role === 'proposer' ? facts.proposalTeam.lead : r.agentType
    const same = out.find((x) => x.agentType === recipient)
    const task = `The architecture-decider returned the target to you. Read \`returnTo\` in ${DECISION_JSON} (the decision in full is ${DECISION_MD}) for the due diligence it names as missing from your design, and supply it.`
    if (same) same.task = `${same.task}\n${task}`
    else out.push({ agentType: recipient, role, task, files: [], answers: [] })
    retries.push({ step: `round${n}:${r.agentType}`, whatChanged: `the architecture-decider returned the target naming missing due diligence (in ${DECISION_JSON})` })
  }
  for (const f of openFindings()) {
    if (f.answered || !f.owner || out.some((x) => x.agentType === f.owner && x.answers.includes(f.id))) continue
    const same = out.find((x) => x.agentType === f.owner)
    if (same) same.answers.push(f.id)
    else out.push({ agentType: f.owner, role: roleOf(f.owner), task: 'Answer the findings named below.', files: [], answers: [f.id] })
  }
  // A finding handed back to the writer that left it unanswered is re-sent once, with that named in its
  // task; still unanswered after that, it is not sent a third time.
  const stuck = []
  for (const d of out) {
    const again = d.answers.filter((id) => asked.has(id) && asked.get(id).agentType === d.agentType)
    if (!again.length) continue
    const repeated = again.filter((id) => asked.get(id).clarified)
    if (repeated.length) {
      stuck.push(`${d.agentType}: ${repeated.join(', ')}`)
      continue
    }
    const prev = Math.max(...again.map((id) => asked.get(id).round))
    const result = silentLast.includes(d.agentType) ? 'never came back' : 'answered none of them'
    d.task = `${d.task}\nROUND ${prev} HANDED YOU finding(s) ${again.join(', ')}, and your result ${result}. Answer each one in \`answers\` this round, as \`fixed\` or \`disputed\`.`
    d.clarified = again
    retries.push({ step: `round${n}:${d.agentType}`, findings: again, whatChanged: `round ${n} tells ${d.agentType} that its round ${prev} result ${result} for finding(s) ${again.join(', ')}` })
  }
  const proposers = out.filter((d) => d.role === 'proposer')
  const allowed = [facts.proposalTeam.lead, facts.proposalTeam.second].filter(Boolean)
  if (proposers.length > 2 || proposers.some((d) => !allowed.includes(d.agentType))) {
    return { dispatches: [], rejected: [...bad, 'proposal budget: only the retained lead and justified second may write proposals'], stuck, budgetError: true }
  }
  return { dispatches: out, rejected: bad, stuck }
}

/**
 * Runs one round's dispatches: writers in waves of disjoint files, then reviewers together. The
 * ledger is folded again from the saved results after the writers, so the reviewers read this
 * round's claims, and after the reviewers. Returns { silent } (the dispatches with no result, or
 * whose result was not saved) or { error } when the saved results could not be read.
 */
async function runRound(n, dispatches) {
  // Last boundary before any agent call; automatic returns and legacy owners cannot bypass it.
  const proposers = dispatches.filter((d) => d.role === 'proposer')
  const team = facts.proposalTeam || {}
  if (proposers.length > 2 || new Set(proposers.map((d) => d.agentType)).size !== proposers.length || proposers.some((d) => ![team.lead, team.second].filter(Boolean).includes(d.agentType))) {
    return { error: 'proposal budget exceeded; saved work retained, no round agents dispatched' }
  }
  const writing = dispatches.filter((d) => WRITER_ROLES.includes(d.role))
  const reviewing = dispatches.filter((d) => REVIEW_ROLES.includes(d.role))
  let ordered = [...writing, ...reviewing].map((d, i) => ({ ...d, seq: d.seq || i + 1, file: `${ROUNDS_DIR}/r${n}-${i + 1}-${d.role}-${d.agentType}.json` }))
  const go = (d) => () =>
    run(dispatchPrompt(n, d, d.file), {
      label: `round${n}:${d.role}:${d.agentType}`,
      phase: 'Rounds',
      agentType: dispatchName(d.agentType),
      effort: d.role === 'proposer' ? 'high' : 'medium',
      schema: WRITER_ROLES.includes(d.role) ? WRITER_SCHEMA : REVIEW_SCHEMA,
    })
  const results = new Map()
  for (const wave of writerWaves(ordered.filter((d) => WRITER_ROLES.includes(d.role) && !d.complete))) {
    const got = await parallel(wave.items.map(go))
    wave.items.forEach((d, i) => results.set(d.seq, got[i]))
    if (dispatchInterruption) return { silent: wave.items.filter((d, i) => !got[i]).map(d => d.agentType) }
  }
  if (facts.rounds.pendingPlan) ordered = facts.rounds.pendingPlan.dispatches
  let reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
  if (reviewers.length) {
    if (ordered.length > reviewers.length) {
      const mid = await readFacts(`round${n}:ledger-writers`, 'Rounds')
      if (mid.error) return { error: mid.error, exception: mid.exception }
      facts = mid
      if (mid.rounds.pendingPlan && mid.rounds.pendingPlan.dispatches.some(d => WRITER_ROLES.includes(d.role) && !d.complete)) return { silent: mid.rounds.pendingPlan.dispatches.filter(d => WRITER_ROLES.includes(d.role) && !d.complete).map(d => d.agentType) }
      ordered = mid.rounds.pendingPlan ? mid.rounds.pendingPlan.dispatches : ordered
      reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role) && !d.complete)
    }
    const got = await parallel(reviewers.map(go))
    reviewers.forEach((d, i) => results.set(d.seq, got[i]))
  }
  const after = await readFacts(`round${n}:ledger`, 'Rounds')
  if (after.error) return { error: after.error, exception: after.exception }
  facts = after
  const savedKeys = listed(facts.rounds.saved)
  const unsaved = ordered.filter((d) => results.get(d.seq) && !savedKeys.includes(`r${n}-${d.seq}`))
  if (unsaved.length) log(`Round ${n}: ${unsaved.map((d) => d.agentType).join(', ')} returned a result but did not save it to its result file; it counts as no result`)
  return { silent: ordered.filter((d) => !savedKeys.includes(`r${n}-${d.seq}`)).map((d) => d.agentType) }
}

/** Runs the decider over the artifacts; returns its decision or null. */
async function decide(n) {
  phase('Decide')
  const dec = await run(
    `You are the architecture-decider. Decide whether the draft target below is approved. You produced none of it, and you decide from the artifacts alone: read them.

ARTIFACTS:
- the PRD: ${hasText(prd.path) ? prd.path : '(inline — see the survey)'}
- the survey: ${SURVEY_MD} and ${SURVEY_JSON}
- every result of every round: the files in ${ROUNDS_DIR}, and the claim and finding ledger folded from them: ${LEDGER_JSON}
- the draft target and its delta: ${DRAFT}
- the effective version, with the owner's constraints in section 2: ${ARC42}; open targets: ${archPath}/target/

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Read all coverage rows and independent checks in ${LEDGER_JSON}; check completeness against the MODEL, not only existing catalog hits. Set coverageRevision to the ledger's coverageRevision. Approval requires resolved relevant obligations with independent current-content evidence; never approve from an aggregate boolean.

The team has designed, challenged and settled this target in its rounds, led by the coordinator. You are not its lead: you approve its result, and you choose only where the team left competing solutions it could not settle.

CHECK THAT THE DUE DILIGENCE IS PRESENT, item by item in \`diligence\`: every claim reviewed with evidence and every finding answered; the target shows every changed element at every scope where the effective version shows it; the delta shows the change; the owner's constraints in section 2 are honoured; the open targets that show the same elements were read and are not contradicted; a departure from an established pattern states its reason and evidence.

COMPETING SOLUTIONS: where findings stand disputed, or a reviewer's alternative was argued with evidence and not adopted, choose between them in \`choices\`: what was in dispute, the option you chose, and why, from the evidence in the artifacts and the product's priorities (the seeker's privacy and data protection first). A choice is part of an approval, not a reason to escalate.

VERDICT:
- \`approve\` when the diligence is present, with every choice you made in \`choices\`.
- \`return\` only when a proposer's due diligence is missing: name each one in \`returnTo\` (one of ${Object.keys(ROSTER.proposer).join(', ')}) with exactly what is missing. A technical value the PRD leaves open is not missing diligence when the team chose it with a reason.
- \`owner-concern\` is the last resort, for two cases only, each in \`ownerConcerns\` with its evidence: kind \`business-conflict\`, two BUSINESS requirements of the PRD that no design whatsoever could satisfy together, shown by the team's own analysis; or kind \`architecture-conflict\`, the architecture contradicting itself where common sense cannot settle which side holds — owner's constraints in section 2 that contradict each other or that no design can meet together with the PRD, or effective views that make competing statements with nothing to show which is current. Never escalate a "how" in the PRD, an open technical value, a security, privacy, cost or best-practice question (the team designs those), or a difference from the effective version.
Set \`round\` to ${n}.

Write ${DECISION_MD} (your decision as one readable Markdown document) and ${DECISION_JSON} (your complete structured result, exactly as you return it, as ONE JSON object) with the Write tool, replacing each if it exists (Read it first if the Write tool asks). Write no other file.`,
    { label: `decide:round${n}`, phase: 'Decide', agentType: 'agent-teams-workforce:architecture-decider', effort: 'high', schema: DECISION_SCHEMA }
  )
  if (dec) await recordFiles('decide:record', 'Decide', [DECISION_MD, DECISION_JSON])
  return dec
}

phase('Rounds')
let ready = !!(savedDecision && savedDecision.verdict === 'approve') || facts.rounds.readyForDecision === true
while (!decision) {
  if (ready) {
    pendingGaps = await decisionGaps(`rounds:gaps-${lastRound}`)
    if (!pendingGaps.length) {
      const dec = await decide(lastRound)
      if (!dec) return { ok: false, stage: 'decide', reason: 'the architecture-decider returned nothing', ...died('Decide'), subject, ...surveyPaths }
      const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
      if (dec.verdict === 'owner-concern' || concerns.length) {
        if (!concerns.length) return { ok: false, stage: 'decide', reason: 'the architecture-decider raised an owner concern and named none', decision: dec, subject }
        if (businessOnly(dec)) return ownerConcern(dec)
        teamNotes = true
        log(`Decide: ${concerns.length} issue(s) escalated that the team decides itself; they go back to the team`)
        phase('Rounds')
        ready = false
        continue
      }
      if (dec.verdict === 'approve') {
        const approvedFacts = await readFacts('decide:coverage-check', 'Decide')
        if (approvedFacts.error || !approvedFacts.rounds || approvedFacts.rounds.pendingPlan || (approvedFacts.rounds.openFindings || []).length || Object.values(approvedFacts.rounds.unreviewedClaims || {}).some(k => k > 0) || !approvedFacts.coverage || approvedFacts.coverage.gaps.length || dec.coverageRevision !== approvedFacts.coverage.revision || !approvedFacts.decision || approvedFacts.decision.coverageRevision !== dec.coverageRevision) {
          return { ok: false, stage: 'decide', reason: 'approval lacks saved independent coverage evidence for the current views; saved work retained', subject }
        }
        facts = approvedFacts
        decision = dec
        break
      }
      forced = returnedTo(dec)
      if (!forced.length) return { ok: false, stage: 'decide', reason: 'the architecture-decider returned the target to no proposer on its roster', decision: dec, subject }
      log(`Decide: returned to ${forced.map((f) => f.agentType).join(', ')}`)
      phase('Rounds')
    }
    ready = false
  }
  if (!facts.rounds.pendingPlan && lastRound >= roundLimit) {
    const gaps = pendingGaps.length ? pendingGaps : await decisionGaps('rounds:gaps-final')
    const why = `${roundLimit} round(s) ran and the target is not ready for a decision: ${gaps.join('; ') || 'the coordinator never declared it ready'}`
    log(`Rounds: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, gaps, subject, ...surveyPaths, ...died('Rounds') }
  }
  const pendingPlan = facts.rounds.pendingPlan
  const n = pendingPlan ? pendingPlan.round : lastRound + 1
  if (!pendingGaps.length && n > 1) pendingGaps = await decisionGaps(`rounds:gaps-${n - 1}`)
  const coordinatorBrief = `You are the architecture-decision-workflow-coordinator. Name the dispatches for round ${n} of at most ${roundLimit}; the script runs them. You read and route; you design, review and decide nothing, write nothing, and dispatch nothing yourself.

PRD: ${prdRef}
THE SURVEY: ${SURVEY_MD} and ${SURVEY_JSON}. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
THE DRAFT TARGET: ${DRAFT} (arc42 section layout; \`delta/\` holds the change alone).
EARLIER RESULTS: ${ROUNDS_DIR}.
THE ARCHITECTURE: ${archPath} (\`arc42/\` effective; \`target/\` open targets).

THE ROSTER (role: agent — what it covers):
${rosterText}

THE LEDGER is ${LEDGER_JSON}: every claim with its reviewer verdicts, and every finding with its owner and answer, folded from the saved results. Read it. So far: ${ledgerLine()}.

WHAT STANDS BETWEEN THE DRAFT AND A DECISION:
${pendingGaps.length ? pendingGaps.map((g) => `- ${g}`).join('\n') : n === 1 ? '- nothing is written yet' : '- nothing'}
${teamNotes ? `\nISSUES FOR THE TEAM TO RESOLVE IN ITS DESIGN were raised at the decision: they are the \`ownerConcerns\` in ${DECISION_JSON} (readable in ${DECISION_MD}). Read them and route each to the writers it concerns, and to reviewers.\n` : ''}${forced.length ? `\nTHE ARCHITECTURE-DECIDER RETURNED THE TARGET to: ${forced.map((f) => f.agentType).join(', ')}; what each is missing is in \`returnTo\` of ${DECISION_JSON}. The retained lead consolidates this missing diligence; do not reinstate legacy specialist fanout.` : ''}${rejected.length ? `\nDISPATCHES REFUSED LAST ROUND: ${rejected.join('; ')}` : ''}${silentLast.length ? `\nDISPATCHES THAT RETURNED NOTHING LAST ROUND: ${silentLast.join(', ')}` : ''}

${PRD_RULE}

${COVERAGE_RULE}

${DESIGN_REVIEW_STANDARD}
Assign coverage ids explicitly in each writer/reviewer task. Coverage gaps in the ledger are work to route, including absent views; do not restart unrelated completed design.

YOU LEAD THE TEAM to a consensus architecture. The architecture-decider is not part of the rounds: it sees the result only after the team has designed, challenged and settled it.

HOW TO ROUTE:
- Return proposalTeam: lead, second, unresolvedIssue, evidence, whySecond (empty strings for the optional second fields). Default one lead for the entire architecture effort, consolidating all concerns. Never more than two proposer identities across rounds. Retain this saved team: ${JSON.stringify(facts.proposalTeam || {})}. A second is exceptional: name the specific unresolved issue, its source/claim/finding evidence, and why the lead cannot resolve it alone; merely touching another concern is not justification. Once selected, identities cannot be replaced; later rounds revise their retained work. A PRD already served needs only a no-change delta.
- Do not split proposals among diagram authors, reviewers or renamed specialists. Diagram authors depict settled design only; reviewers critique without writing competing proposals. Reuse all legacy results as input to the lead, not instructions to redispatch their authors.
- Every design is reviewed before a decision by ${REQUIRED_CHALLENGERS.join(', ')} and by a cost reviewer; the list below names any that have not yet run.
- Dispatch ${ON_DEMAND_REVIEWERS.join(', ')} only for targeted critique of a concrete unresolved weakness; it does not create a competing design or add a proposer.
- When a competing alternative is proposed or a writer disputes a finding, route it back to the writers concerned so the team converges on one design; leave two designs standing only when the team has argued both with evidence and still disagrees.
- Give each writer dispatch the draft files it owns this round, relative to the draft folder; two writers in one round never own the same file.
- Give reviewers claimIds for existing claims and claimFiles for exact draft-relative files whose NEW/revised claims they will check after writers finish. Match file responsibility to reviewer expertise. Assigning the same claimId or claimFile to two or more reviewers is an overlap, and an overlap is one decision you make: state it once in \`overlaps\`, as one entry naming the shared \`files\` and \`claimIds\`, the reviewer \`agentTypes\` that share them, and the one \`reason\`. The reviewers' dispatches carry no reason. The script refuses a plan with an overlap no entry names, and sends it back to you; return \`overlaps: []\` when no two reviewers share anything. Unmatched claims remain gaps for the next normal round; no assignment-only agent pass. Keep each required reviewer's task a bounded domain question even with no claims.
- Every claim gets a reviewer verdict: dispatch reviewers for the claims not yet reviewed, and a cost reviewer for claims about cost.
- For answered findings, route independent resolution; do not send an unchanged accepted claim back to its maker. If a resolution rejects an answer, the next brief names the specific remaining defect and evidence from the ledger.
- Every unanswered open finding is answered by its owner: put its id in that writer's \`answers\`. A finding with no owner is yours to assign to a writer. Legacy proposer findings transfer to the retained lead; do not redispatch former owners outside proposalTeam.
- Dispatch diagram authors to draw the views the proposers describe, once the design is written.
- Writers run first and reviewers after them in the same round, so a reviewer sees this round's writing.
- Set \`readyForDecision\` true, with no dispatches, only when the list above says nothing stands between the draft and a decision.`
  let plan = pendingPlan
  // A plan is saved durably and never replaced, so an overlap with no stated reason is refused before it is saved.
  for (let fix = 0, refusal = ''; !pendingPlan; fix++) {
    plan = await run(`${coordinatorBrief}${refusal}`, { label: fix ? `round${n}:coordinate-fix${fix}` : `round${n}:coordinate`, phase: 'Rounds', agentType: 'agent-teams-workforce:architecture-decision-workflow-coordinator', effort: 'medium', schema: COORDINATOR_SCHEMA })
    const overlapRefusals = plan ? unjustifiedOverlaps(plan) : []
    if (!overlapRefusals.length) break
    if (fix >= MAX_PLAN_FIXES) {
      const why = `the architecture-decision-workflow-coordinator's plan for round ${n} assigns the same review work to several reviewers without stating why, after ${MAX_PLAN_FIXES} correction(s): ${overlapRefusals.join('; ')}. The plan was not saved.`
      log(`Round ${n}: ${why}`)
      return {
        ok: false,
        stage: 'round-plan',
        deterministicFailure: true,
        headline: `Architecture stopped: the coordinator's round ${n} plan has reviewer overlaps with no stated reason after ${MAX_PLAN_FIXES} corrections`,
        reason: why,
        error: why,
        requiredHumanActions: [`The architecture-decision-workflow-coordinator returned ${MAX_PLAN_FIXES + 1} plans for round ${n} of ${subject}, each assigning the same claims or draft files to several reviewers with no \`overlaps\` entry stating why: ${overlapRefusals.join('; ')}. No plan was saved. Check the overlap rule the coordinator is given (the coordinator brief in workflows/architecture.js), then re-run the Epic.`],
        subject,
        ...surveyPaths,
      }
    }
    log(`Round ${n}: plan refused — ${overlapRefusals.join('; ')}`)
    retries.push({ step: `round${n}:coordinate`, whatChanged: `the plan was refused for reviewer overlaps with no stated reason: ${overlapRefusals.join('; ')}` })
    refusal = `\n\nYOUR LAST PLAN FOR ROUND ${n} WAS REFUSED and nothing of it was saved: ${overlapRefusals.join('; ')}. Return the whole plan again. For each overlap you keep, add one \`overlaps\` entry naming the shared files and claimIds, the reviewers that share them, and the reason; or assign the shared work to one reviewer.`
  }
  if (!plan) return { ok: false, stage: 'rounds', reason: `the coordinator returned no plan for round ${n}`, ...died('Rounds'), subject, ...surveyPaths }
  const teamFacts = await readFacts(`round${n}:proposal-team`, 'Rounds', plan.proposalTeam)
  if (teamFacts.error || !teamFacts.proposalTeam || !teamFacts.proposalTeam.lead) return { ok: false, stage: 'rounds', reason: teamFacts.error || 'coordinator did not select a proposal lead; saved work retained', subject }
  facts = teamFacts
  const settled = pendingPlan ? { dispatches: pendingPlan.dispatches, rejected: [], stuck: [] } : settleDispatches(plan, n)
  if (settled.budgetError) return { ok: false, stage: 'rounds', reason: settled.rejected.join('; '), subject }
  rejected = settled.rejected
  forced = []
  teamNotes = false
  if (rejected.length) log(`Round ${n}: refused ${rejected.join('; ')}`)
  if (settled.stuck.length) {
    const why = `finding(s) stayed unanswered after their owner was told once that its result left them unanswered: ${settled.stuck.join('; ')}`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...surveyPaths, retries }
  }
  for (const r of retries.filter((x) => x.step.startsWith(`round${n}:`))) log(`Round ${n}: re-dispatch — ${r.whatChanged}`)
  if (!pendingPlan) {
    const orderedPlan = { round: n, proposalTeam: facts.proposalTeam, readyForDecision: plan.readyForDecision, overlaps: planOverlaps(plan), dispatches: [...settled.dispatches.filter(d => WRITER_ROLES.includes(d.role)), ...settled.dispatches.filter(d => REVIEW_ROLES.includes(d.role))] }
    const savedPlan = await readFacts(`round${n}:save-plan`, 'Rounds', null, orderedPlan)
    if (savedPlan.error) return { ok: false, stage: 'rounds', reason: savedPlan.error, subject }
    facts = savedPlan
    settled.dispatches = savedPlan.rounds.pendingPlan ? savedPlan.rounds.pendingPlan.dispatches : orderedPlan.dispatches
  }
  if (!settled.dispatches.length) {
    if (plan.readyForDecision === true) {
      lastRound = n
      ready = true
      continue
    }
    const why = `the coordinator dispatched nothing in round ${n} and did not declare the target ready: ${plan.reason || 'no reason given'}`
    return { ok: false, stage: 'rounds', reason: why, error: why, rejected, subject, ...surveyPaths }
  }
  log(`Round ${n}: ${settled.dispatches.map((d) => `${d.role}:${d.agentType}`).join(', ')}`)
  for (const d of settled.dispatches) for (const id of d.answers) asked.set(id, { agentType: d.agentType, round: n, clarified: (d.clarified || []).includes(id) })
  const roundRun = await runRound(n, settled.dispatches)
  if (roundRun.error) {
    const why = `depscore.py arch-resume failed after round ${n}: ${roundRun.error}. The saved results in ${ROUNDS_DIR} could not be read; the step stops, and the saved results stay on disk for the next attempt.`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', headline: roundRun.exception ? `Architecture round ${n} failed: ${roundRun.exception}` : `Architecture could not read the saved results of round ${n}: ${roundRun.error}`, reason: why, error: why, subject, ...surveyPaths }
  }
  const silent = roundRun.silent
  silentLast = silent
  if (silent.length) return { ok: false, resumable: true, stage: 'rounds', reason: `round ${n} has unfinished dispatches: ${silent.join(', ')}; saved work retained`, ...died('Rounds'), subject, ...surveyPaths }
  lastRound = n
  pendingGaps = []
  ready = plan.readyForDecision === true || (roundLimit > MAX_ROUNDS && lastRound >= MAX_ROUNDS)
}
const guardRounds = await constraintsGuard(before, 'constraints:after-rounds', 'Rounds')
if (guardRounds) return { ...guardRounds, subject }
const treeRounds = await treeSnapshot('tree:after-rounds', 'Rounds', { against: [TREE_START] })
if (!treeRounds || treeRounds.error) {
  const why = `the architecture could not be fingerprinted after the rounds: ${(treeRounds && treeRounds.error) || 'no result'}`
  return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...died('Rounds') }
}
const roundWrites = diffFiles(treeDiff(treeRounds, 0))
if (roundWrites.length) {
  const why = `sessions wrote in the architecture at ${archPath} before the target was approved; the survey and the rounds write only under ${WORK}: ${roundWrites.join(', ')}`
  log(`Rounds: ${why}`)
  return { ok: false, stage: 'architecture-written', deterministicFailure: true, reason: why, error: why, files: roundWrites, subject }
}

// ---------------------------------------------------------------- Target
phase('Target')
const target = await depscore('target:write', 'Target', `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subject)} --forbid ${shq(FORBID.join(','))} --out ${shq(TARGET_JSON)}`)
const targetSummary = target && target.summary ? target.summary : null
if (!targetSummary || target.error || targetSummary.ok !== true) {
  const why = targetSummary ? `depscore.py arch-target refused the approved draft: ${listed(targetSummary.refusals).join('; ') || 'no reason given'}` : `depscore.py arch-target did not run: ${(target && target.error) || 'no result'}`
  return { ok: false, stage: 'target', reason: why, error: why, decision, subject, ...died('Target') }
}
const targetDir = targetSummary.targetDir
const deltaDir = targetSummary.deltaDir
log(`Target: ${targetSummary.files} view file(s) at ${targetDir}, ${targetSummary.deltaFiles} in its delta`)

// ---------------------------------------------------------------- Integrate
phase('Integrate')
const SECTION_2_RULE = `Write nothing under ${CONSTRAINTS}: section 2 holds the owner's constraints, and only the owner changes them; the run fails on any change there. A constraint you believe should change goes in \`constraintIssues\`, with the constraint, the conflicting content and the reason.`
const INTEGRATE_TASK = `Integrate the approved target at ${targetDir} (the change alone is in ${deltaDir}) into the effective version, the folder ${ARC42}, as the architecture documentation model's step 5 describes. For each element the delta adds, changes or removes, find every effective view that shows it through the catalog (\`subject\` and \`shows\`), at every scope, and update or delete each one; add the target's new views in the section folder the model names, named for their subject. Keep every touched view's catalog frontmatter true to what it now shows. Edit in place: no changelog narrative, and no superseded content left beside the new. Leave every \`lifecycle_state\` as you find it: the run sets it after review. Leave ${targetDir} as it is: later phases read its delta.
${SECTION_2_RULE}
Read approved coverage rows/checks in ${LEDGER_JSON} and approval ${DECISION_JSON}. Apply every approved coverage action, including absent/new views and affected navigation; do not invent unapproved design. For independently excluded unrelated-debt rows record only the unchanged disposition; never repair their absent views. Record each row id in viewsChecked.element with its view/action, using unaffected for justified unchanged/not-applicable rows and view="" for a not-applicable or independently excluded unrelated-debt obligation without an existing path (never invent a view).

Report every file you changed, created or deleted as an absolute path under ${ARC42}, every view the catalog listed for a changed element and what you did to it, and every contradiction with another effective view or open target.`
const updateBrief = persistBrief([UPDATE_JSON], 'your complete structured result, exactly as you return it, as ONE JSON object')
/** The saved integration report's file lists (the report itself stays in UPDATE_JSON), or null. */
const savedFacts = resumedFacts.integration || {}
const savedUpdate = savedFacts.update && typeof savedFacts.update === 'object'
  ? {
      changedFiles: listed(savedFacts.update.changedFiles),
      createdFiles: listed(savedFacts.update.createdFiles),
      deletedFiles: listed(savedFacts.update.deletedFiles),
      constraintIssues: [],
      contradictions: [],
      openItemsSaved: (Number(savedFacts.update.constraintIssues) || 0) + (Number(savedFacts.update.contradictions) || 0),
    }
  : null
const INTEGRATE_BEFORE = `${WORK}/integrate-before.json`
const savedTree = savedFacts.beforeSaved === true
const integrateBefore = savedTree ? { saved: INTEGRATE_BEFORE } : await treeSnapshot('tree:before-integrate', 'Integrate', { save: INTEGRATE_BEFORE })
if (!integrateBefore || integrateBefore.error) {
  const why = `the architecture could not be fingerprinted before the integration: ${(integrateBefore && integrateBefore.error) || 'no result'}`
  return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir, ...died('Integrate') }
}
if (savedUpdate && !savedTree) log('Integrate: no fingerprint was saved before the earlier integration pass; its files are taken from its report and this pass is measured')
/** The last saved review's facts: { n, path, conforms, reviewedFiles, findings: count }. */
const lastSavedReview = savedFacts.lastReview && typeof savedFacts.lastReview === 'object' ? savedFacts.lastReview : null

let integrationCoverageRevision = savedFacts.coverageRevision || ''
let integrationCoverageRows = facts.coverage.checksNeeded
let update = null
let reviewPass = lastSavedReview ? Number(lastSavedReview.n) || 0 : 0
const reusedSaved = !!(savedUpdate && lastSavedReview && lastSavedReview.conforms === true && lastSavedReview.coverageRevision === savedFacts.coverageRevision)
if (reusedSaved) {
  update = savedUpdate
  log('Integrate: reused the saved integration and its conforming review')
} else {
  update = await run(
    savedUpdate
      ? `You are the architecture-maintainer, RESUMING an integration a previous session began and did not finish. Its report is ${UPDATE_JSON}; its edits are in the working tree (\`git status --short\` in the repository holding ${archPath}). Do not start over: finish every view the previous pass left inconsistent with the target or with the other views of the same element, then return the complete report for both passes.\n\n${INTEGRATE_TASK}${updateBrief}`
      : `You are the architecture-maintainer.\n\n${INTEGRATE_TASK}${updateBrief}`,
    { label: 'integrate:maintain', phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!update) return { ok: false, stage: 'integrate', reason: 'the architecture-maintainer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir }
}

const touched = (u) => [...new Set([...listed(u.changedFiles), ...listed(u.createdFiles)])]
const allTouched = (u) => [...touched(u), ...listed(u.deletedFiles)]
/**
 * Adds to a report every file the integration wrote since INTEGRATE_BEFORE, measured from the tree,
 * so an unreported write is reviewed too, and saves the tree to TREE_LAST; with `sinceLast` it also
 * names the files changed since the previous measurement. Returns { update, changedSinceLast } or { failure }.
 */
async function measured(u, label, sinceLast) {
  const now = await treeSnapshot(label, 'Integrate', { save: TREE_LAST, against: sinceLast ? [INTEGRATE_BEFORE, TREE_LAST] : [INTEGRATE_BEFORE] })
  if (!now || now.error) {
    const why = `the architecture could not be fingerprinted after the integration: ${(now && now.error) || 'no result'}`
    return { failure: { ok: false, stage: 'integrate', reason: why, error: why, architectureUpdate: u, decision, subject, targetDir, deltaDir, ...died('Integrate') } }
  }
  const d = treeDiff(now, 0)
  const unreported = diffFiles(d).filter((f) => !allTouched(u).includes(f))
  if (unreported.length) log(`Integrate: files written and not reported, added to the review: ${unreported.join(', ')}`)
  const union = (key, extra) => [...new Set([...listed(u[key]), ...extra])]
  return {
    changedSinceLast: sinceLast ? diffFiles(treeDiff(now, 1)) : [],
    update: { ...u, changedFiles: union('changedFiles', d.changed), createdFiles: union('createdFiles', d.created), deletedFiles: union('deletedFiles', d.deleted) },
  }
}
/** Returns the failure when the integration wrote a file in section 2 or outside arc42 (section 2 is put back), else null. */
async function outOfBounds(u) {
  const inSection2 = allTouched(u).filter((f) => f === CONSTRAINTS || f.startsWith(`${CONSTRAINTS}/`))
  const outside = allTouched(u).filter((f) => !f.startsWith(`${ARC42}/`))
  if (!inSection2.length && !outside.length) return null
  if (inSection2.length) {
    const guard = await constraintsGuard(before, 'constraints:integrate-bounds', 'Integrate')
    if (guard) return { ...guard, architectureUpdate: u, decision, subject, targetDir, deltaDir }
  }
  const why = inSection2.length
    ? `the integration wrote in section 2, which holds the owner's constraints: ${inSection2.join(', ')}`
    : `the integration wrote files outside the effective version ${ARC42}: ${outside.join(', ')}`
  return { ok: false, stage: 'integrate', deterministicFailure: true, reason: why, error: why, architectureUpdate: u, decision, subject, targetDir, deltaDir }
}
const firstMeasure = await measured(update, 'tree:after-integrate')
if (firstMeasure.failure) return firstMeasure.failure
update = firstMeasure.update
const bounds = await outOfBounds(update)
if (bounds) return bounds

/** Names where a review's findings are: the review file, and the changed files it did not review. */
const findingsWhere = (c) =>
  `the \`findings\` in ${c.path}${listed(c.missed).length ? `, and these files the integration changed or created that the review did not review: ${listed(c.missed).join(', ')}` : ''}`
/** Runs one conformance review; a changed file the review does not cover is a finding. `again` names the previous review and the files the correction changed. */
async function review(again) {
  reviewPass += 1
  const againBlock = again
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review's findings are ${findingsWhere(again.previous)}; read them. Correction ${again.correction} changed these files to answer them: ${again.changed.join(', ')}. Confirm each finding is resolved, and check the changed files as fully as the rest.\n`
    : ''
  const reviewFile = `${WORK}/conformance-${reviewPass}.json`
  const current = await readFacts(`integrate:coverage-${reviewPass}`, 'Integrate')
  if (current.error || current.coverage.gaps.length || current.coverage.revision !== decision.coverageRevision) {
    log('Integrate: approved coverage changed or lost review evidence; retain work for targeted reapproval')
    return null
  }
  integrationCoverageRevision = current.integration.coverageRevision
  integrationCoverageRows = current.coverage.checksNeeded
  const got = await run(
    `You are the architecture-conformance-reviewer. Check one integration of an approved target into the effective version; report findings and fix nothing.

THE APPROVED TARGET: ${targetDir} (the change alone in ${deltaDir}).
THE INTEGRATION REPORT: ${UPDATE_JSON}. The files it changed or created, every one of which you review:
${touched(update).map((f) => `- ${f}`).join('\n') || '- (none)'}
Files it deleted: ${listed(update.deletedFiles).join(', ') || '(none)'}
${againBlock}
${ARCH_WHERE}

Read approved coverage in ${LEDGER_JSON} and decision ${DECISION_JSON}. Independently check every approved action, including required views absent before integration, honest diagram declarations, readable rendering, cross-scope consistency and navigation. Report unrelated historical debt in summary, not blocking findings. Set coverageRevision to ${integrationCoverageRevision}; it binds this review to approved coverage and current integrated content. Return coverageChecks for EVERY approved ledger row id/revision, with verdict and evidence naming the integrated view and disposition (including unchanged/not-applicable and independently excluded unrelated-debt, whose missing views must not be repaired). Do not change the design to fill a gap.

Check that the integration applied the approved target exactly, no more and no less; that every effective view the catalog lists for each changed element was updated or deleted, at every scope; that the new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming, and one finding per problem with its file and evidence; \`conforms\` is true only when there is no finding.${persistBrief([reviewFile], 'your complete structured result, exactly as you return it, as ONE JSON object')}`,
    { label: `integrate:review-${reviewPass}`, phase: 'Integrate', agentType: 'agent-teams-workforce:architecture-conformance-reviewer', effort: 'medium', schema: CONFORMANCE_SCHEMA }
  )
  return got ? covered({ ...got, path: reviewFile }) : null
}
/** Marks a review not conforming when it leaves a changed file unreviewed, naming those files in `missed`. */
function covered(c) {
  const missed = touched(update).filter((f) => !listed(c.reviewedFiles).includes(f))
  const checks = Array.isArray(c.coverageChecks) ? c.coverageChecks : []
  const missingCoverage = integrationCoverageRows.filter((row) => !checks.some((check) => check.id === row.id && check.revision === row.revision && check.verdict === 'verified' && hasText(check.evidence)))
  if (missingCoverage.length) return { ...c, conforms: false, missed, findings: [...(Array.isArray(c.findings) ? c.findings : []), ...missingCoverage.map((row) => ({ file: UPDATE_JSON, finding: `coverage ${row.id} lacks verified integration evidence`, evidence: 'no current per-obligation conformance check' }))] }
  if (c.coverageRevision !== integrationCoverageRevision) return { ...c, conforms: false, missed, findings: [...(Array.isArray(c.findings) ? c.findings : []), { file: UPDATE_JSON, finding: 'coverage review is missing or stale for current integrated content', evidence: 'coverageRevision does not match the current integration' }] }
  if (!missed.length) return { ...c, missed: [] }
  return { ...c, conforms: false, missed, findings: [...(Array.isArray(c.findings) ? c.findings : []), ...missed.map((f) => ({ file: f, finding: 'changed or created by the integration and not reviewed', evidence: 'absent from reviewedFiles' }))] }
}

let conformance = lastSavedReview && lastSavedReview.conforms === true && reusedSaved ? covered(lastSavedReview) : null
if (!conformance || conformance.conforms !== true) conformance = await review()
if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
let corrections = 0
while (conformance.conforms !== true && corrections < MAX_CORRECTIONS) {
  corrections += 1
  const fixed = await run(
    `You are the architecture-maintainer, CORRECTING your integration (correction ${corrections} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer's findings are ${findingsWhere(conformance)}: read them. Correct each one in place, then return the complete report of the integration, every pass together.

${INTEGRATE_TASK}${updateBrief}`,
    { label: `integrate:correct-${corrections}`, phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!fixed) return { ok: false, stage: 'integrate', reason: `the architecture-maintainer returned no result for correction ${corrections}`, ...died('Integrate'), decision, subject, targetDir, deltaDir }
  const merged = (key) => [...new Set([...listed(update[key]), ...listed(fixed[key])])]
  const fixMeasure = await measured({ ...fixed, changedFiles: merged('changedFiles'), createdFiles: merged('createdFiles'), deletedFiles: merged('deletedFiles') }, `tree:after-correct-${corrections}`, true)
  if (fixMeasure.failure) return fixMeasure.failure
  update = fixMeasure.update
  const fixedBounds = await outOfBounds(update)
  if (fixedBounds) return fixedBounds
  const changedNow = fixMeasure.changedSinceLast
  if (!changedNow.length) {
    const why = `correction ${corrections} changed no file, so a further review would judge the same integration; the findings stand: ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
    log(`Integrate: ${why}`)
    return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir, retries }
  }
  const whatChanged = `correction ${corrections} changed ${changedNow.join(', ')} to answer ${(conformance.findings || []).length} finding(s)`
  retries.push({ step: 'integrate:review', attempt: reviewPass + 1, whatChanged })
  log(`Integrate: review again — ${whatChanged}`)
  conformance = await review({ correction: corrections, changed: changedNow, previous: conformance })
  if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
}
if (conformance.conforms !== true) {
  const why = `the integration does not conform after ${corrections} correction pass(es): ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
  log(`Integrate: ${why}`)
  return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
}
const guardIntegrate = await constraintsGuard(before, 'constraints:after-integrate', 'Integrate')
if (guardIntegrate) return { ...guardIntegrate, subject, targetDir, deltaDir, architectureUpdate: update }

// Consumed by: lifecycle promotion below — do not promote evidence changed after review.
const finalCoverage = await readFacts('integrate:coverage-final', 'Integrate')
if (finalCoverage.error || finalCoverage.coverage.gaps.length || finalCoverage.coverage.revision !== decision.coverageRevision || finalCoverage.integration.coverageRevision !== conformance.coverageRevision || !finalCoverage.integration.lastReview || finalCoverage.integration.lastReview.coverageRevision !== conformance.coverageRevision) {
  return { ok: false, stage: 'integrate', reason: 'conformance evidence is unsaved or stale; retained work requires a fresh review before promotion', subject, targetDir, deltaDir }
}
let approval = null
const toApprove = touched(update)
if (toApprove.length) {
  approval = await depscore('integrate:approve', 'Integrate', `arch-approve --arch-files ${shq(toApprove.join(','))} --reviewed-files ${shq(listed(conformance.reviewedFiles).join(','))} --arch-root ${shq(ARC42)}`)
  const n = approval && approval.summary ? approval.summary : null
  const notSet = approval && !approval.error ? [...listed(approval.unreviewed), ...(approval.refused || []).map((x) => x.path), ...(approval.failed || []).map((x) => x.path)] : []
  if (!n || approval.error || notSet.length) {
    const why = !n || approval.error
      ? `depscore.py arch-approve did not run: ${(approval && approval.error) || 'no result'}`
      : `depscore.py arch-approve did not set these integrated files to effective: ${notSet.join(', ')}`
    return { ok: false, stage: 'approve', reason: why, error: why, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  log(`Approval: ${n.promoted || 0} file(s) set to effective, ${n.unchanged || 0} already effective`)
}

let vaultCommit = null
const toCommit = allTouched(update)
if (toCommit.length) {
  vaultCommit = await depscore('integrate:commit', 'Integrate', `arch-commit --arch-root ${shq(ARC42)} --files ${shq(toCommit.join(','))} --message ${shq(`docs(architecture): integrate the approved target for ${subject}`)}`)
  if (!vaultCommit || vaultCommit.error || vaultCommit.ok === false) {
    const why = `depscore.py arch-commit did not commit and push the integrated files: ${(vaultCommit && (vaultCommit.error || listed(vaultCommit.refusals).join('; '))) || 'no result'}`
    return { ok: false, stage: 'commit', reason: why, error: why, vaultCommit, approval, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
  }
  log(`Commit: ${vaultCommit.commit ? `${vaultCommit.commit} on ${vaultCommit.branch}` : 'nothing new to commit'}${vaultCommit.pushed ? ', pushed' : ''}`)
}

return {
  ok: true,
  subject,
  subjectName,
  targetDir,
  deltaDir,
  targetPath: TARGET_JSON,
  surveyPath: SURVEY_MD,
  decision,
  decisionPath: DECISION_MD,
  architectureUpdate: update,
  conformance,
  approval,
  vaultCommit,
  rounds: lastRound,
  retries,
  openItems: [
    ...listed(update.constraintIssues),
    ...listed(update.contradictions),
    ...(Number(update.openItemsSaved) > 0 ? [`${update.openItemsSaved} constraint issue(s) and contradiction(s) recorded in ${UPDATE_JSON}`] : []),
  ],
  architectureUpdatePath: UPDATE_JSON,
  ledgerPath: LEDGER_JSON,
}

})())
