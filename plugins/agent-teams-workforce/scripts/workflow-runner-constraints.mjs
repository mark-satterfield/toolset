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
// 6.0.8 fixed the newline but left the same hole one character wider. `\s` matches
// whitespace and nothing else, and whitespace is not the only thing JavaScript allows
// between a token and its parenthesis: a COMMENT is allowed there too. Every one of
//
//     <dynamic-import-token>/*x*/("node:fs")
//     <commonjs-loader>/*x*/(
//     new/*a*/Function/*b*/(
//     <process-object>/*a*/.env
//     <commonjs-loader>/*a*/./*b*/resolve
//     <dynamic-import-token>  NEWLINE  //comment  NEWLINE  (
//
// is valid JavaScript — node --check accepts every one — and every one walked straight
// past the 6.0.8 rules. A scratch workflows directory carrying four of them made this
// checker exit 0 while printing "free of constructs the runner refuses", and
// assertRunnerLoadable was equally blind, so the whole suite would have gone green over a
// script the runner CANNOT LOAD. That is the 6.0.6 P0 failure mode exactly.
//
// So the separator is no longer `\s`. It is GAP / GAP1 below, which match whitespace,
// block comments and line comments — the COMPLETE set of things the grammar permits
// between two tokens, not a longer list of things someone thought of. There is nothing
// else to add, which is why this is a fix rather than another widening.
//
// AND every rule is matched a second time against a comment-STRIPPED copy of the source,
// because a separator pattern only covers gaps someone anticipated writing a rule around.
// The stripped copy preserves byte offsets exactly — comment characters become spaces and
// newlines are kept — so a line number derived from a match in it still points at the
// right line of the RAW source.
//
// THE RAW PASS STAYS. It is not replaced and must not be: how the runner detects a
// dynamic import is not documented, a raw scan on its side is entirely possible, and a
// "harmless" mention inside a comment is not worth risking a repeat outage over. The
// stripped pass is ADDED ALONGSIDE it — strictly more is caught, never less. Discuss a
// forbidden construct by name; do not write the token.

/** The globals the runner injects. Everything else is unavailable. */
export const RUNNER_GLOBALS = Object.freeze(['args', 'agent', 'workflow', 'phase', 'log', 'parallel', 'budget'])

/**
 * What JavaScript permits BETWEEN two tokens: whitespace, a block comment, a line
 * comment. That is the whole list — the grammar has nothing else — so a rule built on
 * these is complete against separator evasion rather than merely longer than the last one.
 *
 * GAP  matches zero or more of them (a token already adjacent to `(` or `.`).
 * GAP1 matches one or more (where the grammar REQUIRES a separator, as in `new Function`);
 *      using GAP there would make `importantThing` match an `import` rule.
 */
const GAP = String.raw`(?:\s|/\*[\s\S]*?\*/|//[^\n]*(?:\n|$))*`
const GAP1 = String.raw`(?:\s|/\*[\s\S]*?\*/|//[^\n]*(?:\n|$))+`

/**
 * Constructs the runner refuses. Each is matched against the WHOLE source text, never
 * line by line, and against a comment-stripped copy of it as well — see the header.
 * Where a rule joins a token to a parenthesis or a dot it spans GAP, because a newline
 * AND a comment are both legal there and the parser accepts both.
 */
