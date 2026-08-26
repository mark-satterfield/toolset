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
import { findForbiddenConstructs } from './workflow-runner-constraints.mjs'

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

// ── Pass 2: EXECUTION SMOKE ────────────────────────────────────────────────────
//
// Parsing is not enough, and the gap is not theoretical. `node --check` asks V8 to
// PARSE; it never resolves identifiers, so a free variable is valid syntax and always
// will be. task-to-deploy.js read an undeclared `spec` at two places, died with
// `ReferenceError: spec is not defined` at Gate 1 for EVERY caller shape, and this
// checker reported it as passing through two shipped releases.
//
// So each script is also EXECUTED, once, with the same six injected globals the runtime
// supplies and with dispatchers that return null. Nothing reaches a network, an agent,
// or a filesystem: `agent` and `workflow` are stubs, and a workflow script has no fs and
// no child_process to reach for. A ReferenceError is a FAILURE; anything else is not,
// because a script legitimately bails on a null dispatch.
//
// NOTE the standing limitation, which is what pass 3 exists for: an AsyncFunction body is
// strictly MORE PERMISSIVE than the real runner. Constructs the runner refuses statically
// are perfectly legal in here, so this pass can execute a script the runner would not even
// load. Never treat a green pass 2 as evidence that the runner will accept the file.
//
// This is dynamic, so it covers executed paths only — the happy path plus whatever
// branches the stubs steer into. That is enough for this defect class, which lives in
// the contract-construction code every run touches on its way to the first gate.
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

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

const refErrors = []
let executed = 0
for (const file of readdirSync(dir).filter((f) => f.endsWith('.js')).sort()) {
  const src = readFileSync(path.join(dir, file), 'utf8').replace(/^export\s+const\s+meta\s*=/m, 'const meta =')
  let fn
  try {
    fn = new AsyncFunction('args', 'agent', 'workflow', 'phase', 'log', 'parallel', src)
  } catch {
    continue // a parse failure is already reported by pass 1
  }
  executed++
  try {
    await Promise.race([
      fn(
        SMOKE_ARGS,
        async () => SMOKE_RETURN,
        async () => SMOKE_RETURN,
        () => {},
        () => {},
        async (thunks = []) => {
          const out = []
          for (const t of thunks) out.push(await t())
          return out
        },
      ),
      new Promise((_, reject) => setTimeout(() => reject(new Error('smoke execution timed out after 5s')), 5000).unref()),
    ])
  } catch (err) {
    // ONLY an unresolved identifier is a defect here. A TypeError from a null dispatch
    // is the stub's doing, not the script's, and failing on it would make this check
    // unusable noise.
    if (err instanceof ReferenceError) refErrors.push({ file, error: `${err.name}: ${err.message}` })
  }
}

for (const { file, error } of refErrors) console.log(`FAIL  ${file}  —  ${error}`)
console.log(
  refErrors.length
    ? `\n${refErrors.length} of ${executed} workflow scripts reference an UNDECLARED identifier`
    : `all ${executed} workflow scripts execute without an undeclared identifier`
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
    : `all ${checked} workflow scripts are free of constructs the runner refuses`,
)

process.exit(failures.length || refErrors.length || strictness.length ? 1 : 0)
