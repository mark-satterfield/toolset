export const meta = {
  name: 'trd-authoring',
  description:
    'Leaf mini — authors a Technical Requirements Document (TRD) from a PRD plus an arc42 SAD extract. A read-only extractor pulls the SAD source feeds (constraints, solution strategy, crosscutting) into a typed packet; the trd-author writes the TRD; ONE independent checker session performs both checks (structure/quality + bidirectional PRD<->TRD traceability) — merged checks in one checker session, never a maker checking itself. Maker never judges its own work; on a bounded maker-checker deadlock the trd-decider rules, and a "revise" ruling is carried out: one targeted author pass with the required changes, then one independent re-check. Gate feedback from a previous run of this phase seeds the first author pass. Read/author only — no production code.',
  phases: [
    { title: 'Extract SAD', detail: 'read-only extraction of the arc42 source feeds into a typed packet' },
    { title: 'Author TRD', detail: 'author the TRD from the PRD + SAD extract (maker)' },
    { title: 'Verify & Traceability', detail: 'independent validation + PRD<->TRD traceability; decider on deadlock' },
  ],
}
// ── EVERY DISPATCH IS SETTLED ────────────────────────────────────────────────────
//
// `agent()` fails in two different ways and the scripts used to conflate them. It
// RETURNS NULL when a subagent is skipped or dies on a terminal API error after the
// runtime's own retries. It THROWS when a subagent finishes without calling
// StructuredOutput — and an uncaught throw leaves this script, leaves whatever
// composite called it, and kills the run: two recorded crashes cost 1.13M and 1.88M
// tokens and discarded every artifact the run had already paid for.
//
// So every dispatch in this file goes through settleAgent(). A throw never escapes it,
// and it records what the engine's error text loses — that text reads
// `agent({schema}): subagent completed without calling StructuredOutput`, which names
// neither the agent, nor the phase, nor the schema, and points at no transcript. The
// caller receives null, which every call site already handles, and `dispatchFailures`
// carries the identity of what died, for the `dispatchFailed` report this script owes
// its caller: a phase whose producing agents died is NOT adjudicated.
//
// This block is identical in every workflow script on purpose. Workflow scripts have no
// import mechanism, so a shared helper is shared by being the same text everywhere.
const dispatchFailures = []
// The dispatch deaths belonging to the named phases (every death when none is named).
// A phase whose PRODUCING agents died has no artifact to judge, so its caller must not
// adjudicate it and must not spend a retry on it — that is the `dispatchFailed` contract.
function dispatchDeaths(...phases) {
  const named = phases.filter(Boolean)
  if (!named.length) return dispatchFailures.slice()
  const set = new Set(named)
  return dispatchFailures.filter((f) => set.has(f.phase))
}
function settleSchemaName(o) {
  if (typeof o.schemaName === 'string' && o.schemaName) return o.schemaName
  const s = o.schema
  if (!s || typeof s !== 'object') return null
  if (typeof s.title === 'string' && s.title) return s.title
  const req = Array.isArray(s.required) && s.required.length ? s.required : Object.keys(s.properties || {})
  return req.length ? `{${req.join(', ')}}` : null
}
function settleTranscript(err, label) {
  const e = err && typeof err === 'object' ? err : {}
  for (const k of ['transcriptPath', 'transcript', 'agentPath', 'logPath']) {
    if (typeof e[k] === 'string' && e[k]) return e[k]
  }
  const id = typeof e.agentId === 'string' && e.agentId ? e.agentId : null
  if (id) return `agent-${id}.jsonl in this run's workflow transcript directory`
  return `the agent-<id>.jsonl in this run's workflow transcript directory whose agent-<id>.meta.json description is ${JSON.stringify(label)}`
}
async function settleAgent(prompt, opts) {
  const o = opts && typeof opts === 'object' ? opts : {}
  const call = { ...o }
  delete call.schemaName
  const who = {
    agentType: o.agentType || null,
    label: o.label || null,
    phase: o.phase || null,
    schema: settleSchemaName(o),
  }
  const name = who.label || who.agentType || 'agent'
  const whose = `${name}${who.agentType && who.agentType !== name ? ` (${who.agentType})` : ''}${who.phase ? ` in ${who.phase}` : ''}`
  let out = null
  try {
    out = await agent(prompt, call)
  } catch (err) {
    const message = String((err && err.message) || err)
    dispatchFailures.push({
      ...who,
      outcome: 'threw',
      message: message.slice(0, 300),
      transcript: settleTranscript(err, name),
      note: `${whose} finished without a structured result${who.schema ? ` for schema ${who.schema}` : ''}: ${message.slice(0, 160)}`,
    })
    log(`${name}: session ended without a structured result — ${message.slice(0, 160)}`)
    // A caller that owns its own failure reporting asks for the throw back, so the real
    // reason reaches its catch instead of being flattened to "returned no result".
    if (o.rethrow) throw err
    return null
  }
  if (out) return out
  dispatchFailures.push({
    ...who,
    outcome: 'skipped',
    message: null,
    transcript: settleTranscript(null, name),
    note: `${whose} returned nothing — skipped, or died on a terminal API error after the runtime's own retries`,
  })
  log(`${name}: returned nothing — skipped, or died on a terminal API error after the runtime's own retries`)
  return null
}

