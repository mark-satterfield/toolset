// The shared blocks every workflow script embeds verbatim, and the one tool that writes them.
//
// A workflow script is not a module: the runner gives it seven globals and no loader, and
// scripts/workflow-runner-constraints.mjs refuses import and require in it. Code every workflow
// needs therefore has ONE canonical definition (SHARED_BLOCKS names it: a block file in
// scripts/shared-blocks/, or the schema a block is generated from), and each workflow carries the
// resulting text between two marker lines. Nobody edits a copy: edit the canonical file and run
//
//     node scripts/shared-blocks.mjs --write [--only <workflow>.js ...]
//
// which rewrites every copy (or only the named workflows'). A workflow gets a block by carrying
// the two marker lines, with anything between them, and being listed in SHARED_BLOCKS; --write
// then fills it. check-workflow-syntax.mjs (the pre-commit gate) fails when any copy
// differs from its canonical text, or a workflow listed for a block lacks it.
//
// CONTRACT SCHEMAS. A schema a workflow hands to agent(...) as `schema:` is a contract, and a
// contract lives in one file (skills/artifact-handoff/schemas/ for agent hand-offs,
// skills/pipeline-contracts/schemas/ for pipeline and journal contracts). A workflow cannot read
// that file, so it carries a GENERATED constant, declared by two marker lines in the workflow
// itself; nothing here lists them:
//
//     // ===== CONTRACT SCHEMA <CONSTANT> = <path from the plugin root>[#<JSON pointer>] — BEGIN =====
//     // ===== CONTRACT SCHEMA <CONSTANT> — END =====
//
// for example
//
//     // ===== CONTRACT SCHEMA EDGES_SCHEMA = skills/artifact-handoff/schemas/epic-edges.schema.json — BEGIN =====
//     // ===== CONTRACT SCHEMA EDGES_SCHEMA — END =====
//
// <CONSTANT> is a JavaScript identifier, unique in the workflow; the path names a .json file in
// the plugin; the optional #<JSON pointer> (RFC 6901, e.g. #/$defs/Proposal) names a schema inside
// it. Anything may follow BEGIN on the begin line (--write rewrites it to its canonical form) and
// anything may sit between the two lines. `--write --only <workflow>.js` fills the block with
//
//     const <CONSTANT> = <the schema, as one line of JSON>
//
// with every $ref (local, or to a file relative to the referring file) inlined and $defs dropped,
// exactly as scripts/portfolio/jsonartifact.py load_contract reads the same file. The check mode
// and check-workflow-syntax.mjs fail when a constant differs from its file, its file or pointer
// does not resolve, its end marker is missing, or one constant is declared twice. A prompt names
// the contract file's path; it never pastes the schema.
//
// An artifact a producer session authors under the checkpoint contract is bound to its contract
// FILE the same way: relayKit.artifactBrief(candidate, contract, revision, helper) and
// relayKit.acceptArtifact({ ..., contract }) take `contract` as that same path from the plugin
// root (with an optional #<JSON pointer>) and hand it to artifactcontract.py and jsonartifact.py
// as `--schema <absolute path>`.
//
// The import ban applies to WORKFLOW SCRIPTS; this file is an ordinary ES module.

import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { artifactCapabilityProblems } from './artifact-capabilities.mjs'
import { createRequire } from 'node:module'

const HERE = dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = join(HERE, '..', 'workflows')

const WRITE_COMMAND = 'node scripts/shared-blocks.mjs --write'

const { userLevelAgentNames } = createRequire(import.meta.url)('../hooks/lib/user-level-agents.cjs')

/**
 * The build and deploy lane's workflows, being rewritten on their own schedule. Their committed
 * copy of the relay block keeps working unchanged because jsonartifact.py and artifactcontract.py
 * still accept --schema-json, so a differing relay block in these files is not drift: the check
 * does not flag it and --write does not touch it. Every other block in them is still checked.
 */
const RELAY_FROZEN = Object.freeze(['built-version.js', 'deploy.js', 'settle.js', 'story-deploy-fix.js', 'suite-run.js', 'task-to-deploy.js', 'tdd-refactor.js', 'workspace.js'])

/**
 * Every shared block: its name, the workflows that must carry it, and where its text is defined.
 * `canonical` is the one file to edit (a schema when the block is generated from one), `filledFrom`
 * the schemas whose values shared-blocks.mjs inlines into a hand-written block, and `regenerate` the
 * command that rewrites a generated block file from its schema before --write copies it.
 */
