export const meta = {
  name: 'tdd-red',
  description:
    'Shared-tail mini — TDD Red. Discovery is a LOOKUP that runs nothing: it reports which acceptance criteria already have a covering test, and writers are DERIVED from the contract\'s declared surfaces (unit always) rather than routed by an agent, with the test strategy inherited from the spec rather than re-ruled per task. Execution happens at Red confirmation only — the writers run what they author, and existing tests are executed just once, under a three-way verdict: red (reuse), already-satisfied (the behavior exists, nothing is authored and the phase reports up), or not-encoded (author against them). An independent coverage reviewer then checks the result against the acceptance criteria. Writes tests only — no production code.',
  phases: [{ title: 'Red', detail: 'author + confirm a failing test' }],
}

// args: {
//   contract:    <bug-triage output or spec contract>,
//   feedback?:   string,     // gate feedback from a previous attempt
//   skipDiscovery?: boolean, // force fresh authoring, bypassing existing-test reuse.
//                            // Use when the tests on disk are known bad — discovery
//                            // would otherwise report them as covering the contract.
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const c = a.contract || {}
// ── PATH SAFETY AT THIS MINI'S OWN BOUNDARY ─────────────────────────────────
//
// The contract repo path is interpolated below into `git -C "<path>"` command text inside
// prompts that agents are told to run exactly as written, and into the prompt PROSE those
// same agents read. Inside a composite the value arrives already validated by the
// workspace step — but this mini is separately dispatchable, and a contract handed
// straight to it has been through no workspace step at all. Then the unvalidated value is
// back, in the phases that WRITE CODE and DEPLOY.
//
// This is the argument 6.0.8 used to justify re-validating inside settle rather than
// trusting the composite, applied where it was left out. A guard that only exists on the
// composite path is a guard on one of the two ways in.
//
// The rule matches the workspace step's: an ALLOWLIST, not a blocklist of shell
// metacharacters. The target is a model reading a prompt as well as a shell parsing a
// line, and a path made only of permitted characters can still be a sentence addressed to
// the reader. No spaces and no colons — a worktree path this pipeline creates needs
// neither, and prose needs both. REFUSE, never sanitize: a rewritten path names a
// different tree and nobody would learn of the substitution.
//
// An ABSENT path is not a fault. It has always meant "no tree was established", the
// placeholder below is not attacker-controlled, and turning that into a refusal would
// change what this mini does rather than what it accepts.
const CONTRACT_PATH_SHAPE = /^\/[A-Za-z0-9._/-]+$/
const suppliedRepoPath = String(c.repoPath || (c.bead && c.bead.repoPath) || '').trim()
const contractPathFault = (() => {
  if (!suppliedRepoPath) return null
  if (!CONTRACT_PATH_SHAPE.test(suppliedRepoPath)) {
    const offending = Array.from(suppliedRepoPath).find((ch) => !/[A-Za-z0-9._/-]/.test(ch))
    return (
      `the contract repoPath ${JSON.stringify(suppliedRepoPath)} ` +
      (suppliedRepoPath.startsWith('/')
        ? `contains ${JSON.stringify(offending)}, which either reshapes the commands an agent is told to run verbatim or lets the path be read as a sentence addressed to that agent`
        : 'is not absolute, and every command in this phase runs as `git -C "<path>"`, which resolves a relative path against whatever tree the agent is standing in')
    )
  }
  if (suppliedRepoPath.includes('//') || suppliedRepoPath.endsWith('/')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} has an empty or trailing path segment; it is refused rather than normalized`
  }
  if (suppliedRepoPath.split('/').includes('..')) {
    return `the contract repoPath ${JSON.stringify(suppliedRepoPath)} contains a ".." segment, so the directory it names is not the directory it reads as`
  }
  return null
})()
if (contractPathFault) {
  return {
    ok: false,
    testFiles: [],
    redConfirmed: false,
    evidence: '',
    greenReachable: false,
    greenPathChecked: false,
    greenPathFindings: [],
    writers: [],
    surfaces: [],
    coverageGaps: [],
    blocked: [
      `${contractPathFault}. This phase refuses the contract rather than dispatching it: the path would ` +
        'already be inside the prompt by the time anyone could object.',
    ],
    ledger: { phase: 'red', beadId: (c.bead && c.bead.id) || null, chosen: [], mode: 'refused', ok: false },
  }
}

const repo = suppliedRepoPath || '(repo path not provided)'
const ac = Array.isArray(c.acceptanceCriteria) ? c.acceptanceCriteria : []
const affectedFiles = Array.isArray(c.affectedFiles) ? c.affectedFiles.filter(Boolean).map(String) : []

// The gate's objection must reach EVERY step that can decide to reuse a test, not just
// the writers. It previously reached only the writer prompt — so on a loop attempt the
// discovery step re-found the previous attempt's bad test, reported no gaps, and the
// confirm-existing branch handed the gate back the identical un-passable test through a
// code path the objection never touched.
const feedbackBlock = a.feedback
  ? `\n\nA GATE REJECTED THE PREVIOUS ATTEMPT AT THIS PHASE. Read this before deciding anything is already covered — a test the gate has objected to is NOT covering test, however well it matches by name:\n${a.feedback}`
  : ''

phase('Red')

const taskBlock = `${c.bead ? `Bug ${c.bead.id || ''}: ${c.bead.title || ''}` : 'Feature under test'}
Reproduction: ${c.reproduction || 'n/a'}
Root cause: ${c.rootCause || 'n/a'}
Affected files: ${(c.affectedFiles || []).join(', ') || 'n/a'}

Acceptance criteria to encode as tests:
${ac.length ? ac.map((x, i) => `${i + 1}. GIVEN ${x.given} WHEN ${x.when} THEN ${x.then}`).join('\n') : '(none — derive minimal coverage from the reproduction)'}`

// ── Writers: DERIVED from the contract's surfaces, not decided here ────────────
//
// Which surfaces a change touches is a semantic judgment, and it is made ONCE
// upstream by the agent that already reads the code — bug-triage's diagnostician,
// or spec authoring. It is not re-made here: a per-task routing turn cost a full
// subagent round-trip to answer a question the contract already answers, and for
// unit-only work the answer was fixed in advance anyway, since the unit generator
// is force-included regardless of what came back.
//
// The mapping below is a lookup, not a guess. Each surface is an upstream-declared
// enum value, so no keyword matching is inferring meaning from file paths here.
const SURFACE_WRITERS = {
  'api-contract': 'consumer-driven-contract-test-writer',
  'event-chain': 'aws-integration-test-writer',
  auth: 'security-test-case-designer',
  performance: 'performance-benchmark-writer',
  'web-ui': 'playwright-e2e-web-test-writer',
  ios: 'xcuitest-writer',
  android: 'espresso-test-writer',
  'cross-platform-mobile': 'mobile-e2e-test-writer',
  ml: 'ml-evaluation-tester',
  'data-pipeline': 'data-pipeline-test-writer',
}
const surfaces = (Array.isArray(c.surfaces) ? c.surfaces : []).map((s) => String(s || '').trim().toLowerCase())
const surfaceWriters = surfaces.map((s) => SURFACE_WRITERS[s]).filter(Boolean)
// Unit is unconditional: every contract has behavior to assert, whatever it touches.
const writersFinal = ['tdd-unit-test-generator', ...new Set(surfaceWriters)]
const selectionMode = surfaceWriters.length ? 'derived' : 'unit-only'
if (surfaces.length && !surfaceWriters.length) {
  log(`⚠ contract declared surfaces [${surfaces.join(', ')}] that map to no writer — authoring unit tests only`)
}
log(`Red writers (${selectionMode}): ${writersFinal.join(', ')}`)

// ── Strategy: INHERITED from the contract, never ruled per task ────────────────
//
// Pyramid shape, coverage threshold, and environment matrix are properties of the
// Story or the repository, not of one task. Ruling them per task did not just cost
// a turn — it let two tasks in the same Story inherit different thresholds, which
// is worse than not deciding at all. The decision still happens under the doctrine,
// once, where the Spec is authored; here it is only carried.
const strategy = c.testStrategy || null
const strategyBlock = strategy
  ? `\nTest strategy (inherited from the spec): pyramid=${strategy.pyramid || 'n/a'}; coverageThreshold=${strategy.coverageThreshold || 'n/a'}; envMatrix=${(strategy.envMatrix || []).join(', ') || 'n/a'}`
  : ''

// ── Discovery: is the contract ALREADY encoded? ────────────────────────────────
//
// Red is idempotent. A run that was interrupted, or re-dispatched after a gate
// loop, may find its tests already on disk from the previous attempt — they are
// real files, committed at deploy and inherited by every later run. Regenerating
// them wastes the most expensive phase in the pipeline and, worse, a second
// writer pass produces a parallel file covering the same behavior.
//
// The only decision at this point is AUTHOR or DON'T AUTHOR, and existence alone
// settles it. So this step RUNS NOTHING — it is a lookup. Whether a found test is
// actually Red is a different question, and it is answered by execution at Red
// confirmation: the writers run what they author, and the branch just below runs
// what discovery found. Executing here would re-answer, minutes early, what the
// next step answers regardless, and every first attempt would pay for it to guard
// a stale-test case that almost never fires. Deferred, the common case pays
// nothing and the rare case pays one loop.
const discovery = a.skipDiscovery === true
  ? null
  : await agent(
      `Before any test is written, establish what the repository ALREADY has. This is a LOOKUP, not an evaluation.

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`ls\`, \`git status\`, or relative path can inspect or write to the wrong copy of the repository entirely. Every path you read or write is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}${feedbackBlock}

Locate the test files that already encode the contract below — a previous attempt at this same work may have written them, or they may predate it. Search by the bead id, by the module under test, and by the behavior each criterion names.

COVERING THE CODE IS NOT ENCODING THE CONTRACT. A module usually has tests already; that does not mean this contract is encoded. The question is whether a test asserts the EXPECTED behavior stated in the criteria below — not whether the file under change is touched by some test. On a defect these come apart hardest: the existing tests assert the CURRENT behavior, which is the behavior being changed. Treat a criterion as covered only when an existing test would have to change for the criterion to be met.

DO NOT RUN ANYTHING. Do not invoke a test runner, a build, or a synth. Whether these tests currently pass or fail is not your question and you must not go looking — that is settled downstream by executing them. Report only what EXISTS.

List in gaps every acceptance criterion that has no covering test file. Those, and only those, will be authored.

${taskBlock}`,
      {
        label: 'red:discovery',
        phase: 'Red',
        effort: 'low',
        agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['existingTestFiles', 'gaps'],
          properties: {
            existingTestFiles: { type: 'array', items: { type: 'string' } },
            gaps: { type: 'array', items: { type: 'string' } },
            notes: { type: 'string' },
          },
        },
      }
    )