// args: {
//   prd: { id?, title?, path?, content?, acceptanceCriteria?: any[] },  // the source PRD
//   sad: { path?, sectionLayout?: 'single-file' | 'one-file-per-section' }, // arc42 SAD location
//   trdPath?: string,        // where the TRD should be written/lives
//   repoPath?: string,       // working repo for file reads/writes
//   maxLoops?: number,       // bounded maker-checker passes (default 2)
//   feedback?: string,       // gate feedback from a previous run of this phase; seeds the first author pass
//   artifacts?: { dir, relDir?, epicId, script, phase, inputs?, beadId? },
//                            // the Epic working directory. When present the author writes the TRD to
//                            // <dir>/trd.md and records it; trdPath is then the FILING home the
//                            // document is copied to on Done, returned as `filingPath`.
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}

// ── ARTIFACT PERSISTENCE ─────────────────────────────────────────────────────────
// When the caller names an Epic working directory, the session that AUTHORED an output
// writes it there once and runs the deterministic recorder, which hashes what is on disk.
// No session copies another session's output. Absent, nothing is written.
const SAFE_ART_PATH = /^\/[A-Za-z0-9._/-]+$/
function artifactsFrom(x) {
  if (!x || typeof x !== 'object') return null
  if (typeof x.dir !== 'string' || !SAFE_ART_PATH.test(x.dir) || x.dir.split('/').includes('..')) return null
  if (typeof x.script !== 'string' || !SAFE_ART_PATH.test(x.script) || x.script.split('/').includes('..')) return null
  if (typeof x.epicId !== 'string' || !/^[A-Za-z0-9._-]+$/.test(x.epicId)) return null
  if (typeof x.phase !== 'string' || !/^[A-Za-z0-9._:-]+$/.test(x.phase)) return null
  return x
}
const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
function persistBrief(art, name, what, opts) {
  if (!art) return ''
  const o = opts || {}
  const file = `${art.dir}/${name}`
  const inputs = (Array.isArray(art.inputs) ? art.inputs : []).filter((p) => typeof p === 'string' && p.trim())
  const record = `python3 ${art.script} record ${file} --epic ${art.epicId} --phase ${art.phase}${inputs.length ? ` --inputs ${inputs.map(shq).join(' ')}` : ''}`
  const steps = [
    `1. Write ${what} to ${file} with the Write tool, replacing the whole file if it exists (the Write tool refuses to overwrite a file this session has not read: Read it first, then Write). Write no other file for this.`,
    `2. Then run exactly this command${o.extraInputs ? `, adding ${o.extraInputs} as further --inputs values (add \`--inputs\` if the command has none)` : ''}:\n   ${record}\n   It hashes the file as it is on disk and prints the recorded metadata as JSON, including \`sha256\`.`,
  ]
  const relOk = typeof art.relDir === 'string' && /^[A-Za-z0-9._/-]+$/.test(art.relDir) && !art.relDir.startsWith('/')
  if (o.beadKey && relOk && typeof art.beadId === 'string' && /^[A-Za-z0-9._-]+$/.test(art.beadId)) {
    steps.push(`3. Then record it on the bead that owns it:\n   bd update ${art.beadId} --set-metadata artifact_${o.beadKey}_path=${art.relDir}/${name} --set-metadata artifact_${o.beadKey}_sha256=<the sha256 that step 2 printed>`)
  }
  return `\n\nSAVE WHAT YOU AUTHORED BEFORE YOU RETURN. This file is the durable copy a later run of this Epic resumes from instead of re-authoring it, and no other session will write it for you.\n${steps.join('\n')}\nIf a step fails, say so in your result and still return your result. Never improvise another way to write, move or record the file.`
}
const ART = artifactsFrom(a.artifacts)
const prd = a.prd || {}
const sad = a.sad || {}
const repo = a.repoPath || '(repo path not provided — ask before editing files)'
// A missing trdPath used to render as a placeholder string, which told the author to
// write the TRD to nowhere. Deciding where a document belongs is NOT this workflow's
// judgment to make — the project's filing clerk owns that, so when the caller names no
// path we ask it rather than inventing one under .claude/. Its ruling is used verbatim.
let trdPath = a.trdPath || null
// Gate retry budget. One rework round, then proceed with the finding recorded.
//
// This was 3, and nested minis carried their own bound of 2 on top, so a single
// phase could burn six expensive attempts before anyone saw a result — the
// dominant cost in every run that stalled. A checker's objection is information;
// it does not have to be a veto. One revision is where nearly all the value is:
// if a maker cannot address a finding on the second try, a third rarely helps and
// the finding is better carried forward than ground against.
//
// Callers who want the old behaviour pass args.maxLoops explicitly.
const MAX_LOOPS = a.maxLoops || 2