export const SHARED_BLOCKS = Object.freeze([
  {
    name: 'architecture-artifacts',
    canonical: 'scripts/shared-blocks/architecture-artifacts.js',
    filledFrom: 'skills/artifact-handoff/schemas/{architecture-writer,architecture-review,conformance,built-conformance,architecture-common}.schema.json',
    requiredIn: ['built-version.js'],
  },
  {
    name: 'composite-phases',
    canonical: 'skills/pipeline-contracts/schemas/composites.json',
    regenerate: 'python3 skills/pipeline-contracts/scripts/generate_composites.py',
    requiredIn: ['built-version.js', 'deploy-mechanism.js', 'story-deploy-fix.js', 'task-to-deploy.js'],
  },
  {
    name: 'recon-contract',
    canonical: 'skills/artifact-handoff/schemas/recon.schema.json',
    regenerate: 'python3 skills/artifact-handoff/scripts/gen_recon_contract.py --write',
    requiredIn: ['task-to-deploy.js', 'tdd-green.js'],
  },
  {
    name: 'story-deploy-args',
    canonical: 'scripts/shared-blocks/story-deploy-args.js',
    filledFrom: 'skills/artifact-handoff/schemas/story-deploy-args.schema.json',
    requiredIn: ['built-version.js', 'deploy-mechanism.js', 'story-deploy-fix.js'],
  },
  {
    name: 'step-journal',
    canonical: 'scripts/shared-blocks/step-journal.js',
    filledFrom: 'skills/pipeline-contracts/schemas/{step-journal.schema,pipeline-steps}.json',
    requiredIn: ['built-version.js', 'story-deploy-fix.js', 'task-to-deploy.js'],
  },
  {
    name: 'fable',
    canonical: 'scripts/shared-blocks/fable.js',
    filledFrom: 'skills/pipeline-contracts/schemas/driver-surface.schema.json and agents/*.md',
    requiredIn: [
      'adversarial.js',
      'built-version.js',
      'dependency-assessment.js',
      'deploy-mechanism.js',
      'deploy.js',
      'documentation.js',
      'gate-enforce.js',
      'infra-intent.js',
      'prd-creation.js',
      'prd-validation.js',
      'settle.js',
      'story-deploy-fix.js',
      'suite-run.js',
      'task-dependency-assessment.js',
      'task-to-deploy.js',
      'tdd-green.js',
      'tdd-red.js',
      'tdd-refactor.js',
      'workspace.js',
      'wsjf-scoring.js',
    ],
  },
  {
    name: 'relay',
    canonical: 'scripts/shared-blocks/relay.js',
    filledFrom: 'skills/artifact-handoff/schemas/{checkpoint,relay-command-result,relay-registered-result,artifact-reference}.schema.json',
    requiredIn: [
      'built-version.js',
      'dependency-assessment.js',
      'deploy.js',
      'prd-validation.js',
      'settle.js',
      'story-deploy-fix.js',
      'suite-run.js',
      'task-dependency-assessment.js',
      'task-to-deploy.js',
      'tdd-refactor.js',
      'workspace.js',
      'wsjf-scoring.js',
    ],
  },
])

/** The registered block named `name`; an unregistered name is a programming error. */
const blockOf = (name) => {
  const block = SHARED_BLOCKS.find((entry) => entry.name === name)
  if (!block) throw new Error(`shared-blocks.mjs: no shared block is named ${JSON.stringify(name)}`)
  return block
}

/** The start of every begin marker of `name`, whatever its canonical note says. */
const beginPrefix = (name) => `// ===== SHARED BLOCK ${name} — BEGIN`

export const beginMarker = (name) => {
  const block = blockOf(name)
  const filled = block.filledFrom ? `; filled from ${block.filledFrom}` : ''
  const commands = [block.regenerate, WRITE_COMMAND].filter(Boolean).join(' and ')
  return `${beginPrefix(name)} (canonical: ${block.canonical}${filled}; edit there, then: ${commands}) =====`
}
export const endMarker = (name) => `// ===== SHARED BLOCK ${name} — END =====`

/** The plugin root: every canonical path above is relative to it. */
const PLUGIN_ROOT = join(HERE, '..')

/** One plugin file's text. */
const pluginText = (relative) => readFileSync(join(PLUGIN_ROOT, relative), 'utf8')

/** One plugin JSON file, compacted to the single line a block embeds. */
const pluginJson = (relative) => JSON.stringify(JSON.parse(pluginText(relative)))

