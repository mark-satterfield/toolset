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
import os from 'node:os'
import { fileURLToPath } from 'node:url'
import { runWorkflowScript } from './helpers/run-workflow.mjs'
import { FORBIDDEN_CONSTRUCTS, findForbiddenConstructs } from '../../scripts/workflow-runner-constraints.mjs'

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

// ── RUNNER STRICTNESS (the 6.0.6 P0) ──────────────────────────────────────────
//
// 6.0.6 shipped a workspace.js that COULD NOT LOAD. It used a dynamic import to reach
// Node's process-spawning module, and the real runner refuses that statically: the
// rejection is total and happens at load, so an occurrence inside a function that is
// never called still makes the whole script unloadable. workspace.js is the first phase
// of all three composites, so no composite could start a run.
//
// Nothing caught it, and the reason is precise: BOTH things that were supposed to —
// scripts/check-workflow-syntax.mjs and this suite's own harness — model the runtime with
// an AsyncFunction body, where a dynamic import works fine. So 446 tests passed and an
// adversarial verifier's 28 probes all missed that the script was unloadable.
//
// A fix that does not close THAT stays open. These tests pin the closure.

for (const file of scripts) {
  test(`${file}: uses no construct the real runner refuses`, () => {
    // RAW bytes — comments and strings are NOT stripped, deliberately. How the runner
    // detects the construct is undocumented, so a raw scan on its side is possible and a
    // "harmless" mention in a comment is not worth risking a repeat outage over.
    const found = findForbiddenConstructs(fs.readFileSync(path.join(WORKFLOWS, file), 'utf8'))
    assert.deepEqual(
      found.map((f) => `line ${f.line}: ${f.name}`),
      [],
      `this script CANNOT LOAD in production:\n  ${found.map((f) => `line ${f.line}: ${f.name} — ${f.why}`).join('\n  ')}`,
    )
  })
}

test('the forbidden list actually covers the construct that shipped the P0', () => {
  // A guard nobody checks the contents of is a guard that quietly loses its teeth.
  const names = FORBIDDEN_CONSTRUCTS.map((c) => c.name)
  for (const required of ['dynamic import', 'require()', 'process', 'child_process', 'new Function']) {
    assert.ok(names.includes(required), `"${required}" must stay in the list the runner-strictness checks share`)
  }
})

test('the HARNESS refuses what the runner refuses — it is no longer the more permissive model', async () => {
  // The positive control. Without this the whole fix is unverified: the harness executing
  // an unloadable script is exactly how 6.0.6 shipped green. So plant the defect and
  // require the harness to reject it.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'runner-strict-'))
  try {
    const probe = path.join(dir, 'probe.js')
    fs.writeFileSync(
      probe,
      "export const meta = { name: 'probe', description: 'x' }\n" +
        // Assembled at runtime so this test file itself stays free of the token.
        `const neverCalled = async () => await ${'imp' + 'ort'}('node:fs')\n` +
        'return { ok: true }\n',
    )
    await assert.rejects(
      () => runWorkflowScript(probe, { args: {} }),
      /would REFUSE to load|dynamic import/,
      'a harness that runs an unloadable script makes every test against it meaningless',
    )
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('the harness still runs a script the runner WOULD accept', async () => {
  // The strictness must not have been bought by refusing everything.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'runner-strict-ok-'))
  try {
    const probe = path.join(dir, 'probe.js')
    fs.writeFileSync(probe, "export const meta = { name: 'probe', description: 'x' }\nreturn { ok: true }\n")
    const { result } = await runWorkflowScript(probe, { args: {} })
    assert.deepEqual(result, { ok: true })
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('the checker and the harness share ONE list, so they cannot drift apart', () => {
  // Two copies of this rule is how the harness ended up more permissive than the checker
  // in the first place. Both must import the shared module rather than restate it.
  const checker = fs.readFileSync(path.resolve(WORKFLOWS, '..', 'scripts', 'check-workflow-syntax.mjs'), 'utf8')
  const harness = fs.readFileSync(path.join(HERE, 'helpers', 'run-workflow.mjs'), 'utf8')
  assert.match(checker, /workflow-runner-constraints\.mjs/, 'the syntax checker must use the shared list')
  assert.match(harness, /workflow-runner-constraints\.mjs/, 'the test harness must use the SAME shared list')
})
