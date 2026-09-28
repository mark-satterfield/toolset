export const meta = {
  name: 'workspace',
  description:
    'Establishes the git worktree the writing phases work in: reuses the tree already registered for the bead, or cuts one on a feature branch at <worktreeRoot>/<bead>-<repo> (a .worktrees/ directory beside the repository when no root is given). Returns { ok, repoPath, branch, reused, defaultBranch, verification, blocked }.',
  phases: [{ title: 'Workspace', detail: 'provision or reuse the linked worktree the writing phases operate in' }],
}

// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null on any other failure.
const DETERMINISTIC_ERROR_TEXT =
  /structured ?output|schema|validation|does not match|required property|additionalproperties|unsatisfiable|invalid argument/i
const TRANSIENT_ERROR_TEXT =
  /overload|rate[ _-]?limit|too many requests|quota|token limit|capacity|throttl|timed? ?out|timeout|econnreset|econnrefused|etimedout|eai_again|socket hang up|network|temporarily unavailable|service unavailable|upstream connect|bad gateway/i
const TRANSIENT_STATUS = new Set([408, 425, 429, 500, 502, 503, 504, 529])
const isTransient = (err) => {
  const e = err && typeof err === 'object' ? err : {}
  const text = String(e.message || err || '')
  if (DETERMINISTIC_ERROR_TEXT.test(text)) return false
  const status = Number(e.status || e.statusCode || (e.response && e.response.status))
  return TRANSIENT_STATUS.has(status) || TRANSIENT_ERROR_TEXT.test(text)
}
async function settleAgent(prompt, opts) {
  const call = opts || {}
  const name = call.label || call.agentType || 'agent'
  for (let attempt = 1; ; attempt++) {
    try {
      const out = await agent(prompt, call)
      if (!out) log(`${name}: returned nothing`)
      return out || null
    } catch (err) {
      const message = String((err && err.message) || err)
      if (isTransient(err) && typeof setTimeout === 'function') {
        const wait = Math.min(300000, 5000 * Math.pow(3, attempt - 1))
        log(`${name}: transient failure on attempt ${attempt}; retrying in ${Math.round(wait / 1000)}s — ${message.slice(0, 160)}`)
        await new Promise((resolve) => setTimeout(resolve, wait))
        continue
      }
      log(`${name}: ended without a structured result — ${message.slice(0, 160)}`)
      return null
    }
  }
}

// args: { repoPath: string, beadId: string, branchPrefix?: string, purpose?: string, worktreeRoot?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const repoPath = String(a.repoPath || '').trim().replace(/\/+$/, '')
const beadId = String(a.beadId || '').trim()
const worktreeRoot = String(a.worktreeRoot || '').trim().replace(/\/+$/, '')
const prefix = String(a.branchPrefix || 'work').trim().replace(/[^a-zA-Z0-9._-]/g, '') || 'work'
const purpose = String(a.purpose || '').replace(/\s+/g, ' ').trim().slice(0, 240)

const refuse = (reason, extra) => ({ ok: false, applicable: true, repoPath: null, branch: null, reused: false, blocked: [reason], ...(extra || {}) })

if (!repoPath) return { ...refuse('no repoPath supplied'), applicable: false }
if (!beadId) return { ...refuse('no beadId supplied'), applicable: false }

const repoBase = repoPath.slice(repoPath.lastIndexOf('/') + 1)
const repoParent = repoPath.slice(0, repoPath.lastIndexOf('/')) || '/'
const worktreeHome = worktreeRoot || `${repoParent === '/' ? '' : repoParent}/.worktrees`
const plannedWorktreePath = `${worktreeHome}/${beadId}-${repoBase}`
const BRANCH = `${prefix}/${beadId}`

phase('Workspace')

