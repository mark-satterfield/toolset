export const meta = {
  name: 'architecture',
  description:
    'Leaf mini — turns an architecture question into a ruled decision and an updated arc42 SAD. It extracts SAD §2/§4/§8 (or reuses the extract the caller passes), takes the analysis dimensions from the caller or from a read-only triage session, collects proposals from the selected analysts unless triage rules the question settled, has the architecture-decider rule, and has the sad-maintainer write the ruling into the SAD (resuming once when the first pass returns nothing). An entry at lifecycle_state: effective, the approved state, is used as given and never re-decided; the decider reviews every other entry the ruling relies on and names those it approves as they stand. Returns approvedFiles, the SAD files holding those entries, beside sadUpdate.changedFiles; the caller sets both to effective. A ruling with no admissible option writes nothing to the SAD and returns ok:false with the blocking rules as requiredHumanActions.',
  phases: [
    { title: 'Extract SAD', detail: 'inventory the SAD files holding §2/§4/§8 and extract them in concurrent shards' },
    { title: 'Triage', detail: 'classify the decision and select the analysis dimensions, unless the caller supplied them' },
    { title: 'Proposals', detail: 'the selected analysts propose options concurrently; skipped when triage rules the question settled' },
    { title: 'Decide', detail: 'the architecture-decider rules on the proposals, or by citing the SAD when the question is settled, and names the entries in review it approves as they stand' },
    { title: 'Update SAD', detail: 'the sad-maintainer writes the ruling into §2/§4/§8' },
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

// args: { decision: { id?, title, context, drivers?, repoPath? }, sadPath, sadExtract?, feedback?,
//   dimensions?, forceFullPanel?, standingRulings?, artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? } }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

const ART = a.artifacts && typeof a.artifacts === 'object' && typeof a.artifacts.dir === 'string' && a.artifacts.dir ? a.artifacts : null
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(name, what, opts) {
  if (!ART) return ''
  const o = opts || {}
  const file = `${ART.dir}/${name}`
  const inputs = (Array.isArray(ART.inputs) ? ART.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${ART.script} record ${file} --epic ${ART.epicId} --phase ${ART.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  if (o.beadKey && typeof ART.relDir === 'string' && ART.relDir && typeof ART.beadId === 'string' && ART.beadId) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${ART.beadId} --set-metadata artifact_${o.beadKey}_path=${ART.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. No other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}

const d = a.decision || {}
const sadPath = typeof a.sadPath === 'string' ? a.sadPath.trim() : ''
const repo = d.repoPath || '(repo path not provided)'
const upstream = a.feedback ? `\nUpstream gate feedback to fold in:\n${a.feedback}` : ''

if (!sadPath) {
  const why = "no sadPath supplied (the project's ATW_SAD_PATH) — there is no SAD to rule against or write the ruling into. Set ATW_SAD_PATH for the run, or pass sadPath to this mini."
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}

const decisionHeader = `Architecture decision ${d.id || ''}: ${d.title || '(untitled)'}
Context: ${d.context || 'n/a'}
Decision drivers: ${(Array.isArray(d.drivers) ? d.drivers : []).join('; ') || 'n/a'}
Work within the repository at: ${repo}${upstream}`

const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim() : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output.

${rulingsText}

END STANDING RULINGS

`
  : ''

const PROPOSAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'options', 'recommendation'],
  properties: {
    lens: { type: 'string' },
    options: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name', 'approach', 'pros', 'cons'],
        properties: {
          name: { type: 'string' },
          approach: { type: 'string' },
          pros: { type: 'array', items: { type: 'string' } },
          cons: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    recommendation: { type: 'string' },
  },
}

const CONTEXT_MAP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['contexts', 'relationships'],
  properties: {
    contexts: { type: 'array', items: { type: 'string' } },
    relationships: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['from', 'to', 'kind'],
        properties: { from: { type: 'string' }, to: { type: 'string' }, kind: { type: 'string' } },
      },
    },
  },
}

const FAILURE_MODES_ITEMS = {
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['failure', 'affects', 'blastRadius'],
    properties: { failure: { type: 'string' }, affects: { type: 'string' }, blastRadius: { type: 'string' } },
  },
}

const ALL_DIMENSIONS = ['integration', 'security', 'cost', 'persistence', 'cdk', 'bounded-context', 'failure-mode']

const TRIAGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['settled', 'rationale', 'relevantDecisions', 'dimensions'],
  properties: {
    settled: { type: 'boolean' },
    rationale: { type: 'string' },
    relevantDecisions: { type: 'array', items: { type: 'string' } },
    dimensions: { type: 'array', items: { type: 'string' } },
  },
}

phase('Extract SAD')

const isExtract = (x) =>
  !!x && typeof x === 'object' && ['constraints', 'solutionStrategy', 'crosscuttingConcepts'].every((k) => Array.isArray(x[k]))

const SHARD_TARGET_BYTES = 175000
const SHARD_MAX_FILES = 16
const ASSUMED_BYTES = 20000

const readingRule = `READING RULE (binding): read EVERY file assigned to you below, IN FULL. Do NOT read any file outside the SAD, and do not survey the product repository or any other repository for architecture content. A section the SAD does not state comes back empty; it is never reconstructed from code.`

const sadWhere = `SAD location (read here, and only here): ${sadPath}
This path is NOT inside the product repository this decision is about. Do not look for the SAD under ${repo}.`

const feedSchema = () => ({
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['id', 'statement', 'source', 'lifecycleState'],
    properties: { id: { type: 'string' }, statement: { type: 'string' }, source: { type: 'string' }, lifecycleState: { type: 'string' } },
  },
})
const extractSchema = {
  type: 'object',
  additionalProperties: false,
  required: ['constraints', 'solutionStrategy', 'crosscuttingConcepts'],
  properties: {
    constraints: feedSchema(),
    solutionStrategy: feedSchema(),
    crosscuttingConcepts: feedSchema(),
    sadLocation: { type: 'string' },
    notes: { type: 'string' },
  },
}

function extractShard(label, feeds, files) {
  return run(
    `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for an architecture decision. Do NOT author anything, do NOT change any file, and invent NOTHING the SAD does not state.

${sadWhere}

YOUR ASSIGNMENT — these arc42 sections and no others:
${feeds.map((f) => `- ${f.title}`).join('\n')}

FILES ASSIGNED TO YOU (${files.length}) — read every one of them in full:
${files.map((f) => `- ${f}`).join('\n')}

${readingRule}

Other sessions are extracting the rest of this SAD concurrently. Extract ONLY the sections assigned to you, from ONLY the files assigned to you, and return the feeds you were not assigned as empty arrays.

For every entry: set its ID, capture the verbatim-grounded statement, note its source location (file:section/anchor) starting with the file's absolute path, and set \`lifecycleState\` to the \`lifecycle_state\` value in the YAML frontmatter of the file that holds it, copied exactly (an empty string when the file has none). If an assigned section is absent from your files, return it as an empty array.

THE ID IS THE SAD'S OWN TAG, COPIED EXACTLY. Most entries open with a backticked tag such as \`C-apigw-construct\`, \`S-…\`, \`X-uniform-zero-egress\` or \`AD-…\`; that tag, character for character, is the entry's ID. Only an entry with no tag gets a made-up ID, and then it is \`<file name without .md>--<kebab-case of the nearest heading>\`, with \`-2\`, \`-3\` appended in document order when one heading holds several untagged entries.
Return every entry your files state; never consolidate, trim or omit an entry.`,
    { label, phase: 'Extract SAD', effort: 'low', agentType: 'agent-teams-workforce:sad-source-extractor', schema: extractSchema }
  )
}

function shardFiles(entries) {
  const shards = []
  let current = []
  let bytes = 0
  for (const e of entries) {
    const size = e.bytes > 0 ? e.bytes : ASSUMED_BYTES
    if (current.length >= SHARD_MAX_FILES || (current.length && bytes + size > SHARD_TARGET_BYTES)) {
      shards.push(current)
      current = []
      bytes = 0
    }
    current.push(e)
    bytes += size
  }
  if (current.length) shards.push(current)
  return shards
}

const fileList = (x) =>
  (Array.isArray(x) ? x : [])
    .map((e) => (typeof e === 'string' ? { path: e } : e))
    .filter((e) => e && typeof e.path === 'string' && e.path.trim())
    .map((e) => ({ path: e.path.trim(), bytes: Number(e.bytes) || 0 }))

let sadExtract = isExtract(a.sadExtract) ? a.sadExtract : null
let crossFiles = []

if (!sadExtract) {
  const inventory = await run(
    `You are READ-ONLY and you are taking an INVENTORY, not an extract. Do not extract any content and change no file.

${sadWhere}

Resolve the arc42 layout (single-file vs one-file-per-section) and list EVERY file that holds the content of these sections, with its size in bytes read with \`stat\` (\`stat -f '%z' <file>\` on macOS, \`stat -c '%s' <file>\` on Linux):
- Section 2 — Constraints
- Section 4 — Solution Strategy
- Section 8 — Crosscutting Concepts

A section held in a DIRECTORY is listed as all of its content files, recursively — every concept file, not the directory and not its README index. Where a section's content lives inside one larger file, list that file under every section it holds. List only files inside the SAD. If a section has no files, return it as an empty array.`,
    {
      label: 'inventory:sad',
      phase: 'Extract SAD',
      effort: 'low',
      agentType: 'agent-teams-workforce:sad-source-extractor',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['constraintsFiles', 'solutionStrategyFiles', 'crosscuttingFiles'],
        properties: {
          constraintsFiles: { $ref: '#/$defs/files' },
          solutionStrategyFiles: { $ref: '#/$defs/files' },
          crosscuttingFiles: { $ref: '#/$defs/files' },
          sadLocation: { type: 'string' },
          layout: { type: 'string' },
          notes: { type: 'string' },
        },
        $defs: {
          files: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['path'],
              properties: { path: { type: 'string' }, bytes: { type: 'number' } },
            },
          },
        },
      },
    }
  )
  if (!inventory) {
    const why = `the SAD inventory at ${sadPath} returned nothing, so no extraction was attempted and nothing was ruled.`
    return { ok: false, stage: 'extract', error: why, reason: why, ...died('Extract SAD') }
  }

  const coreEntries = []
  for (const e of [...fileList(inventory.constraintsFiles), ...fileList(inventory.solutionStrategyFiles)]) {
    if (!coreEntries.some((c) => c.path === e.path)) coreEntries.push(e)
  }
  const crossEntries = fileList(inventory.crosscuttingFiles)
  crossFiles = crossEntries.map((e) => e.path)
  const crossShards = shardFiles(crossEntries)
  log(`SAD inventory: §2+§4 = ${coreEntries.length} file(s); §8 = ${crossEntries.length} file(s) in ${crossShards.length} shard(s)`)

  const jobs = []
  if (coreEntries.length) {
    jobs.push({
      label: 'extract:sad-core',
      feeds: [{ key: 'constraints', title: 'Section 2 — Constraints' }, { key: 'solutionStrategy', title: 'Section 4 — Solution Strategy' }],
      entries: coreEntries,
    })
  }
  crossShards.forEach((entries, i) => {
    jobs.push({
      label: `extract:sad-crosscutting-${i + 1}of${crossShards.length}`,
      feeds: [{ key: 'crosscuttingConcepts', title: 'Section 8 — Crosscutting Concepts' }],
      entries,
    })
  })

  const outs = await parallel(jobs.map((j) => () => extractShard(j.label, j.feeds, j.entries.map((e) => e.path))))
  const merged = { constraints: [], solutionStrategy: [], crosscuttingConcepts: [] }
  const notes = []
  jobs.forEach((job, i) => {
    const out = outs[i]
    if (!out) {
      log(`${job.label}: returned nothing — ${job.entries.length} SAD file(s) not extracted: ${job.entries.map((e) => e.path).join(', ')}`)
      return
    }
    if (typeof out.notes === 'string' && out.notes.trim()) notes.push(`[${job.label}] ${out.notes.trim()}`)
    for (const feed of job.feeds) {
      for (const entry of Array.isArray(out[feed.key]) ? out[feed.key] : []) {
        if (!entry || typeof entry !== 'object') continue
        merged[feed.key].push({
          id: String(entry.id || ''),
          statement: String(entry.statement || ''),
          source: String(entry.source || ''),
          lifecycleState: String(entry.lifecycleState || '').trim(),
        })
      }
    }
  })
  sadExtract = {
    ...merged,
    sadLocation: (typeof inventory.sadLocation === 'string' && inventory.sadLocation) || sadPath,
    notes: notes.join('\n'),
  }
  log(
    `SAD extracted: ${merged.constraints.length} constraint(s), ${merged.solutionStrategy.length} strategy statement(s), ` +
      `${merged.crosscuttingConcepts.length} crosscutting concept(s) from ${jobs.length} batch(es)`
  )
}

