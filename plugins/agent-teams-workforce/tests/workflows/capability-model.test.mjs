// The CAPABILITY MODEL — the test suite that is derived from the model rather than from
// the attack list.
//
// WHY THIS FILE EXISTS AT ALL, AND WHY IT IS NOT ANOTHER TABLE OF PAYLOADS.
//
// Six rounds running, a fix was correct for its examples and the next probe was the same
// class one step out: a line-scan fell to a newline, that fix fell to `/* */`, that fix
// fell to Annex B `<!--`, and the round that closed the SEPARATOR question properly was
// then beaten one level UP — `Function('return this')()` returned the live global object,
// the process uid and $HOME while the checker printed "free of constructs the runner
// refuses". The root cause named at the time is the whole reason for this file: the
// refusal set was an EXAMPLE LIST, and a suite built from the three known payloads would
// have reproduced exactly the failure it was written to end.
//
// So the cases below are enumerated from scripts/workflow-runner-constraints.mjs's
// capability model, not from anything anyone has tried:
//
//   * one case per CAPABILITY CATEGORY the model names (C1 module loading, C2 code
//     generation from strings, C3 the global object or another realm, C4 a host
//     capability), INCLUDING categories nobody has attacked;
//   * one case per REACH MECHANISM the model names (direct, aliased, computed,
//     parenthesized, constructed, indirect, swallowed by a catch);
//   * one case per out-of-contract binding in the model's own list, iterated from the
//     list, so a binding added without a case is impossible and a binding REMOVED from
//     the list fails a test;
//   * one case per SEPARATOR PRODUCTION for the ReDoS bound, iterated the same way.
//
// And the boundary is tested too. The model states what remains open; a test asserts the
// open thing is open, so that a future reader learns it from the suite rather than from
// an outage.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  CAPABILITIES,
  FORBIDDEN_CONSTRUCTS,
  OUT_OF_CONTRACT_GLOBALS,
  RUNNER_GLOBALS,
  SEPARATOR_PRODUCTIONS,
  compileWorkflowBody,
  createCapabilityProbe,
  findForbiddenConstructs,
} from '../../scripts/workflow-runner-constraints.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(HERE, '..', '..')
const WORKFLOWS = path.join(ROOT, 'workflows')
const CHECKER = path.join(ROOT, 'scripts', 'check-workflow-syntax.mjs')

/** Run a workflow body under the capability probe and report what it reached. */
async function probe(body) {
  const compiled = compileWorkflowBody(body)
  let thrown = null
  try {
    await compiled.invoke({
      args: {},
      agent: async () => ({ ok: true }),
      workflow: async () => ({ ok: true }),
      phase: () => {},
      log: () => {},
      parallel: async (t = []) => Promise.all(t.map((x) => x())),
      budget: { total: 1, remaining: () => 1 },
    })
  } catch (err) {
    thrown = err
  }
  return { escapes: compiled.escapes, thrown }
}

// ── 1. THE MODEL ITSELF ───────────────────────────────────────────────────────
//
// The model is the definition everything else derives from. If it drifts silently, every
// derivation below is derived from something nobody agreed to.

test('the runner injects exactly seven globals, and they are named', () => {
  assert.deepEqual([...RUNNER_GLOBALS], ['args', 'agent', 'workflow', 'phase', 'log', 'parallel', 'budget'])
})

test('EVERY refusal rule names the capability it is derived from', () => {
  // This is the whole fix in one assertion. A rule that cannot say which capability it
  // serves was appended because somebody thought of it, which is the defect.
  for (const rule of FORBIDDEN_CONSTRUCTS) {
    assert.ok(
      CAPABILITIES.includes(rule.capability),
      `"${rule.name}" carries capability ${JSON.stringify(rule.capability)}, which is not one of the ` +
        `model's categories — either it is not derived from the model, or the model has grown a category`,
    )
  }
})

test('EVERY capability category has at least one rule — the model has no unimplemented half', () => {
  for (const capability of CAPABILITIES) {
    assert.ok(
      FORBIDDEN_CONSTRUCTS.some((r) => r.capability === capability),
      `${capability} is named by the model but nothing refuses it`,
    )
  }
})

