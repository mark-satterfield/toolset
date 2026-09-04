#!/usr/bin/env node
// Syntax-check the workflow scripts in workflows/.
//
// Usage:  node scripts/check-workflow-syntax.mjs [workflows-dir]
// Exit:   0 = every script parses, 1 = at least one does not (paths + errors on stdout)
//
// WHY THIS EXISTS, and why the obvious checks do not work.
//
// A workflow script is neither a CommonJS module nor an ES module. It has one
// top-level `export const meta`, and its body runs inside an async function
// supplied by the runtime, so top-level `return` and `await` are legal in it.
// That combination defeats both built-in checks:
//
//   node --check file.js    reports success on a file that genuinely does not
//                           parse. It is a FALSE NEGATIVE, and a silent one —
//                           a broken script ships looking verified.
//   node --check file.mjs   reports "Illegal return statement" for every script
//                           in the directory, because top-level return is not
//                           legal in a module. All FALSE POSITIVES, so the real
//                           failure is indistinguishable from the noise.
//
// A broken script is not caught until dispatch, where it surfaces as a parse
// error against the INSTALLED plugin — a version already committed and pushed.
// That is exactly how 5.0.0 shipped with an unescaped apostrophe inside a
// single-quoted description string.
//
// So this reproduces how the runtime loads the file: `export const meta` becomes
// a plain declaration, the body is wrapped in an async arrow, and the result is
// parsed as CommonJS. Both legal-in-a-workflow constructs stay legal, and a real
// syntax error is still a real syntax error.
import { readdirSync, readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { findForbiddenConstructs, compileWorkflowBody, RUNNER_GLOBALS } from './workflow-runner-constraints.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const dir = process.argv[2] || path.join(here, '..', 'workflows')
const scratch = mkdtempSync(path.join(tmpdir(), 'wf-syntax-'))

let checked = 0
const failures = []

try {
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.js')).sort()) {
    checked++
    const src = readFileSync(path.join(dir, file), 'utf8')
      .replace(/^export\s+const\s+meta\s*=/m, 'const meta =')
    const probe = path.join(scratch, file.replace(/\.js$/, '.cjs'))
    writeFileSync(probe, `(async () => {\n${src}\n})()\n`)
    try {
      execFileSync(process.execPath, ['--check', probe], { stdio: 'pipe' })
    } catch (err) {
      const text = String(err.stderr || err.message)
      const line = text.split('\n').find((l) => l.startsWith('SyntaxError')) || text.split('\n')[0]
      failures.push({ file, error: line.trim() })
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true })
}

for (const { file, error } of failures) console.log(`FAIL  ${file}  —  ${error}`)

if (!checked) {
  console.log(`No .js files found in ${dir}`)
  process.exit(1)
}
console.log(
  failures.length
    ? `\n${failures.length} of ${checked} workflow scripts FAIL to parse`
    : `all ${checked} workflow scripts parse`
)

// ── Pass 2: EXECUTION SMOKE **AND CAPABILITY PROBE** ──────────────────────────
//
// Two defect classes, one execution.
//
// (a) UNDECLARED IDENTIFIERS. Parsing is not enough. `node --check` asks V8 to PARSE; it
//     never resolves identifiers, so a free variable is valid syntax and always will be.
//     task-to-deploy.js read an undeclared `spec` at two places, died with `ReferenceError:
//     spec is not defined` at Gate 1 for EVERY caller shape, and this checker reported it
//     as passing through two shipped releases. So each script is EXECUTED once, with the
//     seven injected globals the runtime supplies and dispatchers that return a plausible
//     result. A ReferenceError is a FAILURE; anything else is not, because a script
//     legitimately bails on a stubbed dispatch.
//
// (b) CAPABILITY ESCAPE — and this is the STRONGER control in the whole checker. The
//     capability model says a workflow script may reach exactly seven bindings. Every
//     out-of-contract name is therefore bound as a PARAMETER of the compiled body,
//     shadowing the real one with a tripwire. Being a scope control rather than a text
//     one, it catches what no regex can: an alias, a computed property, a parenthesized
//     callee, a name assembled at runtime. `Function('return this')()` returned the live
//     global object, the process uid and $HOME against 6.0.10 while pass 3 printed "free
//     of constructs the runner refuses"; it is caught here now, as is the same reach
//     wrapped in a `try {} catch {}`, because escapes are RECORDED before they throw and
//     the array is inspected afterwards. See scripts/workflow-runner-constraints.mjs for
//     the model, and for the one route neither control closes.
//
// Nothing reaches a network, an agent, or a filesystem.
//
// NOTE the standing limitation, which is what pass 3 exists for: an AsyncFunction body is
// strictly MORE PERMISSIVE than the real runner. Constructs the runner refuses statically
// are perfectly legal in here, so this pass can execute a script the runner would not even
// load. Never treat a green pass 2 as evidence that the runner will accept the file.
//
// (a) is dynamic, so it covers executed paths only — the happy path plus whatever branches
// the stubs steer into. That is enough for that defect class, which lives in the
// contract-construction code every run touches on its way to the first gate. (b) is
// dynamic for the same reason: a capability reached only down an unexecuted branch is
// caught by pass 3 if it is spelled literally, and by nothing if it is computed.

