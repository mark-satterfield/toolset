export const meta = {
  name: 'task-to-deploy',
  description:
    'Builds a Task from its build contract and deploys it to AWS dev: establishes a worktree, writes failing tests (Red), implements until they pass (Green), deploys to dev and smoke-tests the deployed endpoints (re-entering Green and redeploying on a smoke failure, bounded), then lands the work in git with a pull request on every exit path. Documentation runs beside the build and is awaited before deploy. Returns { ok, stage, beadId, headline, detailPath, deployedToDev, smokePassed, deployIteration } plus the landing verdict.',
  phases: [
    { title: 'Workspace', detail: 'establishes the worktree every writing phase operates in' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Deploy-to-dev', detail: 'deploys to AWS dev and smoke-checks the deployed endpoints; re-enters Green and redeploys on a smoke failure, bounded' },
    { title: 'Settle', detail: 'lands the work in git (commit, push, PR) on every exit path' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, repoPath, title?, description?, specPath?, specPaths?, specSections?, requirementIds?,
//           definitionOfDone?, decisionIds?, acceptanceCriteria?, surfaces?, apiSpec?, eventContracts?, testStrategy? },
//   spec?: object (defaults to bead), implementer?: string, maxLoops?: number (Green attempts, default 2),
//   maxDeployIterations?: number (default 3), maxEscalations?: number (Green → Red re-authors, default 2),
//   worktreeRoot?: string, prCommand?: string
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const spec = a.spec || bead
const PR_COMMAND = typeof a.prCommand === 'string' && a.prCommand.trim() ? a.prCommand.trim() : null
const MAX_LOOPS = a.maxLoops || 2
const MAX_DEPLOY_ITERATIONS = a.maxDeployIterations || 3
const MAX_ESCALATIONS = a.maxEscalations || 2
const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const HUMAN_ACTION_STAGE = 'requires-human-action'

if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied', deployedToDev: false, smokePassed: false, deployIteration: 0 }

const runLedger = []
let runDetail = null
let settleRepoPath = null
let settleBranch = null
let settleDefaultBranch = null
let docTrack = null
let escalations = 0

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

async function settleRun() {
  if (!settleRepoPath) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written' }
  try {
    const out = await workflow('agent-teams-workforce:settle', {
      repoPath: settleRepoPath,
      prCommand: PR_COMMAND,
      branch: settleBranch,
      isLinkedWorktree: true,
      defaultBranch: settleDefaultBranch,
    })
    return out && typeof out.status === 'string' ? out : { status: 'error', error: 'the settle step returned no result' }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

// Sets landed, landingStage, settled, prUrl, orphaned, settleFailed and settleNote on `res` from the settle report;
// sets res.ok=false when the work was written but not landed.
function applySettle(res, settle) {
  const status = (settle && settle.status) || 'error'
  if (status === 'not-applicable') {
    res.landed = false
    res.landingStage = 'not-applicable'
    res.settled = 'not-applicable'
    res.settleNote = (settle && settle.reason) || 'no repo path was established'
    return
  }
  if (status === 'error') {
    res.landed = false
    res.landingStage = 'unlanded'
    res.ok = false
    res.settleFailed = { error: (settle && settle.error) || 'the settle step failed without an error message' }
    return
  }
  if (status === 'blocked') {
    res.landed = false
    res.landingStage = 'unlanded'
    res.ok = false
    res.settled = 'blocked'
    res.orphaned = { worktree: settleRepoPath, branch: settleBranch || null, blocked: [(settle && settle.reason) || 'settle did not land the work'] }
    log(`Settle: blocked — ${(settle && settle.reason) || 'no reason'}`)
    return
  }
  const prUrl = String(settle.prUrl || '').trim()
  const landed = settle.treeClean === true && (settle.hasWork === false || !!prUrl)
  res.landed = landed
  res.landingStage = landed ? 'landed' : 'unlanded'
  res.prUrl = prUrl || null
  res.settled = 'reported'
  if (!landed) {
    res.ok = false
    res.orphaned = {
      worktree: settleRepoPath,
      branch: settle.branch || null,
      blocked: (settle.blocked && settle.blocked.length ? settle.blocked : null) || ['settle returned no PR URL'],
    }
  }
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
    headline: String(headline || ''),
    deployedToDev: false,
    smokePassed: false,
    deployIteration: 0,
    ...(stage === HUMAN_ACTION_STAGE
      ? { requiredHumanActions: [`look at ${bead.id} and re-scope, re-route or clear what stopped it before it is dispatched again: ${String(headline || '').slice(0, 600)}`] }
      : {}),
  }
}

// Returns the stage for a failed phase result: dispatch failure, a stop that needs a person, or `stage`.
const stageOf = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : r.phaseBlocked === true ? HUMAN_ACTION_STAGE : stage)

function deployEvidence(rows) {
  const last = rows.length ? rows[rows.length - 1] : null
  return {
    deployedToDev: rows.some((r) => r.deployedToDev === true),
    smokePassed: !!(last && last.deployedToDev === true && last.smokePassed === true),
    deployIteration: last ? last.iteration : 0,
  }
}

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

    enterPhase('Workspace')
    const workspace = await workflow('agent-teams-workforce:workspace', {
      repoPath: bead.repoPath,
      beadId: bead.id,
      branchPrefix: 'feat',
      purpose: bead.title || 'task',
      worktreeRoot: a.worktreeRoot,
    })
    if (!workspace || workspace.ok !== true || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked[0]) || 'the workspace step returned nothing'
      return handback(false, stageOf('workspace', workspace), `no worktree was established: ${why}`, { workspace: workspace || null })
    }
    const workRepoPath = workspace.repoPath
    settleRepoPath = workRepoPath
    settleBranch = workspace.branch || null
    settleDefaultBranch = workspace.defaultBranch || null
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
    async function runGreen(extraFeedback) {
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
          feedback: [extraFeedback, feedback].filter(Boolean).join('\n\n'),
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

    const g = await runGreen('')
    if (g.fail) return g.fail
    docTrack = Promise.resolve(workflow('agent-teams-workforce:documentation', { contract, green: g.green })).catch((e) => {
      log(`documentation track failed: ${(e && e.message) || e}`)
      return null
    })

    const docResult = docTrack ? await docTrack : null
    if (docResult && Array.isArray(docResult.ledgers)) runLedger.push(...docResult.ledgers)

    const deployIterations = []
    let smokeSuite = []
    let smokeFeedback = ''
    let finalDeploy = null
    const leaseScope = (workspace.verification && workspace.verification.gitCommonDir) || null
    for (let iteration = 1; iteration <= MAX_DEPLOY_ITERATIONS; iteration++) {
      enterPhase('Deploy-to-dev')
      log(`Deploy to dev — iteration ${iteration}/${MAX_DEPLOY_ITERATIONS} (stage deploy-to-dev#${iteration})`)
      const d = await workflow('agent-teams-workforce:deploy', {
        contract,
        green,
        feedback: smokeFeedback,
        smokeTestFiles: smokeSuite,
        leaseScope,
      })
      if (d && d.ledger) runLedger.push(d.ledger)
      const row = {
        phase: 'deploy-iteration',
        stage: `deploy-to-dev#${iteration}`,
        iteration,
        maxIterations: MAX_DEPLOY_ITERATIONS,
        deployedToDev: !!(d && d.deployedToDev === true),
        smokePassed: !!(d && d.smokePassed === true),
      }
      deployIterations.push(row)
      runLedger.push(row)
      if (!d || d.dispatchFailed) {
        return { ...handback(false, DISPATCH_FAILED_STAGE, `deploy-to-dev: ${(d && d.reason) || 'the deploy phase returned nothing'}`, { deploy: d, deployIterations }), ...deployEvidence(deployIterations) }
      }
      if (row.deployedToDev && row.smokePassed) {
        finalDeploy = d
        break
      }
      const rollout = d.rollout || {}
      const failedCases = (Array.isArray(rollout.smokeCases) ? rollout.smokeCases : []).filter((sc) => sc && sc.passed !== true)
      if (!row.deployedToDev || !failedCases.length) {
        const leaseBlocked = typeof d.leaseBlocked === 'string' && d.leaseBlocked ? d.leaseBlocked : null
        const why = leaseBlocked || d.reason || (Array.isArray(d.blocked) && d.blocked.join('; ')) || (row.deployedToDev ? 'the smoke tests did not pass and no failing case was reported' : 'the change did not reach AWS dev')
        return {
          ...handback(false, leaseBlocked ? DISPATCH_FAILED_STAGE : stageOf('deploy-to-dev', d), `deploy-to-dev: ${why}`, { deploy: d, deployIterations }),
          ...deployEvidence(deployIterations),
        }
      }
      if (Array.isArray(d.smokeTestFiles) && d.smokeTestFiles.length) smokeSuite = d.smokeTestFiles
      const smokeEvidence = failedCases.map((sc) => `${sc.name}: ${String(sc.output || '').slice(0, 1500)}`).join('\n')
      if (iteration >= MAX_DEPLOY_ITERATIONS) {
        return {
          ...handback(
            false,
            'deploy-to-dev',
            `${bead.id} deployed to AWS dev but the smoke tests still fail after ${MAX_DEPLOY_ITERATIONS} deploy iteration(s): ${smokeEvidence}`,
            { deploy: d, deployIterations, smokeFailure: smokeEvidence }
          ),
          deployedToDev: true,
          smokePassed: false,
          deployIteration: iteration,
        }
      }
      log(`Deploy to dev — iteration ${iteration} smoke FAILED in AWS dev; re-entering Green, then redeploying`)
      smokeFeedback = `The previous deploy (iteration ${iteration}/${MAX_DEPLOY_ITERATIONS}) reached AWS dev and the smoke tests FAILED against the deployed endpoints: ${smokeEvidence}`
      const g = await runGreen(smokeFeedback)
      if (g.fail) return { ...g.fail, ...deployEvidence(deployIterations) }
    }

    const evidence = deployEvidence(deployIterations)
    const iterationNote = evidence.deployIteration > 1 ? ` after ${evidence.deployIteration} deploy iterations` : ''
    return {
      ...handback(
        true,
        'deployed-to-dev',
        `${bead.id} built and DEPLOYED TO AWS DEV${iterationNote}, with the smoke tests passing against the deployed dev endpoints.`,
        { contract, deployIterations, results: { red, green, deploy: finalDeploy, documentation: docResult } }
      ),
      ...evidence,
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
  if (docTrack) await Promise.allSettled([docTrack])
  enterPhase('Settle')
  const settle = await settleRun()
  if (result) applySettle(result, settle)
}
return result
