// ssbd-annexb — the separator set was widened five times by EXAMPLE, and each widening
// fell to the same class one step out: line-scan → newline → `/* */` → Annex B `<!--`.
//
// THIS SUITE IS NOT DERIVED FROM AN ATTACK LIST. It is derived from the GRAMMAR, which is
// the only thing that makes a completeness claim checkable:
//
//   * ECMA-262 §12.2 WhiteSpace, §12.3 LineTerminator — the whole of both, code point by
//     code point, including the ones nobody has ever attacked (<VT>, <FF>, <ZWNBSP>, every
//     Space_Separator, <LS>, <PS>).
//   * ECMA-262 §12.4 Comment as extended by Annex B.1.1 — ALL FIVE alternatives:
//     MultiLineComment, SingleLineComment, SingleLineHTMLOpenComment,
//     SingleLineHTMLCloseComment, SingleLineDelimitedComment.
//   * ECMA-262 §12.7.1 IdentifierName — a name may be spelled with UnicodeEscapeSequences
//     and denotes the same binding. That is a different production from the separators and
//     it is tested as one.
//
// Every case is first handed to `node --check` as a Script. A case the parser REJECTS is
// not an evasion and is not asserted against; a case it ACCEPTS is source the runner can
// be handed, and the checker must refuse it. That coupling is what stops this suite from
// degenerating into another list of things somebody thought of.
//
// The separator cases are generated as the CROSS PRODUCT of every production above with
// every forbidden construct that has a token/token seam, so a production added to
// SEPARATOR_PRODUCTIONS without a case here fails the completeness test at the bottom.

import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { SEPARATOR_PRODUCTIONS, findForbiddenConstructs } from '../../scripts/workflow-runner-constraints.mjs'

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'atw-grammar-'))

/** True when V8 accepts `src` as a Script — the same dialect the runner's probe uses. */
function parsesAsScript(src) {
  const file = path.join(TMP, `probe-${Math.random().toString(36).slice(2)}.cjs`)
  fs.writeFileSync(file, src)
  try {
    execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' })
    return true
  } catch {
    return false
  } finally {
    fs.rmSync(file, { force: true })
  }
}

// ── §12.2 WhiteSpace and §12.3 LineTerminator, exhaustively ──────────────────
//
// `\s` is DEFINED by §22.2.2.9 as WhiteSpace ∪ LineTerminator, so the checker does not
// enumerate them — but this suite does, so that the definition is actually exercised
// rather than merely cited. Space_Separator (Zs) is listed in full.
const WHITESPACE_CODE_POINTS = Object.freeze({
  '<TAB> U+0009': '\u0009',
  '<VT> U+000B': '\u000B',
  '<FF> U+000C': '\u000C',
  '<ZWNBSP> U+FEFF': '\uFEFF',
  'Zs U+0020 SPACE': '\u0020',
  'Zs U+00A0 NBSP': '\u00A0',
  'Zs U+1680 OGHAM SPACE MARK': '\u1680',
  'Zs U+2000 EN QUAD': '\u2000',
  'Zs U+2001 EM QUAD': '\u2001',
  'Zs U+2002 EN SPACE': '\u2002',
  'Zs U+2003 EM SPACE': '\u2003',
  'Zs U+2004 THREE-PER-EM SPACE': '\u2004',
  'Zs U+2005 FOUR-PER-EM SPACE': '\u2005',
  'Zs U+2006 SIX-PER-EM SPACE': '\u2006',
  'Zs U+2007 FIGURE SPACE': '\u2007',
  'Zs U+2008 PUNCTUATION SPACE': '\u2008',
  'Zs U+2009 THIN SPACE': '\u2009',
  'Zs U+200A HAIR SPACE': '\u200A',
  'Zs U+202F NARROW NBSP': '\u202F',
  'Zs U+205F MEDIUM MATHEMATICAL SPACE': '\u205F',
  'Zs U+3000 IDEOGRAPHIC SPACE': '\u3000',
})

const LINE_TERMINATORS = Object.freeze({
  '<LF> U+000A': '\u000A',
  '<CR> U+000D': '\u000D',
  '<CR><LF> sequence': '\u000D\u000A',
  '<LS> U+2028': '\u2028',
  '<PS> U+2029': '\u2029',
})

