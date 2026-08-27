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
// ─────────────────────────────────────────────────────────────────────────────
// WHAT THIS FILE IMPLEMENTS, AND WHERE ITS BOUNDARY IS
// ─────────────────────────────────────────────────────────────────────────────
//
// Five releases in a row, this scan was widened by EXAMPLE and the next evasion was
// the same class one step out: a line-by-line scan fell to a newline; the newline fix
// fell to `/* */`; the `/* */` fix fell to Annex B `<!--`. Enumerating the forms
// somebody thought of is the defect, not the particular form that got through.
//
// So the scan is now defined against the GRAMMAR, and the grammar is small, closed and
// citable. Two productions are implemented, and they are the only two that decide
// whether a run of source text spells a forbidden construct:
//
//   (P1) WHAT MAY SIT BETWEEN TWO TOKENS.  ECMA-262 §12.2 WhiteSpace, §12.3
//        LineTerminator, and §12.4 Comment as EXTENDED BY Annex B.1.1 (HTML-like
//        Comments), which is normative for a Script. Written out, Annex B's Comment is
//
//            Comment ::  MultiLineComment
//                        SingleLineComment
//                        SingleLineHTMLOpenComment      <!-- ...
//                        SingleLineHTMLCloseComment     <LT> ws* /*…*/ * --> ...
//                        SingleLineDelimitedComment     /* … */ with no LineTerminator
//
//        All five are covered — see SEPARATOR_PRODUCTIONS below, which names each one
//        and is what the grammar-derived tests iterate over. WhiteSpace ∪ LineTerminator
//        is not hand-enumerated: §22.2.2.9 DEFINES the RegExp class `\s` as exactly that
//        union, so `\s` already covers <TAB> <VT> <FF> <ZWNBSP>, every Space_Separator
//        code point, and <LF> <CR> <LS> <PS>. Where a production needs "not a
//        LineTerminator" the four code points ARE spelled out, because §12.3 is a closed
//        four-element production and nothing else can join it.
//
//   (P2) HOW A TOKEN MAY BE SPELLED.  §12.7.1: an IdentifierName may contain a
//        UnicodeEscapeSequence, and it denotes the same binding — `require(x)` and
//        `require(x)` both call require. (A ReservedWord may NOT be escaped, so
//        `import` cannot be hidden this way; the escapable names here are `require`,
//        `process`, `Function`, `child_process`, `globalThis`, `__dirname`,
//        `__filename`.) That is a separate production from (P1) and it is closed the
//        same way: a third pass decodes identifier escapes and rescans.
//
// THE BOUNDARY, stated so the next reader can check completeness against the spec
// rather than against a list of attacks:
//
//   * IN SCOPE: any source text whose TOKEN SEQUENCE contains a forbidden construct,
//     however it is separated (P1) or spelled (P2). If a new evasion is claimed, the
//     question to ask is "which production does it use", and if the answer is neither
//     P1 nor P2 it is not this file's category.
//   * OUT OF SCOPE, deliberately: reaching a forbidden binding without ever writing its
//     token — computed member access, an alias, a name assembled at runtime. No static
//     scan closes that, and it is closed elsewhere instead: `globalThis` is refused
//     outright, and the runner injects seven globals, so there is no object to compute
//     a property of.
//   * Annex B comments are SCRIPT-ONLY (a Module rejects `<!--`; verified against V8).
//     Scanning as a Script is correct here and not a widening: the checker's probe is a
//     .cjs file and the harness body is an AsyncFunction — both Scripts, both accept
//     every Annex B form.
//
// THREE PASSES, and all three are load-bearing:
//
//   raw               the source byte for byte, nothing stripped. The runner's own
//                     detection mechanism is undocumented and may itself be a raw scan,
//                     so a forbidden token written inside a comment is still reported.
//   comment-stripped  comments blanked at IDENTICAL offsets, for a construct split by a
//                     comment in a place no separator rule anticipated.
//   escape-normalized comments blanked AND identifier escapes decoded (P2), with an
//                     offset map back to the raw text so a finding still names its line.
//
// A rule fires if ANY pass sees it. None replaces another; strictly more is caught,
// never less. Discuss a forbidden construct by name; do not write the token.

