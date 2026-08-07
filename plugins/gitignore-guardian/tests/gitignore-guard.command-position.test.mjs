// ssbd-1xcs D2 — dead cd-honoring branch (gitignore-guard.sh).
// Encodes acceptance criteria D2-AC1 .. D2-AC7 (numbered AC7-AC13 in the bead).
//
// Defect under test: the anchored matcher at gitignore-guard.sh:27
// (`grep -qE '^\s*git\s+add\b'`) exits 0 for any compound `cd <repo> && git add
// <file>` form, so the WORKDIR logic added at lines 47-52 is unreachable in every
// case it was written for. The FILES extractor at line 36 is anchored the same
// way, so a de-anchored matcher alone would emit the tokens `cd`, `<repo>`, `&&`,
// `git`, `add` as bogus "ignored file" entries — both must change together
// (AC9 pins the extractor; AC12 pins command-position discipline).
//
// Layer: component/subprocess. The subject is a bash hook whose contract is
// process exit status + stderr text + `cd` side effects + real `git check-ignore`
// / `git ls-files` results — it cannot be unit-tested in-process. Each test
// builds throwaway git repos in an ephemeral tmpdir (TEST_TMPDIR overridable),
// pipes a crafted PreToolUse JSON payload to the hook, and asserts exit status
// and exact stderr lines. Git is isolated from user/system config so global
// excludes cannot skew check-ignore results.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, realpathSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HOOK = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..', 'hooks', 'gitignore-guard.sh'
)
const TMP_BASE = process.env.TEST_TMPDIR || os.tmpdir()

// Hermetic git: no user/system config (global core.excludesFile must not leak in).
const GIT_ENV = {
  ...process.env,
  GIT_CONFIG_GLOBAL: '/dev/null',
  GIT_CONFIG_SYSTEM: '/dev/null',
}

function sh(cmd, cmdArgs, cwd) {
  const r = spawnSync(cmd, cmdArgs, { cwd, encoding: 'utf8', env: GIT_ENV })
  if (r.status !== 0) {
    throw new Error(`fixture setup failed: ${cmd} ${cmdArgs.join(' ')} in ${cwd}\n${r.stderr}`)
  }
  return r
}

/**
 * Build a throwaway git repo.
 * @param {string} dir absolute path (created)
 * @param {object} spec { gitignore, files: {relPath: content}, tracked: [], forceTracked: [] }
 * @returns {string} realpath of the repo
 */
function makeRepo(dir, { gitignore = '', files = {}, tracked = [], forceTracked = [] } = {}) {
  mkdirSync(dir, { recursive: true })
  sh('git', ['init', '-q'], dir)
  sh('git', ['config', 'user.email', 'test@example.invalid'], dir)
  sh('git', ['config', 'user.name', 'ssbd-1xcs fixture'], dir)
  writeFileSync(path.join(dir, '.gitignore'), gitignore)
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true })
    writeFileSync(path.join(dir, rel), content)
  }
  sh('git', ['add', '.gitignore'], dir)
  for (const rel of tracked) sh('git', ['add', rel], dir)
  for (const rel of forceTracked) sh('git', ['add', '-f', rel], dir)
  sh('git', ['commit', '-q', '-m', 'fixture'], dir)
  return realpathSync(dir)
}

/** Run the hook exactly as Claude Code would: JSON payload on stdin, session cwd. */
function runHook(command, cwd) {
  return spawnSync('bash', [HOOK], {
    cwd,
    input: JSON.stringify({ tool_input: { command } }),
    encoding: 'utf8',
    env: GIT_ENV,
  })
}

/** stderr lines that the hook reports as blocked-file entries. */
function reportedEntries(stderr) {
  return stderr.split('\n').filter((l) => l.startsWith('  - '))
}

async function withFixture(name, fn) {
  const base = mkdtempSync(path.join(TMP_BASE, `gg-${name}-`))
  try {
    return await fn(base)
  } finally {
    rmSync(base, { recursive: true, force: true })
  }
}

// ─── D2-AC1 (AC7) — compound && form reaches the WORKDIR logic ────────────────
test('D2-AC1: `cd <repo> && git add <ignored-file>` is blocked with exit 2, evaluated in the TARGET repo', () =>
  withFixture('ac7', (base) => {
    // Session repo has NO rule matching build/ — a block can only come from the target repo.
    const session = makeRepo(path.join(base, 'session-repo'), { gitignore: 'node_modules/\n' })
    const target = makeRepo(path.join(base, 'other-repo'), {
      gitignore: 'build/\n',
      files: { 'build/output.js': 'compiled\n' }, // untracked
    })

    const r = runHook(`cd ${target} && git add build/output.js`, session)

    assert.equal(
      r.status, 2,
      `hook must exit 2 for the compound && form — the anchored matcher at line 27 currently exits 0 without ever reaching the WORKDIR logic. stderr: ${JSON.stringify(r.stderr)}`
    )
    assert.match(r.stderr, /BLOCKED/, 'stderr must contain BLOCKED')
    assert.ok(
      r.stderr.includes('  - build/output.js'),
      `stderr must report the ignored file line '  - build/output.js'; got: ${JSON.stringify(r.stderr)}`
    )
  }))

