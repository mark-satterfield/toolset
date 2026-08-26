// ssbd-ez29 — the checker bypass 6.0.8 shipped: a forbidden construct SPLIT BY A COMMENT.
//
// 6.0.7's bypass was a newline. 6.0.8 fixed it by matching each rule against the whole
// source instead of line by line, and by spanning `\s` wherever a token joins a
// parenthesis or a dot. `\s` matches whitespace — and whitespace is not the only thing
// JavaScript permits between two tokens. A COMMENT is permitted there too.
//
// Every construct below is valid JavaScript (node --check accepts all of them) and every
// one walked past the 6.0.8 rules. A scratch workflows directory carrying four of them
// made check-workflow-syntax.mjs exit 0 while printing "all N workflow scripts are free of
// constructs the runner refuses", and assertRunnerLoadable in the test harness was equally
// blind — so the whole suite would have gone green over a script the runner CANNOT LOAD.
// That is the 6.0.6 P0 failure mode exactly: 446 tests passing over an unloadable file.
//
// The fix is two things at once, and both matter:
//
//   * the separator is now GAP/GAP1 — whitespace, block comments, line comments — which is
//     the COMPLETE set the grammar allows between tokens, not a longer list of things
//     someone thought of;
//   * every rule is also matched against a comment-STRIPPED copy of the source, at
//     preserved byte offsets, ALONGSIDE the raw pass. The raw pass is not replaced: the
//     runner's own detection mechanism is undocumented, so a raw scan on its side is
//     entirely possible and a forbidden token inside a comment stays a finding.
//
// The forbidden tokens are assembled at runtime so this file never contains them
// literally — the same discipline the workflow scripts are held to.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  findForbiddenConstructs,
  assertRunnerLoadable,
  stripCommentsPreservingOffsets,
} from '../../scripts/workflow-runner-constraints.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const WORKFLOWS = path.join(ROOT, 'workflows')
const CHECKER = path.join(ROOT, 'scripts', 'check-workflow-syntax.mjs')

const IMP = 'imp' + 'ort'
const REQ = 'requ' + 'ire'
const PROC = 'proc' + 'ess'

// The exact evasions the adversarial verifier reproduced against 6.0.8.
const EVASIONS = [
  { name: 'dynamic import', code: `await ${IMP}/*x*/("node:fs")\n`, note: 'a block comment between the token and its call parenthesis' },
  { name: 'require()', code: `const m = ${REQ}/*x*/("node:fs")\n`, note: 'the CommonJS loader, same gap' },
  { name: 'new Function', code: `const f = new/*a*/Function/*b*/("return 1")\n`, note: 'runtime code generation, two gaps' },
  { name: 'process', code: `const e = ${PROC}/*a*/.env\n`, note: 'a member access on the process object' },
  { name: 'require.resolve', code: `const p = ${REQ}/*a*/./*b*/resolve("x")\n`, note: 'module resolution, a comment on each side of the dot' },
  { name: 'dynamic import', code: `await ${IMP}\n// a line comment\n("node:fs")\n`, note: 'a NEWLINE and a line comment — 6.0.8 covered the newline alone' },
  { name: 'import statement', code: `${IMP}/*c*/{ readFileSync } from 'node:fs'\n`, note: 'a module import with the comment before the specifier list' },
]

// ── 1. Each evasion is valid JavaScript. If it were not, it would prove nothing. ──

for (const { name, code, note } of EVASIONS) {
  test(`${name}: the evasion is real JavaScript — ${note}`, () => {
    const probe = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cmt-valid-')), 'probe.mjs')
    // `import` is only legal at module top level; the rest go inside an async function.
    fs.writeFileSync(probe, name === 'import statement' ? code : `async function f() {\n${code}\n}\n`)
    execFileSync(process.execPath, ['--check', probe], { stdio: 'pipe' })
  })
}

// ── 2. And each one is now DETECTED. Against 6.0.8 every one of these fails. ──

for (const { name, code, note } of EVASIONS) {
  test(`${name}: split by a comment is still caught — ${note}`, () => {
    const found = findForbiddenConstructs(code)
    assert.ok(
      found.some((f) => f.name === name),
      `a comment between the tokens must not hide ${name}; found: ${JSON.stringify(found.map((f) => f.name))}`,
    )
  })
}

test('the test HARNESS refuses a comment-split construct too, not only the checker', () => {
  // 6.0.6 shipped because the harness was more permissive than production. A harness that
  // still accepted these would let 574 tests agree with each other over an unloadable
  // script — the failure mode this whole file exists to prevent.
  for (const { name, code } of EVASIONS) {
    assert.throws(() => assertRunnerLoadable(code, 'probe.js'), /REFUSE to load/, `harness accepted ${name}`)
  }
})

// ── 3. The end-to-end proof: the CHECKER exits non-zero over a scratch directory ──

