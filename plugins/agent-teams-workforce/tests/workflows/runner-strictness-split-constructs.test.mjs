// The checker bypass 6.0.7 shipped: a forbidden construct SPLIT ACROSS A NEWLINE.
//
// findForbiddenConstructs used to run each rule against each LINE in isolation
// (`lines.findIndex(l => re.test(l))`). No single line of
//
//     let fsmod
//     if (false) { fsmod = await import
//       ("node:fs") }
//
// contains a whole dynamic import, so every rule missed it and the checker printed
// "all 25 workflow scripts are free of constructs the runner refuses" and exited 0 —
// over a script the real runner WOULD refuse, because `import` NEWLINE `(` is a valid
// ImportCall. The same three-character edit evaded the CommonJS loader rule, the
// runtime-code-generation rule, and the process-object rule. The checker and the unit
// test harness both consume that one function, so both were bypassed together.
//
// The fix runs each rule over the WHOLE source and derives the line number from the
// match index. These tests pin it. Every case below is written in split form and FAILS
// against the line-by-line implementation.
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
import { FORBIDDEN_CONSTRUCTS, findForbiddenConstructs, assertRunnerLoadable } from '../../scripts/workflow-runner-constraints.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const WORKFLOWS = path.join(ROOT, 'workflows')
const CHECKER = path.join(ROOT, 'scripts', 'check-workflow-syntax.mjs')

// Assembled, never written. `IMP` is the dynamic-import keyword, `REQ` the CommonJS one.
const IMP = 'imp' + 'ort'
const REQ = 'requ' + 'ire'
const PROC = 'proc' + 'ess'

// Every construct in the list, with the split form that used to walk past the checker.
// `split` is the evasion; where a construct is a single token there is nothing to split,
// and `split` is null — those rows are regression guards, not evasion proofs.
const CASES = [
  {
    name: 'dynamic import',
    split: `let m\nif (false) { m = await ${IMP}\n  ('node:fs') }\n`,
    note: 'the exact form the adversarial verifier used to walk past the 6.0.7 checker',
  },
  {
    name: 'import statement',
    split: `${IMP}\n  { readFileSync } from 'node:fs'\n`,
    note: 'a module import whose specifier list starts on the next line',
  },
  {
    name: 'require()',
    split: `const fsmod = ${REQ}\n  ('node:fs')\n`,
    note: 'the CommonJS loader with its call parenthesis on the next line',
  },
  {
    name: 'require.resolve',
    split: `const where = ${REQ}\n  .resolve('node:fs')\n`,
    note: 'a member access on the CommonJS loader, split at the dot',
  },
  {
    name: 'new Function',
    split: `const f = new\n  Function('return 1')\n`,
    note: 'runtime code generation with the constructor name on the next line',
  },
  {
    name: 'process',
    split: `const argv = ${PROC}\n  .argv\n`,
    note: 'a member access on the process object, split at the dot',
  },
  { name: 'child_process', split: null, note: 'one token — it has no split form; this row guards against losing the rule' },
  { name: '__dirname / __filename', split: null, note: 'one token — no split form' },
  { name: 'globalThis', split: null, note: 'one token — no split form' },
]

test('every construct in the shared list has a case here', () => {
  // A table that silently falls behind the list it tests is worth nothing. If a rule is
  // added, a case for it must be added too.
  assert.deepEqual(
    FORBIDDEN_CONSTRUCTS.map((c) => c.name).sort(),
    CASES.map((c) => c.name).sort(),
    'add the new construct to CASES, in split form if it has one',
  )
})

// ── The bypass itself ─────────────────────────────────────────────────────────
for (const { name, split, note } of CASES) {
  if (!split) continue
  test(`SPLIT ACROSS A NEWLINE, ${name} is still caught — ${note}`, () => {
    const src = `export const meta = { name: 'probe', description: 'x' }\n${split}return { ok: true }\n`
    const found = findForbiddenConstructs(src)
    assert.ok(
      found.some((f) => f.name === name),
      `a newline between the token and what follows it evaded the whole checker. Found instead: ` +
        `${JSON.stringify(found.map((f) => f.name))}`,
    )
  })

  test(`SPLIT ACROSS A NEWLINE, ${name} reports a usable line number`, () => {
    // Reporting quality is part of the fix: a finding that cannot name where it is
    // sends the reader through the file by hand.
    const src = `export const meta = { name: 'probe', description: 'x' }\n// filler\n// filler\n${split}return { ok: true }\n`
    const hit = findForbiddenConstructs(src).find((f) => f.name === name)
    assert.ok(hit, `${name} was not found at all`)
    assert.equal(typeof hit.line, 'number')
    assert.ok(hit.line >= 4, `the construct starts on line 4 or later, reported line ${hit.line}`)
    assert.ok(hit.line <= src.split('\n').length, `reported line ${hit.line} is past the end of the file`)
    assert.ok(String(hit.text || '').length > 0, 'a finding must show the offending text')
  })
}

