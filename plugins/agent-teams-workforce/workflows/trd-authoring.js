export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus the arc42 SAD. Read-only extractor sessions pull SAD sections 2, 4 and 8 into a typed packet in concurrent shards (or a packet the caller supplies is reused), a filing-clerk session names the TRD file when the caller gives no path, then one trd-author session writes the TRD in one pass: PRD requirements that need technical elaboration plus the obligations the architecture imposes, each citing its PRD or SAD source.',
  phases: [
    { title: 'Extract SAD', detail: 'read-only extraction of the arc42 source feeds into a typed packet' },
    { title: 'Author TRD', detail: 'author the TRD from the PRD + SAD extract, one pass' },
  ],
}
const dispatchFailures = []
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  return named.length ? dispatchFailures.filter((f) => named.includes(f.phase)) : dispatchFailures.slice()
}
// Runs agent(); returns its result, or null after recording the failure in dispatchFailures.
async function settleAgent(prompt, opts) {
  const o = opts || {}
  const who = { agentType: o.agentType || null, label: o.label || null, phase: o.phase || null }
  const name = who.label || who.agentType || 'agent'
  try {
    const out = await agent(prompt, o)
    if (out) return out
    dispatchFailures.push({ ...who, outcome: 'skipped', note: `${name} returned nothing` })
    log(`${name}: returned nothing`)
  } catch (err) {
    const message = String((err && err.message) || err).slice(0, 300)
    dispatchFailures.push({ ...who, outcome: 'threw', message, note: `${name} ended without a structured result: ${message}` })
    log(`${name}: ended without a structured result — ${message}`)
  }
  return null
}

// args: {
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },
//   sad: { path?, sectionLayout? }, sadExtract?: { constraints, solutionStrategy, crosscuttingConcepts },
//   trdPath?, repoPath?, feedback?, standingRulings?,
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? }
// }
// returns { ok, trdPath, filingPath, sadExtract, trd, decisionIds } or { ok: false, stage, reason, ... }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  return ['dir', 'script', 'epicId', 'phase'].every((k) => typeof x[k] === 'string' && x[k]) ? x : null
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command:\n   ${record}\n   It prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  if (o.beadKey && typeof art.relDir === 'string' && art.relDir && typeof art.beadId === 'string' && art.beadId) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result.`
}
const ART = artifactsFrom(a.artifacts)
const prd = a.prd || {}
const sad = a.sad || {}
const repo = a.repoPath || '(repo path not provided)'
let trdPath = a.trdPath || null

const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim() : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

const isExtract = (x) =>
  !!x && typeof x === 'object' && ['constraints', 'solutionStrategy', 'crosscuttingConcepts'].every((k) => Array.isArray(x[k]))
const prdContent = typeof prd.content === 'string' && prd.content.trim().length > 0
const prdPath = typeof prd.path === 'string' && prd.path.startsWith('/') ? prd.path : ''
if (!prdContent && !prdPath) {
  const why = 'no PRD supplied — prd.content is empty and prd.path is not an absolute path. Pass the PRD content or its path.'
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}
const sadPathGiven = typeof sad.path === 'string' && sad.path.trim().startsWith('/')
if (!sadPathGiven && !isExtract(a.sadExtract)) {
  const why = 'no SAD supplied — sad.path is not an absolute path and no sadExtract was passed. Set ATW_SAD_PATH for the run, or pass sad.path.'
  return { ok: false, stage: 'input', deterministicFailure: true, error: why, reason: why }
}
const sadRef = sad.path || '(SAD path not provided)'
const sadLayout = sad.sectionLayout || 'unknown (detect single-file vs one-file-per-section)'

const died = (...phases) => {
  const deaths = dispatchDeaths(...phases)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

phase('Extract SAD')

const suppliedExtract = isExtract(a.sadExtract) ? a.sadExtract : null
if (suppliedExtract) log('SAD extract supplied by the caller — reused; the extractor is not dispatched')
else log(`Extracting arc42 source feeds from SAD at ${sadRef}`)

const SHARD_TARGET_BYTES = 175000
const SHARD_MAX_FILES = 16
const ASSUMED_BYTES = 20000

const readingRule = `READING RULE: read EVERY file assigned to you below, IN FULL — an index, README or table of contents is never read in place of the files it lists. Do NOT read any file outside the SAD. A section the SAD does not state comes back empty; it is never reconstructed from code.`

const feedSchema = () => ({
  type: 'array',
  items: {
    type: 'object',
    additionalProperties: false,
    required: ['id', 'statement', 'source'],
    properties: {
      id: { type: 'string' },
      statement: { type: 'string' },
      source: { type: 'string' },
    },
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

function extractShardAgent(label, feeds, entries) {
  const files = entries.map((e) => e.path)
  return settleAgent(
    `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for the TRD author. Do NOT author requirements, do NOT change any file, and invent NOTHING the SAD does not state. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