const sadHome = sadExtract.sadLocation || sadPath
const APPROVED_STATE = 'effective'
const stateOf = (e) => (e && typeof e.lifecycleState === 'string' && e.lifecycleState.trim()) || 'state not extracted'
const APPROVAL_RULE = `APPROVED ENTRIES ARE SETTLED. \`lifecycle_state: ${APPROVED_STATE}\` is the approved state: an entry whose file's frontmatter reads it has been vetted and approved, is used as given, and is never re-decided. Only an entry in any other state is open to review. The state shown beside each entry is its file's \`lifecycle_state\`; for an entry you open, read that field in the file.`
const renderFeed = (title, entries) =>
  `${title} (${entries.length}):\n` +
  (entries.length ? entries.map((e) => `- [${e.id}] (${stateOf(e)}) ${e.statement}${e.source ? ` (${e.source})` : ''}`).join('\n') : '- (the SAD states none)')

const sourceFile = (e) => {
  const m = String((e && e.source) || '').trim().match(/^\/[^\s:#]+/)
  return m ? m[0] : ''
}

function crosscuttingIndex(entries) {
  const byFile = new Map()
  for (const e of Array.isArray(entries) ? entries : []) {
    if (!e || typeof e !== 'object') continue
    const f = sourceFile(e)
    if (!byFile.has(f)) byFile.set(f, [])
    byFile.get(f).push(e)
  }
  const snip = (t) => {
    const x = String(t || '').replace(/\s+/g, ' ').trim()
    return x.length > 40 ? `${x.slice(0, 40)}…` : x
  }
  const groups = [...byFile.entries()].map(
    ([f, es]) => `${f || `(no source file recorded — find these by id under the §8 section at ${sadHome})`} (${stateOf(es[0])})\n${es.map((e) => `  - [${e.id}] ${snip(e.statement)}`).join('\n')}`
  )
  return `§8 Crosscutting Concepts (${Array.isArray(entries) ? entries.length : 0}) — an INDEX, not the text: each line is an entry's id and the opening of its statement, grouped by the SAD file that states it, with that file's \`lifecycle_state\`.
READ IN FULL every entry this question touches before you rely on it or rule past it: grep the file it is listed under for its id.
${groups.join('\n') || '- (the SAD states none)'}`
}

const sadBlock = `THE ARCHITECTURE AS IT STANDS — the arc42 SAD source feed, extracted for this run from ${sadHome}: §2 and §4 in full, §8 as an index.
This is the document your work is ruled against and written back into. Cite entries by the id in brackets.
${APPROVAL_RULE}
${sadExtract.notes ? `Extractor notes: ${sadExtract.notes}\n` : ''}
${renderFeed('§2 Constraints', sadExtract.constraints)}

${renderFeed('§4 Solution Strategy', sadExtract.solutionStrategy)}

${crosscuttingIndex(sadExtract.crosscuttingConcepts)}`

if (!crossFiles.length) {
  for (const e of sadExtract.crosscuttingConcepts || []) {
    const f = sourceFile(e)
    if (f && !crossFiles.includes(f)) crossFiles.push(f)
  }
}
const analystSadBlock = `THE ARCHITECTURE AS IT STANDS — §2 Constraints and §4 Solution Strategy of the arc42 SAD, extracted for this run from ${sadHome}. Cite entries by the id in brackets.
${APPROVAL_RULE} Your options take every approved entry as given; an entry in any other state is open, and an option may keep, refine or replace it.
${renderFeed('§2 Constraints', sadExtract.constraints)}

${renderFeed('§4 Solution Strategy', sadExtract.solutionStrategy)}

§8 Crosscutting Concepts holds ${sadExtract.crosscuttingConcepts.length} entries and is NOT printed here. Grep these files for the subjects of this decision, read only the entries your searches hit, and cite each entry you rely on by the backticked tag that opens it:
${crossFiles.length ? crossFiles.map((f) => `- ${f}`).join('\n') : `- the §8 Crosscutting Concepts section under ${sadPath}`}`

phase('Triage')

const forcedDimensions = Array.isArray(a.dimensions) ? a.dimensions.filter((x) => ALL_DIMENSIONS.includes(x)) : []
let triage = null
let activeDimensions = ALL_DIMENSIONS
if (a.forceFullPanel !== true && forcedDimensions.length) {
  activeDimensions = forcedDimensions
  log(`Triage skipped: the caller selected ${activeDimensions.join(', ')}`)
} else if (a.forceFullPanel !== true) {
  triage = await run(
    `${rulingsBlock}You are the architecture-boundary-guardian acting as the READ-ONLY triage step. Classify this decision against the existing arc42 SAD — do NOT rule on it, do NOT author options, do NOT edit anything. SAD location: ${sadPath}.

Return settled=true when the SAD already answers this question, or when it is a routine variation on a settled pattern; otherwise settled=false. An entry whose frontmatter reads \`lifecycle_state: ${APPROVED_STATE}\` is approved: it answers what it states, as given — open the entry and read that field. An entry in any other state answers nothing until the architecture-decider reviews it, so a question that rests on such an entry is settled=false. Cite in relevantDecisions the SAD sections that bear on it, and explain the classification in rationale. In dimensions, name ONLY the axes that genuinely bear on the choice, drawn from ${JSON.stringify(ALL_DIMENSIONS)}.

${decisionHeader}`,
    { label: 'triage:classify', effort: 'low', phase: 'Triage', agentType: 'agent-teams-workforce:architecture-boundary-guardian', schema: TRIAGE_SCHEMA }
  )
  const picked = triage && Array.isArray(triage.dimensions) ? triage.dimensions.filter((x) => ALL_DIMENSIONS.includes(x)) : []
  if (picked.length) activeDimensions = picked
}
const settled = !!(triage && triage.settled === true)
if (settled) {
  activeDimensions = []
  log(`Triage: SETTLED — ${triage.rationale}`)
} else {
  log(`Analysts selected: ${activeDimensions.join(', ')}`)
}

const SURVEY_BOUND = `READING BUDGET — this is a bounded proposal, not a codebase audit.
Your inputs are the framing above and the SAD printed with it — §2 Constraints and §4 Solution Strategy whole, and the §8 Crosscutting Concepts files to search for your lens. Reason from it first, and cite the entries you rely on by their id. The SAD lives in a different repository from the product repo named above.
Beyond your §8 searches, open files ONLY to resolve a specific question the framing leaves unanswered. Do not survey the repository and do not enumerate services or repositories. Roughly ten tool calls is the expected shape.

Return at most 3 options with honest tradeoffs. Keep every tradeoff, failure mode and assumption under 30 words.`

const makers = [
  {
    agentType: 'agent-teams-workforce:integration-pattern-architect',
    dim: 'integration',
    lens: 'integration/decomposition',
    ask: 'Propose the integration and service-decomposition approach: event-driven flows, service boundaries, and the tradeoffs of each option. Honor the platform constraints (event-driven only — no Step Functions; service isolation; SSM for cross-stack refs).',
  },
  {
    agentType: 'agent-teams-workforce:security-architecture-designer',
    dim: 'security',
    lens: 'security',
    ask: 'Propose the security architecture: trust boundaries, authn/authz placement, data protection, and surface the security tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cost-architecture-reviewer',
    dim: 'cost',
    lens: 'cost',
    ask: 'Assess the cost-architecture tradeoffs of each option: cost drivers, scaling cost shape, and which option is most cost-efficient for the stated drivers.',
  },
  {
    agentType: 'agent-teams-workforce:persistence-architecture-specialist',
    dim: 'persistence',
    lens: 'persistence',
    ask: 'Propose the persistence approach: DynamoDB single- vs multi-table design, key schema, GSI/LSI strategy, and the access-pattern tradeoffs of each option.',
  },
  {
    agentType: 'agent-teams-workforce:cdk-infrastructure-designer',
    dim: 'cdk',
    lens: 'cdk-infrastructure',
    ask: 'Propose the CDK construct topology: Lambda boundaries within the chassis, layer/packaging strategy, and the infrastructure tradeoffs of each option.',
  },
]

let proposals = []
let contextMap = null
let failureModes = []
if (!settled) {
  phase('Proposals')
  const frameBlock = `Panel framing:
Analysis axes on this decision: ${activeDimensions.join(', ')}
Propose from YOUR lens only. The other axes are covered by the analysts dispatched alongside you, and the architecture-decider composes one ruling from all of them.`
  const activeMakers = makers.filter((m) => activeDimensions.includes(m.dim))
  const wantsContextMap = activeDimensions.includes('bounded-context')
  const wantsFailureModes = activeDimensions.includes('failure-mode')

  const jobs = activeMakers.map((m) => () =>
    run(`${rulingsBlock}${m.ask}\n\n${decisionHeader}\n\n${analystSadBlock}\n\n${frameBlock}\n\n${SURVEY_BOUND}`, {
      label: `proposals:${m.lens}`,
      phase: 'Proposals',
      agentType: m.agentType,
      schema: PROPOSAL_SCHEMA,
      effort: 'low',
    })
  )
  if (wantsContextMap || wantsFailureModes) {
    jobs.push(() =>
      run(
        `${rulingsBlock}You are a read-only architecture analysis advisor. Produce the analysis artifact(s) named below in one pass, each under its own key. Do NOT rule or author options.
${wantsContextMap ? `
- \`contextMap\`: map the domain boundaries and context relationships this decision touches — which bounded contexts are involved and how they relate (upstream/downstream, conformist, anti-corruption layer).` : ''}${wantsFailureModes ? `
- \`failureModes\`: model the failure modes the proposed directions must withstand — DynamoDB throttling, duplicate event delivery, downstream unavailability, partial-batch failures, poison messages. For each, name the failure, what it affects, and its blast radius.` : ''}

${decisionHeader}

${analystSadBlock}

${frameBlock}

${SURVEY_BOUND}`,
        {
          label: 'proposals:analysis-advisors',
          phase: 'Proposals',
          effort: 'low',
          agentType: wantsContextMap ? 'agent-teams-workforce:bounded-context-mapper' : 'agent-teams-workforce:failure-mode-analyst',
          schema: {
            type: 'object',
            additionalProperties: false,
            required: [...(wantsContextMap ? ['contextMap'] : []), ...(wantsFailureModes ? ['failureModes'] : [])],
            properties: {
              ...(wantsContextMap ? { contextMap: CONTEXT_MAP_SCHEMA } : {}),
              ...(wantsFailureModes ? { failureModes: FAILURE_MODES_ITEMS } : {}),
            },
          },
        }
      )
    )
  }
  const results = await parallel(jobs)
  proposals = results.slice(0, activeMakers.length).filter(Boolean)
  const advisors = wantsContextMap || wantsFailureModes ? results[activeMakers.length] : null
  if (advisors) {
    contextMap = advisors.contextMap || null
    failureModes = advisors.failureModes || []
  }
}

phase('Decide')

const evidenceBlock = settled
  ? `Triage classified this decision as SETTLED by the existing SAD, so no analyst panel ran.
Triage rationale: ${triage.rationale}
Relevant prior decisions: ${(Array.isArray(triage.relevantDecisions) ? triage.relevantDecisions : []).join('; ') || '(none)'}

Rule by CITING those prior decisions as the SAD states them. If they do not answer this question, say so in the ruling.`
  : `Proposals:
${JSON.stringify(proposals, null, 2)}

Analysis (context map + failure modes):
${JSON.stringify({ contextMap, failureModes }, null, 2)}`

const DECISION_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['admissible', 'ruling', 'imposedConstraints', 'resolvedChallenges', 'blockingRules', 'ruleChallenges', 'approvedEntries'],
  properties: {
    admissible: { type: 'boolean' },
    approvedEntries: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'file'],
        properties: { id: { type: 'string' }, file: { type: 'string' } },
      },
    },
    ruling: { type: 'string' },
    chosenApproach: { type: 'string' },
    imposedConstraints: { type: 'array', items: { type: 'string' } },
    resolvedChallenges: { type: 'array', items: { type: 'string' } },
    blockingRules: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'whyBlocking', 'classification'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          whyBlocking: { type: 'string' },
          classification: { type: 'string', enum: ['constitutive', 'convention'] },
        },
      },
    },
    ruleChallenges: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'source', 'recommendedChange', 'rationale'],
        properties: {
          rule: { type: 'string' },
          source: { type: 'string' },
          recommendedChange: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    },
  },
}

const DECIDER_CHARTER = `You are the architecture-decider. Rule on the architecture given the evidence below. You do not analyze and you do not write the SAD.

YOU HAVE THE SAD. Its source feed is below — §2 and §4 in full, and §8 as an index of every entry with where to read it. Your ruling is written back into those sections and becomes effective architecture, so rule AGAINST what they already state: an option that contradicts a standing entry in review is either wrong or is a deliberate supersession you must say you are making, naming the entry id. Open the §8 entries this ruling touches; do not survey the rest of the SAD.

APPROVED ENTRIES ARE SETTLED; THE REST THIS RULING RELIES ON, YOU REVIEW.
- An entry whose file reads \`lifecycle_state: ${APPROVED_STATE}\` is approved. Rule with it as given; this ruling never re-decides it. Where the PRD cannot be served without changing one, record a ruleChallenge naming it.
- Every entry in any other state that this ruling relies on, you review, reading it in full: approve it as it stands and list it in \`approvedEntries\` with its id and the absolute path of the SAD file that holds it, or change it in the ruling.
- The SAD files holding every entry this ruling creates, changes or approves are set to \`lifecycle_state: ${APPROVED_STATE}\` once the SAD is written.

YOUR AUTHORITY, AND ITS LIMITS:
- Normally you CHOOSE among the options proposed and state the ruling as a decision, not a discussion. Set admissible=true and fill chosenApproach.
- If NO proposed option can be ruled on, set admissible=false, leave chosenApproach empty, and populate blockingRules with the specific rules that eliminated every option.
- Classify every blocking rule as "constitutive" or "convention".
- CONSTITUTIVE is a real external constraint — an AWS service limit, a security fundamental, a legal or contractual obligation — AND the platform bans this project holds constitutive: no Step Functions, no HTTP API v2 (REST API v1 only), no FastAPI/Flask/Django, Powertools-only Lambdas, service isolation, SSM Parameter Store rather than CloudFormation exports for cross-stack refs, and dot-only event naming.
- CONVENTION is any other rule this project wrote for itself — a naming convention, a curated allowlist, a house pattern, a self-authored MUST in our own SAD.
- A convention MUST NOT be the reason delivery halts. If a convention is the only thing eliminating an otherwise sound design, rule it admissible and record a ruleChallenge against the convention.
- Where a CONVENTION conflicts with industry best practice or an AWS Well-Architected principle, BEST PRACTICE WINS. Record it in ruleChallenges with the change you recommend.
- A CONSTITUTIVE rule is never overridden. Rule on the options that honor it; if you believe the rule itself is wrong, honor it and record a ruleChallenge.
- ruleChallenges go to the human owner; they are never applied by this run.

ACCOUNT FOR EVERY SECURITY AND DATA-ISOLATION FINDING raised in the evidence, item by item: MITIGATED, with the mitigation stated as an entry in imposedConstraints; ACCEPTED RESIDUAL, with the remaining mitigations and the rationale stated as an entry in imposedConstraints; or OUT OF SCOPE, naming the requirement that owns it.

EVERY POINT ENDS RULED, OUT OF SCOPE (naming the requirement that owns it), or BLOCKING (admissible=false). Never write "referred", "to be determined", "pending" or "open question": your ruling is written into the SAD, which holds decided current state only. A rule challenge goes in ruleChallenges, never into the ruling, the chosen approach or the imposed constraints.`

const decision = await run(
  `${rulingsBlock}${DECIDER_CHARTER}

${decisionHeader}

${sadBlock}

${evidenceBlock}${persistBrief('architecture-decision.md', 'your ruling as ONE markdown document: whether an option is admissible, the ruling, the chosen approach, the imposed constraints, the challenges it resolves, the entries it approves as they stand, any blocking rules and rule challenges, and the rationale — the same content as your structured result', { beadKey: 'architecture_decision' })}`,
  { label: 'decide:ruling', effort: 'high', phase: 'Decide', agentType: 'agent-teams-workforce:architecture-decider', schema: DECISION_SCHEMA }
)

if (!decision) {
  return { ok: false, stage: 'decide', error: 'the architecture-decider returned nothing', ...died('Decide'), proposals, sadExtract }
}

const admissible = decision.admissible === true
const ruleChallenges = decision.ruleChallenges || []
const decisionName = d.id || d.title
const humanActions = ruleChallenges
  .filter((rc) => rc && typeof rc === 'object')
  .map((rc) => `RULE CHALLENGE from the architecture ruling on ${decisionName}: ${rc.rule} (${rc.source}) — recommended change: ${rc.recommendedChange}. Why: ${rc.rationale}`)

if (!admissible) {
  const blockingText = (decision.blockingRules || []).map((b) => `[${b.classification}] ${b.rule} (${b.source})`).join('; ')
  const why =
    `no admissible option — every option was eliminated by: ${blockingText || '(no blocking rule named)'}.` +
    (ruleChallenges.length ? ` ${ruleChallenges.length} rule challenge(s) are raised for the owner.` : '') +
    ' A person must change the PRD or the blocking rule before this architecture can be ruled.'
  log(`Decide: ${why}`)
  return {
    ok: false,
    stage: 'decide',
    admissible: false,
    deterministicFailure: true,
    reason: why,
    error: why,
    requiredHumanActions: [`ARCHITECTURE BLOCKED for ${decisionName}: ${why}`, ...humanActions],
    blockingRules: decision.blockingRules || [],
    ruleChallenges,
    panelDimensions: activeDimensions,
    sadExtract,
    proposals,
    decision,
  }
}

phase('Update SAD')

const entryFiles = new Map()
for (const e of [...(sadExtract.constraints || []), ...(sadExtract.solutionStrategy || []), ...(sadExtract.crosscuttingConcepts || [])]) {
  const f = sourceFile(e)
  if (e && e.id && f && !entryFiles.has(e.id)) entryFiles.set(e.id, f)
}
const approvedFiles = []
for (const x of Array.isArray(decision.approvedEntries) ? decision.approvedEntries : []) {
  if (!x || typeof x !== 'object') continue
  const f = entryFiles.get(String(x.id || '').trim()) || (typeof x.file === 'string' && x.file.trim().startsWith('/') ? x.file.trim() : '')
  if (f && !approvedFiles.includes(f)) approvedFiles.push(f)
}
log(`Decide: ${approvedFiles.length} SAD file(s) hold entries the ruling approves as they stand`)

const SAD_UPDATE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['updatedSections', 'changedFiles', 'approvedFiles', 'summary'],
  properties: {
    updatedSections: { type: 'array', items: { type: 'string' } },
    changedFiles: { type: 'array', items: { type: 'string' } },
    approvedFiles: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    openItems: { type: 'array', items: { type: 'string' } },
    collisions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['rule', 'where', 'collision'],
        properties: { rule: { type: 'string' }, where: { type: 'string' }, collision: { type: 'string' } },
      },
    },
    entryTags: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['tag', 'section', 'disposition'],
        properties: {
          tag: { type: 'string' },
          section: { type: 'integer' },
          disposition: { type: 'string', enum: ['minted', 'preserved', 'superseded'] },
          statement: { type: 'string' },
          supersededBy: { type: 'string' },
        },
      },
    },
  },
}

