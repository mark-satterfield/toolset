export const meta = {
  name: 'workspace',
  description:
    'Leaf mini — establishes the WORKTREE every writing phase then works in. It is the structural mirror of the settle step: settle LANDS the tree on every exit path, workspace ESTABLISHES it before the first write. A git-worktree-provisioner fetches, fast-forwards, reuses an existing tree for the same bead or cuts a new one on a feature branch under `.worktrees/<bead>-<repo>` — and then a SECOND, independently dispatched read-only verifier, told nothing about what the provisioner claimed, reports the raw git facts for that path. The SCRIPT rules on the two accounts and refuses anything it cannot reconcile: the provisioner must affirm isLinkedWorktree=true (absent refuses — it is not the safe answer), the branch must be neither a default branch nor a detached HEAD, the independent account must agree about the branch, git-dir must differ from git-common-dir, and the tree must share a git-common-dir with the repository the CALLER named. Its return value is the sole source of the contract repoPath — the caller-supplied path is an input to this step, never the tree the phases write in.',
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
const refuse = (reason) => ({
  ok: false,
  applicable: true,
  repoPath: null,
  branch: null,
  reused: false,
  blocked: [reason, ...((provisioned && Array.isArray(provisioned.blocked) && provisioned.blocked) || [])],
  evidence: (provisioned && provisioned.evidence) || null,
})

if (!provisioned || provisioned.ok !== true || !String(provisioned.repoPath || '').trim()) {
  return refuse(
    ((provisioned && Array.isArray(provisioned.blocked) && provisioned.blocked[0]) ||
      'the workspace step returned no verified worktree')
  )
}

// ── SCRIPT-SIDE VERIFICATION ───────────────────────────────────────────────────
// Everything above this line asks the provisioner to verify; nothing until here
// CHECKED it. That gap is the original defect reproduced through the new code path:
// `{ ok: true, repoPath: <the repository's MAIN working tree>, branch: 'main' }` was
// accepted verbatim and handed to a code-WRITING phase — the very tree, and the very
// branch, that stranded nine test files on main.
//
// Both guards below are pure comparisons of the values the provisioner reported. They
// need no shell, no filesystem, and no git. Each REFUSES; none defaults to the
// safe-sounding answer, because defaulting to it is the bug.
const DEFAULT_BRANCHES = new Set(['main', 'master'])
const normalizeBranch = (b) =>
  String(b || '')
    .trim()
    .replace(/^refs\/heads\//, '')
    .replace(/^origin\//, '')
    .toLowerCase()

// (a) The linked-worktree claim must be AFFIRMATIVE. `isLinkedWorktree` is optional in
// the schema, so the previous `!== false` test handed the safe answer to exactly the
// model that never looked. Absent is not verified. Absent refuses.
if (provisioned.isLinkedWorktree !== true) {
  return refuse(
    `the provisioner did not affirm isLinkedWorktree=true for ${String(provisioned.repoPath).trim()} ` +
      `(reported: ${JSON.stringify(provisioned.isLinkedWorktree)}). An unverified tree is a MAIN working ` +
      'tree until proven otherwise — this step refuses rather than hand one to a writing phase.'
  )
}

// (b) HEAD MUST NOT be the default branch. The prompt has said so since 6.0.5 and
// nothing enforced it. An unreported branch falls back to BRANCH, which is
// `<prefix>/<beadId>` and therefore can never be a default branch.
const effectiveBranch = String(provisioned.branch || '').trim() || BRANCH
const normalized = normalizeBranch(effectiveBranch)
if (DEFAULT_BRANCHES.has(normalized) || normalized === 'head') {
  return refuse(
    `the provisioned tree ${String(provisioned.repoPath).trim()} reports HEAD as "${effectiveBranch}" — ` +
      'the default branch (or a detached HEAD) is the one place the project\'s own rules forbid writing. ' +
      'Every writing phase inherits this tree, so it is refused here rather than discovered at settle.'
  )
}

// The path every later comparison is about. Trimmed once, here: a trailing space
// silently breaks every `git -C` after it.
const verifiedPath = String(provisioned.repoPath).trim()

// ── SEGREGATION OF DUTIES: a SECOND, INDEPENDENT account of the same tree ──────
//
// What replaced the shelling-out layer, and why it had to be replaced.
//
// 6.0.6 tried to close this hole from inside the script by dynamically importing Node's
// process-spawning module. The real runner REJECTS a dynamic import STATICALLY, with a
// SyntaxError saying the construct is not available in workflow scripts. The
// rejection is total and happens at LOAD: one dynamic import anywhere in the file —
// even inside a function that is never called — makes the whole script unloadable.
// workspace.js is the first phase of all three composites, so 6.0.6 could not start
// a run at all.
//
// The token itself is deliberately absent from this file, comments included. How the
// runner detects the construct is not documented, so a raw scan is possible, and a
// comment that reintroduced the token could reintroduce the outage. Nothing under
// workflows/ may contain it; scripts/check-workflow-syntax.mjs enforces that against
// the raw bytes, for the same reason.
//
// A workflow script receives ONLY args, agent, workflow, phase, log, parallel and
// budget. There is no filesystem, no process spawning, no require and no module
// loading, so a script-side git check is impossible BY CONSTRUCTION. Do not look for
// another way to shell out; there isn't one.
//
// What the git layer was for is still real: the two guards above compare what the
// provisioner SAID, and neither can catch a provisioner that says it correctly while
// handing back something else. So the check moves from a shell to this plugin's own
// doctrine — segregation of duties. A SECOND agent, dispatched separately, running
// read-only, and told NOTHING about what the provisioner claimed, reports the raw git
// facts. The SCRIPT then compares the two accounts. An affirmative lie now costs two
// separately-dispatched agents independently agreeing on it.
//
// The verifier is told the path and the caller's repository, because it must be told
// WHERE to look. It is never told the branch, the reuse flag, the isLinkedWorktree
// claim, or that a claim exists at all — a verifier shown the answer is not a verifier.
const verified = await agent(
  `Report the raw git facts about two filesystem paths. Report ONLY what git prints. Do not create, move, repair, check out, fetch or delete anything, and do not judge whether what you find is correct — another step rules on that. Your entire job is to be an independent observation.

PATH UNDER INSPECTION: ${verifiedPath}
CALLER'S REPOSITORY:   ${repoPath}

Run every command as \`git -C "<path>"\` exactly as written. Never \`cd\` into a tree and rely on the ambient directory — you may be running inside an isolation copy of a different repository, so a bare \`git status\` can inspect the wrong tree entirely. Never redirect stderr to /dev/null; both streams to a readable log is fine, discarding errors is not.

1. THE PATH UNDER INSPECTION
\`\`\`
git -C "${verifiedPath}" rev-parse --path-format=absolute --git-dir
git -C "${verifiedPath}" rev-parse --path-format=absolute --git-common-dir
git -C "${verifiedPath}" rev-parse --abbrev-ref HEAD
\`\`\`
Report these as \`gitDir\`, \`gitCommonDir\` and \`branch\`. If \`--path-format=absolute\` is not supported by this git, run the same rev-parse without it and resolve the result to an absolute path yourself against the path under inspection, and say so in \`notes\`.

2. THE CALLER'S REPOSITORY
\`\`\`
git -C "${repoPath}" rev-parse --path-format=absolute --git-common-dir
git -C "${repoPath}" symbolic-ref --short refs/remotes/origin/HEAD
\`\`\`
Report these as \`callerCommonDir\` and \`callerDefaultBranch\`. Strip any leading \`origin/\` from the default branch. If that ref does not exist, leave \`callerDefaultBranch\` EMPTY and say so in \`notes\` — do not guess "main", and do not substitute the branch the repository happens to have checked out.

3. Report the literal output of every command you ran as \`evidence\`.

Every value you report must be the literal output of the command that produced it. If a command does not answer, leave its field EMPTY and name the failure in \`notes\` — one failing probe must not discard an answer another probe already gave, and an inferred value is worse than an absent one, because the script cannot tell them apart. Set \`ok\` false only if you could not run git at all.`,
  {
    label: 'workspace:independent-verify',
    phase: 'Workspace',
    agentType: 'agent-teams-workforce:worktree-independent-verifier',
    schema: {
      type: 'object',
      additionalProperties: false,
      required: ['ok', 'gitDir', 'gitCommonDir', 'branch', 'callerCommonDir'],
      properties: {
        ok: { type: 'boolean' },
        gitDir: { type: 'string' },
        gitCommonDir: { type: 'string' },
        branch: { type: 'string' },
        callerCommonDir: { type: 'string' },
        callerDefaultBranch: { type: 'string' },
        evidence: { type: 'string' },
        notes: { type: 'array', items: { type: 'string' } },
      },
    },
  }
)

// The independent report is now the PRIMARY control, not an optional extra, so a
// missing or unusable one REFUSES. 6.0.6's git layer could fall through when it was
// unavailable because two other guards were still standing; this replaces the layer
// those guards could not cover, and falling through here would restore the exact hole
// it exists to close.
const seen = (v) => String((verified && v) || '').trim()
if (!verified || verified.ok !== true) {
  return refuse(
    'no independent verification of the provisioned tree was obtained — the workspace step ' +
      'refuses to certify a tree on the sole authority of the agent that created it.'
  )
}

const obsGitDir = seen(verified.gitDir)
const obsCommonDir = seen(verified.gitCommonDir)
const obsBranch = seen(verified.branch)
const obsCallerCommonDir = seen(verified.callerCommonDir)
const obsDefaultBranch = normalizeBranch(verified.callerDefaultBranch)

// Trailing separators and `/.` make two spellings of one directory compare unequal.
const canonicalDir = (d) => String(d || '').trim().replace(/\/+\.?$/, '') || ''

if (!obsGitDir || !obsCommonDir || !obsBranch || !obsCallerCommonDir) {
  return refuse(
    'the independent verification came back incomplete ' +
      `(git-dir: ${JSON.stringify(obsGitDir)}, git-common-dir: ${JSON.stringify(obsCommonDir)}, ` +
      `branch: ${JSON.stringify(obsBranch)}, caller git-common-dir: ${JSON.stringify(obsCallerCommonDir)}). ` +
      'A partial observation cannot rule out the thing it was dispatched to rule out.' +
      (Array.isArray(verified.notes) && verified.notes.length ? ` Reported: ${verified.notes.join('; ')}` : '')
  )
}

// (c) A LINKED worktree has a git-dir distinct from its git-common-dir. When they are
// equal the path is a MAIN working tree — the original incident — however confidently
// the provisioner reported otherwise.
if (canonicalDir(obsGitDir) === canonicalDir(obsCommonDir)) {
  return refuse(
    `an independent check reports ${verifiedPath} is a MAIN working tree — its --git-dir and ` +
      `--git-common-dir are both "${obsGitDir}" — contradicting the provisioner's isLinkedWorktree=true.`
  )
}

// (d) RESIDUAL 1 — the returned tree must belong to the repository the CALLER named.
// Both guards above pass for a genuine linked worktree of an UNRELATED repository on a
// feature branch: every writing phase then works in the wrong repository and settle
// opens a PR against it. Linked worktrees of one repository all share that repository's
// git-common-dir, so comparing the two absolute common-dirs settles it exactly.
if (canonicalDir(obsCommonDir) !== canonicalDir(obsCallerCommonDir)) {
  return refuse(
    `the provisioned tree ${verifiedPath} belongs to a DIFFERENT repository than the caller asked ` +
      `for: its --git-common-dir is "${obsCommonDir}" while ${repoPath} reports "${obsCallerCommonDir}". ` +
      'It may well be a real worktree on a real feature branch — of the wrong repository. Every writing ' +
      'phase would edit that repository and settle would open a PR against it.'
  )
}

// (e) The two accounts must AGREE about the branch. A provisioner reporting a feature
// branch over a tree git says is on another one is the affirmative lie this whole
// second dispatch exists to detect.
if (normalizeBranch(obsBranch) !== normalizeBranch(effectiveBranch)) {
  return refuse(
    `the two accounts of ${verifiedPath} disagree: the provisioner reported branch ` +
      `"${effectiveBranch}", an independent check reports "${obsBranch}". A tree whose own branch is ` +
      'in dispute is not a tree any writing phase may inherit.'
  )
}

// (f) RESIDUAL 3 — the default branch is whatever THIS repository's origin/HEAD says it
// is. `main` and `master` remain a FLOOR, never the whole test: a repo whose default is
// `develop` or `trunk` was completely unprotected while the hardcoded pair was the only
// check. An unobtainable origin/HEAD narrows the test back to the floor; it never
// widens it to a guess.
const observedNormalized = normalizeBranch(obsBranch)
if (DEFAULT_BRANCHES.has(observedNormalized) || observedNormalized === 'head' || (obsDefaultBranch && observedNormalized === obsDefaultBranch)) {
  return refuse(
    `an independent check reports HEAD at ${verifiedPath} is "${obsBranch}" — ` +
      (obsDefaultBranch && observedNormalized === obsDefaultBranch
        ? `the default branch of ${repoPath} as origin/HEAD names it`
        : 'a default branch or a detached HEAD') +
      '. That is the one place the project\'s own rules forbid writing, and every writing phase ' +
      'inherits this tree.'
  )
}

log(
  `Workspace: ${provisioned.reused ? 'REUSED' : 'created'} worktree ${verifiedPath} on ${effectiveBranch} — ` +
    'independently verified as a linked worktree of the caller\'s repository; every writing phase inherits this tree'
)

return {
  ok: true,
  applicable: true,
  repoPath: verifiedPath,
  branch: effectiveBranch,
  reused: provisioned.reused === true,
  isLinkedWorktree: true,
  // The affirmative marker the composites require before they will run a writing phase.
  // A 6.0.5-shaped result — or any result that skipped the independent account — carries
  // no such field, so it cannot be mistaken for a verified one.
  independentlyVerified: true,
  // The real default branch, so the settle guards test against THIS repository's default
  // rather than a hardcoded pair. Null means unobtainable, which narrows those guards
  // back to their floor.
  defaultBranch: obsDefaultBranch || null,
  verification: {
    gitDir: obsGitDir,
    gitCommonDir: obsCommonDir,
    branch: obsBranch,
    callerCommonDir: obsCallerCommonDir,
    defaultBranch: obsDefaultBranch || null,
    notes: Array.isArray(verified.notes) ? verified.notes : [],
  },
  evidence: provisioned.evidence || null,
  blocked: provisioned.blocked || [],
  ledger: {
    phase: 'workspace',
    beadId,
    branch: effectiveBranch,
    reused: provisioned.reused === true,
    independentlyVerified: true,
    ok: true,
  },
}