YOUR ASSIGNMENT — these arc42 sections and no others:
${feeds.map((f) => `- ${f.title}`).join('\n')}

FILES ASSIGNED TO YOU (${files.length}) — read every one of them in full:
${files.map((f) => `- ${f}`).join('\n')}

${readingRule}

Other sessions are extracting the rest of this SAD concurrently. Extract ONLY the sections assigned to you, from ONLY the files assigned to you, and return the feeds you were not assigned as empty arrays.

For every entry: set its ID, capture the verbatim-grounded statement, and note its source location (file:section/anchor). If an assigned section is absent from your files, return it as an empty array.

THE ID IS THE SAD'S OWN TAG, COPIED EXACTLY. Most entries open with a backticked tag such as \`C-apigw-construct\`, \`S-…\`, \`X-uniform-zero-egress\` or \`AD-…\`; that tag, character for character, is the entry's ID. Only an entry with no tag gets a made-up ID: \`<file name without .md>--<kebab-case of the nearest heading>\`, with \`-2\`, \`-3\` appended in document order when one heading holds several untagged entries.
Return every entry your files state; never consolidate, trim or omit an entry.`,
    {
      label,
      phase: 'Extract SAD',
      effort: 'low',
      agentType: 'agent-teams-workforce:sad-source-extractor',
      schema: extractSchema,
    }
  )
}

/** Packs inventory entries, in order, into shards of at most SHARD_MAX_FILES files and about SHARD_TARGET_BYTES bytes. */
function shardFiles(entries) {
  const shards = []
  let current = []
  let bytes = 0
  for (const e of entries) {
    const size = Number.isFinite(e.bytes) && e.bytes > 0 ? e.bytes : ASSUMED_BYTES
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

let sadExtract = suppliedExtract
let unreadSadFiles = suppliedExtract && Array.isArray(suppliedExtract.unreadSadFiles) ? suppliedExtract.unreadSadFiles : []

if (!sadExtract) {
  const inventory = await settleAgent(
    `You are READ-ONLY and you are taking an INVENTORY, not an extract. Do not extract any content, do not summarize anything, and change no file.

SAD location (read here, and only here — it is not inside the product repository ${repo}): ${sadRef}
SAD layout: ${sadLayout}

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
    return {
      ok: false,
      stage: 'extract',
      reason: 'the SAD inventory session returned nothing, so the SAD was not extracted and no TRD was authored.',
      ...died('Extract SAD'),
    }
  }

  const coreEntries = []
  for (const e of [...fileList(inventory.constraintsFiles), ...fileList(inventory.solutionStrategyFiles)]) {
    if (!coreEntries.some((c) => c.path === e.path)) coreEntries.push(e)
  }
  const crossShards = shardFiles(fileList(inventory.crosscuttingFiles))
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
  log(`SAD inventory: §2+§4 = ${coreEntries.length} file(s); §8 in ${crossShards.length} shard(s)`)

  const outs = await parallel(jobs.map((j) => () => extractShardAgent(j.label, j.feeds, j.entries)))
  const merged = { constraints: [], solutionStrategy: [], crosscuttingConcepts: [] }
  const seen = { constraints: new Set(), solutionStrategy: new Set(), crosscuttingConcepts: new Set() }
  const notes = []
  jobs.forEach((job, jobIndex) => {
    const out = outs[jobIndex]
    if (!out) {
      unreadSadFiles.push(...job.entries.map((e) => e.path))
      return
    }
    if (typeof out.notes === 'string' && out.notes.trim()) notes.push(`[${job.label}] ${out.notes.trim()}`)
    for (const feed of job.feeds) {
      const entries = Array.isArray(out[feed.key]) ? out[feed.key] : []
      entries.forEach((entry, entryIndex) => {
        if (!entry || typeof entry !== 'object') return
        let id = typeof entry.id === 'string' && entry.id.trim() ? entry.id.trim() : `${job.label}-${entryIndex}`
        let n = 2
        while (seen[feed.key].has(id)) id = `${id.replace(/#\d+$/, '')}#${n++}`
        seen[feed.key].add(id)
        merged[feed.key].push({ id, statement: String(entry.statement || ''), source: String(entry.source || '') })
      })
    }
  })
  if (unreadSadFiles.length) log(`SAD extraction: ${unreadSadFiles.length} file(s) not extracted — the author reads them directly`)
  sadExtract = {
    ...merged,
    sadLocation: (typeof inventory.sadLocation === 'string' && inventory.sadLocation) || sadRef,
    notes: notes.join('\n'),
    unreadSadFiles,
  }
  log(
    `SAD extracted: ${merged.constraints.length} constraint(s), ${merged.solutionStrategy.length} strategy statement(s), ` +
      `${merged.crosscuttingConcepts.length} crosscutting concept(s) from ${jobs.length} shard(s)`
  )
}