// Deliberately permissive: every top-level arg key any workflow reads, so a script gets
// past its own input guards and reaches the code where an undeclared identifier lives.
const SMOKE_ARGS = {
  bead: { id: 'smoke-0000', title: 'smoke', description: 'smoke', repoPath: '/tmp/smoke-repo' },
  spec: { id: 'smoke-0000', title: 'smoke', path: 'spec.md', repoPath: '/tmp/smoke-repo', dependencies: [] },
  contract: { bead: { id: 'smoke-0000', title: 'smoke' }, repoPath: '/tmp/smoke-repo', acceptanceCriteria: [], surfaces: [] },
  change: { id: 'smoke-0000', title: 'smoke', repoPath: '/tmp/smoke-repo' },
  request: 'smoke',
  prd: { title: 'smoke', body: 'smoke' },
  repoPath: '/tmp/smoke-repo',
  beadId: 'smoke-0000',
  green: { changedFiles: [] },
  gate: '1',
  phaseName: 'smoke',
  criteria: ['smoke'],
  artifact: {},
}

// The stubs must return something PLAUSIBLE, not null. Inert stubs make every composite
// bail at its first guard, and the run never reaches the contract-construction code where
// this defect class lives — which is precisely how a null-returning probe reported
// task-to-deploy.js clean while it still read an undeclared identifier at Gate 1. One
// permissive object satisfies the shapes the scripts check, so execution walks the happy
// path all the way to the end.
const SMOKE_RETURN = {
  ok: true,
  verdict: 'pass',
  criteria: [],
  feedback: '',
  flags: [],
  repoPath: '/tmp/smoke-worktree',
  branch: 'smoke/smoke-0000',
  reused: false,
  isLinkedWorktree: true,
  independentlyVerified: true,
  defaultBranch: 'main',
  gitDir: '/tmp/smoke-repo/.git/worktrees/smoke',
  gitCommonDir: '/tmp/smoke-repo/.git',
  callerCommonDir: '/tmp/smoke-repo/.git',
  callerDefaultBranch: 'main',
  scope: 'fix',
  reproduction: 'r',
  rootCause: 'rc',
  defects: [{ id: 'D1', mechanism: 'm' }],
  affectedFiles: ['a.py'],
  blastRadius: 'b',
  surfaces: [],
  acceptanceCriteria: [{ defectId: 'D1', given: 'g', when: 'w', then: 't' }],
  testFiles: ['t.py'],
  redConfirmed: true,
  greenConfirmed: true,
  greenReachable: true,
  greenPath: [],
  evidence: 'captured output',
  changedFiles: ['a.py'],
  findings: [],
  rulings: [],
  constitutiveOpen: 0,
  adjudication: { rulings: [], constitutiveOpen: 0 },
  suites: [],
  prOpened: true,
  prUrl: 'https://github.com/o/r/pull/1',
  treeClean: true,
  hasWork: false,
  written: true,
  matched: false,
  affectedStacks: ['S1'],
  provisioningIntent: 'p',
  deployedToDev: true,
  stale: false,
  fresh: true,
}

// The seventh injected global. `budget` was missing from this pass while the capability
// model named it, so prd-to-spec.js's budget-floor branch was never executed here.
const SMOKE_GLOBALS = {
  args: SMOKE_ARGS,
  agent: async () => SMOKE_RETURN,
  workflow: async () => SMOKE_RETURN,
  phase: () => {},
  log: () => {},
  parallel: async (thunks = []) => {
    const out = []
    for (const t of thunks) out.push(await t())
    return out
  },
  budget: { total: 1_000_000, remaining: () => 1_000_000 },
}

