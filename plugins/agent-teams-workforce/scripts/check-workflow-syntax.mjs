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
process.exit(failures.length ? 1 : 0)