/** The globals the runner injects. Everything else is unavailable. */
export const RUNNER_GLOBALS = Object.freeze(['args', 'agent', 'workflow', 'phase', 'log', 'parallel', 'budget'])

// ── (P1) The complete set of things the grammar allows between two tokens ─────
//
// §12.3 LineTerminator is a closed four-element production. Everything below that needs
// "a line terminator" or "anything but a line terminator" is derived from this one list.
const LINE_TERMINATOR_CHARS = '\\n\\r\\u2028\\u2029'
/** §12.3 LineTerminatorSequence — <CR><LF> is ONE sequence, so it is matched first. */
const LINE_TERMINATOR_SEQUENCE = String.raw`(?:\r\n|[${LINE_TERMINATOR_CHARS}])`
/** SourceCharacter but not LineTerminator — i.e. SingleLineCommentChars. */
const NOT_LINE_TERMINATOR = String.raw`[^${LINE_TERMINATOR_CHARS}]`
/** §12.2 WhiteSpace alone: `\s` is WhiteSpace ∪ LineTerminator (§22.2.2.9), less the four. */
const WHITESPACE_NO_LINE_TERMINATOR = String.raw`[^\S${LINE_TERMINATOR_CHARS}]`

/** §12.4 MultiLineComment ∪ Annex B SingleLineDelimitedComment — a slash-star block, LineTerminator inside or not. */
const MULTI_LINE_COMMENT = String.raw`/\*[\s\S]*?\*/`
/** Annex B SingleLineDelimitedComment ONLY — no LineTerminator inside. Used by HTMLCloseComment. */
const SINGLE_LINE_DELIMITED_COMMENT = String.raw`/\*(?:(?!\*/)${NOT_LINE_TERMINATOR})*\*/`
/** §12.4 SingleLineComment. Terminated by ANY LineTerminator, not only <LF>. */
const SINGLE_LINE_COMMENT = String.raw`//${NOT_LINE_TERMINATOR}*`
/** Annex B.1.1 SingleLineHTMLOpenComment. */
const SINGLE_LINE_HTML_OPEN_COMMENT = String.raw`<!--${NOT_LINE_TERMINATOR}*`
/** Annex B.1.1 HTMLCloseComment :: WhiteSpaceSequence? SingleLineDelimitedCommentSequence? `-->` … */
const HTML_CLOSE_COMMENT =
  String.raw`${WHITESPACE_NO_LINE_TERMINATOR}*(?:${SINGLE_LINE_DELIMITED_COMMENT}${WHITESPACE_NO_LINE_TERMINATOR}*)*-->${NOT_LINE_TERMINATOR}*`
/** Annex B.1.1 SingleLineHTMLCloseComment :: LineTerminatorSequence HTMLCloseComment. */
const SINGLE_LINE_HTML_CLOSE_COMMENT = String.raw`${LINE_TERMINATOR_SEQUENCE}${HTML_CLOSE_COMMENT}`

/**
 * Every production that may appear between two tokens, named. The grammar-derived tests
 * iterate this record so that adding a production without a case for it fails the suite,
 * and so a reader can check the list against §12.2/§12.3/§12.4/Annex B.1.1 directly.
 */
export const SEPARATOR_PRODUCTIONS = Object.freeze({
  'WhiteSpace ∪ LineTerminator (§12.2, §12.3)': String.raw`\s`,
  'MultiLineComment (§12.4)': MULTI_LINE_COMMENT,
  'SingleLineDelimitedComment (Annex B.1.1)': SINGLE_LINE_DELIMITED_COMMENT,
  'SingleLineComment (§12.4)': SINGLE_LINE_COMMENT,
  'SingleLineHTMLOpenComment (Annex B.1.1)': SINGLE_LINE_HTML_OPEN_COMMENT,
  'SingleLineHTMLCloseComment (Annex B.1.1)': SINGLE_LINE_HTML_CLOSE_COMMENT,
})