test('the shadowed names and the injected globals are disjoint', () => {
  // A collision would shadow a global the script is ENTITLED to, turning the probe from
  // a control into a breakage.
  const overlap = OUT_OF_CONTRACT_GLOBALS.filter((n) => RUNNER_GLOBALS.includes(n))
  assert.deepEqual(overlap, [], 'the probe would shadow a binding the runner legitimately injects')
})

// ── 2. ONE CASE PER CAPABILITY CATEGORY ───────────────────────────────────────
//
// Including C1, whose only previously-tested forms were syntax. The point is the
// category, not the spelling.

const BY_CATEGORY = [
  { capability: 'C1 module loading', body: `return require('node:fs')`, reached: 'require' },
  { capability: 'C2 code generation from strings', body: `return Function('return this')()`, reached: 'Function' },
  { capability: 'C3 the global object or another realm', body: `return globalThis.process`, reached: 'globalThis' },
  { capability: 'C4 a host capability the runner does not inject', body: `return process.env.HOME`, reached: 'process' },
]

test('every capability category has a runtime case here', () => {
  assert.deepEqual(
    BY_CATEGORY.map((c) => c.capability).sort(),
    [...CAPABILITIES].sort(),
    'a category added to the model without a runtime case is an untested claim',
  )
})

for (const { capability, body, reached } of BY_CATEGORY) {
  test(`${capability} — a script reaching it is CAUGHT AT RUNTIME`, async () => {
    const { escapes } = await probe(body)
    assert.ok(
      escapes.some((e) => e.name === reached),
      `nothing recorded a reach for ${reached}. Recorded: ${JSON.stringify(escapes.map((e) => e.name))}`,
    )
  })
}

// ── 3. ONE CASE PER REACH MECHANISM ───────────────────────────────────────────
//
// The mechanisms are the model's, not the attacker's. Three of these (direct call,
// `new` with a parenthesized callee, indirect eval) are the reaches that were PROVEN end
// to end against 6.0.10; the rest are the mechanisms the model says a scan cannot see,
// and they are here to show the probe sees them anyway.

const MECHANISMS = [
  { how: 'a direct call', body: `return Function('return this')()`, reached: 'Function' },
  { how: 'a parenthesized callee with new', body: `return new (Function)('return this')()`, reached: 'Function' },
  { how: 'indirect eval through a comma expression', body: `return (0, eval)('this')`, reached: 'eval' },
  { how: 'an ALIAS bound on an earlier line', body: `const f = Function\nreturn f('return this')()`, reached: 'Function' },
  { how: 'a COMPUTED property assembled at runtime', body: `return globalThis['pro' + 'cess'].env.HOME`, reached: 'globalThis' },
  { how: 'a PARENTHESIZED callee', body: `return (require)('node:fs')`, reached: 'require' },
  { how: 'optional chaining', body: `return process?.env?.HOME`, reached: 'process' },
  { how: 'a reach SWALLOWED by its own catch', body: `try { Function('return this')() } catch {}\nreturn { ok: true }`, reached: 'Function' },
]

for (const { how, body, reached } of MECHANISMS) {
  test(`reached by ${how}, the escape is still RECORDED`, async () => {
    const { escapes } = await probe(body)
    assert.ok(
      escapes.some((e) => e.name === reached),
      `${how} was not recorded. Recorded: ${JSON.stringify(escapes.map((e) => e.name))}`,
    )
  })
}

test('a swallowed reach is recorded even though the script returns normally', async () => {
  // The distinguishing property: a probe that only THREW would be defeated by a bare
  // `catch {}`, so escapes are appended before the throw and read afterwards.
  const { escapes, thrown } = await probe(`try { process.env.HOME } catch {}\nreturn { ok: true }`)
  assert.equal(thrown, null, 'the script caught its own escape, as a hostile one would')
  assert.equal(escapes.length, 1, 'and the escape was recorded anyway')
})

// ── 4. ONE CASE PER OUT-OF-CONTRACT BINDING ───────────────────────────────────
//
// Iterated from the model's own list, so this covers bindings nobody has attacked —
// fetch, Buffer, WebAssembly, XMLHttpRequest, module, exports, self, window, frames —
// exactly as it covers the three that were proven.

