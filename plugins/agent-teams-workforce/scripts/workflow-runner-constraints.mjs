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
// THE CAPABILITY MODEL — what a workflow script is PERMITTED to reach
// ─────────────────────────────────────────────────────────────────────────────
//
// This section is the definition. Everything below it is DERIVED from this section,
// and a rule that cannot be traced back to it does not belong in the file.
//
// The runner calls a workflow script with exactly seven bindings in scope:
//
//     args, agent, workflow, phase, log, parallel, budget
//
// That is the whole contract. A script composes prompts, dispatches work through
// `agent` and `workflow`, and returns a result. It has no module loader, no
// filesystem, no process object, no network and no way to spawn anything. Every
// other capability is OUT OF CONTRACT — not discouraged, not risky, absent.
//
// So the interesting question is NOT "which of these six token spellings appear".
// It is: CAN THIS SOURCE YIELD A REFERENCE THE SEVEN INJECTED GLOBALS DO NOT PROVIDE?
// Five releases running, that question was answered by example — a line-by-line scan
// fell to a newline, the newline fix fell to `/* */`, that fix fell to Annex B `<!--`
// — and the sixth answered it by appending two more entries, which is the same defect
// wearing a longer list. There are exactly four ways to obtain such a reference, and
// they are categories, not spellings:
//
//   C1  MODULE LOADING — load code from outside the script and take its exports.
//       (dynamic import, an import statement, the CommonJS loader, module resolution)
//   C2  CODE GENERATION FROM STRINGS — compile a string into a function. The compiled
//       function's scope is the GLOBAL scope, not the injected one, so this hands back
//       everything the seven globals withhold. Proven end to end: `Function('return
//       this')()` returned the live global object, the process uid and $HOME while the
//       checker printed "free of constructs the runner refuses". However spelled,
//       aliased, or reached through a constructor chain, this is one category.
//       (eval, indirect eval, the Function constructor, AsyncFunction /
//        GeneratorFunction / AsyncGeneratorFunction via `.constructor.constructor`)
//   C3  THE GLOBAL OBJECT OR ANOTHER REALM — name the object the injected globals were
//       meant to stand in for. (globalThis, global, self, window)
//   C4  A HOST CAPABILITY THE RUNNER DOES NOT INJECT — process, child_process, Buffer,
//       fetch, module-scope values like __dirname.
//
// ─────────────────────────────────────────────────────────────────────────────
// TWO CONTROLS, AND WHICH ONE CARRIES THE WEIGHT
// ─────────────────────────────────────────────────────────────────────────────
//
// (A) A RUNTIME CAPABILITY PROBE — `createCapabilityProbe` below, used by BOTH the
//     syntax checker's execution pass and the unit-test harness. Each out-of-contract
//     name is bound as a PARAMETER of the function the script body is compiled into,
//     shadowing the real binding with a tripwire that records and throws on any read,
//     call or construct. This is a scope-level control, not a text-level one, so it is
//     strictly stronger than any regex: it catches an alias (`const f = Function; f(x)`),
//     a computed property (`globalThis['pro' + 'cess']`) and a name assembled at
//     runtime, none of which a static scan can see. This is where the weight belongs.
//
// (B) THE STATIC SCAN — `findForbiddenConstructs` below. It exists for a DIFFERENT
//     question: the real runner refuses some constructs STATICALLY, before any phase
//     runs, so a script containing one cannot load at all even if no line of it ever
//     executes. That is the 6.0.6 P0, and only a text scan can catch it, because the
//     probe never gets to run. The scan is therefore load-bearing for C1 and for the
//     spellings of C2–C4 that appear literally, and it is NOT a completeness claim.
//
// ─────────────────────────────────────────────────────────────────────────────
// WHAT REMAINS OPEN — stated plainly, because the previous header's implied
// completeness is what made the last gap invisible
// ─────────────────────────────────────────────────────────────────────────────
//
// THE STATIC SCAN CANNOT CLOSE, and does not claim to close:
//
//   * COMPUTED MEMBER ACCESS.       `globalThis['pro' + 'cess']`, `o[k]` for a runtime k.
//   * ALIASING.                     `const f = Function` then `f('...')` on a later line.
//   * PUNCTUATOR INTERPOSITION beyond optional chaining. `(require)(x)` parenthesizes the
//     callee; the rules span optional chaining (`require?.(`, `process?.`) because that is
//     a closed two-character production, but arbitrary parenthesization is expression
//     grammar, not separator grammar, and enumerating it would be example-driven again.
//   * A CONSTRUCTOR CHAIN off a value the scan never sees named, e.g. reaching the
//     Function constructor from an arbitrary expression's `.constructor`. The literal
//     `.constructor` member access IS refused; an equivalent computed one is not.
//
// Every one of those is closed by control (A) instead, because the tripwire is in the
// SCOPE: the alias, the computed key and the parenthesized callee all resolve to the
// same shadowed binding. What neither control closes:
//
//   * A CONSTRUCTOR CHAIN OFF AN INTRINSIC THE PROBE CANNOT SHADOW — `({}).constructor
//     .constructor` reaches the real Function constructor without naming any shadowed
//     binding, and poisoning `Function.prototype.constructor` would corrupt the
//     checker's own realm. The literal spelling is caught by the scan; a computed
//     spelling of it is caught by NEITHER. This is a known, open hole, and it is
//     recorded here rather than papered over.
//   * `this` AT THE TOP LEVEL OF THE COMPILED BODY. Both models compile the script into
//     a sloppy-mode function, so top-level `this` IS the real global object and
//     `this.process` reaches the host — measured, not theorised. `this` is not a
//     binding, so the probe cannot shadow it, and it is far too common in prose for the
//     raw scan to refuse on sight. Note this is a property of the two MODELS, not
//     necessarily of the real runner, which may well call the body in strict mode or
//     with a bound receiver; nobody has checked. Tracked as a bead, deliberately NOT
//     fixed here — prepending a strict-mode directive would change the semantics of
//     every shipped script, which is a bigger change than this component's risk
//     justifies and is not something to do on the way past.
//
// The honest summary: a workflow script is OUR OWN code in OUR OWN repository, and an
// author who can write into workflows/ can already do whatever they like elsewhere in
// the repo. These controls exist to stop an accident from shipping and to stop the
// checker from telling us it verified something it did not. They are not an adversarial
// boundary and must not be described as one.
//
// ─────────────────────────────────────────────────────────────────────────────
// HOW THE STATIC SCAN IS DERIVED — the grammar, not a list of attacks
// ─────────────────────────────────────────────────────────────────────────────
//
// Within its stated scope the scan is defined against the GRAMMAR, and the grammar is
// small, closed and citable. Two productions decide whether a run of source text spells
// a forbidden construct:
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
//        `requir\u0065(x)` both call require. (A ReservedWord may NOT be escaped, so
//        `import` cannot be hidden this way.) That is a separate production from (P1)
//        and it is closed the same way: a third pass decodes identifier escapes and
//        rescans.
//
//   Every SEPARATOR production is written so that it can match a given run of text in
//   exactly ONE way. That is a correctness property AND a performance one: the earlier
//   MultiLineComment was lazy (`/\*[\s\S]*?\*/`), so it could be extended past its own
//   `*/` onto a later one, and n adjacent comments admitted 2^(n-1) parses of the same
//   text. A 147-byte file took 21 seconds; a ~250-byte one never finished. A comment
//   ends at its FIRST `*/`, so the ambiguity was never grammatical to begin with — the
//   productions below are anchored to it and the scan is linear.
//
//   * IN SCOPE: any source text whose TOKEN SEQUENCE contains a forbidden construct,
//     however it is separated (P1) or spelled (P2). If a new evasion is claimed, the
//     question to ask is "which production does it use", and if the answer is neither
//     P1 nor P2 it is not this file's category — see WHAT REMAINS OPEN above.
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
//                     This is also why C2/C3/C4 rules are matched as whole IDENTIFIERS
//                     only where the name never occurs in ordinary prose: `require` and
//                     `process` are common English words and appear in agent prompts, so
//                     their rules stay anchored to a call or a member access, while
//                     `eval`, `Function` and `globalThis` are refused on sight.
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
/**
 * "and here the line ends" — the next character is a §12.3 LineTerminator, or there is no
 * next character.
 *
 * Every to-end-of-line production below is PINNED with this, and that is a correctness
 * property before it is a performance one: a SingleLineComment runs to the end of its
 * line and CANNOT stop early, so a pattern that lets it stop early is describing a
 * grammar JavaScript does not have. Unpinned, `//   a   //   b` admits one parse per
 * position in every trailing space run — the comment ends there, `\s` takes the spaces,
 * and the inner `//` opens another comment that can also end anywhere. Those multiply
 * across a comment block, which is exactly the ReDoS shape the MultiLineComment note
 * below describes, in a different production. Pinned, only the true end of line can
 * match and the scan stays linear.
 */