const foundFiles = (discovery && discovery.existingTestFiles) || []
const openGaps = (discovery && discovery.gaps) || []

// Every criterion already has a covering file, so there is nothing to author —
// but "it exists" is not "it is Red". THIS is where execution belongs, and it is
// the only place Red gets executed before authoring.
//
// The verdict is THREE-WAY, not a boolean, because the two non-red outcomes need
// opposite responses. Tests that pass while genuinely encoding this contract mean
// the expected behavior is ALREADY PRESENT — the defect is fixed, or was never
// real. There is no failing test to write, and sending that to the writers asks
// them to manufacture a red, which they can only do by asserting something false.
// That case ends the phase and reports upward. Only a contract that turns out NOT
// to be encoded — discovery saw neighbouring tests and over-claimed, or the
// failure is an unrelated harness break — goes on to authoring.
if (foundFiles.length && !openGaps.length) {
  const confirmation = await agent(
    `Discovery reports that existing tests already encode every acceptance criterion below. RUN THEM — only these files, never the wider suite — and rule on what you observe. Run everything against this tree, as \`git -C "${repo}"\` / with paths under it; a bare command may inspect a different copy of the repository:
${repo}${feedbackBlock}

${foundFiles.join('\n')}

Return exactly one verdict:

- "red": they FAIL, and the failures are the intended product failures for the criteria below. The contract is encoded and not yet satisfied.
- "already-satisfied": they PASS, and they genuinely assert the expected behavior in the criteria below. The behavior already exists — the defect is already fixed, or was never real. Rule this ONLY when the passing assertions actually match the criteria; it stops the work.
- "not-encoded": they do NOT actually assert the expected behavior in the criteria (they cover the same module or the current behavior instead), or they fail for an unrelated reason — an import error, a missing fixture, a broken harness. Discovery over-claimed and the contract still needs authoring.

Capture the executed output verbatim as evidence; a verdict with no output is not evidence. Do NOT write or repair any test.

${taskBlock}`,
    {
      label: 'red:confirm-existing',
      phase: 'Red',
      agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['verdict', 'evidence'],
        properties: {
          verdict: { type: 'string', enum: ['red', 'already-satisfied', 'not-encoded'] },
          evidence: { type: 'string' },
          staleFiles: { type: 'array', items: { type: 'string' } },
        },
      },
    }
  )

  // A verdict without executed output is a claim, and a claim may not skip work.
  const evidenced = !!(confirmation && String(confirmation.evidence || '').trim())
  const verdict = evidenced ? confirmation.verdict : 'not-encoded'

  if (verdict === 'red') {
    log(`Red already satisfied by existing tests: ${foundFiles.join(', ')} — skipping the writers`)
    return {
      testFiles: foundFiles,
      redConfirmed: true,
      evidence: confirmation.evidence,
      reusedExistingTests: true,
      // These tests were not authored here, so there is no greenPath declaration to
      // check. They were EXECUTED and observed red, and a loop attempt never reaches
      // this branch (the composite sets skipDiscovery from attempt 2), so a rejected
      // test cannot be laundered back through reuse.
      greenReachable: true,
      greenPath: [],
      greenPathChecked: false,
      strategy,
      coverage: { gaps: [], reviewed: 'discovery+confirmation' },
      ledger: { phase: 'red', chosen: writersFinal, mode: 'reused', ok: true },
    }
  }

  if (verdict === 'already-satisfied') {
    log(`Contract ALREADY SATISFIED by passing tests: ${foundFiles.join(', ')} — no Red is obtainable and nothing is authored`)
    return {
      testFiles: foundFiles,
      redConfirmed: false,
      alreadySatisfied: true,
      greenReachable: true,
      greenPath: [],
      greenPathChecked: false,
      evidence: confirmation.evidence,
      reusedExistingTests: true,
      strategy,
      coverage: { gaps: [], reviewed: 'discovery+confirmation' },
      ledger: { phase: 'red', chosen: writersFinal, mode: 'already-satisfied', ok: true },
    }
  }

  log(
    'Red confirmation: existing tests do NOT encode this contract' +
      `${evidenced ? `: ${String(confirmation.evidence).slice(0, 200)}` : ' (no executed evidence returned — treated as unencoded)'}. Writers will author against them.`
  )
}
if (foundFiles.length && openGaps.length) {
  log(`Red discovery: ${foundFiles.length} existing test file(s) found; ${openGaps.length} gap(s) remain — writers will EXTEND, not replace`)
}
const gapBlock = openGaps.length
  ? `\n\nThese criteria are the ONLY ones still needing coverage — the rest are already encoded by the existing tests listed below, which you must extend rather than duplicate:\nGaps: ${openGaps.join('; ')}\nExisting test files: ${foundFiles.join(', ') || 'none'}`
  : foundFiles.length
    ? `\n\nEvery criterion already has a covering test in the files below, but they were RUN and are NOT Red — stale, wrong, or failing for an unrelated reason. Fix the coverage by extending these files; do NOT create parallel ones:\n${foundFiles.join(', ')}`
    : ''