for (const name of OUT_OF_CONTRACT_GLOBALS) {
  test(`\`${name}\` is out of contract, and reading a property of it is caught`, async () => {
    const { escapes } = await probe(`return ${name}.anything`)
    assert.deepEqual(
      escapes.map((e) => e.name),
      [name],
      `${name} is in the model's shadow list but the probe did not record a reach for it`,
    )
  })

  test(`\`${name}\` is out of contract, and CALLING it is caught`, async () => {
    const { escapes } = await probe(`return ${name}('x')`)
    assert.ok(escapes.some((e) => e.name === name && e.op === 'called as a function'))
  })
}

// ── 5. NEGATIVE CONTROLS ──────────────────────────────────────────────────────
//
// A control that fires on everything is not a control. These say what the probe must NOT
// do, and the last one is the one that matters: the real scripts.

test('a script that uses only the injected globals runs untouched', async () => {
  const compiled = compileWorkflowBody(`log('hello')\nawait agent('do a thing')\nreturn { ok: true }`)
  const result = await compiled.invoke({
    args: {},
    agent: async () => ({ ok: true }),
    workflow: async () => ({ ok: true }),
    phase: () => {},
    log: () => {},
    parallel: async (t = []) => Promise.all(t.map((x) => x())),
    budget: { total: 1, remaining: () => 1 },
  })
  assert.deepEqual(result, { ok: true })
  assert.deepEqual(compiled.escapes, [])
})

test('`typeof` on a shadowed name does NOT trip the probe', async () => {
  // Reading a binding's TYPE touches no trap, so a script's own defensive
  // `typeof x !== 'undefined'` guard keeps working. Without this the probe would break
  // scripts rather than observe them.
  const { escapes, thrown } = await probe(`return typeof process === 'undefined' ? 'absent' : 'present'`)
  assert.equal(thrown, null)
  assert.deepEqual(escapes, [])
})

test('EVERY REAL WORKFLOW SCRIPT reaches only the injected globals', () => {
  // The end-to-end statement, run against the shipped directory rather than a fixture.
  const out = execFileSync(process.execPath, [CHECKER], { encoding: 'utf8' })
  assert.match(out, /reached ONLY the 7 injected globals/, out)
})

// ── 6. THE END-TO-END PROOF ───────────────────────────────────────────────────
//
// The 6.0.10 failure was not "a regex missed something". It was the checker EXITING 0
// while printing an assurance, with a live sentinel returning the process uid on the way
// past. So the proof is the checker's own exit status against that same sentinel.