// ── The forbidden constructs, written as (head, seam, tail) ──────────────────
//
// `seam` is where a separator may be inserted. `requiresSeparator` marks the seams the
// grammar REQUIRES a separator at, so a zero-width production is not asserted there.
const CONSTRUCTS = Object.freeze([
  { name: 'dynamic import', head: 'const x = import', tail: '("node:fs")\n' },
  { name: 'require()', head: 'const x = require', tail: '("node:fs")\n' },
  { name: 'require.resolve', head: 'const x = require', tail: '.resolve("node:fs")\n' },
  { name: 'process', head: 'const x = process', tail: '.env\n' },
  { name: 'new Function', head: 'const x = new', tail: 'Function("return 1")\n', requiresSeparator: true },
])

/**
 * The separator text for one production, spelled so it is legal at a token seam.
 * SingleLineHTMLCloseComment carries its own leading LineTerminatorSequence, because the
 * grammar only admits `-->` after one.
 */
const SEPARATOR_SAMPLES = Object.freeze({
  'WhiteSpace ∪ LineTerminator (§12.2, §12.3)': ' \n\t',
  'MultiLineComment (§12.4)': '/* a\n b */',
  'SingleLineDelimitedComment (Annex B.1.1)': '/* a */',
  'SingleLineComment (§12.4)': '// a\n',
  'SingleLineHTMLOpenComment (Annex B.1.1)': '<!-- a\n',
  'SingleLineHTMLCloseComment (Annex B.1.1)': '\n--> a\n',
})

for (const [production, separator] of Object.entries(SEPARATOR_SAMPLES)) {
  for (const construct of CONSTRUCTS) {
    const src = `${construct.head}${separator}${construct.tail}`
    test(`${production} between the tokens of ${construct.name} is refused`, () => {
      assert.ok(parsesAsScript(src), 'the case must be real JavaScript, or it proves nothing')
      const found = findForbiddenConstructs(src)
      assert.ok(found.length > 0, `${JSON.stringify(src)} parses and must be refused`)
      assert.equal(found[0].name, construct.name)
    })
  }
}

// A production may appear MORE THAN ONCE at a seam, and the forms may be mixed. The
// grammar permits any sequence of them, so the checker must too.
test('an arbitrary MIXED sequence of every separator production at one seam is refused', () => {
  const seam = ` /* a */ <!-- b\n// c\n\t--> d\n/* e\n f */ `
  const src = `const x = import${seam}("node:fs")\n`
  assert.ok(parsesAsScript(src), 'the mixed sequence must be real JavaScript')
  assert.equal(findForbiddenConstructs(src)[0].name, 'dynamic import')
})

// ── §12.2 / §12.3 exhaustively, one case per code point ──────────────────────

for (const [label, ch] of Object.entries(WHITESPACE_CODE_POINTS)) {
  test(`WhiteSpace ${label} between the tokens of new Function is refused`, () => {
    const src = `const x = new${ch}Function("return 1")\n`
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    assert.equal(findForbiddenConstructs(src)[0].name, 'new Function')
  })
}

for (const [label, ch] of Object.entries(LINE_TERMINATORS)) {
  test(`LineTerminator ${label} between the tokens of a dynamic import is refused`, () => {
    const src = `const x = import${ch}("node:fs")\n`
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    assert.equal(findForbiddenConstructs(src)[0].name, 'dynamic import')
  })

  test(`LineTerminator ${label} terminates a SingleLineComment, so the code after it is still scanned`, () => {
    const src = `const a = 1 // a comment${ch}const x = process.env\n`
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    assert.equal(findForbiddenConstructs(src)[0].name, 'process')
  })

  test(`LineTerminator ${label} terminates a SingleLineHTMLOpenComment too`, () => {
    const src = `const a = 1 <!-- a comment${ch}const x = process.env\n`
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    assert.equal(findForbiddenConstructs(src)[0].name, 'process')
  })

  test(`LineTerminator ${label} licenses a following SingleLineHTMLCloseComment`, () => {
    const src = `const x = require${ch}--> a\n("node:fs")\n`
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    assert.equal(findForbiddenConstructs(src)[0].name, 'require()')
  })
}

// ── Annex B.1.1 HTMLCloseComment, in full ────────────────────────────────────
//
//   HTMLCloseComment :: WhiteSpaceSequence? SingleLineDelimitedCommentSequence? `-->` ...
//
// The two optional halves are what an example-driven fix would leave out.

test('HTMLCloseComment with a WhiteSpaceSequence before the arrow is refused', () => {
  const src = 'const x = import\n   \t--> a\n("node:fs")\n'
  assert.ok(parsesAsScript(src))
  assert.equal(findForbiddenConstructs(src)[0].name, 'dynamic import')
})

