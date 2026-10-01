export const meta = {
  name: 'task-to-deploy',
  description:
    "Builds a Task from its build contract on its Story's branch and commits it only when the repository's whole test suite passes. Establishes (or reuses) the Story's worktree, stashing a reused tree's uncommitted changes; for an infrastructure Task authors the provisioning intent; runs the suite command the repository declares once as a baseline; loops Red until a new test fails with no new collection error and no regression; loops Green until the whole suite exits 0, routing tests the implementer names to Red in update mode; refactors, restoring the pre-refactor snapshot when the suite goes red; updates the documentation; then commits to the Story branch after a final green run. Stops with red-unsatisfied, blocked-upstream or no-progress when the contract cannot be built. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree every writing phase operates in" },
    { title: 'Infra Intent', detail: 'authors the provisioning intent for an infrastructure Task' },
    { title: 'Baseline', detail: "resolves the repository's suite command and runs it before any change" },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'runs the suite a final time and commits the Task to the Story branch' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, repoPath, story: { id, title? }, type?, labels?, title?, description?, specPath?, specPaths?, specSections?,
//           requirementIds?, definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy? },
//   infraVocabulary: { types, labels } (the plugin's scripts/infra-vocabulary.json),
//   spec?: object (defaults to bead), implementer?: string, worktreeRoot?: string,
//   maxRedRounds?: number (default 4), maxGreenRounds?: number (default 8)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
const MAX_RED_ROUNDS = a.maxRedRounds || 4
const MAX_GREEN_ROUNDS = a.maxGreenRounds || 8
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const TAIL_CHARS = 4000

// An infrastructure Task, by the same type and label test route-build applies.
const norm = (v) => String(v || '').trim().toLowerCase()
const vocabulary = a.infraVocabulary || {}
const INFRA_TYPES = (Array.isArray(vocabulary.types) ? vocabulary.types : []).map(norm).filter(Boolean)
const INFRA_LABELS = (Array.isArray(vocabulary.labels) ? vocabulary.labels : []).map(norm).filter(Boolean)
const beadLabels = (Array.isArray(bead.labels) ? bead.labels : []).map(norm)
const isInfra = INFRA_TYPES.includes(norm(bead.type)) || beadLabels.some((l) => INFRA_LABELS.includes(l))

if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied' }
if (!INFRA_TYPES.length || !INFRA_LABELS.length) {
  return { ok: false, stage: 'input', error: 'no infraVocabulary supplied: pass the types and labels from scripts/infra-vocabulary.json' }
}

const runLedger = []
let runDetail = null
let workspaceOut = null

// Logs the journal payload as `RUN-JOURNAL {json}`, or as `RUN-JOURNAL-PART i/n <chunk>` lines when
// it exceeds JOURNAL_CHUNK characters; the host concatenates the parts and writes the journal file.
const JOURNAL_CHUNK = 4000
function emitRunJournal(payload) {
  const body = JSON.stringify(payload)
  if (body.length <= JOURNAL_CHUNK) {
    log(`RUN-JOURNAL ${body}`)
    return
  }
  const parts = []
  for (let i = 0; i < body.length; ) {
    let end = Math.min(i + JOURNAL_CHUNK, body.length)
    const last = body.charCodeAt(end - 1)
    if (end < body.length && last >= 0xd800 && last <= 0xdbff) end -= 1
    parts.push(body.slice(i, end))
    i = end
  }
  parts.forEach((part, i) => log(`RUN-JOURNAL-PART ${i + 1}/${parts.length} ${part}`))
}
function persistRun(outcome) {
  if (!runLedger.length && !runDetail) return null
  try {
    emitRunJournal({ composite: 'task-to-deploy', bead: null, subject: bead.id || null, outcome, runLedger, detail: runDetail })
  } catch (e) {
    log(`run journal could not be serialized: ${e && e.message ? e.message : e}`)
  }
  return null
}

let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// Returns the caller-facing result; `detail` goes to the run journal only.
function handback(ok, stage, headline, detail) {
  runDetail = detail === undefined ? null : detail
  return {
    ok,
    stage,
    beadId: bead.id || null,
    storyId: story.id || null,
    headline: String(headline || ''),
    branch: (workspaceOut && workspaceOut.branch) || null,
    worktree: (workspaceOut && workspaceOut.repoPath) || null,
  }
}

// Returns the stage for a failed phase result: dispatch failure, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : stage)