// The HTML CLOSE form is tried FIRST because it begins with a LineTerminatorSequence that
// `\s` would otherwise swallow one character at a time, leaving the `-->` unconsumed.
const SEPARATOR =
  `(?:${SINGLE_LINE_HTML_CLOSE_COMMENT}|${MULTI_LINE_COMMENT}|${SINGLE_LINE_COMMENT}|${SINGLE_LINE_HTML_OPEN_COMMENT}|\\s)`

/**
 * GAP  matches zero or more separators (a token already adjacent to `(` or `.`).
 * GAP1 matches one or more (where the grammar REQUIRES a separator, as in `new Function`);
 *      using GAP there would make `importantThing` match an `import` rule.
 */
export const GAP = `${SEPARATOR}*`
export const GAP1 = `${SEPARATOR}+`

/**
 * Constructs the runner refuses. Each is matched against the WHOLE source text, never
 * line by line, and against the comment-stripped and escape-normalized copies as well —
 * see the header. Where a rule joins a token to a parenthesis or a dot it spans GAP,
 * because every production in SEPARATOR_PRODUCTIONS is legal there and the parser
 * accepts all of them.
 */
export const FORBIDDEN_CONSTRUCTS = Object.freeze([
  {
    re: new RegExp(String.raw`\bimport` + GAP + String.raw`\(`),
    name: 'dynamic import',
    why:
      'the runner refuses it STATICALLY — one occurrence anywhere in the file, even inside a ' +
      'function that is never called, makes the whole script unloadable. This is the 6.0.6 P0.',
  },
  {
    re: new RegExp(String.raw`^${WHITESPACE_NO_LINE_TERMINATOR}*import` + GAP1 + String.raw`[\w{*]`, 'm'),
    name: 'import statement',
    why: 'a workflow script is a script body, not a module.',
  },
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
 * Counts every §12.3 LineTerminator, not only <LF>: a construct split with <LS> would
 * otherwise be reported on the wrong line.
 *
 * @param {string} text  the whole source
 * @param {number} index a character offset into it
 * @returns {number} 1-based line number
 */
function lineAt(text, index) {
  let line = 1
  const stop = Math.min(index, text.length)
  for (let i = 0; i < stop; i++) {
    const c = text.charCodeAt(i)
    if (c === 13 && text.charCodeAt(i + 1) === 10) continue
    if (c === 10 || c === 13 || c === 0x2028 || c === 0x2029) line++
  }
  return line
}

const LINE_TERMINATOR_SET = new Set(['\n', '\r', '\u2028', '\u2029'])
const isLineTerminator = (ch) => ch !== undefined && LINE_TERMINATOR_SET.has(ch)
const IDENTIFIER_CHAR = /[A-Za-z0-9_$]/

/**
 * The index of the first §12.3 LineTerminator at or after `from`, or the end of the text.
 *
 * @param {string} text the whole source
 * @param {number} from where to start looking
 * @returns {number} an index into `text`
 */
function endOfLineFrom(text, from) {
  for (let k = from; k < text.length; k++) if (isLineTerminator(text[k])) return k
  return text.length
}

/**
 * Read a §12.7.1 UnicodeEscapeSequence at `at` (`\uXXXX` or `\u{H+}`).
 *
 * Only escapes that decode to an identifier character are reported: this pass exists to
 * normalize the SPELLING of a name, and decoding anything else could only invent a
 * construct that the source does not contain.
 *
 * @param {string} text the whole source
 * @param {number} at   the offset of the backslash
 * @returns {{decoded: string, end: number}|null} null when this is not such an escape
 */
function readIdentifierEscape(text, at) {
  if (text[at] !== '\\' || text[at + 1] !== 'u') return null
  let decoded = null
  let end = -1
  if (text[at + 2] === '{') {
    const close = text.indexOf('}', at + 3)
    const hex = close === -1 ? '' : text.slice(at + 3, close)
    if (hex && /^[0-9a-fA-F]{1,6}$/.test(hex)) {
      const cp = Number.parseInt(hex, 16)
      if (cp <= 0x10ffff) {
        decoded = String.fromCodePoint(cp)
        end = close + 1
      }
    }
  } else {
    const hex = text.slice(at + 2, at + 6)
    if (/^[0-9a-fA-F]{4}$/.test(hex)) {
      decoded = String.fromCharCode(Number.parseInt(hex, 16))
      end = at + 6
    }
  }
  if (decoded === null || !IDENTIFIER_CHAR.test(decoded)) return null
  return { decoded, end }
}

/**
 * One scan of `source` producing the two derived copies the extra passes need.
 *
 * `stripped` has every comment — all five Annex B forms — replaced by spaces at IDENTICAL
 * offsets, so a match index in it names the same line of the raw source.
 *
 * `normalized` additionally decodes identifier escapes (P2), which changes the length, so
 * it carries `normalizedOffsets`: normalized index → raw index.
 *
 * Strings, template literals and regex literals are recognised only so that a `//`, a
 * `/*`, a `<!--` or an escape INSIDE one is not mistaken for code. Their contents are
 * copied through untouched — the raw pass scans them, deliberately.
 *
 * This scan is additive. If it ever misjudges a division for a regex it can only miss a
 * comment, never invent a construct, and the raw pass and the GAP-tolerant rules are both
 * still scanning independently.
 *
 * @param {string} source raw workflow script text
 * @returns {{stripped: string, normalized: string, normalizedOffsets: number[]}} the derived copies
 */
export function scanSource(source) {
  const text = String(source)
  const stripped = text.split('')
  const norm = []
  const normAt = []
  const emit = (ch, at) => {
    norm.push(ch)
    normAt.push(at)
  }
  const blankBoth = (from, to) => {
    for (let k = from; k < to && k < text.length; k++) {
      const keep = isLineTerminator(text[k])
      if (!keep) stripped[k] = ' '
      emit(keep ? text[k] : ' ', k)
    }
  }
  const copyThrough = (from, to) => {
    for (let k = from; k < to && k < text.length; k++) emit(text[k], k)
  }
  // A `/` opens a regex literal only where a VALUE may begin. After an identifier,
  // a number, `)`, `]` or a closing quote it is division. These are the keywords after
  // which a `/` is still a regex.
  const VALUE_KEYWORDS = new Set(['return', 'typeof', 'instanceof', 'in', 'of', 'new', 'delete', 'void', 'throw', 'case', 'do', 'else', 'yield', 'await'])
  let prev = ''
  let prevWord = ''
  // Annex B's `-->` is a comment only when nothing but WhiteSpace and
  // SingleLineDelimitedComments separate it from the preceding LineTerminatorSequence.
  // It starts true because V8 accepts `-->` on the first line of a Script (verified), and
  // being permissive here can only blank text the raw pass still scans.
  let htmlCloseAllowed = true
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    const next = text[i + 1]
    // §12.4 SingleLineComment
    if (ch === '/' && next === '/') {
      const end = endOfLineFrom(text, i)
      blankBoth(i, end)
      i = end
      continue
    }
    // Annex B.1.1 SingleLineHTMLOpenComment
    if (ch === '<' && text.startsWith('<!--', i)) {
      const end = endOfLineFrom(text, i)
      blankBoth(i, end)
      i = end
      continue
    }
    // Annex B.1.1 SingleLineHTMLCloseComment — the `-->` half; the LineTerminatorSequence
    // that licenses it was consumed earlier and recorded in htmlCloseAllowed.
    if (ch === '-' && htmlCloseAllowed && text.startsWith('-->', i)) {
      const end = endOfLineFrom(text, i)
      blankBoth(i, end)
      i = end
      continue
    }
    // §12.4 MultiLineComment ∪ Annex B SingleLineDelimitedComment
    if (ch === '/' && next === '*') {
      let end = text.indexOf('*/', i + 2)
      end = end === -1 ? text.length : end + 2
      // Only the SingleLineDelimitedComment form preserves a pending `-->`; a comment
      // carrying a LineTerminator supplies one of its own, which V8 honours.
      for (let k = i; k < end; k++) if (isLineTerminator(text[k])) { htmlCloseAllowed = true; break }
      blankBoth(i, end)
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
      const end = Math.min(k + 1, text.length)
      copyThrough(i, end)
      i = end
      prev = ch
      prevWord = ''
      htmlCloseAllowed = false
      continue
    }
    if (ch === '/' && !/[A-Za-z0-9_$)\]]/.test(prev)) {
      const regexOk = !prev || !/[A-Za-z0-9_$]/.test(prev) || VALUE_KEYWORDS.has(prevWord)
      if (regexOk) {
        let k = i + 1
        let inClass = false
        let closed = false
        while (k < text.length && !isLineTerminator(text[k])) {
          const c = text[k]
          if (c === '\\') { k += 2; continue }
          if (c === '[') inClass = true
          else if (c === ']') inClass = false
          else if (c === '/' && !inClass) { closed = true; break }
          k++
        }
        if (closed) {
          copyThrough(i, k + 1)
          i = k + 1
          prev = '/'
          prevWord = ''
          htmlCloseAllowed = false
          continue
        }
      }
    }
    // §12.7.1 IdentifierName UnicodeEscapeSequence — same binding, different spelling.
    const escape = readIdentifierEscape(text, i)
    if (escape) {
      for (const c of escape.decoded) emit(c, i)
      i = escape.end
      prev = escape.decoded
      prevWord += escape.decoded
      htmlCloseAllowed = false
      continue
    }
    emit(ch, i)
    if (isLineTerminator(ch)) {
      htmlCloseAllowed = true
    } else if (!/\s/.test(ch)) {
      prev = ch
      prevWord = IDENTIFIER_CHAR.test(ch) ? prevWord + ch : ''
      htmlCloseAllowed = false
    }
    i++
  }
  return { stripped: stripped.join(''), normalized: norm.join(''), normalizedOffsets: normAt }
}