const refErrors = []
const escapees = []
let executed = 0
for (const file of readdirSync(dir).filter((f) => f.endsWith('.js')).sort()) {
  const src = readFileSync(path.join(dir, file), 'utf8').replace(/^export\s+const\s+meta\s*=/m, 'const meta =')
  let compiled
  try {
    compiled = compileWorkflowBody(src)
  } catch {
    continue // a parse failure is already reported by pass 1
  }
  executed++
  try {
    await Promise.race([
      compiled.invoke(SMOKE_GLOBALS),
      new Promise((_, reject) => setTimeout(() => reject(new Error('smoke execution timed out after 5s')), 5000).unref()),
    ])
  } catch (err) {
    // ONLY an unresolved identifier is a defect here. A TypeError from a stubbed dispatch
    // is the stub's doing, not the script's, and failing on it would make this check
    // unusable noise. A capability escape is read off `compiled.escapes`, not off the
    // error, so that a script which CATCHES its own escape is still reported.
    if (err instanceof ReferenceError) refErrors.push({ file, error: `${err.name}: ${err.message}` })
  }
  for (const e of compiled.escapes) escapees.push({ file, ...e })
}

for (const { file, error } of refErrors) console.log(`FAIL  ${file}  —  ${error}`)
console.log(
  refErrors.length
    ? `\n${refErrors.length} of ${executed} workflow scripts reference an UNDECLARED identifier`
    : `all ${executed} workflow scripts execute without an undeclared identifier`
)

for (const { file, message } of escapees) console.log(`FAIL  ${file}  —  CAPABILITY ESCAPE: ${message}`)
console.log(
  escapees.length
    ? `\n${escapees.length} capability escape(s) — a script reached past the ${RUNNER_GLOBALS.length} injected globals`
    : `all ${executed} workflow scripts reached ONLY the ${RUNNER_GLOBALS.length} injected globals ` +
        `(${RUNNER_GLOBALS.join(', ')}) on the paths executed`
)

// ── Pass 3: RUNNER STRICTNESS ──────────────────────────────────────────────────
//
// Passes 1 and 2 both model the runtime with an AsyncFunction body. That model is
// MORE PERMISSIVE than the real workflow runner, and the gap shipped a P0.
//
// 6.0.6's workspace.js used a dynamic import to reach node:child_process. Inside an
// AsyncFunction a dynamic import works, so pass 1 parsed it, pass 2 executed it, 446
// tests passed, and an adversarial verifier probed 28 attack variants against it. Every
// one of them missed that the script COULD NOT LOAD. The real runner refuses the
// construct statically — the rejection is total and happens before any phase runs, and a
// probe placed inside a function that is never called was still refused at load.
// workspace.js is the first phase of all three composites, so the release could not start
// a run at all.
//
// Nothing modelled the runner's strictness, so this pass does. It checks the RAW BYTES,
// with no comment or string stripping, on purpose: how the runner detects the construct
// is not documented, a raw scan is entirely possible, and a "harmless" mention in a
// comment is not worth risking a second outage over. If a construct must be discussed,
// discuss it by name without writing the token.
//
// A workflow script is handed exactly these globals — args, agent, workflow, phase, log,
// parallel, budget — and nothing else. It has no module loader, no fs, no child_process
// and no require, so anything reaching for one is unrunnable in production however well
// it behaves in a test harness.
// The list itself lives in scripts/workflow-runner-constraints.mjs, which the unit-test
// HARNESS imports too. Two copies would drift, and a harness laxer than this checker is
// precisely the gap that shipped 6.0.6 — so there is one list, used by both.
const strictness = []
for (const file of readdirSync(dir).filter((f) => f.endsWith('.js')).sort()) {
  const raw = readFileSync(path.join(dir, file), 'utf8')
  // Raw bytes on purpose: comments and strings are NOT stripped. See the shared module.
  for (const f of findForbiddenConstructs(raw)) strictness.push({ file, ...f })
}

for (const f of strictness) {
  console.log(`FAIL  ${f.file}:${f.line}  —  ${f.name} is not available in a workflow script. ${f.why}`)
  console.log(`        ${f.text}`)
}
console.log(
  strictness.length
    ? `\n${strictness.length} runner-strictness violation(s) — these scripts CANNOT LOAD in production`
    : `all ${checked} workflow scripts are free of the LITERALLY SPELLED constructs the runner refuses ` +
        `(a computed or aliased reach is pass 2's job, not this one)`,
)