function implementersOf(artifact) {
  const l = artifact && artifact.ledger
  return l && (l.mode === 'selected' || l.mode === 'reused') && Array.isArray(l.chosen) && l.chosen.length ? l.chosen : undefined
}

const list = (v) => (Array.isArray(v) ? v.filter(Boolean) : [])

// A suite-run failure, { kind: test | load, file, test, line }, keyed the same way in every run.
const entryOf = (f) =>
  f && typeof f === 'object'
    ? { kind: f.kind === 'load' ? 'load' : 'test', file: String(f.file || '').trim().replace(/^\.\//, ''), test: String(f.test || '').trim(), line: String(f.line || '').trim() }
    : null
const idOf = (e) => `${e.kind}|${e.file}|${e.test}`
const describe = (e) => (e.kind === 'load' ? `${e.file || e.line} could not be loaded` : `${e.file}${e.test ? ` ${e.test}` : ''}`)
const failures = (run) => {
  const byId = new Map()
  for (const e of list(run && run.failing).map(entryOf)) if (e && (e.file || e.test)) byId.set(idOf(e), e)
  return byId
}
const failingIds = (run) => new Set(failures(run).keys())
const sameFile = (p, f) => {
  const x = String(p || '').replace(/^\.\//, '')
  const y = String(f || '').replace(/^\.\//, '')
  return !!x && !!y && (x === y || x.endsWith(`/${y}`) || y.endsWith(`/${x}`))
}

// The runner's report as feedback text for the next session.
const runText = (run) =>
  [
    `The suite runner ran \`${(run && run.command) || '(no command)'}\` and it exited ${run ? run.exitCode : 'with no result'}.`,
    run && run.summary ? `Summary: ${run.summary}` : '',
    failures(run).size ? `Failing:\n${[...failures(run).values()].map((e) => e.line || describe(e)).join('\n')}` : '',
    run && run.tail ? `Output (last part):\n${String(run.tail).slice(-TAIL_CHARS)}` : '',
  ]
    .filter(Boolean)
    .join('\n')

const validRun = (r) => !!r && !r.dispatchFailed && Number.isInteger(r.exitCode) && r.exitCode >= 0

const shq = (p) => `'${String(p).replace(/'/g, "'\\''")}'`
const FINGERPRINT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['exitCode', 'stdout'],
  properties: { exitCode: { type: 'integer' }, stdout: { type: 'string' } },
}
/** Returns { files: { <path>: <git blob hash or "missing"> } } for the given test files in the tree, or { error }. */
async function fingerprint(tree, files, label) {
  if (!files.length) return { files: {} }
  const command = `cd ${shq(tree)} && for f in ${files.map(shq).join(' ')}; do if [ -f "$f" ]; then printf '%s\\t%s\\n' "$f" "$(git hash-object -- "$f")"; else printf '%s\\tmissing\\n' "$f"; fi; done`
  let out = null
  try {
    out = await agent(
      `Run exactly this one shell command, once, and change nothing else:

${command}

Return its exit code as \`exitCode\` and everything it printed on stdout, verbatim, as \`stdout\`. Do not retry, do not repair, do not run any other command.`,
      { label, phase: currentPhase || 'Green', model: 'haiku', effort: 'low', schema: FINGERPRINT_SCHEMA }
    )
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 300) }
  }
  if (!out || out.exitCode !== 0) return { error: `the fingerprint of the test files did not run${out ? `: exit ${out.exitCode}` : ''}` }
  const got = {}
  for (const row of String(out.stdout || '').split('\n')) {
    const [f, h] = row.split('\t')
    if (f && h) got[f.trim()] = h.trim()
  }
  const missing = files.filter((f) => !(f in got))
  return missing.length ? { error: `the fingerprint names no hash for ${missing.join(', ')}` } : { files: got }
}

let result
try {
  result = await (async () => {
    if (!String(bead.repoPath || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} carries no repoPath, so its build contract is incomplete. The repository is ruled during elaboration: re-elaborate the Task's Story, or record the repository on the Task as its repoPath.`),
        incompleteContract: ['repoPath'],
        requiredHumanActions: [`re-elaborate the Story of ${bead.id}, or record the ruled repository on it as its repoPath`],
      }
    }
    if (!String(story.id || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} names no Story. A Task is built on its Story's branch and deploys with its Story, so it needs one: parent it to the Story of its repository.`),
        incompleteContract: ['story'],
        requiredHumanActions: [`parent ${bead.id} to the Story of its repository`],
      }
    }

    enterPhase('Workspace')
    const workspace = await workflow('agent-teams-workforce:workspace', {
      repoPath: bead.repoPath,
      beadId: story.id,
      branchPrefix: 'story',
      purpose: story.title || `Story ${story.id}`,
      worktreeRoot: a.worktreeRoot,
      stashUncommitted: true,
      stashLabel: bead.id,
    })
    if (!workspace || workspace.ok !== true || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked[0]) || 'the workspace step returned nothing'
      return handback(false, stageOf('workspace', workspace), `no worktree was established: ${why}`, { workspace: workspace || null })
    }
    workspaceOut = workspace
    const workRepoPath = workspace.repoPath
    if (workspace.ledger) runLedger.push(workspace.ledger)

    const declaredSurfaces = Array.isArray(bead.surfaces) ? bead.surfaces : null
    const structuralSurfaces = [
      bead.apiSpec ? 'api-contract' : null,
      Array.isArray(bead.eventContracts) && bead.eventContracts.length ? 'event-chain' : null,
    ].filter(Boolean)
    const contractSurfaces = declaredSurfaces
      ? [...new Set([...declaredSurfaces, ...structuralSurfaces])]
      : structuralSurfaces.length
        ? structuralSurfaces
        : null
    const contract = {
      spec,
      bead: { id: bead.id, title: bead.title || null, description: bead.description || null, repoPath: workRepoPath },
      repoPath: workRepoPath,
      acceptanceCriteria: Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria : [],
      decisionIds: [
        ...new Set(
          [...(Array.isArray(spec && spec.decisionIds) ? spec.decisionIds : []), ...(Array.isArray(bead.decisionIds) ? bead.decisionIds : [])]
            .map((x) => String(x || '').trim())
            .filter(Boolean)
        ),
      ],
      surfaces: contractSurfaces,
      testStrategy: bead.testStrategy && typeof bead.testStrategy === 'object' ? bead.testStrategy : null,
    }

    let intent = null
    if (isInfra) {
      enterPhase('Infra Intent')
      intent = await workflow('agent-teams-workforce:infra-intent', {
        change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
      })
      if (!intent || !intent.provisioningIntent) {
        return handback(false, stageOf('infra-intent', intent), `infra-intent: ${(intent && intent.reason) || 'no provisioning intent was produced'}`, { intent: intent || null })
      }
      const stacks = Array.isArray(intent.affectedStacks) ? intent.affectedStacks : []
      contract.affectedStacks = stacks
      contract.provisioningIntent = intent.provisioningIntent
      contract.acceptanceCriteria = [
        ...contract.acceptanceCriteria.filter(Boolean),
        {
          given: `the provisioning intent for ${bead.title || 'this infrastructure change'} on stacks ${stacks.join(', ') || '(affected stacks)'}`,
          when: 'cdk synth runs against the changed stacks',
          then: 'the synthesized template asserts the intended resources and their properties, the cross-stack references the stacks write and read, and the IAM permissions the intent names',
        },
      ]
    }
    const implementer = a.implementer || (isInfra ? 'cdk-stack-author' : undefined)

    // ── Baseline: the suite command the repository declares, resolved once and reused ──
    enterPhase('Baseline')
    const baseline = await workflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, label: 'baseline' })
    if (baseline && baseline.resolveError) {
      return {
        ...handback(false, 'baseline', `baseline: ${workRepoPath} declares no test command (${baseline.resolveError}). A Task is committed only when the repository's whole suite passes, so the repository must say how its suite runs.`, { baseline }),
        requiredHumanActions: [`declare the command that runs the whole test suite in the AGENTS.md or CLAUDE.md of the repository at ${bead.repoPath}, or as the \`test\` task in its Taskfile`],
      }
    }
    if (!validRun(baseline) || !String(baseline.command || '').trim()) {
      return handback(false, stageOf('baseline', baseline), `baseline: the suite runner returned no exit code: ${(baseline && baseline.reason) || 'no result'}`, { baseline: baseline || null })
    }
    const suiteCommand = String(baseline.command).trim()
    contract.suiteCommand = suiteCommand
    const baselineIds = failingIds(baseline)
    const runSuite = async (label) => {
      const r = await workflow('agent-teams-workforce:suite-run', { repoPath: workRepoPath, command: suiteCommand, label })
      return r || null
    }
    log(`Baseline: \`${suiteCommand}\` exited ${baseline.exitCode}; ${baselineIds.size} failing before any change`)

    // ── Red: loops until a new test fails, with no new collection error and no regression ──
    const redFiles = []
    const addRedFiles = (r) => {
      for (const f of list(r && r.testFiles).map(String)) if (!redFiles.includes(f)) redFiles.push(f)
    }
    const judgeRed = (run) => {
      const inRedFile = (e) => redFiles.some((f) => sameFile(e.file, f))
      const fresh = [...failures(run).entries()].filter(([id]) => !baselineIds.has(id)).map(([, e]) => e)
      const collection = fresh.filter((e) => e.kind === 'load').map(describe)
      const redFails = fresh.filter((e) => e.kind === 'test' && inRedFile(e)).map(describe)
      const regressions = fresh.filter((e) => e.kind === 'test' && !inRedFile(e)).map(describe)
      const reasons = [
        redFails.length ? '' : 'no test in a file Red wrote or edited fails',
        collection.length ? `test files that no longer load: ${collection.join('; ')}` : '',
        regressions.length ? `tests outside Red's files that did not fail at baseline now fail: ${regressions.join('; ')}` : '',
      ].filter(Boolean)
      return { ok: run.exitCode !== 0 && !reasons.length, reasons, redFails, collection, regressions }
    }

    let red = null
    let redRun = null
    let redFeedback = ''
    let previousRedKey = null
    for (let round = 1; ; round++) {
      enterPhase('Red')
      red = await workflow('agent-teams-workforce:tdd-red', {
        contract,
        feedback: redFeedback,
        ...(redFiles.length ? { red: { testFiles: [...redFiles] } } : {}),
      })
      if (red && red.ledger) runLedger.push(red.ledger)
      if (!red || red.dispatchFailed) {
        return handback(false, stageOf('red', red), `red: ${(red && red.reason) || 'the Red phase returned nothing'}`, { red })
      }
      addRedFiles(red)
      redRun = await runSuite(`red-${round}`)
      if (!validRun(redRun)) {
        return handback(false, stageOf('red', redRun), `red: the suite runner returned no exit code: ${(redRun && redRun.reason) || 'no result'}`, { red, run: redRun })
      }
      const verdict = judgeRed(redRun)
      if (verdict.ok) {
        log(`Red: round ${round} satisfied — ${verdict.redFails.length} new failing test(s) in Red's files`)
        break
      }
      log(`Red: round ${round} not satisfied — ${verdict.reasons.join('; ')}`)
      if (round >= MAX_RED_ROUNDS) {
        return {
          ...handback(
            false,
            'red-unsatisfied',
            `red-unsatisfied: after ${round} Red round(s) the suite does not show the Task's new tests failing cleanly: ${verdict.reasons.join('; ')}`,
            { red, run: redRun, verdict, baseline }
          ),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      // A round whose suite fails exactly as the round before gives Red the same input again.
      const redKey = JSON.stringify([redRun.exitCode, ...[...failingIds(redRun)].sort(), ...verdict.reasons])
      if (redKey === previousRedKey) {
        return {
          ...handback(false, 'no-progress', `no-progress: Red round ${round} left the suite exactly as the round before: ${verdict.reasons.join('; ')}`, { red, run: redRun, verdict }),
          evidence: runText(redRun).slice(0, TAIL_CHARS),
        }
      }
      previousRedKey = redKey
      redFeedback = `The suite does not show Red yet: ${verdict.reasons.join('; ')}.\n${runText(redRun)}`
      runLedger.push({ phase: 'retry:red', round: round + 1, whatChanged: `Red round ${round + 1} is given round ${round}'s suite result: ${verdict.reasons.join('; ')}` })
    }

    // ── Green: loops until the whole suite exits 0 ──
    const baselineNote = baselineIds.size
      ? `\nThe suite already failed before this Task on: ${[...failures(baseline).values()].map(describe).join('; ')}. Green means the whole suite exits 0, so these must pass too.`
      : ''
    let green = null
    let finalRun = null
    let greenFeedback = `${runText(redRun)}${baselineNote}`
    let previousKey = null
    let testPrint = null
    for (let round = 1; ; round++) {
      enterPhase('Green')
      testPrint = await fingerprint(workRepoPath, [...redFiles], `green-${round}:tests-before`)
      if (testPrint.error) return handback(false, 'green', `green: Red's test files could not be fingerprinted before Green round ${round}: ${testPrint.error}`, {})
      const g = await workflow('agent-teams-workforce:tdd-green', {
        contract,
        red: { ...red, testFiles: [...redFiles], evidence: runText(redRun) },
        implementer,
        implementers: implementersOf(green),
        feedback: greenFeedback,
      })
      if (g && g.ledger) runLedger.push(g.ledger)
      if (!g || g.dispatchFailed) {
        return handback(false, stageOf('green', g), `green: ${(g && g.reason) || 'the Green phase returned nothing'}`, { green: g })
      }
      green = g
      const testsAfter = await fingerprint(workRepoPath, Object.keys(testPrint.files), `green-${round}:tests-after`)
      if (testsAfter.error) return handback(false, 'green', `green: Red's test files could not be fingerprinted after Green round ${round}: ${testsAfter.error}`, { green: g })
      const touchedTests = Object.keys(testPrint.files).filter((f) => testPrint.files[f] !== testsAfter.files[f])
      if (touchedTests.length) {
        return handback(
          false,
          'green-modified-tests',
          `green-modified-tests: Green round ${round} changed test files Red wrote, which Green leaves to Red (a test Green believes is wrong goes in testIssues): ${touchedTests.join(', ')}`,
          { green: g, touchedTests }
        )
      }
      let run = await runSuite(`green-${round}`)
      if (!validRun(run)) {
        return handback(false, stageOf('green', run), `green: the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { green: g, run })
      }
      if (run.exitCode === 0) {
        finalRun = run
        break
      }

      const upstream = list(g.upstreamMissing)
      if (upstream.length) {
        return {
          ...handback(
            false,
            'blocked-upstream',
            `blocked-upstream: the suite cannot pass until something outside this Task exists: ${upstream.map((u) => u.what).join('; ')}`,
            { green: g, run, upstreamMissing: upstream }
          ),
          upstreamMissing: upstream,
          evidence: runText(run).slice(0, TAIL_CHARS),
        }
      }

      let redUpdated = false
      const issues = list(g.testIssues)
      if (issues.length) {
        enterPhase('Red')
        const updated = await workflow('agent-teams-workforce:tdd-red', {
          contract,
          testIssues: issues,
          red: { testFiles: [...redFiles] },
          feedback: runText(run),
        })
        if (updated && updated.ledger) runLedger.push(updated.ledger)
        if (!updated || updated.dispatchFailed) {
          return handback(false, stageOf('red', updated), `red (update): ${(updated && updated.reason) || 'the Red update returned nothing'}`, { green: g, red: updated, issues })
        }
        addRedFiles(updated)
        redUpdated = true
        run = await runSuite(`red-update-${round}`)
        if (!validRun(run)) {
          return handback(false, stageOf('red', run), `red (update): the suite runner returned no exit code: ${(run && run.reason) || 'no result'}`, { red: updated, run })
        }
        if (run.exitCode === 0) {
          finalRun = run
          break
        }
      }

      const key = JSON.stringify([run.exitCode, ...[...failingIds(run)].sort()])
      const changedNothing = !list(g.changedFiles).length && !redUpdated
      if (changedNothing && key === previousKey) {
        return {
          ...handback(
            false,
            'no-progress',
            `no-progress: Green round ${round} changed no file and the suite fails exactly as it did the round before`,
            { green: g, run }
          ),
          evidence: runText(run).slice(0, TAIL_CHARS),
        }
      }
      previousKey = key
      if (round >= MAX_GREEN_ROUNDS) {
        return handback(false, 'green', `green: the suite is not green after ${round} Green round(s): ${run.summary || `exit ${run.exitCode}`}`, { green: g, run })
      }
      greenFeedback = `The suite is not green yet.${redUpdated ? ' The test author has ruled on the tests you named; their decisions are in the tests now.' : ''}\n${runText(run)}${baselineNote}`
      runLedger.push({
        phase: 'retry:green',
        round: round + 1,
        whatChanged: `Green round ${round + 1} is given round ${round}'s suite result${list(g.changedFiles).length ? ` after round ${round} changed ${list(g.changedFiles).join(', ')}` : ''}${redUpdated ? ', and the tests the test author updated' : ''}`,
      })
    }

    // ── Refactor: ends green, refactored or restored to its snapshot ──
    enterPhase('Refactor')
    const refactor = await workflow('agent-teams-workforce:tdd-refactor', { contract, green })
    if (refactor && refactor.ledger) runLedger.push(refactor.ledger)
    if (!refactor || refactor.dispatchFailed) {
      return handback(false, stageOf('refactor', refactor), `refactor: ${(refactor && refactor.reason) || 'the Refactor phase returned nothing'}`, { refactor })
    }
    let refactorRun = await runSuite('refactor')
    if (!validRun(refactorRun)) {
      return handback(false, stageOf('refactor', refactorRun), `refactor: the suite runner returned no exit code: ${(refactorRun && refactorRun.reason) || 'no result'}`, { refactor, run: refactorRun })
    }
    let restored = null
    if (refactorRun.exitCode !== 0) {
      const snapshot = String(refactor.snapshotTree || '').trim()
      if (!snapshot) {
        return handback(false, 'refactor', `refactor: the suite is red after the refactor and the refactor recorded no snapshot to restore: ${refactorRun.summary || `exit ${refactorRun.exitCode}`}`, { refactor, run: refactorRun })
      }
      restored = await workflow('agent-teams-workforce:tdd-refactor', { contract, restoreTo: snapshot })
      if (!restored || restored.dispatchFailed || restored.restored !== true) {
        return handback(false, stageOf('refactor', restored), `refactor: the suite is red after the refactor and the tree could not be restored to ${snapshot}`, { refactor, restored, run: refactorRun })
      }
      refactorRun = await runSuite('refactor-restored')
      if (!validRun(refactorRun) || refactorRun.exitCode !== 0) {
        return handback(false, stageOf('refactor', refactorRun), `refactor: the suite is red after restoring the pre-refactor snapshot ${snapshot}: ${(refactorRun && refactorRun.summary) || 'no result'}`, { refactor, restored, run: refactorRun })
      }
      log(`Refactor: the suite went red, so the tree was restored to ${snapshot}`)
    }

    enterPhase('Documentation')
    const docs = await workflow('agent-teams-workforce:documentation', { contract, green })
    if (docs && docs.ledger) runLedger.push(docs.ledger)

    enterPhase('Commit')
    finalRun = await runSuite('final')
    if (!validRun(finalRun) || finalRun.exitCode !== 0) {
      return handback(false, stageOf('commit', finalRun), `commit: the final suite run did not exit 0 (${(finalRun && (finalRun.summary || `exit ${finalRun.exitCode}`)) || 'no result'}), so nothing was committed`, { run: finalRun })
    }
    const committed = await workflow('agent-teams-workforce:settle', {
      repoPath: workRepoPath,
      commitOnly: true,
      branch: workspace.branch || null,
      defaultBranch: workspace.defaultBranch || null,
      message: `${bead.id} ${bead.title || ''}`.trim(),
    })
    if (!committed || committed.status !== 'reported' || (Array.isArray(committed.blocked) && committed.blocked.length)) {
      const why =
        (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
        'the commit step returned nothing'
      return handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `commit: ${why}`, { commit: committed || null })
    }

    return {
      ...handback(
        true,
        'committed',
        `${bead.id} built on ${workspace.branch}: \`${suiteCommand}\` exits 0${finalRun.summary ? ` (${finalRun.summary})` : ''} and the work is committed to the branch of Story ${story.id} (${committed.commit || 'no new commit'}).`,
        {
          contract,
          stashed: workspace.stashed || null,
          results: { intent, baseline, red, green, refactor, restored, documentation: docs, final: finalRun, commit: committed },
        }
      ),
      commit: committed.commit || null,
      suite: { command: suiteCommand, summary: finalRun.summary || '' },
    }
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const environmental = /overload|rate[ _-]?limit|too many requests|quota|capacity|session limit|usage limit|spend limit|credit balance|out of credits|timed? ?out|network/i.test(message)
  const where = currentPhase || 'unknown'
  const slug = String(where).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'unknown'
  log(`RUN ABORTED in ${where}: ${message.slice(0, 300)}`)
  result = handback(false, environmental ? DISPATCH_FAILED_STAGE : slug, `${where}: the run threw — ${message.slice(0, 300)}`, {
    reason: message.slice(0, 400),
    dispatchFailed: environmental,
  })
} finally {
  enterPhase('Run Ledger')
  const detailPath = persistRun(result && result.ok ? 'ok' : `failed:${(result && result.stage) || 'unknown'}`)
  if (result) result.detailPath = detailPath || null
}
return result
