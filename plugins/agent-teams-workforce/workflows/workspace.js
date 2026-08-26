export const meta = {
  name: 'workspace',
  description:
    'Leaf mini — establishes the WORKTREE every writing phase then works in. It is the structural mirror of the settle step: settle LANDS the tree on every exit path, workspace ESTABLISHES it before the first write. A git-worktree-provisioner fetches, fast-forwards, reuses an existing tree for the same bead or cuts a new one on a feature branch under `.worktrees/<bead>-<repo>`, and verifies the result really is a LINKED worktree (git-dir != git-common-dir) on a branch that is not the default. Its return value is the sole source of the contract repoPath — the caller-supplied path is an input to this step, never the tree the phases write in.',
  phases: [{ title: 'Workspace', detail: 'provision or reuse the linked worktree the writing phases operate in' }],
}

// args: {
//   repoPath: string,      // the repository (or an already-established worktree) to work from
//   beadId: string,        // the work item — names the branch and the worktree directory
//   branchPrefix?: string, // 'fix' (bug), 'feat' (task), 'infra' (infra change). Default 'work'.
//   purpose?: string,      // one line, for the log and the branch description
// }
const a = (typeof args === 'string' ? JSON.parse(args) : args) || {}
const repoPath = String(a.repoPath || '').trim()
const beadId = String(a.beadId || '').trim()
const prefix = String(a.branchPrefix || 'work').trim().replace(/[^a-zA-Z0-9._-]/g, '') || 'work'

// Fail closed. A workspace step that "succeeds" with no path hands the writing phases
// whatever tree they happen to be standing in, which is the exact failure this mini
// exists to prevent — production work stranded, uncommitted, on main in a main tree.
if (!repoPath) {
  return { ok: false, applicable: false, repoPath: null, branch: null, reused: false, blocked: ['no repoPath supplied — refusing to provision a worktree without a repository'] }
}
if (!beadId) {
  return { ok: false, applicable: false, repoPath: null, branch: null, reused: false, blocked: ['no beadId supplied — the branch and worktree directory are named after the work item'] }
}

phase('Workspace')

const BRANCH = `${prefix}/${beadId}`

const provisioned = await agent(
  `Establish the git worktree this run's writing phases will operate in, then report exactly what you established. Do not write any project code here — this step only provisions the tree.

Repository or existing worktree given: ${repoPath}
Work item: ${beadId}${a.purpose ? ` — ${a.purpose}` : ''}
Branch to use: ${BRANCH}

Every git command runs as \`git -C "<path>"\`. Never \`cd\` into a tree and rely on the ambient directory; you may be running inside an isolation copy of a different repository, so a bare \`git status\` can inspect the wrong tree entirely. Never redirect stderr to /dev/null — errors must stay visible.

STEP 1 — IS THE PATH ALREADY A LINKED WORKTREE?
\`\`\`
git -C "${repoPath}" rev-parse --git-dir
git -C "${repoPath}" rev-parse --git-common-dir
git -C "${repoPath}" rev-parse --abbrev-ref HEAD
\`\`\`
When --git-dir and --git-common-dir DIFFER, the path is already a linked worktree. If it is also on a branch that is not the default branch, REUSE IT: report it as the worktree with reused=true and stop. A resumed or re-dispatched run must land in the same tree as the attempt before it — in a fresh tree it cannot see the earlier run's tests, and the most expensive phase in the pipeline is paid for twice.

STEP 2 — OTHERWISE THE PATH IS A MAIN WORKING TREE. Find the repository root and the default branch:
\`\`\`
REPO=$(git -C "${repoPath}" rev-parse --show-toplevel)
DEFAULT=$(git -C "$REPO" symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
\`\`\`
If that ref is missing, fall back to main, then master, whichever exists.

STEP 3 — LOOK BEFORE YOU CUT. A tree for this bead may already exist:
\`\`\`
git -C "$REPO" worktree list --porcelain
\`\`\`
If one is already registered for ${beadId}, REUSE it. Report its path and its branch with reused=true and stop.

STEP 4 — BRANCH FROM THE CURRENT TIP, NOT A STALE REF. A worktree cut from an older commit silently omits work that already landed, and the Red survey — looking for tests that ARE committed but absent from this tree — finds nothing and re-authors what was just paid for:
\`\`\`
git -C "$REPO" fetch origin "$DEFAULT"
\`\`\`
Fast-forward the main tree onto origin only when it is safe to: the tree is clean, HEAD is the default branch, and the local branch is an ancestor of the remote one. Otherwise do NOT force anything — record the divergence in \`blocked\` and cut from the local tip anyway, naming what you saw.

STEP 5 — CUT THE TREE. The fleet convention is a \`.worktrees/\` directory BESIDE the repository, named \`<bead>-<repo>\` with any \`SkillSpoke-\` prefix stripped from the repo name. Match the layout already in use in that \`.worktrees\` directory if one exists; inventing a third layout scatters the fleet's worktrees where the next run will not find them.
\`\`\`
WT="$(dirname "$REPO")/.worktrees/${beadId}-$(basename "$REPO" | sed 's/^SkillSpoke-//')"
git -C "$REPO" worktree add -b "${BRANCH}" "$WT" "$(git -C "$REPO" rev-parse "$DEFAULT")"
\`\`\`
If the branch name is already taken, add the existing branch instead of creating it (\`git -C "$REPO" worktree add "$WT" "${BRANCH}"\`) rather than inventing a second branch name.

STEP 6 — VERIFY, DO NOT ASSUME. The whole point of this step is that the tree is real and is NOT the main working tree:
\`\`\`
git -C "$WT" rev-parse --git-dir
git -C "$WT" rev-parse --git-common-dir
git -C "$WT" rev-parse --abbrev-ref HEAD
git -C "$WT" log --oneline -1
\`\`\`
The two dir values MUST differ, and HEAD MUST NOT be the default branch. If either check fails, report ok=false with the observed values in \`blocked\` — do not report a worktree you did not actually verify.

Report: the absolute worktree path, its branch, whether you reused an existing tree, and the verification output as evidence.`,
  {
    label: 'workspace:provision',
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
        isLinkedWorktree: { type: 'boolean' },
        evidence: { type: 'string' },
        blocked: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// A missing or unusable result is a failure, never a shrug. The caller must be able to
// refuse to run rather than write into whichever tree it was pointed at.
if (!provisioned || provisioned.ok !== true || !String(provisioned.repoPath || '').trim()) {
  return {
    ok: false,
    applicable: true,
    repoPath: null,
    branch: null,
    reused: false,
    blocked: (provisioned && provisioned.blocked) || ['the workspace step returned no verified worktree'],
    evidence: (provisioned && provisioned.evidence) || null,
  }
}

log(
  `Workspace: ${provisioned.reused ? 'REUSED' : 'created'} worktree ${provisioned.repoPath} on ${provisioned.branch || BRANCH} — every writing phase inherits this tree`
)

return {
  ok: true,
  applicable: true,
  repoPath: String(provisioned.repoPath).trim(),
  branch: provisioned.branch || BRANCH,
  reused: provisioned.reused === true,
  isLinkedWorktree: provisioned.isLinkedWorktree !== false,
  evidence: provisioned.evidence || null,
  blocked: provisioned.blocked || [],
  ledger: { phase: 'workspace', beadId, branch: provisioned.branch || BRANCH, reused: provisioned.reused === true, ok: true },
}