/**
 * A copy of `source` with every comment blanked out, at IDENTICAL byte offsets.
 *
 * @param {string} source raw workflow script text
 * @returns {string} the same text with comment bodies replaced by spaces
 */
export function stripCommentsPreservingOffsets(source) {
  return scanSource(source).stripped
}

/**
 * Every forbidden construct in `source`, with the line each was found on.
 *
 * THREE passes, and all three are load-bearing — see the header. A rule fires if ANY of
 * them sees it, and the report names which one did.
 *
 * @param {string} source raw workflow script text — NOT stripped of comments or strings
 * @returns {Array<{line: number, name: string, why: string, text: string, via: string}>} empty when clean
 */
export function findForbiddenConstructs(source) {
  const text = String(source)
  const { stripped, normalized, normalizedOffsets } = scanSource(text)
  const found = []
  for (const { re, name, why } of FORBIDDEN_CONSTRUCTS) {
    // Defensive: a `g` or `y` rule would carry lastIndex between calls and start
    // skipping matches. Scan with a stateless clone.
    const scan = re.global || re.sticky ? new RegExp(re.source, re.flags.replace(/[gy]/g, '')) : re
    let m = scan.exec(text)
    let via = 'raw'
    let rawIndex = m ? m.index : -1
    if (!m) {
      m = scan.exec(stripped)
      via = 'comment-stripped'
      rawIndex = m ? m.index : -1
    }
    if (!m) {
      m = scan.exec(normalized)
      via = 'escape-normalized'
      rawIndex = m ? (normalizedOffsets[m.index] ?? 0) : -1
    }
    if (!m) continue
    const line = lineAt(text, rawIndex)
    const lineStart = text.lastIndexOf('\n', rawIndex - 1) + 1
    const nextBreak = text.indexOf('\n', rawIndex)
    const sourceLine = text.slice(lineStart, nextBreak === -1 ? text.length : nextBreak).trim().slice(0, 80)
    const spansLines = /[\n\r\u2028\u2029]/.test(m[0])
    const collapsed = m[0].replace(/\s+/g, ' ').trim().slice(0, 80)
    const suffix =
      via === 'raw'
        ? spansLines
          ? `   ⟵ the construct CONTINUES ACROSS LINES: ${collapsed}`
          : ''
        : via === 'comment-stripped'
          ? `   ⟵ SPLIT BY A COMMENT; with comments removed it reads: ${collapsed}`
          : `   ⟵ SPELLED WITH IDENTIFIER ESCAPES; decoded it reads: ${collapsed}`
    found.push({ line, name, why, via, text: `${sourceLine}${suffix}` })
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
