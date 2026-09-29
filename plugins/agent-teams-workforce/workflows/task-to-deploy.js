export const meta = {
  name: 'task-to-deploy',
  description:
    "Builds a Task from its build contract on its Story's branch: establishes (or reuses) the Story's worktree, writes failing tests (Red), implements until they pass (Green), refactors, updates the documentation, then commits the work to the Story branch. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree every writing phase operates in" },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'commits the Task to the Story branch' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, repoPath, story: { id, title? }, title?, description?, specPath?, specPaths?, specSections?, requirementIds?,
//           definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy? },
//   spec?: object (defaults to bead), implementer?: string, maxLoops?: number (Green attempts, default 2),
//   maxEscalations?: number (Green → Red re-authors, default 2), worktreeRoot?: string
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
const MAX_LOOPS = a.maxLoops || 2
const MAX_ESCALATIONS = a.maxEscalations || 2
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const HUMAN_ACTION_STAGE = 'requires-human-action'

if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied' }

const runLedger = []
let runDetail = null
let escalations = 0
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
    ...(stage === HUMAN_ACTION_STAGE
      ? { requiredHumanActions: [`look at ${bead.id} and re-scope, re-route or clear what stopped it before it is dispatched again: ${String(headline || '').slice(0, 600)}`] }
      : {}),
  }
}

// Returns the stage for a failed phase result: dispatch failure, a stop that needs a person, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : r.phaseBlocked === true ? HUMAN_ACTION_STAGE : stage)

function implementersOf(artifact) {
  const l = artifact && artifact.ledger
  return l && (l.mode === 'selected' || l.mode === 'reused') && Array.isArray(l.chosen) && l.chosen.length ? l.chosen : undefined
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

    enterPhase('Red')
    let red = await workflow('agent-teams-workforce:tdd-red', { contract, feedback: '' })
    if (red && red.ledger) runLedger.push(red.ledger)
    if (!red || red.dispatchFailed || red.phaseBlocked === true) {
      return handback(false, stageOf('red', red), `red: ${(red && (red.blockedReason || red.reason)) || 'the Red phase returned nothing'}`, { red })
    }

    let green = null
    // Runs tdd-green until it reports greenConfirmed, up to MAX_LOOPS attempts per Red; a reported
    // contradiction or defective test re-authors Red (bounded by MAX_ESCALATIONS) and starts again.
    // Returns { green } or { fail: <handback> }.
    async function runGreen() {
      let feedback = ''
      let attempt = 0
      for (;;) {
        attempt += 1
        enterPhase('Green')
        const g = await workflow('agent-teams-workforce:tdd-green', {
          contract,
          red,
          implementer: a.implementer,
          implementers: implementersOf(green),
          feedback,
        })
        if (g && g.ledger) runLedger.push(g.ledger)
        if (!g || g.dispatchFailed || g.phaseBlocked === true) {
          return { fail: handback(false, stageOf('green', g), `green: ${(g && (g.blockedReason || g.reason)) || 'the Green phase returned nothing'}`, { green: g }) }
        }
        green = g
        if (g.greenConfirmed === true) return { green: g }
        const defect = g.contradiction
          ? `Two tests assert opposite outcomes for the same input and cannot both pass. Decide which expectation is the correct contract and correct the other test: ${JSON.stringify(g.contradiction)}`
          : g.testDefect
            ? `The failing test cannot pass as written. Correct the test so a pass is reachable without weakening what it asserts: ${g.testDefect}`
            : null
        if (defect && escalations < MAX_ESCALATIONS) {
          escalations += 1
          log(`Green reported a test that cannot pass; re-authoring Red (${escalations}/${MAX_ESCALATIONS})`)
          enterPhase('Red')
          const reRed = await workflow('agent-teams-workforce:tdd-red', { contract, red, feedback: defect, skipDiscovery: true })
          if (reRed && reRed.ledger) runLedger.push(reRed.ledger)
          if (!reRed || reRed.dispatchFailed || reRed.phaseBlocked === true) {
            return { fail: handback(false, stageOf('red', reRed), `red: ${(reRed && (reRed.blockedReason || reRed.reason)) || 'the Red re-author returned nothing'}`, { red: reRed }) }
          }
          red = reRed
          attempt = 0
          feedback = ''
          continue
        }
        if (attempt >= MAX_LOOPS) {
          return { fail: handback(false, 'green', `green: the tests did not pass after ${attempt} attempt(s): ${String(g.reason || g.evidence || '').slice(0, 400)}`, { green: g }) }
        }
        feedback = `The previous Green attempt did not get the tests passing. Its evidence:\n${String(g.evidence || g.reason || '').slice(0, 4000)}`
      }
    }

    const g = await runGreen()
    if (g.fail) return g.fail

    enterPhase('Refactor')
    const refactor = await workflow('agent-teams-workforce:tdd-refactor', { contract, green: g.green })
    if (refactor && refactor.ledger) runLedger.push(refactor.ledger)
    if (!refactor || refactor.dispatchFailed) {
      return handback(false, stageOf('refactor', refactor), `refactor: ${(refactor && refactor.reason) || 'the Refactor phase returned nothing'}`, { refactor })
    }
    if (refactor.testsGreen !== true) {
      return handback(false, 'refactor', `refactor: the suite is not green after the refactor: ${String(refactor.reason || '').slice(0, 400)}`, { refactor })
    }

    enterPhase('Documentation')
    const docs = await workflow('agent-teams-workforce:documentation', { contract, green: g.green })
    if (docs && Array.isArray(docs.ledgers)) runLedger.push(...docs.ledgers)

    enterPhase('Commit')
    const committed = await workflow('agent-teams-workforce:settle', {
      repoPath: workRepoPath,
      commitOnly: true,
      branch: workspace.branch || null,
      defaultBranch: workspace.defaultBranch || null,
      message: `${bead.id} ${bead.title || ''}`.trim(),
    })
    if (!committed || committed.status !== 'reported' || committed.treeClean !== true) {
      const why =
        (committed && (committed.error || committed.reason || (Array.isArray(committed.blocked) && committed.blocked.join('; ')))) ||
        (committed && committed.treeClean === false ? 'the tree is not clean after the commit' : 'the commit step returned nothing')
      return handback(false, !committed || committed.status === 'error' ? DISPATCH_FAILED_STAGE : 'commit', `commit: ${why}`, { commit: committed || null })
    }

    return {
      ...handback(
        true,
        'committed',
        `${bead.id} built on ${workspace.branch}: tests pass and the work is committed to the branch of Story ${story.id} (${committed.commit || 'no new commit'}).`,
        { contract, results: { red, green: g.green, refactor, documentation: docs, commit: committed } }
      ),
      commit: committed.commit || null,
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
