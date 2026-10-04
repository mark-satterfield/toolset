// The shared blocks every workflow script embeds verbatim, and the one tool that writes them.
//
// A workflow script is not a module: the runner gives it seven globals and no loader, and
// scripts/workflow-runner-constraints.mjs refuses import and require in it. Code every workflow
// needs therefore has ONE canonical text, in scripts/shared-blocks/<name>.js, and each workflow
// carries it between two marker lines. Nobody edits a copy: edit the canonical file and run
//
//     node scripts/shared-blocks.mjs --write [--only <workflow>.js ...]
//
// which rewrites every copy (or only the named workflows'). A workflow gets a block by carrying
// the two marker lines, with anything between them, and being listed in SHARED_BLOCKS; --write
// then fills it. check-workflow-syntax.mjs (the pre-commit gate) fails when any copy
// differs from its canonical text, or a workflow listed for a block lacks it.
//
// The import ban applies to WORKFLOW SCRIPTS; this file is an ordinary ES module.

import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { agentContracts } from './agent-contracts.mjs'
import { artifactCapabilityProblems } from './artifact-capabilities.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = join(HERE, '..', 'workflows')

/** Every shared block: its name, and the workflows that must carry it. */
export const SHARED_BLOCKS = Object.freeze([
  { name: 'architecture-baseline', requiredIn: ['architecture.js'] },
  { name: 'architecture-artifacts', requiredIn: ['architecture.js'] },
  { name: 'trd-artifact', requiredIn: ['trd-authoring.js'] },
  {
    name: 'fable',
    requiredIn: [
      'adversarial.js',
      'architecture.js',
      'bug-fix.js',
      'bug-triage.js',
      'built-version.js',
      'dependency-assessment.js',
      'deploy-mechanism.js',
      'deploy.js',
      'documentation.js',
      'gate-enforce.js',
      'infra-intent.js',
      'integration.js',
      'prd-creation.js',
      'prd-reconciliation.js',
      'prd-to-spec.js',
      'prd-validation.js',
      'repo-scoping.js',
      'settle.js',
      'spec-authoring.js',
      'story-deploy-fix.js',
      'suite-run.js',
      'task-decomposition.js',
      'task-dependency-assessment.js',
      'task-to-deploy.js',
      'tdd-green.js',
      'tdd-red.js',
      'tdd-refactor.js',
      'trd-authoring.js',
      'workspace.js',
      'wsjf-scoring.js',
    ],
  },
  {
    name: 'relay',
    requiredIn: [
      'architecture.js',
      'bug-fix.js',
      'built-version.js',
      'dependency-assessment.js',
      'deploy.js',
      'integration.js',
      'prd-reconciliation.js',
      'prd-to-spec.js',
      'prd-validation.js',
      'repo-scoping.js',
      'settle.js',
      'spec-authoring.js',
      'story-deploy-fix.js',
      'suite-run.js',
      'task-decomposition.js',
      'task-dependency-assessment.js',
      'task-to-deploy.js',
      'tdd-refactor.js',
      'trd-authoring.js',
      'workspace.js',
      'wsjf-scoring.js',
    ],
  },
])

export const beginMarker = (name) => `// ===== SHARED BLOCK ${name} — BEGIN (canonical: scripts/shared-blocks/${name}.js; edit there, then: node scripts/shared-blocks.mjs --write) =====`
export const endMarker = (name) => `// ===== SHARED BLOCK ${name} — END =====`

/** The canonical text of one block. */
export const canonicalBlock = (name) => {
  const text = readFileSync(join(HERE, 'shared-blocks', `${name}.js`), 'utf8').replace(/\n+$/, '')
  if (name === 'architecture-baseline') return text.replace('/* ARCHITECTURE_BASELINE_SCHEMA */ {}', () => JSON.stringify(JSON.parse(readFileSync(join(HERE, '..', 'skills', 'artifact-handoff', 'schemas', 'architecture-baseline.schema.json'), 'utf8'))))
  if (name === 'architecture-artifacts') {
    const schema = kind => JSON.stringify(JSON.parse(readFileSync(join(HERE, '..', 'skills', 'artifact-handoff', 'schemas', `architecture-${kind}.schema.json`), 'utf8')))
    return text.replace('/* ARCHITECTURE_WRITER_SCHEMA */ {}', () => schema('writer'))
      .replace('/* ARCHITECTURE_REVIEW_SCHEMA */ {}', () => schema('review'))
  }
  if (name === 'trd-artifact') return text.replace('/* TRD_ARTIFACT_SCHEMA */ {}', () => JSON.stringify(JSON.parse(readFileSync(join(HERE, '..', 'skills', 'artifact-handoff', 'schemas', 'trd.schema.json'), 'utf8'))))
  // Registry data is generated from owned definitions; no manually maintained allowlist.
  if (name !== 'fable') return text
  const core = ['subagent-contract'].map(skill =>
    readFileSync(join(HERE, '..', 'skills', skill, 'SKILL.md'), 'utf8')).join('\n\n')
  return text.replace('/* OWNED_AGENT_CONTRACTS */ {}', () => JSON.stringify(agentContracts(join(HERE, '..'))))
    .replace("/* OWNED_CORE_CONTRACTS */ ''", () => JSON.stringify(core))
    .replace("/* OWNED_BASELINE_CONTRACT */ ''", () => JSON.stringify(readFileSync(join(HERE, '..', 'skills', 'architecture-baseline', 'SKILL.md'), 'utf8')))
    .replace("/* OWNED_ARTIFACT_CONTRACT */ ''", () => JSON.stringify(readFileSync(join(HERE, '..', 'skills', 'artifact-handoff', 'SKILL.md'), 'utf8')))
}

/** The text between a block's markers in `source`, or null when the source lacks the markers. */
export function extractBlock(source, name) {
  const b = source.indexOf(beginMarker(name))
  const e = source.indexOf(endMarker(name))
  if (b < 0 || e < 0 || e < b) return null
  return source.slice(b + beginMarker(name).length + 1, e).replace(/\n+$/, '')
}

/**
 * Checks (or, with write, rewrites) every copy of every block. Returns the problems found:
 * a listed workflow without the block, a copy that differs from the canonical text.
 */
export function syncSharedBlocks({ write = false, only = [] } = {}) {
  const problems = artifactCapabilityProblems(join(HERE, '..'))
  const files = readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js') && (!only.length || only.includes(f)))
  for (const block of SHARED_BLOCKS) {
    const text = canonicalBlock(block.name)
    for (const file of files) {
      const path = join(WORKFLOWS, file)
      const source = readFileSync(path, 'utf8')
      const copy = extractBlock(source, block.name)
      if (copy === null) {
        if (block.requiredIn.includes(file)) problems.push(`${file}: lacks the shared block ${block.name}`)
        continue
      }
      if (copy === text) continue
      if (write) {
        const b = source.indexOf(beginMarker(block.name))
        const e = source.indexOf(endMarker(block.name))
        writeFileSync(path, `${source.slice(0, b)}${beginMarker(block.name)}\n${text}\n${source.slice(e)}`)
      } else {
        problems.push(`${file}: the shared block ${block.name} differs from scripts/shared-blocks/${block.name}.js (run node scripts/shared-blocks.mjs --write)`)
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