test('the SENTINEL that returned the uid and $HOME against 6.0.10 now fails the checker', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'capability-'))
  try {
    fs.writeFileSync(
      path.join(dir, 'sentinel.js'),
      "export const meta = { name: 'sentinel', description: 'x' }\n" +
        "const g = Function('return this')()\n" +
        "log(String(g['pro' + 'cess'].getuid()))\n" +
        'return { ok: true }\n',
    )
    let status = 0
    let out = ''
    try {
      out = execFileSync(process.execPath, [CHECKER, dir], { encoding: 'utf8' })
    } catch (err) {
      status = err.status
      out = String(err.stdout || '')
    }
    assert.equal(status, 1, `the checker exited 0 on the sentinel. Output:\n${out}`)
    assert.match(out, /CAPABILITY ESCAPE/, out)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('a clean script still passes the checker — the gate is not simply always red', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'capability-'))
  try {
    fs.writeFileSync(
      path.join(dir, 'clean.js'),
      "export const meta = { name: 'clean', description: 'x' }\n" +
        "log('working')\nconst r = await agent('do a thing')\nreturn { ok: Boolean(r) }\n",
    )
    const out = execFileSync(process.execPath, [CHECKER, dir], { encoding: 'utf8' })
    assert.match(out, /reached ONLY the 7 injected globals/, out)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

// ── 7. THE STATIC SCAN, DERIVED THE SAME WAY ──────────────────────────────────
//
// The scan answers a DIFFERENT question — would the runner refuse to LOAD this file —
// so it is tested separately, and only for what it claims.

const SCAN_CASES = [
  { name: 'Function', src: `const g = Function('return this')()`, why: 'the reach that was proven end to end' },
  { name: 'Function', src: `const g = new (Function)('return this')()`, why: 'a parenthesized callee that the call-position rule missed' },
  { name: 'Function', src: `const f = Function\nconst g = f('return this')()`, why: 'an alias whose binding is still spelled out' },
  { name: 'eval', src: `const g = (0, eval)('this')`, why: 'indirect eval, which compiles in the global scope' },
  { name: 'AsyncFunction / GeneratorFunction', src: `const g = AsyncFunction('return 1')`, why: 'the same intrinsic under another name' },
  { name: '.constructor', src: `const F = (() => {}).constructor`, why: 'the constructor chain to the same intrinsic' },
  { name: 'require()', src: `const fsmod = require?.('node:fs')`, why: 'optional-chaining interposition' },
  { name: 'process', src: `const home = process?.env`, why: 'optional-chaining interposition on a member access' },
]

for (const { name, src, why } of SCAN_CASES) {
  test(`the static scan reports ${name} — ${why}`, () => {
    const found = findForbiddenConstructs(src)
    assert.ok(
      found.some((f) => f.name === name),
      `expected ${name}; found ${JSON.stringify(found.map((f) => f.name))}`,
    )
  })
}

test('a C2 name split by a comment (P1) is still reported', () => {
  const found = findForbiddenConstructs(`const F = ({}).\n  /* a comment */ constructor\n`)
  assert.ok(found.some((f) => f.name === '.constructor'), JSON.stringify(found.map((f) => f.name)))
})

test('a C2 name spelled with an identifier escape (P2) is still reported', () => {
  // §12.7.1 — `eval` and `eval` denote the same binding.
  const found = findForbiddenConstructs(`const g = (0, \\u0065val)('this')`)
  assert.ok(found.some((f) => f.name === 'eval'), JSON.stringify(found.map((f) => f.name)))
})

// ── 8. THE BOUNDARY, ASSERTED ─────────────────────────────────────────────────
//
// The previous header claimed a completeness it did not have, and that claim is what
// made the gap invisible. So the open edges are tests, not prose: if one of them ever
// starts passing, the header is out of date and the suite says so.

test('OPEN, and stated: the static scan does NOT see a parenthesized callee', () => {
  assert.deepEqual(
    findForbiddenConstructs(`const fsmod = (require)('node:fs')`).map((f) => f.name),
    [],
    'the scan now catches this — update WHAT REMAINS OPEN in workflow-runner-constraints.mjs',
  )
})

test('CLOSED by the probe instead: the same parenthesized callee IS caught at runtime', async () => {
  const { escapes } = await probe(`return (require)('node:fs')`)
  assert.ok(escapes.some((e) => e.name === 'require'), 'the open scan edge is not covered by the probe either')
})

test('OPEN, and stated: neither control sees a COMPUTED constructor chain off an intrinsic', async () => {
  // `({}).constructor.constructor` reaches the real Function constructor without naming a
  // shadowed binding. Spelled literally the scan catches it; computed, nothing does.
  const body = `const k = 'const' + 'ructor'\nreturn ({})[k][k]('return 1')()`
  assert.deepEqual(findForbiddenConstructs(body).map((f) => f.name), [])
  const { escapes } = await probe(body)
  assert.deepEqual(
    escapes,
    [],
    'this is now caught — that is good news, and WHAT REMAINS OPEN must be updated to say so',
  )
})

test('OPEN, and stated: top-level `this` in the compiled body IS the global object', async () => {
  // Measured, not assumed. Both models compile the body into a sloppy-mode function, so
  // `this` is the real global object and `this.process` reaches the host. `this` is not a
  // binding, so the probe cannot shadow it; it is far too common in prose for the raw scan
  // to refuse on sight. Whether the REAL runner behaves this way is unverified.
  //
  // This test exists so the hole is learned from the suite. If it starts failing, some
  // control has closed the route and WHAT REMAINS OPEN must be updated to say so.
  const body = `return this === undefined ? 'no-receiver' : typeof this.process`
  const { escapes, thrown } = await probe(body)
  assert.equal(thrown, null)
  assert.deepEqual(escapes, [], 'a control now sees this route — update WHAT REMAINS OPEN')
})

// ── 9. THE ReDoS BOUND, PER PRODUCTION ────────────────────────────────────────
//
// 6.0.10's MultiLineComment was lazy, so it could be extended past its own terminator:
// n adjacent comments admitted 2^(n-1) parses and a 147-byte file took 20.8s while a
// ~250-byte one never finished. The SingleLineComment had the same shape — it could end
// early, and a comment containing another `//` and trailing spaces multiplied the same
// way. Both are pinned now, and the bound is asserted per PRODUCTION so that a new
// separator arriving without a bound fails here.

const REDOS_INPUTS = {
  'WhiteSpace ∪ LineTerminator (§12.2, §12.3)': (n) => ' \n'.repeat(n),
  'MultiLineComment (§12.4)': (n) => '/* */'.repeat(n),
  'SingleLineDelimitedComment (Annex B.1.1)': (n) => '/* x */ '.repeat(n),
  'SingleLineComment (§12.4)': (n) => '//   a   //   b   \n'.repeat(n),
  'SingleLineHTMLOpenComment (Annex B.1.1)': (n) => '<!--   a   \n'.repeat(n),
  'SingleLineHTMLCloseComment (Annex B.1.1)': (n) => '\n-->   a   '.repeat(n),
}

test('every separator production has a ReDoS bound here', () => {
  assert.deepEqual(
    Object.keys(REDOS_INPUTS).sort(),
    Object.keys(SEPARATOR_PRODUCTIONS).sort(),
    'a production added without a ReDoS bound is an untested claim',
  )
})

for (const [production, build] of Object.entries(REDOS_INPUTS)) {
  test(`${production} — a pathological run of it scans in LINEAR time`, () => {
    // 400 repetitions is far past the 2^n cliff the 6.0.10 patterns fell off at n≈28.
    // Both anchors matter: `.` and `import` are the tokens whose rules span a separator.
    const src = `const x = .${build(400)}\nimport${build(400)}\n`
    const started = Date.now()
    findForbiddenConstructs(src)
    const ms = Date.now() - started
    assert.ok(ms < 2000, `${src.length} bytes took ${ms}ms — this pattern backtracks super-linearly`)
  })
}

test('the checker scans every real workflow script in well under a second each', () => {
  for (const file of fs.readdirSync(WORKFLOWS).filter((f) => f.endsWith('.js'))) {
    const raw = fs.readFileSync(path.join(WORKFLOWS, file), 'utf8')
    const started = Date.now()
    findForbiddenConstructs(raw)
    const ms = Date.now() - started
    assert.ok(ms < 1000, `${file} (${raw.length} bytes) took ${ms}ms`)
  }
})

// ── 10. THE HARNESS CARRIES THE SAME CONTROL ──────────────────────────────────
//
// A harness laxer than the checker is precisely the gap that shipped 6.0.6. The list is
// shared; so is the probe.

test('the unit-test HARNESS refuses a capability escape too', async () => {
  const { runWorkflowScript } = await import('./helpers/run-workflow.mjs')
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'capability-harness-'))
  try {
    const probeFile = path.join(dir, 'probe.js')
    // Written so the STATIC scan cannot see it: the capability is reached through a
    // parenthesized callee, which the model states the scan does not close. If the
    // harness only had the scan, this would run.
    fs.writeFileSync(
      probeFile,
      "export const meta = { name: 'probe', description: 'x' }\n" +
        "const loader = (require)\n" +
        "const fsmod = loader('node:fs')\n" +
        'return { ok: Boolean(fsmod) }\n',
    )
    await assert.rejects(
      () => runWorkflowScript(probeFile, { args: {} }),
      /CAPABILITY ESCAPE/,
      'a harness that lets a script reach the global object makes every test against it meaningless',
    )
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
})

test('createCapabilityProbe hands back aligned names and values', () => {
  const p = createCapabilityProbe()
  assert.equal(p.names.length, p.values.length)
  assert.deepEqual(p.names, [...OUT_OF_CONTRACT_GLOBALS])
  assert.deepEqual(p.escapes, [])
})