// Each selected writer authors its tests and confirms Red — different test files, so
// they run concurrently (unlike production-code writers).
const RED_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['testFiles', 'redConfirmed', 'evidence', 'greenPath'],
  properties: {
    testFiles: { type: 'array', items: { type: 'string' } },
    redConfirmed: { type: 'boolean' },
    evidence: { type: 'string' },
    // ── THE GREEN-REACHABILITY DECLARATION ───────────────────────────────────
    // Red proves a test fails NOW. Nothing here used to ask whether a PASS is
    // reachable, so a test pinned to the PRE-FIX import path — one that can never go
    // green no matter how correct the production change is — was indistinguishable
    // from a correct Red and was certified as one. Naming the production file and
    // symbol whose change makes each test pass turns that into a set comparison the
    // script can settle with no model turn.
    greenPath: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['testFile', 'targetFile', 'targetSymbol', 'assertionSubject'],
        properties: {
          testFile: { type: 'string' },
          targetFile: { type: 'string' },
          targetSymbol: { type: 'string' },
          assertionSubject: { type: 'string' },
        },
      },
    },
    notes: { type: 'string' },
  },
}
const writerResults = (await parallel(writersFinal.map((w) => () =>
  agent(
    `Write the failing test(s) that encode the expected behavior below, then RUN them and confirm they FAIL for the intended reason (Red). Write test code ONLY — do not change production code. You are '${w}' — author only the tests of your specialty.

PIN YOURSELF TO THE RIGHT TREE FIRST. You may be running in an isolation worktree, so a bare \`git status\`, a relative path, or an editor's idea of the project root can inspect — or WRITE TO — the wrong copy of the repository. Every file you create or modify is under this tree, and every git command runs as \`git -C "${repo}"\`:
${repo}

FIND THE EXISTING SUITE BEFORE YOU WRITE. These tests are permanent: they are committed and every later run inherits them. Locate the file that already covers this module or behavior and ADD to it, matching its imports, fixtures, naming, and helpers. Create a new file only when nothing covers this area yet.

ASSERT AGAINST WHAT THE CODE PRODUCES, NOT A COMMITTED ARTIFACT. Synthesize, build, or render the thing under test as part of the test run. A test that reads a checked-in build output — a committed cdk.out template, a generated client, a snapshot nobody regenerates — passes forever no matter what the code does, and it will not fail when the defect returns. If half a suite synthesizes in process and half reads a committed file, the two halves are testing different artifacts and the suite is lying about what it covers.

A second file covering the same behavior is worse than no test at all — the suite gets slower, and a failure no longer tells anyone which expectation is the real one. If you find an existing test that is WRONG rather than missing, say so in your evidence and leave it alone; repairing it is not yours to do.

${taskBlock}

${strategyBlock}${gapBlock}
${a.feedback ? `\nGate feedback from the previous attempt — address it:\n${a.feedback}` : ''}

DECLARE THE PATH TO GREEN. For every test you author, name the PRODUCTION file and symbol whose change will make it pass, and what the test actually asserts about that symbol. This is not paperwork: a test whose mock is patched at the module path the code used BEFORE the fix fails perfectly and can never go green, and this declaration is the only thing that distinguishes it from a correct Red. The targetFile must be a production file this change will actually touch${affectedFiles.length ? ` — the contract names these: ${affectedFiles.join(', ')}` : ''}. If you cannot name one, you have not written a test the fix can satisfy.

Deliver: the test file paths you created/modified, whether Red is confirmed, the greenPath declaration, and the captured failing output as evidence.`,
    {
      label: `red:${w}`,
      phase: 'Red',
      agentType: `agent-teams-workforce:${w}`,
      schema: RED_SCHEMA,
    }
  )
))).filter(Boolean)