const renderFeed = (title, entries) =>
  `${title} (${entries.length}):\n` +
  (entries.length ? entries.map((e) => `- [${e.id}] ${e.statement}${e.source ? ` (${e.source})` : ''}`).join('\n') : '- (the SAD states none)')
const INDEX_SNIPPET_CHARS = 40
/** Renders §8 entries as an id index grouped by source file. */
function crosscuttingIndex(entries, sadHome) {
  const byFile = new Map()
  for (const e of Array.isArray(entries) ? entries : []) {
    if (!e || typeof e !== 'object') continue
    const m = String(e.source || '').trim().match(/^\/[^\s:#]+/)
    const f = m ? m[0] : ''
    if (!byFile.has(f)) byFile.set(f, [])
    byFile.get(f).push(e)
  }
  const snip = (t) => {
    const x = String(t || '').replace(/\s+/g, ' ').trim()
    return x.length > INDEX_SNIPPET_CHARS ? `${x.slice(0, INDEX_SNIPPET_CHARS)}…` : x
  }
  const groups = [...byFile.entries()].map(
    ([f, es]) =>
      `${f || `(no source file recorded — find these by id under the §8 section at ${sadHome})`}\n${es.map((e) => `  - [${e.id}] ${snip(e.statement)}`).join('\n')}`
  )
  return `§8 Crosscutting Concepts (${Array.isArray(entries) ? entries.length : 0}) — an INDEX, not the text: each line is an entry's id and the opening of its statement, grouped by the SAD file that states it.
READ IN FULL, in the SAD file it is listed under, every entry this TRD touches before you rely on it.
${groups.join('\n') || '- (the SAD states none)'}`
}

const extractText = [
  `SAD location: ${sadExtract.sadLocation || sadRef}`,
  ...(sadExtract.notes ? [`Extractor notes: ${sadExtract.notes}`] : []),
  renderFeed('§2 Constraints', sadExtract.constraints),
  renderFeed('§4 Solution Strategy', sadExtract.solutionStrategy),
  crosscuttingIndex(sadExtract.crosscuttingConcepts, sadExtract.sadLocation || sadRef),
  ...(unreadSadFiles.length ? [`SAD files not extracted above — read them in full yourself:\n${unreadSadFiles.map((f) => `- ${f}`).join('\n')}`] : []),
].join('\n\n')
const prdText = prdContent
  ? prd.content
  : `PRD ${prd.id || ''}${prd.title ? `: ${prd.title}` : ''}\n\nThe PRD is the document at ${prdPath}. Read that ONE file in full before you author anything; every requirement in it is in scope.`

const feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

phase('Author TRD')

if (!trdPath) {
  const home = await settleAgent(
    `Decide the ONE correct absolute file path for the Technical Requirements Document described below, using this project's documentation conventions and knowledge base. Do not author the TRD and do not create the file — return only where it belongs.

If a TRD for this subject already exists, return ITS path so the document is updated in place rather than duplicated.

Subject: ${prd.id || prd.title || 'TRD'}
PRD title: ${prd.title || '(untitled)'}
Repository the run is working in: ${repo}`,
    {
      label: 'trd:filing-home',
      phase: 'Author TRD',
      effort: 'low',
      agentType: 'filing-clerk',
      schema: {
        type: 'object', additionalProperties: false, required: ['ok'],
        properties: { ok: { type: 'boolean' }, path: { type: 'string' }, existing: { type: 'boolean' }, error: { type: 'string' } },
      },
    }
  )
  if (home && home.ok === true && typeof home.path === 'string' && home.path.startsWith('/')) {
    trdPath = home.path
    log(`TRD home ruled by the filing clerk: ${trdPath}`)
  } else {
    trdPath = '(no path supplied — ask the filing clerk before writing)'
  }
}

const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. \`trdPath\` in your result must be the path you actually wrote.
`
const MAX_REQUIREMENTS = 40
log(`Authoring TRD at ${authorPath}`)

const trd = await settleAgent(
  `${rulingsBlock}Author the Technical Requirements Document (TRD). Write the TRD; do not write production code. Work within the repository at: ${repo}

WHAT THIS DOCUMENT IS FOR. The TRD is the single point at which the obligations the architecture imposes enter the build chain. The Specs, Stories and Tasks are built from it; an obligation that does not reach the TRD is built by nobody. It is NOT the full HOW — the detailed HOW lives in the Specs and Tasks. Make sure the right obligations are PRESENT AND SOURCED.

THE TRD'S REQUIREMENTS COME FROM TWO SOURCES.

1. PRD REQUIREMENTS THAT NEED TECHNICAL ELABORATION. One PRD requirement may need several technical requirements, and several may be answered by one.

2. THE OBLIGATIONS THE ARCHITECTURE IMPOSES, WHICH NO PRD WOULD EVER STATE. These have NO PRD parent. System uptime, latency, maintainability, security, failover, disaster recovery, specific infrastructure and CDK instructions, and observability: this system uses EVENTS as its observability mechanism, so if this PRD results in a service being built, the TRD says WHICH EVENTS that service must emit. The same class covers throughput and latency budgets, data modelling, API contracts, encryption, retention and auth protocols, and monitoring and alerting. The SAD is the authority on what belongs.

The SAD extract below gives §2 and §4 in full and §8 as an INDEX. Open in full every §8 entry whose obligation could apply to anything this PRD builds — each service, store, API, event, data flow and boundary — and ask what it demands.

CITE THE SAD; DO NOT RESTATE IT. A requirement that names the obligation and cites the SAD entry that defines it is complete and is the preferred shape. Where the SAD already settles a point a PRD requirement raises, cite that decision. A correct TRD is often very short; where the architecture obliges nothing new, write nothing for it.

${writeBrief}
PRD (source of product requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

SAD extract (cite each entry by the id in brackets):
${extractText}
${feedback ? `\nFeedback on the previous version from the gate — address every point:\n${feedback}` : ''}

Each technical requirement has a stable ID, NAMES ITS SOURCE, and is verifiable. The source is EITHER a PRD requirement (in \`prdRefs\`) OR a SAD entry (in \`sadRefs\`); a SAD-sourced requirement carries an empty \`prdRefs\`. A requirement must not contradict the SAD.

Return at most ${MAX_REQUIREMENTS} technical requirements, each under 60 words, and keep the TRD document under about 25,000 characters: consolidate related obligations into one requirement rather than splitting them. Cite every SAD entry a requirement rests on in \`sadRefs\`.

CITE THE DECISIONS IN THE DOCUMENT AS WELL AS IN YOUR RESULT: YAML frontmatter at the top of the TRD with \`decisionIds:\` listing every SAD entry id any requirement depends on, and on each requirement the ids it depends on. Cite the SAD's own entry tags exactly as the extract writes them (\`C-…\`, \`S-…\`, \`X-…\`, \`AD-…\`); never invent or paraphrase one, and never cite a section number in place of one.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
  {
    label: 'author:trd',
    phase: 'Author TRD',
    effort: 'medium',
    agentType: 'agent-teams-workforce:trd-author',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['trdPath', 'requirements'],
      properties: {
        trdPath: { type: 'string' },
        decisionIds: { type: 'array', items: { type: 'string' } },
        requirements: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: false,
            required: ['id', 'requirement', 'prdRefs', 'sadRefs', 'verification'],
            properties: {
              id: { type: 'string' },
              requirement: { type: 'string' },
              prdRefs: { type: 'array', items: { type: 'string' } },
              sadRefs: { type: 'array', items: { type: 'string' } },
              verification: { type: 'string' },
            },
          },
        },
        summary: { type: 'string' },
        notes: { type: 'string' },
      },
    },
  }
)
if (!trd) return { ok: false, stage: 'author', reason: 'TRD authoring produced nothing', sadExtract, ...died('Author TRD') }
const resultPath = ART ? authorPath : trd.trdPath || trdPath
if (typeof resultPath === 'string' && resultPath.startsWith('/')) trd.trdPath = resultPath

return {
  ok: true,
  trdPath: resultPath,
  filingPath,
  sadExtract,
  trd,
  decisionIds: [...new Set([
    ...(Array.isArray(trd.decisionIds) ? trd.decisionIds : []),
    ...(Array.isArray(trd.requirements) ? trd.requirements : []).flatMap((r) => (Array.isArray(r.sadRefs) ? r.sadRefs : [])),
  ].map((x) => String(x == null ? '' : x).trim()).filter(Boolean))],
}