export const FORBIDDEN_CONSTRUCTS = Object.freeze([
  {
    re: new RegExp(String.raw`\bimport` + GAP + String.raw`\(`),
    name: 'dynamic import',
    why:
      'the runner refuses it STATICALLY — one occurrence anywhere in the file, even inside a ' +
      'function that is never called, makes the whole script unloadable. This is the 6.0.6 P0.',
  },
  { re: new RegExp(String.raw`^[^\S\n]*import` + GAP1 + String.raw`[\w{*]`, 'm'), name: 'import statement', why: 'a workflow script is a script body, not a module.' },
  { re: new RegExp(String.raw`\brequire` + GAP + String.raw`\(`), name: 'require()', why: 'there is no CommonJS loader in the runner.' },
  { re: new RegExp(String.raw`\brequire` + GAP + String.raw`\.` + GAP + String.raw`resolve\b`), name: 'require.resolve', why: 'there is no module resolution in the runner.' },
  { re: new RegExp(String.raw`\bnew` + GAP1 + String.raw`Function` + GAP + String.raw`\(`), name: 'new Function', why: 'code generated at runtime escapes every check that guards this directory.' },
  { re: new RegExp(String.raw`\bprocess` + GAP + String.raw`\.`), name: 'process', why: 'the runner injects no process object.' },
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
 * A copy of `source` with every comment blanked out, at IDENTICAL byte offsets.
 *
 * Comment characters become spaces and newlines are preserved, so the result has the same
 * length and the same line breaks as the input: a match index found here names the same
 * line in the raw source, and the raw line can be quoted in the report unchanged.
 *
 * Strings, template literals and regex literals are recognised only so that a `//` or a
 * `/*` INSIDE one is not mistaken for a comment. Their contents are left alone — the raw
 * pass scans them, deliberately, and blanking them would lose findings.
 *
 * This pass is additive. If it ever misjudges a division for a regex it can only miss a
 * comment, never invent a construct, and the raw pass and the GAP-tolerant rules are both
 * still scanning independently.
 *
 * @param {string} source raw workflow script text
 * @returns {string} the same text with comment bodies replaced by spaces
 */
export function stripCommentsPreservingOffsets(source) {
  const text = String(source)
  const out = Array.from(text)
  const blank = (from, to) => {
    for (let k = from; k < to && k < out.length; k++) if (out[k] !== '\n') out[k] = ' '
  }
  // A `/` opens a regex literal only where a VALUE may begin. After an identifier,
  // a number, `)`, `]` or a closing quote it is division. These are the keywords after
  // which a `/` is still a regex.
  const VALUE_KEYWORDS = new Set(['return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void', 'throw', 'case', 'do', 'else', 'yield', 'await'])
  let prev = ''
  let prevWord = ''
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    const next = text[i + 1]
    if (ch === '/' && next === '/') {
      let end = text.indexOf('\n', i)
      if (end === -1) end = text.length
      blank(i, end)
      i = end
      continue
    }
    if (ch === '/' && next === '*') {
      let end = text.indexOf('*/', i + 2)
      end = end === -1 ? text.length : end + 2
      blank(i, end)
      i = end
      continue
    }
    if (ch === '"' || ch === "'" || ch === '`') {
      // Templates may nest `${ ... }` containing anything, comments included. Skipping the
      // whole literal is the conservative choice: a comment inside a template expression
      // stays visible to the raw pass, which is where it would have been caught anyway.
      let k = i + 1
      while (k < text.length) {
        if (text[k] === '\\') { k += 2; continue }
        if (text[k] === ch) break
        k++
      }
      i = Math.min(k + 1, text.length)
      prev = ch
      prevWord = ''
      continue
    }
    if (ch === '/' && !/[A-Za-z0-9_$)\]]/.test(prev)) {
      const regexOk = !prev || !/[A-Za-z0-9_$]/.test(prev) || VALUE_KEYWORDS.has(prevWord)
      if (regexOk) {
        let k = i + 1
        let inClass = false
        let closed = false
        while (k < text.length && text[k] !== '\n') {
          const c = text[k]
          if (c === '\\') { k += 2; continue }
          if (c === '[') inClass = true
          else if (c === ']') inClass = false
          else if (c === '/' && !inClass) { closed = true; break }
          k++
        }
        if (closed) {
          i = k + 1
          prev = '/'
          prevWord = ''
          continue
        }
      }
    }
    if (!/\s/.test(ch)) {
      prev = ch
      prevWord = /[A-Za-z0-9_$]/.test(ch) ? prevWord + ch : ''
    }
    i++
  }
  return out.join('')
}

/**
 * Every forbidden construct in `source`, with the line each was found on.
 *
 * TWO passes, and both are load-bearing. The RAW pass scans the source byte for byte with
 * nothing stripped, because the runner's own detection mechanism is undocumented and a
 * forbidden token written inside a comment is not worth the risk. The COMMENT-STRIPPED
 * pass catches a construct someone split with a comment in a place no separator rule
 * anticipated. Neither replaces the other; a rule fires if EITHER pass sees it.
 *
 * Each rule is matched over the whole text in one piece; the line number is derived from
 * the match index, which is valid for both passes because the stripped copy preserves
 * offsets. When a construct spans lines the report names the line it STARTS on and shows
 * it with whitespace collapsed, so a finding is still readable.
 *
 * @param {string} source raw workflow script text — NOT stripped of comments or strings
 * @returns {Array<{line: number, name: string, why: string, text: string, via: string}>} empty when clean
 */
export function findForbiddenConstructs(source) {
  const text = String(source)
  const stripped = stripCommentsPreservingOffsets(text)
  const found = []
  for (const { re, name, why } of FORBIDDEN_CONSTRUCTS) {
    // Defensive: a `g` or `y` rule would carry lastIndex between calls and start
    // skipping matches. Scan with a stateless clone.
    const scan = re.global || re.sticky ? new RegExp(re.source, re.flags.replace(/[gy]/g, '')) : re
    const raw = scan.exec(text)
    const hidden = raw ? null : scan.exec(stripped)
    const m = raw || hidden
    if (!m) continue
    const via = raw ? 'raw' : 'comment-stripped'
    const line = lineAt(text, m.index)
    const lineStart = text.lastIndexOf('\n', m.index - 1) + 1
    const nextBreak = text.indexOf('\n', m.index)
    const sourceLine = text.slice(lineStart, nextBreak === -1 ? text.length : nextBreak).trim().slice(0, 80)
    const spansLines = m[0].includes('\n')
    const collapsed = m[0].replace(/\s+/g, ' ').trim().slice(0, 80)
    found.push({
      line,
      name,
      why,
      via,
      text: spansLines
        ? `${sourceLine}   ⟵ the construct CONTINUES ACROSS LINES: ${collapsed}`
        : hidden
          ? `${sourceLine}   ⟵ SPLIT BY A COMMENT; with comments removed it reads: ${collapsed}`
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