const END_OF_LINE_AHEAD = String.raw`(?![^${LINE_TERMINATOR_CHARS}])`

/**
 * §12.4 MultiLineComment ∪ Annex B SingleLineDelimitedComment — a slash-star block,
 * LineTerminator inside or not.
 *
 * ANCHORED TO THE FIRST COMMENT TERMINATOR, deliberately. The lazy form — a star-slash
 * body written non-greedily — matches the same comment, but on backtracking it can be EXTENDED past that terminator onto a later
 * one — so n adjacent comments admit 2^(n-1) distinct parses of the same text and the
 * enclosing SEPARATOR star explores all of them. Measured on 6.0.10: a 147-byte source
 * took 20.8s and a ~250-byte one did not finish, which is a denial of service against
 * our own checker. A comment ends at its first terminator, so the longer matches were
 * never grammatical; `(?:[^*]|\*(?!/))*` cannot produce them and the scan is linear.
 */
const MULTI_LINE_COMMENT = String.raw`/\*(?:[^*]|\*(?!/))*\*/`
/** Annex B SingleLineDelimitedComment ONLY — no LineTerminator inside. Used by HTMLCloseComment. */
const SINGLE_LINE_DELIMITED_COMMENT = String.raw`/\*(?:(?!\*/)${NOT_LINE_TERMINATOR})*\*/`
/** §12.4 SingleLineComment. Terminated by ANY LineTerminator, not only <LF>, and it runs to it. */
const SINGLE_LINE_COMMENT = String.raw`//${NOT_LINE_TERMINATOR}*${END_OF_LINE_AHEAD}`
/** Annex B.1.1 SingleLineHTMLOpenComment. Runs to the end of its line. */
const SINGLE_LINE_HTML_OPEN_COMMENT = String.raw`<!--${NOT_LINE_TERMINATOR}*${END_OF_LINE_AHEAD}`
/** Annex B.1.1 HTMLCloseComment :: WhiteSpaceSequence? SingleLineDelimitedCommentSequence? `-->` … */
const HTML_CLOSE_COMMENT =
  String.raw`${WHITESPACE_NO_LINE_TERMINATOR}*(?:${SINGLE_LINE_DELIMITED_COMMENT}${WHITESPACE_NO_LINE_TERMINATOR}*)*-->${NOT_LINE_TERMINATOR}*${END_OF_LINE_AHEAD}`
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
 * §11.1.4 / §13.3 OptionalExpression — `?.` is ONE punctuator and may stand where a call
 * or a member access would. It is a closed two-character production, so spanning it is
 * derivation, not another entry on an example list. `require?.(` and `process?.` are the
 * forms that reached 6.0.10.
 */