const SAD_TAG_BRIEF = `
TAG EVERY §2/§4/§8 ENTRY YOU WRITE, AND NEVER RECYCLE A TAG.
- Every entry in §2 Constraints, §4 Solution Strategy and §8 Crosscutting Concepts carries an explicit tag at the head of the entry in the form this SAD already uses (\`C-…\` for a constraint, \`S-…\` for a solution-strategy entry, \`X-…\` for a crosscutting concept, \`AD-…\` for a decision recorded in §9). Short, kebab-case, descriptive of the FACT.
- An entry that already has a tag KEEPS it, whatever you do to its wording.
- A tag is NEVER reused for a different fact. When this ruling overturns an entry, leave that entry's tag attached to the superseded statement, mark it superseded by the new tag, and mint a NEW tag for the replacement.
- Report every tag you minted, preserved or superseded under \`entryTags\`.`

const priorPassRefs = [
  ART ? `the file ${ART.dir}/sad-update.json, when it exists — the report an earlier pass wrote, whose \`entryTags\` and \`changedFiles\` name its entries` : '',
  ART ? `\`derived_from\` provenance and entries naming ${ART.epicId}` : '',
  d.id ? `entries naming decision ${d.id}` : '',
].filter(Boolean)
const PRIOR_PASS_BRIEF = `
AN EARLIER PASS OF THIS SAME RULING MAY ALREADY BE IN THE SAD. Before you write, look for its entries: ${priorPassRefs.length ? priorPassRefs.join('; ') : 'entries whose provenance names this decision'}. Grep for those tags; do not read the SAD end to end.
- An entry an earlier pass of this Epic wrote is THIS ruling's own draft. UPDATE IT IN PLACE under its existing tag and report it as \`preserved\`. Never append a second entry for the same fact under a new tag.
- If the ruling now decides a DIFFERENT fact than such an entry states, rewrite that entry to the new fact under a NEW tag and delete the old tag from the document. Report the old tag as \`superseded\`, with \`supersededBy\` naming the new one.
- Entries from OTHER Epics' rulings follow the ordinary tag rules above.`