/** Replaces each placeholder of `text` with its value; a missing placeholder means the block file drifted. */
const fillPlaceholders = (name, text, fills) => fills.reduce((block, [placeholder, value]) => {
  if (!block.includes(placeholder)) throw new Error(`scripts/shared-blocks/${name}.js lacks ${placeholder}`)
  return block.replace(placeholder, () => value)
}, text)

/** Keywords whose values are instance data, never subschemas: a $ref or $defs inside them is copied as is. */
const DATA_KEYWORDS = new Set(['const', 'default', 'enum', 'examples'])

/**
 * The schema a plugin file holds at a JSON pointer (RFC 6901), with every $ref (local, or to a file
 * relative to the referring file's folder) replaced by the schema it names and $defs dropped, so a
 * workflow validator needs no second file. `relative` is the file's path from the plugin root.
 * scripts/portfolio/jsonartifact.py load_contract resolves a contract file the same way.
 */
export function resolvedContract(relative, pointer = '') {
  const documents = new Map()
  const load = (file) => {
    if (!documents.has(file)) {
      if (!resolve(file).startsWith(`${resolve(PLUGIN_ROOT)}/`)) throw new Error(`${file} is outside the plugin`)
      documents.set(file, JSON.parse(readFileSync(file, 'utf8')))
    }
    return documents.get(file)
  }
  const at = (file, ptr) => (ptr ? ptr.split('/').slice(1) : []).reduce((node, raw) => {
    const part = raw.replace(/~1/g, '/').replace(/~0/g, '~')
    if (!node || typeof node !== 'object' || !Object.hasOwn(node, part)) throw new Error(`${file}#${ptr} does not resolve`)
    return node[part]
  }, load(file))
  const inline = (value, file, seen) => {
    if (Array.isArray(value)) return value.map(item => inline(item, file, seen))
    if (!value || typeof value !== 'object') return value
    if (typeof value.$ref === 'string') {
      const [target, ptr = ''] = value.$ref.split('#')
      const targetFile = target ? resolve(dirname(file), target) : file
      const key = `${targetFile}#${ptr}`
      if (seen.includes(key)) throw new Error(`circular schema reference: ${[...seen, key].join(' -> ')}`)
      return inline(at(targetFile, ptr), targetFile, [...seen, key])
    }
    return Object.fromEntries(Object.entries(value).filter(([key]) => key !== '$defs').map(([key, item]) => [key, DATA_KEYWORDS.has(key) ? item : inline(item, file, seen)]))
  }
  const file = resolve(PLUGIN_ROOT, relative)
  return inline(at(file, pointer), file, [])
}

/** One schema of the artifact-handoff schemas folder at a JSON pointer, resolved as resolvedContract does. */
const resolvedSchema = (file, pointer = '') => resolvedContract(join('skills', 'artifact-handoff', 'schemas', file), pointer)