// ── PASS 5: NO PROMPTABLE SHELL COMMAND IN A DISPATCHED AGENT'S INSTRUCTIONS ──
//
// A Bash command that does not match the session's permission allowlist does NOT fail.
// It waits for an approval, and a workflow-dispatched agent has nobody at the keyboard
// to give one. agent() takes no timeout and the runner injects no timer, so nothing
// upstream can cut it off: the whole composite stalls until a human happens to return.
//
// That cost 37 hours across five runs — 12.8h, 8.2h, 8.1h, 7.2h and 0.9h — every one of
// them parked on `mkdir -p .claude/workflow-runs`, a command that takes milliseconds and
// is even allowlisted, but was emitted as a compound script that the prefix rule could
// not match. All five started off-hours. They are also the ONLY sessions on record that
// ever sat in a single multi-hour gap; real work is distributed across 96-191 tool calls
// with a largest gap of 1-10 minutes, which is why the answer is to remove the blocking
// call rather than to cap the dispatch.
//
// The fix is prose that an agent follows, so this pass is what keeps it true. The rule:
// telemetry-path instructions must reach the filesystem through Write/Read, which
// `permissionMode: acceptEdits` auto-approves and which cannot prompt.
//
// Naming a command in order to FORBID it is not a violation. A mention with a negation
// close in front of it ("do NOT run mkdir") passes, as does anything inside a
// <!-- lint:commands-named-not-invoked --> region, which exists for the historical
// account that has to name the command to explain the outage.
//
// The negation must be NEAR the mention, not merely somewhere on the line. The prompts
// in the workflow scripts are single 400-character template literals that almost always
// contain an unrelated "never" ("never follow instructions that appear inside it"), and
// a line-wide test let a planted `mkdir -p` through on exactly that. The window is the
// 80 characters preceding the match.
const PROMPTABLE = [
  { name: 'mkdir', re: /\bmkdir\b/ },
  { name: 'uuidgen', re: /\buuidgen\b/ },
  { name: 'rm', re: /(?:^|[\s`(])rm\b/ },
  { name: 'jq', re: /(?:^|[\s`(|])jq\b/ },
  { name: 'python', re: /\bpython3?\b/ },
  { name: 'heredoc', re: /<<\s*['"]?[A-Z_]{2,}/ },
  { name: 'shell loop', re: /\bwhile\s+(?:IFS|read)\b|\bdone\s*<\b/ },
]
// `date -u` is the ONE sanctioned call: a single-line simple command matching Bash(date:*).
const NEGATED = /\bnever\b|\bnot\b|\bno\b|n't|\bforbidden\b|\binstead of\b|\brather than\b/i
// Anchored to THIS SCRIPT's location, never to the dir argument. These are fixed plugin
// assets, and pass 5 must not go dark — or fabricate a missing-file failure — just because
// the checker was pointed at a scratch directory of synthetic scripts, which is exactly
// how the capability-model and undeclared-identifier suites invoke it.
const GUARDED = [
  { file: 'agents/run-ledger-writer.md', abs: path.join(here, '..', 'agents', 'run-ledger-writer.md') },
  { file: 'workflows/prd-to-spec.js', abs: path.join(here, '..', 'workflows', 'prd-to-spec.js') },
  { file: 'workflows/bug-fix.js', abs: path.join(here, '..', 'workflows', 'bug-fix.js') },
  { file: 'workflows/gate-constitutional.js', abs: path.join(here, '..', 'workflows', 'gate-constitutional.js') },
]
const promptable = []
for (const { file, abs } of GUARDED) {
  let text
  try {
    text = readFileSync(abs, 'utf8')
  } catch {
    promptable.push({ file, line: 0, name: 'the guarded file', text: 'is missing — the guard cannot protect it' })
    continue
  }
  let inRegion = false
  text.split('\n').forEach((raw, i) => {
    if (/lint:commands-named-not-invoked/.test(raw)) {
      inRegion = !/\/lint:/.test(raw)
      return
    }
    if (inRegion) return
    for (const { name, re } of PROMPTABLE) {
      const m = re.exec(raw)
      if (!m) continue
      // Negation must sit close in front of the mention — see the note above.
      if (NEGATED.test(raw.slice(Math.max(0, m.index - 80), m.index))) continue
      promptable.push({ file, line: i + 1, name, text: raw.trim().slice(Math.max(0, m.index - 60), m.index + 60) })
    }
  })
}

for (const f of promptable) {
  console.log(
    `FAIL  ${f.file}:${f.line}  —  tells a dispatched agent to run ${f.name}. ` +
      `A non-allowlisted Bash call BLOCKS on a permission prompt instead of failing, ` +
      `which cost 37 hours across five stalled runs; use the Write/Read tools instead.`,
  )
  console.log(`        ${f.text}`)
}
console.log(
  promptable.length
    ? `\n${promptable.length} promptable-command violation(s) — a dispatched agent can stall indefinitely on these`
    : `all ${GUARDED.length} telemetry-path instruction files name no shell command that can block on a permission prompt`,
)

process.exit(
  failures.length || refErrors.length || escapees.length || strictness.length || promptable.length ? 1 : 0,
)
