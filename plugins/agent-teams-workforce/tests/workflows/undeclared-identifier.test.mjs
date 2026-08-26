// ssbd-nhcx enabler — scripts/check-workflow-syntax.mjs could not catch an undeclared
// identifier, because it only asked V8 to PARSE. `node --check` never resolves
// identifiers, so a free variable is valid syntax and always will be: task-to-deploy.js
// read an undeclared `spec`, died with ReferenceError at Gate 1 for every caller shape,
// and the checker reported it as passing through two shipped releases.
//
// The checker now also EXECUTES each script once, with the same six injected globals the
// runtime supplies and with stub dispatchers. This test is the CI seam for that pass, and
// it also proves the pass actually detects the defect rather than merely reporting green.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..')
const CHECKER = path.join(ROOT, 'scripts', 'check-workflow-syntax.mjs')

function check(dir) {
  try {
    return { status: 0, out: execFileSync(process.execPath, [CHECKER, dir], { encoding: 'utf8' }) }
  } catch (e) {
    return { status: e.status, out: String(e.stdout || '') + String(e.stderr || '') }
  }
}

test('every shipped workflow parses AND executes without an undeclared identifier', () => {
  const r = check(path.join(ROOT, 'workflows'))
  assert.equal(r.status, 0, r.out)
  assert.match(r.out, /execute without an undeclared identifier/)
})

test('the checker actually CATCHES an undeclared identifier', () => {
  // Parse-only checking reports this file as fine. That is the whole defect.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-refcheck-'))
  try {
    fs.writeFileSync(
      path.join(dir, 'broken.js'),
      "export const meta = { name: 'broken', description: 'd' }\n" +
        "const a = args || {}\n" +
        "const r = await workflow('x', { notDeclaredAnywhere })\n" +
        'return r\n',
    )
    const r = check(dir)
    assert.equal(r.status, 1, 'a free variable must fail the check')
    assert.match(r.out, /ReferenceError: notDeclaredAnywhere is not defined/)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('a genuine syntax error is still caught by the parse pass', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-syncheck-'))
  try {
    fs.writeFileSync(path.join(dir, 'bad.js'), "export const meta = { name: 'it's broken' }\n")
    const r = check(dir)
    assert.equal(r.status, 1)
    assert.match(r.out, /FAIL {2}bad\.js/)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('a script that merely bails on a stubbed dispatch is NOT a failure', () => {
  // Dynamic checking is only useful if it has no false positives. A TypeError from a
  // null-ish stub return is the stub's doing, not the script's.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'wf-okcheck-'))
  try {
    fs.writeFileSync(
      path.join(dir, 'bails.js'),
      "export const meta = { name: 'bails', description: 'd' }\n" +
        'const a = args || {}\n' +
        'if (!a.nothingLikeThis) return { ok: false, stage: "input" }\n' +
        'return { ok: true }\n',
    )
    const r = check(dir)
    assert.equal(r.status, 0, r.out)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})