/** The canonical text of one block. */
export const canonicalBlock = (name) => {
  const text = readFileSync(join(HERE, 'shared-blocks', `${name}.js`), 'utf8').replace(/\n+$/, '')
  if (name === 'relay') {
    const handoff = (file) => join('skills', 'artifact-handoff', 'schemas', file)
    return fillPlaceholders(name, text, [
      ['/* CHECKPOINT_SCHEMA */ {}', pluginJson(handoff('checkpoint.schema.json'))],
      ['/* RELAY_COMMAND_RESULT_SCHEMA */ {}', JSON.stringify(resolvedSchema('relay-command-result.schema.json'))],
      ['/* RELAY_REGISTERED_RESULT_SCHEMA */ {}', JSON.stringify(resolvedSchema('relay-registered-result.schema.json'))],
      ['/* ARTIFACT_REFERENCE_SCHEMA */ {}', JSON.stringify(resolvedSchema('artifact-reference.schema.json'))],
    ])
  }
  if (name === 'story-deploy-args') {
    return fillPlaceholders(name, text, [['/* STORY_DEPLOY_ARGS_SCHEMA */ {}', pluginJson(blockOf(name).filledFrom)]])
  }
  if (name === 'step-journal') {
    const contracts = join('skills', 'pipeline-contracts', 'schemas')
    const schema = JSON.parse(pluginText(join(contracts, 'step-journal.schema.json')))
    const wire = {
      changePrefix: schema['x-changePrefix'],
      changePartPrefix: schema['x-changePartPrefix'],
      changeChunk: schema['x-changeChunk'],
      plannedForPrefix: schema['x-plannedForPrefix'],
    }
    return fillPlaceholders(name, text, [
      ['/* STEP_JOURNAL_WIRE */ {}', JSON.stringify(wire)],
      ['/* PIPELINE_STEPS */ {}', pluginJson(join(contracts, 'pipeline-steps.json'))],
    ])
  }
  if (name === 'architecture-artifacts') {
    const common = 'architecture-common.schema.json'
    const def = (defs, file) => resolvedSchema(file, `/$defs/${defs}`)
    const arrayOf = (defs) => JSON.stringify({ type: 'array', items: def(defs, common) })
    const values = (defs, file = common) => JSON.stringify(def(defs, file).enum)
    const fills = [
      ['/* ARCHITECTURE_WRITER_SCHEMA */ {}', JSON.stringify(resolvedSchema('architecture-writer.schema.json'))],
      ['/* ARCHITECTURE_REVIEW_SCHEMA */ {}', JSON.stringify(resolvedSchema('architecture-review.schema.json'))],
      ['/* CONFORMANCE_SCHEMA */ {}', JSON.stringify(resolvedSchema('conformance.schema.json'))],
      ['/* BUILT_CONFORMANCE_SCHEMA */ {}', JSON.stringify(resolvedSchema('built-conformance.schema.json'))],
      ['/* COVERAGE_ROWS_SCHEMA */ {}', arrayOf('CoverageRow')],
      ['/* EVIDENCE_REFS_SCHEMA */ {}', arrayOf('EvidenceRef')],
      ['/* CONFLICT_ITEMS_SCHEMA */ {}', arrayOf('BusinessConflict')],
      ['/* COVERAGE_CHECKS_SCHEMA */ {}', arrayOf('CoverageCheck')],
      ['/* COVERAGE_STATUSES */ []', values('CoverageStatus')],
      ['/* COVERAGE_ACTIONS */ []', values('CoverageAction')],
      ['/* REVIEW_VERDICTS */ []', values('ReviewVerdict')],
      ['/* RESOLUTION_VERDICTS */ []', values('ResolutionVerdict', 'architecture-review.schema.json')],
      ['/* REPAIR_VERDICTS */ []', values('RepairVerdict', 'architecture-review.schema.json')],
      ['/* ANSWER_RESPONSES */ []', values('AnswerResponse', 'architecture-writer.schema.json')],
    ]
    return fillPlaceholders(name, text, fills)
  }
  if (name !== 'fable') return text
  const userLevel = new Set(userLevelAgentNames(PLUGIN_ROOT))
  const pluginOnly = readdirSync(join(PLUGIN_ROOT, 'agents'))
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.slice(0, -'.md'.length))
    .filter((agent) => !userLevel.has(agent))
    .sort()
  return fillPlaceholders(name, text, [
    ['/* DRIVER_SURFACE_SCHEMA */ {}', pluginJson('skills/pipeline-contracts/schemas/driver-surface.schema.json')],
    ['/* PLUGIN_ONLY_AGENTS */ []', JSON.stringify(pluginOnly)],
  ])
}

/**
 * Where a block sits in `source`: the begin-marker line (whatever canonical note it carries), the
 * start of the block text, and the end marker. Null when the source lacks the markers.
 */
const locateBlock = (source, name) => {
  const begin = source.indexOf(beginPrefix(name))
  const end = source.indexOf(endMarker(name))
  if (begin < 0 || end < 0 || end < begin) return null
  const lineEnd = source.indexOf('\n', begin)
  if (lineEnd < 0 || lineEnd > end) return null
  return { begin, marker: source.slice(begin, lineEnd), body: lineEnd + 1, end }
}

/** The text between a block's markers in `source`, or null when the source lacks the markers. */
export function extractBlock(source, name) {
  const at = locateBlock(source, name)
  return at === null ? null : source.slice(at.body, at.end).replace(/\n+$/, '')
}