// ── Standing rulings from the project owner ─────────────────────────────────────
// Injected into JUDGMENT prompts only (never mechanical plumbing). The composite
// resolves .claude/standing-rulings.md in the repo the run operates on and threads
// the text here; absent -> empty string, zero behavior change. Capped so a bloated
// file cannot blow up every brief.
const RULINGS_CAP = 8192
const rulingsText = typeof a.standingRulings === 'string' ? a.standingRulings.trim().slice(0, RULINGS_CAP) : ''
const rulingsBlock = rulingsText
  ? `STANDING RULINGS FROM THE PROJECT OWNER — these outrank any document they contradict (PRD, SAD, TRD, spec, bead text). Where a ruling applies to your task, apply it, and CITE the ruling in your output (e.g. "dropped migration requirement per standing ruling dev-env-no-preservation") so the trace shows the ruling working.

${rulingsText}

END STANDING RULINGS

`
  : ''

if (!prd.id && !prd.path && !prd.content) {
  return { ok: false, stage: 'input', error: 'no PRD supplied (id/path/content all empty) — refusing to run without a work item' }
}

const prdRef = prd.path || prd.id || '(inline content)'
const sadRef = sad.path || '(SAD path not provided — ask before extracting)'
const sadLayout = sad.sectionLayout || 'unknown (detect single-file vs one-file-per-section)'

// ── THE `dispatchFailed` CONTRACT THIS MINI OWES ITS CALLER ──────────────────────
//
// An extractor or author that DIED did not produce a TRD the checkers found wanting — it
// never ran. Reported as an ordinary failure, the caller adjudicates it at its gate,
// every deterministic check fails against the artifact that does not exist, the gate
// loops, the re-dispatch meets the same wall, and the budget is spent. So a death in the
// producing phases is reported AS a death: no gate dispatch, no retry spent.
const died = (...phases) => {
  const deaths = dispatchDeaths(...phases)
  return deaths.length ? { dispatchFailed: true, dispatchFailures: deaths } : {}
}

// ── Phase 1: Extract SAD ──────────────────────────────────────────────────────
// Read-only extraction of the four arc42 source sections into a stably-identified
// packet. The extractor authors no TRD content — it only normalizes what the SAD
// states. Invents nothing the SAD does not contain.
phase('Extract SAD')

// ── A PACKET THE CALLER ALREADY HOLDS IS REUSED, NOT RE-BOUGHT ─────────────────
// The composite re-runs this mini when its gate sends the TRD back for rework. The SAD
// cannot change between those passes (a gate that needs the architecture changed
// ESCALATES and ends the run instead of looping), so the second pass used to pay the
// extractor again for the packet the first pass already produced — on 2026-09-16 the
// extractor was 2.26M of 38.0M weighted units across 17 runs. The caller passes the
// first pass's packet back as `args.sadExtract`; only a packet with all three feeds is
// believed, and anything else is extracted fresh.
const isExtract = (x) =>
  !!x && typeof x === 'object' && ['constraints', 'solutionStrategy', 'crosscuttingConcepts'].every((k) => Array.isArray(x[k]))
const suppliedExtract = isExtract(a.sadExtract) ? a.sadExtract : null
if (suppliedExtract) log('SAD extract supplied by the caller from an earlier pass of this run — reused; the extractor is not dispatched')
else log(`Extracting arc42 source feeds from SAD at ${sadRef}`)

// ── THE SAD IS READ WHOLE, IN SHARDS — IT IS NEVER TRUNCATED ────────────────────
//
// This dispatch used to carry "read the SAD and the files it points at — at most 12
// files". §8 (Crosscutting Concepts) is a DIRECTORY: 67 concept files, 787KB. Under a
// 12-file cap the extractor could not open them, so it read §8's README — an index —
// and reported the concepts it had never opened. The TRD, whose entire job is to be
// derived from the PRD and the SAD, was then authored from a summary of the
// architecture. That is wrong output, not cheaper output.
//
// The constraint that matters is "never read OUTSIDE the SAD"; the file count was a
// proxy for it that became a cap on the authoritative input. So the anti-sprawl rule
// stays verbatim in spirit and the volume is handled by SHARDING instead: §2+§4 in one
// session (~239KB), §8 split across concurrent sessions of roughly 175KB each, every
// assigned file read IN FULL. The SCRIPT merges the typed entries — no model merges
// another model's shards, and no session summarizes another's output.
//
// Workflow scripts have no filesystem, so the §8 file list cannot be globbed here. It
// comes from one cheap inventory dispatch, which is also what resolves single-file vs
// one-file-per-section layout — the same detection the extractor already does.
const SHARD_TARGET_BYTES = 175000
// A file ceiling as well as a byte one: sad-source-extractor runs with maxTurns 50, and
// every assigned file costs at least one Read turn (a large one costs two). 16 leaves the
// session room to finish even when the inventory reported no sizes at all.
const SHARD_MAX_FILES = 16
const MAX_SHARDS = 8
const ASSUMED_BYTES = 20000 // an inventory entry with no usable size is costed pessimistically

const readingRule = `READING RULE (binding): read EVERY file assigned to you below, IN FULL — none of them is optional, and an index, README or table of contents is never read in place of the files it lists. Do NOT read any file outside the SAD, and do not survey this repository or any other repository for architecture content that is not in the SAD. A section the SAD does not state comes back empty; it is never reconstructed from code.`