test('HTMLCloseComment with a SingleLineDelimitedCommentSequence before the arrow is refused', () => {
  const src = 'const x = import\n /*a*/ /*b*/ --> c\n("node:fs")\n'
  assert.ok(parsesAsScript(src))
  assert.equal(findForbiddenConstructs(src)[0].name, 'dynamic import')
})

test('a MultiLineComment carrying a LineTerminator also licenses the arrow', () => {
  const src = 'const x = import/*a\nb*/ --> c\n("node:fs")\n'
  assert.ok(parsesAsScript(src))
  assert.equal(findForbiddenConstructs(src)[0].name, 'dynamic import')
})

test('`-->` after CODE on the same line is NOT a comment, and V8 agrees', () => {
  // `a-- > b` — the grammar does not admit HTMLCloseComment here, so this is not an
  // evasion route. Pinned so a future widening that accepted it would be visible.
  assert.equal(parsesAsScript('var a = 1;\nvar b = 2; --> x\n'), false)
})

// ── §12.7.1 IdentifierName UnicodeEscapeSequence — the SPELLING production ───
//
// A ReservedWord may not be escaped, so `import` cannot hide this way. Every other
// forbidden name is an ordinary IdentifierName and can.

const ESCAPED = Object.freeze([
  { name: 'require()', src: 'const x = \\u0072equire("node:fs")\n' },
  { name: 'require()', src: 'const x = requ\\u0069re("node:fs")\n' },
  { name: 'require()', src: 'const x = \\u{72}equire("node:fs")\n' },
  { name: 'require.resolve', src: 'const x = require.\\u0072esolve("node:fs")\n' },
  { name: 'process', src: 'const x = \\u0070rocess.env\n' },
  { name: 'new Function', src: 'const x = new \\u0046unction("return 1")\n' },
  { name: 'globalThis', src: 'const x = \\u0067lobalThis\n' },
  { name: '__dirname / __filename', src: 'const x = _\\u005Fdirname\n' },
])

for (const { name, src } of ESCAPED) {
  test(`an identifier escape spelling of ${name} is refused: ${JSON.stringify(src.trim()).slice(0, 52)}`, () => {
    assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
    const found = findForbiddenConstructs(src)
    assert.ok(found.length > 0, 'an escaped spelling denotes the same binding')
    assert.equal(found[0].name, name)
    assert.equal(found[0].via, 'escape-normalized', 'and the report says which pass caught it')
  })
}

test('an escaped spelling COMBINED with an Annex B separator is still refused', () => {
  const src = 'const x = \\u0072equire<!--evade\n("node:fs")\n'
  assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
  assert.equal(findForbiddenConstructs(src)[0].name, 'require()')
})

test('a `\\u` sequence inside a STRING is not decoded into a construct', () => {
  // The escape production applies to IdentifierName, not to string contents. Decoding
  // inside a string would invent a construct the source does not contain — a false
  // positive that would refuse a legitimate script.
  const src = 'const doc = "write \\\\u0072equire(x) to load a module"\nconst y = 1\n'
  assert.ok(parsesAsScript(src), 'the case must be real JavaScript')
  assert.deepEqual(findForbiddenConstructs(src), [], 'prose about a construct is not the construct')
})

// ── Completeness, mechanically ───────────────────────────────────────────────

test('every production the checker CLAIMS to cover has a case in this suite', () => {
  assert.deepEqual(
    Object.keys(SEPARATOR_PRODUCTIONS).sort(),
    Object.keys(SEPARATOR_SAMPLES).sort(),
    'a production added to SEPARATOR_PRODUCTIONS without a grammar case here is an untested claim',
  )
})

test('the 25 real workflow scripts stay clean under all three passes', () => {
  const dir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', '..', 'workflows')
  const files = fs.readdirSync(dir).filter((f) => f.endsWith('.js'))
  assert.ok(files.length >= 25, 'the corpus should not have shrunk')
  for (const file of files) {
    assert.deepEqual(findForbiddenConstructs(fs.readFileSync(path.join(dir, file), 'utf8')), [], `${file}`)
  }
})

test('the scan does not blow up on a long run of line terminators', () => {
  // The HTMLCloseComment alternative begins with a LineTerminatorSequence that `\s` can
  // also match. If that ambiguity were unbounded the scan would backtrack exponentially.
  const src = `const x = import${'\n'.repeat(4000)}notAParen\n`
  const started = Date.now()
  findForbiddenConstructs(src)
  assert.ok(Date.now() - started < 2000, 'the separator alternation must stay linear')
})