/** A contract-schema begin marker line: the constant name, the contract file and the optional JSON pointer. */
const CONTRACT_BEGIN = /^\/\/ ===== CONTRACT SCHEMA ([A-Za-z_$][\w$]*) = ([A-Za-z0-9_-][A-Za-z0-9._/-]*\.json)(?:#(\/\S*))? — BEGIN\b.*$/gm
const contractEnd = (constant) => `// ===== CONTRACT SCHEMA ${constant} — END =====`
export const contractBeginMarker = (constant, source, file) =>
  `// ===== CONTRACT SCHEMA ${constant} = ${source} — BEGIN (generated from that contract file; edit it, then: ${WRITE_COMMAND} --only ${file}) =====`

/**
 * Checks (or, with write, rewrites) every contract-schema block of one workflow's `source`.
 * Returns { source, problems }: the source with every block filled, and what is wrong.
 */
export function syncContractSchemas(file, source, write) {
  const problems = []
  const seen = new Set()
  const blocks = [...source.matchAll(CONTRACT_BEGIN)].map((match) => {
    const [line, constant, contract, pointer = ''] = match
    const end = source.indexOf(contractEnd(constant), match.index)
    const nextBegin = source.indexOf('// ===== CONTRACT SCHEMA ', match.index + line.length)
    return { constant, contract, pointer, begin: match.index, body: match.index + line.length + 1, end, nextBegin, line }
  })
  let out = source
  for (const block of [...blocks].reverse()) {
    const where = `${file}: contract schema ${block.constant}`
    if (seen.has(block.constant)) problems.push(`${where} is declared twice`)
    seen.add(block.constant)
    if (block.end < 0 || (block.nextBegin >= 0 && block.nextBegin < block.end)) {
      problems.push(`${where} has no end marker (${contractEnd(block.constant)}) before the next block`)
      continue
    }
    const named = `${block.contract}${block.pointer ? `#${block.pointer}` : ''}`
    let text
    try {
      text = `const ${block.constant} = ${JSON.stringify(resolvedContract(block.contract, block.pointer))}`
    } catch (err) {
      problems.push(`${where}: ${named} does not resolve: ${String((err && err.message) || err)}`)
      continue
    }
    const marker = contractBeginMarker(block.constant, named, file)
    if (block.line === marker && out.slice(block.body, block.end).replace(/\n+$/, '') === text) continue
    if (write) out = `${out.slice(0, block.begin)}${marker}\n${text}\n${out.slice(block.end)}`
    else problems.push(`${where} differs from ${named} (run ${WRITE_COMMAND} --only ${file})`)
  }
  return { source: out, problems }
}

/**
 * Checks (or, with write, rewrites) every copy of every block. Returns the problems found:
 * a listed workflow without the block, a copy that differs from the canonical text, a
 * contract-schema block whose constant differs from its contract file or lacks its end marker.
 */
export function syncSharedBlocks({ write = false, only = [] } = {}) {
  const problems = artifactCapabilityProblems(join(HERE, '..'))
  const files = readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js') && (!only.length || only.includes(f)))
  for (const file of files) {
    const path = join(WORKFLOWS, file)
    const source = readFileSync(path, 'utf8')
    const synced = syncContractSchemas(file, source, write)
    problems.push(...synced.problems)
    if (write && synced.source !== source) writeFileSync(path, synced.source)
  }
  for (const block of SHARED_BLOCKS) {
    const text = canonicalBlock(block.name)
    for (const file of files) {
      const path = join(WORKFLOWS, file)
      const source = readFileSync(path, 'utf8')
      const at = locateBlock(source, block.name)
      if (at === null) {
        if (block.requiredIn.includes(file)) problems.push(`${file}: lacks the shared block ${block.name}`)
        continue
      }
      if (block.name === 'relay' && RELAY_FROZEN.includes(file)) continue
      const marker = beginMarker(block.name)
      if (at.marker === marker && source.slice(at.body, at.end).replace(/\n+$/, '') === text) continue
      if (write) {
        writeFileSync(path, `${source.slice(0, at.begin)}${marker}\n${text}\n${source.slice(at.end)}`)
      } else {
        problems.push(`${file}: the shared block ${block.name} differs from ${block.canonical} (run ${[block.regenerate, WRITE_COMMAND].filter(Boolean).join(' and ')})`)
      }
    }
  }
  return problems
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  // --only FILE (repeatable) limits the check or rewrite to those workflow files.
  const only = process.argv.flatMap((a, i) => (process.argv[i - 1] === '--only' ? [a] : []))
  const problems = syncSharedBlocks({ write: process.argv.includes('--write'), only })
  for (const p of problems) console.error(p)
  if (problems.length) process.exit(1)
  console.log(`shared blocks ${process.argv.includes('--write') ? 'written' : 'match'}: ${SHARED_BLOCKS.map((b) => b.name).join(', ')}`)
}