test('a split construct makes the HARNESS refuse the script, as an unsplit one does', () => {
  // The harness and the checker consume the same function, so the bypass bypassed both.
  const src = `export const meta = { name: 'probe', description: 'x' }\nlet m\nif (false) { m = await ${IMP}\n  ('node:fs') }\nreturn { ok: true }\n`
  assert.throws(
    () => assertRunnerLoadable(src, 'probe.js'),
    /would REFUSE to load/,
    'a harness that runs an unloadable script makes every test against it meaningless',
  )
})

test('the CHECKER exits non-zero on a workflows directory carrying a split construct', () => {
  // End to end, through the real script, because that is what CI runs. Against 6.0.7
  // this exited 0 and printed the all-clear line.
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'split-construct-'))
  try {
    fs.writeFileSync(
      path.join(dir, 'probe.js'),
      `export const meta = { name: 'probe', description: 'x' }\nlet m\nif (false) { m = await ${IMP}\n  ('node:fs') }\nreturn { ok: true }\n`,
    )
    let status = 0
    let stdout = ''
    try {
      stdout = String(execFileSync(process.execPath, [CHECKER, dir], { stdio: 'pipe' }))
    } catch (err) {
      status = err.status
      stdout = String(err.stdout || '')
    }
    assert.equal(status, 1, `the checker must FAIL on an unloadable script. It printed:\n${stdout}`)
    assert.match(stdout, /dynamic import is not available/, 'the failure must name the construct')
    assert.doesNotMatch(stdout, /free of constructs the runner refuses/, 'it must not also print the all-clear')
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

// ── No false positives ────────────────────────────────────────────────────────
//
// Strictness bought by refusing prose is not strictness. The workflow scripts discuss
// these constructs by name on purpose — a Red gate tells its writer not to reject a
// failure "as an import error" — and that must keep passing.

test('the real workflow set is still clean — the fix added no false positive', () => {
  const offenders = []
  for (const f of fs.readdirSync(WORKFLOWS).filter((n) => n.endsWith('.js'))) {
    for (const hit of findForbiddenConstructs(fs.readFileSync(path.join(WORKFLOWS, f), 'utf8'))) {
      offenders.push(`${f}:${hit.line} ${hit.name} — ${hit.text}`)
    }
  }
  assert.deepEqual(offenders, [], `the whole-source scan flagged prose the line scan did not:\n  ${offenders.join('\n  ')}`)
})

test('prose about an import error, in a comment and in a prompt, still passes', () => {
  const src =
    `export const meta = { name: 'probe', description: 'x' }\n` +
    `// The older wording ("not a harness or ${IMP} error") made the gate reject a correct test.\n` +
    `// Reject only a genuine harness fault: the test module itself failing to ${IMP}, a broken\n` +
    `// fixture, a typo, or a missing test dependency.\n` +
    `const prompt = 'do NOT reject it as an ${IMP} error'\n` +
    `const more = 'a test pinned to a pre-fix ${IMP} path can never go green'\n` +
    `const proseProcess = 'the review ${PROC} is not a shell'\n` +
    `return { ok: true, prompt, more, proseProcess }\n`
  assert.deepEqual(findForbiddenConstructs(src), [], 'prose naming a construct is not the construct')
})

test('the workflow set really does carry that prose — the false-positive test is not vacuous', () => {
  // If the prose ever disappears, this test says so rather than quietly guarding nothing.
  // bug-fix.js alone carries 9 of these, in the Red gate's missing-capability carve-out.
  const word = new RegExp(`\\b${IMP}\\b`, 'gi')
  const phrase = new RegExp(`${IMP}\\s+error`, 'gi')
  let words = 0
  let phrases = 0
  let inBugFix = 0
  for (const f of fs.readdirSync(WORKFLOWS).filter((n) => n.endsWith('.js'))) {
    const src = fs.readFileSync(path.join(WORKFLOWS, f), 'utf8')
    const hits = (src.match(word) || []).length
    words += hits
    phrases += (src.match(phrase) || []).length
    if (f === 'bug-fix.js') inBugFix = hits
  }
  assert.ok(inBugFix >= 9, `bug-fix.js should still discuss the token at least 9 times, found ${inBugFix}`)
  assert.ok(words >= 15, `the workflow set should still discuss the token at least 15 times, found ${words}`)
  assert.ok(phrases >= 5, `the literal "<token> error" phrase should still appear at least 5 times, found ${phrases}`)
})