const provisioned = await settleAgent(
  `Establish the git worktree this run's writing phases will operate in, then report what you established. Write no project code.

Repository: ${repoPath}
Work item: ${beadId}
Branch: ${BRANCH}
Worktree path: ${plannedWorktreePath}${purpose ? `\nPurpose: ${purpose}` : ''}

Run every git command as \`git -C "<path>"\`. Never redirect stderr to /dev/null.

1. Find the default branch: \`git -C "${repoPath}" symbolic-ref --short refs/remotes/origin/HEAD\` (strip \`origin/\`; if missing use main, then master).
2. \`git -C "${repoPath}" worktree list --porcelain\`. If a tree is already registered for branch ${BRANCH} or at ${plannedWorktreePath}, reuse it (reused=true) and go to step 5.
3. \`git -C "${repoPath}" fetch origin <default>\`. Fast-forward the main tree only if it is clean, on the default branch, and behind origin; otherwise leave it alone.
4. \`mkdir -p "$(dirname "${plannedWorktreePath}")"\` then \`git -C "${repoPath}" worktree add --no-track -b "${BRANCH}" "${plannedWorktreePath}" origin/<default>\`. If the branch already exists, \`git -C "${repoPath}" worktree add "${plannedWorktreePath}" "${BRANCH}"\`.
5. On the tree: \`git -C "<tree>" rev-parse --abbrev-ref HEAD\` and \`git -C "<tree>" rev-parse --path-format=absolute --git-common-dir\`.

Report:
- ok: true when the tree exists on a branch that is not the default branch.
- repoPath: the WORKTREE path (never the repository path above unless you reused it as the tree).
- branch: the branch step 5 printed.
- reused: true if you reused an existing tree.
- gitCommonDir: the git-common-dir step 5 printed.
- defaultBranch: the default branch from step 1.
- blocked: one short sentence for each thing that stopped you or that you worked around.`,
  {
    label: 'workspace:provision',
    effort: 'low',
    phase: 'Workspace',
    agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['ok', 'repoPath', 'branch', 'reused'],
      properties: {
        ok: { type: 'boolean' },
        repoPath: { type: 'string' },
        branch: { type: 'string' },
        reused: { type: 'boolean' },
        gitCommonDir: { type: 'string' },
        defaultBranch: { type: 'string' },
        blocked: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

if (!provisioned) {
  return refuse('the provisioner returned nothing, so no worktree was established', {
    dispatchFailed: true,
    dispatchFailures: [{ label: 'workspace:provision', phase: 'Workspace', outcome: 'no-result' }],
  })
}
const blocked = Array.isArray(provisioned.blocked) ? provisioned.blocked : []
if (provisioned.ok !== true) {
  return { ...refuse('the provisioner could not establish a worktree (ok=false)'), blocked: ['the provisioner could not establish a worktree (ok=false)', ...blocked] }
}

const reported = String(provisioned.repoPath || '').trim().replace(/\/+$/, '')
const treePath = reported && reported !== repoPath ? reported : plannedWorktreePath
const branch = String(provisioned.branch || '').trim() || BRANCH
const defaultBranch = String(provisioned.defaultBranch || '').trim().replace(/^refs\/heads\//, '').replace(/^origin\//, '') || null
const normalized = branch.replace(/^refs\/heads\//, '').replace(/^origin\//, '').toLowerCase()

if (['main', 'master', 'head'].includes(normalized) || (defaultBranch && normalized === defaultBranch.toLowerCase())) {
  return { ...refuse(`the worktree ${treePath} is on "${branch}", a default branch or a detached HEAD`), blocked: [`the worktree ${treePath} is on "${branch}", a default branch or a detached HEAD`, ...blocked] }
}

log(`Workspace: ${provisioned.reused ? 'reused' : 'created'} worktree ${treePath} on ${branch}`)

return {
  ok: true,
  applicable: true,
  repoPath: treePath,
  branch,
  reused: provisioned.reused === true,
  isLinkedWorktree: true,
  independentlyVerified: true,
  defaultBranch,
  verification: { gitCommonDir: String(provisioned.gitCommonDir || '').trim() || null, branch, defaultBranch },
  blocked,
  ledger: { phase: 'workspace', beadId, branch, reused: provisioned.reused === true, ok: true },
}
