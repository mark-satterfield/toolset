export const meta = {
  name: 'settle',
  description:
    'Lands a worktree in git: commits, pushes the branch and opens the pull request with the project PR command. With commitOnly it commits on the branch and stops: no push, no pull request. Returns { status }: not-applicable (no tree), blocked (no PR command), error (the landing agent failed), or reported (treeClean, hasWork, branch, prUrl, commit, blocked).',
  phases: [{ title: 'Settle', detail: 'commit, push and open the pull request' }],
}

// Retries a dispatch that failed transiently (overload, rate limit, network) with capped backoff;
// returns null, or rethrows when opts.rethrow, on any other failure.
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
  const { rethrow, ...call } = opts || {}
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
      if (rethrow) throw err
      return null
    }
  }
}

// args: { repoPath: string|null, prCommand: string|null, branch?: string|null, defaultBranch?: string|null, isLinkedWorktree?: boolean,
//         commitOnly?: boolean, message?: string }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const wt = typeof a.repoPath === 'string' && a.repoPath.trim() ? a.repoPath.trim() : null
const prCommand = typeof a.prCommand === 'string' && a.prCommand.trim() ? a.prCommand.trim() : null
const baseName = String(a.defaultBranch || '').trim().replace(/^refs\/heads\//, '').replace(/^origin\//, '') || 'main'
const baseRef = `origin/${baseName}`
const commitOnly = a.commitOnly === true
const message = String(a.message || '').replace(/\s+/g, ' ').trim()

const COMMIT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['treeClean', 'hasWork', 'branch', 'commit'],
  properties: {
    treeClean: { type: 'boolean' },
    hasWork: { type: 'boolean' },
    branch: { type: 'string' },
    commit: { type: 'string' },
    blocked: { type: 'array', items: { type: 'string' } },
  },
}

async function commitRun() {
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written' }
  try {
    const reported = await settleAgent(
      `Commit every change in the worktree ${wt} on its current branch, or say exactly why it could not be committed.

Run every git command as \`git -C "${wt}"\`.
1. \`git -C "${wt}" rev-parse --abbrev-ref HEAD\`. If it prints ${baseName} or HEAD, commit nothing and name it in \`blocked\`.
2. \`git -C "${wt}" status --porcelain\`. Report \`hasWork\`: true if it printed anything.
3. If hasWork, \`git -C "${wt}" add -A\` and commit as \`type(scope): description\`${message ? ` (the change: ${message})` : ''} with NO Co-Authored-By header. \`--no-verify\` is forbidden; when a hook fails, fix every finding, stage the fixes and commit again; if a finding cannot be fixed, abort with NO commit and name it in \`blocked\`.
4. Do not push, do not open a pull request, and do not merge.
5. Report the branch, \`git -C "${wt}" rev-parse HEAD\` as \`commit\`, and whether \`git -C "${wt}" status --porcelain\` is now empty as \`treeClean\`.`,
      { label: 'settle:commit', rethrow: true, phase: 'Settle', agentType: 'agent-teams-workforce:github-actions-pipeline-implementer', schema: COMMIT_SCHEMA }
    )
    if (!reported) return { status: 'error', error: 'the commit agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`commit failed: ${error}`)
    return { status: 'error', error }
  }
}

async function settleRun() {
  if (!wt) return { status: 'not-applicable', reason: 'the run established no repo path, so nothing was written' }
  if (!prCommand) {
    return { status: 'blocked', reason: `settle has no PR command (args.prCommand, ATW_PR_COMMAND) to land the work in ${wt} with; the work is left in the worktree.` }
  }
  try {
    const reported = await settleAgent(
      `Land every change in the worktree ${wt}, or say exactly why it could not be landed.

Run every git command as \`git -C "${wt}"\`, and \`cd "${wt}"\` before the PR command.
1. \`git -C "${wt}" status --porcelain\`. Commit anything uncommitted as \`type(scope): description\` with NO Co-Authored-By header. \`--no-verify\` is forbidden; if a hook finding cannot be fixed, abort with NO commit and name it in \`blocked\`.
2. If \`git -C "${wt}" rev-parse --abbrev-ref --symbolic-full-name @{u}\` resolves to ${baseRef}, run \`git -C "${wt}" branch --unset-upstream\`. Never push to the default branch.
3. \`git -C "${wt}" fetch origin ${baseName}\`. Report \`hasWork\`: true if the tree was dirty or the branch has commits not reachable from ${baseRef}.
4. If hasWork, \`cd "${wt}" && ${prCommand} --title "<type(scope): description>" --body "<what changed>"\`. It pushes the branch and opens the pull request. Never open the PR another way and never merge it. A PR that already exists for this head is success; report its URL.
5. Report the PR URL, the branch, and whether the tree is clean.`,
      {
        label: 'settle:land-work',
        rethrow: true,
        phase: 'Settle',
        agentType: 'agent-teams-workforce:github-actions-pipeline-implementer',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['treeClean', 'hasWork', 'branch', 'prUrl'],
          properties: {
            treeClean: { type: 'boolean' },
            hasWork: { type: 'boolean' },
            branch: { type: 'string' },
            prUrl: { type: 'string' },
            blocked: { type: 'array', items: { type: 'string' } },
          },
        },
      }
    )
    if (!reported) return { status: 'error', error: 'the settle agent returned no result' }
    return { status: 'reported', ...reported }
  } catch (e) {
    const error = e && e.message ? e.message : String(e)
    log(`settle failed: ${error}`)
    return { status: 'error', error }
  }
}

phase('Settle')
return commitOnly ? await commitRun() : await settleRun()