const OPTIONAL_CALL = String.raw`(?:\?\.)?`
/** `?.name` / `.name` — the member half of the same production. */
const OPTIONAL_MEMBER = String.raw`\??\.`

// ── The four capability categories the rules below are DERIVED from ───────────
// Each rule names the category it serves. A rule with no category has no derivation,
// which is the defect this file exists to stop repeating.
export const C1_MODULE_LOADING = 'C1 module loading'
export const C2_CODE_GENERATION = 'C2 code generation from strings'
export const C3_GLOBAL_OBJECT = 'C3 the global object or another realm'
export const C4_HOST = 'C4 a host capability the runner does not inject'

/** The four categories, for tests that iterate them. */
export const CAPABILITIES = Object.freeze([C1_MODULE_LOADING, C2_CODE_GENERATION, C3_GLOBAL_OBJECT, C4_HOST])

/**
 * Constructs the runner refuses. Each is matched against the WHOLE source text, never
 * line by line, and against the comment-stripped and escape-normalized copies as well —
 * see the header. Where a rule joins a token to a parenthesis or a dot it spans GAP,
 * because every production in SEPARATOR_PRODUCTIONS is legal there and the parser
 * accepts all of them.
 */
export const FORBIDDEN_CONSTRUCTS = Object.freeze([
  // ── C1  MODULE LOADING ──────────────────────────────────────────────────────
  {
    capability: C1_MODULE_LOADING,
    re: new RegExp(String.raw`\bimport` + GAP + String.raw`\(`),
    name: 'dynamic import',
    why:
      'the runner refuses it STATICALLY — one occurrence anywhere in the file, even inside a ' +
      'function that is never called, makes the whole script unloadable. This is the 6.0.6 P0.',
  },
  {
    capability: C1_MODULE_LOADING,
    re: new RegExp(String.raw`^${WHITESPACE_NO_LINE_TERMINATOR}*import` + GAP1 + String.raw`[\w{*]`, 'm'),
    name: 'import statement',
    why: 'a workflow script is a script body, not a module.',
  },
  {
    capability: C1_MODULE_LOADING,
    re: new RegExp(String.raw`\brequire` + GAP + OPTIONAL_CALL + GAP + String.raw`\(`),
    name: 'require()',
    why: 'there is no CommonJS loader in the runner.',
  },
  {
    capability: C1_MODULE_LOADING,
    re: new RegExp(String.raw`\brequire` + GAP + OPTIONAL_MEMBER + GAP + String.raw`resolve\b`),
    name: 'require.resolve',
    why: 'there is no module resolution in the runner.',
  },

  // ── C2  CODE GENERATION FROM STRINGS ────────────────────────────────────────
  //
  // These four rules are ONE capability, not four spellings. A compiled string runs in
  // the GLOBAL scope, so any of them hands back everything the seven injected globals
  // withhold — proven with a live sentinel that returned the process uid and $HOME.
  // `eval`, `Function` and the `*Function` intrinsics never occur in workflow prose, so
  // they are refused as bare identifiers rather than only in call position: that is what
  // covers `(0, eval)(…)`, `new (Function)(…)` and `const f = Function` in one rule each,
  // instead of a punctuator list that the next round walks around.
  {
    capability: C2_CODE_GENERATION,
    re: new RegExp(String.raw`\bnew` + GAP1 + String.raw`Function` + GAP + String.raw`\(`),
    name: 'new Function',
    why: 'code generated at runtime escapes every check that guards this directory.',
  },
  {
    capability: C2_CODE_GENERATION,
    re: /\bFunction\b/,
    name: 'Function',
    why:
      'the Function constructor compiles a string in the GLOBAL scope, however it is spelled or ' +
      'aliased — naming the binding at all is out of contract.',
  },
  {
    capability: C2_CODE_GENERATION,
    re: /\beval\b/,
    name: 'eval',
    why: 'direct and indirect eval both compile a string; indirect eval compiles it in the global scope.',
  },
  {
    capability: C2_CODE_GENERATION,
    re: /\b(?:Async|Generator|AsyncGenerator)Function\b/,
    name: 'AsyncFunction / GeneratorFunction',
    why: 'the same code-generation intrinsic reached through a constructor chain rather than by name.',
  },
  {
    capability: C2_CODE_GENERATION,
    re: new RegExp(String.raw`\.` + GAP + String.raw`constructor\b`),
    name: '.constructor',
    why:
      'a function value\u2019s `.constructor` IS the Function constructor, so a constructor chain reaches ' +
      'code generation without ever writing its name. A COMPUTED equivalent is not caught here — see ' +
      'WHAT REMAINS OPEN in the header, and the runtime capability probe.',
  },

  // ── C3  THE GLOBAL OBJECT OR ANOTHER REALM ──────────────────────────────────
  {
    capability: C3_GLOBAL_OBJECT,
    re: /\bglobalThis\b/,
    name: 'globalThis',
    why: 'reaching past the injected globals is unsupported and unportable.',
  },

  // ── C4  A HOST CAPABILITY THE RUNNER DOES NOT INJECT ────────────────────────
  //
  // `process` and `require` are ordinary English words that DO occur in the agent prompts
  // these scripts compose, and the raw pass scans prose. So unlike the C2 names they stay
  // anchored to a call or a member access — spanning optional chaining, which is a closed
  // two-character production, but not arbitrary parenthesization. See the header.
  {
    capability: C4_HOST,
    re: new RegExp(String.raw`\bprocess` + GAP + OPTIONAL_MEMBER),
    name: 'process',
    why: 'the runner injects no process object.',
  },
  {
    capability: C4_HOST,
    re: /\b(?:child_process|node:child_process)\b/,
    name: 'child_process',
    why: 'a workflow script cannot shell out; use an agent dispatch.',
  },
  {
    capability: C4_HOST,
    re: /\b(?:__dirname|__filename)\b/,
    name: '__dirname / __filename',
    why: 'module-scope values the runner does not define.',
  },
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

// ─────────────────────────────────────────────────────────────────────────────
// CONTROL (A) — THE RUNTIME CAPABILITY PROBE
// ─────────────────────────────────────────────────────────────────────────────
//
// This is the stronger of the two controls and it is where the weight belongs. The
// static scan above answers "would the runner refuse to LOAD this file"; this answers
// the capability-model question directly — "did this script reach anything the seven
// injected globals do not provide".
//
// The mechanism is scope, not text. Both places that execute a workflow body — the
// syntax checker's execution pass and the unit-test harness — compile it into a
// function whose parameter list is the seven runner globals FOLLOWED BY every
// out-of-contract name below. A parameter shadows the real binding for the whole body,
// so inside the script `Function`, `eval`, `globalThis`, `process` and the rest resolve
// to a tripwire that records the reach and throws.
//
// Being a scope control, it closes what no regex can:
//
//   const f = Function; f('return this')()   the alias resolves to the tripwire
//   globalThis['pro' + 'cess']               the computed key hits the get trap
//   (require)('node:fs')                     the parenthesized callee is still the binding
//   (0, eval)('this')                        the comma expression yields the tripwire
//
// It does NOT close a constructor chain off an intrinsic — `({}).constructor.constructor`
// never names a shadowed binding, and poisoning `Function.prototype.constructor` would
// corrupt the realm the checker itself runs in. The literal spelling of that chain is
// refused by the static scan; a computed spelling of it is refused by neither control.
// That hole is real and is stated in the header rather than papered over.
//
// A probe that only threw would be evadable by a `try {} catch {}`, so every reach is
// APPENDED TO `escapes` before the throw and callers must inspect the array after the
// run rather than trusting that an error propagated.

/** Names the runner does NOT inject, grouped by the capability category they serve. */
export const OUT_OF_CONTRACT_GLOBALS = Object.freeze([
  // C2 — code generation from strings
  'eval',
  'Function',
  'AsyncFunction',
  'GeneratorFunction',
  'AsyncGeneratorFunction',
  // C3 — the global object or another realm
  'globalThis',
  'global',
  'self',
  'window',
  'frames',
  // C1 — module loading (the syntax forms are the static scan's job; these are bindings)
  'require',
  'module',
  'exports',
  // C4 — host capabilities
  'process',
  'Buffer',
  '__dirname',
  '__filename',
  'fetch',
  'XMLHttpRequest',
  'WebAssembly',
])

/** Thrown by a tripwire. Distinguishable so a caller can tell it from a script's own error. */
export class CapabilityEscapeError extends Error {
  /**
   * @param {string} message what was reached, and how
   */
  constructor(message) {
    super(message)
    this.name = 'CapabilityEscapeError'
  }
}

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

/**
 * A set of tripwire bindings for every out-of-contract global, plus the array they
 * record into.
 *
 * @returns {{names: string[], values: unknown[], escapes: Array<{name: string, op: string, detail: string|null, message: string}>}}
 *          `names`/`values` are positionally aligned, for use as parameters and arguments
 */
export function createCapabilityProbe() {
  const escapes = []
  const trip = (name, op, detail) => {
    const message = `\`${name}\` was reached (${op}${detail ? ` ${detail}` : ''}) — the runner injects only ${RUNNER_GLOBALS.join(', ')}`
    escapes.push({ name, op, detail: detail ?? null, message })
    throw new CapabilityEscapeError(message)
  }
  const values = OUT_OF_CONTRACT_GLOBALS.map((name) =>
    // The target is a function so that `apply` and `construct` are legal traps.
    new Proxy(function () {}, {
      apply: () => trip(name, 'called as a function', null),
      construct: () => trip(name, 'used with new', null),
      get: (_t, prop) => trip(name, 'property read', typeof prop === 'symbol' ? prop.toString() : `.${String(prop)}`),
      has: (_t, prop) => trip(name, 'probed with in', String(prop)),
    }),
  )
  return { names: [...OUT_OF_CONTRACT_GLOBALS], values, escapes }
}

/**
 * Compile a workflow script body the way both executing models must: the seven injected
 * globals, then a tripwire for every out-of-contract name.
 *
 * `typeof` on a shadowed name does NOT trip — reading a binding's type touches no trap —
 * so a script's own `typeof budget !== 'undefined'` style guard still behaves.
 *
 * @param {string} source the workflow script body, with `export const meta` already neutralized
 * @returns {{invoke: (globals: Record<string, unknown>) => Promise<unknown>, escapes: Array<object>}}
 * @throws {SyntaxError} when the body does not parse
 */
export function compileWorkflowBody(source) {
  const probe = createCapabilityProbe()
  const fn = new AsyncFunction(...RUNNER_GLOBALS, ...probe.names, String(source))
  return {
    escapes: probe.escapes,
    invoke: (globals = {}) => fn(...RUNNER_GLOBALS.map((n) => globals[n]), ...probe.values),
  }
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
