// Every workflow script must be LAUNCHABLE by the real runtime.
//
// bug-fix.js carried a second top-level export (DEPLOYED_RED_CRITERION) and the
// runtime rejected the whole script with "Unexpected keyword 'export'" before any
// phase ran — so the composite could never be dispatched at all. It shipped that
// way through several releases.
//
// The test harness hid it: runWorkflowScript strips EVERY `export const` prefix
// with a regex, so it is strictly more permissive than the runtime it models. A
// suite that only exercises scripts through the harness cannot see this class of
// defect. These tests read the source directly for that reason.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const WORKFLOWS = path.resolve(HERE, '..', '..', 'workflows')
const scripts = fs.readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js'))

test('there are workflow scripts to check', () => {
  assert.ok(scripts.length > 10, `expected the workflow set, found ${scripts.length}`)
})

for (const file of scripts) {
  const src = fs.readFileSync(path.join(WORKFLOWS, file), 'utf8')
  const exports = src.split('\n').filter((l) => /^export\s/.test(l))

  test(`${file}: exactly one top-level export, and it is meta`, () => {
    assert.equal(
      exports.length,
      1,
      `the runtime accepts one top-level export and rejects the script on a second, ` +
        `before any phase runs. Found ${exports.length}: ${exports.map((e) => e.trim().slice(0, 60)).join(' | ')}. ` +
        `Make the extras plain consts — nothing imports them.`,
    )
    assert.match(exports[0], /^export const meta\s*=/, `the single export must be \`meta\`, found: ${exports[0].trim()}`)
  })

  test(`${file}: meta declares a name and a description`, () => {
    const m = /export const meta = \{([\s\S]*?)\n\}/.exec(src)
    assert.ok(m, 'meta must be a top-level object literal the runtime can read')
    assert.match(m[1], /name:\s*'[^']+'/, 'meta.name is required')
    assert.match(m[1], /description:/, 'meta.description is required')
  })
}