const testFiles = writerResults.flatMap((r) => (r && r.testFiles) || [])
const redConfirmed = writerResults.length > 0 && writerResults.every((r) => r && r.redConfirmed)
const evidence = writerResults.map((r) => r && r.evidence).filter(Boolean).join('\n---\n')

// ── Green reachability, settled in script ─────────────────────────────────────
//
// Zero model turns. Two tiers, and which one applies depends on whether the contract
// declared the files the fix must change:
//   • affectedFiles declared (the bug path — bug-triage always supplies them): every
//     targetFile must resolve to one of them. A mock patched at the pre-fix module path
//     names a file the fix does not touch, and dies here.
//   • affectedFiles absent: the declaration itself is still required — every authored
//     test file must name a production file and symbol whose change makes it pass. A
//     writer that cannot name one has not written a test the fix can satisfy.
const greenPath = writerResults.flatMap((r) => (r && Array.isArray(r.greenPath) ? r.greenPath : []))
function normPath(p) {
  return String(p || '').trim().replace(/^\.\//, '').replace(/^\/+/, '')
}
function sameFile(x, y) {
  const nx = normPath(x)
  const ny = normPath(y)
  if (!nx || !ny) return false
  return nx === ny || nx.endsWith(`/${ny}`) || ny.endsWith(`/${nx}`)
}
const greenPathFindings = []
for (const entry of greenPath) {
  if (!String(entry.targetFile || '').trim() || !String(entry.targetSymbol || '').trim()) {
    greenPathFindings.push(`${entry.testFile || '(unnamed test)'}: named no production file/symbol whose change makes it pass`)
    continue
  }
  if (affectedFiles.length && !affectedFiles.some((f) => sameFile(f, entry.targetFile))) {
    greenPathFindings.push(
      `${entry.testFile || '(unnamed test)'}: targets ${entry.targetFile} (${entry.targetSymbol}), which the contract does not list among the files the fix changes (${affectedFiles.join(', ')}). A test pinned to a path the fix does not touch cannot go green.`
    )
  }
}
const declaredFor = new Set(greenPath.map((e) => normPath(e.testFile)))
for (const f of testFiles) {
  if (!declaredFor.has(normPath(f))) greenPathFindings.push(`${f}: no greenPath entry — the test declares no route to green`)
}
const greenReachable = redConfirmed && greenPathFindings.length === 0
if (greenPathFindings.length) {
  log(`⚠ Red: ${greenPathFindings.length} test(s) declare no reachable path to green — ${greenPathFindings.join(' | ')}`)
}

// Independent coverage check — every acceptance criterion has a covering test. The
// reviewer authors no tests; it only judges.
const coverage = await agent(
  `You are the test-coverage-gap-reviewer — INDEPENDENT of the test writers. Check the authored tests against the acceptance criteria; flag any criterion with no covering test. Do NOT write tests.

Acceptance criteria:
${ac.length ? ac.map((x, i) => `${i + 1}. GIVEN ${x.given} WHEN ${x.when} THEN ${x.then}`).join('\n') : '(none)'}

Authored test files: ${testFiles.join(', ') || 'none'}`,
  {
    label: 'red:coverage',
    phase: 'Red',
    agentType: 'agent-teams-workforce:test-coverage-gap-reviewer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['gaps'],
      properties: { gaps: { type: 'array', items: { type: 'string' } } },
    },
  }
)

// test-design-lead and test-strategy-decider no longer run here: writers are
// derived from the contract's declared surfaces and the strategy is inherited
// from the spec, so neither is a choice this phase makes.
const ledger = {
  phase: 'red',
  beadId: (c.bead && c.bead.id) || null,
  chosen: [...writersFinal, 'test-coverage-gap-reviewer'],
  mode: selectionMode,
  ok: redConfirmed,
}

return {
  testFiles,
  redConfirmed,
  evidence,
  greenPath,
  greenReachable,
  greenPathChecked: true,
  greenPathFindings,
  writers: writersFinal,
  surfaces,
  strategy,
  coverageGaps: (coverage && coverage.gaps) || [],
  ledger,
}