const SAD_SAVE_WHAT = 'your complete structured result (updatedSections, changedFiles, approvedFiles, entryTags, openItems, summary — exactly as you return them) as ONE JSON object'
const APPROVED_FILES_BRIEF = `
THE RULING APPROVES THESE SAD FILES AS THEY STAND. Return this list, exactly as written, as \`approvedFiles\`:
${approvedFiles.length ? approvedFiles.map((f) => `- ${f}`).join('\n') : '- (none: return an empty list)'}
Leave the \`lifecycle_state\` frontmatter field of every SAD file as you find it: the run sets it on the files this ruling covers after you return.`
const SAD_SAVE_OPTS = { extraInputs: 'the absolute path of EVERY SAD file changed, each in single quotes' }
const rulingLines = `Ruling: ${decision.ruling}
Chosen approach: ${decision.chosenApproach || '(not stated separately — see the ruling)'}
Imposed constraints: ${(decision.imposedConstraints || []).join('; ') || 'none'}
Resolved challenges: ${(decision.resolvedChallenges || []).join('; ') || 'none'}`

let sadUpdate = await run(
  `You are the sad-maintainer. Consolidate the ruling below into the living arc42 SAD, editing ONLY the source-feed sections it touches: §2 Constraints, §4 Solution Strategy, §8 Crosscutting Concepts. Keep those sections mutually consistent. Edit the living document in place — no changelog narrative. SAD location: ${sadPath}.

SWEEP EVERY CLAIM YOU CHANGE. The sweep set is the entries this ruling MINTS, REWORDS or SUPERSEDES, plus the other SAD statements (including index/summary rows) that restate or cite one of them. Find those with one targeted grep per changed claim, on the old value and on the subject, and correct every hit that restates it. Do not touch entries outside that set.

READING BUDGET. Open and edit ONLY the sections this ruling touches and the hits your greps return. Do not read the SAD end to end and do not print whole files.

A COLLISION WITH OLDER CONTENT this ruling does not own is reported under \`collisions\`, naming the older rule and where it lives — never written into the SAD.

THE SAD HOLDS NO OPEN ITEMS. Never write into it an open question, an unresolved marker, a required action, a rule challenge, a referral, a "pending" or "TBD", or anything addressed to the owner. Everything still open goes in \`openItems\` in your result.

Never label the adopted option with a bare proposal letter; write its descriptive name.
${SAD_TAG_BRIEF}
${PRIOR_PASS_BRIEF}
${APPROVED_FILES_BRIEF}

If a \`derived_from\` entry asserts a state this ruling overturns, append a supersession marker naming this decision to that entry.

${rulingLines}

Deliver: which §2/§4/§8 sections you changed, the file paths edited, every entry tag you minted, preserved or superseded, the approved files, and a one-line summary of the change.${persistBrief('sad-update.json', SAD_SAVE_WHAT, SAD_SAVE_OPTS)}`,
  { label: 'sad:maintain', effort: 'medium', phase: 'Update SAD', agentType: 'agent-teams-workforce:sad-maintainer', schema: SAD_UPDATE_SCHEMA }
)
if (!sadUpdate) {
  sadUpdate = await run(
    `You are the sad-maintainer, RESUMING an interrupted pass. A previous sad-maintainer session consolidated the ruling below into the living arc42 SAD at ${sadPath} but ended before it returned its result. Its edits are already in the working tree.

Do NOT start over and do NOT re-read the whole SAD. Run \`git status --short\` and \`git diff --stat\` in the repository holding ${sadPath} to see what was changed, open only the changed files you need, finish any changed claim the previous pass left inconsistent (targeted grep only), and return. Keep §2/§4/§8 mutually consistent; no changelog narrative.
${SAD_TAG_BRIEF}
${PRIOR_PASS_BRIEF}
${APPROVED_FILES_BRIEF}

${rulingLines}

Deliver: which §2/§4/§8 sections were changed (by either pass), the file paths edited, every entry tag minted, preserved or superseded, the approved files, and a one-line summary of the change.${persistBrief('sad-update.json', SAD_SAVE_WHAT, SAD_SAVE_OPTS)}`,
    { label: 'sad:maintain-resume', effort: 'medium', phase: 'Update SAD', agentType: 'agent-teams-workforce:sad-maintainer', schema: SAD_UPDATE_SCHEMA }
  )
}

return {
  ok: !!sadUpdate,
  ...(sadUpdate ? {} : { stage: 'update-sad', error: 'the sad-maintainer returned no result', ...died('Update SAD') }),
  admissible,
  ruleChallenges,
  ...(humanActions.length ? { requiredHumanActions: humanActions } : {}),
  openItems: sadUpdate && Array.isArray(sadUpdate.openItems) ? sadUpdate.openItems : [],
  decisionRef: d.id || null,
  panelDimensions: activeDimensions,
  sadExtract,
  proposals,
  tradeoffs: proposals.map((p) => ({ lens: p.lens, recommendation: p.recommendation, options: p.options })),
  contextMap,
  failureModes,
  decision,
  decisionPath: ART ? `${ART.dir}/architecture-decision.md` : null,
  sadUpdate,
  entryTags: sadUpdate && Array.isArray(sadUpdate.entryTags) ? sadUpdate.entryTags : [],
  approvedFiles,
}