// ─── D2-AC2 (AC8) — cross-repo false positive is not reintroduced ─────────────
test('D2-AC2: `cd <service-repo> && git add apps/web/package.json` (tracked there, ignored only in the session repo) is allowed', () =>
  withFixture('ac8', (base) => {
    // The original bug this repair targeted: session repo carries a bare `package.json`
    // rule; the file is tracked in the target repo and matches no rule there.
    const session = makeRepo(path.join(base, 'session-repo'), { gitignore: 'package.json\n' })
    const target = makeRepo(path.join(base, 'service-repo'), {
      gitignore: 'node_modules/\n',
      files: { 'apps/web/package.json': '{ "name": "web" }\n' },
      tracked: ['apps/web/package.json'],
    })

    const r = runHook(`cd ${target} && git add apps/web/package.json`, session)

    assert.equal(r.status, 0, `hook must exit 0; stderr: ${JSON.stringify(r.stderr)}`)
    assert.equal(r.stderr, '', 'hook must write nothing to stderr')
  }))

// ─── D2-AC3 (AC9) — FILES extraction is de-anchored consistently ──────────────
test('D2-AC3: the BLOCKED report for the compound form lists exactly one real path — no cd/repo/&&/git/add tokens', () =>
  withFixture('ac9', (base) => {
    const session = makeRepo(path.join(base, 'session-repo'), { gitignore: 'node_modules/\n' })
    const target = makeRepo(path.join(base, 'other-repo'), {
      gitignore: 'secrets/\n',
      files: { 'secrets/key.pem': 'PEM\n' }, // untracked
    })

    const r = runHook(`cd ${target} && git add secrets/key.pem`, session)

    assert.equal(r.status, 2, `hook must exit 2; stderr: ${JSON.stringify(r.stderr)}`)
    const entries = reportedEntries(r.stderr)
    assert.deepEqual(
      entries,
      ['  - secrets/key.pem'],
      `stderr must list exactly one entry, '  - secrets/key.pem' — a de-anchored matcher with the old anchored sed extractor would emit 'cd', '${target}', '&&', 'git', 'add' as bogus entries. Got: ${JSON.stringify(entries)}`
    )
    for (const token of ['cd', target, '&&', 'git', 'add']) {
      assert.ok(
        !entries.includes(`  - ${token}`),
        `'${token}' must not appear as a reported file entry`
      )
    }
  }))

// ─── D2-AC4 (AC10) — bare form regression ─────────────────────────────────────
test('D2-AC4: bare `git add <ignored-file>` in the session repo is still blocked with exit 2', () =>
  withFixture('ac10', (base) => {
    const session = makeRepo(path.join(base, 'session-repo'), {
      gitignore: '.auto-claude/\n',
      files: { '.auto-claude/state.json': '{}\n' }, // untracked
    })

    const r = runHook('git add .auto-claude/state.json', session)

    assert.equal(r.status, 2, `bare-form blocking must be unchanged by the de-anchoring; stderr: ${JSON.stringify(r.stderr)}`)
    assert.ok(
      r.stderr.includes('  - .auto-claude/state.json'),
      `stderr must report '  - .auto-claude/state.json'; got: ${JSON.stringify(r.stderr)}`
    )
  }))

// ─── D2-AC5 (AC11) — tracked-file skip regression ─────────────────────────────
test('D2-AC5: `git add` of a TRACKED file that pattern-matches an ignore rule is still allowed', () =>
  withFixture('ac11', (base) => {
    const session = makeRepo(path.join(base, 'session-repo'), {
      gitignore: 'src/config.py\n',
      files: { 'src/config.py': 'x = 1\n' },
      forceTracked: ['src/config.py'],
    })

    const r = runHook('git add src/config.py', session)

    assert.equal(r.status, 0, `tracked-file skip must be unchanged; stderr: ${JSON.stringify(r.stderr)}`)
    assert.equal(r.stderr, '', 'hook must write nothing to stderr')
  }))

// ─── D2-AC6 (AC12) — de-anchoring does not over-match ─────────────────────────
test("D2-AC6: a 'git add' occurrence that is NOT in command position is not treated as a git add invocation", () =>
  withFixture('ac12', (base) => {
    const session = makeRepo(path.join(base, 'session-repo'), { gitignore: '.auto-claude/\n' })

    const r = runHook('echo "remember to git add the file" >> notes.txt', session)

    assert.equal(
      r.status, 0,
      `'git add' inside an echo argument is not a git add invocation — the de-anchored matcher must only match command position (start of string, or after &&, ||, ;, or a newline). stderr: ${JSON.stringify(r.stderr)}`
    )
    assert.equal(r.stderr, '', 'hook must write nothing to stderr')
  }))

// ─── D2-AC7 (AC13) — semicolon separator behaves like && ──────────────────────
test('D2-AC7: `cd <repo>; git add <ignored-file>` (semicolon separator) is blocked identically to the && form', () =>
  withFixture('ac13', (base) => {
    const session = makeRepo(path.join(base, 'session-repo'), { gitignore: 'node_modules/\n' })
    const target = makeRepo(path.join(base, 'other-repo'), {
      gitignore: 'ignored/\n',
      files: { 'ignored/a.txt': 'a\n' }, // untracked
    })

    const r = runHook(`cd ${target}; git add ignored/a.txt`, session)

    assert.equal(r.status, 2, `semicolon form must block like the && form; stderr: ${JSON.stringify(r.stderr)}`)
    assert.ok(
      r.stderr.includes('  - ignored/a.txt'),
      `stderr must report '  - ignored/a.txt'; got: ${JSON.stringify(r.stderr)}`
    )
  }))
