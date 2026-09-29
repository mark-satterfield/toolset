export const meta = {
  name: 'infra-change',
  description:
    "Composite — provisions or changes infrastructure for a Task on its Story's branch: establishes (or reuses) the Story's worktree, authors the provisioning intent, writes the failing cdk synth assertions (Red), has the cdk-stack-author write the CDK that passes them (Green; a run that stays red stops there), refactors, updates the documentation, then commits the work to the Story branch. It deploys nothing and opens no pull request: the Story deploys and opens one pull request once its last Task is done. Returns { ok, stage, beadId, storyId, headline, detailPath, branch, worktree, commit }.",
  phases: [
    { title: 'Workspace', detail: "establishes or reuses the Story's worktree every writing phase operates in" },
    { title: 'Infra Intent' },
    { title: 'Red' },
    { title: 'Green' },
    { title: 'Refactor' },
    { title: 'Documentation' },
    { title: 'Commit', detail: 'commits the Task to the Story branch' },
    { title: 'Run Ledger', detail: 'writes the run journal on every exit path' },
  ],
}

// args: {
//   bead: { id, title, description, repoPath, story: { id, title? }, specPath?, specPaths?, specSections?, requirementIds?,
//           definitionOfDone?, decisionIds?, acceptanceCriteria? },
//   worktreeRoot?: string
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const bead = a.bead || {}
const story = bead.story && typeof bead.story === 'object' ? bead.story : {}
if (!bead.id) return { ok: false, stage: 'input', error: 'no bead.id supplied' }

const runLedger = []
let runDetail = null
let workspaceOut = null

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

let currentPhase = null
function enterPhase(title) {
  currentPhase = title
  phase(title)
}

// Returns the caller-facing result { ok, stage, beadId, storyId, headline, branch, worktree } and records detail for the run journal.
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
    if (!workspace || workspace.ok === false || !workspace.repoPath) {
      const why = (workspace && Array.isArray(workspace.blocked) && workspace.blocked.join('; ')) || (workspace && workspace.reason) || 'the workspace step returned no worktree'
      return handback(false, stageFor('workspace', workspace), `workspace: no worktree was established — ${why}`, { workspace: workspace || null })
    }
    workspaceOut = workspace
    const workRepoPath = workspace.repoPath
    if (workspace.ledger) runLedger.push(workspace.ledger)

    enterPhase('Infra Intent')
    log(`Infra change ${bead.id} — ${bead.title || ''}`)
    const intent = await workflow('agent-teams-workforce:infra-intent', {
      change: { id: bead.id, title: bead.title, description: bead.description, repoPath: workRepoPath },
    })
    if (!intent || !intent.provisioningIntent) {
      return { ...failure('infra-intent', intent, 'infra-intent produced no provisioning intent'), intent: intent || null }
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
          then: 'the synthesized template asserts the intended resources and their properties, the SSM parameter names the stacks write and read, and the IAM permissions (incl. S3 versioning + SSE-S3 where buckets exist), and no banned constructs are present',
        },
      ],
    }

    enterPhase('Red')
    const red = await workflow('agent-teams-workforce:tdd-red', { contract: tailContract })
    if (red && red.ledger) runLedger.push(red.ledger)
    if (!red || red.dispatchFailed) return failure('red', red, 'tdd-red returned nothing')
    if (red.redConfirmed !== true) log(`Red: not confirmed — ${red.reason || 'no reason given'}; Green proceeds`)

    enterPhase('Green')
    const green = await workflow('agent-teams-workforce:tdd-green', {
      contract: tailContract,
      red,
      implementer: 'cdk-stack-author',
      feedback: '',
    })
    if (green && green.ledger) runLedger.push(green.ledger)
    if (!green || green.dispatchFailed) return failure('green', green, 'tdd-green returned nothing')
    if (green.greenConfirmed !== true || green.noRegressions !== true) return failure('green', green, 'the synth assertions do not pass')

    enterPhase('Refactor')
    const refactor = await workflow('agent-teams-workforce:tdd-refactor', { contract: tailContract, green })
    if (refactor && refactor.ledger) runLedger.push(refactor.ledger)
    if (!refactor || refactor.dispatchFailed) return failure('refactor', refactor, 'tdd-refactor returned nothing')
    if (refactor.testsGreen !== true) return failure('refactor', refactor, 'the suite is not green after the refactor')

    enterPhase('Documentation')
    const docs = await workflow('agent-teams-workforce:documentation', { contract: tailContract, green })
    if (docs && docs.ledger) runLedger.push(docs.ledger)

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
        `${bead.id} provisioned in CDK on ${workspace.branch}: the synth assertions pass and the work is committed to the branch of Story ${story.id} (${committed.commit || 'no new commit'}).`,
        {
          stagesComplete: ['infra-intent', 'red', 'green', 'refactor', 'documentation', 'committed'],
          contract: tailContract,
          results: { intent, red, green, refactor, documentation: docs, commit: committed },
        }
      ),
      commit: committed.commit || null,
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
}
return result