// The SAD's own sections are finite and this is a normalization, not a survey. A feed
// longer than its cap is the extractor reconstructing architecture from code, which the
// reading rule forbids. The cap is now PER SHARD, not per document — §8 is read in
// slices, so each slice gets room for what its own files actually state.
const feedSchema = (cap) => ({
  type: 'array',
  maxItems: cap,
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
const extractSchema = (crosscuttingCap) => ({
  type: 'object',
  additionalProperties: false,
  required: ['constraints', 'solutionStrategy', 'crosscuttingConcepts'],
  properties: {
    constraints: feedSchema(40),
    solutionStrategy: feedSchema(40),
    crosscuttingConcepts: feedSchema(crosscuttingCap),
    sadLocation: { type: 'string' },
    notes: { type: 'string' },
  },
})

// One shard dispatch. `feeds` names the sections this session owns; every other feed in
// its result is discarded by the merge, so a shard can never widen its own assignment.
function extractShardAgent(label, feeds, files, crosscuttingCap) {
  return settleAgent(
    `You are READ-ONLY. Extract the decision-bearing sections of the arc42 Software Architecture Document into one typed packet for the TRD author. Do NOT author requirements, do NOT change any file, and invent NOTHING the SAD does not state. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

YOUR ASSIGNMENT — these arc42 sections and no others:
${feeds.map((f) => `- ${f.title}`).join('\n')}

FILES ASSIGNED TO YOU (${files.length}) — read every one of them in full:
${files.map((f) => `- ${f}`).join('\n')}

${readingRule}

Other sessions are extracting the rest of this SAD concurrently. Extract ONLY the sections assigned to you, from ONLY the files assigned to you, and return the feeds you were not assigned as empty arrays. Do not read another shard's files and do not guess at what it will find.

For every entry: assign a stable, content-anchored ID, capture the verbatim-grounded statement, and note its source location (file:section/anchor). If an assigned section is genuinely absent from your files, return it as an empty array — do not fabricate.`,
    {
      label,
      phase: 'Extract SAD',
      effort: 'low',
      agentType: 'agent-teams-workforce:sad-source-extractor',
      schema: extractSchema(crosscuttingCap),
    }
  )
}

// Greedy, size-ordered packing over the inventory in the order the inventory gave it,
// so related concept files stay together and a re-run shards identically. Derived from
// the real file sizes rather than a hardcoded list — the concept set grows as Epics
// complete, and a list would rot the first time one is added.
function shardFiles(entries) {
  const shards = []
  let current = []
  let bytes = 0
  for (const e of entries) {
    const size = Number.isFinite(e.bytes) && e.bytes > 0 ? e.bytes : ASSUMED_BYTES
    const full = current.length >= SHARD_MAX_FILES || (current.length && bytes + size > SHARD_TARGET_BYTES)
    if (full && shards.length < MAX_SHARDS - 1) {
      shards.push(current)
      current = []
      bytes = 0
    }
    current.push(e.path)
    bytes += size
  }
  if (current.length) shards.push(current)
  return shards
}

const fileList = (x) =>
  (Array.isArray(x) ? x : [])
    .map((e) => (typeof e === 'string' ? { path: e, bytes: 0 } : e))
    .filter((e) => e && typeof e.path === 'string' && e.path.trim())
    .map((e) => ({ path: e.path.trim(), bytes: Number(e.bytes) || 0 }))

let sadExtract = suppliedExtract
let sadUnread = []

if (!sadExtract) {
  // ── Step 1: inventory. Cheap, read-only, and the only thing that knows the layout.
  const inventory = await settleAgent(
    `You are READ-ONLY and you are taking an INVENTORY, not an extract. Do not extract any content, do not summarize anything, and change no file. Work within the repository at: ${repo}

SAD location: ${sadRef}
SAD layout: ${sadLayout}

Resolve the arc42 layout (single-file vs one-file-per-section) and list EVERY file that holds the content of these sections, with its size in bytes:
- Section 2 — Constraints
- Section 4 — Solution Strategy
- Section 8 — Crosscutting Concepts

A section held in a DIRECTORY is listed as all of its content files, recursively — every concept file, not the directory and not its README index. Where a section's content lives inside one larger file, list that file under every section it holds. List only files inside the SAD; never list a file elsewhere in this repository or in another repository. If a section has no files at all, return it as an empty array.`,
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
            maxItems: 400,
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
      reason: 'SAD inventory produced nothing — the files holding sections 2, 4 and 8 could not be listed, so no extraction was attempted. Nothing was read and nothing was authored.',
      ...died('Extract SAD'),
    }
  }

  const coreFiles = [...new Set([...fileList(inventory.constraintsFiles), ...fileList(inventory.solutionStrategyFiles)].map((e) => e.path))]
  const crossEntries = fileList(inventory.crosscuttingFiles)
  const crossShards = shardFiles(crossEntries)
  log(`SAD inventory: §2+§4 = ${coreFiles.length} file(s); §8 = ${crossEntries.length} file(s) in ${crossShards.length} shard(s)`)

  // ── Step 2: every shard runs CONCURRENTLY and reads its slice in full.
  const jobs = []
  if (coreFiles.length) {
    jobs.push({
      label: 'extract:sad-core',
      feeds: [{ key: 'constraints', title: 'Section 2 — Constraints' }, { key: 'solutionStrategy', title: 'Section 4 — Solution Strategy' }],
      files: coreFiles,
    })
  }
  crossShards.forEach((files, i) => {
    jobs.push({
      label: `extract:sad-crosscutting-${i + 1}of${crossShards.length}`,
      feeds: [{ key: 'crosscuttingConcepts', title: 'Section 8 — Crosscutting Concepts' }],
      files,
    })
  })
  if (!jobs.length) {
    return {
      ok: false,
      stage: 'extract',
      reason: `SAD inventory listed no files for sections 2, 4 or 8 at ${sadRef} — there is nothing to extract, so no TRD was authored.`,
    }
  }

  const results = await parallel(jobs.map((j) => () => extractShardAgent(j.label, j.feeds, j.files, j.feeds.some((f) => f.key === 'crosscuttingConcepts') ? 60 : 40)))

  // ── Step 3: the SCRIPT merges. Each shard contributes only the feeds it was assigned,
  // in shard order, de-duplicated by stable id. No model sees another model's shard.
  const merged = { constraints: [], solutionStrategy: [], crosscuttingConcepts: [] }
  const seen = { constraints: new Set(), solutionStrategy: new Set(), crosscuttingConcepts: new Set() }
  const notes = []
  const deadShards = []
  jobs.forEach((job, i) => {
    const out = results[i]
    if (!out) {
      deadShards.push(job)
      return
    }
    if (typeof out.notes === 'string' && out.notes.trim()) notes.push(`[${job.label}] ${out.notes.trim()}`)
    for (const feed of job.feeds) {
      for (const entry of Array.isArray(out[feed.key]) ? out[feed.key] : []) {
        if (!entry || typeof entry !== 'object' || typeof entry.id !== 'string' || !entry.id.trim()) continue
        let id = entry.id.trim()
        if (seen[feed.key].has(id)) {
          // Two shards minted the same content-anchored id for different text. Keeping
          // both, disambiguated, loses nothing; dropping one would silently shrink §8.
          let n = 2
          while (seen[feed.key].has(`${id}#${n}`)) n++
          id = `${id}#${n}`
        }
        seen[feed.key].add(id)
        merged[feed.key].push({ id, statement: String(entry.statement || ''), source: String(entry.source || '') })
      }
    }
  })

  // ── A SHARD THAT DIED NEVER SHRINKS THE PACKET QUIETLY ─────────────────────────
  // A partial §8 that looks whole is the exact defect this sharding was built to fix:
  // the TRD author cannot tell a concept the SAD does not state from one nobody read.
  // So a dead shard ENDS the run, naming every file that went unread.
  if (deadShards.length) {
    sadUnread = deadShards.flatMap((j) => j.files)
    log(`SAD extraction INCOMPLETE — ${deadShards.length} of ${jobs.length} shard(s) returned nothing; ${sadUnread.length} file(s) went unread`)
    return {
      ok: false,
      stage: 'extract',
      reason: `SAD extraction is INCOMPLETE: ${deadShards.length} of ${jobs.length} shard(s) returned nothing, so ${sadUnread.length} SAD file(s) were never read. No TRD was authored — a TRD derived from part of the architecture is wrong output, not cheaper output. Unread: ${sadUnread.join(', ')}`,
      unreadSadFiles: sadUnread,
      deadShards: deadShards.map((j) => ({ label: j.label, files: j.files })),
      partialSadExtract: merged,
      ...died('Extract SAD'),
    }
  }

  sadExtract = {
    ...merged,
    sadLocation: (typeof inventory.sadLocation === 'string' && inventory.sadLocation) || sadRef,
    notes: notes.join('\n'),
  }
  log(`SAD extracted whole: ${merged.constraints.length} constraint(s), ${merged.solutionStrategy.length} strategy statement(s), ${merged.crosscuttingConcepts.length} crosscutting concept(s) from ${jobs.length} shard(s)`)
}
if (!sadExtract) return { ok: false, stage: 'extract', reason: 'SAD extraction produced nothing', ...died('Extract SAD') }

const extractText = JSON.stringify(sadExtract, null, 2)
const prdText = prd.content
  ? prd.content
  : `PRD ${prd.id || ''}: ${prd.title || ''} (path: ${prd.path || 'n/a'})`

// ── Phases 2 + 3: bounded maker-checker loop ──────────────────────────────────
// The maker (trd-author) writes the TRD; two INDEPENDENT checkers judge it. Neither
// checker ever authored the TRD. On rejection the maker re-runs with the combined
// checker feedback. The script owns this loop in plain JS — no workflow() calls.
let trd = null
let trdValidation = null
let traceabilityMatrix = null
let decision = null
let feedback = typeof a.feedback === 'string' && a.feedback.trim() ? `[Gate feedback from the previous run of this phase] ${a.feedback.trim()}` : ''

// ── WHERE THE TRD LIVES IS THE FILING CLERK'S RULING ─────────────────────────
// A TRD is a durable document, so it needs a real home before it is authored, not a
// path this workflow made up. The clerk already owns that decision for this knowledge
// base: it searches the vault, applies the single-source-of-truth rule, and returns the
// one correct location. Asked once per run, before the authoring loop.
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
    log(`TRD home ruled by the filing clerk: ${trdPath}${home.existing ? ' (updating an existing TRD in place)' : ''}`)
  } else {
    // The clerk is the authority on location; if it cannot rule, this workflow does not
    // get to substitute a guess. Authoring proceeds and the author is told to ask.
    trdPath = '(no path supplied — ask the filing clerk before writing)'
    log('Filing clerk returned no usable path for the TRD — the author is instructed to ask before writing')
  }
}