test('check-workflow-syntax.mjs FAILS on a workflows directory carrying comment-split constructs', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cmt-workflows-'))
  const scripts = [
    `export const meta = { name: 'a', description: 'a', phases: [] }\nlet m\nif (false) { m = await ${IMP}/*x*/('node:fs') }\nreturn { ok: true }\n`,
    `export const meta = { name: 'b', description: 'b', phases: [] }\nlet m\nif (false) { m = ${REQ}/*x*/('node:fs') }\nreturn { ok: true }\n`,
    `export const meta = { name: 'c', description: 'c', phases: [] }\nlet f\nif (false) { f = new/*a*/Function/*b*/('return 1') }\nreturn { ok: true }\n`,
    `export const meta = { name: 'd', description: 'd', phases: [] }\nlet e\nif (false) { e = ${PROC}/*a*/.env }\nreturn { ok: true }\n`,
  ]
  scripts.forEach((src, i) => fs.writeFileSync(path.join(dir, `probe-${i}.js`), src))

  let status = 0
  let stdout = ''
  try {
    stdout = execFileSync(process.execPath, [CHECKER, dir], { encoding: 'utf8' })
  } catch (err) {
    status = err.status
    stdout = String(err.stdout || '')
  }

  assert.equal(status, 1, `the checker must FAIL over these scripts. It printed:\n${stdout}`)
  assert.ok(
    !/are free of constructs the runner refuses/.test(stdout),
    'and it must never claim the directory is clean:\n' + stdout,
  )
  assert.match(stdout, /runner-strictness violation/, 'the failure must name what it is')
  assert.equal((stdout.match(/CANNOT LOAD/g) || []).length, 1)
  fs.rmSync(dir, { recursive: true, force: true })
})

// ── 4. The raw pass is ADDED TO, never replaced ──────────────────────────────

test('a forbidden token written only inside a comment is STILL a finding', () => {
  // The runner's detection mechanism is undocumented, a raw scan on its side is possible,
  // and 6.0.6 was an outage. Stripping comments before scanning would have quietly
  // relaxed this; the two passes exist so it cannot.
  const found = findForbiddenConstructs(`// harmless mention: await ${IMP}('node:fs')\nreturn 1\n`)
  assert.ok(found.some((f) => f.name === 'dynamic import'), 'a comment is not a hiding place')
  assert.equal(found[0].via, 'raw', 'and it is the RAW pass that says so')
})

test('a construct only visible once comments are removed is reported as such', () => {
  // GAP covers every gap the rules were written around, so most evasions are caught by
  // the raw pass now. This one is not: the import-statement rule anchors to the start of
  // the line, and a block comment BEFORE the keyword pushes it off that anchor. The raw
  // pass sees nothing; the stripped copy — same offsets, comment blanked — sees it. That
  // is what the second pass is for, and why a separator rule alone is not enough.
  const found = findForbiddenConstructs(`/*x*/${IMP} { readFileSync } from 'node:fs'\n`)
  const hit = found.find((f) => f.name === 'import statement')
  assert.ok(hit, 'a comment before the keyword must not hide a module import')
  assert.equal(hit.via, 'comment-stripped')
  assert.match(hit.text, /SPLIT BY A COMMENT/, 'the report must say why the raw line does not look forbidden')
  assert.equal(hit.line, 1, 'offsets are preserved, so the line number still points at the raw source')
})

// ── 5. The stripper must not invent findings in the REAL corpus ──────────────

test('the comment-stripped pass finds nothing in the 25 real workflow scripts', () => {
  const files = fs.readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js'))
  assert.ok(files.length >= 25, 'the corpus should not have shrunk')
  for (const file of files) {
    const raw = fs.readFileSync(path.join(WORKFLOWS, file), 'utf8')
    assert.deepEqual(findForbiddenConstructs(raw), [], `${file} must stay clean under BOTH passes`)
  }
})

test('stripping preserves length and every newline position', () => {
  for (const file of fs.readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js'))) {
    const raw = fs.readFileSync(path.join(WORKFLOWS, file), 'utf8')
    const stripped = stripCommentsPreservingOffsets(raw)
    assert.equal(stripped.length, raw.length, `${file}: a shifted offset reports the wrong line`)
    for (let i = 0; i < raw.length; i++) {
      if (raw[i] === '\n') assert.equal(stripped[i], '\n', `${file}: newline at ${i} was lost`)
    }
  }
})

test('stripping leaves a `//` inside a string or a regex alone', () => {
  // A regex literal like /^refs\/heads\// contains `//`. Mistaking it for a comment would
  // blank real code and turn this checker into a source of FALSE NEGATIVES.
  const src = "const a = 'http://x/y'\nconst b = String(z).replace(/^refs\\/heads\\//, '')\nconst c = 1\n"
  const stripped = stripCommentsPreservingOffsets(src)
  assert.ok(stripped.includes("'http://x/y'"), 'the string survived')
  assert.ok(stripped.includes('const c = 1'), 'and nothing after the regex was swallowed')
})
