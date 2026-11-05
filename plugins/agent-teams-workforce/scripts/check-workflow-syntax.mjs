#!/usr/bin/env node
// Parse workflow syntax and inspect source constraints without executing workflow bodies.
// Usage: node scripts/check-workflow-syntax.mjs [workflows-dir]
import { readdirSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { syncSharedBlocks } from './shared-blocks.mjs'
import { findForbiddenConstructs, findNondeterminism, neutralizeMetaExport } from './workflow-runner-constraints.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const dir = process.argv[2] || path.join(here, '..', 'workflows')
const files = readdirSync(dir).filter(file => file.endsWith('.js')).sort()
const scratch = mkdtempSync(path.join(tmpdir(), 'wf-syntax-'))
const failures = []

try {
  for (const file of files) {
    const raw = readFileSync(path.join(dir, file), 'utf8')
    const source = neutralizeMetaExport(raw)
    const parsed = path.join(scratch, file.replace(/\.js$/, '.cjs'))
    // The async wrapper permits workflow-level await/return; --check only parses it.
    writeFileSync(parsed, `(async () => {\n${source}\n})\n`)
    try {
      execFileSync(process.execPath, ['--check', parsed], { stdio: 'pipe' })
    } catch (error) {
      const text = String(error.stderr || error.message)
      const detail = text.split('\n').find(line => line.startsWith('SyntaxError')) || text.split('\n')[0]
      failures.push(`${file}: ${detail.trim()}`)
    }
    for (const finding of [...findForbiddenConstructs(raw), ...findNondeterminism(raw)]) {
      failures.push(`${file}:${finding.line}: ${finding.name}: ${finding.why}`)
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true })
}

if (!files.length) failures.push(`No .js files found in ${dir}`)
failures.push(...syncSharedBlocks())
for (const failure of failures) console.log(`FAIL  ${failure}`)
console.log(failures.length
  ? `${failures.length} static workflow source finding(s)`
  : `${files.length} workflows parse; literal source constraints and shared blocks match`)
// Parsing and literal scans do not prove dynamic identifier resolution or behavior.
process.exit(failures.length ? 1 : 0)