// With an Epic working directory the TRD is authored THERE, and the filing home ruled above
// is where it is filed once the run reaches Done — so a TRD from an unfinished run never
// lands in the vault as if it were accepted.
const authorPath = ART ? `${ART.dir}/trd.md` : trdPath
const filingPath = typeof trdPath === 'string' && trdPath.startsWith('/') ? trdPath : null
const writeBrief = ART
  ? `WRITE THE TRD AS MARKDOWN BEFORE YOU RETURN, as the steps at the end of this brief say. \`trdPath\` in your result must be ${authorPath}.${filingPath ? ` Do NOT write it to ${filingPath}: that is where it is filed once the run completes, and that copy is not yours to make.` : ''}\n`
  : `WRITE THE TRD TO THIS FILE BEFORE YOU RETURN: ${trdPath}
Create any missing parent directories. A TRD is a durable document, not a value passed
between phases: returning its text without saving the file means a run that ends early
leaves no TRD anywhere, and the next run re-derives it from nothing. Saving the file is
part of authoring it, not an optional extra, and \`trdPath\` in your result must be the
path you actually wrote.
`

// ── Phase 2: Author TRD (maker) ──────────────────────────────────────────────
// The author reads the shared `feedback`, so every pass carries whatever the checker,
// the gate or the decider last asked for.
function authorTrd(pass) {
  phase('Author TRD')
  log(`Authoring TRD (${pass}) at ${authorPath}`)

  return settleAgent(
    `${rulingsBlock}Author the Technical Requirements Document (TRD). The TRD translates the PRD's product requirements into testable technical requirements, grounded in and consistent with the SAD extract below. Write the TRD; do not write production code. Work within the repository at: ${repo}

${writeBrief}
PRD (source of product requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

SAD extract (architecture constraints/strategy/crosscutting the TRD must honor; cite by stable ID):
${extractText}
${feedback ? `\nFeedback on the previous version (checker, gate or decider) — address every point:\n${feedback}` : ''}

Each technical requirement must have a stable ID, trace upward to a PRD requirement, cite any SAD source IDs it depends on, and be verifiable. Deliver the TRD file path(s) you wrote, the structured requirements, and the upstream PRD/SAD references each requirement carries.

VOLUME IS THE COST OF THIS PHASE. Return AT MOST 40 technical requirements, each stated in under 60 words, and keep the TRD document itself under about 25,000 characters. That is not a quota to fill — it is a ceiling, and a TRD that needs more than 40 requirements is one Epic's worth of HOW spread too thin: consolidate related obligations into one requirement rather than splitting them, and drop restatement, background and rationale the PRD or the SAD already carries. Every word here is read again by the verifier and by every spec author downstream, so length is paid for many times over.

CITE THE DECISIONS, IN THE DOCUMENT AS WELL AS IN YOUR RESULT.
A \`sadRefs\` entry that reaches only your structured result is read by this run and by nothing after it. The TRD file itself carries the citation twice:
- in YAML frontmatter at the top of the document, \`decisionIds:\` listing every SAD entry id any requirement in this TRD depends on, as a flat list;
- and on each requirement, naming the ids that requirement depends on.
Cite the SAD's own entry tags exactly as the extract writes them (\`C-…\`, \`S-…\`, \`X-…\`, \`AD-…\`). Never invent an id, never paraphrase one, and never cite a section number in place of one — a section number moves, a tag does not.${persistBrief(ART, 'trd.md', 'the complete TRD as a markdown document', { beadKey: 'trd' })}`,
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
          // Every SAD entry id this TRD depends on, flat — the same list the document's
          // frontmatter carries. It is what the impact pass matches a changed decision
          // against, so it lives on the document and not only inside a requirement.
          decisionIds: { type: 'array', maxItems: 60, items: { type: 'string' } },
          requirements: {
            type: 'array',
            // The ceiling stated in the brief above. Output volume is what this phase
            // costs in wall-clock: the TRD is re-read by the verifier, by the decider and
            // by every spec author downstream, so an unbounded list is paid for repeatedly.
            maxItems: 40,
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['id', 'requirement', 'prdRefs', 'sadRefs', 'verification'],
              properties: {
                id: { type: 'string' },
                requirement: { type: 'string' },
                prdRefs: { type: 'array', maxItems: 10, items: { type: 'string' } },
                sadRefs: { type: 'array', maxItems: 10, items: { type: 'string' } },
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
}

// ── Phase 3: Verify & Traceability — ONE independent checker session, both checks ─
// This used to be two parallel checker sessions, each paying a full session-start to
// read the same TRD. Both are independent CHECKS on the maker's artifact — neither
// ever judged the other — so one session carrying both preserves segregation of
// duties (the checker authored nothing) at half the cost.
function verifyTrd() {
  const trdText = JSON.stringify(trd, null, 2)
  phase('Verify & Traceability')

  return settleAgent(
    `You are an INDEPENDENT verifier. You did NOT author this TRD; you only judge it. Do not modify it. Perform BOTH checks below in one pass and return each under its own key. Keep every finding and feedback item under 40 words.

CHECK 1 — structure and quality (return under \`validation\`): required sections present, every requirement has a stable ID and a concrete verification method, requirements are unambiguous and testable, and the TRD is internally consistent with the SAD extract it cites. verdict "pass" only if every check holds; otherwise "reject" with feedback specific enough that the author can fix it without interpretation, and each finding with its severity.

CHECK 2 — bidirectional PRD<->TRD traceability (return under \`traceability\`): every PRD requirement maps forward to at least one TRD requirement (no coverage gaps), and every TRD requirement maps back to a PRD requirement (no orphans). Build the traceability matrix and report gaps in both directions. verdict "pass" only if traceability is complete in BOTH directions with no unexplained gaps or orphans.

PRD (source requirements):
${prdText}
${Array.isArray(prd.acceptanceCriteria) && prd.acceptanceCriteria.length ? `\nPRD acceptance criteria:\n${prd.acceptanceCriteria.map((x, i) => `${i + 1}. ${typeof x === 'string' ? x : JSON.stringify(x)}`).join('\n')}` : ''}

TRD under review:
${trdText}

SAD extract the TRD must stay consistent with:
${extractText}`,
    {
      label: 'verify:trd-and-traceability',
      phase: 'Verify & Traceability',
      // A checker, and the trd-validator's own file already says `effort: low` — this
      // override was RAISING it. Judging a document against stated criteria is the
      // cheapest kind of judgment there is; the expensive one is the decider below.
      effort: 'low',
      agentType: 'agent-teams-workforce:trd-validator',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['validation', 'traceability'],
        properties: {
          validation: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'findings', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              findings: {
                type: 'array',
                // A checker's job is to name what blocks, not to enumerate everything it
                // noticed. Past 25 findings the author cannot act on them in one pass
                // anyway, and the loop below only has one pass.
                maxItems: 25,
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['issue', 'severity'],
                  properties: {
                    issue: { type: 'string' },
                    severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
                    location: { type: 'string' },
                  },
                },
              },
              feedback: { type: 'string' },
            },
          },
          traceability: {
            type: 'object',
            additionalProperties: false,
            required: ['verdict', 'links', 'prdGaps', 'trdOrphans', 'feedback'],
            properties: {
              verdict: { type: 'string', enum: ['pass', 'reject'] },
              links: {
                type: 'array',
                // The traceability matrix is the one place where completeness IS the
                // check, so this cap is a blow-up guard rather than a budget: at most 40
                // TRD requirements against a PRD's requirements, one row per real link.
                // A matrix longer than this is a cross-product, not a mapping.
                maxItems: 200,
                items: {
                  type: 'object',
                  additionalProperties: false,
                  required: ['prdRef', 'trdRef'],
                  properties: {
                    prdRef: { type: 'string' },
                    trdRef: { type: 'string' },
                  },
                },
              },
              prdGaps: { type: 'array', maxItems: 40, items: { type: 'string' } },
              trdOrphans: { type: 'array', maxItems: 40, items: { type: 'string' } },
              feedback: { type: 'string' },
            },
          },
        },
      },
    }
  )
}

