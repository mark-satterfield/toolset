// What the REAL workflow runner refuses — in ONE place.
//
// A workflow script is not a module and not a CommonJS file. The runner hands it
// exactly these globals and nothing else:
//
//     args, agent, workflow, phase, log, parallel, budget
//
// There is no module loader, no filesystem, no process object and no way to spawn
// anything. A script that reaches for one of those is unrunnable in production no
// matter how well it behaves in a test harness.
//
// WHY THIS FILE IS SHARED, AND WHY THAT MATTERS
//
// 6.0.6 shipped a workspace.js that could not load. Both of the things that were
// supposed to catch it — the syntax checker and the unit-test harness — model the
// runtime with an AsyncFunction body, and an AsyncFunction is strictly MORE
// PERMISSIVE than the runner. The construct the runner refuses statically is
// perfectly legal inside one. So 446 tests passed, an adversarial verifier probed 28
// variants, and nothing noticed that the first phase of all three composites was
// unloadable.
//
// The fix is only worth anything if BOTH models get stricter, and they only stay
// in step if there is one list rather than two copies that drift. This is that list:
// scripts/check-workflow-syntax.mjs and tests/workflows/helpers/run-workflow.mjs
// both import it, so a construct added here is refused by both at once.
//
// THE SCAN IS OVER THE WHOLE RAW SOURCE — and 6.0.7 proved why that wording has to be
// exact. The scan has always been raw (no comment or string stripping) but until 6.0.8
// it ran LINE BY LINE: every rule was tested against each line in isolation. A construct
// split across a newline therefore matched nothing, because no single line contained all
// of it. A dynamic import written as the token, a newline, then its parenthesis is a
// perfectly valid ImportCall that the runner WOULD refuse, and the checker printed
// "free of constructs the runner refuses" over it. The same evasion worked for the
// CommonJS loader, for runtime code generation, and for a member access on the process
// object. Both the checker and the test harness consume this one function, so both were
// bypassed by the same three-character edit.
//
// So each rule is now matched against the ENTIRE source text in one piece, and the line
// number is DERIVED from the match index for reporting. Every rule that has a token and
// a following parenthesis or dot allows arbitrary whitespace — newlines included —
// between them, because the parser does.
//
// Comments and strings are still NOT stripped, on purpose. How the runner detects a
// dynamic import is not documented, so a raw scan on its side is entirely possible, and
// a "harmless" mention inside a comment is not worth risking a repeat outage over.
// Discuss a forbidden construct by name; do not write the token.

/** The globals the runner injects. Everything else is unavailable. */
export const RUNNER_GLOBALS = Object.freeze(['args', 'agent', 'workflow', 'phase', 'log', 'parallel', 'budget'])

/**
 * Constructs the runner refuses. Each is matched against the WHOLE raw source text,
 * never line by line — see the header. Where a rule joins a token to a parenthesis or
 * a dot it must span `\s` (which includes newlines), or a one-newline edit evades it.
 */
export const FORBIDDEN_CONSTRUCTS = Object.freeze([
  {
    re: /\bimport\s*\(/,
    name: 'dynamic import',
    why:
      'the runner refuses it STATICALLY — one occurrence anywhere in the file, even inside a ' +
      'function that is never called, makes the whole script unloadable. This is the 6.0.6 P0.',
  },
  { re: /^[^\S\n]*import\s+[\w{*]/m, name: 'import statement', why: 'a workflow script is a script body, not a module.' },
  { re: /\brequire\s*\(/, name: 'require()', why: 'there is no CommonJS loader in the runner.' },
  { re: /\brequire\s*\.\s*resolve\b/, name: 'require.resolve', why: 'there is no module resolution in the runner.' },
  { re: /\bnew\s+Function\s*\(/, name: 'new Function', why: 'code generated at runtime escapes every check that guards this directory.' },
  { re: /\bprocess\s*\./, name: 'process', why: 'the runner injects no process object.' },
  { re: /\b(?:child_process|node:child_process)\b/, name: 'child_process', why: 'a workflow script cannot shell out; use an agent dispatch.' },
  { re: /\b(?:__dirname|__filename)\b/, name: '__dirname / __filename', why: 'module-scope values the runner does not define.' },
  { re: /\bglobalThis\b/, name: 'globalThis', why: 'reaching past the injected globals is unsupported and unportable.' },
])

/**
 * The 1-based line number that character offset `index` falls on in `text`.
 *
 * @param {string} text  the whole source
 * @param {number} index a character offset into it
 * @returns {number} 1-based line number
 */
function lineAt(text, index) {
  let line = 1
  const stop = Math.min(index, text.length)
  for (let i = 0; i < stop; i++) if (text.charCodeAt(i) === 10) line++
  return line
}

/**
 * Every forbidden construct in `source`, with the line each was found on.
 *
 * The match runs over the whole source in one piece; the line number is derived from the
 * match index. When a construct spans lines the report names the line it STARTS on and
 * shows the construct with its whitespace collapsed, so a finding is still readable.
 *
 * @param {string} source raw workflow script text — NOT stripped of comments or strings
 * @returns {Array<{line: number, name: string, why: string, text: string}>} empty when clean
 */
export function findForbiddenConstructs(source) {
  const text = String(source)
  const found = []
  for (const { re, name, why } of FORBIDDEN_CONSTRUCTS) {
    // Defensive: a `g` or `y` rule would carry lastIndex between calls and start
    // skipping matches. Scan with a stateless clone.
    const scan = re.global || re.sticky ? new RegExp(re.source, re.flags.replace(/[gy]/g, '')) : re
    const m = scan.exec(text)
    if (!m) continue
    const line = lineAt(text, m.index)
    const lineStart = text.lastIndexOf('\n', m.index - 1) + 1
    const nextBreak = text.indexOf('\n', m.index)
    const sourceLine = text.slice(lineStart, nextBreak === -1 ? text.length : nextBreak).trim().slice(0, 80)
    const spansLines = m[0].includes('\n')
    found.push({
      line,
      name,
      why,
      text: spansLines
        ? `${sourceLine}   ⟵ the construct CONTINUES ACROSS LINES: ${m[0].replace(/\s+/g, ' ').trim().slice(0, 80)}`
        : sourceLine,
    })
  }
  return found
}

/**
 * Throw unless `source` is loadable by the real runner.
 *
 * @param {string} source raw workflow script text
 * @param {string} label  how to name the script in the error
 * @throws {Error} naming every construct the runner would refuse
 */
export function assertRunnerLoadable(source, label = 'workflow script') {
  const found = findForbiddenConstructs(source)
  if (!found.length) return
  throw new Error(
    `${label}: the real workflow runner would REFUSE to load this script, so a passing test here ` +
      `would be meaningless.\n` +
      found.map((f) => `  line ${f.line}: ${f.name} — ${f.why}\n    ${f.text}`).join('\n'),
  )
}
