export const meta = {
  name: 'infra-change',
  description:
    'Composite — provisions or changes infrastructure for a Task: establishes a worktree, authors the provisioning intent, writes the failing synth assertions (Red), has the cdk-stack-author write the CDK that passes them (Green; a run that stays red stops there), runs Documentation beside the build and awaits it before each deploy, deploys to AWS dev and smoke-tests there (a smoke failure re-enters Green and redeploys, bounded), then lands the work in git. Returns { ok, stage, beadId, headline, detailPath, deployedToDev, smokePassed, deployIteration } plus the landing verdict.',
  phases: [
    { title: 'Workspace', detail: 'establishes the worktree every writing phase operates in' },
    { title: 'Infra Intent' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Deploy-to-dev', detail: 'deploys to AWS dev and smoke-tests; re-enters Green and redeploys on a smoke failure, bounded' },
    { title: 'Settle', detail: 'lands the work in git — commit, push, PR — on every exit path' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, title, description, repoPath, specPath?, specPaths?, specSections?, requirementIds?,
//           definitionOfDone?, decisionIds?, acceptanceCriteria? },
//   worktreeRoot?: string, prCommand?: string, maxDeployIterations?: number (default 3)
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const MAX_DEPLOY_ITERATIONS = a.maxDeployIterations || 3
if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied', deployedToDev: false, smokePassed: false, deployIteration: 0 }

const runLedger = []
let runDetail = null

// Logs the run journal as one `RUN-JOURNAL {json}` line, or as `RUN-JOURNAL-PART i/n` lines when longer than JOURNAL_CHUNK; the host reassembles and writes it.
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
    emitRunJournal({ composite: 'infra-change', bead: { id: bead.id || null, title: bead.title || null }, outcome, runLedger, detail: runDetail })
  } catch (e) {
    log(`run journal could not be serialized: ${e && e.message ? e.message : e}`)
  }
  return null
}

let docTrack = null
let repairDocTrack = null
let docContract = null
function startDocTrack(greenArtifact) {
  return Promise.resolve(workflow('agent-teams-workforce:documentation', { contract: docContract, green: greenArtifact })).catch((e) => {
    log(`documentation track failed: ${(e && e.message) || e}`)
    return null
  })
}

let settleRepoPath = null
let settleBranch = null
let settleIsLinkedWorktree = false
let settleDefaultBranch = null

async function settleRun() {
  if (!settleRepoPath) return { status: 'not-applicable', reason: 'the run established no worktree' }
  try {
    const out = await workflow('agent-teams-workforce:settle', {
      repoPath: settleRepoPath,
      prCommand: typeof a.prCommand === 'string' && a.prCommand ? a.prCommand : null,
      branch: settleBranch,
      isLinkedWorktree: settleIsLinkedWorktree,
      defaultBranch: settleDefaultBranch,
    })
    return out && typeof out.status === 'string' ? out : { status: 'error', error: 'the settle step returned no result' }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

// Sets res.landed, res.landingStage, res.settled, res.prUrl, res.orphaned, res.settleFailed from the settle report; unlanded work sets res.ok = false.
function applySettle(res, settle) {
  const status = (settle && settle.status) || 'error'
  if (status === 'not-applicable') {
    res.landed = false
    res.landingStage = 'not-applicable'
    res.settled = 'not-applicable'
    res.settleNote = (settle && settle.reason) || 'no worktree was established'
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
    res.orphaned = { worktree: settleRepoPath, branch: settleBranch || null, blocked: [(settle && settle.reason) || 'settle refused to commit'] }
    log(`Settle: REFUSED — ${(settle && settle.reason) || 'no reason given'}`)
    return
  }
  const prUrl = typeof settle.prUrl === 'string' && settle.prUrl.trim() ? settle.prUrl.trim() : null
  const landed = settle.hasWork === false || !!prUrl
  res.landed = landed
  res.landingStage = landed ? 'landed' : 'unlanded'
  res.prUrl = prUrl
  res.settled = 'reported'
  if (!landed) {
    res.ok = false
    res.orphaned = {
      worktree: settleRepoPath,
      branch: settle.branch || null,
      blocked: (Array.isArray(settle.blocked) && settle.blocked.length ? settle.blocked : null) || ['settle returned no PR URL'],
    }
  }
}

let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// Returns the caller-facing result { ok, stage, beadId, headline, deployedToDev: false, smokePassed: false, deployIteration: 0 } and records detail for the run journal.
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
  }
}

function deployEvidence(rows) {
  const last = rows.length ? rows[rows.length - 1] : null
  return {
    deployedToDev: rows.some((r) => r.deployedToDev === true),
    smokePassed: !!(last && last.deployedToDev === true && last.smokePassed === true),
    deployIteration: last ? last.iteration : 0,
  }
}

const DISPATCH_FAILED_STAGE = 'agent-dispatch-failed'
const ENVIRONMENTAL_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|throttl|timed? ?out|econnreset|econnrefused|etimedout|socket hang up|service unavailable|session limit|usage limit|spend limit|credit balance|out of credits/i
const stageFor = (stage, r) => (!r || r.dispatchFailed ? DISPATCH_FAILED_STAGE : stage)
const failure = (stage, r, what) =>
  handback(false, stageFor(stage, r), `${stage}: ${(r && r.reason) || what}`, r || null)

let result
try {
  result = await (async () => {
    if (!String(bead.repoPath || '').trim()) {
      return {
        ...handback(false, 'input', `${bead.id} carries no repoPath, so its build contract is incomplete. The repository is ruled during elaboration: re-elaborate the Task's Story, or record the repository on the Task as its repoPath.`),
        incompleteContract: ['repoPath'],
        requiredHumanActions: [`re-elaborate the Story of ${bead.id}, or record the repository on it as its repoPath`],
      }
    }

    enterPhase('Workspace')
    const workspace = await workflow('agent-teams-workforce:workspace', {
      repoPath: bead.repoPath,
      beadId: bead.id,
      branchPrefix: 'infra',
      purpose: bead.title || 'infra change',
      worktreeRoot: a.worktreeRoot,
    })
    if (!workspace || workspace.ok === false || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked.join('; ')) || (workspace && workspace.reason) || 'the workspace step returned no worktree'
      return handback(false, stageFor('workspace', workspace), `workspace: no worktree was established — ${why}`, { workspace: workspace || null })
    }
    const workRepoPath = workspace.repoPath
    settleRepoPath = workRepoPath
    settleBranch = workspace.branch || null
    settleIsLinkedWorktree = workspace.isLinkedWorktree === true
    settleDefaultBranch = workspace.defaultBranch || null
    if (workspace.ledger) runLedger.push(workspace.ledger)

    enterPhase('Infra Intent')
    log(`Infra change ${bead.id} — ${bead.title || ''}`)
    const intent = await workflow('agent-teams-workforce:infra-intent', {
      change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
    })
    if (!intent || !intent.provisioningIntent) {
      return { ...failure('infra-intent', intent, 'infra-intent produced no provisioning intent'), gate: 'G1', intent: intent || null }
    }

    const tailContract = {
      bead: { id: bead.id, title: bead.title || 'infra change', description: bead.description || null, repoPath: workRepoPath },
      spec: bead,
      decisionIds: (Array.isArray(bead.decisionIds) ? bead.decisionIds : []).map((x) => String(x || '').trim()).filter(Boolean),
      repoPath: workRepoPath,
      affectedStacks: intent.affectedStacks || [],
      provisioningIntent: intent.provisioningIntent || null,
      surfaces: [],
      testStrategy: null,
      acceptanceCriteria: [
        ...(Array.isArray(bead.acceptanceCriteria) ? bead.acceptanceCriteria.filter(Boolean) : []),
        {
          given: `the provisioning intent for ${bead.title || 'this infra change'} on stacks ${(intent.affectedStacks || []).join(', ') || '(affected stacks)'}`,
          when: 'cdk synth runs against the changed stacks',
          then: 'the synthesized template asserts the intended resources/properties (incl. S3 versioning + SSE-S3 where buckets exist) and no banned constructs are present',
        },
      ],
    }

    enterPhase('Red')
    const red = await workflow('agent-teams-workforce:tdd-red', { contract: tailContract })
    if (red && red.ledger) runLedger.push(red.ledger)
    if (!red || red.dispatchFailed) return failure('red', red, 'tdd-red returned nothing')
    if (red.redConfirmed !== true) log(`Red: not confirmed — ${red.reason || 'no reason given'}; Green proceeds`)

    // Runs tdd-green with cdk-stack-author; returns { green } when the suite is green, else { handback }.
    async function runGreen(feedback) {
      enterPhase('Green')
      const g = await workflow('agent-teams-workforce:tdd-green', {
        contract: tailContract,
        red,
        implementer: 'cdk-stack-author',
        feedback: feedback || '',
      })
      if (g && g.ledger) runLedger.push(g.ledger)
      if (!g || g.dispatchFailed) return { handback: failure('green', g, 'tdd-green returned nothing') }
      if (g.greenConfirmed !== true || g.noRegressions !== true) return { handback: failure('green', g, 'the synth assertions do not pass') }
      return { green: g }
    }

    const first = await runGreen('')
    if (first.handback) return first.handback
    let green = first.green

    docContract = tailContract
    docTrack = startDocTrack(green)

    const deployIterations = []
    let deployed = null
    let smokeFeedback = ''
    let smokeSuite = []
    const leaseScope = (workspace.verification && workspace.verification.gitCommonDir) || null
    for (let iteration = 1; iteration <= MAX_DEPLOY_ITERATIONS; iteration++) {
      const docs = await Promise.all([docTrack, repairDocTrack])
      docTrack = null
      repairDocTrack = null
      for (const d of docs) if (d && d.ledger) runLedger.push(d.ledger)

      enterPhase('Deploy-to-dev')
      log(`Deploy to dev — iteration ${iteration}/${MAX_DEPLOY_ITERATIONS} (stage deploy-to-dev#${iteration})`)
      deployed = await workflow('agent-teams-workforce:deploy', {
        contract: tailContract,
        green,
        feedback: smokeFeedback,
        smokeTestFiles: smokeSuite,
        leaseScope,
      })
      const dep = deployed || {}
      if (dep.ledger) runLedger.push(dep.ledger)
      const row = {
        phase: 'deploy-iteration',
        stage: `deploy-to-dev#${iteration}`,
        iteration,
        maxIterations: MAX_DEPLOY_ITERATIONS,
        deployedToDev: dep.deployedToDev === true,
        smokePassed: dep.smokePassed === true,
        ok: dep.deployedToDev === true && dep.smokePassed === true,
      }
      deployIterations.push(row)
      runLedger.push(row)
      if (row.ok) break

      const leaseBlocked = typeof dep.leaseBlocked === 'string' && dep.leaseBlocked ? dep.leaseBlocked : null
      if (!deployed || dep.dispatchFailed || leaseBlocked) {
        return {
          ...handback(false, DISPATCH_FAILED_STAGE, `deploy-to-dev: ${leaseBlocked || dep.reason || 'the deploy step returned nothing'}`, { deployed, deployIterations }),
          ...deployEvidence(deployIterations),
        }
      }
      if (dep.deployedToDev !== true) {
        return {
          ...handback(false, 'deploy-to-dev', `deploy-to-dev: the change did not reach AWS dev — ${dep.reason || dep.blockedReason || 'no reason given'}`, { deployed, deployIterations }),
          ...deployEvidence(deployIterations),
        }
      }
      const rollout = dep.rollout || {}
      const failedCases = (Array.isArray(rollout.smokeCases) ? rollout.smokeCases : []).filter((sc) => sc && sc.passed !== true)
      const smokeEvidence =
        failedCases.map((sc) => `${sc.name}: ${String(sc.output || '').slice(0, 1500)}`).join('\n') ||
        rollout.evidence ||
        (rollout.findings || []).join('; ') ||
        'the deploy phase reported no smoke output'
      if (iteration >= MAX_DEPLOY_ITERATIONS) {
        return {
          ...handback(
            false,
            'deploy-to-dev',
            `${bead.id} deployed to AWS dev on iteration ${iteration}/${MAX_DEPLOY_ITERATIONS}, but the smoke tests FAILED against the deployed dev endpoints: ${smokeEvidence}`,
            { deployed, deployIterations, smokeFailure: smokeEvidence }
          ),
          deployedToDev: true,
          smokePassed: false,
          deployIteration: iteration,
        }
      }
      if (Array.isArray(dep.smokeTestFiles) && dep.smokeTestFiles.length) smokeSuite = dep.smokeTestFiles
      smokeFeedback = `Deploy iteration ${iteration}/${MAX_DEPLOY_ITERATIONS} reached AWS dev and the smoke tests FAILED against the deployed endpoints. Fix the CDK so they pass: ${smokeEvidence}`
      log(`Deploy to dev — iteration ${iteration} smoke FAILED in AWS dev; re-entering Green, then redeploying`)
      const repaired = await runGreen(smokeFeedback)
      if (repaired.handback) return { ...repaired.handback, ...deployEvidence(deployIterations) }
      green = repaired.green
      repairDocTrack = startDocTrack(green)
    }

    const last = deployIterations[deployIterations.length - 1]
    return {
      ...handback(
        true,
        'deployed-to-dev',
        `${bead.id} provisioned and DEPLOYED TO AWS DEV${last.iteration > 1 ? ` after ${last.iteration} deploy iterations` : ''}, with the smoke tests PASSING against the deployed dev endpoints. Landing in git is reported under \`settled\` / \`prUrl\`.`,
        {
          stagesComplete: ['infra-intent', 'red', 'green', 'deployed-to-dev'],
          deployIterations,
          contract: tailContract,
          results: { intent, red, green, deploy: deployed },
        }
      ),
      deployedToDev: true,
      smokePassed: true,
      deployIteration: last.iteration,
    }
  })()
} catch (err) {
  const message = String((err && err.message) || err)
  const environmental = ENVIRONMENTAL_ERROR_TEXT.test(message)
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
  await Promise.allSettled([docTrack, repairDocTrack])
  enterPhase('Settle')
  const settle = await settleRun()
  if (result) applySettle(result, settle)
}
return result