for (let attempt = 1; attempt <= MAX_LOOPS; attempt++) {
  trd = await authorTrd(`attempt ${attempt}/${MAX_LOOPS}`)
  if (!trd) return { ok: false, stage: 'author', reason: 'TRD authoring produced nothing', sadExtract, ...died('Author TRD') }

  const verification = await verifyTrd()
  const validation = verification && verification.validation
  const traceability = verification && verification.traceability

  trdValidation = validation
  traceabilityMatrix = traceability

  const validationPass = validation && validation.verdict === 'pass'
  const traceabilityPass = traceability && traceability.verdict === 'pass'

  if (validationPass && traceabilityPass) {
    log(`TRD accepted on attempt ${attempt}: validation PASS, traceability PASS`)
    decision = { verdict: 'pass', ruledByDecider: false, rationale: 'Both independent checkers passed.' }
    break
  }

  // Combine the rejecting checkers' feedback for the next maker pass.
  const parts = []
  if (!validationPass) parts.push(`[Structure/quality] ${(validation && validation.feedback) || 'rejected (no feedback)'}`)
  if (!traceabilityPass) parts.push(`[Traceability] ${(traceability && traceability.feedback) || 'rejected (no feedback)'}`)
  feedback = parts.join('\n\n')
  log(`TRD rejected on attempt ${attempt}/${MAX_LOOPS}: ${parts.join(' | ')}`)

  // On deadlock (final pass exhausted while still rejected), the trd-decider rules.
  // The decider only rules — it never authored or analyzed the TRD itself.
  if (attempt === MAX_LOOPS) {
    log('Maker-checker loop exhausted — escalating to trd-decider for a binding ruling')
    const ruling = await settleAgent(
      `The TRD author and the independent checkers reached a deadlock across the bounded retry loop. You ONLY rule — you did not author the TRD and you do not re-analyze it from scratch. Decide whether the TRD ships as-is ("accept"), returns to the author for a final targeted change ("revise"), or is rejected ("reject"), and state the binding rationale. A "revise" is carried out: the author makes the changes you list in \`requiredChanges\` and the TRD is re-checked once, so list every change, each precise enough to apply without re-deciding anything.

TRD:
${JSON.stringify(trd, null, 2)}

Structure/quality verdict: ${(trdValidation && trdValidation.verdict) || 'n/a'}
Structure/quality feedback: ${(trdValidation && trdValidation.feedback) || 'n/a'}

Traceability verdict: ${(traceabilityMatrix && traceabilityMatrix.verdict) || 'n/a'}
Traceability feedback: ${(traceabilityMatrix && traceabilityMatrix.feedback) || 'n/a'}`,
      {
        label: 'decide:trd',
        phase: 'Verify & Traceability',
        effort: 'high',
        agentType: 'agent-teams-workforce:trd-decider',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['verdict', 'rationale'],
          properties: {
            verdict: { type: 'string', enum: ['accept', 'reject', 'revise'] },
            rationale: { type: 'string' },
            // A revise buys exactly ONE targeted author pass. A change list longer than
            // this is not targeted — it is a rewrite the decider had no mandate to order.
            requiredChanges: { type: 'array', maxItems: 15, items: { type: 'string' } },
          },
        },
      }
    )
    decision = ruling
      ? { verdict: ruling.verdict, ruledByDecider: true, rationale: ruling.rationale, requiredChanges: ruling.requiredChanges || [] }
      : { verdict: 'reject', ruledByDecider: true, rationale: 'trd-decider returned no ruling.' }
  }
}

