export const meta = {
  name: 'architecture',
  description:
    "Leaf mini — designs the architecture for one Epic's PRD as a target and a delta version, and integrates the approved target into the effective version. Its inputs are the PRD, the effective version in arc42 (every section and view, found through the catalog frontmatter), the open targets that show the same elements, the code on each relevant repository's main, the open beads, and the AWS documentation through the AWS MCP tools; never what is deployed. A prd-reality-reconciler session writes survey.md and survey.json, with repository facts from the polyrepo-steward. Then rounds: the architecture-decision-workflow-coordinator names the proposers, reviewers, diagram authors and cost reviewers each round and the script runs them; proposers write the target and delta views into a draft, reviewers mark every claim verified, unsupported or wrong with evidence, and every finding is answered by its owner, up to maxRounds (default 6). The script holds the decision until every claim has a verdict, every finding is answered and depscore.py arch-target accepts the draft. The architecture-decider, given artifact paths only, approves, returns to a named proposer, or raises an owner concern (a serious security, privacy, cost or best-practice concern, or a PRD defect). On approval depscore.py arch-target writes target/<subject>/ and its delta/ as in-review, the architecture-maintainer integrates the target into arc42, the architecture-conformance-reviewer checks it (at most 2 correction passes), and depscore.py arch-approve sets the integrated files the review covered to effective; depscore.py arch-commit then commits the files the integration changed, staging only those paths, and pushes the branch. A write under arc42 section 2 fails the run and is undone: depscore.py arch-constraints fingerprints that folder before and after and copies it aside, and depscore.py arch-constraints-restore puts it back. depscore.py arch-snapshot fingerprints arc42/, target/ and built/: a write there before the target is approved fails the run, and the integration's files are measured from it, not taken from the maintainer's report, so every file the integration wrote is reviewed before arch-approve sets it to effective. Returns { ok, stage, subject, targetDir, deltaDir, deltaFiles, decision, architectureUpdate, conformance, approval, vaultCommit } or, for an owner concern, ok:false at stage owner-concern with requiredHumanActions.",
  phases: [
    { title: 'Survey', detail: 'the polyrepo-steward names the repositories; a prd-reality-reconciler session surveys the effective views, code on main, open beads and open targets for each capability the PRD needs' },
    { title: 'Rounds', detail: 'the coordinator names each round of proposers, reviewers, diagram authors and cost reviewers; the script runs them and tracks every claim and finding' },
    { title: 'Decide', detail: 'the architecture-decider approves, returns to a named proposer, or raises an owner concern' },
    { title: 'Target', detail: 'depscore.py arch-target writes the approved draft to target/<subject>/ and its delta/ as in-review' },
    { title: 'Integrate', detail: 'the architecture-maintainer integrates the target into arc42; the architecture-conformance-reviewer checks it; depscore.py arch-approve sets the reviewed files to effective; depscore.py arch-commit commits and pushes the integrated files' },
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
    return { error: (out.output && out.output.error) || `depscore.py exited ${out.exitCode}`, output: out.output || null }
  }
  return out.output
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

const SAVED_PY = [
  'import json, sys, pathlib',
  'd = pathlib.Path(sys.argv[1])',
  'out = {}',
  "files = sorted(p for p in d.rglob('*.json') if p.is_file() and not p.name.endswith('.meta.json') and 'draft' not in p.relative_to(d).parts) if d.is_dir() else []",
  "[out.__setitem__(p.relative_to(d).as_posix(), json.loads(p.read_text(encoding='utf-8'))) for p in files]",
  "print(json.dumps({'dir': str(d), 'exists': d.is_dir(), 'saved': out, 'surveyMd': (d / 'survey.md').is_file()}))",
].join('; ')
/** Reads what an earlier run of this step saved, so a stopped run resumes from it. */
async function readSaved() {
  const out = await run(
    `Run exactly this one shell command, once, and change nothing else:

python3 -c ${shq(SAVED_PY)} ${shq(WORK)}

It prints one JSON object on stdout. Return the process exit code as \`exitCode\` and that JSON object, parsed and unaltered, as \`output\`. If stdout is not JSON, return {"error": "<stdout and stderr, verbatim>"} as \`output\`. Do not retry, do not repair, do not run any other command.`,
    { label: 'resume:read-saved', phase: 'Survey', model: 'haiku', effort: 'low', schema: RUN_SCHEMA }
  )
  const o = out && out.exitCode === 0 && out.output && !out.output.error ? out.output : null
  return o && o.saved && typeof o.saved === 'object' ? o : { saved: {}, surveyMd: false }
}

const ARCH_WHERE = `THE ARCHITECTURE is at ${archPath}. It is not inside any product repository.
- \`arc42/\` is the effective version: the approved architecture. \`arc42/02-architecture-constraints/README.md\` holds the owner's constraints; read it in full. \`arc42/04-solution-strategy/README.md\` holds the enterprise-level strategy; read it. Every other section is the design so far, as views.
- The constraints are the owner's; everything else in the architecture is the design so far, followed as established patterns unless a design states a reason and evidence to change it.
- Each view's frontmatter names its \`view_type\`, \`scope\`, \`subject\` and every element it \`shows\`: that frontmatter is the catalog. Find the views of an element by searching it (\`subject:\` and the \`shows:\` lists) for the element's name, in every section, at every scope.
- \`target/<subject>/\` folders are open targets (designs in progress) and \`built/<subject>/\` folders record builds that differ from the effective version. Read every open target that shows an element this PRD touches, so the designs do not contradict each other.
- The architecture documentation model is ${MODEL}; the view types to choose from are ${MENU}.
- \`lifecycle_state\` is per file: \`effective\` was reviewed and approved; \`in-review\` is input to check, never assumed vetted.`

const INPUTS_RULE = `YOUR INPUTS are the PRD, the effective version and the open targets above, the code on each relevant repository's \`main\` (read it as committed there: \`git -C <repo> grep -n <term> main\`, \`git -C <repo> show main:<path>\`), the open beads (other Epics' Stories and Tasks planned but not built), and the AWS documentation through the AWS MCP tools and skills. What is deployed in AWS is not an input: run no AWS describe, list or get call against an account. Repository code is input to check, never evidence that a design is right. Cite what you rely on: a view by its absolute path and heading, code by repository, path and line on \`main\`, AWS behaviour by the documentation URL you read.`

const DRAFT_RULES = `THE DRAFT TARGET is the folder ${DRAFT}. It has the arc42 section layout (\`05-building-block-view/…\`, \`06-runtime-view/…\`, \`07-deployment-view/…\`, \`08-crosscutting-concepts/…\`, and \`03-context-and-scope/\` or \`04-solution-strategy/\` only when the change reaches them) and a \`delta/\` folder beside them.
- A target view is the view as it will read once approved: a changed copy of each effective view that shows a changed element, at every scope where the element appears, and a new view for each new element. Copy an effective view into the draft before you change it, at the same relative path.
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
    'architecture-pattern-challenger': 'counters a design with a structurally different alternative and the weaknesses it exposes',
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

const DEFECT_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['requirement', 'defect'],
    properties: { requirement: { type: 'string' }, defect: { type: 'string' } },
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
const SURVEY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['subject', 'subjectReason', 'capabilities', 'openTargets', 'prdDefects', 'summary'],
  properties: {
    subject: { type: 'string' },
    subjectReason: { type: 'string' },
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
    prdDefects: DEFECT_ITEMS,
    summary: { type: 'string' },
  },
}
const COORDINATOR_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['readyForDecision', 'reason', 'dispatches'],
  properties: {
    readyForDecision: { type: 'boolean' },
    reason: { type: 'string' },
    dispatches: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['agentType', 'role', 'task', 'files', 'answers'],
        properties: {
          agentType: { type: 'string' },
          role: { type: 'string', enum: Object.keys(ROSTER) },
          task: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } },
          answers: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}
const WRITER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['files', 'claims', 'answers', 'prdDefects', 'summary'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claim', 'file', 'citation'],
        properties: { claim: { type: 'string' }, file: { type: 'string' }, citation: { type: 'string' } },
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
    prdDefects: DEFECT_ITEMS,
    summary: { type: 'string' },
  },
}
const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings', 'summary'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['claimId', 'claim', 'file', 'verdict', 'evidence', 'owner'],
        properties: {
          claimId: { type: 'string' },
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
const OWNER_CONCERN_KINDS = ['security', 'privacy', 'cost', 'best-practice', 'prd-defect']
const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['round', 'verdict', 'diligence', 'returnTo', 'ownerConcerns', 'summary'],
  properties: {
    round: { type: 'integer' },
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
  required: ['conforms', 'reviewedFiles', 'findings', 'summary'],
  properties: {
    conforms: { type: 'boolean' },
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

/** Returns the fingerprint of every file of arc42/, target/ and built/, or { error }; `save` also writes it to that file. */
const treeSnapshot = (label, phaseName, save) => depscore(label, phaseName, `arch-snapshot --arch-root ${shq(archPath)}${save ? ` --save ${shq(save)}` : ''}`)
/** Returns the files created, changed and deleted between two tree fingerprints, as absolute paths. */
function treeDiff(x, y) {
  const was = (x && x.files) || {}
  const now = (y && y.files) || {}
  const abs = (rel) => `${archPath}/${rel}`
  return {
    created: Object.keys(now).filter((k) => !(k in was)).map(abs),
    changed: Object.keys(now).filter((k) => k in was && was[k] !== now[k]).map(abs),
    deleted: Object.keys(was).filter((k) => !(k in now)).map(abs),
  }
}
const diffFiles = (d) => [...d.created, ...d.changed, ...d.deleted]

const before = await constraintsSnapshot('constraints:before', 'Survey', true)
if (!before || before.error || !hasText(before.kept)) {
  const why = `section 2 of the architecture could not be fingerprinted and copied before the step: ${(before && before.error) || 'no copy was named'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}
const treeBefore = await treeSnapshot('tree:before', 'Survey')
if (!treeBefore || treeBefore.error) {
  const why = `the architecture could not be fingerprinted before the step: ${(treeBefore && treeBefore.error) || 'no result'}`
  return { ok: false, stage: 'survey', reason: why, error: why, ...died('Survey') }
}

const resumed = await readSaved()
const saved = resumed.saved || {}

// ---------------------------------------------------------------- Survey
phase('Survey')
let survey = saved['survey.json'] && resumed.surveyMd ? saved['survey.json'] : null
if (survey) {
  log(`Survey: reused ${SURVEY_JSON}`)
} else {
  const repos = await run(
    `List every repository of this project: its name, the absolute path of its local checkout, its role (what it is for) and its lifecycle (for example active, deprecated, archived). Answer from your records and the live repositories. Change nothing.`,
    { label: 'survey:repositories', phase: 'Survey', agentType: 'agent-teams-workforce:polyrepo-steward', effort: 'low', schema: REPOS_SCHEMA }
  )
  if (!repos) return { ok: false, stage: 'survey', reason: 'the polyrepo-steward named no repositories', ...died('Survey') }
  survey = await run(
    `You are the prd-reality-reconciler, SURVEYING for the architecture step. The architecture team designs from your survey; you design nothing.

PRD: ${prdRef}

${ARCH_WHERE}

${INPUTS_RULE}

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
List in \`prdDefects\` only where the PRD contradicts itself or lacks a value only the owner can give.
Write survey.md as the readable survey and survey.json as your structured result.${persistBrief([SURVEY_MD, SURVEY_JSON], 'the survey: survey.md as one Markdown document, and survey.json as your complete structured result, exactly as you return it')}`,
    { label: 'survey:reality', phase: 'Survey', agentType: 'prd-reality-reconciler', effort: 'medium', schema: SURVEY_SCHEMA }
  )
  if (!survey) return { ok: false, stage: 'survey', reason: 'the prd-reality-reconciler returned no survey', ...died('Survey') }
}
// The subject as named; depscore.py arch-target derives the folder name every later step uses.
const subjectName = hasText(a.subject) ? a.subject.trim() : hasText(survey.subject) ? survey.subject.trim() : ''
const subjectCheck = await depscore('target:check-subject', 'Survey', `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subjectName || '-')} --forbid ${shq(FORBID.join(','))} --dry-run`)
const subjectRefusals = subjectCheck && !subjectCheck.error ? listed(subjectCheck.subjectRefusals) : []
const subject = subjectCheck && !subjectCheck.error && hasText(subjectCheck.subject) ? subjectCheck.subject.trim() : ''
if (!subjectName || subjectRefusals.length || !subjectCheck || subjectCheck.error || !subject) {
  const why = !subjectName
    ? 'the survey named no subject for the target'
    : subjectRefusals.length
      ? `the target subject cannot name a target: ${subjectRefusals.join('; ')}`
      : `the target subject could not be checked: ${(subjectCheck && subjectCheck.error) || 'no folder name returned'}`
  return { ok: false, stage: 'survey', deterministicFailure: subjectRefusals.length > 0, reason: why, error: why, survey }
}
log(`Survey: subject ${subjectName} (folder target/${subject}/); ${(survey.capabilities || []).length} capabilit(ies)`)

// ---------------------------------------------------------------- Rounds
const claims = []
const findings = []
const writers = new Set()
const roundFiles = []
let lastRound = 0
/** Every re-dispatch after a failed or empty result, with what changed in its input. */
const retries = []
/** Each finding id handed to a writer to answer: { agentType, round, clarified }. */
const asked = new Map()
let silentLast = []

/** Folds one saved or returned round result into the claim and finding ledger. */
function absorb(n, seq, role, agentType, result, file) {
  if (!result || typeof result !== 'object') return
  roundFiles.push(file)
  if (n > lastRound) lastRound = n
  if (WRITER_ROLES.includes(role)) {
    writers.add(agentType)
    ;(Array.isArray(result.claims) ? result.claims : []).forEach((c, k) => {
      if (c && hasText(c.claim)) claims.push({ id: `C${n}.${seq}.${k + 1}`, round: n, by: agentType, claim: c.claim, file: c.file || '', citation: c.citation || '', verdicts: [] })
    })
    for (const ans of Array.isArray(result.answers) ? result.answers : []) {
      const f = ans && findings.find((x) => x.id === ans.findingId)
      if (!f || f.answer || (f.owner && f.owner !== agentType)) continue
      f.owner = agentType
      f.answer = { round: n, response: ans.response, evidence: ans.evidence || '' }
    }
    return
  }
  ;(Array.isArray(result.findings) ? result.findings : []).forEach((x, k) => {
    if (!x || !hasText(x.verdict)) return
    const claim = hasText(x.claimId) ? claims.find((c) => c.id === x.claimId.trim()) : null
    if (claim) claim.verdicts.push({ by: agentType, verdict: x.verdict })
    const owner = claim ? claim.by : hasText(x.owner) && writers.has(x.owner.trim()) ? x.owner.trim() : ''
    findings.push({ id: `F${n}.${seq}.${k + 1}`, round: n, by: agentType, claimId: claim ? claim.id : '', claim: x.claim || '', file: x.file || '', verdict: x.verdict, evidence: x.evidence || '', owner, answer: null })
  })
}

const savedRound = /^rounds\/r(\d+)-(\d+)-(proposer|diagram|reviewer|cost)-([a-z0-9-]+)\.json$/
Object.keys(saved)
  .map((name) => ({ name, m: savedRound.exec(name) }))
  .filter((x) => x.m && roleOf(x.m[4]) === x.m[3])
  .map((x) => ({ name: x.name, n: Number(x.m[1]), seq: Number(x.m[2]), role: x.m[3], agentType: x.m[4] }))
  .sort((p, q) => p.n - q.n || p.seq - q.seq)
  .forEach((x) => absorb(x.n, x.seq, x.role, x.agentType, saved[x.name], `${WORK}/${x.name}`))
if (lastRound) log(`Rounds: resumed after round ${lastRound} — ${claims.length} claim(s), ${findings.length} finding(s)`)

const openFindings = () => findings.filter((f) => f.verdict !== 'verified' && !f.answer)
const unreviewedClaims = () => claims.filter((c) => !c.verdicts.length)
/** Returns what still stands between the draft and a decision. */
async function decisionGaps(label) {
  const gaps = []
  if (![...writers].some((w) => roleOf(w) === 'proposer')) gaps.push('no proposer has written the target yet')
  for (const f of openFindings()) gaps.push(`finding ${f.id} (${f.verdict}) on ${f.file || 'the draft'} is unanswered; owner ${f.owner || 'not known — assign it to a writer'}`)
  for (const c of unreviewedClaims()) gaps.push(`claim ${c.id} by ${c.by} has no reviewer verdict`)
  const check = await depscore(label, 'Rounds', `arch-target --draft ${shq(DRAFT)} --arch-root ${shq(archPath)} --subject ${shq(subject)} --forbid ${shq(FORBID.join(','))} --dry-run`)
  if (!check || check.error) gaps.push(`the draft could not be checked: ${(check && check.error) || 'no result'}`)
  else for (const r of listed(check.refusals)) gaps.push(`draft: ${r}`)
  return gaps
}

const ledgerText = () =>
  JSON.stringify(
    {
      claims: claims.map((c) => ({ id: c.id, by: c.by, file: c.file, claim: c.claim, citation: c.citation, verdicts: c.verdicts })),
      findings: findings.map((f) => ({ id: f.id, by: f.by, owner: f.owner, claimId: f.claimId, file: f.file, verdict: f.verdict, evidence: f.evidence, answer: f.answer })),
      savedResults: roundFiles,
    },
    null,
    1
  )

const savedDecision = saved['decision.json'] && typeof saved['decision.json'] === 'object' ? saved['decision.json'] : null
let decision = savedDecision && savedDecision.verdict === 'approve' ? savedDecision : null
/** Returns the proposers a decision returned the target to, each { agentType, missing }. */
const returnedTo = (dec) =>
  (dec && Array.isArray(dec.returnTo) ? dec.returnTo : [])
    .filter((r) => r && hasText(r.agentType) && roleOf(r.agentType.trim().replace(AGENT_PREFIX, '')) === 'proposer')
    .map((r) => ({ agentType: r.agentType.trim().replace(AGENT_PREFIX, ''), missing: String(r.missing || '') }))
let forced = savedDecision && savedDecision.verdict === 'return' && !(lastRound > (savedDecision.round || 0)) ? returnedTo(savedDecision) : []
let rejected = []
let pendingGaps = []

/** Returns the owner-concern result that holds the Epic for the owner. */
function ownerConcern(dec) {
  const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
  return {
    ok: false,
    stage: 'owner-concern',
    reason: `the architecture-decider raised ${concerns.length} owner concern(s) on ${subject}`,
    ownerConcerns: concerns,
    requiredHumanActions: [
      ...concerns.map((c) => `ARCHITECTURE ${c.kind === 'prd-defect' ? 'PRD DEFECT' : `${String(c.kind).toUpperCase()} CONCERN`} on ${subject}: ${c.concern} — evidence: ${c.evidence}`),
      `Once each concern is ruled on (or the PRD fixed), delete ${DECISION_JSON}: while it holds these concerns, every run of the architecture step holds the Epic again.`,
    ],
    decision: dec,
    decisionPath: DECISION_MD,
    subject,
    survey,
  }
}
if (savedDecision && savedDecision.verdict === 'owner-concern') {
  log('Decide: the saved decision holds owner concerns; the Epic is held again')
  return ownerConcern(savedDecision)
}

/** Returns the prompt for one writer or reviewer dispatch. */
function dispatchPrompt(n, d, file) {
  const answerList = findings.filter((f) => d.answers.includes(f.id))
  const answersBlock = answerList.length
    ? `\nFINDINGS YOU ANSWER THIS ROUND — answer every one in \`answers\`: \`fixed\` (name the change you made) or \`disputed\` (with your evidence):\n${JSON.stringify(answerList.map((f) => ({ findingId: f.id, verdict: f.verdict, claim: f.claim, file: f.file, evidence: f.evidence, by: f.by })), null, 1)}\n`
    : ''
  const shared = `PRD: ${prdRef}

${ARCH_WHERE}

${INPUTS_RULE}

THE SURVEY is ${SURVEY_MD} (readable) and ${SURVEY_JSON} (structured): read it first. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
EARLIER RESULTS of this step are in ${ROUNDS_DIR}; read the ones that touch your work.`
  if (WRITER_ROLES.includes(d.role)) {
    const work = d.role === 'proposer'
      ? `Design the target for your concern (${ROSTER.proposer[d.agentType]}) from the effective version, at every scope the change reaches (system, domain, service, component, concept), as views of the types in ${MENU}: diagrams and prose. Write the target views and the delta views for it into the draft. A design that departs from an established pattern states its reason and evidence in the view's prose.`
      : `Draw the views your task names (${ROSTER.diagram[d.agentType]}) into the draft, from the design the proposers wrote there. Depict nothing that design does not contain.`
    return `You are the ${d.agentType}, a writer on the architecture team for this PRD, round ${n}. ${work}

YOUR TASK THIS ROUND, from the coordinator: ${d.task}
${d.files.length ? `THE DRAFT FILES YOU OWN THIS ROUND, relative to ${DRAFT} (write only these; other sessions may be writing the rest):\n${d.files.map((f) => `- ${f}`).join('\n')}` : 'You were named no draft files this round: change no view another writer owns, and name every file you write in `files`.'}
${answersBlock}
${shared}

${DRAFT_RULES}

Return in \`files\` every draft file you wrote, relative to ${DRAFT}. Return in \`claims\` every claim your views make that a reviewer must check — about AWS (cite the documentation page you read), the code (cite repository, path and line on \`main\`), or the architecture (cite the view path and heading) — each with the draft file it is in. List in \`prdDefects\` only where the PRD contradicts itself or lacks a value only the owner can give.${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
  }
  const toCheck = unreviewedClaims()
  return `You are the ${d.agentType}, a ${d.role === 'cost' ? 'cost reviewer' : 'reviewer'} on the architecture team for this PRD, round ${n}: ${ROSTER[d.role][d.agentType]}.

YOUR TASK THIS ROUND, from the coordinator: ${d.task}

THE DRAFT TARGET is ${DRAFT} (target views in the arc42 section layout, the change alone in \`delta/\`). Read it; write nothing in it and nothing in ${archPath}.

${shared}

Check each claim below against its citation, with your own evidence: AWS behaviour through the AWS MCP documentation tools, code by reading the cited lines on \`main\`, the architecture by reading the cited view. Mark each \`verified\`, \`unsupported\` (the citation does not show it) or \`wrong\` (the evidence shows otherwise), with the evidence you found, and its claimId. A problem no claim covers is a finding with claimId "" and, as \`owner\`, the writer whose view it is in (writers so far: ${[...writers].join(', ') || 'none'}).${d.role === 'cost' ? ' State your estimates, with the unit math, in `estimates`; a cost the design does not support is a finding like any other.' : ''}

CLAIMS NOT YET REVIEWED:
${toCheck.length ? JSON.stringify(toCheck.map((c) => ({ claimId: c.id, by: c.by, file: c.file, claim: c.claim, citation: c.citation })), null, 1) : '(none — review the draft for problems no claim covers)'}${persistBrief([file], 'your complete structured result, exactly as you return it, as ONE JSON object')}`
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
      const f = findings.find((x) => x.id === id && !x.owner)
      if (f) f.owner = name
    }
    const same = out.find((x) => x.agentType === name)
    if (same) {
      same.task = `${same.task}\n${d.task}`
      same.files = [...new Set([...same.files, ...files])]
      same.answers = [...new Set([...same.answers, ...answers])]
    } else {
      out.push({ agentType: name, role, task: String(d.task || ''), files, answers })
    }
  }
  for (const d of out) d.answers = d.answers.filter((id) => findings.some((f) => f.id === id && f.owner === d.agentType && !f.answer))
  for (const r of forced) {
    const role = roleOf(r.agentType)
    if (!role || !WRITER_ROLES.includes(role)) continue
    const same = out.find((x) => x.agentType === r.agentType)
    const task = `The architecture-decider returned the target to you. Supply the missing due diligence: ${r.missing}`
    if (same) same.task = `${same.task}\n${task}`
    else out.push({ agentType: r.agentType, role, task, files: [], answers: [] })
    retries.push({ step: `round${n}:${r.agentType}`, whatChanged: `the architecture-decider returned the target naming the missing due diligence: ${r.missing}` })
  }
  for (const f of openFindings()) {
    if (!f.owner || out.some((x) => x.agentType === f.owner && x.answers.includes(f.id))) continue
    const same = out.find((x) => x.agentType === f.owner)
    if (same) same.answers.push(f.id)
    else out.push({ agentType: f.owner, role: roleOf(f.owner), task: 'Answer the findings listed below.', files: [], answers: [f.id] })
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
  return { dispatches: out, rejected: bad, stuck }
}

/** Runs one round's dispatches: writers in waves of disjoint files, then reviewers together. */
async function runRound(n, dispatches) {
  const writing = dispatches.filter((d) => WRITER_ROLES.includes(d.role))
  const reviewing = dispatches.filter((d) => REVIEW_ROLES.includes(d.role))
  const ordered = [...writing, ...reviewing].map((d, i) => ({ ...d, seq: i + 1, file: `${ROUNDS_DIR}/r${n}-${i + 1}-${d.role}-${d.agentType}.json` }))
  const go = (d) => () =>
    run(dispatchPrompt(n, d, d.file), {
      label: `round${n}:${d.role}:${d.agentType}`,
      phase: 'Rounds',
      agentType: dispatchName(d.agentType),
      effort: d.role === 'proposer' ? 'high' : 'medium',
      schema: WRITER_ROLES.includes(d.role) ? WRITER_SCHEMA : REVIEW_SCHEMA,
    })
  const results = new Map()
  for (const wave of writerWaves(ordered.filter((d) => WRITER_ROLES.includes(d.role)))) {
    const got = await parallel(wave.items.map(go))
    wave.items.forEach((d, i) => results.set(d.seq, got[i]))
  }
  const reviewers = ordered.filter((d) => REVIEW_ROLES.includes(d.role))
  if (reviewers.length) {
    const got = await parallel(reviewers.map(go))
    reviewers.forEach((d, i) => results.set(d.seq, got[i]))
  }
  for (const d of ordered) absorb(n, d.seq, d.role, d.agentType, results.get(d.seq), d.file)
  return ordered.filter((d) => !results.get(d.seq)).map((d) => d.agentType)
}

/** Runs the decider over the artifacts; returns its decision or null. */
async function decide(n) {
  phase('Decide')
  const dec = await run(
    `You are the architecture-decider. Decide whether the draft target below is approved. You produced none of it, and you decide from the artifacts alone: read them.

ARTIFACTS:
- the PRD: ${hasText(prd.path) ? prd.path : '(inline — see the survey)'}
- the survey: ${SURVEY_MD} and ${SURVEY_JSON}
- every result of every round: ${roundFiles.length ? roundFiles.join(', ') : '(none)'}
- the draft target and its delta: ${DRAFT}
- the effective version, with the owner's constraints in section 2: ${ARC42}; open targets: ${archPath}/target/

CHECK THAT THE DUE DILIGENCE IS PRESENT, item by item in \`diligence\`: every claim reviewed with evidence and every finding answered; the target shows every changed element at every scope where the effective version shows it; the delta shows the change; the owner's constraints in section 2 are honoured; the open targets that show the same elements were read and are not contradicted; a departure from an established pattern states its reason and evidence.

VERDICT:
- \`approve\` when the diligence is present.
- \`return\` when a proposer's diligence is missing: name each one in \`returnTo\` (one of ${Object.keys(ROSTER.proposer).join(', ')}) with what is missing.
- \`owner-concern\` only for a serious security, privacy, cost or best-practice concern that is the primary factor, or a PRD defect (the PRD contradicts itself, or lacks a value only the owner can give), each in \`ownerConcerns\` with its evidence. A difference from the effective version is not an owner concern: a design that changes the effective version with its reason and evidence is the normal case.
Set \`round\` to ${n}.

Write ${DECISION_MD} (your decision as one readable Markdown document) and ${DECISION_JSON} (your complete structured result, exactly as you return it, as ONE JSON object) with the Write tool, replacing each if it exists (Read it first if the Write tool asks). Write no other file.`,
    { label: `decide:round${n}`, phase: 'Decide', agentType: 'agent-teams-workforce:architecture-decider', effort: 'high', schema: DECISION_SCHEMA }
  )
  if (dec) await recordFiles('decide:record', 'Decide', [DECISION_MD, DECISION_JSON])
  return dec
}

phase('Rounds')
let ready = false
while (!decision) {
  if (ready) {
    pendingGaps = await decisionGaps(`rounds:gaps-${lastRound}`)
    if (!pendingGaps.length) {
      const dec = await decide(lastRound)
      if (!dec) return { ok: false, stage: 'decide', reason: 'the architecture-decider returned nothing', ...died('Decide'), subject, survey }
      const concerns = (Array.isArray(dec.ownerConcerns) ? dec.ownerConcerns : []).filter((c) => c && hasText(c.concern))
      if (dec.verdict === 'owner-concern' || concerns.length) {
        if (!concerns.length) return { ok: false, stage: 'decide', reason: 'the architecture-decider raised an owner concern and named none', decision: dec, subject }
        return ownerConcern(dec)
      }
      if (dec.verdict === 'approve') {
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
  if (lastRound >= MAX_ROUNDS) {
    const gaps = pendingGaps.length ? pendingGaps : await decisionGaps('rounds:gaps-final')
    const why = `${MAX_ROUNDS} round(s) ran and the target is not ready for a decision: ${gaps.join('; ') || 'the coordinator never declared it ready'}`
    log(`Rounds: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, gaps, subject, survey, ...died('Rounds') }
  }
  const n = lastRound + 1
  if (!pendingGaps.length && n > 1) pendingGaps = await decisionGaps(`rounds:gaps-${n - 1}`)
  const plan = await run(
    `You are the architecture-decision-workflow-coordinator. Name the dispatches for round ${n} of at most ${MAX_ROUNDS}; the script runs them. You read and route; you design, review and decide nothing, write nothing, and dispatch nothing yourself.

PRD: ${prdRef}
THE SURVEY: ${SURVEY_MD} and ${SURVEY_JSON}. The target's subject is ${subjectName}; its folder is \`target/${subject}/\`.
THE DRAFT TARGET: ${DRAFT} (arc42 section layout; \`delta/\` holds the change alone).
EARLIER RESULTS: ${ROUNDS_DIR}.
THE ARCHITECTURE: ${archPath} (\`arc42/\` effective; \`target/\` open targets).

THE ROSTER (role: agent — what it covers):
${rosterText}

THE LEDGER (claims, reviewer verdicts, findings and answers so far):
${ledgerText()}

WHAT STANDS BETWEEN THE DRAFT AND A DECISION:
${pendingGaps.length ? pendingGaps.map((g) => `- ${g}`).join('\n') : n === 1 ? '- nothing is written yet' : '- nothing'}
${forced.length ? `\nTHE ARCHITECTURE-DECIDER RETURNED THE TARGET to: ${forced.map((f) => `${f.agentType} (missing: ${f.missing})`).join('; ')}. The script dispatches each of them this round.` : ''}${rejected.length ? `\nDISPATCHES REFUSED LAST ROUND: ${rejected.join('; ')}` : ''}${silentLast.length ? `\nDISPATCHES THAT RETURNED NOTHING LAST ROUND: ${silentLast.join(', ')}` : ''}

HOW TO ROUTE:
- Size the team to the PRD: dispatch the proposers whose concern the PRD changes, and no others (no persistence proposer when nothing is persisted). A PRD the effective version already serves still gets one proposer, writing a delta that says the effective version serves it.
- Give each writer dispatch the draft files it owns this round, relative to the draft folder; two writers in one round never own the same file.
- Every claim gets a reviewer verdict: dispatch reviewers for the claims not yet reviewed, and a cost reviewer for claims about cost.
- Every open finding is answered by its owner: put its id in that writer's \`answers\`. A finding with no owner is yours to assign to a writer. The script adds the owner's dispatch when you leave one out.
- Dispatch diagram authors to draw the views the proposers describe, once the design is written.
- Writers run first and reviewers after them in the same round, so a reviewer sees this round's writing.
- Set \`readyForDecision\` true, with no dispatches, only when the list above says nothing stands between the draft and a decision.`,
    { label: `round${n}:coordinate`, phase: 'Rounds', agentType: 'agent-teams-workforce:architecture-decision-workflow-coordinator', effort: 'medium', schema: COORDINATOR_SCHEMA }
  )
  if (!plan) return { ok: false, stage: 'rounds', reason: `the coordinator returned no plan for round ${n}`, ...died('Rounds'), subject, survey }
  const settled = settleDispatches(plan, n)
  rejected = settled.rejected
  forced = []
  if (rejected.length) log(`Round ${n}: refused ${rejected.join('; ')}`)
  if (settled.stuck.length) {
    const why = `finding(s) stayed unanswered after their owner was told once that its result left them unanswered: ${settled.stuck.join('; ')}`
    log(`Round ${n}: ${why}`)
    return { ok: false, stage: 'rounds', reason: why, error: why, subject, survey, retries }
  }
  for (const r of retries.filter((x) => x.step.startsWith(`round${n}:`))) log(`Round ${n}: re-dispatch — ${r.whatChanged}`)
  if (!settled.dispatches.length) {
    if (plan.readyForDecision === true) {
      lastRound = n
      ready = true
      continue
    }
    const why = `the coordinator dispatched nothing in round ${n} and did not declare the target ready: ${plan.reason || 'no reason given'}`
    return { ok: false, stage: 'rounds', reason: why, error: why, rejected, subject, survey }
  }
  log(`Round ${n}: ${settled.dispatches.map((d) => `${d.role}:${d.agentType}`).join(', ')}`)
  for (const d of settled.dispatches) for (const id of d.answers) asked.set(id, { agentType: d.agentType, round: n, clarified: (d.clarified || []).includes(id) })
  const silent = await runRound(n, settled.dispatches)
  silentLast = silent
  if (silent.length) log(`Round ${n}: no result from ${silent.join(', ')}`)
  lastRound = n
  pendingGaps = []
  ready = plan.readyForDecision === true
}
const guardRounds = await constraintsGuard(before, 'constraints:after-rounds', 'Rounds')
if (guardRounds) return { ...guardRounds, subject }
const treeRounds = await treeSnapshot('tree:after-rounds', 'Rounds')
if (!treeRounds || treeRounds.error) {
  const why = `the architecture could not be fingerprinted after the rounds: ${(treeRounds && treeRounds.error) || 'no result'}`
  return { ok: false, stage: 'rounds', reason: why, error: why, subject, ...died('Rounds') }
}
const roundWrites = diffFiles(treeDiff(treeBefore, treeRounds))
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
Report every file you changed, created or deleted as an absolute path under ${ARC42}, every view the catalog listed for a changed element and what you did to it, and every contradiction with another effective view or open target.`
const updateBrief = persistBrief([UPDATE_JSON], 'your complete structured result, exactly as you return it, as ONE JSON object')
const savedUpdate = saved['architecture-update.json'] && typeof saved['architecture-update.json'] === 'object' ? saved['architecture-update.json'] : null
const INTEGRATE_BEFORE = `${WORK}/integrate-before.json`
const savedTree = saved['integrate-before.json'] && saved['integrate-before.json'].files ? saved['integrate-before.json'] : null
const integrateBefore = savedTree || (await treeSnapshot('tree:before-integrate', 'Integrate', INTEGRATE_BEFORE))
if (!integrateBefore || integrateBefore.error) {
  const why = `the architecture could not be fingerprinted before the integration: ${(integrateBefore && integrateBefore.error) || 'no result'}`
  return { ok: false, stage: 'integrate', reason: why, error: why, decision, subject, targetDir, deltaDir, ...died('Integrate') }
}
if (savedUpdate && !savedTree) log('Integrate: no fingerprint was saved before the earlier integration pass; its files are taken from its report and this pass is measured')
const savedReviews = Object.keys(saved).filter((k) => /^conformance-\d+\.json$/.test(k)).sort((p, q) => Number(p.match(/\d+/)[0]) - Number(q.match(/\d+/)[0]))
const lastSavedReview = savedReviews.length ? saved[savedReviews[savedReviews.length - 1]] : null

let update = null
let reviewPass = savedReviews.length
const reusedSaved = !!(savedUpdate && lastSavedReview && lastSavedReview.conforms === true)
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
/** Adds to a report every file the integration wrote since `integrateBefore`, measured from the tree, so an unreported write is reviewed too; returns { update } or { failure }. */
async function measured(u, label) {
  const now = await treeSnapshot(label, 'Integrate')
  if (!now || now.error) {
    const why = `the architecture could not be fingerprinted after the integration: ${(now && now.error) || 'no result'}`
    return { failure: { ok: false, stage: 'integrate', reason: why, error: why, architectureUpdate: u, decision, subject, targetDir, deltaDir, ...died('Integrate') } }
  }
  const d = treeDiff(integrateBefore, now)
  const unreported = diffFiles(d).filter((f) => !allTouched(u).includes(f))
  if (unreported.length) log(`Integrate: files written and not reported, added to the review: ${unreported.join(', ')}`)
  const union = (key, extra) => [...new Set([...listed(u[key]), ...extra])]
  return { tree: now, update: { ...u, changedFiles: union('changedFiles', d.changed), createdFiles: union('createdFiles', d.created), deletedFiles: union('deletedFiles', d.deleted) } }
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
let lastTree = firstMeasure.tree
const bounds = await outOfBounds(update)
if (bounds) return bounds

/** Runs one conformance review; a changed file the review does not cover is a finding. `again` names the previous review's findings and the files the correction changed. */
async function review(again) {
  reviewPass += 1
  const againBlock = again
    ? `\nTHIS IS REVIEW ${reviewPass}. The previous review found the findings below, and correction ${again.correction} changed these files to answer them: ${again.changed.join(', ')}. Confirm each finding is resolved, and check the changed files as fully as the rest.\nPREVIOUS FINDINGS:\n${JSON.stringify(again.findings, null, 1)}\n`
    : ''
  const reviewFile = `${WORK}/conformance-${reviewPass}.json`
  const got = await run(
    `You are the architecture-conformance-reviewer. Check one integration of an approved target into the effective version; report findings and fix nothing.

THE APPROVED TARGET: ${targetDir} (the change alone in ${deltaDir}).
THE INTEGRATION REPORT: ${UPDATE_JSON}. The files it changed or created, every one of which you review:
${touched(update).map((f) => `- ${f}`).join('\n') || '- (none)'}
Files it deleted: ${listed(update.deletedFiles).join(', ') || '(none)'}
${againBlock}
${ARCH_WHERE}

Check that the integration applied the approved target exactly, no more and no less; that every effective view the catalog lists for each changed element was updated or deleted, at every scope; that the new views sit in the section folders the model names with catalog frontmatter true to what they show; that no superseded content remains beside the new and no view contradicts another or an open target; and that nothing under ${CONSTRAINTS} changed. Return in \`reviewedFiles\` the absolute path of every file you checked and found conforming, and one finding per problem with its file and evidence; \`conforms\` is true only when there is no finding.${persistBrief([reviewFile], 'your complete structured result, exactly as you return it, as ONE JSON object')}`,
    { label: `integrate:review-${reviewPass}`, phase: 'Integrate', agentType: 'agent-teams-workforce:architecture-conformance-reviewer', effort: 'medium', schema: CONFORMANCE_SCHEMA }
  )
  return got ? covered(got) : null
}
/** Marks a review not conforming when it leaves a changed file unreviewed. */
function covered(c) {
  const missed = touched(update).filter((f) => !listed(c.reviewedFiles).includes(f))
  if (!missed.length) return c
  return { ...c, conforms: false, findings: [...(Array.isArray(c.findings) ? c.findings : []), ...missed.map((f) => ({ file: f, finding: 'changed or created by the integration and not reviewed', evidence: 'absent from reviewedFiles' }))] }
}

let conformance = lastSavedReview && lastSavedReview.conforms === true && reusedSaved ? covered(lastSavedReview) : null
if (!conformance || conformance.conforms !== true) conformance = await review()
if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
let corrections = 0
while (conformance.conforms !== true && corrections < MAX_CORRECTIONS) {
  corrections += 1
  const fixed = await run(
    `You are the architecture-maintainer, CORRECTING your integration (correction ${corrections} of ${MAX_CORRECTIONS}). The architecture-conformance-reviewer found the findings below. Correct each one in place, then return the complete report of the integration, every pass together.

FINDINGS:
${JSON.stringify(conformance.findings || [], null, 1)}

${INTEGRATE_TASK}${updateBrief}`,
    { label: `integrate:correct-${corrections}`, phase: 'Integrate', agentType: 'architecture-maintainer', effort: 'medium', schema: MAINTAIN_SCHEMA }
  )
  if (!fixed) return { ok: false, stage: 'integrate', reason: `the architecture-maintainer returned no result for correction ${corrections}`, ...died('Integrate'), decision, subject, targetDir, deltaDir }
  const merged = (key) => [...new Set([...listed(update[key]), ...listed(fixed[key])])]
  const fixMeasure = await measured({ ...fixed, changedFiles: merged('changedFiles'), createdFiles: merged('createdFiles'), deletedFiles: merged('deletedFiles') }, `tree:after-correct-${corrections}`)
  if (fixMeasure.failure) return fixMeasure.failure
  update = fixMeasure.update
  const fixedBounds = await outOfBounds(update)
  if (fixedBounds) return fixedBounds
  const changedNow = diffFiles(treeDiff(lastTree, fixMeasure.tree))
  lastTree = fixMeasure.tree
  if (!changedNow.length) {
    const why = `correction ${corrections} changed no file, so a further review would judge the same integration; the findings stand: ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
    log(`Integrate: ${why}`)
    return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir, retries }
  }
  const whatChanged = `correction ${corrections} changed ${changedNow.join(', ')} to answer ${(conformance.findings || []).length} finding(s)`
  retries.push({ step: 'integrate:review', attempt: reviewPass + 1, whatChanged })
  log(`Integrate: review again — ${whatChanged}`)
  conformance = await review({ correction: corrections, changed: changedNow, findings: conformance.findings || [] })
  if (!conformance) return { ok: false, stage: 'integrate', reason: 'the architecture-conformance-reviewer returned no result', ...died('Integrate'), decision, subject, targetDir, deltaDir, architectureUpdate: update }
}
if (conformance.conforms !== true) {
  const why = `the integration does not conform after ${corrections} correction pass(es): ${(conformance.findings || []).map((f) => `${f.file}: ${f.finding}`).join('; ')}`
  log(`Integrate: ${why}`)
  return { ok: false, stage: 'integrate', reason: why, error: why, conformance, architectureUpdate: update, decision, subject, targetDir, deltaDir }
}
const guardIntegrate = await constraintsGuard(before, 'constraints:after-integrate', 'Integrate')
if (guardIntegrate) return { ...guardIntegrate, subject, targetDir, deltaDir, architectureUpdate: update }

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
  openItems: [...listed(update.constraintIssues), ...listed(update.contradictions)],
}