// ── A "revise" ruling is carried out, not reported ────────────────────────────
// The decider is offered "return to the author for a final targeted change". Ending the
// run on that ruling returned ok:false with the change never made, and the gate's re-run
// of this mini did not hand the required changes to the author either, so the same
// finding came back and the gate budget ran out on a TRD the decider had ruled fixable.
// A revise gets exactly one targeted author pass and one independent re-check; a TRD the
// checker still rejects after it ends the run with the ruling and the new findings.
if (decision && decision.verdict === 'revise' && trd) {
  const changes = decision.requiredChanges && decision.requiredChanges.length
    ? decision.requiredChanges.map((c, i) => `${i + 1}. ${c}`).join('\n')
    : '(none listed — apply the rationale)'
  feedback = `BINDING RULING FROM THE TRD DECIDER — make these targeted changes and change nothing else:\n${changes}\n\nRationale: ${decision.rationale || 'n/a'}\n\nLatest checker feedback:\n${feedback}`
  const revised = await authorTrd('final targeted revision per the decider ruling')
  if (revised) {
    trd = revised
    const verification = await verifyTrd()
    trdValidation = verification && verification.validation
    traceabilityMatrix = verification && verification.traceability
    const passed = !!(trdValidation && trdValidation.verdict === 'pass' && traceabilityMatrix && traceabilityMatrix.verdict === 'pass')
    log(`TRD ${passed ? 'accepted' : 'still rejected'} after the decider's targeted revision`)
    decision = passed
      ? { ...decision, verdict: 'accept', revisedPerRuling: true, rationale: `${decision.rationale} Required changes applied; both independent checks passed on re-check.` }
      : { ...decision, revisedPerRuling: true, recheckFeedback: [trdValidation && trdValidation.feedback, traceabilityMatrix && traceabilityMatrix.feedback].filter(Boolean).join('\n\n') }
  } else {
    decision = { ...decision, revisedPerRuling: false }
  }
}

const accepted = decision && (decision.verdict === 'pass' || decision.verdict === 'accept')

return {
  ok: !!accepted,
  trdPath: ART ? authorPath : (trd && trd.trdPath) || trdPath,
  // The filing home ruled for this TRD, when one was ruled. Null means nobody ruled it.
  filingPath,
  sadExtract,
  trd,
  // The SAD entry ids this TRD depends on. They go up to the caller, where they are matched
  // against a changed decision id, never against a file date.
  decisionIds: [...new Set([
    ...((trd && Array.isArray(trd.decisionIds) ? trd.decisionIds : [])),
    ...((trd && Array.isArray(trd.requirements) ? trd.requirements : []).flatMap((r) => (Array.isArray(r.sadRefs) ? r.sadRefs : []))),
  ].map((x) => String(x == null ? '' : x).trim()).filter(Boolean))],
  trdValidation,
  traceabilityMatrix,
  decision,
}
